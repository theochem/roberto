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

from pytest import raises

from invoke import Context
from invoke.config import DataProxy

from ..utils import (update_env_command, compute_req_hash, parse_git_describe,
                     iter_packages_tools, write_sha256_sum, TagError,
                     check_env_var, need_deployment)


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
    tmpdir = str(tmpdir)  # for python-3.5 compatibility
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


def test_parse_git_describe():
    assert parse_git_describe("1.2.3") == {
        'describe': '1.2.3',
        'tag': '1.2.3',
        'tag_version': '1.2.3',
        'tag_soversion': '1.2',
        'tag_version_major': '1',
        'tag_version_minor': '2',
        'tag_version_patch': '3',
        'tag_version_suffix': '',
        'tag_stable': True,
        'tag_test': False,
        'tag_dev': False,
        'tag_release': True,
        'deploy_label': 'main',
    }
    assert parse_git_describe("0.18.1b1") == {
        'describe': '0.18.1b1',
        'tag': '0.18.1b1',
        'tag_version': '0.18.1b1',
        'tag_soversion': '0.18',
        'tag_version_major': '0',
        'tag_version_minor': '18',
        'tag_version_patch': '1',
        'tag_version_suffix': 'b1',
        'tag_stable': False,
        'tag_test': True,
        'tag_dev': False,
        'tag_release': True,
        'deploy_label': 'test',
    }
    assert parse_git_describe("30.1.2a7") == {
        'describe': '30.1.2a7',
        'tag': '30.1.2a7',
        'tag_version': '30.1.2a7',
        'tag_soversion': '30.1',
        'tag_version_major': '30',
        'tag_version_minor': '1',
        'tag_version_patch': '2',
        'tag_version_suffix': 'a7',
        'tag_stable': False,
        'tag_test': False,
        'tag_dev': True,
        'tag_release': True,
        'deploy_label': 'dev',
    }
    assert parse_git_describe("15.13.11a9-10") == {
        'describe': '15.13.11a9-10',
        'tag': '15.13.11a9',
        'tag_version': '15.13.11a9.post10',
        'tag_soversion': '15.13',
        'tag_version_major': '15',
        'tag_version_minor': '13',
        'tag_version_patch': '11',
        'tag_version_suffix': 'a9.post10',
        'tag_stable': False,
        'tag_test': False,
        'tag_dev': False,
        'tag_release': False,
        'deploy_label': None,
    }
    assert parse_git_describe("1.0.30l") == {
        'describe': '1.0.30l',
        'tag': '1.0.30l',
        'tag_version': '1.0.30l',
        'tag_soversion': '1.0',
        'tag_version_major': '1',
        'tag_version_minor': '0',
        'tag_version_patch': '30',
        'tag_version_suffix': 'l',
        'tag_stable': False,
        'tag_test': False,
        'tag_dev': False,
        'tag_release': False,
        'deploy_label': None,
    }
    assert parse_git_describe("5.0.0") == {
        'describe': '5.0.0',
        'tag': '5.0.0',
        'tag_version': '5.0.0',
        'tag_soversion': '5.0',
        'tag_version_major': '5',
        'tag_version_minor': '0',
        'tag_version_patch': '0',
        'tag_version_suffix': '',
        'tag_stable': True,
        'tag_test': False,
        'tag_dev': False,
        'tag_release': True,
        'deploy_label': 'main',
    }
    assert parse_git_describe("2.7.0-3-foo") == {
        'describe': '2.7.0-3-foo',
        'tag': '2.7.0',
        'tag_version': '2.7.0.post3',
        'tag_soversion': '2.7',
        'tag_version_major': '2',
        'tag_version_minor': '7',
        'tag_version_patch': '0',
        'tag_version_suffix': '.post3',
        'tag_stable': False,
        'tag_test': False,
        'tag_dev': False,
        'tag_release': False,
        'deploy_label': None,
    }
    assert parse_git_describe("0.9.0a2") == {
        'describe': '0.9.0a2',
        'tag': '0.9.0a2',
        'tag_version': '0.9.0a2',
        'tag_soversion': '0.9',
        'tag_version_major': '0',
        'tag_version_minor': '9',
        'tag_version_patch': '0',
        'tag_version_suffix': 'a2',
        'tag_stable': False,
        'tag_test': False,
        'tag_dev': True,
        'tag_release': True,
        'deploy_label': 'dev',
    }
    assert parse_git_describe("0.0.0-666-notag") == {
        'describe': '0.0.0-666-notag',
        'tag': '0.0.0',
        'tag_version': '0.0.0.post666',
        'tag_soversion': '0.0',
        'tag_version_major': '0',
        'tag_version_minor': '0',
        'tag_version_patch': '0',
        'tag_version_suffix': '.post666',
        'tag_stable': False,
        'tag_test': False,
        'tag_dev': False,
        'tag_release': False,
        'deploy_label': None,
    }
    with raises(TagError):
        parse_git_describe('1.2')
    with raises(TagError):
        parse_git_describe('0.0.0.1')
    with raises(TagError):
        parse_git_describe('0.0.foo')
    with raises(TagError):
        parse_git_describe('0.foo.0')
    with raises(TagError):
        parse_git_describe('foo.0.0')


def test_iter_packages_tools():
    pk1 = DataProxy.from_data({"tools": ['a', 'b', 'c']})
    pk2 = DataProxy.from_data({"tools": ['a', 'c']})
    ctx = DataProxy.from_data({
        'project': {'packages': [pk1, pk2]},
        'tools': {
            'a': {'task': 'first', 'option1': 5, 'foo': 'bar'},
            'b': {'task': 'first', },
            'c': {'task': 'second', 'option2': 'egg'},
        },
        'config': None
    })
    ctx.config = ctx
    lfirst = [({'task': 'first', 'option1': 5, 'foo': 'bar', 'name': 'a'},
               pk1, {'config': ctx.config, 'package': pk1}),
              ({'task': 'first', 'name': 'b'},
               pk1, {'config': ctx.config, 'package': pk1}),
              ({'task': 'first', 'option1': 5, 'foo': 'bar', 'name': 'a'},
               pk2, {'config': ctx.config, 'package': pk2})]
    lsecond = [({'task': 'second', 'option2': 'egg', 'name': 'c'},
                pk1, {'config': ctx.config, 'package': pk1}),
               ({'task': 'second', 'option2': 'egg', 'name': 'c'},
                pk2, {'config': ctx.config, 'package': pk2})]
    assert list(iter_packages_tools(ctx, 'first')) == lfirst
    assert list(iter_packages_tools(ctx, 'second')) == lsecond
    assert list(iter_packages_tools(ctx, '__all__')) == [
        lfirst[0], lfirst[1], lsecond[0], lfirst[2], lsecond[1]]


def test_check_env_var():
    # This test assumes the following variable is not defined in the environment.
    name = "d2f400557595b05b39dc6153567b2493c75b132114571b2bdd5d375c88ea732c"
    assert name not in os.environ
    assert check_env_var(name) == 'The environment variable {} is not set.'.format(name)
    os.environ[name] = ''
    assert check_env_var(name) == 'The environment variable {} is empty.'.format(name)
    os.environ[name] = '1'
    assert check_env_var(name) == 'The environment variable {} is not empty.'.format(name)


def test_need_deployment():
    ctx = DataProxy.from_data({
        'deploy_binary': False,
        'deploy_noarch': False,
        'git': {'deploy_label': 'foo'}})
    assert not need_deployment(ctx, '', True, ['foo', 'bar'])
    assert not need_deployment(ctx, '', True, ['egg', 'foo'])
    assert not need_deployment(ctx, '', True, ['bar', 'egg'])
    assert not need_deployment(ctx, '', False, ['foo', 'bar'])
    assert not need_deployment(ctx, '', False, ['egg', 'foo'])
    assert not need_deployment(ctx, '', False, ['bar', 'egg'])
    ctx = DataProxy.from_data({
        'deploy_binary': True,
        'deploy_noarch': False,
        'git': {'deploy_label': 'foo'}})
    assert need_deployment(ctx, '', True, ['foo', 'bar'])
    assert need_deployment(ctx, '', True, ['egg', 'foo'])
    assert not need_deployment(ctx, '', True, ['bar', 'egg'])
    assert not need_deployment(ctx, '', False, ['foo', 'bar'])
    assert not need_deployment(ctx, '', False, ['egg', 'foo'])
    assert not need_deployment(ctx, '', False, ['bar', 'egg'])
    ctx = DataProxy.from_data({
        'deploy_binary': False,
        'deploy_noarch': True,
        'git': {'deploy_label': 'foo'}})
    assert not need_deployment(ctx, '', True, ['foo', 'bar'])
    assert not need_deployment(ctx, '', True, ['egg', 'foo'])
    assert not need_deployment(ctx, '', True, ['bar', 'egg'])
    assert need_deployment(ctx, '', False, ['foo', 'bar'])
    assert need_deployment(ctx, '', False, ['egg', 'foo'])
    assert not need_deployment(ctx, '', False, ['bar', 'egg'])
    ctx = DataProxy.from_data({
        'deploy_binary': True,
        'deploy_noarch': True,
        'git': {'deploy_label': 'foo'}})
    assert need_deployment(ctx, '', True, ['foo', 'bar'])
    assert need_deployment(ctx, '', True, ['egg', 'foo'])
    assert not need_deployment(ctx, '', True, ['bar', 'egg'])
    assert need_deployment(ctx, '', False, ['foo', 'bar'])
    assert need_deployment(ctx, '', False, ['egg', 'foo'])
    assert not need_deployment(ctx, '', False, ['bar', 'egg'])


def test_write_sha256_sum_1(tmpdir):
    fn_test = os.path.join(str(tmpdir), 'a.bin')
    with open(fn_test, "wb") as f:
        f.write(b"foobar\n")
    fn_hash = write_sha256_sum(fn_test)
    assert os.path.isfile(fn_hash)
    with open(fn_hash, 'r') as f:
        assert f.read() == ("aec070645fe53ee3b3763059376134f058cc337247c978add1"
                            "78b6ccdfb0019f  {}\n").format(fn_test)


def test_write_sha256_sum_1000(tmpdir):
    fn_test = os.path.join(str(tmpdir), 'a.bin')
    with open(fn_test, "wb") as f:
        f.write(b"eggspam\n"*1000)
    fn_hash = write_sha256_sum(fn_test)
    assert os.path.isfile(fn_hash)
    os.system("sha256sum {}".format(fn_test))
    with open(fn_hash, 'r') as f:
        assert f.read() == ("e3cf7ad45677ef171d77ec47e2dea492ba32e36b9d9fbcd0c9"
                            "0951421d78bcc9  {}\n").format(fn_test)
