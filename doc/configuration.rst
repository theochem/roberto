.. _configuration:

Configuration
#############

Roberto uses invoke to process its configuration files. For most purposes,
it is sufficient to just write a ``.roberto.yaml`` file in the root of your
project's source tree. In some cases, environment variables, prefixed with
``ROBERTO_`` can be useful to extend or override the settings in the
configuration file. These settings extend the default configuration file shown
in the last section below.

Invoke's also offers other mechanisms to modify Roberto's configuration, which is
explained here: http://docs.pyinvoke.org/


Basic configuration
===================

The configuration file must at least contain the following:

.. code-block:: yaml

  project:
    # 'name' is used for package and directory names.
    name: 'your_project_name'
    # List one or more software packages below.
    packages:
        # No default value for 'conda_nane'.
        # It must be unique in case
        # of multiple package.
      - conda_name: 'conda_package_name'
        # A package name, must not be unique.
        # The default is the project name.
        name: 'package_name'
        # A subdirectory of the source tree.
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

Each tool will enable a feature in the overall work flow for the corresponding
package. See section :ref:`workflow` for a more detailed description.

Other sections can be added as well, e.g. to define new tools as explained
below, or to change other settings, shown in the default configuration.

Basic examples
==============

A basic configuration for a Python project, e.g. called `spammer` can be done as
follows:

.. code-block:: yaml

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


A basic configuration for a CMake (e.g. C++) project and a Python wrapper, here
called `bummer` can be done as follows:

.. code-block:: yaml

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



Adding tools
============

One can add custom tools to the workflow, by adding a `tools` section to the
configuration file:

.. code-block:: yaml

    tools:
      <name of the tool>:
        task: <name of task in which the tool intended to work>
        # ...

Additional fields can be added after ``task``, and the details of these
additional settings depend on the selected ``task``.

Filenames and most other fields in the tool settings can make use of
other confiruaton values, e.g. with ``{config.project.name}``, package-specific
configuration, e.g. ``{package.conda_name}``, or tool-specific settings, e.g.
``{tool.destination}``. These substitutions are not carried out recursively.

In the default configuration file, for each task there is one tool for which
the settings are explained in detail for the general case. Read these comments
if you would like to understand the settings for a new tools in your config
file.

All tasks can specify ``pip_requirements`` and ``conda_requirements``, which
will be installed upfront when Roberto prepares the development environment.


Default configuration
=====================

TODO: fix url

See http://github.com/theochem/roberto/...
