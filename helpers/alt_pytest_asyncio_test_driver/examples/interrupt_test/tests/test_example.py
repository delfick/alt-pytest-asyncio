import asyncio

import pytest


@pytest.fixture()
async def thing():
    try:
        yield 1
    finally:
        print("THING FINALLY")


async def test_aa_has_a_passing_test():
    pass


async def test_bb_shows_failed_tests():
    assert False, "NOOOOO"


@pytest.mark.async_timeout(1)
async def test_cc_shows_timedout_tests():
    await asyncio.sleep(3)


async def test_dd_executes_finally_on_interrupt(pytestconfig, thing):
    async def wat():
        while True:
            await asyncio.sleep(0.1)

    asyncio.get_event_loop().create_task(wat())

    try:
        await asyncio.sleep(10)
    finally:
        print("TEST FINALLY")


async def test_ee_does_not_try_to_make_a_test_after_loop_is_closed():
    await asyncio.get_event_loop().create_future()
