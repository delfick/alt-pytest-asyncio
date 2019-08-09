# coding: spec

import asyncio
import pytest

pytestmark = pytest.mark.async_timeout(0.01)

@pytest.fixture()
async def fixture_timeout_in_finally():
    try:
        yield 1
    finally:
        await asyncio.sleep(1)

@pytest.fixture()
async def fixture_timeout_in_setup():
    await asyncio.sleep(1)
    yield 1

@pytest.fixture()
async def fixture_timeout():
    await asyncio.sleep(1)
    return 1

@pytest.fixture(scope="module")
async def fixture_timeout_in_setup_module():
    await asyncio.sleep(1)
    yield 1

@pytest.fixture(scope="module", autouse=True)
async def fixture_timeout_in_teardown_module():
    try:
        yield 1
    finally:
        await asyncio.sleep(1)

@pytest.fixture(scope="module")
async def fixture_timeout_module():
    await asyncio.sleep(1)
    return 1

it "one", fixture_timeout_in_finally:
    pass

it "two", fixture_timeout_in_setup:
    pass

it "three", fixture_timeout:
    pass

it "four", fixture_timeout_in_setup_module:
    pass

it "five", fixture_timeout_module:
    pass

it "six", fixture_timeout_in_setup_session:
    pass

it "seven", fixture_timeout_session:
    pass
