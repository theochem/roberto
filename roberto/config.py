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
import subprocess

from invoke.config import Config, merge_dicts

from .utils import parse_git_describe


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
        # Once all is loaded, finalize the config, mostly for convenience:
        self._finalize()

    def _finalize(self):
        """Derive some config variables for convenience.

        Note: nested mofications inside data proxy objects do not survive.
        TODO: report this issue as bug and after fixed, set default tool config.
        """
        # Expand stuff in paths
        self.conda.download_path = os.path.expandvars(os.path.expanduser(self.conda.download_path))
        self.conda.base_path = os.path.expandvars(os.path.expanduser(self.conda.base_path))

        # The conda environment
        env_name = self.project.name + '-dev'
        if self.conda.pinning:
            env_name += '-' + '-'.join(self.conda.pinning.split())
        print("Conda development environment: {}".format(env_name))

        # Package default options
        env_path = os.path.join(self.conda.base_path, 'envs', env_name)
        self.conda.env_name = env_name
        self.conda.env_path = env_path
        for package in self.project.packages:
            if 'path' not in package:
                package['path'] = '.'
            if 'name' not in package:
                package['name'] = self.project.name

        # Fix a problem with the conda build purge feature.
        # See https://github.com/conda/conda-build/issues/2592
        # CONDA_BLD_PATH should not be overwritten, to allow for customization.
        if 'CONDA_BLD_PATH' not in os.environ:
            os.environ['CONDA_BLD_PATH'] = os.path.join(self.conda.env_path, 'conda-bld')
        self.conda.build_path = os.environ['CONDA_BLD_PATH']

        # Git version and branch information
        try:
            git_describe = subprocess.run(
                ['git', 'describe', '--tags'],
                capture_output=True, check=True).stdout.decode('utf-8')
        except subprocess.CalledProcessError:
            # May fail, e.g. when there are no tags.
            git_describe = '0.0.0-0-notag'
        self.git.update(parse_git_describe(git_describe))
        print('Version number {} derived from `git describe --tags` {}.'.format(
            self.git.tag_version, self.git.describe))

        self.git.branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, check=True).stdout.decode('utf-8').strip()

    @staticmethod
    def global_defaults() -> dict:
        """Set the global default configuration."""
        their_defaults = Config.global_defaults()
        my_defaults = {'run': {
            'echo': True,
        }, 'conda': {
            'download_path': '${HOME}/Downloads/miniconda.sh',
            'linux_url': 'https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh',
            'osx_url': 'https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh',
            'base_path': '${HOME}/miniconda3',
            'pinning': 'python 3.7',
        }, 'deploy': False, 'project': {
            'inplace_env': {},
            'name': None,
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
                'config': {
                    'pip_requirements':
                        ['git+https://github.com/theochem/cardboardlint.git'
                         '@master#egg=cardboardlint'],
                    'conda_requirements':
                        ['pycodestyle', 'pydocstyle', 'pylint', 'flake8',
                         'conda-forge::cppcheck', 'conda-forge::cpplint',
                         'conda-forge::yamllint'],
                },
                'commands': {
                    'lint_static_master': ['cardboardlinter -f static'],
                    'lint_static_feature':
                        ['cardboardlinter -r {config.git.merge_branch} -f static'],
                    'lint_dynamic_master': ['cardboardlinter -f dynamic'],
                    'lint_dynamic_feature':
                        ['cardboardlinter -r {config.git.merge_branch} -f dynamic'],
                },
            },
            'pytest': {
                'config': {
                    'conda_requirements': ['pytest', 'pytest-cov'],
                },
                'commands': {
                    'test_inplace':
                        ["pytest {name} -v --cov={name} --cov-report xml "
                         "--cov-report term-missing --cov-branch --color=yes"],
                    'test_inplace_ci': ["bash <(curl -s https://codecov.io/bash)"]
                },
            },
            'nose': {
                'config': {
                    'conda_requirements': ['nose', 'coverage'],
                },
                'commands': {
                    'test_inplace':
                        ["rm -f .coverage",
                         "nosetests {name} -v --detailed-errors "
                         "--with-coverage --cover-package={name} "
                         "--cover-tests --cover-inclusive --cover-branches",
                         "coverage xml -i"],
                },
            },
            'maketest': {
                'config': {
                    'pip_requirements': ['gcovr'],
                },
                'commands': {
                    'test_inplace':
                        ["cd build; find | grep '\\.gcda$' | xargs rm -vf",
                         "cd build; make test",
                         "cd {name}; gcovr -r . --gcov-executable ${{HOST}}-gcov "
                         " --object-directory ../build/{name}/CMakeFiles/{name}.dir"],
                },
            },
            'py_build_inplace': {
                'config': {
                    'build_inplace_paths': {'PYTHONPATH': '{path}/{name}'},
                },
                'commands': {
                    'build_inplace':
                        ['python setup.py build_ext -i -L $LD_LIBRARY_PATH '
                         '-I $CPATH --define CYTHON_TRACE_NOGIL'],
                }
            },
            'cpp_build_inplace': {
                'config': {
                    'build_inplace_paths': {
                        'CPATH': '{path}',
                        'LD_LIBRARY_PATH': '{path}/build/{name}',
                    },
                },
                'commands': {
                    'build_inplace':
                        ['mkdir -p build',
                         'cd build; cmake .. -DCMAKE_BUILD_TYPE=debug',
                         'cd build; make']
                },
            },
        }}
        return merge_dicts(their_defaults, my_defaults)
