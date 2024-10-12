# coding: spec

from alt_pytest_asyncio_test_driver import available_examples
import asyncio
import importlib.resources
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from contextlib import contextmanager

import pytest


@contextmanager
def listening():
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


def example_dir_factory(tmp_path_factory, name):
    examples = importlib.resources.files("alt_pytest_asyncio_test_driver") / "examples" / name
    assert examples.is_dir()

    expected = (examples / "expected").read_text()

    directory = tmp_path_factory.mktemp(name)
    shutil.rmtree(directory)
    shutil.copytree(examples, directory)

    class Factory:
        @property
        def expected(s):
            return expected

        def mktemp(s, p, **kwargs):
            if p.startswith("tmp-"):
                res = tmp_path_factory.mktemp(p)
            else:
                res = directory

            return res

    return Factory()


@pytest.mark.parametrize("name", available_examples)
async it "shows correctly for failing fixtures", name, request, tmp_path_factory, monkeypatch:
    factory = example_dir_factory(tmp_path_factory, name)
    testdir = pytest.Pytester(request, factory, monkeypatch)
    expected = factory.expected
    result = testdir.runpytest("--tb", "short")
    assert not result.errlines

    lines = 0
    for line in result.outlines:
        if line.startswith("=") and isinstance(lines, int):
            if lines < 1:
                lines += 1
            else:
                lines = []

        if isinstance(lines, list):
            lines.append(line)

    matcher = pytest.LineMatcher(lines)
    matcher.fnmatch_lines(expected.strip().split("\n"))


@pytest.mark.async_timeout(7)
@pytest.mark.skipif(os.name == "nt", reason="Can't use async subprocess on windows")
async it "cleans up tests properly on interrupt":
    examples = importlib.resources.files("alt_pytest_asyncio_test_driver") / "examples" / "interrupt_test"
    assert examples.is_dir()
    expected = (examples / "expected").read_text()

    p = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pytest",
        cwd=examples,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    await asyncio.sleep(4)
    p.send_signal(signal.SIGINT)
    await p.wait()

    got = (await p.stdout.read()).decode().strip().split("\n")
    while got and not got[0].startswith("collected"):
        got.pop(0)

    want = expected.strip().split("\n")

    matcher = pytest.LineMatcher(got)
    matcher.fnmatch_lines(want)
