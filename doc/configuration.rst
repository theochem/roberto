.. _configuration:

Configuration
#############

Roberto uses invoke, amongst other things, to parse its configuration files. For
most projectes, it is sufficient to just write a ``.roberto.yaml`` file in the
root of the project's source tree. In some cases, environment variables,
prefixed with ``ROBERTO_`` can be useful to extend or override the settings in
the configuration file. All your settings extend the
`default configuration file <https://github.com/theochem/roberto/blob/master/roberto/default_config.yaml>`_.

Invoke also offers other mechanisms to modify Roberto's configuration, which is
explained here: http://docs.pyinvoke.org/


Basic configuration
===================

The configuration file must at least contain the following:

.. code-block:: yaml

  project:
    # 'name' is used for package and directory names.
    name: your_project_name
    # List one or more software packages below.
    packages:
        # 'conda_nane' is required and there is no default value.
        # It must be unique in case of multiple package.
      - conda_name: 'conda_package_name'
        # An optional package name, must not be unique.
        # The default is the project name.
        name: 'package_name'
        # An optional subdirectory of the source tree.
        # Defaults to '.'
        path: .
        # List one or more tools below.
        # Using all tools is probably not sensible
        # because some are geared towards CMake
        # packages, while others are only
        # useful for Python packages.
        tools:
          - write-py-version
          - cardboardlint-static
          # ...
      # You can add multiple packages.
      - conda_name: '...'
        # ...

Each tool of each package will be executed in one task in the overall work
flow. See section :ref:`workflow` for a more detailed description. A complete
list of the built-in tools can be found in the
`default configuration file <https://github.com/theochem/roberto/blob/master/roberto/default_config.yaml>`_.

Other sections can be added as well, e.g. to define new tools as explained
below, or to change other settings from
`default configuration file <https://github.com/theochem/roberto/blob/master/roberto/default_config.yaml>`_.


Python example
==============

This is a basic configuration for a Python project, e.g. called `spammer`:

.. code-block:: yaml
    :caption: .roberto.yaml

    project:
      name: spammer
      packages:
        - conda_name: spammer
          tools:
            - write-py-version
            - cardboardlint-static
            - cardboardlint-dynamic
            - pytest
            - build-sphinx-doc
            - build-py-source
            - build-conda
            - deploy-pypi
            - deploy-conda
            - deploy-github
            - upload-docs-gh

This configuration assumes you have at least the following files in your Git
repository:

.. code-block:: bash

    .cardboardlint.yaml
    setup.py
    spammer/__init__.py
    tools/conda/meta.yaml


CMake and Python wrapper example
================================

A basic configuration for a CMake (e.g. C++) project and a Python wrapper, here
called `bummer` can be done as follows:

.. code-block:: yaml
    :caption: .roberto.yaml

    project:
      name: bummer
      packages:
        - conda_name: bummer
          tools:
            - write-cmake-version
            - cardboardlint-static
            - cardboardlint-dynamic
            - build-cmake-inplace
            - maketest
            - build-cmake-source
            - build-conda
            - deploy-conda
            - deploy-github
        - conda_name: python-bummer
          path: python-bummer
          tools:
            - write-py-version
            - cardboardlint-static
            - cardboardlint-dynamic
            - build-py-inplace
            - pytest
            - build-py-source
            - build-conda
            - deploy-conda
            - deploy-github


This configuration assumes you have at least the following files in your Git
repository:

.. code-block:: bash

    .cardboardlint.yaml
    CMakeLists.txt
    tools/conda/meta.yaml
    python-bummer/setup.py
    python-bummer/bummer/__init__.py
    python-bummer/tools/conda/meta.yaml


Working with git tag for versions
=================================

When Roberto starts, it will run ``git describe --tags`` to determine the
version number and add this version information in various forms in the ``git``
section of the
`default configuration file <https://github.com/theochem/roberto/blob/master/roberto/default_config.yaml>`.
From there, all tasks
can access version information when they need it. Below the most important of
these tasks are discussed.

Python projects
---------------

Us the tool ``write-py-version`` to make sure the file ``version.py`` exists
before ``setup.py`` is called.

In ``setup.py``, use the following code to derive the version instead of
hard-coding it:

  .. code-block:: python

    import os

    NAME = 'spammer'  # <-- change this name.

    def get_version():
        """Read __version__ from version.py, with exec to avoid importing it."""
        try:
            with open(os.path.join(NAME, 'version.py'), 'r') as f:
                myglobals = {}
                # pylint: disable=exec-used
                exec(f.read(), myglobals)
            return myglobals['__version__']
        except IOError:
            return "0.0.0.post0"

    setup(
        name=NAME,
        version=get_version(),
        package_dir={NAME: NAME},
        packages=[NAME, NAME + '.test'],
        # ...
    )

This is an ugly trick but for a good reason. It is needed because (in
general) one not assume the package can be imported before ``setup.py`` has been
executed.

When the Sphinx documentation is build, one can assume an in-place built has
succeeded and one can simply import the version in ``doc/conf.py`` as follows:

  .. code-block:: python

    from spammer.version import __version__  # <-- change name spammer

    # ...

    release = __version__
    version = '.'.join(release.split('.')[:2])


CMake projects
--------------

With the tool ``write-cmake-version``, one can generate a file
``CMakeListsVersion.txt.in``, which can be included from the main
``CMakeLists.txt`` file as follows:

  .. code-block:: cmake

    include(CMakeListsVersion.txt.in)


Conda package specifications (``meta.yaml``)
--------------------------------------------

In the file ``tools/conda.recipe/meta.yaml``, one can make use of Jinja
templating to insert the version number:

  .. code-block:: yaml

    package:
      version: "{{ PROJECT_VERSION }}"

When Roberto builds conda packages with the tool ``build-conda``, the
environment variable ``${PROJECT_VERSION}`` will be set.


Adding tools
============

One can add custom tools to the workflow, by adding a `tools` section to the
configuration file:

.. code-block:: yaml

    tools:
      <name of the tool>:
        task: <name of task for which the tool is intended>
        # ...

Additional fields can be added after ``task``, and the details of these
additional settings depend on the selected ``task``.

Filenames and most other fields in the tool settings can make use of
other confiruaton values, e.g. with ``{config.project.name}``, package-specific
configuration, e.g. ``{package.conda_name}``, or tool-specific settings, e.g.
``{tool.destination}``. These substitutions are not carried out recursively.

In `default configuration file <https://github.com/theochem/roberto/blob/master/roberto/default_config.yaml>`_,
there is one tool for each task, for which the settings are explained in detail.
Read these comments if you would like add a new tool in your configuration file.

All tasks can specify ``pip_requirements`` and ``conda_requirements``, which
will be installed upfront when Roberto prepares the development environment.
