from collections.abc import AsyncGenerator
from typing import NoReturn

import pytest


async def one() -> NoReturn:
    await two()


async def two() -> NoReturn:
    raise ValueError("WAT")


@pytest.fixture()
async def fixture_returns() -> NoReturn:
    await one()


@pytest.fixture()
async def fixture_yields() -> AsyncGenerator[None]:
    yield await one()


@pytest.fixture()
async def fixture_fails_in_finally() -> AsyncGenerator[int]:
    try:
        yield 1
    finally:
        await one()


_done_iterator: bool = False
_done_result: bool = False
_done_finally: bool = False


@pytest.fixture()
async def fixture_fails_once_iterator() -> AsyncGenerator[None]:
    global _done_iterator
    if _done_iterator:
        return

    _done_iterator = True
    yield await one()


@pytest.fixture()
async def fixture_fails_once_result() -> None:
    global _done_result
    if _done_result:
        return

    _done_result = True
    await one()


@pytest.fixture()
async def fixture_fails_once_finally() -> AsyncGenerator[None]:
    try:
        yield
    finally:
        global _done_finally
        if _done_finally:
            return

        _done_finally = True
        await one()


def test_fails_on_fixture_returns(fixture_returns: int) -> None:
    pass


def test_fails_on_fixture_yields(fixture_yields: int) -> None:
    pass


def test_fails_on_fixture_fails_in_finally(fixture_fails_in_finally: int) -> None:
    pass


def test_fails_fixture_failure_does_not_linger_first_iterator(
    fixture_fails_once_iterator: None,
) -> None:
    pass


def test_fails_fixture_failure_does_not_linger_second_iterator(
    fixture_fails_once_iterator: None,
) -> None:
    pass


def test_fails_fixture_failure_does_not_linger_first_result(
    fixture_fails_once_result: None,
) -> None:
    pass


def test_fails_fixture_failure_does_not_linger_second_result(
    fixture_fails_once_result: None,
) -> None:
    pass


def test_fails_fixture_failure_does_not_linger_first_finally(
    fixture_fails_once_finally: None,
) -> None:
    pass


def test_fails_fixture_failure_does_not_linger_second_finally(
    fixture_fails_once_finally: None,
) -> None:
    pass
