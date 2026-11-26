import json
from datetime import timedelta

import pytest

import forecast_evidence
import wettfinder_automation as worker
from config_loader import AppConfig
from tests.test_forecast_evidence_settlement import (
    DECISION, START, FootballProvider, football_row, record, run,
)
from tests.test_wettfinder_next_day import NOW, TODAY, TOMORROW, _today_snapshot, _next_day_snapshot


def pair(kickoff, captured):
    return dict(fixture_id=1, league_id=39, home_id=10, away_id=20,
                kickoff=kickoff.isoformat(), captured_at=captured.isoformat(),
                model_version="model-v1", model_scope="same_competition",
                with_form=(.30, .30, .40), without_form=(.40, .25, .35))


@pytest.mark.parametrize("forced", [False, True])
def test_regular_today_scan_writes_study_without_adding_forecasts(tmp_path, monkeypatch, forced):
    state = tmp_path / "wettfinder_latest.json"
    monkeypatch.setattr(worker, "STATE_PATH", state)
    monkeypatch.setattr(forecast_evidence, "_now", lambda: NOW)
    calls = []

    def scan(day, _config, **opts):
        capture = opts.get("form_comparison_capture")
        calls.append((day, capture is not None))
        if capture:
            capture(pair(NOW + timedelta(hours=4), NOW))
        return _today_snapshot() if day == TODAY else _next_day_snapshot()

    monkeypatch.setattr(worker, "_default_football_scan", scan)
    result = worker.run_wettfinder(now=NOW, state_path=state, clock=lambda: NOW,
        config=AppConfig(api_football_key="test"), force_football=forced,
        football_next_day=True, team_esports_next_day=False, riskobet_enabled=False,
        football_context_refresher=lambda *_args: {}, football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [],
        evidence_db_path=tmp_path / "evidence.db", evidence_settlement_runner=lambda **_kwargs: {})

    assert calls == [(TODAY, not forced), (TOMORROW, False)]
    assert {row["fixture_id"] for row in result["model_candidates"]} == {1, 2}
    report = tmp_path / "football_form_comparison_latest.json"
    if forced:
        assert not report.exists()
    else:
        payload = json.loads(report.read_text(encoding="utf-8"))
        assert payload["stored"] == 1 and payload["settled"] == 0
        assert payload["generated_at"] == NOW.isoformat()
        assert payload["capture"]["inserted"] == 1


def test_existing_result_queue_settles_study_without_querying_unserved_pairs(tmp_path, monkeypatch):
    from football_form_comparison import append_pairs, league_report

    evidence = tmp_path / "evidence.db"
    study = tmp_path / "football_form_comparison.db"
    append_pairs(study, [pair(START, DECISION), {**pair(START, DECISION), "fixture_id": 2}],
                 recorded_at=DECISION)
    record(evidence, monkeypatch, [football_row()])

    class Provider(FootballProvider):
        def details_by_fixture(self, ids):
            rows = super().details_by_fixture(ids)
            for row in rows.values():
                row["league"] = {"id": 39}
            return rows

    provider = Provider()
    summary = run(evidence, football_provider=provider, form_comparison_path=study)
    assert provider.calls == [("details", (1,))]
    assert summary["terminal_results"] == 1
    assert league_report(study)["settled"] == 1
    assert league_report(study)["stored"] == 2


def test_broken_optional_study_is_tried_only_once_and_does_not_hold_results(tmp_path, monkeypatch):
    import football_form_comparison

    evidence = tmp_path / "evidence.db"
    record(evidence, monkeypatch, [football_row(fixture_id=1), football_row(fixture_id=2)])
    attempts = []

    def unavailable(_path, fixture, *, observed_at):
        attempts.append(fixture["fixture"]["id"])
        raise OSError("unavailable sidecar")

    monkeypatch.setattr(football_form_comparison, "settle_pairs", unavailable)
    provider = FootballProvider()
    summary = run(evidence, football_provider=provider,
                  form_comparison_path=tmp_path / "unavailable.db")
    assert provider.calls == [("details", (1, 2))]
    assert summary["terminal_results"] == 2
    assert len(attempts) == 1
