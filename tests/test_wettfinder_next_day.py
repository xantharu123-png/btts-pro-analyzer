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
