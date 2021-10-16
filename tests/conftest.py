import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent / "code_contextvars"))

pytest_plugins = ["pytester"]


@pytest.fixture(scope="session", autouse=True)
def change_pytester(pytestconfig):
    pytestconfig.option.runpytest = "subprocess"


@pytest.hookspec(firstresult=True)
def pytest_ignore_collect(path):
    if path.basename.startswith("example_"):
        return True
    if path.basename == "interrupt_test":
        return True
