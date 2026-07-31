"""Freemode-Freischaltung und Rotkarten-Shadow-Logger."""

from __future__ import annotations

import unittest

from football_recommendations import red_card_candidate
from redcard_signal_log import (
    _connect,
    log_signal,
    settle_open_signals,
    settlement_stats,
)


def _entry(
    *,
    quality: str = "MEDIUM",
    p_opponent: float = 0.60,
    p_red: float = 0.15,
    p_none: float = 0.25,
    score: str = "1-0",
):
    return {
        "card": {
            "match": {
                "fixture": {"id": 424242},
                "league": {"name": "Testliga"},
            },
            "minute": 40,
            "team": "Heimteam",
        },
        "home": "Heimteam",
        "away": "Auswärtsteam",
        "score": score,
        "prediction": {
            "next_goal_by_opponent": p_opponent,
            "next_goal_by_red_team": p_red,
            "no_more_goals": p_none,
            "data_quality": quality,
            "too_late_for_signal": False,
        },
        "prediction_minute": 60,
        "red_side": "home",
        "fixture_red_card_count": 1,
        "error": None,
    }


class FreemodeTests(unittest.TestCase):
    def test_model_vetoes_block_without_freemode(self):
        candidate = red_card_candidate(
            _entry(quality="LOW", p_opponent=0.40),
            snapshot_age_seconds=30,
            freemode=False,
        )

        self.assertFalse(candidate.model_ready)
        self.assertTrue(candidate.blockers)

    def test_freemode_turns_model_vetoes_into_evidence(self):
        candidate = red_card_candidate(
            _entry(quality="LOW", p_opponent=0.40),
            snapshot_age_seconds=30,
            freemode=True,
        )

        self.assertTrue(candidate.model_ready)
        self.assertFalse(candidate.blockers)
        self.assertTrue(
            any("Modell-Warnung" in line for line in candidate.evidence)
        )

    def test_freemode_keeps_hard_data_gates(self):
        candidate = red_card_candidate(
            _entry(score="n/a"),
            snapshot_age_seconds=30,
            freemode=True,
        )
        # Spielstand fehlt nicht als hartes Gate im red_card_candidate,
        # aber zu alter Snapshot bleibt hart:
        stale = red_card_candidate(
            _entry(),
            snapshot_age_seconds=999,
            freemode=True,
        )

        self.assertFalse(stale.model_ready)
        self.assertTrue(
            any("älter als zwei Minuten" in b for b in stale.blockers)
        )

    def test_freemode_still_blocks_when_no_probability(self):
        entry = _entry()
        entry["prediction"] = {
            "next_goal_by_opponent": None,
            "next_goal_by_red_team": None,
            "no_more_goals": None,
            "data_quality": "MEDIUM",
            "too_late_for_signal": False,
        }
        candidate = red_card_candidate(
            entry, snapshot_age_seconds=30, freemode=True
        )

        self.assertFalse(candidate.model_ready)


class RedCardSignalLogTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path

        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "signals.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_log_signal_writes_and_deduplicates(self):
        entry = _entry()

        self.assertTrue(log_signal(entry, db_path=self.db))
        self.assertFalse(log_signal(entry, db_path=self.db))  # Duplikat

        conn = _connect(self.db)
        row = conn.execute("SELECT * FROM signals").fetchone()
        conn.close()
        self.assertEqual(row["fixture_id"], 424242)
        self.assertEqual(row["minute"], 60)
        self.assertEqual(row["status"], "open")
        self.assertAlmostEqual(row["p_opponent"], 0.60)

    def test_log_signal_rejects_incomplete_entries(self):
        self.assertFalse(log_signal({"error": "kaputt"}, db_path=self.db))
        self.assertFalse(log_signal({}, db_path=self.db))
        too_late = _entry()
        too_late["prediction"]["too_late_for_signal"] = True
        self.assertFalse(log_signal(too_late, db_path=self.db))

    def test_settle_marks_opponent_goal_and_brier(self):
        log_signal(_entry(), db_path=self.db)

        class _FakeAPI:
            def _request(self, endpoint, params):
                if endpoint == "fixtures":
                    return {
                        "response": [
                            {
                                "fixture": {"status": {"short": "FT"}},
                                "teams": {
                                    "home": {"id": 10},
                                    "away": {"id": 20},
                                },
                            }
                        ]
                    }
                if endpoint == "events":
                    return {
                        "response": [
                            {
                                "type": "Goal",
                                "time": {"elapsed": 75},
                                "team": {"id": 20},
                            }
                        ]
                    }
                return {"response": []}

        result = settle_open_signals(_FakeAPI(), sleep_seconds=0, db_path=self.db)

        self.assertEqual(result["settled"], 1)
        stats = settlement_stats(db_path=self.db)
        self.assertEqual(stats["settled"], 1)
        # Auswärtsteam (11 Mann, Heim hatte Rot) traf -> opponent.
        self.assertEqual(stats["by_outcome"]["opponent"]["n"], 1)
        # Top-Auswahl war opponent (0.60) -> Treffer.
        self.assertEqual(stats["top_pick_hit_rate"], 1.0)

    def test_settle_no_goal_outcome(self):
        log_signal(_entry(), db_path=self.db)

        class _FakeAPI:
            def _request(self, endpoint, params):
                if endpoint == "fixtures":
                    return {
                        "response": [
                            {
                                "fixture": {"status": {"short": "FT"}},
                                "teams": {
                                    "home": {"id": 10},
                                    "away": {"id": 20},
                                },
                            }
                        ]
                    }
                return {"response": []}

        result = settle_open_signals(_FakeAPI(), sleep_seconds=0, db_path=self.db)

        self.assertEqual(result["settled"], 1)
        stats = settlement_stats(db_path=self.db)
        self.assertEqual(stats["by_outcome"]["no_goal"]["n"], 1)
        self.assertEqual(stats["top_pick_hit_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
