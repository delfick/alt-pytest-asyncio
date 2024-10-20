Alternative Pytest Asyncio
==========================

This plugin allows you to have async pytest fixtures and tests.

This plugin only supports python 3.11 and above.

The code here is influenced by pytest-asyncio but with some differences:

* Error tracebacks from are from your tests, rather than asyncio internals
* There is only one loop for all of the tests
* You can manage the lifecycle of the loop yourself outside of pytest by using
  this plugin with your own loop
* No need to explicitly mark your tests as async. (pytest-asyncio requires you
  mark your async tests because it also supports other event loops like curio
  and trio)

Like pytest-asyncio it supports async tests, coroutine fixtures and async
generator fixtures.

Full documentation can be found at https://alt-pytest-asyncio.readthedocs.io
