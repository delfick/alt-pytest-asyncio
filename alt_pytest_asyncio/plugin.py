import asyncio
import contextvars
import dataclasses
import inspect
import sys
from collections import defaultdict
from collections.abc import Callable, Coroutine, Iterator
from functools import partial, wraps
from types import TracebackType
from typing import TYPE_CHECKING, Self

import pytest
from _pytest._code.code import ExceptionInfo

from alt_pytest_asyncio.async_converters import convert_fixtures, converted_async_test


class AltPytestAsyncioPlugin:
    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self.own_loop = False
        self.test_tasks: dict[asyncio.AbstractEventLoop, list[asyncio.Task[object]]] = defaultdict(
            list
        )

        if loop is None:
            self.own_loop = True
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        self.loop = loop
        self.ctx = contextvars.copy_context()

    def pytest_configure(self, config: pytest.Config) -> None:
        """Register our timeout marker which is used to signify async timeouts"""
        config.addinivalue_line(
            "markers", "async_timeout(length): mark async test to have a timeout"
        )

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> Iterator[None]:
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
                    self.loop.run_until_complete(asyncio.tasks.gather(*ts, return_exceptions=True))
            yield
        finally:
            if self.own_loop:
                try:
                    cancel_all_tasks(self.loop)
                finally:
                    self.loop.close()

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_fixture_setup(
        self, fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest
    ) -> Iterator[None]:
        """Convert async fixtures to sync fixtures"""
        convert_fixtures(self.ctx, fixturedef, request, request.node)
        yield

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_pyfunc_call(self, pyfuncitem: pytest.Function) -> Iterator[None]:
        """Convert async tests to sync tests"""
        if inspect.iscoroutinefunction(pyfuncitem.obj):
            timeout_marker = pyfuncitem.get_closest_marker("async_timeout")

            if timeout_marker:
                timeout = float(timeout_marker.args[0])
            else:
                timeout = float(
                    pyfuncitem.config.getoption("default_async_timeout", None)
                    or pyfuncitem.config.getini("default_async_timeout")
                )

            o = pyfuncitem.obj
            pyfuncitem.obj = wraps(o)(
                partial(converted_async_test, self.ctx, self.test_tasks, o, timeout)
            )
        else:
            original: Callable[..., object] = pyfuncitem.obj

            @wraps(original)
            def run_obj(*args: object, **kwargs: object) -> None:
                try:
                    self.ctx.run(lambda: None)

                    def run(func: Callable[..., object]) -> object:
                        return self.ctx.run(func)

                except RuntimeError:

                    def run(func: Callable[..., object]) -> object:
                        return func()

                run(partial(original, *args, **kwargs))

            pyfuncitem.obj = run_obj

        yield


def cancel_all_tasks(
    loop: asyncio.AbstractEventLoop,
    ignore_errors_from_tasks: list[asyncio.Task[object]] | None = None,
) -> None:
    to_cancel = asyncio.tasks.all_tasks(loop)

    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    gathered = asyncio.tasks.gather(*to_cancel, return_exceptions=True)
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


def run_coro_as_main(
    loop: asyncio.AbstractEventLoop, coro: Coroutine[object, object, None]
) -> None:
    @dataclasses.dataclass(frozen=True, kw_only=True)
    class Captured(Exception):
        error: BaseException

    try:

        async def runner() -> None:
            __tracebackhide__ = True

            try:
                await coro
            except:
                exc_type, exc, tb = sys.exc_info()
                if TYPE_CHECKING:
                    assert exc_type is not None
                    assert exc is not None
                    assert tb is not None

                exc.__traceback__ = tb
                raise Captured(error=exc)

        task = loop.create_task(runner())
        loop.run_until_complete(task)
    except:
        exc_type, exc, tb = sys.exc_info()
        if (
            isinstance(exc_type, type)
            and issubclass(exc_type, Captured)
            and isinstance(exc, Captured)
        ):
            exc = exc.error
            exc_type = type(exc)
            tb = exc.__traceback__

        if TYPE_CHECKING:
            assert exc_type is not None
            assert exc is not None
            assert tb is not None

        info = ExceptionInfo[BaseException]((exc_type, exc, tb), "")
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

    loop: asyncio.AbstractEventLoop | None

    def __init__(self, new_loop: bool = True) -> None:
        self.tasks: list[asyncio.Task[object]] = []
        self.new_loop = new_loop

    def __enter__(self) -> Self:
        self._original_loop = asyncio.get_event_loop_policy().get_event_loop()

        if self.new_loop:
            self.loop = asyncio.new_event_loop()
        else:
            self.loop = None

        asyncio.set_event_loop(self.loop)
        return self

    def __exit__(self, exc_typ: type[Exception], exc: Exception, tb: TracebackType) -> None:
        try:
            if self.loop is not None:
                cancel_all_tasks(self.loop, ignore_errors_from_tasks=self.tasks)
                self.loop.run_until_complete(self.shutdown_asyncgens())
                self.loop.close()
        finally:
            if hasattr(self, "_original_loop"):
                asyncio.set_event_loop(self._original_loop)

    async def shutdown_asyncgens(self) -> None:
        """
        A version of loop.shutdown_asyncgens that tries to cancel the generators
        before closing them.
        """
        if self.loop is None:
            return

        asyncgens = getattr(self.loop, "_asyncgens", None)
        assert asyncgens is not None
        if not len(asyncgens):
            return

        closing_agens = list(asyncgens)
        asyncgens.clear()

        # I would do an asyncio.tasks.gather but it would appear that just causes
        # the asyncio loop to think it's shutdown, so I have to do them one at a time
        for ag in closing_agens:
            try:
                try:
                    try:
                        await ag.athrow(asyncio.CancelledError())
                    except StopAsyncIteration:
                        pass
                finally:
                    await ag.aclose()
            except asyncio.CancelledError:
                pass
            except:
                exc = sys.exc_info()[1]
                self.loop.call_exception_handler(
                    {
                        "message": "an error occurred during closing of asynchronous generator",
                        "exception": exc,
                        "asyncgen": ag,
                    }
                )

    def run_until_complete(self, coro: Coroutine[object, object, None]) -> None:
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
