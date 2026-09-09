# D3 implementation packets after the read-only producer preflight

Date: 2026-09-09. The original `PREFLIGHT.md` is frozen unchanged at SHA-256
`bfe0aee8faa5815cc950b3c9b62d8e1f5012ce5c0d0719a090a23e954b5d09fd`.
This addendum separates small executable work packets; it is not implementation evidence.
Root authorized Tennis producer work next, in a new worktree on `da0ae346`.

## P1: real original Tennis winner producer (next authorized packet)

Owner: producer agent. `tennis/predict.py`, `scripts/tennis_daily.py`, `tennis/shadow.py`,
new owning original/context-coordinator modules, dedicated tests/audit. Root separately
owns the shared consumer/Domain/UI reader. No serve, native historical alias, provider or
production changes; no activation/transport/core-domain edit without explicit agreement.

Proposed interfaces submitted to Root before code:

- Optional `predict_match(..., original_capture=None)` reports directly computed
  unrounded values from the same invocation, without modifying the default return shape
  or calculating again. Collector is owning/internal, not an empirical-authority flag.
- Explicit original version `tennis-live-calibrated-winner-v1`; actual singles grouping,
  not invented BO rules. A1 kind `tennis-live-winner-original-v1` binds actual original
  Event/cutoff, loaded tour-state artifact, original inputs, code and direct probabilities.
  It contains no Base to avoid a hash cycle; its digest is the proposed Base model identity.
- Prepare, then leave the existing capture scope, then read actual B1 history and resolve
  the actual A1/D2 inputs. Keep the original prediction decision; do not backdate late
  evidence or replace its clock with the capture finish time.
- Write the optional closed `context_model` into the existing `context_json` of the exact
  new prediction revision, inside its append transaction. It carries full Event, cutoff,
  exact existing four-field consumer reference, A/B canonical winner mapping and original
  artifact hash. Old absent fields/serialization/IDs remain unchanged. No latest-row lookup.
- Root's `context_consumers.load_context_market(path, reference, selected_market, *,
  expected_event, expected_cutoff)` verifies stored identity and returns a detached projection.

RED witnesses before implementation: actual same-call non-four-decimal value survives;
spy shows one original prediction; source receipt appears only after capture publication;
malformed/newer native participant/status/schedule revision cannot reuse old source;
real A1 state bytes and cutoff differ from a manufactured hash; exact shadow revision is
linked despite duplicate original prediction IDs; failed transaction adds no link;
missing/SofaScore/legacy original remains a valid old baseline; no approval leaves p
unchanged; changed price cannot change context identity; no provider call in pending refresh.

## P2: shared normal/RisikoBet consumption (Root, after P1 shape agreement)

Add optional reference-aware fields/projection to actual readers and serializers, not a
second historical adjustment. Both sides/markets use the same B3 reference and existing
owning market mapping. New optional fields are absent on legacy rows, not emitted as null.
Read-only lookup does not use `compute_once`, refit a model, resolve a provider or load
an arbitrary current Event by label. Expected full Event and cutoff come from the exact
stored model revision. Require actual UI/serialization regressions plus identical shared
reference/probability in ModelSignal and RisikoBet. Keep existing historical/ticket IDs.

## P3: Basketball/Hockey original export at the actual first computation

This is an important precision over the preflight's existing callable export list:
the current Basketball wrapper invokes `predict_prematch` again and then `_fit`/`_predict`;
Hockey's `_original_parts` likewise normalizes and invokes the fit/predict path again.
Caching often avoids another optimizer run, but does not make these wrappers a true
same-call original export. They must not become the production attachment strategy.

Small owning change, separately authorized when reached:

1. At the existing `sports_prematch.predict_prematch` invocation, preserve the actual
   `_Identity`, normalized `_Match` tuple, `_Fit`, `_predict` output probability and full
   `values`, input hash and frozen decision in an optional detached collector before
   returning formatted factor strings. Do not add a field to default `PrematchPrediction`
   serialization or invoke `predict_prematch` again from the collector.
2. Internal C2/C3 constructors consume those already computed parts. Basketball takes
   exact mean/scale/p; Hockey exact two rates, conditional OT conversion and original
   regulation/inclusive probabilities. The target/selected source projection is bound to
   these parts; no rounding, clipping, re-estimation or inferred native identity.
3. Any full reference replay remains an explicit preparation/audit step, not an extra
   fit on either consumer's read path. The existing prequential `_evaluate` itself fits
   historical folds; tests must distinguish those legitimate original diagnostics from
   an added duplicate target fit. Spy on the target's exact fit-input key, not on a
   misleading claim that all historical evaluation calls disappeared.
4. `_riskobet_research_batch` should prepare one family distribution before choosing a
   side and produce reusable model outputs. A shared adapter feeds both ModelSignal and
   RisikoBet from that output. Do not let each reader call the full historical model and
   apply the same context independently. Manual total markets are not this family.
5. Preserve original missing branches: no sufficient connected history/model -> no
   manufactured distribution; reference unavailable -> truthful original basis with
   missing context. Qualified scope/rotation/goalie data must still be real.

RED witnesses: add export to a real available legacy fixture and show the wrapper's
duplicate target fit/predict path before the seam; then prove one target computation;
exact original p/mean/scale/lambdas/OT bytes; reversed real IDs rejected; missing original
remains absent; unavailable reference retains baseline; independent shared consumers
reuse one B3 callback/ref; hypothetical future effects not applied twice.

Cricket default is explicitly protected: snapshot default function output, canonical
serialized `PrematchPrediction`, input hash and key calculation before edits; compare
unchanged afterward on actual successful and missing-data cricket test fixtures. No new
cricket field, dispatch, coefficient, loader or side effect. An opt-in basketball/hockey
collector may not run for a default Cricket call. Preserve legacy cases byte-for-byte,
not merely numerical closeness. Shared source changes require updating owning raw-code
identities honestly, without pretending unchanged Git/raw identities.

## P4: Football original export and real worker coordinator

One additive collector in the actual `fixture_market_probabilities` / candidate-producing
call captures raw law, exact final calibrated market map, complete sample/reference and
actual calibration identity before card rounding. Both normal/manual post-capture
workers call the same coordinator before price annotation. Keep qualified raw-compatible,
calibrated, cross-competition and count-family paths distinct. Tests must witness exact
original parity for each null path and forbid a raw D1 basis replacing calibrated p.
Context-only refresh can consume a retained original descriptor; old rounded rows cannot
retroactively become exact originals. New schedule/cutoff requires a new bound case.

## P5: C4 source preservation plus existing exact original export

Preserve real native title/competition/season/status fields before the existing scanner's
lossy finished-only projection, with actual receipt clocks and whole native revision
lineage. Use the already present `base_request` branch at the single original candidate
calculation point. Preserve post-IID p exactly. Same result feeds both consumers; old
first-observation shadow rows remain unchanged. Missing roster/map/patch/duration remains
missing, and absent D1/D2 source/effect approval stays baseline. No extra endpoint.

## Integration evidence remains separate

All packets require actual temp A1/B1/Shadow SQLite and the real worker control flow with
fake transport only, followed by owning/focused/full regression and independent review.
The source-capture fixtures remain source-mechanics evidence, not historical empirical
acceptance. No publication/deployment is part of this producer-agent scope.
