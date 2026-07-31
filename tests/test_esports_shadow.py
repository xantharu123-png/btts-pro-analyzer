import tempfile
import unittest
from pathlib import Path

from esports_shadow import EsportsShadowLog


def _history(team_id, opponent_id, wins, losses, start_id):
    total = wins + losses
    return [
        {
            "match_id": start_id + index,
            "begin_at": f"2026-07-{1 + index:02d}T12:00:00Z",
            "opponent_id": opponent_id,
            "won": (index * wins) % total < wins,
            "number_of_games": 3,
        }
        for index in range(total)
    ]


def _match(match_id=55, team1_wins=15, team2_wins=8):
    return {
        "id": match_id,
        "game": "CS2",
        "team1": "Alpha",
        "team2": "Beta",
        "team1_id": 7,
        "team2_id": 8,
        "team1_score": 0,
        "team2_score": 0,
        "series_type": 3,
        "status": "upcoming",
        "team1_stats": {"matches": 20, "wins": team1_wins},
        "team2_stats": {"matches": 20, "wins": team2_wins},
        "team1_history": _history(7, 100, team1_wins, 20 - team1_wins, 1000),
        "team2_history": _history(8, 100, team2_wins, 20 - team2_wins, 2000),
    }


class EsportsShadowLogTests(unittest.TestCase):
    def test_logs_ready_candidates_once_per_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")

            self.assertEqual(log.log_predictions([_match()]), 1)
            # First observation counts: a second scan must not overwrite.
            self.assertEqual(log.log_predictions([_match()]), 0)

            summary = log.summary()
            self.assertEqual(summary["predictions"], 1)
            self.assertEqual(summary["open"], 1)
            self.assertIsNone(summary["hit_rate"])

    def test_skips_matches_without_enough_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            thin = _match()
            thin["team1_history"] = thin["team1_history"][:10]

            self.assertEqual(log.log_predictions([thin]), 0)
            self.assertEqual(log.summary()["predictions"], 0)

    def test_settles_hits_and_misses_and_computes_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            log.log_predictions([_match(55), _match(56, team1_wins=6, team2_wins=14)])

            results = {
                55: {"winner_team_id": 7},   # Alpha was selected -> hit
                56: {"winner_team_id": 7},   # Beta was selected -> miss
            }
            settled = log.settle_open(results.get, max_calls=10)
            self.assertEqual(settled, 2)

            summary = log.summary()
            self.assertEqual(summary["settled"], 2)
            self.assertEqual(summary["hits"], 1)
            self.assertEqual(summary["hit_rate"], 50.0)
            self.assertIsNotNone(summary["avg_model_probability"])
            self.assertIsNotNone(summary["brier_score"])
            self.assertEqual(summary["open"], 0)

    def test_unfinished_results_stay_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            log.log_predictions([_match()])

            settled = log.settle_open(lambda _mid: None, max_calls=10)
            self.assertEqual(settled, 0)
            self.assertEqual(log.summary()["open"], 1)


if __name__ == "__main__":
    unittest.main()
