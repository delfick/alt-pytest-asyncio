# coding: spec

from _pytest.pytester import Testdir as TD, LineMatcher
from contextlib import contextmanager
from textwrap import dedent
import subprocess
import tempfile
import asyncio
import socket
import signal
import pytest
import shutil
import sys
import py
import os

this_dir = os.path.dirname(__file__)

@contextmanager
def listening():
    filename = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as fle:
            filename = fle.name
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

def example_dir_factory(tmpdir_factory, name):
    path = os.path.join(this_dir, name)
    assert os.path.isdir(path)

    expected_file = os.path.join(this_dir, name, "expected")
    assert os.path.isfile(expected_file)

    with open(expected_file, 'r') as fle:
        expected = fle.read().strip()

    directory = tmpdir_factory.mktemp(name)
    shutil.rmtree(directory)
    shutil.copytree(path, directory)

    class Factory:
        @property
        def expected(s):
            return expected

        def mktemp(s, p, **kwargs):
            if p.startswith("tmp-"):
                return tmpdir_factory.mktemp(p)
            else:
                return directory

    return Factory()

@pytest.mark.parametrize("name", [name for name in os.listdir(this_dir) if name.startswith("example_")])
async it "shows correctly for failing fixtures", name, request, tmpdir_factory:
    factory = example_dir_factory(tmpdir_factory, name)
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

    with open(expected_file, 'r') as fle:
        expected = fle.read().strip()

    with listening() as (s, name):
        p = await asyncio.create_subprocess_exec(
              sys.executable
            , "main.py", "--test-socket", name
            , cwd = directory
            , stdout = subprocess.PIPE
            , stderr = subprocess.STDOUT
            )

        try:
            s.accept()
        except socket.timeout:
            print((await p.stdout.read()).decode())
            assert False, "Timed out waiting for the test to say it's ready to be interrupted"

        await asyncio.sleep(0.01)
        p.send_signal(signal.SIGINT)
        await p.wait()

    got = (await p.stdout.read()).decode().strip().split('\n')
    while got and not got[0].startswith("collected"):
        got.pop(0)

    want = expected.strip().split("\n")

    if len(got) != len(want):
        print("\n".join(got))
        assert False, "expected different number of lines in output"

    matcher = LineMatcher(got)
    matcher.fnmatch_lines(want)
