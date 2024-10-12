import asyncio
from collections.abc import Coroutine
from typing import Protocol, TypeVar

T_Ret = TypeVar("T_Ret")


class Loop(Protocol):
    controlled_loop: asyncio.AbstractEventLoop | None

    def run_until_complete(self, coro: Coroutine[object, object, T_Ret]) -> T_Ret: ...
