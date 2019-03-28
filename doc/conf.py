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

import runpy

from roberto.version import __version__


# --  Generate files to be included in the documentation ---------------------

runpy.run_path('./list_tasks.py', run_name='__main__')

# -- Project information -----------------------------------------------------

project = 'Roberto'
copyright = '2019, The Roberto Development Team'
author = 'The Roberto Development Team'

release = __version__
version = '.'.join(release.split('.')[:2])

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.githubpages',
    'sphinxcontrib.apidoc',
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx_autodoc_typehints',
]
source_suffix = '.rst'
master_doc = 'index'
exclude_patterns = ['_build']
pygments_style = 'sphinx'

# -- Options for HTML output -------------------------------------------------

html_theme = 'alabaster'
html_static_path = []

# -- Extnensions configuration -----------------------------------------------

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False

apidoc_module_dir = '../roberto'
apidoc_excluded_paths = ['test']
# apidoc_separate_modules = True
apidoc_toc_file = False

autodoc_member_order = 'bysource'

autodoc_default_options = {
    'special-members': True,
    'undoc-members': True,
    'show-inheritance': True,
    'members': True,
    'inherited-members': True,
}
