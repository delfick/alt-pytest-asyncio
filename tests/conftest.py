import pytest

pytest_plugins = ["pytester"]


@pytest.fixture(scope="session", autouse=True)
def change_pytester(pytestconfig: pytest.Config):
    pytestconfig.option.runpytest = "subprocess"
