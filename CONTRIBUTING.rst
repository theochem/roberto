We'd love you to contribute, and here is the mini how-to:
talk, fork, branch, hack, rob & pull request.

Longer version:

1. Before diving into technicalities: if you intend to make major changes,
   beyond fixing bugs and small functionality improvements, please open a Github
   issue first, so we can discuss before coding. That often saves a lot of time
   and trouble in the long run.

   Use the issue to plan your changes. Try to solve only one problem at a time,
   instead of fixing several issues and adding different features in a single
   shot. (Small changes are easier to review in the last step.)

   Mention in the corresponding issue when you are working on it. "Claim" the
   issue to avoid duplicate efforts.

2. Make a fork of the project, using the Github "fork" feature.

3. Clone the original repository on your local machine and enter the directory

   .. code-block:: bash

    git clone git@github.com:theochem/roberto.git
    cd roberto

4. Install this version of Roberto on your system, e.g. with one of the
   following lines, whichever works best for you:

   .. code-block:: bash

    python3 setup.py install
    python3 setup.py install --user
    pip install .
    pip install . --user
    python3 -m pip install .
    python3 -m pip install . --user

5. Add your fork as a second remote to your local repository, for which we will
   use the short name `mine` below, but any short name is fine:

   .. code-block:: bash

    git remote add mine git@github.com:<your-github-account>/roberto.git

6. Make a new branch, with a name that hints at the purpose of your
   modification:

   .. code-block:: bash

    git checkout -b new-feature

7. Make changes to the source. Please, make it easy for others to understand
   your code. Rules of thumb:

   - Write transparent code, e.g. self-explaining variable names.
   - Add comments to passages that are not easy to understand at first glance.
   - Write docstrings explaining the API.
   - Try to add unit tests when feasible. Not everything in Roberto is covered
     with unit tests because some functions only work when the program is
     executed as a whole. If possible, try to factor out parts of features into
     separate functions that are easily unit-tested.

8. Commit your changes with a meaningful commit message. The first line is a
   short summary, written in the imperative mood. Optionally, this can be
   followed by an empty line and a longer description.

   If you feel the summary line is too short to describe what you did, it
   may be better to split your changes into multiple commits.

9. Run Roberto on itself and fix all problems it reports. Style issues, failing
   tests and packaging issues should all be detected at this stage. Either one
   of the following should work

   .. code-block:: bash

    rob                 # Normal case
    python3 -m roberto  # Only if your PATH is not set correctly

10. Push your branch to your forked repository on Github:

    .. code-block:: bash

        git push mine -u new-feature

    A link should be printed on screen, which will take the next step for you.

11. Make a pull request from your branch `new-feature` in your forked repository
    to the `master` branch in the original repository.

12. Wait for the tests on Travis-CI to complete. These should pass. Also
    coverage analysis will be shown, but this is merely indicative. Normally,
    someone should review your pull request in a few days. Ideally, the review
    results in minor corrections at worst. We'll do our best to avoid larger
    problems in step 1.
