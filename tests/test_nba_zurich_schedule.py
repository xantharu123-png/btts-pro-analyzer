from datetime import date, datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlencode

from context_sources import team_sports_capture, team_sports_status
from scanners import basketball_scanner


def _espn_game(game_id, start):
    return {
        "id": game_id,
        "competitions": [{
            "id": game_id,
            "date": start,
            "status": {"type": {"state": "pre"}},
            "competitors": [
                {"homeAway": "home", "team": {"id": "10", "abbreviation": "BOS"}},
                {"homeAway": "away", "team": {"id": "20", "abbreviation": "NYK"}},
            ],
        }],
    }


def test_nba_zurich_day_includes_previous_espn_calendar_day_without_duplicates(monkeypatch, tmp_path):
    overnight = _espn_game("501", "2026-11-25T03:10:00Z")  # 04:10 Zürich, 22:10 ET on Tuesday
    evening = _espn_game("502", "2026-11-25T19:30:00Z")
    schedule = {
        "20261125": [evening, _espn_game("503", "2026-11-25T23:00:00Z")],
        "20261124-20261125": [overnight, evening, evening, _espn_game("500", "2026-11-24T22:59:00Z"),
                              _espn_game("503", "2026-11-25T23:00:00Z")],
    }
    requests = []

    def fetch(url, *, headers, params, timeout):
        assert url.endswith("/basketball/nba/scoreboard")
        bucket = params["dates"]
        requests.append(params)
        return SimpleNamespace(status_code=200, url=url+"?"+urlencode(params), history=[],
                               json=lambda: {"season":{"year":2027}, "events":schedule.get(bucket, [])})

    monkeypatch.setattr(basketball_scanner.requests, "get", fetch)
    observed = datetime(2026,11,24,12,tzinfo=timezone.utc)
    monkeypatch.setattr(team_sports_capture, "_receipt_now", lambda: observed)
    day = date(2026, 11, 25)
    path = tmp_path/"observations.db"
    with team_sports_capture.capture_team_sports_worker(path=path):
        games = basketball_scanner.BasketballScanner().get_upcoming_games("NBA", day, day)
    assert [(r["game_id"], r["home_team_id"], r["away_team_id"]) for r in games] == [
        ("501", "10", "20"), ("502", "10", "20")
    ]
    assert requests == [{"dates":"20261124-20261125","limit":1000}]
    records = team_sports_status.team_sport_observations_as_of(path, cutoff="2026-11-24T12:01:00+00:00")
    assert any(record["event_key"]=="espn:basketball:501" and
               record["payload"]["request"]["request_window"]=={"start":"2026-11-24","end":"2026-11-25"}
               for record in records)


def test_nba_keeps_other_day_out_even_if_espn_returns_night_games(monkeypatch):
    replies = {
        "20260307": [_espn_game("600", "2026-03-07T22:59:59Z")],
        "20260308": [_espn_game("601", "2026-03-08T23:01:00Z")],
    }
    replies["20260307-20260308"] = [*replies["20260307"], *replies["20260308"]]
    monkeypatch.setattr(basketball_scanner.requests, "get",
        lambda _url, **kw: SimpleNamespace(status_code=200, json=lambda: {"events": replies[kw["params"]["dates"]]}))
    day = date(2026, 3, 8)  # US daylight saving change, not a Zürich offset change.
    assert basketball_scanner.BasketballScanner().get_upcoming_games("NBA", day, day) == []


def test_nba_schedule_http400_falls_back_only_to_the_overlapping_public_days(monkeypatch):
    calls = []

    def fetch(_url, *, params, **_options):
        key = params["dates"]
        calls.append(key)
        if key == "20261124-20261125":
            return SimpleNamespace(status_code=400)
        return SimpleNamespace(status_code=200, json=lambda: {"events": (
            [_espn_game("504", "2026-11-25T04:00:00Z")] if key=="20261124" else []
        )})

    monkeypatch.setattr(basketball_scanner.requests, "get", fetch)
    scanner = basketball_scanner.BasketballScanner()
    day = date(2026,11,25)
    assert [r["game_id"] for r in scanner.get_upcoming_games("NBA",day,day)] == ["504"]
    assert calls == ["20261124-20261125", "20261124", "20261125"]
    assert "nba_schedule" not in scanner.errors


def test_espn_single_day_history_must_bind_to_exact_native_day():
    import pytest
    from context_models.contracts import ContextContractError

    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    params = {"dates":"20261124", "limit":100}
    response = SimpleNamespace(status_code=200, url=url+"?"+urlencode(params), history=[])
    contract = team_sports_status.response_request(
        "ESPN", url, params, phase="history", window=None, request_key="nba:day:2026-11-24", response=response)
    assert contract["request_window"]=={"start":"2026-11-24","end":"2026-11-24"}
    with pytest.raises(ContextContractError):
        team_sports_status.response_request(
            "ESPN", url, params, phase="history", window=None, request_key="nba:day:2026-11-23", response=response)


def test_espn_schedule_day_receipt_cannot_claim_unrelated_zurich_window():
    import pytest
    from context_models.contracts import ContextContractError

    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    params = {"dates":"20261124", "limit":100}
    response = SimpleNamespace(status_code=200, url=url+"?"+urlencode(params), history=[])
    day = date(2026,11,25)
    assert team_sports_status.response_request(
        "ESPN", url, params, phase="schedule", window=(day, day), request_key=None, response=response)
    with pytest.raises(ContextContractError):
        team_sports_status.response_request("ESPN", url, params, phase="schedule",
            window=(date(2026,12,1), date(2026,12,1)), request_key=None, response=response)
