import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import sqlite3

from esports_shadow import ESPORTS_MODEL_VERSION, EsportsShadowLog


def _history(team_id, opponent_id, wins, losses, start_id):
    total = wins + losses
    return [
        {
            "match_id": start_id + index,
            "begin_at": f"2026-07-{1 + index:02d}T12:00:00Z",
            "end_at": f"2026-07-{1 + index:02d}T14:00:00Z",
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
        "begin_at": "2099-08-01T18:00:00Z",
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

    def test_logged_elo_uses_the_same_causal_twenty_rows_as_the_candidate(self):
        from unittest.mock import patch

        from esports_elo import subgraph_ratings

        with tempfile.TemporaryDirectory() as tmp:
            log = EsportsShadowLog(Path(tmp) / "shadow.db")
            match = _match()
            match["team1_history"] = _history(7, 100, 18, 7, 3000)
            match["team2_history"] = _history(8, 100, 9, 16, 4000)

            with patch(
                "esports_shadow.subgraph_ratings",
                wraps=subgraph_ratings,
            ) as shadow_ratings:
                self.assertEqual(log.log_predictions([match]), 1)

            shadow_ratings.assert_called_once()
            history1, history2 = shadow_ratings.call_args.args[:2]
            self.assertEqual(
                [row["match_id"] for row in history1],
                list(range(3024, 3004, -1)),
            )
            self.assertEqual(
                [row["match_id"] for row in history2],
                list(range(4024, 4004, -1)),
            )

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
                55: {
                    "winner_team_id": 7,
                    "team1_id": 7,
                    "team2_id": 8,
                    "score1": 2,
                    "score2": 0,
                    "termination": "normal",
                },
                56: {
                    "winner_team_id": 7,
                    "team1_id": 7,
                    "team2_id": 8,
                    "score1": 2,
                    "score2": 1,
                    "termination": "normal",
                },
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

    def test_summary_never_mixes_an_old_prematch_model_version(self):
        import sqlite3
        from contextlib import closing

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "shadow.db"
            log = EsportsShadowLog(db)
            log.log_predictions([_match(55)])
            with closing(sqlite3.connect(db)) as con:
                con.execute(
                    "UPDATE esports_shadow_predictions "
                    "SET model_version='subgraph-elo-v2', settled=1, hit=1 "
                    "WHERE match_id=55"
                )
                con.commit()

            summary = log.summary()

            self.assertEqual(summary["predictions"], 0)
            self.assertEqual(summary["settled"], 0)
            self.assertEqual(summary["model_version"], ESPORTS_MODEL_VERSION)
            self.assertEqual(ESPORTS_MODEL_VERSION, "subgraph-elo-v3")
            self.assertEqual(log.release_status()["settled"], 0)
            self.assertEqual(log.summary("subgraph-elo-v2")["settled"], 1)

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
                    lambda _mid: {
                        "void": True,
                        "status": "canceled",
                        "termination": "cancelled",
                        "team1_id": 7,
                        "team2_id": 8,
                    },
                    max_calls=10,
                ),
                1,
            )
            summary = log.summary()
            self.assertEqual(summary["open"], 0)
            self.assertEqual(summary["voided"], 1)

    def test_legacy_schema_is_migrated_without_fabricating_result_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "shadow.db"
            with closing(sqlite3.connect(db)) as connection:
                connection.execute(
                    """
                    CREATE TABLE esports_shadow_predictions (
                        match_id INTEGER PRIMARY KEY, logged_at TEXT NOT NULL,
                        game TEXT NOT NULL, team1 TEXT NOT NULL, team2 TEXT NOT NULL,
                        selected_team_id INTEGER NOT NULL, selection TEXT NOT NULL,
                        status TEXT NOT NULL, series_type INTEGER NOT NULL,
                        score1 INTEGER NOT NULL, score2 INTEGER NOT NULL,
                        elo1 REAL NOT NULL, elo2 REAL NOT NULL,
                        model_probability REAL NOT NULL,
                        risk_adjusted_probability REAL NOT NULL,
                        minimum_odds REAL NOT NULL, settled INTEGER NOT NULL DEFAULT 0,
                        winner_team_id INTEGER, hit INTEGER, settled_at TEXT
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO esports_shadow_predictions VALUES (
                        55, '2026-01-01T10:00:00+00:00', 'CS2', 'Alpha', 'Beta',
                        7, 'Alpha', 'upcoming', 3, 0, 0, 1600, 1500, 60, 55,
                        1.8, 1, 7, 1, '2026-01-01T12:00:00+00:00'
                    )
                    """
                )
                connection.commit()

            EsportsShadowLog(db)

            with closing(sqlite3.connect(db)) as connection:
                columns = {
                    row[1] for row in connection.execute(
                        "PRAGMA table_info(esports_shadow_predictions)"
                    )
                }
                migrated = connection.execute(
                    "SELECT team1_id, team2_id, termination, final_score1, final_score2 "
                    "FROM esports_shadow_predictions WHERE match_id=55"
                ).fetchone()
            self.assertTrue(
                {"team1_id", "team2_id", "termination", "final_score1", "final_score2"}
                <= columns
            )
            self.assertEqual(migrated, (None, None, None, None, None))

    def test_overlapping_settlers_cannot_overwrite_a_terminal_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "shadow.db"
            first = EsportsShadowLog(db)
            second = EsportsShadowLog(db)
            first.log_predictions([_match()])
            alpha_win = {
                "winner_team_id": 7,
                "team1_id": 7,
                "team2_id": 8,
                "score1": 2,
                "score2": 0,
                "termination": "normal",
            }
            beta_win = {
                "winner_team_id": 8,
                "team1_id": 7,
                "team2_id": 8,
                "score1": 1,
                "score2": 2,
                "termination": "normal",
            }

            def racing_fetcher(_match_id):
                self.assertEqual(second.settle_open(lambda _mid: alpha_win), 1)
                return beta_win

            self.assertEqual(first.settle_open(racing_fetcher), 0)
            with closing(sqlite3.connect(db)) as connection:
                terminal = connection.execute(
                    "SELECT winner_team_id, final_score1, final_score2, termination "
                    "FROM esports_shadow_predictions WHERE match_id=55"
                ).fetchone()
            self.assertEqual(terminal, (7, 2, 0, "normal"))

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
            self.assertEqual(status["required"], 300)
            self.assertFalse(status["price_evidence_ready"])


if __name__ == "__main__":
    unittest.main()
