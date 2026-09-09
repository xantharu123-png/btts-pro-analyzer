# D3: actual producer connection preflight

Date: 2026-09-09. Independent read-only preflight, not implementation or release approval.

Inspected root worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Initial HEAD: `d4312dd6c63d7bcda1845f13af73c3c42b814513`.
Root integrated its own accepted work in parallel; final source inventory was read at
`da0ae34613fb030280aac3e8abc504d18ebca47e`.
The intervening producer-independent changes were the accepted football result capture
repair and D3's exact embedded original-Event check, plus their tests/reports/ledgers.
Both relevant final diffs were read. Producer files below were unchanged by those merges.
The modified staging helper and unrelated untracked root output files were not read or changed.

Read the full Task18 controller rulings, context-contract decisions and validation-contract
decisions; applied the previously read approved sport specifications and source rulings.
All observations below come from actual current code, not from old test totals or VPS claims.
No provider request, production database read, model fit, test run, Git write, source edit or
VPS operation was performed. The only write is this ignored report in the review worktree.

## Outcome

The production producer graph is not yet connected to D3. The models themselves are not
uniformly absent. Several original numerical outputs and real native identities already
exist in the running paths, but are discarded, rounded, or consumed before a shared typed
snapshot can be made. Searches of the actual production callsites found no call to
`calculate_context_payload`, `context_consumer_reference` or the C2/C3 original export
functions. C4's opt-in export exists, but its real callers do not request it.

The smallest useful first worker connection is a **same-call, original Tennis winner
export in the ESPN daily path, finalized after capture publication**, or a **qualified
raw-compatible football branch at its existing worker boundary**. These can use the already
implemented live B1 capture. They are not permission to synthesize native historical
identity or to replace individually calibrated football markets. Both require the exact
producer/export plumbing described below. Missing approval must retain the real original
probability, not prevent storing a truthful baseline context snapshot.

C2/C3 and C4 also have concrete original-basis supply. Their source capture and empirical
family resolution have further gaps, so they can be connected as actual baseline-only
producer paths without pretending the absent effects already work. A no-effect snapshot
is useful only when attached to the actual worker and read by the actual consumers; another
standalone helper with manufactured caller inputs would not close this task.

## Actual producer/consumer map

| Route | Actual producer | Actual reuse | Current loss / missing connection |
| --- | --- | --- | --- |
| Automated football | `wettfinder_automation._default_football_scan` -> `scan_daily_challenge` -> `build_fixture_candidates` | Persisted normal model rows and RisikoBet's pre-gate football pool | Complete unrounded model/market law is lost before `ChallengeCandidate` serialization; no D3 coordinator after the B1 scope |
| Manual football | `alternative_markets_tab_extended._run_market_scan_worker` -> the same scan | Manual search catalogue, then independent price annotation | Same original loss; post-capture/pre-price boundary already exists |
| Football context refresh | `_default_football_context_refresh` -> `refresh_discovered_candidates` | Previously discovered, rounded candidates | This is not a full original model producer; old rows cannot reconstruct the lost rates/market law |
| Automated and manual Tennis | `scripts/tennis_daily.main` -> `_run_daily` -> `scan_fixtures` -> `predict_match` -> `shadow.store_prediction` | `tennis_model_signals`, `adapt_tennis_shadow`, Tennis tab | Current native player IDs are dropped in fixture projection; original winner values rounded and holds dropped before storage |
| Tennis pending refresh | `refresh_pending_predictions` -> cached A1 tour state -> `predict_match` -> append model revision | The same latest-prediction readers | No network; can consume already committed B1 data, but old rounded rows lack original export and current native participant binding |
| Basketball/NHL RisikoBet | `_riskobet_research_batch` -> `adapt_research_matchwinner` -> `sports_prematch.predict_prematch` | RisikoBet only | Real historical model exists; full params are reduced to formatted factor strings; C2/C3 export is unused |
| Manual Basketball/NHL | `app.py` -> `build_candidate` -> total-points/total-goals candidates | Manual selected market | Different model families from C2/C3 winner models; cannot borrow those context refs |
| E-Sport automation | `run_shadow_scan` -> `EsportsShadowLog.log_predictions` -> `esports_match_winner_candidate` | E-Sport signal and RisikoBet shadow readers | Same-call original C4 export is implemented but unused; legacy log stores rounded first observation, not full context |
| Manual E-Sport | `app.py` -> `build_candidate` -> `esports_match_winner_candidate` | Manual card | Does a separate calculation without export; no shared context reference to the automated original |
| Generic manual Tennis event scan | `app.py` -> fixture listing -> `build_candidate` | No model probability | Explicitly returns no-model; it must not fabricate a second prediction from this listing |

The normal automated `run_wettfinder` still explicitly declares Basketball and Eishockey
`live_only_no_prematch_model` (around lines 3272-3281). Their actual research models are
in the separate RisikoBet branch. Also, `_scanner_completed_history_loader`'s docstring
saying the scanners have no history interface is stale: the methods are implemented.
Those are routing/documentation gaps, not evidence that every model lacks historical input.

## Tennis: exact original available, current join is lost locally

Callsites:

- `scripts/tennis_daily.py:236` `fetch_fixtures_espn(date, *, observe_status=None)`.
  `_fetch_espn_events` at 291 already captures the exact response via
  `observe_espn_response` with the actual receipt clock. The same competition contains
  native event and both athlete IDs. The returned fixture retains event ID, source,
  names, start, tour, surface/indoor, but drops both native athlete IDs and the native
  tournament identity/competition revision needed to bind the B1 Event.
- `fetch_fixtures_sofascore` at 177 is preferred by `fetch_fixtures` at 633 when it
  succeeds. It also drops native participant IDs. It is not an ESPN identity alias.
  The new v3 capture does not supply a SofaScore-to-ESPN resolver.
- `tennis/predict.py:113` `predict_match(state, player_a, player_b, surface, best_of=3, ...)`
  possesses actual unrounded `p_raw`, `p_cal`, and, when service statistics qualify,
  `hold_a`, `hold_b` and the full `MatchMarkets` returned by `simulate_match`.
  It then returns probabilities rounded to four decimals. `market_summary` at 87
  also rounds side markets, and neither original hold is retained in `TennisPrediction`.
- The model uses name-resolved state keys. Those are actual legacy computational inputs,
  not proof that historical native ESPN player identities were resolved. Do not rename
  those name keys to ESPN/Sackmann identities or infer an alias from the current fixture.
- `scan_fixtures` at 859 loads an actual separately scoped A1 ATP/WTA state and uses
  the provided decision clock. Best-of comes from `resolve_surface(tournament_name, ...)`,
  not a captured native rules fact. For a first winner-only route, actual singles grouping
  supports `format=singles`; it does not support inventing BO3/BO5 for the serve variant.
- `shadow.store_prediction` at 897 stores the already rounded output. Its latest model
  revision is append-only; a repeated base row may return `-1` while a model revision was
  still appended. A new context link must bind that precise revision transaction, not
  resolve whichever row happens to be latest afterward.
- `main` at 970 wraps `_run_daily` in `capture_tennis_worker`; the scope exits only after
  the current `_run_daily` at 987 has predicted and stored its rows. Reading the context
  DB inside the existing `scan_fixtures` therefore does not include the newly captured
  status/terminal observations from this run. That is a real sequencing gap.
- `tennis_tab._run_tennis_scan_worker` at 301 invokes the same daily CLI for each day;
  a corrected daily producer serves both manual and scheduled execution.

Smallest honest first branch (proposal, not an implemented API):

1. Preserve native ordered participant IDs, native tournament/revision and source status
   from the same already received ESPN competition. Attach an original export produced
   inside the single `predict_match` call, before rounding. Preserve the legacy return
   values exactly when this optional export is absent.
2. Explicitly version the original **calibrated winner** base, with `params.p_a = p_cal`
   and complementary winner markets from the actual original pre-rounding values.
   Bind the actually loaded A1 tour state, actual calculation inputs and actual decision.
   A small owning export/provenance contract is needed; a caller-supplied `model_hash`
   or a name-derived native alias is not that contract. It is not a D1 replay approval.
3. Make the daily operation two-phase: collect actual prepared prediction revisions,
   exit/publish the capture scope, then assemble context and append the prediction plus
   optional context reference atomically. Do not invoke `predict_match` again to recover
   missing decimals. A new sidecar must not rewrite existing shadow/financial history.
   Any alternative early capture flush would need an explicit lifecycle ruling; the
   current scope-exit contract does not provide it.
4. Use `tennis_observations_as_of(path, *, cutoff, tour)` from
   `context_sources/tennis_status.py`, then
   `tennis_features_v3(event, observations, original_base, *, cutoff)`.
   This is actual persisted, validated full native tour history before participant/
   schedule filtering. New status withdrawals therefore remain effective.
5. Missing native current identity, SofaScore-only source, malformed status or lost original
   export yields no new numeric-context claim. Preserve the legacy prediction separately.
   A model-ready ESPN winner with current real IDs can have genuine v3 context facts and
   an unchanged original winner base even though no effect is empirically approved.
6. Pending refresh at 704 remains no-network. New correctly stored original inputs may
   be recalculated once against the new A1 state and already committed B1 observations.
   A prior prediction with only names/rounded values is not backfilled as a native v3 case.

Serve must remain a separate later branch: the actual full holds exist locally, but
current calibrated/blended match winner is not the winner of the standalone strict B7
serve simulator. B7 additionally requires its precise simulator version and actual BO
format. Never infer holds from winner-p, switch from blended/calibrated winner to serve
winner silently, or label catalog-derived best-of as observed rules.

True external/historical gap: `context_models/replay.py:86` and
`training_cases.py:64` explicitly reject Tennis replay with
`native_to_state_key_source_resolver_unavailable`. Neither saving current ESPN athlete IDs
nor a successful synthetic B2 fit closes that historical identity/evaluation path.

## Football: preserve both calibration and full original sample

`challenge_engine._fixture_model` at 1014 already accepts optional
`include_provenance=False, native_provenance=None`; default behavior is unchanged.
Its full active/season/form lambdas, sample support and optional native reference weights
exist before the market cards are built.

`fixture_market_probabilities(fixture, league_history, calibration=None, *, team_history=None)`
at 1642 calculates the raw goal matrix/markets, then **replaces each market's values with
its own `MarketCalibration` curve** when available. It currently calls `_fixture_model`
without requesting provenance. `MarketCalibration` stores actual points and sample count;
those objects can be captured at that same call, not guessed from a rounded card.

`build_fixture_candidates` at 2268 sees the complete full-precision result once before
looping over markets, but stores probabilities rounded to six decimals and expected
goals rounded to three. The RisikoBet pool is selected before normal price/eligibility
gates, but after this loss. The legacy engine also includes corners/cards families;
those are not the B5 90-minute goal law and require separate family handling.

Locally executable connection:

- Add an opt-in same-call original export before those lossy candidate projections.
  Preserve the full original raw rates, exact original final market map, actual calibration
  identities/points and complete actually used input history, including cross-competition
  team-history mode. No additional scan/fit per candidate and no probability from UI text.
- In the genuinely raw-compatible branch, require that every transported goal market is
  exactly the output of the original raw law, and retain the correct original version.
  Native source joins can then use `football_native_provenance` and validated B1 receipts.
  Empty/identity calibration is a real supported branch in the current code; this preflight
  did not execute a live scan and does not claim a current count of eligible events.
- The current D1 recipe is explicitly `FOOTBALL_RAW_BASE`, single-competition native
  detail input, no calibrator. It is not the original of a generally calibrated live
  candidate. An identity-at-one-point coincidence does not qualify an otherwise unrelated
  model version/recipe for the old D1/D2 population.
- Calibrated, cross-league, CSV-enriched or count-market branches must retain their actual
  legacy forecasts. Do not call raw `replay_base_distribution` to replace their basis.
  A closed, replayable original calibrated law/version and its separate evaluation
  definition are needed before such a branch can consume a numerical B5 effect.
- Both `_default_football_scan` at 2104 and manual `_run_market_scan_worker` at 444
  already exit `capture_football_worker` before price annotation. That is the appropriate
  actual coordinator boundary once the scan returns detached original exports.
- `scan_daily_challenge` does base modelling before its later detail/injury/weather calls.
  The new context decision must be deliberately frozen after the applicable inputs are
  received, with the actual original sample/support retained. A start-of-scan cutoff cannot
  consume later receipts; a consumer's current wall clock cannot relabel an old decision.
- `refresh_discovered_candidates` at 2896 only rechecks native fixture/context against old
  rounded candidates. It needs the carried original export to make a new bound context
  decision. A schedule/participant/model revision must be explicitly reassembled; never
  alter an old snapshot's Event or construct exact lambdas from three-decimal fields.

Actual source limitations remain: completed history can contain CSV/native mixtures;
native IDs/provenance are not guaranteed for each historical row. Existing capture can
persist real API responses, but cannot retroactively turn imported history into old
prematch receipts. Missing regulation player minutes, complete historical rosters or
learned participation artifacts produce missing features rather than invented 90-minute
exposure. C1 weather/load is not an adapter for the injury-only B5 feature version;
current D3 football dispatch accepts `football-roster-components-v2` only.

## C2/C3: real model supply, separate source/consumer gaps

The concrete path is `wettfinder_automation._default_basketball_risk_source` at 2549 /
`_default_ice_hockey_risk_source` at 2575 -> `_scanner_completed_history_loader` at 2419
-> `_riskobet_research_batch` at 2468 -> `riskobet_candidates.adapt_research_matchwinner`
at 1717. The latter calls `sports_prematch.predict_prematch` at 441, then chooses the
underdog. Prepare both sides' original distribution before that selection, not from its
one chosen probability later.

`BasketballScanner.get_completed_games` and `get_completed_nhl_games` are implemented.
`scanners/completed_history.py` has real bounded/cache-aware result parsers and receipt
clocks for ESPN, EuroLeague and NHL. Availability still depends on actual stored/fetched
results and the existing model's minimum history/connectivity. No request was made here.

Existing callable exports:

```text
sports_prematch.basketball_base_distribution(event, history, as_of, *, context_event, scope=None)
sports_prematch.hockey_base_distribution(event, history, as_of, *, context_event, scope=None)
team_sport_features("basketball", event, observations, base, *, cutoff, preprocessing=None)
hockey_features(event, observations, base, *, cutoff, scenario_id=None)
```

Basketball export preserves actual Ridge mean/residual scale and full winner probabilities;
its `_fit` uses the existing cache. Hockey preserves original Poisson rates and the actual
legacy conditional OT conversion, not an invented 50% split. Where the legacy model has
no usable probability, Basketball raises a typed model-unavailable error and Hockey
returns `None`. Neither branch should create a fake baseline.

- NBA/EuroLeague formatted upcoming rows and completed rows already have native event/
  team IDs. Actual neutral/season metadata is partly present in raw replies but dropped or
  absent in projections. The C2 complete reference additionally requires explicit actual
  season/rules and complete measured/expected rotation data. The current parser does not
  produce `context_rules`/normalized rotation receipts. `scope=None` truthfully exports
  the original basis with an unavailable reference; numeric rotation effect remains absent.
- NHL upcoming and completed parsers retain native IDs, game type, season and final scope,
  but the current upcoming `neutral_site = (... is True)` collapses missing metadata to
  false. Do not treat that default as native venue proof. Completed season is a string;
  owning C3 qualification requires a strict native season/rules contract, not a silent cast
  or inferred rules. Current C3 qualified scope is exactly 2025/26 rule84, not a blanket
  approval for a September 2026 next-season fixture.
- C3 admits regular-season type 2 and playoff type 3; legacy type 1 preseason is not a
  supported C3 format. Neutral/no-OT-data/insufficient-history null paths remain unchanged.
- The old model's subtraction of a winning goal for an OT/SO final is a **legacy modelling
  assumption**, not newly observed regulation scores. Goalie/skater regulation TOI,
  confirmed starters, exposure and actual match-end clocks are not produced by the current
  schedule/result adapters. The C3 CPU normalizer is not a live data source.
- Carrying an available original basis into a real B3 snapshot is implementable without
  guessing these missing fields. Source-qualified rotations/goalie effects are not.
- The normal automated Wettfinder route needs an explicit shared research-model consumer
  if it is intended to show these models. Its current status literals do not mean the
  RisikoBet history methods are absent. Manual totals stay their separate unsupported
  families; do not attach an inclusive winner context to total points/goals.

## C4: strongest existing numerical export seam, no native capture yet

`multi_sport_recommendations.esports_match_winner_candidate(match, *, now=None, base_request=None)`
at 650 already supports an exact opt-in request with `event` and `observations`. Its output
becomes `{"candidate": existing_candidate, "base": original_base_or_none}`. At the original
pre-rounding calculation point it passes full `team1_live_probability` and the exact two
historical windows to `export_esports_base`. That probability is **after the original
Elo -> inverse-IID -> series roundtrip**, not raw Elo expected_score.

Current real callers omit `base_request`: `EsportsShadowLog.log_predictions` at 115 and
manual `build_candidate` at 845. The scanner returns native current event/team IDs,
explicit 0:0 and odd best-of. It drops native title/competition/season metadata from the
final formatted dictionary; the generic tournament text is not the owning native scope.
Preserve actual native metadata from the same already returned provider payload before
constructing a source-owned Event; do not synthesize its competition ID from a name.

`_get_team_history` at 517 uses the existing team endpoint/cache. It keeps finished rows
only, then projects match IDs, opponent IDs, winner, begin/end and number_of_games. It
does not keep the full status/retraction lineage, map facts, roster, patch/veto or native
season/rules needed by C4. Capture must occur before that filter on already obtained
replies, and preserve unknown/cancelled/started corrections. No new endpoint is required
merely to save existing facts, but absent roster/map/patch data is still genuinely absent.

Without those receipts the existing export returns the original valid probability with
`native-series-scope-receipts-unavailable`; C4 features and B3 can honestly preserve the
basis. It cannot claim qualified participation or numerical fatigue. BO7/unknown BO,
nonzero starting maps, malformed native identity and no original model remain null paths.
Keep the raw source hashes of the actual platform; Git-blob identity is not raw recipe
identity when the source bytes differ by line endings.

The existing shadow log is first-observation `INSERT OR IGNORE`. A new versioned context
sidecar/reference must coexist with that history; it must not replace old recorded
predictions/tickets. The log also recomputes Elo metadata after the candidate computation;
B3 compute-once by itself does not eliminate those existing upstream calculations.

## Smallest actual shared coordinator, not a new isolated model

The following is a proposed worker assembly shape, not an existing implemented API:

```text
one actual original model invocation + detached native original inputs
  -> publish existing source capture at its real worker boundary
  -> prepare immutable cases for one frozen decision, without odds
  -> resolve whole relevant B1 revision inventory and actual A1 manifest/artifacts
  -> derive the owning full Event/Base/FeatureVector and exact ref roles
  -> resolve any claimed D2 approval outside the snapshot callback
  -> context_payload_key(complete input descriptor)
  -> compute_once(context_db, key, CPU-only calculate_context_payload callback)
  -> persist optional exact consumer reference with the owning new prediction revision
  -> both normal and RisikoBet consumers project that same stored law
```

Existing exact APIs usable in that assembly:

```text
approved_effect(path, *, effect_hash, event, features, base) -> approval envelope | None
verify_approval(connection, approval_hash) -> historical verified envelope
compute_once(path, key, compute) -> detached stored dict
calculate_context_payload(*, event, base, features, observation_refs,
                          preprocessing_refs, effect_artifact, effect_hash, approval)
context_payload_key(input_descriptor) -> key
context_consumer_reference(key, payload) -> typed reference
project_context_market(payload, reference, selected_market) -> exact bound projection
```

`approved_effect` does not choose/return an effect: the worker must resolve its actual
active A1 slot/envelope first. Effects have free slot names; use validated artifact kinds
and exact population/version, not substring guesses. No matching slot means no effect.
Several matching choices require an explicit deterministic owning model selection rule,
not choosing a favorable probability. The approval slot is exactly
`context-approval:<effect_hash>` and must remain coupled to the active effect.

The current `approved_effect` opens and verifies the complete persisted report each call.
Do not repeat this per card or describe it as cheap. Prepare one validated manifest/report
inventory for the worker batch, with frozen publication/decision clocks; reuse resolution,
then perform exact case-scope checks. Preserve corruption errors: a malformed active
approval is not harmless absence. `verify_approval(connection, ...)` is the existing
historical no-write seam for that factoring; no DB query belongs in `compute_once`.

The implemented actual D1 replay/case resolver is football raw-goals only. Tennis is
explicitly unavailable as above. Basketball/Hockey/E-Sport currently have no owning D1/D2
family case/replay/evaluation connection, and `approved_effect` ultimately has input
validators only for football/Tennis. Missing active approval simply returns `None`;
fabricating an envelope/slot for another sport is not an approved shortcut. Actual future
family support needs its independent frozen registry/cohort/outcome work, not a generic
`passed=True` or a copied football certificate.

Consumer plumbing is also concrete work, not presently done:

- `ModelSignal` has useful native identity fields but no context reference;
  `_signal_record` at 578 enumerates serializable fields explicitly.
- `RiskCandidate` is based on `EventModelSnapshot` (`riskobet_domain.py:241`), whose
  serialization and snapshot identity contain no D3 reference. Its existing immutable
  history and IDs must not change for old absent-reference rows.
- `ChallengeCandidate`, shadow revision stores and the persisted normal search output
  need an optional versioned ref. An omitted ref must preserve legacy bytes/IDs and
  existing price/settlement behavior, not serialize a new `null` everywhere.
- Reads need a real trusted snapshot-ref lookup. `compute_once` is a writer with a
  callback, not an existing read-only consumer lookup API. Read path must validate the
  exact stored key/digest and use `project_context_market`, without fitting or refreshing.
- The D4 source inspected in this snapshot still marks generic snapshots
  `d3-snapshot-input-binding-unavailable`. Root is independently completing that seam;
  new live snapshots cannot be called fully recoverable/source-verified merely because
  `compute_once` stored JSON. Coordinate the typed source/approval resolver before release.

## Narrow implementation order / necessary decisions

1. **First useful live branch:** original Tennis winner + same-response native ESPN event,
   two-phase daily publication, actual B1 v3, A1 state binding and shared consumer sidecar.
   Need a closed original calibrated-winner export identity and atomic prediction/ref
   transaction decision. No new provider permission is needed to preserve those existing
   fields; native historical state replay remains explicitly unavailable. The same daily
   worker covers manual scans; no-network pending refresh consumes committed data only.
2. **Football in parallel or next:** same-call full original export and explicit calibration
   branch identity; shared post-capture coordinator in both normal/manual workers. The
   raw-compatible/native-reference branch is locally executable. The original calibrated
   distribution/recipe is a separate technical contract decision before a B5 effect, not
   grounds for substituting raw predictions. No count-market or cross-league approval
   inheritance.
3. **C2/C3/C4:** wire the existing original exports into their real producer callsites,
   preserve native fields before current lossy adapters, capture actual existing-source
   receipts, and carry one context ref before side selection. Keep baseline-only where
   reference/source/scope is genuinely unavailable. Explicitly add a shared normal
   research-model consumer for C2/C3 if required; manual totals are separate scope.
4. Complete family empirical resolvers only with real chronological source/identity
   data and frozen approvals. None of steps 1-3 proves an improvement in betting quality
   or supplies missing medical/roster data. No quotation gate is added.

Required end-to-end regression witnesses for the first packet: exact original bytes with
no effect, original fixture/provider IDs preserved without name joins, capture committed
before feature DB read, no duplicate prediction per event, same optional ref in both
consumer branches, native schedule/status correction invalidates/rebuilds correctly,
corrupt/missing actual A1/B1 distinguished, no final labels before D2 opening, missing
approval stays baseline, price changes do not change key/probability, and old serialized
rows remain byte/ID compatible. These are proposed acceptance tests, not tests run here.

## Final source inventory (raw SHA-256)

```text
context_transport.py d55e8ad4f81fc8a3958f48fe5e0a072e1640de8e6e5b9f694de794fafd3c9713
context_snapshots.py de9d8146917f568e1567cd8a92b92b64af1b33157f2afadf3c91c27a153de1da
context_models/activation.py 887090c03a7107eb16946dd214a5ae7235b4e6cc3ea714a462c5c0e2f1ffd0c3
context_models/replay.py fb7e0d581f45144c1f1b0456f828e58a7cb16ac124c1ec9683dc4f2b43fae32d
context_models/training_cases.py ce05e30b6062a40d76d5b76715fd30375cdb3a582131333adb97a98acbf8eeb1
context_models/football.py 0f38c93c3a4c38c21112aa22d7b04f7f61f1369dbdba71f319df81c191fbe1dc
context_models/tennis_v3.py ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c
context_models/team_sports.py 6d93c2b77ce5f0085cb1861edcc9524d3064b84faa772b501bf8481fedfb7228
context_models/ice_hockey.py 5b27b2fc84c354e87e7842e5191658f9aea9f0213f4a9e5e2136270c4f1280d4
context_models/esports.py d2c95016828fde4b0c30f7849f239b647cdd12c1b97fa7a0fb7c8a287bf26e33
context_sources/football_capture.py fa4adf76c31fb1fa84f2296f8ba735ca0877fc3d181ff7c62ce53e51a3faccec
context_sources/tennis_capture.py 918839283fd4bb446f01fbe34e32ef1e25fb690aa7d1e8f2627650506eef5fdc
context_sources/tennis_status.py 021ee5c234bf7a01166ee82dd21025154af1c48b81e5303c0963d2760166424f
scripts/tennis_daily.py 96099d53717f1a5b869826dadf4b3d5818ff89b9e8b372e069f693c0c3c50280
tennis/predict.py a9cdf2e1c33428ea21f662964fae65f73ba06340ca2bb5934cdaedb6284ae833
tennis/shadow.py 9d7519a5542ee2f0710d82532de3ac2865da61e9ea09627118e6730de8e91509
tennis_tab.py c80933898a51cda6fdcdae58f615753fc270f2c439fb8b539eae3cc6efb0b0ac
challenge_engine.py 915a49325754ace657227c8195c914a18cd2d5fba83482c8f526d7fb03f75fa5
challenge_15k.py 7d7e217282c6e0a9d12aeb38f03340311aaa2895037a79c12226566769535433
alternative_markets_tab_extended.py 8856e23aeeecfda6e206d7db70652f3c4d9061a08360c8e336a29f7181cee1a0
wettfinder_automation.py 44812cd89fbf85bdf01237bb0b249e26832497441e31a83fe549e77b0bf4be36
riskobet_candidates.py cb90cd100d023c4041410fa954ecfe53fce604767357ea13d6005e7840457153
riskobet_domain.py 953a8e93aa1e7c361f7722bccbe6fd28e5f8631fc391bf8b69e22e1b59b534c2
ev_signal_sources.py 15d88acc7885e2cb681ee6051848f801869f173ae9513f05e11bec8e43be8e5c
sports_prematch.py ef393f89ca54489bab28aae6c8d224012961795e387bc272d78ba7cad264a9df
scanners/basketball_scanner.py ed66273ee9b115424dab2ab38031d260ea8aa7e275be44f716010f97c204c36c
scanners/completed_history.py 0097b25c2763732af8d02621ce95d6acbd951b4c81f28ac7ea1de1ed12b65657
scanners/esports_scanner.py 88154b79be09dd11c09c45c8b09d45c6ffde277fe197911576dcffa14834fc8d
multi_sport_recommendations.py 80c545cf82a577bd4d1540bbd2619a12171662781373161d6db4c80ba38615c5
esports_shadow.py d2e5fd53b25332f0070d3d36f3221c40523a14d80838b1a4f7c8d8e1a1b22725
app.py 9aa24d7738913f623dcbed0e6bd22771ad08f0d644b86cb12700d297730374f6
```
