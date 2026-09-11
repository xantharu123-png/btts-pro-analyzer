# Task 6: Tennis selected-receipt checking design analysis

Date: 2026-09-11. Read-only design subtask against the controller's stated 7cf1e94 baseline. Only this report is written; no product, test, index, Git, deployment or VPS action was taken.

## Recommendation

Reuse the existing completed encoded history bytes as an exact-value validation witness, with a **new owning validation seal at cache storage** and a private, verification-local checking scope around the existing snapshot feature call. Do not add a receipt LRU, decoded cache, digest-only trust table, trusted argument, alternative feature implementation or result memoization.

Smallest recommended product scope:

1. `context_runtime_history_cache.py`: fully validate the encoded representation before sealing a completed entry; provide a bounded, non-owning entry cursor for exact-equivalence checking.
2. `context_sources/tennis_status.py`: retain the existing selected-receipt validator body as an unconditional private cold implementation; let the unchanged public signature consult a private scoped witness, otherwise execute that body.
3. `context_runtime_tennis.py`: enter that scope around the existing `tennis_features_v3(...)` call in `verify_live_snapshot` and leave it in `finally`.

**Leave `context_models/tennis_v3.py`, `context_models/tennis.py`, predictor and mathematical consumers byte-identical.** The current full tuple, every original/native/predictor replay, every snapshot feature calculation, receipt-ref comparison and mathematical transport replay remain in place. This is an equivalent checking repair within the latest approved amendment, not a new authority request. Actual runtime improvement still requires native measurement.

## Evidence and trust dependencies inspected

- The recovery plan's Global Constraints now explicitly allow narrowly equivalent Tennis/D2 checking changes, while prohibiting mathematics changes, cap raises, history deletion and hash whitelists. The older Task 4 owner-file freeze is historical, superseded only by that amendment.
- Task 4 and the existing cache retain one completed maximum-cutoff basis per tour, materialize fresh real tuples, and share a 64 MiB aggregate encoded-byte budget including pending entries.
- `context_runtime_tennis._cold_replay_history` executes owning selection on every eligible ordinary row, including opposite-tour Tennis validation before selecting its tour. Full physical validation remains upstream; unopened D2 final representations have no `source_schema` and remain unopened.
- `context_models.tennis_v3._history` calls `validate_selected_tennis_receipt` for every tuple row before event, cutoff, tour and participant projection. The remainder resolves native revisions and invokes the unchanged v2 feature implementation. The v2 implementation still performs its own factor/workload checks on its selected rows; this recommendation does not remove those checks.
- `validate_selected_tennis_receipt` repeats normalization, strict JSON validation/copying, timestamps, canonical encodings, content and receipt hashes, then native status/workload validation. Native status validation additionally reconstructs its normalized envelope and reception identity. These are row-local checks; they do not depend on the consuming event or its model parameters.
- `model_artifacts.canonical_bytes` is ordinary `json.dumps(... sort_keys=True, allow_nan=False ...)`. It is **not** a typed identity: tuple/list and many subclasses can encode alike. `contracts.require_object`, `require_list`, `require_number` and `_sport_json` intentionally impose exact Python types. Therefore canonical equality alone is insufficient.
- `VerifiedReceiptMapping` owns its completed physical proof and permanently revokes it on failed/interrupted validation. The existing cache pins exact mapping identity, transaction generation, changes, main/temp schema, validation stamp and open transaction. Physical proof alone is not a Tennis selected-receipt proof.
- Critically, current `EncodedHistoryCache._store` assumes its caller supplied completed owning-selector output. Its constructor and `_store` arguments cannot, by themselves, justify a new skip of selected-receipt validation.

## Alternatives considered

### A. Validator-only algebraic/serialization optimization

Hoist fixed field sets, reuse repeated timestamp/canonical calculations, and replace redundant reconstruction only where equivalence is independently demonstrated. This needs no cache capability and leaves ordinary calls simple. However, substantial savings would require changing the composition of general B1 normalization and source-specific validation. Those checks overlap but are not interchangeable: normalized JSON shape, prohibited names, clocks, hashes, source identity and native status semantics all matter. An informal direct-field rewrite is high-risk, while small hoists cannot be assumed to solve consumer-count growth. Keep this as a separately profiled follow-up, not the primary design.

### B. Receipt-hash LRU or a new prevalidated tuple/callback API

Reject digest-only memoization: a changed payload with an unchanged digest must fail, and untyped canonical identity aliases rejected objects. A second encoded LRU duplicates history bytes and competes with the 64 MiB basis. A per-row index adds avoidable retained metadata; a decoded or frozen history conflicts with fresh consumer ownership. A public trusted flag/callback or fake tuple broadens the owning API and makes the caller a proof authority. None is needed.

### C. Sealed existing bytes plus exact current-value checking

Recommended. The stored bytes are already necessary for reconstruction. Seal their actual decoded representation once with the full owner, then compare each current row against that same retained representation under strict type equivalence. This replaces repeated semantic derivation with an O(row-size) exact-value proof. It still iterates every history row and never memoizes event-specific calculations.

## Precise bounded API and implementation outline

Names below are proposals, not implemented interfaces.

### 1. Seal only actual completed owner-validated bytes

Factor the existing body to `_validate_selected_tennis_receipt_cold(row)` without altering its checks or return value. Its public wrapper remains `validate_selected_tennis_receipt(row)`.

In `_store`, apply the recursive exact plain-JSON eligibility guard to the **original row before encoding**. This prevents an invalid tuple/subclass input from being laundered through `json.loads`. For a non-plain original, run the unconditional cold validator on that original: propagate its rejection; if it accepts an edge case, preserve acceptance but do not seal that entry for acceleration. This is not permission to globally reject types which the old owner accepts in some metadata fields.

For each eligible canonical encoded row which the budget permits retaining, deserialize that single row and call the **unconditional cold** validator. Do not consult the scope when creating proof. This proves the actual plain JSON representation later delivered by cache materialization, not an assumed pre-encoding caller object. A completed inventory stamp is additionally required before the entry can support accelerated checking. Never-validated mappings retain the ordinary full-validation behavior.

Only after every retained row passes and the final existing lifetime checks pass may the entry be published with a new internal entry serial. No caller provides a seal, a validated boolean or a validation callback. The entry serial and bounded metadata identify one completed publication, not new data authority. A failure/interrupt publishes nothing and clears pending accounting exactly as today. An oversized build still bypasses the optional cache; it cannot truncate or reject a valid smaller consumer history.

This introduces one extra full selected-row validation pass per stored fitting basis. The conservative extra pass is intentional: current `_store` is not a proof-producing owner. It is preferable to a subtle caller-granted completion mechanism. If the controller's profile shows that pass is too costly, a separately reviewed owner-produced completion design would be needed; do not silently omit the seal.

### 2. Scope contains metadata, not retained history

Provide a private context manager such as `cache._selected_receipt_scope(receipts, cutoff=..., tour=...)`. It identifies the exact or existing completed covering entry using current selection rules and installs a private `ContextVar` witness consumed by the selected-receipt wrapper.

The concrete private witness can be `_SelectedReceiptScope`, minted only by the cache's context-manager factory after inspecting the current completed sealed entry. It stores only cache reference, exact inventory reference if necessary, entry key, entry serial, ordinal and bounded active-state metadata. It holds **no encoded entry tuple, row bytes, digest-to-row map, decoded row, full history or iterator/generator that closes over an entry**. Serial/key lookup is performed against the current cache on each attempted hit. Eviction removes the bytes and their proof together; an old witness cannot keep them alive. Never recreate a proof from a saved serial or stamp alone.

Entry and exit check the lifetime even for empty histories. Use ContextVar token reset in `finally` and deactivate the witness at exit so a copied context cannot continue using a closed scope. Nested scopes restore the previous token correctly; each factory call gets its own witness, never reactivates an old one, and reentrant use of the same witness is not allowed. Do not offer a public generic setter accepting an arbitrary validator callback. If the source module accepts an internal witness object, validate its exact implementation type/active state rather than invoking an arbitrary callable as authority. An unrelated object placed in the private context must confer no authority and use the ordinary validator, never an arbitrary object's method.

### 3. A hit proves the current row, not just its identifier

At each `validate_selected_tennis_receipt(row)` call:

1. No scope means the unchanged cold implementation immediately.
2. Check the scope's active lifetime and the cache's exact current inventory proof. Revocation, mutation, DDL, ended/restarted transaction or closure is a hard failure, never a cache miss.
3. Resolve the entry by key and serial and current ordinal. Missing/evicted/replaced/unsealed entries mean ordinary cold validation, not acceptance or invalidation of otherwise valid input.
4. Check recursively that the candidate consists only of exact built-in `dict` with exact `str` keys, exact `list`, exact `str`, `int`, `float`, `bool`, or `None`. This is an optimization eligibility guard, **not** a replacement schema validator. Any other type or guard/encoding failure falls back to the original validator, preserving its accepted/rejected behavior instead of introducing a new unconditional rejection. Thus valid-but-ineligible edge cases remain supported.
5. Canonically encode that one current row and compare its bytes directly with the sealed retained row at the ordinal. Do not compare only a caller digest or Python equality (`True == 1` is another trap). No byte match means cold validation. A valid differently ordered/duplicated/mutated row is not rejected merely because it misses the acceleration.
6. Recheck lifetime, entry presence and serial after the comparison before returning the same current row. Advance the bounded cursor per call; fail-safe loss of alignment only reduces hits. A match at a different ordinal is not searched with an unbounded index or new cache.

For exact JSON trees, canonical equality preserves the field/value representation used by these validators; strict types exclude tuple/list and subclass aliases. Numeric encodings distinguish bool/int and int/float. A nonfinite value cannot produce a canonical hit. Every field, including evidence metadata and supplied hashes, participates in the comparison.

The ordinary one-row serialization/decoding work buffers remain transient, as in current cache construction; they are not retained encoded cache entries. Every retained/pending encoded entry still shares the same 64 MiB counter. Do not retain even a whole-entry local alias across a call that can evict it; retrieve only the one comparison row and recheck its entry afterward.

### 4. Integration is deliberately narrow

Wrap only the already existing `tennis_features_v3(payload['event'], history, original, cutoff=...)` invocation in `verify_live_snapshot`. Do not replace it, pass a different tuple, move its mathematical internals or bypass the following transport replay. Scope absence, no cache, oversize basis, eviction and unsupported ordinary inputs all use the original path. There is no need to edit v3 or its signature.

Leave maximum-cutoff construction, full physical proof, causal selection, opposite-tour eligible validation and protected-final handling intact. Original model/native replays remain unchanged. A local caller using the normal feature API outside this D4 scope cannot obtain a new trusted-input path.

## Required RED/GREEN regressions

Use real source validators and existing SQLite/native fixtures; spies count calls only and do not replace validation.

- **No forged storage proof:** directly attempt `_store` with B1-valid but Tennis-invalid selected data and with raw type aliases. No sealed entry appears. Repeat with failure/interrupt on the final row and inspect pending bytes. A physical validation stamp alone must not turn these rows into hits.
- **Value/type alias rejection parity:** warm a valid row, then test nested tuple for list (`participant_ids`, `workload_receipts`, `issues`, `set_scores`), dict/list/string/integer/float subclasses, subclass dictionary keys, bool for number, nonfinite numbers, missing/extra fields, modified payload/metadata with unchanged hashes and self-consistently rehashed but source-invalid rows. For each, compare ordinary and scoped accepted/rejected outcome; do not assume every subclass field is rejected by the old validator. Include valid changed rows that must fall back and remain accepted.
- **Every row checked:** malformed future, unrelated participant/event and opposite-tour rows in a direct feature tuple still reach the original validator when not proved; verify upstream full physical and eligible opposite-tour selector checks are unchanged. Include real unopened D2 final fixtures with zero body-decoder calls.
- **Exact model output:** compare canonical complete feature vectors, states, refs, coverage, reference hash and final reports for old/new paths using paired, legacy-only, mixed, unavailable, equal-time conflict, revised participant/schedule, target-state, orphan-original and cutoff/timezone fixtures. Spy that every actual original and snapshot retains its native/predictor/feature/transport calls.
- **Fresh ownership:** mutate one materialized consumer's nested payload and verify the next consumer receives unchanged fresh data. A mutated current consumer cannot hit by its old digest. Preserve a real tuple and reject the same tuple subclasses/other containers as v3 currently does.
- **Lifetime:** never-validated, failed/interrupted validation, different mapping, total_changes, main/temp DDL, transaction end/restart, connection close, and mutation during comparison or after last row. Empty scope entry/exit also fails closed. Nested scopes, exception exit and copied inactive contexts do not leak acceleration.
- **Budget and eviction:** both tours compete for the single limit; pending plus entries never exceeds it. Evict/reinsert the same key while a scope exists: old serial cannot retain or authorize old bytes; subsequent calls cold-validate. Inspect witness fields to ensure no byte/row/iterator retention, and prove normal garbage collection after eviction. Exercise zero budget, empty bases/metadata bound and oversized maximum with valid small prefix.
- **Performance:** count cold owner calls so repeated snapshot receipt checks demonstrably become equality checks, while one storage seal is observable. Then run exact uninstrumented native current input and G1/G2/G3 with growth in receipts **and consumers/cutoffs**, unchanged UID997, AS2 GiB, CPU300, wall600, output1 MiB and RSS target below1 GiB. Passing unit tests is not a runtime acceptance claim.

## Compatibility and remaining concerns

- `context_models.tennis_live.CODE_PATHS` pins six predictor/state files, not `tennis_v3.py` or `tennis_status.py`. None of those pinned files needs editing for this design. No historical hash whitelist is justified.
- `context_models.evaluator.implementation_hashes()` includes `context_models/tennis.py`, `tennis_effect.py` and **`dataset.py`**, but not this proposed Tennis three-file scope. Keep the legacy math files unchanged. The concurrent D2 dataset checking repair genuinely changes its implementation hash: old reports must continue to fail exact current-hash comparison where required; do not conceal or normalize that change.
- A ContextVar keeps the public feature API and mathematical file unchanged, but adds a subtle dynamic checking dependency. Keep it private, short-lived and fully tested; never let a generic callable supplied by a caller become authority.
- This design eliminates repeated selected-row semantic validation on fitting stored bases, not full physical validation, cold selector construction, JSON reconstruction, v2 checks or event math. The extra seal has measurable cost. The controller's in-progress native phase profile decides whether sufficient headroom remains; no performance result is claimed here.
- Controller-supplied in-progress G1 observations received during this analysis: physical validation41.045 CPU seconds; one cold basis91.672 CPU seconds; retained56,865,423 bytes with zero evictions/bypasses; old original prefix reconstruction approximately1.1 seconds, old-cutoff snapshot checks approximately9.1-10.1 CPU seconds. These observations support testing the one-extra-seal tradeoff, but are not a completed native acceptance run and were not independently executed by this design subtask.
- Failure precedence can move to the entry's sealing pass, already after completed selection; it must not change valid input admission or hide an invalid input. Scope misses must not become new schema rejections. True lifetime corruption remains fail-closed.

No genuinely new authority is needed for the proposed equivalent checking scope. A future proposal to change model outputs, pinned legacy mathematics, validation acceptance, budget, data retention, source compatibility rules or external deployment scope would need separate direction.
