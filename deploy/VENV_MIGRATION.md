# Reviewed venv migration gate

`betboy-update` deliberately refuses a target whose `requirements.txt` blob
differs from the deployed commit. Do not bypass that check with an in-place
`pip install` or by moving a prepared venv: generated console scripts contain
absolute shebangs, and the current requirement ranges are not a reproducible
lock.

A dependency-changing release is authorized only after a separate change has
all of the following evidence:

1. A reviewed, hash-bound lock file for the supported Python version and Linux
   platform (`pip --require-hashes` succeeds without resolving new versions).
2. A versioned final directory such as
   `/opt/betboy/venvs/<lock-sha256>` created at that exact final path by a
   preparation account which cannot write the app checkout, databases,
   production venv or backup directories.
3. `python -m pip check`, imports and a Streamlit health smoke test executed
   from that final directory before downtime. Check console-script shebangs or
   run entry points as `python -m ...`.
4. A one-time migration of the current real `/opt/betboy/venv` directory to an
   immutable versioned directory, followed by an atomic
   `/opt/betboy/venv` symlink switch on the same filesystem. Every component
   and parent must be root-verified as a non-symlink before the migration.
5. The normal updater's quiesce sequence: stop all seven timers, wait for all
   workers, stop the app, reverify tracked bytes, and create the trusted
   root-protected SQLite inventory backup before switching code or the venv
   link.
6. Rollback tests which atomically restore the old link and byte-verified code
   before any new app process starts. After new code starts, any failure stays
   fail-closed and requires an operator-reviewed database restore decision.

Until those controls and their shell-level failure tests are committed and
reviewed, keep `requirements.txt` unchanged and let `betboy-update` stop at its
preflight gate.
