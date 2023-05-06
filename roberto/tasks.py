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


from functools import wraps

from invoke import task

from .requirements import install_requirements_conda, install_requirements_pip
from .utils import sanitize_branch
from .tools import (execute_tools, WriteVersion, LintStatic, BuildInPlace,
                    TestInPlace, UploadCoverage, LintDynamic, BuildDocs,
                    UploadDocs, BuildPackage, Deploy)


TASK_HEADER = """\
\033[0;94m +-{line}-+\033[0;0m
\033[0;94m | TASK  {task} |\033[0;0m
\033[0;94m +-{line}-+\033[0;0m\
"""


def with_stdout_header(f):
    """Print a header for a task."""
    @wraps(f)
    def wrapper(ctx, *args, **kwargs):
        name = f.__name__
        print(TASK_HEADER.format(task=name, line="-"*(len(name)+6)))
        return f(ctx, *args, **kwargs)
    return wrapper


@task()
@with_stdout_header
def sanitize_git(ctx):
    """Fetch the git branch to be merged into, if it is absent."""
    sanitize_branch(ctx, ctx.git.merge_branch)
    print("Current branch:", ctx.git.branch)
    print("Merge branch:", ctx.git.merge_branch)


@task()
@with_stdout_header
def write_version(ctx):
    """Derive the version files from ``git describe --tags``."""
    execute_tools(ctx, WriteVersion)


@task()
@with_stdout_header
def setup_testenv(ctx):
    """Set up a testing environment."""
    ctx.testenv.setup(ctx)


@task(setup_testenv)
@with_stdout_header
def install_requirements(ctx):
    """Install all requirements, including tools used by Roberto."""
    if ctx.package_manager == "conda":
        install_requirements_conda(ctx)
    elif ctx.package_manager == "pip":
        install_requirements_pip(ctx)
    else:
        raise NotImplementedError


@task(install_requirements, sanitize_git, write_version)
@with_stdout_header
def lint_static(ctx):
    """Run static linters."""
    execute_tools(ctx, LintStatic)


@task(install_requirements, sanitize_git, write_version)
@with_stdout_header
def build_inplace(ctx):  # pylint: disable=too-many-branches
    """Build software in-place and update environment variables."""
    execute_tools(ctx, BuildInPlace)


@task(build_inplace)
@with_stdout_header
def test_inplace(ctx):
    """Run tests in-place."""
    execute_tools(ctx, TestInPlace)


@task(test_inplace)
@with_stdout_header
def upload_coverage(ctx):
    """Upload coverage reports, if explicitly enabled in config."""
    if ctx.upload_coverage:
        execute_tools(ctx, UploadCoverage)
    else:
        print("Coverage upload disabled by configuration.")


@task(build_inplace)
@with_stdout_header
def lint_dynamic(ctx):
    """Run dynamic linters."""
    execute_tools(ctx, LintDynamic)


@task(install_requirements, build_inplace, write_version)
@with_stdout_header
def build_docs(ctx):
    """Build documentation."""
    execute_tools(ctx, BuildDocs)


@task(install_requirements, build_docs)
@with_stdout_header
def upload_docs(ctx):
    """Upload documentation."""
    execute_tools(ctx, UploadDocs)


@task(install_requirements, write_version)
@with_stdout_header
def build_packages(ctx):
    """Build software package(s)."""
    execute_tools(ctx, BuildPackage)


@task(install_requirements, build_packages)
@with_stdout_header
def deploy(ctx):
    """Run all deployment tasks."""
    execute_tools(ctx, Deploy)


@task()
@with_stdout_header
def nuke_testenv(ctx):
    """Purge the test environment and stale source files. USE AT YOUR OWN RISK."""
    ctx.testenv.nuke(ctx)


@task(lint_static, test_inplace, upload_coverage, lint_dynamic, build_docs, default=True)
def quality(ctx):  # pylint: disable=unused-argument
    """Run all quality assurance tasks: linting and in-place testing."""
    print("\033[0;92m All QA checks passed!\033[0;0m")


@task(quality, upload_docs, deploy)
def robot(ctx):  # pylint: disable=unused-argument
    """Run all tasks, except nuke_virtual_env."""
    print("\033[0;92m All tasks completed!\033[0;0m")
