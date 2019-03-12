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
"""Define the Roberto's configuration."""

import os
import subprocess
try:
    from importlib_resources import open_text
except ImportError:
    from importlib.resources import open_text

from invoke.config import Config, merge_dicts, DataProxy
import yaml

from .utils import parse_git_describe


class RobertoConfig(Config):
    """A specialized Invoke configuration for Roberto.

    The main modifications in behavior w.r.t. the vanilla Config are:

    - The `roberto` prefix.
    - A project config file `.roberto.*` can be loaded from the current directory.
    - Default configuration.
    - Config finalization, filling in some blanks with sensible defaults.

    """

    prefix = 'roberto'

    def load_base_conf_files(self):
        Config.load_base_conf_files(self)
        # Always truy load the project config file.
        self._load_file(prefix="project", merge=False)

    def set_project_location(self, path):
        """
        Set the directory path where a project-level config file may be found.

        Does not do any file loading on its own; for that, see `load_project`.

        .. versionadded:: 1.0
        """
        # Impose our own project location, config file prefixed with dot.
        self._set(_project_prefix=os.path.join(os.getcwd(), '.'))
        self._set(_project_path=None)
        self._set(_project_found=None)
        self._set(_project={})

    def load_shell_env(self):
        Config.load_shell_env(self)
        # Once everything is loaded, including environment variables, finalize
        # the config, mostly for convenience.
        self._finalize()

    def _finalize(self):
        """Derive some config variables for convenience."""
        # Expand stuff in paths
        self.conda.download_path = os.path.expandvars(os.path.expanduser(self.conda.download_path))
        self.conda.base_path = os.path.expandvars(os.path.expanduser(self.conda.base_path))

        # The conda environment
        env_name = self.project.name + '-dev'
        if self.conda.pinning:
            env_name += '-' + '-'.join(self.conda.pinning.split())
        self.conda.env_name = env_name
        env_path = os.path.join(self.conda.base_path, 'envs', env_name)
        self.conda.env_path = env_path
        print("Conda development environment: {}".format(env_name))

        # Package default options
        self.project.packages = [
            DataProxy.from_data(package) for package in self.project.packages]
        for package in self.project.packages:
            if 'path' not in package:
                package.path = '.'
            if 'name' not in package:
                package.name = self.project.name

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
        with open_text('roberto', 'default_config.yaml') as f:
            my_defaults = yaml.load(f)
        return merge_dicts(their_defaults, my_defaults)
