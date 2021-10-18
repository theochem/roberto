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
"""Installation of requirements."""


from glob import glob
import hashlib
import os
import tempfile
import time
from typing import Set

from invoke import Context
import yaml

from .tools import TOOLS


def compute_req_hash(req_items: Set[str], req_fns: Set[str]) -> str:
    """Compute a hash from all parameters that affect installed packages.

    Parameters
    ----------
    req_items
        A set of requirement items.
    req_fns
        A set of requirement files.

    Returns
    -------
    hashdigest : str
        The hex digest of the sha256 hash of all development requirements.

    """
    hasher = hashlib.sha256()
    for req_item in sorted(req_items):
        hasher.update(req_item.encode('utf-8'))
    for req_fn in sorted(req_fns):
        hasher.update(req_fn.encode("utf-8"))
        if os.path.isfile(req_fn):
            with open(req_fn, 'br') as f:
                hasher.update(f.read())
    return hasher.hexdigest()


def check_install_requirements(fn_skip: str, req_hash: str) -> bool:
    """Check if reinstallation of requirements is desired.

    Parameters
    ----------
    fn_skip
        File where the requirements hash is stored.
    req_has
        The (new) requirement hash.

    Returns
    -------
    install
        True if reinstallation is desired.

    """
    # The install and update will be skipped if it was done already once,
    # less than 24 hours ago and the req_hash has not changed.
    if os.path.isfile(fn_skip):
        if (time.time() - os.path.getmtime(fn_skip)) < 24*3600:
            with open(fn_skip) as f:
                if f.read().strip() == req_hash:
                    print("Skipping install+update of requirements.")
                    print(f"To force install+update: rm {fn_skip}")
                    return False
    print("Starting install+update of requirements.")
    print(f"To skip install+update: echo {req_hash} > {fn_skip}")
    return True


# pylint: disable=too-many-branches,too-many-statements
def install_requirements_conda(ctx: Context):
    """Install all requirements, including tools used by Roberto."""
    # Collect all parameters determining the install commands (to good
    # approximation) and turn them into a hash.
    # Some conda requirements are included by default because they must be present:
    # - conda: to make sure it is always up to date.
    # - conda-build: to have conda-render for getting requirements from recipes.
    conda_reqs = set(["conda"])
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
            print(f"Skipping recipe {recipe_dir}. (directory does not exist)")
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

    fn_skip = os.path.join(ctx.testenv.path, ".skip_install")
    if check_install_requirements(fn_skip, req_hash):
        with ctx.prefix(ctx.conda.activate_base):
            # Update conda packages in the base env. Conda packages in the dev env
            # tend to be ignored.
            conda_reqs_base_str = " ".join(
                f"'{conda_req}'" for conda_req
                in conda_reqs if conda_req.startswith('conda')
            )
            ctx.run(f"conda install --update-deps -y {conda_reqs_base_str}")

        with ctx.prefix(ctx.testenv.activate):
            # Update packages already installed
            ctx.run("conda update --all -y")

            # Update and install other requirements for Roberto, in the dev env.
            conda_reqs_dev_str = " ".join(
                f"'{conda_req}'" for conda_req in conda_reqs
                if not conda_req.startswith('conda')
            )
            ctx.run(f"conda install --update-deps -y {conda_reqs_dev_str}")

            print("Rendering conda package, extracting requirements, which will be installed.")

            # Install dependencies from recipes, excluding own packages.
            own_conda_reqs = [package.dist_name for package in ctx.project.packages]
            for recipe_dir in recipe_dirs:
                # Send the output of conda render to a temporary directory.
                with tempfile.TemporaryDirectory() as tmpdir:
                    rendered_path = os.path.join(tmpdir, "rendered.yml")
                    ctx.run(
                        f"conda render -f {rendered_path} {recipe_dir} "
                        f"--variants {ctx.conda.variants}"
                    )
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
                            dep_conda_req = words[0]
                            if len(words) > 1 and any(char in words[1] for char in "<>!="):
                                dep_conda_req += " " + words[1]
                            dep_conda_reqs.add(dep_conda_req)
                conda_reqs_render_str = " ".join(
                    f"'{conda_req}'" for conda_req in dep_conda_reqs
                )
                ctx.run(f"conda install --update-deps -y {conda_reqs_render_str}")

            # Update and install requirements for Roberto from pip, if any.
            if pip_reqs:
                pip_reqs_str = " ".join(f"'{pip_req}'" for pip_req in pip_reqs)
                ctx.run(f"pip install --upgrade {pip_reqs_str}")

        # Update the timestamp on the skip file.
        with open(fn_skip, 'w') as f:
            f.write(req_hash + '\n')


def convert_requires(fn_requires, fn_requirements):
    """Convert requires.txt from an egg-info to a requirements.txt file."""
    requires = []
    suffix = ""
    with open(fn_requires) as f:
        for line in f:
            line = line.strip()
            if len(line) == 0:
                continue
            if line.startswith("[:"):
                suffix = "; " + line[2:-1]
            else:
                requires.append(line + suffix)
    print("Extracted requirements:")
    with open(fn_requirements, "w") as f:
        for require in requires:
            print(require)
            f.write(require + "\n")


def install_requirements_pip(ctx: Context):
    """Install requirements in the virtual environment."""
    # Collect all parameters determining installation of requirements
    pip_reqs = set([])
    req_fns = set([])
    for _conda_req, pip_req in ctx.project.requirements:
        if pip_req is not None:
            pip_reqs.add(pip_req)
    for package in ctx.project.packages:
        for toolname in package.tools:
            tool = TOOLS[toolname]
            for _conda_req, pip_req in tool.requirements:
                if pip_req is not None:
                    pip_reqs.add(pip_req)
        req_fns.add(os.path.join(package.path, "setup.py"))
    req_hash = compute_req_hash(pip_reqs, req_fns)

    fn_skip = os.path.join(ctx.testenv.path, ".skip_install")
    if check_install_requirements(fn_skip, req_hash):
        with ctx.prefix(ctx.testenv.activate):
            if len(pip_reqs) > 0:
                # Upgrade pip
                ctx.run("pip install -U pip")
                # Install pip packages for the tools
                pip_reqs_str = " ".join(f"'{pip_req}'" for pip_req in pip_reqs)
                ctx.run(f"pip install -U {pip_reqs_str}")
            # Install dependencies for the project.
            for package in ctx.project.packages:
                with ctx.cd(package.path):
                    ctx.run("python setup.py egg_info")
                    fn_requires = os.path.join(
                        package.dist_name.replace("-", "_") + ".egg-info",
                        "requires.txt")
                    with tempfile.TemporaryDirectory() as tmpdir:
                        fn_requirements = os.path.join(tmpdir, "requirements.txt")
                        convert_requires(fn_requires, fn_requirements)
                        ctx.run("pip install -U -r " + fn_requirements)
        # Update the timestamp on the skip file.
        with open(fn_skip, 'w') as f:
            f.write(req_hash + '\n')
