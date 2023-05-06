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
"""Unit tests roberto.requirements."""

import os

from ..requirements import compute_req_hash


def test_req_hash(tmpdir):
    req_items = set(["conda-build", "anaconda-client", "conda-verify"])
    # Use a fake but safe recipe dir
    fn_foo = os.path.join(tmpdir, "foo")
    with open(fn_foo, "w") as f:
        f.write("bar")
    req_fns = set([fn_foo])
    hash1 = compute_req_hash(req_items, req_fns)
    assert len(hash1) == 64
    req_items.add("1")
    hash2 = compute_req_hash(req_items, req_fns)
    assert len(hash2) == 64
    assert hash1 != hash2
    req_items.add("aaa")
    hash3 = compute_req_hash(req_items, req_fns)
    assert len(hash3) == 64
    assert hash1 != hash3
    assert hash2 != hash3
    fn_egg = os.path.join(tmpdir, "egg")
    with open(fn_egg, "w") as f:
        f.write("spam")
    req_fns.add(fn_egg)
    hash4 = compute_req_hash(req_items, req_fns)
    assert len(hash4) == 64
    assert hash1 != hash4
    assert hash2 != hash4
    assert hash3 != hash4
