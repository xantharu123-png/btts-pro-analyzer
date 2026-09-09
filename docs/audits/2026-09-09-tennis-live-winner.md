# D3 real Tennis winner producer

Date: 2026-09-09. Worktree baseline `da0ae34613fb030280aac3e8abc504d18ebca47e`.
Bounded implementation completed locally; complete regression and independent review pending.
No new provider qualification, empirical approval or deployment claim.

## Owning controller rulings recorded before code

- Scope is the existing ESPN daily response and original calibrated winner calculation,
  not a new provider, service model, native historical identity resolver or D1 replay.
- The opt-in original collector runs inside the one original `predict_match` call before
  rounding. Default numerical output and default serialization remain unchanged.
- Original version: `tennis-live-calibrated-winner-v1`. Its model hash is the actually
  loaded predecision A1 `tennis-tour-state` identity, not a later original-publication hash.
- Closed reference kind: `tennis-live-winner-origin-v1`, only `tennis:winner`.
  It binds actual native current Event/receipt, decision, original model inputs, code,
  state identity and unrounded values; native historical state identity stays unresolved.
- Separate A1 kind `tennis-live-winner-original-v1` is a later publication. It never
  claims a training/model-build time before its actual creation. No hash cycle/backdating.
- Capture scope must publish before B1 reads. Pending refresh remains no-network.
  Unsupported/SofaScore/legacy rows preserve the existing valid baseline without a
  fabricated native context link. Unknown or ambiguous current revisions stay explicit.
- Sidecar is optional `context_json.context_model` with exact fields `schema`, `kind`,
  `reference`, `event`, `cutoff`, `markets`, `original_artifact_hash`. Kind is
  `tennis-live-winner-context-v1`; markets exactly map A/B to winner_a/winner_b.
  The existing four-field reference is unchanged. Store in the exact new shadow model
  revision's transaction; no later lookup of whichever revision happens to be latest.
- D2 resolution remains actual A1/report verification; missing/ambiguous matching effects
  preserve basis, malformed claimed artifacts raise. No matching real Tennis historical
  approval is manufactured for this new version. Experimental comparison may be retained.
- New pure origin validator lives in `context_models/tennis_live.py`. Only its narrow
  reference dispatch is authorized in B1 contracts. Root separately adds exact original
  transport/lightreader binding and implements shared Domain/Signal/UI consumption.
- No source/activation/transport/15K/Cricket changes outside the explicitly owned seam;
  no network, production DB, Git push or VPS work. Tests use isolated real SQLite.

## Implemented real producer, not a separate export-only helper

1. `scripts/tennis_daily.main` explicitly owns `tennis.live_context.live_worker`.
   It executes the existing `_run_daily` inside the existing ESPN capture scope.
   The same already-received competition is matched to that scope's actual normalized
   native status receipt before fixture formatting drops native player IDs.
2. `scan_fixtures` selects its actual separately published A1 tour state once per tour.
   An opt-in `predict_match(..., original_capture=callback)` copies full original raw,
   calibrated and complementary winner probabilities inside the single original call,
   before presentation rounding. Its return type/fields, legacy numerical path,
   side markets and price rules are unchanged.
3. Only storage is deferred. After scope exit has committed actual B1 receipts, the
   worker verifies the selected immutable state, chronological source inventory and
   latest complete native current-event revision. No new HTTP request or refit occurs.
4. `tennis_features_v3` consumes the owning entire tour history as of the actual
   prediction decision. Player selection follows native event revision handling.
   Actual source clocks are not replaced by scope-exit/publication times.
5. A prepared A1/D2 inventory loads actual active effect artifacts and verifies actual
   claimed approvals once per batch. Exact population/feature/coverage/variant matching
   selects zero or one unique artifact. Multiple different matches do not select a
   favorable coefficient. Claimed malformed effect/approval evidence raises an error.
6. A separate original-publication artifact is stored using its actual later clock;
   the stored clock is read back and checked, including idempotent existing artifacts.
   A deterministic descriptor binds all inputs before `compute_once`. The callback is
   CPU-only `calculate_context_payload`, with no A1/B1/D2 read, fitting or provider access.
7. The returned snapshot is checked against the actual resolved input copies. Its
   four-field consumer reference and complete native Event/cutoff are inserted into
   the same append-only Shadow revision as the current rounded legacy prediction.
   The record remains the original calibrated prediction without a real scoped D2
   approval. Legacy side markets receive no inferred winner adjustment.

Cross-database publication is not one transaction. A crash after A1/B3 publication
can leave an unreferenced immutable original/snapshot. Shadow publication happens last;
it does not publish a reference before the target exists. Existing snapshot bytes are
not overwritten or recalculated on an identical input revision.

## Exact interfaces for shared reader and D4 integration

Pure `context_models.tennis_live` exports:

- `BASE_VERSION = "tennis-live-calibrated-winner-v1"`
- `ORIGIN_KIND = "tennis-live-winner-origin-v1"`
- `ORIGINAL_ARTIFACT_KIND = "tennis-live-winner-original-v1"`
- `SIDECAR_KIND = "tennis-live-winner-context-v1"`
- `validate_live_winner_reference(value, history_refs)`
- `validate_live_winner_origin(base, event=None)`
- `original_base(origin)`
- `validate_original_publication(payload, *, created_at)`
- `validate_context_model(sidecar)`

These functions have no IO, refit, state-key/native alias resolution or numerical
probability recomputation. The original-only validator rejects the B7 comparison
version and requires exact original values, complementary probability, parameters,
markets, full Event, decision and the actual loaded state identity. The generic B1
change is exactly one additive dispatch in `validate_reference_weights` for this
reference kind and only the `tennis:winner` family. Old branches are unchanged.

Original artifact payload is exactly `{schema: 1, origin: <closed reference>}`.
Its A1 created_at is a publication clock, not a training/model-build clock. The base
model_hash remains the actual `tennis-tour-state` digest. Original artifact hash is
carried separately by the sidecar; there is no circular digest.

`shadow.store_prediction` gains optional `context_model` and `context_original`
arguments. They must appear together. The actual original's publication digest,
decision, current native ID/tour/start, current player labels, executed model inputs,
model hash and rounded original probabilities are compared before the transaction.
`prediction.context_evidence` cannot silently inherit a previous context_model.
The caller's context object is not mutated. No absent/null field is inserted into
ordinary old serialized output.

The sidecar stays exactly:

```text
schema, kind, reference, event, cutoff, markets, original_artifact_hash
markets = {A: winner_a, B: winner_b}
reference = existing {schema, kind, key, payload_digest}
```

Root separately integrates the shared Domain/Signal/UI reader and D3 original/light
validation for this explicit base version, plus D4's new original-publication kind.
Those files are deliberately not edited here. A sidecar alone is not empirical proof.

## Native metadata, legacy identity and refresh boundaries

- The existing status-v1 source does not project native surface or indoor metadata.
  This exact new origin version therefore requires Event.surface and Event.indoor
  to be explicitly null and the actual status-v1 schedule digest. Known executed
  catalog/provider input values remain separately in origin.inputs, without being
  promoted into source-verified event metadata. A new native-environment source
  contract/version is needed before a surface-specific effect can be used.
- Event.format stays `singles`. Legacy executed best_of is retained as an original
  calculation input, not reclassified as observed BO3/BO5. No serve probabilities,
  actual rule completeness, historical joins or holds are inferred from winner p.
- The current native players are from this exact competition, not name joins.
  The historic Elo name keys are recorded as actual executed inputs only;
  `native_state_identity="unresolved"` and empty history_refs state that limitation.
- Unqualified IDs, non-ESPN fixtures and genuine legacy model paths still store their
  ordinary valid legacy forecast, without a fabricated native context link.
- The pre-existing Shadow key omits tour. This patch does not migrate its identity or
  finance schema. A new context append checks the parent tour and every prior revision
  digest/clock/tour. Known foreign or missing tour provenance cannot silently certify
  a new native context association. Actual different ATP/WTA native IDs remain separate.
- Pending refresh never fetches. Only rows already carrying a valid new original link
  can reuse its proved current native association. It verifies actual saved A1 original
  and B3 payload/ref, then the full newer B1 event history at the new decision. Changed,
  started, cancelled, conflicting, malformed or unsupported native revisions do not
  resurrect an old fixture. A valid refresh recalculates once and publishes a NEW
  context reference at the new model decision; historical old references stay unchanged.
- Source facts received later than a historical decision do not become earlier facts.
  An original decision earlier than the actual input is rejected, not shifted forward
  after the prediction was already computed. Late originals are not backdated.

## Local RED/GREEN evidence

All source responses used by the new integration tests are explicitly synthetic.
They run the actual normalizers, A1 tour-state codec/publication/loader, B1 SQLite,
B6-v3 features, B3 persistence and actual Shadow revision store. No provider request
was made; HTTP is replaced at the existing request boundary.

- Origin API: initial real 26 RED tests (25 missing-module cases and the unsupported
  original_capture keyword); subsequently green. Later exact native-environment/
  schedule contract probes added 4 true RED and one already-safe format control.
- Actual worker: 10 initial missing-worker RED tests; subsequently green, with actual
  capture-before-read, same-call full probability, tour state and atomically linked row.
- Pending refresh: the corrected real-state test harness yielded 6 true RED cases:
  a lost context reference and five eligible-state retractions still being refreshed.
  All now pass; no network invocation is permitted in those refresh tests.
- Integrity attacks: the corrected actual SQLite harness yielded 4 true RED cases:
  two unhashable-input TypeErrors, accepting a backdated actual stored original clock,
  and allowing a foreign-tour immutable legacy revision despite matching parent tour.
  All now fail closed. Other controls cover changed artifact bytes, hidden source index,
  missing receipt, simultaneous native identity conflict, sidecar mismatches and history.
- Real B2 fitting is used to build artificial active-catalog artifacts. These tests
  check missing/ambiguous/wrong-scope matching and actual D2 rejection of a caller's
  `passed` claim. They do not assert a fitted synthetic coefficient has empirical value.
- 48 same-CPU comparisons load the unchanged pre-edit predictor source from Git blob
  `19f92678de5b236b72ec8fee921ef598d98bc223` (baseline da0ae346). ATP/WTA, two best_of
  calculations, missing/Hard/Clay surfaces, indoor states, real serve-model inputs and
  optional prices compare full typed output including exact float hex and tuple-key
  simulator distributions, plus exact ordinary market-summary bytes. No tolerance.
  The legacy fixture's Git blob is checked after explicit LF text normalization;
  this is not a claim that raw platform source hashes are portable.

Harness-only corrections, not product defects: one initial syntax typo, the original
test's nonexistent receipt-table name/SQL-null-in-NOT-NULL setup, and the parity harness
initially attempting to JSON-encode the simulator's tuple-key maps and datetime.
Those runs are retained under .pytest_tmp and are not counted as product RED evidence.

Final focused and full results, review disposition and source hashes are appended below
after the frozen runs finish. No result from a different worktree is claimed as this run.

## Remaining external/empirical integration work

This package connects the actual daily and already-linked pending producer. It does
not resolve historical native-to-state tennis aliases, add native venue metadata to
status-v1, create an archival source, perform a new training run, invent holdout labels,
approve a live calibrated base via the older raw D1 base, or claim a health/fatigue law.
In particular the v1 native environment remains unknown: no surface-specific B7 effect
can be treated as applicable by inventing metadata from the catalog input. A real D2
approval for this new version is presently unavailable. That leaves the original
calibrated winner visible and unchanged, with honest observed-context coverage.

No Cricket, source adapter, calibration, server, stage helper, ticket, price ledger,
historical result, consumer/UI or deployment file is changed by this bounded package.

## Frozen review candidate

- Focused actual run: **758 passed, 0 skipped**, 88.98 seconds, including all
  **154 new owning tests** (48 exact legacy comparisons). Command selected the four
  new tests plus contracts, snapshots, transport/byte tests, v3 model transport,
  status/capture, pending refresh, immutable revisions, tour readers, fixture metadata,
  daily pipeline and actual activation tests.
- Evidence: `.pytest_tmp/tennis-live-focused-final-01.xml`.
- Full suite started on these exact source/test bytes with
  `python -B -m pytest -q -p no:cacheprovider tests
  --basetemp=.pytest_tmp/tennis-live-full-01
  --junitxml=.pytest_tmp/tennis-live-full-01.xml`.
  **Still running at this commit; no complete-suite acceptance yet.**
- No source/test edits while that run or the independent review is active. A later
  audit-only append will record the actual completed full result.

SHA-256 (raw local bytes; no cross-platform identity claim):

```text
context_models/contracts.py cd37c1a64f5bd645192068b5812702e6362749bb9546dabc0d1f9b429a0c019d
context_models/tennis_live.py 5498d79266bf5b5a9e9ddc97610a2318f6abe292c164e8a0bf57b0adfcf09ed0
tennis/live_context.py 61bbec8218860f536965391fd0c22634c3dcbe080ac2aca0498706f6d895f10c
tennis/predict.py bd1c2c8f7666e3de5f32d754eac09967edde566c1d7b48c298635f2b3d989ecc
scripts/tennis_daily.py 114493ab3ac8411a35b0f194b7f9115e8e09ccb06f89180322fe550af477280d
tennis/shadow.py 18655f55436d1d0c831a0b7221347aa6b3d34b2791660759993d6057fc51faee
tests/test_tennis_live_origin.py e79f11b33c01fbe245921b773eb27e7b18e54029aed694ad78964446feb37b65
tests/test_tennis_live_worker.py 425a8b29a6efa17a2f6e833e5c8bc2f3fc8ceefb69c2affb7f121b84f5da5be6
tests/test_tennis_live_integrity.py 0187170831fc4be24ce1b3249414fc8925f2fbb778787aca1e294765412ab68a
tests/test_tennis_live_legacy_parity.py 5665261481ae91f29c6665ecb4c14b5044d35b11953763ed5067178a8af40b6e
tests/fixtures/tennis_predict_legacy_da0ae34.py f92d9451d3e7c0612832101ab1d6298cb99baeeaaa4f2d7c89cb8e9fe0526c7c
```

## Completed frozen full run

The full run on source commit `32ac1d8ac739a51f84654c2c41fc27017c95cedd`
completed with **5,249 passed, 19 skipped and 97 subtests passed**, zero failures,
exit 0, **1,067.06 seconds**. Its command is the exact command above. All eleven
listed code/test/legacy-fixture SHA-256 hashes were checked again after completion
and remain unchanged. Only this evidence append changes the audit document.

JUnit: `.pytest_tmp/tennis-live-full-01.xml`, SHA-256
`11bec44ddc00a4e4e03bdc4ce1cba6eea05bdb29d7eceba950798685a1371d3f`.
Focused JUnit SHA-256:
`4f74d969eb3b54006e7738b8bc4b3b1f5ccf451a047950efa6e6d7f759d539da`.

This is local regression evidence, not the independent review's verdict or a
deployment/real-provider/empirical approval. Those boundaries remain as above.
