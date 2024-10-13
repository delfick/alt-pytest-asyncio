import pytest

from . import plugin


def pytest_configure(config: pytest.Config) -> None:
    """
    Used to configure alt_pytest_asyncio
    """
    if not any(
        isinstance(p, plugin.AltPytestAsyncioPlugin) for p in config.pluginmanager.get_plugins()
    ):
        config.pluginmanager.register(plugin.AltPytestAsyncioPlugin())
