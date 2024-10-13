import asyncio
from collections.abc import AsyncGenerator

import pytest


@pytest.fixture(scope="module")
def module_default_async_timeout() -> float:
    return 0.02


@pytest.fixture
def default_async_timeout() -> float:
    return 0.01


@pytest.fixture()
async def fixture_timeout_in_finally() -> AsyncGenerator[int]:
    try:
        yield 1
    finally:
        await asyncio.sleep(1)


@pytest.fixture()
async def fixture_timeout_in_setup() -> AsyncGenerator[int]:
    await asyncio.sleep(1)
    yield 1


@pytest.fixture()
async def fixture_timeout() -> int:
    await asyncio.sleep(1)
    return 1


@pytest.fixture(scope="module")
async def fixture_timeout_in_setup_module() -> AsyncGenerator[int]:
    await asyncio.sleep(1)
    yield 1


@pytest.fixture(scope="module", autouse=True)
async def fixture_timeout_in_teardown_module() -> AsyncGenerator[int]:
    try:
        yield 1
    finally:
        await asyncio.sleep(1)


@pytest.fixture(scope="module")
async def fixture_timeout_module() -> int:
    await asyncio.sleep(1)
    return 1


def test_one(fixture_timeout_in_finally: int) -> None:
    pass


def test_two(fixture_timeout_in_setup: int) -> None:
    pass


def test_three(fixture_timeout: int) -> None:
    pass


def test_four(fixture_timeout_in_setup_module: int) -> None:
    pass


def test_five(fixture_timeout_module: int) -> None:
    pass


def test_six(fixture_timeout_in_setup_session: int) -> None:
    pass


def test_seven(fixture_timeout_session: int) -> None:
    pass
