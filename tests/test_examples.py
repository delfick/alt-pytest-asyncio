import asyncio
import contextlib
import importlib.resources
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from typing import Protocol

import pytest
from alt_pytest_asyncio_test_driver import available_examples


@contextlib.contextmanager
def listening() -> Iterator[tuple[socket.socket, str]]:
    try:
        with tempfile.NamedTemporaryFile(delete=False) as fle:
            fle.close()
            os.remove(fle.name)

            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            s.bind(fle.name)
            s.listen(1)
            yield s, fle.name
            s.close()
    finally:
        if os.path.exists(fle.name):
            os.remove(fle.name)


class Factory(Protocol):
    @property
    def expected(self) -> str: ...

    def mktemp(self, p: str, **kwargs: object) -> pathlib.Path: ...


def example_dir_factory(tmp_path_factory: pytest.TempPathFactory, name: str) -> Factory:
    examples = importlib.resources.files("alt_pytest_asyncio_test_driver") / "examples" / name
    assert examples.is_dir()

    expected = (examples / "expected").read_text()

    directory = tmp_path_factory.mktemp(name)
    shutil.rmtree(directory)
    with importlib.resources.as_file(examples) as examples_path:
        shutil.copytree(examples_path, directory)

    class Factory:
        @property
        def expected(self) -> str:
            return expected

        def mktemp(self, p: str, **kwargs: object) -> pathlib.Path:
            if p.startswith("tmp-"):
                res = tmp_path_factory.mktemp(p)
            else:
                res = directory

            return res

    return Factory()


@pytest.mark.parametrize("name", available_examples)
async def test_shows_correctly_for_failing_fixtures(name: str, pytester: pytest.Pytester) -> None:
    examples = importlib.resources.files("alt_pytest_asyncio_test_driver") / "examples" / name
    assert examples.is_dir()
    expected = (examples / "expected").read_text()

    with importlib.resources.as_file(examples) as examples_path:
        shutil.copytree(examples_path, pytester.path / name)

    result = pytester.runpytest_subprocess("--tb", "short")
    assert not result.errlines

    lines: int | list[str] = 0
    for line in result.outlines:
        if line.startswith("=") and isinstance(lines, int):
            if lines < 1:
                lines += 1
            else:
                lines = []

        if isinstance(lines, list):
            lines.append(line)

    assert isinstance(lines, list)

    matcher = pytest.LineMatcher(lines)
    matcher.fnmatch_lines(expected.strip().split("\n"))


@pytest.mark.async_timeout(7)
@pytest.mark.skipif(os.name == "nt", reason="Can't use async subprocess on windows")
async def test_cleans_up_tests_properly_on_interrupt(pytester: pytest.Pytester) -> None:
    examples = (
        importlib.resources.files("alt_pytest_asyncio_test_driver") / "examples" / "interrupt_test"
    )
    assert examples.is_dir()
    expected = (examples / "expected").read_text()

    with importlib.resources.as_file(examples) as directory:
        p = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pytest",
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    await asyncio.sleep(4)
    p.send_signal(signal.SIGINT)
    await p.wait()

    assert p.stdout is not None
    got = (await p.stdout.read()).decode().strip().split("\n")
    while got and not got[0].startswith("collected"):
        got.pop(0)

    want = expected.strip().split("\n")

    matcher = pytest.LineMatcher(got)
    matcher.fnmatch_lines(want)
