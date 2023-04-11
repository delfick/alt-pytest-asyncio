# coding: spec

import asyncio

import pytest


@pytest.fixture()
async def thing():
    try:
        yield 1
    finally:
        print("THING FINALLY")


async it "aa has a passing test":
    pass

async it "bb shows failed tests":
    assert False, "NOOOOO"


@pytest.mark.async_timeout(1)
async it "cc shows timedout tests":
    await asyncio.sleep(3)

async it "dd executes finally on interrupt", pytestconfig, thing:

    async def wat():
        while True:
            await asyncio.sleep(0.1)

    asyncio.get_event_loop().create_task(wat())

    try:
        await asyncio.sleep(10)
    finally:
        print("TEST FINALLY")

async it "ee doesn't try to make a test after loop is closed":
    await asyncio.get_event_loop().create_future()
