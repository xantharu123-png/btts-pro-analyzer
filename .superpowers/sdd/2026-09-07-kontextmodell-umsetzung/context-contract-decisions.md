# Controller decisions for B1-B3 and downstream consumers

These are implementation clarifications of the approved specification, not relaxed data or empirical gates. The controller read the B1-B3 briefs, D2 interface and relevant existing baseline/A1 code, then considered the read-only contract pre-review. No source has been newly certified by this document.

## Continuation rulings — 9 September 2026

- Current B4/B5 reference identity is v2, superseding the earlier unversioned
  base/preprocessing-only formula: `digest({version: 'football-context-reference-v2',
  base_hash: digest(validate_base_distribution(base)), event_hash: digest(validate_event(event)),
  preprocessing: sorted(set(preprocessing_artifact_hashes))})`. Producer version
  is `football-roster-components-v2`. B6/B7 use the same full base/event binding
  under `tennis-context-reference-v2`, without preprocessing, and feature version
  `tennis-performed-load-v2`. The independent review reproduced acceptance of
  unchanged old features after a kickoff/revision change. A new output hash
  alone did not fix stale input. Rebuild features on every new worker event
  revision; never accept the old unversioned/history-only reference or silently
  migrate its meaning. Price/tab state remains absent. This is an integrity
  correction before runtime integration, not a new predictive approval.
- B4 projected lineup/appearance records bind the entire team CONTENT revision,
  including every player's minutes/role and the event schedule revision. A
  membership-only digest was insufficient: partial authentic projections from
  two simultaneous same-roster revisions could otherwise invent a mixed team
  or twelve starting players. Reconstruct the complete declared content from
  the selected projections, keep simultaneous revisions conflicting, and never
  fill missing projections from an older revision. These hashes prove internal
  record consistency only, not source truth or medical coverage.
- B7 explicit serve scope is `singles_best_of_3` or `singles_best_of_5`, matching
  `base.params.best_of`; do not infer singles from an ambiguous format alias.
  B6 accepts these plus its existing `singles` for load measurement. A separately
  tested winner-only unknown-format population may remain `singles` but cannot
  supply serve markets. The strict simulator seam does not clip/round holds
  and retains the existing DP/tiebreak approximation; no empirical exactness
  claim. Serve heads must be mirror-consistent with identical fitting scales,
  parameter routing and training counts, not posthoc-averaged unconstrained fits.
- B7 consumed observed-load dimensions require their matching per-side/window
  completeness flag. This means complete measured values within the observed
  subset, never a proven complete career or competition schedule. Unknown end,
  duration or rest remains its separately tested coverage case or unchanged base.
- B5/B7 factor groups explicitly name consumed feature lists in artifact order,
  jointly covering all consumed columns; overlap is allowed only as an explicit
  interaction-group choice. Each contrast zeroes its group against original
  features/base independently. Outputs retain all hashes and `additive=False`;
  no claim these model counterfactuals are observed causal effects or sum to the
  full change. D1/D3 still own fitted/grouping provenance and user activation.

- B3 `base_hash` is `digest(validate_base_distribution(original_base))`, binding
  the entire normalized event/cutoff/parameters/markets/history/reference
  revision. `base.model_hash` remains a separate model identity. B5/B7/D1 must
  use the same distinction, never pass prior `used_params` as original base.
- D2/B3 `base_versions` is a canonical sorted unique nonempty list of stable
  `BaseDistribution.version` codes, with exact membership. `outcome_contract`
  is a stable versioned identifier of the frozen D1 outcome registry. Neither
  field is a guessed model hash, display label or free object.
- New ContextResults always carry the paired `approval_hash` and
  `certified_markets`. Only applied results retain the verified decision hash
  and the nonempty canonical tested-market subset. Other results carry
  `None`/`[]`. Legacy records lacking both remain readable but gain no new
  certification. D3 may not label untested markets certified or inherit an
  old release status onto a changed distribution.
- B6 performed-load windows are explicitly UTC `[cutoff - N*24h, cutoff)`,
  N=1/3/7, attributed by observed actual match end. A receipt is not an end.
  Unknown end leaves its performed-window placement unknown. Receipt-based
  rest bounds remain a distinct coverage variant, never input to a coefficient
  fitted for exact rest. Raw observed sets/games remain stored separately.
- B4 roster-component v1 describes a feature, not an assigned effect:
  `outer * pair * metric * sum(sample_weight * (expected_minutes - historical_minutes)) / 90`.
  The unchanged league pseudo-count is not a named team roster and is never
  represented as a healthy player or a second absence. Every player/sample
  exposure must be explicitly known regulation minutes. The complete baseline
  weights and preprocessing references are bound in feature identity. Training
  and independent review remain necessary before any numeric use.
- B4 optional participation transport is an A1-resolved
  `football-participation-v1` envelope containing a closed
  `football-doubtful-v1` binomial status model, its training cutoff/refs and
  exact population. It supplies no default percentage. The trusted D1 resolver
  must prove its causal training inventory; a public content hash alone does
  not prove fitted provenance or predictive value. No runtime activation or
  empirical approval follows from accepting this mechanical transport.

## Receipt/content identity and clocks (B1)

- Store both immutable content and receipt identities. `content_digest` hashes the complete normalized record (including source revision, excluding receipt time); returned `digest` hashes `{content_digest, observed_at}`. Canonical receipt time is UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ`. Persist the content digest alongside each receipt. Exact duplicate receipt ingestion is idempotent; a later actual recheck is a new receipt. Never overwrite first receipt to refresh old data.
- Normalize B1 timestamps before hashing/comparison; reject naive/invalid dates. Validity time may be future (for a forecast); publication time cannot be after the actual receipt. Prospective selection requires receipt <= decision cutoff. Equal-time differing eligible revisions remain conflicting, not lexically selected. Archive publication is a separate proof/classification route, never a rewritten receipt clock.
- Add optional `proof_resolver=None` to historical selection. Default registry is empty. A recognized, explicitly registered source-specific resolver may inspect already secured local evidence (no network during query); no provider-supplied `verified` flag, content hash, self-issued artifact or arbitrary callback is a historical proof. The record's `publication_proof` is only a claim/reference. A resolver must independently bind exact source/content identity, publication instant and secured evidence digest/locator, returning a versioned resolution digest. Until an actual source adapter is reviewed, all late imports remain `retrospective`; tests of a test-only registered resolver prove mechanics only. Selected rows expose `evidence_class`, receipt/content identities and any verified resolution reference. D1/D2 must preserve these distinctions.
- Resolver output is the closed record: `schema=1`, `resolver_id`, `resolver_version`, `content_digest`, `published_at`, `evidence_locator`, `evidence_digest`, `resolution_digest`. The resolver registry, not the payload, determines trust. Unknown/unverifiable proof is retrospective; malformed claimed recognized proof fails integrity validation.

## Baseline roster provenance (B1 structure, B4 producer)

- Use typed `history_refs` records: `{ref, source, source_event_id, native_event_key, event_join, roster_join}`. `ref` is the hash of the price-free historical sport record; both joins are `verified_native` or `unresolved`. Nullable `native_event_key` is allowed for a genuine unresolved CSV row. Never relabel a CSV pseudo-ID as an API-Football native ID. An unresolved reference preserves the valid base distribution but cannot support a verified player/roster feature.
- `reference_weights` is tagged by `schema=1` and `kind`. The football goal variant is `football-goals-v1` with `heads.home` and `heads.away`. Each head stores `outer_weights` (venue/form), `pair_weights` (attack/defense per venue/form), and four named `components`: venue_attack, venue_defense, form_attack, form_defense. No generic expression tree and no changes to existing rate arithmetic.
- Each component stores `{team_id, team_join, scope, prior_raw_weight, metric_weights, goals, xg}`. `team_join` is verified_native/unresolved; scope is home_venue/away_venue/all_form. Goals and any actually used xG term each store `{samples, prior_weight, prior_value, prior_refs}`; samples/prior_refs contain `{ref, weight}`. Sample weights plus normalized prior_weight sum to one; prior_refs are separately normalized within the league prior. `prior_raw_weight` preserves the existing 4/3 pseudo-count, not a learned penalty. xG is null when unused. Outer 0.75/0.25, pair 0.5/0.5, actual conditional goal/xG mixture and separate missing-xG samples remain explicit.
- B1 validates this declared shape without computing roster features. Other sport reference variants are added by their owning B/C tasks with explicit validators; B1 may represent unavailable provenance as `{schema:1, kind:"unavailable", reason:<stable code>}`. This means no verified roster effect, never an invalid/hidden baseline. Do not label that placeholder as completed source/model integration.

## Ordered residual features (B2)

- Every training row uses the exact artifact-wide ordered feature_names; do not sort/reorder one head independently. Fits retain explicit family/head routing. Each head's coef and scale lengths must match the declared feature order. Training-only scale is max(population std with ddof=0, 1e-8), with no mean subtraction. Existing specified losses, gradients, zero-reference behavior and D1 alpha selection remain unchanged.
- Numerical execution clarification after the independent B2 pre-review: evaluate the rate inverse link in joint log space so a representable `base * exp(delta)` is not rejected merely because the intermediate exponential overflows/underflows (examples `1e-300,+800` and `1e300,-800`). Preserve the exact base for zero delta. Truly nonfinite/nonpositive rates or numerically saturated logit endpoints are typed model errors, never clipped values. This is a stable implementation of the specified link, not a new fitted model variant.
- Counts mean integer-valued observations, not exclusively Python integer dtype: `1.0` is legal, fractional successes/counts are not. Poisson targets are nonnegative; binomial successes/trials are integer-valued with `0 <= target <= trials`, `trials >= 1`, default one. The standalone identity fit supports finite real targets, including negative values, without prematurely adding C-family contracts.
- B2 owns one shared closed standalone fit validator, reused by EffectArtifact heads and offset prediction: exact `link,scale,coef,alpha,n_rows`, supported link, same nonempty dimensions, finite JSON lists, scale >= 1e-8, alpha >= 0, actual integer n_rows >= 2. Artifact feature order and family/head checks remain additional requirements. Numeric functions reject bool/string/object/complex/masked inputs before float conversion, wrong shapes and unintended broadcasting. Failed convergence, exceptions or nonfinite scale/objective/gradient/parameters produce the typed model error, not a zero or prior fit. Synthetic edge tests establish mechanics only.

## Scope, comparison and snapshot binding (B1/B3, then D2/D3)

- Add a complete canonical FeatureVector `feature_hash` to `snapshot_key`, retaining its feature_version and sorted context_refs. Reference hash, values, statuses, coverage and refs are therefore all bound. Tab/price changes cannot supply a different decision clock or alter this identity.
- Keep comparison as the existing pure distribution result; do not add an alternate comparison wrapper that would force every sport adapter to duplicate its binding. Extend `select_context_result` with explicit keyword inputs `event`, `features`, and `effect_artifact` (verified A1 kind/payload envelope or None). This provides the scope and feature inputs missing from the original signature. Verify effect_hash against A1 canonical envelope hashing and validate its typed payload before checking its scope. When no effect is present, base-only remains a legitimate result.
- D2's verified approval must expose its A1 envelope and bind the exact effect hash, family, feature version, population, coverage and model variant plus its immutable report/experiment provenance. B3 must not treat non-None as sufficient. A malformed or contradictory claimed verified envelope is a typed integrity error. A valid approval for a different scope is not applicable: retain base, with a stable scope-mismatch limitation (comparison may remain experimental only if its own features are eligible). Stale/ineligible features yield not_applied; an accepted zero coefficient remains applied.
- Scope cannot be guessed from names or encoded numeric features. Event permits explicit optional tennis fields `tour`, `surface`, `indoor` from verified metadata; unknown remains null, not a fabricated value. Population uses a closed object with sport and explicit nonempty allowed sets `competitions`, `formats`, `tours`, `surfaces`, `indoor`; nullable members are allowed only for the last three to represent explicitly tested unknown/not-applicable scope. Normalize order/deduplicate at construction, then require canonical form. There are no wildcard/empty-set approvals. D2 must check each event belongs to the frozen tested scope; effect and approval population objects must match exactly. TrainingRow carries that same population object, grouped by canonical identity rather than Python dict hash. This supports explicitly declared multi-competition cohorts without automatic transfer to unseen competition/format/tour/surface.
- Feature values/states/refs share named feature keys. Factor roles cannot claim applied features outside the artifact's consumed feature_names or exceed the actual overall role; no-context/unconsumed features remain not_applied. Preserve factor data states independently. The UI may aggregate these names into readable groups but must not turn a checked source into a learned advantage.

## B1 execution clarifications — 2026-09-08

- Model coverage in FeatureVector, EffectArtifact and TrainingRow is the closed object `{version: <nonempty stable string>, case: <nonempty stable string>}`. It is an identity, not evidence of completeness. Coverage cases are declared by each owning feature/model variant and later matched exactly by B3/D2. Do not silently promote a legacy string to a verified object. The separate operational `factor_state().coverage` remains the brief's explicit completeness status; do not confuse that status with the versioned model-coverage identity. Minimal plan snippets are behavior sketches, not complete contract fixtures.
- B1 supports the explicitly planned families `football:goals:90min`, `tennis:winner` and `tennis:serve`, without prematurely adding C-family implementations. Closed base parameter shapes are respectively `{home_lambda, away_lambda}` (positive finite rates), `{p_a}` (finite probability), and `{hold_a, hold_b, best_of}` (strictly interior hold probabilities, actual integer 3 or 5). An endpoint winner probability may be a valid base; B2/B7 may decline a logit effect without hiding that base. Other families require their owning task's explicit validator extension.
- `BaseDistribution.markets` is a mapping of nonempty canonical market identifiers to finite JSON numeric probabilities in [0,1], never outcome/price/provider objects. This follows B5's `market_probability` float outputs and B7's winner A/B example. B1 validates that typed mapping and rejects forbidden price fields; the owning B5/B7 adapters enforce the exact supported catalog/family and coherent distribution. In particular `tennis:winner` contains exactly `winner_a` and `winner_b` with complementary probabilities. The richer serve catalog belongs to B7; do not falsely certify arbitrary typed keys as a supported market. A1/B1 storage does not authorize probability use on its own.
- Observation `payload` is a strictly validated finite JSON object with string keys and no price/bookmaker fields at any depth. B1 stores normalized source observations, not arbitrary model features; each B4/B6/C producer must add its own source_schema/kind-specific allowlist before using a field numerically. No raw provider blob, permissive object-to-dict conversion or claimed source completeness. B1's shape checks are not proof of causal provider coverage.
- Historical reads select the causal class (prospective or separately archive-verified) independently from retrospective imports for each source/subject/kind. Causal availability is actual receipt for prospective data, independently verified publication time for archive data. Retrospective imports remain separately labelled and use actual receipt ordering; a later unverified correction cannot displace an earlier causal fact. Preserve equal-time conflicts within each class. D1/D2 exclude retrospective rows explicitly, never infer eligibility from a nonempty query result.

### B1 independent-review correction contract

- Preserve `factor_state.refs` as explicitly documented **audit-only inspected receipt references**, including relevant inspected event-status evidence; the original missing-data example may retain its diagnostic references. Add `usable_refs` as a separate sorted unique list. It is nonempty only for an available factor and contains exactly the final same-event/scope/schedule, prospectively received, applicable, fresh, source-precedence-selected observations that actually establish the factor. B4/B6 and later C feature builders must derive numeric input provenance from this usable selection, never promote the audit list into FeatureVector refs or causal training input. No database schema or historical receipt changes are needed.
- A `factor_state` call is for one native event and complete declared event scope. Reject mixed event/sport/competition/format rows before any early status decision; schedule revision text alone is not identity. Event-status invalidation additionally requires the same schedule, an eligible actual receipt and `valid_from <= cutoff < valid_until` (or no end), and preserves its status receipt in audit provenance. Future or expired status does not invalidate the current factor.
- Resolve the usable source collection before computing actual-fact presence, required completeness, coverage, usable refs and freshness metadata. Excluded stale/empty/lower-priority observations cannot lend freshness, factual substance or completeness to selected rows. A fresh empty incomplete player payload remains missing; a selected incomplete collection remains missing when complete coverage is required. Conflicts and unavailable states carry no usable numeric references.

Controller basis: complete independent B1 report and public-path reproductions, original B1 missing-data example, current factor implementation and downstream feature interfaces. This narrow return-contract clarification preserves diagnostic history while preventing excluded records from looking causally consumed. It requires fresh focused/full regression and independent rereview; source validity and empirical activation remain separate.

Controller basis: read the B1 brief/decisions, B5/B7 interfaces and examples, actual `challenge_engine.market_probability` and `tennis.predict.market_summary`, and C2/C3/C4 family boundaries. Wrong choices could alias coverage scopes, silently coerce outcome objects, invent unsupported markets or let retrospective corrections displace causal data. Require closed-shape, boundary-probability, unknown-family and mixed-evidence-class regressions. These clarifications do not approve any source or relax empirical thresholds.

## Previously recorded implementation risks

- Receipt/proof schema errors could falsely make retrospective data causal; therefore unknown archive sources remain untrusted and these cases require regressions.
- Reference/scope shape errors could misjoin players or over-transfer an approval; unresolved joins keep the baseline visible and block only that effect, and all new shapes require round-trip and mismatch tests.
- Feature-order or snapshot-binding errors could route coefficients incorrectly or reuse the wrong calculation; exact ordering, full feature hashes, changed-coverage tests and independent review are required before any release.
