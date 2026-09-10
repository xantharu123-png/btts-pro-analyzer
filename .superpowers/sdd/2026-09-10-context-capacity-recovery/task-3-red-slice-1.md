# Task 3: RED-only slice 1

10 September 2026. Sole writer permission was limited to the new test file and
this report. No installer implementation, README, updater, helper, model,
production path, service or Git history was changed. Existing controller/reviewer
WIP was preserved. No VPS/network action, push or subagent was used.

## Added contract

`tests/test_context_updater_repair.py` declares 35 initial cases:

- Exact two-argument 40-hex release / 64-hex updater digest request; malformed,
  extra, path-like and newline-tainted arguments rejected.
- Actual future `repair_main` orchestration must pass invocation, lock, fetched
  source, full backup/restore and target D4 before its sole exchange action.
  Each failed gate stops advancement; deployment/service/marker calls are fatal
  in the isolated Bash harness.
- Real local old/new/third candidate bytes; reviewed new digest mismatch;
  independent old copy, one-link target, missing/hardlinked installed target.
- File fsync, before/after replacement and parent-fsync operational failures;
  exact old-byte preservation or rollback.
- Crash modeled by BaseException, followed by a freshly loaded production
  namespace: disk evidence, not retained globals, must authorize recovery.
- Repeated recovery, successful idempotence, unknown third hash preservation,
  changed release identity, corrupted old copy and corrupted durable journal.

The proposed minimal internal seams are Bash `repair_main` and `repair_data`,
with embedded stdlib `parse_request`, `install_updater`, `recover_updater`.
Internal names can be mechanically aligned with the eventual reviewed
implementation; this is not authorization for an extra production CLI, path
override, failpoint flag, trust boolean or arbitrary executable argument.

The fixed production old digest is
`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`,
current expected production source is
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`, and the only permanent executable
target is `/usr/local/sbin/betboy-update`. Transaction fixtures substitute their
own byte digest and private paths only inside the extracted test namespace.

## Fresh RED evidence

Command:

```powershell
& C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_updater_repair.py -q -p no:cacheprovider --basetemp=.pytest_tmp/updater-repair-red-02 --tb=no --junitxml=.pytest_tmp/updater-repair-red-02.xml
```

Result: **35 failed, 0 errors, 0 skipped in 0.25s; process exit 1**.
Every failure is the explicit expected assertion
`missing Task3 updater-only repair installer`. The earlier 31-case slice likewise
failed for that reason before the additional restart/corruption cases were added.

This proves collection and missing-feature RED only. It is NOT yet proof that
the future transaction implementation, all deeper harness branches, Git fetch,
actual lock contention, real restore/HMAC/D4, Linux DAC, concurrent races or
crash durability pass. Windows metadata and directory-fsync emulation is
explicitly labeled and cannot clear any Linux gate.

## Remaining work before claiming Task 3 coverage

After explicit implementation permission and accepted Task 2, wire the minimal
installer and run through each deeper test branch; repair harness-only issues
without relaxing the byte, identity, ordering or fail-closed contract. Add focused
behavioral tests against its actual fixed Git/remote/commit/blob path, lock
implementation, root-private journal schema and reviewed backup/restore/D4
composition. The current external-gate doubles prove only orchestration failure
ordering, not those gates' implementation.

Fresh full Linux restore/HMAC and final real/growth capacity evidence remain
controller-owned release gates. No timing claim from another revision is
promoted by these RED tests. Product implementation is intentionally paused at
the controller's explicit RED-only boundary.

Process: used test-driven-development and verification-before-completion;
the TDD restriction kept all production code absent during this slice.
