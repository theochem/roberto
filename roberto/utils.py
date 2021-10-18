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
import re
from typing import List

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
        'tag_version': f'{major}.{minor}.{patch}{suffix}',
        'tag_soversion': f'{major}.{minor}',
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
        message = f'Invalid tag: {tag} ({message})'
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
        ctx.run(f"git rev-parse --verify {branch}")
        return
    except Failure:
        print(f"Merge branch \"{branch}\" not found.")

    # Try to create it without connection to origin
    try:
        ctx.run(f"git branch --track {branch} origin/{branch}")
        return
    except Failure:
        print(f"Local copy of remote merge branch \"{branch}\" not found.")

    # Last resort: fetch the merge branch
    ctx.run(f"git fetch origin {branch}:{branch}")


def check_env_var(name: str):
    """Check if an environment variable is set and non-empty.

    Parameters
    ----------
    name
        The environment variable to be checked.

    """
    if name not in os.environ:
        return f'The environment variable {name} is not set.'
    if os.environ[name] == "":
        return f'The environment variable {name} is empty.'
    return f'The environment variable {name} is not empty.'


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
        print(f"{prefix} not requested in configuration. (binary)")
        return False
    if not binary and not ctx.deploy_noarch:
        print(f"{prefix} not requested in configuration. (noarch)")
        return False
    if ctx.git.deploy_label not in deploy_labels:
        print(f"{prefix} skipped, because of deploy label {ctx.git.deploy_label}.")
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
        line = f'{hasher.hexdigest()}  {fn_asset}'
        f.write(line + '\n')
        print(line)
    return fn_sha256
