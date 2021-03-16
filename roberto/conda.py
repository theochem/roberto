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
"""Conda-specific infrastructure for Roberto."""


from glob import glob
import json
import os
import platform
import stat
import tempfile
import urllib.request
import warnings

from invoke import Context, Failure
import yaml

from .utils import (update_env_command, compute_req_hash,
                    check_install_requirements, install_macosx_sdk)


def conda_deactivate(ctx: Context, iterate: bool = True):
    """Deactivate the current conda environment, if any.

    Parameters
    ----------
    ctx
        A invoke.Context instance.
    iterate
        Normally, this function keeps deactivating until conda is totally
        out of the environment variables. To get a single iteration, set this
        argument to False

    """
    def clean_env():
        """Get rid of lingering conda environment variables."""
        # See https://github.com/conda/conda/issues/7031
        if "HOST" in os.environ:
            del os.environ['HOST']
        for name in list(os.environ.keys()):
            if name.startswith("CONDA_"):
                del os.environ[name]

    # 0) Return if no work needs to be done
    if "CONDA_PREFIX" not in os.environ:
        clean_env()
        return

    # 1) Get the base path of the currently loaded conda, could be different
    #    from ours
    conda_exe = os.path.normpath(os.environ["CONDA_EXE"])
    conda_base_path = os.sep.join(conda_exe.split('/')[:-2])
    command = ". {}/etc/profile.d/conda.sh; conda deactivate".format(conda_base_path)

    # 2) Deactivate until conda is gone.
    update_env_command(ctx, command)
    if iterate:
        while "CONDA_PREFIX" in os.environ:
            update_env_command(ctx, command)
        clean_env()


def conda_activate(ctx: Context, env: str):
    """Activate the given conda environment.

    Parameters
    ----------
    ctx
        A invoke.Context instance.
    env
        The name of the environment to activate.

    """
    # Load the correct base environment. These commands define bash functions
    # which are not exported, but we need them for future conda commands to
    # work, hence "set -a" to export all variables and functions, also those not
    # marked for export.
    command = ("set -a && . {}/etc/profile.d/conda.sh; conda activate {}").format(
        ctx.conda.base_path, env)
    update_env_command(ctx, command)


def install_conda(ctx: Context):
    """Install miniconda if not present yet."""
    # Install miniconda if needed.
    dest = ctx.conda.base_path
    if not os.path.isdir(os.path.join(dest, 'bin')):
        dwnlconda = os.path.join(ctx.download_dir, 'miniconda.sh')
        if os.path.isfile(dwnlconda):
            print("Conda installer already present: {}".format(dwnlconda))
        else:
            print("Downloading latest conda to {}.".format(dwnlconda))
            if platform.system() == 'Darwin':
                urllib.request.urlretrieve(ctx.conda.osx_url, dwnlconda)
            elif platform.system() == 'Linux':
                urllib.request.urlretrieve(ctx.conda.linux_url, dwnlconda)
            else:
                raise Failure("Operating system {} not supported.".format(platform.system()))

        # Fix permissions of the conda installer.
        os.chmod(dwnlconda, os.stat(dwnlconda).st_mode | stat.S_IXUSR)

        # Unload any currently loaded conda environments.
        conda_deactivate(ctx)

        # Install
        print("Installing conda in {}.".format(dest))
        ctx.run("{} -b -p {}".format(dwnlconda, dest))

        # Load our new conda environment
        conda_activate(ctx, "base")


def setup_conda_env(ctx: Context):
    """Set up a conda testing environment."""
    # Bail out if not needed.
    if not ctx.testenv.from_scratch:
        return
    # Install conda if not present.
    install_conda(ctx)

    # Check the sanity of the pinning configuration
    for char in "=<>!*":
        if char in ctx.conda.pinning:
            raise Failure("Character '{}' should not be used in pinning.".format(char))
    pinned_words = ctx.conda.pinning.split()
    if len(pinned_words) % 2 != 0:
        raise Failure("Pinning config should be an even number of words, alternating "
                      "package names and versions, without wildcards.")
    pinned_reqs = ["{}={}".format(name, version) for name, version
                   in zip(pinned_words[::2], pinned_words[1::2])]

    # Load the correct base environment.
    conda_deactivate(ctx)
    conda_activate(ctx, "base")

    # Check if the right environment exists, and make if needed.
    result = ctx.run("conda env list --json")
    print("Conda env needed is: {}".format(ctx.conda.env_path))
    if ctx.conda.env_path not in json.loads(result.stdout)["envs"]:
        ctx.run("conda create -n {} {} -y".format(ctx.conda.env_name, " ".join(pinned_reqs)))
        with open(os.path.join(ctx.conda.env_path, "conda-meta", "pinning"), "w") as f:
            for pin in pinned_reqs:
                f.write(pin + "\n")

    # Load the development environment.
    conda_activate(ctx, ctx.conda.env_name)

    # Reset the channels. Removing previous may fail if there were none. That's ok.
    ctx.run("conda config --remove-key channels", warn=True, hide='err')
    for channel in ctx.conda.channels:
        # Prepend is used to take as many packages as possible, e.g.
        # from conda-forge. Appending can cause issues with some packages are
        # present in the default channel and some are not (dependency issues.)
        ctx.run("conda config --prepend channels {}".format(channel))


# pylint: disable=too-many-branches,too-many-statements
def install_requirements_conda(ctx: Context):
    """Install all requirements, including tools used by Roberto."""
    # Bail out if not needed.
    if not ctx.testenv.install_requirements:
        return
    # Set up conda environment.
    setup_conda_env(ctx)
    # Install the macosx sdk
    install_macosx_sdk(ctx, ctx.conda.base_path)

    # Collect all parameters determining the install commands (to good
    # approximation) and turn them into a hash.
    # Some conda requirements are included by default because they must be present:
    # - conda: to make sure it is always up to date.
    # - conda-build: to have conda-render for getting requirements from recipes.
    conda_reqs = set(["conda", "conda-build"])
    pip_reqs = set([])
    recipe_dirs = []
    # Add project as a tool because it also contains requirements.
    tools = [ctx.project]
    for package in ctx.project.packages:
        for toolname in package.tools:
            tools.append(ctx.tools[toolname])
        recipe_dir = os.path.join(package.path, "tools", "conda.recipe")
        if os.path.isdir(recipe_dir):
            recipe_dirs.append(recipe_dir)
        else:
            warnings.warn("Skipping recipe {}. (directory does not exist)".format(recipe_dir))
    for tool in tools:
        for conda_req, pip_req in tool.get("requirements", []):
            if conda_req is None:
                pip_reqs.add(pip_req)
                conda_reqs.add("pip")
            else:
                conda_reqs.add(conda_req)
    req_hash = compute_req_hash(
        set("conda:" + conda_req for conda_req in conda_reqs) |
        set("pip:" + pip_req for pip_req in pip_reqs),
        sum([glob(os.path.join(recipe_dir, "*")) for recipe_dir in recipe_dirs], [])
    )

    fn_skip = os.path.join(ctx.conda.env_path, ".skip_install")
    if check_install_requirements(fn_skip, req_hash):
        # Update conda packages in the base env. Conda packages in the dev env
        # tend to be ignored.
        ctx.run("conda install --update-deps -y -n base -c defaults {}".format(
            " ".join("'{}'".format(conda_req) for conda_req
                     in conda_reqs if conda_req.startswith('conda'))))

        # Update and install other requirements for Roberto, in the dev env.
        conda_activate(ctx, ctx.conda.env_name)
        ctx.run("conda install --update-deps -y {}".format(" ".join(
            "'{}'".format(conda_req) for conda_req in conda_reqs
            if not conda_req.startswith('conda'))))

        print("Rendering conda package, extracting requirements, which will be installed.")

        # Install dependencies from recipes, excluding own packages.
        own_conda_reqs = [package.dist_name for package in ctx.project.packages]
        for recipe_dir in recipe_dirs:
            # Send the output of conda render to a temporary directory.
            with tempfile.TemporaryDirectory() as tmpdir:
                rendered_path = os.path.join(tmpdir, "rendered.yml")
                ctx.run(
                    "conda render -f {} {} --variants {}".format(
                        rendered_path, recipe_dir, ctx.conda.variants),
                    env={"PROJECT_VERSION": ctx.git.tag_version})
                with open(rendered_path) as f:
                    rendered = yaml.safe_load(f)
            # Build a (simplified) list of requirements and install.
            dep_conda_reqs = set([])
            req_sources = [
                ("requirements", 'build'),
                ("requirements", 'host'),
                ("requirements", 'run'),
                ("test", 'requires'),
            ]
            for req_section, req_type in req_sources:
                for recipe_req in rendered.get(req_section, {}).get(req_type, []):
                    words = recipe_req.split()
                    if words[0] not in own_conda_reqs:
                        dep_conda_reqs.add(" ".join(words[:2]))
            ctx.run("conda install --update-deps -y {}".format(" ".join(
                "'{}'".format(conda_req) for conda_req in dep_conda_reqs)))

        # Deactivate and activate conda again after installing conda packages,
        # because new environment variables may need to be set by the activation
        # script.
        conda_deactivate(ctx)
        conda_activate(ctx, ctx.conda.env_name)

        # Update and install requirements for Roberto from pip, if any.
        if pip_reqs:
            ctx.run("pip install --upgrade {}".format(" ".join(
                "'{}'".format(pip_req) for pip_req in pip_reqs)))

        # Update the timestamp on the skip file.
        with open(fn_skip, 'w') as f:
            f.write(req_hash + '\n')


def nuclear_conda(ctx: Context):
    """Erase the conda environment."""
    # Go back to the base env before nuking the development env.
    conda_deactivate(ctx)
    conda_activate(ctx, "base")
    if ctx.testenv.from_scratch:
        ctx.run("conda uninstall -n {} --all -y".format(ctx.conda.env_name))
        ctx.run("git clean -fdX")
