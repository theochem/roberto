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
"""Tasks in Roberto's workflow."""


from glob import glob
import json
import os
import platform
import stat
import tempfile
import time
import urllib.request

from invoke import task
from invoke.exceptions import Failure
import yaml

from .utils import (conda_deactivate, conda_activate, compute_req_hash,
                    iter_packages_tools)


@task
def sanitize_git(ctx):
    """Fetch required git branches when absent."""
    branch = ctx.git.merge_branch

    # Test if merge branch is present
    try:
        ctx.run("git rev-parse --verify {}".format(branch))
        return
    except Failure:
        print("Merge branch \"{}\" not found.".format(branch))

    # Try to create it without connection to origin
    try:
        ctx.run("git branch --track {0} origin/{0}".format(branch))
        return
    except Failure:
        print("Local copy of remote merge branch \"{}\" not found.".format(branch))

    # Last resort: fetch the merge branch
    ctx.run("git fetch origin {0}:{0}".format(branch))


@task()
def install_conda(ctx):
    """Install miniconda if not present yet."""
    dest = ctx.conda.base_path
    if not os.path.isdir(os.path.join(dest, 'bin')):
        # Prepare download location
        dwnl = ctx.conda.download_path
        dwnldir = os.path.dirname(dwnl)
        if not os.path.isdir(dwnldir):
            os.makedirs(dwnldir)

        if os.path.isfile(dwnl):
            print("Conda install already present: {}".format(dwnl))
        else:
            print("Downloading latest conda to {}.".format(dwnl))
            system = platform.system()
            if system == 'Darwin':
                urllib.request.urlretrieve(ctx.conda.osx_url, dwnl)
            elif system == 'Linux':
                urllib.request.urlretrieve(ctx.conda.linux_url, dwnl)
            else:
                raise Failure("Operating system {} not supported.".format(system))

        # Fix permissions of the conda installer.
        os.chmod(dwnl, os.stat(dwnl).st_mode | stat.S_IXUSR)

        # Unload any currently loaded conda environments.
        conda_deactivate(ctx)

        # Install
        print("Installing conda in {}.".format(dest))
        ctx.run("{} -b -p {}".format(dwnl, dest))

        # Load our new conda environment
        conda_activate(ctx, "base")

        # Update to the latest conda. This is needed upfront because the conda
        # version from the miniconda installer is easily outdated. However,
        # latest versions might also have their issues. At the moment, updating
        # is unavoidable becuase we are otherwise hitting bugs.
        ctx.run("conda update -n base -c defaults conda -y")


@task(install_conda)
def setup_conda_env(ctx):
    """Set up a conda testing environment."""
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
    if ctx.conda.env_path not in json.loads(result.stdout)["envs"]:
        ctx.run("conda create -n {} {} -y".format(ctx.conda.env_name, " ".join(pinned_reqs)))
        with open(os.path.join(ctx.conda.env_path, "conda-meta", "pinning"), "w") as f:
            for pin in pinned_reqs:
                f.write(pin + "\n")

    # Load the development environment.
    conda_activate(ctx, ctx.conda.env_name)

    # Reset the channels. Removing previous may fail if there were none. That's ok.
    ctx.run("conda config --remove-key channels", warn=True)
    for channel in ctx.conda.channels:
        # Append is used to keep defaults at highest priority, essentially
        # to avoid pulling in lots of conda-forge packages, which may be
        # lower quality than their counterparts in the default channels.
        ctx.run("conda config --append channels {}".format(channel))


@task(setup_conda_env)
def install_requirements(ctx):
    """Install all dependencies, including tools used by roberto."""
    # Collect all parameters determining the install commands, to good
    # approximation and turn them into a hash.
    conda_packages = set(["conda", "conda-build"])
    pip_packages = set([])
    recipe_dirs = []
    for package in ctx.project.packages:
        for toolname in package.tools:
            config = ctx.tools[toolname].get('config', {})
            conda_packages.update(config.get('conda_requirements', []))
            pip_packages.update(config.get('pip_requirements', []))
        recipe_dirs.append(os.path.join(package.path, "tools", "conda.recipe"))
    conda_packages = sorted(conda_packages)
    pip_packages = sorted(pip_packages)
    recipe_dirs = sorted(recipe_dirs)
    req_hash = compute_req_hash(conda_packages, recipe_dirs, pip_packages)
    print("The requirements hash is: {}".format(req_hash))

    # The install and update will be skipped if it was done already once,
    # less than 24 hours ago and the req_hash has not changed.
    fn_skip = os.path.join(ctx.conda.env_path, ".skip_install")
    skip_install = False
    if os.path.isfile(fn_skip):
        if (time.time() - os.path.getmtime(fn_skip)) < 24*3600:
            with open(fn_skip) as f:
                if f.read().strip() == req_hash:
                    skip_install = True

    if skip_install:
        print("Skipping install and update of packages in conda env.")
        print("To force install: rm {}".format(fn_skip))
    else:
        # Update and install dependencies
        ctx.run("conda install --update-deps -y {}".format(" ".join(conda_packages)))

        # Render the conda package specs, extract and install dependencies.
        print("Rendering conda package and extracting dependencies.")
        own_conda_packages = [package.conda_name for package in ctx.project.packages]
        for recipe_dir in recipe_dirs:
            with tempfile.TemporaryDirectory() as tmpdir:
                rendered_path = os.path.join(tmpdir, "rendered.yml")
                ctx.run("conda render -f {} {}".format(rendered_path, recipe_dir),
                        env={"PROJECT_VERSION": ctx.git.tag_version})
                with open(rendered_path) as f:
                    rendered = yaml.load(f)
            requirements = set([])
            for reqtype in 'build', 'host', 'run':
                for requirement in rendered.get("requirements", {}).get(reqtype, []):
                    words = requirement.split()
                    if words[0] not in own_conda_packages:
                        requirements.add("'" + " ".join(words[:2]) + "'")
            ctx.run("conda install --update-deps -y {}".format(" ".join(requirements)))

        # Update and install linting tools from pip, if any
        if pip_packages:
            ctx.run("pip install --upgrade {}".format(" ".join(pip_packages)))

        # Update the timestamp on the skip file.
        with open(fn_skip, 'w') as f:
            f.write(req_hash + '\n')

        # Deactivate and activate conda again, because it set more environment
        # variables after compilers have been installed.
        conda_deactivate(ctx)
        conda_activate(ctx, ctx.conda.env_name)


@task()
def write_version(ctx):
    """Derive the version files from git describe."""
    for tool, package, fmtkargs in iter_packages_tools(ctx, "write-version"):
        fn_version = tool.destination.format(**fmtkargs)
        content = tool.template.format(**fmtkargs)
        with open(os.path.join(package.path, fn_version), 'w') as f:
            f.write(content)


@task(install_requirements, sanitize_git, write_version)
def lint_static(ctx):
    """Run static linters."""
    for tool, package, fmtkargs in iter_packages_tools(ctx, "lint-static"):
        with ctx.cd(package.path):
            if ctx.git.branch == "" or ctx.git.branch == ctx.git.merge_branch:
                for command in tool.commands_master:
                    ctx.run(command.format(**fmtkargs))
            else:
                for command in tool.commands_feature:
                    ctx.run(command.format(**fmtkargs))


@task(install_requirements, sanitize_git, write_version)
def build_inplace(ctx):
    """Build in-place."""
    # First do all the building
    inplace_env = {}
    for tool, package, fmtkargs in iter_packages_tools(ctx, "build-inplace"):
        with ctx.cd(package.path):
            for command in tool.commands:
                ctx.run(command.format(**fmtkargs), env=inplace_env)
                paths = tool.get('paths', {})
                for name, dirname in paths.items():
                    dirname = dirname.format(**fmtkargs)
                    dirname = os.path.abspath(dirname)
                    if name in inplace_env:
                        inplace_env[name] += ':' + dirname
                    else:
                        inplace_env[name] = dirname
    ctx.project.inplace_env = inplace_env
    # Then also write a file, activate-*.sh, which can be sourced to
    # activate the in-place build.
    with open('activate-{}.sh'.format(ctx.conda.env_name), 'w') as f:
        f.write('[[ -n $CONDA_PREFIX_1 ]] && conda deactivate &> /dev/null\n')
        f.write('[[ -n $CONDA_PREFIX ]] && conda deactivate &> /dev/null\n')
        f.write('source {}/bin/activate\n'.format(ctx.conda.base_path))
        f.write('conda activate {}\n'.format(ctx.conda.env_name))
        for name, value in inplace_env.items():
            f.write('export {0}=${{{0}}}:{1}\n'.format(name, value))
        f.write('export PROJECT_VERSION={}\n'.format(ctx.git.tag_version))


@task(build_inplace)
def test_inplace(ctx):
    """Run tests in-place and upload coverage if requested."""
    for tool, package, fmtkargs in iter_packages_tools(ctx, "test-inplace"):
        with ctx.cd(package.path):
            for command in tool.commands:
                ctx.run(command.format(**fmtkargs), env=ctx.project.inplace_env)
    if ctx.upload_coverage:
        ctx.run("bash <(curl -s https://codecov.io/bash)")


@task(build_inplace)
def lint_dynamic(ctx):
    """Run dynamic linters."""
    for tool, package, fmtkargs in iter_packages_tools(ctx, "lint-dynamic"):
        with ctx.cd(package.path):
            if ctx.git.branch == "" or ctx.git.branch == ctx.git.merge_branch:
                for command in tool.commands_master:
                    ctx.run(command.format(**fmtkargs))
            else:
                for command in tool.commands_feature:
                    ctx.run(command.format(**fmtkargs))


@task(install_requirements, write_version)
def build_packages(ctx):
    """Build the source package(s)."""
    for tool, package, fmtkargs in iter_packages_tools(ctx, "build-packages"):
        with ctx.cd(package.path):
            for command in tool.commands:
                ctx.run(command.format(**fmtkargs))


@task(install_requirements, build_packages)
def deploy(ctx):  # pylint: disable=unused-argument
    """Run all deployment tasks."""
    # Check if we need to deploy
    if not ctx.deploy:
        print("Deployment not requested in configuration.")
        return

    # Get the deployment label, or return if no release is to be made.
    if ctx.git.tag_stable:
        deploy_label = "main"
    elif ctx.git.tag_test:
        deploy_label = "test"
    elif ctx.git.tag_dev:
        deploy_label = "dev"
    else:
        print("No deployment because the version is not for release: {}".format(
            ctx.git.tag_version))
        return

    checked_deploy_vars = set([])
    for tool, package, fmtkargs in iter_packages_tools(ctx, "deploy"):
        # Check if and how deployment vars are set.
        for deploy_var in tool.deploy_vars:
            if deploy_var not in checked_deploy_vars:
                check_env_var(deploy_var)
                checked_deploy_vars.add(deploy_var)
        # Collect assets for each tool
        pattern = tool.asset_pattern.format(**fmtkargs)
        assets = glob(pattern)
        if not assets:
            raise Failure("Could not find assets for {}: {}".format(tool.name, pattern))
        # Check if needed.
        if deploy_label not in tool.deploy_labels:
            print("Skipping {} for package {}, because of deploy label {}.".format(
                tool.name, package.name, deploy_label))
            continue
        # Set extra formatting variables
        fmtkargs.update({
            'assets': ' '.join(assets),
            'hub_assets': ' '.join('-a {}'.format(asset) for asset in assets),
            'deploy_label': deploy_label,
        })
        # Run deployment commands
        for command in tool.commands:
            ctx.run(command.format(**fmtkargs))


def check_env_var(name):
    """Check if an environment variable is set and non-empty."""
    if name not in os.environ:
        print('The environment variable {} is not set.'.format(name))
    elif os.environ[name] == "":
        print('The environment variable {} is empty.'.format(name))
    else:
        print('The environment variable {} is not empty.'.format(name))


@task(setup_conda_env)
def nuclear(ctx):
    """USE AT YOUR OWN RISK. Purge conda env and stale files in source tree."""
    # Go back to the base env before nuking the development env.
    conda_deactivate(ctx, iterate=False)
    ctx.run("conda uninstall -n {} --all -y".format(ctx.conda.env_name))
    ctx.run("git clean -fdx")


@task(lint_static, build_inplace, test_inplace, lint_dynamic)
def quality(ctx):  # pylint: disable=unused-argument
    """Run all quality assurance tasks: linting and in-place testing."""


@task(quality, deploy, default=True)
def robot(ctx):  # pylint: disable=unused-argument
    """Run all tasks, except nuclear."""
