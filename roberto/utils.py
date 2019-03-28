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


from glob import glob
import hashlib
import json
import os
import re
from typing import List

from invoke import Context, Failure


__all__ = [
    'parse_git_describe', 'TagError', 'sanitize_branch',
    'conda_deactivate', 'conda_activate', 'update_env_command',
    'compute_req_hash', 'iter_packages_tools', 'run_all_commands',
    'check_env_var', 'need_deployment', 'write_sha256_sum']


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
        version_info['deploy_label'] = 'main'
    elif version_info['tag_test']:
        version_info['deploy_label'] = "test"
    elif version_info['tag_dev']:
        version_info['deploy_label'] = "dev"
    else:
        version_info['deploy_label'] = None
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


def update_env_command(ctx: Context, command: str) -> None:
    """Update the environment variables with a bash command.

    The command should not produce any output.

    Parameters
    ----------
    ctx
        The context object with which to execute the command.
    command
        A bash command line.

    """
    dump = 'python -c "import os, json; print(json.dumps(dict(os.environ)))"'
    result = ctx.run('{} && {}'.format(command, dump), hide='out')
    newenv = json.loads(result.stdout)
    for key, value in newenv.items():
        os.environ[key] = value
    removed_keys = [key for key in os.environ.keys() if key not in newenv]
    for key in removed_keys:
        del os.environ[key]


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


def compute_req_hash(conda_packages: List[str], recipe_dirs: List[str],
                     pip_packages: List[str]) -> str:
    """Compute a hash from all parameters that affect installed packages.

    Parameters
    ----------
    conda_packages
        A list of packages to be installed with conda.
    recipe_dirs
        The directories with the conda recipes. All files in these directories
        will be loaded and hashed.
    pip_packages:
        A list of packages to be installed with pip.

    Returns
    -------
    hashdigest : str
        The hex digest of the sha256 hash of all development requirements.

    """
    hasher = hashlib.sha256()
    for conda_package in conda_packages:
        hasher.update(conda_package.encode('utf-8'))
    for recipe_dir in recipe_dirs:
        for fn_recipe in glob(os.path.join(recipe_dir, "*")):
            if os.path.isfile(fn_recipe):
                with open(fn_recipe, 'br') as f:
                    hasher.update(f.read())
    for pip_package in pip_packages:
        hasher.update(pip_package.encode('utf-8'))
    return hasher.hexdigest()


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
        with ctx.cd(package.path):
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
