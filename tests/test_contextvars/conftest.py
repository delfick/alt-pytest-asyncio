import contextvars_for_test as ctxvars
import pytest


@pytest.fixture(scope="session", autouse=True)
async def a_set_conftest_fixture_session_autouse():
    ctxvars.a.set("a_set_conftest_fixture_session_autouse")


@pytest.fixture(scope="session", autouse=True)
async def b_set_conftest_cm_session_autouse():
    ctxvars.b.set("b_set_conftest_cm_session_autouse")
    yield


@pytest.fixture()
async def c_set_conftest_fixture_test():
    ctxvars.c.set("c_set_conftest_fixture_test")


@pytest.fixture()
async def c_set_conftest_cm_test():
    token = ctxvars.c.set("c_set_conftest_cm_test")
    try:
        yield
    finally:
        ctxvars.c.reset(token)
