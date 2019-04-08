#!/usr/bin/env python3
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

import os

from setuptools import setup


NAME = 'roberto'


def get_version():
    """Read __version__ from version.py, with exec to avoid importing it."""
    try:
        with open(os.path.join(NAME, 'version.py'), 'r') as f:
            myglobals = {}
            exec(f.read(), myglobals)  # pylint: disable=exec-used
        return myglobals['__version__']
    except IOError:
        return "0.0.0.post0"


def load_readme():
    """Load README for display on PyPI."""
    with open('README.rst') as f:
        return f.read()


setup(
    name=NAME,
    version=get_version(),
    package_dir={NAME: NAME},
    packages=[NAME, NAME + '.test'],
    description='Collection of configurable development workflows',
    long_description=load_readme(),
    author='HORTON-ChemTools Dev Team',
    author_email='horton.chemtools@gmail.com',
    url='https://github.com/theochem/roberto',
    include_package_data=True,
    install_requires=[
        'invoke', 'pyyaml', 'importlib_resources; python_version < "3.7"'],
    python_requires='>=3.5',
    entry_points={
        'console_scripts': ['rob = roberto.__main__:main']
    },
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
