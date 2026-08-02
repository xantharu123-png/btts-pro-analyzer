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
    player_a TEXT, player_b TEXT, p_cal REAL, settled INTEGER DEFAULT 0,
    verdict TEXT DEFAULT 'WETTE', recommended_side TEXT DEFAULT 'A'
);
"""

ESPORTS_SCHEMA = """
CREATE TABLE esports_shadow_predictions (
    match_id TEXT, logged_at TEXT, game TEXT, team1 TEXT, team2 TEXT,
    selection TEXT, status TEXT, model_probability REAL,
    risk_adjusted_probability REAL, settled INTEGER DEFAULT 0,
    hit INTEGER
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
        " team1, team2, selection, status, model_probability,"
        " risk_adjusted_probability)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [tuple(row) + (row[-1],) for row in rows],
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

    def test_open_released_prediction_yields_only_recommended_side(self):
        db = _tennis_db(
            [("2099-01-01", "ATP", "Test Open", "Spieler A", "Spieler B", 0.6, 0)],
            self.tmp,
        )
        signals = tennis_signals(db_path=db, today="2099-01-01")

        self.assertEqual(len(signals), 1)
        side_a = signals[0]
        self.assertAlmostEqual(side_a.probability, 0.6)
        self.assertIn("Sieg Spieler A", side_a.label)
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
        signals = esports_signals(db_path=db, require_released=False)

        self.assertEqual(len(signals), 1)
        self.assertAlmostEqual(signals[0].probability, 0.5527)
        self.assertIn("LOL", signals[0].label)
        self.assertIn("Sieg Team Eins", signals[0].label)

    def test_fraction_probability_is_accepted(self):
        db = _esports_db(
            [("m2", "2026-07-31", "DOTA2", "A", "B", "A", "upcoming", 0.61)],
            self.tmp,
        )
        signals = esports_signals(db_path=db, require_released=False)
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
        self.assertEqual(
            esports_signals(db_path=db, require_released=False),
            [],
        )

    def test_missing_db_returns_empty(self):
        self.assertEqual(esports_signals(db_path=self.tmp / "fehlt.db"), [])

    def test_young_shadow_is_hidden_from_automatic_signals(self):
        db = _esports_db(
            [("m1", "2026-07-31", "LOL", "A", "B", "A", "upcoming", 60.0)],
            self.tmp,
        )
        self.assertEqual(esports_signals(db_path=db), [])


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
                tennis_db=tennis_db,
                esports_db=esports_db,
                today="2099-01-01",
                require_esports_release=False,
            )
        # One released tennis side + one E-Sport signal.
        self.assertEqual(len(signals), 2)
        self.assertEqual(len({s.key for s in signals}), 2)


class FootballSignalTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name: str, signals: list, finished_at: str) -> None:
        import json

        (self.tmp / f"{name}.json").write_text(
            json.dumps({"finished_at": finished_at, "signals": signals}),
            encoding="utf-8",
        )

    def test_fresh_scans_become_signals(self):
        from datetime import datetime

        from ev_signal_sources import football_signals

        now = datetime.now().astimezone()
        self._write(
            "prematch",
            [
                {"home": "FC A", "away": "FC B", "league": "BL1",
                 "date": "2026-08-02", "market": "BTTS Ja", "p": 0.64},
            ],
            now.isoformat(),
        )
        self._write(
            "red_cards",
            [
                {"home": "FC C", "away": "FC D", "league": None,
                 "date": now.isoformat(), "market": "Nächstes Tor: FC D",
                 "p": 0.58},
            ],
            now.isoformat(),
        )

        signals = football_signals(jobs_dir=self.tmp, now=now)

        self.assertEqual(len(signals), 2)
        btts = next(s for s in signals if "BTTS" in s.label)
        self.assertIn("⚽ FC A vs FC B", btts.label)
        self.assertAlmostEqual(btts.probability, 0.64)
        self.assertIn("Fußball-Scan · BTTS", btts.detail)
        red = next(s for s in signals if "Nächstes Tor" in s.label)
        self.assertAlmostEqual(red.probability, 0.58)

    def test_stale_scans_are_excluded(self):
        from datetime import datetime, timedelta

        from ev_signal_sources import football_signals

        now = datetime.now().astimezone()
        old = (now - timedelta(hours=48)).isoformat()
        self._write(
            "prematch",
            [{"home": "A", "away": "B", "market": "BTTS Ja", "p": 0.6}],
            old,
        )
        self.assertEqual(football_signals(jobs_dir=self.tmp, now=now), [])

    def test_invalid_rows_are_skipped(self):
        from datetime import datetime

        from ev_signal_sources import football_signals

        now = datetime.now().astimezone()
        self._write(
            "prematch",
            [
                {"home": "A", "away": "B", "market": "BTTS Ja", "p": 0.0},
                {"home": "A", "away": "B", "market": "BTTS Ja", "p": 1.2},
                {"home": "A", "away": "B", "market": "BTTS Ja", "p": None},
                {"home": "", "away": "B", "market": "BTTS Ja", "p": 0.6},
                {"home": "A", "away": "B", "market": None, "p": 0.6},
                "kein dict",
                {"home": "Gut", "away": "Böse", "market": "BTTS Ja", "p": 0.61},
            ],
            now.isoformat(),
        )
        signals = football_signals(jobs_dir=self.tmp, now=now)
        self.assertEqual(len(signals), 1)
        self.assertIn("Gut vs Böse", signals[0].label)

    def test_live_source_appears_with_context(self):
        from datetime import datetime

        from ev_signal_sources import football_signals

        now = datetime.now().astimezone()
        self._write(
            "live",
            [
                {"home": "FC Live", "away": "FC Kurz",
                 "league": "PL", "date": now.isoformat(),
                 "market": "Live: Mindestens 1 weiteres Tor (Stand 1:0, 55')",
                 "p": 0.71},
            ],
            now.isoformat(),
        )
        signals = football_signals(jobs_dir=self.tmp, now=now)

        self.assertEqual(len(signals), 1)
        self.assertIn("FC Live vs FC Kurz", signals[0].label)
        self.assertIn("Stand 1:0", signals[0].label)
        self.assertIn("Fußball-Scan · Live", signals[0].detail)
        self.assertAlmostEqual(signals[0].probability, 0.71)

    def test_per_source_freshness_windows(self):
        from datetime import datetime, timedelta

        from ev_signal_sources import football_signals

        now = datetime.now().astimezone()
        row = {"home": "A", "away": "B", "market": "M", "p": 0.6}
        # Live 3h alt -> wertlos; Prematch 23h alt -> noch tragbar
        self._write("live", [dict(row)], (now - timedelta(hours=3)).isoformat())
        self._write(
            "prematch", [dict(row)], (now - timedelta(hours=23)).isoformat()
        )

        signals = football_signals(jobs_dir=self.tmp, now=now)

        self.assertEqual(len(signals), 1)
        self.assertIn("BTTS", signals[0].detail)

    def test_missing_files_return_empty(self):
        from ev_signal_sources import football_signals

        self.assertEqual(football_signals(jobs_dir=self.tmp), [])


if __name__ == "__main__":
    unittest.main()
