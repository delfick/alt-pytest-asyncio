import asyncio
from collections.abc import AsyncGenerator

import pytest

import alt_pytest_asyncio

AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout


@pytest.fixture()
async def fixture_timeout_in_finally(async_timeout: AsyncTimeout) -> AsyncGenerator[int]:
    async_timeout.set_timeout_seconds(0.01)

    try:
        yield 1
    finally:
        await asyncio.sleep(1)


@pytest.fixture()
async def fixture_timeout_in_setup(async_timeout: AsyncTimeout) -> AsyncGenerator[int]:
    async_timeout.set_timeout_seconds(0.01)
    await asyncio.sleep(1)
    yield 1


@pytest.fixture()
async def fixture_timeout(async_timeout: AsyncTimeout) -> int:
    async_timeout.set_timeout_seconds(0.01)
    await asyncio.sleep(1)
    return 1


@pytest.fixture(scope="module")
async def fixture_timeout_in_setup_module(async_timeout: AsyncTimeout) -> AsyncGenerator[int]:
    async_timeout.set_timeout_seconds(0.01)
    await asyncio.sleep(1)
    yield 1


@pytest.fixture(scope="module", autouse=True)
async def fixture_timeout_in_teardown_module(async_timeout: AsyncTimeout) -> AsyncGenerator[int]:
    async_timeout.set_timeout_seconds(0.01)
    try:
        yield 1
    finally:
        await asyncio.sleep(1)


@pytest.fixture(scope="module")
async def fixture_timeout_module(async_timeout: AsyncTimeout) -> int:
    async_timeout.set_timeout_seconds(0.01)
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
