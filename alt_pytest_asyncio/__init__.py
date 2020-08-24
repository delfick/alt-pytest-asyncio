"""pytest-cov: avoid already-imported warning: PYTEST_DONT_REWRITE."""
from alt_pytest_asyncio.version import VERSION

import pytest


@pytest.hookimpl
def pytest_addoption(parser):
    """Add an option for default async timeouts"""
    desc = "timeout in seconds before failing a test. This can be overriden with @pytest.mark.async_timeout(<my_timeout>)"

    group = parser.getgroup(
        "alt-pytest-asyncio", description="Alternative asyncio pytest plugin options"
    )
    group.addoption("--default-async-timeout", type=float, dest="default_async_timeout", help=desc)
    parser.addini(
        "default_async_timeout", desc, default=5,
    )


def pytest_configure(config):
    from alt_pytest_asyncio.plugin import AltPytestAsyncioPlugin

    if not any(isinstance(p, AltPytestAsyncioPlugin) for p in config.pluginmanager.get_plugins()):
        config.pluginmanager.register(AltPytestAsyncioPlugin())


__all__ = ["pytest_addoption", "pytest_configure", "VERSION"]
