Spec Compliance ❌ — one Important transaction-lifetime defect requires correction.

⚠️ Unverifiable release gates: actual Linux DAC and concurrent path/file/sidecar races; valid >64-MiB input; fresh current-data complete replay; three representative growth generations; measured RSS/CPU/wall time. These remain controller gates, not failed local tests and not completed acceptance. No Task 2/3 completion judgment is included.

## Scope and evidence

Reviewed Task 1 brief, Global Constraints and Capacity contract, implementation report, and the supplied `0ac56fc..59b001d` review package. The initial tool output truncated the middle production hunks; that missing production section was retrieved explicitly. No Git operation, broad test suite, provider/VPS call, privileged fixture execution, or source/test mutation was performed. The only executed counterprobe used an in-memory SQLite connection and the current inventory class.

Focused unchanged-owner checks covered receipt/artifact decoders, exact tennis tuple-selection equivalence, schema integrity/orphan behavior, D2 subset consumers, and the actual authorized rollback writer. The reported 192-pass/12-skip and earlier 272-pass/16-skip results remain author-recorded evidence; this review does not relabel them as independently rerun results.

## Strengths

- The default explicit memory path retains the 64-MiB ceiling and has no automatic file-mode fallback. The new CLI switch is explicit; the public report construction remains unchanged.
- The sealed reader structurally checks root ownership, single-link regular files, restrictive mode, no-follow root-owned ancestry, DELETE header, companions, held descriptor/path metadata and streamed pre/post SHA256. SQLite is configured read-only/query-only with trusted schema disabled. App code need not run as root.
- Ordinary physical contents and all receipts are still validated, including unreferenced rows. The antijoin retains orphan rejection; owning decoders remain in use. Protected-final membership and retrieval do not body-decode those finals.
- Inventory values are freshly decoded rather than cached. Tennis descriptors retain neither histories nor decoded base/state caches. The unchanged selector is row-local and sorts by observed_at/digest, so single-row selection followed by the same global order preserves the complete tuple, including historical native revisions. Snapshot receipt lists and original mathematical replay remain exact.
- The 256-MiB canonical history admission applies only to sealed input, preserving old memory-mode and rollback admission. The implementation appropriately makes no constant-memory, Linux-positive, real-data capacity, or deployment claim.
- `model_artifacts.py:407-432` keeps both verification passes in the same BEGIN IMMEDIATE transaction, consumes the unchanged dictionary fields, and commits only afterward. No present rollback-writer regression was found.

## Critical findings

None identified.

## Important findings

1. **The transaction-bound inventory can silently revive in a different transaction.** `context_runtime_inventory.py:18-20` checks only the current boolean `connection.in_transaction`; it does not bind either Verified mapping to the transaction in which it was created. The lifetime check is used by iteration, length, membership and lookup. Consequently, COMMIT/ROLLBACK followed by BEGIN before the next access makes an old view appear valid again and exposes rows from the new transaction. A protected receipt view additionally carries its old protection classification into that new transaction, although its values now come from the replacement transaction. This violates the required transaction-bound verified-view lifetime: it is not merely a stale decoded-value cache concern.

   **Focused current-code counterprobe:** create an in-memory artifacts table, BEGIN, insert `old`, create `VerifiedArtifactMapping`, COMMIT, BEGIN, insert `new`, iterate the original mapping. Output was `original_transaction ['old']` followed by `old_view_after_commit_begin ['old', 'new']`; no trust error occurred. This is an API-lifetime defect, not a claim that the current rollback caller already follows this bad sequence. Documenting that callers must not do it does not enforce the promised binding.

   **Fix:** introduce an explicit verifier-owned transaction lifetime/lease (or an equivalent reliable transaction-generation guard) which is permanently invalidated when that transaction ends; require every mapping operation to verify that original lifetime. Integrate it without changing the authorized writer's transaction semantics or commandeering existing SQLite callbacks. Add focused COMMIT/BEGIN and ROLLBACK/BEGIN regressions proving that both artifact and receipt views, including protected views, cannot be reused in a later transaction; retain the existing closure/mutation tests.

## Minor findings

None requiring a change in this gate.

## Decision

**Needs fixes.** Correct the transaction-lifetime defect and obtain targeted independent re-review. Linux transport/race and empirical resource gates remain explicitly outstanding afterward; no unsafe root pytest fixtures or fabricated constant-memory assertion is requested.
