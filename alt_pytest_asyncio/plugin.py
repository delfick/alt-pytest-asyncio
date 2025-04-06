import asyncio
import contextlib
import inspect
import sys
from collections.abc import Callable, Iterator
from types import TracebackType
from typing import TYPE_CHECKING, NoReturn, cast

import pytest

from . import base, converter, errors, loop_manager, protocols


@pytest.hookimpl
def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Will add a pytest option for default async timeouts
    """
    desc = "timeout in seconds before failing a test. This can be overridden with the ``async_timeout`` fixture"

    group = parser.getgroup(
        "alt-pytest-asyncio", description="Alternative asyncio pytest plugin options"
    )
    group.addoption("--default-async-timeout", type=float, dest="default_async_timeout", help=desc)
    parser.addini("default_async_timeout", desc)


class _ManagedLoop(contextlib.AbstractContextManager[None]):
    _original_loop: asyncio.AbstractEventLoop | None

    def __init__(self, *, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def __enter__(self) -> None:
        if hasattr(self, "_original_loop"):
            raise Exception("This context manager is already active")

        try:
            self._original_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._original_loop = None

        asyncio.set_event_loop(self.loop)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not hasattr(self, "_original_loop"):
            return

        if self._original_loop is None:
            asyncio.set_event_loop(None)
        else:
            asyncio.set_event_loop(self._original_loop)

        del self._original_loop


class AltPytestAsyncioPlugin:
    def __init__(self, *, managed_loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._managed_loop = managed_loop
        self._converter = converter.Converter()

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_sessionstart(self, session: pytest.Session) -> Iterator[None]:
        if hasattr(self, "_cm"):
            raise errors.PluginAlreadyStarted()

        self._cm = contextlib.ExitStack()
        if self._managed_loop is None:
            self._cm.enter_context(loop_manager.Loop(new_loop=True))
        else:
            self._cm.enter_context(_ManagedLoop(loop=self._managed_loop))

        yield

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> Iterator[None]:
        """
        Make sure all the test coroutines have been finalized once pytest has finished

        This is so if pytest is interrupted, we still execute the finally blocks of all the tests
        """
        try:
            self._converter.sessionfinish()
            yield
        finally:
            if _cm := getattr(self, "_cm", None):
                _cm.close()

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_fixture_setup(
        self, fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest
    ) -> Iterator[None]:
        """Convert async fixtures to sync fixtures"""
        self._converter.convert_fixturedef(fixturedef, request)
        yield

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_pyfunc_call(self, pyfuncitem: pytest.Function) -> Iterator[None]:
        """Convert async tests to sync tests"""
        self._converter.convert_pyfunc(pyfuncitem)
        yield


class LoadedAsyncTimeout(base.AsyncTimeout):
    def __init__(self, *, default_timeout: float) -> None:
        self.error: BaseException | None = None
        self.timeout: float = default_timeout
        self.cancelled: bool = False
        self.run_count: int = 0
        self._timeout: asyncio.TimerHandle | None = None

    def use_default_timeout(self) -> None:
        self.set_timeout_seconds(self.timeout)

    def set_timeout_seconds(self, timeout: float) -> None:
        if self._timeout:
            self._timeout.cancel()

        self.timeout = timeout
        current_task = asyncio.current_task()

        def timeout_task(task: asyncio.Task[object] | None) -> None:
            if timeout < self.timeout:
                return

            if task and not task.done():
                # If the debugger is active then don't cancel, so that debugging may continue
                # sys.gettrace is not a language feature and not guaranteed to be available
                # on all python implementations, so we see if it exists
                gettrace = getattr(sys, "gettrace", None)
                if gettrace is None or gettrace() is None:
                    self.cancelled = True
                    task.cancel()

        self._timeout = asyncio.get_event_loop().call_later(timeout, timeout_task, current_task)

    def raise_maybe(self, func: Callable[..., object]) -> None:
        __tracebackhide__ = True

        if hasattr(func, "__original__"):
            func = func.__original__

        fle = inspect.getfile(func)
        if hasattr(func, "__func__"):
            func = func.__func__
        lineno = func.__code__.co_firstlineno

        def raise_error() -> None:
            if self.cancelled:
                raise AssertionError(
                    f"Took too long to complete: {fle}:{lineno} (timeout={self.timeout})"
                )
            if self.error:
                raise self.error

        if self.error and not isinstance(self.error, StopAsyncIteration):
            # Use a separate function so when --tb=short is not set we don't get
            # this entire function in the output
            raise_error()


class AsyncTimeoutProvider(base.AsyncTimeoutProvider):
    def __init__(self, timeout_factory: protocols.AsyncTimeoutFactory) -> None:
        self.timeout_factory = timeout_factory

    def load(self, *, default_timeout: float) -> base.AsyncTimeout:
        return self.timeout_factory(default_timeout=default_timeout)

    def set_timeout_seconds(self, timeout: float) -> NoReturn:
        raise errors.NoAsyncTimeoutInSyncFunctions(
            "The async_timeout fixture only makes sense in async fixtures/functions"
        )


@pytest.fixture(scope="session")
def session_default_async_timeout(pytestconfig: pytest.Config) -> float:
    timeout = pytestconfig.getini("default_async_timeout")

    if not timeout:
        timeout = pytestconfig.option.default_async_timeout

    if timeout is None:
        timeout = 5

    return float(timeout)


@pytest.fixture(scope="session")
def async_timeout() -> protocols.AsyncTimeoutProvider:
    """
    This is a special fixture where asking for it in a fixture or a test provides
    an object that matches ``alt_pytest_asyncio.protocols.AsyncTimeout``

    This can be overridden to return an object that sets a different ``load``
    method if that's desirable.
    """
    return AsyncTimeoutProvider(timeout_factory=LoadedAsyncTimeout)


if TYPE_CHECKING:
    _ATP: protocols.AsyncTimeoutProvider = cast(AsyncTimeoutProvider, None)
    _ATPF: protocols.AsyncTimeout = cast(AsyncTimeoutProvider, None)
    _AT: protocols.AsyncTimeout = cast(LoadedAsyncTimeout, None)
    _ATF: protocols.AsyncTimeoutFactory = LoadedAsyncTimeout
