# Context capacity repair execution ledger

Base: `82ca31d4340ed2dabd2a9812eb6bcadfbd757a5a`; branch `codex/context-capacity-recovery-20260910`.
User approved the one-time updater-only replacement with independent review, fresh backup and rollback. No data deletion or unrelated deployment is authorized by this repair.

- Task 1: initial code `b333c3c`; lifecycle fix `41067c0`, report `3967778`. Independent fix re-review APPROVED: stale Mapping revival is closed. Final targeted fix checks124 passed/12 skipped,22lifecycle cases and1actual protected-final guard. Real-data performance is still a separate HOLD; no release acceptance claimed.
- Task 2: waiting for Task 1 review; streaming normal updater and pre-downtime full capacity proof.
- Task 3: waiting for Tasks 1-2; narrowly pinned repair installer, Linux real-backup evidence and controlled release.
- Baseline: 332 passed / 3 skipped, 45.69s, exit 0; `.pytest_tmp/capacity-baseline-01.xml`.
- Production unchanged by repair so far. Existing main/VPS release `2dd1116`; installed updater SHA `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
- Frozen A0 and P4b3 branches, protected stage helper, existing keys, account data and all historical receipts remain out of scope.
- Fresh real backup: `betboy-sqlite-20260910T140039Z.zip`, 88 verified / 0 pruned. Old-reader diagnostic against isolated 99.375-MiB copy completed in173.319s, peak836908KiB; current inventory6artifacts/4snapshots/47497receipts. See `live-capacity-evidence-20260910.md`.
- Provisional pre-fix Task1 native BetBoy-user DAC checks:3write/rename/SQLite denials;8unsafe-fixture classes rejected; small memory/sealed reports equal. The bounded real-copy new-reader attempt ended without a final verification report (supervisor exit1). Targeted first-history profiling is running; this is not a successful capacity run. Input and installed updater hashes remain unchanged.
- Task2 integration preflight is complete and its narrow path/phase/legacy/resource clarifications are incorporated into the plan. Helpers/units remain unchanged.
