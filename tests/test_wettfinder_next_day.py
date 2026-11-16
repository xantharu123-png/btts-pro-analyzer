"""Folgetag (owner 02.11.2026, always since 10.11.2026): the daily run also lists the next day.

The next day's games are model selections only. They never become a tip, a 15K row, a
Daily3 choice or an archived publication, and a failure there leaves today unchanged.
"""
import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

import wettfinder_automation as automation
from config_loader import AppConfig
import ev_signal_sources
from ev_signal_sources import (
    _load_automated_wettfinder_document,
    automated_next_day,
    automated_wettfinder_forecasts,
    automated_wettfinder_signals,
    listed_next_day_signal,
)
from tests.test_wettfinder_automation import _football_snapshot

UTC = timezone.utc
NOW = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
TODAY, TOMORROW = date(2030, 1, 1), date(2030, 1, 2)


def _today_snapshot(**changes) -> dict:
    # Below 65 % an unpriced tip stays visible under the 1.20 display floor
    # (as in test_run_without_any_bookmaker_quote_keeps_its_unpriced_tips).
    snapshot = _football_snapshot(NOW)
    original = snapshot["shortlist"][0]
    candidate = replace(original, probability=0.45, conservative_probability=0.38,
                        probability_haircut_pp=7.0, model_price=1.0 / 0.38, **changes)
    candidate.context = dict(original.context)
    snapshot.update(shortlist=[], wettfinder_candidates=[candidate], discovery_candidates=[candidate])
    return snapshot


def _next_day_snapshot() -> dict:
    snapshot = _today_snapshot(candidate_id="fixture-2-btts", fixture_id=2,
                               kickoff="2030-01-02T15:00:00+00:00")
    snapshot.update(context_fixture_statuses={"2": "verified"},
                    fixture_kickoffs=["2030-01-02T15:00:00+00:00"])
    return snapshot


def _refuse_context(*_args):
    raise AssertionError("no context refresh expected")


def _run(tmp_path, scanner, **kwargs):
    artifact = tmp_path / "wettfinder.json"
    document = automation.run_wettfinder(
        now=NOW, state_path=artifact, config=AppConfig(api_football_key="test"),
        football_scanner=scanner, football_context_refresher=_refuse_context,
        football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [], **kwargs,
    )
    return artifact, document


def _scanner(calls, *, fail_next_day=False):
    def scan(day):
        calls.append(day)
        if day == TOMORROW:
            if fail_next_day:
                raise RuntimeError("provider down for key=secret")
            return _next_day_snapshot()
        return _today_snapshot()
    return scan


def _fixture_ids(rows):
    return {row.get("fixture_id") for row in rows}


def test_next_day_has_no_game_threshold():
    # Owner 10.11.2026 "heute und morgen": no longer only below 30 football games.
    assert not hasattr(automation, "NEXT_DAY_MIN_GAMES")
    assert not hasattr(ev_signal_sources, "NEXT_DAY_MIN_GAMES")


def _full_day_snapshot(games=30) -> dict:
    snapshot = _today_snapshot()
    base = snapshot["wettfinder_candidates"][0]
    candidates = []
    for fixture_id in range(100, 100 + games):
        candidate = replace(base, candidate_id=f"fixture-{fixture_id}-btts", fixture_id=fixture_id)
        candidate.context = dict(base.context)
        candidates.append(candidate)
    snapshot.update(wettfinder_candidates=candidates, discovery_candidates=candidates,
                    context_fixture_statuses={str(c.fixture_id): "verified" for c in candidates},
                    base_fixture_count=games, context_fixtures=games, context_verified_fixtures=games)
    return snapshot


def test_small_match_day_lists_next_day_games_as_model_selections_only(tmp_path):
    calls = []
    artifact, document = _run(tmp_path, _scanner(calls), football_next_day=True)

    assert calls == [TODAY, TOMORROW]
    assert document["next_day_search_date"] == "2030-01-02"
    assert document["football_next_day"]["search_date"] == "2030-01-02"
    assert _fixture_ids(document["model_candidates"]) == {1, 2}
    assert 2 not in _fixture_ids(document["candidates"])
    assert 2 not in _fixture_ids(document["challenge_release_candidates"])
    summary = document["sources"]["football"]["next_day"]
    assert summary["status"] == "listed" and summary["today_games"] == 1 and summary["games"] == 1
    assert document["run_status"] == "completed"

    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    next_day = [signal for signal in forecasts if listed_next_day_signal(signal, now=NOW)]
    assert [signal.key for signal in next_day] == [
        row["key"] for row in document["model_candidates"] if row["fixture_id"] == 2]
    assert all(not listed_next_day_signal(signal, now=NOW)
               for signal in automated_wettfinder_signals(artifact, now=NOW))


def test_full_match_day_also_lists_the_next_day(tmp_path):
    calls = []

    def scan(day):
        calls.append(day)
        return _next_day_snapshot() if day == TOMORROW else _full_day_snapshot()

    _artifact, document = _run(tmp_path, scan, football_next_day=True)
    summary = document["sources"]["football"]["next_day"]
    assert summary["today_games"] >= 30
    assert calls == [TODAY, TOMORROW]
    assert summary["status"] == "listed" and document["next_day_search_date"] == "2030-01-02"
    assert 2 in _fixture_ids(document["model_candidates"]) and 2 not in _fixture_ids(document["candidates"])


def test_isolated_runs_keep_the_single_day_unless_asked(tmp_path):
    calls = []
    _artifact, document = _run(tmp_path, _scanner(calls))

    assert calls == [TODAY]
    assert "next_day_search_date" not in document


def test_next_day_failure_leaves_today_unchanged(tmp_path):
    reference_calls = []
    _reference_artifact, reference = _run(tmp_path / "a", _scanner(reference_calls))
    calls = []
    _artifact, document = _run(tmp_path / "b", _scanner(calls, fail_next_day=True), football_next_day=True)

    assert calls == [TODAY, TOMORROW]
    assert document["run_status"] == "completed" and document["football"]["status"] == "completed"
    assert document["model_candidates"] == reference["model_candidates"]
    assert document["candidates"] == reference["candidates"]
    summary = document["sources"]["football"]["next_day"]
    assert summary == {"search_date": "2030-01-02", "status": "failed", "failure_type": "RuntimeError",
                       "today_games": 1, "candidate_count": 0, "games": 0, "price_checked_count": 0,
                       "price_status_counts": summary["price_status_counts"],
                       "quote_operational_error_count": 0}
    assert "secret" not in json.dumps(document)


def test_partial_next_day_scan_still_lists_complete_fixtures(tmp_path):
    # 05.11.2026: one ReadTimeout among 539 calls dropped the whole next day. Like the match
    # day, a partial scan keeps fixtures whose own model and context record are complete.
    def scan(day):
        if day == TOMORROW:
            snapshot = _next_day_snapshot()
            snapshot["errors"] = ["Stats Fixture 9: ReadTimeout"]
            return snapshot
        return _today_snapshot()

    artifact, document = _run(tmp_path, scan, football_next_day=True)

    summary = document["sources"]["football"]["next_day"]
    assert summary["status"] == "listed_partial" and summary["partial_operational_errors"] == 1
    assert document["next_day_search_date"] == "2030-01-02"
    assert document["football_next_day"]["status"] == "degraded"
    assert 2 in _fixture_ids(document["model_candidates"])
    assert document["run_status"] == "completed" and document["football"]["status"] == "completed"
    assert any(listed_next_day_signal(s, now=NOW) for s in automated_wettfinder_forecasts(artifact, now=NOW))


def test_next_day_without_context_accounting_is_still_dropped(tmp_path):
    def scan(day):
        if day == TOMORROW:
            snapshot = _next_day_snapshot()
            snapshot.pop("context_fixture_statuses")
            return snapshot
        return _today_snapshot()

    _artifact, document = _run(tmp_path, scan, football_next_day=True)
    assert document["sources"]["football"]["next_day"]["status"] in {"degraded", "failed"}
    assert "next_day_search_date" not in document and 2 not in _fixture_ids(document["model_candidates"])


@pytest.fixture
def listed(tmp_path):
    artifact, _document = _run(tmp_path, _scanner([]), football_next_day=True)
    return artifact, json.loads(artifact.read_text(encoding="utf-8"))


def _rewrite(artifact, document):
    artifact.write_text(json.dumps(document), encoding="utf-8")
    return _load_automated_wettfinder_document(artifact, now=NOW)


def test_loader_rejects_next_day_rows_without_a_valid_marker(listed):
    artifact, document = listed
    assert _rewrite(artifact, document) is not None

    assert _rewrite(artifact, {**document, "next_day_search_date": "2030-01-03"}) is None
    unmarked = dict(document)
    unmarked.pop("next_day_search_date")
    assert _rewrite(artifact, unmarked) is None
    assert _rewrite(artifact, {**document, "football_next_day": {
        **document["football_next_day"], "search_date": "2030-01-01"}}) is None


def test_loader_never_accepts_a_next_day_tip_or_15k_row(listed):
    artifact, document = listed
    next_row = next(row for row in document["model_candidates"] if row["fixture_id"] == 2)
    tip = {**next_row, "status": "RECOMMENDED"}
    assert _rewrite(artifact, {**document, "candidates": [*document["candidates"], tip]}) is None
    assert _rewrite(artifact, {**document, "challenge_release_candidates": [tip]}) is None


def test_next_day_rows_need_their_own_verified_context(listed):
    artifact, document = listed
    state = dict(document["football_next_day"])
    state["context_fixture_statuses"] = {"2": "unchecked"}
    state["context_verified_fixtures"] = 0
    state["context_unchecked_fixtures"] = 1
    _rewrite(artifact, {**document, "football_next_day": state})

    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    assert forecasts and not any(listed_next_day_signal(signal, now=NOW) for signal in forecasts)


def test_marker_helper_requires_the_following_day():
    state = {"search_date": "2030-01-02"}
    assert automated_next_day({"next_day_search_date": "2030-01-02", "football_next_day": state}, TODAY) == TOMORROW
    assert automated_next_day({"next_day_search_date": "2030-01-02", "football_next_day": state}, TOMORROW) is None
    assert automated_next_day({"next_day_search_date": "2030-01-02"}, TODAY) is None


def test_quotes_run_also_prices_listed_next_day_rows(listed, monkeypatch):
    _artifact, document = listed
    seen = []

    def loader(rows):
        seen.extend(row["fixture_id"] for row in rows)
        return {}, []

    monkeypatch.setattr(automation, "_persist_quote_diagnostics", lambda *args, **kwargs: None)
    automation._refresh_price_document(document, quote_sport="football", config=AppConfig(api_football_key="x"),
                                       now=NOW + timedelta(minutes=5), quote_loader=loader)
    assert {1, 2} <= set(seen)


@pytest.mark.price_policy("floor")  # unpriced rows below 65 % stay in the default inventory
def test_tip_archive_skips_listed_next_day_games(listed, monkeypatch):
    import tip_publication

    artifact, _document = listed
    archived = {}

    def record(surface, signals, **_kwargs):
        archived[surface] = [signal.key for signal in signals]
        return {"status": "recorded"}

    monkeypatch.setattr(tip_publication, "record_signal_catalog", record)
    assert tip_publication.record_automatic_publication(artifact, as_of=NOW)["status"] == "completed"
    assert archived["wettfinder_default_inventory"] == ["wettfinder-football-fixture-1-btts"]


def test_tennis_box_keeps_the_match_day_label():
    # 3.11.2026: the header reads "Heute und morgen", the tennis box listed only today's matches.
    import inspect

    import app

    source = inspect.getsource(app._render_automated_daily_selection)
    assert source.index("rail_label = target_label") < source.index("target_label += ' und morgen'")
    assert "time_parts = [target_label]" in source and "target_label=rail_label" in source


# Owner 13.11.2026 ("alles erledigen"): a football game that starts in the night after the
# match day (before 04:30 Zurich) was never settled. The match-day run records forecasts at
# about 03:45-04:10, after its kickoff, and a next-day row was never evidence. Since then the
# run before records such night games as evidence only; they stay a next-day preview.
NIGHT_KICKOFF = "2030-01-02T01:30:00+00:00"  # 02:30 Zurich
DAY_KICKOFF = "2030-01-02T15:00:00+00:00"


def _night_and_day_snapshot() -> dict:
    night = _today_snapshot(candidate_id="fixture-2-btts", fixture_id=2,
                            kickoff=NIGHT_KICKOFF)["wettfinder_candidates"][0]
    day = _today_snapshot(candidate_id="fixture-3-btts", fixture_id=3,
                          kickoff=DAY_KICKOFF)["wettfinder_candidates"][0]
    snapshot = _today_snapshot()
    snapshot.update(wettfinder_candidates=[night, day], discovery_candidates=[night, day],
                    context_fixture_statuses={"2": "verified", "3": "verified"},
                    fixture_kickoffs=[NIGHT_KICKOFF, DAY_KICKOFF],
                    base_fixture_count=2, context_fixtures=2, context_verified_fixtures=2)
    return snapshot


def _evidence_fixtures(path):
    import sqlite3

    with sqlite3.connect(path) as connection:
        return {row[0] for row in connection.execute(
            "SELECT json_extract(payload_json, '$.quote_identity.fixture_id') FROM forecast_rows")}


def test_night_game_of_the_next_day_is_recorded_as_evidence_only(tmp_path, monkeypatch):
    import forecast_evidence

    monkeypatch.setattr(forecast_evidence, "_now", lambda: NOW)
    evidence = tmp_path / "evidence.db"

    def scan(day):
        return _night_and_day_snapshot() if day == TOMORROW else _today_snapshot()

    artifact, document = _run(tmp_path, scan, football_next_day=True, evidence_db_path=evidence,
                              evidence_settlement_runner=lambda **_kwargs: {})

    assert _evidence_fixtures(evidence) == {1, 2}
    night_rows = [row for row in document["model_candidates"] if row["fixture_id"] == 2]
    assert night_rows and 3 in _fixture_ids(document["model_candidates"])
    summary = document["forecast_evidence_night_games"]
    assert summary["status"] == "completed" and summary["recorded"] == len(night_rows)
    assert summary["kickoff_before"] == "2030-01-02T04:30:00+01:00"
    assert document["forecast_evidence"]["recorded"] == len(
        [row for row in document["model_candidates"] if row["fixture_id"] == 1])
    # Still only a next-day preview: no tip, no 15K row, no archive entry.
    assert 2 not in _fixture_ids(document["candidates"])
    assert 2 not in _fixture_ids(document["challenge_release_candidates"])
    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    assert {s.key for s in forecasts if listed_next_day_signal(s, now=NOW)} == {
        row["key"] for row in document["model_candidates"] if row["fixture_id"] in {2, 3}}
    assert document["run_status"] == "completed"


def test_night_games_are_not_recorded_without_an_evidence_store(tmp_path):
    def scan(day):
        return _night_and_day_snapshot() if day == TOMORROW else _today_snapshot()

    _artifact, document = _run(tmp_path, scan, football_next_day=True)
    assert "forecast_evidence_night_games" not in document


@pytest.mark.parametrize("kickoff,kept", [
    ("2030-01-01T23:00:00+00:00", True),    # 00:00 Zurich on the next day
    ("2030-01-02T03:29:59+00:00", True),    # 04:29:59 Zurich
    ("2030-01-02T03:30:00+00:00", False),   # 04:30 Zurich: the match-day run records it
    ("2030-01-02T15:00:00+00:00", False),
    ("2030-01-01T22:59:59+00:00", False),   # still the match day
    ("2030-01-02T23:30:00+00:00", False),   # 00:30 two days later
])
def test_night_game_window_uses_the_zurich_clock_of_the_next_day(kickoff, kept):
    row = {"sport": "Fußball", "fixture_id": 2, "scheduled_start": kickoff}
    assert automation._night_game_rows([row], TOMORROW) == ([row] if kept else [])


def test_night_game_window_follows_summer_time():
    summer = date(2030, 7, 2)
    early = {"sport": "Fußball", "scheduled_start": "2030-07-02T02:29:00+00:00"}  # 04:29 CEST
    late = {"sport": "Fußball", "scheduled_start": "2030-07-02T02:30:00+00:00"}   # 04:30 CEST
    assert automation._night_game_rows([early, late], summer) == [early]


def test_night_game_window_takes_football_only():
    hockey = {"sport": "Eishockey", "scheduled_start": "2030-01-02T01:30:00+00:00"}
    unknown = {"sport": "Fußball", "scheduled_start": "nicht lesbar"}
    assert automation._night_game_rows([hockey, unknown], TOMORROW) == []


# Audit H5 (16.11.2026): today is published first. The search for tomorrow, its price
# check and the night-game evidence follow, then a second write adds tomorrow. A run that
# dies in the work for tomorrow leaves today's document public and complete.
T0 = datetime(2030, 1, 1, 2, 35, tzinfo=UTC)  # 03:35 Zurich, the nightly timer
PENDING = {"search_date": "2030-01-02", "status": "pending", "today_games": 1}


def _write_log(monkeypatch, events=None, clock=None):
    """Record every publication as a deep copy; optionally its place among the scans and its time."""
    import copy

    writes, times = [], []
    real_write = automation.write_state

    def recording_write(document, path):
        writes.append(copy.deepcopy(document))
        if events is not None:
            events.append("write")
        if clock is not None:
            times.append(clock[0])
        return real_write(document, path)

    monkeypatch.setattr(automation, "write_state", recording_write)
    return writes, times


def _without_run_id(document):
    document = json.loads(json.dumps(document))
    document.get("forecast_evidence", {}).pop("run_id", None)
    return document


def _reference_run(tmp_path, monkeypatch):
    """The same match day without a next day: what must be public when tomorrow fails."""
    import forecast_evidence

    monkeypatch.setattr(forecast_evidence, "_now", lambda: NOW)
    _artifact, reference = _run(tmp_path / "reference", lambda _day: _today_snapshot(),
                                evidence_db_path=tmp_path / "reference.db",
                                evidence_settlement_runner=lambda **_kwargs: {})
    return reference


def _assert_today_alone_is_public(artifact, reference, evidence):
    """The file is the run without a next day, apart from the ``pending`` marker."""
    on_disk = _without_run_id(json.loads(artifact.read_text(encoding="utf-8")))
    expected = _without_run_id(reference)
    assert on_disk["sources"]["football"].pop("next_day") == PENDING
    assert expected["sources"]["football"].pop("next_day")["status"] == "not_needed"
    assert on_disk == expected
    assert "next_day_search_date" not in on_disk and "football_next_day" not in on_disk
    assert "decision_at" not in on_disk
    assert _fixture_ids(on_disk["model_candidates"]) == {1}
    assert _load_automated_wettfinder_document(artifact, now=NOW) is not None
    assert automated_wettfinder_forecasts(artifact, now=NOW)
    assert _evidence_fixtures(evidence) == {1}


@pytest.mark.parametrize("death", [KeyboardInterrupt, SystemExit])
def test_death_in_the_next_day_search_leaves_today_published(tmp_path, monkeypatch, death):
    reference = _reference_run(tmp_path, monkeypatch)

    def scan(day):
        if day == TOMORROW:
            raise death("stand-in for the 60-minute kill")
        return _today_snapshot()

    evidence = tmp_path / "dead.db"
    with pytest.raises(death):
        _run(tmp_path / "dead", scan, football_next_day=True, evidence_db_path=evidence,
             evidence_settlement_runner=lambda **_kwargs: {})

    _assert_today_alone_is_public(tmp_path / "dead" / "wettfinder.json", reference, evidence)


def test_death_in_the_next_day_price_check_leaves_today_published(tmp_path, monkeypatch):
    reference = _reference_run(tmp_path, monkeypatch)
    artifact = tmp_path / "dead" / "wettfinder.json"
    evidence = tmp_path / "dead.db"

    def quotes(rows):
        if any(row["fixture_id"] == 2 for row in rows):
            raise KeyboardInterrupt("stand-in for the 60-minute kill")
        return {}, []

    with pytest.raises(KeyboardInterrupt):
        automation.run_wettfinder(
            now=NOW, state_path=artifact, config=AppConfig(api_football_key="test"),
            football_scanner=_scanner([]), football_context_refresher=_refuse_context,
            football_quote_loader=quotes, tennis_loader=lambda **_kwargs: [],
            esports_loader=lambda **_kwargs: [], football_next_day=True,
            evidence_db_path=evidence, evidence_settlement_runner=lambda **_kwargs: {},
        )

    _assert_today_alone_is_public(artifact, reference, evidence)


def test_unexpected_error_in_the_work_for_tomorrow_keeps_today_public(tmp_path, monkeypatch):
    reference = _reference_run(tmp_path, monkeypatch)
    real_ledger = automation.build_model_selection_ledger

    def ledger(*args, **kwargs):
        if kwargs.get("target_date") == TOMORROW:
            raise ZeroDivisionError("a programming error stays loud")
        return real_ledger(*args, **kwargs)

    monkeypatch.setattr(automation, "build_model_selection_ledger", ledger)
    evidence = tmp_path / "bug.db"
    with pytest.raises(ZeroDivisionError):
        _run(tmp_path / "bug", _scanner([]), football_next_day=True, evidence_db_path=evidence,
             evidence_settlement_runner=lambda **_kwargs: {})

    _assert_today_alone_is_public(tmp_path / "bug" / "wettfinder.json", reference, evidence)


def test_next_day_is_searched_only_after_todays_publication(tmp_path, monkeypatch):
    events = []
    writes, _times = _write_log(monkeypatch, events)

    def scan(day):
        events.append(day)
        return _next_day_snapshot() if day == TOMORROW else _today_snapshot()

    artifact, document = _run(tmp_path, scan, football_next_day=True)

    assert events == [TODAY, "write", TOMORROW, "write"]
    first, second = writes
    assert _fixture_ids(first["model_candidates"]) == {1}
    assert first["sources"]["football"]["next_day"] == PENDING
    assert "next_day_search_date" not in first and "football_next_day" not in first
    assert second == document
    assert json.loads(artifact.read_text(encoding="utf-8")) == json.loads(json.dumps(document))
    assert _fixture_ids(second["model_candidates"]) == {1, 2}
    assert second["sources"]["football"]["next_day"]["status"] == "listed"
    # Today's part of the second publication is the first publication.
    today_only = json.loads(json.dumps(second))
    today_only["model_candidates"] = [row for row in today_only["model_candidates"] if row["fixture_id"] == 1]
    today_only["price_check_attempts"] = {
        key: value for key, value in today_only["price_check_attempts"].items()
        if key in first["price_check_attempts"]}
    for key in ("football_next_day", "next_day_search_date"):
        del today_only[key]
    today_only["sources"]["football"]["next_day"] = PENDING
    assert today_only == json.loads(json.dumps(first))


def test_run_without_next_day_writes_once(tmp_path, monkeypatch):
    writes, _times = _write_log(monkeypatch)
    calls = []

    _artifact, document = _run(tmp_path, _scanner(calls))

    assert calls == [TODAY] and len(writes) == 1 and writes[0] == document
    assert document["sources"]["football"]["next_day"] == {
        "status": "not_needed", "today_games": 1, "candidate_count": 0, "games": 0,
        "price_checked_count": 0, "price_status_counts": {}, "quote_operational_error_count": 0}
    assert "decision_at" not in document


def test_failed_next_day_search_still_gets_its_second_publication(tmp_path, monkeypatch):
    writes, _times = _write_log(monkeypatch)

    artifact, document = _run(tmp_path, _scanner([], fail_next_day=True), football_next_day=True)

    assert len(writes) == 2
    assert writes[0]["sources"]["football"]["next_day"] == PENDING
    assert document["sources"]["football"]["next_day"]["status"] == "failed"
    assert json.loads(artifact.read_text(encoding="utf-8")) == json.loads(json.dumps(document))
    assert _fixture_ids(document["model_candidates"]) == {1} and "decision_at" not in document


def test_fixed_clock_documents_are_unchanged(tmp_path):
    # With ``now=`` the clock never passes ``generated_at``: no second decision clock and
    # no own price clock, so every stored fixed-clock expectation keeps its exact shape.
    _artifact, document = _run(tmp_path, _scanner([]), football_next_day=True)

    assert "decision_at" not in document
    next_rows = [row for row in document["model_candidates"] if row["fixture_id"] == 2]
    assert next_rows and all("reference_price_evaluated_at" not in row for row in next_rows)


def _snapshot_at(scanned_at, fixtures) -> dict:
    snapshot = _football_snapshot(scanned_at)
    original = snapshot["shortlist"][0]
    candidates = []
    for fixture_id, kickoff in fixtures:
        candidate = replace(original, probability=0.45, conservative_probability=0.38,
                            probability_haircut_pp=7.0, model_price=1.0 / 0.38,
                            candidate_id=f"fixture-{fixture_id}-btts", fixture_id=fixture_id, kickoff=kickoff)
        candidate.context = dict(original.context)
        candidates.append(candidate)
    snapshot.update(shortlist=[], wettfinder_candidates=candidates, discovery_candidates=candidates,
                    context_fixture_statuses={str(fixture_id): "verified" for fixture_id, _ in fixtures},
                    fixture_kickoffs=[kickoff for _, kickoff in fixtures], base_fixture_count=len(fixtures),
                    context_fixtures=len(fixtures), context_verified_fixtures=len(fixtures))
    return snapshot


def _quotes_at(clock, odd="2.05"):
    """A quote loader that takes a minute and stamps its offers with the moving clock."""
    from market_consensus import parse_fixture_consensus

    def loader(rows):
        clock[0] += timedelta(minutes=1)
        fetched = clock[0]
        result = {}
        for fixture_id in sorted({row["fixture_id"] for row in rows}):
            fixture_rows = [row for row in rows if row["fixture_id"] == fixture_id]
            payload = {"response": [{
                "fixture": {"id": fixture_id, "date": fixture_rows[0]["scheduled_start"]},
                "update": fetched.isoformat(),
                "bookmakers": [{"id": book, "name": f"Book {book}", "bets": [{
                    "name": "Both Teams Score", "values": [{"value": "Yes", "odd": odd}]}]}
                    for book in range(1, 5)],
            }]}
            result.update(parse_fixture_consensus(payload, fixture_rows, fetched_at=fetched))
        return result, []
    return loader


def _moving_clock_run(tmp_path, monkeypatch):
    """A run on a moving clock: 8 min for today, 10 min for tomorrow, 1 min per price check."""
    import forecast_evidence

    clock = [T0]
    monkeypatch.setattr(forecast_evidence, "_now", lambda: clock[0])
    writes, write_times = _write_log(monkeypatch, clock=clock)
    scans = []

    def scan(day):
        scans.append((day, clock[0]))
        if day == TODAY:
            clock[0] += timedelta(minutes=8)
            return _snapshot_at(clock[0], [(1, "2030-01-01T15:00:00+00:00")])
        clock[0] += timedelta(minutes=10)
        return _snapshot_at(clock[0], [(2, NIGHT_KICKOFF), (3, DAY_KICKOFF)])

    artifact = tmp_path / "wettfinder.json"
    evidence = tmp_path / "evidence.db"
    document = automation.run_wettfinder(
        clock=lambda: clock[0], state_path=artifact, config=AppConfig(api_football_key="test"),
        football_scanner=scan, football_context_refresher=_refuse_context,
        football_quote_loader=_quotes_at(clock), tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [], football_next_day=True, evidence_db_path=evidence,
        evidence_settlement_runner=lambda **_kwargs: {},
    )
    return clock, writes, write_times, scans, artifact, evidence, document


def test_tomorrow_after_publication_survives_reader_and_evidence(tmp_path, monkeypatch):
    clock, writes, write_times, scans, artifact, evidence, document = _moving_clock_run(tmp_path, monkeypatch)

    first, second = writes
    assert second == document and first["generated_at"] == second["generated_at"]
    # Tomorrow was searched only after today's file was written.
    assert scans[1][0] == TOMORROW and scans[1][1] >= write_times[0]
    generated = datetime.fromisoformat(document["generated_at"])
    next_rows = [row for row in document["model_candidates"] if row["fixture_id"] in {2, 3}]
    assert _fixture_ids(next_rows) == {2, 3}
    # Tomorrow's rows were modelled and priced after the publication clock ...
    assert all(datetime.fromisoformat(row["modeled_at"]) > generated for row in next_rows)
    priced_at = {row["reference_price_evaluated_at"] for row in next_rows}
    assert len(priced_at) == 1 and datetime.fromisoformat(min(priced_at)) > generated
    assert all(document["price_check_attempts"][row["key"]] == row["reference_price_evaluated_at"]
               for row in next_rows)
    # ... so the document carries a later decision clock for them. Today's file had none.
    assert "decision_at" not in first
    decision = datetime.fromisoformat(document["decision_at"])
    assert all(decision >= datetime.fromisoformat(row[field])
               for row in next_rows for field in ("modeled_at", "input_cutoff_at", "context_checked_at"))

    # The reader accepts both publications and reproduces every stored price status.
    reader_now = clock[0] + timedelta(minutes=1)
    assert _load_automated_wettfinder_document(artifact, now=reader_now) is not None
    forecasts = automated_wettfinder_forecasts(artifact, now=reader_now)
    listed = {signal.key for signal in forecasts if listed_next_day_signal(signal, now=reader_now)}
    assert listed == {row["key"] for row in next_rows}
    first_file = tmp_path / "first.json"
    first_file.write_text(json.dumps(first), encoding="utf-8")
    assert _load_automated_wettfinder_document(first_file, now=write_times[0]) is not None

    # The night game is evidence with its entry quote; tomorrow's day game is not.
    night = document["forecast_evidence_night_games"]
    assert night["status"] == "completed" and night["recorded"] == 1
    assert night["rejected_count"] == 0 and night["quote_rejected_count"] == 0
    assert _evidence_fixtures(evidence) == {1, 2}
    assert document["run_status"] == "completed"


def test_night_game_keeps_its_closing_quote_in_a_later_quotes_run(tmp_path, monkeypatch):
    import forecast_evidence

    clock, _writes, _times, _scans, artifact, evidence, _document = _moving_clock_run(tmp_path, monkeypatch)

    # A quotes run 45 minutes before the night kickoff reads the stored document.
    clock[0] = datetime.fromisoformat(NIGHT_KICKOFF) - timedelta(minutes=45)
    stored = json.loads(artifact.read_text(encoding="utf-8"))
    summary = automation._refresh_price_document(
        stored, quote_sport="football", config=AppConfig(api_football_key="test"),
        now=clock[0] + timedelta(minutes=1), quote_loader=_quotes_at(clock, odd="1.95"))
    clock[0] += timedelta(minutes=1)
    closing = forecast_evidence.record_current_closing_quotes(
        stored, db_path=evidence, model_version=automation.CHALLENGE_PREDICTION_VERSION)

    assert summary["quotes"] > 0
    assert closing["recorded"] > 0 and closing["rejected"] == 0
