import asyncio
import pytest


async def _coro():
    await asyncio.sleep(0.1)
    return "works"


@pytest.mark.no_default_loop
def test_with_custom_loop():
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(_coro())
    assert res == "works"
    loop.close()
