# coding: spec

from _pytest.pytester import Testdir as TD, LineMatcher
from contextlib import contextmanager
import subprocess
import tempfile
import asyncio
import socket
import signal
import pytest
import shutil
import os

this_dir = os.path.dirname(__file__)

pytest_uses_paths = False
try:
    from _pytest.pytester import Pytester

    pytest_uses_paths = True
    TD = Pytester  # noqa
except ImportError:
    pass


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
    path = os.path.join(this_dir, name)
    assert os.path.isdir(path)

    expected_file = os.path.join(this_dir, name, "expected")
    assert os.path.isfile(expected_file)

    with open(expected_file, "r") as fle:
        expected = fle.read().strip()

    directory = tmp_path_factory.mktemp(name)
    shutil.rmtree(directory)
    shutil.copytree(path, directory)

    class Factory:
        @property
        def expected(s):
            return expected

        def mktemp(s, p, **kwargs):
            if p.startswith("tmp-"):
                res = tmp_path_factory.mktemp(p)
            else:
                res = directory

            try:
                import py
            except ImportError:
                return res
            else:
                if pytest_uses_paths:
                    return res

                return py.path.local(str(res))

    return Factory()


@pytest.mark.parametrize(
    "name", [name for name in os.listdir(this_dir) if name.startswith("example_")]
)
async it "shows correctly for failing fixtures", name, request, tmp_path_factory:
    factory = example_dir_factory(tmp_path_factory, name)
    testdir = TD(request, factory)
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

    matcher = LineMatcher(lines)
    matcher.fnmatch_lines(expected.split("\n"))


@pytest.mark.async_timeout(4)
async it "cleans up tests properly on interrupt":
    directory = os.path.join(this_dir, "interrupt_test")
    expected_file = os.path.join(directory, "expected")

    assert os.path.isfile(expected_file)

    with open(expected_file, "r") as fle:
        expected = fle.read().strip()

    p = await asyncio.create_subprocess_exec(
        shutil.which("pytest"),
        cwd=directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    await asyncio.sleep(2)
    p.send_signal(signal.SIGINT)
    await p.wait()

    got = (await p.stdout.read()).decode().strip().split("\n")
    while got and not got[0].startswith("collected"):
        got.pop(0)

    want = expected.strip().split("\n")

    if len(got) != len(want):
        print("\n".join(got))
        assert False, "expected different number of lines in output"

    matcher = LineMatcher(got)
    matcher.fnmatch_lines(want)
