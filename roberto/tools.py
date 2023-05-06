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
"""Tools contribute functionality to tasks."""


from glob import glob
import json
import os
import urllib.request

from invoke import UnexpectedExit

from .utils import (sanitize_branch, need_deployment,
                    check_env_var, write_sha256_sum)
from .testenvs import append_activate


TOOL_CLASSES = {}
TOOLS = {}


def initialize_tools(tools_config):
    """Build a dictionary with available tools."""
    for tool_name, tool_config in tools_config.items():
        # Extract generic stuff
        cls = tool_config.pop("cls")
        kwargs = dict(tool_config)
        supported_envs = kwargs.pop("supported_envs", ["conda", "venv"])
        requirements = kwargs.pop("requirements", [])
        # Initialize
        tool = TOOL_CLASSES[cls](tool_name, **kwargs)
        # Inject attributes, to keep constructors light. Ugly here, but sweet
        # in code below.
        tool.supported_envs = supported_envs
        tool.requirements = requirements
        # Register
        TOOLS[tool_name] = tool


def execute_tools(ctx, tool_cls):
    """Execute all tools of a given class for all packages."""
    for package in ctx.project.packages:
        for toolname in package.tools:
            tool = TOOLS[toolname]
            if isinstance(tool, tool_cls):
                # Skip tools which are not supported
                print(f"\033[0;94m   TOOL  {tool.name}\033[0;0m")
                if ctx.testenv.use not in tool.supported_envs:
                    print(
                        f"Tool {toolname} skipped due to incompatibility with "
                        f"{ctx.testenv.use}.")
                    continue
                fmtkwargs = {'config': ctx.config, 'package': package}
                tool.execute(ctx, package, fmtkwargs)


class Tool:
    """Tool base class."""

    def __init_subclass__(cls, **kwargs):
        """Register any new sub class."""
        super().__init_subclass__(**kwargs)
        TOOL_CLASSES[cls.__name__] = cls

    def execute(self, ctx, package, fmtkwargs):
        """Execute the tool for a given package.

        Parameters
        ----------
        ctx
            Invoke Context instance.
        package
            Package configuration.
        fmtkwargs
            A dictionary used for formatting arguments.

        """
        raise NotImplementedError

    @staticmethod
    def _run_commands(ctx, package, fmtkwargs, commands):
        """Run all commengs for a given package, performanc variable substitution."""
        with ctx.cd(package.path), ctx.prefix(ctx.testenv.activate):
            for command in commands:
                ctx.run(command.format(**fmtkwargs))


class WriteVersion(Tool):
    """Write version info to a file."""

    def __init__(self, name, template, destination):
        """Initialize a WriteVersion instance.

        Parameters
        ----------
        name
            The name of the tool
        template
            Template for the source code with the version info.
        destination
            The destination to write the file too.

        """
        self.name = name
        self.template = template
        self.destination = destination

    def execute(self, ctx, package, fmtkwargs):
        """Execute the tool for a given package."""
        fn_version = self.destination.format(**fmtkwargs)
        content = self.template.format(**fmtkwargs)
        with open(os.path.join(package.path, fn_version), 'w') as f:
            f.write(content)
        print("Version file written to:", fn_version)


class Lint(Tool):
    """Base class for linters."""

    def __init__(self, name, commands_master, commands_feature):
        """Initialize a Lint instance.

        Parameters
        ----------
        name
            The name of the tool
        commands_master
            Executed when working in the merge_branch, usually master.
        commands_feature
            Executed when working in a feature branch.

        """
        self.name = name
        self.commands_master = commands_master
        self.commands_feature = commands_feature

    def execute(self, ctx, package, fmtkwargs):
        """Execute the tool for a given package."""
        if ctx.absolute:
            on_merge_branch = True
        else:
            result = ctx.run(f'git diff {ctx.git.merge_branch}..HEAD --stat', hide='out')
            on_merge_branch = result.stdout.strip() == ""
        if on_merge_branch:
            self._run_commands(ctx, package, fmtkwargs, self.commands_master)
        else:
            self._run_commands(ctx, package, fmtkwargs, self.commands_feature)


class LintStatic(Lint):
    """Stub for static linters."""


class LintDynamic(Lint):
    """Stub for dynamic linters."""


class BuildInPlace(Tool):
    """Build in-place and check and/or extend environment variables."""

    def __init__(self, name, check_vars, commands, extra_vars):
        """Initialize a BuiltInPlace instance.

        Parameters
        ----------
        name
            The name of the tool
        check_vars
            A list of variable names to print before building, just to
            help detecting issues.
        commands
            Build commands.
        extra_vars
            Additions to environment variables needed after this build.

        """
        self.name = name
        self.check_vars = check_vars
        self.commands = commands
        self.extra_vars = extra_vars

    def _check_vars(self):
        """Print out some variables who might reveal issues."""
        print('Existing variables that could affect the in-place build:')
        for varname in self.check_vars:
            if varname in os.environ:
                print(f'{varname}={os.environ[varname]}')

    def _update_extra_vars(self, ctx, fmtkwargs):
        """Update environment variables after running build commands."""
        for name, value in self.extra_vars.items():
            separator = ":" if "PATH" in name else " "
            value = value.format(**fmtkwargs)
            append_activate(ctx, f'export {name}="${{{name}:+${{{name}}}{separator}}}{value}"')

    def execute(self, ctx, package, fmtkwargs):
        """Execute the tool for a given package."""
        self._check_vars()
        self._run_commands(ctx, package, fmtkwargs, self.commands)
        self._update_extra_vars(ctx, fmtkwargs)


class RunCommands(Tool):
    """Base class for all tools that just execute some commands."""

    def __init__(self, name, commands):
        """Initialize a BuiltInPlace instance.

        Parameters
        ----------
        name
            The name of the tool
        commands
            Commands to run.

        """
        self.name = name
        self.commands = commands

    def execute(self, ctx, package, fmtkwargs):
        """Execute the tool for a given package."""
        self._run_commands(ctx, package, fmtkwargs, self.commands)


class TestInPlace(RunCommands):
    """Stub for in-place testing tools."""


class UploadCoverage(RunCommands):
    """Stub for coverage upload."""


class BuildDocs(RunCommands):
    """Stub for documentation builds."""


class UploadDocs(Tool):
    """Base class for all docu upload tools."""


class UploadDocsGit(UploadDocs):
    """Squash-push documentation to a git branch."""

    def __init__(self, name, docroot, docbranch, docremote, deploy_labels):
        """Initialize an UploadDocsGit instance.

        Parameters
        ----------
        name
            The name of the tool
        docroot
            The subdirectory where the documentation can be found.
        docbranch
            The branch to which the documentation must be pushed.
        docremote
            The remote repository for the documentation.
        deploy_labels
            The kind of releases for which documentation must be uploaded.

        """
        self.name = name
        self.docroot = docroot
        self.docbranch = docbranch
        self.docremote = docremote
        self.deploy_labels = deploy_labels

    def execute(self, ctx, package, fmtkwargs):
        """Execute the tool for a given package."""
        # Try to get a git username and author argument for the doc commit.
        if 'GITHUB_TOKEN' in os.environ:
            # First get user info from the owner of the token
            req = urllib.request.Request('https://api.github.com/user')
            req.add_header('Authorization', f'token {os.environ["GITHUB_TOKEN"]}')
            try:
                with urllib.request.urlopen(req) as f:
                    user_info = json.loads(f.read().decode('utf-8'))['login']
            except urllib.error.HTTPError:
                # The exception may be raised when the token has no permission to
                # access user information.
                user_info = {}
            author_name = user_info.get("name", user_info.get("login", "Roberto"))
            fallback_email = user_info.get("login", "roberto") + "@users.noreply.github.com"
            author_email = user_info.get("email", fallback_email)
            os.environ["GIT_AUTHOR_NAME"] = author_name
            os.environ["GIT_AUTHOR_EMAIL"] = author_email
            os.environ["GIT_COMMITTER_NAME"] = author_name
            os.environ["GIT_COMMITTER_EMAIL"] = author_email

        # Check if deployment is needed with deploy_label.
        prefix = f'{self.name} of {package.dist_name}'
        if not need_deployment(ctx, prefix, False, self.deploy_labels):
            return

        with ctx.cd(package.path):
            # Switch to a docu branch and remove everything that was present in
            # the previous commit. It is assumed that the doc branch is an
            # orphan branch made previously.
            sanitize_branch(ctx, self.docbranch)
            ctx.run(f"git checkout {self.docbranch}")
            ctx.run("git ls-tree HEAD -r --name-only | xargs rm")
            # Copy the documentation to the repo root.
            docroot = self.docroot.format(**fmtkwargs)
            ctx.run(f"GLOBIGNORE='.:..'; cp -rv {docroot}/* .")
            # Add all files
            for root, _dirs, filenames in os.walk(docroot):
                for filename in filenames:
                    fullfn = os.path.join(root, filename)[len(docroot)+1:]
                    ctx.run(f"git add {fullfn}")
            # Commit, push and go back to the original branch
            ctx.run("git commit -a -m 'Automatic documentation update' --amend ")
            ctx.run(f"git checkout {ctx.git.branch}")
            # Push
            if 'GITHUB_TOKEN' in os.environ:
                # Get the remote url
                giturl = ctx.run("git config --get remote.origin.url").stdout.strip()
                # Derive the slug, works for both ssh and https
                slug = '/'.join(giturl.replace(':', '/').split('/')[-2:])
                # Push with github token magic. Taken from
                # https://gist.github.com/willprice/e07efd73fb7f13f917ea
                ctx.run(
                    "git remote add origin-pages "
                    f"https://{os.environ['GITHUB_TOKEN']}@github.com/{slug}",
                    hide=True, echo=False, warn=True
                )
                ctx.run(f"git push --quiet -f origin-pages {self.docbranch}:{self.docbranch}")
            else:
                # Fallback for local doc updates.
                ctx.run(f"git push -f {self.docremote} {self.docbranch}:{self.docbranch}")


class BuildPackage(RunCommands):
    """Stub for building a package."""


class Deploy(Tool):
    """Upload software packages to distribution servers."""

    def __init__(self, name, deploy_vars, include_sha256, noarch_asset_patterns,
                 binary_asset_patterns, deploy_labels, commands):
        """Initialize an UploadDocsGit instance.

        Parameters
        ----------
        name
            The name of the tool
        deploy_vars
            Essential environment variables for deployment. Their presence is
            checked.
        include_sha256
            If True, sha256 checksums are generated for the assets
        noarch_asset_patterns
            Glob pattern for architecture-independent assets.
        binary_asset_patterns
            Glob pattern for architecture-dependent assets.
        deploy_labels
            The kind of releases for which documentation must be uploaded.
        commands
            Bash command to perform the deployment.

        """
        self.name = name
        self.deploy_vars = deploy_vars
        self.include_sha256 = include_sha256
        self.noarch_asset_patterns = noarch_asset_patterns
        self.binary_asset_patterns = binary_asset_patterns
        self.deploy_labels = deploy_labels
        self.commands = commands

    def execute(self, ctx, package, fmtkwargs):
        """Execute the tool for a given package."""
        # Check if and how deployment vars are set.
        for deploy_var in self.deploy_vars:
            print(check_env_var(deploy_var))

        for binary, asset_patterns in [(True, self.binary_asset_patterns),
                                       (False, self.noarch_asset_patterns)]:
            # Fill in config variables in asset_patterns
            asset_patterns = [pattern.format(**fmtkwargs) for pattern in asset_patterns]
            descr = f'{self.name} of {package.dist_name} (binary={binary})'
            print(f"Preparing for {descr}")
            # Collect assets, skipping hash files previously generated.
            assets = []
            for pattern in asset_patterns:
                print("  Searching for", pattern)
                assets.extend([filename for filename in glob(pattern)
                               if not filename.endswith("sha256")])
            if not assets:
                print("No assets found")
                continue
            # Make sha256 checksums
            asset_hashes = [write_sha256_sum(asset) for asset in assets]
            if self.include_sha256:
                assets.extend(asset_hashes)
            # Print final assets
            print(f"Assets for upload: {assets}")
            # Set extra formatting variables.
            fmtkwargs['assets'] = ' '.join(assets)
            # Check if deployment is needed before running commands. This check
            # is maximally postponed to increase the coverage of the code above.
            if need_deployment(ctx, descr, binary, self.deploy_labels):
                try:
                    self._run_commands(ctx, package, fmtkwargs, self.commands)
                except UnexpectedExit:
                    print("\033[0;91m Deployment failed:\033[0;0m", descr)
