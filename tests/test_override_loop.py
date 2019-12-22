# coding: spec

from alt_pytest_asyncio.plugin import OverrideLoop

import asyncio
import pytest


@pytest.fixture()
def fut():
    return asyncio.Future()


async def things(futs, loop_info, works=False):
    found = []

    async def setter():
        await asyncio.sleep(0.05)
        futs["a"].set_result(None)
        futs["b"].set_result(None)

    task = asyncio.get_event_loop().create_task(setter())

    try:
        if not works:
            loop_info["thingsa"] = asyncio.get_event_loop()

        if works:
            found.append(await futs["a"])
        else:
            try:
                found.append(await futs["a"])
            except RuntimeError as error:
                assert "attached to a different loop" in str(error)

        found.append(await futs["b"])
    finally:
        if not works:
            loop_info["thingsb"] = asyncio.get_event_loop()

        if works:
            assert found == [None, None]
        else:
            assert found == [None]


it "won't let you do run_until_complete outside the context manager":

    info = {"coro": None}

    async def blah():
        pass

    try:
        coro = info["coro"] = blah()
        OverrideLoop().run_until_complete(coro)
        assert False, "should have risen an error"
    except Exception as error:
        msg = (
            "Cannot use run_until_complete on OverrideLoop outside of using it as a context manager"
        )
        assert str(error) == msg

    assert info["coro"] is not None
    asyncio.get_event_loop().run_until_complete(info["coro"])

it "can replace the loop", fut:
    info = {}
    futs = {"a": fut}

    info["original"] = asyncio.get_event_loop()

    with OverrideLoop() as custom_loop:
        futs["b"] = asyncio.Future()

        info["before_run"] = asyncio.get_event_loop()

        custom_loop.run_until_complete(things(futs, info))

        info["after_run"] = asyncio.get_event_loop()

        assert all(not l.is_closed() for l in info.values())

    original = info.pop("original")
    assert not original.is_closed()
    assert all(l.is_closed() for l in info.values())

    assert len(set([l for l in info.values()])) == 1
    assert len(set([*info.values(), original])) == 2


@pytest.fixture()
def loop_info():
    return {}


describe "no new loop":
    it "sets None":
        info = {"coro": None}

        original = asyncio.get_event_loop()

        with OverrideLoop(new_loop=False) as custom_loop:
            msg = "There is no current event loop in thread.*"
            try:
                assert asyncio.get_event_loop() is None
                assert False, "should have risen an error"
            except Exception as error:
                assert str(error).startswith("There is no current event loop in thread")

            try:

                async def blah():
                    pass

                coro = info["coro"] = blah()

                custom_loop.run_until_complete(coro)
                assert False, "should have risen an error"
            except Exception as error:
                msg = "OverrideLoop is not managing your overridden loop, use run_until_complete on that loop instead"
                assert str(error) == msg

        assert asyncio.get_event_loop() is original
        assert not original.is_closed()

        assert info["coro"] is not None
        asyncio.get_event_loop().run_until_complete(info["coro"])


describe "testing autouse":

    @pytest.fixture(autouse=True)
    def custom_loop(self, loop_info):
        assert not loop_info
        loop_info["original"] = asyncio.get_event_loop()

        with OverrideLoop() as custom_loop:
            assert loop_info["original"] is not asyncio.get_event_loop()
            yield custom_loop

        assert list(loop_info) == [
            "original",
            "fix1",
            "fix2",
            "fix3a",
            "fix4a",
            "fix5a",
            "test",
            "fix4b",
            "fix4c",
            "fix3b",
            "fix3c",
        ]
        self.assertLoopInfo(loop_info, closed=True)

    def assertLoopInfo(self, loop_info, *, closed):
        original = loop_info["original"]
        rest = [l for k, l in loop_info.items() if k != "original"]

        assert not original.is_closed()
        if closed:
            assert all(l.is_closed() for l in rest)
        else:
            assert all(not l.is_closed() for l in rest)

        assert len(set([l for l in rest])) == 1
        assert len(set([*rest, original])) == 2

    @pytest.fixture(autouse=True)
    async def fix1(self, custom_loop, loop_info):
        loop_info["fix1"] = asyncio.get_event_loop()

    @pytest.fixture()
    async def fix2(self, loop_info):
        loop_info["fix2"] = asyncio.get_event_loop()

    @pytest.fixture()
    async def fix3(self, loop_info):
        loop_info["fix3a"] = asyncio.get_event_loop()
        try:
            yield
            loop_info["fix3b"] = asyncio.get_event_loop()
        finally:
            loop_info["fix3c"] = asyncio.get_event_loop()

    @pytest.fixture()
    def fix4(self, loop_info):
        loop_info["fix4a"] = asyncio.get_event_loop()
        try:
            yield
            loop_info["fix4b"] = asyncio.get_event_loop()
        finally:
            loop_info["fix4c"] = asyncio.get_event_loop()

    @pytest.fixture()
    def fix5(self, loop_info):
        loop_info["fix5a"] = asyncio.get_event_loop()

    it "works", fix1, fix2, fix3, fix4, fix5, loop_info:
        loop_info["test"] = asyncio.get_event_loop()
        assert list(loop_info) == ["original", "fix1", "fix2", "fix3a", "fix4a", "fix5a", "test"]
        self.assertLoopInfo(loop_info, closed=False)

    it "has the loop on custom_loop", custom_loop, fix1, fix2, fix3, fix4, fix5, loop_info:
        loop_info["test"] = asyncio.get_event_loop()
        assert list(loop_info) == ["original", "fix1", "fix2", "fix3a", "fix4a", "fix5a", "test"]
        assert custom_loop.loop is asyncio.get_event_loop()
        self.assertLoopInfo(loop_info, closed=False)

    it "can use futures from fixtures", custom_loop, fix1, fix2, fix3, fix4, fix5, loop_info, fut:
        loop_info["test"] = asyncio.get_event_loop()

        futs = {"a": fut, "b": asyncio.Future()}
        custom_loop.run_until_complete(things(futs, loop_info, works=True))
