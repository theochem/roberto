.. image:: https://travis-ci.com/theochem/roberto.svg?branch=master
    :target: https://travis-ci.com/theochem/roberto
.. image:: https://anaconda.org/theochem/roberto/badges/version.svg
    :target: https://anaconda.org/theochem/roberto
.. image:: https://codecov.io/gh/theochem/roberto/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/theochem/roberto
.. image:: https://img.shields.io/pypi/v/roberto.svg
    :target: https://pypi.org/project/roberto
.. image:: https://img.shields.io/pypi/pyversions/roberto.svg
    :target: https://pypi.org/project/roberto
.. image:: https://img.shields.io/github/release/theochem/roberto.svg
    :target: https://github.com/theochem/roberto/releases


Roberto is a collection of configurable development work flows. Its goal is to
facilitate the development and quality assurance of some packages in the
theochem organization on Github.

With a relatively simple configuration file (``.roberto.yaml``), the command
``rob`` will take the following steps:

1. Install miniconda (and a MacOSX SDK on OSX).
2. Make a conda environment for development and testing
3. Install dependencies (for the package being developed and for all
   development tools).
4. Build the software in-place, i.e. without installing it.
5. Run Linters (optionally showing only messages related to your changes).
6. Run unit and other tests
7. Build the documentation

When you run ``rob robot``, a few additional steps will be performed, which are
not done by default because they are slow and have a low risk of failing:

8. Upload the documentation. (disabled by default)
9. Make source and binary release packages.
10. Deploy the releases. (disabled by default)

(A few minor steps were omitted for clarity.) These steps should work on your
local computer in the same way as on a continuous integration system like
Travis-CI, making it easy to prepare a pull request locally. It is also possible
to just run a subset of these tasks, which is often needed when working on the
code. Several steps will also reuse previous results (e.g. conda environment) if
these are already present, to speed up Roberto.

The preparation tasks (1-3) are somewhat hard-coded but they are clever enough
to install a decent development environment with the correct requirements for
the remaining tasks. These remaining tasks (4-10) are configurable and can be
changed to work for Python and/or CMake projects.


Installation
============

Python 3 (>=3.5) must be installed. Other dependencies will be pulled in with
the instructions below.

Roberto can be installed with conda:

.. code-block:: bash

    conda install theochem::roberto

It can also be installed with pip. One of the following is fine, whichever you
prefer:

.. code-block:: bash

    pip install roberto
    pip install roberto --user
    python3 -m pip install roberto
    python3 -m pip install roberto --user

On some platforms, you may have to adapt your ``${PATH}`` variable before you
can run ``rob``.


Usage
=====

Before you start, please be aware that Roberto will install miniconda, by default in
``~/miniconda3``, if not present yet. You can modify this directory by setting
the environment variable ``ROBERTO_CONDA_BASE_PATH`` or by putting the following
in your global Roberto configuration file ``~/.roberto.yaml``:

.. code-block:: yaml

    conda:
      base_path: <your/preferred/location>

E.g. you can use this to avoid interference with an existing miniconda install.
However, to avoid such interference, Roberto will also make conda environments
for the development of every package, with relatively long names. For example,
when Roberto is executed in its own source tree, the conda environment would be
``roberto-dev-python-3.7``.

To use Roberto, just run ``rob`` in the root of the source tree, where also the
project's ``.roberto.yaml`` is located. Use ``rob --help`` to get a list of
tasks if you are interested in replicating just a part of the CI process. If
your ``${PATH}`` variable is not set correctly, you can also run Roberto as
``python3 -m roberto`` instead of ``rob``.

It is a good practice to run ``rob`` before every ``git commit`` to make sure
the committed code is clean and working.

When using the cardboardlint tool and when you are working in a development
branch, cardboardlint will only show linter messages for lines of code that you
have changed. If you would like to see all messages, run Roberto as
``ROBERTO_ABS=1 rob``.

More details, e.g. on how to configure Roberto, can be found in the
documentation: https://theochem.github.com/roberto


Development
===========

If you have questions or ideas, just open an issue on Github. Practical
information on how to contribute can be found in
`CONTRIBUTING.rst <CONTRIBUTING.rst>`_.

Roberto is intentionally a small code base, so one can easily understand how
it works by reading the source code. Roberto makes extensive use of `invoke
<http://pyinvoke.org>`_ to avoid having to write a lot of boiler-plate code.
