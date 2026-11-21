"""Tests for the red-card history harvester's pure extraction logic."""

import unittest
import sqlite3
import pytest

from redcard_history_harvester import (
    RedCardHistoryHarvester,
    connect,
    extract_dismissal_case,
)
from redcard_pattern_report import load_cases


def _fixture(home_id=10, away_id=20, home_goals=2, away_goals=1):
    return {
        "fixture": {"status": {"short": "FT"}},
        "teams": {"home": {"id": home_id}, "away": {"id": away_id}},
        "goals": {"home": home_goals, "away": away_goals},
    }


def _card(minute, team_id, detail="Red Card"):
    return {
        "type": "Card",
        "detail": detail,
        "time": {"elapsed": minute},
        "team": {"id": team_id},
    }


def _goal(minute, team_id):
    return {"type": "Goal", "time": {"elapsed": minute}, "team": {"id": team_id}}


class HarvesterExtractionTests(unittest.TestCase):
    def test_no_cards_returns_none(self):
        self.assertIsNone(extract_dismissal_case(_fixture(), [_goal(10, 10)]))

    def test_first_red_defines_window_and_score_at_red(self):
        events = [
            _goal(22, 10),           # 1:0 vor Rot
            _card(36, 10),           # Rot Heim
            _goal(50, 10),           # 10-Mann trifft
            _goal(82, 20),           # 11-Mann trifft
        ]
        case = extract_dismissal_case(_fixture(), events)

        self.assertEqual(case["red_minute"], 36)
        self.assertEqual(case["red_side"], "home")
        self.assertEqual(case["score_at_red_home"], 1)
        self.assertEqual(case["score_at_red_away"], 0)
        self.assertEqual(case["red_team_goal_diff"], 1)
        self.assertEqual(
            case["goals_after"],
            [
                {"minute": 50, "by_11_team": False, "since_card": 14},
                {"minute": 82, "by_11_team": True, "since_card": 46},
            ],
        )
        self.assertEqual(case["complex_state"], 0)

    def test_second_yellow_counts_as_dismissal(self):
        events = [
            _card(30, 20, "Yellow Card"),
            _card(55, 20, "Second Yellow card"),
            _goal(60, 10),
        ]
        case = extract_dismissal_case(_fixture(home_goals=1, away_goals=0), events)

        self.assertIsNotNone(case)
        self.assertEqual(case["red_minute"], 55)
        self.assertEqual(case["red_side"], "away")
        self.assertEqual(case["goals_after"][0]["by_11_team"], True)

    def test_second_red_closes_observation_window(self):
        events = [
            _card(40, 10),
            _goal(50, 20),           # zaehlt noch (11v10)
            _card(60, 20),           # zweite Rote -> 10v10
            _goal(70, 10),           # darf NICHT mehr zaehlen
        ]
        case = extract_dismissal_case(_fixture(home_goals=1, away_goals=1), events)

        self.assertEqual(case["complex_state"], 1)
        self.assertEqual(len(case["goals_after"]), 1)
        self.assertEqual(case["goals_after"][0]["minute"], 50)

    def test_unrelated_team_card_is_ignored_safely(self):
        events = [_card(30, 999)]
        self.assertIsNone(extract_dismissal_case(_fixture(), events))

    def test_malformed_events_do_not_crash(self):
        events = [
            None,
            {"type": "Card"},                      # kein detail/time/team
            {"type": "Card", "detail": "Red Card",
             "time": {"elapsed": True}},           # bool elapsed
            _card(44, 20),
            _goal(50, 20),
        ]
        case = extract_dismissal_case(_fixture(), events)

        self.assertIsNone(case)


class HarvesterQuotaRoutingTests(unittest.TestCase):
    def test_provider_calls_use_the_budgeted_api_wrapper(self):
        calls = []

        class FakeResponse:
            status_code = 200
            @staticmethod
            def json():
                return {"errors": [], "response": [{"fixture": {"id": 7}}]}

        class FakeAPI:
            base_url = "https://v3.football.api-sports.io"
            headers = {"x-apisports-key": "test-key"}

            @staticmethod
            def _get(url, **kwargs):
                calls.append((url, kwargs))
                return FakeResponse()

        connection = sqlite3.connect(":memory:")
        try:
            harvester = RedCardHistoryHarvester(FakeAPI(), connection)
            result = harvester._get("fixtures", {"league": 78})
        finally:
            connection.close()

        self.assertEqual(result, [{"fixture": {"id": 7}}])
        self.assertEqual(harvester.calls_used, 1)
        self.assertEqual(
            calls,
            [
                (
                    "https://v3.football.api-sports.io/fixtures",
                    {
                        "headers": {"x-apisports-key": "test-key"},
                        "params": {"league": 78},
                        "timeout": 20,
                    },
                )
            ],
        )


@pytest.mark.parametrize("status,payload", [(503, {"response": []}), (200, {"response": None}),
                                            (200, {"errors": {}, "results": 0})])
def test_harvest_error_cannot_be_consumed_as_a_successful_empty_fixture_list(status, payload):
    class API:
        base_url = "https://offline.invalid"
        headers = {}

        def _get(self, *args, **kwargs):
            return type("OfflineResponse", (), {"status_code": status, "json": lambda self: payload})()

    conn = connect(":memory:")
    harvester = RedCardHistoryHarvester(API(), conn)
    with pytest.raises(RuntimeError):
        harvester.ingest_fixture_lists(budget=1)
    assert harvester.calls_used == 1
    assert conn.execute("SELECT count(*) FROM meta").fetchone()[0] == 0
    conn.close()


def test_transport_error_debits_the_single_history_call_budget():
    class API:
        base_url = "https://offline.invalid"
        headers = {}

        def _get(self, *args, **kwargs):
            raise TimeoutError()

    harvester = RedCardHistoryHarvester(API(), None)
    with pytest.raises(TimeoutError):
        harvester._get("fixtures/events", {"fixture": 1})
    assert harvester.calls_used == 1


@pytest.mark.parametrize("detail", ["Missed Penalty", "Goal cancelled", "Goal Disallowed", "Penalty Shootout"])
def test_non_scoring_event_does_not_enter_research(detail):
    non_goal = dict(_goal(50, 10), detail=detail)
    fixture = _fixture(home_goals=0, away_goals=1)
    case = extract_dismissal_case(fixture, [_card(48, 10), non_goal, _goal(60, 20)])
    assert case is not None
    assert case["goals_after"] == [{"minute": 60, "by_11_team": True, "since_card": 12}]


@pytest.mark.parametrize("event", [_goal(55, 999), _goal(None, 20), _goal(60, True), _goal(50, 10)])
def test_malformed_or_score_inconsistent_history_cannot_become_research(event):
    assert extract_dismissal_case(_fixture(home_goals=0, away_goals=1), [_card(35, 10), event]) is None


def test_goal_and_dismissal_with_same_native_clock_leave_case_unclassified():
    assert extract_dismissal_case(_fixture(home_goals=0, away_goals=1), [_card(35, 10), _goal(35, 20)]) is None


def test_history_keeps_explicit_regulation_stoppage_and_excludes_extra_time():
    fixture = _fixture(home_goals=1, away_goals=1)
    fixture["fixture"]["status"]["short"] = "AET"
    fixture["score"] = {"fulltime": {"home": 1, "away": 0}}
    goal = _goal(90, 10)
    goal["time"]["extra"] = 4
    case = extract_dismissal_case(fixture, [_card(70, 20), goal, _goal(95, 20)])
    assert case is not None
    assert (case["final_home"], case["final_away"]) == (1, 0)
    assert case["goals_after"] == [{"minute": 94, "by_11_team": True, "since_card": 24}]


def test_first_half_added_time_card_precedes_second_half_goal_without_negative_exposure():
    card = _card(45, 10)
    card["time"]["extra"] = 4
    case = extract_dismissal_case(_fixture(home_goals=0, away_goals=1), [card, _goal(46, 20)])
    assert case is not None
    assert case["goals_after"] == [{"minute": 46, "by_11_team": True, "since_card": None}]
    assert not case["exposure_usable"]


def test_harvest_preserves_legacy_rows_but_reports_only_verified_new_cases(monkeypatch):
    conn = connect(":memory:")
    for fixture_id in (1, 2):
        conn.execute("INSERT INTO fixtures(fixture_id,league_id,season,match_date,status_short,"
                     "home_id,away_id,home_name,away_name,final_home,final_away,events_fetched)"
                     " VALUES(?,39,2026,'2026-11-01','FT',10,20,'H','A',1,0,?)", (fixture_id, int(fixture_id == 1)))
    conn.execute("INSERT INTO dismissals(fixture_id,match_date,league_id,league_name,home_name,away_name,"
                 "final_home,final_away,red_minute,red_side,red_team_name,score_at_red_home,"
                 "score_at_red_away,red_team_goal_diff,complex_state,goals_after_json,created_at) VALUES"
                 "(1,'2026-11-01',39,'L','H','A',0,0,40,'away','A',0,0,0,0,'[]','2026-11-01')")
    late = _goal(90, 10)
    late["time"]["extra"] = 4
    harvester = RedCardHistoryHarvester(None, conn)
    monkeypatch.setattr(harvester, "_get", lambda *a: [_card(65, 20), late])
    assert harvester.harvest_events(1)["dismissals"] == 1
    assert conn.execute("SELECT COUNT(*) FROM dismissals").fetchone()[0] == 2
    cases = load_cases(conn)
    assert len(cases) == 1
    assert cases[0]["red_minute"] == 65
    assert cases[0]["goals_after"] == []  # 93-minute exposure study, not live settlement
    conn.close()


def test_harvest_carries_halftime_evidence_from_fixture_list_to_event_reconciliation(monkeypatch):
    conn = connect(":memory:")
    fx = _fixture(home_goals=0, away_goals=1)
    fx["fixture"].update(id=6, date="2026-11-04")
    fx["teams"]["home"]["name"] = "H"
    fx["teams"]["away"]["name"] = "A"
    fx["score"] = {"halftime": {"home": 0, "away": 1}}
    harvester = RedCardHistoryHarvester(None, conn)
    def fetch(endpoint, params):
        harvester.calls_used += 1
        return [fx] if endpoint == "fixtures" else [_card(40, 10), _goal(46, 20)]
    monkeypatch.setattr(harvester, "_get", fetch)
    harvester.ingest_fixture_lists(1)
    assert harvester.backlog() == 1
    assert harvester.harvest_events(2)["dismissals"] == 0
    conn.close()


if __name__ == "__main__":
    unittest.main()
