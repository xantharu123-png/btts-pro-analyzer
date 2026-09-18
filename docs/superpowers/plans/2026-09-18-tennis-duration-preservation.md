# Preserve real WTA match duration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Close the confirmed F8 input-loss defect without inventing match end times or activating an unqualified fatigue effect.
**Architecture:** Extend the existing TennisAbstract WTA loader with a validated optional match_duration and explicit missing/conflicting provenance; retain exact historical prediction replay compatibility for the additive loader transition.
**Tech Stack:** Existing Python/pandas loader and pytest; no new package or source.
**Spec:** `docs/superpowers/specs/2026-09-07-kontextmodell-design.md` sections 4.1, 6.2, 7, 9; product audit F8/F9.

## Global Constraints

- No new source, subscription, prediction feature, trained coefficient or activation. Cricket and money state unchanged.
- Match playing duration is not actual end time; date/tournament date/scheduled start/receipt time must not be promoted to a measured end or actual rest.
- Preserve missing, invalid and conflicting source evidence; never zero-fill duration or silently choose a conflicting winner/loser observation.
- Legacy ORIGINAL payloads, source identities and predictions remain immutable and reproducible. Exact historical compatibility only, no generic hash bypass.
- Source headers have already been verified with bounded public GETs by root; worker uses offline source-shaped fixtures, no network/cache/model/VPS writes.

### Task 1: Add duration with truthful coverage and historical replay compatibility

**Files:** `tennis/data_loader.py`, `tests/test_wta_ta_loader.py`, exact compatibility definitions in `context_runtime_tennis.py`/owning manifest module and tests in `tests/test_context_runtime_tennis_live.py`; adjust `context_models/tennis_training.py` only to reuse the SAME exact source-manifest support helper if needed. No other effect or prediction arithmetic changes.

**Verified source contract:** Existing https://www.tennisabstract.com/cgi-bin/leaders_wta.cgi declares matchhead indices 22 tbw, 23 tbl, 24 setw, 25 setl, 26 time, 27 aces, 28 dfs. Native page uses `minutesPerMatch = parseInt(pstats[p].time)/nmatches` and `secondsPerPoint = ...time*60/npoints`. Page read 18 September 2026 with TLS verification, HTTP200, 70801 bytes, SHA256 `5cc9508dd9b4eb850282225e854d0489cb8884e7a30cb5f8b6f2f1a416ccf23a`. Existing source-shaped 45-column fixtures avoid copying full upstream data. Earlier bounded audit found partial leaderboard coverage, not the entire WTA tour.

- [ ] RED tests: native time='97' retained as match_duration=97 for winner and loser views; blank/zero duration remains unavailable, negative/nonintegral/nonfinite/bool/nonnumeric values not coerced into real minutes; duplicate equal durations preserve one match; different valid durations produce missing numeric duration plus conflicting state; one genuinely missing view and one valid value may preserve the available observed value while recording partial coverage. Existing box-score values/dedup and result ordering remain unchanged.
- [ ] Add `_TA['time']=26` and focused parser accepting a positive whole-minute native value only. Preserve optional `match_duration` compatible with existing ATP name, plus `match_duration_state` (available/missing/invalid/conflicting), source and explicit leaderboard-pool coverage. Do not add an actual end time, native provider ID, complete-history claim or health status. Detached observed provenance cannot be used as proof that this data existed before a historical decision.
- [ ] Reconcile duration evidence across all views independently from the existing winner-view box-score precedence: retain distinct valid values to detect conflict, never let a later missing winner view erase a valid observed duration or hide conflicting values. Malformed/missing time must not drop an otherwise valid box-score row. Existing rejection of unsuitable tour levels stays unchanged.

```python
assert frame.iloc[0]['match_duration'] == 97
assert frame.iloc[0]['match_duration_state'] == 'available'
assert 'actual_end_at' not in frame.columns
assert conflicting.iloc[0]['match_duration_state'] == 'conflicting'
assert pd.isna(conflicting.iloc[0]['match_duration'])
```

- [ ] Prove unchanged existing model-state/predict outputs when optional duration columns are added (consumers do not silently activate a new effect). Use owned synthetic loader/state fixtures, no new empirical claim.
- [ ] This source file participates in six-file stored ORIGINAL code identity. Before editing, capture exact current LF/CRLF full-manifest values from Git/current bytes. Extend the reviewed compatibility rule only for the exact current-to-additive-loader transition and already reviewed older locator predecessor, with the other five prediction owner files identical. Existing arbitrary/mixed/future manifest rejection remains. Cover both prior production manifests, actual old ORIGINAL replay through runtime and training verifier, and rejection when another owner changes. Never merely overwrite historical pins or accept any data_loader hash.
- [ ] Run new focused RED/GREEN, existing WTA loader/training-refresh/live-replay/runtime/legacy-parity tests affected. Self-review and commit owned files. Report actual field retention and remaining native-identity/end-time/empirical gaps; do not describe duration preservation as completed fatigue modeling. Root owns broad tests and push.
