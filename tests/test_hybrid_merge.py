import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from challenge_15k import API_TAIL_DAYS, ChallengeDataProvider  # noqa: E402
from football_data_history import merge_api_tail  # noqa: E402

NOW = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)


class FrozenDateTime(datetime):
    """Eingefrorene Uhr: now() liefert immer NOW, Rest erbt datetime."""

    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


def csv_entry(fixture_id, played_at, home_name, away_name, home_id, away_id,
              home_goals=2, away_goals=1):
    return {
        "fixture": {
            "id": fixture_id,
            "date": played_at.isoformat(),
            "referee": "R Test",
        },
        "league": {"id": 39, "season": 2025, "name": "Football-Data 39"},
        "teams": {
            "home": {"id": home_id, "name": home_name},
            "away": {"id": away_id, "name": away_name},
        },
        "goals": {"home": home_goals, "away": away_goals},
        "challenge_stats": {
            "corners_home": 6,
            "corners_away": 4,
            "yellow_cards_home": 2,
            "yellow_cards_away": 3,
        },
        "challenge_source": "football-data-results-only",
    }


def api_entry(fixture_id, played_at, home_name, away_name, home_id, away_id,
              home_goals=1, away_goals=0):
    return {
        "fixture": {
            "id": fixture_id,
            "date": played_at.isoformat(),
            "status": {"short": "FT"},
        },
        "league": {"id": 39, "season": 2025, "name": "Premier League"},
        "teams": {
            "home": {"id": home_id, "name": home_name},
            "away": {"id": away_id, "name": away_name},
        },
        "goals": {"home": home_goals, "away": away_goals},
    }


class MergeApiTailTest(unittest.TestCase):
    def setUp(self):
        self.history = [
            csv_entry(-101, NOW - timedelta(days=14), "Arsenal", "Chelsea", 501, 502),
            csv_entry(-102, NOW - timedelta(days=7), "Liverpool", "Everton", 503, 504),
        ]

    def test_recent_api_fixture_is_appended_without_stats(self):
        tail = [api_entry(9001, NOW - timedelta(days=1), "Newcastle", "West Ham", 601, 602)]

        merged = merge_api_tail(self.history, tail, now=NOW)

        self.assertEqual(len(merged), 3)
        added = merged[-1]
        self.assertEqual(added["fixture"]["id"], 9001)
        self.assertEqual(added["challenge_stats"], {})
        self.assertEqual(added["challenge_source"], "api-football-ft-tail")
        # CSV-Zeilen bleiben unverändert (Stats intakt)
        self.assertEqual(merged[0]["challenge_stats"]["corners_home"], 6)
        self.assertEqual(merged[1]["challenge_stats"]["yellow_cards_away"], 3)

    def test_same_match_is_deduped_despite_alias_names(self):
        history = [csv_entry(-201, NOW - timedelta(days=2), "Ath Madrid", "Betis", 701, 702)]
        tail = [api_entry(9002, NOW - timedelta(days=2), "Atletico Madrid", "Real Betis", 801, 802)]

        merged = merge_api_tail(history, tail, now=NOW)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["fixture"]["id"], -201)

    def test_fixture_outside_tail_window_is_ignored(self):
        tail = [api_entry(9003, NOW - timedelta(days=30), "Fulham", "Brentford", 603, 604)]

        merged = merge_api_tail(self.history, tail, now=NOW)

        self.assertEqual(len(merged), 2)

    def test_future_and_incomplete_fixtures_are_skipped(self):
        future = api_entry(9004, NOW + timedelta(days=1), "Fulham", "Brentford", 603, 604)
        no_goals = api_entry(9005, NOW - timedelta(days=1), "Fulham", "Brentford", 603, 604)
        no_goals["goals"] = {"home": None, "away": None}
        bool_goals = api_entry(9006, NOW - timedelta(days=1), "Wolves", "Palace", 605, 606)
        bool_goals["goals"] = {"home": True, "away": 0}

        merged = merge_api_tail(self.history, [future, no_goals, bool_goals], now=NOW)

        self.assertEqual(len(merged), 2)

    def test_invalid_ids_are_skipped(self):
        bad_fixture_id = api_entry(-5, NOW - timedelta(days=1), "Fulham", "Brentford", 603, 604)
        bad_team_id = api_entry(9007, NOW - timedelta(days=1), "Fulham", "Brentford", True, 604)

        merged = merge_api_tail(self.history, [bad_fixture_id, bad_team_id], now=NOW)

        self.assertEqual(len(merged), 2)

    def test_team_ids_are_patched_from_history_names(self):
        tail = [api_entry(9008, NOW - timedelta(days=1), "Arsenal", "Fulham", 42, 603)]

        merged = merge_api_tail(self.history, tail, now=NOW)

        self.assertEqual(len(merged), 3)
        added = merged[-1]
        self.assertEqual(added["teams"]["home"]["id"], 501)  # aus der CSV geerbt
        self.assertEqual(added["teams"]["away"]["id"], 603)   # unbekannt -> API-ID bleibt

    def test_inputs_are_never_mutated(self):
        tail = [api_entry(9009, NOW - timedelta(days=1), "Arsenal", "Fulham", 42, 603)]
        history_snapshot = [dict(item) for item in self.history]

        merge_api_tail(self.history, tail, now=NOW)

        self.assertEqual(len(self.history), 2)
        self.assertNotIn("challenge_source", tail[0])
        self.assertNotIn("challenge_stats", tail[0])
        for original, snapshot in zip(self.history, history_snapshot):
            self.assertEqual(original["fixture"]["id"], snapshot["fixture"]["id"])

    def test_empty_or_missing_tail_keeps_history(self):
        self.assertEqual(len(merge_api_tail(self.history, None, now=NOW)), 2)
        self.assertEqual(len(merge_api_tail(self.history, [], now=NOW)), 2)

    def test_non_list_history_returns_empty_list(self):
        self.assertEqual(merge_api_tail(None, [api_entry(1, NOW, "A", "B", 1, 2)], now=NOW), [])

    def test_tail_days_must_be_positive_int(self):
        with self.assertRaises(ValueError):
            merge_api_tail(self.history, [], tail_days=0, now=NOW)
        with self.assertRaises(ValueError):
            merge_api_tail(self.history, [], tail_days=True, now=NOW)

    def test_output_is_sorted_by_kickoff(self):
        tail = [
            api_entry(9010, NOW - timedelta(days=1), "Fulham", "Brentford", 603, 604),
            api_entry(9011, NOW - timedelta(days=3), "Wolves", "Palace", 605, 606),
        ]

        merged = merge_api_tail(self.history, tail, now=NOW)

        dates = [item["fixture"]["date"] for item in merged]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(len(merged), 4)


class CompletedHistoryMergeTest(unittest.TestCase):
    def setUp(self):
        # completed_history() fragt intern die echte Uhr ab (Tail-Fenster,
        # from/to-Daten). Ohne eingefrorene Zeit kippt der Test, sobald die
        # reale Zeit von NOW wegläuft (Zeitbombe am Fensterrand).
        for target in ("challenge_15k.datetime", "football_data_history.datetime"):
            patcher = patch(target, FrozenDateTime)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_completed_history_merges_api_tail_over_csv(self):
        csv_history = [
            csv_entry(-101, NOW - timedelta(days=14), "Arsenal", "Chelsea", 501, 502),
        ]
        tail = [api_entry(9001, NOW - timedelta(days=1), "Newcastle", "West Ham", 601, 602)]
        provider = ChallengeDataProvider("test-key", None)
        provider._football_get = Mock(
            side_effect=lambda endpoint, params, label, **_kwargs: (
                tail if "Tail" in label else None
            )
        )

        def fake_stat_history(league_id, season, upcoming):
            return csv_history if season == 2025 else None

        with patch("challenge_15k.fetch_stat_history", side_effect=fake_stat_history):
            result = provider.completed_history(39, 2025, [])

        self.assertEqual(len(result), 2)
        self.assertEqual(result[-1]["fixture"]["id"], 9001)
        params = provider._football_get.call_args_list[0].args[1]
        self.assertEqual(params["status"], "FT")
        self.assertIn("from", params)
        self.assertIn("to", params)

    def test_completed_history_falls_back_to_full_api_without_csv(self):
        provider = ChallengeDataProvider("test-key", None)
        provider._football_get = Mock(
            side_effect=lambda endpoint, params, label, **_kwargs: (
                [api_entry(1, NOW, "A", "B", 1, 2)] if params.get("season") == 2025 else None
            )
        )

        with patch("challenge_15k.fetch_stat_history", return_value=None):
            result = provider.completed_history(999, 2025, [])

        self.assertEqual(len(result), 1)
        params = provider._football_get.call_args_list[0].args[1]
        self.assertEqual(params, {"league": 999, "season": 2025, "status": "FT"})

    def test_completed_history_keeps_csv_when_tail_call_fails(self):
        csv_history = [
            csv_entry(-101, NOW - timedelta(days=14), "Arsenal", "Chelsea", 501, 502),
        ]
        provider = ChallengeDataProvider("test-key", None)
        provider._football_get = Mock(return_value=None)

        def fake_stat_history(league_id, season, upcoming):
            return csv_history if season == 2025 else None

        with patch("challenge_15k.fetch_stat_history", side_effect=fake_stat_history):
            result = provider.completed_history(39, 2025, [])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["fixture"]["id"], -101)

    def test_thin_history_gets_previous_season_prepended(self):
        current = [csv_entry(-101, NOW - timedelta(days=14), "Arsenal", "Chelsea", 501, 502)]
        previous = [
            csv_entry(-201, NOW - timedelta(days=200), "Arsenal", "Fulham", 501, 505),
            csv_entry(-202, NOW - timedelta(days=193), "Fulham", "Arsenal", 505, 501),
        ]
        provider = ChallengeDataProvider("test-key", None)
        provider._football_get = Mock(return_value=None)

        def fake_stat_history(league_id, season, upcoming):
            return current if season == 2025 else previous if season == 2024 else None

        with patch("challenge_15k.fetch_stat_history", side_effect=fake_stat_history):
            result = provider.completed_history(39, 2025, [])

        self.assertEqual(len(result), 3)
        self.assertEqual([row["fixture"]["id"] for row in result], [-201, -202, -101])

    def test_full_history_skips_previous_season(self):
        fat = [
            csv_entry(-1000 - index, NOW - timedelta(days=400 + index), "Arsenal", "Chelsea", 501, 502)
            for index in range(230)
        ]
        provider = ChallengeDataProvider("test-key", None)
        provider._football_get = Mock(return_value=None)
        calls = []

        def fake_stat_history(league_id, season, upcoming):
            calls.append(season)
            return fat if season == 2025 else None

        with patch("challenge_15k.fetch_stat_history", side_effect=fake_stat_history):
            result = provider.completed_history(39, 2025, [])

        self.assertEqual(len(result), 230)
        self.assertEqual(calls, [2025])  # kein Vorsaison-Abruf

    def test_tail_window_constant_is_sane(self):
        self.assertGreaterEqual(API_TAIL_DAYS, 3)
        self.assertLessEqual(API_TAIL_DAYS, 14)


if __name__ == "__main__":
    unittest.main()
