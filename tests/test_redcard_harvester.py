"""Tests for the red-card history harvester's pure extraction logic."""

import unittest

from redcard_history_harvester import extract_dismissal_case


def _fixture(home_id=10, away_id=20, home_goals=2, away_goals=1):
    return {
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
        case = extract_dismissal_case(_fixture(), events)

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
        case = extract_dismissal_case(_fixture(), events)

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

        self.assertIsNotNone(case)
        self.assertEqual(case["red_minute"], 44)


if __name__ == "__main__":
    unittest.main()
