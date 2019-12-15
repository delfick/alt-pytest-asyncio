Alternative Pytest Asyncio
==========================

This plugin allows you to have async pytest fixtures and tests.

This plugin only supports python 3.6 and above.

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

Changelog
---------

0.5.1 - 15 December 2019
    * Added an ini option ``default_alt_async_timeout`` for the default async
      timeout for fixtures and tests. The default is now 5 seconds. So say
      you wanted the default to be 3.5 seconds, you would set
      ``default_alt_async_timeout`` to be 3.5

0.5 - 16 August 2019
    * I made this functionality in a work project where I needed to run
      pytest.main from an existing event loop. I decided to make this it's
      own module so I can have tests for this code.

Running from your own event loop
--------------------------------

If you want to run pytest.main from with an existing event loop then you can
do something like:

.. code-block:: python

   from alt_pytest_asyncio.plugin import AltPytestAsyncioPlugin, run_coro_as_main
   import nest_asyncio
   import asyncio
   import pytest

   async def my_tests():
      await do_some_setup_before_pytest()

      plugins = [AltPytestAsyncioPlugin(loop)]

      try:
          code = pytest.main([], plugins=plugins)
      finally:
          # Note that alt_pytest_asyncio will make sure all your async tests
          # have been finalized by this point, even if you KeyboardInterrupt
          # the pytest.main
          await do_any_teardown_after_pytest()

      if code != 0:
         raise Exception(repr(code))

   if __name__ == '__main__':
      # Nest asyncio is required so that we can do run_until_complete in an
      # existing event loop - https://github.com/erdewit/nest_asyncio
      loop = asyncio.get_event_loop()
      nest_asyncio.apply(loop)

      run_coro_as_main(loop, my_tests())

Note that if you don't need to run pytest from an existing event loop, you don't
need to do anything other than have alt_pytest_asyncio installed in your
environment and you'll be able to just use async keywords on your fixtures and
tests.

Timeouts
--------

alt_pytest_asyncio registers a ``pytest.mark.async_timeout(seconds)`` mark which
you can use to set a timeout for your test.

For example:

.. code-block:: python

   import pytest

   @pytest.mark.async_timeout(10)
   async def test_something():
      await something_that_may_take_a_while()

This test will be cancelled after 10 seconds and raise an assertion error saying
the test took too long and the file and line number where the test is.

You can also use the async_timeout mark on coroutine fixtures:

.. code-block:: python

   import pytest

   @pytest.fixture()
   @pytest.mark.async_timeout(0.5)
   async def my_amazing_fixture():
      await asyncio.sleep(1)
      return 1

And you can have a timeout on generator fixtures:

.. code-block:: python

   import pytest

   @pytest.fixture()
   @pytest.mark.async_timeout(0.5)
   async def my_amazing_fixture():
      try:
         await asyncio.sleep(1)
         yield 1
      finally:
         await asyncio.sleep(1)

Note that for generator fixtures, the timeout is applied in whole to both the
setup and finalization of the fixture. As in the real timeout for the entire
fixture is essentially double the single timeout specified.

The default timeout is 5 seconds. You can change this default by setting the
``default_alt_async_timeout`` option to the number of seconds you want.
