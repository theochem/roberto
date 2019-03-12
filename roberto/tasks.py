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
                    run_tools, append_path, parse_git_describe)


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


@task(sanitize_git)
def _finalize_config(ctx):
    """Derive some config variables for convenience."""
    # The conda environment
    env_name = ctx.project.name + '-dev'
    if ctx.conda.pinning:
        env_name += '-' + '-'.join(ctx.conda.pinning.split())
    print("# Conda development environment: {}".format(env_name))

    # Package default options
    env_path = os.path.join(ctx.conda.base_path, 'envs', env_name)
    ctx.conda.env_name = env_name
    ctx.conda.env_path = env_path
    for package in ctx.project.packages:
        if 'path' not in package:
            package['path'] = '.'
        if 'name' not in package:
            package['name'] = ctx.project.name

    # Fix a problem with the conda build purge feature.
    # See https://github.com/conda/conda-build/issues/2592
    # CONDA_BLD_PATH should not be overwritten, to allow for customization.
    if 'CONDA_BLD_PATH' not in os.environ:
        os.environ['CONDA_BLD_PATH'] = os.path.join(ctx.conda.env_path, 'conda-bld')
    ctx.conda.build_path = os.environ['CONDA_BLD_PATH']

    # Git version and branch information
    try:
        git_describe = ctx.run('git describe --tags').stdout
    except Failure:
        # May fail, e.g. when there are no tags.
        git_describe = '0.0.0-0-notag'
    ctx.git.update(parse_git_describe(git_describe))
    print('Version number {} derived from `git describe --tags` {}.'.format(
        ctx.git.tag_version, ctx.git.describe))
    result = ctx.run("git rev-parse --abbrev-ref HEAD")
    ctx.git.branch = result.stdout.strip()


@task
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


@task(install_conda, _finalize_config)
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
    result = ctx.run("conda env list --json", hide=True)
    if ctx.conda.env_path not in json.loads(result.stdout)["envs"]:
        ctx.run("conda create -n {} {} -y".format(ctx.conda.env_name, " ".join(pinned_reqs)))
        with open(os.path.join(ctx.conda.env_path, "conda-meta", "pinning"), "w") as f:
            for pin in pinned_reqs:
                f.write(pin + "\n")

    # Load the development environment.
    conda_activate(ctx, ctx.conda.env_name)


@task(setup_conda_env)
def install_requirements(ctx):
    """Install dependencies, linters and packaging tools."""
    # Collect all parameters determining the install commands, to good
    # approximation and turn them into a hash.
    conda_packages = set(["conda", "conda-build", "anaconda-client",
                          "conda-verify", "twine", "conda-forge::hub"])
    pip_packages = set([])
    recipe_dirs = []
    for package in ctx.project.packages:
        for tool in package['tools']:
            conda_packages.update(ctx.tools[tool].get('__conda__', []))
            pip_packages.update(ctx.tools[tool].get('__pip__', []))
        recipe_dirs.append(os.path.join(package['path'], "tools", "conda.recipe"))
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

    if not skip_install:
        # Update and install conda build, anaconda client, conda verify and
        # linting tools, if any.
        ctx.run("conda install --update-deps -y {}".format(" ".join(conda_packages)))

        # Render the conda package specs, extract and install dependencies.
        print("Rendering conda package and extracting dependencies.")
        own_conda_packages = [package['conda_name'] for package in ctx.project.packages]
        conda_packages = set([])
        for recipe_dir in recipe_dirs:
            with tempfile.TemporaryDirectory() as tmpdir:
                rendered_path = os.path.join(tmpdir, "rendered.yml")
                ctx.run("conda render -f {} {}".format(rendered_path, recipe_dir),
                        env={"PROJECT_VERSION": ctx.git.tag_version})
                with open(rendered_path) as f:
                    rendered = yaml.load(f)
            requirements = []
            for reqtype in 'build', 'host', 'run':
                requirements.extend(rendered.get("requirements", {}).get(reqtype, []))
            for requirement in requirements:
                words = requirement.split()
                if words[0] not in own_conda_packages:
                    conda_packages.add("'" + " ".join(words[:2]) + "'")
        ctx.run("conda install --update-deps -y {}".format(" ".join(conda_packages)))

        # Update and install linting tools from pip, if any
        if pip_packages:
            ctx.run("pip install --upgrade {}".format(" ".join(pip_packages)))

        # Update the timestamp on the skip file.
        with open(fn_skip, 'w') as f:
            f.write(req_hash + '\n')
    else:
        print("Skipping install and update of packages in conda env.")
        print("To force install: rm {}".format(fn_skip))


@task(install_requirements, sanitize_git)
def lint_static(ctx):
    """Run static linters."""
    if ctx.git.branch == "" or ctx.git.branch == ctx.git.merge_branch:
        run_tools(ctx, "lint_static_master")
    else:
        run_tools(ctx, "lint_static_feature")


VERSION_TEMPLATES = {
    'py': """\
\"""Do not edit this file because it will be overwritten before packaging.

The output of git describe was: {config.git.describe}
\"""
__version__ = '{config.git.tag_version}'
""",
    'cpp': """\
# This file is automatically generated. Changes will be overwritten before packaging.
set(GIT_DESCRIBE "{config.git.describe}")
set(GIT_TAG_VERSION "{config.git.tag_version}")
set(GIT_TAG_SOVERSION "{config.git.tag_soversion}")
set(GIT_TAG_VERSION_MAJOR "{config.git.tag_version_major}")
set(GIT_TAG_VERSION_MINOR "{config.git.tag_version_minor}")
set(GIT_TAG_VERSION_PATCH "{config.git.tag_version_patch}")
"""}


@task(_finalize_config)
def write_version(ctx):
    """Derive the version files from git describe."""
    for package in ctx.project.packages:
        if package['kind'] == "py":
            fn_version = os.path.join(package['name'], "version.py")
        elif package['kind'] == "cpp":
            fn_version = "CMakeListsVersion.txt.in"
        fn_version = os.path.join(package['path'], fn_version)
        with open(fn_version, "w") as f:
            f.write(VERSION_TEMPLATES[package['kind']].format(config=ctx.config))


@task(install_requirements, write_version)
def build_inplace(ctx):
    """Build in-place."""
    inplace_env = {}
    for package in ctx.project.packages:
        workdir = package['path']
        if package['kind'] == "py":
            # Build a debugging version of a Python package, possibly linking
            # with earlier packages in this project.
            ctx.run(("cd {}; python setup.py build_ext -i -L $LD_LIBRARY_PATH "
                     "-I $CPATH --define CYTHON_TRACE_NOGIL").format(workdir),
                    env=inplace_env)
            append_path(inplace_env, "PYTHONPATH",
                        os.path.join(os.getcwd(), workdir, package['name']))
        elif package['kind'] == "cpp":
            # Build a debug version of a C++ packages, possibly linking with
            # earlier packages in this project.
            append_path(inplace_env, "CPATH",
                        os.path.join(os.getcwd(), workdir))
            ctx.run("cd {}; mkdir -p build".format(workdir))
            workdir = os.path.join(workdir, "build")
            ctx.run("cd {}; cmake .. -DCMAKE_BUILD_TYPE=debug".format(workdir), env=inplace_env)
            ctx.run("cd {}; make".format(workdir), env=inplace_env)
            append_path(inplace_env, "LD_LIBRARY_PATH",
                        os.path.join(os.getcwd(), workdir, package['name']))

    ctx.project.inplace_env = inplace_env


@task(build_inplace)
def test_inplace(ctx):
    """Run tests in-place."""
    run_tools(ctx, "test_inplace", env=ctx.project.inplace_env)
    if "CONTINUOUS_INTEGRATION" in os.environ:
        ctx.run("bash <(curl -s https://codecov.io/bash)")


@task(build_inplace, sanitize_git)
def lint_dynamic(ctx):
    """Run dynamic linters."""
    if ctx.git.branch == "" or ctx.git.branch == ctx.git.merge_branch:
        run_tools(ctx, "lint_dynamic_master", env=ctx.project.inplace_env)
    else:
        run_tools(ctx, "lint_dynamic_feature", env=ctx.project.inplace_env)


@task(install_requirements, write_version)
def build_source(ctx):
    """Build the source package."""
    for package in ctx.project.packages:
        workdir = package['path']
        if package['kind'] == "py":
            ctx.run("cd {}; python setup.py sdist".format(workdir))
        elif package['kind'] == "cpp":
            ctx.run("cd {}; mkdir -p dist".format(workdir))
            workdir = os.path.join(workdir, "dist")
            ctx.run("cd {}; cmake .. -DCMAKE_BUILD_TYPE=release".format(workdir))
            ctx.run("cd {}; make sdist".format(workdir))


@task(install_requirements, write_version)
def build_conda(ctx):
    """Build the Conda package."""
    ctx.run("conda build purge-all")
    for package in ctx.project.packages:
        workdir = package['path']
        env = {'PROJECT_VERSION': ctx.git.tag_version}
        ctx.run("cd {}; rm -rf build; conda build tools/conda.recipe".format(workdir), env=env)


def check_env_var(name):
    """Check if an environment variable is set and non-empty."""
    if name not in os.environ:
        print('The environment variable {} is not set.'.format(name))
    elif os.environ[name] == "":
        print('The environment variable {} is empty.'.format(name))
    else:
        print('The environment variable {} is not empty.'.format(name))


@task(_finalize_config, install_requirements)
def deploy_pypi(ctx):
    """Upload source release to pypi (files must be present)."""
    if ctx.git.tag_stable:
        # Sanity check on user and pass
        check_env_var('TWINE_USERNAME')
        check_env_var('TWINE_PASSWORD')

        # Run twine on every separate package because it can hanle only one
        # at a time.
        for package in ctx.project.packages:
            if package['kind'] == 'py':
                pattern = os.path.join(
                    package['path'], 'dist',
                    '{}-{}.*'.format(package['name'], ctx.git.tag_version)
                )
                filenames = glob(pattern)
                if not filenames:
                    raise Failure("Could not find release for pattern: {}".format(pattern))
                ctx.run("twine upload {}".format(' '.join(filenames)), warn=True)
    else:
        print("No pypi release. This would require a stable version.")


@task(_finalize_config, install_requirements)
def deploy_github(ctx):
    """Upload source release to github (files must be present)."""
    if ctx.git.tag_release:
        # Collect assets
        assets = []
        for package in ctx.project.packages:
            pattern = os.path.join(
                package['path'], 'dist',
                '{}-{}.*'.format(package['name'], ctx.git.tag_version)
            )
            filenames = glob(pattern)
            if not filenames:
                raise Failure("Could not find release for pattern: {}".format(pattern))
            assets.extend(filenames)

        # Sanity check on token
        check_env_var('GITHUB_TOKEN')

        # Upload to github
        ctx.run("hub release create {} {} {} {}".format(
            " ".join("-a {}".format(srf) for srf in assets),
            '' if ctx.git.tag_stable else '-p',
            '-m "Automic release of version {}"'.format(ctx.git.tag_version),
            ctx.git.tag,
        ), warn=True)
    else:
        print("No github release. This would require a tagged commit.")


@task(_finalize_config, install_requirements)
def deploy_conda(ctx):
    """Upload conda release to anaconda (files must be present)."""
    if ctx.git.tag_release:
        # Determine the label
        if ctx.git.tag_stable:
            anaconda_label = "main"
        elif ctx.git.tag_test:
            anaconda_label = "test"
        elif ctx.git.tag_dev:
            anaconda_label = "dev"
        else:
            raise NotImplementedError

        # Determine the assets
        assets = []
        for package in ctx.project.packages:
            pattern = os.path.join(
                ctx.conda.build_path, '*',
                '{}-{}-*.*'.format(package['name'], ctx.git.tag_version)
            )
            filenames = glob(pattern)
            if not filenames:
                raise Failure("Could not find release for pattern: {}".format(pattern))
            assets.extend(filenames)

        # Sanity check on token
        check_env_var('ANACONDA_API_TOKEN')

        # Call the uploader
        ctx.run("anaconda -v upload --force -l {} {}".format(
            anaconda_label, " ".join(assets),
        ), warn=True)
    else:
        print("No conda release. This would require a tagged commit.")


@task(_finalize_config, setup_conda_env)
def nuclear(ctx):
    """USE AT YOUR OWN RISK. Purge conda env and stale files in source tree."""
    # Go back to the base env before nuking the development env.
    conda_deactivate(ctx, iterate=False)
    ctx.run("conda uninstall -n {} --all -y".format(ctx.conda.env_name))
    ctx.run("git clean -fdx")


@task(lint_static, test_inplace, lint_dynamic, build_source, build_conda)
def test(ctx):  # pylint: disable=unused-argument
    """Run all testing tasks, including package builds."""


@task(deploy_pypi, deploy_conda, deploy_github)
def deploy(ctx):  # pylint: disable=unused-argument
    """Run all deployment tasks."""


@task(test, deploy)
def test_and_deploy(ctx):  # pylint: disable=unused-argument
    """Run all tests and deploy."""


@task(default=True)
def robot(ctx):
    """Run test or test_and_deploy, depending on config."""
    from .program import program
    if ctx.deploy:
        program.execute_task(ctx, "test_and_deploy")
    else:
        program.execute_task(ctx, "test")
