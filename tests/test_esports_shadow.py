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

    def test_live_matches_are_never_logged(self):
        # E1: a score-conditioned record is a different product and must
        # not contaminate the pre-match shadow
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            live = _match()
            live["status"] = "live"
            live["team1_score"] = 1

            self.assertEqual(log.log_predictions([live]), 0)
            summary = log.summary()
            self.assertEqual(summary["predictions"], 0)
            self.assertEqual(summary["live_records"], 0)

    def test_upcoming_match_requires_verified_zero_zero_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            missing = _match(57)
            missing.pop("team1_score")
            started = _match(58)
            started["team2_score"] = 1

            self.assertEqual(log.log_predictions([missing, started]), 0)
            self.assertEqual(log.summary()["predictions"], 0)

    def test_summary_ignores_legacy_live_rows(self):
        # rows written before the E1 fix stay in the table but leave the
        # pre-match rates untouched
        import sqlite3
        from contextlib import closing

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "shadow.db"
            log = EsportsShadowLog(db)
            log.log_predictions([_match(55)])
            with closing(sqlite3.connect(db)) as con:
                con.execute(
                    """
                    INSERT INTO esports_shadow_predictions (
                        match_id, logged_at, game, team1, team2,
                        selected_team_id, selection, status, series_type,
                        score1, score2, elo1, elo2, model_probability,
                        risk_adjusted_probability, minimum_odds,
                        settled, winner_team_id, hit, settled_at
                    ) VALUES (
                        999, '2026-07-31T12:00:00+00:00', 'CS2', 'X', 'Y',
                        7, 'X', 'live', 3, 2, 0, 1600, 1400, 95.0,
                        80.0, 1.25, 1, 7, 1, '2026-07-31T14:00:00+00:00'
                    )
                    """
                )
                con.commit()
            summary = log.summary()
            self.assertEqual(summary["predictions"], 1)      # not 2
            self.assertEqual(summary["live_records"], 1)     # visible, but outside
            self.assertIsNone(summary["hit_rate"])           # legacy live hit ignored

    def test_age_alone_never_voids_an_unresolved_row(self):
        import sqlite3
        from contextlib import closing

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "shadow.db"
            log = EsportsShadowLog(db)
            log.log_predictions([_match()])
            with closing(sqlite3.connect(db)) as con:
                con.execute(
                    "UPDATE esports_shadow_predictions "
                    "SET logged_at = '2026-01-01T00:00:00+00:00'"
                )
                con.commit()

            self.assertEqual(log.settle_open(lambda _mid: None, max_calls=10), 0)
            summary = log.summary()
            self.assertEqual(summary["open"], 1)
            self.assertEqual(summary["settled"], 0)
            self.assertEqual(summary["voided"], 0)
            self.assertIsNone(summary["hit_rate"])

    def test_explicit_provider_cancellation_is_voided(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            log.log_predictions([_match()])

            self.assertEqual(
                log.settle_open(
                    lambda _mid: {"void": True, "status": "canceled"},
                    max_calls=10,
                ),
                0,
            )
            summary = log.summary()
            self.assertEqual(summary["open"], 0)
            self.assertEqual(summary["voided"], 1)

    def test_unresolved_rows_rotate_instead_of_starving_newer_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            log.log_predictions([_match(55), _match(56)])
            checked = []

            def missing(match_id):
                checked.append(match_id)
                return None

            log.settle_open(missing, max_calls=1)
            log.settle_open(missing, max_calls=1)
            self.assertEqual(checked, [55, 56])

    def test_young_shadow_sample_is_not_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            log.log_predictions([_match()])
            status = log.release_status()
            self.assertFalse(status["ready"])
            self.assertEqual(status["required"], 100)


if __name__ == "__main__":
    unittest.main()
