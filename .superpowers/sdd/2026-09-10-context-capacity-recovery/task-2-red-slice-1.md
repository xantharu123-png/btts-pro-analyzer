# Task 2: bounded RED slice 1

Date: 2026-09-10. Base: `4fad098`. Controller authorized test/report edits only; no production implementation is included.

## Verified result

Using `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest tests/test_context_update_hook.py -q -p no:cacheprovider`:

- New slice: `--basetemp=.pytest_tmp/task2-red-02 -k capacity_ --junitxml=.pytest_tmp/task2-red-02.xml`: **9 failed, 1 passed, 239 deselected in 3.51s**, exit 1.
- Existing baseline: `--basetemp=.pytest_tmp/task2-existing-baseline-01 -k 'not capacity_' --junitxml=.pytest_tmp/task2-existing-baseline-01.xml`: **239 passed, 10 deselected in 29.14s**, exit 0.
- `git -c core.autocrlf=false diff --check -- tests/test_context_update_hook.py`: exit 0.

The initial `task2-red-01` run exposed a test-harness PATH omission. It is not accepted RED evidence. The harness now sets the Git Bash tool path and checks for missing-command errors; the clean second run below fails for production behavior, not missing fixtures/functions.

## Concrete RED observations

| Test suffix after `test_capacity_` | Observed current behavior |
| --- | --- |
| `member_reads_are_at_most_one_mib` | Actual ZIP extraction requests 67,108,865 bytes in one read. |
| `valid_65_mib_member_reaches_sealed_copy` | A real, quick-checked 65-MiB-payload SQLite database is rejected by the old context-image cap. This is a transport fixture, not D4/model evidence. |
| `phase_distinguishes_real_live_sqlite_commit[online-True]` | Actual stage/finish rejects a committed insertion on the same live inode, although the sealed online snapshot is unchanged. |
| `unknown_phase_cannot_silently_use_quiesced_finish` | An unknown supplied phase is ignored and continuity is printed. |
| `failure_from_fresh_online_backup_precedes_every_stop_and_write` | The real orchestration omits online capture and reaches recorded service stops, key/autostart/marker operations and payload application. Host mutations are recording doubles only. |
| `success_uses_two_distinct_archives_and_private_phase_hooks` | The real orchestration has only the quiesced recovery capture; the online archive and separate private phase stages do not occur. |
| `full_var_lib_mount_rejects_before_preflight_capture` | The actual disk-admission block accepts abundant staging/backup space despite a separate seal mount having only 1 KiB free. |
| `output_overflow_is_an_immediate_child_failure` | A real child emits 1 MiB + 1 byte; the bounded collector stores it but its shell boundary still reports acceptance. |
| `child_environment_fixes_all_numerical_threads` | A real child launched through the actual cleared environment sees all five numerical-thread variables unset. |

The paired `phase_distinguishes_real_live_sqlite_commit[quiesced-False]` control passes: strict post-quiesce mutation rejection remains a required existing behavior.

The proposed explicit phase argument is appended to the existing internal `stage`/`finish` invocation in this first test slice. It must become closed and proof-bound in implementation, not a free bypass flag. Internal fixture wiring may be adapted to the final reviewed launcher/phase interface without weakening these behavioral assertions.

## Boundaries and remaining test slices

This is deliberately not complete Task 2 coverage or approval. Still required before implementation completion: native strict ancestry/DAC and identity-bound cleanup; 1-GiB admission and CRC/length/header/race negatives for streaming; concurrent WAL capture and full inventory/principal identity checks; keyless AND proven contextless exception plus negative authentication cases; explicit in-progress resume with actual source-head binding; mount-shared aggregate sums; AS/CPU/wall limits and fixed-command launchers for inline/helper/D4 children; remaining pipeline failures; second-capture failure recovery. Existing tests already retain closed report and twelve-limitation checks, but those must be rerun after production edits.

Windows fixture ownership emulation does not prove Linux DAC. No tests connected to a VPS, stopped services, changed live keys/markers/databases, or ran the whole repository suite.

## Unchanged production bytes

- `deploy/update_server.sh`: `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`
- `scripts/backup_runtime_databases.py`: `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`
- `scripts/stage_runtime_databases.py`: `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`

Only `tests/test_context_update_hook.py` and this report belong to this slice. Controller-owned evidence and other WIP are excluded from staging.
