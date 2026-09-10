# Task 2 checkpoint 1: independent read-only review

Date: 2026-09-10. Reviewer: `capacity_task2_checkpoint_review`.

Scope: the **incomplete checkpoint**, not final Task 2 acceptance. Review package: `73e6abd34376286e8b02b2326b25e4143e7e691d..43bfd0d276b36465865c9ddac5a3937c61886c1c`. Read the entire capacity-recovery plan, integration preflight and checkpoint report, the supplied diff, and the affected source plus surrounding invocation/recovery paths. The requesting/receiving-code-review and verification-before-completion skills governed the review: requirements and actual control flow are the evidence; previous test results are not new reviewer verification.

The checked working files matched the checkpoint's exact raw SHA-256 values both before and after review:

| File | SHA-256 |
| --- | --- |
| `deploy/update_server.sh` | `91917ed4009b63ae77ddc04ed68fc2767fef483a69793dd2ae45d2f75df50740` |
| `tests/test_context_update_hook.py` | `63c57e6a3e035ba32b40b3f94da122cf3950ca40b1f7d06af64301a24c7c1389` |
| `scripts/backup_runtime_databases.py` | `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604` |
| `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |

No tests, Git commands, network/VPS actions, child agents, implementation edits or native experiments were run. The only write is this report. All repros below are **tests to add**, not executed evidence.

## Strengths

- Explicit `online` and `quiesced` receipts prevent silent phase relabeling; the legacy two-argument data-hook path remains quiesced. The online main-inode comparison permits ordinary SQLite content changes, while quiesced execution retains before/after no-process checks and the full live signature (`1602-1647`, `1801-1823`).
- The new launcher uses fixed roles, fixed executables, fixed numerical-thread environment and AS/CPU limits. Root execution selects only the unchanged pinned stdlib backup helper; target imports/D4 stay in the app-user path (`1698-1755`).
- Online and recovery archive variables remain distinct. The main path still places the fresh quiesced archive after marker preparation and before payload application (`1959-1967`, `3525-3533`). Both full verification stages inspect the new root-private archive inode.
- Archive MANIFEST/inventory requirements and the closed report/limitation validator are retained. No helper, owning model/source, schema or mathematical contract change is present in this checkpoint.

## Additional findings

### Important 1: extraction-to-sealing handoff discards the verified inode identity

**Location:** `deploy/update_server.sh:1520-1522`; related `1493-1510`, `1615-1617`.

The extractor records and verifies `created` for the output FD, then closes that FD. When sealing begins, it assigns **a new** `created = identity(os.fstat(seal_fd))` instead of comparing the reopened file to the extracted identity. A different root-owned 0600, single-link, valid SQLite file installed at the destination in that interval therefore becomes the new baseline. Its SQLite checks may pass, and `stage` records its fresh `sealed_hash`, while `member_hash` still names the original ZIP member. No later check reconnects those two byte histories.

This is an actual identity rebaseline in the code, not merely a request for more race coverage. It violates the required continuous streamed-member/FD/path binding. Under the intended private DAC an ordinary app process cannot replace this file, so this is **not** a claimed app-to-root exploit or a witnessed production replacement; the failure case is a privileged/concurrent path replacement that the stated contract requires rejecting.

**Fix direction:** retain the extracted FD/identity through the handoff, or compare the new FD and current path to the saved extraction identity before SQLite can open it. Preserve the streamed digest binding before journal conversion; do not merely rename/recompute the baseline.

**RED to add:** with two different valid SQLite fixture images A and B, substitute B precisely on the second open of the destination (after archive integrity checks, before `seal_fd` is returned). Require rejection before SQLite opens B, no accepted `stage.json`, and no target D4 acceptance of B. Existing streaming/DELETE conversion controls must continue working. No native race was executed here.

### Important 2: the new root archive copy bypasses the resource and source-stability boundary

**Location:** `deploy/update_server.sh:2234-2239`; related `2224-2233`, `1941-1956`.

The code correctly acknowledges that chmod/chown cannot revoke an already-open application FD, but the subsequent private-inode copy is a bare `install`. It has no admitted byte ceiling, fixed captured source length, source-FD/signature continuity check, or wall limit. Both bounded root verifiers start only **after** this copy completes.

During the online phase, a process retaining a writable FD can enlarge the producer file after the producer's limits/inventory checks have finished and before the root copy starts. Even if the particular `install` implementation copies only a snapshotted length, that length is not capped by this code. The root copy can consume unreserved recovery-disk space before a later verifier rejects it. A copy stall is likewise outside the 600-second child boundary. Whether continuous append makes a particular native `install` build run indefinitely has not been tested and is not asserted as proof.

**Fix direction:** use a reviewed bounded stdlib copy inside the fixed resource/deadline envelope, from a no-follow held regular source FD into an exclusive new root-owned destination. Bind the expected length/identity, reject growth/truncation/change, enforce the admission ceiling and exact EOF, fsync, and only then pass the private copy to the existing verifiers. Keep the root-private new-inode property.

**RED to add:** a producer fixture retains an app FD, then grows the source after the producer exits but before copy. Require bounded rejection with no archive publication and no service stop. Separately exercise truncation/replacement, injected copy failure and deadline expiry. Test the root copy itself, not only the later verifier collector. This is separate from the checkpoint's acknowledged missing collector tests.

### Important 3: disk admission measures the parent, not the actual recovery archive filesystem

**Location:** `deploy/update_server.sh:3427-3433`; related `20`, `1959-1984`, `2906-2912`.

The recovery archive destination is `/var/backups/betboy-update`, but disk admission charges its archive reservations to `stat/statvfs('/var/backups')`. A pre-existing separate filesystem mounted at `/var/backups/betboy-update` is accepted by `produce_update_backup`: its checks require root ownership/private mode/no symlink, not same-device or non-mountpoint. The separate-mount rejection at `2908-2912` applies only to the scheduled backup tree `/var/backups/betboy`, so it does not close this gap.

A recovery mount with space for one accepted online archive but not the later quiesced copy can therefore pass the new admission check and fail after services are stopped. The current tests only model the three parent paths; their same-device test cannot detect this target/parent mismatch (`tests/test_context_update_hook.py:1333-1349`). This is a concrete wrong-path decision, not a missing native measurement claim.

**Fix direction:** resolve/validate the actual archive destination or its nearest verified existing parent before admission and account on that device. Alternatively explicitly reject unsupported separate recovery mounts before online capture. Keep aggregation when real consumers share a device; do not add an extra copy of the same free-byte pool.

**RED to add:** `/var/backups` has abundant space but an existing root-private `/var/backups/betboy-update` has a different device and room for only one fixture archive. Require failure before online production/service stop. Retain passing separate-sufficient-device and shared-device controls.

### Important 4: a full-backup verifier still bypasses all new limits after migration

**Location:** `deploy/update_server.sh:2708-2710`; relevant new policy/launcher `1715-1726` and call chain `3551-3553`.

`verify_backup_service_migration` directly runs the installed helper as `betboy-backup` with `--verify-only`, outside `capture_root_verifier`, `context_hook_command`, the rlimit launcher and either timeout. `scripts/backup_runtime_databases.py:3649-3656` dispatches that command to the full `verify_archive` restore/check path (`2114` onward). Thus this explicit verifier has no fixed AS/CPU/wall/aggregate-output boundary and runs after migration has started.

This is an **inherited callsite missed by the new all-full-backup-verifier resource contract**, not a claim that the checkpoint newly introduced the call. The systemd service's own timeout does not cover a separate subsequent `runuser` invocation. Scheduled archives normally omit MANIFEST, but this is still a complete restore/SQLite/authentication verifier, so omission of the large embedded-manifest allocation does not make it resource-bounded.

**Fix direction:** route this exact already-authorized verifier role through a fixed, reviewed, uid-appropriate resource/collector path without changing the installed helper or pinned unit. Do not generalize the launcher to arbitrary programs/arguments, expose the archive to the app user, or relabel a resource failure as a permitted D4 limitation. If the controller intends this callsite to be outside Task 2's all-verifier constraint, that exception must be explicit rather than claimed covered.

**RED to add:** exercise the actual shell post-migration verification function with the fixed backup principal and an output-overflow/timeout/resource-failing child. Confirm both pipeline statuses and no continued acceptance. Separately record that the rollback/fail-closed branch remains the existing durable-migration branch; do not silently restart the old app.

## Known incomplete work, not reported as novel findings

The checkpoint already acknowledges the cross-phase configuration-receipt gap, missing direct WAL producer tests, further ancestry/extraction/cleanup coverage, MemoryError classification, second-phase recovery tests, FD cleanup audit, final regressions and native evidence. Those remain open. In particular, findings 1 and 2 identify concrete code paths within related pending audit areas, rather than treating the absence of tests itself as a newly discovered defect.

The inspected recovery logic still reads only `FRESH_BACKUP`, never `PREFLIGHT_BACKUP`: old-complete recovery follows its existing code/root/unit restoration path; durable in-progress or migration-started recovery preserves staging and keeps runtime disabled (`3189-3267`). This is a static callsite observation, not an executed rollback proof. The separate context tree is preserved whenever the existing fail-closed branch avoids `safe_remove_stage`; its path is not currently included in the fail-closed log text.

## Assessment

**Ready to merge as completed Task 2: No.** This is an intentionally incomplete checkpoint with the additional Important findings above and the already documented follow-up. The report does not withdraw the checkpoint as a coherent handoff, does not claim local/native tests passed, and gives no updater repair, deployment or release approval. Task 1 live-capacity status remains HOLD; only the controller may reassign the sole writer and perform later native/release actions.
