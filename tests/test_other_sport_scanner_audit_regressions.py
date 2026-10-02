"""Offline regressions for the B1/H1/E1 scanner audit, never production scans."""
from contextlib import closing
from copy import deepcopy
from datetime import date, datetime, timedelta
import sqlite3
from types import SimpleNamespace

import pytest

import multi_sport_recommendations as recommendations
from esports_shadow import EsportsShadowLog
from scanners import completed_history as history
from scanners.basketball_scanner import BasketballScanner
from test_completed_sports_history import (
    NOW, cricket_payload, euro_payload, nba_payload, nhl_payload,
)
from test_multi_sport_recommendations import _esports_match


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), (None, None), ("true", None), (1, None)])
def test_nba_upcoming_preserves_only_native_boolean_neutral_site(value, expected):
    payload = nba_payload()
    event = payload["events"][0]
    game = event["competitions"][0]
    game["status"]["type"] = {"state": "pre", "completed": False}
    game["neutralSite"] = value
    scanner = BasketballScanner.__new__(BasketballScanner)
    parsed = scanner._parse_espn_upcoming_basketball_game(event, game, "NBA")
    assert parsed is not None
    assert parsed.get("neutral_site") is expected


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), (None, None), ("true", None), (1, None)])
def test_euroleague_upcoming_preserves_native_neutral_site(monkeypatch, value, expected):
    payload = euro_payload()
    payload["data"][0].update(played=False, isNeutralVenue=value)
    scanner = BasketballScanner.__new__(BasketballScanner)
    scanner.euroleague_games_base = "https://example.test/euroleague"
    scanner.errors = {}
    response = SimpleNamespace(status_code=200, json=lambda: payload)
    monkeypatch.setattr("scanners.basketball_scanner.requests.get", lambda *a, **kw: response)
    monkeypatch.setattr("scanners.basketball_scanner.observe_euroleague_schedule", lambda *a, **kw: None)
    rows = scanner._get_upcoming_euroleague_games(date(2026, 5, 24), date(2026, 5, 24))
    assert len(rows) == 1
    assert rows[0].get("neutral_site") is expected


def cricketdata_payload():
    return {"status": "success", "data": [{
        "id": "uuid-1", "matchEnded": True, "dateTimeGMT": "2026-09-01T10:00:00",
        "teams": ["Alpha", "Beta"], "matchType": "odi", "name": "ODI",
        "status": "Beta won by 2 wickets",
    }]}


def _native_case(provider):
    if provider == "ESPN":
        payload = nba_payload()
        native = payload["events"][0]["competitions"][0]
        retract = lambda: native["status"].update(type={"state": "pre", "completed": False})
        return payload, native, history.parse_espn_results, retract
    if provider == "EuroLeague":
        payload = euro_payload()
        native = payload["data"][0]
        return payload, native, history.parse_euroleague_results, lambda: native.update(played=False)
    if provider == "NHL":
        payload = nhl_payload()
        native = payload["gameWeek"][0]["games"][0]
        return payload, native, history.parse_nhl_results, lambda: native.update(gameState="FUT")
    if provider == "Cricbuzz":
        payload = cricket_payload()
        native = payload["typeMatches"][0]["seriesMatches"][0]["seriesAdWrapper"]["matches"][0]["matchInfo"]
        return payload, native, history.parse_cricbuzz_results, lambda: native.update(state="In Progress")
    payload = cricketdata_payload()
    native = payload["data"][0]
    return payload, native, history.parse_cricketdata_results, lambda: native.update(matchEnded=False)


PROVIDERS = ["ESPN", "EuroLeague", "NHL", "Cricbuzz", "CricketData"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_explicit_native_final_retraction_invalidates_current_not_historical_view(tmp_path, monkeypatch, provider):
    clock = [NOW]
    cache = history.CompletedHistoryStore(tmp_path / "history.db", clock=lambda: clock[0])
    payload, native, parser, retract = _native_case(provider)
    final = deepcopy(payload)
    reply = [payload]
    monkeypatch.setattr(history.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: reply[0]))
    monkeypatch.setattr(history, "observe_completed_team_sports_response", lambda *a, **kw: None)
    start = date(2026, 1, 1)
    history.fetch_page(cache, provider, "final", "https://example.test/history", parser)
    assert len(cache.read([provider], start, NOW.date())) == 1
    retract()
    # A corrected future kickoff must not prevent retraction of the old final.
    if provider == "NHL":
        native["startTimeUTC"] = (NOW + timedelta(days=1)).isoformat()
    clock[0] += timedelta(hours=1)
    history.fetch_page(cache, provider, "correction", "https://example.test/history", parser)
    assert cache.read([provider], start, NOW.date()) == []
    assert len(cache.read([provider], start, NOW.date(), as_of=NOW)) == 1
    with closing(sqlite3.connect(cache.path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM history_result_revisions").fetchone()[0] == 2
    # Repeated withdrawal does not manufacture another revision.
    clock[0] += timedelta(hours=1)
    history.fetch_page(cache, provider, "repeat", "https://example.test/history", parser)
    with closing(sqlite3.connect(cache.path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM history_result_revisions").fetchone()[0] == 2
    reply[0] = final
    clock[0] += timedelta(hours=1)
    history.fetch_page(cache, provider, "reinstated", "https://example.test/history", parser)
    assert len(cache.read([provider], start, NOW.date())) == 1
    assert cache.read([provider], start, NOW.date(), as_of=NOW + timedelta(hours=1)) == []


@pytest.mark.parametrize("provider", PROVIDERS)
def test_absent_event_or_unavailable_native_status_does_not_retract_final(tmp_path, monkeypatch, provider):
    clock = [NOW]
    cache = history.CompletedHistoryStore(tmp_path / "history.db", clock=lambda: clock[0])
    payload, native, parser, _retract = _native_case(provider)
    original = parser(payload)[0]
    cache.record(provider, "final", [original])
    status_field = {"ESPN": "status", "EuroLeague": "played", "NHL": "gameState", "Cricbuzz": "state", "CricketData": "matchEnded"}[provider]
    native.pop(status_field)
    monkeypatch.setattr(history.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: payload))
    monkeypatch.setattr(history, "observe_completed_team_sports_response", lambda *a, **kw: None)
    clock[0] += timedelta(hours=1)
    history.fetch_page(cache, provider, "missing-status", "https://example.test/history", parser)
    cache.record(provider, "other-page", [])
    assert len(cache.read([provider], date(2026, 1, 1), NOW.date())) == 1


def test_one_page_conflicting_final_and_retraction_cannot_resurrect_old_result(tmp_path, monkeypatch):
    clock = [NOW]
    cache = history.CompletedHistoryStore(tmp_path / "history.db", clock=lambda: clock[0])
    final = nba_payload()
    cache.record("ESPN", "final", history.parse_espn_results(final))
    retracted = deepcopy(final["events"][0])
    retracted["competitions"][0]["status"]["type"] = {"completed": False, "state": "pre"}
    final["events"].append(retracted)
    clock[0] += timedelta(hours=1)
    monkeypatch.setattr(history.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: final))
    monkeypatch.setattr(history, "observe_completed_team_sports_response", lambda *a, **kw: None)
    history.fetch_page(cache, "ESPN", "correction", "https://example.test/history", history.parse_espn_results)
    assert cache.read(["ESPN"], date(2026, 1, 1), NOW.date()) == []


def test_transport_failure_cannot_retract_previous_final(tmp_path, monkeypatch):
    cache = history.CompletedHistoryStore(tmp_path / "history.db", clock=lambda: NOW)
    cache.record("NHL", "final", history.parse_nhl_results(nhl_payload()))
    monkeypatch.setattr(history.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=503))
    assert history.fetch_page(cache, "NHL", "failed", "https://example.test/history", history.parse_nhl_results) == (True, "HTTP 503")
    assert len(cache.read(["NHL"], date(2026, 1, 1), NOW.date())) == 1


@pytest.mark.parametrize("provider", ["Cricbuzz", "CricketData"])
def test_explicit_terminal_no_result_retracts_old_cricket_winner(tmp_path, monkeypatch, provider):
    clock = [NOW]
    cache = history.CompletedHistoryStore(tmp_path / "history.db", clock=lambda: clock[0])
    payload, native, parser, _retract = _native_case(provider)
    cache.record(provider, "final", parser(payload))
    native["status"] = "No result"
    clock[0] += timedelta(hours=1)
    monkeypatch.setattr(history.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: payload))
    monkeypatch.setattr(history, "observe_completed_team_sports_response", lambda *a, **kw: None)
    history.fetch_page(cache, provider, "corrected", "https://example.test/history", parser)
    assert cache.read([provider], date(2026, 1, 1), NOW.date()) == []


def _prematch():
    match = _esports_match()
    match.update(status="upcoming", begin_at=(NOW + timedelta(hours=2)).isoformat(), team1_score=0, team2_score=0)
    return match


def _freeze_shadow_clock(monkeypatch):
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)
    monkeypatch.setattr("esports_shadow.datetime", FixedClock)


def test_duplicate_esports_series_do_not_satisfy_sample_or_shadow_gate(tmp_path, monkeypatch):
    _freeze_shadow_clock(monkeypatch)
    match = _prematch()
    for side in ("team1_history", "team2_history"):
        match[side] = [deepcopy(match[side][0]) for _ in range(20)]
    candidate = recommendations.esports_match_winner_candidate(match, now=NOW)
    assert not candidate.model_ready
    assert recommendations.esports_history_window(match, now=NOW) == ([match["team1_history"][0]], [match["team2_history"][0]])
    captured = recommendations.esports_match_winner_candidate(match, now=NOW, capture_original=True)
    assert not captured["candidate"].model_ready and captured["original"] is None
    log = EsportsShadowLog(tmp_path / "shadow.db")
    assert log.log_predictions([match]) == 0
    # Prove rejection is the sample gate, not an already-started fixture.
    assert log.log_predictions([_prematch()]) == 1


def test_esports_dedupe_precedes_window_slice_preserves_valid_model_and_raw_indices(tmp_path, monkeypatch):
    _freeze_shadow_clock(monkeypatch)
    original = _prematch()
    duplicate = deepcopy(original)
    for side in ("team1_history", "team2_history"):
        duplicate[side] = [row for original_row in original[side] for row in (deepcopy(original_row), deepcopy(original_row))]
    baseline = recommendations.esports_match_winner_candidate(original, now=NOW)
    result = recommendations.esports_match_winner_candidate(duplicate, now=NOW)
    assert result == baseline
    captured = recommendations.esports_match_winner_candidate(duplicate, now=NOW, capture_original=True)
    assert captured["candidate"] == baseline
    assert captured["original"] is not None
    selected = recommendations._esports_history_selection(duplicate, now=NOW)
    assert all(len(side) == 20 and len({row["match_id"] for _, row in side}) == 20 for side in selected)
    assert all(duplicate[f"team{number}_history"][index] == row for number, side in enumerate(selected, 1) for index, row in side)
    log = EsportsShadowLog(tmp_path / "shadow.db")
    assert log.log_predictions([duplicate]) == 1
    with closing(sqlite3.connect(tmp_path / "shadow.db")) as connection:
        wins = connection.execute("SELECT team1_last5_wins,team2_last5_wins FROM esports_shadow_form").fetchone()
    assert wins == tuple(sum(row["won"] for _, row in side[:5]) for side in selected)


@pytest.mark.parametrize("field,value", [("match_id", None), ("match_id", True), ("match_id", "1000"), ("opponent_id", None), ("opponent_id", 7)])
def test_non_elo_series_do_not_count_as_esports_history(field, value):
    match = _prematch()
    match["team1_history"][0][field] = value
    candidate = recommendations.esports_match_winner_candidate(match, now=NOW)
    assert not candidate.model_ready


def test_conflicting_duplicate_esports_series_not_guessed_but_future_rows_ignored():
    match = _prematch()
    conflict = deepcopy(match["team1_history"][0])
    conflict["won"] = not conflict["won"]
    match["team1_history"].append(conflict)
    assert not recommendations.esports_match_winner_candidate(match, now=NOW).model_ready
    conflict["end_at"] = (NOW + timedelta(minutes=1)).isoformat()
    assert recommendations.esports_match_winner_candidate(match, now=NOW).model_ready


@pytest.mark.parametrize("consistent", [False, True])
def test_shared_esports_series_has_one_canonical_winner_across_both_histories(consistent):
    match = _prematch()
    match["team1_history"][0].update(match_id=3000, opponent_id=8, won=True)
    match["team2_history"][0].update(match_id=3000, opponent_id=7, won=not consistent)
    candidate = recommendations.esports_match_winner_candidate(match, now=NOW)
    first, second = recommendations.esports_history_window(match, now=NOW)
    captured = recommendations.esports_match_winner_candidate(match, now=NOW, capture_original=True)
    if consistent:
        assert candidate.model_ready
        assert len(first) == len(second) == 20
        assert captured["original"].to_dict()["outputs"]["subgraph_size"] == 39
    else:
        assert not candidate.model_ready
        assert len(first) == len(second) == 19
        assert all(row["match_id"] != 3000 for row in first + second)
        assert captured["original"] is None
