import asyncio
from collections.abc import AsyncGenerator

import pytest

import alt_pytest_asyncio

AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout


class TestAClass:
    @pytest.fixture()
    async def fixture_timeout(self, async_timeout: AsyncTimeout) -> int:
        async_timeout.set_timeout_seconds(0.01)
        await asyncio.sleep(1)
        return 1

    @pytest.fixture()
    async def fixture_timeout_in_setup(self, async_timeout: AsyncTimeout) -> AsyncGenerator[int]:
        async_timeout.set_timeout_seconds(0.01)
        await asyncio.sleep(1)
        yield 1

    @pytest.fixture()
    async def fixture_timeout_in_teardown(
        self, async_timeout: AsyncTimeout
    ) -> AsyncGenerator[int]:
        async_timeout.set_timeout_seconds(0.01)
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
