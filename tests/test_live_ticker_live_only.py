from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import app
from test_live_football_source import native


def uefa_at_46():
    fixture = native()
    fixture["league"].update(id=3, name="Europa League")
    fixture["fixture"]["status"].update(elapsed=46, extra=None)
    fixture["goals"].update(home=4, away=0)
    fixture["score"]["halftime"] = dict(fixture["goals"])
    fixture["events"] = [
        {"time": {"elapsed": minute}, "team": {"id": 1}, "type": "Goal", "detail": "Normal Goal"}
        for minute in (8, 17, 28, 40)
    ]
    for team_stats in fixture["statistics"]:
        home = team_stats["team"]["id"] == 1
        values = {"expected_goals": .84 if home else .28, "Red Cards": 0,
                  "Total Shots": 8 if home else 9, "Shots on Goal": 6 if home else 2}
        team_stats["statistics"] = [{"type": key, "value": val} for key, val in values.items()]
    return fixture


def analyse(fixture, *, age=1):
    ordinary, separate = app._analyze_ticker_fixture(fixture, object())
    return ordinary, app._assess_live_fixture(fixture, ordinary, separate, age=age, freemode=False)


def test_uefa_can_publish_from_verified_live_data_without_any_prior_or_http(monkeypatch):
    import live_football_priors
    import requests
    from scanners.ultra_live_scanner_v3 import UltraLiveScanner

    def forbidden(*_a, **_kw):
        pytest.fail("an automatic live tip must not read a prior or start another request")

    monkeypatch.setattr(live_football_priors, "stored_goal_priors", forbidden)
    monkeypatch.setattr(UltraLiveScanner, "_get_prematch_goal_priors", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    fixture = uefa_at_46()
    ordinary, (best, reason) = analyse(fixture)
    assert ordinary["model_version"] == "live-restspiel-xg-neutral-split-v1"
    assert best is not None and reason == "Live-Tipp"
    candidate, row, _ = best
    assert not candidate.model_ready
    assert row["live_comparison"]["market"] not in {"next_goal", "ft_total"}
    assert "6:2 Schüsse aufs Tor" in row["live_comparison"]["reason"]
    assert "gleich verteilten Torchancen" in row["live_comparison"]["reason"]


@pytest.mark.parametrize("fault", ["equal", "missing-xg", "goal-log", "red-log", "old"])
def test_score_alone_or_unsupported_snapshot_is_not_a_tip(fault):
    fixture = deepcopy(uefa_at_46())
    if fault == "equal":
        fixture["statistics"][0]["statistics"][0]["value"] = .84
    elif fault == "missing-xg":
        fixture["statistics"][0]["statistics"].pop(0)
    elif fault == "goal-log":
        fixture["events"].pop()
    elif fault == "red-log":
        fixture["statistics"][0]["statistics"][1]["value"] = 1
    _, (best, status) = analyse(fixture, age=121 if fault == "old" else 1)
    assert best is None and "Vorabprognose" not in status
    if fault == "equal":
        assert status == "Geprüft – kein Tipp"


@pytest.mark.parametrize("minutes_ago", [2, 240, 22 * 60])
def test_fresh_receipt_cannot_make_a_contradictory_kickoff_current(minutes_ago):
    fixture = uefa_at_46()
    fixture["fixture"]["date"] = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    _, (best, status) = analyse(fixture)
    assert best is None
    assert status == "Spielzeit und Anpfiff passen nicht zusammen"
