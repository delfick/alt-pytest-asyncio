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


def test_fails_on_fixture_returns(fixture_returns: int) -> None:
    pass


def test_fails_on_fixture_yields(fixture_yields: int) -> None:
    pass


def test_fails_on_fixture_fails_in_finally(fixture_fails_in_finally: int) -> None:
    pass
