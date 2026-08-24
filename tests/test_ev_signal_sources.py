"""Signalquellen für den Wett-Check: Tennis- und E-Sport-Adapter."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from betting_math import BETTING_POLICY_VERSION, minimum_recommendation_odds
from esports_shadow import ESPORTS_MODEL_VERSION
from ev_signal_sources import (
    AUTOMATED_SELECTION_POLICY_VERSION,
    AUTOMATED_WETTFINDER_VERSION,
    _load_automated_wettfinder_document,
    automated_wettfinder_forecasts,
    automated_wettfinder_signals,
    automated_wettfinder_status,
    esports_signals,
    list_signals,
    tennis_model_signals,
    tennis_signals,
)
from market_consensus import (
    ODDS_API_REFERENCE_SOURCE,
    parse_fixture_consensus,
    wettfinder_reference_price_status,
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


def _playable_automatic_candidate(
    *,
    generated_at: str = "2030-01-01T10:00:00+00:00",
    scheduled_start: str = "2030-01-01T15:00:00+00:00",
    odds: tuple[str, ...] = ("2.00", "2.02", "2.04", "2.06"),
) -> dict:
    candidate = {
        "candidate_id": "1:BTTS_YES",
        "fixture_id": 1,
        "market_key": "BTTS_YES",
        "key": "football-auto-1",
        "label": "Fußball - A vs B - Beide Teams treffen: Ja",
        "sport": "Fussball",
        "event": "A vs B",
        "market": "Beide Teams treffen",
        "selection": "Ja",
        "probability": 0.60,
        "probability_haircut": 0.08,
        "conservative_probability": 0.52,
        "minimum_odds": 1.99,
        "evidence_stage": "SHADOW",
        "policy_version": BETTING_POLICY_VERSION,
        "scheduled_start": scheduled_start,
        "status": "RECOMMENDED",
        "source": "football_challenge",
        "detail": "Automatisch preisgeprüft",
        "reference_price_status": "PLAYABLE",
        "model_scope": "same_competition",
        "context": {
            "release_context_complete": True,
            "release_eligible": True,
        },
        "context_stale": False,
        "is_basic_forecast": False,
        "statistical_release_passed": True,
        "paired_loss_mean": 0.04,
        "paired_loss_hac_standard_error": 0.01,
        "paired_loss_lower_confidence_bound": 0.02,
        "paired_loss_p_value": 0.01,
        "fdr_q_value": 0.02,
        "tested_hypotheses": 90,
    }
    payload = {
        "response": [
            {
                "fixture": {"id": 1, "date": scheduled_start},
                "update": generated_at,
                "bookmakers": [
                    {
                        "id": index,
                        "name": f"Book {index}",
                        "bets": [
                            {
                                "name": "Both Teams Score",
                                "values": [{"value": "Yes", "odd": value}],
                            }
                        ],
                    }
                    for index, value in enumerate(odds, start=1)
                ],
            }
        ]
    }
    fetched_at = datetime.fromisoformat(generated_at)
    quote = parse_fixture_consensus(
        payload,
        [candidate],
        fetched_at=fetched_at,
    )[candidate["candidate_id"]]
    status = wettfinder_reference_price_status(
        quote,
        candidate["minimum_odds"],
        candidate=candidate,
        now=fetched_at,
    )
    candidate["reference_price_status"] = status.code
    candidate["reference_quote"] = quote.to_dict()
    if status.code == "PLAYABLE":
        candidate["reference_quote_source"] = quote.source
        candidate["reference_quote_executable_odds"] = status.usable_odds
        candidate["reference_quote_bookmaker"] = status.bookmaker
        candidate["reference_quote_bookmaker_id"] = status.bookmaker_id
        candidate["reference_quote_observed_at"] = status.observed_at
    return candidate


def _model_automatic_candidate(**kwargs) -> dict:
    candidate = _playable_automatic_candidate(**kwargs)
    candidate["status"] = "MODEL_SELECTION"
    candidate.pop("reference_quote", None)
    for field in (
        "reference_quote_source",
        "reference_quote_executable_odds",
        "reference_quote_bookmaker",
        "reference_quote_bookmaker_id",
        "reference_quote_observed_at",
    ):
        candidate.pop(field, None)
    candidate["reference_price_status"] = "UNAVAILABLE"
    return candidate


def _automatic_model_row(
    index: int,
    *,
    sport: str = "Fussball",
    source: str = "football_challenge",
    policy_version: str = BETTING_POLICY_VERSION,
) -> dict:
    row = _model_automatic_candidate()
    row.update(
        {
            "candidate_id": f"{index}:BTTS_YES",
            "fixture_id": index,
            "key": f"automatic-model-{sport.casefold()}-{index}",
            "label": f"{sport} - Spiel {index} - Beide treffen: Ja",
            "sport": sport,
            "event": f"Spiel {index}",
            "source": source,
            "policy_version": policy_version,
            "context_summary": (
                "Kontext: H2H berücksichtigt · Ausfälle berücksichtigt · "
                "Wetter nicht verfügbar · Aufstellungen noch offen"
            ),
        }
    )
    return row


def _automatic_document(
    model_candidates: list[dict],
    *,
    candidates: list[dict] | None = None,
) -> dict:
    strict = list(candidates or [])
    football_ids = [
        int(row["fixture_id"])
        for row in model_candidates
        if str(row.get("sport") or "").casefold().replace("ß", "ss")
        == "fussball"
    ]
    statuses = {str(fixture_id): "verified" for fixture_id in football_ids}
    sources = {
        "football": {"discovery_scope": 51, "operational_error_count": 0},
        "tennis": {"operational_error_count": 0},
        "esports": {"operational_error_count": 0},
    }
    return {
        "version": AUTOMATED_WETTFINDER_VERSION,
        "generated_at": "2030-01-01T10:00:00+00:00",
        "betting_policy_version": BETTING_POLICY_VERSION,
        "selection_policy_version": AUTOMATED_SELECTION_POLICY_VERSION,
        "bookmaker_data_used": bool(strict),
        "quote_required": True,
        "run_status": "completed",
        "operational_error_count": 0,
        "target_search_date": "2030-01-01",
        "football": {
            "status": "completed",
            "search_date": "2030-01-01",
            "last_discovery_at": "2030-01-01T09:45:00+00:00",
            "fixtures_found": len(football_ids),
            "fixtures_modeled": len(football_ids),
            "base_fixture_count": len(statuses),
            "context_fixtures": len(statuses),
            "context_verified_fixtures": len(statuses),
            "context_data_incomplete_fixtures": 0,
            "context_unchecked_fixtures": 0,
            "deferred_context_fixtures": 0,
            "context_scope_complete": True,
            "context_accounting_available": True,
            "context_fixture_statuses": statuses,
            "operational_error_count": 0,
            "approved_candidates": len(strict),
        },
        "sources": sources,
        "model_candidates": model_candidates,
        "candidates": strict,
    }


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
    def test_previous_catalog_and_selection_policy_versions_are_rejected(self):
        import json

        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            for version, policy in (
                (13, AUTOMATED_SELECTION_POLICY_VERSION),
                (AUTOMATED_WETTFINDER_VERSION, "useful-selection-catalog-v11"),
            ):
                with self.subTest(version=version, policy=policy):
                    document = _automatic_document([])
                    document["version"] = version
                    document["selection_policy_version"] = policy
                    artifact.write_text(json.dumps(document), encoding="utf-8")

                    self.assertIsNone(
                        _load_automated_wettfinder_document(artifact, now=now)
                    )

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
            artifact = tmp / "wettfinder.json"
            candidate = _playable_automatic_candidate()
            artifact.write_text(
                json.dumps(
                    {
                        "version": AUTOMATED_WETTFINDER_VERSION,
                        "generated_at": "2030-01-01T10:00:00+00:00",
                        "betting_policy_version": BETTING_POLICY_VERSION,
                        "selection_policy_version": AUTOMATED_SELECTION_POLICY_VERSION,
                        "bookmaker_data_used": True,
                        "quote_required": True,
                        "run_status": "completed",
                        "operational_error_count": 0,
                        "target_search_date": "2030-01-01",
                        "football": {
                            "status": "completed",
                            "search_date": "2030-01-01",
                            "last_discovery_at": "2030-01-01T09:45:00+00:00",
                            "fixtures_found": 13,
                            "fixtures_modeled": 12,
                            "base_fixture_count": 1,
                            "context_fixtures": 1,
                            "context_verified_fixtures": 1,
                            "context_data_incomplete_fixtures": 0,
                            "context_unchecked_fixtures": 0,
                            "deferred_context_fixtures": 0,
                            "context_scope_complete": True,
                            "context_accounting_available": True,
                            "context_fixture_statuses": {"1": "verified"},
                            "operational_error_count": 0,
                            "approved_candidates": 1,
                        },
                        "sources": {
                            "football": {
                                "discovery_scope": 51,
                                "operational_error_count": 0,
                            }
                        },
                        "model_candidates": [
                            {**candidate, "status": "MODEL_SELECTION"}
                        ],
                        "candidates": [candidate],
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
            # Quote evidence expires after 90 minutes, while the model
            # artifact remains valid for 150 minutes. The stale quote may
            # remove the strict signal, never the model forecast.
            stale_at = datetime(2030, 1, 1, 11, 31, tzinfo=timezone.utc)
            stale_forecasts = automated_wettfinder_forecasts(
                artifact,
                now=stale_at,
            )
            stale_signals = automated_wettfinder_signals(
                artifact,
                now=stale_at,
            )
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].source, "automated_wettfinder")
        self.assertEqual(signals[0].minimum_odds, 1.99)
        self.assertEqual(signals[0].event_label, "A vs B")
        self.assertEqual(signals[0].market, "Beide Teams treffen")
        self.assertEqual(signals[0].selection, "Ja")
        self.assertIsNotNone(signals[0].reference_quote)
        self.assertIsNotNone(status)
        self.assertEqual(status.discovery_scope, 51)
        self.assertEqual(status.fixtures_found, 13)
        self.assertEqual(status.fixtures_modeled, 12)
        self.assertEqual(status.approved_candidates, 1)
        self.assertEqual(len(stale_forecasts), 1)
        self.assertEqual(stale_signals, [])

    def test_degraded_tennis_source_preserves_strict_football_signal(self):
        import json

        candidate = _playable_automatic_candidate()
        model_candidate = {**candidate, "status": "MODEL_SELECTION"}
        document = _automatic_document(
            [model_candidate],
            candidates=[candidate],
        )
        document["run_status"] = "degraded"
        document["operational_error_count"] = 1
        document["sources"]["tennis"] = {
            "status": "degraded",
            "operational_error_count": 1,
        }
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            artifact.write_text(json.dumps(document), encoding="utf-8")

            loaded = _load_automated_wettfinder_document(
                artifact,
                now=now,
            )
            signals = automated_wettfinder_signals(artifact, now=now)
            status = automated_wettfinder_status(artifact, now=now)

        self.assertIsNotNone(loaded)
        self.assertEqual([signal.selection for signal in signals], ["Ja"])
        self.assertIsNotNone(status)
        self.assertEqual(status.operational_error_count, 1)
        self.assertEqual(status.candidate_count, 1)

    def test_reader_rejects_candidate_from_its_failed_source(self):
        import json

        candidate = _playable_automatic_candidate()
        model_candidate = {**candidate, "status": "MODEL_SELECTION"}
        document = _automatic_document(
            [model_candidate],
            candidates=[candidate],
        )
        document["run_status"] = "degraded"
        document["operational_error_count"] = 1
        document["sources"]["football"]["operational_error_count"] = 1
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            artifact.write_text(json.dumps(document), encoding="utf-8")

            self.assertIsNone(
                _load_automated_wettfinder_document(artifact, now=now)
            )
            self.assertEqual(
                automated_wettfinder_signals(artifact, now=now),
                [],
            )

    def test_automatic_catalog_roundtrip_enforces_per_sport_caps(self):
        import json

        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        def rows(
            *,
            football: int = 15,
            tennis: int = 3,
            esports: int = 3,
            basketball: int = 0,
        ) -> list[dict]:
            catalog = [
                _automatic_model_row(index)
                for index in range(1, football + 1)
            ]
            catalog.extend(
                _automatic_model_row(
                    100 + index,
                    sport="Tennis",
                    source="tennis_shadow",
                    policy_version=TENNIS_POLICY_VERSION,
                )
                for index in range(1, tennis + 1)
            )
            catalog.extend(
                _automatic_model_row(
                    200 + index,
                    sport="E-Sport",
                    source="esports_shadow",
                    policy_version=(
                        f"{BETTING_POLICY_VERSION}:{ESPORTS_MODEL_VERSION}"
                    ),
                )
                for index in range(1, esports + 1)
            )
            catalog.extend(
                _automatic_model_row(
                    300 + index,
                    sport="Basketball",
                    source="basketball_model",
                )
                for index in range(1, basketball + 1)
            )
            return catalog

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"

            accepted = rows()
            accepted[0]["context"] = {"release_context_complete": True}
            accepted[1]["context"] = {"release_context_complete": False}
            accepted[2].pop("context", None)
            artifact.write_text(
                json.dumps(_automatic_document(accepted)),
                encoding="utf-8",
            )
            self.assertIsNotNone(
                _load_automated_wettfinder_document(artifact, now=now)
            )
            forecasts = automated_wettfinder_forecasts(artifact, now=now)
            self.assertEqual(len(forecasts), 21)
            self.assertIn("Wetter nicht verfügbar", forecasts[0].context_summary)
            self.assertEqual(forecasts[0].market_key, "BTTS_YES")
            self.assertIs(forecasts[0].context_complete, True)
            self.assertIs(forecasts[1].context_complete, False)
            self.assertIsNone(forecasts[2].context_complete)

            for rejected in (
                rows(football=16, tennis=3, esports=2),
                rows(football=15, tennis=4, esports=2),
                rows(football=15, tennis=3, esports=3, basketball=1),
            ):
                artifact.write_text(
                    json.dumps(_automatic_document(rejected)),
                    encoding="utf-8",
                )
                self.assertIsNone(
                    _load_automated_wettfinder_document(artifact, now=now)
                )

    def test_strict_rows_follow_model_order_even_when_probability_differs(self):
        import json

        def playable(index: int, probability: float) -> dict:
            row = _playable_automatic_candidate()
            candidate_id = f"{index}:BTTS_YES"
            row.update(
                {
                    "candidate_id": candidate_id,
                    "fixture_id": index,
                    "key": f"football-auto-{index}",
                    "label": f"Fußball - Spiel {index} - Beide treffen: Ja",
                    "event": f"Spiel {index}",
                    "probability": probability,
                    "conservative_probability": probability - 0.08,
                    "minimum_odds": minimum_recommendation_odds(
                        probability * 100.0,
                        probability_haircut=8.0,
                    ),
                }
            )
            row["reference_quote"]["candidate_id"] = candidate_id
            row["reference_quote"]["fixture_id"] = index
            return row

        lower_probability_first = playable(1, 0.60)
        higher_probability_second = playable(2, 0.70)
        model_rows = [
            {**lower_probability_first, "status": "MODEL_SELECTION"},
            {**higher_probability_second, "status": "MODEL_SELECTION"},
        ]
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            artifact.write_text(
                json.dumps(
                    _automatic_document(
                        model_rows,
                        candidates=[
                            lower_probability_first,
                            higher_probability_second,
                        ],
                    )
                ),
                encoding="utf-8",
            )
            self.assertIsNotNone(
                _load_automated_wettfinder_document(artifact, now=now)
            )

            artifact.write_text(
                json.dumps(
                    _automatic_document(
                        model_rows,
                        candidates=[
                            higher_probability_second,
                            lower_probability_first,
                        ],
                    )
                ),
                encoding="utf-8",
            )
            self.assertIsNone(
                _load_automated_wettfinder_document(artifact, now=now)
            )

    def test_automatic_artifact_rejects_strict_payload_mismatch(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            candidate = _playable_automatic_candidate()
            model_candidate = {**candidate, "status": "MODEL_SELECTION"}
            model_candidate["selection"] = "Nein"
            artifact.write_text(
                json.dumps(
                    {
                        "version": AUTOMATED_WETTFINDER_VERSION,
                        "generated_at": "2030-01-01T10:00:00+00:00",
                        "betting_policy_version": BETTING_POLICY_VERSION,
                        "selection_policy_version": (
                            AUTOMATED_SELECTION_POLICY_VERSION
                        ),
                        "bookmaker_data_used": True,
                        "quote_required": True,
                        "target_search_date": "2030-01-01",
                        "model_candidates": [model_candidate],
                        "candidates": [candidate],
                    }
                ),
                encoding="utf-8",
            )

            self.assertIsNone(
                _load_automated_wettfinder_document(
                    artifact,
                    now=datetime(
                        2030,
                        1,
                        1,
                        10,
                        30,
                        tzinfo=timezone.utc,
                    ),
                )
            )

    def test_model_selection_survives_without_a_bookmaker_quote(self):
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
                        "quote_required": True,
                        "run_status": "completed",
                        "operational_error_count": 0,
                        "target_search_date": "2030-01-01",
                        "football": {
                            "status": "completed",
                            "operational_error_count": 0,
                            "base_fixture_count": 1,
                            "context_fixtures": 1,
                            "context_verified_fixtures": 1,
                            "context_data_incomplete_fixtures": 0,
                            "context_unchecked_fixtures": 0,
                            "deferred_context_fixtures": 0,
                            "context_scope_complete": True,
                            "context_accounting_available": True,
                            "context_fixture_statuses": {"1": "verified"},
                        },
                        "sources": {
                            "football": {
                                "discovery_scope": 51,
                                "operational_error_count": 0,
                            }
                        },
                        "model_candidates": [_model_automatic_candidate()],
                        "candidates": [],
                    }
                ),
                encoding="utf-8",
            )

            forecasts = automated_wettfinder_forecasts(
                artifact,
                now=datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc),
            )
            priced = automated_wettfinder_signals(
                artifact,
                now=datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc),
            )

        self.assertEqual(len(forecasts), 1)
        self.assertEqual(forecasts[0].selection, "Ja")
        self.assertIsNone(forecasts[0].reference_quote)
        self.assertEqual(priced, [])

    def test_degraded_football_artifact_never_exposes_football_signal(self):
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
                        "bookmaker_data_used": True,
                        "quote_required": True,
                        "run_status": "degraded",
                        "operational_error_count": 1,
                        "target_search_date": "2030-01-01",
                        "football": {
                            "status": "degraded",
                            "operational_error_count": 1,
                        },
                        "model_candidates": [],
                        "candidates": [_playable_automatic_candidate()],
                    }
                ),
                encoding="utf-8",
            )

            signals = automated_wettfinder_signals(
                artifact,
                now=datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc),
            )

        self.assertEqual(signals, [])

    def test_football_signal_requires_candidate_release_contract(self):
        import json

        violations = (
            (
                "release context incomplete",
                {
                    "context": {
                        "release_context_complete": False,
                        "release_eligible": True,
                    }
                },
            ),
            (
                "release ineligible",
                {
                    "context": {
                        "release_context_complete": True,
                        "release_eligible": False,
                    }
                },
            ),
            ("wrong model scope", {"model_scope": "home_league_transfer"}),
            ("stale context", {"context_stale": True}),
            (
                "statistical release not passed",
                {"statistical_release_passed": False},
            ),
            ("missing paired evidence", {"paired_loss_p_value": None}),
            ("invalid FDR correction", {"fdr_q_value": 0.051}),
            ("wrong hypothesis family", {"tested_hypotheses": 89}),
        )
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            for label, override in violations:
                with self.subTest(violation=label):
                    candidate = _playable_automatic_candidate()
                    candidate.update(override)
                    model_candidate = {
                        **candidate,
                        "status": "MODEL_SELECTION",
                    }
                    artifact.write_text(
                        json.dumps(
                            _automatic_document(
                                [model_candidate],
                                candidates=[candidate],
                            )
                        ),
                        encoding="utf-8",
                    )

                    self.assertIsNotNone(
                        _load_automated_wettfinder_document(
                            artifact,
                            now=now,
                        )
                    )
                    self.assertEqual(
                        automated_wettfinder_signals(artifact, now=now),
                        [],
                    )

            candidate = _playable_automatic_candidate()
            candidate.pop("context_stale")
            artifact.write_text(
                json.dumps(
                    _automatic_document(
                        [{**candidate, "status": "MODEL_SELECTION"}],
                        candidates=[candidate],
                    )
                ),
                encoding="utf-8",
            )
            self.assertIsNotNone(
                _load_automated_wettfinder_document(artifact, now=now)
            )
            self.assertEqual(
                automated_wettfinder_signals(artifact, now=now),
                [],
            )

    def test_failed_statistical_release_keeps_forecast_but_never_strict_tip(self):
        import json

        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)
        candidate = _playable_automatic_candidate()
        candidate["statistical_release_passed"] = False
        model_candidate = {**candidate, "status": "MODEL_SELECTION"}
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            artifact.write_text(
                json.dumps(
                    _automatic_document(
                        [model_candidate],
                        candidates=[candidate],
                    )
                ),
                encoding="utf-8",
            )

            forecasts = automated_wettfinder_forecasts(artifact, now=now)
            strict = automated_wettfinder_signals(artifact, now=now)

        self.assertEqual(len(forecasts), 1)
        self.assertIs(forecasts[0].statistical_release_passed, False)
        self.assertEqual(strict, [])


    def test_football_signal_does_not_use_basic_market_metadata_as_gate(self):
        import json

        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            for metadata in (True, None):
                with self.subTest(is_basic_forecast=metadata):
                    candidate = _playable_automatic_candidate()
                    if metadata is None:
                        candidate.pop("is_basic_forecast")
                    else:
                        candidate["is_basic_forecast"] = metadata
                    artifact.write_text(
                        json.dumps(
                            _automatic_document(
                                [{**candidate, "status": "MODEL_SELECTION"}],
                                candidates=[candidate],
                            )
                        ),
                        encoding="utf-8",
                    )

                    self.assertIsNotNone(
                        _load_automated_wettfinder_document(artifact, now=now)
                    )
                    signals = automated_wettfinder_signals(artifact, now=now)
                    self.assertEqual(len(signals), 1)
                    self.assertEqual(signals[0].market_key, "BTTS_YES")

    def test_esports_signal_is_never_strict_without_a_verified_price_provider(self):
        import json

        candidate = _playable_automatic_candidate()
        candidate.update(
            {
                "key": "esports-auto-1",
                "sport": "E-Sport",
                "event": "Alpha vs Beta",
                "market": "Match Winner",
                "market_key": "H2H",
                "selection": "Sieg Alpha",
                "source": "esports_shadow",
                "policy_version": (
                    f"{BETTING_POLICY_VERSION}:{ESPORTS_MODEL_VERSION}"
                ),
            }
        )
        candidate.pop("fixture_id")
        candidate["reference_quote"]["market_key"] = "H2H"
        model_candidate = {**candidate, "status": "MODEL_SELECTION"}
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            artifact.write_text(
                json.dumps(
                    _automatic_document(
                        [model_candidate],
                        candidates=[candidate],
                    )
                ),
                encoding="utf-8",
            )

            self.assertIsNone(
                _load_automated_wettfinder_document(artifact, now=now)
            )
            self.assertEqual(
                automated_wettfinder_signals(artifact, now=now),
                [],
            )

    def test_automatic_artifact_rejects_mismatched_quote_identity(self):
        import json

        mutations = (
            ("wrong market", {"market_key": "BTTS_NO"}),
            ("wrong fixture", {"fixture_id": 2}),
            (
                "wrong source",
                {
                    "source": ODDS_API_REFERENCE_SOURCE,
                    "provider_event_id": "wrong-provider-event",
                },
            ),
        )
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            for label, quote_mutation in mutations:
                with self.subTest(mismatch=label):
                    candidate = _playable_automatic_candidate()
                    candidate["reference_quote"].update(quote_mutation)
                    model_candidate = {
                        **candidate,
                        "status": "MODEL_SELECTION",
                    }
                    artifact.write_text(
                        json.dumps(
                            _automatic_document(
                                [model_candidate],
                                candidates=[candidate],
                            )
                        ),
                        encoding="utf-8",
                    )

                    self.assertIsNone(
                        _load_automated_wettfinder_document(
                            artifact,
                            now=now,
                        )
                    )
                    self.assertIsNone(
                        automated_wettfinder_status(artifact, now=now)
                    )
                    self.assertEqual(
                        automated_wettfinder_forecasts(artifact, now=now),
                        [],
                    )
                    self.assertEqual(
                        automated_wettfinder_signals(artifact, now=now),
                        [],
                    )

    def test_automatic_artifact_rejects_tampered_execution_provenance(self):
        import json

        mutations = (
            ("synthetic q25", "reference_quote_executable_odds", 2.015),
            ("wrong bookmaker", "reference_quote_bookmaker", "Other Book"),
            (
                "wrong bookmaker id",
                "reference_quote_bookmaker_id",
                "api-football:999",
            ),
            (
                "wrong observation",
                "reference_quote_observed_at",
                "2030-01-01T09:59:00+00:00",
            ),
            ("missing provider source", "reference_quote_source", None),
        )
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            for label, field, value in mutations:
                with self.subTest(tamper=label):
                    candidate = _playable_automatic_candidate()
                    if value is None:
                        candidate.pop(field)
                    else:
                        candidate[field] = value
                    model_candidate = {
                        **candidate,
                        "status": "MODEL_SELECTION",
                    }
                    artifact.write_text(
                        json.dumps(
                            _automatic_document(
                                [model_candidate],
                                candidates=[candidate],
                            )
                        ),
                        encoding="utf-8",
                    )

                    self.assertIsNone(
                        _load_automated_wettfinder_document(
                            artifact,
                            now=now,
                        )
                    )
                    self.assertEqual(
                        automated_wettfinder_signals(artifact, now=now),
                        [],
                    )

    def test_automatic_model_without_quote_must_be_unavailable_for_every_sport(
        self,
    ):
        import json

        cases = (
            ("Tennis", "tennis_shadow", TENNIS_POLICY_VERSION),
            (
                "E-Sport",
                "esports_shadow",
                f"{BETTING_POLICY_VERSION}:{ESPORTS_MODEL_VERSION}",
            ),
        )
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            for index, (sport, source, policy) in enumerate(cases, start=1):
                with self.subTest(sport=sport):
                    row = _automatic_model_row(
                        index,
                        sport=sport,
                        source=source,
                        policy_version=policy,
                    )
                    row["reference_price_status"] = "PLAYABLE"
                    artifact.write_text(
                        json.dumps(_automatic_document([row])),
                        encoding="utf-8",
                    )

                    self.assertIsNone(
                        _load_automated_wettfinder_document(
                            artifact,
                            now=now,
                        )
                    )
                    self.assertIsNone(
                        automated_wettfinder_status(artifact, now=now)
                    )

    def test_automatic_strict_candidate_requires_known_generated_source(self):
        import json

        candidate = _playable_automatic_candidate()
        candidate["source"] = "manipulated_shadow"
        model_candidate = {**candidate, "status": "MODEL_SELECTION"}
        now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            artifact.write_text(
                json.dumps(
                    _automatic_document(
                        [model_candidate],
                        candidates=[candidate],
                    )
                ),
                encoding="utf-8",
            )

            self.assertIsNone(
                _load_automated_wettfinder_document(artifact, now=now)
            )
            self.assertEqual(
                automated_wettfinder_signals(artifact, now=now),
                [],
            )

    def test_football_signal_requires_verified_fixture_accounting(self):
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
                        "bookmaker_data_used": True,
                        "quote_required": True,
                        "run_status": "completed",
                        "operational_error_count": 0,
                        "target_search_date": "2030-01-01",
                        "football": {
                            "status": "completed",
                            "operational_error_count": 0,
                            "context_scope_complete": True,
                            "context_accounting_available": True,
                        },
                        "model_candidates": [],
                        "candidates": [_playable_automatic_candidate()],
                    }
                ),
                encoding="utf-8",
            )

            signals = automated_wettfinder_signals(
                artifact,
                now=datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc),
            )

        self.assertEqual(signals, [])

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
                        "bookmaker_data_used": True,
                        "quote_required": True,
                        "run_status": "completed",
                        "operational_error_count": 0,
                        "target_search_date": "2030-01-01",
                        "football": {
                            "status": "completed",
                            "search_date": "2030-01-01",
                            "last_discovery_at": "2030-01-01T09:45:00+00:00",
                            "fixtures_found": 13,
                            "fixtures_modeled": 13,
                            "base_candidates": 5,
                            "base_fixture_count": 2,
                            "context_fixtures": 2,
                            "context_verified_fixtures": 1,
                            "context_data_incomplete_fixtures": 1,
                            "context_unchecked_fixtures": 0,
                            "deferred_context_fixtures": 0,
                            "context_scope_complete": False,
                            "context_fixture_statuses": {
                                "1": "verified",
                                "2": "data_incomplete",
                            },
                            "context_accounting_available": True,
                            "operational_error_count": 0,
                            "approved_candidates": 0,
                        },
                        "sources": {
                            "football": {
                                "discovery_scope": 51,
                                "price_checked_count": 3,
                                "reference_quote_count": 1,
                                "price_status_counts": {
                                    "TOO_LOW": 1,
                                    "UNAVAILABLE": 2,
                                },
                            }
                        },
                        "model_candidates": [],
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
        self.assertEqual(status.base_candidates, 5)
        self.assertEqual(status.base_fixture_count, 2)
        self.assertEqual(status.context_fixtures, 2)
        self.assertEqual(status.context_verified_fixtures, 1)
        self.assertEqual(status.context_data_incomplete_fixtures, 1)
        self.assertFalse(status.context_scope_complete)
        self.assertTrue(status.context_accounting_available)
        self.assertEqual(status.operational_error_count, 0)
        self.assertEqual(status.candidate_count, 0)
        self.assertTrue(status.bookmaker_data_used)
        self.assertEqual(status.price_checked_count, 3)
        self.assertEqual(status.reference_quote_count, 1)
        self.assertEqual(
            dict(status.price_status_counts),
            {"TOO_LOW": 1, "UNAVAILABLE": 2},
        )

    def test_automatic_artifact_rejects_stale_or_started_candidates(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            document = {
                "version": AUTOMATED_WETTFINDER_VERSION,
                "generated_at": "2030-01-01T06:00:00+00:00",
                "betting_policy_version": BETTING_POLICY_VERSION,
                "selection_policy_version": AUTOMATED_SELECTION_POLICY_VERSION,
                "bookmaker_data_used": True,
                "quote_required": True,
                "target_search_date": "2030-01-01",
                "model_candidates": [],
                "candidates": [_playable_automatic_candidate()],
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

    def test_automatic_artifact_rejects_missing_or_unplayable_price(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact = Path(tmpdir) / "wettfinder.json"
            base = {
                "version": AUTOMATED_WETTFINDER_VERSION,
                "generated_at": "2030-01-01T10:00:00+00:00",
                "betting_policy_version": BETTING_POLICY_VERSION,
                "selection_policy_version": AUTOMATED_SELECTION_POLICY_VERSION,
                "bookmaker_data_used": True,
                "quote_required": True,
                "target_search_date": "2030-01-01",
                "model_candidates": [],
            }
            missing = _playable_automatic_candidate()
            missing.pop("reference_quote")
            base["candidates"] = [missing]
            artifact.write_text(json.dumps(base), encoding="utf-8")
            now = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)
            self.assertEqual(
                automated_wettfinder_signals(artifact, now=now),
                [],
            )

            too_low = _playable_automatic_candidate(
                odds=("1.40", "1.42", "1.44", "1.46")
            )
            base["candidates"] = [too_low]
            artifact.write_text(json.dumps(base), encoding="utf-8")
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
