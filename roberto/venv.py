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
"""Pip/VirtualEnv-specific infrastructure for Roberto."""

import os

from invoke import Context

from .utils import (update_env_command, compute_req_hash,
                    check_install_requirements, install_macosx_sdk)


def venv_deactivate(ctx: Context):
    """Deactivate the virtual environement."""
    if "VIRTUAL_ENV" in os.environ:
        update_env_command(ctx, "deactivate")


def venv_activate(ctx: Context):
    """Activate the virtual environement."""
    update_env_command(ctx, "source {}/bin/activate".format(ctx.venv.env_path))


def setup_venv(ctx: Context):
    """Make sure there is a virtual environment and activate it."""
    if not ctx.testenv.from_scratch:
        return
    # Deactivate any existing venv
    venv_deactivate(ctx)
    # Check if the required environment already exists
    if not os.path.isdir(ctx.venv.env_path):
        # Create a new environment
        ctx.run("{} -m venv {}".format(ctx.venv.python_bin, ctx.venv.env_path))
    # Activate the environment
    venv_activate(ctx)


def install_requirements_venv(ctx: Context):
    """Install requirements in the virtual environment."""
    # Bail out if not needed.
    if not ctx.testenv.install_requirements:
        return
    # Set up conda environment.
    setup_venv(ctx)
    # Install the macosx sdk
    install_macosx_sdk(ctx, ctx.venv.base_path)

    # Collect all parameters determining installation of requirements
    pip_reqs = set([])
    req_fns = set([])
    # Add project as a tool because they may also contain requirements, e.g.
    # related to testing.
    tools = [ctx.project]
    for package in ctx.project.packages:
        for toolname in package.tools:
            tools.append(ctx.tools[toolname])
        req_fns.add(os.path.join(package.path, "requirements.txt"))
        req_fns.add(os.path.join(package.path, "setup.py"))
    for tool in tools:
        for _conda_req, pip_req in tool.get("requirements", []):
            if pip_req is not None:
                pip_reqs.add(pip_req)
    req_hash = compute_req_hash(pip_reqs, req_fns)

    fn_skip = os.path.join(ctx.venv.env_path, ".skip_install")
    if check_install_requirements(fn_skip, req_hash):
        # Install pip packages for the tools
        ctx.run("pip install -U {}".format(" ".join(
                "'{}'".format(pip_req) for pip_req in pip_reqs)))
        # Install dependencies for the project.
        for package in ctx.project.packages:
            with ctx.cd(package.path):
                if os.path.isfile("requirements.txt"):
                    ctx.run("pip install -U -r requirements")
                # setup.py must be present.
                # Installing as editable package differs from the conda
                # environment, where in-place packages are used instead.
                # It would be nice to get the same behavior in both cases.
                ctx.run("pip install -e ./")
        # Update the timestamp on the skip file.
        with open(fn_skip, 'w') as f:
            f.write(req_hash + '\n')


def nuclear_venv(ctx: Context):
    """Erase the virtual environment."""
    venv_deactivate(ctx)
    if ctx.testenv.from_scratch:
        ctx.run("echo rm -rv {}".format(ctx.conda.env_path))
        ctx.run("git clean -fdX")
