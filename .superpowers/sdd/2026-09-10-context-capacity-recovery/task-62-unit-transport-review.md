# Task62 native unit instrument review

Spec/scope verdict: scoped correctly, with one wall-bound issue to fix before launch.
Quality verdict: NEEDS FIXES for the instrument only. Task62 walker approval is unchanged.

Reviewed complete entry SHA256
`3f290ec20e4a14c613e3866e0ae9ad92ac0dd70cc77599f66eb001a99f55c00e`
and runner SHA256
`182066684b61babd28f9723d71e96703bdb91bc2c02b1d07f7bb81ab0b234d40`;
both match the dispatched files. No tests, VPS/network action, Git operation,
source edit or subagents were used. Only this review report was written.

## Important

I1: Add an overall remote controller wall deadline before launch.

`evidence/task62-native-unit-entry.py` installs CPU/AS/file/core limits but no
controller wall timer. Its `subprocess.run(..., timeout=90)` bounds only each
pytest call; it does not bound archive/setup/output I/O or controller work
between calls. `evidence/task62-native-unit-run.ps1` waits in
`while (-not $unitProcess.WaitForExit(1000))` without an elapsed cutoff.
SSH keepalives detect a lost connection, not a hung process on a responsive
server. Consequently the instrument does not currently provide a fixed
end-to-end execution wall ceiling.

Fix: install an explicit fixed controller wall alarm before bundle decoding or
fixture writes, allowing the two 90-second phases plus declared setup/output
headroom (for example 210 seconds). Keep timeout termination non-successful and
retain the external exit observation. A bounded transport failsafe may supplement
this but must not silently retry or claim that disconnecting proves remote exit.
This is distinct from deferred T2 generic SSH log caps, which are not reviewed
or cleared here.

## Critical

None.

## Checked strengths and semantics

- The runner holds and hashes the exact template and archives before replacing
  exactly one occurrence of each fixed placeholder. The entry independently
  verifies archive byte counts, hashes, Git commit comments, complete allowed
  member sets and individual file hashes before its first mkdir. It does not
  extract archive paths generally or import live application sources.
- The fixed new `/tmp/betboy-context-retained-task62-6eb267a-01` must not exist.
  Creation is private under umask077; staged files use exclusive no-follow
  creation. Only validated synthetic inputs and fixtures inhabit the new root;
  no cleanup, retained scan, live DB, admission or service mutation is present.
- Remote execution requires real/effective/saved UID and GID1000, isolated
  no-site/non-optimized controller Python and an exact clean environment.
  Pytest uses the existing ordinary-user interpreter, isolated mode, no
  conftest, disabled plugin autoload/cache/bytecode and fresh stage-specific
  basetemp/XML paths. No sudo or root pytest exists in the instrument.
- CPU60/AS2GiB/file64MiB/core0 limits are installed before archive handling and
  inherited by pytest. CPU60 is per process, not an aggregate60CPU claim.
  Each pytest invocation has a90-second timeout; I1 addresses the missing outer
  wall bound rather than claiming those individual bounds are absent.
- RED stages the same pinned new tests/helper with only the old pinned catalogue.
  It selects the exact native scaling/equivalence test and requires exit1,
  one failure, zero errors/skips, plus the `sum(name` assertion text. The focused
  test declaration check confirms the intended assertion is line173 of
  `tests/test_native_context_receipt_retained_walk.py`: one absolute root open.
  An import/collection error cannot count as the requested RED.
- GREEN requires actual exit0 and43 cases with no failures/errors/skips. The
  module's declarations total43 (14 fault cases in each of two groups, six
  modeled bounds, four replacements and five single cases). The prior44-case
  portable report included a separate adjacent historical-hardlink test, as
  clarified by Root; it is not part of this minimal three-file package.
- The runner preserves fresh local stdout/stderr files, awaits both streams,
  flushes them, prints the actual SSH exit and propagates it. The remote
  controller records each child exit/XML counts and refuses final success
  unless both exact phase expectations hold. A printed phase observation alone
  is not a successful final execution.

## Cannot verify / open gates

The supplied DryRun exit0,225215-byte payload and payload hash are controller
evidence, not a native result regenerated here. Actual existing pytest/runtime
state, SSH target UID, native RED/GREEN behavior, terminal exit and captured
artifacts require the separately prepared run after I1 is resolved.

Native unit success would prove only the selected synthetic tests. Actual
retained-union inventory/timing, real diagnostic admission and baseline1024,
parent60/worker240 enforcement and C/B/empirical/release remain open. T2 remains
deferred without any new log-cap finding or implied closure.
