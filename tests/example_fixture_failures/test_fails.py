# coding: spec

import asyncio
import pytest

async def one():
    return await two()

async def two():
    raise ValueError("WAT")

@pytest.fixture()
async def fixture_returns():
    await one()

@pytest.fixture()
async def fixture_yields():
    yield await one()

@pytest.fixture()
async def fixture_fails_in_finally():
    try:
        yield 1
    finally:
        await one()

it "fails on fixture returns", fixture_returns:
    pass

it "fails on fixture yields", fixture_yields:
    pass

it "fails on fixture fails in finally", fixture_fails_in_finally:
    pass
