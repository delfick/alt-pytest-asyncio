.. toctree::
   :hidden:
   :maxdepth: 2

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

Changelog
---------

.. _release-0.9.3:

0.9.3 - TBD
    * Fixed a bug where fixture errors would persist across multiple tests
      https://github.com/delfick/alt-pytest-asyncio/issues/26

.. _release-0.9.2:

0.9.2 - 23 February 2025
    * Fixed a memory leak for large test suites

.. _release-0.9.1:

0.9.1 - 5 November 2024
    * Made the plugin take into account pytest.ini for setting the default async timeout

.. _release-0.9.0:

0.9.0 - 20 October 2024
    * Enabling the plugin must now be done by adding ``alt_pytest_asyncio.enable``
      to the pytest list of enabled plugins if it's not being manually enabled.
    * Removed ``pytest.mark.async_timeout`` and replaced the functionality with
      a fixture.
    * Changed the exported api of the plugin

        * ``alt_pytest_asyncio.plugin.OverrideLoop`` is now ``alt_pytest_asyncio.Loop``
        * ``alt_pytest_asyncio.plugin.AltPytestAsyncioPlugin`` now takes ``managed_loop``
          as a keyword argument instead of the first positional argument with the
          name ``loop``.
        * The new ``Loop`` that replaces ``OverrideLoop`` now has an attributed
          ``controlled_loop`` instead of ``loop``.

.. _release-0.8.2:

0.8.2 - 12 October 2024
    * Added type annotations
    * CI now tests against python 3.13

.. _release-0.8.1:

0.8.1 - 3 June 2024
    * Remove a namespace conflict that restricted what names could be used as
      parametrize arguments.

.. _release-0.8.0:

0.8.0 - 1 June 2024
    * Provide simple support for tests being aware of asyncio.Context
    * Remove support for python less than 3.11
    * Added support for asyncio ContextVars

.. _release-0.7.2:

0.7.2 - 1 October 2023
    * Timeouts don't take affect if the debugger is active

.. _release-0.7.1:

0.7.1 - 23 June 2023
    * No functional changes, only fixing how hatchling understands the
      license field in the pyproject.toml with thanks to @piotrm-nvidia

.. _release-0.7.0:

0.7.0 - 12 April 2023
    * Changed the pytest dependency to be greater than pytest version 7
    * Using isort now
    * Went from setuptools to hatch
    * CI now runs against python 3.11

.. _release-0.6.0:

0.6.0 - 23 October 2021
    * Fix bug where it was possible for an async generator fixture to
      be cleaned up even if it was never started.
    * This library is now 3.7+ only
    * Added an equivalent ``shutdown_asyncgen`` to the OverrideLoop helper

.. _release-0.5.4:

0.5.4 - 26 January 2021
    * Added a ``--default-async-timeout`` option from the CLI. With many thanks
      to @andredias.
    * Renamed existing pytest.ini option from ``default_alt_async_timeout`` to
      be ``default_async_timeout``.

.. _release-0.5.3:

0.5.3 - 25 July 2020
    * Make sure a KeyboardInterrupt on running tests still shows errors from
      failed tests

.. _release-0.5.2:

0.5.2 - 6 February 2020
    * Added ability to make a different event loop for some tests

.. _release-0.5.1:

0.5.1 - 15 December 2019
    * Added an ini option ``default_alt_async_timeout`` for the default async
      timeout for fixtures and tests. The default is now 5 seconds. So say
      you wanted the default to be 3.5 seconds, you would set
      ``default_alt_async_timeout`` to be 3.5

.. _release-0.5.0:

0.5 - 16 August 2019
    * I made this functionality in a work project where I needed to run
      pytest.main from an existing event loop. I decided to make this it's
      own module so I can have tests for this code.

Installation
------------

Most users of this plugin won't need to manually construct the plugin as that's
only required if you're doing funky things where you want to manually call
``pytest.main`` (see next section).

For this majority case, enabling the plugin requires:

* The plugin be installed in the python environment
* Adding ``alt_pytest_asyncio.enable`` to the list of pytest plugins that are
  enabled.

Running from your own event loop
--------------------------------

If you want to run pytest.main from with an existing event loop then you can
do something like:

.. code-block:: python

   import alt_pytest_asyncio
   import nest_asyncio
   import asyncio
   import pytest

   async def my_tests():
      await do_some_setup_before_pytest()

      loop: asyncio.AbstractEventLoop = ...

      plugins = [
        alt_pytest_asyncio.plugin.AltPytestAsyncioPlugin(
            managed_loop=loop
        ),
      ]

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

      alt_pytest_asyncio.run_coro_as_main(loop, my_tests())

Note that if you don't need to run pytest from an existing event loop, you don't
need to do anything other than have ``alt_pytest_asyncio`` installed in your
environment and ``alt_pytest_asyncio.enable`` in your pytest plugins list
and you'll be able to just use async keywords on your fixtures and
tests.

Timeouts
--------

.. note:: The ``pytest.mark.async_timeout(seconds)`` that existed before
   version 0.9.0 no longer has an effect and has been replaced with the fixtures
   as mentioned below

This plugin can configure the timeout for any async fixture or test using the
``async_timeout`` fixture or by creating a ``default_async_timeout`` fixture.

For example:

.. code-block:: python

   import pytest
   import alt_pytest_asyncio

   AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout

   async def test_something(async_timeout: AsyncTimeout) -> None:
      async_timeout.set_timeout_seconds(10)
      await something_that_may_take_a_while()

This test will be cancelled after 10 seconds and raise an assertion error saying
the test took too long and the file and line number where the test is.

.. note:: The async_timeout passed into a fixture or a test is a new instance
   specific to that fixture or test. Setting it in a fixture only affects that
   fixture and setting it in a test only affects that test.

You can also set a ``default_async_timeout`` fixture to change the default:

.. code-block:: python

   import pytest
   import alt_pytest_asyncio

   AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout


   @pytest.fixture()
   def default_async_timeout() -> float:
       return 0.5

   @pytest.fixture
   async def my_amazing_fixture() -> int:
      # Will timeout because of our default 0.5
      await asyncio.sleep(1)
      return 1

   @pytest.fixture
   async def my_amazing_fixture(async_timeout: AsyncTimeout) -> int:
      # Change timeout for just this fixture
      async_timeout.set_timeout_seconds(2)
      await asyncio.sleep(1)
      return 1

For fixtures that have a non function scope, they require a
``{scope}_default_async_timeout`` fixture:

.. code-block:: python

   import pytest


   @pytest.fixture(scope="session")
   def session_default_async_timeout() -> float:
       return 5

   @pytest.fixture(scope="session")
   async def some_fixture() -> None:
       # timeout here is 5
       pass

   class TestStuff:
       @pytest.fixture(scope="class")
       async def some_fixture() -> None:
           # timeout here is 5
           pass

       class TestMore:
           @pytest.fixture(scope="class")
           async def class_default_async_timeout() -> int:
               return 8

           @pytest.fixture(scope="class")
           async def some_fixture() -> None:
               # timeout here is 8
               pass

The plugin knows about the scopes ``function``, ``class``, ``module``, ``package``
and ``session``. So say a ``scope="class"`` async fixture is executed, the closest
``class_default_async_timeout`` fixture is used unless that doesn't exist, in which
case ``module_default_async_timeout`` is used, otherwise ``package_default_async_timeout``,
otherwise ``session_default_async_timeout``.

There is a default ``session_default_async_timeout`` available which returns the
value set by the ``default_async_timeout`` pytest option the plugin provides.

And you can have a timeout on generator fixtures:

.. code-block:: python

   import pytest
   from collections.abc import Iterator
   import alt_pytest_asyncio

   AsyncTimeout = alt_pytest_asyncio.protocols.AsyncTimeout

   @pytest.fixture()
   async def my_amazing_fixture(async_timeout: AsyncTimeout) -> Iterator[int]:
      async_timeout.set_timeout_seconds(0.5)

      try:
         await asyncio.sleep(1)
         yield 1
      finally:
         await asyncio.sleep(1)

Note that for generator fixtures, the timeout is applied in whole to both the
setup and finalization of the fixture. As in the real timeout for the entire
fixture is essentially double the single timeout specified.

The default timeout is 5 seconds. You can change this default by setting the
``default_async_timeout`` option to the number of seconds you want.

This setting is also available from the CLI using the ``--default-async-timeout``
option.

Note that if the timeout fires whilst you have the debugger active then the timeout
will not cancel the current test. This is determined by checking if ``sys.gettrace()``
returns a non-None value.

The object that is provided when the fixture/test asks for ``async_timeout`` can
be modified by overriding the ``async_timeout`` session scope'd fixture and
returning an object that inherits from and implements
``alt_pytest_asyncio.base.AsyncTimeoutProvider``. This is a python "abc" class
with a single method ``load`` which is called to return the object given to the
fixture or test. This object must implement
``alt_pytest_asyncio.base.AsyncTimeout``. The default implementation can be found
at ``alt_pytest_asyncio.plugin.LoadedAsyncTimeout``.

Overriding the loop
-------------------

Sometimes it may be necessary to close the current loop in a test. For this to
not then break the rest of your tests, you will need to set a new event loop for
your test and then restore the old loop afterwards.

For this, we have a context manager that will install a new asyncio loop and
then restore the original loop on exit.

Usage looks like::

    import alt_pytest_asyncio

    class TestThing:
        @pytest.fixture(autouse=True)
        def custom_loop(self) -> alt_pytest_asyncio.protocols.Loop:
            with alt_pytest_asyncio.Loop() as custom_loop:
                yield custom_loop

        def test_thing(self, custom_loop: alt_pytest_asyncio.protocols.Loop):
            custom_loop.run_until_complete(my_thing())

By putting the loop into an autouse fixture, all fixtures used by the test
will have the custom loop. If you want to include module level fixtures too
then use the OverrideLoop in a module level fixture too.

If the Loop is instantiated with ``new_loop=True`` then it will create and manage
a new event loop whilst it's being used as a context manager. This new loop
will be available on the object as ``.controlled_loop``.

The ``run_until_complete`` on the ``custom_loop`` in the above example will
do a ``run_until_complete`` on the new loop, but in a way that means you
won't get ``unhandled exception during shutdown`` errors when the context
manager closes the new loop.

When the context manager exits and closes the new loop, it will first cancel
all tasks to ensure finally blocks are run.
