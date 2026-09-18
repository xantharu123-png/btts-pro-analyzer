# Shared forecast selection — Implementation Plan

**Implementation status (19.09.): COMPLETE and independently reviewed.** Commits `c953d46`, `9467148`; 455 focused tests passed. Final model-identity propagation `a927370` independently closed, 337 tests plus26 subtests. Checklist below is the original execution contract, not unfinished work. Final integration and renderer evidence: [repair report](../../audits/2026-09-18-produktreparatur.md). No demonstrated improvement in predictive quality or VPS activation implied.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Repair product audit F1/F2/F4/F5: one coherent sporting direction across normal Wettfinder and Daily3, evidence-aware highlighting, and explicit underlying data age.
**Architecture:** Add a price-blind shared consumer selection function and shared bound explanation metadata. Reuse existing logical compatibility checks, not new sport models. Keep forecasts visible separately from their eligibility for highlighting.
**Tech Stack:** Python, Streamlit, pytest/AppTest.
**Spec:** `docs/audits/2026-09-18-produktqualitaet.md`, approved repair criteria F1/F2/F4/F5. Existing price and no-market-ban rules remain binding.

## Global Constraints

- No price, bookmaker, minimum odds, haircut, RELEASED status or money balance as a ranking input.
- Do not sort all markets by maximum probability. Compare probability only within mutually exclusive directions of the same event, market family and model revision.
- No categorical ban on any configured market; no invented picks to fill three slots.
- Original forecasts, model values, historical tickets and money rules are immutable.
- Missing or stale evidence may prevent a TOP claim, not erase a forecast because of price.
- Cricket is unchanged; no network, production writes or deployment in this task.
- Work in the current isolated worktree. TDD first, apply_patch edits, commit owned files, root coordinates push.

### Task 1: Common direction, factual explanation and fresh-model highlighting

**Files:** Create `forecast_selection.py` and `tests/test_forecast_selection.py`. Modify `daily3_selection.py`, `forecast_analysis.py`, `wettfinder_surface.py`, `app.py`; extend corresponding tests. Only touch `daily3_ui.py` after the separate price/recovery task is committed, to reuse shared data-age copy if required.
**Interfaces:** `select_consumer_forecasts(rows)` returns original objects in a deterministic quote-independent coherent order. It accepts existing ModelSignal/WettfinderCard identity attributes; cards must retain modeled_at/model_version/policy_version/model_scope and any scalar highlight eligibility needed, without raw private context payloads. `build_forecast_analysis` remains the explanation entry point for public cards; centralize existing exact-bound tennis/esports explanation checks instead of duplicating them.

- [ ] Create the frozen same-event regression using `tests/test_daily3_selection.py::football`: RESULT_AWAY .195253, RESULT_HOME .551276, DC_X2 .454140, DC_1X .806871, same clocks. Preserve bound fixture evidence by rebuilding each fixture with its own probability. The normal and Daily3 selections must admit a jointly possible outcome, irrespective of price mutations. The result-family representative must be HOME rather than the weaker AWAY. Do not compare those two directions with unrelated markets.

```python
assert 'RESULT_AWAY' not in {c.market_key for c in catalog.featured + catalog.additional}
assert choices[0].signal.market_key in {'RESULT_HOME', 'DC_1X'}
assert [s.probability for s in inputs] == original_probabilities
```

- [ ] Add permutations, repeated event revisions, price/status changes, all legacy simple-market examples, and full-pool-before-pagination tests. Compare directions only when the event/participants, canonical model clock and model identity agree. On ties use an explicit stable key, not source iteration. Preserve weak/native event-alias safeguards.
- [ ] Add tests where a 14-hour-old esports signal, unknown model clock or unsupported explanation remains a visible descriptive forecast but cannot become a highlighted TOP card. A fresh exact-bound esports Elo packet must produce its real supporting explanation, not the current missing-football-basis fallback. Test foreign participants and altered observation clocks are rejected as explanatory evidence.
- [ ] Add tennis tests for stats_through/model_built_at/training_cutoff independent of modeled_at. Surface the actual data date and its kind (result date versus tournament-start proxy); missing data date remains unknown, not fresh. A newly recalculated model with January 2000 data must not be highlighted as current. Use existing update policy thresholds if applicable; any new presentation freshness threshold must be named/documented as an operational review rule, not an empirical theorem or prediction filter.
- [ ] Run focused RED tests before production edits. Confirm they fail on opposing published choices, undeserved highlight, missing real explanation and concealed data age.
- [ ] Implement one shared selection pass over the complete pool. Resolve mutually exclusive result/BTTS/H2H directions within one model revision using their comparable probabilities; preserve independent market diversity. Then apply existing `select_coherent_forecasts` once with the same canonical preference in both consumers, before section/slot/price filtering. Daily3 may select fewer compatible events for its slots, never choose an opposing direction because it reordered the raw pool independently.
- [ ] Preserve original forecast values and visible neutral fallback cards. Highlight only candidates whose actual model clock is aware, not future, no older than the existing 150-minute consumer window, and whose exact-bound sport evidence can produce an explanation. Keep a separate explicit field/reason for non-highlight eligibility. Do not let a stale/unexplained record become the primary direction merely by arriving first.
- [ ] Replace unsupported global-best wording with an accurate model-selection heading/badge. Explain what is actually selected (current, supported, diverse forecasts), not guaranteed safety or the best bet. For RESULT_HOME/AWAY supporting text whose rate direction opposes the selected result, describe it explicitly as an outsider scenario instead of claiming those lower rates support a TOP selection. This does not modify the probability.
- [ ] Share tennis/esports evidence-bound explanations across Daily3 and normal cards. Retain the injury/fatigue caveat. Show calculation time and underlying tennis coverage separately, escape text at the existing renderer boundary, keep cards flat.
- [ ] Run all changed consumer tests plus existing coherence, forecast-analysis, workflow-integrity and market-scope tests. Update existing tests only where they intentionally encoded the defective TOP semantics; retain quote independence, all-market eligibility and no-forced-three coverage.
- [ ] Self-review and commit owned source/tests. Write a report with exact RED/GREEN, changed interfaces, chosen operational freshness rule and remaining statistical qualification limits. Do not claim a calibrated best-three ranking or improved accuracy.
