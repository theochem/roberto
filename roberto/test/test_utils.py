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
"""Unit tests Roberto.utils."""

import os

import pytest

from invoke.config import DataProxy

from ..utils import (parse_git_describe, write_sha256_sum, TagError,
                     check_env_var, need_deployment)


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
        'dev_classifier': 'Development Status :: 5 - Production/Stable',
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
        'dev_classifier': 'Development Status :: 4 - Beta',
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
        'dev_classifier': 'Development Status :: 3 - Alpha',
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
        'dev_classifier': 'Development Status :: 2 - Pre-Alpha',
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
        'dev_classifier': 'Development Status :: 2 - Pre-Alpha',
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
        'dev_classifier': 'Development Status :: 5 - Production/Stable',
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
        'dev_classifier': 'Development Status :: 2 - Pre-Alpha',
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
        'dev_classifier': 'Development Status :: 3 - Alpha',
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
        'dev_classifier': 'Development Status :: 2 - Pre-Alpha'
    }
    with pytest.raises(TagError):
        parse_git_describe('1.2')
    with pytest.raises(TagError):
        parse_git_describe('0.0.0.1')
    with pytest.raises(TagError):
        parse_git_describe('0.0.foo')
    with pytest.raises(TagError):
        parse_git_describe('0.foo.0')
    with pytest.raises(TagError):
        parse_git_describe('foo.0.0')


def test_check_env_var():
    # This test assumes the following variable is not defined in the environment.
    name = "d2f400557595b05b39dc6153567b2493c75b132114571b2bdd5d375c88ea732c"
    assert name not in os.environ
    assert check_env_var(name) == f'The environment variable {name} is not set.'
    os.environ[name] = ''
    assert check_env_var(name) == f'The environment variable {name} is empty.'
    os.environ[name] = '1'
    assert check_env_var(name) == f'The environment variable {name} is not empty.'


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
                            f"78b6ccdfb0019f  {fn_test}\n")


def test_write_sha256_sum_1000(tmpdir):
    fn_test = os.path.join(str(tmpdir), 'a.bin')
    with open(fn_test, "wb") as f:
        f.write(b"eggspam\n"*1000)
    fn_hash = write_sha256_sum(fn_test)
    assert os.path.isfile(fn_hash)
    os.system(f"sha256sum {fn_test}")
    with open(fn_hash, 'r') as f:
        assert f.read() == ("e3cf7ad45677ef171d77ec47e2dea492ba32e36b9d9fbcd0c9"
                            f"0951421d78bcc9  {fn_test}\n")
