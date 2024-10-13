import asyncio
from collections.abc import AsyncGenerator

import pytest

import alt_pytest_asyncio

AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout


@pytest.fixture(scope="session")
async def fixture_timeout_in_setup_session(async_timeout: AsyncTimeout) -> AsyncGenerator[int]:
    async_timeout.set_timeout_seconds(0.01)
    await asyncio.sleep(1)
    yield 1


@pytest.fixture(scope="session")
async def fixture_timeout_session(async_timeout: AsyncTimeout) -> int:
    async_timeout.set_timeout_seconds(0.01)
    await asyncio.sleep(1)
    return 1


@pytest.fixture(scope="session", autouse=True)
async def fixture_timeout_in_teardown_session(async_timeout: AsyncTimeout) -> AsyncGenerator[int]:
    async_timeout.set_timeout_seconds(0.01)
    try:
        yield 1
    finally:
        await asyncio.sleep(1)
