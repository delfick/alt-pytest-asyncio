# coding: spec

import asyncio
import pytest

describe "a class":
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

    it "2one", fixture_timeout:
        pass

    it "2two", fixture_timeout_in_setup:
        pass

    it "2three", fixture_timeout_in_teardown:
        pass

    it "2four", fixture_timeout_in_teardown_session:
        pass
