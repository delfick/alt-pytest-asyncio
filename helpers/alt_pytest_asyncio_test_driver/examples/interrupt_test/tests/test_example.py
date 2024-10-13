import asyncio
from collections.abc import AsyncGenerator

import pytest

import alt_pytest_asyncio

AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout


@pytest.fixture()
async def thing() -> AsyncGenerator[int]:
    try:
        yield 1
    finally:
        print("THING FINALLY")


async def test_aa_has_a_passing_test() -> None:
    pass


async def test_bb_shows_failed_tests() -> None:
    assert False, "NOOOOO"


async def test_cc_shows_timedout_tests(async_timeout: AsyncTimeout) -> None:
    async_timeout.set_timeout_seconds(1)
    await asyncio.sleep(3)


async def test_dd_executes_finally_on_interrupt(pytestconfig: pytest.Config, thing: int) -> None:
    async def wat() -> None:
        while True:
            await asyncio.sleep(0.1)

    asyncio.get_event_loop().create_task(wat())

    try:
        await asyncio.sleep(10)
    finally:
        print("TEST FINALLY")


async def test_ee_does_not_try_to_make_a_test_after_loop_is_closed() -> None:
    await asyncio.get_event_loop().create_future()
