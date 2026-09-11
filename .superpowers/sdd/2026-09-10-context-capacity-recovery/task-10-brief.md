# Task10 — exact checking predicates, less allocation/dispatch

## Authority and ruling

The user authorized the equivalent Tennis/D2 checking repair and subsequent
commit/push/controlled updater repair/app deployment. The latest actual
30-snapshot input still fails CPU300 at exact1c65ada; source correctness and
the completed fullsuite do not authorize deployment. This is an internal
allocation/dispatch refinement of the same accepted checking contract, not
a new model, feature, source contract or acceptance-rule change.

Ruling: reopen only `context_runtime_history_cache.py` and
`context_runtime_inventory.py` for exactly the two measured seams below.
Keep literal canonical-byte equality, every fresh before/after/final proof
boundary, both actual schema cookies, independent cold source seal, all
original predictors and full fresh snapshot histories/features/transport.
If an optimization cannot preserve those obligations, leave it out and
report the limitation. No other production source, protected transaction
module, model/owner feature, helper, updater, schema or data may change.

## Observed problem and evidence

Exact1c65ada current input265793536B/99774receipts/32artifacts/30snapshots
failed299.978CPU/300.233wall, child-9, no report, input unchanged. The prior
26snapshot input passed262.838wall; do not reuse that acceptance.
Read complete `fresh30-capacity-analysis.md` and Task9 report/brief plus
current source and relevant boundary tests. Root's first complete native
snapshot feature sample (diagnostic only) began at109.913s and processed
20501rows. Profile4.3025s: witness matching4.0275; fresh proof1.7058;
plain-JSON guard1.3226; canonical encoding0.8704; unchanged feature math0.0576.
Local14real-row status/workload mix supports a simple loop/fixed-type guard
more strongly than replacing the canonical comparison with structural equality.

The separate above30distinct-query complete-prefix fallback remains a
documented growth concern. Rolling query batches are NOT part of this task.
Do not increase query/slot/byte caps or claim this micro-optimization solves
arbitrary future growth. Root must run current-first and meaningful larger
consumer-count controls before any release decision.

## Exact implementation scope

1. `_plain_json`: replace recursive `all(generator)` bodies with recursive
   same-order `for` loops and first-False return; hoist only the fixed exact
   five leaf types `(str, int, float, bool, type(None))`. Dict/list make seven
   accepted builtin kinds in total. Keep exact `type` checks, key-type checks,
   recursion/short-circuit behavior and actual `canonical_bytes(row) == raw`.
   No normalization, structural comparator, digest-only authority, feature
   cache, decoded retained pool or unbounded worklist.
2. Schema cookie reads: at an exact internal owner, one short-lived local
   `TrackedCursor` may execute the same `PRAGMA main.schema_version` then
   `PRAGMA temp.schema_version`, with the same fetches, statement tracking,
   transaction/write values and evaluation order. Close on success and failure
   before returning; no persistent/shared cursor or cached cookie/stamp. The
   protected transaction module stays byte-identical. Preserve the original
   connection-dispatch route for connection/mapping/cache subclasses whose
   overrides would otherwise be bypassed. Do not substitute table-valued
   PRAGMAs, suppress errors or move/remove an integrity boundary.

Allowed authored files:

- `context_runtime_history_cache.py`
- `context_runtime_inventory.py`
- new `tests/test_context_runtime_check_dispatch.py`
- `.superpowers/sdd/2026-09-10-context-capacity-recovery/task-10-report.md`

No existing test edits without a concrete scope request to root. There is
one index/product writer, the assigned implementer. Root owns controller
docs, diagnostic scripts, native QA, final fullsuite and publication. Read-only
reviewers may write only their named reports. Preserve all worktrees/WIP/output.

## RED-first plan

1. Inspect exact source and current real fixtures. Add deterministic bounded
   allocation/dispatch probes: prior plain guard creates recursive generator
   frames; prior exact schema boundary allocates two tracked cursors. Count
   real delegated operations, not source strings or wall-time thresholds.
   Observe expected RED before product edits. Existing semantic code is
   correct: call this a performance-contract RED, not a fabricated outcome bug.
2. Independent expected guard matrix: every exact builtin kind, empty/nested
   dictionaries/lists, non-string/aliased keys, dict/list/str/int/float subclasses,
   bool versus int, signed zero, nonfinite values, recursive/cyclic inputs and
   ordinary cold fallback. Keep canonical encoding/error behavior unchanged.
3. Actual SQLite boundary tests: both fresh cookies/order/statements, main and
   temp DDL/shadowing, writes, commit/rollback/restart/close, failure/interrupt
   between cookies, cleanup on exception, reentrant cursor/connection seams,
   subclass dispatch preservation and permanently revoked proof. Instrument
   actual owner interfaces; do not replace all checking with a mock result.
4. Integrated real witness/covering/original/snapshot regressions: no before/
   after/final/empty boundary skipped; source-invalid/alias mutations still
   reach real unchanged cold validation; no stale scope after exception,
   eviction or identical-byte replacement. Count full real predictors/features/
   transports where available; no altered acceptance/model output.
5. Implement only the measured equivalent seams, then run new module and the
   existing receipt-witness/shared-history/projection/coordinated/capacity/
   live-Tennis/inventory/semantics/backup/rollback contracts as relevant. Root
   alone runs whole repository/native acceptance. Use fresh basetemp outputs.

## Commands, report and handoff

Quality executable:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Use `-B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning` with
UTF8/bytecode settings and all numerical-thread variables fixed to1. Actual
timing microbenchmarks are advisory, never flaky pass thresholds.

Report full RED/GREEN commands/results, unchanged-predicate argument, cursor
ownership/cleanup/subclass behavior, all relevant frozen hashes, any test
failures and remaining risks. State exactly which source/bytes were tested.
Stage only the four exact owned paths (`git -c core.autocrlf=false`, force-add
only named ignored report), check staged inventory/diff, commit and return
empty index. No push, SSH, fullsuite, deployment or new subagents by implementer.
The skill scripts disappeared mid-session; use the already-read manual TDD/
immutable brief/independent-review workflow without claiming a missing tool ran.

## Acceptance owned by root

Fresh scoped review of immutable Task10 delta, then exact current-input native
FIRST. Failure holds release and avoids another premature fullsuite. Preserve
all limits: UID997/AS2GiB/CPU300/wall600/output1MiB and measured CPU/wall<300,
RSS<1GiB; input1GiB/history256MiB/cache64MiB/30queries/32slots unchanged.
Then meaningful fresh consumer-growth controls, historical profiles, actual
DAC/races, exact final fullsuite, fresh88DB backup/actualrestore/HMAC and latest
data recheck. The completed whole-branch review remains preserved; review the
new immutable delta independently without pretending old approval covers it.
Only actual acceptance permits normal main push, reviewed updater-only exchange
and separate exact app deployment. Cricket/A0/P4b3/empirical five-sport work
and the daily Tennis HTTPError/timeout are not completed by this repair.
