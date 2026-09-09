"""Later native results for already observed prematch context, no extra GETs."""
from copy import deepcopy
from datetime import datetime, timedelta
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from model_artifacts import put_artifact
from test_context_football_capture import detail, implementation, stored
from test_football_context_provider import NOW, payload, provider


def finished():
    row = detail()
    row["fixture"]["status"]["short"] = "FT"
    row["goals"] = {"home": 2, "away": 1}
    return row


END_RECEIPT = datetime.fromisoformat(detail()["fixture"]["date"]) + timedelta(hours=3)


def capture_prematch(path, monkeypatch, *, fixture=None, at=NOW):
    owner, calls = provider(monkeypatch, details=payload([fixture or detail()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: at)
    with implementation().capture_football_worker(owner, path=path):
        owner.details_by_fixture([1575469])
    assert len(calls) == 1


def capture_results(path, monkeypatch, *, response=None, at=END_RECEIPT, season_only=False):
    owner, calls = provider(monkeypatch, details=response or payload([finished()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: at)
    params = {"league": 94, "season": 2026, "status": "FT"}
    if not season_only:
        params.update({"from": NOW.date().isoformat(), "to": at.date().isoformat(),
                       "timezone": "Europe/Zurich"})
    with implementation().capture_football_worker(owner, path=path) as capture:
        legacy = owner._football_get("fixtures", params, "existing FT history")
    assert len(calls) == 1 and calls[0][1]["allow_redirects"] is False
    return capture.report(), legacy


@pytest.mark.parametrize("season_only", [False, True])
def test_existing_result_response_retains_actual_result_for_previously_watched_event(tmp_path, monkeypatch, season_only):
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    before = {row["digest"]: row for row in stored(path)}
    report, legacy = capture_results(path, monkeypatch, season_only=season_only)
    after = {row["digest"]: row for row in stored(path)}
    outcomes = [row for row in after.values() if row["kind"] == "match_outcome"]
    assert legacy == [finished()]
    assert len(outcomes) == 1
    assert outcomes[0]["payload"]["result"] == {"goals_home": 2, "goals_away": 1}
    assert outcomes[0]["observed_at"] == canonical_timestamp(END_RECEIPT)
    assert outcomes[0]["published_at"] is None and outcomes[0]["publication_proof"] is None
    assert all(after[key] == row for key, row in before.items())
    assert outcomes[0]["digest"] in report["receipt_refs"]


def test_result_capture_does_not_expand_to_unwatched_native_fixtures(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    other = finished()
    other["fixture"]["id"] = 99
    report, legacy = capture_results(path, monkeypatch, response=payload([finished(), other]))
    assert legacy == [finished(), other]
    outcomes = [row for row in stored(path) if row["kind"] == "match_outcome"]
    assert [row["event_key"] for row in outcomes] == ["api-football:football:1575469"]
    assert report["status"] == "captured"


def test_result_only_does_not_create_a_context_database_or_watchlist(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    report, legacy = capture_results(path, monkeypatch)
    assert legacy == [finished()]
    assert report["receipt_refs"] == [] and not path.exists()


@pytest.mark.parametrize("status", ["NS", "TBD", "PST"])
@pytest.mark.parametrize("early", [False, True])
def test_only_actually_prematch_observation_enrols_later_result(tmp_path, monkeypatch, status, early):
    path = tmp_path / "context.db"
    row = detail()
    row["fixture"]["status"]["short"] = status
    capture_prematch(path, monkeypatch, fixture=row, at=NOW if early else END_RECEIPT)
    capture_results(path, monkeypatch, at=END_RECEIPT+timedelta(seconds=1))
    assert len([row for row in stored(path) if row["kind"] == "match_outcome"]) == int(early)


@pytest.mark.parametrize("bad", ["season", "league", "date", "AET", "PEN", "NS", "paging", "duplicate", "goals"])
def test_invalid_or_out_of_scope_result_batch_does_not_create_a_result(tmp_path, monkeypatch, bad):
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    before = stored(path)
    row = finished()
    if bad in {"season", "league"}:
        row["league"]["season" if bad == "season" else "id"] += 1
    elif bad == "date":
        row["fixture"]["date"] = (NOW-timedelta(days=8)).isoformat()
    elif bad in {"AET", "PEN", "NS"}:
        row["fixture"]["status"]["short"] = bad
    elif bad == "goals":
        row["goals"]["away"] = None
    data = payload([row, deepcopy(row)] if bad == "duplicate" else [row])
    if bad == "paging":
        data["paging"]["total"] = 2
    report, legacy = capture_results(path, monkeypatch, response=data)
    assert legacy == data["response"]
    assert stored(path) == before and report["status"] == "partial"


def test_later_outcome_correction_and_repeated_receipts_never_rewrite_prior_bytes(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    capture_results(path, monkeypatch)
    original = {row["digest"]: row for row in stored(path)}
    capture_results(path, monkeypatch)
    assert {row["digest"]: row for row in stored(path)} == original
    correction = finished()
    correction["goals"]["home"] = 3
    capture_results(path, monkeypatch, response=payload([correction]), at=END_RECEIPT+timedelta(minutes=5))
    after = {row["digest"]: row for row in stored(path)}
    assert all(after[key] == value for key, value in original.items())
    outcomes = [row for row in after.values() if row["kind"] == "match_outcome"]
    assert sorted(row["payload"]["result"]["goals_home"] for row in outcomes) == [2, 3]


def test_corrupt_existing_prematch_receipt_is_not_used_as_watch_authority(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    with sqlite3.connect(path) as connection:
        ref = connection.execute("SELECT content_digest FROM context_observations WHERE kind='base_fixture'").fetchone()[0]
        connection.execute("UPDATE context_contents SET payload=? WHERE content_digest=?", (b"{}", ref))
    with pytest.raises(ContextIntegrityError):
        capture_results(path, monkeypatch)


def test_untouched_a1_database_without_context_tables_is_not_initialized_by_result_scan(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    put_artifact(path, kind="test", payload={"x": 1}, created_at=NOW)
    with sqlite3.connect(path) as connection:
        before = connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
    report, _ = capture_results(path, monkeypatch)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall() == before
    assert report["receipt_refs"] == []


def test_future_native_prematch_receipt_cannot_authorize_an_earlier_result(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    future = detail()
    future["fixture"]["date"] = (END_RECEIPT+timedelta(days=3)).isoformat()
    capture_prematch(path, monkeypatch, fixture=future, at=END_RECEIPT+timedelta(days=2))
    report, _ = capture_results(path, monkeypatch)
    assert report["receipt_refs"] == []
    assert not any(row["kind"] == "match_outcome" for row in stored(path))


def test_native_schedule_correction_is_captured_but_not_joined_to_an_old_prediction(tmp_path, monkeypatch):
    from context_models.contracts import ContextContractError
    from context_sources.football import _detail_event
    from context_sources.outcomes import validate_outcome_record
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    corrected = finished()
    corrected["fixture"]["date"] = (datetime.fromisoformat(corrected["fixture"]["date"])+timedelta(hours=1)).isoformat()
    capture_results(path, monkeypatch, response=payload([corrected]))
    record = next(row for row in stored(path) if row["kind"] == "match_outcome")
    record = {**record, "effective_at": record["observed_at"], "evidence_class": "prospective", "publication_resolution": None}
    assert validate_outcome_record(record, event=_detail_event(corrected)) == record
    with pytest.raises(ContextContractError):
        validate_outcome_record(record, event=_detail_event(detail()))


def test_actual_automatic_worker_persists_existing_ft_tail_without_extra_provider_calls(tmp_path, monkeypatch):
    import runtime_paths
    import wettfinder_automation as automation
    from config_loader import AppConfig
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    owner, calls = provider(monkeypatch, details=payload([finished()]))
    monkeypatch.setattr(owner, "_context_received_at", lambda: END_RECEIPT)
    monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", path)
    monkeypatch.setattr(automation, "ChallengeDataProvider", lambda *_: owner)
    def scan(actual, *args, **kwargs):
        assert actual is owner
        assert actual.recent_ft_results(94, 2026, NOW.date(), END_RECEIPT.date()) == [finished()]
        return {"shortlist": [], "fixtures_found": 0}
    monkeypatch.setattr(automation, "scan_daily_challenge", scan)
    result = automation._default_football_scan(END_RECEIPT.date(), AppConfig(api_football_key="test"))
    assert len(calls) == 1 and owner.errors == []
    assert result["context_capture"]["status"] == "captured"
    assert len([row for row in stored(path) if row["kind"] == "match_outcome"]) == 1


def test_incomplete_b1_schema_is_not_mistaken_for_an_empty_watchlist(tmp_path, monkeypatch):
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE context_contents")
    with pytest.raises(ContextIntegrityError):
        capture_results(path, monkeypatch)


@pytest.mark.parametrize("index", ["content_digest", "schedule_revision"])
def test_corrupt_b1_watch_index_cannot_be_used_as_scope_permission(tmp_path, monkeypatch, index):
    path = tmp_path / "context.db"
    capture_prematch(path, monkeypatch)
    with sqlite3.connect(path) as connection:
        connection.execute(f"UPDATE context_observations SET {index}=? WHERE kind='base_fixture'", ("f"*64,))
    with pytest.raises(ContextIntegrityError):
        capture_results(path, monkeypatch)


@pytest.mark.parametrize("index,value", [("source", "espn"), ("source", "API-FOOTBALL"),
    ("kind", "match_outcome"), ("kind", "other")])
@pytest.mark.parametrize("valid_second_watch", [False, True])
def test_scope_index_corruption_fails_before_any_later_result_publication(
        tmp_path, monkeypatch, index, value, valid_second_watch):
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_base_input
    path = tmp_path/"context.db"
    capture_prematch(path, monkeypatch)
    replies = [finished()]
    if valid_second_watch:
        second = detail()
        second["fixture"]["id"] = 99
        append_observation(path, normalize_football_base_input(second, observed_at=NOW), observed_at=NOW)
        second = finished()
        second["fixture"]["id"] = 99
        replies.append(second)
    with sqlite3.connect(path) as connection:
        connection.execute(f"UPDATE context_observations SET {index}=? WHERE event_key=? AND kind='base_fixture'",
            (value, "api-football:football:1575469"))
        connection.commit()
        before = tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in ("context_observations", "context_contents"))
    with pytest.raises(ContextIntegrityError):
        capture_results(path, monkeypatch, response=payload(replies))
    with sqlite3.connect(path) as connection:
        after = tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in ("context_observations", "context_contents"))
    assert after == before
