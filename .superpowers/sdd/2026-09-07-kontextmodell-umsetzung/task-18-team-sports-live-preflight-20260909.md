# P3/P4: actual Basketball/Hockey producer connection — read-only preflight

2026-09-09. Inspected Root worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`, exact HEAD
`68aff4786d334cee9c71703ed6dd8d2f21aa2195`. Accepted P3
`ccefe858d5f2d5913bc1c39142e27fb6f52248ae` is an ancestor. The named source files
were unchanged from HEAD. Unrelated Root staging-helper WIP was not inspected
or changed. This report proposes interfaces; it implements none of them.

## Outcome

There is an executable connection path, not a blanket source blocker:

1. Consume the already accepted, actual same-call `OriginalPrematch` before
   display rounding. Preserve its fitted state and exact winning probabilities.
2. Capture native schedule/result envelopes only at existing successful response
   reads, before parsers discard status or identity revisions. Commit these real
   receipt observations before resolving a new context decision.
3. Prepare one BB/Hockey batch and publish one B3 result per exact native
   event/model revision. Project that same used distribution into normal
   `ModelSignal` and RisikoBet, with one shared revision-bound context reference.

Current C2/C3 APIs cannot simply be called from the P3 callback: their original
export and validators replay the target model. C2 additionally solves for Ridge
coefficients and residual scale unconditionally. C3's `_fit` calls can hit the
existing LRU cache; this is not evidence that every invocation performs another
optimizer run, but it is also not a no-fit worker/consumer contract.

Native schedule and score history capture is locally implementable. Real
NBA player minutes/availability, NHL TOI/confirmed starters, and empirical D2
approval are separate absent inputs; no schedule or winning-goalie field proves
them. Existing valid baseline predictions must remain visible without them.

## 1. Actual accepted P3 input and mathematical construction

`sports_prematch.py:124` provides `OriginalPrematch` with the actual copied raw
event/history, `_Identity`, normalized `_Match` tuple, actual `_Fit`, original
unrounded `probability`, direct numeric `values`, `input_hash`, `as_of`, and
the returned `PrematchPrediction`. `predict_prematch:465` invokes the optional
callback after the same actual target fit; prequential historical folds remain
legitimate separate evaluations. No callback is used by default or for Cricket.

### Basketball

Construct from `values['expected_margin']`, `values['residual_scale']` and the
actual `_Fit.coefficients`, `_Fit.teams`, `_Fit.residual_scale`. Keep the
original winner probability and exact `1.0 - p` complement from the returned
prediction. Owning family remains `basketball:margin:including_ot`, two winner
markets, not regulation-only and not a newly inferred score distribution.

The target mean can be checked with the actual ordered team coefficients and
home-intercept design. Do not solve for a second coefficient vector or estimate
a second scale. Where actual C2 signed historical influence is qualified, extract
only `q @ solve(X.T @ X + penalty, X.T)` from `_recipe_arrays:125` into a narrow
reference-weight operation; retain signs. This is an auxiliary exact linear
influence calculation, not a second target fit and not a roster exposure weight.
The old coefficient/scale replay remains in the explicit offline audit.

`export_basketball_base:234` is unsuitable as the live callback today: it calls
`predict_prematch`, `_fit`, `_predict`, `_recipe_arrays`, and the general
validator. `validate_basketball_reference:148` calls `_recipe_arrays` again.
The native whole-event, season/rules, neutral-site and historical alias checks
must not be removed to avoid that work.

### Hockey

Construct the exact three parameters from actual direct values:
`expected_home_goals`, `expected_away_goals`, `overtime_home_rate`. The actual
fit supplies ordered attack/defence/intercept/home coefficients, OT rate and
OT sample count. The existing `hockey_distribution:39` may derive the five
regulation/inclusive market probabilities from those parameters: this is
forward distribution evaluation, not fitting. Require exact equality with
the actual direct home-regulation, draw-regulation and inclusive winner values;
keep the returned winner complement. No guessed holds, OT goal, duration or
neutral-site input may be substituted.

Reuse the mathematical reference composition in `_make_reference:183` with
the already captured parts instead of `_original_parts:159`. The latter calls
the old `_fit` and `_predict`; export and base/reference validators also call
it. The historical exposure reference is not a Poisson causal sensitivity and
must never be replaced with Basketball's signed Ridge influences.

The inherited one-winning-goal subtraction for OT/SO final scores is explicitly
`legacy-one-winning-goal-subtraction-not-observed-period-totals`, not a newly
observed regulation score. No new TOI or regulation-end assertion follows.

### Required narrow version/API decision

Proposed new owning module: `context_models/team_sports_live.py`:

```python
build_basketball_live_original(original: OriginalPrematch, *, event, receipt_binding)
build_hockey_live_original(original: OriginalPrematch, *, event, receipt_binding)
validate_team_sport_live_origin(base, event=None)  # pure, no IO/fit
replay_team_sport_live_origin(base, *, resolved_inventory)  # explicit offline audit
```

These are proposed names, not existing interfaces. The builds return a detached
original envelope plus exact source-binding status, or typed unavailable context;
they do not change the existing returned prediction on an unavailable path.
Use explicit new captured-origin base/reference versions, with a closed exact
sport/mathematical-family dispatch. Do not relabel old C2/C3 bytes or supply a
caller `verified=True` / `skip_replay=True` to authorize publication.

The pure validator binds complete native Event, cutoff, actual source-input
hash, copied model parameters, ordered fit, exact original probabilities and
origin recipe/code identity. The publication record is created after the
decision, not falsely backdated as a previously available trained A1 artifact.
The existing inline model input hash remains distinguishable from the new A1
publication content hash; D4 needs an explicit owning publication contract.
Check actual stored publication time against final forecast append time, as in
the corrected Tennis boundary, including idempotent old publication metadata.

Current feature/effect entry points require exact old versions:
`team_sport_features:441`, `_prepare_effect:572`, `hockey_features:442`,
`validate_hockey_context_binding:574`, `_prepare:594`. New live versions need
explicit adapters/routing and a separately scoped D2 capability decision; they
cannot inherit old approvals. Historical joins unresolved in a legacy input
remain unresolved even if a present native schedule is known.

## 2. Real response capture points and chronology

Proposed module: `context_sources/team_sports_capture.py`, scoped to ESPN NBA,
EuroLeague and NHL responses already fetched by these methods:

| Existing path | Actual capture boundary |
| --- | --- |
| `BasketballScanner._get_upcoming_euroleague_games:132` | Immediately after `response.json()` at 160, before played/date filtering |
| `_get_espn_upcoming_basketball_games:227` | Immediately after JSON at 257, before competition parsing/status filtering |
| `get_upcoming_nhl_games:357` | Immediately after JSON at 383, before FUT/PRE filtering |
| `completed_history.fetch_page:247` | JSON after the existing reserved GET, before parser at 254 and `store.record` |

Capture binds actual request provider, competition/season/date scope where
source-owned, native envelope and actual receipt clock. Store the complete
identified event revision lineage before selecting current participants,
schedule or terminal results. Known-ID cancelled/started/unsupported or broken
participant revisions must retract an old usable terminal or schedule claim;
do not retain only successfully parsed terminal rows. No new query, request
reservation, endpoint, secret or budget is needed. Opt-in capture must not
alter the shared helper's Cricket path or default outputs.

The completed loaders already exist: `_scanner_completed_history_loader:2420`
uses `get_completed_games` / `get_completed_nhl_games`; the older comment claiming
only upcoming/live scanner support is stale. NBA cold filling is bounded to
four monthly requests, NHL to eight weekly requests per run, with existing
provider budgets and cache TTLs retained.

`CompletedHistoryStore.record:179` stamps actual time after parsing; `read:204`
returns latest normalized rows before its `as_of`. The old cache is useful
baseline input, but its payload does not retain the full native envelope or
validate its stored digest on read. It is not interchangeable with verified B1
native receipt inventory. New capture begins prospectively; do not import old
rows today as if their complete native bodies had been received in the past.

`_riskobet_research_batch:2469` currently fixes `source_time` before loading and
adds it as `source_observed_at` when the incoming event lacks a clock. That is
not actual native receipt evidence. Also, newly fetched completed rows may be
later than that fixed `as_of` and are then honestly deferred by the current
cache path. For the qualified context path, commit captured receipts first,
sample a real decision clock afterwards, then select and model that exact causal
input inventory once. Do not reuse the pre-GET batch clock as a receipt, and do
not silently add newly fetched rows after a model has already been captured.
Retain exact legacy call/clock/output behavior for unqualified/default paths.

## 3. Actual source gaps versus code gaps

- ESPN upcoming parsing retains native IDs but drops raw season/neutral-site
  information. EuroLeague drops request season. These are locally preservable
  only when present/source-owned in the actual existing response/request.
- NHL upcoming output includes native IDs, season and game type, but converts
  absent neutral-site into False. New capture must preserve unknown. Its target
  `game_id` alias also needs owning native projection; old C3's `_native_projection`
  accepts a narrower set of ID keys. NHL completed parsing keeps season as text,
  and omits `context_rule_version`; no automatic int/rule assertion is justified
  without actual owning validation.
- C3 `hockey_scope:78` currently qualifies only integer season `20252026` with
  `nhl-2025-26-rule84`, regular season type 2 or playoffs type 3. A future
  `20262027` or preseason type 1 is not silently that population. Legacy type-1
  predictions may exist and must retain their exact basis without a C3 effect.
- C2 accepts explicit NBA/EuroLeague regulation/OT rules and actual season,
  not season guessed from a display label. Current parsers do not supply a
  fully qualified context rule/roster reference for the historical fit.
- The retained 2026-09-07 NHL probe is a real HTTP-200 schedule field-path
  inventory (50 events, two inspected native event IDs), not full raw JSON and
  not a successful present-day live fixture. Its `winningGoalie.playerId` is
  post-result information, not a confirmed prematch starter; it contains no TOI.
- That day's NBA probe was HTTP 403, with no usable body/schema. No repeat or
  replacement endpoint was attempted here. Lack of that probe is not proof that
  every future existing NBA worker request must fail.
- `context_sources/basketball.py` and `context_sources/ice_hockey.py` are
  explicitly internal CPU contracts, not real roster/minute/starter adapters.
  Schedules/results do not satisfy their minute/rotation/manpower/availability
  records. No healthy=0, participation=0.5, expected=observed or invented duration.
- Thus native event plus exact original basis can be publishable before player
  context is available. Missing actual context leaves B3 `used` equal to base;
  an existing missing base probability remains missing, not 50% or a tip.

## 4. One worker batch, two projections

Proposed owning worker module: `team_sports_live_context.py`:

```python
prepare_team_sport_batch(sport, events, history, *, receipt_inventory, clock)
# -> originals and published context envelopes/refs, prepared once per event
project_team_sport_signals(prepared_batch)  # normal ModelSignal projection
project_team_sport_risk(prepared_batch)     # existing RiskSourceBatch shape
```

Use a separate internal prepared-batch value instead of silently extending
`RiskSourceBatch` (`riskobet_automation:52`), whose present contract contains
sport, snapshots, candidates and errors only. Resolve actual A1/B1 and
`approved_effect` inventory once per prepared batch; CPU `compute_once` must
not perform database/source/fit work. Missing or ambiguous qualifying model
selection remains baseline with internal reason, corrupt bound objects raise.

`adapt_research_matchwinner:1717` currently calls predict and immediately builds
its Risk snapshot/candidate. The P3 callback alone does not feed B3's used result
back into it. Extract its post-prediction projection as a pure adapter: it may
select the underdog from the shared used winner pair, but must not refit or
apply context again. Existing eligibility/tie behavior, missing-core-data
handling and quote-independent identity remain intact; no 15K release expansion.

Both outputs bind the same complete native event, decision cutoff, selected
market and existing four-field context reference. Context must enter the actual
Risk `input_hash` and snapshot identity together. No-ref/null paths preserve
existing Risk IDs and prediction bytes; new normal records require an explicit
new source/version contract, not a made-up old source key. A context ref with
unchanged base probability is still a legitimate new model revision.

The current real normal path needs three coordinated Root edits, not just a
`ModelSignal` constructor:

1. `_signal_record:578` assigns **every non-Tennis signal** to `esports_shadow`.
   Add explicit closed BB/Hockey source dispatch; never pass new signals through
   that fallback or make the reader accept arbitrary sport/source combinations.
2. `ev_signal_sources.py:945` accepts only football, Tennis and E-Sport in the
   normal artifact. Add explicit typed BB/Hockey normal-source readback and
   source-status mappings. Current `live_only_no_prematch_model` statuses at
   `wettfinder_automation:3262` are not an honest description of its Risk models.
3. The normal catalog is built at 3451/3472, while the real Risk source batch is
   invoked only after 3691. Materialize due BB/Hockey batches once before both
   catalogs; give RisikoBet closures over these immutable results. On non-due
   runs use a persistent prepared projection/reference inventory, not a second
   fetch/fit triggered by opening the normal view. `enable_riskobet=False` must
   not disable otherwise requested normal BB/Hockey modeling.

Normal winner cards and Risk underdog cards can choose different projections of
one distribution; the existing cross-card consistency policy remains a separate
Root-owned selection rule. Never show both as simultaneous contrary advice by
accident. Public copy must use actual applied/not-applied factors, not retain a
blanket old claim that acute context never changed an actually adjusted result.

## 5. Smallest testable implementation packets / proposed ownership

**P4a — actual original builders and no-fit contract.** Worker owns new
`context_models/team_sports_live.py`, narrow C2/C3 helper extractions and new
`tests/test_team_sports_live_original.py`. Root owns coordinated closed dispatch
in contracts/transport and later D4 original replay. Introduce no broad validator
skip. Proof: actual cold target fit once, original callback's float-exact values,
zero `_fit`/optimizer/coefficient/scale replay after capture, and exact parameter
neutrality. Test missing/infinite/unknown-scope inputs and all original mutations.

**P4b — existing response receipts plus producer.** Worker owns new
`context_sources/team_sports_capture.py`, narrowly opt-in hooks in
`scanners/basketball_scanner.py` / `scanners/completed_history.py`, new
`team_sports_live_context.py` and tests. Root first confirms observer signature
and decision ordering. Real temporary SQLite with fake *existing* responses
tests captured JSON before parser filters, budgets/query counts unchanged,
actual receipt <= cutoff, full native lifecycle/correction lineage, simultaneous
conflicts, bad IDs, unknown neutral/rules/season, exact idempotence and no
backdating. Existing complete-source facts are not synthetic player statistics.

**P4c — shared consumer projection.** Root owns extraction/extension in
`riskobet_candidates.py`, `ev_signal_sources.py`, `wettfinder_automation.py`,
shared Domain/readonly reader/D4 integration and public copy. Worker can return
the narrow prepared data API but must not concurrently edit these consumers.
Prove one source load/one original capture/one B3 calculation serves both
outputs, shared key/hash/event/cutoff, no duplicate effect, unchanged prices,
no odds-based hiding, correct scheduled revisions and no accidental source alias.

For all packets: exact old-default Cricket prediction, Risk IDs and relevant
source-call outputs against the frozen legacy fixture; existing Football/Tennis/
E-Sport behavior untouched. No additional provider request, deployed service,
ledger, privileged helper or UI redesign belongs to this preflight.

Remaining controller choices before code: accept the explicit captured-origin
version/pure-validator split; assign the named owning files and shared callback
boundary; define durable prepared-batch publication/reuse in Root's producer
coordinator. A new 2026/27 hockey rule population, absent real player feeds and
actual D2 empirical approval are not decisions that can be solved with a flag.

## Evidence identity and limits

No new implementation or runtime test was performed for this read-only design.
P3's prior independent review remains its own evidence (39 new probes plus 425
existing tests passed); it does not certify these proposed P4 APIs. Inspected
source hashes are local raw-byte identities, not cross-OS newline promises:

```text
1d908a32d4decdd508477526af9802f3a81bd9054f93636e4df8c63675b9a07d sports_prematch.py
f5bb84e23eca72c79ed28c567efea1706ced947e07d8fb9bb898fec7b530bf28 riskobet_candidates.py
360e4515f6b3a14e3ee523e3b6ac4988a8bd8ba12009dc291af1ce9670fc6367 wettfinder_automation.py
090b11fadbaf32246aff9ebd8afb396c6e2754dfda92d2c386d042f7377c763f ev_signal_sources.py
eba4299f851b38e391626bc3c120cfcc1f56136d451942a2a2d1df110bf7c64a riskobet_automation.py
a4650e19a33220e036fe12602300027f1ecb4e06e949837baf7076687784e762 riskobet_domain.py
6d93c2b77ce5f0085cb1861edcc9524d3064b84faa772b501bf8481fedfb7228 context_models/team_sports.py
5b27b2fc84c354e87e7842e5191658f9aea9f0213f4a9e5e2136270c4f1280d4 context_models/ice_hockey.py
5f810f023946021548f969adbbacfbb4b27a16d21e00c1b351f67300ca510b29 context_models/contracts.py
d55e8ad4f81fc8a3958f48fe5e0a072e1640de8e6e5b9f694de794fafd3c9713 context_transport.py
b68f39bb176e4f09ad49327859e088524bcf68960e3b29bd5b66f5347eeef039 context_sources/basketball.py
b32f01b4fe6bd88eeeced71baade95a2d6e5215879c0e58ba097fdf2f72e1bf7 context_sources/ice_hockey.py
ed66273ee9b115424dab2ab38031d260ea8aa7e275be44f716010f97c204c36c scanners/basketball_scanner.py
0097b25c2763732af8d02621ce95d6acbd951b4c81f28ac7ea1de1ed12b65657 scanners/completed_history.py
2b5e7dc4edc73ddd985133faf4d7aef15f61649335545f91dd61e880f0d68df5 basketball-nhl-schedule-probe-20260907.json
```
