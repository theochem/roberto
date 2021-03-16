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
import urllib.request

from invoke import task, UnexpectedExit

from .conda import install_requirements_conda, nuclear_conda
from .utils import (iter_packages_tools, run_all_commands, write_sha256_sum,
                    sanitize_branch, on_merge_branch, need_deployment,
                    check_env_var)
from .venv import install_requirements_venv, nuclear_venv


@task()
def sanitize_git(ctx):
    """Fetch the git branch to be merged into, if it is absent."""
    sanitize_branch(ctx, ctx.git.merge_branch)
    print("Current branch:", ctx.git.branch)
    print("Merge branch:", ctx.git.merge_branch)


@task()
def install_requirements(ctx):  # pylint: disable=too-many-branches,too-many-statements
    """Install all requirements, including tools used by Roberto."""
    if ctx.testenv.use == "conda":
        install_requirements_conda(ctx)
    elif ctx.testenv.use == "venv":
        install_requirements_venv(ctx)
    else:
        raise NotImplementedError


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
    if on_merge_branch(ctx) or ctx.absolute:
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
        if ctx.testenv.from_scratch:
            if ctx.testenv.use == "conda":
                f.write('[[ -n "${CONDA_PREFIX_1}" ]] && conda deactivate &> /dev/null\n')
                f.write('[[ -n "${CONDA_PREFIX}" ]] && conda deactivate &> /dev/null\n')
                f.write('source "{}/bin/activate"\n'.format(ctx.conda.base_path))
                f.write('conda activate "{}"\n'.format(ctx.conda.env_name))
                f.write('export CONDA_BLD_PATH="{}"\n'.format(ctx.conda.build_path))
            elif ctx.testenv.use == "venv":
                f.write('[[ -n "${VIRTUAL_ENV}" ]] && deactivate &> /dev/null\n')
                f.write('source "{}/bin/activate"\n'.format(ctx.venv.base_path))
            else:
                raise NotImplementedError
        for extra_vars, separator in [(extra_paths, ':'), (extra_flags, ' ')]:
            for name, values in extra_vars.items():
                f.write('if [[ -n "${{{0}}}" ]]; then\n'.format(name))
                f.write('  export {0}="{1}{2}${{{0}}}"\n'.format(
                    name, separator.join(values), separator))
                f.write('else\n')
                f.write('  export {0}="{1}"\n'.format(name, separator.join(values)))
                f.write('fi\n')
        f.write('export PROJECT_VERSION="{}"\n'.format(ctx.git.tag_version))
        if platform.system() == 'Darwin' and ctx.macosx.install_sdk:
            f.write('# MacOSX specific variables\n')
            f.write('export MACOSX_DEPLOYMENT_TARGET="{}"\n'.format(ctx.macosx.release))
            f.write('export SDKROOT="{}"\n'.format(ctx.macosx.sdk_root))
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
    if on_merge_branch(ctx) or ctx.absolute:
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
                try:
                    # Run deployment commands.
                    for command in tool.commands:
                        ctx.run(command.format(**fmtkargs))
                except UnexpectedExit:
                    print("Deployment failed:", descr)


@task()
def nuclear(ctx):
    """Purge the environment and stale source files. USE AT YOUR OWN RISK."""
    if ctx.testenv.use == "conda":
        nuclear_conda(ctx)
    elif ctx.testenv.use == "venv":
        nuclear_venv(ctx)
    else:
        raise NotImplementedError


@task(lint_static, test_inplace, upload_coverage, lint_dynamic, build_docs, default=True)
def quality(ctx):  # pylint: disable=unused-argument
    """Run all quality assurance tasks: linting and in-place testing."""


@task(quality, upload_docs_git, deploy)
def robot(ctx):  # pylint: disable=unused-argument
    """Run all tasks, except nuclear."""
