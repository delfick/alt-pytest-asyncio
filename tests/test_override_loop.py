# coding: spec

from alt_pytest_asyncio.plugin import OverrideLoop

import asyncio
import pytest


def get_event_loop():
    return asyncio.get_event_loop_policy().get_event_loop()


@pytest.fixture()
def fut():
    return get_event_loop().create_future()


async def things(futs, loop_info, works=False):
    found = []

    async def setter():
        await asyncio.sleep(0.05)
        futs["a"].set_result(None)
        futs["b"].set_result(None)

    task = None

    try:
        task = get_event_loop().create_task(setter())

        if not works:
            loop_info["thingsa"] = get_event_loop()

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
            loop_info["thingsb"] = get_event_loop()

        task.cancel()
        await asyncio.wait([task])

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
    get_event_loop().run_until_complete(info["coro"])

it "can replace the loop", fut:
    info = {}
    futs = {"a": fut}

    info["original"] = get_event_loop()

    with OverrideLoop() as custom_loop:
        futs["b"] = get_event_loop().create_future()

        info["before_run"] = get_event_loop()

        custom_loop.run_until_complete(things(futs, info))

        info["after_run"] = get_event_loop()

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

        original = get_event_loop()

        with OverrideLoop(new_loop=False) as custom_loop:
            msg = "There is no current event loop in thread.*"
            try:
                assert get_event_loop() is None
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

        assert get_event_loop() is original
        assert not original.is_closed()

        assert info["coro"] is not None
        get_event_loop().run_until_complete(info["coro"])


it "can shutdown async gens":
    info1 = []
    info2 = []
    info3 = []

    original = asyncio.get_event_loop()

    async def my_generator(info):
        try:
            info.append(1)
            yield
            info.append(2)
            yield
            info.append(3)
        except asyncio.CancelledError:
            info.append("cancelled")
            raise
        finally:
            info.append(("done", __import__("sys").exc_info()[0]))

    # Test that the outside loop isn't affected by the inside loop
    outside_gen = my_generator(info1)

    async def outside1():
        await outside_gen.__anext__()
        await outside_gen.__anext__()

    original.run_until_complete(outside1())
    assert info1 == [1, 2]

    # The way python asyncio works
    # Means that by defining this outside our OverrideLoop
    # The weakref held against it in the _asyncgens set on the loop
    # Will remain so that our shutdown_asyncgens function may work
    ag = my_generator(info2)

    with OverrideLoop(new_loop=True) as custom_loop:
        assert info2 == []
        assert info3 == []

        async def doit():
            ag2 = my_generator(info3)
            assert set(asyncio.get_event_loop()._asyncgens) == set()
            await ag2.__anext__()
            assert set(asyncio.get_event_loop()._asyncgens) == set([ag2])
            await ag.__anext__()
            assert set(asyncio.get_event_loop()._asyncgens) == set([ag2, ag])
            await ag.__anext__()
            assert info3 == [1]

        custom_loop.run_until_complete(doit())
        assert list(custom_loop.loop._asyncgens) == [ag]
        assert info3 == [1]
        assert info2 == [1, 2]

    assert asyncio.get_event_loop() is original
    assert not original.is_closed()

    assert info3 == [1, "cancelled", ("done", asyncio.CancelledError)]
    assert info2 == [1, 2, "cancelled", ("done", asyncio.CancelledError)]
    assert info1 == [1, 2]

    async def outside2():
        try:
            await outside_gen.__anext__()
        except StopAsyncIteration:
            pass

    # Test that the outside loop isn't affected by the inside loop
    original.run_until_complete(outside2())
    assert info1 == [1, 2, 3, ("done", None)]

describe "testing autouse":

    @pytest.fixture(autouse=True)
    def custom_loop(self, loop_info):
        assert not loop_info
        loop_info["original"] = get_event_loop()

        with OverrideLoop() as custom_loop:
            assert loop_info["original"] is not get_event_loop()
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
        loop_info["fix1"] = get_event_loop()

    @pytest.fixture()
    async def fix2(self, loop_info):
        loop_info["fix2"] = get_event_loop()

    @pytest.fixture()
    async def fix3(self, loop_info):
        loop_info["fix3a"] = get_event_loop()
        try:
            yield
            loop_info["fix3b"] = get_event_loop()
        finally:
            loop_info["fix3c"] = get_event_loop()

    @pytest.fixture()
    def fix4(self, loop_info):
        loop_info["fix4a"] = get_event_loop()
        try:
            yield
            loop_info["fix4b"] = get_event_loop()
        finally:
            loop_info["fix4c"] = get_event_loop()

    @pytest.fixture()
    def fix5(self, loop_info):
        loop_info["fix5a"] = get_event_loop()

    it "works", fix1, fix2, fix3, fix4, fix5, loop_info:
        loop_info["test"] = get_event_loop()
        assert list(loop_info) == ["original", "fix1", "fix2", "fix3a", "fix4a", "fix5a", "test"]
        self.assertLoopInfo(loop_info, closed=False)

    it "has the loop on custom_loop", custom_loop, fix1, fix2, fix3, fix4, fix5, loop_info:
        loop_info["test"] = get_event_loop()
        assert list(loop_info) == ["original", "fix1", "fix2", "fix3a", "fix4a", "fix5a", "test"]
        assert custom_loop.loop is get_event_loop()
        self.assertLoopInfo(loop_info, closed=False)

    it "can use futures from fixtures", custom_loop, fix1, fix2, fix3, fix4, fix5, loop_info, fut:
        loop_info["test"] = get_event_loop()

        futs = {"a": fut, "b": get_event_loop().create_future()}
        custom_loop.run_until_complete(things(futs, loop_info, works=True))
