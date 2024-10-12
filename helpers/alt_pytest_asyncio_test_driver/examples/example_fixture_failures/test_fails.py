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


def test_fails_on_fixture_returns(fixture_returns):
    pass


def test_fails_on_fixture_yields(fixture_yields):
    pass


def test_fails_on_fixture_fails_in_finally(fixture_fails_in_finally):
    pass
