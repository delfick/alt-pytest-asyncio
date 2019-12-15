from alt_pytest_asyncio.plugin import AltPytestAsyncioPlugin, run_coro_as_main
import nest_asyncio
import asyncio
import pytest
import sys


async def my_tests():
    fut = loop.create_future()

    class Plugin:
        def pytest_addoption(self, parser):
            parser.addoption("--test-socket")

        @pytest.fixture(scope="session")
        def test_fut(self):
            return fut

    plugins = [Plugin(), AltPytestAsyncioPlugin(loop)]

    code = pytest.main(sys.argv[1:], plugins=plugins)
    assert fut.done()

    if code != 0:
        raise Exception(repr(code))


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    nest_asyncio.apply(loop)
    run_coro_as_main(loop, my_tests())
