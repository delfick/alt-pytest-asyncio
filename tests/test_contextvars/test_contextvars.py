# coding: spec

import alt_pytest_asyncio_test_driver.contextvars_for_test as ctxvars
import pytest


@pytest.fixture(scope="module", autouse=True)
def d_set_conftest_cm_module_autouse():
    token = ctxvars.d.set("d_set_conftest_fixture_test")
    try:
        yield
    finally:
        ctxvars.d.reset(token)


@pytest.fixture(scope="module", autouse=True)
async def e_set_conftest_cm_test():
    assert ctxvars.f.get(ctxvars.Empty) is ctxvars.Empty
    ctxvars.e.set("e_set_conftest_cm_module")
    yield
    assert ctxvars.f.get() == "f_set_conftest_cm_module"


@pytest.fixture(scope="module", autouse=True)
async def f_set_conftest_cm_module(e_set_conftest_cm_test):
    assert ctxvars.e.get() == "e_set_conftest_cm_module"
    ctxvars.f.set("f_set_conftest_cm_module")
    yield


@pytest.mark.order(1)
async it "gets session modified vars":
    assert ctxvars.a.get() == "a_set_conftest_fixture_session_autouse"
    assert ctxvars.b.get() == "b_set_conftest_cm_session_autouse"
    assert ctxvars.d.get() == "d_set_conftest_fixture_test"
    assert ctxvars.e.get() == "e_set_conftest_cm_module"
    assert ctxvars.f.get() == "f_set_conftest_cm_module"
    ctxvars.assertVarsEmpty(excluding=("a", "b", "d", "e", "f"))


@pytest.mark.order(2)
async it "can use a fixture to change the var", c_set_conftest_fixture_test:
    assert ctxvars.a.get() == "a_set_conftest_fixture_session_autouse"
    assert ctxvars.b.get() == "b_set_conftest_cm_session_autouse"
    assert ctxvars.d.get() == "d_set_conftest_fixture_test"
    assert ctxvars.e.get() == "e_set_conftest_cm_module"
    assert ctxvars.f.get() == "f_set_conftest_cm_module"

    assert ctxvars.c.get() == "c_set_conftest_fixture_test"
    ctxvars.assertVarsEmpty(excluding=("a", "b", "c", "d", "e", "f"))


@pytest.mark.order(3)
async it "does not reset contextvars for you":
    """
    It's too hard to know when a contextvar should be reset. It should
    be up to whatever sets the contextvar to know when it should be unset
    """
    assert ctxvars.a.get() == "a_set_conftest_fixture_session_autouse"
    assert ctxvars.b.get() == "b_set_conftest_cm_session_autouse"
    assert ctxvars.d.get() == "d_set_conftest_fixture_test"
    assert ctxvars.e.get() == "e_set_conftest_cm_module"
    assert ctxvars.f.get() == "f_set_conftest_cm_module"

    assert ctxvars.c.get() == "c_set_conftest_fixture_test"
    ctxvars.assertVarsEmpty(excluding=("a", "b", "c", "d", "e", "f"))


@pytest.mark.order(4)
async it "works in context manager fixtures", c_set_conftest_cm_test:
    """
    It's too hard to know when a contextvar should be reset. It should
    be up to whatever sets the contextvar to know when it should be unset
    """
    assert ctxvars.a.get() == "a_set_conftest_fixture_session_autouse"
    assert ctxvars.b.get() == "b_set_conftest_cm_session_autouse"
    assert ctxvars.d.get() == "d_set_conftest_fixture_test"
    assert ctxvars.e.get() == "e_set_conftest_cm_module"
    assert ctxvars.f.get() == "f_set_conftest_cm_module"

    assert ctxvars.c.get() == "c_set_conftest_cm_test"
    ctxvars.assertVarsEmpty(excluding=("a", "b", "c", "d", "e", "f"))


@pytest.mark.order(5)
it "resets the contextvar successfully when cm attempts that":
    """
    It's too hard to know when a contextvar should be reset. It should
    be up to whatever sets the contextvar to know when it should be unset
    """
    assert ctxvars.a.get() == "a_set_conftest_fixture_session_autouse"
    assert ctxvars.b.get() == "b_set_conftest_cm_session_autouse"
    assert ctxvars.d.get() == "d_set_conftest_fixture_test"
    assert ctxvars.e.get() == "e_set_conftest_cm_module"
    assert ctxvars.f.get() == "f_set_conftest_cm_module"

    assert ctxvars.c.get() == "c_set_conftest_fixture_test"
    ctxvars.assertVarsEmpty(excluding=("a", "b", "c", "d", "e", "f"))
