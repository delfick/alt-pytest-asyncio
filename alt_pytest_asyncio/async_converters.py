"""
Helpers for converting async functions into sync functions.

convert_fixtures and converted_async_test are used by the Plugin
to convert async fixtures and async tests.

We try our best to make sure error reporting is short and useful by doing some
hacks with capturing errors inside run_until_complete rather than outside so
that you don't get asyncio internals in the errors.
"""
from functools import wraps
import asyncio
import inspect
import sys


def convert_fixtures(fixturedef, request, node):
    """Used to replace async fixtures"""
    if not hasattr(fixturedef, "func"):
        return

    if inspect.iscoroutinefunction(fixturedef.func):
        convert_async_coroutine_fixture(fixturedef, request, node)

    elif inspect.isasyncgenfunction(fixturedef.func):
        convert_async_gen_fixture(fixturedef, request, node)


def converted_async_test(test_tasks, func, timeout, *args, **kwargs):
    """Used to replace async tests"""
    __tracebackhide__ = True

    info = {}
    loop = asyncio.get_event_loop()

    def look_at_task(t):
        test_tasks[loop].append(t)

    return _run_and_raise(
        loop, info, func, async_runner(func, timeout, info, args, kwargs), look_at_task
    )


def _find_async_timeout(func, node):
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


def _raise_maybe(func, info):
    __tracebackhide__ = True

    if hasattr(func, "__original__"):
        func = func.__original__

    fle = inspect.getfile(func)
    if hasattr(func, "__func__"):
        func = func.__func__
    lineno = func.__code__.co_firstlineno

    def raise_error():
        __tracebackhide__ = True
        if info["cancelled"]:
            assert False, f"Took too long to complete: {fle}:{lineno}"
        raise info["e"]

    if info.get("e"):
        # Use a separate function so when --tb=short is not set we don't get
        # this entire function in the output
        raise_error()


def _run_and_raise(loop, info, func, coro, look_at_task=None):
    __tracebackhide__ = True

    def silent_done_task(res):
        if res.cancelled():
            pass
        res.exception()

    task = loop.create_task(coro)
    task.add_done_callback(silent_done_task)

    if look_at_task:
        look_at_task(task)

    res = loop.run_until_complete(task)
    _raise_maybe(func, info)

    return res


def _wrap(fixturedef, extras, override, func):
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
            fixturedef.argnames += (extra,)
            strip[extra] = True

    @wraps(func)
    def wrapper(*args, **kwargs):
        __tracebackhide__ = True

        got = {}
        for extra in extras:
            got[extra] = kwargs[extra]
            if extra in strip:
                del kwargs[extra]

        return override(got, *args, **kwargs)

    wrapper.__original__ = func

    return wrapper


def convert_async_coroutine_fixture(fixturedef, request, node):
    """
    Run our async fixture in our event loop and capture the error from
    inside the loop.
    """
    func = fixturedef.func
    timeout = _find_async_timeout(func, node)

    def override(extra, *args, **kwargs):
        __tracebackhide__ = True

        info = {}
        loop = asyncio.get_event_loop()
        return _run_and_raise(loop, info, func, async_runner(func, timeout, info, args, kwargs))

    fixturedef.func = _wrap(fixturedef, [], override, func)


def convert_async_gen_fixture(fixturedef, request, node):
    """
    Return the yield'd value from the generator and ensure the generator is
    finished.
    """
    generator = fixturedef.func

    def override(extra, *args, **kwargs):
        __tracebackhide__ = True

        request = extra["request"]
        loop = asyncio.get_event_loop()

        timeout = _find_async_timeout(fixturedef.func, node)
        gen_obj = generator(*args, **kwargs)

        def finalizer():
            """Yield again, to finalize."""
            __tracebackhide__ = True

            info = {}

            async def async_finalizer():
                __tracebackhide__ = True

                await async_runner(gen_obj.__anext__, timeout, info, (), {})
                if "e" in info:
                    if isinstance(info["e"], StopAsyncIteration):
                        del info["e"]
                else:
                    info["e"] = ValueError("Async generator fixture should only yield once")

            _run_and_raise(loop, info, generator, async_finalizer())

        request.addfinalizer(finalizer)

        info = {}
        return _run_and_raise(
            loop, info, generator, async_runner(gen_obj.__anext__, timeout, info, (), {}),
        )

    fixturedef.func = _wrap(fixturedef, ["request"], override, generator)


async def async_runner(func, timeout, info, args, kwargs):
    """
    Run our function until timeout has been reached, at which point we cancel
    this task. We record any exceptions in info so that calling code can extract
    the exception from within the loop.
    """
    info["cancelled"] = False

    if hasattr(asyncio, "current_task"):
        current_task = asyncio.current_task()
    else:
        current_task = asyncio.Task.current_task()

    def timeout_task(task):
        if not task.done():
            info["cancelled"] = True
            task.cancel()

    asyncio.get_event_loop().call_later(timeout, timeout_task, current_task)

    try:
        return await func(*args, **kwargs)
    except:
        __tracebackhide__ = True
        exc_info = sys.exc_info()
        e = exc_info[1]
        info["e"] = e
