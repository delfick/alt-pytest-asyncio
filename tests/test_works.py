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


async def test_works_for_async_functions(a_list):
    await asyncio.sleep(0.01)
    a_list.append(0)
    assert True


def test_works_for_non_async_functions(a_list):
    a_list.append(1)
    assert True


class TestAClass:
    async def test_works_for_async_methods(self, a_list):
        await asyncio.sleep(0.01)
        a_list.append(2)
        assert True

    def test_works_for_non_async_methods(self, a_list):
        a_list.append(3)
        assert True

    def test_uses_our_fixtures(self, a_value_times_two):
        assert a_value_times_two == 2


@pytest.mark.parametrize("func", [1])
def test_allows_func_as_a_parametrize(func):
    assert func == 1


@pytest.mark.parametrize("func", [1])
async def test_allows_func_as_a_parametrize_for_async_too(func):
    assert func == 1
