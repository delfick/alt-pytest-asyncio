import asyncio

import alt_pytest_asyncio

AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout


async def test_within_cli_timeout(async_timeout: AsyncTimeout) -> None:
    await asyncio.sleep(0.03)


# Note that there is a bit in the tests_examples.py that sets the timeout with the cli
async def test_outside_cli_timeout(async_timeout: AsyncTimeout) -> None:
    await asyncio.sleep(0.1)
