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

from invoke import task, Failure
import yaml

from .utils import (conda_deactivate, conda_activate, compute_req_hash,
                    iter_packages_tools, run_all_commands)


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
            print("Conda installer already present: {}".format(dwnl))
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
    """Install all requirements, including tools used by Roberto."""
    # Collect all parameters determining the install commands, to good
    # approximation and turn them into a hash.
    conda_packages = set(["conda", "conda-build"])
    pip_packages = set([])
    recipe_dirs = []
    for package in ctx.project.packages:
        for toolname in package.tools:
            tool = ctx.tools[toolname]
            conda_packages.update(tool.get('conda_requirements', []))
            pip_packages.update(tool.get('pip_requirements', []))
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
        print("Skipping install+update of packages in conda env.")
        print("To force install+update: rm {}".format(fn_skip))
    else:
        # Update and install requirements for Roberto
        ctx.run("conda install --update-deps -y {}".format(" ".join(conda_packages)))

        print("Rendering conda package, extracting requirements, which will be installed.")
        own_conda_packages = [package.conda_name for package in ctx.project.packages]
        for recipe_dir in recipe_dirs:
            # Send the output of conda render to a temporary directory.
            with tempfile.TemporaryDirectory() as tmpdir:
                rendered_path = os.path.join(tmpdir, "rendered.yml")
                ctx.run("conda render -f {} {}".format(rendered_path, recipe_dir),
                        env={"PROJECT_VERSION": ctx.git.tag_version})
                with open(rendered_path) as f:
                    rendered = yaml.load(f)
            # Build a (simplified) list of requirements and install.
            requirements = set([])
            for reqtype in 'build', 'host', 'run':
                for requirement in rendered.get("requirements", {}).get(reqtype, []):
                    words = requirement.split()
                    if words[0] not in own_conda_packages:
                        requirements.add("'" + " ".join(words[:2]) + "'")
            ctx.run("conda install --update-deps -y {}".format(" ".join(requirements)))

        # Update and install requirements for Roberto from pip, if any.
        if pip_packages:
            ctx.run("pip install --upgrade {}".format(" ".join(pip_packages)))

        # Update the timestamp on the skip file.
        with open(fn_skip, 'w') as f:
            f.write(req_hash + '\n')

        # Deactivate and activate conda again, because more environment
        # variables need to be set by the activation script after compilers
        # have been installed.
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
    if ctx.git.branch == "" or ctx.git.branch == ctx.git.merge_branch:
        run_all_commands(ctx, "lint-static", 'commands_master')
    else:
        run_all_commands(ctx, "lint-static", 'commands_feature')


@task(install_requirements, sanitize_git, write_version)
def build_inplace(ctx):
    """Build in-place."""
    # First do all the building.
    inplace_env = {}
    for tool, package, fmtkargs in iter_packages_tools(ctx, "build-inplace"):
        with ctx.cd(package.path):
            for command in tool.commands:
                ctx.run(command.format(**fmtkargs), env=inplace_env)
                # Update *PATH variables in environment for subsequent paclages.
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
    # In-place tests need the environment variable changes from the in-place build.
    run_all_commands(ctx, "test-inplace", env=ctx.project.inplace_env)
    if ctx.upload_coverage:
        ctx.run("bash <(curl -s https://codecov.io/bash)")


@task(build_inplace)
def lint_dynamic(ctx):
    """Run dynamic linters."""
    if ctx.git.branch == "" or ctx.git.branch == ctx.git.merge_branch:
        run_all_commands(ctx, "lint-dynamic", 'commands_master')
    else:
        run_all_commands(ctx, "lint-dynamic", 'commands_feature')


@task(install_requirements, write_version)
def build_packages(ctx):
    """Build software package(s)."""
    run_all_commands(ctx, "build-packages")


@task(install_requirements, write_version)
def build_docs(ctx):
    """Build documentation."""
    run_all_commands(ctx, "build-docs")


def need_deployment(ctx, prefix):
    """Return True if deployment is needed, globally speaking."""
    if not ctx.deploy:
        print("{} not requested in configuration.".format(prefix))
        return False
    if ctx.git.deploy_label is None:
        print("{} skipped because the version is not for release: {}".format(
            prefix, ctx.git.tag_version))
        return False
    return True


def check_env_var(name):
    """Check if an environment variable is set and non-empty."""
    if name not in os.environ:
        print('The environment variable {} is not set.'.format(name))
    elif os.environ[name] == "":
        print('The environment variable {} is empty.'.format(name))
    else:
        print('The environment variable {} is not empty.'.format(name))


@task(install_requirements, build_packages)
def deploy(ctx):
    """Run all deployment tasks."""
    if not need_deployment(ctx, "Deployment"):
        return

    checked_deploy_vars = set([])
    for tool, package, fmtkargs in iter_packages_tools(ctx, "deploy"):
        # Check if and how deployment vars are set.
        for deploy_var in tool.deploy_vars:
            if deploy_var not in checked_deploy_vars:
                check_env_var(deploy_var)
                checked_deploy_vars.add(deploy_var)
        # Collect assets for each tool.
        pattern = tool.asset_pattern.format(**fmtkargs)
        assets = glob(pattern)
        if not assets:
            raise Failure("Could not find assets for {}: {}".format(tool.name, pattern))
        # Check if deployment is needed with deploy_label.
        if ctx.git.deploy_label not in tool.deploy_labels:
            print("Skipping {} for package {}, because of deploy label {}.".format(
                tool.name, package.name, ctx.git.deploy_label))
            continue
        # Set extra formatting variables.
        fmtkargs.update({
            'assets': ' '.join(assets),
            'hub_assets': ' '.join('-a {}'.format(asset) for asset in assets),
        })
        # Run deployment commands.
        with ctx.cd(package.path):
            for command in tool.commands:
                ctx.run(command.format(**fmtkargs))


@task(install_requirements, build_docs)
def upload_docs_git(ctx):
    """Squash-push documentation to a git branch."""
    if not need_deployment(ctx, "Doc upload"):
        return

    for tool, package, fmtkargs in iter_packages_tools(ctx, "upload-docs-git"):
        # Check if deployment is needed with deploy_label.
        if ctx.git.deploy_label not in tool.deploy_labels:
            print("Skipping {} for package {}, because of deploy label {}.".format(
                tool.name, package.name, ctx.git.deploy_label))
            continue

        with ctx.cd(package.path):
            # Switch to a docu branch and remove everything that was present in
            # the previous commit. It is assumed that the doc branch is an
            # orphan branch made previously.
            ctx.run("git checkout {}".format(tool.docbranch))
            ctx.run("git ls-tree HEAD -r --name-only | xargs rm")
            # Copy the documentation to the repo root.
            docroot = tool.docroot.format(**fmtkargs)
            ctx.run("GLOBIGNORE='.:..'; cp -rv {}/* .".format(docroot))
            # Add all files
            for root, _dirs, filenames in os.walk(docroot):
                for filename in filenames:
                    fullfn = os.path.join(root, filename)[len(docroot)+1:]
                    ctx.run("git add {}".format(fullfn))
            # Commit, push and go back to the original branch
            ctx.run("git commit -a -m 'Automatic documentation update' --amend")
            ctx.run("git push -f {0} {1}:{1}".format(tool.docremote, tool.docbranch))
            ctx.run("git checkout {}".format(ctx.git.branch))


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


@task(quality, deploy, upload_docs_git, default=True)
def robot(ctx):  # pylint: disable=unused-argument
    """Run all tasks, except nuclear."""
