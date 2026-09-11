# Task8 independent scoped review — 7bab03c, fix required

Reviewer `/root/tennis_check_task8_review`, BASE06db3be..HEAD7bab03c,
supplied package91046bytes. Controller verified the reported loop lifetime
against `_store_encoded` and `_make_room`; no plan conflict, waiver or
production mutation. Complete review verdict follows.

## Spec Compliance

- Issues found: dropped-query metadata can survive outside accounting during
  sealing, violating the explicit retained-plus-pending budget contract.
- Owner-completeness and fallback provenance otherwise match the refinement:
  fixed cold preparation, serial-bound markers, independently sealed folds,
  pinned owned-full reconstruction, and cache-disabled cold fallback.
- Cannot verify from this scoped review: exact current/G1/G2/G3 native
  capacity, full-repository/platform acceptance, protected-file byte identity
  beyond the supplied diff, or release prerequisites. The reported962passes
  and baseline-oracle results were not independently regenerated.

## Strengths

- cache:279: completeness comes from fixed cold-owner preparation plus
  completed independent sealing; ordinary `_store` cannot mint the marker.
- cache:340: projection enforces whole-prefix admission before native
  rejection and rechecks the actual serial after candidate decoding.
- cache:366: full fallback reconstructs the pinned owned entry; an unowned
  exact-key subset cannot shadow its authority.
- runtime-tennis:110: projection/full/cold paths converge on the same native
  predicate; cold fallback explicitly disables generic cache reuse.
- projection-tests:49: substantive persisted-fixture tests cover subset
  forgery, serial replacement, mutation, native parity and complete snapshots.

## Important finding — verbatim technical finding

`context_runtime_history_cache.py:510`: **The last `query` loop variable remains alive across subsequent rows after `_make_room` drops and uncharges that record.** Python retains the loop variable in `_store_encoded`'s frame. When subsequent pressure removes it from `_queries`, its scalar draft and potentially long key remain owned by the still-running seal, outside the reported metadata budget. This is not merely a conservative-reservation discrepancy: at the exact history budget, the pending history alone fills the limit while the removed draft still exists.

- Focused real-fixture diagnostic reproduced this at a **13,690-byte budget**: final sealing step had **13,690 pending bytes, zero charged metadata, zero retained queries**, but the frame still held a dropped query with a **268-byte reservation**. Reported peak remained13,690.
- Clear query references before subsequent pressure operations, preferably through a short-lived folding helper, and add a regression observing actual dropped-record lifetime. The existing accounting test at `tests/test_context_runtime_original_projection.py:227` checks counters, which cannot detect this hidden reference.

No Critical or Minor findings identified. **Task quality: Needs fixes.**
Completeness, admission ordering and serial-bound fallback are carefully
implemented, but the confirmed hidden draft reference violates a binding
resource invariant.

Reviewer checks: supplied diff read once, only truncated output restored;
unchanged cold replay/inventory validation/cutoff callees and the real fixture
inspected for the named risk; one focused lifetime diagnostic. No suite
rerun, file/index/HEAD mutation, SSH or deployment action by reviewer.

## Controller follow-up within the same retained-reference finding

Root inspected the callers for the same lifetime class and identified the
last `query_key` in `_store` and last `key`/publication temporaries in
`_prepare_originals` surviving into basis storage. The implementer confirmed
three additional actual REDs: key refcount3rather than2in each parent frame,
and2validated publication temporaries still alive during basis work. These
are included in fix round1, not waived as counter-only discrepancies.
Short-lived owned planning/drop helpers preserve the existing scan/drop logic
and free their frames before storage. The scoped rereview must cover these
same-class sibling paths as well as the original folding-frame finding.
No independent approval of that fix is implied by the targeted GREENs.

## Fresh scoped Fix1 rereview —07d975f APPROVED

Reviewer `/root/tennis_check_task8_rereview`, immutable package
`review-7bab03c..07d975f.diff` (1commit,27699bytes). Complete verdict:

Finding verdict: RESOLVED.

- Original fold-frame leak addressed: `_fold_original_queries` returns
  before later proof/pressure operations, releasing its last query reference.
- `_store` sibling addressed: `_drop_original_tour_queries` returns before
  `_store_encoded`, releasing query_key.
- `_prepare_originals` sibling addressed: `_plan_original_publications`
  returns before basis preparation, releasing key/publication/origin/envelope.
- Tests observe actual weak-reference/refcount lifetimes including4096-digit
  keys, not merely accounting counters.
- No new Critical, Important or Minor regression found in the three helpers
  or their call ordering. No out-of-scope code findings.
- Final118-test coverage was not rerun because source scrutiny left no
  unanswered specific doubt. Native profiles, protected-file identity,
  full-repository acceptance, publication and deployment remain root gates.

Round verdict: all addressed / no new Critical or Important findings.
Root separately rehashed all16frozen owners/helpers/math files after Fix1;
every expected byte identity is preserved. No release waiver follows.
