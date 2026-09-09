"""Offline actual-response capture tests; no provider/data qualification."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from context_observations import append_observation
from scripts import tennis_daily as daily


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def competition(**changes):
    return {"id": "101", "date": "2026-09-08T18:00Z",
        "status": {"type": {"state": "post", "completed": True, "name": "STATUS_FINAL"}},
        "competitors": [{"id": "1", "linescores": [{"value": 6, "winner": True}, {"value": 6, "winner": True}]},
                        {"id": "2", "linescores": [{"value": 2, "winner": False}, {"value": 4, "winner": False}]}],
        **changes}


def response(comp=None, *, slug="mens-singles"):
    return {"events": [{"id": "189-2026", "groupings": [{"grouping": {"slug": slug},
        "competitions": [competition() if comp is None else comp]}]}]}


def records(comp=None, *, clock=NOW-timedelta(hours=1), tour="ATP", slug="mens-singles", tournament="189-2026"):
    from context_sources.tennis_status import normalize_tennis_status
    return normalize_tennis_status(tour, tournament, competition() if comp is None else comp,
                                  grouping_slug=slug, observed_at=clock)


def persist(db, rows, *, clock):
    return tuple(append_observation(db, row, observed_at=clock) for row in rows)


def test_status_binds_both_exact_actual_workload_receipts():
    rows = records()
    status, *work = rows
    assert status["source_schema"] == "espn-tennis-event-status-v1"
    assert len(work) == 2
    expected = sorted(digest({"content_digest": digest(row), "observed_at": canonical_timestamp(NOW-timedelta(hours=1))}) for row in work)
    assert status["payload"]["workload_receipts"] == expected
    assert status["payload"]["status"] == "completed"
    assert all(row["payload"]["actual_end"] is None and row["payload"]["minutes"] is None for row in work)
    assert all(not row["complete"] for row in rows)


@pytest.mark.parametrize("state,name,completed", [
    ("pre", "STATUS_SCHEDULED", False), ("in", "STATUS_IN_PROGRESS", False),
    ("post", "STATUS_CANCELED", True), ("post", "STATUS_ABANDONED", True),
    ("post", "STATUS_DEFAULTED", True), ("strange", "STATUS_UNKNOWN", False),
])
def test_nonterminal_and_unsupported_still_have_native_retraction_record(state, name, completed):
    rows = records(competition(status={"type": {"state": state, "name": name, "completed": completed}}))
    assert len(rows) == 1
    assert rows[0]["event_key"] == "espn:tennis:ATP:match:101"
    assert rows[0]["payload"]["workload_receipts"] == []
    assert rows[0]["payload"]["native_status"]["name"] == name


@pytest.mark.parametrize("change", [
    {"competitors": []}, {"competitors": [{"id": "1"}]},
    {"competitors": [{"id": True}, {"id": "2"}]},
    {"competitors": [{"id": "1"}, {"id": "1"}]},
    {"date": "not-a-date"}, {"date": None}, {"status": []},
    {"status": {"type": {"state": "post", "completed": "true", "name": "STATUS_FINAL"}}},
])
def test_bad_native_projection_is_retained_as_unknown_not_old_values(change):
    rows = records(competition(**change))
    assert len(rows) == 1
    assert rows[0]["payload"]["issues"]
    assert rows[0]["payload"]["workload_receipts"] == []


def test_wrong_singles_group_and_missing_tournament_retain_only_retraction():
    for kwargs in ({"slug": "mens-doubles"}, {"tournament": None}):
        rows = records(**kwargs)
        assert len(rows) == 1 and rows[0]["payload"]["issues"]


@pytest.mark.parametrize("bad_id", [None, True, "name", "01", 0, -1])
def test_no_invented_native_event_for_invalid_match_id(bad_id):
    with pytest.raises(ContextContractError):
        records(competition(id=bad_id))


def test_prices_names_extra_provider_fields_are_not_competition_revision_inputs():
    old = records()
    raw = competition(odds={"decimal": 1.2}, displayName="Untrusted label", weather={"degrees": 25})
    raw["competitors"][0]["athlete"] = {"displayName": "Some person"}
    assert records(raw) == old
    assert records(clock=NOW) != old


def test_dated_sanitized_two_match_fixture_is_shape_evidence_only():
    sample = json.loads((Path(__file__).parent / "fixtures/tennis_context_espn_20260907.json").read_text(encoding="utf-8"))
    clock = datetime.fromisoformat(sample["received_at"])
    assert len(sample["examples"]) == 2 and sample["new_network_calls"] == 0
    for raw in sample["examples"]:
        rows = records(raw, clock=clock, tournament=raw["event_id"])
        assert len(rows) == 3
        assert rows[0]["valid_from"] == canonical_timestamp(clock)
        assert all(r["payload"]["actual_end"] is None for r in rows[1:])


def fake_get(monkeypatch, raw):
    calls = []
    class Reply:
        def raise_for_status(self):
            pass
        def json(self):
            return deepcopy(raw)
    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return Reply()
    monkeypatch.setattr(daily.requests, "get", get)
    return calls


def test_existing_request_default_output_and_query_count_remain_unchanged(monkeypatch, tmp_path):
    from context_sources.tennis_capture import capture_tennis_worker
    import context_sources.tennis_capture as capture
    import runtime_paths
    raw, db = response(), tmp_path / "context.db"
    monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", db)
    calls = fake_get(monkeypatch, raw)
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    assert daily._fetch_espn_events("atp", "2026-09-09") == raw["events"]
    assert not db.exists()
    with capture_tennis_worker(path=db) as observer:
        assert daily._fetch_espn_events("atp", "2026-09-09") == raw["events"]
    assert len(calls) == 2 and calls[0] == calls[1]
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM context_observations").fetchone()[0] == 3
        assert connection.execute("SELECT DISTINCT observed_at FROM context_observations").fetchall() == [(canonical_timestamp(NOW),)]
    assert observer.report()["status"] == "captured"


def test_capture_drains_received_data_on_worker_exception_and_resets_scope(monkeypatch, tmp_path):
    from context_sources.tennis_capture import capture_tennis_worker
    db = tmp_path / "context.db"
    calls = fake_get(monkeypatch, response())
    with pytest.raises(RuntimeError, match="worker failed"):
        with capture_tennis_worker(path=db):
            daily._fetch_espn_events("atp", "2026-09-09")
            raise RuntimeError("worker failed")
    before = db.read_bytes()
    daily._fetch_espn_events("atp", "2026-09-09")
    assert db.read_bytes() == before and len(calls) == 2


def test_empty_worker_creates_no_database_and_nested_worker_rejected(tmp_path):
    from context_sources.tennis_capture import capture_tennis_worker
    db = tmp_path / "unused.db"
    with capture_tennis_worker(path=db) as observer:
        with pytest.raises(ContextContractError):
            with capture_tennis_worker(path=db):
                pass
    assert not db.exists() and observer.report()["status"] == "no_receipts"


def test_main_owns_capture_but_pending_refresh_never_fetches(monkeypatch, tmp_path):
    import context_sources.tennis_capture as capture
    from contextlib import contextmanager
    calls = []
    @contextmanager
    def owner(**kwargs):
        calls.append("enter")
        yield type("Report", (), {"report": lambda self: {"status": "no_receipts", "issues": []}})()
        calls.append("exit")
    monkeypatch.setattr(capture, "capture_tennis_worker", owner)
    monkeypatch.setattr(daily, "_run_daily", lambda args: calls.append("run") or 0)
    monkeypatch.setattr(daily.sys, "argv", ["tennis_daily.py", "2026-09-09"])
    assert daily.main() == 0 and calls == ["enter", "run", "exit"]
    monkeypatch.setattr(daily.requests, "get", lambda *a, **kw: pytest.fail("pending refresh fetched"))
    monkeypatch.setattr(daily.shadow, "latest_predictions", lambda *a, **kw: [])
    calls.clear()
    assert daily.refresh_pending_predictions(db_path=tmp_path/"legacy.db", as_of=NOW)["provider_checked"] is False
    assert calls == []


@pytest.mark.parametrize("terminal", ["retired", "walkover"])
def test_supported_terminal_is_not_a_health_diagnosis_or_invented_work(terminal):
    raw = competition(notes=[{"text": terminal}])
    rows = records(raw)
    assert len(rows) == 3 and rows[0]["payload"]["status"] == "completed"
    for row in rows[1:]:
        assert row["payload"]["incomplete_match"] is True
        assert row["payload"]["actual_end"] is None and row["payload"]["minutes"] is None
        assert not any("injur" in key or "health" in key for key in row["payload"])
        if terminal == "walkover":
            assert row["payload"]["sets"] is row["payload"]["games"] is None


def test_utc_equivalent_receipt_is_exactly_same_revision():
    from datetime import timezone
    assert records(clock=NOW) == records(clock=NOW.astimezone(timezone(timedelta(hours=2))))
    with pytest.raises(ContextContractError):
        records(clock=NOW.replace(tzinfo=None))


def test_source_score_error_keeps_status_with_unknown_workload():
    raw = competition()
    raw["competitors"][0]["linescores"] = "bad source scores"
    rows = records(raw)
    assert len(rows) == 1
    assert rows[0]["payload"]["issues"] == ["terminal-workload-unavailable"]


def test_doubles_and_unknown_group_do_not_acquire_singles_workload():
    for slug in ("mens-doubles", "womens-singles", None):
        answer = records(slug=slug)
        assert len(answer) == 1 and answer[0]["format"] == "unsupported"
        assert answer[0]["payload"]["issues"] == ["unsupported-format"]


def test_partial_capture_persists_native_retractions_and_continues_valid_events(monkeypatch, tmp_path):
    from context_sources.tennis_capture import capture_tennis_worker
    from context_sources.tennis_status import tennis_observations_as_of
    import context_sources.tennis_capture as capture
    raw = response()
    raw["events"][0]["groupings"][0]["competitions"].extend([
        competition(id="102", competitors=[]), competition(id=None), competition(id="103")])
    fake_get(monkeypatch, raw)
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    db = tmp_path / "partial.db"
    with capture_tennis_worker(path=db) as observer:
        daily._fetch_espn_events("atp", "2026-09-09")
    pool = tennis_observations_as_of(db, cutoff=NOW, tour="ATP")
    assert len(pool) == 7
    assert observer.report()["status"] == "partial"
    assert observer.report()["issues"] == ["invalid-participants", "native-competition-unavailable"]


def test_storage_interruption_keeps_status_first_and_does_not_swallow_integrity(monkeypatch, tmp_path):
    import context_sources.tennis_capture as capture
    from context_sources.tennis_status import tennis_observations_as_of
    from context_models.tennis_v3 import tennis_features_v3
    from test_tennis_context_features import base, event
    calls, db = [], tmp_path / "interrupted.db"
    fake_get(monkeypatch, response())
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    original = capture.append_observation
    def interrupted(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("persistent store failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(capture, "append_observation", interrupted)
    with pytest.raises(RuntimeError, match="persistent store failure"):
        with capture.capture_tennis_worker(path=db):
            daily._fetch_espn_events("atp", "2026-09-09")
    rows = tennis_observations_as_of(db, cutoff=NOW, tour="ATP")
    assert len(rows) == 1 and rows[0]["kind"] == "event_status"
    assert tennis_features_v3(event(), rows, base(), cutoff=NOW)["values"]["observed_recovery_minimum_hours_a"] is None
    with capture.capture_tennis_worker(path=tmp_path/"empty.db"):
        pass


def test_old_workload_source_and_feature_versions_remain_publicly_unchanged():
    from context_models.tennis import FEATURE_VERSION
    from context_sources.tennis import SOURCE_SCHEMA
    assert FEATURE_VERSION == "tennis-performed-load-v2"
    assert SOURCE_SCHEMA == "espn-tennis-workload-v1"
