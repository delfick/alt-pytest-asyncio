import asyncio
import contextvars
import inspect
import sys
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from functools import wraps
from typing import TYPE_CHECKING, Any

import pytest

from . import base, machinery, protocols

_PytestScopes = ["function", "class", "module", "package", "session"]


class Converter:
    def __init__(self) -> None:
        self._ctx = contextvars.copy_context()
        self._test_tasks: dict[asyncio.AbstractEventLoop, list[asyncio.Task[object]]] = (
            defaultdict(list)
        )

    def _cleanup_completed_tasks(self) -> None:
        """
        Remove references to completed tasks to they can be garbage collected, including the
        return (or yielded) values of the fixture functions, which would otherwise leak memory.
        """
        for loop, tasks in list(self._test_tasks.items()):
            if loop.is_closed():
                continue

            remaining: list[asyncio.Task[object]] = []
            finished: list[asyncio.Task[object]] = []
            for t in tasks:
                if not t.done():
                    remaining.append(t)
                else:
                    t.cancel()
                    finished.append(t)

            self._test_tasks[loop] = remaining

            if finished:
                loop.run_until_complete(asyncio.tasks.gather(*finished, return_exceptions=True))

    def _add_new_task(self, loop: asyncio.AbstractEventLoop, task: asyncio.Task[object]) -> None:
        self._cleanup_completed_tasks()
        self._test_tasks[loop].append(task)

    def sessionfinish(self) -> None:
        for loop, tasks in self._test_tasks.items():
            ts = []
            for t in tasks:
                if not t.done():
                    t.cancel()
                    ts.append(t)

            if ts:
                loop.run_until_complete(asyncio.tasks.gather(*ts, return_exceptions=True))

    def convert_fixturedef(
        self, fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest
    ) -> None:
        if not hasattr(fixturedef, "func"):
            return

        if hasattr(fixturedef.func, "__alt_asyncio_pytest_converted__"):
            fixturedef.func = fixturedef.func.__alt_asyncio_pytest_original__  # type: ignore[misc,attr-defined]

        original = fixturedef.func

        if inspect.iscoroutinefunction(fixturedef.func):
            async_timeout_maker = self._get_async_timeout_maker(
                request.scope, request.getfixturevalue
            )
            self._convert_async_coroutine_fixture(fixturedef, request, async_timeout_maker)

        elif inspect.isasyncgenfunction(fixturedef.func):
            async_timeout_maker = self._get_async_timeout_maker(
                request.scope, request.getfixturevalue
            )
            self._convert_async_gen_fixture(fixturedef, request, async_timeout_maker)

        elif inspect.isgeneratorfunction(fixturedef.func):
            self._convert_sync_gen_fixture(fixturedef)

        else:
            self._convert_sync_fixture(fixturedef)

        fixturedef.func.__alt_asyncio_pytest_converted__ = True  # type: ignore[attr-defined]
        fixturedef.func.__alt_asyncio_pytest_original__ = original  # type: ignore[attr-defined]

    def convert_pyfunc(self, pyfuncitem: pytest.Function) -> None:
        if inspect.iscoroutinefunction(pyfuncitem.obj):
            _obj: Any = pyfuncitem.obj
            func: Callable[..., Awaitable[object]] = _obj

            async_timeout_maker = self._get_async_timeout_maker(
                "function", pyfuncitem._request.getfixturevalue
            )

            @wraps(func)
            def run_test(*args: object, **kwargs: object) -> object:
                async_timeout = async_timeout_maker()
                res = self._run(async_timeout, func, args, kwargs)
                async_timeout.raise_maybe(func)
                return res

            pyfuncitem.obj = run_test
        else:
            original: Callable[..., object] = pyfuncitem.obj
            pyfuncitem.obj = machinery.run_sync_with_ctx(self._ctx, original)

    def _convert_async_coroutine_fixture(
        self,
        fixturedef: pytest.FixtureDef[object],
        request: pytest.FixtureRequest,
        async_timeout_maker: base.AsyncTimeoutMaker,
    ) -> None:
        """
        Run our async fixture in our event loop and capture the error from
        inside the loop.
        """
        _func: Any = fixturedef.func
        func: Callable[..., Awaitable[object]] = _func

        @wraps(func)
        def run_fixture(*args: object, **kwargs: object) -> object:
            __tracebackhide__ = True

            async_timeout = async_timeout_maker()
            res = self._run(async_timeout, func, args, kwargs)
            async_timeout.raise_maybe(func)
            return res

        fixturedef.func = run_fixture  # type: ignore[misc]

    def _convert_async_gen_fixture(
        self,
        fixturedef: pytest.FixtureDef[object],
        request: pytest.FixtureRequest,
        async_timeout_maker: base.AsyncTimeoutMaker,
    ) -> None:
        """
        Return the yield'd value from the generator and ensure the generator is
        finished.
        """
        _generator: Any = fixturedef.func
        generator: Callable[..., AsyncGenerator[object]] = _generator

        @wraps(generator)
        def run_fixture(*args: object, **kwargs: object) -> object:
            __tracebackhide__ = True

            async_timeout = async_timeout_maker()

            if "async_timeout" in kwargs:
                kwargs["async_timeout"] = async_timeout

            gen_obj = generator(*args, **kwargs)

            def finalizer() -> None:
                """Yield again, to finalize."""
                __tracebackhide__ = True

                if not async_timeout.run_count > 0:
                    return

                async def async_finalizer() -> None:
                    __tracebackhide__ = True

                    async_timeout.use_default_timeout()
                    if not isinstance(async_timeout.error, StopAsyncIteration):
                        await self._async_runner(async_timeout, gen_obj.__anext__, (), {})

                    if async_timeout.error is None:
                        async_timeout.error = ValueError(
                            "Async generator fixture should only yield once"
                        )

                self._run(async_timeout, async_finalizer, (), {})
                async_timeout.raise_maybe(generator)

            request.addfinalizer(finalizer)

            res = self._run(async_timeout, gen_obj.__anext__, (), {})
            async_timeout.raise_maybe(generator)
            return res

        fixturedef.func = run_fixture  # type: ignore[misc]

    def _convert_sync_fixture(self, fixturedef: pytest.FixtureDef[object]) -> None:
        """
        Used to make sure a non-async fixture is run in our
        asyncio contextvars
        """
        original: Callable[..., object] = fixturedef.func
        fixturedef.func = machinery.run_sync_with_ctx(self._ctx, original)  # type: ignore[misc]

    def _convert_sync_gen_fixture(self, fixturedef: pytest.FixtureDef[object]) -> None:
        """
        Used to make sure a non-async generator fixture is run in our
        asyncio contextvars
        """
        _original: Any = fixturedef.func
        original: Callable[..., Generator[object, None, None]] = _original

        @wraps(original)
        def run_fixture(*args: object, **kwargs: object) -> object:
            cm = original(*args, **kwargs)
            value = machinery.run_sync_with_ctx(self._ctx, cm.__next__)()

            try:
                yield value
                machinery.run_sync_with_ctx(self._ctx, cm.__next__)()
            except StopIteration:
                pass

        fixturedef.func = run_fixture  # type: ignore[misc]

    async def _async_runner(
        self,
        async_timeout: base.AsyncTimeout,
        func: Callable[protocols.P_Args, Awaitable[protocols.T_Ret]],
        args: protocols.P_Args.args,
        kwargs: protocols.P_Args.kwargs,
    ) -> protocols.T_Ret | None:
        try:
            if "async_timeout" in kwargs:
                kwargs["async_timeout"] = async_timeout
            async_timeout.use_default_timeout()
            return await func(*args, **kwargs)
        except:
            __tracebackhide__ = True
            _, e, _ = sys.exc_info()
            if TYPE_CHECKING:
                assert e is not None
            async_timeout.error = e
        finally:
            async_timeout.run_count += 1

        return None

    def _run(
        self,
        async_timeout: base.AsyncTimeout,
        func: Callable[..., Awaitable[protocols.T_Ret]],
        args: object,
        kwargs: object,
    ) -> protocols.T_Ret | None:
        __tracebackhide__ = True

        def silent_done_task(res: asyncio.Future[protocols.T_Ret | None] | None) -> None:
            if res is None:
                return
            if res.cancelled():
                pass
            res.exception()
            return

        loop = asyncio.get_event_loop_policy().get_event_loop()
        task = loop.create_task(
            self._async_runner(async_timeout, func, args, kwargs), context=self._ctx
        )
        task.add_done_callback(silent_done_task)
        self._add_new_task(loop, task)

        return loop.run_until_complete(task)

    def _get_async_timeout_maker(
        self, scope: str, getfixturevalue: Callable[[str], object]
    ) -> base.AsyncTimeoutMaker:
        assert scope in _PytestScopes

        default_timeout: float = 5
        for scope in _PytestScopes[_PytestScopes.index(scope) :]:
            name = "default_async_timeout"
            if scope != "function":
                name = f"{scope}_{name}"

            try:
                default_timeout_fix = getfixturevalue(name)
            except pytest.FixtureLookupError:
                pass
            else:
                assert isinstance(default_timeout_fix, int | float)
                default_timeout = default_timeout_fix
                break

        async_timeout_provider = getfixturevalue("async_timeout")
        assert isinstance(async_timeout_provider, base.AsyncTimeoutProvider)

        return lambda: async_timeout_provider.load(default_timeout=default_timeout)
