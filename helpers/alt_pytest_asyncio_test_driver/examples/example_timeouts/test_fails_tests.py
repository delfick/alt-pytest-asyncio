import asyncio

import pytest

import alt_pytest_asyncio

AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout


@pytest.fixture
def default_async_timeout() -> float:
    return 0.01


async def test_takes_closest_pytestmark() -> None:
    await asyncio.sleep(0.03)


async def test_takes_pytestmark_on_function(async_timeout: AsyncTimeout) -> None:
    async_timeout.set_timeout_seconds(0.04)
    await asyncio.sleep(0.03)


async def test_takes_pytestmark_on_function2(async_timeout: AsyncTimeout) -> None:
    async_timeout.set_timeout_seconds(0.02)
    await asyncio.sleep(0.03)
