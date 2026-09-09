"""Actual existing GET -> immutable B1 capture; synthetic source responses.

No additional provider call, past publication or validated injury effect is
established by these mechanics tests. Production/runtime files are never used.
"""
from copy import deepcopy
from datetime import timedelta
import importlib
import sqlite3

import pytest

from context_models.contracts import canonical_timestamp
from context_models.contracts import ContextIntegrityError
from context_observations import _SELECT, _decode_receipt
from test_football_context_provider import NOW, payload, provider, sample


def implementation():
    return importlib.import_module("context_sources.football_capture")


def detail():
    return deepcopy(sample()["calls"][0]["samples"][1])


def stored(path):
    if not path.exists():
        return []
    with sqlite3.connect(path) as connection:
        return [_decode_receipt(row) for row in connection.execute(_SELECT)]


def test_capture_existing_gets_once_retains_receipt_not_flush_clock(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    times = iter([NOW, NOW + timedelta(seconds=2)])
    monkeypatch.setattr(owner, "_context_received_at", lambda: next(times))
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path):
        details = owner.details_by_fixture([1575469])
        injuries = owner.injuries_by_fixture([1575469])
    rows = stored(path)
    assert len(calls) == 2 and all(c[1]["allow_redirects"] is False for c in calls)
    assert details == {1575469: detail()} and injuries == {1575469: []}
    assert {row["observed_at"] for row in rows if row["kind"] == "base_fixture"} == {canonical_timestamp(NOW)}
    absent = [row for row in rows if row["kind"] == "availability"]
    assert len(absent) == 2 and all(not row["complete"] for row in absent)
    assert {row["observed_at"] for row in absent} == {canonical_timestamp(NOW + timedelta(seconds=2))}
    assert all(row["published_at"] is None and row["publication_proof"] is None for row in rows)
    assert owner._context_capture is None
    assert "test-key" not in str(rows)


def test_legacy_provider_without_worker_capture_writes_nothing(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    assert owner.details_by_fixture([1575469]) == {1575469: detail()}
    assert owner.injuries_by_fixture([1575469]) == {1575469: []}
    assert len(calls) == 2 and all("allow_redirects" not in call[1] for call in calls)
    assert not list(tmp_path.iterdir())


def test_later_detail_does_not_backdate_an_earlier_injury_binding(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    times = iter([NOW, NOW + timedelta(seconds=2)])
    monkeypatch.setattr(owner, "_context_received_at", lambda: next(times))
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path) as capture:
        owner.injuries_by_fixture([1575469])
        owner.details_by_fixture([1575469])
    assert len(calls) == 2
    assert not any(row["kind"] == "availability" for row in stored(path))
    assert any("native-event-binding" in error for error in capture.report()["issues"])
    assert owner.errors == []


def test_upcoming_source_can_bind_first_injury_before_later_detail(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    times = iter([NOW, NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)])
    monkeypatch.setattr(owner, "_context_received_at", lambda: next(times))
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path):
        owner.upcoming_fixtures(94, 2026, NOW.date())
        owner.injuries_by_fixture([1575469])
        owner.details_by_fixture([1575469])
    absent = [row for row in stored(path) if row["kind"] == "availability"]
    assert len(calls) == 3 and len(absent) == 2
    assert {row["observed_at"] for row in absent} == {canonical_timestamp(NOW + timedelta(seconds=1))}


@pytest.mark.parametrize("invalid", ["paging", "error", "foreign", "duplicate"])
def test_invalid_endpoint_creates_no_captured_assertion(tmp_path, monkeypatch, invalid):
    data = payload([detail()])
    if invalid == "paging":
        data["paging"]["total"] = 2
    elif invalid == "error":
        data["errors"] = {"plan": "not available"}
    elif invalid == "foreign":
        data["response"][0]["fixture"]["id"] = 99
    else:
        data = payload([detail(), detail()])
    owner, calls = provider(monkeypatch, details=data)
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path):
        owner.details_by_fixture([1575469])
    assert stored(path) == [] and len(calls) >= 1


def test_capture_survives_later_worker_failure_and_clears_observer(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "context.db"
    with pytest.raises(RuntimeError, match="model failed"):
        with implementation().capture_football_worker(owner, path=path):
            owner.details_by_fixture([1575469])
            raise RuntimeError("model failed")
    assert stored(path) and len(calls) == 1
    assert owner._context_capture is None


def test_no_new_receipt_on_flush_or_exact_duplicate_ingestion(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "context.db"
    for _ in range(2):
        with implementation().capture_football_worker(owner, path=path):
            owner.details_by_fixture([1575469])
        if len(calls) == 1:
            original = stored(path)
    assert stored(path) == original
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW + timedelta(seconds=30))
    with implementation().capture_football_worker(owner, path=path):
        owner.details_by_fixture([1575469])
    assert len(stored(path)) == 2 * len(original)


def test_source_response_mutation_cannot_change_captured_native_bytes(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path):
        returned = owner.details_by_fixture([1575469])
        returned[1575469]["teams"]["home"]["id"] = 999
    base = next(row for row in stored(path) if row["kind"] == "base_fixture")
    assert base["payload"]["detail"]["teams"]["home"]["id"] == detail()["teams"]["home"]["id"]


@pytest.mark.parametrize("entry", ["automatic-scan", "automatic-refresh", "manual-scan"])
def test_actual_worker_entries_capture_same_two_budgeted_responses(tmp_path, monkeypatch, entry):
    import runtime_paths
    import wettfinder_automation as automation
    import alternative_markets_tab_extended as manual
    from config_loader import AppConfig
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "context.db"
    monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", path)
    seen = []
    def scan(actual, *args, **kwargs):
        assert actual is owner
        seen.append(kwargs)
        actual.details_by_fixture([1575469])
        actual.injuries_by_fixture([1575469])
        return {"shortlist": []}
    if entry == "manual-scan":
        monkeypatch.setattr(manual, "ChallengeDataProvider", lambda *_args: owner)
        monkeypatch.setattr(manual, "scan_daily_challenge", scan)
        monkeypatch.setattr(manual, "fetch_football_consensus", lambda *_args: ({}, []))
        manual._run_market_scan_worker("test", None, [94], NOW.date(), NOW.date(), 20, {})
    else:
        monkeypatch.setattr(automation, "ChallengeDataProvider", lambda *_args: owner)
        if entry == "automatic-scan":
            monkeypatch.setattr(automation, "scan_daily_challenge", scan)
            automation._default_football_scan(NOW.date(), AppConfig(api_football_key="test"))
        else:
            monkeypatch.setattr(automation, "refresh_discovered_candidates", scan)
            automation._default_football_context_refresh([], NOW.date(), NOW, AppConfig(api_football_key="test"))
    assert len(seen) == 1 and len(calls) == 2
    assert len([row for row in stored(path) if row["kind"] == "availability"]) == 2
    assert owner._context_capture is None


def test_discovery_only_does_not_expand_capture_to_unselected_events(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path):
        owner.upcoming_fixtures(94, 2026, NOW.date())
    assert len(calls) == 1 and not path.exists()


@pytest.mark.parametrize("status", [200, 206, 301, 503])
def test_existing_provider_capture_requires_full_actual_http_200(tmp_path, monkeypatch, status):
    import challenge_15k
    from test_football_context_provider import Response
    owner, _ = provider(monkeypatch)
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    response = Response(payload([detail()]))
    response.status_code = status
    calls = []
    def fetch(*args, **kwargs):
        calls.append(kwargs)
        return response
    monkeypatch.setattr(challenge_15k, "api_football_get", fetch)
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path):
        owner.details_by_fixture([1575469])
    assert len(calls) == 1 and calls[0]["allow_redirects"] is False
    assert bool(stored(path)) is (status == 200)


def test_existing_b1_corruption_is_not_reclassified_as_missing_provider(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path):
        owner.details_by_fixture([1575469])
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE context_contents SET payload=?", (b"{}",))
    with pytest.raises(ContextIntegrityError):
        with implementation().capture_football_worker(owner, path=path):
            owner.details_by_fixture([1575469])
    assert owner._context_capture is None


def test_simultaneous_native_participant_conflict_never_binds_empty_injuries(tmp_path, monkeypatch):
    import challenge_15k
    from test_football_context_provider import Response
    owner, _ = provider(monkeypatch)
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    changed = detail()
    changed["teams"]["home"]["id"] = 999
    responses = iter([payload([detail()]), payload([changed]), payload([])])
    monkeypatch.setattr(challenge_15k, "api_football_get", lambda *_a, **_k: Response(next(responses)))
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path):
        owner.details_by_fixture([1575469])
        owner.details_by_fixture([1575469])
        owner.injuries_by_fixture([1575469])
    rows = stored(path)
    assert len([row for row in rows if row["kind"] == "base_fixture"]) == 2
    assert not any(row["kind"] == "availability" for row in rows)


def test_capture_gap_is_admin_only_not_a_new_legacy_model_scan_failure(tmp_path, monkeypatch):
    # Existing legacy reader can use its rows. This new capture contract cannot
    # certify the source envelope; neither fact grants the other its authority.
    incomplete = payload([detail()])
    incomplete["paging"]["total"] = 2
    owner, _ = provider(monkeypatch, details=incomplete)
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    with implementation().capture_football_worker(owner, path=tmp_path / "context.db") as capture:
        assert owner.details_by_fixture([1575469]) == {1575469: detail()}
    assert owner.errors == []
    assert capture.report()["status"] == "partial"
    assert capture.report()["receipt_refs"] == []


@pytest.mark.parametrize("entry", ["discovery", "refresh"])
def test_capture_report_survives_state_without_changing_old_forecast_fields(entry):
    import wettfinder_automation as automation
    report = {"schema": 1, "scope": "existing-football-context-requests",
              "status": "partial", "receipt_refs": ["a" * 64],
              "issues": ["Kontext-Capture: native-event-binding-unavailable"]}
    snapshot = {"fixtures_found": 3, "fixtures_modeled": 3, "errors": [], "candidates": []}
    def convert(value):
        if entry == "discovery":
            return automation._football_state_from_snapshot(value, attempted_at=NOW, search_date=NOW.date())
        return automation._merge_context_refresh({"status": "completed", "errors": [], "candidates": []},
            value, fixture_ids=[], checked_at=NOW)
    legacy = convert(snapshot)
    assert "context_capture" not in legacy
    captured = convert({**snapshot, "context_capture": report})
    assert captured.pop("context_capture") == report
    assert captured == legacy and captured["status"] == "completed" and captured["errors"] == []
    captured = convert({**snapshot, "context_capture": report})
    report["issues"].append("not a valid issue")
    assert len(captured["context_capture"]["issues"]) == 1


@pytest.mark.parametrize("invalid", [None, {"secret": "must not pass"},
    {"schema": True, "scope": "existing-football-context-requests", "status": "no_receipts",
     "receipt_refs": [], "issues": []}])
def test_capture_report_is_closed_not_arbitrary_snapshot_metadata(invalid):
    import wettfinder_automation as automation
    from context_models.contracts import ContextContractError
    with pytest.raises(ContextContractError):
        automation._football_state_from_snapshot({"context_capture": invalid},
            attempted_at=NOW, search_date=NOW.date())


def test_missing_requested_detail_is_partial_but_preserves_actual_returned_fixture(tmp_path, monkeypatch):
    owner, calls = provider(monkeypatch, details=payload([detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: NOW)
    path = tmp_path / "context.db"
    with implementation().capture_football_worker(owner, path=path) as capture:
        owner._football_get("fixtures", {"ids": "1575469-99"}, "capture fixture")
    assert len(calls) == 1 and owner.errors == []
    assert {row["event_key"] for row in stored(path)} == {"api-football:football:1575469"}
    assert capture.report()["status"] == "partial" and capture.report()["receipt_refs"]
