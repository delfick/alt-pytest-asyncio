import alt_pytest_asyncio_test_driver.contextvars_for_test as ctxvars
import pytest


@pytest.mark.order(100)
def test_only_keeps_values_from_other_module_fixtures_if_they_have_not_been_cleaned_up() -> None:
    assert ctxvars.a.get() == "a_set_conftest_fixture_session_autouse"
    assert ctxvars.b.get() == "b_set_conftest_cm_session_autouse"
    assert ctxvars.c.get() == "c_set_conftest_fixture_test"
    assert ctxvars.e.get() == "e_set_conftest_cm_module"
    assert ctxvars.f.get() == "f_set_conftest_cm_module"
    ctxvars.assertVarsEmpty(excluding=("a", "b", "c", "e", "f"))
