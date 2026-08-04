"""Freemode-Freischaltung und Rotkarten-Shadow-Logger."""

from __future__ import annotations

import unittest

from football_recommendations import red_card_candidate
from redcard_signal_log import (
    RED_CARD_POLICY_VERSION,
    _first_goal_after,
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

    def test_freemode_keeps_model_vetoes_as_blockers(self):
        candidate = red_card_candidate(
            _entry(quality="LOW", p_opponent=0.40),
            snapshot_age_seconds=30,
            freemode=True,
        )

        self.assertFalse(candidate.model_ready)
        self.assertTrue(candidate.blockers)
        self.assertTrue(
            any("Research-Hinweis" in line for line in candidate.evidence)
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

    def test_log_signal_requires_complete_normalized_probabilities(self):
        partial = _entry()
        partial["prediction"]["p_no_goal"] = None
        partial["prediction"]["no_more_goals"] = None
        self.assertFalse(log_signal(partial, db_path=self.db))

        invalid_sum = _entry(p_opponent=0.60, p_red=0.15, p_none=0.10)
        self.assertFalse(log_signal(invalid_sum, db_path=self.db))

        infinite = _entry(p_opponent=float("inf"))
        self.assertFalse(log_signal(infinite, db_path=self.db))

    def test_only_first_snapshot_per_fixture_is_logged(self):
        first = _entry()
        later = _entry()
        later["prediction_minute"] = 70
        self.assertTrue(log_signal(first, db_path=self.db))
        self.assertFalse(log_signal(later, db_path=self.db))

    def test_statistics_exclude_legacy_model_generations(self):
        from red_card_impact_predictor import RED_CARD_MODEL_VERSION

        self.assertTrue(log_signal(_entry(), db_path=self.db))
        conn = _connect(self.db)
        conn.execute(
            "UPDATE signals SET status='settled', outcome='opponent', brier=0.1, "
            "model_version='legacy-model', policy_version='legacy-policy'"
        )
        conn.commit()
        conn.close()

        stats = settlement_stats(db_path=self.db)

        self.assertEqual(stats["settled"], 0)
        self.assertEqual(stats["model_version"], RED_CARD_MODEL_VERSION)
        self.assertEqual(stats["policy_version"], RED_CARD_POLICY_VERSION)

    def test_stoppage_extra_orders_goals_chronologically(self):
        first = _first_goal_after(
            [
                {
                    "type": "Goal",
                    "time": {"elapsed": 90, "extra": 3},
                    "team": {"id": 20},
                },
                {
                    "type": "Goal",
                    "time": {"elapsed": 90, "extra": 1},
                    "team": {"id": 10},
                },
            ],
            90,
            "FT",
        )
        self.assertEqual(first, (91, 10))

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


class RedCardHorizonSettlementTests(unittest.TestCase):
    """Modell-Horizont: Verlängerung und Elfmeterschießen zählen nicht
    als Outcome — das Modell endet bei der regulären Spielzeit (93')."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        self._tmp = tempfile.TemporaryDirectory()
        self.db = Path(self._tmp.name) / "signals.db"

    def tearDown(self):
        self._tmp.cleanup()

    def _settle_with(self, status, events):
        log_signal(_entry(), db_path=self.db)

        class _FakeAPI:
            def _request(self, endpoint, params):
                if endpoint == "fixtures":
                    return {
                        "response": [
                            {
                                "fixture": {"status": {"short": status}},
                                "teams": {
                                    "home": {"id": 10},
                                    "away": {"id": 20},
                                },
                            }
                        ]
                    }
                if endpoint == "events":
                    return {"response": events}
                return {"response": []}

        result = settle_open_signals(_FakeAPI(), sleep_seconds=0, db_path=self.db)
        self.assertEqual(result["settled"], 1)
        return settlement_stats(db_path=self.db)

    def test_extra_time_goal_does_not_count(self):
        stats = self._settle_with(
            "AET",
            [{"type": "Goal", "time": {"elapsed": 95}, "team": {"id": 20}}],
        )
        self.assertEqual(stats["by_outcome"]["no_goal"]["n"], 1)

    def test_stoppage_goal_counts_when_ft(self):
        stats = self._settle_with(
            "FT",
            [{"type": "Goal", "time": {"elapsed": 92}, "team": {"id": 20}}],
        )
        self.assertEqual(stats["by_outcome"]["opponent"]["n"], 1)

    def test_stoppage_window_goal_ignored_when_aet(self):
        # elapsed 92 bei AET ist bereits Verlängerung, nicht Nachspielzeit
        stats = self._settle_with(
            "AET",
            [{"type": "Goal", "time": {"elapsed": 92}, "team": {"id": 20}}],
        )
        self.assertEqual(stats["by_outcome"]["no_goal"]["n"], 1)

    def test_shootout_goals_ignored(self):
        stats = self._settle_with(
            "PEN",
            [
                {"type": "Goal", "time": {"elapsed": 121}, "team": {"id": 20}},
                {"type": "Goal", "time": {"elapsed": None}, "team": {"id": 10}},
            ],
        )
        self.assertEqual(stats["by_outcome"]["no_goal"]["n"], 1)

    def test_regular_goal_counts_when_aet(self):
        stats = self._settle_with(
            "AET",
            [{"type": "Goal", "time": {"elapsed": 88}, "team": {"id": 20}}],
        )
        self.assertEqual(stats["by_outcome"]["opponent"]["n"], 1)

    def test_explicit_regulation_stoppage_goal_counts_when_aet(self):
        stats = self._settle_with(
            "AET",
            [
                {
                    "type": "Goal",
                    "time": {"elapsed": 90, "extra": 2},
                    "team": {"id": 20},
                }
            ],
        )
        self.assertEqual(stats["by_outcome"]["opponent"]["n"], 1)


class RedCardBotWiringTests(unittest.TestCase):
    """Der Telegram-Alert muss die Kartenminute an den Predictor
    durchreichen — sonst sind Fatigue-/Schock-Layer inaktiv."""

    def test_alert_passes_red_card_minute(self):
        from unittest.mock import patch

        from red_card_bot import RedCardBotEnhanced

        bot = RedCardBotEnhanced(
            api_key="test-key",
            telegram_token="token",
            telegram_chat_id="chat",
        )

        captured = {}

        class _FakePredictor:
            def predict(self, **kwargs):
                captured.update(kwargs)
                return {"prediction": True}

            def format_prediction(
                self, prediction, home, away, red_card_minute=None
            ):
                return "Modellnachricht"

        bot.predictor = _FakePredictor()
        card_info = {
            "player": "Testspieler",
            "team": "Heim",
            "team_id": 10,
            "minute": 55,
            "match": {
                "fixture": {"id": 7, "status": {"elapsed": 58}},
                "teams": {
                    "home": {"id": 10, "name": "Heim"},
                    "away": {"id": 20, "name": "Gast"},
                },
                "goals": {"home": 1, "away": 0},
                "league": {"name": "Liga", "country": "Land"},
            },
        }
        with patch("red_card_bot.requests.post") as post:
            post.return_value.status_code = 200
            ok = bot.send_telegram_alert_with_stats(
                card_info, fetch_live_stats=False
            )

        self.assertTrue(ok)
        self.assertEqual(captured.get("red_card_minute"), 55)
        self.assertEqual(captured.get("minute"), 58)


if __name__ == "__main__":
    unittest.main()
