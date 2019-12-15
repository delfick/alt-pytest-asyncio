# coding: spec

import asyncio
import pytest

pytestmark = pytest.mark.async_timeout(0.01)

async it "takes closest pytestmark":
    await asyncio.sleep(0.03)


@pytest.mark.async_timeout(0.04)
async it "takes pytestmark on function":
    await asyncio.sleep(0.03)


@pytest.mark.async_timeout(0.02)
async it "takes pytestmark on function2":
    await asyncio.sleep(0.03)
