"""
Helpers for converting async functions into sync functions.

convert_fixtures and converted_async_test are used by the Plugin
to convert async fixtures and async tests.

We try our best to make sure error reporting is short and useful by doing some
hacks with capturing errors inside run_until_complete rather than outside so
that you don't get asyncio internals in the errors.
"""

import asyncio
import contextvars
import inspect
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine, Generator
from functools import wraps
from typing import TYPE_CHECKING, Any, NoReturn, NotRequired, ParamSpec, TypedDict, TypeVar

import pytest

P_Args = ParamSpec("P_Args")
T_Ret = TypeVar("T_Ret")


class RunInfo(TypedDict):
    e: NotRequired[BaseException]
    func: NotRequired[Callable[..., object]]
    ran_once: NotRequired[bool]
    cancelled: bool


class GenRunInfo(RunInfo):
    gen_obj: AsyncGenerator[object]
    finalizer: NotRequired[bool]


def convert_fixtures(
    ctx: contextvars.Context,
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
    node: pytest.Item,
) -> None:
    """Used to replace async fixtures"""
    if not hasattr(fixturedef, "func"):
        return

    if hasattr(fixturedef.func, "__alt_asyncio_pytest_converted__"):
        return

    if inspect.iscoroutinefunction(fixturedef.func):
        convert_async_coroutine_fixture(ctx, fixturedef, request, node)
        fixturedef.func.__alt_asyncio_pytest_converted__ = True  # type: ignore[attr-defined]

    elif inspect.isasyncgenfunction(fixturedef.func):
        convert_async_gen_fixture(ctx, fixturedef, request, node)
        fixturedef.func.__alt_asyncio_pytest_converted__ = True  # type: ignore[attr-defined]

    elif inspect.isgeneratorfunction(fixturedef.func):
        convert_sync_gen_fixture(ctx, fixturedef)
        fixturedef.func.__alt_asyncio_pytest_converted__ = True  # type: ignore[attr-defined]

    else:
        convert_sync_fixture(ctx, fixturedef)
        fixturedef.func.__alt_asyncio_pytest_converted__ = True  # type: ignore[attr-defined]


def convert_sync_fixture(ctx: contextvars.Context, fixturedef: pytest.FixtureDef[object]) -> None:
    """
    Used to make sure a non-async fixture is run in our
    asyncio contextvars
    """
    original: Callable[..., object] = fixturedef.func

    @wraps(original)
    def run_fixture(*args: object, **kwargs: object) -> object:
        try:
            ctx.run(lambda: None)

            def run(func: Callable[..., object], *a: object, **kw: object) -> object:
                return ctx.run(func, *a, **kw)
        except RuntimeError:

            def run(func: Callable[..., object], *a: object, **kw: object) -> object:
                return func(*a, **kw)

        return run(original, *args, **kwargs)

    fixturedef.func = run_fixture  # type: ignore[misc]


def convert_sync_gen_fixture(
    ctx: contextvars.Context, fixturedef: pytest.FixtureDef[object]
) -> None:
    """
    Used to make sure a non-async generator fixture is run in our
    asyncio contextvars
    """
    _original: Any = fixturedef.func
    original: Callable[..., Generator[object, None, None]] = _original

    @wraps(original)
    def run_fixture(*args: object, **kwargs: object) -> object:
        try:
            ctx.run(lambda: None)

            def run(func: Callable[..., object], *a: object, **kw: object) -> object:
                return ctx.run(func, *a, **kw)
        except RuntimeError:

            def run(func: Callable[..., object], *a: object, **kw: object) -> object:
                return func(*a, **kw)

        cm = original(*args, **kwargs)
        value = run(cm.__next__)
        try:
            yield value
            run(cm.__next__)
        except StopIteration:
            pass

    fixturedef.func = run_fixture  # type: ignore[misc]


def converted_async_test(
    ctx: contextvars.Context,
    test_tasks: dict[asyncio.AbstractEventLoop, list[asyncio.Task[object]]],
    func: Callable[P_Args, Awaitable[T_Ret]],
    timeout: float,
    /,
    *args: P_Args.args,
    **kwargs: P_Args.kwargs,
) -> T_Ret:
    """Used to replace async tests"""
    __tracebackhide__ = True

    info: RunInfo = {"cancelled": False}
    loop = asyncio.get_event_loop_policy().get_event_loop()

    def look_at_task(t: asyncio.Task[object]) -> None:
        test_tasks[loop].append(t)

    info["func"] = func

    return _run_and_raise(  # type: ignore[return-value]
        ctx, loop, info, func, async_runner(func, timeout, info, args, kwargs), look_at_task
    )


def _find_async_timeout(func: Callable[..., object], node: pytest.Item) -> float:
    timeout = float(
        node.config.getoption("default_async_timeout", None)
        or node.config.getini("default_async_timeout")
    )

    marker = node.get_closest_marker("async_timeout")
    if marker:
        timeout = marker.args[0]

    if hasattr(func, "pytestmark"):
        for m in func.pytestmark:
            if m.name == "async_timeout":
                timeout = m.args[0]

    return timeout


def _raise_maybe(func: Callable[..., object], info: RunInfo) -> None:
    __tracebackhide__ = True

    if hasattr(func, "__original__"):
        func = func.__original__

    fle = inspect.getfile(func)
    if hasattr(func, "__func__"):
        func = func.__func__
    lineno = func.__code__.co_firstlineno

    def raise_error() -> NoReturn:
        if info["cancelled"]:
            assert False, f"Took too long to complete: {fle}:{lineno}"
        raise info["e"]

    if info.get("e"):
        # Use a separate function so when --tb=short is not set we don't get
        # this entire function in the output
        raise_error()


def _run_and_raise(
    ctx: contextvars.Context,
    loop: asyncio.AbstractEventLoop,
    info: RunInfo,
    func: Callable[P_Args, T_Ret],
    coro: Coroutine[object, object, T_Ret],
    look_at_task: Callable[[asyncio.Task[T_Ret]], None] | None = None,
) -> T_Ret:
    __tracebackhide__ = True

    def silent_done_task(res: asyncio.Future[T_Ret]) -> None:
        if res.cancelled():
            pass
        res.exception()

    task = loop.create_task(coro, context=ctx)
    task.add_done_callback(silent_done_task)

    if look_at_task:
        look_at_task(task)

    res = loop.run_until_complete(task)
    _raise_maybe(func, info)

    return res


def _wrap(
    fixturedef: pytest.FixtureDef[object],
    extras: list[str],
    override: Callable[..., T_Ret],
    func: Callable[P_Args, object],
) -> Callable[P_Args, T_Ret]:
    """
    Used to wrap a fixture so that we get extra information to be given to
    override and remove those extra information from kwargs so that the override
    function can safely execute the function being wrapped.

    for example::

        def my_fixture(one):
            pass

        wrapped = _wrap(fixturedef, ["request"], override, my_fixture)

    can be thought of as replacing my_fixture with::

        def override(extra, *args, **kwargs):
            original_my_fixture(*args, **kwargs)

        def my_fixture(one, request):
            override({"request": ...}, one=one)
    """
    strip = {}

    for extra in extras:
        if extra not in fixturedef.argnames:
            fixturedef.argnames += (extra,)  # type: ignore[misc]
            strip[extra] = True

    @wraps(func)
    def wrapper(*args: P_Args.args, **kwargs: P_Args.kwargs) -> T_Ret:
        __tracebackhide__ = True

        got = {}
        for extra in extras:
            got[extra] = kwargs[extra]
            if extra in strip:
                del kwargs[extra]

        return override(got, *args, **kwargs)

    wrapper.__original__ = func  # type: ignore[attr-defined]

    return wrapper


def convert_async_coroutine_fixture(
    ctx: contextvars.Context,
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
    node: pytest.Item,
) -> None:
    """
    Run our async fixture in our event loop and capture the error from
    inside the loop.
    """
    _func: Any = fixturedef.func
    func: Callable[..., Awaitable[object]] = _func
    timeout = _find_async_timeout(func, node)

    def override(extra: dict[str, object], *args: object, **kwargs: object) -> object:
        __tracebackhide__ = True

        info: RunInfo = {"cancelled": False, "func": func}
        loop = asyncio.get_event_loop_policy().get_event_loop()
        return _run_and_raise(
            ctx, loop, info, func, async_runner(func, timeout, info, args, kwargs)
        )

    fixturedef.func = _wrap(fixturedef, [], override, func)  # type: ignore[misc]


def convert_async_gen_fixture(
    ctx: contextvars.Context,
    fixturedef: pytest.FixtureDef[object],
    request: pytest.FixtureRequest,
    node: pytest.Item,
) -> None:
    """
    Return the yield'd value from the generator and ensure the generator is
    finished.
    """
    _generator: Any = fixturedef.func
    generator: Callable[..., AsyncGenerator[object]] = _generator

    class Extra(TypedDict):
        request: pytest.FixtureRequest

    def override(extra: Extra, *args: object, **kwargs: object) -> object:
        __tracebackhide__ = True

        request = extra["request"]
        loop = asyncio.get_event_loop_policy().get_event_loop()

        timeout = _find_async_timeout(fixturedef.func, node)
        gen_obj = generator(*args, **kwargs)

        info: GenRunInfo = {"gen_obj": gen_obj, "cancelled": False}

        def finalizer() -> None:
            """Yield again, to finalize."""
            __tracebackhide__ = True

            nonlocal info
            if "ran_once" not in info:
                return

            info = {"gen_obj": gen_obj, "finalizer": True, "cancelled": False}

            async def async_finalizer() -> None:
                __tracebackhide__ = True

                await async_runner(gen_obj.__anext__, timeout, info, (), {})
                if "e" in info:
                    if isinstance(info["e"], StopAsyncIteration):
                        del info["e"]
                else:
                    info["e"] = ValueError("Async generator fixture should only yield once")

            _run_and_raise(ctx, loop, info, generator, async_finalizer())

        request.addfinalizer(finalizer)

        return _run_and_raise(
            ctx,
            loop,
            info,
            generator,
            async_runner(gen_obj.__anext__, timeout, info, (), {}),
        )

    fixturedef.func = _wrap(fixturedef, ["request"], override, generator)  # type: ignore[misc]


async def async_runner(
    func: Callable[P_Args, Awaitable[T_Ret]],
    timeout: float,
    info: RunInfo,
    args: P_Args.args,
    kwargs: P_Args.kwargs,
) -> T_Ret | None:
    """
    Run our function until timeout has been reached, at which point we cancel
    this task. We record any exceptions in info so that calling code can extract
    the exception from within the loop.
    """
    info["cancelled"] = False

    current_task = asyncio.current_task()

    def timeout_task(task: asyncio.Task[T_Ret] | None) -> None:
        if task and not task.done():
            # If the debugger is active then don't cancel, so that debugging may continue
            # sys.gettrace is not a language feature and notguaranteed to be available
            # on all python implementations, so we see if it exists
            gettrace = getattr(sys, "gettrace", None)
            if gettrace is None or gettrace() is None:
                info["cancelled"] = True
                task.cancel()

    asyncio.get_event_loop().call_later(timeout, timeout_task, current_task)

    try:
        return await func(*args, **kwargs)
    except:
        __tracebackhide__ = True
        _, e, _ = sys.exc_info()
        if TYPE_CHECKING:
            assert e is not None
        info["e"] = e
    finally:
        info["ran_once"] = True

    return None
