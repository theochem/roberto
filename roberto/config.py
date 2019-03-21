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
        # Always try to load the project config file.
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
        # Check if essential configuration is present.
        if self.project.name is None:
            raise TypeError("No project name defined in the configuration. Missing .roberty.yaml?")

        # Expand stuff in paths
        self.conda.download_dir = os.path.expandvars(os.path.expanduser(self.conda.download_dir))
        self.conda.base_path = os.path.expandvars(os.path.expanduser(self.conda.base_path))

        # Derive the name for the conda environment.
        env_name = self.project.name + '-dev'
        if self.conda.pinning:
            env_name += '-' + '-'.join(self.conda.pinning.split())
        self.conda.env_name = env_name
        self.conda.env_path = os.path.join(self.conda.base_path, 'envs', env_name)

        # Package default options
        self.project.packages = [
            DataProxy.from_data(package) for package in self.project.packages]
        for package in self.project.packages:
            if 'path' not in package:
                package.path = '.'
            package.abspath = os.path.abspath(package.path)
            if 'name' not in package:
                package.name = self.project.name
            if 'tools' not in package:
                package.tools = []
            # Check if all tools exist
            for toolname in package.tools:
                if toolname not in self.tools:
                    raise ValueError("Unknown Roberto tool: {}".format(toolname))

        # CONDA_BLD_PATH should not be overwritten, to allow for customization.
        if 'CONDA_BLD_PATH' in os.environ:
            self.conda.build_path = os.environ['CONDA_BLD_PATH']
        else:
            self.conda.build_path = os.path.join(self.conda.env_path, 'conda-bld')

    @staticmethod
    def global_defaults() -> dict:
        """Set the global default configuration."""
        defaults = Config.global_defaults()

        # Load default configuration
        with open_text('roberto', 'default_config.yaml') as f:
            defaults = merge_dicts(defaults, yaml.safe_load(f))

        # Git version and branch information
        try:
            git_describe = subprocess.run(
                ['git', 'describe', '--tags'],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                check=True).stdout.decode('utf-8')
        except subprocess.CalledProcessError:
            # May fail, e.g. when there are no tags.
            git_describe = '0.0.0-0-notag'
        defaults['git'].update(parse_git_describe(git_describe))

        # First try to get a decent branch name
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE, check=True).stdout.decode('utf-8').strip()
        # If that failed, try to get the tag
        if branch == 'HEAD':
            try:
                branch = subprocess.run(
                    ["git", "describe", "--tags", "--exact-match"],
                    stdout=subprocess.PIPE, check=True).stdout.decode('utf-8').strip()
            except subprocess.CalledProcessError:
                # Final attempt, just the sha.
                try:
                    branch = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        stdout=subprocess.PIPE, check=True).stdout.decode('utf-8').strip()
                except subprocess.CalledProcessError:
                    branch = '__nogit__'
        defaults['git']['branch'] = branch

        return defaults
