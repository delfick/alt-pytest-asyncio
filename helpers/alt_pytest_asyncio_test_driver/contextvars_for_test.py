from collections.abc import Iterable
from contextvars import ContextVar

allvars: dict[str, ContextVar[str]] = {}


class Empty:
    pass


def assertVarsEmpty(excluding: Iterable[str] | None = None) -> None:
    for letter, var in allvars.items():
        if not excluding or letter not in excluding:
            assert var.get(Empty) is Empty


a: ContextVar[str] = ContextVar("a")
allvars["a"] = a

b: ContextVar[str] = ContextVar("b")
allvars["b"] = b

c: ContextVar[str] = ContextVar("c")
allvars["c"] = c

d: ContextVar[str] = ContextVar("d")
allvars["d"] = d

e: ContextVar[str] = ContextVar("e")
allvars["e"] = e

f: ContextVar[str] = ContextVar("f")
allvars["f"] = f
