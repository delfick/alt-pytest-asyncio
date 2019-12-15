import asyncio
import pytest
import struct
import socket

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


def free_port():
    """
    Return an unused port number
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


def port_connected(port):
    """
    Return whether something is listening on this port
    """
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def tcp_port():
    return free_port()


@pytest.fixture(scope="session", autouse=True)
async def a_sync_generator_fixture(tcp_port, reversing_echo_tcp_server):
    try:
        yield
    finally:
        assert port_connected(tcp_port)


@pytest.fixture(scope="session", autouse=True)
async def reversing_echo_tcp_server(tcp_port):
    async def start_connection(reader, writer):
        while True:
            length = await reader.read(1)
            if not length:
                return

            data = await reader.read(struct.unpack("<b", length)[0])
            if not data:
                return

            writer.write(bytes(reversed(data)))

    try:
        server = await asyncio.start_server(start_connection, "127.0.0.1", tcp_port)
        while True:
            if port_connected(tcp_port):
                break
            await asyncio.sleep(0.01)
        assert port_connected(tcp_port)
        yield server
    finally:
        server.close()
        await server.wait_closed()


@pytest.fixture()
async def tcp_client(tcp_port):
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", tcp_port)

        async def communicate(s):
            bts = struct.pack("<b", len(s)) + s.encode()
            writer.write(bts)
            return await reader.read(len(s))

        yield communicate
    finally:
        writer.close()
