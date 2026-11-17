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
    kwargs.setdefault("football_quote_loader", lambda _rows: ({}, []))
    document = automation.run_wettfinder(
        now=NOW, state_path=artifact, config=AppConfig(api_football_key="test"),
        football_scanner=scanner, football_context_refresher=_refuse_context,
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
    # The row of tomorrow is really priced; without a quote the price clock is never written.
    _artifact, document = _run(tmp_path, _scanner([]), football_next_day=True,
                               football_quote_loader=_quotes_at([NOW], minutes=0))

    assert "decision_at" not in document
    next_rows = [row for row in document["model_candidates"] if row["fixture_id"] == 2]
    assert next_rows and all(row.get("reference_quote") for row in next_rows)
    assert all("reference_price_evaluated_at" not in row for row in next_rows)


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


def _quotes_at(clock, odd="2.05", minutes=1):
    """A quote loader that takes a minute and stamps its offers with the moving clock."""
    from market_consensus import parse_fixture_consensus

    def loader(rows):
        clock[0] += timedelta(minutes=minutes)
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


TODAY_GAMES = ((1, "2030-01-01T15:00:00+00:00"),)


def _moving_clock_run(tmp_path, monkeypatch, *, today=TODAY_GAMES, publish_minutes=0, tomorrow_fails=False,
                      **changes):
    """A run on a moving clock: 8 min for today, 10 min for tomorrow, 1 min per price check."""
    import forecast_evidence

    clock = [T0]
    monkeypatch.setattr(forecast_evidence, "_now", lambda: clock[0])
    writes, write_times = _write_log(monkeypatch, clock=clock)
    if publish_minutes:
        logged_write = automation.write_state

        def slow_first_write(document, path):
            result = logged_write(document, path)
            if len(writes) == 1:
                clock[0] += timedelta(minutes=publish_minutes)
            return result

        monkeypatch.setattr(automation, "write_state", slow_first_write)
    scans = []

    def scan(day):
        scans.append((day, clock[0]))
        if day == TODAY:
            clock[0] += timedelta(minutes=8)
            return _snapshot_at(clock[0], list(today))
        clock[0] += timedelta(minutes=10)
        if tomorrow_fails:
            raise RuntimeError("provider down")
        return _snapshot_at(clock[0], [(2, NIGHT_KICKOFF), (3, DAY_KICKOFF)])

    artifact = tmp_path / "wettfinder.json"
    evidence = tmp_path / "evidence.db"
    options = dict(football_quote_loader=_quotes_at(clock), football_next_day=True)
    options.update(changes)
    document = automation.run_wettfinder(
        clock=lambda: clock[0], state_path=artifact, config=AppConfig(api_football_key="test"),
        football_scanner=scan, football_context_refresher=_refuse_context,
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [], evidence_db_path=evidence,
        evidence_settlement_runner=lambda **_kwargs: {}, **options,
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


# --- Audit H5, cross-check 16.11.2026: running clock without rows, error paths, production path ---


def _later_quotes_run(clock, artifact, evidence):
    """A quotes run 45 minutes before the night kickoff on the stored document."""
    import forecast_evidence

    clock[0] = datetime.fromisoformat(NIGHT_KICKOFF) - timedelta(minutes=45)
    stored = json.loads(artifact.read_text(encoding="utf-8"))
    automation._refresh_price_document(
        stored, quote_sport="football", config=AppConfig(api_football_key="test"),
        now=clock[0] + timedelta(minutes=1), quote_loader=_quotes_at(clock, odd="1.95"))
    clock[0] += timedelta(minutes=1)
    return forecast_evidence.record_current_closing_quotes(
        stored, db_path=evidence, model_version=automation.CHALLENGE_PREDICTION_VERSION)


def test_todays_game_that_started_before_the_second_write_is_no_rejection(tmp_path, monkeypatch):
    # 03:50 Zurich: after the publication clock, before the decision clock of the second write.
    early = "2030-01-01T02:50:00+00:00"
    clock, _writes, _times, _scans, artifact, evidence, document = _moving_clock_run(
        tmp_path, monkeypatch, today=(*TODAY_GAMES, (4, early)))

    kickoff = datetime.fromisoformat(early)
    assert datetime.fromisoformat(document["generated_at"]) < kickoff <= datetime.fromisoformat(
        document["decision_at"])
    early_rows = [row for row in document["model_candidates"] if row["fixture_id"] == 4]
    assert early_rows and all(row.get("reference_quote") for row in early_rows)
    assert _evidence_fixtures(evidence) == {1, 2, 4}

    closing = _later_quotes_run(clock, artifact, evidence)

    # The started game cannot get a closing price; it must not look like a refused row either.
    assert closing["recorded"] > 0 and closing["rejected"] == 0


def test_search_for_tomorrow_is_stamped_after_a_slow_publication(tmp_path, monkeypatch):
    _clock, _writes, write_times, scans, _artifact, _evidence, document = _moving_clock_run(
        tmp_path, monkeypatch, publish_minutes=7)

    search_started = scans[1][1]
    assert scans[1][0] == TOMORROW and search_started == write_times[0] + timedelta(minutes=7)
    attempted = datetime.fromisoformat(document["football_next_day"]["last_attempt_at"])
    assert attempted >= search_started


@pytest.mark.parametrize("due", [True, False])
def test_running_clock_without_rows_for_tomorrow_has_no_decision_clock(tmp_path, monkeypatch, due):
    clock, writes, _times, _scans, artifact, _evidence, document = _moving_clock_run(
        tmp_path, monkeypatch, tomorrow_fails=True, football_next_day=due)

    assert len(writes) == (2 if due else 1)
    assert "decision_at" not in document
    assert {written["generated_at"] for written in writes} == {document["generated_at"]}
    assert document["sources"]["football"]["next_day"]["status"] == ("failed" if due else "not_needed")
    assert _load_automated_wettfinder_document(artifact, now=clock[0] + timedelta(minutes=1)) is not None


def test_tomorrow_without_a_price_check_still_gets_its_decision_clock(tmp_path, monkeypatch):
    # Without a quote loader nothing is priced: only the clock read after the search keeps the
    # decision clock behind tomorrow's model clocks, and with it the night-game evidence.
    clock, _writes, _times, _scans, artifact, evidence, document = _moving_clock_run(
        tmp_path, monkeypatch, football_quote_loader=None)

    next_rows = [row for row in document["model_candidates"] if row["fixture_id"] in {2, 3}]
    assert _fixture_ids(next_rows) == {2, 3}
    assert _load_automated_wettfinder_document(artifact, now=clock[0] + timedelta(minutes=1)) is not None
    decision = datetime.fromisoformat(document["decision_at"])
    assert all(decision >= datetime.fromisoformat(row[field])
               for row in next_rows for field in ("modeled_at", "input_cutoff_at", "context_checked_at"))
    night = document["forecast_evidence_night_games"]
    assert night["status"] == "completed" and night["recorded"] == 1 and night["rejected_count"] == 0
    assert _evidence_fixtures(evidence) == {1, 2}


PUBLICATION_STAGES = ("forecast_publication", "tip_receipts", "football_discovery_next_day",
                      "forecast_recording_night_games", "forecast_publication_next_day",
                      "football_appearances", "forecast_publication_final")


def _production_run(tmp_path, monkeypatch, *, scanner, clock=None, receipt_error=None, background_error=None,
                    receipts_missing=False, first_write_error=None, raises=None, **changes):
    """The private production path (``STATE_PATH``) with recorded stages, writes and receipts."""
    import copy
    from contextlib import nullcontext
    from types import SimpleNamespace

    import context_sources.football_appearances as appearances
    import forecast_evidence
    import tip_publication

    config = AppConfig(api_football_key="private-test-key")
    path = tmp_path / "prod.json"
    instant = (lambda: clock[0]) if clock else (lambda: NOW)
    run = SimpleNamespace(path=path, evidence=tmp_path / "evidence.db", stages=[], writes=[], write_times=[],
                          receipts=[], document=None, error=None)
    monkeypatch.setattr(automation, "TENNIS_DB", tmp_path / "tennis.db")
    monkeypatch.setattr(automation, "ESPORTS_DB", tmp_path / "esports.db")
    monkeypatch.setattr(automation, "load_app_config", lambda: config)
    monkeypatch.setattr(automation, "capture_football_worker", lambda *_args, **_kwargs: nullcontext())
    monkeypatch.setattr(automation, "ChallengeDataProvider", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(automation, "STATE_PATH", path)
    monkeypatch.setattr(forecast_evidence, "_now", instant)
    real_write, real_stage = automation.write_state, automation._logged_stage

    def logged(name, callback, *args, **kwargs):
        if name in PUBLICATION_STAGES:
            run.stages.append(name)
        return real_stage(name, callback, *args, **kwargs)

    def write(document, target):
        run.writes.append(copy.deepcopy(document))
        run.write_times.append(instant())
        if first_write_error is not None and len(run.writes) == 1:
            raise first_write_error
        return real_write(document, target)

    def receipt(target):
        on_disk = json.loads(target.read_text(encoding="utf-8"))
        run.receipts.append({
            "fixtures": _fixture_ids(on_disk["model_candidates"]),
            "reader_accepts": _load_automated_wettfinder_document(target, now=instant()) is not None,
        })
        if receipt_error is not None:
            raise receipt_error
        return {"status": "completed"}

    def background(_provider, *, now):
        if clock:
            clock[0] += timedelta(minutes=5)
        if background_error is not None:
            raise background_error
        return {"status": "completed", "requested_count": 0}

    monkeypatch.setattr(automation, "_logged_stage", logged)
    monkeypatch.setattr(automation, "write_state", write)
    if receipts_missing:
        monkeypatch.delattr(tip_publication, "record_automatic_publication")
    else:
        monkeypatch.setattr(tip_publication, "record_automatic_publication", receipt)
    monkeypatch.setattr(appearances, "refresh_football_appearances", background)
    options = dict(
        state_path=path, config=config, force_football=True, football_scanner=scanner,
        football_context_refresher=_refuse_context, football_quote_loader=lambda _rows: ({}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [],
        tennis_quote_loader=lambda _rows: ({}, []),
        tennis_model_refresher=lambda **_kwargs: {"status": "completed", "errors": []},
        riskobet_enabled=False, evidence_db_path=run.evidence,
        evidence_settlement_runner=lambda **_kwargs: {"status": "completed", "operational_error_count": 0},
        esports_settlement_runner=lambda *_args, **_kwargs: {"status": "completed", "checked": 0, "settled": 0},
    )
    options.update(changes)
    options.update({"clock": instant} if clock else {"now": NOW})
    if raises is None:
        run.document = automation.run_wettfinder(**options)
    else:
        with pytest.raises(raises) as caught:
            automation.run_wettfinder(**options)
        run.error = caught.value
    run.on_disk = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return run


class ReceiptsBroke(Exception):
    """An error the receipts do not catch themselves (they catch OS, database and value errors)."""


def _receipt_notes(captured):
    """The journal lines that name a held receipts error: (phase, error type)."""
    rows = [json.loads(line) for line in captured.err.splitlines() if line.startswith("{")]
    return [(row["phase"], row.get("error_type")) for row in rows
            if row.get("stage") == "tip_receipts" and row["phase"].startswith("failed_")], rows


@pytest.mark.parametrize("why", ["not_asked", "today_failed", "today_partial"])
def test_production_run_without_next_day_is_public_before_the_background_batch(tmp_path, monkeypatch, why):
    def scanner(day):
        assert day == TODAY, "no search for tomorrow expected"
        if why == "today_failed":
            raise RuntimeError("provider down")
        snapshot = _today_snapshot()
        if why == "today_partial":
            snapshot["errors"] = ["Stats Fixture 9: ReadTimeout"]
        return snapshot

    run = _production_run(tmp_path, monkeypatch, scanner=scanner,
                          **({"football_next_day": False} if why == "not_asked" else {}))

    assert tuple(run.stages) == ("forecast_publication", "tip_receipts", "football_appearances",
                                 "forecast_publication_final")
    assert len(run.writes) == 2 and len(run.receipts) == 1
    assert "football_context_history" not in run.writes[0]
    assert run.on_disk == json.loads(json.dumps(run.document))
    assert run.on_disk["football_context_history"] == {"status": "completed", "requested_count": 0}
    assert run.on_disk["sources"]["football"]["next_day"]["status"] == "not_needed"
    assert "decision_at" not in run.on_disk


def test_production_run_on_a_running_clock_keeps_all_three_files_readable(tmp_path, monkeypatch):
    clock = [T0]

    def scanner(day):
        if day == TODAY:
            clock[0] += timedelta(minutes=8)
            return _snapshot_at(clock[0], list(TODAY_GAMES))
        clock[0] += timedelta(minutes=10)
        return _snapshot_at(clock[0], [(2, NIGHT_KICKOFF), (3, DAY_KICKOFF)])

    run = _production_run(tmp_path, monkeypatch, scanner=scanner, clock=clock,
                          football_quote_loader=_quotes_at(clock))

    assert tuple(run.stages) == PUBLICATION_STAGES
    assert len(run.writes) == 3
    assert run.receipts == [{"fixtures": {1}, "reader_accepts": True}]
    # Rule 1: one publication clock for all three files, also after the background batch.
    assert {written["generated_at"] for written in run.writes} == {run.document["generated_at"]}
    listed_next = []
    for index, (written, written_at) in enumerate(zip(run.writes, run.write_times)):
        copy_path = tmp_path / f"write{index}.json"
        copy_path.write_text(json.dumps(written), encoding="utf-8")
        reader_now = written_at + timedelta(seconds=1)
        assert _load_automated_wettfinder_document(copy_path, now=reader_now) is not None
        forecasts = automated_wettfinder_forecasts(copy_path, now=reader_now)
        listed_next.append(len([signal for signal in forecasts if listed_next_day_signal(signal, now=reader_now)]))
    assert [_fixture_ids(written["model_candidates"]) for written in run.writes] == [{1}, {1, 2, 3}, {1, 2, 3}]
    assert listed_next == [0, 2, 2]
    assert ["football_context_history" in written for written in run.writes] == [False, False, True]
    assert "decision_at" not in run.writes[0]
    assert run.writes[1]["decision_at"] == run.writes[2]["decision_at"]
    night = run.document["forecast_evidence_night_games"]
    assert night["recorded"] == 1 and night["rejected_count"] == 0
    assert _evidence_fixtures(run.evidence) == {1, 2}
    assert run.document["run_status"] == "completed" and run.document["operational_error_count"] == 0
    assert run.on_disk == json.loads(json.dumps(run.document))


@pytest.mark.parametrize("due", [True, False])
def test_receipts_error_stays_loud_but_does_not_cost_tomorrow(tmp_path, monkeypatch, capsys, due):
    # The receipts catch their own provider and database errors. Anything else used to end the
    # run after its last write; it still does, and tomorrow and the background batch still happen.
    error = ReceiptsBroke("private text")
    run = _production_run(tmp_path, monkeypatch, scanner=_scanner([]), receipt_error=error,
                          raises=ReceiptsBroke, football_next_day=due)

    assert run.error is error
    # The journal names the step when the error is held and again right before it is raised:
    # the alarm quotes only the last lines. Type only, never the message.
    notes, rows = _receipt_notes(capsys.readouterr())
    assert notes == [("failed_held", "ReceiptsBroke"), ("failed_raised", "ReceiptsBroke")]
    assert rows[-1]["phase"] == "failed_raised" and "private text" not in json.dumps(rows)
    assert len(run.receipts) == 1
    assert run.stages[-2:] == ["football_appearances", "forecast_publication_final"]
    assert run.on_disk["football_context_history"] == {"status": "completed", "requested_count": 0}
    if due:
        assert len(run.writes) == 3
        assert _fixture_ids(run.on_disk["model_candidates"]) == {1, 2}
        assert run.on_disk["sources"]["football"]["next_day"]["status"] == "listed"
    else:
        assert len(run.writes) == 2
        assert _fixture_ids(run.on_disk["model_candidates"]) == {1}


def test_missing_receipts_function_is_held_like_any_other_error(tmp_path, monkeypatch, capsys):
    # The lazy import itself fails (a broken deploy): no stage line exists, the note still does.
    run = _production_run(tmp_path, monkeypatch, scanner=_scanner([]), receipts_missing=True,
                          raises=ImportError)

    assert len(run.writes) == 3 and "tip_receipts" not in run.stages
    assert run.on_disk["sources"]["football"]["next_day"]["status"] == "listed"
    notes, _rows = _receipt_notes(capsys.readouterr())
    assert notes == [("failed_held", "ImportError"), ("failed_raised", "ImportError")]


def test_receipts_error_is_raised_also_after_a_failed_background_batch(tmp_path, monkeypatch):
    error = ReceiptsBroke("receipts")
    run = _production_run(tmp_path, monkeypatch, scanner=_scanner([]), receipt_error=error,
                          background_error=RuntimeError("batch"), raises=ReceiptsBroke)

    assert run.error is error and len(run.writes) == 3
    assert run.on_disk["run_status"] == "degraded" and run.on_disk["operational_error_count"] == 1


@pytest.mark.parametrize("kill", [KeyboardInterrupt, SystemExit])
def test_kill_during_the_receipts_ends_the_run_at_once(tmp_path, monkeypatch, kill):
    # Only an ordinary error is carried to the end; a kill is never held back.
    run = _production_run(tmp_path, monkeypatch, scanner=_scanner([]), receipt_error=kill("kill"), raises=kill)

    assert run.stages == ["forecast_publication", "tip_receipts"] and len(run.writes) == 1
    assert _fixture_ids(run.on_disk["model_candidates"]) == {1}
    assert run.on_disk["sources"]["football"]["next_day"] == PENDING


def test_failed_first_write_ends_the_run_before_tomorrow(tmp_path, monkeypatch):
    # Only the receipts are guarded. A file that cannot be written stays an immediate failure:
    # nothing is searched for tomorrow on top of a day that is not public.
    scans = []
    error = OSError("disk")
    run = _production_run(tmp_path, monkeypatch, scanner=_scanner(scans), first_write_error=error,
                          raises=OSError)

    assert run.error is error
    assert scans == [TODAY] and run.stages == ["forecast_publication"]
    assert run.receipts == [] and run.on_disk is None


def test_failed_background_batch_degrades_only_the_last_file(tmp_path, monkeypatch):
    run = _production_run(tmp_path, monkeypatch, scanner=_scanner([]), background_error=RuntimeError("batch"))

    assert [written["run_status"] for written in run.writes] == ["completed", "completed", "degraded"]
    assert [written["operational_error_count"] for written in run.writes] == [0, 0, 1]
    assert run.on_disk == json.loads(json.dumps(run.document))
    assert run.on_disk["football_context_history"] == {"status": "failed", "failure_type": "RuntimeError"}
    assert _fixture_ids(run.on_disk["model_candidates"]) == {1, 2}
