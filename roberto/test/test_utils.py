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
"""Unit tests for the utilities defined in Roberto's tasks."""

import os

from invoke import Context

from ..utils import update_env_command, compute_req_hash, append_path


def test_update_env_command():
    context = Context()
    context.config.run.in_stream = False
    varname = "SDAFSDFADGQERGADFGASDFADFADFASDGQ"
    assert varname not in os.environ
    update_env_command(context, "export {}=4".format(varname))
    assert os.environ[varname] == "4"
    update_env_command(context, "unset {}".format(varname))
    assert varname not in os.environ


def test_req_hash(tmpdir):
    conda_packages = ["conda-build", "anaconda-client", "conda-verify"]
    pip_packages = ["codecov"]
    # Use a fake but safe recipe dir
    with open(os.path.join(tmpdir, "foo"), "w") as f:
        f.write("bar")
    recipe_dirs = [tmpdir]
    hash1 = compute_req_hash(conda_packages, recipe_dirs, pip_packages)
    assert len(hash1) == 64
    pip_packages.append("1")
    hash2 = compute_req_hash(conda_packages, recipe_dirs, pip_packages)
    assert len(hash2) == 64
    assert hash1 != hash2
    pip_packages.append("aaa")
    hash3 = compute_req_hash(conda_packages, recipe_dirs, pip_packages)
    assert len(hash3) == 64
    assert hash1 != hash3
    assert hash2 != hash3
    with open(os.path.join(tmpdir, "egg"), "w") as f:
        f.write("spam")
    hash4 = compute_req_hash(conda_packages, recipe_dirs, pip_packages)
    assert len(hash4) == 64
    assert hash1 != hash4
    assert hash2 != hash4
    assert hash3 != hash4
    os.mkdir(os.path.join(tmpdir, "subdir"))
    hash5 = compute_req_hash(conda_packages, recipe_dirs, pip_packages)
    assert len(hash5) == 64
    assert hash4 == hash5


def test_append_path():
    env = {}
    append_path(env, "T", "aaa")
    assert len(env) == 1
    assert env["T"] == "aaa"
    append_path(env, "T", "bbb")
    assert len(env) == 1
    assert env["T"] == "aaa:bbb"
    append_path(env, "S", "ccc")
    assert len(env) == 2
    assert env["T"] == "aaa:bbb"
    assert env["S"] == "ccc"
