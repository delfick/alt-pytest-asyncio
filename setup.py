from setuptools import setup, find_packages

import runpy
import os

VERSION = runpy.run_path(
    os.path.join(os.path.dirname(__file__), "alt_pytest_asyncio", "version.py")
)["VERSION"]

# fmt: off

setup(
      name = 'alt_pytest_asyncio'
    , version = VERSION
    , packages = find_packages(include="alt_pytest_asyncio.*", exclude=["tests*"])

    , python_requires = ">= 3.5"

    , install_requires =
      [ "pytest >= 3.0.6"
      ]

    , extras_require =
      { 'tests':
        [ 'pytest==5.4.3'
        , 'noseOfYeti==2.0.2'
        , "nest-asyncio==1.0.0"
        ]
      }

    , entry_points =
      { 'pytest11': ['alt_pytest_asyncio = alt_pytest_asyncio']
      }

    , classifiers =
      [ "Framework :: Pytest"
      , 'Topic :: Software Development :: Testing'
      ]

    , author = 'Stephen Moore'
    , license = 'MIT'
    , author_email = 'delfick755@gmail.com'

    , url = "https://github.com/delfick/alt-pytest-asyncio"
    , description = 'Alternative pytest plugin to pytest-asyncio'
    , long_description = open("README.rst").read()
    )

# fmt: on
