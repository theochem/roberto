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
"""Utilities used by tasks in Roberto's workflow."""


import hashlib
import os
import platform
import re
import time
import urllib.request
from typing import List, Set

from invoke import Context, Failure


def parse_git_describe(git_describe: str) -> dict:
    """Parse the output of ``git describe --tags``.

    Parameters
    ----------
    git_describe
        The output of git describe

    Returns
    -------
    version_info: dict
        A dictionary with version information.

    """
    # Split the input string into basic parts.
    git_describe = git_describe.strip()
    version_words = git_describe.split('-')
    tag = version_words[0]
    version_parts = tag.split('.')
    if len(version_parts) != 3:
        raise TagError('A version tag must at least contain two dots.', tag)

    # If the last version part has a non numeric suffix,
    # it needs to be taken out.
    match = re.fullmatch(r'(\d+)(.*)', version_parts[-1])
    if match is None:
        raise TagError('The patch version must start with a number.', tag)
    version_parts[-1] = match.group(1)
    suffix = match.group(2)

    # Define various meaningful pieces
    major, minor, patch = version_parts
    if not minor.isnumeric():
        raise TagError('The minor version must be numeric.', tag)
    if not major.isnumeric():
        raise TagError('The major version must be numeric.', tag)
    if len(version_words) > 1:
        suffix += '.post' + version_words[1]

    # Construct results
    version_info = {
        'describe': git_describe,
        'tag': tag,
        'tag_version': '{}.{}.{}{}'.format(major, minor, patch, suffix),
        'tag_soversion': '{}.{}'.format(major, minor),
        'tag_version_major': major,
        'tag_version_minor': minor,
        'tag_version_patch': patch,
        'tag_version_suffix': suffix,
        'tag_stable': len(suffix) == 0,
        'tag_test': re.fullmatch(r'b\d+', suffix) is not None,
        'tag_dev': re.fullmatch(r'a\d+', suffix) is not None,
    }
    version_info['tag_release'] = (
        version_info['tag_stable']
        or version_info['tag_test']
        or version_info['tag_dev'])
    if version_info['tag_stable']:
        version_info['deploy_label'] = "main"
        version_info['dev_classifier'] = 'Development Status :: 5 - Production/Stable'
    elif version_info['tag_test']:
        version_info['deploy_label'] = "test"
        version_info['dev_classifier'] = 'Development Status :: 4 - Beta'
    elif version_info['tag_dev']:
        version_info['deploy_label'] = "dev"
        version_info['dev_classifier'] = 'Development Status :: 3 - Alpha'
    else:
        # Non-release tag or no tag.
        version_info['deploy_label'] = None
        version_info['dev_classifier'] = 'Development Status :: 2 - Pre-Alpha'
    return version_info


class TagError(Exception):
    """An exception raised when a version tag is invalid."""

    def __init__(self, message: str, tag: str):
        """Initialize an TagError.

        Parameters
        ----------
        message
            Describe the error.
        tag
            The tag having the problem, which will be added to the error
            message.

        """
        message = 'Invalid tag: {} ({})'.format(tag, message)
        super().__init__(message)


def sanitize_branch(ctx: Context, branch: str):
    """Attempt to fix the presence of a branch.

    The branch is checked with rev-parse. If not present, try to set it to
    origin/branch. If that does not work, try to fetch it.

    Parameters
    ----------
    ctx
        A invoke.Context instance.
    branch
        The branch to resurrect.

    """
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


def on_merge_branch(ctx: Context):
    """Return True if we are currently on the merge branch."""
    result = ctx.run('git diff {}..HEAD --stat'.format(ctx.git.merge_branch), hide='out')
    return result.stdout.strip() == ""


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
                    print("To force install+update: rm {}".format(fn_skip))
                    return False
    print("Starting install+update of requirements.")
    print("To skip install+update: echo {} > {}".format(req_hash, fn_skip))
    return True


def install_macosx_sdk(ctx: Context, base_path: str):
    """Install MacOSX SDK if on OSX if needed.

    Parameters
    ----------
    ctx
        The context object with which to execute the commands.
    base_path
        SDK Install location.

    """
    if platform.system() == 'Darwin' and ctx.macosx.install_sdk:
        optdir = os.path.join(base_path, 'opt')
        if not os.path.isdir(optdir):
            os.makedirs(optdir)
        sdk = 'MacOSX{}.sdk'.format(ctx.macosx.release)
        sdk_root = os.path.join(optdir, sdk)
        if not os.path.isdir(sdk_root):
            sdk_tar = '{}.tar.xz'.format(sdk)
            sdk_dwnl = os.path.join(ctx.download_dir, sdk_tar)
            sdk_url = '{}/{}'.format(ctx.maxosx.sdk_release, sdk_tar)
            print("Downloading {}".format(sdk_url))
            urllib.request.urlretrieve(sdk_url, sdk_dwnl)
            with ctx.cd(optdir):
                ctx.run('tar -xJf {}'.format(sdk_dwnl))
        os.environ['MACOSX_DEPLOYMENT_TARGET'] = ctx.macosx.release
        os.environ['SDKROOT'] = sdk_root
        print('MaxOSX sdk in: {}'.format(sdk_root))
        ctx.run('ls -alh {}'.format(sdk_root))
        ctx.macosx.sdk_root = sdk_root


def iter_packages_tools(ctx: Context, task: str):
    """Iterate over all tools for all packages.

    Parameters
    ----------
    ctx
        The context object with which to execute the commands.
    task
        A task name, defined by Roberto's (main) tasks.

    Yields
    ------
    tool : DataProxy
        The part of the config file describing the tool, with tool.name added.
    package: DataProxy
        The part of the config file describing the package.
    fmtkargs: dict
        Formatting arguments for strings from the config file.

    """
    for package in ctx.project.packages:
        for toolname in package.tools:
            tool = ctx.tools[toolname]
            tool.name = toolname
            if task in ('__all__', tool.task):
                # Skip tools which are not supported
                if "testenv" in tool and ctx.testenv.use not in tool.testenv:
                    print(
                        f"Tool {toolname} skipped due to incompatibility with "
                        f"testenv {ctx.testenv.use}.")
                    continue
                fmtkargs = {'config': ctx.config, 'package': package}
                yield tool, package, fmtkargs


def run_all_commands(ctx: Context, task: str, commands_name: str = 'commands'):
    """Run a specific subtask from a list of tools for all packages.

    Parameters
    ----------
    ctx
        The context object with which to execute the commands.
    task
        A subtask, defined by Roberto's (main) tasks.
    commands_name
        The name of the commands field in the tool to use.

    """
    for tool, package, fmtkargs in iter_packages_tools(ctx, task):
        with ctx.cd(package.path), ctx.prefix(ctx.testenv.activate):
            commands = tool.get(commands_name, [])
            for command in commands:
                ctx.run(command.format(**fmtkargs))


def check_env_var(name: str):
    """Check if an environment variable is set and non-empty.

    Parameters
    ----------
    name
        The environment variable to be checked.

    """
    if name not in os.environ:
        return 'The environment variable {} is not set.'.format(name)
    if os.environ[name] == "":
        return 'The environment variable {} is empty.'.format(name)
    return 'The environment variable {} is not empty.'.format(name)


def need_deployment(ctx: Context, prefix: str, binary: bool, deploy_labels: List[str]) -> bool:
    """Return True if deployment is needed.

    Parameters
    ----------
    ctx
        A invoke.Context instance.
    prefix
        The type of deployment, used for message printed to stdout.
    binary
        Whether or not a binary is being deployment. If binary, it may be of
        interest to deploy for different architectures, which is controlled by
        a config.deploy_binary, intead of config.deploy_source.
    deploy_labels
        A list of valid deploy labels for this release. If the current deploy
        label matches any of the ones in the list, deployment is needed.

    """
    if binary and not ctx.deploy_binary:
        print("{} not requested in configuration. (binary)".format(prefix))
        return False
    if not binary and not ctx.deploy_noarch:
        print("{} not requested in configuration. (noarch)".format(prefix))
        return False
    if ctx.git.deploy_label not in deploy_labels:
        print("{} skipped, because of deploy label {}.".format(prefix, ctx.git.deploy_label))
        return False
    return True


def write_sha256_sum(fn_asset: str) -> str:
    """Make a sha256 checksum file, print it and return the checksum filename.

    Parameters
    ----------
    fn_asset
        The file of which the hash will be computed.

    Returns
    -------
    fn_asset_hash : str
        The filename of the file containing the hash.

    """
    hasher = hashlib.sha256()
    with open(fn_asset, 'br') as f:
        for chunck in iter(lambda: f.read(4096), b""):
            hasher.update(chunck)
    fn_sha256 = fn_asset + '.sha256'
    with open(fn_sha256, 'w') as f:
        line = '{}  {}'.format(hasher.hexdigest(), fn_asset)
        f.write(line + '\n')
        print(line)
    return fn_sha256
