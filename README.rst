.. image:: https://travis-ci.org/theochem/roberto.svg?branch=master
    :target: https://travis-ci.org/theochem/roberto
.. image:: https://anaconda.org/theochem/roberto/badges/version.svg
    :target: https://anaconda.org/theochem/roberto
.. image:: https://codecov.io/gh/theochem/roberto/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/theochem/roberto


Roberto is a collection of configurable development work flows. Its goal is to
facilitate testing and developing some packages in the theochem organization on
Github.

After it is configured (in ``.roberto.yaml``), it can autonomously perform the
complete process that takes place on Travis-CI (or other continuous integration
services).


Installation
============

Python 3 (>=3.5) must be installed. Other dependencies will be pulled in with
the instructions below.

With conda:

.. code-block:: bash

    conda install theochem::roberto

With pip, one of the following, whichever you prefer:

.. code-block:: bash

    pip install roberto
    pip install roberto --user
    python3 -m pip install roberto
    python3 -m pip install roberto --user


Usage
=====

Before you start, be aware that Roberto will install miniconda, by default in
``~/miniconda3``. You can modify this directory by setting the environment
variable ``ROBERTO_CONDA_BASE_PATH`` or by putting the following in your global
Roberto configuration file ``~/.roberto.yaml``:

.. code-block:: yaml

    conda:
      base_path: <your/preferred/location>

E.g. you can use this to avoid interference with an existing miniconda install.
However, to avoid such interference, Roberto will make conda environments for
the development of every package, with relatively long names. For example,
for Roberto itself, this conda environment would be ``roberto-dev-python-3.7``.

To use Roberto, just run ``rob`` in the root of the source tree, where also the
project's ``.roberto.yaml`` is located. User ``rob --help`` to get a list of
tasks if you are interested in replicating just a part of the CI process.

If your PATH variable is not set correctly, which may easily happen on OSX, you
can also run Roberto as ``python3 -m roberto`` instead of ``rob``.

More details, e.g. on how to configure Roberto, can be found in the
documentation: https://theochem.github.com/roberto


Development
===========

If you have questions or ideas, just open an issue on Github. Practical
information on how to contribute can be found in CONTRIBUTING.rst.

Roberto is intentionally a small code base, to make it easy to understand how
it works by reading its code. Roberto makes extensive use of `invoke
<http://pyinvoke.org>`_ to avoid having to write a lot of boiler-plate code.
