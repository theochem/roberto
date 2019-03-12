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
"""Define the Roberto's default configuration."""

import os

from invoke.config import Config, merge_dicts


class RobertoConfig(Config):
    """A specialized Invoke configuration for Roberto.

    The main modifications in behavior w.r.t. the vanilla Config are:

    - The `roberto` prefix.
    - A project config file `.roberto.*` can be loaded from the current directory.
    - Default configuration.

    """

    prefix = 'roberto'

    def __init__(self, *args, **kwargs):
        """Initialize Roberto Config instance, extend with loading local config.

        See invoke.config.Config.__init__ for details.
        """
        Config.__init__(self, *args, **kwargs)
        # The following will let invoke pick up a local project's .roberto.yaml
        # (or its alternative forms).
        self._set(_project_prefix=os.path.join(os.getcwd(), '.'))
        self._set(_project_path=None)
        self._set(_project_found=None)
        self._set(_project={})
        if not kwargs.get("lazy", False):
            self._load_file(prefix="project", merge=False)

    @staticmethod
    def global_defaults() -> dict:
        """Set the global default configuration."""
        their_defaults = Config.global_defaults()
        my_defaults = {'run': {
            'echo': True,
        }, 'conda': {
            'download_path': os.path.join(os.environ['HOME'], 'Downloads', 'miniconda.sh'),
            'linux_url': 'https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh',
            'osx_url': 'https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh',
            'base_path': os.path.join(os.environ['HOME'], 'miniconda3'),
            'pinning': 'python 3.7',
        }, 'deploy': False, 'project': {
            'packages': [
                # Repeat as many as you like. order may matter.
                # {
                #  'conda_name': name of the conda package,
                #  'kind': 'py' or 'cpp',
                #  'tools': list, any of the tools defined below.,
                #  'name': python or cpp name, defaults to project.name,
                #  'path': root of the package relative to the project root,
                #          defaults to '.'},
            ]
        }, 'git': {
            'merge_branch': 'master',
        }, 'tools': {
            'cardboardlint': {
                '__pip__': ['git+https://github.com/theochem/cardboardlint.git'
                            '@master#egg=cardboardlint'],
                '__conda__': ['pycodestyle', 'pydocstyle', 'pylint', 'flake8',
                              'conda-forge::cppcheck', 'conda-forge::cpplint',
                              'conda-forge::yamllint'],
                'lint_static_master': ['cardboardlinter -f static'],
                'lint_static_feature': ['cardboardlinter -r {config.git.merge_branch} '
                                        '-f static'],
                'lint_dynamic_master': ['cardboardlinter -f dynamic'],
                'lint_dynamic_feature': ['cardboardlinter -r {config.git.merge_branch} '
                                         '-f dynamic'],
            },
            'pytest': {
                '__conda__': ['pytest', 'pytest-cov'],
                'test_inplace': ["pytest {name} -v --cov={name} --cov-report xml "
                                 "--cov-report term-missing --cov-branch --color=yes"],
                'test_inplace_ci': ["bash <(curl -s https://codecov.io/bash)"]
            },
            'nose': {
                '__conda__': ['nose', 'coverage'],
                'test_inplace': ["rm -f .coverage",
                                 "nosetests {name} -v --detailed-errors "
                                 "--with-coverage --cover-package={name} "
                                 "--cover-tests --cover-inclusive --cover-branches",
                                 "coverage xml -i"],
            },
            'maketest': {
                '__pip__': ['gcovr'],
                'test_inplace': [
                    "cd build; find | grep '\\.gcda$' | xargs rm -vf"
                    "cd build; make test",
                    "cd {name}; gcovr -r . --gcov-executable ${{HOST}}-gcov "
                    " --object-directory ../build/{name}/CMakeFiles/{name}.dir"],
            }
        }}
        return merge_dicts(their_defaults, my_defaults)
