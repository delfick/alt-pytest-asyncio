"""pytest-cov: avoid already-imported warning: PYTEST_DONT_REWRITE."""
VERSION = "0.5"

def pytest_configure(config):
    from alt_pytest_asyncio.plugin import AltPytestAsyncioPlugin
    if not any(isinstance(p, AltPytestAsyncioPlugin) for p in config.pluginmanager.get_plugins()):
        config.pluginmanager.register(AltPytestAsyncioPlugin())
