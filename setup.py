#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
"""roberto setup script.

If you are not familiar with setup.py, just use pip instead:

    pip install roberto --user --upgrade

Alternatively, you can install from source with

    ./setup.py install --user
"""

from __future__ import print_function

from setuptools import setup


def get_version():
    """Load the version from version.py, without importing it.

    This function assumes that the last line in the file contains a variable defining the
    version string with single quotes.

    """
    try:
        with open('roberto/version.py', 'r') as f:
            return f.read().split('=')[-1].replace('\'', '').strip()
    except IOError:
        return "0.0.0"


def load_readme():
    """Load README.rst for display on PyPI."""
    with open('README.rst') as f:
        return f.read()


setup(
    name='roberto',
    version=get_version(),
    description='Collection of configurable development workflows',
    long_description=load_readme(),
    author='HORTON-ChemTools Dev Team',
    author_email='horton.chemtools@gmail.com',
    url='https://github.com/theochem/roberto',
    packages=['roberto', 'roberto.test'],
    package_dir={'roberto': 'roberto'},
    install_requires=['invoke', 'pyyaml'],
    entry_points={
        'console_scripts': ['rob = roberto.__main__:main']
    }
)
