.. _setupci:

CI Setup
########


General instructions
====================

When using Roberto to drive a continuous integration (CI) setup, you may want to
set additional environment variables:

- ``ROBERTO_CONDA_PINNING`` can be used to pin any dependencies to a specific
  version, e.g. ``"python 3.5"`` will let Roberto install Python-3.5 instead of
  the default. This variable must be an even number of strings separated by
  spaces, each time a conda package followed by a version number.

- ``ROBERTO_DEPLOY_BINARY``. Set this to ``1`` if you want Roberto to upload
  binary releases.

- ``ROBERTO_DEPLOY_NOARCH``. Set this to ``1`` if you want Roberto to upload
  architecture independent releases

- ``ROBERTO_UPLOAD_COVERAGE``. Set this to ``1`` if you want coverage reports
  on CodeCov.

- ``GITHUB_TOKEN``: a token with write access to your repo, to
  make deployment to Github and pushing to gh-pages work.

- ``ANACONDA_API_TOKEN``: a token to make anaconda uploads work.

- ``TWINE_USERNAME`` and ``TWINE_PASSWORD``: needed for uploads to pypi.

Make sure tokens are encrypted and passwords in your CI configuration
file.

Besides setting the above environment variables, you also need to install and
run Roberto correctly. The following minimalistic set of bash commands should
work on both Linux and OSX:

.. code-block:: bash

  # These commands assume you are in the root of the repository and
  # that a basic Python 3 (>= 3.5) is installed.
  # 1) Install pip and roberto
  wget --no-clobber -O ${HOME}/get-pip.py https://bootstrap.pypa.io/get-pip.py || true
  python3 ${HOME}/get-pip.py --user
  python3 -m pip install roberto --user
  # 2) Run Roberto
  python3 -m roberto


Tips and tricks for Travis-CI
=============================

Travis is extensively documented and this section does not replace that
documentation. See https://docs.travis-ci.com/


Minimal example of a ``.travis.yaml`` file that uses Roberto
------------------------------------------------------------

.. code-block:: yaml

    matrix:
      include:
        - os: linux
          dist: xenial
          language: generic
          env:
            - ROBERTO_CONDA_PINNING="python 3.6"
            - ROBERTO_DEPLOY_BINARY=1
        - os: linux
          dist: xenial
          language: generic
          env:
            - ROBERTO_CONDA_PINNING="python 3.7"
            - ROBERTO_DEPLOY_NOARCH=1
            - ROBERTO_DEPLOY_BINARY=1
        - os: osx
          osx_image: xcode9.4
          language: generic
          env:
            - ROBERTO_CONDA_PINNING="python 3.6"
            - ROBERTO_DEPLOY_BINARY=1
        - os: osx
          osx_image: xcode9.4
          language: generic
          env:
            - ROBERTO_CONDA_PINNING="python 3.7"
            - ROBERTO_DEPLOY_BINARY=1

    env:
      global:
        # Install conda in a *sub*directory of a
        # directory cached by travis.
        - ROBERTO_CONDA_BASE_PATH=${HOME}/cache/miniconda3
        # Tell Roberto to upload coverage results
        - ROBERTO_UPLOAD_COVERAGE=1
        # Build conda packages outside the
        # miniconda tree, to avoid caching.
        - CONDA_BLD_PATH=${HOME}/conda-bld
        # Tell roberto which branch is being
        # merged into, in case of a PR.
        - ROBERTO_MERGE_BRANCH=${TRAVIS_BRANCH}

        # GITHUB_TOKEN
        # yamllint disable-line rule:line-length
        # - secure: "..."
        # ANACONDA_API_TOKEN
        # yamllint disable-line rule:line-length
        # - secure: "..."
        # TWINE_PASSWORD
        # yamllint disable-line rule:line-length
        # - secure: "..."
        # - TWINE_USERNAME: theochem

    cache:
      # More time is needed for caching due to
      # the sheer size of the conda env.
      timeout: 1000
      directories:
        # Everything under the cache directory will be archived and made
        # available in subsequent builds to speed them up.
        - ${HOME}/cache

    install:
      # Disable deployment when TRAVIS_TAG is not set.
      # This avoids duplicate deployments.
      - if [[ -z $TRAVIS_TAG ]]; then
          export ROBERTO_DEPLOY_BINARY=0 ROBERTO_DEPLOY_NOARCH=0;
        fi
      # Get a basic python 3 with pip to run roberto
      - python3 --version
      - wget --no-clobber -O ${HOME}/cache/get-pip.py
        https://bootstrap.pypa.io/get-pip.py || true
      - python3 ${HOME}/cache/get-pip.py --user
      # To avoid surprises, constrain the major
      # version number of roberto.
      - python3 -m pip install 'roberto<2.0.0' --user

    script:
      # Instead of simply calling `rob`, do something that
      # always works on OSX too. When testing a pull request,
      # it is sufficient to run only the quality checks on
      # the in-place build, which should catch 99% of the
      # problems while it is considerably faster.
      - if [[ "$TRAVIS_PULL_REQUEST" == "false" ]]; then
          python3 -m roberto robot;
        else
          python3 -m roberto;
        fi

    before_cache:
      # Remove things that are not needed in subsequent builds.
      - rm -rf ${ROBERTO_CONDA_BASE_PATH}/conda-bld
      - rm -rf ${ROBERTO_CONDA_BASE_PATH}/locks
      - rm -rf ${ROBERTO_CONDA_BASE_PATH}/pkgs
      - rm -rf ${ROBERTO_CONDA_BASE_PATH}/var
      - rm -rf ${ROBERTO_CONDA_BASE_PATH}/envs/*/conda-bld
      - rm -rf ${ROBERTO_CONDA_BASE_PATH}/envs/*/locks
      - rm -rf ${ROBERTO_CONDA_BASE_PATH}/envs/*/pkgs
      - rm -rf ${ROBERTO_CONDA_BASE_PATH}/envs/*/var


Setting up encrypted tokens and passwords (for theochem admins)
---------------------------------------------------------------

**GITHUB_TOKEN**

0. Install the ``travis-ci`` command-line client. See
   https://github.com/travis-ci/travis.rb#installation

1. Login with the theochem-ci-bot account on github.com.

2. Go to profile settings: https://github.com/settings/profile

3. Select "Developer settings".

4. Select "Personal access tokens".

5. Create a new token "automatic releases for theochem/???" and
   activate "public_repo", then save.

6. Copy the token. It is only shown once.

7. Encrypt the token on the command line

   .. code-block:: bash

     travis encrypt --pro GITHUB_TOKEN="[copy-paste-your-github-token]"

   This command asks for a username and a password of the theochem-ci-bot
   account. (Do not use the ``--add`` feature.)

8. Put the output in ``.travis.yaml``:

   .. code-block:: yaml

    env:
      global:
        # ...
        # GITHUB_TOKEN
        # yamllint disable-line rule:line-length
        - secure: "..."

   Do not forget to add a comment so everyone can figure out the purpose of the
   encrypted string.

9. Add the repository to the list the Buildtools team on theochem and
   enable write permission.


**ANACONDA_API_TOKEN**

0. Install the ``travis-ci`` command-line client. See
   https://github.com/travis-ci/travis.rb#installation

1. Login on anaconda.org (with our bot account).

2. Go to profile settings: https://anaconda.org/theochem/settings/profile

3. Select "Access".

4. Create a new token (Allow all API operations)

5. Copy the token.

6. Encrypt the token on the command line

   .. code-block:: bash

     travis encrypt --pro ANACONDA_API_TOKEN="[copy-paste-your-anaconda-token]"

   This command asks for a username and a password of the theochem-ci-bot
   account. (Do not use the ``--add`` feature.)

7. Put the output in ``.travis.yaml``:

   .. code-block:: yaml

    env:
      global:
        # ...
        # ANACONDA_API_TOKEN
        # yamllint disable-line rule:line-length
        - secure: "..."

   Do not forget to add a comment so everyone can figure out the purpose of the
   encrypted string.



**TWINE_PASSWORD**

0. Install the ``travis-ci`` command-line client. See
   https://github.com/travis-ci/travis.rb#installation

1. Encrypt the Pypi password on the command line

   .. code-block:: bash

     travis encrypt --pro TWINE_PASSWORD='[copy-paste-pypi-password]'

   This command asks for a username and a password of the theochem-ci-bot
   account. (Do not use the ``--add`` feature.)

2. Put the output and the username in ``.travis.yaml``:

   .. code-block:: yaml

    env:
      global:
        # ...
        # TWINE_PASSWORD
        # yamllint disable-line rule:line-length
        - secure: "..."
        - TWINE_USERNAME: theochem

   Do not forget to add a comment so everyone can figure out the purpose of the
   encrypted string.


Troubleshooting encrypted token issues
--------------------------------------

Debugging issues with encrypted tokens and passwords can be very tricky.
Here are some clues to overcome the most common problems:

- When the en- or decryption has somehow failed, the corresponding variables
  are not set when your build runs on Travis-CI. You should be able to see this
  in the header of the build log (under the section ``Setting environment
  variables from .travis.yml``). It normally shows all variables, with the
  encrypted ones masked as ``MEANINGFULL_NAME=[secure]``. When it fails, you
  see something like ``wPKmdvIo2cOt6SH02fDd=[secure]``.

- The deployment scripts will fail if the necessary tokens or passwords are
  not found in the right environment variables. Twine and hub will start
  asking for login crediatials. Anaconda will fail without clear error
  message. Roberto checks the required variables and will print for each one if
  it is not set, empty or not empty.

- The order of the lines in the build log tends to get mixed up near the
  deployment scripts, so it may not be easy to follow what is going on.

- The simplest solution to try first, is a second attempt to encrypt the
  variables. If that does not work, check if something else is causing the
  problem by running the Travis-CI image in a docker instance as explained
  below. In this docker instance, just use non-encrypted variables.

- We had some issues with encryption before on travis-ci.org that magically
  disappaered on travis-ci.com. The ``--pro`` argument mentioned in the
  instructions above is needed for travis-ci.com, not for travis-ci.org.


Manually running tests in a Travis docker image
-----------------------------------------------

Even when ``rob`` reports no problems your local computer, ``rob`` might still
print errors for exactly the same code on Travis. (This should be rare though.)
In this case, it could be helpful to run ``rob`` or any other tests manually in
a Travis docker image:

1. Install docker-ce: https://docs.docker.com/install/

2. Get an up-to-date travis-ci docker image. For our linux builds, these can
   be found here: https://hub.docker.com/r/travisci/ci-sardonyx/tags

   Download as follows:

   .. code-block:: bash

       docker pull travisci/ci-sardonyx:packer-1549881206-387f377

   This will take a while. (3GB download!)
   You may want to use a newer tag than ``packer-1549881206-387f377``.

3. Run the headless image:

   .. code-block:: bash

       docker run --name foobar \
           travisci/ci-sardonyx:packer-1549881206-387f377 \
           /sbin/init

   where you may also need to change the tag to be consistent with step 2.
   Note that tab completion can be convenient.

4. In another terminal window, run the following, to get into the docker
   instance:

   .. code-block:: bash

       docker exec -it foobar bash -l


5. Once in the image, switch first to the travis user:

   .. code-block:: bash

       su - travis

6. Then run all the commands you encounter in the travis log and debug.

7. When done, log out of the instance (exit two times)

8. Stop the instance

   .. code-block:: bash

       docker stop foobar

9. Clean up

   .. code-block:: bash

       docker rm foobar

   This will clean up your experiments, but not the image you downloaded.
