import abc
from collections.abc import Callable
from typing import NoReturn, Protocol


class AsyncTimeout(abc.ABC):
    run_count: int
    error: BaseException | None

    @abc.abstractmethod
    def set_timeout_seconds(self, timeout: float) -> None: ...

    @abc.abstractmethod
    def use_default_timeout(self) -> None: ...

    @abc.abstractmethod
    def raise_maybe(self, func: Callable[..., object]) -> None: ...


class AsyncTimeoutMaker(Protocol):
    def __call__(self) -> AsyncTimeout: ...


class AsyncTimeoutProvider(abc.ABC):
    @abc.abstractmethod
    def load(self, *, default_timeout: float) -> AsyncTimeout: ...

    @abc.abstractmethod
    def set_timeout_seconds(self, timeout: float) -> NoReturn: ...
