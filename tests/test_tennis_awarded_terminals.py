"""Awarded is not proof of an ordinary played result, even with set scores."""
from scripts import tennis_daily as daily


def test_espn_awarded_final_is_not_promoted_to_normal_result(monkeypatch):
    comp = dict(id="123", date="2026-05-12T12:00:00Z",
        status={"type": {"state": "post", "completed": True,
                         "name": "STATUS_FINAL", "description": "Awarded"}},
        competitors=[dict(athlete={"displayName": "Alpha"}, winner=True,
            linescores=[dict(value=6, winner=True), dict(value=6, winner=True)]),
            dict(athlete={"displayName": "Beta"}, winner=False,
            linescores=[dict(value=3, winner=False), dict(value=4, winner=False)])])
    monkeypatch.setattr(daily, "_fetch_espn_events", lambda *a: [dict(groupings=[
        dict(grouping={"slug": "mens-singles"}, competitions=[comp])])])
    assert daily.fetch_results_espn("2026-05-12", "ATP") == []


def test_sofascore_awarded_final_is_not_promoted_to_normal_result(monkeypatch):
    event = dict(id=123, startTimestamp=1778587200,
        tournament={"category": {"slug": "atp"}},
        homeTeam={"name": "Alpha"}, awayTeam={"name": "Beta"},
        status={"type": "finished", "description": "Awarded"},
        winnerCode=1, homeScore={"current": 2}, awayScore={"current": 0})

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"events": [event]}

    monkeypatch.setattr(daily.requests, "get", lambda *a, **k: Response())
    assert daily.fetch_results_sofascore("2026-05-12") == []
