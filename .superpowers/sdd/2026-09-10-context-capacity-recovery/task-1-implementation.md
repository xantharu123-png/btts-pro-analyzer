# Task 1 implementation: bounded complete D4 reader

Status: DONE_WITH_CONCERNS (implementation and focused Windows verification complete; independent review, Linux DAC/race/resource and real-data acceptance are controller gates).

Code commit: `b333c3c` (`fix: bound context verification memory without dropping history`).
Starting commit: `0ac56fcfa5c6a5ac87198b31ff0d24b5a0157e51`.
Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.
Branch: `codex/context-capacity-recovery-20260910`.

## Scope and implementation

- Explicit keyword-only `verify_context_database(path, input_mode="memory")`; only alternative is `sealed_file`. Unsupported values fail with RuntimeArtifactTrustError. The default keeps the old 64-MiB image ceiling and never falls back to a pathname reader.
- CLI selection is `scripts/verify_context_runtime.py --sealed-file`; unchanged default, report schema, diagnostic redaction and exit levels.
- `context_runtime_input.open_sealed_connection(path, max_bytes=...)` requires Linux, root-owned regular file with exactly one link, permissions limited to 0440, root-owned app-unwritable ancestors all the way to filesystem root, no symlinks and no SQLite companions. Every directory is opened relative to a held no-follow directory descriptor. File/ancestor descriptor and pathname identities are checked before and after SQLite's separate open; the complete file SHA256 is streamed before and after verification. DELETE-mode header and input length are checked before SQLite. The file ceiling is 1 GiB.
- SQLite is opened `mode=ro&immutable=1` only after that seal proof, query_only=ON, trusted_schema=OFF, foreign_keys=ON, 8-MiB page cache, mmap disabled, and a held read transaction. Root ownership/DAC, not a caller assertion, justifies immutable mode. The orchestrator does not nest BEGIN.
- `VerifiedArtifactMapping` and `VerifiedReceiptMapping` are read-only transaction-backed mappings. Membership and iteration query identities without decoding values. Each value lookup invokes the owning decoder and retains no value cache; caller mutations cannot poison later reads. Ended/closed connections fail instead of returning cached data. The caller is contractually responsible for keeping the same transaction open throughout use; the mappings do not install authorizer/trace callbacks or mutate a writer's transaction controls.
- Full A1, physical content and receipt validation is retained, including inactive/unreferenced rows. Orphan contents use a LEFT JOIN antijoin so SQLite can build an automatic transient index rather than a correlated full scan. Protected unopened finals retain opaque hash/outer-only handling. An ordinary receipt corrupted beside protected finals still fails verification.
- The narrow permitted semantics adjustment replaces the decoded `known` artifact dictionary with an identity-only lazy subset. Owning D2 validators, plans/configuration work and report mathematics are unchanged; no dataset/evaluator source hash whitelist was altered.
- Tennis originals are verified serially and return small immutable descriptors containing artifact identity and shared mapping references, not base/history/state caches. Snapshot replay reconstructs and releases the exact complete causal tour history. Each decoded row goes through the unchanged owning tuple selector; all selected rows are globally sorted with its exact observed_at/digest order. No participant pruning, latest-only shortcut, omitted native revisions or changed numerical replay. Original base distribution validation remains present even for publications without snapshots.
- Sealed-file history admission is 256 MiB of canonical selected input bytes per complete replay. Failure is typed RuntimeArtifactTrustError, never truncation. The old memory input and rollback writer path do not acquire this new history budget, preserving admission of old valid <=64-MiB inputs. MemoryError at orchestration/transport boundaries is converted to a typed trust/resource failure; no automatic mode change.
- `_verify_connection(connection)` still returns the real dictionary with report/manifests/chain/artifacts/tables. Its old one-argument call form is preserved for the default reader and authorized rollback writers; an optional history_max_bytes keyword is used only for explicitly selected sealed input. The dictionary's artifact inventory is now a Mapping valid during the held transaction.

Files committed: context_runtime.py, context_runtime_tennis.py, context_runtime_input.py, context_runtime_inventory.py, context_runtime_semantics.py, scripts/verify_context_runtime.py, tests/test_context_runtime_capacity.py. Existing backup tests were exercised without editing them.

## TDD and exact local evidence

Used the test-driven-development skill and its writing-good-tests reference: tests preceded implementation, the missing interfaces were observed RED, then owning storage and replay behavior was implemented. Used verification-before-completion before the commit. No subagents or full-suite run.

All commands below ran in the worktree above with:

```powershell
& C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -B -m pytest <tests> -q -p no:cacheprovider --basetemp=<directory>
```

1. RED, `<tests>=tests/test_context_runtime_capacity.py`, directory `.pytest_tmp/capacity-red`: **6 failed, 3 passed in 2.11s**, exit 1. Explicit input_mode was absent (TypeError), CLI --sealed-file was unrecognized (exit 2 instead of typed exit 1), inventory module/replay descriptor/history helper did not exist (ModuleNotFoundError). The three existing-contract passes covered the old cap and unreferenced corruption.
2. Expanded RED, same tests, `.pytest_tmp/capacity-red-02`: **7 failed, 3 passed, 13 skipped in 1.91s**, exit 1. Added the absent strict-reader platform entry point. The initial Linux-only tests were skipped on Windows; after the controller clarified root must not import pytest/app/model code, these were replaced with nonroot tests against externally root-staged fixtures. They were never executed as root.
3. Initial GREEN attempt, capacity tests, `.pytest_tmp/capacity-green-01`: **1 failed, 9 passed, 13 skipped in 61.47s**. Failure was a test fixture generating a later prediction before its earlier cutoff, correctly rejected by the existing prediction revision owner. The fixture was corrected to generate earlier then later decisions; production chronology was not relaxed.
4. Backup regression, `tests/test_context_runtime_backup.py`, `.pytest_tmp/capacity-backup-01`: **5 failed, 88 passed, 3 skipped in 11.12s**. Existing race tests wrapped `_verify_connection(connection)` and rejected the new unnecessary keyword in default memory mode. Fixed the default invocation to retain the exact old one-argument form, not the tests.
5. Broad focused regression, `.pytest_tmp/capacity-green-02`, exact tests:

```text
tests/test_context_runtime_capacity.py
tests/test_context_runtime_backup.py
tests/test_context_runtime_semantics.py
tests/test_context_runtime_transport.py
tests/test_context_runtime_tennis_live.py
tests/test_tennis_status_v3.py
tests/test_tennis_v3_model_transport.py
```

Result: **272 passed, 16 skipped in 412.57s**, exit 0. This run had collected the older Windows-skipped Linux fixture tests; its app/semantic/rollback tests all ran. No network/provider calls were made by this implementation task.

6. Updated standalone capacity run, `.pytest_tmp/capacity-green-03`, additionally `--durations=3`: **10 passed, 9 skipped in 61.78s**, exit 0. Protected-final synthetic packet creation/verification dominated at 59.62s. This and the final run explicitly set OPENBLAS_NUM_THREADS, OMP_NUM_THREADS, MKL_NUM_THREADS and NUMEXPR_NUM_THREADS to 1 in the child shell.
7. Self-review RED: `tests/test_context_runtime_capacity.py::test_no_originals_do_not_require_original_replay_code`, `.pytest_tmp/capacity-red-no-originals`: **1 failed in 1.48s**, exit 1. The initial serial rewrite requested original code variants even for databases with no originals. Fixed to request variants only upon the first actual original.
8. Final current-code focused run, `.pytest_tmp/capacity-final-local`, additionally `--durations=5`, exact tests:

```text
tests/test_context_runtime_capacity.py
tests/test_context_runtime_backup.py
tests/test_context_runtime_tennis_live.py
tests/test_tennis_status_v3.py
tests/test_tennis_v3_model_transport.py
```

Result: **192 passed, 12 skipped in 80.37s**, exit 0. Includes the new no-originals regression, protected-final membership and complete D4 guard, unrelated ordinary corruption beside those finals, fresh mutable mapping values, closed-connection failure, two original cutoffs, history budget failure/recovery, exact snapshot receipt checks, complete historical native retractions and actual prior bilateral source history. Nine skips are the externally staged Linux DAC fixtures; three are existing unavailable Windows platform checks.

`git -c core.autocrlf=false diff --check` and staged `diff --cached --check`: exit 0, no output. Exact files were staged; no add-all/reset/clean was used.

## Unchanged protected code

`git -c core.autocrlf=false diff --name-only 0ac56fc -- context_models tennis scripts/stage_runtime_databases.py` returned no paths.

Actual on-disk protected helper SHA256: `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

No predictor, feature, dataset, evaluator or training owner was modified. No changes to cricket, models, odds, forecasts, DB schemas, activation, source access, original code hash equivalence, writer rollback permissions, updater, VPS, secrets or other SDD directories. The controller-owned untracked live-capacity-evidence report was left untouched.

## Exact Linux fixture contract for controller

Run pytest and every app/model import as the application user, never root. Root staging must only copy exact bytes and perform reviewed standard-library filesystem/permission operations. These tests do not invoke sudo or spawn a privileged application interpreter.

An already generated valid seed containing exactly two tour artifacts and one manifest is available at:

`C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/.pytest_tmp/capacity-green-03/test_explicit_memory_mode_pres0/context.db`

Size: **24,576 bytes**. SHA256: **ee932b44a72687ca85ce72329c8c8f4cd004f305b19da9e17b2e9171fa2269b3**. It was produced unprivileged by the existing seeded fixture, not by a root model import. Alternatively generate `seeded(Path(...))` from tests/test_context_runtime_backup.py as the app user in a disposable application-owned directory, then root-copy it.

Set `CONTEXT_CAPACITY_TEST_ROOT` to an existing root:betboy 0750 directory under `/var/lib` or `/run`, with root-owned app-unwritable ancestors. `/tmp` and `/var/tmp` are intentionally invalid ancestors. Populate the following names before starting unprivileged tests; all normal subdirectories are root:betboy 0750 and regular copies root:betboy 0440:

| Relative file | Difference from valid seed |
| --- | --- |
| valid/context.db | Exact seed, one link, no companions |
| hardlink/context.db | Exact seed plus a second hardlink, nlink=2 |
| symlink/context.db | A symbolic link to valid/context.db |
| owner/context.db | App-owned file, even with 0440 permissions |
| mode/context.db | root:betboy 0640 file |
| ancestor_mode/context.db | Its containing directory is root:betboy 0770 |
| sidecar/context.db | Empty context.db-wal companion exists |
| wal/context.db | Seed copy whose header offsets 18 and 19 are 2, then sealed 0440 |

The budget test uses the valid seed with max_bytes=1. Missing fixture files are asserted before expected rejection; absence cannot falsely pass a negative case. Positive checks prove app OS write/rename denial, query-only SQLite write denial, held transaction, and exact memory/sealed report equality. The valid memory comparison is safe because this fixture is only 24 KiB.

Controller must separately execute the real concurrency harness for ancestor replacement, file replacement, same-inode byte changes and companion creation between precheck/SQLite open and final verification. A root standard-library actor may mutate only disposable fixtures; the verifier remains app-user code. The implementation has pre/post descriptor/path/ancestor/SHA checks, but these races were not physically exercised on Windows. No mocked Linux metadata is being claimed as DAC proof.

## Concerns and release gates

- This task has **no Linux-positive, real >64-MiB, live-data RSS/CPU or growth-profile acceptance claim**. The nine Linux tests require the external fixtures above. The controller's separate baseline evidence is not this implementation's performance proof.
- Zero decoded-value caching reduces retained inventory and cutoff history memory, but serial complete reconstruction increases repeated owning decoding/validation. Actual CPU and peak RSS must be measured on the new revision against the exact same fresh backup and multiple growth generations. Do not raise the candidate limits to force acceptance or prune history.
- Mappings require their caller to preserve the same held transaction. They reject access after closure or an ended transaction. Deliberately ending a transaction and starting another before reusing an old mapping violates that caller contract; no intrusive trace/authorizer transaction-generation mechanism was installed in rollback writers.
- Existing owning D2 working structures (experiment plans, configs, physical outer metadata and one current fit/replay) are not redesigned. The D4 duplicate decoded inventory cache was removed; the model-owning files and hashes remain unchanged.
- Independent spec/quality review is the controller's responsibility. No full suite, push, remote execution, updater change or production mutation was performed here.
