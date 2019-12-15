# coding: spec

import pytest


@pytest.mark.async_timeout(1)
async it "can use our session global tcp server from one module", tcp_client:
    assert (await tcp_client("hello")) == b"olleh"
