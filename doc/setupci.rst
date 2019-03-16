.. _setupci:

CI Setup
========

When using Roberot to drive a continuous integration (CI) setup, you may want to set
additional environment variables:

- ``ROBERTO_CONDA_PINNING`` can be used to pin any dependencies to a specific
  version, e.g. ``"python 3.5"`` will let Roberto install Python-3.5 instead of
  the default. This variable must be an even number of strings separated by
  spaces, each time a conda package followed by a version number.

- ``ROBERTO_DEPLOY_BINARY``. Set this to ``1`` if you want Roberto to upload
  binary releases.

- ``ROBERTO_DEPLOY_NOARCH``. Set this to ``1`` if you want Roberto to upload
  architecture independent releases

- ``GITHUB_TOKEN``. Set this to a token with write access to your repo to
  make deployment to Github and pushing to gh-pages work.

- ``ANACONDA_API_TOKEN``. Set this token to make anaconda uploads work.

- ``TWINE_USERNAME`` and ``TWINE_PASSWORD``. Set these to make uploads to pypi
  work.

Make sure you properly encrypt tokens and passwords in your CI configuration
file. For Travis-CI, detailed explanations can be found in Roberto's
``.travis.yaml`` file. See TODO.

Besides setting the above environment variables, you also need to install and
run Roberto correctly. The following minimalistic set of bash commands should
work on both Linux and OSX:

.. code-block:: bash

  # These commands assume you are in the root of the repository and that a basic
  # Python 3 (>= 3.5) is installed.
  # 1) Install pip and roberto
  wget --no-clobber -O ${HOME}/get-pip.py https://bootstrap.pypa.io/get-pip.py || true
  python3 ${HOME}/get-pip.py --user
  python3 -m pip install . --user
  # 2) Run Roberto
  python3 -m roberto
