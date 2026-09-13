# Task63 native unit transport review

Spec/scope: COMPLIANT. Instrument quality: APPROVED.
Critical: none. Important: none.

Both instruments were read completely, with the existing scoped Task63 review
used for the already-reviewed test semantics. Entry SHA256
`bb0e4a79d89a8266d45db81032fcb67f0c1139a75d3396944c36d78546015257`
matches dispatch. Runner SHA256 is
`0248ac7ef842e3c39afdb07fb4796fcc7d2cbf73e1b7ecf7db66622b1d60378f`.
No execution, Git/SSH command, code edit or new subagent; only this report was written.

## Checked scope, provenance and terminal contract

- The runner holds and verifies the exact template/archive bytes before
  substituting the single fixed placeholder. The entry independently requires
  archive143360bytes/SHA
  `6d93ed7db2d1fb29167deceda86e4910f0fe99f951a2dfc3cf0f421f89d4ea10`,
  commit `bb54ec58eadcab0e9c0ae065aa258cb7a8f337d6`, exactly four pinned regular
  members, no duplicates/unexpected members and bounded member sizes. Validation
  finishes before the first output directory creation; no general tar extraction.
- The fixed `/tmp/betboy-context-descriptors-task63-bb54ec5-01` must be absent.
  It and its test directory are created0700 under umask077. Source/evidence writes
  use exclusive no-follow0600 creation. No reuse, overwrite, cleanup, retained
  inventory scan, live DB, admission or application write is introduced.
- Real/effective/saved UID and GID must be1000. The controller requires isolated,
  no-site, non-optimized, bytecode-disabled Python and an exact clean environment.
  Initial NOFILE must be exactly1024/1048576. The existing pytest environment is
  used with isolation, no conftest, no plugin autoload/cache/bytecode and a fresh
  synthetic basetemp; there is no sudo or root pytest.
- CPU60, AS2GiB, FSIZE64MiB and core0 are installed before archive decoding.
  CPU60 is per process, not a claim that the entire test tree consumes at most
  60CPU in aggregate. Pytest has a75-second timeout, while external timeout90
  TERM/kill-after5 covers setup and the controller/test process group. No
  foreground/preserve-status override or retry is present. As with prior
  instruments, timeout/disconnection alone does not prove every process dead;
  Root must retain abnormal-exit evidence and perform required process readback.
- The exact pinned module is selected, not a broad suite. Final success requires
  child exit0,36 tests/0 failures/0 errors/1 skip, and that sole skip's exact name
  `test_portable_sample_marks_native_descriptor_validation_absent`. Thus an
  additional native skip, import error or count-only partial run cannot pass.
  Empty child stderr and unchanged controller NOFILE are also mandatory.
- The independently reviewed module contains actual old1024-EMFILE, new1100-file
  full ownership/restoration and unchanged-supervisor child-closure tests. This
  transport does not replace those with synthetic counts or monkeypatched OS
  claims. Controller NOFILE equality alone would not prove pytest cleanup;
  that evidence comes from the actual pinned tests and their successful exit.
- The XML is read with a262145-byte bounded read and refused above262144 bytes.
  Fresh per-run logs/XML/result remain on the server; fresh local stdout/stderr
  logs are captured, awaited, flushed and hashed. Actual SSH exit is propagated.
  Result JSON is deliberately emitted before final assertions: it is an
  observation, not a success credential. Root must require the actual final
  outer exit0 as well as exact XML/skip/stderr checks.

## Native acceptance remains separate

The supplied DryRun287c1e exit0 and payload196919/SHA
`b755022191075ff2b290007ec5691e11613e0ea0d1d66b3efee9a64442f2369c`
are preparation evidence, not reviewer-regenerated native evidence. Actual
runtime availability, UID/NOFILE state, executed native assertions and retained
terminal artifacts remain to be observed in the separately authorized run.

Even successful35pass/1named-skip establishes only these synthetic native FD
cases. Child closure is not full UID-drop/guard/SIGSTOP/receipt acceptance;
1100 synthetic inputs do not prove the full live-input inventory or descriptor
availability. The previously diagnosed repeated-retained-scan CPU60 conflict,
actual diagnostic admission, whole C/B and release remain open. T2 generic SSH
log caps remain explicitly deferred, not re-reviewed or silently closed.
