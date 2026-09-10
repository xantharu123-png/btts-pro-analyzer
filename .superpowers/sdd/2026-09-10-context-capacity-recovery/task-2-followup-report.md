# Task 2 follow-up - submitted for independent acceptance

Date: 2026-09-10. Base: `b389b2caaabfd0ba5d4584432f97eaab5f537e36`. Code commit: `bdd5731b56e19e6da3b2312abf8ef3cbf971beb4`. Earlier incomplete checkpoint: `43bfd0d276b36465865c9ddac5a3937c61886c1c` and `task-2-checkpoint-1.md`.

This is a coherent implementation/test handoff, not independent Task 2 acceptance, native capacity acceptance, Task 3 installation, VPS repair, deployment, or model/frontend approval. The controller requested return of the sole-writer slot for further Task 1 performance work. No further edits or tests by this implementer after the report commit without renewed authorization.

## Review-driven changes

- The quiesced configuration must equal the original online receipt, revalidated against current environment/payload/path configuration. Authorized migration-marker preparation is not incorrectly compared to online authentication bytes.
- Extraction-to-sealing now keeps the original extraction inode identity and compares its digest to the extracted member digest before SQLite opens it. It no longer rebaselines a replacement inode; descriptors close on error, and failed SQL sealing cannot execute the successful-seal permission path.
- The completed producer emits one closed receipt containing path, size, SHA-256 and complete signature. Root independently opens the app-owned source with no-follow/nonblocking flags, compares the receipt, streams exactly the admitted bytes to an exclusive independent root inode in <=1-MiB reads, checks EOF/digest/source identity, fsyncs and validates its own destination. No bare `install` archive copy remains. App ownership of the source inode is retained so root does not invalidate its completion signature by chowning it; the containing work directory is revoked before root copying.
- Copy admission and the producer's per-file limit use `2 * initial apparent database/sidecar bytes + 64 MiB`. The producer also bounds total uncompressed snapshot bytes during SQLite backup progress and after each completed snapshot. A progress callback follows at most 256 pages, at most 16 MiB with SQLite's maximum page size, inside the existing safety margin. This prevents highly compressed ZIP size from substituting for restore/snapshot disk admission. The existing 1-GiB sealed context cap remains separate.
- Disk reservations remain summed by device. The recovery reservation uses the actual existing `/var/backups/betboy-update` mount, or `/var/backups` only if that destination does not yet exist. The seal reservation includes admitted source growth. Existing rollback/private-copy/restore reservations remain conservative simultaneous high-water reservations.
- The inherited post-migration full verifier now executes a fixed `backup-service` launcher role as exactly the configured nonroot `betboy-backup` UID, using only the installed fixed helper path and its unchanged digest, without recovery-mode overrides. The root-private context tree is not exposed to the backup account: fixed stdlib launcher text is supplied over stdin, with producer, child and collector statuses all retained. It has the same AS/CPU/wall/thread/output limits as the other complete verifiers.
- MemoryError/closed capacity diagnostics and file-size signal status 153 now produce immediate typed resource rejection, in addition to the existing timeout/CPU/OOM statuses. No report limitation was added. Ordinary nonzero verifier exits still reach the existing strict caller/report checks.
- The root-helper unit metadata simulation is now explicit on Linux as well as Windows. Real helper bytes still determine the pin. This addresses the controller's ordinary-SSH-user Linux fixture failure without chowning any protected helper or running application tests as root.
- Removed unused `live_identity` and obsolete disk locals. Helper, owner/source/model/mathematics/schema and closed D4 report/12-limitation contracts are unchanged.

## Concrete RED evidence

All artifacts below are local ignored `.pytest_tmp/` test artifacts, not deployment evidence.

- `task2-followup-red-01.xml`: 3 expected failures, 262 deselected, 0.57s: changed online environment was rebaselined, replacement extracted SQLite was accepted for sealing, and a full actual recovery mount borrowed its parent's free space.
- `task2-followup-red-02.xml`: 2 expected failures, 265 deselected, 1.00s. The actual old transfer statement copied a source enlarged through a retained FD after completion (17 to 19,473 bytes); the actual old post-migration route accepted a child emitting over 1 MiB. Account assignment alone was simulated for the copy. The replacement test now exercises the new receipt-bound function, not a stale source-string lookup.
- `task2-followup-red-04.xml`: 4 expected failures and 4 passing CPU/wall controls, 295 deselected, 3.36s. MemoryError and file-size status were not immediately typed by app/root collectors. This was a classification-boundary gap, not evidence that production's subsequent report/caller checks accepted a failed D4.
- `task2-followup-red-05.xml`: 1 expected failure, 312 deselected, 0.45s. A real SQLite snapshot expanded beyond a 64-KiB fixture admission while its highly compressible ZIP was only 1,365 bytes, and the producer still emitted a receipt. Unix rlimits are simulated in this unit fixture; the new total-snapshot callback is exercised with real SQLite pages.

Intermediate fixture-development failures (missing mocked resource constants, Windows open-file replacement restrictions, one test syntax typo, CRLF diagnostic matching and a harness replacement mismatch) were corrected and are not counted as RED evidence. DB removal/replacement is performed late in actual archive creation, after source descriptors close, so these cases mutate real paths portably rather than treating Windows sharing violations as successful security rejection.

## Final verification

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/task2-completion-01 --tb=short --junitxml=.pytest_tmp/task2-completion-01.xml
```

Result: **313 passed in 39.24s**, exit 0. `C:/Program Files/Git/bin/bash.exe -n deploy/update_server.sh` and `git -c core.autocrlf=false diff --check -- deploy/update_server.sh tests/test_context_update_hook.py` also returned 0 on these exact bytes.

Coverage added since the 262-test checkpoint includes complete producer real WAL commits, DB add/remove/replacement and directory-principal change, key replacement/mutation and marker mutation, actual source HEAD in an in-progress archive, receipt-bound independent copy success/growth/truncation/replacement/digest/deadline/size, strict sealed ancestors including sticky rejection, identity cleanup preserving replacements while permitting phase-child link-count changes, generation/collector failure, fixed backup-principal roles, output/resource failures, second-phase backup/D4 stop-before-apply, and actual old-complete versus durable fail-closed recovery. ZIP CRC/truncation and inclusive bound decisions use real ZIP/SQLite bytes. Existing 65-MiB streaming and closed report/legacy/resume regressions remain green.

The exact 1-GiB comparison is checked by its literal plus a scaled boundary using a real small SQLite file; this unit run does not allocate a 1-GiB fixture. Metadata, UID and resource calls are explicitly simulated only at Unix boundaries. Unit checks are not native DAC/resource enforcement or adversarial concurrency proof for every possible filesystem race.

## Remaining gates / handoff

1. Independent spec/quality review of combined Task 2 checkpoint plus this follow-up; the checkpoint review was not acceptance of this later patch.
2. Controller's current-source Linux hook rerun, actual root/app/backup-principal DAC checks, real AS/CPU/wall/output enforcement, full producer/private-copy/complete-verifier peak measurements and retained-FD/ancestor race checks. The earlier Linux 261-pass/1-fixture-fail result was for the old checkpoint, not these bytes.
3. Native current/growth Task 1 replay performance and exact full archive transport capacity. Ordinary-WAL success here is per-database snapshot consistency, not a cross-database transaction claim.
4. Controller-owned repository-wide gates, any installer/updater-only repair and subsequent ordinary app update remain pending. No full suite, network, push, Task 3, VPS or production data changes were performed by this implementer.

Only the two authorized Task 2 files were staged in the code commit. This report is a separate exact-file documentation commit. Root-owned plan/progress/live-evidence and review/diff WIP remain excluded.

## File identities

- `deploy/update_server.sh`: `666014acdac4c200fb2efa9e9c67f42d6ef768c406715897bab9acee82e242ce`.
- `tests/test_context_update_hook.py`: `d92c96ed31f6202170b52cc925dcac2b4c76125c7811114e577ccd6de9af259e`.
- Unchanged backup helper: `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`.
- Unchanged staging helper: `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
