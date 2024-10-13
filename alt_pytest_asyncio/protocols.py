import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING, NoReturn, ParamSpec, Protocol, TypeVar, cast

from . import base

T_Ret = TypeVar("T_Ret")
P_Args = ParamSpec("P_Args")


class Loop(Protocol):
    controlled_loop: asyncio.AbstractEventLoop | None

    def run_until_complete(self, coro: Coroutine[object, object, T_Ret]) -> T_Ret: ...


class AsyncTimeout(Protocol):
    def set_timeout_seconds(self, timeout: float) -> None: ...


class AsyncTimeoutFactory(Protocol):
    def __call__(self, *, default_timeout: float) -> base.AsyncTimeout: ...


class AsyncTimeoutProvider(Protocol):
    def load(self, *, default_timeout: float) -> base.AsyncTimeout: ...
    def set_timeout_seconds(self, timeout: float) -> NoReturn: ...


if TYPE_CHECKING:
    _ATP: AsyncTimeout = cast(AsyncTimeoutProvider, None)
