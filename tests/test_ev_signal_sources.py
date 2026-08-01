"""Signalquellen für den Wett-Check: Tennis- und E-Sport-Adapter."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ev_signal_sources import esports_signals, list_signals, tennis_signals

TENNIS_SCHEMA = """
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_date TEXT, tour TEXT, tournament TEXT,
    player_a TEXT, player_b TEXT, p_cal REAL, settled INTEGER DEFAULT 0
);
"""

ESPORTS_SCHEMA = """
CREATE TABLE esports_shadow_predictions (
    match_id TEXT, logged_at TEXT, game TEXT, team1 TEXT, team2 TEXT,
    selection TEXT, status TEXT, model_probability REAL
);
"""


def _tennis_db(rows, tmp: Path) -> Path:
    db = tmp / "tennis_shadow.db"
    conn = sqlite3.connect(db)
    conn.execute(TENNIS_SCHEMA)
    conn.executemany(
        "INSERT INTO predictions (match_date, tour, tournament, player_a,"
        " player_b, p_cal, settled) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def _esports_db(rows, tmp: Path) -> Path:
    db = tmp / "esports_shadow.db"
    conn = sqlite3.connect(db)
    conn.execute(ESPORTS_SCHEMA)
    conn.executemany(
        "INSERT INTO esports_shadow_predictions (match_id, logged_at, game,"
        " team1, team2, selection, status, model_probability)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


class TennisSignalTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_open_future_prediction_yields_both_sides(self):
        db = _tennis_db(
            [("2099-01-01", "ATP", "Test Open", "Spieler A", "Spieler B", 0.6, 0)],
            self.tmp,
        )
        signals = tennis_signals(db_path=db, today="2099-01-01")

        self.assertEqual(len(signals), 2)
        side_a = next(s for s in signals if s.key.endswith("-A"))
        side_b = next(s for s in signals if s.key.endswith("-B"))
        self.assertAlmostEqual(side_a.probability, 0.6)
        self.assertAlmostEqual(side_b.probability, 0.4)
        self.assertIn("Sieg Spieler A", side_a.label)
        self.assertIn("Sieg Spieler B", side_b.label)
        self.assertIn("Test Open", side_a.detail)

    def test_settled_and_past_matches_are_excluded(self):
        db = _tennis_db(
            [
                ("2099-01-01", "ATP", "T", "A", "B", 0.6, 1),      # settled
                ("2020-01-01", "ATP", "T", "C", "D", 0.6, 0),      # vergangen
            ],
            self.tmp,
        )
        self.assertEqual(tennis_signals(db_path=db, today="2099-01-01"), [])

    def test_invalid_probabilities_are_excluded(self):
        db = _tennis_db(
            [
                ("2099-01-01", "ATP", "T", "A", "B", None, 0),
                ("2099-01-01", "ATP", "T", "C", "D", 0.0, 0),
                ("2099-01-01", "ATP", "T", "E", "F", 1.0, 0),
            ],
            self.tmp,
        )
        self.assertEqual(tennis_signals(db_path=db, today="2099-01-01"), [])

    def test_missing_db_returns_empty(self):
        self.assertEqual(
            tennis_signals(db_path=self.tmp / "fehlt.db", today="2099-01-01"),
            [],
        )


class EsportsSignalTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_upcoming_percent_probability_is_converted(self):
        db = _esports_db(
            [("m1", "2026-07-31", "LOL", "Team Eins", "Team Zwei",
              "Team Eins", "upcoming", 55.27)],
            self.tmp,
        )
        signals = esports_signals(db_path=db)

        self.assertEqual(len(signals), 1)
        self.assertAlmostEqual(signals[0].probability, 0.5527)
        self.assertIn("LOL", signals[0].label)
        self.assertIn("Sieg Team Eins", signals[0].label)

    def test_fraction_probability_is_accepted(self):
        db = _esports_db(
            [("m2", "2026-07-31", "DOTA2", "A", "B", "A", "upcoming", 0.61)],
            self.tmp,
        )
        signals = esports_signals(db_path=db)
        self.assertEqual(len(signals), 1)
        self.assertAlmostEqual(signals[0].probability, 0.61)

    def test_non_upcoming_and_invalid_are_excluded(self):
        db = _esports_db(
            [
                ("m3", "2026-07-31", "LOL", "A", "B", "A", "settled", 60.0),
                ("m4", "2026-07-31", "LOL", "C", "D", "C", "upcoming", None),
                ("m5", "2026-07-31", "LOL", "E", "F", "E", "upcoming", 105.0),
            ],
            self.tmp,
        )
        self.assertEqual(esports_signals(db_path=db), [])

    def test_missing_db_returns_empty(self):
        self.assertEqual(esports_signals(db_path=self.tmp / "fehlt.db"), [])


class ListSignalsTests(unittest.TestCase):
    def test_merges_tennis_and_esports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            tennis_db = _tennis_db(
                [("2099-01-01", "WTA", "T", "A", "B", 0.55, 0)], tmp
            )
            esports_db = _esports_db(
                [("m1", "2026-07-31", "CS2", "X", "Y", "X", "upcoming", 66.0)],
                tmp,
            )
            signals = list_signals(
                tennis_db=tennis_db, esports_db=esports_db, today="2099-01-01"
            )
        # 2 Tennis-Seiten + 1 E-Sport
        self.assertEqual(len(signals), 3)
        self.assertEqual(len({s.key for s in signals}), 3)


if __name__ == "__main__":
    unittest.main()
