"""Tests für das Shadow-Automation-Modul (Quoten-Mapping + Settlement-Integrität)."""
import gc
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import shadow_clv_automation as shadow  # noqa: E402


def test_nations_league_shadow_history_uses_recent_team_adapter_not_2025(tmp_path):
    from unittest.mock import Mock

    fixture = {"fixture": {"id": 91}, "league": {"id": 5}}
    provider = Mock()
    recent = [{"fixture": {"id": 20}, "league": {"id": 32}}]
    with (
        patch.object(shadow, "CACHE_DIR", tmp_path),
        patch("challenge_15k.ChallengeDataProvider") as adapter_type,
        patch.object(shadow, "fetch_stat_history") as old_history,
    ):
        adapter_type.return_value.completed_history.return_value = recent
        result = shadow._cached_history(provider, 5, 2026, fixture, "2026-09-24")
        again = shadow._cached_history(provider, 5, 2026, fixture, "2026-09-24")

    assert result == again == recent
    adapter_type.return_value.completed_history.assert_called_once_with(
        5, 2026, [fixture],
    )
    old_history.assert_not_called()
    provider.ft_history.assert_not_called()

from challenge_engine import MARKET_BY_KEY, MARKET_SPECS, market_outcome  # noqa: E402


def _odds_response(bookmaker_name="Bet365", bets=None, updated_at=None):
    return [{
        "update": updated_at,
        "bookmakers": [{
            "name": bookmaker_name,
            "bets": bets if bets is not None else [
                {"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "1.85"},
                    {"value": "Draw", "odd": "3.60"},
                    {"value": "Away", "odd": "4.20"},
                ]},
                {"name": "Double Chance", "values": [
                    {"value": "1X", "odd": "1.25"},
                    {"value": "X2", "odd": "1.95"},
                    {"value": "12", "odd": "1.30"},
                ]},
                {"name": "Both Teams Score", "values": [
                    {"value": "Yes", "odd": "1.75"},
                    {"value": "No", "odd": "2.05"},
                ]},
                {"name": "Goals Over/Under", "values": [
                    {"value": "Over 2.5", "odd": "1.90"},
                    {"value": "Under 2.5", "odd": "1.91"},
                    {"value": "Over 0.5", "odd": "1.05"},
                ]},
            ],
        }],
    }]


class MarketQuoteTest(unittest.TestCase):
    def test_extracts_all_mapped_markets(self):
        response = _odds_response()
        self.assertAlmostEqual(shadow._market_quote(response, "RESULT_HOME"), 1.85)
        self.assertAlmostEqual(shadow._market_quote(response, "RESULT_DRAW"), 3.60)
        self.assertAlmostEqual(shadow._market_quote(response, "RESULT_AWAY"), 4.20)
        self.assertAlmostEqual(shadow._market_quote(response, "DC_1X"), 1.25)
        self.assertAlmostEqual(shadow._market_quote(response, "DC_X2"), 1.95)
        self.assertAlmostEqual(shadow._market_quote(response, "DC_12"), 1.30)
        self.assertAlmostEqual(shadow._market_quote(response, "BTTS_YES"), 1.75)
        self.assertAlmostEqual(shadow._market_quote(response, "BTTS_NO"), 2.05)
        self.assertAlmostEqual(shadow._market_quote(response, "TOTAL_OVER_2_5"), 1.90)
        self.assertAlmostEqual(shadow._market_quote(response, "TOTAL_UNDER_2_5"), 1.91)
        self.assertAlmostEqual(shadow._market_quote(response, "TOTAL_OVER_0_5"), 1.05)

    def test_missing_line_returns_none(self):
        # Under 3.5 ist nicht im Block
        self.assertIsNone(shadow._market_quote(_odds_response(), "TOTAL_UNDER_3_5"))

    def test_unknown_market_key_returns_none(self):
        self.assertIsNone(shadow._market_quote(_odds_response(), "CORNERS_OVER_5_5"))
        self.assertIsNone(shadow._market_quote(_odds_response(), "RESULT_TOTAL_1X_UNDER_3_5"))

    def test_wrong_bookmaker_returns_none(self):
        self.assertIsNone(shadow._market_quote(_odds_response("Pinnacle"), "RESULT_HOME"))

    def test_invalid_odds_return_none(self):
        bad = _odds_response(bets=[
            {"name": "Match Winner", "values": [
                {"value": "Home", "odd": "1.00"},
                {"value": "Draw", "odd": "keine-zahl"},
                {"value": "Away", "odd": None},
            ]},
        ])
        self.assertIsNone(shadow._market_quote(bad, "RESULT_HOME"))
        self.assertIsNone(shadow._market_quote(bad, "RESULT_DRAW"))
        self.assertIsNone(shadow._market_quote(bad, "RESULT_AWAY"))

    def test_empty_response_returns_none(self):
        self.assertIsNone(shadow._market_quote([], "RESULT_HOME"))
        self.assertIsNone(shadow._market_quote(None, "RESULT_HOME"))

    def test_btts_wrapper_still_works(self):
        self.assertAlmostEqual(shadow._btts_quote(_odds_response(), "BTTS_YES"), 1.75)

    def test_provider_update_time_is_required_for_clv(self):
        self.assertIsNone(shadow._market_quote_observation(_odds_response(), "BTTS_YES"))
        stamp = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(
            shadow._market_quote_observation(
                _odds_response(updated_at=stamp.isoformat()), "BTTS_YES"
            ),
            (1.75, stamp),
        )


class ProviderSecretRedactionTest(unittest.TestCase):
    def test_shadow_odds_filter_exact_bet365_id_not_first_bookmaker_page(self):
        provider = shadow.ShadowProvider("football-key", None)
        with patch.object(provider, "_get", return_value=[]) as fetch:
            provider.odds(91)
        self.assertEqual(fetch.call_args.args[:2], (
            "odds", {"fixture": 91, "bookmaker": shadow.BOOKMAKER_ID},
        ))

    def test_weather_http_error_never_leaks_query_string_api_key(self):
        secret = "weather-secret-must-not-escape"
        prepared = shadow.requests.Request(
            "GET",
            "https://api.openweathermap.org/geo/1.0/direct",
            params={"q": "Zurich,CH", "appid": secret},
        ).prepare()
        response = shadow.requests.Response()
        response.status_code = 401
        response.url = prepared.url
        response.request = prepared
        fixture = {
            "fixture": {
                "date": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "venue": {"city": "Zurich"},
            },
            "league": {"country": "CH"},
        }
        previous_errors = list(shadow.errors)
        shadow.errors.clear()
        try:
            with patch.object(shadow.requests, "get", return_value=response):
                result = shadow.ShadowProvider("football-key", secret).weather(fixture)
            serialized_errors = "\n".join(shadow.errors)
        finally:
            shadow.errors.clear()
            shadow.errors.extend(previous_errors)

        self.assertIsNone(result)
        self.assertNotIn(secret, serialized_errors)
        self.assertNotIn("appid", serialized_errors)
        self.assertNotIn("openweathermap.org", serialized_errors)
        self.assertIn("HTTP 401", serialized_errors)


class QuoteMappingIntegrityTest(unittest.TestCase):
    def test_tracker_release_allowlist_matches_exact_quoted_shadow_markets(self):
        self.assertEqual(
            shadow.CLVTracker.SHADOW_SETTLEABLE_MARKETS,
            frozenset(shadow._QUOTE_BETS),
        )

    def test_every_mapped_key_exists_in_engine_and_settles_on_goals(self):
        engine_keys = {spec.key for spec in MARKET_SPECS}
        for market_key in shadow._QUOTE_BETS:
            self.assertIn(market_key, engine_keys, f"{market_key} fehlt in MARKET_SPECS")
            spec = MARKET_BY_KEY[market_key]
            # Settlement muss aus dem Endstand (Tore) möglich sein
            self.assertIsInstance(market_outcome(spec, 2, 1), bool)
            self.assertIsInstance(market_outcome(spec, 0, 0), bool)

    def test_settlement_semantics_match_market_meaning(self):
        self.assertTrue(market_outcome(MARKET_BY_KEY["RESULT_HOME"], 2, 1))
        self.assertFalse(market_outcome(MARKET_BY_KEY["DC_X2"], 2, 1))
        self.assertTrue(market_outcome(MARKET_BY_KEY["DC_X2"], 1, 2))
        self.assertTrue(market_outcome(MARKET_BY_KEY["TOTAL_OVER_2_5"], 2, 1))
        self.assertFalse(market_outcome(MARKET_BY_KEY["TOTAL_OVER_2_5"], 1, 1))
        self.assertTrue(market_outcome(MARKET_BY_KEY["BTTS_NO"], 2, 0))
        self.assertTrue(market_outcome(MARKET_BY_KEY["BTTS_YES"], 2, 1))

    def test_only_goal_based_markets_are_mapped(self):
        # Ecken-/Karten-Märkte dürfen nie ins Mapping (Settlement bräuchte Stats)
        for market_key in shadow._QUOTE_BETS:
            self.assertNotIn("CORNER", market_key)
            self.assertNotIn("YELLOW", market_key)


class ModelFirstShadowTest(unittest.TestCase):
    @staticmethod
    def _candidate(market_key, probability, evidence=80.0):
        return SimpleNamespace(
            market_key=market_key,
            conservative_probability=probability,
            evidence_score=evidence,
        )

    def test_candidate_ranking_ignores_price_size_and_value_gate(self):
        now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
        weaker = self._candidate("RESULT_HOME", 0.45, evidence=75.0)
        stronger = self._candidate("BTTS_NO", 0.55, evidence=85.0)
        response = _odds_response(updated_at=(now - timedelta(minutes=2)).isoformat())
        with patch.object(shadow, "candidate_selection_rank", side_effect=lambda c: (c.evidence_score,)):
            selected = shadow._model_first_observations([weaker, stronger], response, now)
        self.assertEqual([item[0] for item in selected], [stronger, weaker])
        self.assertEqual(selected[0][1], 2.05)

    def test_unstamped_or_stale_quote_is_not_clv_evidence(self):
        now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
        candidate = self._candidate("BTTS_NO", 0.55)
        self.assertEqual(shadow._model_first_observations([candidate], _odds_response(), now), [])
        stale = _odds_response(updated_at=(now - timedelta(minutes=11)).isoformat())
        self.assertEqual(shadow._model_first_observations([candidate], stale, now), [])

    def test_extra_time_results_are_not_auto_settled_as_regulation(self):
        self.assertEqual(shadow.FT_STATUSES, {"FT"})

    def test_closing_requires_provider_update_inside_final_window(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        kickoff = now + timedelta(minutes=10)
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "shadow.db"
            tracker = shadow.CLVTracker(db_path=str(db_path))
            prediction_id = tracker.record_prediction(
                fixture_id=91, home_team="Home", away_team="Away",
                market_type="BTTS_YES", prediction="Ja", odds=1.75,
                model_probability=55.0, bookmaker=shadow.BOOKMAKER_NAME,
                quote_source=shadow.QUOTE_SOURCE, quoted_at=now - timedelta(minutes=3),
                fixture_kickoff=kickoff, model_version=shadow.SHADOW_MODEL_VERSION,
                policy_version=shadow.SHADOW_POLICY_VERSION,
            )
            previous_db = shadow.SHADOW_DB
            shadow.SHADOW_DB = db_path
            try:
                provider = SimpleNamespace(odds=lambda *_args, **_kwargs: _odds_response(
                    updated_at=(now - timedelta(minutes=30)).isoformat()
                ))
                self.assertEqual(shadow.step_closing(tracker, provider, now), 0)
                fresh = now - timedelta(minutes=1)
                provider.odds = lambda *_args, **_kwargs: _odds_response(
                    updated_at=fresh.isoformat()
                )
                self.assertEqual(shadow.step_closing(tracker, provider, now), 1)
                connection = sqlite3.connect(db_path)
                try:
                    row = connection.execute(
                        "SELECT closing_odds, closing_quoted_at FROM predictions WHERE id = ?",
                        (prediction_id,),
                    ).fetchone()
                finally:
                    connection.close()
                self.assertEqual(row, (1.75, fresh.isoformat()))
            finally:
                shadow.SHADOW_DB = previous_db
                gc.collect()


class ShadowConditionTest(unittest.TestCase):
    @staticmethod
    def _database(path, now, *, fixture_due):
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "CREATE TABLE predictions ("
                "result TEXT, fixture_kickoff TEXT, closing_odds REAL)"
            )
            connection.execute(
                "CREATE TABLE shadow_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE shadow_fixtures (kickoff TEXT, evaluated INTEGER)"
            )
            connection.execute(
                "INSERT INTO shadow_meta (key, value) VALUES (?, ?)",
                (shadow._schedule_marker(shadow._zurich_time(now).date()), "loaded"),
            )
            connection.execute(
                "INSERT INTO shadow_meta (key, value) VALUES (?, ?)",
                (shadow._schedule_marker(shadow._zurich_time(now).date() + timedelta(days=1)), "loaded"),
            )
            if fixture_due:
                connection.execute(
                    "INSERT INTO shadow_fixtures (kickoff, evaluated) VALUES (?, 0)",
                    ((now + timedelta(minutes=30)).isoformat(),),
                )
            connection.commit()
        finally:
            connection.close()

    def test_uses_production_evaluation_window(self):
        now = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "shadow.db"
            self._database(db_path, now, fixture_due=True)
            self.assertTrue(shadow._shadow_work_due(now, db_path))

    def test_stays_idle_without_due_work(self):
        now = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "shadow.db"
            self._database(db_path, now, fixture_due=False)
            self.assertFalse(shadow._shadow_work_due(now, db_path))

    def test_missing_tomorrow_schedule_is_due_only_after_nine_zurich(self):
        now = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "shadow.db"
            self._database(db_path, now, fixture_due=False)
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "DELETE FROM shadow_meta WHERE key = ?",
                    (shadow._schedule_marker(shadow._zurich_time(now).date() + timedelta(days=1)),),
                )
                connection.commit()
            finally:
                connection.close()
            self.assertTrue(shadow._shadow_work_due(now, db_path))

    def test_settlement_retry_is_not_due_every_ten_minutes(self):
        now = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "shadow.db"
            self._database(db_path, now, fixture_due=False)
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "INSERT INTO predictions VALUES (?, ?, ?)",
                    (None, (now - timedelta(hours=3)).isoformat(), None),
                )
                connection.commit()
                self.assertTrue(shadow._shadow_work_due(now, db_path))
                connection.execute(
                    "INSERT INTO shadow_meta VALUES (?, ?)",
                    (shadow._settlement_marker(shadow._zurich_time(now).date()), now.isoformat()),
                )
                connection.commit()
            finally:
                connection.close()
            self.assertFalse(shadow._shadow_work_due(now, db_path))

    def test_legacy_schedule_marker_does_not_hide_new_model_run(self):
        now = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "shadow.db"
            self._database(db_path, now, fixture_due=False)
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("DELETE FROM shadow_meta")
                connection.execute(
                    "INSERT INTO shadow_meta (key, value) VALUES (?, ?)",
                    ("schedule:2026-08-01", "legacy"),
                )
                connection.commit()
            finally:
                connection.close()

            self.assertTrue(shadow._shadow_work_due(now, db_path))

    def test_artifact_counts_only_current_model_and_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "shadow.db"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "CREATE TABLE predictions (result TEXT, closing_odds REAL, "
                    "model_version TEXT, policy_version TEXT)"
                )
                connection.executemany(
                    "INSERT INTO predictions VALUES (?, ?, ?, ?)",
                    (
                        (
                            None,
                            None,
                            shadow.SHADOW_MODEL_VERSION,
                            shadow.SHADOW_POLICY_VERSION,
                        ),
                        (None, None, "legacy-model", "legacy-policy"),
                    ),
                )
                connection.commit()
            finally:
                connection.close()
            original = shadow.SHADOW_DB
            shadow.SHADOW_DB = db_path
            try:
                self.assertEqual(shadow._counts(), (1, 1))
            finally:
                shadow.SHADOW_DB = original


class ShadowVersionLifecycleTest(unittest.TestCase):
    def test_cache_path_changes_with_model_version(self):
        with tempfile.TemporaryDirectory() as folder:
            original_dir = shadow.CACHE_DIR
            original_version = shadow.SHADOW_MODEL_VERSION
            shadow.CACHE_DIR = Path(folder)
            try:
                current = shadow._cache_path("validation", 39, 2030, "2030-01-01")
                shadow.SHADOW_MODEL_VERSION = "next-model"
                changed = shadow._cache_path("validation", 39, 2030, "2030-01-01")
            finally:
                shadow.CACHE_DIR = original_dir
                shadow.SHADOW_MODEL_VERSION = original_version

        self.assertNotEqual(current.name, changed.name)

    def test_legacy_prediction_does_not_block_current_model(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "shadow.db"
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "CREATE TABLE predictions (fixture_id INTEGER, "
                    "model_version TEXT, policy_version TEXT)"
                )
                connection.execute(
                    "INSERT INTO predictions VALUES (?, ?, ?)",
                    (42, "legacy-model", "legacy-policy"),
                )
                connection.commit()
            finally:
                connection.close()
            original = shadow.SHADOW_DB
            shadow.SHADOW_DB = db_path
            try:
                self.assertFalse(shadow._current_prediction_exists(42))
                connection = shadow._connect()
                try:
                    connection.execute(
                        "INSERT INTO predictions VALUES (?, ?, ?)",
                        (
                            42,
                            shadow.SHADOW_MODEL_VERSION,
                            shadow.SHADOW_POLICY_VERSION,
                        ),
                    )
                    connection.commit()
                finally:
                    connection.close()
                self.assertTrue(shadow._current_prediction_exists(42))
            finally:
                shadow.SHADOW_DB = original


class ShadowVerdictTest(unittest.TestCase):
    def test_positive_average_before_300_closings_stays_in_evidence_building(self):
        verdict = shadow._verdict({
            "clv_bets": 999,
            "independent_clv_fixtures": 299,
            "evidence_valid": True,
            "cohort_versioned": True,
            "duplicate_fixture_groups": 0,
            "avg_clv": 4.5,
        })

        self.assertIn("299/300", verdict)
        self.assertIn("Evidenzaufbau", verdict)
        self.assertIn("keine Freigabediskussion", verdict)
        for premature_claim in ("positiv", "schlägt", "Edge"):
            self.assertNotIn(premature_claim, verdict)

    def test_review_stage_does_not_label_one_window_as_a_trend(self):
        verdict = shadow._verdict({
            "clv_bets": 300,
            "independent_clv_fixtures": 300,
            "evidence_valid": True,
            "cohort_versioned": True,
            "duplicate_fixture_groups": 0,
            "avg_clv": 1.25,
        })

        self.assertIn("Prüfstufe", verdict)
        self.assertNotIn("Trend", verdict)
        self.assertIn("keine Echtgeldfreigabe", verdict)
        self.assertIn("No-Vig-Benchmark", verdict)
        self.assertIn("Konfidenz", verdict)

    def test_duplicate_fixture_evidence_blocks_review_even_above_threshold(self):
        verdict = shadow._verdict({
            "clv_bets": 999,
            "independent_clv_fixtures": 999,
            "evidence_valid": False,
            "cohort_versioned": True,
            "duplicate_fixture_groups": 1,
            "avg_clv": 9.99,
        })

        self.assertIn("Evidenz gesperrt", verdict)
        self.assertIn("doppelte Fixture", verdict)
        self.assertIn("Keine Freigabediskussion", verdict)
        self.assertNotIn("Prüfstufe erreicht", verdict)

    def test_missing_integrity_metadata_never_falls_back_to_raw_row_count(self):
        verdict = shadow._verdict({"clv_bets": 999, "avg_clv": 9.99})

        self.assertIn("Evidenz gesperrt", verdict)
        self.assertIn("Integritätsmetadaten", verdict)
        self.assertNotIn("Prüfstufe erreicht", verdict)

    def test_malformed_or_unproven_rows_block_review_above_threshold(self):
        verdict = shadow._verdict({
            "clv_bets": 300,
            "independent_clv_fixtures": 300,
            "evidence_valid": False,
            "cohort_versioned": True,
            "duplicate_fixture_groups": 0,
            "invalid_evidence_rows": 1,
            "avg_clv": 9.99,
        })

        self.assertIn("Evidenz gesperrt", verdict)
        self.assertIn("Opening-/Closing-Provenienz", verdict)
        self.assertIn("Keine Freigabediskussion", verdict)
        self.assertNotIn("Prüfstufe erreicht", verdict)


if __name__ == "__main__":
    unittest.main()
