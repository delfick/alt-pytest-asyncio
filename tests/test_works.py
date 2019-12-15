# coding: spec

import asyncio
import pytest


@pytest.fixture()
async def a_value():
    return 1


@pytest.fixture()
async def a_value_times_two(a_value):
    """Make sure coroutine fixtures can receive other fixtures"""
    return a_value * 2


@pytest.fixture(scope="module")
async def a_list_fut():
    fut = asyncio.Future()
    fut.set_result([])
    return fut


@pytest.fixture(scope="module")
async def a_list(a_list_fut):
    lst = await a_list_fut
    try:
        yield lst
    finally:
        assert set(lst) == set(range(4))


async it "works for async functions", a_list:
    await asyncio.sleep(0.01)
    a_list.append(0)
    assert True

it "works for non async functions", a_list:
    a_list.append(1)
    assert True

describe "A class":
    async it "works for async methods", a_list:
        await asyncio.sleep(0.01)
        a_list.append(2)
        assert True

    it "works for non async methods", a_list:
        a_list.append(3)
        assert True

    it "uses our fixtures", a_value_times_two:
        assert a_value_times_two == 2
