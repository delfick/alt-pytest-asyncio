# coding: spec

import asyncio
import socket

async it "executes finally on interrupt", pytestconfig, test_fut:
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(pytestconfig.option.test_socket)
        s.close()

        # The test in test_examples will wait until the socket gets a connection
        # And so we'll be in this asyncio.sleep when we send a SIGINT
        # So that we can test the finally block is called before pytest finishes
        await asyncio.sleep(10)
    finally:
        test_fut.set_result(True)
