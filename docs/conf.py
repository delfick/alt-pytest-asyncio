import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent))

extensions = [
    "sphinx.ext.autodoc",
    "sphinx_rtd_theme",
]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["css/extra.css"]

exclude_patterns = ["_build/**", ".sphinx-build/**", "README.rst"]

master_doc = "index"
source_suffix = ".rst"

pygments_style = "pastie"

copyright = "Stephen Moore"
project = "alt-pytest-asyncio"

version = "0.1"
release = "0.1"
