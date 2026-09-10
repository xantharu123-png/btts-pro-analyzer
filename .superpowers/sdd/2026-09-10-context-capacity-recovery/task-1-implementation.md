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
- `VerifiedArtifactMapping` and `VerifiedReceiptMapping` are read-only transaction-backed mappings. Membership and iteration query identities without decoding values. Each value lookup invokes the owning decoder and retains no value cache; caller mutations cannot poison later reads. Fix round 1 below enforces the original transaction lifetime through owned tracked connections: ended/closed transactions cannot revive old views after a restart. No authorizer/trace callback is installed and writer SQL semantics are unchanged.
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
- The initial transaction-revival defect was corrected in fix round 1 below; it is no longer delegated to a caller precondition. Every view retains and checks the tracked connection's original generation. Independent scoped re-review remains required.
- Existing owning D2 working structures (experiment plans, configs, physical outer metadata and one current fit/replay) are not redesigned. The D4 duplicate decoded inventory cache was removed; the model-owning files and hashes remain unchanged.
- Independent spec/quality review is the controller's responsibility. No full suite, push, remote execution, updater change or production mutation was performed here.

## Fix round 1: permanently enforced transaction lifetime

Independent review identified a valid Important defect: checking only in_transaction allowed an old view, including its protected-receipt classification, to revive after COMMIT/BEGIN or ROLLBACK/BEGIN. This fix implements the promised lifetime instead of relaxing the plan or documenting away the failure. The review-reception skill was used to check the counterexample and the actual rollback caller before editing.

Fix code commit: `41067c0` (`fix: bind verified inventory to SQLite transaction generation`), based on `59b001d`.

### Implementation

- Added the narrowly scoped `context_runtime_transaction.py` with TrackedConnection and TrackedCursor. Only the connection factories owned by the memory reader, strict sealed reader and authorized `_open_database(..., writable=True)` are changed. `model_artifacts.py` remains untouched.
- Each ordinary statement execution observes SQLite's transaction state, including failures that implicitly roll back. Connection shortcuts return tracked cursors; cursor execute/executemany paths are observed too. Cached SQL needs no re-prepare event, SQL parsing or rewritten statements.
- A monotonic generation explicitly invalidates views at commit/rollback, context-manager exit, close, image replacement and scripts. executescript is conservatively a new view lifetime even if its whole end/restart occurs inside one call and leaves in_transaction true. This also avoids relying on which transaction policy makes a script implicitly commit.
- Python 3.12 autocommit and isolation_level assignments are observed directly, so attribute-driven commits/restarts cannot evade lifetime invalidation. Transaction-policy assignments conservatively invalidate prior views; no callback is commandeered.
- Verified mappings reject raw untracked SQLite connections. They store the original generation and require it on lookup (including missing keys), length, membership and each iterator step. Artifact subset views propagate the same check, including already-started iterators. A newly constructed view in a later legitimate transaction is permitted; an old view never revives.
- No global trace/authorizer hooks, trusted booleans, source/model edits or SQL transaction-semantic changes. Deliberate direct invocation of base-class C methods to bypass subclass dispatch is outside the normal consumer API, as explicitly scoped by the controller; no global monkeypatching was added to police hostile in-process Python.
- Existing injected backup test subclasses now inherit TrackedConnection and replace the supplied factory keyword. Their original read-only, race, failure-after-audit and closure assertions remain intact. Direct mapping fixtures explicitly opt into the tracked factory; the raw-connection rejection test intentionally does not.

### RED/GREEN evidence

All commands use the same worktree and quality Python as above, `-B -m pytest`, `-q -p no:cacheprovider`; no broad semantic suite or full suite was rerun.

1. RED: `tests/test_context_runtime_capacity.py -k 'transaction_generation or untracked_connections' --basetemp=.pytest_tmp/capacity-r1-red`: **16 failed, 20 deselected in 1.90s**, exit 1. Reproduced missing lifetime rejection for method and SQL COMMIT/ROLLBACK, cursor SQL, a shortcut-returned cursor, connection/cursor executescript, context exit, connection/cursor executemany implicit rollback, isolation_level=None, closed subset views, and acceptance of an untracked raw connection. Failures were actual `DID NOT RAISE` against the old implementation, not missing-module errors.
2. Initial GREEN, same selection, `.pytest_tmp/capacity-r1-green-01`: **16 passed, 20 deselected in 1.58s**, exit 0.
3. Targeted contracts plus exact backup/rollback regressions: `tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py -k 'not lazy_membership_does_not_decode_unopened_final' --basetemp=.pytest_tmp/capacity-r1-green-02`: **119 passed, 12 skipped, 1 deselected in 12.65s**, exit 0.
4. Added top-level SAVEPOINT RELEASE, ended-without-restart and Python 3.12 autocommit=False commit/rollback/context-exit end+automatic-restart cases. Same two test files and selection, `.pytest_tmp/capacity-r1-final`: **124 passed, 12 skipped, 1 deselected in 12.84s**, exit 0. The 12 skips are the same unavailable Linux fixture/Windows-platform gates, not lifecycle skips.
5. Added the controller's exact autocommit=True then autocommit=False property regression. `tests/test_context_runtime_capacity.py -k 'transaction_generation or untracked_connections or pep249' --basetemp=.pytest_tmp/capacity-r1-setters`: **22 passed, 20 deselected in 1.86s**, exit 0. All method/SQL boundary cases run twice to exercise cached identical boundary SQL with unchanged data. Artifact, ordinary receipt, protected receipt and subset views all remain permanently invalid after the original generation ends; protected-body decoding is guarded.
6. The one existing actual unopened-final test was run separately, not the large semantic suite: `tests/test_context_runtime_capacity.py::test_lazy_membership_does_not_decode_unopened_final --basetemp=.pytest_tmp/capacity-r1-protected-final`: **1 passed in 60.69s**, exit 0. It guards the real owning final-body decoder, complete D4 validation and rejection of unrelated ordinary corruption beside those protected finals.

`git -c core.autocrlf=false diff --check` and staged diff check: exit 0. `git -c core.autocrlf=false diff --name-only 59b001d -- model_artifacts.py context_models tennis scripts/stage_runtime_databases.py`: no paths. Only six exact code/test paths were committed. Controller edits to progress/plan and untracked review/preflight/evidence files were not staged or altered by this fix.

Scoped re-review is requested. All previously identified Linux physical race, >64-MiB, real-data/growth RSS/CPU and deployment gates remain controller-owned and unclaimed.

## Approved performance refinement: bounded immutable whole-history reuse

Code commit: `c3bac37` (`perf: reuse bounded immutable Tennis replay histories`), based on the controller-approved plan refinement `d488350`. The controller's native diagnosis showed that repeated complete history selection exceeded the candidate CPU envelope, despite much lower retained memory. This appendix records local implementation evidence, not native performance acceptance. The approved refinement permits bounded encoded reuse; it does not permit decoded-object caching, an incomplete physical validation pass, cutoff filtering, or changes to owning model/selector code.

### Implementation and correctness contract

- Added only the narrow `context_runtime_history_cache.py`, wired in `context_runtime_tennis.py`, and amended `tests/test_context_runtime_capacity.py`. No changes to `context_runtime.py` were needed.
- One cache belongs to the exact verified receipt mapping and its original tracked transaction generation and `total_changes`. Different mapping identity, transaction end/restart, closure, or a same-transaction write permanently invalidates it and clears entries. It cannot silently rekey after mutation. Even `UPDATE ... SET source=source` invalidates through `total_changes`.
- Keys are canonical cutoff plus tour within that pinned inventory. Each stored value contains immutable canonical bytes for every row of a completed, sorted owning-selector history. Every hit JSON-decodes fresh nested objects and returns an actual tuple. Neither cold nor warm consumer mutations can poison later consumers. Numerical replay, ordering, causal references and owning tuple semantics remain unchanged.
- `_cold_replay_history` retains the previous reconstruction body unchanged. A miss, eviction or oversized cache entry reruns that complete path. All physical receipt validation still precedes replay; cold selection still checks unrelated/future receipt integrity and owning both-tour typed validation before its tour filter. No future/cutoff inventory filter or trusted receipt decoder was introduced.
- The candidate cache budget is 64 MiB of aggregate canonical bytes, including admitted pending bytes and existing entries. LRU eviction maintains that bound while building; oversize bypasses without rejecting valid history. Entry metadata is additionally bounded to 32 entries, including zero-byte empty histories. Encoding uses one current-row work buffer, not an additional whole-history JSON blob. The canonical budget is not a claim that total process RSS or Python object overhead is 64 MiB.
- Partial/failed encoding is never published. Separate complete-history admission remains 256 MiB and is enforced on both misses and hits. Cache capacity does not change input admission or truncate lineage.
- Before any cache lookup, the unchanged owning selector is invoked on an empty tuple to validate cutoff/tour argument types cheaply. This preserves rejection of a string cutoff on warm hits as well as cold calls.
- Each verification shares the cache across its original and snapshot descriptors. It is constructed only when live Tennis originals exist and the inventory is a verified mapping; legacy empty-inventory failure behavior is preserved. Public D4 report fields are unchanged.

### Private diagnostics for controller measurements

`EncodedHistoryCache.stats` returns a fresh dictionary containing `hits`, `misses`, `stores`, `evictions`, `bypasses`, `peak_bytes`, `bytes`, `pending_bytes`, `entries`, `entry_bytes` and `max_bytes`. The counters expose no decoded histories and can be observed in an isolated diagnostic subclass of the class imported by `context_runtime_tennis`; `LiveReplayDescriptor.history_cache` also identifies the per-verification instance while descriptors are held. Tests observe one real verifier cache and confirm two original misses followed by two snapshot hits. A synthetic eight-consumer/two-cutoff test confirms exactly two cold reconstructions and six hits. These are local operation counts, not predictions that a native fixture necessarily fits the cache.

### Focused TDD and verification evidence

All commands ran in the designated Windows worktree with `C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -B -m pytest`, `-q -p no:cacheprovider`. The larger focused commands set child-process `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `NUMEXPR_NUM_THREADS` to `1`. No full suite or large semantic suite was run.

1. RED: `tests/test_context_runtime_capacity.py -k encoded_history --basetemp=.pytest_tmp/capacity-cache-red`: **12 failed, 42 deselected in 4.34s**, exit 1. The proposed cache module/interface was absent; the tests defined the new behavior before implementation.
2. First implementation pass, same selection, `.pytest_tmp/capacity-cache-green-01`: **10 passed, 2 failed, 42 deselected in 4.26s**. The corruption fixtures correctly reached owning `ContextIntegrityError`, while their initial expected class was the wrong outer artifact exception. Corrected those test expectations and used the owning canonical timestamp formatter for the future-clock fixture; no production validation was relaxed.
3. Expanded cache contracts, same selection, `.pytest_tmp/capacity-cache-green-02`: **15 passed, 42 deselected in 4.85s**, exit 0.
4. Targeted capacity, backup/authorized rollback and live Tennis files: `tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py tests/test_context_runtime_tennis_live.py --basetemp=.pytest_tmp/capacity-cache-final --durations=5`: **178 passed, 12 skipped in 83.25s**, exit 0. This includes the real `test_lazy_membership_does_not_decode_unopened_final` (60.89s): two replay consumers use the cache with the owning protected-final decoder guarded, and unrelated ordinary corruption is still rejected.
5. Controller review identified a warm-input argument mismatch. Added `tests/test_context_runtime_capacity.py::test_encoded_history_warm_hit_rejects_string_cutoff --basetemp=.pytest_tmp/capacity-cache-args-red`: **1 failed in 1.73s**, exit 1, actual `DID NOT RAISE ContextContractError`. This independently proves the bug before the owning empty-input argument validation fix.
6. After that fix: `tests/test_context_runtime_capacity.py -k encoded_history --basetemp=.pytest_tmp/capacity-cache-args-green`: **16 passed, 42 deselected in 5.02s**, exit 0.
7. Final current-code focused rerun: `tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py tests/test_context_runtime_tennis_live.py -k 'not lazy_membership_does_not_decode_unopened_final' --basetemp=.pytest_tmp/capacity-cache-current-final`: **178 passed, 12 skipped, 1 deselected in 22.97s**, exit 0. The already exercised minute-long actual protected-final case was not rerun after the cheap argument-type fix. The 12 skips are nine external Linux fixture gates and three existing Windows-platform skips.

The cache matrix covers exact eight-consumer parity; nested mutation isolation; aggregate pressure, LRU and oversize cold bypass; transaction restart/closure, different inventory and same-transaction writes; cold/warm history admission and failed-build nonpublication; malformed future/unrelated receipt and typed opposite-tour rejection; empty-history metadata bounding and separate tour keys; actual original/snapshot reuse; and the actual protected-final decoder guard. Interrupted second-row encoding deliberately raises `MemoryError`, leaves no partial entry or pending charge, and the retry reconstructs the complete history.

### Scope verification and remaining gates

`git -c core.autocrlf=false diff --name-only d488350 -- model_artifacts.py context_models context_sources tennis scripts/stage_runtime_databases.py` returned no paths. The protected stage helper SHA-256 remains `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`. Staged diff whitespace check passed. Only the three exact implementation/test paths were staged for `c3bac37`; controller evidence/report edits and untracked review diffs were left alone. This report is committed separately.

Independent scoped review and actual Linux current-data/multiple-growth-generation performance acceptance remain controller-owned. The candidate address-space, CPU, wall-time, RSS and input limits were not raised. No VPS/provider/network calls, push, updater edits, production mutation or Linux-positive claims were made by this implementation task. The local cache operation-count improvements do not establish the required native `<300s` CPU and `<1 GiB` RSS gates.
