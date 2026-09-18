# Price and recovery truth repair — Implementation Plan

**Implementation status (19.09.): COMPLETE and independently reviewed.** Commit `f844f05`; 4 new regression tests and 75 consumer tests passed. Checklist below is the original execution contract, not a request to repeat the task. Final integration evidence: [repair report](../../audits/2026-09-18-produktreparatur.md). No empirical workload-effect qualification or VPS activation implied.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Repair F7/F9 of the approved product audit without changing forecasts or money rules.
**Architecture:** Reuse the existing price decision instead of discarding it; describe observed tennis result age without claiming actual recovery. No new model, source, account or service.
**Tech Stack:** Python, Streamlit, pytest/AppTest.
**Spec:** `docs/audits/2026-09-18-produktqualitaet.md`, findings F7/F9, approved for implementation by the user.

## Global Constraints

- Quotes never hide or reorder forecasts. Low quotes produce information, not a booking/import barrier.
- No automatic bet placement, money-rule changes or modifications to existing production records.
- Missing data does not mean healthy or rested. No invented numerical effects.
- Cricket and the VPS remain unchanged. Preserve inherited untracked files.
- Edit with apply_patch. Record actual RED/GREEN commands; commit only owned files. Root coordinates push.

### Task 1: Non-blocking price warnings and honest observed-result ages

**Files:** Modify `daily3_ui.py`, `tennis/workload.py`; extend `tests/test_daily3_ui.py`, `tests/test_tennis_prediction_revisions.py`; create `tests/test_tennis_workload_truth.py` for focused regression cases.
**Interfaces:** Continue consuming `build_wettfinder_card(...).price_code/price_label/value_threshold`. Keep `render_daily3` arguments and monetary callbacks unchanged. Workload output retains existing keys for readers; `minimum_recovery_hours` must not assert actual recovery when history coverage is only observed matches. Add an explicitly named observed-result age if needed; do not redefine a model feature silently.

- [ ] Add an AppTest fixture carrying an exact current quote of 1.12 with a 0.65 model probability and minimum_odds 2.00. The production price status must be TOO_LOW. Assert a warning describing the low offered price is visible while the same forecast remains present. Also test missing/stale price status without changing selection, and the existing real-money record flow remains valid.

```python
assert any('Quote' in w.value and ('unter' in w.value.lower() or 'niedrig' in w.value.lower()) for w in app.warning)
assert any('Heimteam 1' in item.value for item in app.subheader)
```

- [ ] Add a workload fixture with incomplete observed history and disordered start/receipt timestamps. A later-started match whose result was received 48 hours ago cannot prove 48 hours actual rest when another accepted result arrived one hour ago. Assert the actual-rest field is unavailable and the facts explicitly limit the statement to the observed result. Preserve sets/minutes and lack of probability adjustment.

```python
assert player['minimum_recovery_hours'] is None
assert result['probability_adjustment_applied'] is False
assert any('Ergebnis' in fact for fact in player['facts'])
assert not any('tatsächliche Erholung mindestens' in fact for fact in player['facts'])
```

- [ ] Run these focused tests before editing production code; verify behavioral RED rather than fixture/import errors.
- [ ] Render the existing price status beside Daily3's quote. For TOO_LOW use a warning; for unavailable, stale, thin/borderline or invalid threshold use accurate existing status concepts without claiming safety. Never disable callbacks because of this display change.

```python
if card.price_code == 'TOO_LOW':
    st.warning('Die beobachtete Quote liegt unter der berechneten Preisschwelle. Die Modell-Auswahl bleibt unverändert.')
```

- [ ] Replace the legacy actual-rest claim with time since the specifically observed result and an explicit incomplete-history limitation. If retaining elapsed hours, expose them under an observed-result name, with no effect change. Check consumers of the old field before making it unavailable and update their tests to reflect the honest semantic contract.
- [ ] Run the focused regressions, all `test_daily3_ui.py`, `test_daily3_selection.py`, `test_tennis_prediction_revisions.py`, plus relevant workload consumers discovered by exact symbol search. Root runs broad integration tests once after all repair blocks.
- [ ] Self-review, commit owned source/tests, and write report with RED/GREEN evidence, changed files and limitations. No push, deployment or full-suite duplication by the worker.
