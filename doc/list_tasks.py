#!/usr/bin/env python3
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
"""Generate a list of all tasks in Roberto in rst format."""

from collections import namedtuple

from invoke.tasks import Task
import roberto.tasks


TaskDescription = namedtuple("TaskDescription", ["prenames", "doc"])


def main():
    """Generate a human-readable list of Roberto tasks."""
    taskmap = {}

    # Extract all tasks
    for name in dir(roberto.tasks):
        task = roberto.tasks.__dict__[name]
        if isinstance(task, Task):
            taskmap[task.name.replace('_', '-')] = TaskDescription(
                [pretask.name.replace('_', '-') for pretask in task.pre],
                task.__doc__.strip().split("\n")
            )

    # Sort them by their dependencies
    todo_names = sorted(taskmap)
    done_names = []
    while todo_names:
        name = todo_names.pop(0)
        accept = True
        for prename in taskmap[name].prenames:
            if prename not in done_names:
                accept = False
                break
        if accept:
            done_names.append(name)
        else:
            todo_names.append(name)

    # Print tasks in rst format
    with open("tasks_generated.rst.inc", "w") as f:
        for name in done_names:
            tdr = taskmap[name]
            endsentence = tdr.doc[0][0].lower() + tdr.doc[0][1:]
            if tdr.prenames:
                fmt_dependencies = ", ".join(f"**{name}**" for name in tdr.prenames)
                f.write(f"- **{name}** depends on {fmt_dependencies} and will {endsentence}\n")
            else:
                f.write("- **{name}** will {endsentence}\n")


if __name__ == '__main__':
    main()
