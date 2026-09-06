from datetime import datetime, timedelta, timezone
from contextlib import closing
import json
import sqlite3

import pytest
import wettfinder_automation as worker
from ev_signal_sources import ModelSignal
from config_loader import AppConfig


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)


def test_shared_tennis_refresh_runs_before_both_consumer_reads(tmp_path):
    events = []
    def refresh(**kwargs):
        events.append("refresh")
        return {"status": "complete", "refreshed": 1, "errors": [], "provider_checked": False}
    def read(**kwargs):
        events.append("read")
        return []
    document = worker.run_wettfinder(
        now=NOW, state_path=tmp_path / "latest.json",
        football_scanner=lambda _: {"candidates": []},
        tennis_model_refresher=refresh, tennis_loader=read,
        esports_loader=lambda **_: [], riskobet_enabled=False,
    )
    assert events == ["refresh", "read"]
    assert document["sources"]["tennis"]["model_refresh"]["refreshed"] == 1
    assert document["sources"]["tennis"]["model_refresh"]["provider_checked"] is False


def test_refresh_failure_is_reported_without_erasing_persisted_forecasts(tmp_path):
    def refresh(**kwargs):
        raise OSError("private provider detail")
    document = worker.run_wettfinder(
        now=NOW, state_path=tmp_path / "latest.json",
        football_scanner=lambda _: {"candidates": []},
        tennis_model_refresher=refresh, tennis_loader=lambda **_: [],
        esports_loader=lambda **_: [], riskobet_enabled=False,
    )
    assert document["sources"]["tennis"]["model_refresh"] == {
        "status": "failed", "failure_type": "OSError",
    }
    assert document["sources"]["tennis"]["operational_error_count"] == 1
    assert document["run_status"] == "degraded"


def test_isolated_local_worker_never_starts_default_tennis_writer(tmp_path, monkeypatch):
    from scripts import tennis_daily
    monkeypatch.setattr(tennis_daily, "refresh_pending_predictions", lambda **_: pytest.fail("local writer invoked"))
    worker.run_wettfinder(
        now=NOW, state_path=tmp_path / "latest.json",
        football_scanner=lambda _: {"candidates": []},
        tennis_loader=lambda **_: [], esports_loader=lambda **_: [], riskobet_enabled=False,
    )


def test_worker_records_native_tennis_identity_and_runs_evidence_settlement(tmp_path, monkeypatch):
    import forecast_evidence
    monkeypatch.setattr(forecast_evidence, "_now", lambda: NOW)
    evidence_db = tmp_path / "quality.db"
    calls = []
    def settle(**kwargs):
        calls.append(kwargs["db_path"])
        return {"terminal_results": 0, "errors": []}
    signal = ModelSignal(
        key="tennis-model-1-A", label="Alpha vs Beta", probability=.62,
        probability_haircut=.15, evidence_stage="SHADOW", policy_version="test",
        detail="test", sport="Tennis", source="tennis_model", market="Match Winner",
        market_key="H2H", selection="Sieg Alpha", competitor_a="Alpha", competitor_b="Beta",
        selected_competitor="Alpha", fixture_source="ESPN", provider_event_id="123",
        scheduled_start=(NOW+timedelta(hours=6)).isoformat(), modeled_at=NOW.isoformat(),
        input_cutoff_at=NOW.isoformat(), model_version="tennis-native-v1",
    )
    document = worker.run_wettfinder(
        now=NOW, state_path=tmp_path / "latest.json", evidence_db_path=evidence_db,
        evidence_settlement_runner=settle,
        football_scanner=lambda _: {"candidates": []},
        tennis_loader=lambda **_: [signal], esports_loader=lambda **_: [], riskobet_enabled=False,
    )
    assert calls == [evidence_db]
    assert document["forecast_evidence"]["recorded"] == 1
    with closing(sqlite3.connect(evidence_db)) as conn:
        row = json.loads(conn.execute("SELECT payload_json FROM forecast_rows").fetchone()[0])
    assert row["selection"] == "Alpha"
    assert row["quote_identity"]["selection"] == "Sieg Alpha"
    assert row["quote_identity"]["provider_event_id"] == "123"
    from riskobet_domain import stable_event_key
    assert row["event_key"] == stable_event_key("tennis", "espn", "123")
    assert row["model_version"] == "tennis-native-v1"


def test_canonical_worker_constructs_result_provider_with_real_config(tmp_path, monkeypatch):
    import forecast_evidence
    monkeypatch.setattr(forecast_evidence, "_now", lambda: NOW)
    path = tmp_path / "latest.json"
    monkeypatch.setattr(worker, "STATE_PATH", path)
    received = []
    def settle(**kwargs):
        received.append(kwargs["football_provider"].weather_key)
        return {"terminal_results": 0, "errors": []}
    document = worker.run_wettfinder(
        now=NOW, state_path=path, evidence_db_path=tmp_path / "quality.db",
        config=AppConfig(api_football_key="test-only", weather_key="test-weather"),
        evidence_settlement_runner=settle,
        tennis_model_refresher=lambda **_: {"status": "complete", "errors": []},
        football_scanner=lambda _: {"candidates": []},
        tennis_loader=lambda **_: [], esports_loader=lambda **_: [], riskobet_enabled=False,
    )
    assert document["forecast_evidence"]["status"] == "completed"
    assert received == ["test-weather"]


def test_risk_source_failure_marks_job_degraded_without_affecting_normal_catalog(tmp_path):
    def risk_failure(**kwargs):
        raise RuntimeError("must not leak")
    document = worker.run_wettfinder(
        now=NOW, state_path=tmp_path / "latest.json",
        football_scanner=lambda _: {"candidates": []},
        tennis_loader=lambda **_: [], esports_loader=lambda **_: [],
        riskobet_enabled=True, riskobet_runner=risk_failure,
    )
    assert document["riskobet"]["status"] == "failed"
    assert document["run_status"] == "degraded"
    assert document["operational_error_count"] >= 1


def test_partial_coverage_does_not_report_operational_failure(tmp_path):
    document = worker.run_wettfinder(
        now=NOW, state_path=tmp_path / "latest.json",
        football_scanner=lambda _: {"candidates": []},
        tennis_loader=lambda **_: [], esports_loader=lambda **_: [],
        riskobet_enabled=True, riskobet_runner=lambda **_: {
            "status": "partial", "candidates": [], "snapshots": [],
            "errors": ["basketball: source_partial"],
        },
    )
    assert document["riskobet"]["error_count"] == 1
    assert document["riskobet"]["operational_error_count"] == 0
    assert document["operational_error_count"] == 0


def test_native_tennis_events_do_not_collide_and_survive_rescheduling():
    from riskobet_domain import stable_event_key
    def identity(provider, event_id, start=NOW):
        return worker._signal_event_identity("Tennis", "same-pair", "Alpha", "Beta", start,
                                             fixture_source=provider, provider_event_id=event_id)
    assert identity("ESPN", "123") == stable_event_key("tennis", "espn", "123")
    assert identity("ESPN", "123") != identity("ESPN", "456")
    assert identity("ESPN", "123") != identity("sofascore", "123")
    assert identity("ESPN", "123") == identity("ESPN", "123", NOW + timedelta(days=1))
