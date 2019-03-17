.. _configuration:

Configuration
#############

Roberto uses invoke, amongst other things, to parse its configuration files. For
most projectes, it is sufficient to just write a ``.roberto.yaml`` file in the
root of the project's source tree. In some cases, environment variables,
prefixed with ``ROBERTO_`` can be useful to extend or override the settings in
the configuration file. All your settings extend the
`default configuration file <https://>`_. TODO FIX URL


TODO: fix url

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
list of the built-in tools can be found in the `default configuration file <https://>`_. TODO FIX URL

Other sections can be added as well, e.g. to define new tools as explained
below, or to change other settings from `default configuration file <https://>`_. TODO FIX URL


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

In `default configuration file <https://>`_, TODO FIX URL there is one tool for each task, for which
the settings are explained in detail. Read these comments if you would like add
a new tool in your configuration file.

All tasks can specify ``pip_requirements`` and ``conda_requirements``, which
will be installed upfront when Roberto prepares the development environment.
