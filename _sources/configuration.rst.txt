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
        # 'dist_name' is required and there is no default value.
        # It must be unique in case of multiple package.
      - dist_name: 'name_for_distribution_packages'
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
      - dist_name: '...'
        # ...

Each tool of each package will be executed in one task in the overall work
flow. See section :ref:`workflow` for a more detailed description. A complete
list of the built-in tools and configuration options can be found in the
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
        - dist_name: spammer
          tools:
            - write-py-version
            - cardboardlint-static
            - build-py-inplace
            - pytest
            - upload-codecov
            - cardboardlint-dynamic
            - build-sphinx-doc
            - upload-docs-gh
            - build-py-source
            - build-conda
            - deploy-pypi
            - deploy-conda
            - deploy-github

This configuration assumes that you have at least the following files in your
Git repository:

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
        - dist_name: bummer
          tools:
            - write-cmake-version
            - cardboardlint-static
            - build-cmake-inplace
            - maketest
            - upload-codecov
            - cardboardlint-dynamic
            - build-cmake-source
            - build-conda
            - deploy-conda
            - deploy-github
        - dist_name: python-bummer
          path: python-bummer
          tools:
            - write-py-version
            - cardboardlint-static
            - build-py-inplace
            - pytest
            - upload-codecov
            - cardboardlint-dynamic
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
`default configuration file <https://github.com/theochem/roberto/blob/master/roberto/default_config.yaml>`_.
From there, all tasks
can access version information when they need it. Below the most important of
these tasks are discussed.

Python projects
---------------

Use the tool ``write-py-version`` to make sure the file ``_version.py`` exists
before ``setup.py`` is called.

In ``setup.py``, use the following code to derive the version instead of
hard-coding it:

  .. code-block:: python

    import os

    NAME = 'spammer'  # <-- change this name.

    def get_version():
        """Read __version__ from version.py, with exec to avoid importing it."""
        with open(os.path.join(NAME, 'version.py'), 'r') as f:
            myglobals = {"__name__": f"{NAME}.version"}
            # pylint: disable=exec-used
            exec(f.read(), myglobals)
        return myglobals['__version__'], myglobals['DEV_CLASSIFIER']

    VERSION, DEV_CLASSIFIER = get_version_info()

    setup(
        name=NAME,
        version=VERSION,
        package_dir={NAME: NAME},
        packages=[NAME, NAME + '.test'],
        classifiers=[
            DEV_CLASSIFIER,
            # ...
        ],
        # ...
    )

The file ``version.py`` contains the following

  .. code-block:: python

    try:
        # pylint: disable=unused-import
        from ._version import __version__, DEV_CLASSIFIER
    except ImportError:
        __version__ = '0.0.0.post0'
        DEV_CLASSIFIER = 'Development Status :: 2 - Pre-Alpha'

This is automates all versioning tasks but still works when Roberto has not
been used to write the version file.

When the Sphinx documentation is built, one can assume an in-place built has
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

When Roberto sets up a conda environment, environment variable
``${PROJECT_VERSION}`` will be set.


Adding tools
============

One can add custom tools to the workflow, by adding a `tools` section to the
configuration file:

.. code-block:: yaml

    tools:
      <name of the tool>:
        cls: <Class name from roberto/tools.py>
        # ...

Additional fields can be added after ``cls``, and the details of these
additional settings depend on the selected ``cls``.

Filenames and most other fields in the tool settings can make use of
other confiruaton values, e.g. with ``{config.project.name}``, package-specific
configuration, e.g. ``{package.dist_name}``, or tool-specific settings, e.g.
``{tool.destination}``. These substitutions are not carried out recursively.

The fields in the tool section are (almost) all constructor arguments for a
corresponding class in `roberto/tools.py`. Refer to their docstrings for more
details. There are two optional fields not used as constructor arguments:

- ``requirements``: a list of 2-tuples, in which the first string is the
  conda package name and the second is the pip package name (if available).

- ``suported_envs``: present when a tool is only supported by conda, in which
  case the corresponding value is ``[conda]``. When not present, the tool is
  assumed to work for both types of virtual environments.
