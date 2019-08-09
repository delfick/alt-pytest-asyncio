from alt_pytest_asyncio.async_converters import convert_fixtures, converted_async_test

from _pytest._code.code import ExceptionInfo
from functools import partial, wraps
import inspect
import asyncio
import pytest
import sys

class AltPytestAsyncioPlugin:
    def __init__(self, loop=None):
        self.own_loop = False
        self.test_tasks = []

        if loop is None:
            self.own_loop = True
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self.loop = loop

    @pytest.fixture(scope="session")
    def event_loop(self):
        """The loop to run our fixtures and tests in"""
        return self.loop

    def pytest_configure(self, config):
        """Register our timeout marker which is used to signify async timeouts"""
        config.addinivalue_line("markers", "async_timeout(length): mark async test to have a timeout")

    def pytest_sessionfinish(self, session, exitstatus):
        """
        Make sure all the test coroutines have been finalized once pytest has finished

        Also, if we created our own loop, then cancel any remaining tasks on it and close it.

        This is so if pytest is interrupted, we still execute the finally blocks of all the tests
        """
        ts = []
        for task in self.test_tasks:
            ts.append(task)
            task.cancel()

        self.loop.run_until_complete(asyncio.tasks.gather(*ts, loop=self.loop, return_exceptions=True))

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
                timeout = 60

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
                  { 'message': 'unhandled exception during shutdown'
                  , 'exception': task.exception()
                  , 'task': task
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
