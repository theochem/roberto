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

from invoke import Context, Failure
import yaml

from .utils import compute_req_hash, check_install_requirements, install_macosx_sdk


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

        # Install
        print("Installing conda in {}.".format(dest))
        ctx.run("{} -b -p {}".format(dwnlconda, dest))

    ctx.conda.activate_base = "source {}/etc/profile.d/conda.sh".format(ctx.conda.base_path)


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

    with ctx.prefix(ctx.conda.activate_base):
        # Check if the right environment exists, and make if needed.
        result = ctx.run("conda env list --json")
        print("Conda env needed is: {}".format(ctx.conda.env_path))
        if ctx.conda.env_path not in json.loads(result.stdout)["envs"]:
            ctx.run("conda create -n {} {} -y".format(ctx.conda.env_name, " ".join(pinned_reqs)))
            with open(os.path.join(ctx.conda.env_path, "conda-meta", "pinning"), "w") as f:
                for pin in pinned_reqs:
                    f.write(pin + "\n")

    ctx.testenv.activate = "{} && conda activate {}".format(
        ctx.conda.activate_base, ctx.conda.env_name
    )

    with ctx.prefix(ctx.testenv.activate):
        # Reset the channels. Removing previous may fail if there were none. That's ok.
        ctx.run("conda config --env --remove-key channels", warn=True, hide='err')
        for channel in ctx.conda.channels:
            # Prepend is used to take as many packages as possible, e.g.
            # from conda-forge. Appending can cause issues with some packages are
            # present in the default channel and some are not (dependency issues.)
            ctx.run("conda config --env --prepend channels {}".format(channel))


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
            print("Skipping recipe {}. (directory does not exist)".format(recipe_dir))
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
        with ctx.prefix(ctx.testenv.activate):
            # Update conda packages in the base env. Conda packages in the dev env
            # tend to be ignored.
            ctx.run("conda install --update-deps -y -n base -c defaults {}".format(
                " ".join("'{}'".format(conda_req) for conda_req
                         in conda_reqs if conda_req.startswith('conda'))))

            # Update and install other requirements for Roberto, in the dev env.
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
    if ctx.testenv.from_scratch:
        with ctx.prefix(ctx.conda.activate_base):
            ctx.run("conda uninstall -n {} --all -y".format(ctx.conda.env_name))
        ctx.run("git clean -fdX")
