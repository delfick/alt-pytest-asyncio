import asyncio
from collections.abc import AsyncGenerator, Coroutine, Iterator

import pytest

from alt_pytest_asyncio import Loop


def get_event_loop() -> asyncio.AbstractEventLoop:
    return asyncio.get_event_loop_policy().get_event_loop()


@pytest.fixture()
def fut() -> asyncio.Future[None]:
    return get_event_loop().create_future()


async def things(
    futs: dict[str, asyncio.Future[None]],
    loop_info: dict[str, asyncio.AbstractEventLoop],
    works: bool = False,
) -> None:
    found: list[None] = []

    async def setter() -> None:
        await asyncio.sleep(0.05)
        futs["a"].set_result(None)
        futs["b"].set_result(None)

    task: asyncio.Task[None] | None = None

    try:
        task = get_event_loop().create_task(setter())

        if not works:
            loop_info["thingsa"] = get_event_loop()

        if works:
            await futs["a"]
            found.append(None)
        else:
            try:
                await futs["a"]
                found.append(None)
            except RuntimeError as error:
                assert "attached to a different loop" in str(error)

        await futs["b"]
        found.append(None)
    finally:
        if not works:
            loop_info["thingsb"] = get_event_loop()

        if task:
            task.cancel()
            await asyncio.wait([task])

        if works:
            assert found == [None, None]
        else:
            assert found == [None]


def test_will_not_let_you_do_run_until_complete_outside_the_context_manager() -> None:
    info: dict[str, Coroutine[None, None, None] | None] = {"coro": None}

    async def blah() -> None:
        pass

    try:
        coro = info["coro"] = blah()
        Loop().run_until_complete(coro)
        assert False, "should have risen an error"
    except Exception as error:
        msg = "Cannot use run_until_complete on this alt_pytest_asyncio.Loop outside of using it as a context manager"
        assert str(error) == msg

    assert info["coro"] is not None
    get_event_loop().run_until_complete(info["coro"])


def test_can_replace_the_loop(fut: asyncio.Future[None]) -> None:
    info = {}
    futs = {"a": fut}

    info["original"] = get_event_loop()

    with Loop() as custom_loop:
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
def loop_info() -> dict[str, asyncio.AbstractEventLoop]:
    return {}


class TestNoNewLoop:
    def test_sets_None(self) -> None:
        info: dict[str, Coroutine[None, None, None] | None] = {"coro": None}

        original = get_event_loop()

        with Loop(new_loop=False) as custom_loop:
            msg = "There is no current event loop in thread.*"
            try:
                assert get_event_loop() is None
                assert False, "should have risen an error"
            except Exception as error:
                assert str(error).startswith("There is no current event loop in thread")

            try:

                async def blah() -> None:
                    pass

                coro = info["coro"] = blah()

                custom_loop.run_until_complete(coro)
                assert False, "should have risen an error"
            except Exception as error:
                msg = "This alt_pytest_asyncio.Loop is not managing your overridden loop, use run_until_complete on that loop instead"
                assert str(error) == msg

        assert get_event_loop() is original
        assert not original.is_closed()

        made_coro = info["coro"]
        assert made_coro is not None
        get_event_loop().run_until_complete(made_coro)


def test_can_shutdown_async_gens() -> None:
    info1: list[int | str | tuple[str, object]] = []
    info2: list[int | str | tuple[str, object]] = []
    info3: list[int | str | tuple[str, object]] = []

    try:
        original = asyncio.get_running_loop()
    except RuntimeError:
        original = asyncio.new_event_loop()
        asyncio.set_event_loop(original)

    async def my_generator(info: list[int | str | tuple[str, object]]) -> AsyncGenerator[None]:
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

    async def outside1() -> None:
        await outside_gen.__anext__()
        await outside_gen.__anext__()

    original.run_until_complete(outside1())
    assert info1 == [1, 2]

    # The way python asyncio works
    # Means that by defining this outside our Loop
    # The weakref held against it in the _asyncgens set on the loop
    # Will remain so that our shutdown_asyncgens function may work
    ag = my_generator(info2)

    with Loop(new_loop=True) as custom_loop:
        assert custom_loop.controlled_loop is not None

        assert info2 == []
        assert info3 == []

        async def doit() -> None:
            ag2 = my_generator(info3)
            assert set(asyncio.get_event_loop()._asyncgens) == set()  # type: ignore[attr-defined]
            await ag2.__anext__()
            assert set(asyncio.get_event_loop()._asyncgens) == set([ag2])  # type: ignore[attr-defined]
            await ag.__anext__()
            assert set(asyncio.get_event_loop()._asyncgens) == set([ag2, ag])  # type: ignore[attr-defined]
            await ag.__anext__()
            assert info3 == [1]

        custom_loop.run_until_complete(doit())
        assert list(custom_loop.controlled_loop._asyncgens) == [ag]  # type: ignore[attr-defined]
        assert info3 == [1]
        assert info2 == [1, 2]

    assert not original.is_closed()

    assert info3 == [1, "cancelled", ("done", asyncio.CancelledError)]
    assert info2 == [1, 2, "cancelled", ("done", asyncio.CancelledError)]
    assert info1 == [1, 2]

    async def outside2() -> None:
        try:
            await outside_gen.__anext__()
        except StopAsyncIteration:
            pass

    # Test that the outside loop isn't affected by the inside loop
    original.run_until_complete(outside2())
    assert info1 == [1, 2, 3, ("done", None)]


class TestTestingAutoUse:
    @pytest.fixture(autouse=True)
    def custom_loop(self, loop_info: dict[str, asyncio.AbstractEventLoop]) -> Iterator[Loop]:
        assert not loop_info
        loop_info["original"] = get_event_loop()

        with Loop() as custom_loop:
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

    def assertLoopInfo(
        self, loop_info: dict[str, asyncio.AbstractEventLoop], *, closed: bool
    ) -> None:
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
    async def fix1(
        self,
        custom_loop: Loop,
        loop_info: dict[str, asyncio.AbstractEventLoop],
    ) -> None:
        loop_info["fix1"] = get_event_loop()

    @pytest.fixture()
    async def fix2(self, loop_info: dict[str, asyncio.AbstractEventLoop]) -> None:
        loop_info["fix2"] = get_event_loop()

    @pytest.fixture()
    async def fix3(self, loop_info: dict[str, asyncio.AbstractEventLoop]) -> AsyncGenerator[None]:
        loop_info["fix3a"] = get_event_loop()
        try:
            yield
            loop_info["fix3b"] = get_event_loop()
        finally:
            loop_info["fix3c"] = get_event_loop()

    @pytest.fixture()
    def fix4(self, loop_info: dict[str, asyncio.AbstractEventLoop]) -> Iterator[None]:
        loop_info["fix4a"] = get_event_loop()
        try:
            yield
            loop_info["fix4b"] = get_event_loop()
        finally:
            loop_info["fix4c"] = get_event_loop()

    @pytest.fixture()
    def fix5(self, loop_info: dict[str, asyncio.AbstractEventLoop]) -> None:
        loop_info["fix5a"] = get_event_loop()

    def test_works(
        self,
        fix1: None,
        fix2: None,
        fix3: None,
        fix4: None,
        fix5: None,
        loop_info: dict[str, asyncio.AbstractEventLoop],
    ) -> None:
        loop_info["test"] = get_event_loop()
        assert list(loop_info) == ["original", "fix1", "fix2", "fix3a", "fix4a", "fix5a", "test"]
        self.assertLoopInfo(loop_info, closed=False)

    def test_has_the_loop_on_custom_loop(
        self,
        custom_loop: Loop,
        fix1: None,
        fix2: None,
        fix3: None,
        fix4: None,
        fix5: None,
        loop_info: dict[str, asyncio.AbstractEventLoop],
    ) -> None:
        loop_info["test"] = get_event_loop()
        assert list(loop_info) == ["original", "fix1", "fix2", "fix3a", "fix4a", "fix5a", "test"]
        assert custom_loop.controlled_loop is get_event_loop()
        self.assertLoopInfo(loop_info, closed=False)

    def test_can_use_futures_from_fixtures(
        self,
        custom_loop: Loop,
        fix1: None,
        fix2: None,
        fix3: None,
        fix4: None,
        fix5: None,
        loop_info: dict[str, asyncio.AbstractEventLoop],
        fut: asyncio.Future[None],
    ) -> None:
        loop_info["test"] = get_event_loop()

        futs = {"a": fut, "b": get_event_loop().create_future()}
        custom_loop.run_until_complete(things(futs, loop_info, works=True))
