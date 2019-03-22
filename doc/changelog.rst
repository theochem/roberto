.. _changelog:

Change log
##########

- Version 1.2.0 March 21, 2019

  - Make pytest run in parallel.
  - Parallel in-place build with CMake.
  - Default task has become "quality", i.e. the in-place subset of the tests.
  - More configuration options for in-place builds (paths and flags).
  - Fix SDK blues on OSX.
  - Various small fixes.

- Versoin 1.1.1 March 18, 2019

  - Fix bugs in SDK download and usage on OSX.
  - Re-activate conda after every install.
  - Use yaml.safe_load
  - Roberto no longer crashes outside a git repo.
  - Stop using LD_LIBRARY_PATH and use RPATH for dynamic in-place linking
    instead.
  - Report SIP status on OSX, which could be useful info in case of troubles.
  - Fix mistake in generation of PATH variables.

- Version 1.1.0 March 17, 2019

  - Download MacOSX SDK when needed.
  - Fix PyPi upload (no sha256).
  - Small documentation fixes.

- Version 1.0.1 March 17, 2019

  - Small documentation improvements.
  - Fix missing requirement for static cardboard linting

- Version 1.0.0 March 17, 2019

  This is the first official release, all previous ones being just testing
  artifacts.
