class AltPytestAsyncioError(Exception):
    pass


class PluginAlreadyStarted(AltPytestAsyncioError):
    pass


class NoAsyncTimeoutInSyncFunctions(AltPytestAsyncioError):
    pass
