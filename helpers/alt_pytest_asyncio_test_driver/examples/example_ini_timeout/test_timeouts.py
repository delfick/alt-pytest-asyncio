import asyncio

import alt_pytest_asyncio

AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout


async def test_within_ini_timeout(async_timeout: AsyncTimeout) -> None:
    await asyncio.sleep(0.03)


async def test_outside_ini_timeout(async_timeout: AsyncTimeout) -> None:
    await asyncio.sleep(0.1)
