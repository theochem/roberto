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
"""Define the Roberto program."""

from invoke import Collection, Program

from . import tasks
from .config import RobertoConfig

try:
    from .version import __version__
except ImportError:
    __version__ = '0.0.0'


# The program instance provides a `run` method, which is the entrypoint.
program = Program(   # pylint: disable=invalid-name
    config_class=RobertoConfig,
    namespace=Collection.from_module(tasks),
    version=__version__
)
