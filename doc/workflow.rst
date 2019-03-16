.. _workflow:

Work flow
#########

Roberto divides the development, testing, packaging and deployment process into
smaller "tasks", which are listed by `rob --help`. All tasks are defined
in `roberto/tasks.py` and the following lines from this file show all tasks,
what they are intended for, and how they depend on each other. (The dependencies
of each task are arguments to the `@task` decorator.)

TODO: grep for essential lines from task.py, including dependencies and
docstrings. We need the output of:

``grep '^@task' tasks.py -A 2 -B 1 | grep -v -- --``

The tasks `sanitize-git`, `install-conda`, `setup-conda-env`,
`install-requirements` and `nuclear` are rather hard-coded and make sure a
proper development environment is set up for the remaining tasks. In case of
`nuclear`, the purpose is exactly the opposite, to tear down the development
environment and to clean the repository.

The other tasks are controlled more by the tools specified in the configuration
file `.roberto.yml`, see :ref:`configuration`. Without this configuration, such
tasks won't do much.

When `rob` is executed without arguments, the `robot` task is executed, which
runs everything except nuclear. Alternatiely, you may provide one or more tasks
as positional command-line arguments.
