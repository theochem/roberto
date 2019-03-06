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
"""Utilities used by tasks in Roberto's workflow.

These utility functions should be testable with unit tests.
"""


from glob import glob
import hashlib
import json
import os
from typing import List

from invoke import Context


__all__ = ['update_env_command', 'compute_req_hash', 'run_tools', 'append_path']


def update_env_command(ctx: Context, command: str) -> None:
    """Update the environment variables with a bash command.

    Parameters
    ----------
    ctx
        The context object with which to execute the command.
    command
        A bash command line.

    """
    dump = 'python -c "import os, json; print(json.dumps(dict(os.environ)))"'
    result = ctx.run('{} && {}'.format(command, dump), hide=True)
    newenv = json.loads(result.stdout)
    for key, value in newenv.items():
        os.environ[key] = value
    removed_keys = [key for key in os.environ.keys() if key not in newenv]
    for key in removed_keys:
        del os.environ[key]


def compute_req_hash(conda_packages: List[str], recipe_dirs: List[str],
                     pip_packages: List[str]) -> str:
    """Compute a hash from all parameters that affect installed packages.

    Parameters
    ----------
    conda_packages
        A list of packages to be installed with conda.
    recipe_dirs
        The directories with the conda recipes. All files in these directories
        will be loaded and hashed.
    pip_packages:
        A list of packages to be installed with pip.

    Returns
    -------
    req_hash
        The hex digest of the sha256 hash of all development requirements.

    """
    hasher = hashlib.sha256()
    for conda_package in conda_packages:
        hasher.update(conda_package.encode('utf-8'))
    for recipe_dir in recipe_dirs:
        for fn_recipe in glob(os.path.join(recipe_dir, "*")):
            if os.path.isfile(fn_recipe):
                with open(fn_recipe, 'br') as f:
                    hasher.update(f.read())
    for pip_package in pip_packages:
        hasher.update(pip_package.encode('utf-8'))
    return hasher.hexdigest()


def run_tools(ctx: Context, subtask: str, env=None):
    """Run a specific subtask from a list of tools for all packages.

    Parameters
    ----------
    ctx
        The context object with which to execute the commands.
    subtask
        A subtask, defined by Roberto's (main) tasks.
    env
        Custom environment variables needed by the tools.

    """
    for package in ctx.project.packages:
        workdir = package["path"]
        for toolname in package["tools"]:
            commands = ctx.tools[toolname].get(subtask, [])
            for cmd in commands:
                # fill in all parameters and execute
                mycmd = "cd {}; ".format(workdir)
                mycmd += cmd.format(config=ctx.config, **package)
                ctx.run(mycmd, env=env)


def append_path(env: dict, name: str, newdir: str):
    """Append a directory to a path environment variable.

    Parameters
    ----------
    env
        A dictionary with environment variables.
    name
        The name of the variable to update.
    newdir
        The name of the directory to add.

    """
    if name in env:
        env[name] += ':' + newdir
    else:
        env[name] = newdir
