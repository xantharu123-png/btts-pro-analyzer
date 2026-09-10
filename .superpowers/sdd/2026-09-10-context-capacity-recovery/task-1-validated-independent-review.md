Spec Compliance ✅ — APPROVED for the validation-owned cutoff refinement.

⚠️ Fresh exact-final-revision native current-data and multi-generation capacity acceptance remains open. The prior largest-growth CPU-limit failure explains this refinement; passing local correctness tests does not resolve that resource gate.

## Scope and independent evidence

Reviewed the second measured-refinement plan paragraph, the supplied `02d1232..8249c288d69337b50e1fde4209171836abba190f` diff and the appended implementation report. The review was scoped to complete-validation ownership, proof lifetime, selective replay parity and new cross-cutting call-site behavior. No source/test/Git/VPS changes or broad test suite were performed; only this report was written.

Independent targeted command, with all four numerical-library thread limits set to one:

`python -B -m pytest tests/test_context_runtime_capacity.py -k 'validated_cutoff or encoded_history_cold_path_keeps_full_validation' -q -p no:cacheprovider --basetemp=.pytest_tmp/validated-independent-review`

Result: **20 passed, 72 deselected in 8.09s**. These include malformed future/unrelated inputs, eligible opposite-tour typed corruption, complete-pass decoder counts, never-validated fallback, boundary/timezone parity, failed/interrupted validation, orphan/content errors, ordinary/DDL/transaction mutation, started iterators and existing warm-cache revocation.

The author's **213 passed, 12 skipped**, including the approximately 63-second real protected-final case, is separately recorded evidence. That expensive case was inspected in the diff and report but not independently duplicated here.

## Contract assessment

- **Complete physical pass preserved:** `context_runtime.py::_verify_observations` now delegates to `VerifiedReceiptMapping.validate_all()`. The diff preserves the former ordering: collect protected-content identities, inspect every content hash/canonical ordinary body, inspect every receipt via existing lookup/owning decoder, then reject orphan contents. No time, tour, activity or reference filter is applied to this complete pass. The returned content count and absent-observations behavior are preserved.
- **No premature proof:** `validate_all()` captures the inventory stamp before the pass, compares it afterward and publishes the completion stamp only after every check succeeds. A failing or interrupted pass revokes the instance under `BaseException` and re-raises; it cannot retry into a trusted state. A new mapping receives no inherited completion.
- **Permanent lifetime enforcement:** generation, total_changes and main/temp schema cookies bind the completed capability. The selective iterator checks the stamp before reading, between rows, after lookup, after yield resumption and at exhaustion. Failed validation also rejects ordinary mapping access, so an already-populated encoded cache cannot outlive that failure through a warm hit. Existing cache mutation and transaction guards remain intact.
- **Selection equivalence:** a never-validated mapping still yields the full `.values()` stream. Only a successfully validated mapping may compare canonical receipt clocks to the inclusive cutoff before ordinary decoding. The owning selector already excludes future rows before its selected-row typed checks; all eligible rows from both tours still pass through that same selector. No source/event/tour/participant/revision pruning is added, and exact tuples, sorting, receipt references, numerical replay and admission budgets are unchanged.
- **Protected finals remain opaque:** every protected receipt is included regardless of clock, and retrieval retains its existing outer-only representation. The full pass preserves hash-only protected content handling. The amended real-final test additionally asserts that an early cutoff retains exactly those opaque refs, while retaining its owning-decoder guard and unrelated-corruption failure assertion.
- **Scope remains narrow:** the sole cold-replay integration change chooses the new iterator for VerifiedReceiptMapping; ordinary mappings retain the original values path. No new index/schema, caller-supplied completion boolean, generic decoded cache, callback, public report field or owning model/source change appears in the patch.

## Findings

Critical: none identified.

Important: none identified.

Minor: none requiring a change in this scoped gate.

## Gate result

**APPROVED.** The refinement preserves the mandatory complete validation before using the narrower repeated-decoding path and meets its targeted lifetime/parity checks. Prior closed transaction/cache/schema findings remain closed. Native CPU/wall/RSS, current-data and growth-profile measurements must use this amended implementation and remain release gates; no claim of bounded unlimited growth or successful deployment is made.
