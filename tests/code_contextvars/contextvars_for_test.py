import string
from contextvars import ContextVar

allvars = {}


class Empty:
    pass


def assertVarsEmpty(excluding=None):
    for letter, var in allvars.items():
        if not excluding or letter not in excluding:
            assert var.get(Empty) is Empty


for letter in string.ascii_letters:
    var = ContextVar(letter)
    locals()[letter] = var
    allvars[letter] = var

__all__ = ["allvars", "Empty", "assertVarsEmpty"] + sorted(allvars)
