from alt_pytest_asyncio.async_converters import convert_fixtures, converted_async_test

from _pytest._code.code import ExceptionInfo
from functools import partial, wraps
from collections import defaultdict
import inspect
import asyncio
import pytest
import sys


class AltPytestAsyncioPlugin:
    def __init__(self, loop=None):
        self.own_loop = False
        self.test_tasks = defaultdict(list)

        if loop is None:
            self.own_loop = True
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self.loop = loop

    def pytest_configure(self, config):
        """Register our timeout marker which is used to signify async timeouts"""
        config.addinivalue_line(
            "markers", "async_timeout(length): mark async test to have a timeout"
        )

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_sessionfinish(self, session, exitstatus):
        """
        Make sure all the test coroutines have been finalized once pytest has finished

        Also, if we created our own loop, then cancel any remaining tasks on it and close it.

        This is so if pytest is interrupted, we still execute the finally blocks of all the tests
        """
        try:
            for loop, tasks in self.test_tasks.items():
                ts = []
                for t in tasks:
                    if not t.done():
                        t.cancel()
                        ts.append(t)

                if ts:
                    self.loop.run_until_complete(
                        asyncio.tasks.gather(*ts, loop=loop, return_exceptions=True)
                    )
            yield
        finally:
            if self.own_loop:
                try:
                    cancel_all_tasks(self.loop)
                finally:
                    self.loop.close()

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):
        """Convert async fixtures to sync fixtures"""
        convert_fixtures(fixturedef, request, request.node)
        yield

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        """Convert async tests to sync tests"""
        if inspect.iscoroutinefunction(pyfuncitem.obj):
            timeout = pyfuncitem.get_closest_marker("async_timeout")

            if timeout:
                timeout = timeout.args[0]
            else:
                timeout = float(
                    pyfuncitem.config.getoption("default_async_timeout", None)
                    or pyfuncitem.config.getini("default_async_timeout")
                )

            o = pyfuncitem.obj
            pyfuncitem.obj = wraps(o)(partial(converted_async_test, self.test_tasks, o, timeout))
        yield


def cancel_all_tasks(loop, ignore_errors_from_tasks=None):
    if hasattr(asyncio.tasks, "all_tasks"):
        to_cancel = asyncio.tasks.all_tasks(loop)
    else:
        to_cancel = asyncio.Task.all_tasks(loop)

    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    gathered = asyncio.tasks.gather(*to_cancel, loop=loop, return_exceptions=True)
    loop.run_until_complete(gathered)

    for task in to_cancel:
        if task.cancelled():
            continue

        if task.exception() is not None:
            if ignore_errors_from_tasks and task in ignore_errors_from_tasks:
                continue

            loop.call_exception_handler(
                {
                    "message": "unhandled exception during shutdown",
                    "exception": task.exception(),
                    "task": task,
                }
            )


def run_coro_as_main(loop, coro):
    class Captured(Exception):
        def __init__(self, error):
            self.error = error

    try:

        async def runner():
            __tracebackhide__ = True

            try:
                await coro
            except:
                exc_info = sys.exc_info()
                exc_info[1].__traceback__ = exc_info[2]
                raise Captured(exc_info[1])

        task = loop.create_task(runner())
        loop.run_until_complete(task)
    except:
        exc_type, exc, tb = sys.exc_info()
        if issubclass(exc_type, Captured):
            exc = exc.error
            exc_type = type(exc)
            tb = exc.__traceback__
        info = ExceptionInfo((exc_type, exc, tb), "")
        print(info.getrepr(style="short"))
        sys.exit(1)
    finally:
        cancel_all_tasks(loop, ignore_errors_from_tasks=[task])
        loop.close()


class OverrideLoop:
    """
    A context manager that will install a new asyncio loop and then restore the
    original loop on exit.

    Usage looks like::

        from alt_pytest_asyncio.plugin import OverrideLoop

        class TestThing:
            @pytest.fixture(autouse=True)
            def custom_loop(self):
                with OverrideLoop() as custom_loop:
                    yield custom_loop

            def test_thing(self, custom_loop):
                custom_loop.run_until_complete(my_thing())

    By putting the loop into an autouse fixture, all fixtures used by the test
    will have the custom loop. If you want to include module level fixtures too
    then use the OverrideLoop in a module level fixture too.

    OverrideLoop takes in a ``new_loop`` boolean that will make it so no new
    loop is set and asyncio is left with no default loop.

    The new loop itself (or None if new_loop is False) can be found in the
    ``loop`` attribute of the object yielded by the context manager.

    The ``run_until_complete`` on the ``custom_loop`` in the above example will
    do a ``run_until_complete`` on the new loop, but in a way that means you
    won't get ``unhandled exception during shutdown`` errors when the context
    manager closes the new loop.

    When the context manager exits and closes the new loop, it will first cancel
    all tasks to ensure finally blocks are run.
    """

    def __init__(self, new_loop=True):
        self.tasks = []
        self.new_loop = new_loop

    def __enter__(self):
        self._original_loop = asyncio.get_event_loop()

        if self.new_loop:
            self.loop = asyncio.new_event_loop()
        else:
            self.loop = None

        asyncio.set_event_loop(self.loop)
        return self

    def __exit__(self, exc_typ, exc, tb):
        try:
            if getattr(self, "loop", None):
                cancel_all_tasks(self.loop, ignore_errors_from_tasks=self.tasks)
                self.loop.close()
        finally:
            if hasattr(self, "_original_loop"):
                asyncio.set_event_loop(self._original_loop)

    def run_until_complete(self, coro):
        if not hasattr(self, "loop"):
            raise Exception(
                "Cannot use run_until_complete on OverrideLoop outside of using it as a context manager"
            )

        if self.loop is None:
            raise Exception(
                "OverrideLoop is not managing your overridden loop, use run_until_complete on that loop instead"
            )

        task = self.loop.create_task(coro)

        # Add the task so that when we cancel all tasks before closing the loop
        # We don't complain about errors in this particular task
        # As we get the errors risen to the caller via run_until_complete
        self.tasks.append(task)

        return self.loop.run_until_complete(task)
