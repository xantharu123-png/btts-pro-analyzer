# Shared basketball and hockey forecasts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Repair F6 by exposing the existing same-call basketball/hockey model outputs in normal Wettfinder, with their real evidence limitations.
**Architecture:** An optional immutable typed forecast payload travels on the existing RisikoBet model snapshot; one pure projector supplies the normal research catalogue after the existing run returns. No extra fetch, prediction or model fitting.
**Tech Stack:** Python dataclasses, current immutable JSON/SQLite store, Streamlit, pytest.
**Spec:** `docs/audits/2026-09-18-produktqualitaet.md` F6 and `docs/superpowers/specs/2026-09-07-kontextmodell-design.md` sections 3, 4.3, 6.3, 10.

## Global Constraints

- No prices, bookmakers or requested returns enter model values or selection order.
- No invented probabilities, risk haircuts, conservative bounds or minimum odds. Unqualified research is not an approved tip.
- No second sport calculation or provider request for another tab. Original calculation and source clocks survive reuse.
- Cricket behavior and old immutable snapshot payloads/IDs remain unchanged. No historical enrichment/rewrite.
- No financial-store, staking, settlement or strict-release relaxation. No network, production writes or deployment in this task.
- Use the reviewed shared selection/explanation interfaces from the preceding task. No parallel implementation, apply_patch only, TDD, focused tests, owned commits; root runs full suite and push.

### Task 1: Persist and consume the full existing team-sport forecast

**Files:** Create `team_sport_forecasts.py` and `tests/test_team_sport_forecasts.py`. Modify `riskobet_domain.py`, `riskobet_candidates.py`, `riskobet_automation.py`, `wettfinder_automation.py`, `ev_signal_sources.py`, `wettfinder_surface.py`, `forecast_analysis.py`, relevant tests and only exact consumers requiring a nullable research-risk guard. A narrow `daily3_ui.py`/`tests/test_daily3_ui.py` copy clarification makes shared provenance and unfilled slots explicit. Keep domain validation focused in the new module; no unrelated refactoring.

**Interfaces:** Frozen `TeamSportForecast`, owned closed `to_dict/from_dict`, optional `EventModelSnapshot.team_sport_forecast`; absent field omitted in legacy serialization. Pure `team_sport_forecast_rows(run, *, now, target_date)` projects existing returned snapshots, never loads/fits another model. `ModelSignal.probability_haircut` and card cautious probability may be None only under the exact new research-only source contract.

- [ ] RED: through actual `adapt_research_matchwinner` and synthetic valid history fixtures, prove full base probabilities survive even for 50/50, a below-RisikoBet-threshold underdog, either underdog side and no selected risk candidate. Assert prediction call count is one, no new data calls, exact unrounded values.
- [ ] Define typed payload fields: schema/kind, provider/event IDs, home/away IDs/names, model input hash, p_home/p_away, actual market contract, training/home/away counts, evaluation, latest result observation, base missing inputs, factors and limitations, optional regulation components. Validate finite non-boolean probabilities and complete complement within existing numeric tolerance; coherent optional unavailable pairs; identity/time/contract agreement with enclosing snapshot. Do not mistake RisikoBet-specific 'no underdog' for missing base inputs. Keep data immutable (nested mappings/arrays detached or frozen).
- [ ] Populate payload from the already returned PrematchPrediction before underdog filtering. Include its complete canonical schema/payload in adapter input hash only when present. Legacy other sports and snapshots without this field serialize byte-identically. Snapshot reader reconstructs explicitly; malformed/future/misbound payloads fail. Changed payload creates a new snapshot identity, never enriches an old stored key.
- [ ] GREEN roundtrip tests with actual temporary RiskobetStore: original payload/ID preserved, old snapshots readable with field omitted, immutable changed-content collision rejected. No DB schema change.
- [ ] After the existing run_riskobet return and before forecast_evidence recording/publication, project its returned snapshots. Keep only target Zurich date, future starts and valid nonfuture model/source clocks. Emit both full winner outcomes from actual p_home/p_away, snapshot-bound keys and evidence. Reuse prior snapshots with original clocks; expired source evidence or missing base probability yields explicit source-coverage reason, not 50/50. The separate 150-minute highlight-recency rule must not become a new hidden-model filter: otherwise valid older same-day forecasts may remain descriptive. Legacy snapshots without the payload stay immutable and cannot be enriched from risk-candidate guesses; the next normally due source run creates the new payload. Source failures cannot erase independent existing forecasts.
- [ ] Basketball winner contract includes overtime. Hockey full-match winner includes overtime AND shootout; do not label regulation-only. Missing OT support retains no full-match probability. Publish no new regulation markets in this task.
- [ ] Merge these rows through existing catalogue ordering/ledger helpers without rerunning strict recommendations. Add explicit normal-artifact source allowlist/schema contract and per-sport resource bounds. Version the automated artifact when necessary so an old reader cannot silently misinterpret nullable fields. Never append research to strict candidates or challenge_release_candidates.
- [ ] Nullable risk is narrowly allowed only for exact new basketball/hockey research source, RESEARCH stage, statistical_release_passed=False, no release overlay and a valid snapshot-bound payload. Retain required haircut/minimum arithmetic for all existing sources. Ranking uses no substitute zero haircut or invented bound. Card displays model probability/sample basis and 'Modell noch nicht unabhängig bestätigt', not raw internal codes; conservative value/minimum shown as unavailable, not 0 or infinity. Manual money flows and all current qualified-source behavior unchanged.
- [ ] Shared analysis gives factual sample/model explanation and explicit unapplied injury/fatigue limitations. Remain descriptive, not highlighted as a validated safety ranking. Existing selection coherence resolves opposing full winner choices consistently; no copy of only the underdog candidate.
- [ ] Daily3's existing selection caption explicitly says it uses the same Wettfinder forecast pool, not a second independent confirmation. Show actual available selection count against remaining unoccupied slots, including a single choice; never imply three new forecasts or guaranteed daily results. Preserve the existing zero-choice message and occupied/closed-day behavior; do not change budget, reservation or selection policy. Test zero/one/three choices and already occupied slots with the actual Streamlit test harness.
- [ ] Test full reader/card/normal snapshot paths, source counters, same-day reuse without extra calls or clock refresh, expired/failing sources, invalid/null risk rejection outside the narrow contract, unchanged Cricket/football/tennis payloads, and inability to become released merely through an attractive quote.

```python
assert actual_prediction_calls == 1
assert {row['probability'] for row in full_rows} == {prediction.p_home, prediction.p_away}
assert all(row['probability_haircut'] is None and row['minimum_odds'] is None for row in full_rows)
assert all(row['evidence_stage'] == 'RESEARCH' and row['statistical_release_passed'] is False for row in full_rows)
assert strict_recommendations_after == strict_recommendations_before
```

- [ ] Run new focused tests RED then GREEN, affected domain/store/automation/loader/surface/analysis tests, and explicit unchanged-Cricket regressions. Self-review, commit owned files, report exact commands/results and data-dependent limitations. Do not claim contextual effects or improved betting accuracy.
