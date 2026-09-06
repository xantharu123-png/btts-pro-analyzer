from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from scanners import completed_history as h

UTC = timezone.utc
NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


def nba_payload():
    return {"events": [{"id": "401810101", "date": "2026-01-01T19:00:00Z", "competitions": [{
        "id": "401810101", "date": "2026-01-01T19:00:00Z", "neutralSite": False,
        "status": {"period": 5, "type": {"state": "post", "completed": True, "name": "STATUS_FINAL"}},
        "competitors": [
            {"homeAway": "home", "team": {"id": "2", "abbreviation": "BOS"}, "score": "109", "winner": True},
            {"homeAway": "away", "team": {"id": "13", "abbreviation": "LAL"}, "score": "101", "winner": False},
        ],
    }]}]}


def nhl_payload():
    # Shape verified against the official NHL schedule endpoint.
    return {"gameWeek": [{"games": [{
        "id": 2025020632, "season": 20252026, "gameType": 2,
        "startTimeUTC": "2026-01-01T18:00:00Z", "gameState": "OFF", "neutralSite": False,
        "homeTeam": {"id": 9, "abbrev": "OTT", "score": 4},
        "awayTeam": {"id": 15, "abbrev": "WSH", "score": 3},
        "gameOutcome": {"lastPeriodType": "OT"},
    }]}]}


def euro_payload():
    # Shape verified against api-live.euroleague.net's E2025 season response.
    return {"data": [{
        "id": "13302d2b-97e6-4b96-ab6a-d422324fb6f0", "identifier": "E2025_406",
        "played": True, "utcDate": "2026-05-24T18:00:00Z", "isNeutralVenue": True,
        "local": {"club": {"code": "OLY"}, "score": 92},
        "road": {"club": {"code": "MAD"}, "score": 85}, "winner": {"code": "OLY"},
    }]}


def cricket_payload():
    return {"typeMatches": [{"seriesMatches": [{"seriesAdWrapper": {"matches": [{"matchInfo": {
        "matchId": 100001, "state": "Complete", "status": "Alpha won by 5 runs (DLS method)",
        "startDate": "1788177600000", "matchFormat": "T20", "seriesName": "Test T20",
        "team1": {"teamId": 101, "teamName": "Alpha"},
        "team2": {"teamId": 102, "teamName": "Beta"},
    }}]}}]}]}


def store(tmp_path, clock=None):
    return h.CompletedHistoryStore(tmp_path / "history.db", clock=clock or (lambda: NOW))


def test_official_final_schemas_and_sport_specific_result_features():
    nba = h.parse_espn_results(nba_payload())[0]
    nhl = h.parse_nhl_results(nhl_payload())[0]
    euro = h.parse_euroleague_results(euro_payload())[0]
    assert (nba["home_team_id"], nba["winner_side"], nba["periods"]) == ("2", "home", 5)
    assert (nhl["home_team"], nhl["away_team"], nhl["last_period_type"]) == ("OTT", "WSH", "OT")
    assert nhl["result_scope"] == "including_overtime_shootout"
    assert euro["home_team_id"] == "OLY" and euro["neutral_site"] is True


@pytest.mark.parametrize("state", ["FUT", "PRE", "LIVE", "CRIT", "PST", "CANC"])
def test_nhl_scheduled_cancelled_and_live_scores_are_not_history(state):
    payload = nhl_payload()
    payload["gameWeek"][0]["games"][0]["gameState"] = state
    assert h.parse_nhl_results(payload) == []


def test_score_identity_and_winner_conflicts_do_not_become_results():
    payload = nba_payload()
    game = payload["events"][0]["competitions"][0]
    game["competitors"][1]["winner"] = True
    assert h.parse_espn_results(payload) == []
    game["competitors"][1]["winner"] = False
    game["competitors"][0]["score"] = "NaN"
    assert h.parse_espn_results(payload) == []
    euro = euro_payload()
    euro["data"][0]["winner"]["code"] = "MAD"
    assert h.parse_euroleague_results(euro) == []
    euro["data"][0]["played"] = False
    assert h.parse_euroleague_results(euro) == []


def test_cricket_requires_terminal_state_and_explicit_winner_never_run_totals():
    payload = cricket_payload()
    info = payload["typeMatches"][0]["seriesMatches"][0]["seriesAdWrapper"]["matches"][0]["matchInfo"]
    assert h.parse_cricbuzz_results(payload)[0]["winner_side"] == "home"
    info["matchWinner"] = "Alpha"
    for status in ("No result", "Match drawn", "Match tied", "Match abandoned"):
        info["status"] = status
        assert h.parse_cricbuzz_results(payload) == []
    info.pop("matchWinner")
    info["status"] = "Beta won by 5 wickets"
    info["state"] = "In Progress"
    assert h.parse_cricbuzz_results(payload) == []
    info["state"] = "Complete"
    row = h.parse_cricbuzz_results(payload)[0]
    assert row["winner_side"] == "away" and row["home_score"] is None


def test_cricketdata_terminal_identity_and_explicit_gmt():
    row = {"id": "uuid-1", "matchEnded": True, "dateTimeGMT": "2026-09-01T10:00:00",
           "teams": ["Alpha", "Beta"], "matchType": "odi", "name": "ODI", "status": "Beta won by 2 wickets"}
    result = h.parse_cricketdata_results({"status": "success", "data": [row]})[0]
    assert result["start_time"] == "2026-09-01T10:00:00+00:00" and result["winner_side"] == "away"
    row["matchEnded"] = False
    assert h.parse_cricketdata_results({"status": "success", "data": [row]}) == []


def test_first_observation_not_backdated_and_corrections_are_asof_versioned(tmp_path):
    clock = [NOW]
    cache = store(tmp_path, lambda: clock[0])
    original = h.parse_nhl_results(nhl_payload())[0]
    cache.record("NHL", "page", [original])
    assert cache.read(["NHL"], date(2026, 1, 1), NOW.date(), as_of=NOW-timedelta(seconds=1)) == []
    first = cache.read(["NHL"], date(2026, 1, 1), NOW.date(), as_of=NOW)[0]
    assert first["result_observed_at"] == NOW.isoformat()
    assert "completed_at" not in first  # kickoff is not a claimed completion clock.
    clock[0] += timedelta(hours=1)
    cache.record("NHL", "page", [original])
    assert cache.read(["NHL"], date(2026, 1, 1), NOW.date())[0]["result_observed_at"] == NOW.isoformat()
    correction = {**original, "home_score": 2, "winner_side": "away"}
    cache.record("NHL", "page", [correction])
    assert cache.read(["NHL"], date(2026, 1, 1), NOW.date(), as_of=NOW)[0]["winner_side"] == "home"
    assert cache.read(["NHL"], date(2026, 1, 1), NOW.date())[0]["winner_side"] == "away"


def test_terminal_future_or_same_time_game_is_never_causal_history(tmp_path):
    cache = store(tmp_path)
    row = h.parse_nhl_results(nhl_payload())[0]
    for kickoff in (NOW, NOW + timedelta(hours=1)):
        cache.record("NHL", "future", [{**row, "start_time": kickoff.isoformat()}])
    assert cache.read(["NHL"], date(2026, 1, 1), NOW.date()) == []
    with pytest.raises(ValueError):
        cache.read(["NHL"], date(2026, 1, 1), NOW.date(), as_of=NOW + timedelta(seconds=1))


def test_cache_reservations_bound_requests_across_instances_and_failures(tmp_path, monkeypatch):
    cache = store(tmp_path)
    second = store(tmp_path)
    calls = []
    monkeypatch.setattr(h.requests, "get", lambda *a, **k: calls.append(k) or SimpleNamespace(status_code=503))
    for key in ("a", "a", "b", "c"):
        h.fetch_page(second if key == "b" else cache, "NHL", key, "https://api-web.nhle.com/v1/schedule/test", h.parse_nhl_results, daily_limit=2)
    assert len(calls) == 2
    assert second.request_error("NHL", "a") == "HTTP 503"
    assert second.request_error("NHL", "c") == "Daily history request budget reached"


def test_cached_history_does_not_refetch_before_ttl_and_fetch_clock_is_honest(tmp_path, monkeypatch):
    clock = [NOW]
    cache = store(tmp_path, lambda: clock[0])
    calls = []
    def get(*args, **kwargs):
        calls.append(args[0])
        clock[0] += timedelta(seconds=2)
        return SimpleNamespace(status_code=200, json=nhl_payload)
    monkeypatch.setattr(h.requests, "get", get)
    scanner = SimpleNamespace(nhl_schedule_base="https://api-web.nhle.com/v1/schedule", errors={})
    kwargs = dict(as_of=NOW, store=cache)
    assert h.completed_nhl(scanner, date(2026, 1, 1), date(2026, 1, 7), **kwargs) == []
    first_calls = len(calls)
    result = h.completed_nhl(scanner, date(2026, 1, 1), date(2026, 1, 7), store=cache)
    assert len(calls) == first_calls and len(result) == 1
    assert h.utc_time(result[0]["result_observed_at"]) > NOW


def test_history_cold_start_is_bounded_and_progresses_into_older_weeks(tmp_path, monkeypatch):
    clock = [NOW]
    cache = store(tmp_path, lambda: clock[0])
    urls = []
    monkeypatch.setattr(h.requests, "get", lambda url, **kw: urls.append(url) or SimpleNamespace(status_code=200, json=lambda: {"gameWeek": []}))
    scanner = SimpleNamespace(nhl_schedule_base="https://api-web.nhle.com/v1/schedule", errors={})
    h.completed_nhl(scanner, date(2025, 9, 5), NOW.date(), store=cache)
    assert len(urls) == 8
    old_urls = set(urls)
    clock[0] += timedelta(minutes=30)
    h.completed_nhl(scanner, date(2025, 9, 5), NOW.date(), store=cache)
    assert len(urls) == 16 and set(urls[8:]).isdisjoint(old_urls)


def test_invalid_asof_rejected_before_network_and_cricket_missing_key_is_safe(tmp_path, monkeypatch):
    def no_call(*args, **kwargs):
        raise AssertionError("network must not be called")
    monkeypatch.setattr(h.requests, "get", no_call)
    scanner = SimpleNamespace(nhl_schedule_base="https://api-web.nhle.com/v1/schedule", errors={})
    with pytest.raises(ValueError):
        h.completed_nhl(scanner, date(2026, 1, 1), NOW.date(), as_of=NOW + timedelta(seconds=1), store=store(tmp_path))
    cricket = SimpleNamespace(rapidapi_key=None, cricket_api_key=None, last_error=None)
    assert h.completed_cricket(cricket, date(2026, 1, 1), NOW.date(), store=store(tmp_path)) == []
    assert cricket.last_error == "Cricket API key missing"


def test_cricket_configured_provider_endpoint_and_secret_not_in_history_cache(tmp_path, monkeypatch):
    calls = []
    scanner = SimpleNamespace(rapidapi_key="sensitive-example", cricket_api_key=None,
                              cricbuzz_base="https://cricbuzz-cricket.p.rapidapi.com",
                              headers={"X-RapidAPI-Key": "sensitive-example"}, last_error=None)
    monkeypatch.setattr(h.requests, "get", lambda url, **kw: calls.append((url, kw)) or SimpleNamespace(status_code=200, json=cricket_payload))
    cache = store(tmp_path)
    rows = h.completed_cricket(scanner, date(2026, 1, 1), NOW.date(), store=cache)
    assert calls[0][0].endswith("/matches/v1/recent") and rows[0]["winner_side"] == "home"
    assert b"sensitive-example" not in cache.path.read_bytes()


def test_basketball_one_failed_provider_preserves_other_real_history_and_reports_partial(tmp_path, monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if "espn" in url:
            return SimpleNamespace(status_code=403)
        return SimpleNamespace(status_code=200, json=euro_payload)
    monkeypatch.setattr(h.requests, "get", get)
    scanner = SimpleNamespace(espn_nba_url="https://site.api.espn.com/scoreboard",
                              nba_headers={"User-Agent": "test"},
                              euroleague_games_base="https://api-live.euroleague.net/v2", errors={})
    cache = store(tmp_path)
    result = h.completed_basketball(scanner, "All", date(2025, 9, 5), NOW.date(), store=cache)
    assert len(calls) <= 3 and len(result) == 1 and result[0]["provider"] == "EuroLeague"
    assert scanner.history_coverage["status"] == "partial"
    assert "HTTP 403" in scanner.errors["basketball_history"]
    calls.clear()
    h.completed_basketball(scanner, "All", date(2025, 9, 5), NOW.date(), store=cache)
    assert calls == [] and "HTTP 403" in scanner.errors["basketball_history"]


def test_basketball_month_history_request_limit_starts_with_current_month(tmp_path, monkeypatch):
    requested = []
    monkeypatch.setattr(h.requests, "get", lambda url, **kw: requested.append(kw["params"]["dates"]) or SimpleNamespace(status_code=200, json=lambda: {"events": []}))
    scanner = SimpleNamespace(espn_nba_url="https://site.api.espn.com/scoreboard", nba_headers={"User-Agent": "test"}, errors={})
    h.completed_basketball(scanner, "NBA", date(2025, 9, 10), date(2026, 9, 10), store=store(tmp_path))
    assert len(requested) == 4
    assert requested[0] == "20260901-20260930"
    assert scanner.history_coverage["status"] == "partial"
