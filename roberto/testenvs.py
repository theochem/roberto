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
"""Tools to set up virtual environments.

All classes implemented here are stateless. They do not have attributes and
store state information in the configuration object instead. They are
essentially groups of methods with compatible API, yet with implementation
details that may differ.
"""

import json
import os
import platform
import stat
import subprocess
import urllib.request

from invoke import Failure


def append_activate(ctx, line):
    """Append a line to the activate script and show it."""
    mode = "w" if ctx.testenv.activate == "true" else "a"
    with open(ctx.testenv.fn_activate, mode) as f:
        f.write(line + "\n")
    print(f"\033[0;96m   ENV:  {line}\033[0;0m")
    ctx.testenv.activate = "source " + os.path.abspath(ctx.testenv.fn_activate)


def install_macosx_sdk(ctx):
    """Install MacOSX SDK if on OSX if needed."""
    if platform.system() == 'Darwin' and ctx.macosx.install_sdk:
        optdir = os.path.join(ctx.testenv.base_path, 'opt')
        if not os.path.isdir(optdir):
            os.makedirs(optdir)
        sdk = f'MacOSX{ctx.macosx.release}.sdk'
        sdk_root = os.path.join(optdir, sdk)
        if not os.path.isdir(sdk_root):
            sdk_tar = f'{sdk}.tar.xz'
            sdk_dwnl = os.path.join(ctx.download_dir, sdk_tar)
            sdk_url = f'{ctx.maxosx.sdk_release}/{sdk_tar}'
            print(f"Downloading {sdk_url}")
            urllib.request.urlretrieve(sdk_url, sdk_dwnl)
            with ctx.cd(optdir):
                ctx.run(f'tar -xJf {sdk_dwnl}')
        append_activate(ctx, "export MACOSX_DEPLOYMENT_TARGET=" + ctx.macosx.release)
        append_activate(ctx, f'export SDKROOT="{sdk_root}"')
        print(f'MaxOSX sdk in: {sdk_root}')
        ctx.run(f'ls -alh {sdk_root}')
        ctx.macosx.sdk_root = sdk_root


def init_testenv(cfg):
    """Initialize a test environment defined in the configuration."""
    # Only initialize once
    if cfg.testenv.name is None:
        function = {
            "conda": init_testenv_conda,
            "venv": init_testenv_venv,
            "none": init_testenv_none,
        }[cfg.testenv.use]
        function(cfg)


def init_testenv_conda(cfg):
    """Initialize a testenv using Conda."""
    cfg.testenv = {}
    cfg.testenv.base_path = os.path.expandvars(os.path.expanduser(cfg.conda.base_path))
    cfg.testenv.name = cfg.project.name + '-dev'
    if cfg.conda.pinning:
        cfg.testenv.name += '-' + '-'.join(cfg.conda.pinning.split())
    cfg.testenv.path = os.path.join(cfg.testenv.base_path, 'envs', cfg.testenv.name)
    cfg.testenv.fn_activate = f"activate-conda-{cfg.testenv.name}.sh"
    cfg.testenv.activate = "true"
    cfg.testenv.setup = setup_conda
    cfg.testenv.nuke = nuke_conda


def install_conda(ctx):
    """Install miniconda if not present yet."""
    # Install miniconda if needed.
    if not os.path.isdir(os.path.join(ctx.testenv.base_path, 'bin')):
        dwnlconda = os.path.join(ctx.download_dir, 'miniconda.sh')
        if os.path.isfile(dwnlconda):
            print(f"Conda installer already present: {dwnlconda}")
        else:
            print(f"Downloading latest conda to {dwnlconda}.")
            if platform.system() == 'Darwin':
                urllib.request.urlretrieve(ctx.conda.osx_url, dwnlconda)
            elif platform.system() == 'Linux':
                urllib.request.urlretrieve(ctx.conda.linux_url, dwnlconda)
            else:
                raise Failure(f"Operating system {platform.system()} not supported.")

        # Fix permissions of the conda installer.
        os.chmod(dwnlconda, os.stat(dwnlconda).st_mode | stat.S_IXUSR)

        # Install
        print(f"Installing conda in {ctx.testenv.base_path}.")
        ctx.run(f"{dwnlconda} -b -p {ctx.testenv.base_path}")

    ctx.conda.activate_base = f"source '{ctx.testenv.base_path}/bin/activate'"

    install_macosx_sdk(ctx)


def setup_conda(ctx):
    """Set up a conda testing environment."""
    # Install stuff that may not be present.
    install_conda(ctx)

    # CONDA_BLD_PATH should not be overwritten, to allow for customization.
    if 'CONDA_BLD_PATH' in os.environ:
        ctx.conda.build_path = os.environ['CONDA_BLD_PATH']
    else:
        ctx.conda.build_path = os.path.join(ctx.testenv.path, 'conda-bld')

    # Check the sanity of the pinning configuration
    for char in "=<>!*":
        if char in ctx.conda.pinning:
            raise Failure(f"Character '{char}' should not be used in pinning.")
    pinned_words = ctx.conda.pinning.split()
    if len(pinned_words) % 2 != 0:
        raise Failure("Pinning config should be an even number of words, alternating "
                      "package names and versions, without wildcards.")

    # pinning as requirements for building the initial test environment.
    pinned_reqs = [
        f"{name}={version}" for name, version
        in zip(pinned_words[::2], pinned_words[1::2])]

    # Create the variants argument for render and build
    pinned_words = ctx.conda.pinning.split()
    ctx.conda.variants = '"{' + ','.join(
        f"{name}: '{version}'" for name, version
        in zip(pinned_words[::2], pinned_words[1::2])) + '}"'

    append_activate(ctx, '[[ -n \"${CONDA_PREFIX_1}\" ]] && conda deactivate &> /dev/null')
    append_activate(ctx, '[[ -n \"${CONDA_PREFIX}\" ]] && conda deactivate &> /dev/null')
    append_activate(ctx, ctx.conda.activate_base)

    with ctx.prefix(ctx.testenv.activate):
        # Check if the right environment exists, and make if needed.
        result = ctx.run("conda env list --json")
        print(f"Required conda env: {ctx.testenv.path}")
        if ctx.testenv.path not in json.loads(result.stdout)["envs"]:
            ctx.run(f"conda create -n {ctx.testenv.name} {' '.join(pinned_reqs)} -y")
            with open(os.path.join(ctx.testenv.path, "conda-meta", "pinning"), "w") as f:
                for pin in pinned_reqs:
                    f.write(pin + "\n")

    append_activate(ctx, f'conda activate {ctx.testenv.name}')
    append_activate(ctx, f'export CONDA_BLD_PATH="{ctx.conda.build_path}"')
    append_activate(ctx, f'export PROJECT_VERSION="{ctx.git.tag_version}"')

    with ctx.prefix(ctx.testenv.activate):
        # Reset the channels. Removing previous may fail if there were none. That's ok.
        ctx.run("conda config --env --remove-key channels", warn=True, hide='err')
        for channel in ctx.conda.channels:
            ctx.run(f"conda config --env --add channels {channel}")
        ctx.run("conda config --env --set channel_priority strict")


def nuke_conda(ctx):
    """Erase the conda environment."""
    # Go back to the base env before nuking the development env.
    setup_conda(ctx)
    with ctx.prefix(ctx.conda.activate_base):
        ctx.run(f"conda uninstall -n {ctx.testenv.name} --all -y")
    ctx.run("git clean -fdX")


def init_testenv_venv(cfg):
    """Initialize a test environment using Python's built-in venv."""
    cfg.testenv = {}
    cfg.testenv.base_path = os.path.expandvars(os.path.expanduser(cfg.venv.base_path))
    try:
        pyver = subprocess.run(
            ['python', '-c', 'import sys; print("{}.{}".format(*sys.version_info[:2]))'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=True).stdout.decode('utf-8').strip()
    except subprocess.CalledProcessError:
        # May fail, e.g. when python binary is absent.
        pyver = 'X.Y'
    cfg.testenv.name = cfg.project.name + '-dev-python-' + pyver
    cfg.testenv.path = os.path.join(cfg.testenv.base_path, cfg.testenv.name)
    cfg.testenv.fn_activate = f"activate-venv-{cfg.testenv.name}.sh"
    cfg.testenv.activate = "true"
    cfg.testenv.setup = setup_venv
    cfg.testenv.nuke = nuke_venv


def setup_venv(ctx):
    """Make sure there is a virtual environment and activate it."""
    # Check if the required environment already exists
    if not os.path.isdir(ctx.testenv.path):
        # Create a new environment
        ctx.run(f"{ctx.venv.python_bin} -m venv {ctx.testenv.path}")
    else:
        print("Virtual environment already exists:")
        print(ctx.testenv.path)
    append_activate(ctx, '[[ -n "${VIRTUAL_ENV}" ]] && deactivate &> /dev/null')
    append_activate(ctx, f"source {ctx.testenv.path}/bin/activate")

    install_macosx_sdk(ctx)


def nuke_venv(ctx):
    """Erase the virtual environment."""
    # Not (yet) removing it, just showing how.
    ctx.run(f"echo rm -rv {ctx.testenv.path}")
    ctx.run("git clean -fdX")


def init_testenv_none(cfg):
    """Initialize a testenv without really doing anything."""
    cfg.testenv = {}
    cfg.testenv.base_path = None
    cfg.testenv.name = "noenv"
    cfg.testenv.path = None
    cfg.testenv.fn_activate = "activate.sh"
    cfg.testenv.activate = "true"
    cfg.testenv.setup = setup_none
    cfg.testenv.nuke = nuke_none


def setup_none(ctx):  # pylint: disable=unused-argument
    """Do nothing. Stub for API consistency."""


def nuke_none(ctx):  # pylint: disable=unused-argument
    """Do nothing. Stub for API consistency."""
