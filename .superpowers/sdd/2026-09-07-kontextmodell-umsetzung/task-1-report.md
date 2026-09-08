# Task 1 / A1 implementation report

## Status

DONE. Commit `bb0b08410b3a6e8f433df7cbf2fcbab49b99e789` (`feat: add immutable runtime model artifact registry`) contains exactly the three authorized task files.

## Implementation

- Added `model_artifacts.py` with deterministic UTF-8 JSON serialization (`sort_keys=True`, compact separators, `allow_nan=False`) and SHA-256 content identities.
- Added immutable typed artifact storage in SQLite. Artifact identity covers exactly `{"kind": kind, "payload": payload}`; `created_at` is stored as provenance and an idempotent repeat preserves the original row.
- Added strict load-time checks for lowercase SHA-256 identities, SQLite storage classes, aware ISO timestamps, canonical JSON bytes, duplicate JSON object keys (including duplicate encoded manifest slots), non-finite JSON numbers, payload schema, artifact hashes and manifest hashes.
- Added atomic slot publication with `BEGIN IMMEDIATE`, compare-and-swap against `expected_manifest`, merge-without-overwrite of unrelated slots, in-transaction validation of every referenced artifact, one active-row update and one final commit. Missing/corrupt artifacts and stale writers roll back without publication.
- Kept all historical manifest rows. No pruning or mutation of prior artifacts was added.
- Added the dedicated `runtime_paths.CONTEXT_MODEL_DB_PATH = RUNTIME_STATE_DIR / "context_models.db"`.
- Reused the runtime trust boundary in `runtime_paths.py` for SQLite: all existing path components are checked for symlinks/junctions; the immediate database directory and an existing database must have trusted ownership and no group/world write permission on POSIX; the database must be a regular file. The complete path is checked before and again immediately after SQLite opens it.
- SQLite setup explicitly enables `foreign_keys=ON`, sets `busy_timeout=5000`, and initializes the exact three specified tables inside an explicit transaction.
- No quote, ticket, settlement, Cricket, provider, VPS, scheduler, account, or money behavior was touched.

## TDD evidence

### Initial RED

Command:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-red
```

Relevant output:

```text
E   ModuleNotFoundError: No module named 'model_artifacts'
ERROR tests/test_model_artifacts.py
1 error in 0.19s
```

This was the expected failure because the required module/API did not yet exist.

### Core GREEN

Command:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-core-green-2
```

Relevant output:

```text
1 passed in 0.08s
```

### Validation/concurrency RED

Command:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-validation-red
```

Relevant output:

```text
11 failed, 6 passed, 1 skipped in 0.38s
```

The expected failures specifically showed that the core still accepted naive timestamps and non-object payloads, did not reject malformed hashes before lookup, did not detect duplicate/non-finite encoded JSON, did not validate manifest identity or referenced artifact integrity, and did not yet apply runtime database path/owner trust checks.

### Required focused GREEN plus runtime-path regressions

Command:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py tests/test_runtime_paths.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-green
```

Relevant output at completion of that cycle:

```text
26 passed, 1 skipped in 0.97s
```

After self-review additions (literal known hash vectors, collision regression, dedicated path assertion, and post-open path revalidation), the final focused command was:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py tests/test_runtime_paths.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-self-review-green-2
```

Final focused output:

```text
29 passed, 1 skipped in 1.01s
```

The one skip is the deliberately POSIX-only real group-writable database permission test on Windows.

## Full regression before commit

Command (run exactly once after the final code/test changes and before staging/commit):

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-full
```

Output:

```text
1744 passed, 12 skipped, 97 subtests passed in 58.34s
```

Additional checks:

```text
python -m py_compile model_artifacts.py runtime_paths.py tests/test_model_artifacts.py
git diff --check -- model_artifacts.py runtime_paths.py tests/test_model_artifacts.py
git diff --cached --check
```

All completed successfully without diagnostic output (apart from Git's expected Windows line-ending notice before staging).

## Test coverage added

- ATP/WTA slot preservation and stale-writer rejection.
- Concurrent CAS with exactly one winner.
- Canonical UTF-8 bytes, rejection of NaN and unknown non-JSON values.
- Literal independently calculated artifact and manifest hash vectors.
- Same-content idempotence, changed-content identity, original `created_at` preservation, and changed payload under an existing digest.
- Naive timestamp and non-object payload rejection.
- Missing-artifact atomic rollback and corrupt referenced-artifact rollback.
- Malformed digest rejection before lookup/publication.
- Artifact JSON duplication, non-canonical/corrupt bytes, non-finite values, and hash mismatch.
- Duplicate raw manifest slot keys, tampered manifest identity, and dangling active-manifest reference.
- First-install database creation, real SQLite BLOB/TEXT types, and historical predecessor availability.
- Simulated symlink and wrong-owner rejection on Windows; real POSIX group/world-write rejection is present as a platform-gated test.

## Files changed and committed

- `model_artifacts.py` (new)
- `runtime_paths.py` (modified)
- `tests/test_model_artifacts.py` (new)

`git diff-tree --no-commit-id --name-only -r HEAD` returned exactly those three paths. Nothing was pushed.

## Self-review

- Re-read the complete staged diff after the full regression and confirmed the schema, hash envelopes and transaction boundaries against the approved brief/spec.
- Confirmed publication reads current manifest/slots and resolves all next-manifest artifacts inside the same `BEGIN IMMEDIATE` transaction.
- Confirmed unrelated slots are preserved, prior manifests remain present, and missing/corrupt references cannot move `active_manifest`.
- Added fixed known hash vectors so changing either documented envelope fails independently of implementation helpers.
- Tightened trust handling to recheck the path after SQLite opens it rather than relying only on the pre-open check.
- Confirmed `scripts/stage_runtime_databases.py` is not staged or committed and has no content diff: both `HEAD:scripts/stage_runtime_databases.py` and `git hash-object scripts/stage_runtime_databases.py` were `ff16f8a6639a0c166b1eec2a04656c6518bab2b8`.
- During the first add-file patch, the patch tool unexpectedly used its parent process CWD and briefly created `C:\Projekt\BetBoy\model_artifacts.py`. After resolving the exact path, I deleted only that newly created file via `apply_patch`; `Test-Path C:\Projekt\BetBoy\model_artifacts.py` then returned `False`. No inherited parent artifact was removed or altered.

## Concerns / checks not run

- WSL is unavailable by controller clarification. The actual POSIX owner/mode test is committed but skipped on Windows; it was not executed on Linux. Windows tests cover the same owner branch through controlled stat metadata and cover the no-symlink rule. No Linux/VPS action or installation was attempted.
- Windows reports `scripts/stage_runtime_databases.py` as modified because of the pre-existing stat/line-ending condition, but its raw Git blob identity is unchanged as documented above, and it is outside this commit.
- No provider calls, deployment, VPS writes, push, or production activation were performed.

---

# Review fix round 1

## Fix base and commit

- Fix base: `bb0b08410b3a6e8f433df7cbf2fcbab49b99e789`.
- Fix commit: `d292c21` (`fix: harden model artifact trust validation`).
- The fix commit again contains exactly `model_artifacts.py`, `runtime_paths.py`, and `tests/test_model_artifacts.py`.

## Findings addressed

1. Runtime database trust now validates the complete existing ancestor chain both before creating missing nested parents and after creation/open checks. Every existing ancestor must be a directory owned by root or the effective service user on POSIX. The direct database directory may never be group/world writable. A higher group/world-writable ancestor is accepted only when it is sticky and trusted-owned, matching safe `/tmp`-style traversal without accepting an ordinary replaceable writable directory.
2. Artifact writes now recursively reject every non-string JSON object key before timestamp hashing, database preparation, or insertion. Nested dictionaries inside lists/tuples are covered, including the reproduced `{2: "two", 10: "ten"}` ordering case.

## TDD RED evidence

The first test-only run exposed an incomplete Windows stat double (`st_reparse_tag` absent) in three path tests. I corrected only the test fixture before evaluating production behavior. A second test-only run showed that simulated Windows permission bits also needed to normalize all non-target directory stats; otherwise the newly created direct parent was falsely reported world-writable. I again corrected only the test fixture.

The authoritative RED command after those test-harness corrections was:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-review1-red-3
```

Relevant output before production changes:

```text
FAILED test_artifact_rejects_non_string_keys_recursively_before_database_write
E   Failed: DID NOT RAISE TypeError
FAILED test_runtime_database_rejects_writable_ancestor_before_creating_parents
E   Failed: DID NOT RAISE RuntimeArtifactTrustError
FAILED test_runtime_database_rejects_untrusted_ancestor_owner_before_creation
E   Failed: DID NOT RAISE RuntimeArtifactTrustError
3 failed, 21 passed, 3 skipped in 0.47s
```

The sticky-writable trusted-ancestor positive regression already passed at RED, while the three missing rejection branches failed for the expected production reasons.

## GREEN and focused regression evidence

Command:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py tests/test_runtime_paths.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-review1-green
```

Output:

```text
33 passed, 3 skipped in 1.05s
```

The three Windows skips are deliberately real-POSIX tests: a non-sticky `chmod 0777` ancestor must be rejected before nested-directory creation, a trusted sticky `chmod 01777` ancestor must be accepted, and a group-writable database file must be rejected. Equivalent ancestor branches are exercised on Windows with complete controlled stat metadata. The controller will run the real chmod cases in its isolated Linux QA environment.

Additional successful checks:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m py_compile model_artifacts.py runtime_paths.py tests/test_model_artifacts.py
git diff --check -- model_artifacts.py runtime_paths.py tests/test_model_artifacts.py
git diff --cached --check
```

Per the review-fix instruction, the amended code received the focused covering suite; the full suite was not rerun in this fix round. The immediately preceding base report retains the pre-base-commit full result (`1744 passed, 12 skipped, 97 subtests`).

## Self-review and boundaries

- Verified ancestor checks run before `mkdir(parents=True)` and again afterward; missing directories are skipped only until the next existing ancestor is reached.
- Verified trusted ownership is required before the sticky exception is considered.
- Verified sticky permission is never an exception for the direct SQLite directory, protecting the database and journal filename namespace.
- Verified recursive key validation runs before `_connect`, and the regression asserts that the database path remains absent.
- Verified the staged fix contained exactly the same three A1 files and no unrelated source.
- Reconfirmed the out-of-scope `scripts/stage_runtime_databases.py` content hash remains identical to its Git blob (`ff16f8a6639a0c166b1eec2a04656c6518bab2b8`) and it was not staged/committed.
- No provider call, VPS write, deployment, push, financial behavior change, pickle behavior change, Cricket change, or later-task implementation occurred.

## Remaining concern

- Actual POSIX chmod execution is intentionally pending the controller's isolated Linux QA. Windows evidence is complete for the platform-independent branches but is not presented as Linux proof.

---

# Review fix round 2

## Fix base and commit

- Fix base: `d292c216d90ecc4872cf99d2261eb566893fc204`.
- Fix commit: `e41458d` (`fix: create trusted runtime parents privately`).
- The commit changes only `runtime_paths.py` and `tests/test_model_artifacts.py`, both within the unchanged three-file A1 scope.

## Findings addressed

1. First-install directory creation no longer uses `Path.mkdir(parents=True)` with ambient `0777 & umask` permissions. The implementation enumerates every missing parent and creates it top-down with a separate `os.mkdir(path, 0o700)`. Thus intermediate as well as final missing directories remain private under common `umask 0002`; no process umask mutation and no chmod of an existing directory occurs.
2. If a component appears concurrently and `os.mkdir` reports `FileExistsError`, that exact component is immediately rechecked for symlink/junction status, trusted ownership, directory type, and appropriate sticky/write policy before creation continues below it.
3. Controlled owner fixtures now consistently preserve the production `{0, effective owner}` trust set. The wrong-database-owner test changes only the database leaf's owner metadata, so it cannot pass by accidentally distrusting a legitimate root-owned ancestor.

## Test-only RED evidence

The first local test-only run exposed one intended production failure and one Windows fixture failure: enabling POSIX ownership checks also exposed Windows group/world bits on the direct parent. I normalized only the non-target stat metadata and reran before changing production.

Authoritative local RED command against unchanged `d292c21` production files:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-review2-red-2
```

Relevant output:

```text
FAILED test_first_install_requests_private_mode_for_every_missing_parent
expected every successful mkdir mode to be 0700; actual modes were 0777
1 failed, 24 passed, 4 skipped in 0.51s
```

Before production was changed, the controller copied this test-only file (SHA-256 `adb784a385ad57de3f29bed42ccf85d0a94ae8ca7d19f2993281338a5c7354e7`) onto the separately frozen `d292c21` Linux archive. The controller's exact Linux RED command was:

```text
env PYTHONPATH=/tmp/betboy-context-qa.9xr68INa/a1-r2-red /tmp/betboy-context-qa.9xr68INa/venv/bin/python -m pytest /tmp/betboy-context-qa.9xr68INa/a1-r2-red/tests/test_model_artifacts.py -q -p no:cacheprovider --basetemp=/tmp/betboy-context-qa.9xr68INa/a1-tests-r2-red
```

Controller-reported Linux environment/output:

```text
Python 3.12.3, pytest 9.1.1, user ubuntu, default umask 0002
FAILED test_first_install_uses_real_sqlite_types_and_keeps_history
FAILED test_first_install_requests_private_mode_for_every_missing_parent
FAILED test_posix_first_install_is_private_with_group_permissive_umask
FAILED test_posix_runtime_database_allows_real_trusted_sticky_ancestor
4 failed, 25 passed in 0.66s
```

All four failures were confirmed to be the same unsafe newly-created `0775` parent. The corrected leaf-owner stub passed on Linux.

## Local GREEN evidence

Command:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m pytest tests/test_model_artifacts.py tests/test_runtime_paths.py -q -p no:cacheprovider --basetemp=.pytest_tmp/a1-review2-green
```

Output:

```text
34 passed, 4 skipped in 1.26s
```

The skips are the four intentionally real-POSIX permission/umask cases. The cross-platform mkdir-mode regression passed and verified exactly three nested successful creations, each requested as `0700`.

Additional successful checks:

```text
C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe -m py_compile model_artifacts.py runtime_paths.py tests/test_model_artifacts.py
git diff --check -- model_artifacts.py runtime_paths.py tests/test_model_artifacts.py
git diff --cached --check
```

Per the scoped review-fix instruction, only the focused covering suite was rerun locally. The controller will execute the unchanged commit archive on actual Linux before A1 completion.

## Self-review and boundaries

- Confirmed every missing directory, including intermediate ancestors, receives an explicit `0700` request and is validated before any child is created below it.
- Confirmed existing safe directories are preserved byte/mode-for-mode and existing unsafe directories remain rejected; production never calls `chmod` or `umask`.
- Confirmed the higher sticky-ancestor exception still requires root/effective ownership and never applies to the direct database directory.
- Confirmed publication, artifact hashing, JSON validation, SQLite schema, pickle behavior, and all financial/Cricket code are unchanged in this round.
- Reconfirmed `scripts/stage_runtime_databases.py` is neither staged nor committed and still hashes exactly to its Git blob `ff16f8a6639a0c166b1eec2a04656c6518bab2b8`.
- No provider/VPS/network/deployment/push action occurred.

## Remaining concern

- The fixed commit is frozen for the controller's actual Linux GREEN and scoped re-review; local Windows results do not substitute for that evidence.
