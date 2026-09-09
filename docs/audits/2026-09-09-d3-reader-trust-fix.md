# D3 consumer reader: closed schema and physical SQLite trust correction

9 September 2026. Bounded owner correction after the independent review of
`97cb672bea8d2e5ca2705f05e41a25eb9cab070b`.

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-reader-fix-20260909`.
Branch: `codex/kontext-reader-fix-20260909`.
Base: `7201302a7b145c7dd94de30bd41d1b5b8a498f9f`.

## Authority, original evidence and scope

Root read and accepted both findings, then explicitly authorized only:

- The consumer's complete physical table descriptor, using `table_xinfo` with
  three exact non-hidden columns.
- A shared `context_models.dataset._reader` main/companion trust guard using the
  existing runtime primitives, preserving actual live WAL and read transactions.
- New permanent regression tests and this separate correction audit.

The original independent report remains unchanged at
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-reader-review-20260909/.pytest_tmp/consumer-reader-independent-20260909/REPORT.md`,
SHA256 `85874edf9da050ff77ccb30b36b92b29c1df162ef9f88da77a8b199b35a23529`.
It remains REQUEST CHANGES against its original commit. The review's sources,
assertions and all four probe files have not been edited.

F1 showed that a generated extra column was absent from `PRAGMA table_info` and
thus accepted by the claimed closed-schema check. F2 used a real NTFS hardlink
from `models.db-shm` to a separate 88,064-byte non-database file; a correct
read-only projection replaced that separate file with 32,768 bytes of SQLite
shared memory. The real hardlink does not depend on symbolic-link privileges.

Both exact original test IDs were run RED in this clean fix worktree before
source edits. No live/production database or provider was involved.

## Correction

`context_consumers` now uses `PRAGMA table_xinfo`. It requires exactly the same
three columns with their prior indices, names, types, NOT NULL/default/PK
values and a final `hidden=0`. Additional virtual or stored generated columns
are rejected, not migrated or treated as an alternate schema.

The shared reader checks the main file and every existing `-wal`, `-shm` and
`-journal` companion before SQLite is called. Each must satisfy the unchanged
runtime no-symlink/no-junction, trusted-ancestor, regular-file and POSIX
owner/permission policy, plus a single physical link (`st_nlink == 1`). It
checks the same physical identities immediately after opening. Newly appearing
companions must pass the same trust rules. Known files that disappear or change
device/inode are rejected rather than silently substituted. Successful reads
recheck trust/identity before returning, including new companions created
during ordinary SQLite synchronization. Exceptions still close the connection;
rollback failure also cannot skip close.

This fixes a shared physical trust boundary rather than creating a second,
weaker consumer-only database connector. The artifact/outcome/header/label
decoders, D2 opening policy, dataset API, D4 sealed reader, original models,
runtime trust primitives and transport/copy contracts are unchanged.

## Deliberate live-WAL and race boundaries

`mode=ro`, `query_only=ON`, `trusted_schema=OFF` and one read transaction remain.
No data/schema/model publication is performed. Normal **trusted** WAL/SHM
synchronization metadata creation is allowed. There is no `immutable=1`, raw
main-file copy or sealed-D4 diversion: newly committed uncheckpointed WAL rows
must remain visible, and an older explicit reference must still read its own
unchanged revision.

The guard rejects a pre-existing invalid companion before SQLite can touch its
target. These filesystem checks are not an atomic race-proof VFS. Another
process with the same trusted filesystem authority may replace/create a file
between checks. Postchecks detect observed identity/trust changes but cannot
undo an intervening native-library side effect. Concurrent legitimate deletion
or replacement of a known companion can therefore cause an explicit integrity
error; it is not reclassified as missing model data or an automatic legacy
replacement. No absolute protection against a same-trusted-user race is claimed.

POSIX owner/mode semantics come from the existing primitives. Windows retains
the prior operating-system ACL boundary; no new Windows ACL verifier is
invented. The tests separately identify simulated POSIX policy checks and the
host's unavailable real-symlink capability.

## Permanent TDD and independent replay

New permanent files: `tests/test_context_reader_trust.py` and
`tests/test_context_consumer_schema.py` (35 cases).

- Before source edits: **27 failed, 7 passed, 1 expected real-symlink skip**.
- After the correction, with the existing 26 consumer tests: **60 passed,
  1 expected skip**.
- Real main/companion hardlinks, directories, no-symlink primitive reuse,
  owner/permission policy, new invalid files during open, replacement identity,
  closed handles and successful-read postchecks are covered.
- Both virtual and stored generated columns have permanent RED-to-GREEN cases.
- A real pinned WAL read transaction proves the new `.71` snapshot is visible
  without checkpointing while the older reference still returns `.6`.
- A real writer commit between schema and payload queries proves one reader
  cannot mix revisions; the next read sees and rejects committed corruption.
- Normal DELETE-mode main bytes and baseline probabilities remain unchanged.

The exact two independent finding cases and both qualified WAL controls pass
unchanged on the fix. An additional 34 portable original controls also pass:
**38 passed, 3 explicitly deselected**. The three exclusions are the already
documented initial idle-WAL setup, its obsolete `table_info`-specific race hook
(superseded by the qualified query-bound control), and the original review's
hardcoded source-worktree location assertion. Their original bytes remain
unchanged. An initial replay including that final metadata pin correctly showed
the module was loaded from the new fix worktree and failed only that old-path
assertion; it is recorded rather than counted as an application defect.

The discarded original expectation of total OS-sidecar freedom is not rerun
as an acceptance criterion. It would incorrectly favor stale immutable reads;
the positive real live-WAL tests explicitly guard against that regression.

## Execution ledger

Interpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Each command uses `-B -m pytest -q -p no:cacheprovider`, a fresh named
`.pytest_tmp` basetemp and a separate JUnit XML. No suite outcome is inferred
from the prior independent report or Root's runs.

| JUnit under `.pytest_tmp` | Actual result | SHA256 |
| --- | --- | --- |
| `reader-fix-original-red-01.xml` | 2 original failures, 1.01 s | `da671aa188936620fc0ebd9420ef4d7251b9e48455f1f72c1adeffa7861ee87a` |
| `reader-fix-own-red-01.xml` | 27 failed / 7 passed / 1 skipped, 2.03 s | `f6b55ada840b66c85f0ef69ca1c4d5ad9725788e9a39ec0f245ba7c6ba00c6c8` |
| `reader-fix-own-green-01.xml` | 60 passed / 1 skipped, 6.67 s | `2ca0665b7e23ac76e381efb87d2d0b6c4af5ce58cb8455388752b7637957c17d` |
| `reader-fix-original-green-01.xml` | 38 passed / 1 old-path pin failure / 2 deselected, 1.72 s | `d85041061bec60c1335ea44b31f9903dbb2079d98bf42a9e996c6e72d24b6d77` |
| `reader-fix-original-green-02.xml` | 38 passed / 3 deselected, 1.64 s | `7dc73457d4a8f2feceb4fa0bc4bf4eb0d0dd2d329076c338d295a0fc0c46fc24` |
| `reader-fix-d3-a1-b1-01.xml` | 531 passed / 5 skipped, 40.06 s | `89e3303dfa75840489928f237e1b4c1fee10e42e85aff56016379237c1e7dd48` |
| `reader-fix-d2-d4-01.xml` | 507 passed / 3 skipped, 983.78 s | `06f6408915564f4830f29ff7d716b5425688f0085f81c1f6c2d7008968d50821` |

Completed broader D3/A1/B1/runtime-path suite: **531 passed, 5 expected Windows
skips, 40.06 s**. These are one genuine unavailable symlink capability plus four
POSIX mode/umask tests, not hidden test failures.

Completed D2/D4 and related D1 assembly/replay regression: **507 passed,
3 expected Windows skips, 983.78 s**. These are two genuine unavailable symlink
operations (file and directory, WinError 1314) and one POSIX owner/mode test.
The command selected these complete files, without deselections:
`test_context_dataset.py`, `test_context_evaluator.py`,
`test_context_evaluator_cli.py`, `test_context_validation.py`,
`test_context_activation.py`, `test_context_experiments.py`,
`test_context_runtime_transport.py`, `test_context_runtime_semantics.py`,
`test_context_runtime_backup.py`, `test_context_training.py`,
`test_context_training_contracts.py`, `test_context_training_cases.py`,
`test_context_training_fit.py`, `test_context_training_identity.py`,
`test_context_training_reports.py`, `test_context_training_tennis_math.py`,
`test_context_replay.py` and `test_context_replay_identity_refresh.py` under
`tests/`. This exercises the shared reader's actual dataset/label-opening,
fit/report verification, runtime activation/backup and training replay callers.
No full-repository test result is claimed for this isolated correction; Root's
separate earlier full run predates this fix and is not counted here.

## Source hashes and remaining release boundaries

Current raw SHA256:

| File | SHA256 |
| --- | --- |
| `context_consumers.py` | `b49824992a65505f4ef9fd39d2c32fe5d79fee9fbcc153d45116c88a1892decd` |
| `context_models/dataset.py` | `a63ea094fe38635af3f5175597afc3b4b167e162f3a8af0e8f0540af80c99fde` |
| `tests/test_context_reader_trust.py` | `99486ab526ac7ae048fd57817d3bbe7019f3244b0c35accd71b2f7bf4da9d79f` |
| `tests/test_context_consumer_schema.py` | `61aec099f5322dcbf9838ae8df3d0f5af43278cb13d003e014ae86109348f0c4` |

Explicit unchanged pins:

- `context_copy.py`: `f69678e5888aeddc21177d5660ca6bf9e220413a2653a3b2445efee4bab88683`.
- `context_transport.py`: `d55e8ad4f81fc8a3958f48fe5e0a072e1640de8e6e5b9f694de794fafd3c9713`.
- `runtime_paths.py`: `710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c`.
- `model_artifacts.py`: `6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16`.

No sources, APIs, coefficients or approvals have been invented. No provider,
VPS, production database, Git main, pricing, Cricket, 15K or old ticket/ledger
mutation occurred. This packet does not establish real context-model empirical
quality, complete D3 live wiring, D4 qualification, UX/browser acceptance or
deployment. Root will independently review the final focused fix commit.
