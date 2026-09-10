Spec Compliance ✅ — APPROVED for the scoped schema-invalidation fix.

⚠️ Exact-final-revision Linux current-data/growth performance and capacity acceptance remain controller-owned and open. This is correctness approval, not release or native resource approval.

## Scope and evidence

Reviewed only the supplied `c871999..4fad0983b7595d1be260b652b216fedb8b9fb8a1` diff and the appended schema-fix implementation evidence (code commit `7d6595e`). No unrelated plan/code rescan, Git/VPS operation, source/test edit, or broad suite occurred. Prior positive cache findings remain applicable; this review addresses the original schema invalidation finding and new breakage in its narrow fix.

Independent focused command, with all four numerical-library thread counts fixed to one:

`python -B -m pytest tests/test_context_runtime_capacity.py -k encoded_history_schema_change -q -p no:cacheprovider --basetemp=.pytest_tmp/cache-schema-independent-review`

Result: **16 passed, 58 deselected in 4.74s**. The author's 32-cache-test and 194-adjacent-test results are separately reported evidence and were not independently rerun here.

## Original Important finding

**ADDRESSED.** The original exact counterexample was: create receipt/content tables on a TrackedConnection, BEGIN, construct VerifiedReceiptMapping and EncodedHistoryCache, cache an empty ATP history, then execute `DROP TABLE context_observations` through the ordinary connection. Generation and total_changes remained unchanged; formerly, the warm cache returned `()` while the uncached path raised missing-table OperationalError.

`context_runtime_history_cache.py:30` now captures schema identity, `:44-49` reads both main and temp schema cookies, and `:54-59` includes them in the existing permanent invalidation condition. The independently passing DROP cases reproduce the unchanged original counters and the cold missing-table error, but now require the cached path to raise RuntimeArtifactTrustError. Repeated accesses reject and stored/pending accounting is cleared.

The tests also cover CREATE, ALTER and ordinary temporary-table shadowing through both connection and cursor APIs, with populated empty-history entries and not-yet-populated caches. Pinning temp is relevant because the receipt inventory uses unqualified table names. Once invalidation has occurred, the existing `_invalid` guard remains permanent; restoring tables cannot revive that cache instance.

## New breakage review

No new Critical or Important issue identified in this fix.

- Existing inventory identity, transaction generation and total_changes guards remain intact.
- Both PRAGMAs are read-only metadata checks; they neither decode protected bodies nor change the owning selection, numeric replay, public report, history/cache budgets or transaction semantics.
- Schema errors enter the existing fail-closed invalidation path. No callback interception or SQL parsing is introduced.
- The previous cache review's positive findings about fresh decoded values, completed-only entries, bounded bytes/metadata, cold-path completeness and per-consumer numeric replay are preserved.

Deliberate hostile manipulation of SQLite internals or base-class dispatch bypass is outside the established normal consumer API scope and is not requested as additional hardening.

## Gate result

**APPROVED.** The original Important schema-mutation finding is closed. Native measurements must use this amended implementation: the two added metadata queries also run during pending-row checks, so the earlier provisional cache benchmark is not final performance evidence. Current-data, growth-generation, RSS/CPU/wall and release gates remain open.
