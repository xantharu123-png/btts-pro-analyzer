# Independent card-analysis review

Date: 2026-09-08. Review target: exact `8c3df7978bf074cfe6ce3d9a794f6f60139327ea..e8e057fcef2ad6be860d2bbe7cf4b0808f78b4f5` in `C:/Projekt/BetBoy/betboy-app/.worktrees/erklaerbare-karten-20260908`.

Disposition: **one actionable P2; fix and focused rereview required**. No other actionable finding in this bounded review.

## P2 — Reject future model clocks for the optional numerical explanation

Primary anchor: `forecast_analysis.py:89-91`; rendering consumption: `forecast_analysis.py:294-298`. Reader transport: `ev_signal_sources.py:1316-1324`, called by both automated readers.

`_identity` checks `input_cutoff_at <= modeled_at <= scheduled_start`, but never checks either model clock against the actual evaluation time. `read_football_analysis` has no evaluation-clock parameter, and `build_forecast_analysis` reads the envelope without applying the `current` clock it already uses for context freshness. Neither the existing document loader nor the two automated readers supplies a compensating model-clock check: the document loader only verifies the artifact generation time.

Reproduced through the real document loader and both readers using the existing valid synthetic football test fixture:

- Artifact generation: `2030-01-01T10:00:00+00:00`.
- Evaluation: `2030-01-01T10:01:00+00:00`.
- `modeled_at`: `2030-01-01T12:00:00+00:00`.
- `input_cutoff_at`: `2030-01-01T11:59:00+00:00`.
- Kickoff: `2030-01-01T15:00:00+00:00`.
- Bound basis: expected goals `1.527 / 1.133`, probability `0.60`.

Observed: `automated_wettfinder_forecasts` **and** `automated_wettfinder_signals` each returned one signal with non-null analysis evidence. `build_wettfinder_card(..., now=evaluation_time)` displayed the specific `1.53 / 1.13` model basis. Thus the concern is an actual reachable reader/rendering defect, not merely a missing local assertion.

Required narrow correction: use the shared evaluation clock to decline optional numerical explanation whose supplied model or input cutoff clock is in the future. Keep the underlying forecast, probability, haircut, rank, price state, and existing release contract unchanged; show the normal honest fallback. Include both future-clock cases and a boundary-at-now case in regression coverage.

### Reproduction (in memory; no provider or runtime database access)

Run with the quality interpreter, `-B -`, in the review worktree:

```python
from datetime import datetime, timezone
import json, runpy
from unittest.mock import patch
import requests
import ev_signal_sources as sources
from forecast_analysis import project_football_analysis
from wettfinder_surface import build_wettfinder_card

helpers = runpy.run_path('tests/test_ev_signal_sources.py')
row = helpers['_playable_automatic_candidate']()
row.update(home_id=10, away_id=11,
           modeled_at='2030-01-01T12:00:00+00:00',
           input_cutoff_at='2030-01-01T11:59:00+00:00')
row['analysis_evidence'] = project_football_analysis(row, model_basis={
    **row, 'expected_home_goals': 1.527, 'expected_away_goals': 1.133,
    'venue_samples': [12, 12], 'form_samples': [6, 6],
})
document = helpers['_automatic_document'](
    [helpers['_model_overlay'](row)], candidates=[row])
now = datetime(2030, 1, 1, 10, 1, tzinfo=timezone.utc)
with patch.object(sources.Path, 'read_text', return_value=json.dumps(document)), \
     patch.object(requests.sessions.Session, 'request',
                  side_effect=AssertionError('No network')):
    for builder in (sources.automated_wettfinder_forecasts,
                    sources.automated_wettfinder_signals):
        signals = builder('memory-only-review.json', now=now)
        assert len(signals) == 1
        assert signals[0].analysis_evidence is not None  # defect at reviewed HEAD
        card = build_wettfinder_card(signals[0], now=now)
        assert '1,53' in card.analysis_basis             # defect at reviewed HEAD
        print(builder.__name__, card.analysis_basis)
```

## Independent checks completed

- Read `task-brief.md` and implementation `report.md` fully. Verified target HEAD exactly. Invoked the exact Git diff once; read complete relevant source/test files directly where the tool's aggregate diff output was truncated.
- Traced optional envelope projection, both readers, the card renderer, existing document clock validation, and context-refresh rebinding in both catalogs.
- Checked canonical market definitions and settlement contracts, goal versus count-model sample/rate provenance, all configured market paths including conjunction/disjunction, selected-side reversal, sub-50% complement wording, missing legacy envelopes, and unmodeled context wording.
- The projection is price-free and introduces no provider/API call, generation call, scan, or reader-side legacy join. Existing source/model/price/release policies remain outside this change. Original model clocks are preserved on context refresh in both catalogs.
- Reran the five scoped modules independently:

  ```powershell
  & 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -B -m pytest tests/test_forecast_analysis.py tests/test_wettfinder_surface.py tests/test_wettfinder_automation.py tests/test_ev_signal_sources.py tests/test_workflow_integrity.py -q -p no:cacheprovider --basetemp=.pytest_tmp/cards-review-independent01
  ```

  Exit 0: **305 passed, 26 subtests passed in 4.00s**. The reported full-suite result (**1,787 passed, 11 skipped, 97 subtests**) was read, not independently rerun in this review.

## Boundaries

No source edits, Git writes, provider requests, VPS access, runtime database access, sibling worktree access, or subagent dispatch. Only this review report was added. Controller-owned browser/output artifacts and `scripts/stage_runtime_databases.py` were not touched. Rendered desktop/mobile acceptance, deployment and actual production post-refresh verification remain controller-owned. No model profitability, live fixture accuracy or complete context-model integration is approved by this review.

## Focused rereview — P2 closed

Date: 2026-09-08. Exact follow-up reviewed: `e8e057fcef2ad6be860d2bbe7cf4b0808f78b4f5..f82d7aeea2e42d81affa2c4389cb377f2293af5c`.

**Approved source HEAD: `f82d7aeea2e42d81affa2c4389cb377f2293af5c`. No actionable findings remain within this review scope.** This follow-up supersedes the original P2 disposition above; it does not approve production deployment or the separate context-model project.

Read the complete follow-up diff once and the complete updated implementation report. The only production-source changes add optional evaluation-time validation and pass the existing shared evaluation clock from both automated readers and the direct forecast renderer. Search of all Python callsites confirms that every runtime use of `read_football_analysis` supplies that clock; only structural test/projection checks omit it. No model probability, haircut, ordering, price, release policy, original source-clock string, or context-refresh implementation was changed in this follow-up.

Independently reran the original in-memory real-document-loader reproduction, extended to seven temporal cases through **both** automated readers and direct card rendering:

| Case at evaluation `2030-01-01T10:01:00+00:00` | Result |
| --- | --- |
| Original model `12:00`, cutoff `11:59` | Optional evidence rejected; visible fallback |
| `modeled_at` absent, cutoff `11:59` | Optional evidence rejected; visible fallback |
| `input_cutoff_at` absent, model `12:00` | Optional evidence rejected; visible fallback |
| Model absent, cutoff exactly `10:01` | Numerical basis retained |
| Cutoff absent, model exactly `10:01` | Numerical basis retained |
| Both clocks exactly `10:01` | Numerical basis retained |
| Both clocks `12:01+02:00` (same instant as evaluation) | Numerical basis retained |

All seven cases passed for both readers and direct cards. The isolated future-cutoff case proves the cutoff guard independently of the model guard. Compared each resulting signal/card against the same document without optional evidence: all non-analysis fields, probability, haircut, release fields and reference quote were identical; price remained `PLAYABLE`; source strings and original in-memory artifact stayed unchanged. Requests and any new reader/analysis wall-clock acquisition were forbidden by mocks. This rerun made no source edit or fixture-file write.

Fresh independent scoped regression:

```powershell
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -B -m pytest tests/test_forecast_analysis.py tests/test_wettfinder_surface.py tests/test_wettfinder_automation.py tests/test_ev_signal_sources.py tests/test_workflow_integrity.py -q -p no:cacheprovider --basetemp=.pytest_tmp/cards-review-independent02
```

Exit 0: **313 passed, 26 subtests passed in 4.30s**. The implementation report's fresh full-suite result (**1,795 passed, 11 skipped, 97 subtests**) was read, not independently rerun here. The four follow-up source/test files have no working-tree content diff against the approved HEAD. Working-file hashes match the updated implementation report:

- `forecast_analysis.py`: `c1e5341a5df4e3409e4714c72bf434c8ec24aff8539a3da9ccbfa6dc7405f258`.
- `ev_signal_sources.py`: `298bb9510afc586181abd05f410346fefcd20375a5ce4347bdc4d8c063d1d797`.
- `tests/test_forecast_analysis.py`: `d371ad291f2092d212cf93bfe2b9aec57b7491f54e7316bcc5a7b4fcc99d0f4b`.
- `tests/test_ev_signal_sources.py`: `36cdffd0fde7ee783dd32bee58816afbda59d8fe3bc20820747672cdd27917f4`.

All original read-only and production/browser boundaries remain in force. Only this reviewer-owned follow-up section was written.
