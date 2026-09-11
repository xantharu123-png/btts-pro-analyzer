# Task 8 design: original-only native projection from an owned complete basis

Date: 2026-09-11. Design only against the current Task7 checking implementation. Only this report is written. No product/test/index/Git/native/VPS actions, and no subagents.

## Conclusion

**Feasible as a narrowly equivalent original-checking representation, provided aggregate completeness is established by a cache-owned fixed full basis preparation, not by `_store` alone.** The proposed summary is sufficient for the exact native predicate in `_verify_live_original`; it is not a model-result cache. Every actual original still performs its existing publication/base/code/state checks, native-field checks, native-event equality, unchanged predictor call and predictor-result equality. Every snapshot still receives the full fresh tuple and runs all feature/transport calculations.

This requires an explicit implementation-plan refinement: Task4 says every consumer receives a complete tuple. That internal representation sentence cannot remain an asserted invariant once originals use the projection. The broader product spec does not mandate materializing unrelated history for this particular original check. It mandates causal/native identities, correction handling, exact model outputs, immutable histories and complete integrity checking, which this design preserves. The existing user-approved equivalent Tennis checking scope is sufficient if these proof obligations are met; no model/data/cap/source-hash authority is inferred.

No runtime acceptance is claimed. Controller evidence says exact Task7 actual input still failed CPU300. This proposal targets the measured repeated original-history reconstruction, not the unchanged cold basis, independent seal or snapshot feature work.

## Specification cross-check

Inspected:

- `docs/superpowers/specs/2026-09-07-kontextmodell-design.md`, sections4.1-4.3,9-11: preserve observation clocks/native identities, distinct correction revisions, causal reconstruction, exact numerical behavior and fully verifiable old identities/history.
- `docs/superpowers/plans/2026-09-07-kontext-d-validierung-release.md`, D4: complete SQLite/JSON/hash/reference/schema checks; exact artifact/manifest/row-count/forecast parity; consistent snapshots; no destructive history rollback.
- Recovery plan Global Constraints and Task4: full physical/unreferenced/source/final checks, exact native/predictor and snapshot replay, resource budgets and fresh complete tuples. Only the last original-specific representation requirement needs amending.
- Current `_verify_live_original`: its `history` is used solely to derive `target`, `newest` and `latest`. The predictor receives the actual decoded tour state and `workload_history=()`, not that history tuple. The history is not returned or retained by the original descriptor.

No broader inspected spec requires a complete original-only tuple as an observable result. Public `tennis_features_v3` and source selector tuple contracts remain unchanged; do not pass a projection to either function. Existing unresolved D1/D3 limitations and all empirical/activation claims stay unchanged.

## Exact mathematical sufficiency

Let `B` be the complete owning-selected maximum-cutoff basis for tour `t`, ordered by `(observed_at, digest)`. For original query `q=(event_key, cutoff, tour)`, define:

- `Hq = all rows r in B with r.observed_at <= q.cutoff`.
- `Sq = sum(len(encoded(r)) for r in Hq)`, over the **whole tour prefix**, not merely target rows.
- `Tq = all rows r in Hq whose event_key equals q.event_key`.
- `Lq = rows in Tq at its maximum observed_at`, or empty if `Tq` is empty.

The original only needs the complete-prefix admission result, whether `len(Lq)` is0,1 or greater than1, and the unique row when it exists. Thus the sufficient summary is `(Sq, latest_target_clock, multiplicity_in_{0,1,2plus}, candidate_ordinal_or_none)`. Saturating multiplicity at2 is exact because every count other than1 takes the same existing rejection branch.

Count **every target row**, including workload/non-status rows. Never select only statuses, only the referenced digest, or a single row per timestamp. A workload row at a later timestamp can make an older scheduled status invalid; a status plus another row at the same timestamp is not unique. There is no receipt deduplication in this fold beyond the owning complete basis itself.

The owning selector is row-local/cutoff-monotone and its evidence fields depend on receipt clocks, so completed maximum selection is sufficient to identify every earlier inclusive prefix. Full physical validation and all eligible opposite-tour source checks still happen in unchanged complete basis creation before projection authority exists.

## Non-negotiable completeness provenance

Current `_store` independently validates every encoded row but cannot prove that its caller supplied every eligible inventory row. A valid older-target-only tuple can omit a newer or equal-time competitor while every supplied row passes its seal. Consequently:

**Direct `_store` must never mint an authoritative original-native projection or an owner-completeness marker, even with a completed physical inventory stamp.** Its existing row-seal behavior remains valid and unchanged for Task6 witnesses. This distinction must protect the original's full-history fallback too: a projection miss followed by unrestricted `_replay_history(..., cache=cache)` could otherwise reuse the same incomplete direct-store tuple and incorrectly accept the original.

Introduce a private cache-owned preparation operation, for example `_prepare_original_basis(receipts, cutoff=..., tour=...)`. It must:

1. Check its exact completed inventory proof and internally planned cutoff/tour.
2. Invoke the fixed, unchanged `_cold_replay_history` through a fixed lazy import. No caller builder/callback, supplied history, completion flag or trusted token argument.
3. Feed that privately owned complete history through the existing independent sealing/storage pass.
4. Bind an entry-local owner-completeness marker and any derived query drafts to the exact newly completed entry serial and inventory proof only after successful cold completion, successful whole-entry seal and final lifetime/entry checks. The completeness marker is independent of query capacity: a genuinely owned complete basis may support a full-history fallback even when no aggregate query is retained.
5. Release the preparation history and all drafts on every exit.

A small private storage worker may be shared with ordinary `_store`. It can calculate drafts during the seal pass, but direct `_store` discards them and can never activate them. Activation is performed only inside the fixed owned preparation operation. Do not add a public or private caller-supplied `complete=True`/`trusted=True` switch.

Keep provisional drafts in cache-owned, accounted pending state until publication/discard; do not return a draft collection whose bytes/variable-length keys escape accounting. All new state is verification-local. A replaced entry, failed seal, interrupt or changed inventory prevents promotion. A direct subsequent `_store` replacement drops both the old owner-completeness marker and aggregate proof even if its rows happen to be equal. Reusing the same key, matching row bytes or retaining a physical validation stamp cannot transfer the former entry's completeness to the new serial.

The marker is bounded scalar metadata attached to the existing entry, not another byte pool, decoded value or separately retained history. Charge its representation alongside that entry within64MiB and the same entry metadata slot. There is no caller-supplied completeness flag. If its charge cannot fit, omit the marker and aggregate queries; originals then cold-fallback rather than treating a row seal as completeness. Query-cap-zero preparations still use the fixed owned cold builder and may publish this small marker without any query records.

## Planning and bounded metadata

Plan only actual original keys discovered from artifacts, with `validate_original_publication(..., created_at=...)` executed by the planning owner. A cache-private planning method can own the existing artifact scan. Extracted caller keys alone do not establish validated-original authority. Visit and validate **all** originals, including orphans and originals beyond the optimization's metadata capacity; the capacity limit is not an artifact-admission limit.

Deduplicate identical `(event_key, canonical cutoff, tour)` requests; their originals still replay individually. Continue discovering both maximum tour cutoffs over every original even when no further query can be retained.

Retain at most32 metadata slots in aggregate, counting both basis entries and planned/projected queries. Reserving the two possible tour-entry slots leaves at most30 query slots; zero retained queries is valid and uses the existing complete-history path. If existing generic entries consume slots, reduce/drop optional queries or evict under the current policy rather than exceeding the limit. Do not retain a second unbounded query list or per-receipt index.

Every variable-length query key and draft/final summary is charged against the same64MiB budget as retained and pending basis bytes. Long valid event identifiers must not create an uncharged metadata channel. Recommended accounting: retain bounded scalar/tuple metadata and charge its canonical representation size, without keeping a second encoded metadata copy. Reserve a conservative upper bound for each summary before streaming, so counters need not be canonically serialized once per row. Prefix byte totals and ordinals are bounded by the basis-byte limit; clocks have canonical fixed-width representation; multiplicity saturates at2. Charge any serial-width change before publication. Prove the reservation bound with boundary tests.

If a query reservation cannot fit, omit that optional query. If metadata pressure would prevent a formerly fitting basis, prefer discarding optional queries before bypassing the basis. Do not increase admission limits, retain uncharged drafts, or reject data merely because proof metadata does not fit. Pending plus retained basis and query charges must never exceed64MiB, including cross-tour construction.

Evicting/replacing a basis removes its owner-completeness marker, aggregate proofs and draft authority atomically. Any retained planning-only record must remain separately charged and carry no active serial/proof; the simpler implementation may discard those plans too and fall back later. Descriptors and lookup results never retain encoded entry tuples or hidden references that keep evicted data alive.

## Derivation during the existing seal pass

Use the exact fresh decoded row already passed to `_validate_selected_tennis_receipt_cold(json.loads(encoded))` during sealing. Do not perform another inventory scan or introduce another decoder. For each bounded planned query of this tour:

1. If its cutoff includes the row, add `len(encoded)` to its complete-prefix total, regardless of target event.
2. For an included target row, replace latest clock/count/ordinal when its clock is newer; at the same latest clock saturate count at2 and clear the unique ordinal.
3. Continue through **all** rows and all existing owner checks even when the target is missing, ambiguous, or already appears unsuitable for an original.

The fold costs O(N*Q) scalar operations with Q bounded by30 and retains no source payload. Derive from the independently validated encoded representation, not the possibly aliased pre-encoding input. Nonsealable original types, arbitrary direct-store histories and entries lacking owned completion cannot receive aggregate authority.

Do not raise native-original predicate failures during preparation: store count0/count2 as completed facts and let the corresponding original reject in its existing replay order. Publication errors already exposed by existing planning may retain their current earlier precedence.

## Original-only lookup and integration

A private `_lookup_original_native(...)` returns a distinct miss sentinel or an internally produced result containing multiplicity and, for count1 only, one fresh decoded candidate row. Absence and ambiguity are valid completed projections, not cache misses. No caller can pass such a result back as authority.

Lookup order:

1. Preserve the current owning publication/base/code/state checks in `_verify_live_original` before history/native processing.
2. Validate requested tour/cutoff using the existing empty owning selector guard. Require exact planned query key and current completed inventory proof, active basis and matching serial.
3. Enforce the **whole-prefix** canonical history admission budget using `Sq`, before native missing/ambiguity/status rejection. Use the existing comparison/error contract, not a new cap or candidate-only size.
4. If count1, locate only its retained ordinal, deserialize that one row into fresh nested objects, and recheck lifetime and exact entry serial after decoding. Count0/count2 also perform final lifetime/serial checks.
5. Execute the existing native predicate, `_same(_native_event(...), event)`, predictor and recorded-output comparison. The native predicate may be factored to consume `(multiplicity, candidate)` so projection and full-history fallback share one implementation; do not create a subtly different acceptance branch.

For an aggregate-query miss, first attempt a private **owned-complete full-history fallback**. It may materialize an exact/covering entry only when that particular current entry has a matching owner-completeness marker, serial and inventory proof. This path preserves the complete fresh tuple, exact inclusive prefix/order, full canonical admission budget and existing before/after/empty/final lifetime boundaries. It is available for unplanned queries and zero query capacity when a genuinely owned complete basis still exists.

If no such entry exists, use `_replay_history(..., cache=None)` and derive latest rows from its complete cold result. Do not call unrestricted `_replay_history(..., cache=cache)` merely because aggregate lookup missed: an arbitrary direct-store subset can still occupy that cache. This cold fallback need not publish a new aggregate proof or alter ordinary direct `_store` behavior.

The owned full-history materializer must bind the **actual entry used** to the checked key/serial, not just ask whether some complete covering entry exists and then let the generic lookup select again. In particular, an unowned exact-key entry must not shadow a proved covering entry. A small private `_lookup_owned_original_history(...)` can select and materialize only owned entries; alternatively it can conservatively miss whenever the ordinary preferred entry is unowned. Do not retain a whole encoded-entry alias; resolve the pinned entry during reconstruction and recheck its marker/serial after decoding and at completion. Pure replacement/eviction during reconstruction discards the candidate result and cold-fallbacks; inventory revocation or mutation remains a hard failure. A precheck followed by a separately reselecting generic lookup is not sufficient provenance.

For no cache, no owned-complete entry, oversized basis, unsealed entry or never-completed proof, the full cold path is mandatory. Revoked/failed inventory, mutation, DDL or closure is a hard trust failure, never an optimization miss. A stale serial caused purely by cache replacement/eviction means a miss after lifetime checks, not proof reuse. Neither aggregate nor owned-full misses may grant completeness to generic entries or inherit an old marker.

The current public runtime supplies `None` or a positive history limit. Preserve the underlying private helper's existing size/type behavior where it is contractual; add explicit empty-prefix/zero-limit/boundary tests and do not accidentally tighten comparable argument types. Do not let a proved absent target bypass a history-size error.

`verify_live_snapshot` remains unchanged: full fresh tuple, exact complete observation_refs, whole owning `tennis_features_v3`, feature equality and transport replay. No projection reaches model or feature code. No SQL query, inventory/transaction change, model hash change, persistent cache or result memoization is needed.

## Required rejection, lifetime and equivalence tests

- **Completeness forgery:** inventory contains a newer target or equal-time competitor. Direct `_store` of a fully valid older-only subset, even after real `validate_all`, must have neither aggregate authority nor an owner-completeness marker. Spy that original processing does not consume that generic cached tuple: it executes complete cold selection and rejects. Repeat for arbitrary empty/subset poisoning, exact and covering keys, caller-selected query keys and a physically valid but source-invalid row.
- **Owned fallback and replacement:** with query capacity zero, an internally owned complete basis has no query summaries but retains its charged completeness marker and supplies the exact full-history fallback without a cold rebuild. Replace that basis with a direct `_store` older-only subset at the same key; both its old marker and projections disappear, and original fallback cold-rebuilds and rejects. Also test an unowned exact-key subset shadowing an owned covering basis: the result must come from the actual owned entry or complete cold selection, never the subset. Replacement/eviction between fallback entry selection, row decoding and return cannot lend another entry's completeness to the result.
- **All-target semantics:** absent target; one scheduled status; later workload; status plus workload at identical clock; two status revisions at identical clock; newer cancelled/started/defective status; changed participant/schedule; wrong digest/native clock/competition revision. Native rejection and predictor-call counts must match the full-history reference.
- **Causal/budget exactness:** before/at/after cutoff, canonical timezone equivalence through existing input contracts, empty prefix, exact byte limit and one byte below, earlier small prefix under a larger basis, large unrelated history with tiny candidate, zero budget, oversized maximum and two-tour pressure. Complete-prefix budget failure precedes native absence/ambiguity failure.
- **No coverage loss:** malformed future/unreferenced physical rows, eligible opposite-tour source-invalid rows and actual unopened D2 finals retain their existing validation/body-decoder behavior. Orphan originals and originals beyond the query cap still receive every original/native/predictor check.
- **Publication lifetime:** interruption in cold preparation, final-row independent seal or draft publication; write/DDL/revocation/end/restart/closure between cold completion, storage and aggregate activation. No partial authority or uncharged pending metadata survives. Replace/evict the entry between preparation and activation; its old draft cannot become live.
- **Lookup lifetime:** mutation during candidate deserialization and after the final candidate, plus empty/ambiguous projections; schema changes, closure and proof failure hard-fail. Pure eviction/replacement triggers full fallback, not a stale result. Corrupt claimed-active metadata must not authorize an out-of-range ordinal or mismatched candidate.
- **Isolation/accounting:** mutation of one returned candidate cannot change a later one. No retained decoded row or entry alias in query records/descriptors. Metadata slots<=32; pending+retained total<=64MiB for completeness markers, huge keys, duplicate keys, excess originals and cross-tour builds. Dropped queries change performance only. Marker-budget failure takes cold fallback without a new data rejection. Eviction removes associated authority and charges.
- **Full replay parity:** compare canonical reports, native errors, limitation strings, source hashes and all original/snapshot call counts with projection enabled, disabled, evicted and capacity-bypassed. Every snapshot's full tuple/ref/features/transport path is exercised unchanged.
- **Performance gate:** exact uninstrumented current input and representative receipt+consumer growth under unchanged UID997/AS2GiB/CPU300/wall600/output1MiB and RSS target. Local counts and microbenchmarks cannot clear this gate.

## Risks and implementation stop conditions

The key risk is confusing valid rows with a complete basis, including on a query miss: either direct `_store` aggregate authority or an unrestricted generic-cache full fallback would make the proposal unsound. The second is hiding planned/draft/completeness metadata outside accounting or allowing a near-limit proof reservation to become a new data rejection. The third is native uniqueness drift from filtering statuses or deduplicating target rows. The fourth is retaining or transferring old serial authority after replacement.

Controller should record the original-only representation refinement explicitly before implementation/review, superseding the relevant Task4 sentence without weakening its full snapshot contract. If implementation cannot enforce owned completion, charged atomic publication and exact fallback, stop rather than grant a completion flag or skip checks. No broader product-spec conflict was identified for the precise design above.
