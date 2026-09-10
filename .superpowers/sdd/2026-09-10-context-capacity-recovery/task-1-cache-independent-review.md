Spec Compliance ❌ — Needs fixes for one Important cache invalidation defect.

⚠️ Native current-data/growth runtime, RSS and capacity acceptance remain open. This review neither promotes the 64-MiB candidate cache budget to a measured supported profile nor claims production release readiness.

## Scope and independent evidence

Reviewed the measured Task 1 refinement and Global Constraints/Task 1 contract, and the supplied `d488350..c3bac371dede2f7ac825fc8f38f22f75f69d7919` diff in two bounded sections. No Git/source/test/VPS modification or broad suite was performed. Only this report was created.

Independent targeted execution, using the quality Python with numerical-library thread counts fixed to one:

`python -B -m pytest tests/test_context_runtime_capacity.py -k encoded_history -q -p no:cacheprovider --basetemp=.pytest_tmp/cache-independent-review`

Result: **16 passed, 42 deselected in 4.91s**. These tests cover eight consumers/two cold passes, fresh nested objects, typed cutoff rejection, exact small history admission on hits/misses, eviction/oversize bypass, transaction and ordinary DML mutation rejection, failed-build cleanup, bounded empty entries, full cold-path validation and actual D4 cache sharing. The separate approximately 60-second actual protected-final test was not duplicated; its added cold/hit decoder-guard assertions were inspected in the diff and its execution remains author/controller evidence.

An additional focused in-memory counterprobe tested an unanswered schema-mutation case; details follow.

## Strengths

- Cache entries contain per-row canonical immutable bytes, not retained decoded inventories. Warm consumers receive newly decoded nested objects and a real tuple. The cold owning decoder/selector path and total ordering are unchanged.
- Complete-history admission is rechecked on hits. Cache pressure evicts or bypasses rather than truncating a history; pending entries are not published until completed, and failed encoding clears pending accounting. Empty-history metadata is bounded to 32 entries.
- A shared verification-local cache is attached to small descriptors. Numeric original prediction, state checks, feature replay, exact observation-reference binding and context replay still execute for each consumer; none of those checks is replaced by a cache hit.
- Cache keys preserve tour/canonical cutoff distinctions, with an explicit owning-selector typed-argument check before either hit or miss. Receipt-object identity, tracked transaction generation and ordinary write-count changes are guarded; permanent invalidation clears stored entries.
- Public JSON, old input-mode limits and owning predictor/feature/source files are not changed by this patch.

## Critical findings

None identified.

## Important findings

1. **Schema mutations can leave the cache valid even though its receipt inventory no longer exists.** `context_runtime_history_cache.py:43-49` relies on transaction generation and `total_changes` to detect mutations. SQLite does not increment `total_changes` for DROP/ALTER/CREATE schema operations, and a successful DDL statement inside an existing transaction does not end that transaction. Thus the exact-inventory guard can pass after a normal same-transaction schema mutation; `_lookup` then returns cached output without the failure the unchanged cold path would produce.

   **Independent current-code counterprobe:** on a TrackedConnection, create the two receipt/content tables, BEGIN, create VerifiedReceiptMapping and EncodedHistoryCache, and cache an empty ATP history. Execute `DROP TABLE context_observations` through the normal tracked connection. Both generation and total_changes remain `(1, 0)`. The warm call returns `()`, whereas the same `_replay_history(..., cache=None)` raises `OperationalError: no such table: context_observations`. This requires neither base-class bypass nor direct cache-field tampering. An already-created protected view/cache likewise retains its old classification; the claimed permanent-on-mutation invariant does not cover this ordinary SQLite API case.

   The production query-only verification flow does not itself execute this DDL, and no current rollback-owner exploit is claimed. Nevertheless, the cache is explicitly usable on verified writable transaction views and the approved contract requires binding to the exact inventory and invalidation on mutation. This is the same class of fail-open API-lifetime mismatch that the earlier generation fix was intended to remove.

   **Fix:** additionally pin/check the relevant SQLite schema generation (for example the main schema cookie) or reliably advance the owned connection generation on schema changes, without SQL parsing or callback commandeering. Keep ordinary DML and transaction guards. Add a targeted same-transaction DROP/ALTER regression showing both warm and subsequent cold attempts fail closed and that the cache stays permanently invalid after the original schema is restored. A small schema-guard check must not decode protected-final bodies or substitute for existing full validation.

## Minor findings

None requiring a change in this scoped gate.

## Decision

**Needs fixes.** Address schema-change invalidation, run focused regression/counterprobe evidence and obtain scoped re-review. Real Linux current-data and growth capacity gates remain explicitly open regardless of the cache correctness gate; retaining complete replay is mandatory even if the measured runtime still misses the candidate profile.
