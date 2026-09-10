# Task 2 checkpoint 1 - NOT COMPLETE / NOT RELEASE APPROVED

Date: 2026-09-10. Production-edit base: `73e6abd34376286e8b02b2326b25e4143e7e691d`. Earlier RED-only commit: `624280d`.

Controller requested this coherent, tested checkpoint so Task 1 can temporarily regain the sole implementation-writer slot. This report is not a Task 2 completion report, independent review, native resource result, or deployment authorization. After committing these exact three files, the implementer is read-only until the controller reauthorizes writes/testing.

## Changes currently implemented

- `deploy/update_server.sh` streams the chosen context ZIP member in at most 1-MiB reads, enforces the candidate 1-GiB input cap, verifies length/CRC/digest/header, and binds output descriptors/path identities before SQLite DELETE sealing and 0440 permissions. It no longer reads the entire sealed DB merely to inspect its header.
- A separate strict `/var/lib/betboy-context-update.XXXXXXXX` root-owned tree contains distinct `online` and `quiesced` hooks. Git/rollback staging stays under `/var/tmp`. Cleanup checks this exact private tree's saved identity and is invoked only through the existing safe-cleanup paths; existing fail-closed recovery paths continue preserving staging.
- Explicit phase receipts distinguish online same-inode SQLite content changes from the unchanged strict quiesced live signature. Unknown phases and phase relabeling fail. The legacy two-argument internal data-hook form remains strictly quiesced; production call sites supply explicit phases.
- Existing configuration/code-path legacy proof is combined with existing authentication state. Only keyless AND proven contextless AND markerless legacy retains the old post-quiesce first-migration route. No key/marker is fabricated online. Existing in-progress markers remain allowed.
- A checked, root-private temporary stdlib launcher has fixed role/command selection, fixed single-thread environment, 2-GiB AS and 300-second CPU bounds. Its source is written successfully before use; unchecked process-substitution input is not used to launch verifiers. The launcher is not installed as a new permanent helper.
- App-user dependency and target D4 execution remain separated from root stdlib transport/helper execution. D4 uses `--sealed-file`. The dependency probe requires Linux and the explicit sealed reader rather than merely successful deserialize support.
- App and root verification collectors retain both pipeline statuses, impose 600-second child/610-second collector wall bounds, reject output above 1 MiB and reject known timeout/resource signals. Inline full-backup verification also sets AS/CPU limits; the unchanged pinned backup helper is launched under the fixed resource wrapper with `--recovery-mode`.
- The existing archive producer is factored into explicit phase/work/output/source-HEAD inputs. `PREFLIGHT_BACKUP` never overwrites `FRESH_BACKUP`. Online capture precedes `UPDATE_STARTED`/service stops/marker preparation; quiesced capture remains after the existing migration boundary and before payload application.
- Before verification/publication the produced archive is copied to a separate root-owned inode, because directory access revocation cannot revoke an already-open application FD. Both complete-archive verification stages inspect that private copy.
- Producer code compares complete DB path/principal identities before/after capture while allowing regular same-file size/time changes. It keeps authentication bytes/metadata stable across capture. Per-database snapshots are not described as one cross-database transaction.
- Disk admission sums reservations by actual filesystem device, including `/var/lib`, both archives, retained work copies and restore space. It never counts one device's free bytes independently for each consumer.

## Verified local evidence

Command:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest tests/test_context_update_hook.py -q -p no:cacheprovider --basetemp=.pytest_tmp/task2-checkpoint-01 --tb=short --junitxml=.pytest_tmp/task2-checkpoint-01.xml
```

Result: **262 passed in 33.56s**, exit 0. Bash syntax (`C:/Program Files/Git/bin/bash.exe -n deploy/update_server.sh`) and `git -c core.autocrlf=false diff --check -- deploy/update_server.sh tests/test_context_update_hook.py` also returned 0.

The original RED-only report records 9 real expected failures and 1 passing quiesced control; the existing hook baseline was 239 passed. Intermediate integration runs included expected test-interface updates and Windows simulation corrections; they are not new accepted RED evidence. This checkpoint does not claim that every added behavior has completed its own RED/GREEN proof.

Current tests cover real ZIP/SQLite streaming (including a real 65-MiB payload), phase-sensitive committed insertion, unknown/relabelled phases, shell online-before-stop ordering, separate archive/hook identities, private-mount and same-device disk decisions, output overflow, thread environment, launcher role/fixed-command/limit decisions, exact keyless legacy boundary, prior resume predecessor-vs-backup-HEAD behavior, and the inherited closed report/limitation regressions.

Windows ownership/resource modules are explicitly simulated only at the Linux boundary. The helper digest is read from real unchanged bytes. These tests are not Linux DAC, real AS/CPU enforcement, full producer capture, target D4 performance, or VPS acceptance.

## Required follow-up before Task 2 completion

1. **Known integration gap from final read-only self-review:** `configure_context_phase` currently creates the second hook from current configuration. Add a cross-phase comparison against the original online configuration receipt so a root-side environment/path configuration change between accepted online replay and quiesce cannot silently become the new baseline. The old updater bound one pre-downtime receipt across this interval. Add a RED test first. The intentional post-quiesce migration-marker change must remain allowed; do not copy online authentication equality onto the quiesced marker.
2. Run the actual factored full producer against a real SQLite WAL fixture with commits during capture, and test DB addition/removal/replacement, ancestor/principal changes, authentication replacement/mutation/appearance, and actual in-progress resume source HEAD. Its new inventory/capture implementation is not directly exercised by the current shell recording harness.
3. Add strict ancestry and cleanup decision/race tests, including sticky ancestors, root/group/write/hardlink failures, exact path replacement, directory link-count changes after adding phase children, and fail-closed evidence preservation. Native owner/app-user verification remains a controller Linux gate.
4. Expand extraction negatives for the exact 1-GiB boundary, CRC/truncation/length mismatch, descriptor/path and ancestor replacement, and failure before any accepted sealed proof. A failed streamed hash may leave a root-private unsealed candidate; unlike the old whole-image reader, writing necessarily precedes knowing its complete digest.
5. Add real root collector failure cases and fixed-launcher generation failure cases. Audit every resource-failure classification, including MemoryError exits that are not a timeout/signal. Do not turn any such failure into an allowed limitation.
6. Add second-fresh-backup/second-D4 failure recovery tests. Confirm the existing old-complete rollback and durable in-progress fail-closed branches still use only the quiesced `FRESH_BACKUP`, not the accepted online archive.
7. Remove unused implementation remnants such as `live_identity` and obsolete shell disk locals during the final focused cleanup; re-audit held-FD closure on all exception paths and cross-phase environment/ancestor binding.
8. Rerun all focused hook regressions and syntax after the follow-up, then obtain independent spec/quality review. Controller still owns native full-backup peak/RSS, current/growth D4 evidence, full repository suite, push, updater-only repair, and any eventual ordinary application update.

## Exact file identities at this checkpoint

- Updater SHA-256: `91917ed4009b63ae77ddc04ed68fc2767fef483a69793dd2ae45d2f75df50740`.
- Hook test SHA-256: `63c57e6a3e035ba32b40b3f94da122cf3950ca40b1f7d06af64301a24c7c1389`.
- Unchanged `scripts/backup_runtime_databases.py`: `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604`.
- Unchanged `scripts/stage_runtime_databases.py`: `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

Only the two Task 2 source/test files and this checkpoint report are staged. Controller-owned plan, progress and live-evidence WIP remain excluded. No helper, owning source/model/mathematics, cricket behavior, history, production database, credential, permanent installed executable or VPS state has been changed by this work.
