import asyncio
import pytest


@pytest.fixture(scope="session")
@pytest.mark.async_timeout(0.01)
async def fixture_timeout_in_setup_session():
    await asyncio.sleep(1)
    yield 1


@pytest.fixture(scope="session")
@pytest.mark.async_timeout(0.01)
async def fixture_timeout_session():
    await asyncio.sleep(1)
    return 1


@pytest.fixture(scope="session", autouse=True)
@pytest.mark.async_timeout(0.01)
async def fixture_timeout_in_teardown_session():
    try:
        yield 1
    finally:
        await asyncio.sleep(1)
