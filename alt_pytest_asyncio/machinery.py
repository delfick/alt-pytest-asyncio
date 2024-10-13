import asyncio
import contextvars
import dataclasses
import functools
import sys
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from _pytest._code.code import ExceptionInfo

P_Args = ParamSpec("P_Args")
T_Ret = TypeVar("T_Ret")


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
        sys.exit(str(info.getrepr(style="short")))
    finally:
        cancel_all_tasks(loop, ignore_errors_from_tasks=[task])
        loop.close()


def run_sync_with_ctx(
    ctx: contextvars.Context, func: Callable[P_Args, T_Ret]
) -> Callable[P_Args, T_Ret]:
    @functools.wraps(func)
    def run(*args: P_Args.args, **kwargs: P_Args.kwargs) -> T_Ret:
        try:
            ctx.run(lambda: None)
        except RuntimeError:
            return func(*args, **kwargs)
        else:
            return ctx.run(func, *args, **kwargs)

    return run
