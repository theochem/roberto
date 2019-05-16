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
"""Tasks in Roberto's workflow.

Due to the decorators, no documentation is generated for this module. Use
``rob --help`` to get an overview of Roberto's task.
"""


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
                    iter_packages_tools, run_all_commands, write_sha256_sum,
                    sanitize_branch, on_merge_branch, need_deployment,
                    check_env_var)


@task()
def sanitize_git(ctx):
    """Fetch the git branch to be merged into, if it is absent."""
    sanitize_branch(ctx, ctx.git.merge_branch)
    print("Current branch:", ctx.git.branch)
    print("Merge branch:", ctx.git.merge_branch)


@task()
def install_conda(ctx):
    """Install miniconda if not present yet. On OSX, also install the SDK."""
    # Prepare the download directory
    dwnldir = ctx.conda.download_dir
    if not os.path.isdir(dwnldir):
        os.makedirs(dwnldir)

    # Install miniconda if needed.
    dest = ctx.conda.base_path
    if not os.path.isdir(os.path.join(dest, 'bin')):
        dwnlconda = os.path.join(dwnldir, 'miniconda.sh')
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

    # Install MacOSX SDK if on OSX
    if platform.system() == 'Darwin':
        optdir = os.path.join(ctx.conda.base_path, 'opt')
        if not os.path.isdir(optdir):
            os.makedirs(optdir)
        sdk = 'MacOSX{}.sdk'.format(ctx.conda.macosx)
        sdkroot = os.path.join(optdir, sdk)
        if not os.path.isdir(sdkroot):
            sdktar = '{}.tar.xz'.format(sdk)
            sdkdwnl = os.path.join(dwnldir, sdktar)
            sdkurl = '{}/{}'.format(ctx.conda.maxosx_sdk_release, sdktar)
            print("Downloading {}".format(sdkurl))
            urllib.request.urlretrieve(sdkurl, sdkdwnl)
            with ctx.cd(optdir):
                ctx.run('tar -xJf {}'.format(sdkdwnl))
        os.environ['MACOSX_DEPLOYMENT_TARGET'] = ctx.conda.macosx
        os.environ['SDKROOT'] = sdkroot
        print('MaxOSX sdk in: {}'.format(sdkroot))
        ctx.run('ls -alh {}'.format(sdkroot))
        ctx.conda.sdkroot = sdkroot


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
        # Append is used to keep defaults at highest priority, essentially
        # to avoid pulling in lots of conda-forge packages, which may be
        # lower quality than their counterparts in the default channels.
        ctx.run("conda config --append channels {}".format(channel))


@task(setup_conda_env)
def install_requirements(ctx):  # pylint: disable=too-many-branches,too-many-statements
    """Install all requirements, including tools used by Roberto."""
    # Collect all parameters determining the install commands, to good
    # approximation and turn them into a hash.
    # Some conda requirements are included by default because they must be present:
    # - conda: to make sure it is always up to date.
    # - conda-build: to have conda-render for getting requirements from recipes.
    # - pip: to install dependencies for tasks with pip, must be recent to work
    #        wel with conda.
    conda_packages = set(["conda", "conda-build", "pip"])
    pip_packages = set([])
    recipe_dirs = []
    tools = [ctx.project]  # Add project as a tool because it also contains requirements.
    for package in ctx.project.packages:
        for toolname in package.tools:
            tools.append(ctx.tools[toolname])
        recipe_dir = os.path.join(package.path, "tools", "conda.recipe")
        if os.path.isdir(recipe_dir):
            recipe_dirs.append(recipe_dir)
        else:
            print("Skipping recipe {}. (directory does not exist)".format(recipe_dir))
    for tool in tools:
        conda_packages.update(tool.get('conda_requirements', []))
        pip_packages.update(tool.get('pip_requirements', []))
    conda_packages = sorted(conda_packages)
    pip_packages = sorted(pip_packages)
    recipe_dirs = sorted(recipe_dirs)
    req_hash = compute_req_hash(conda_packages, recipe_dirs, pip_packages)

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
        print("Starting install+update of packages in conda env.")
        print("To skip install+update: echo {} > {}".format(req_hash, fn_skip))

        # Update conda packages in the base env. Conda packages in the dev env
        # tend to be ignored.
        ctx.run("conda install --update-deps -y -n base -c defaults {}".format(
            " ".join("'{}'".format(conda_package) for conda_package
                     in conda_packages if conda_package.startswith('conda'))))

        # Update and install other requirements for Roberto, in the dev env.
        conda_activate(ctx, ctx.conda.env_name)
        ctx.run("conda install --update-deps -y {}".format(" ".join(
            "'{}'".format(conda_package) for conda_package in conda_packages
            if not conda_package.startswith('conda'))))

        print("Rendering conda package, extracting requirements, which will be installed.")

        # First convert pinning to yaml code
        own_conda_packages = [package.dist_name for package in ctx.project.packages]
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
            requirements = set([])
            for reqtype in 'build', 'host', 'run':
                for requirement in rendered.get("requirements", {}).get(reqtype, []):
                    words = requirement.split()
                    if words[0] not in own_conda_packages:
                        requirements.add(" ".join(words[:2]))
            ctx.run("conda install --update-deps -y {}".format(" ".join(
                "'{}'".format(conda_package) for conda_package in requirements)))

        # Deactivate and activate conda again after installing conda packages,
        # because new environment variables may need to be set by the activation
        # script.
        conda_deactivate(ctx)
        conda_activate(ctx, ctx.conda.env_name)

        # Update and install requirements for Roberto from pip, if any.
        if pip_packages:
            ctx.run("pip install --upgrade {}".format(" ".join(
                "'{}'".format(pip_package) for pip_package in pip_packages)))

        # Update the timestamp on the skip file.
        with open(fn_skip, 'w') as f:
            f.write(req_hash + '\n')


@task()
def write_version(ctx):
    """Derive the version files from ``git describe --tags``."""
    for tool, package, fmtkargs in iter_packages_tools(ctx, "write-version"):
        fn_version = tool.destination.format(**fmtkargs)
        content = tool.template.format(**fmtkargs)
        with open(os.path.join(package.path, fn_version), 'w') as f:
            f.write(content)


@task(install_requirements, sanitize_git, write_version)
def lint_static(ctx):
    """Run static linters."""
    if on_merge_branch(ctx) or ctx.abs:
        run_all_commands(ctx, "lint-static", 'commands_master')
    else:
        run_all_commands(ctx, "lint-static", 'commands_feature')


@task(install_requirements, sanitize_git, write_version)
def build_inplace(ctx):  # pylint: disable=too-many-branches
    """Build software in-place and update environment variables."""
    # This is a fairly complicated process, so yes too many branches. Clarity
    # would not improve by splitting this over multiple functions.

    # Check existing variables
    vars_to_check = set([])
    for tool, _package, _fmtkargs in iter_packages_tools(ctx, "build-inplace"):
        for varname in tool.get('check_vars', []):
            if varname in os.environ:
                vars_to_check.add(varname)
    if vars_to_check:
        print('Pre-existing variables that could affect the in-place build:')
    for varname in sorted(vars_to_check):
        print('{}={}'.format(varname, os.environ[varname]))

    # Update *PATH and *FLAGS environment variables after running build commands
    extra_paths = {}
    extra_flags = {}
    for tool, package, fmtkargs in iter_packages_tools(ctx, "build-inplace"):
        # Run commands
        with ctx.cd(package.path):
            for command in tool.commands:
                ctx.run(command.format(**fmtkargs))
        # Update *PATH variables
        for export_vars, separator in [(tool.get('export_paths', {}), ':'),
                                       (tool.get('export_flags', {}), ' ')]:
            for name, value in export_vars.items():
                value = value.format(**fmtkargs)
                extra_paths.setdefault(name, []).append(value)
                current = os.environ.get(name, "")
                if current != '':
                    current += separator
                os.environ[name] = current + value

    # Write a file, activate-*.sh, which can be sourced to
    # activate the in-place build.
    fn_activate = 'activate-{}.sh'.format(ctx.conda.env_name)
    with open(fn_activate, 'w') as f:
        f.write('[[ -n "${CONDA_PREFIX_1}" ]] && conda deactivate &> /dev/null\n')
        f.write('[[ -n "${CONDA_PREFIX}" ]] && conda deactivate &> /dev/null\n')
        f.write('source "{}/bin/activate"\n'.format(ctx.conda.base_path))
        f.write('conda activate "{}"\n'.format(ctx.conda.env_name))
        for extra_vars, separator in [(extra_paths, ':'), (extra_flags, ' ')]:
            for name, values in extra_vars.items():
                f.write('if [[ -n "${{{0}}}" ]]; then\n'.format(name))
                f.write('  export {0}="{1}{2}${{{0}}}"\n'.format(
                    name, separator.join(values), separator))
                f.write('else\n')
                f.write('  export {0}="{1}"\n'.format(name, separator.join(values)))
                f.write('fi\n')
        f.write('export PROJECT_VERSION="{}"\n'.format(ctx.git.tag_version))
        f.write('export CONDA_BLD_PATH="{}"\n'.format(ctx.conda.build_path))
        if platform.system() == 'Darwin':
            f.write('# MacOSX specific variables\n')
            f.write('export MACOSX_DEPLOYMENT_TARGET="{}"\n'.format(ctx.conda.macosx))
            f.write('export SDKROOT="{}"\n'.format(ctx.conda.sdkroot))
    ctx.run('cat "{}"'.format(fn_activate))


@task(build_inplace)
def test_inplace(ctx):
    """Run tests in-place and upload coverage if requested."""
    # In-place tests need the environment variable changes from the in-place build.
    run_all_commands(ctx, "test-inplace")


@task(test_inplace)
def upload_coverage(ctx):
    """Upload coverage reports, if explicitly enabled in config."""
    if ctx.upload_coverage:
        run_all_commands(ctx, "upload-coverage")
    else:
        print("Coverage upload disabled by configuration.")


@task(build_inplace)
def lint_dynamic(ctx):
    """Run dynamic linters."""
    if on_merge_branch(ctx) or ctx.abs:
        run_all_commands(ctx, "lint-dynamic", 'commands_master')
    else:
        run_all_commands(ctx, "lint-dynamic", 'commands_feature')


@task(install_requirements, build_inplace, write_version)
def build_docs(ctx):
    """Build documentation."""
    run_all_commands(ctx, "build-docs")


@task(install_requirements, build_docs)
def upload_docs_git(ctx):
    """Squash-push documentation to a git branch."""
    # Try to get a git username and author argument for the doc commit.
    if 'GITHUB_TOKEN' in os.environ:
        # First get user info from the owner of the token
        req = urllib.request.Request('https://api.github.com/user')
        req.add_header('Authorization', 'token {}'.format(os.environ['GITHUB_TOKEN']))
        with urllib.request.urlopen(req) as f:
            login = json.loads(f.read().decode('utf-8'))['login']
        ctx.run('git config --global user.email "{}@users.noreply.github.com"'.format(login))
        ctx.run('git config --global user.name "{}"'.format(login))

    for tool, package, fmtkargs in iter_packages_tools(ctx, "upload-docs-git"):
        # Check if deployment is needed with deploy_label.
        prefix = '{} of {}'.format(tool.name, package.dist_name)
        if not need_deployment(ctx, prefix, False, tool.deploy_labels):
            continue

        with ctx.cd(package.path):
            # Switch to a docu branch and remove everything that was present in
            # the previous commit. It is assumed that the doc branch is an
            # orphan branch made previously.
            sanitize_branch(ctx, tool.docbranch)
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
            ctx.run("git commit -a -m 'Automatic documentation update' --amend ")
            ctx.run("git checkout {}".format(ctx.git.branch))
            if 'GITHUB_TOKEN' in os.environ:
                # Get the remote url
                giturl = ctx.run("git config --get remote.origin.url").stdout.strip()
                # Derive the slug, works for both ssh and https
                slug = '/'.join(giturl.replace(':', '/').split('/')[-2:])
                # Push with github token magic. Taken from
                # https://gist.github.com/willprice/e07efd73fb7f13f917ea
                ctx.run("git remote add origin-pages https://{}@github.com/{}".format(
                    os.environ['GITHUB_TOKEN'], slug
                ), hide=True, echo=False, warn=True)
                ctx.run("git push --quiet -f origin-pages {0}:{0}".format(tool.docbranch))
            else:
                # Fallback for local doc updates.
                ctx.run("git push -f {0} {1}:{1}".format(tool.docremote, tool.docbranch))


@task(install_requirements, write_version)
def build_packages(ctx):
    """Build software package(s)."""
    run_all_commands(ctx, "build-packages")


@task(install_requirements, build_packages)
def deploy(ctx):
    """Run all deployment tasks."""
    # Check if and how deployment vars are set.
    checked_deploy_vars = set([])
    for tool, package, fmtkargs in iter_packages_tools(ctx, "deploy"):
        for deploy_var in tool.deploy_vars:
            if deploy_var not in checked_deploy_vars:
                print(check_env_var(deploy_var))
                checked_deploy_vars.add(deploy_var)

    for tool, package, fmtkargs in iter_packages_tools(ctx, "deploy"):
        for binary, asset_patterns in [(True, tool.binary_asset_patterns),
                                       (False, tool.noarch_asset_patterns)]:
            # Fill in config variables in asset_patterns
            asset_patterns = [pattern.format(**fmtkargs) for pattern in asset_patterns]
            descr = '{} of {} (binary={})'.format(tool.name, package.dist_name, binary)
            print("Preparing for {}".format(descr))
            # Collect assets, skipping hash files previously generated.
            assets = []
            for pattern in asset_patterns:
                assets.extend([filename for filename in glob(pattern)
                               if not filename.endswith("sha256")])
            if not assets:
                print("No assets found")
                continue
            # Make sha256 checksums
            asset_hashes = [write_sha256_sum(asset) for asset in assets]
            if tool.get('include_sha256', False):
                assets.extend(asset_hashes)
            # Print final assets
            print("Assets for upload: {}".format(assets))
            # Set extra formatting variables.
            fmtkargs.update({
                'assets': ' '.join(assets),
                'hub_assets': ' '.join('-a {}'.format(asset) for asset in assets),
            })
            # Check if deployment is needed before running commands. This check
            # is maximally postponed to increase the coverage of the code above.
            if need_deployment(ctx, descr, binary, tool.deploy_labels):
                # Run deployment commands.
                for command in tool.commands:
                    ctx.run(command.format(**fmtkargs), warn=True)


@task(setup_conda_env)
def nuclear(ctx):
    """Purge the conda environment and stale source files. USE AT YOUR OWN RISK."""
    # Go back to the base env before nuking the development env.
    conda_deactivate(ctx, iterate=False)
    ctx.run("conda uninstall -n {} --all -y".format(ctx.conda.env_name))
    ctx.run("git clean -fdX")


@task(lint_static, test_inplace, upload_coverage, lint_dynamic, build_docs, default=True)
def quality(ctx):  # pylint: disable=unused-argument
    """Run all quality assurance tasks: linting and in-place testing."""


@task(quality, upload_docs_git, deploy)
def robot(ctx):  # pylint: disable=unused-argument
    """Run all tasks, except nuclear."""
