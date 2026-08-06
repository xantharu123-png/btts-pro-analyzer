"""Signalquellen für den Wett-Check: Tennis- und E-Sport-Adapter."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from betting_math import BETTING_POLICY_VERSION
from esports_shadow import ESPORTS_MODEL_VERSION
from ev_signal_sources import (
    AUTOMATED_SELECTION_POLICY_VERSION,
    AUTOMATED_WETTFINDER_VERSION,
    automated_wettfinder_signals,
    automated_wettfinder_status,
    esports_signals,
    list_signals,
    tennis_model_signals,
    tennis_signals,
)
from tennis.predict import WINNER_PROBABILITY_HAIRCUT
from tennis.shadow import TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION

TENNIS_SCHEMA = """
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_date TEXT, tour TEXT, tournament TEXT,
    player_a TEXT, player_b TEXT, p_cal REAL, settled INTEGER DEFAULT 0,
    verdict TEXT DEFAULT 'WETTE', recommended_side TEXT DEFAULT 'A',
    scheduled_start_utc TEXT, policy_version TEXT,
    gates_json TEXT, model_version TEXT
);
"""

ESPORTS_SCHEMA = """
CREATE TABLE esports_shadow_predictions (
    match_id TEXT, logged_at TEXT, game TEXT, team1 TEXT, team2 TEXT,
    selection TEXT, status TEXT, model_probability REAL,
    risk_adjusted_probability REAL, settled INTEGER DEFAULT 0,
    hit INTEGER, scheduled_at TEXT, model_version TEXT
);
"""


def _tennis_db(rows, tmp: Path) -> Path:
    db = tmp / "tennis_shadow.db"
    conn = sqlite3.connect(db)
    conn.execute(TENNIS_SCHEMA)
    conn.executemany(
        "INSERT INTO predictions (match_date, tour, tournament, player_a,"
        " player_b, p_cal, settled, scheduled_start_utc, policy_version,"
        " model_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            tuple(row)
            + (
                f"{row[0]}T23:59:59Z",
                TENNIS_POLICY_VERSION,
                TENNIS_MODEL_VERSION,
            )
            for row in rows
        ],
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
        " risk_adjusted_probability, scheduled_at, model_version)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                (tuple(row) + (row[-1],) if len(row) == 8 else tuple(row))
                + ("2099-01-01T12:00:00+00:00", ESPORTS_MODEL_VERSION)
            )
            for row in rows
        ],
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
        self.assertAlmostEqual(
            side_a.probability_haircut,
            WINNER_PROBABILITY_HAIRCUT,
        )
        self.assertEqual(side_a.evidence_stage, "SHADOW")
        self.assertEqual(side_a.policy_version, TENNIS_POLICY_VERSION)
        self.assertIn("Sieg Spieler A", side_a.label)
        self.assertIn("Test Open", side_a.detail)
        self.assertEqual(side_a.sport, "Tennis")
        self.assertEqual(side_a.event_label, "Spieler A vs Spieler B")
        self.assertEqual(side_a.market, "Match Winner")
        self.assertEqual(side_a.selection, "Sieg Spieler A")

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

    def test_old_tennis_price_policy_is_excluded(self):
        db = _tennis_db(
            [("2099-01-01", "ATP", "Test Open", "A", "B", 0.60, 0)],
            self.tmp,
        )
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "UPDATE predictions SET policy_version='legacy-edge-policy'"
            )
            conn.commit()
        finally:
            conn.close()

        self.assertEqual(
            tennis_signals(db_path=db, today="2099-01-01"),
            [],
        )

    def test_old_tennis_model_is_excluded_from_price_signals(self):
        db = _tennis_db(
            [("2099-01-01", "ATP", "Test Open", "A", "B", 0.60, 0)],
            self.tmp,
        )
        conn = sqlite3.connect(db)
        try:
            conn.execute("UPDATE predictions SET model_version='legacy-model'")
            conn.commit()
        finally:
            conn.close()

        self.assertEqual(
            tennis_signals(db_path=db, today="2099-01-01"),
            [],
        )

    def test_started_match_is_excluded_from_wett_check(self):
        db = _tennis_db(
            [("2099-01-01", "ATP", "T", "A", "B", 0.6, 0)],
            self.tmp,
        )
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "UPDATE predictions SET scheduled_start_utc=?",
                ("2099-01-01T18:30:00Z",),
            )
            conn.commit()
        finally:
            conn.close()
        signals = tennis_signals(
            db_path=db,
            today="2099-01-01",
            now=datetime(2099, 1, 1, 18, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(signals, [])

    def test_model_signal_chooses_the_more_likely_side_without_price(self):
        import json

        db = _tennis_db(
            [("2099-01-01", "ATP", "T", "A", "B", 0.62, 0)],
            self.tmp,
        )
        connection = sqlite3.connect(db)
        try:
            connection.execute(
                """
                UPDATE predictions
                SET gates_json=?, model_version=?,
                    verdict='WETTE', recommended_side='B'
                """,
                (
                    json.dumps(
                        {
                            "Belag": {"passed": True},
                            "Aufschlag-Daten": {"passed": True},
                            "Quote/Risiko-EV": {"passed": True},
                        }
                    ),
                    TENNIS_MODEL_VERSION,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        signals = tennis_model_signals(
            db_path=db,
            today="2099-01-01",
        )

        self.assertEqual(len(signals), 1)
        self.assertIn("Sieg A", signals[0].label)
        self.assertNotIn("Sieg B", signals[0].label)
        self.assertEqual(signals[0].source, "tennis_model")
        self.assertIn("quotenfrei", signals[0].detail)
        self.assertEqual(signals[0].event_label, "A vs B")
        self.assertEqual(signals[0].selection, "Sieg A")

    def test_model_signal_requires_every_non_price_gate(self):
        import json

        db = _tennis_db(
            [("2099-01-01", "ATP", "T", "A", "B", 0.62, 0)],
            self.tmp,
        )
        connection = sqlite3.connect(db)
        try:
            connection.execute(
                "UPDATE predictions SET gates_json=?, model_version=?",
                (
                    json.dumps(
                        {
                            "Belag": {"passed": True},
                            "Aufschlag-Daten": {"passed": False},
                        }
                    ),
                    TENNIS_MODEL_VERSION,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        self.assertEqual(
            tennis_model_signals(db_path=db, today="2099-01-01"),
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
        self.assertEqual(signals[0].sport, "E-Sport")
        self.assertEqual(
            signals[0].event_label,
            "LOL · Team Eins vs Team Zwei",
        )
        self.assertEqual(signals[0].market, "Match Winner")
        self.assertEqual(signals[0].selection, "Sieg Team Eins")

    def test_fraction_probability_is_accepted(self):
        db = _esports_db(
            [("m2", "2026-07-31", "DOTA2", "A", "B", "A", "upcoming", 0.61)],
            self.tmp,
        )
        signals = esports_signals(db_path=db, require_released=False)
        self.assertEqual(len(signals), 1)
        self.assertAlmostEqual(signals[0].probability, 0.61)

    def test_esports_signal_keeps_point_probability_and_model_haircut_separate(self):
        db = _esports_db(
            [
                (
                    "m3",
                    "2026-07-31",
                    "LOL",
                    "A",
                    "B",
                    "A",
                    "upcoming",
                    60.0,
                    52.0,
                )
            ],
            self.tmp,
        )

        signal = esports_signals(db_path=db, require_released=False)[0]

        self.assertAlmostEqual(signal.probability, 0.60)
        self.assertAlmostEqual(signal.probability_haircut, 0.08)
        self.assertEqual(signal.evidence_stage, "SHADOW")

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

    def test_started_esports_match_is_excluded(self):
        db = _esports_db(
            [("m6", "2026-07-31", "LOL", "A", "B", "A", "upcoming", 60.0)],
            self.tmp,
        )
        connection = sqlite3.connect(db)
        try:
            connection.execute(
                "UPDATE esports_shadow_predictions SET scheduled_at=?",
                ("2030-01-01T12:00:00+00:00",),
            )
            connection.commit()
        finally:
            connection.close()
        signals = esports_signals(
            db_path=db,
            require_released=False,
            now=datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(signals, [])

    def test_old_esports_model_is_excluded(self):
        db = _esports_db(
            [("m7", "2026-07-31", "LOL", "A", "B", "A", "upcoming", 60.0)],
            self.tmp,
        )
        connection = sqlite3.connect(db)
        try:
            connection.execute(
                "UPDATE esports_shadow_predictions SET model_version='legacy'"
            )
            connection.commit()
        finally:
            connection.close()
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
                automated_path=tmp / "missing-wettfinder.json",
            )
        # One tennis Shadow price signal + one E-Sport signal.
        self.assertEqual(len(signals), 2)
        self.assertEqual(len({s.key for s in signals}), 2)

    def test_fresh_automatic_artifact_replaces_raw_shadow_pool(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            minimum_odds = 1.99
            artifact = tmp / "wettfinder.json"
            artifact.write_text(
                json.dumps(
                    {
                        "version": AUTOMATED_WETTFINDER_VERSION,
                        "generated_at": "2030-01-01T10:00:00+00:00",
                        "betting_policy_version": BETTING_POLICY_VERSION,
                        "selection_policy_version": AUTOMATED_SELECTION_POLICY_VERSION,
                        "bookmaker_data_used": False,
                        "quote_required": False,
                        "target_search_date": "2030-01-01",
                        "football": {
                            "status": "completed",
                            "search_date": "2030-01-01",
                            "last_discovery_at": "2030-01-01T09:45:00+00:00",
                            "fixtures_found": 13,
                            "fixtures_modeled": 12,
                            "approved_candidates": 1,
                        },
                        "sources": {"football": {"discovery_scope": 51}},
                        "candidates": [
                            {
                                "key": "tennis-auto-1",
                                "label": "Tennis - A vs B - Sieg A",
                                "sport": "Tennis",
                                "event": "A vs B",
                                "market": "Match Winner",
                                "selection": "Sieg A",
                                "probability": 0.60,
                                "probability_haircut": 0.08,
                                "minimum_odds": minimum_odds,
                                "evidence_stage": "SHADOW",
                                "policy_version": TENNIS_POLICY_VERSION,
                                "scheduled_start": "2030-01-01T15:00:00+00:00",
                                "status": "PRICE_REQUIRED",
                                "detail": "Automatisch verdichtet",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            # 1.03 / 0.52 = 1.9807, first cent is 1.99.
            signals = automated_wettfinder_signals(
                artifact,
                now=datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc),
            )
            status = automated_wettfinder_status(
                artifact,
                now=datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc),
            )
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].source, "automated_wettfinder")
        self.assertEqual(signals[0].minimum_odds, 1.99)
        self.assertEqual(signals[0].event_label, "A vs B")
        self.assertEqual(signals[0].market, "Match Winner")
        self.assertEqual(signals[0].selection, "Sieg A")
        self.assertIsNotNone(status)
        self.assertEqual(status.discovery_scope, 51)
        self.assertEqual(status.fixtures_found, 13)
        self.assertEqual(status.fixtures_modeled, 12)
        self.assertEqual(status.approved_candidates, 1)

    def test_automatic_status_survives_an_empty_recommendation_list(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            artifact.write_text(
                json.dumps(
                    {
                        "version": AUTOMATED_WETTFINDER_VERSION,
                        "generated_at": "2030-01-01T10:00:00+00:00",
                        "betting_policy_version": BETTING_POLICY_VERSION,
                        "selection_policy_version": AUTOMATED_SELECTION_POLICY_VERSION,
                        "bookmaker_data_used": False,
                        "quote_required": False,
                        "target_search_date": "2030-01-01",
                        "football": {
                            "status": "completed",
                            "search_date": "2030-01-01",
                            "last_discovery_at": "2030-01-01T09:45:00+00:00",
                            "fixtures_found": 13,
                            "fixtures_modeled": 13,
                            "approved_candidates": 0,
                        },
                        "sources": {"football": {"discovery_scope": 51}},
                        "candidates": [],
                    }
                ),
                encoding="utf-8",
            )
            status = automated_wettfinder_status(
                artifact,
                now=datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc),
            )
        self.assertIsNotNone(status)
        self.assertEqual(status.discovery_scope, 51)
        self.assertEqual(status.fixtures_found, 13)
        self.assertEqual(status.fixtures_modeled, 13)
        self.assertEqual(status.candidate_count, 0)

    def test_automatic_artifact_rejects_stale_or_started_candidates(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            document = {
                "version": AUTOMATED_WETTFINDER_VERSION,
                "generated_at": "2030-01-01T06:00:00+00:00",
                "betting_policy_version": BETTING_POLICY_VERSION,
                "selection_policy_version": AUTOMATED_SELECTION_POLICY_VERSION,
                "bookmaker_data_used": False,
                "quote_required": False,
                "target_search_date": "2030-01-01",
                "candidates": [
                    {
                        "key": "tennis-auto-2",
                        "label": "Tennis - A vs B - Sieg A",
                        "probability": 0.60,
                        "probability_haircut": 0.08,
                        "minimum_odds": 1.99,
                        "evidence_stage": "SHADOW",
                        "policy_version": TENNIS_POLICY_VERSION,
                        "scheduled_start": "2030-01-01T15:00:00+00:00",
                        "status": "PRICE_REQUIRED",
                        "detail": "Automatisch verdichtet",
                    }
                ],
            }
            artifact.write_text(json.dumps(document), encoding="utf-8")
            now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)
            self.assertEqual(
                automated_wettfinder_signals(artifact, now=now),
                [],
            )

            document["generated_at"] = "2030-01-01T10:00:00+00:00"
            document["candidates"][0]["scheduled_start"] = (
                "2030-01-02T09:00:00+00:00"
            )
            artifact.write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(
                automated_wettfinder_signals(artifact, now=now),
                [],
            )

            document["candidates"][0]["scheduled_start"] = (
                "2030-01-01T10:30:00+00:00"
            )
            artifact.write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(
                automated_wettfinder_signals(artifact, now=now),
                [],
            )


class FootballSignalTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name: str, signals: list, finished_at: str) -> None:
        import json

        normalized = [
            {
                "haircut": 0.10,
                "evidence_stage": "SHADOW",
                "policy_version": BETTING_POLICY_VERSION,
                **row,
            }
            if isinstance(row, dict)
            else row
            for row in signals
        ]
        (self.tmp / f"{name}.json").write_text(
            json.dumps({"finished_at": finished_at, "signals": normalized}),
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
        self.assertAlmostEqual(btts.probability_haircut, 0.10)
        self.assertEqual(btts.evidence_stage, "SHADOW")
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

    def test_legacy_football_price_policy_is_excluded(self):
        from datetime import datetime

        from ev_signal_sources import football_signals

        now = datetime.now().astimezone()
        self._write(
            "prematch",
            [
                {
                    "home": "A",
                    "away": "B",
                    "market": "BTTS Ja",
                    "p": 0.60,
                    "policy_version": "legacy-edge-policy",
                }
            ],
            now.isoformat(),
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
