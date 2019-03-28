# Collection of configurable development workflows
# Copyright (C) 2011-2019 The Roberto Development Team
#
# This file is part of Roberto.
#
# Roberto is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# Roberto is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
# --
# pylint: disable=invalid-name,redefined-builtin
"""Sphinx configuration."""

import sys
import os

from roberto.version import __version__

# This is ugly, but it makes it possible to build the docs by just calling
# sphinx-build directly without using the Makefile. Cleaner solutions, not
# requiring tricks outside the conf.py file, are always welcome.
sys.path.insert(0, os.path.dirname(__file__))
# pylint: disable=wrong-import-position
from list_tasks import main as main_list_tasks  # noqa

main_list_tasks()

# -- Project information -----------------------------------------------------

project = 'Roberto'
copyright = '2019, The Roberto Development Team'
author = 'The Roberto Development Team'

release = __version__
version = '.'.join(release.split('.')[:2])

# -- General configuration ---------------------------------------------------

extensions = ['sphinx.ext.githubpages']
source_suffix = '.rst'
master_doc = 'index'
exclude_patterns = ['_build']
pygments_style = 'sphinx'

# -- Options for HTML output -------------------------------------------------

html_theme = 'alabaster'
html_static_path = []
