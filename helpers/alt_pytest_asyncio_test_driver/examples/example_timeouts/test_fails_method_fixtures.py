import asyncio
from collections.abc import AsyncGenerator

import pytest


class TestAClass:
    @pytest.fixture()
    @pytest.mark.async_timeout(0.01)
    async def fixture_timeout(self) -> int:
        await asyncio.sleep(1)
        return 1

    @pytest.fixture()
    @pytest.mark.async_timeout(0.01)
    async def fixture_timeout_in_setup(self) -> AsyncGenerator[int]:
        await asyncio.sleep(1)
        yield 1

    @pytest.fixture()
    @pytest.mark.async_timeout(0.01)
    async def fixture_timeout_in_teardown(self) -> AsyncGenerator[int]:
        try:
            yield 1
        finally:
            await asyncio.sleep(1)

    def test_2one(self, fixture_timeout: int) -> None:
        pass

    def test_2two(self, fixture_timeout_in_setup: int) -> None:
        pass

    def test_2three(self, fixture_timeout_in_teardown: int) -> None:
        pass

    def test_2four(self, fixture_timeout_in_teardown_session: int) -> None:
        pass
