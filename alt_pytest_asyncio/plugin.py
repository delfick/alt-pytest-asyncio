import asyncio
import contextlib
import contextvars
import inspect
from collections import defaultdict
from collections.abc import Callable, Iterator
from functools import partial, wraps
from types import TracebackType

import pytest

from . import async_converters, errors, loop_manager


@pytest.hookimpl
def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Will add a pytest option for default async timeouts
    """
    desc = "timeout in seconds before failing a test. This can be overriden with @pytest.mark.async_timeout(<my_timeout>)"

    group = parser.getgroup(
        "alt-pytest-asyncio", description="Alternative asyncio pytest plugin options"
    )
    group.addoption("--default-async-timeout", type=float, dest="default_async_timeout", help=desc)
    parser.addini(
        "default_async_timeout",
        desc,
        default=5,
    )


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
        self._test_tasks: dict[asyncio.AbstractEventLoop, list[asyncio.Task[object]]] = (
            defaultdict(list)
        )
        self._ctx = contextvars.copy_context()

    def pytest_configure(self, config: pytest.Config) -> None:
        """Register our timeout marker which is used to signify async timeouts"""
        config.addinivalue_line(
            "markers", "async_timeout(length): mark async test to have a timeout"
        )

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
            for loop, tasks in self._test_tasks.items():
                ts = []
                for t in tasks:
                    if not t.done():
                        t.cancel()
                        ts.append(t)

                if ts:
                    loop.run_until_complete(asyncio.tasks.gather(*ts, return_exceptions=True))
            yield
        finally:
            if _cm := getattr(self, "_cm", None):
                _cm.close()

    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_fixture_setup(
        self, fixturedef: pytest.FixtureDef[object], request: pytest.FixtureRequest
    ) -> Iterator[None]:
        """Convert async fixtures to sync fixtures"""
        async_converters.convert_fixtures(self._ctx, fixturedef, request, request.node)
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
                partial(
                    async_converters.converted_async_test, self._ctx, self._test_tasks, o, timeout
                )
            )
        else:
            original: Callable[..., object] = pyfuncitem.obj

            @wraps(original)
            def run_obj(*args: object, **kwargs: object) -> None:
                try:
                    self._ctx.run(lambda: None)

                    def run(func: Callable[..., object]) -> object:
                        return self._ctx.run(func)

                except RuntimeError:

                    def run(func: Callable[..., object]) -> object:
                        return func()

                run(partial(original, *args, **kwargs))

            pyfuncitem.obj = run_obj

        yield
