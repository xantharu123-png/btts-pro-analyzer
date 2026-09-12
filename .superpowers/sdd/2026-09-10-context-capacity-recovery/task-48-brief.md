# Task 48 — complete the actual copied receipt corpus owner

Continuation of the already authorized Task48, not a new feature contract.
Base at account handoff: `a0c949e551f4305f5420647a328ed0045646daf4`.
Existing untracked implementation and tests belong to this task; preserve them.

## Owned files and result

Only `context_storage_v2/receipt_corpus.py`,
`tests/test_context_storage_receipt_corpus.py`, and
`.superpowers/sdd/2026-09-10-context-capacity-recovery/task-48-report.md`.
Root owns Git, the progress ledger, server access, and all integration edits.
Do not dispatch subagents. Do not commit, stage, push, deploy, or change any
existing module, contract, source database, old QA directory, or dependency.

API already agreed:

```python
build_receipt_corpus(source, observations, *, expected_source_sha256,
                     workspace, owned_directory, main_cap_bytes,
                     ledger_cap_bytes, limits=DEFAULT_LIMITS)
```

This call creates its own fresh C1 copy and extends only that new private copy.
Do not accept existing/resumable copies, a CopyReceipt as permission, a public
raw writer, or manufacture FreshSQLiteWriter with object.__new__.
Reuse the actual existing receipt normalization/append operation. No fabricated
receipt references, source coverage, protected emptiness, or success wrappers.

## Binding invariants

- Preserve source SQLite encoding, page size, schema, every raw row/physical
  field in all seven original tables, including unrelated rows and NUL-bearing
  TEXT/BLOB. Do not mutate/reprofile the pinned source.
- Private copied writer first SQL MEMORY, then actual bounded DELETE/FULL,
  cache/mmap/ATTACH/Threads policy. One transaction, one successful commit,
  complete cursor/blob/connection/FD closure; errors retain new artifacts.
- RawInventory requires an actual unmodified read-only TrackedConnection.
  After writer commit/close, reopen a newly profiled read-only owner and compare
  full old rowid plus typed field bytes blockwise against source.
- Record actual inserted members in own fixed `receipt-additions.bin`, using
  held O_EXCL FD, actual table, signed rowid and typed-row hash. No unbounded
  Python list/set of inputs, count-only proof, or hash-hull membership substitute.
- Reserve main M + journal M + ledger L before copying, active source + M + L;
  require L <= M so the native FSIZE=M envelope covers the ledger too.
- Ledger sorting/merge must remain within its accounted fixed file. Strictly
  reject duplicate ledger members, missing/extra/same-count changed membership;
  existing INT64_MAX rowids cannot imply new IDs are monotonically appended.
- Final membership is the exact merge of source plus actual new ledger members
  versus output. Bind close-to-read-only reopening to the same owned identity.
- Source changes, iterator errors, quota/FULL/TOOBIG, SQL failures, FD/reopen
  failures and late close errors must fail closed, close owned handles, and keep
  artifacts charged. No reset, deletion, successful partial corpus or new input
  cap derived from 16MiB processing block size.

## Tests and task boundary

Continue existing TDD; existing 11-green checkpoint is not the finished task.
Use real legacy differentials (all seven tables), real copied UTF/page variants,
INT64_MAX case, three actual Tennis receipts, and exact negative membership and
file/transaction lifecycle cases. Independently derived outcomes; no mock-only
success. New tests must first expose the intended missing behavior.

Use existing `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`, fresh unused
basetemp/XML, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, -B -p no:cacheprovider, and
`-o junit_family=xunit1` when using record_property. Preserve prior outputs.

Report exact changed-file hashes, TDD failures, final commands/results and
specific residual risks. This small one-invocation owner is not the native
490000-receipt/global-budget owner, true Tennis consumer, empirical model
acceptance, B verification, restore, or release. Do not claim those.

Return only status, report path, concise test summary and concrete concerns.
