import asyncio
import contextvars
import inspect
from collections import defaultdict
from collections.abc import Callable
from functools import partial, wraps

import pytest

from . import async_converters


class Converter:
    def __init__(self) -> None:
        self._ctx = contextvars.copy_context()
        self._test_tasks: dict[asyncio.AbstractEventLoop, list[asyncio.Task[object]]] = (
            defaultdict(list)
        )

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
        async_converters.convert_fixtures(self._ctx, fixturedef, request, request.node)

    def convert_pyfunc(self, pyfuncitem: pytest.Function) -> None:
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
