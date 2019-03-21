.. _workflow:

Work flow
#########

Roberto divides the continuous integration process into
smaller "tasks", which are listed by ``rob --help`` and which are defined in
``roberto/tasks.py``:

.. include:: tasks_generated.rst.inc

When ``rob`` is executed without arguments, the **quality** task is executed,
which runs all the tests related to the in-placed build. You may provide one or
more task names as positional command-line arguments to change this behavior.
The **robot** task is a more complete test and runs all tasks except for
**nuclear**, so also including the packaging.

The tasks **sanitize-git**, **install-conda**, **setup-conda-env**,
**install-requirements** and **nuclear** are less configurable than the other
tasks. They take care of a proper development environment for the remaining
tasks, except for **nuclear** which does exactly the opposite.

The other tasks are more configurable through ``.roberto.yml``. In this file,
you specify which software packages need to be built and which tools should be
used in each task. More details can be found in :ref:`configuration`.

When Roberto starts, it will also run ``git describe --tags`` to determine the
current version. It is assumed that git tags are complete `semantic version
numbers <https://semver.org>`_. The expected format of a tag is just three
numbers separated by dots, *not* prefixed with a ``v``. Roberto will fail when
the last tag does not follow these conventions. The version information can be
used in all tasks.

For development purposes, it is often sufficient to run ``rob quality`` to
perform all code quality checks or ``rob build-inplace`` to prepare a function
in-place compilation. The latter will also generate a file
``activate-{project.name}-dev-{pinning}.sh``, which can be sourced to load all
the environment variables that will activate the in-place build for further
testing.
