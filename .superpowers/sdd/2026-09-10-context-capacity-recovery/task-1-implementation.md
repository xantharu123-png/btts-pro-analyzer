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

## Cache review fix: pin the original schema as well as transaction/write counters

Code commit: `7d6595e` (`fix: invalidate replay cache on schema changes`), based on `c871999`.

Independent review reproduced an Important API lifecycle mismatch: ordinary `DROP TABLE context_observations` inside the held tracked transaction changes neither `transaction_generation` nor `total_changes`. A previously cached empty history was returned even though an uncached reconstruction raised `sqlite3.OperationalError`. The receiving-code-review and TDD skills required verifying that concrete counterexample before changing production code; the new tests reproduce both the unchanged counters and cold/warm discrepancy.

The minimal fix pins `PRAGMA main.schema_version` and `PRAGMA temp.schema_version` at cache acquisition and checks both cookies in the existing cache lifetime check. Temp is included because the inventory uses unqualified table names and ordinary temporary-table creation can shadow main inventory tables. A schema mismatch takes the existing permanent invalidation path, clearing entries and pending byte accounting; original identity, generation and `total_changes` checks are retained. There are no transaction factory, owning selector, runtime report, budget, callback or SQL semantic changes. Deliberate hostile manipulation of SQLite internals is not added to the threat model. The two read-only PRAGMAs run on each otherwise valid cache check, including pending-store row checks; final native timing must use this amended implementation rather than the provisional `c3bac37` benchmark.

Focused commands used the quality Python and `-B -m pytest -q -p no:cacheprovider` as documented above:

1. Initial RED: `tests/test_context_runtime_capacity.py -k encoded_history_schema_change --basetemp=.pytest_tmp/capacity-cache-schema-red`: **12 failed, 58 deselected in 4.37s**, exit 1. DROP/CREATE/ALTER were exercised through both connection and cursor SQL, with both empty warm entries and not-yet-populated caches. Every case confirms the transaction stays open and both old counters stay unchanged. DROP cold cases reached the old OperationalError instead of cache invalidation; warm DROP and CREATE/ALTER cases failed with `DID NOT RAISE RuntimeArtifactTrustError`.
2. Expanded RED with ordinary `CREATE TEMP TABLE context_observations (digest TEXT)` shadowing: same selection plus `--tb=short`, `.pytest_tmp/capacity-cache-schema-red-temp`: **16 failed, 58 deselected in 5.25s**, exit 1, before the schema pin was implemented.
3. GREEN after the schema pin: `tests/test_context_runtime_capacity.py -k encoded_history --basetemp=.pytest_tmp/capacity-cache-schema-green`: **32 passed, 42 deselected in 8.47s**, exit 0. Repeated post-mutation calls must continue to reject and retained/pending bytes and entry count must be zero.
4. Final focused current-code regression run with the four numeric-library thread limits set to 1: `tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py tests/test_context_runtime_tennis_live.py -k 'not lazy_membership_does_not_decode_unopened_final' --basetemp=.pytest_tmp/capacity-cache-schema-final`: **194 passed, 12 skipped, 1 deselected in 26.58s**, exit 0. The minute-long actual protected-final case remains previously exercised as recorded above; it was not rerun for the schema-cookie-only fix. No full suite or large semantic suite was run.

`git -c core.autocrlf=false diff --name-only c871999 -- model_artifacts.py context_models context_sources tennis scripts/stage_runtime_databases.py` returned no paths, and the protected stage helper SHA remains `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`. Exact staged implementation paths were only `context_runtime_history_cache.py` and `tests/test_context_runtime_capacity.py`; staged whitespace check passed. Controller-owned evidence and untracked review files remain untouched. Independent scoped re-review and exact-final-revision Linux native performance acceptance remain pending and unclaimed.

## Second measured refinement: validation-owned cutoff iteration

Code commit: `8249c28` (`perf: filter replay only after complete receipt validation`), based on the controller-approved plan refinement `02d1232`. The controller reported that exact `4fad098` on the largest synthetic growth fixture (387,739,648 bytes, 188,791 receipts) reached 300.040 CPU seconds / 300.219 wall seconds, peak 312,792 KiB, child return -9, no report and unchanged input. These controller facts explain the refinement; this local implementation task performed no native measurements or remote operations.

### Implementation and preserved proof boundary

- `VerifiedReceiptMapping.validate_all()` now owns the former `_verify_observations` complete checks in the same order: identify protected contents; check every content identity and canonical ordinary body (protected contents remain opaque hash checks); visit every receipt using its existing lookup/owning decoder; reject orphan contents. Future, inactive and unreferenced receipts are not excluded. `_verify_observations` only constructs the mapping and returns it with this method's complete content count; the absent-observation return remains `({}, 0)`.
- A completion stamp is published only after those checks succeed and an end-state comparison confirms the original transaction generation, `total_changes`, and main/temp schema cookies. It belongs to the exact mapping instance and retains no decoded receipts. Later ordinary writes, schema changes, transaction end/restart or closure invalidate the capability permanently. Failed or interrupted validation catches `BaseException` solely to revoke proof before re-raising; it cannot retry into a new proof on that instance.
- Validation failure also revokes ordinary mapping access through its existing transaction-check boundary. This matters when an unvalidated baseline reader filled the encoded cache before a later interrupted full validation: the old warm cache must not remain usable. No cache implementation change was required.
- `values_at_or_before(cutoff)` uses full `.values()` when this particular mapping has never completed validation. After successful validation it scans only receipt digest/clock metadata and decodes eligible ordinary rows through the unchanged `__getitem__`. Every protected receipt is retained regardless of its clock, still exposing only the existing opaque outer representation. This does not assume a new protected-clock proof or decode unopened labels.
- Canonical fixed-UTC microsecond clock comparison is inclusive. The owning Tennis selector already excludes later clocks before typed validation, so only redundant future ordinary decoding is omitted. Both-tour eligible owning typed validation remains before the selector's tour filter; no event, source, participant, tour or latest-only filtering was introduced. History sorting, complete tuples, fresh consumer objects, revisions, causal references, numerical replay and history/cache budgets remain unchanged.
- The only cold replay change selects the new iterator for a verified receipt mapping; other mappings keep their full values path. Started validated iterators check proof before rows, after decoding, on yield resumption and at completion. SQLite itself prohibits DROP while a read cursor is active, so the DROP regression uses a created-but-unstarted iterator; CREATE/ALTER/temp shadowing, ordinary writes and transaction cases exercise started iterators.
- There is no new schema/index, callback, caller-supplied trust flag, generic decoded cache, model/source change or public D4 report field. Tests observe actual owning-decoder receipt IDs: all three fixture receipts are decoded during full validation; afterward only the two eligible receipts are decoded for replay. A separate newly constructed mapping still visits all three, proving completion is not shared implicitly. No extra production diagnostic API was necessary.

### Focused TDD and verification

Commands used the same quality Python with `-B -m pytest`, `-q -p no:cacheprovider` and `--tb=short`. The final focused run and final narrow contracts also set `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` to `1` in their child environment.

1. RED: `tests/test_context_runtime_capacity.py -k 'validated_cutoff or cold_path_keeps_full_validation' --basetemp=.pytest_tmp/capacity-validation-red`: **17 failed, 2 passed, 72 deselected in 7.53s**, exit 1. The new validation/iteration methods were absent; existing unvalidated corruption cases still passed. Tests were written before implementation using the TDD skill.
2. First GREEN attempt, same selection, `.pytest_tmp/capacity-validation-green-01`: **18 passed, 1 failed, 72 deselected in 5.83s**. The remaining failure was real SQLite `database table is locked` while attempting DROP with an active read cursor, before the intended assertion. Adjusted that fixture to an unstarted iterator; active-iterator checks remain for operations SQLite permits. No production safety behavior was relaxed.
3. Additional lifecycle RED: `tests/test_context_runtime_capacity.py::test_validated_cutoff_failure_revokes_existing_warm_cache --basetemp=.pytest_tmp/capacity-validation-revocation-red`: **1 failed in 1.83s**, exit 1, actual `DID NOT RAISE RuntimeArtifactTrustError`. The already-filled warm cache survived an interrupted full validation. Added permanent mapping revocation through its transaction check, then verified the complete focused set.
4. Focused capacity, backup/authorized rollback and live Tennis: `tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py tests/test_context_runtime_tennis_live.py --basetemp=.pytest_tmp/capacity-validation-final --durations=5`: **213 passed, 12 skipped in 94.36s**, exit 0. This includes exactly one run of the amended actual `test_lazy_membership_does_not_decode_unopened_final` (63.22s): successful full validation, an early cutoff retaining every protected ref, repeated replay/cache consumers, full D4 report, and unrelated ordinary corruption rejection with the owning final decoder guarded throughout.
5. Strengthened two test assertions without further production edits: the B1-valid opposite-tour corruption must pass `validate_all()` outside the expected owning replay error, and a distinct never-validated mapping must still decode the complete inventory. Final narrow command, selection from step 1, `.pytest_tmp/capacity-validation-final-contracts`: **20 passed, 72 deselected in 6.07s**, exit 0.

The matrix includes full-pass decoder counts and never-validated fallback; exact cutoff equality, one-microsecond-before and timezone-equivalent cutoff parity for ATP/WTA; fresh nested result ownership; future wrong-index/content corruption; orphan detection; interruption and mid-validation writes; repeated rejection after validation failure; same-transaction write/DDL/temp shadowing, commit/BEGIN, rollback/BEGIN and closure; started iterator revocation; preexisting warm-cache revocation; real D4 snapshots and exact authorized rollback regressions. The 12 skips remain external Linux-fixture and existing Windows-platform gates. No full suite, updater tests, broad semantic suite, provider call, VPS access or push was performed.

### Scope and remaining acceptance

Only `context_runtime_inventory.py`, `context_runtime_tennis.py`, `context_runtime.py` and `tests/test_context_runtime_capacity.py` were staged for the code commit. Staged whitespace check passed. `git -c core.autocrlf=false diff --name-only 02d1232 -- model_artifacts.py context_models context_sources tennis scripts/stage_runtime_databases.py` returned no paths; the protected stage helper SHA-256 is still `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`. Task2's already-committed RED tests and controller evidence/untracked review files were left untouched. This appendix is committed separately.

Independent scoped review plus fresh exact-final native current-data and multi-generation resource measurements are still required. The optimization reduces repeated future body decoding but does not bound unbounded database growth or eliminate the full validation cost. No CPU, wall, RSS, address-space, sealed-input or history/cache limit was raised, and no release/deployment acceptance is claimed here.

## Third measured refinement: covering later history to earlier cutoff

Code commit: `4db6118` (`perf: reuse covering completed Tennis history for earlier cutoffs`), based on the controller-approved third refinement `8f42995`. The exact third-refinement plan paragraph and final native evidence sections were read before implementation. Task2 had committed its checkpoint and relinquished the sole-writer slot; its files were not edited or tested here.

The controller's measured current-copy API run identified two approximately 64-second cold selections, two equal 28,432,021-byte entries fitting the existing cache with no eviction, and the actual later/earlier/later/earlier original order. The 263 intervening receipts were measured as football, not inferred from similar counts. Consequently this change is the approved covering-later prefix reuse, not earlier-to-later interval reconstruction, source pruning, original reordering or an additional input filter. Controller measurements justify the change but do not constitute native acceptance of this new revision.

### Exact implementation boundary

- Added `_lookup_covering` only to the existing immutable cache. After the ordinary exact-key miss, it checks the exact pinned cache lifetime and the existing mapping's completed-validation proof, then chooses the nearest cached strictly later cutoff for the same tour. Never-validated mappings return no covering result and follow the unchanged full cold path. Failed/revoked validation raises through existing checks; it cannot fall back around a failed proof.
- Completed owning selector outputs are ordered by `(observed_at, digest)` and their evidence annotations depend only on receipt clocks. Decoding cached canonical rows one at a time and retaining the inclusive earlier prefix therefore preserves the exact earlier owning output. The loop stops at the first later row, rather than materializing another entire later decoded history. Every retained nested object is freshly decoded. No body comes from a newly trusted database decoder.
- Admission charges the existing immutable canonical byte length of each retained row only. A parent too large for the requested earlier-history budget is usable when the complete selected prefix fits; a genuinely oversized prefix still raises. Empty prefix results are legitimate tuples, distinct from the no-cover `None` sentinel.
- Cache lifetime checks run before reconstruction, before/after individual decoding and after completion, including empty entries/results. An interruption cannot publish a partial child. The unchanged `_store` independently encodes the completed result under its new key and the same aggregate 64-MiB budget, so parent eviction does not truncate or invalidate its child. Pressure/bypass behavior remains unchanged.
- `_replay_history` retains the unchanged owning empty-tuple argument validation, exact-hit-first behavior, and fallback cold implementation. Snapshot owning feature calculation and validation are untouched. There are no changes to inventory implementation, full physical validation, owning source/model code, schema/index, updater, public report or any budget.
- Added private diagnostic `covering_hits`, incremented after successful covering reconstruction. Existing `misses` still counts exact-key misses, including requests subsequently served by covering reuse; existing `hits` remains exact-key hits. A successful covering reconstruction followed by a later store interruption remains a reconstruction count, not a completed public report. The later-first test proves one cold reconstruction; no runtime prediction is substituted for native measurement.

### TDD and focused verification

Commands used `C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -B -m pytest`, `-q -p no:cacheprovider` in the designated worktree. The final focused command set child `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` to `1`.

1. Initial RED: `tests/test_context_runtime_capacity.py -k covering_history --tb=short --basetemp=.pytest_tmp/capacity-covering-red`: **17 failed, 4 passed, 92 deselected in 7.73s**, exit 1. Excess cold calls and wrong fallback were reproduced. Some decode-race tests initially patched the shared JSON module too broadly and hit the owning decoder's keyword arguments; those were corrected to replace only the cache module's JSON binding with a test-local adapter, leaving owning JSON decoding untouched.
2. Clean RED, before production changes: same selection with `--tb=line`, `.pytest_tmp/capacity-covering-red-02`: **17 failed, 4 passed, 92 deselected in 6.41s**, exit 1. These are actual excess cold reconstruction/unexpected fallback failures and `DID NOT RAISE` in paths that did not yet perform covering reconstruction, not absent-module failures. The four negative controls prove full cold fallback for never-validated, different-tour, forward-only and missing-cache situations.
3. GREEN after the minimal implementation: same selection with `--tb=short`, `.pytest_tmp/capacity-covering-green-01`: **21 passed, 92 deselected in 6.49s**, exit 0.
4. Final capacity, backup/authorized rollback and live Tennis regression: `tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py tests/test_context_runtime_tennis_live.py --tb=short --basetemp=.pytest_tmp/capacity-covering-final --durations=5`: **234 passed, 12 skipped in 110.23s**, exit 0. This includes one amended actual `test_lazy_membership_does_not_decode_unopened_final` run (71.23s): the real protected receipts remain opaque during full validation, exact replay and covering an earlier empty history, and ordinary corruption remains rejected. The 12 skips are the existing external Linux-fixture/Windows-platform gates.

The new matrix proves actual later-first ordering against independent unchanged owning selection; exact clock equality, earlier microsecond and timezone-equivalent cutoffs; empty earlier results; nested mutation isolation for parent and child; selected-prefix-only byte admission and failed-budget nonpublication; all four cold fallback controls; real same-transaction write, DDL, temp shadowing, commit/BEGIN, rollback/BEGIN and closure injected during fresh covering decoding for both empty and nonempty results; decode/encode interruptions and clean retry; bounded cache pressure, parent eviction, independent child reuse and subsequent forward cold fallback. Existing adjacent tests additionally exercise B1-valid malformed opposite-tour data, future/unrelated physical corruption, failed complete validation, warm-cache revocation and exact rollback contracts.

### Scope checks and remaining gate

Only `context_runtime_history_cache.py`, `context_runtime_tennis.py` and `tests/test_context_runtime_capacity.py` were staged for `4db6118`; staged whitespace check passed. `git -c core.autocrlf=false diff --name-only 8f42995 -- model_artifacts.py context_models context_sources tennis context_runtime_inventory.py context_runtime.py scripts deploy` returned no paths. The protected stage helper SHA-256 remains `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`. All controller evidence/untracked outputs and frozen Task2 files were preserved. This appendix is committed separately.

No full suite, updater tests, broad semantic suite, VPS/provider/network call, push or production mutation was performed. Independent scoped review and fresh exact-final native current/largest/multiple-growth-generation capacity gates remain controller-owned and unclaimed. Full physical validation and four snapshot owning feature passes still incur their actual cost; no limit was raised to obtain acceptance.

## Fourth measured refinement: shared streaming LEFT-JOIN traversal

Code commit: `c4e20e01f90a9003114ec44655de7bf30dff55fa` (`perf: stream complete and validated cutoff receipt joins`), based on the fourth refinement approved in `e279848`. Task2 relinquished the sole implementation writer slot before this work. The exact new plan paragraph was read first. This revision changes only inventory traversal and targeted capacity tests; native largest-generation acceptance remains HOLD until the controller measures this exact revision.

The controller's preceding largest-data diagnostic measured full physical validation at 147.192s, first cold history at 76.698s and successful covering reuse at 4.202s. The 25-CPU-second sampled receipt profile attributed 24.638s cumulative to approximately 23,668 lookups, including 21.734s owning decoding and 2.256s tracked SQL execution. These measured observations motivated removing repeated SQL/Python traversal work; they do not predict this revision's wall time, CPU or release acceptance. All mandatory owner decoding remains.

### Preserved contracts and exact change

- `validate_all()` retains its protected-content discovery, every content check, every receipt check, orphan check, final inventory stamp comparison and permanent-failure handling in their original phase order. Its receipt phase now streams the existing unfiltered `context_observations._SELECT` LEFT JOIN once instead of scanning digests and executing one indexed JOIN per receipt. Every ordinary row still invokes the unchanged owning `_decode_receipt`; no future/inactive/unreferenced row is excluded from the full pass.
- The narrowly shared `_decode_row` performs the transaction check and preserves the owning ordinary decoder or existing protected outer representation. `__getitem__` still raises `KeyError` for an absent requested identity and uses that same row path. The new direct stream cannot bypass ordinary NULL/invalid-identity rejection. Protected rows additionally require the receipt digest's existing canonical format: RED exposed that arbitrary invalid protected string/byte IDs had previously been accepted through the isolated mapping API. NULL and malformed protected identities now reject without any protected body decode. This is the explicitly required identity guard, not a new source/model decoder.
- Only after the existing completed proof succeeds, `values_at_or_before` uses the same LEFT JOIN with parameterized `WHERE r.observed_at<=?`. Canonical ordinary clocks have already been validated. Eligible ordinary receipts still use the exact owner decoder, and subsequent Tennis selection still validates both tours before its tour filter. Never-validated inventory retains the full values fallback; failed/revoked proof still rejects.
- A bounded identity-only copy of the existing protected-ref set tracks refs not yet yielded by the eligible query. Those remaining refs are looked up individually regardless of clock, so later, noncanonical or opaque clock values cannot suppress protected rows. Genuinely absent protected refs are skipped as in the old whole-inventory traversal; checks around the absence path prevent a concurrent post-proof write/deletion from being hidden. No variable-limit IN list, temporary table, new index or second full metadata scan is used.
- The valid-completion stamp is checked before/during decoding, after decoding, after yield resumption and at exhaustion, including empty queries and missing-protected lookup paths. Full validation catches/re-raises interruptions with permanent proof revocation. Protected results remain outer-only, duplicate-free and never passed to a body decoder. No decoded inventory or `fetchall` is introduced. SQL row visitation order was unspecified before and remains so; phase order and rejection coverage are preserved, not a fabricated first-error precedence among multiple corrupt rows.
- Cache code, Tennis orchestration, snapshot feature/owner validation, model/source files, schemas, indexes, input/cache/SQLite/resource budgets and updater code are byte-unchanged. Public D4 reports and existing private cache statistics are unchanged.

### Observed TDD and focused verification

Commands used `C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -B -m pytest`, `-q --tb=short -p no:cacheprovider` in the designated worktree. The final focused command set child `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` to `1`.

1. RED before production edits: `tests/test_context_runtime_capacity.py -k streamed --basetemp=.pytest_tmp/capacity-stream-red`: **6 failed, 22 passed, 113 deselected in 8.40s**, exit 1. The full pass made three receipt JOINs instead of one; cutoff replay made two instead of one; 40 added valid future receipts caused 49 Python validation checks instead of a constant bound; two invalid protected IDs were accepted (`DID NOT RAISE`); the absent-protected lookup race was not reached by the old traversal (`DID NOT RAISE`). Existing NULL, opaque-clock, lifetime and last-row failure controls passed before the change.
2. GREEN after the minimal implementation: same selection, `.pytest_tmp/capacity-stream-green-01`: **28 passed, 113 deselected in 8.03s**, exit 0. The phase/owner test observes exactly three content checks, three unchanged owner receipt decodes, then the orphan check, with one receipt JOIN. Both zero and forty additional future rows use one eligible JOIN and at most ten Python validation checks after the full pass.
3. Added explicit direct missing-content/LEFT-JOIN rejection and empty-query mutation coverage, then ran focused adjacent capacity, backup/authorized rollback and live Tennis: `tests/test_context_runtime_capacity.py tests/test_context_runtime_backup.py tests/test_context_runtime_tennis_live.py --basetemp=.pytest_tmp/capacity-stream-final --durations=5`: **264 passed, 12 skipped in 109.82s**, exit 0. This includes exactly one amended actual `test_lazy_membership_does_not_decode_unopened_final` run (65.22s), guarding the owning final decoder through full validation, cutoff traversal, cache/exact/covering replay, full D4 checking and unrelated ordinary corruption rejection. The 12 skips remain external Linux-fixture and existing Windows-platform gates.

The new 30-case matrix covers complete owner-call counts and phase ordering; future-growth-independent Python checks after full proof; ordinary/protected NULL, invalid string and invalid byte receipt IDs; protected canonical before/after clocks, early/late noncanonical strings and opaque byte clocks; genuinely missing protected refs; mutation triggered specifically by the absent-ref lookup; final-receipt write/DDL/commit/rollback/close/interruption in both full and cutoff streams; mutation after the final yield; missing joined content; and mutation after an empty query. Unknown-clock protected fixtures deliberately isolate the opaque mapping contract and are not claimed to be valid full D4/D2 databases. Existing adjacent tests preserve cutoff/timezone parity, malformed future/unrelated and opposite-tour checks, orphan detection, failed-proof/cache revocation, both tours and exact rollback behavior.

### Scope and handoff

Only `context_runtime_inventory.py` and `tests/test_context_runtime_capacity.py` were staged for the code commit; staged whitespace check passed. `git -c core.autocrlf=false diff --name-only e279848 -- model_artifacts.py context_models context_sources tennis context_runtime_history_cache.py context_runtime_tennis.py context_runtime.py scripts deploy` returned no paths. Protected stage helper SHA-256 remains `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`. Controller untracked outputs and frozen Task2 files were preserved. This report appendix is committed separately.

No full suite, broad semantic/updater suite, VPS/provider/network operation, push, model change or budget increase was performed. Independent scoped review and fresh exact native current/largest/multiple-growth measurements remain required. This implementation claims traversal correctness and focused local regression evidence only; largest-generation capacity remains HOLD until independently measured acceptance. The sole-writer slot is returned after this report commit.
