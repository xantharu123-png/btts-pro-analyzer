# Controller decisions for D1/D2 and the B3 approval boundary

These clarify the approved experiment and acceptance interfaces; they do not relax a threshold or certify any dataset. Read together with context-contract-decisions.md. The controller read both D briefs, the B contracts and the approved specification, then adjudicated the bounded read-only preflight. No code or real evaluation is supplied by this document.

## D1 implementation rulings — 9 September 2026

Controller read the complete `task-16-preflight-20260909.md` and accepts its
A-D boundaries, with these precise implementation choices. These do not make
the incomplete real corpus causal or authorize a new source/subscription.

- Add an owning closed outcome transport separately from B4 appearances/B6
  workload, never extra target fields in those existing payloads. Football v1
  uses actual native FT regulation outcomes; AET/PEN cannot borrow final goals.
  Tennis completed winner requires real native A/B/tour/winner; retirement and
  walkover are not silently added. Serve requires actual bilateral hold/trial
  data and the declared final set outcome. An internal synthetic serve schema
  is not an available real source capability.
- Replay gets an explicit keyword-only recipe/state input and returns the
  proposed separate replay envelope, leaving B1 BaseDistribution unchanged.
  Logical cutoff, exact code/model/calibrator/input references, original base,
  full Event/native-identity hash and actual reconstruction clock are bound.
  Only owning resolved receipts can establish its evidence class; no free
  caller `verified`/archive flag, no backdated state or freshness bypass.
- Keep the proposed closed EventCase alongside unchanged scalar TrainingRows.
  Every referenced outcome/replay/receipt/preprocessing byte must resolve;
  content hashes prove internal consistency, not historical source truth.
  Features must be derived without the target result entering feature history.
  Unresolved cross-source aliases remain excluded; no name/kickoff matching.
- Implement a report-returning fit function with explicit keyword-only cases;
  `train_family` remains an artifact-only projection on successful fit, with a
  typed failure on unavailable data/fit. The separate closed FitResult binds
  all alpha scores, selected alpha, case/row/config hashes and exclusions.
  Do not extend EffectArtifact, accept executable callbacks or mutate config.
- Train/tune fitting must reject final-test cases, not inspect their labels and
  then silently filter them. Select the train-only fit by exact declared
  event-market Brier using full B5/B7 comparisons; ties choose larger alpha.
  Shared mirrored A/B serve fitting is one law, not averaged independent fits;
  doubled head observations never double the canonical event count.
- Freeze explicit feature vocabulary; absent player/component columns are not
  zeros. Prior participation/preprocessing for earlier cases must itself be
  available before each case, not fitted at a later outer cutoff. New pooled
  role designs need an explicit owning feature version, never a hidden D1 fill.
- The initial packet owns outcome/case/replay contracts, supported causal row
  assembly, actual train/tune fitting and reports. Persisted experiment/opened-
  test registry and CLI integration follow after these closed contracts are
  reviewed. None of these mechanics constitutes a completed D1 real run.

### Owning assembly interface clarification

`assemble_training_cases(cases, config)` is the one source-resolving assembly
path. It supersedes the older insufficient three-argument
`build_football_training_rows` / `build_tennis_training_rows` sketches, which
cannot bind the approved closed EventCase/config/replay contract. Do not add a
second unchecked row builder just to reproduce those obsolete signatures.
The implementer's Python-wide caller search found no existing implementations
or callers to preserve; the audit must retain that evidence. This is an
interface clarification, not a weaker provenance requirement or proof of a
real Tennis replay. B5/B7 assembly mechanics and actual causal fits remain
distinct completion claims.

## Frozen inventory and opening transport — 9 September 2026

The D1 plan adds the already required `hypotheses` and global
`event_identity_hash`, plus `test_inventory`. Each inventory entry is closed:
`{event, decision_at, block}`. `event` is the unchanged B1 Event, not an outcome;
`decision_at` is the actual pre-start feature/base cutoff, not kickoff. Entries
are sorted by decision/event key and a canonical native event occurs once.
Block `test:i` is recomputed from the frozen half-open intervals. The full
identity-map artifact is `context-native-identity-map-v1`; its owner is D1's
`training_contracts.validate_identity_map` / `resolve_identity_map`. The map
hash binds the whole dataset, never one convenient event. Freeze checks the
map shape and inventory identities; only resolved source receipts establish
identity evidence during assembly/evaluation. No label or source truth is
implied by freeze alone.

Opening is an append-only A1 artifact `context-test-opening-v1`, with closed
payload `{schema, experiment_hash, event_identity_hash, event_keys, opened_at}`.
The sorted unique `event_keys` must equal the frozen experiment inventory, not
a selected successful subset. An A1 IMMEDIATE transaction verifies prior
opening hashes/references and rejects a different experiment overlapping any
opened canonical event. Exact reruns reuse the original opening unchanged.
This uses A1 artifacts, no additional table/manifest shape. A changed creation
clock, dataset hash or identity-map revision does not reset opened events.
This is a local analysis workflow guard, not proof nobody saw external match
results. Freeze/open alone cannot issue model approval; D2 still needs real
source-resolved cases, full registry/cohort evaluation and linked provenance.

## 1. The selected fit stays train-only

D1 explicitly requires train-only scale and coefficients. Fit each declared alpha on train, choose using event-mean Brier on tune (existing tie rule unchanged), and freeze the selected train-only fit. Do not refit coefficients/scales/player or participation effects on train+tune. EffectArtifact.training_end is the logical train_end, not tune_end or the physical artifact creation time. Preserve all tuning scores and the chosen artifact hash. The preflight suggestion to refit train+tune is rejected because it contradicts the explicit plan. Cost if wrong: some usable training observations remain unused; this is preferable to silently changing the approved fitting protocol.

## 2. Register hypotheses even when no fit exists

Add a frozen `hypotheses` list to the D1 experiment. Each closed record has `hypothesis_id`, `family_config_hash`, `ablation`, `target_markets`, `outcome_contract`, `candidate_artifact`, `pretest_status`. The config hash binds a canonical entry of the experiment's family_configs, including sport/family/population/coverage/feature version/order/model variant and declared fitting policy. The hypothesis_id is SHA-256 of canonical bytes of its definition (family_config_hash, ablation, target_markets, outcome_contract), excluding candidate_artifact and pretest_status. No ordinal/name-only or success-dependent identity.

Candidate_artifact is a digest or null. Pretest_status is ready, fit_failed, insufficient_data, unsupported, or baseline_control. Ready requires its verified fitted artifact; failed/unavailable hypotheses keep null and their pretest failure reason in the report. A baseline_control may compare the frozen basis with itself without a learned effect; it never obtains a context approval. The existing candidate_artifacts field must equal the derived set of non-null registered candidates, not a second independent list.

Every results/distribution_losses mapping contains exactly one key per frozen hypothesis_id, including empty tuples for unevaluable entries. Missing/unknown keys or duplicate definitions are errors, not silent exclusions. Every registered hypothesis is reported and receives a BH entry; unevaluable and baseline-control entries use p=1. Pretest-failed/unsupported candidates do not create an empty intersection that erases a supported cohort. For ready variants, eligibility intersections remain within the predeclared comparable population/coverage/target-outcome cohort; a failed ready prediction cannot be silently relabelled unsupported after seeing the test. Cost if wrong: a hypothesis could disappear from multiplicity or unrelated missing data could erase valid comparisons; registry and incomplete-result regressions are required.

## 3. Canonical native event identity is an assembly obligation

Before split_rows, dataset assembly must resolve each event_key to the canonical, namespaced native B Event identity. A string-only split function cannot discover that two unrelated provider strings name the same real match. Use a frozen identity policy and verified alias-to-canonical evidence; its canonical identity-map hash is bound as `event_identity_hash` in the dataset/experiment. Do not infer a verified join from names or kickoff similarity. Unresolved cross-source identity stays outside the strict population, with counts/reasons, without hiding a runtime baseline. All head/market rows and known aliases of one event share one decision and split; test the assembly plus split path, not just string grouping. Cost if wrong: one match could leak across splits or inflate the 200-event count.

## 4. Preserve the statistical sampling unit and order

aggregate_event_losses also returns canonical decision_at. Each canonical eligible event contributes exactly one unweighted advantage; order the HAC input by (decision_at, event_key) across the declared consecutive blocks. Do not concatenate provider order or weight by market/head count. BH is keyed by hypothesis_id, exactly one p-value per registry entry. Existing confidence constant, bandwidth/Bartlett/zero-variance/invalid-input formulas remain unchanged. Cost if wrong: ordering or duplicated event weights would change uncertainty and the pass/fail result.

## 5. Distribution comparison uses the same final events

Each distribution-loss row has event_key, decision_at, block, outcome_contract, base_logloss, context_logloss, tail_policy. Exactly one row per event, matching the fixed distribution outcome. Use the same final eligibility intersection as primary Brier, not a more favorable second subset. A missing/invalid distribution is a reported exclusion in that ready cohort; all event and block counts are computed after the common intersection. Compute unweighted event means, and report block differences separately. Follow the existing declared tail policy; never hide impossible outcomes with an after-the-fact epsilon. Continuous-density logloss is not incorrectly constrained to nonnegative values. Cost if wrong: the no-worse-distribution requirement could be passed on a different population.

## 6. Close the approval transport and provenance

Use A1 artifact kind `context-effect-v1` for EffectArtifact, `context-evaluation-v1` for the immutable full D2 report, and `context-approval-v1` for successful approvals. The active approval slot is `context-approval:<effect_hash>`. Effect/approval rollback remains coupled under D4.

The closed approval payload contains schema=1, decision="approved", hypothesis_id, experiment_hash, report_hash, effect_hash, dataset_hash, event_identity_hash, code_revision, policy_version, base_versions, sport, family, feature_version, population, coverage, model_variant, target_markets, outcome_contract, test_events_hash, evaluated_at. Canonical types/clocks/scope conventions are inherited from B. The full immutable report contains every paired/calibration/block/cohort metric; report_hash binds all of them, avoiding a second independently editable statistics copy in the compact approval.

approved_effect returns the verified record `{digest, kind, payload}`. Its digest must equal SHA-256(canonical_bytes({kind,payload})); the outer digest is never included in its own hash. Before returning, D2 loads/hash-checks the linked report and experiment, validates the registered hypothesis/candidate, recomputes the approval decision from the report's policy metrics rather than trusting a passed flag, and checks exact effect/scope/base version/feature coverage, publication/decision eligibility, and provenance agreement. It does not return unchecked provider JSON or accept a force flag. An event's feature_hash remains B3 snapshot identity, not a global approval for one historical event.

B3 validates this exact transport/hash and common bindings before using it; D2 is the trusted storage/provenance resolver outside B3's CPU-only transaction. Malformed or contradictory claimed verified records are integrity errors; a valid but inapplicable scope retains basis/limitations. B3/D3 keep the declared target-market certification visible to the existing market-specific checks; untested markets/families cannot inherit certification. This is not a new blanket market ban. Cost if wrong: an approval could bind the wrong residual baseline, model or scope, or lose its verifiable origin; round-trip, mismatch and corruption tests must cover the producer/consumer seam.

## 7. A new experiment hash must not reset opened-test history

The spec requires new untouched data after model/policy selection changes. Persist an append-only record of test opening/evaluation tied to the canonical test-event inventory and exact experiment_hash. D1/D2 must reject a changed experiment that overlaps already opened final-test events; a changed created_at or dataset hash alone does not make those events untouched. Exact reruns use the same frozen experiment identity. Register/open the inventory before evaluation consumes labels, and keep it even if evaluation fails. Predeclared hypotheses inside one experiment are evaluated together; missing candidates remain in that registry. Source/result corrections are recorded as revisions, not a way to relabel an inspected test window as fresh. Cost if wrong: repeated experiments could silently tune against the final test and invalidate the claimed FDR/holdout evidence. This is a required D1/D2 persistence check, not a new model-quality threshold.
