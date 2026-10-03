from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

import consumer_tip_history as history
from market_consensus import parse_fixture_consensus


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
START = NOW+timedelta(hours=4)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_now", lambda: NOW)
    return tmp_path/"consumer.db"


def row(fixture=1, **changes):
    return {
        "candidate_id": f"{fixture}:BTTS_YES", "fixture_id": fixture,
        "event_identity": f"football:{fixture}", "sport": "Fußball",
        "source": "football_challenge", "market_key": "BTTS_YES", "selection": "Ja",
        "scheduled_start": START.isoformat(), "probability": .6,
        "model_version": "model-v1", "policy_version": "selection-v1",
        "modeled_at": (NOW-timedelta(minutes=5)).isoformat(),
        "input_cutoff_at": (NOW-timedelta(minutes=10)).isoformat(),
        "home_team": "Home", "away_team": "Away", **changes,
    }


def record(db, rows, **kw):
    return history.record_tip_publication(db, surface="wettfinder:top", rows=rows,
                                         as_of=kw.pop("as_of", NOW), source_run_id="run-1", **kw)


def quote(candidate, captured=NOW, odds=2.0):
    payload = {"response": [{
        "fixture": {"id": candidate["fixture_id"], "date": candidate["scheduled_start"]},
        "update": captured.isoformat(), "bookmakers": [
            {"id": number, "name": f"Book {number}", "bets": [
                {"name": "Both Teams Score", "values": [{"value": "Yes", "odd": str(odds)}]}]}
            for number in (1, 2, 3)],
    }]}
    return parse_fixture_consensus(payload, [candidate], fetched_at=captured)[candidate["candidate_id"]].to_dict()


def test_only_supplied_display_inventory_is_stored_in_original_order(db):
    outcome = record(db, [row(2), row(1)])
    assert outcome["status"] == "recorded" and outcome["recorded_tips"] == 2
    publication, = history.read_tip_publications(db)
    assert publication["complete"] is True
    assert [tip["candidate_id"] for tip in publication["tips"]] == ["2:BTTS_YES", "1:BTTS_YES"]
    assert [tip["position"] for tip in publication["tips"]] == [0, 1]
    assert all(tip["quote"] == {"status": "missing"} for tip in publication["tips"])


def test_retry_clock_does_not_duplicate_or_rewrite_first_observation(db, monkeypatch):
    first = record(db, [row()])
    monkeypatch.setattr(history, "_now", lambda: NOW+timedelta(minutes=1))
    second = record(db, [row()], as_of=NOW+timedelta(minutes=1))
    assert second["status"] == "unchanged"
    assert second["publication_id"] == first["publication_id"]
    assert second["first_observed_at"] == NOW.isoformat()
    assert len(history.read_tip_publications(db)) == 1


def test_empty_inventory_and_surface_policy_content_changes_are_historized(db):
    assert record(db, [])["recorded_tips"] == 0
    record(db, [row()], policy_version="display-v1")
    record(db, [row(probability=.61)], policy_version="display-v1")
    history.record_tip_publication(db, surface="daily3:plan", rows=[row()], as_of=NOW)
    pubs = history.read_tip_publications(db)
    assert len(pubs) == 4
    assert sorted(pub["recorded_count"] for pub in pubs) == [0, 1, 1, 1]


def test_bulk_context_secrets_evidence_refs_and_money_never_enter_storage(db):
    heavy = row(context={"api_key": "private", "refs": ["x"*100]*100_000},
                context_evidence={"password": "private"}, context_summary="token=private",
                account_id="private", balance=100, stake=10, analysis_evidence={"heavy": [1]*100_000})
    assert record(db, [heavy])["status"] == "recorded"
    with sqlite3.connect(db) as conn:
        raw = conn.execute("SELECT payload_json FROM consumer_tips").fetchone()[0]
        assert len(raw.encode()) < 2000
        assert all(word not in raw for word in ("private", "refs", "context_evidence", "account", "balance", "stake", "heavy"))
    before = db.stat().st_size
    for _ in range(20):
        assert record(db, [heavy])["status"] == "unchanged"
    assert db.stat().st_size == before


@pytest.mark.parametrize("changes, reason", [
    ({"scheduled_start": NOW.isoformat()}, "event_already_started"),
    ({"scheduled_start": "2030-01-01T15:00:00"}, "invalid_clock"),
    ({"probability": True}, "invalid_probability"),
    ({"probability": float("nan")}, "invalid_probability"),
    ({"modeled_at": (NOW+timedelta(seconds=1)).isoformat()}, "future_model_input"),
    ({"input_cutoff_at": NOW.isoformat()}, "input_after_model"),
    ({"market_key": ""}, "invalid_text"),
    ({"candidate_id": "token=private"}, "invalid_text"),
    ({"fixture_id": True}, "invalid_native_identity"),
    ({"forecast_id": "not-a-sha"}, "invalid_forecast_id"),
    ({"fixture_id": "1"}, "invalid_native_identity"),
    ({"away_team": "HOME"}, "identical_participants"),
    ({"event_key": "football:2"}, "conflicting_event_identity"),
    ({"competitor_a": "A", "competitor_b": "B", "selected_competitor": "C"}, "invalid_selected_competitor"),
    ({"home_team_id": 1, "home_id": 2}, "conflicting_participant_aliases"),
    ({"home_team_id": 1, "away_id": 1}, "identical_participant_ids"),
    ({"competitor_a_id": "a", "competitor_b_id": "a"}, "identical_participant_ids"),
])
def test_invalid_rows_are_counted_without_claiming_complete_inventory(db, changes, reason):
    result = record(db, [row(**changes), row(2)])
    assert result["recorded_tips"] == 1 and result["skipped_tips"] == 1
    assert result["errors"] == {reason: 1}
    publication, = history.read_tip_publications(db)
    assert publication["complete"] is False and publication["supplied_count"] == 2


def test_no_historical_backfill_or_future_capture_and_unknown_clocks_remain_unknown(db, monkeypatch):
    assert record(db, [row()], as_of=NOW+timedelta(seconds=1))["status"] == "rejected"
    assert not db.exists()
    monkeypatch.setattr(history, "_now", lambda: START)
    result = record(db, [row()])
    assert result["recorded_tips"] == 0 and result["errors"] == {"event_already_started": 1}
    monkeypatch.setattr(history, "_now", lambda: NOW)
    record(db, [row(modeled_at=None, input_cutoff_at=None)])
    tip = next(pub for pub in history.read_tip_publications(db) if pub["recorded_count"])["tips"][0]
    assert tip["modeled_at"] is None and tip["input_cutoff_at"] is None


def test_exact_real_quote_is_recorded_without_value_gate_or_synthetic_prices(db):
    item = row(minimum_odds=100)
    item["reference_quote"] = quote(item, odds=1.15)
    record(db, [item])
    tip = history.read_tip_publications(db)[0]["tips"][0]
    assert tip["quote"]["status"] == "observed"
    assert tip["quote"]["odds"] == 1.15
    assert tip["quote"]["observed_at"] == NOW.isoformat()
    assert "minimum_odds" not in tip


@pytest.mark.parametrize("kind, expected", [("stale", "stale"), ("future", "future"),
                                            ("wrong_side", "identity_mismatch"), ("malformed", "invalid")])
def test_quote_clocks_and_side_identity_never_become_executable_by_capture(db, kind, expected):
    item = row()
    captured = NOW-timedelta(hours=2) if kind == "stale" else NOW+timedelta(minutes=1) if kind == "future" else NOW
    item["reference_quote"] = quote(item, captured=captured)
    if kind == "wrong_side":
        item["selection"] = "Nein"
    if kind == "malformed":
        item["reference_quote"] = {"odds": 100}
    record(db, [item])
    assert history.read_tip_publications(db)[0]["tips"][0]["quote"]["status"] == expected


def test_actual_capture_clock_not_old_selector_clock_determines_quote_freshness(db, monkeypatch):
    item = row()
    item["reference_quote"] = quote(item)
    monkeypatch.setattr(history, "_now", lambda: NOW+timedelta(hours=1))
    record(db, [item], as_of=NOW)
    assert history.read_tip_publications(db)[0]["tips"][0]["quote"]["status"] == "stale"


def test_readonly_reader_does_not_create_missing_db_and_filters_capture_time(db):
    assert history.read_tip_publications(db) == [] and not db.exists()
    record(db, [row()])
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    assert len(history.read_tip_publications(db, since=NOW, until=NOW+timedelta(seconds=1))) == 1
    assert history.read_tip_publications(db, until=NOW) == []
    assert history.read_tip_publications(db, surface="daily3:plan") == []
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_schema_conflicts_and_hash_corruption_fail_closed_without_overwrite(db):
    record(db, [row()])
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute("UPDATE consumer_tips SET payload_json='{}'")
        conn.execute("DROP TRIGGER consumer_tips_no_update")
        conn.execute("UPDATE consumer_tips SET payload_json='{}'")
        conn.execute(history._trigger_sql("consumer_tips", "UPDATE"))
    before = db.read_bytes()
    assert record(db, [row()])["status"] == "rejected"
    with pytest.raises(ValueError, match="invalid_tip_hash"):
        history.read_tip_publications(db)
    assert db.read_bytes() == before


def test_foreign_database_and_partial_schema_are_not_migrated(db):
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE accounts (name TEXT)")
    before = db.read_bytes()
    assert record(db, [row()])["status"] == "rejected"
    assert db.read_bytes() == before


def test_locked_database_is_bounded_and_does_not_mutate_existing_publications(db):
    record(db, [row()])
    with sqlite3.connect(db) as locked:
        locked.execute("BEGIN IMMEDIATE")
        result = record(db, [row(2)])
        assert result["status"] == "unavailable" and result["errors"] == {"OperationalError": 1}
        locked.rollback()
    assert len(history.read_tip_publications(db)) == 1


def test_missing_read_path_never_creates_parent_or_empty_database(tmp_path):
    target = tmp_path/"absent"/"tips.db"
    assert history.read_tip_publications(target) == []
    assert not target.parent.exists()


def test_concurrent_retries_are_atomic_and_idempotent(db):
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: record(db, [row()]), range(12)))
    assert sum(result["status"] == "recorded" for result in results) == 1
    assert all(result["status"] in {"recorded", "unchanged"} for result in results)
    assert len(history.read_tip_publications(db)) == 1


def test_reader_limits_duplicates_and_infinite_iterators_are_bounded(db, monkeypatch):
    result = record(db, [row(), row()])
    assert result["recorded_tips"] == 1 and result["errors"] == {"duplicate_display_row": 1}
    record(db, [row(2)])
    with pytest.raises(ValueError, match="publication_reader_limit_exceeded"):
        history.read_tip_publications(db, limit=1)
    monkeypatch.setattr(history, "MAX_PUBLICATION_ROWS", 2)
    from itertools import repeat
    assert record(db, repeat(row()))["errors"] == {"too_many_publication_rows": 1}


def test_dataclass_like_signals_and_role_forecast_binding_hints_are_supported(db):
    item = row(featured_role="primary", forecast_id="a"*64, snapshot_id="b"*64)
    item.pop("event_identity")
    item["key"] = item.pop("candidate_id")
    result = record(db, [SimpleNamespace(**item)])
    assert result["recorded_tips"] == 1
    tip = history.read_tip_publications(db)[0]["tips"][0]
    assert json.loads(tip["event_key"]) == ["football", "fixture", "1"]
    assert tip["featured_role"] == "primary" and tip["forecast_id"] == "a"*64
    assert tip["snapshot_id"] == "b"*64


def test_event_date_filter_excludes_old_unrelated_publications_before_limit(db, monkeypatch):
    old = NOW-timedelta(days=10)
    monkeypatch.setattr(history, "_now", lambda: old)
    for fixture in range(2, 5):
        item = row(fixture, scheduled_start=(old+timedelta(hours=4)).isoformat(),
                   modeled_at=(old-timedelta(minutes=5)).isoformat(),
                   input_cutoff_at=(old-timedelta(minutes=10)).isoformat())
        record(db, [item], as_of=old)
    monkeypatch.setattr(history, "_now", lambda: NOW)
    record(db, [row()])
    data = history.read_tip_publications(db, limit=1,
        event_window_start=NOW, event_window_end=NOW+timedelta(days=1))
    assert len(data) == 1 and data[0]["tips"][0]["event_key"] == "football:1"


def test_event_date_filter_preserves_original_capture_when_schedule_changes(db, monkeypatch):
    old = NOW-timedelta(days=2)
    monkeypatch.setattr(history, "_now", lambda: old)
    item = row(scheduled_start=(old+timedelta(hours=4)).isoformat(),
               modeled_at=(old-timedelta(minutes=5)).isoformat(),
               input_cutoff_at=(old-timedelta(minutes=10)).isoformat())
    record(db, [item], as_of=old)
    monkeypatch.setattr(history, "_now", lambda: NOW)
    record(db, [row()])
    data = history.read_tip_publications(db,
        event_window_start=NOW, event_window_end=NOW+timedelta(days=1))
    assert len(data) == 2 and data[0]["first_observed_at"] == old.isoformat()


def test_event_date_filter_never_uses_future_publication_to_reconstruct_past_day(db, monkeypatch):
    old = NOW-timedelta(days=2)
    monkeypatch.setattr(history, "_now", lambda: old)
    item = row(scheduled_start=(old+timedelta(hours=4)).isoformat(),
               modeled_at=(old-timedelta(minutes=5)).isoformat(),
               input_cutoff_at=(old-timedelta(minutes=10)).isoformat())
    record(db, [item], as_of=old)
    monkeypatch.setattr(history, "_now", lambda: NOW)
    record(db, [row()])
    data = history.read_tip_publications(db, until=NOW,
        event_window_start=NOW, event_window_end=NOW+timedelta(days=1))
    assert data == []
