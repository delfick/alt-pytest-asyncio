import asyncio

import pytest


class TestAClass:
    @pytest.fixture()
    @pytest.mark.async_timeout(0.01)
    async def fixture_timeout(self):
        await asyncio.sleep(1)
        return 1

    @pytest.fixture()
    @pytest.mark.async_timeout(0.01)
    async def fixture_timeout_in_setup(self):
        await asyncio.sleep(1)
        yield 1

    @pytest.fixture()
    @pytest.mark.async_timeout(0.01)
    async def fixture_timeout_in_teardown(self):
        try:
            yield 1
        finally:
            await asyncio.sleep(1)

    def test_2one(self, fixture_timeout):
        pass

    def test_2two(self, fixture_timeout_in_setup):
        pass

    def test_2three(self, fixture_timeout_in_teardown):
        pass

    def test_2four(self, fixture_timeout_in_teardown_session):
        pass
