import asyncio
import contextlib
import sys
from collections.abc import Coroutine
from types import TracebackType
from typing import Self

from . import machinery, protocols


class Loop(contextlib.AbstractContextManager["Loop"]):
    """
    A context manager that will manager an asyncio loop and then restore the
    original loop on exit.

    Usage looks like::

        from alt_pytest_asyncio import Loop, protocols

        class TestThing:
            @pytest.fixture(autouse=True)
            def custom_loop(self) -> protocols.Loop:
                with Loop() as custom_loop:
                    yield custom_loop

            def test_thing(self, custom_loop: protocols.Loop):
                custom_loop.run_until_complete(my_thing())

    By putting the loop into an autouse fixture, all fixtures used by the test
    will have the custom loop. If you want to include module level fixtures too
    then use the Loop in a module level fixture too.

    Loop takes in a ``new_loop`` boolean that will make it so a new
    loop is created. This loop will be set as `controlled_loop`.

    The ``run_until_complete`` on the ``custom_loop`` in the above example will
    do a ``run_until_complete`` on the new loop, but in a way that means you
    won't get ``unhandled exception during shutdown`` errors when the context
    manager closes the new loop.

    When the context manager exits and closes the new loop, it will first cancel
    all tasks to ensure finally blocks are run.
    """

    controlled_loop: asyncio.AbstractEventLoop | None
    _original_loop: asyncio.AbstractEventLoop

    def __init__(self, new_loop: bool = True) -> None:
        self._tasks: list[asyncio.Task[object]] = []
        self._new_loop = new_loop

    def __enter__(self) -> Self:
        self._original_loop = asyncio.get_event_loop_policy().get_event_loop()

        if self._new_loop:
            self.controlled_loop = asyncio.new_event_loop()
        else:
            self.controlled_loop = None

        asyncio.set_event_loop(self.controlled_loop)
        return self

    def __exit__(
        self,
        exc_typ: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if self.controlled_loop is not None:
                machinery.cancel_all_tasks(
                    self.controlled_loop, ignore_errors_from_tasks=self._tasks
                )
                self.controlled_loop.run_until_complete(self.shutdown_asyncgens())
                self.controlled_loop.close()
        finally:
            if original_loop := getattr(self, "_original_loop", None):
                asyncio.set_event_loop(original_loop)

    async def shutdown_asyncgens(self) -> None:
        """
        A version of loop.shutdown_asyncgens that tries to cancel the generators
        before closing them.
        """
        if self.controlled_loop is None:
            return

        asyncgens = getattr(self.controlled_loop, "_asyncgens", None)
        assert asyncgens is not None
        if not len(asyncgens):
            return

        closing_agens = list(asyncgens)
        asyncgens.clear()

        # I would do an asyncio.tasks.gather but it would appear that just causes
        # the asyncio loop to think it's shutdown, so I have to do them one at a time
        for ag in closing_agens:
            try:
                try:
                    try:
                        await ag.athrow(asyncio.CancelledError())
                    except StopAsyncIteration:
                        pass
                finally:
                    await ag.aclose()
            except asyncio.CancelledError:
                pass
            except:
                exc = sys.exc_info()[1]
                self.controlled_loop.call_exception_handler(
                    {
                        "message": "an error occurred during closing of asynchronous generator",
                        "exception": exc,
                        "asyncgen": ag,
                    }
                )

    def run_until_complete(
        self, coro: Coroutine[object, object, protocols.T_Ret]
    ) -> protocols.T_Ret:
        if not hasattr(self, "controlled_loop"):
            raise Exception(
                "Cannot use run_until_complete on this alt_pytest_asyncio.Loop outside of using it as a context manager"
            )

        if self.controlled_loop is None:
            raise Exception(
                "This alt_pytest_asyncio.Loop is not managing your overridden loop, use run_until_complete on that loop instead"
            )

        task = self.controlled_loop.create_task(coro)

        # Add the task so that when we cancel all tasks before closing the loop
        # We don't complain about errors in this particular task
        # As we get the errors risen to the caller via run_until_complete
        self._tasks.append(task)

        return self.controlled_loop.run_until_complete(task)
