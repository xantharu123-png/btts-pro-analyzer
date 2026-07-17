import os
import math
import sqlite3
import tempfile
import tomllib
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from advanced_analyzer import (
    BivariatePoissonModel,
    DixonColesModel,
    beta_smoothed_percentage,
    build_prematch_training_rows,
)
from alternative_markets import negative_binomial_probability, poisson_probability
from api_football import APIFootball
from best_bet_finder import BestBetFinder
from betboy_v3_ml_engine import BacktestingEngine, MLEnsemble, MatchFeatures
from betting_math import BettingMathError, evaluate_market_price
from clv_tracker import CLVTracker
from config_loader import load_app_config
import data_engine
from league_catalog import ANALYZER_LEAGUE_IDS, LEAGUE_BY_ID
from red_card_impact_predictor import RedCardImpactPredictor
from scanners.cricket_scanner import CricketScanner
from scanners.esports_scanner import EsportsScanner
from season_utils import (
    current_season_start_year,
    current_season_start_year_for_id,
)
from smart_bet_finder import SmartBetFinder
from train_ml_models import FeatureEngineer, HistoricalDataCollector
from ultra_live_scanner_v3 import UltraLiveScanner


class ConfigLoaderTests(unittest.TestCase):
    def test_env_overrides_ini(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.ini"
            config_path.write_text("[api]\napi_football_key = ini_key\n", encoding="utf-8")

            old_value = os.environ.get("API_FOOTBALL_KEY")
            os.environ["API_FOOTBALL_KEY"] = "env_key"
            try:
                config = load_app_config(config_path=config_path)
            finally:
                if old_value is None:
                    os.environ.pop("API_FOOTBALL_KEY", None)
                else:
                    os.environ["API_FOOTBALL_KEY"] = old_value

            self.assertEqual(config.api_football_key, "env_key")


class DeploymentConfigTests(unittest.TestCase):
    def test_streamlit_request_protections_are_enabled(self):
        config_path = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))

        self.assertIs(config["server"]["enableXsrfProtection"], True)
        self.assertIs(config["server"]["enableCORS"], True)


class SmartBetFinderTests(unittest.TestCase):
    @staticmethod
    def _validation():
        now = datetime.now(timezone.utc)
        return {
            "btts_yes": {
                "calibrated": True,
                "out_of_sample": True,
                "sample_size": 500,
                "calibration_bins": 5,
                "min_bin_size": 40,
                "expected_calibration_error": 0.02,
                "max_calibration_error": 0.07,
                "method": "expanding_window_isotonic",
                "model_version": "test-v1",
                "validation_start": (now - timedelta(days=180)).isoformat(),
                "validation_end": (now - timedelta(days=1)).isoformat(),
                "league_ids": [39],
            }
        }

    @classmethod
    def _analysis(cls, **updates):
        payload = {
            "fixture_id": 123,
            "league_id": 39,
            "fixture_date": (
                datetime.now(timezone.utc) + timedelta(days=1)
            ).isoformat(),
            "market_validation": cls._validation(),
        }
        payload.update(updates)
        return payload

    @staticmethod
    def _quote(odds=2.1):
        return {
            "best_odds": odds,
            "bookmaker": "TestBook",
            "all_odds": {"TestBook": odds},
            "source": "test_api",
            "quoted_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def _btts_quotes(cls):
        return {
            "btts_yes": cls._quote(2.1),
            "btts_no": cls._quote(1.8),
        }

    def test_value_bets_require_real_market_price(self):
        finder = SmartBetFinder()
        finder.odds_client.get_match_odds = lambda *args, **kwargs: {}

        bets = finder.find_value_bets(
            self._analysis(btts_probability=80),
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(bets, [])

    def test_model_only_output_is_explicitly_non_actionable(self):
        estimates = SmartBetFinder().find_model_signals(
            {"btts_probability": 80.0}
        )

        self.assertEqual(len(estimates), 1)
        self.assertEqual(estimates[0].recommendation_type, "EXPLORATORY_ESTIMATE")
        self.assertFalse(estimates[0].calibrated)
        self.assertFalse(estimates[0].actionable)
        self.assertIsNone(estimates[0].real_odds)
        self.assertIsNone(estimates[0].kelly_stake)

    def test_value_bet_uses_market_price_only_after_model_probability(self):
        finder = SmartBetFinder()
        finder.odds_client.get_match_odds = lambda *args, **kwargs: self._btts_quotes()

        bets = finder.find_value_bets(
            self._analysis(btts_probability=80),
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].sub_market, "btts_yes")
        self.assertAlmostEqual(bets[0].risk_adjusted_probability, 73.0)
        self.assertAlmostEqual(bets[0].edge, 25.4, places=1)
        self.assertGreater(bets[0].point_edge, 30)
        self.assertLessEqual(bets[0].kelly_stake, 2.0)
        self.assertTrue(bets[0].calibrated)
        self.assertTrue(bets[0].actionable)
        self.assertEqual(bets[0].bookmaker, "TestBook")

    def test_value_bet_requires_exact_fixture_binding(self):
        finder = SmartBetFinder()
        calls = []
        finder.odds_client.get_match_odds = lambda *args, **kwargs: calls.append(
            (args, kwargs)
        ) or self._btts_quotes()

        analysis = self._analysis(btts_probability=80)
        analysis.pop("fixture_id")
        bets = finder.find_value_bets(
            analysis,
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(bets, [])
        self.assertEqual(calls, [])

    def test_kelly_output_is_bankroll_percent(self):
        finder = SmartBetFinder()
        stake_percent = finder._calculate_kelly_stake(80, 2.0)

        self.assertEqual(stake_percent, 2.0)

    def test_bad_quote_does_not_discard_valid_market_values(self):
        finder = SmartBetFinder()
        parsed = finder.odds_client._parse_api_football_odds([{
            "bookmakers": [{
                "name": "Book",
                "bets": [{
                    "name": "Both Teams Score",
                    "values": [
                        {"value": "Yes", "odd": "bad"},
                        {"value": "No", "odd": "2.05"},
                    ],
                }],
            }],
        }])

        self.assertNotIn("btts_yes", parsed)
        self.assertEqual(parsed["btts_no"]["best_odds"], 2.05)

    def test_fuzzy_odds_fixture_binding_rejects_large_kickoff_gap(self):
        kickoff = datetime.now(timezone.utc)

        self.assertTrue(SmartBetFinder().odds_client._kickoff_matches(
            kickoff.isoformat(),
            (kickoff + timedelta(minutes=90)).isoformat(),
        ))
        self.assertFalse(SmartBetFinder().odds_client._kickoff_matches(
            kickoff.isoformat(),
            (kickoff + timedelta(hours=3)).isoformat(),
        ))

    def test_value_bets_require_calibrated_market(self):
        finder = SmartBetFinder()
        finder.odds_client.get_match_odds = lambda *args, **kwargs: self._btts_quotes()

        analysis = self._analysis(btts_probability=80)
        analysis.pop("market_validation")
        analysis["validated_markets"] = ["btts_yes"]
        bets = finder.find_value_bets(
            analysis,
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(bets, [])

    def test_stale_quote_is_rejected(self):
        finder = SmartBetFinder()
        stale_quote = self._quote()
        stale_quote["quoted_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        quotes = self._btts_quotes()
        quotes["btts_yes"] = stale_quote
        finder.odds_client.get_match_odds = lambda *args, **kwargs: quotes

        bets = finder.find_value_bets(
            self._analysis(btts_probability=80),
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(bets, [])

    def test_incomplete_market_cannot_pass_quote_integrity_gate(self):
        finder = SmartBetFinder()
        finder.odds_client.get_match_odds = lambda *args, **kwargs: {
            "btts_yes": self._quote(2.1),
        }

        bets = finder.find_value_bets(
            self._analysis(btts_probability=80),
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(bets, [])

    def test_calibration_haircut_removes_fragile_point_edge(self):
        finder = SmartBetFinder()
        finder.odds_client.get_match_odds = lambda *args, **kwargs: {
            "btts_yes": self._quote(2.0),
            "btts_no": self._quote(2.0),
        }

        bets = finder.find_value_bets(
            self._analysis(btts_probability=55),
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(bets, [])

    def test_only_one_correlated_selection_is_staked_per_fixture(self):
        finder = SmartBetFinder()
        validations = self._validation()
        validations["over_2.5"] = dict(validations["btts_yes"])
        finder.odds_client.get_match_odds = lambda *args, **kwargs: {
            **self._btts_quotes(),
            "over_2.5": self._quote(2.0),
            "under_2.5": self._quote(1.9),
        }

        bets = finder.find_value_bets(
            self._analysis(
                btts_probability=80,
                **{
                    "over_2.5_probability": 75,
                    "market_validation": validations,
                },
            ),
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].sub_market, "btts_yes")

    def test_probability_units_are_explicit_and_coherent(self):
        finder = SmartBetFinder()
        percent = finder._extract_all_probabilities({
            "match_result": {
                "home_win": 0.8,
                "draw": 49.2,
                "away_win": 50.0,
                "probability_unit": "percent",
            },
            "btts": {
                "yes": 61.0,
                "no": 39.0,
                "probability_unit": "percent",
            },
        })
        decimal = finder._extract_all_probabilities({
            "match_result": {
                "home_win": 0.4,
                "draw": 0.3,
                "away_win": 0.3,
                "probability_unit": "decimal",
            },
        })
        incoherent = finder._extract_all_probabilities({
            "match_result": {
                "home_win": 60,
                "draw": 30,
                "away_win": 30,
                "probability_unit": "percent",
            },
        })

        self.assertEqual(percent["home_win"], 0.8)
        self.assertEqual(percent["btts_yes"], 61.0)
        self.assertEqual(decimal["home_win"], 40.0)
        self.assertTrue({'home_win', 'draw', 'away_win'}.isdisjoint(incoherent))

    def test_calibration_must_precede_fixture_and_cover_league(self):
        wrong_league = self._analysis(btts_probability=80)
        wrong_league["market_validation"]["btts_yes"]["league_ids"] = [78]
        future_validation = self._analysis(btts_probability=80)
        future_validation["market_validation"]["btts_yes"]["validation_end"] = (
            datetime.now(timezone.utc) + timedelta(days=2)
        ).isoformat()

        self.assertEqual(SmartBetFinder._validated_markets(wrong_league), {})
        self.assertEqual(SmartBetFinder._validated_markets(future_validation), {})


class BettingMathTests(unittest.TestCase):
    def test_negative_kelly_is_zero(self):
        metrics = evaluate_market_price(40, 2.0)

        self.assertLess(metrics.expected_roi, 0)
        self.assertEqual(metrics.kelly_fraction, 0)

    def test_invalid_decimal_odds_are_rejected(self):
        with self.assertRaises(BettingMathError):
            evaluate_market_price(60, 1.0)
        with self.assertRaises(BettingMathError):
            evaluate_market_price(True, 2.0)

    def test_kelly_uses_risk_adjusted_probability(self):
        metrics = evaluate_market_price(
            60,
            2.0,
            probability_haircut=7.0,
        )

        self.assertAlmostEqual(metrics.expected_roi, 20.0)
        self.assertAlmostEqual(metrics.risk_adjusted_expected_roi, 6.0)
        self.assertAlmostEqual(metrics.kelly_fraction, 0.015)


class GoalModelTests(unittest.TestCase):
    def test_small_empirical_rate_is_beta_smoothed(self):
        self.assertAlmostEqual(beta_smoothed_percentage(100.0, 2), 75.0)
        self.assertAlmostEqual(beta_smoothed_percentage(50.0, 20), 50.0)

    def test_zero_dependence_matches_independent_btts_formula(self):
        home_rate = 1.4
        away_rate = 1.1
        expected = (
            (1 - math.exp(-home_rate))
            * (1 - math.exp(-away_rate))
            * 100
        )

        dixon_coles = DixonColesModel(rho=0.0)
        bivariate = BivariatePoissonModel(covariance=0.0)

        self.assertAlmostEqual(
            dixon_coles.calculate_btts_probability(home_rate, away_rate),
            expected,
            places=5,
        )
        self.assertAlmostEqual(
            bivariate.calculate_btts_probability(home_rate, away_rate),
            expected,
            places=5,
        )

    def test_dixon_coles_tau_uses_goal_rates(self):
        model = DixonColesModel(rho=-0.05)
        self.assertAlmostEqual(model.tau(0, 0, 1.4, 1.1), 1.077)
        self.assertAlmostEqual(model.tau(1, 0, 1.4, 1.1), 0.945)

    def test_no_remaining_time_means_no_future_goal_probability(self):
        scanner = UltraLiveScanner.__new__(UltraLiveScanner)

        btts = scanner._calculate_btts_probability(1, 0, 1.4, 1.1, 93)
        next_goal = scanner._calculate_next_goal(1, 0, 1.4, 1.1, 93, {})

        self.assertEqual(btts['probability'], 0.0)
        self.assertEqual(next_goal['home_prob'], 0.0)
        self.assertEqual(next_goal['away_prob'], 0.0)
        self.assertEqual(next_goal['no_goal_prob'], 100.0)

    def test_count_distributions_are_normalized_and_have_expected_mean(self):
        self.assertEqual(poisson_probability(0, 0), 1.0)
        probabilities = [negative_binomial_probability(k, 4.0, 0.3) for k in range(100)]
        self.assertAlmostEqual(sum(probabilities), 1.0, places=6)
        self.assertAlmostEqual(
            sum(k * probability for k, probability in enumerate(probabilities)),
            4.0,
            places=5,
        )


class SeasonUtilsTests(unittest.TestCase):
    def test_european_season_rolls_in_july(self):
        self.assertEqual(current_season_start_year("PL", date(2026, 6, 30)), 2025)
        self.assertEqual(current_season_start_year("PL", date(2026, 7, 1)), 2026)

    def test_calendar_year_league_uses_current_year(self):
        self.assertEqual(current_season_start_year("BSA", date(2026, 2, 1)), 2026)

    def test_provider_verified_ids_have_one_canonical_meaning(self):
        self.assertEqual(ANALYZER_LEAGUE_IDS["SPL"], 265)
        self.assertEqual(LEAGUE_BY_ID[265].country, "Chile")
        self.assertEqual(LEAGUE_BY_ID[292].name, "K League 1")
        self.assertEqual(LEAGUE_BY_ID[274].country, "Indonesia")

    def test_calendar_year_season_by_id(self):
        self.assertEqual(
            current_season_start_year_for_id(292, date(2026, 2, 1)),
            2026,
        )
        self.assertEqual(
            current_season_start_year_for_id(188, date(2026, 7, 1)),
            2025,
        )


class MLFeatureTests(unittest.TestCase):
    def test_current_match_result_cannot_change_its_own_features(self):
        history = [
            (1, 1),
            (0, 1),
            (2, 0),
            (1, 2),
            (0, 0),
        ]
        rows = []
        for index, (home_goals, away_goals) in enumerate(history, start=1):
            rows.append({
                "id": index,
                "date": f"2026-01-{index:02d}",
                "league_code": "PL",
                "home_team_id": 1,
                "away_team_id": 2,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "btts": int(home_goals > 0 and away_goals > 0),
            })

        with_btts = rows + [{
            "id": 6,
            "date": "2026-01-06",
            "league_code": "PL",
            "home_team_id": 1,
            "away_team_id": 2,
            "home_goals": 2,
            "away_goals": 2,
            "btts": 1,
        }]
        without_btts = rows + [{
            "id": 6,
            "date": "2026-01-06",
            "league_code": "PL",
            "home_team_id": 1,
            "away_team_id": 2,
            "home_goals": 5,
            "away_goals": 0,
            "btts": 0,
        }]

        X_with, y_with = build_prematch_training_rows(pd.DataFrame(with_btts))
        X_without, y_without = build_prematch_training_rows(pd.DataFrame(without_btts))

        np.testing.assert_allclose(X_with[0], X_without[0])
        self.assertEqual(X_with[0][0], 40.0)
        self.assertNotEqual(y_with[0], y_without[0])


class DataEngineMigrationTests(unittest.TestCase):
    def test_unreachable_postgres_falls_back_to_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fallback.db"
            original_url = data_engine._SUPABASE_URL_CACHE

            def connection_for_backend(engine):
                if engine.use_postgres:
                    raise RuntimeError("tenant not found")
                return sqlite3.connect(engine.db_path)

            try:
                data_engine._SUPABASE_URL_CACHE = "postgresql://configured.invalid/db"
                with patch("data_engine._check_postgres", return_value=True), patch.object(
                    data_engine.DataEngine,
                    "_get_connection",
                    connection_for_backend,
                ):
                    engine = data_engine.DataEngine(api_key="test", db_path=str(db_path))
            finally:
                data_engine._SUPABASE_URL_CACHE = original_url

            self.assertFalse(engine.use_postgres)
            self.assertIsNone(engine.supabase_url)
            self.assertIn("SQLite", engine.database_warning)
            self.assertEqual(engine.get_match_count(), 0)

    def test_legacy_sqlite_matches_schema_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE teams (
                    team_id INTEGER,
                    name TEXT,
                    short_name TEXT,
                    league_code TEXT,
                    last_updated TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE matches (
                    match_id INTEGER,
                    home_team_id INTEGER,
                    away_team_id INTEGER,
                    league_code TEXT,
                    match_date TEXT,
                    home_score INTEGER,
                    away_score INTEGER,
                    status TEXT,
                    btts INTEGER,
                    total_goals INTEGER,
                    last_updated TEXT
                )
                """
            )
            cur.execute("INSERT INTO teams VALUES (1, 'Home FC', 'HOM', 'PL', 'now')")
            cur.execute("INSERT INTO teams VALUES (2, 'Away FC', 'AWY', 'PL', 'now')")
            cur.execute(
                "INSERT INTO matches VALUES (10, 1, 2, 'PL', '2025-05-01', 2, 1, 'FT', 1, 3, 'now')"
            )
            conn.commit()
            conn.close()

            data_engine._SUPABASE_URL_CACHE = None
            engine = data_engine.DataEngine(api_key="test", db_path=str(db_path))

            self.assertEqual(engine.get_match_count("PL"), 1)
            stats = engine.get_team_stats(1, "PL", "home")
            self.assertEqual(stats["matches_played"], 1)
            self.assertEqual(stats["avg_scored"], 2.0)

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(matches)")
            columns = {row[1] for row in cur.fetchall()}
            cur.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            tables = {row[0] for row in cur.fetchall()}
            conn.close()

            self.assertIn("id", columns)
            self.assertIn("home_goals", columns)
            self.assertIn("matches_legacy", tables)

    def test_no_data_is_none_and_observed_zero_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "stats.db"
            data_engine._SUPABASE_URL_CACHE = None
            engine = data_engine.DataEngine(api_key="test", db_path=str(db_path))

            empty = engine.get_team_stats(1, "PL", "home")
            self.assertEqual(empty["matches_played"], 0)
            self.assertIsNone(empty["avg_scored"])

            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO matches (
                        id, league_code, league_id, date, home_team, away_team,
                        home_team_id, away_team_id, home_goals, away_goals,
                        btts, total_goals, fetched_at
                    ) VALUES (1, 'PL', 39, '2026-01-01', 'Home', 'Away',
                              1, 2, 0, 0, 0, 0, 'now')
                    """
                )
                conn.commit()
            finally:
                conn.close()

            stats = engine.get_team_stats(1, "PL", "home")
            form = engine.get_recent_form(1, "PL", "home")
            league = engine.get_league_stats("PL")
            self.assertEqual(stats["avg_scored"], 0.0)
            self.assertEqual(stats["avg_conceded"], 0.0)
            self.assertEqual(stats["btts_rate"], 0.0)
            self.assertEqual(form["avg_scored"], 0.0)
            self.assertEqual(league["avg_total_goals"], 0.0)

    def test_finished_fixture_with_missing_score_is_not_stored_as_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fetch.db"
            data_engine._SUPABASE_URL_CACHE = None
            engine = data_engine.DataEngine(api_key="test", db_path=str(db_path))
            response = Mock(status_code=200)
            response.json.return_value = {
                "response": [{
                    "fixture": {"id": 7, "date": "2026-01-01T12:00:00Z"},
                    "teams": {
                        "home": {"id": 1, "name": "Home"},
                        "away": {"id": 2, "name": "Away"},
                    },
                    "goals": {"home": None, "away": 0},
                }]
            }
            with patch("data_engine.requests.get", return_value=response):
                stored = engine.fetch_league_matches("PL", season=2025)

            self.assertEqual(stored, 0)
            self.assertEqual(engine.get_match_count("PL"), 0)

    def test_data_refresh_exposes_provider_error_returned_with_http_200(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "provider-error.db"
            data_engine._SUPABASE_URL_CACHE = None
            engine = data_engine.DataEngine(api_key="test", db_path=str(db_path))
            response = Mock(status_code=200)
            response.json.return_value = {
                "errors": {"access": "Your account is suspended"},
                "response": [],
            }
            with patch("data_engine.requests.get", return_value=response):
                stored = engine.fetch_league_matches("PL", season=2025)

            self.assertEqual(stored, 0)
            self.assertIn("suspended", engine.last_error)


class APIOrientationTests(unittest.TestCase):
    def test_live_statistics_are_mapped_by_team_id_not_response_order(self):
        api = APIFootball("test")
        api._rate_limit = lambda: None
        response = Mock(status_code=200)
        response.json.return_value = {
            "response": [
                {
                    "team": {"id": 2},
                    "statistics": [{"type": "Corner Kicks", "value": 7}],
                },
                {
                    "team": {"id": 1},
                    "statistics": [{"type": "Corner Kicks", "value": 3}],
                },
            ]
        }
        with patch("api_football.requests.get", return_value=response):
            stats = api.get_match_statistics(99, 1, 2)

        self.assertEqual(stats["corners_home"], 3.0)
        self.assertEqual(stats["corners_away"], 7.0)


class CLVTrackerTests(unittest.TestCase):
    def test_quote_provenance_order_settlement_and_statistics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = CLVTracker(str(Path(tmp) / "clv.db"))
            now = datetime.now(timezone.utc)
            opening_time = now - timedelta(minutes=1)
            kickoff_time = now + timedelta(minutes=10)
            prediction_id = tracker.record_prediction(
                10,
                "Home",
                "Away",
                "BTTS",
                "YES",
                2.0,
                55.0,
                bookmaker="Book A",
                quote_source="API",
                fixture_kickoff=kickoff_time,
                quoted_at=opening_time,
            )
            with self.assertRaises(ValueError):
                tracker.update_closing_odds(
                    prediction_id,
                    1.8,
                    bookmaker="Book A",
                    quote_source="API",
                    quoted_at=opening_time - timedelta(minutes=1),
                )
            tracker.update_closing_odds(
                prediction_id,
                1.8,
                bookmaker="Book A",
                quote_source="API",
                quoted_at=now,
            )
            tracker.settle_prediction(prediction_id, "Won", 2, 1)
            with self.assertRaises(ValueError):
                tracker.settle_prediction(prediction_id, "Lost", 2, 1)

            stats = tracker.get_clv_statistics(days=10000)
            self.assertEqual(stats["total_bets"], 1)
            self.assertEqual(stats["clv_bets"], 1)
            self.assertAlmostEqual(stats["avg_clv"], 11.11, places=2)
            self.assertEqual(stats["roi"], 100.0)

    def test_opening_quote_requires_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = CLVTracker(str(Path(tmp) / "clv.db"))
            with self.assertRaises(ValueError):
                tracker.record_prediction(
                    10,
                    "Home",
                    "Away",
                    "BTTS",
                    "YES",
                    2.0,
                    55.0,
                    bookmaker="",
                    quote_source="API",
                    fixture_kickoff=datetime.now(timezone.utc) + timedelta(minutes=10),
                )

    def test_closing_quote_must_be_in_pre_kickoff_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = CLVTracker(str(Path(tmp) / "clv.db"))
            now = datetime.now(timezone.utc)
            prediction_id = tracker.record_prediction(
                10,
                "Home",
                "Away",
                "BTTS",
                "YES",
                2.0,
                55.0,
                bookmaker="Book A",
                quote_source="API",
                fixture_kickoff=now + timedelta(hours=1),
                quoted_at=now,
            )

            with self.assertRaises(ValueError):
                tracker.update_closing_odds(
                    prediction_id,
                    1.9,
                    bookmaker="Book A",
                    quote_source="API",
                    quoted_at=now,
                )

    def test_stale_opening_quote_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = CLVTracker(str(Path(tmp) / "clv.db"))
            now = datetime.now(timezone.utc)

            with self.assertRaises(ValueError):
                tracker.record_prediction(
                    10,
                    "Home",
                    "Away",
                    "BTTS",
                    "YES",
                    2.0,
                    55.0,
                    bookmaker="Book A",
                    quote_source="API",
                    fixture_kickoff=now + timedelta(hours=1),
                    quoted_at=now - timedelta(minutes=11),
                )


class RedCardModelTests(unittest.TestCase):
    def test_minute_93_has_deterministic_current_result(self):
        prediction = RedCardImpactPredictor().predict(
            minute=93,
            home_goals=2,
            away_goals=1,
            red_card_team="home",
        )

        self.assertEqual(prediction.next_goal_probability, 0.0)
        self.assertEqual(prediction.no_more_goals, 1.0)
        self.assertAlmostEqual(prediction.red_team_wins, 1.0)
        self.assertAlmostEqual(prediction.draw, 0.0)
        self.assertAlmostEqual(prediction.opponent_wins, 0.0)
        self.assertFalse(prediction.calibrated)
        self.assertFalse(prediction.actionable)


class UltraDataGateTests(unittest.TestCase):
    def test_missing_xg_and_prior_produces_no_probability(self):
        scanner = UltraLiveScanner(None, None)
        home_mean, away_mean, quality = scanner._remaining_goal_means(
            None,
            None,
            30,
        )

        self.assertIsNone(home_mean)
        self.assertIsNone(away_mean)
        self.assertEqual(quality, "INSUFFICIENT")

    def test_shots_are_not_used_as_synthetic_xg(self):
        class FakeAPI:
            @staticmethod
            def get_match_statistics(*args):
                return {"shots_home": 12, "shots_away": 8}

        scanner = UltraLiveScanner(None, FakeAPI())
        result = scanner.analyze_live_match_ultra({
            "fixture": {"id": 1, "status": {"elapsed": 45}},
            "teams": {
                "home": {"id": 10, "name": "Home"},
                "away": {"id": 20, "name": "Away"},
            },
            "goals": {"home": 0, "away": 0},
            "league": {"id": 39, "name": "Premier League"},
        })

        self.assertIsNone(result["btts_prob"])
        self.assertEqual(result["btts_confidence"], "INSUFFICIENT")
        self.assertFalse(result["calibrated"])
        self.assertFalse(result["actionable"])
        self.assertEqual(result["recommendation_type"], "EXPLORATORY_ESTIMATE")


class CrossSportMathTests(unittest.TestCase):
    @staticmethod
    def _esports_match(score1=0, score2=0):
        return {
            "id": 1,
            "game": "CS2",
            "team1": "Alpha",
            "team2": "Beta",
            "team1_score": score1,
            "team2_score": score2,
            "series_type": 3,
            "team1_stats": {
                "win_rate": 70.0,
                "matches": 20,
                "wins": 14,
                "form": ["W", "W", "L"],
            },
            "team2_stats": {
                "win_rate": 45.0,
                "matches": 20,
                "wins": 9,
                "form": ["L", "W", "L"],
            },
        }

    def test_cricket_decimal_over_notation_counts_balls(self):
        scanner = CricketScanner.__new__(CricketScanner)
        run_rate = scanner._calculate_run_rate({
            "team1Score": {"inngs1": {"runs": 102, "overs": 8.3}},
            "team2Score": {},
        })

        self.assertEqual(run_rate, 12.0)

    def test_esports_series_probability_is_exact_first_to_n_recursion(self):
        self.assertAlmostEqual(
            EsportsScanner._series_win_probability(0.5, 0, 0, 2),
            0.5,
        )
        self.assertAlmostEqual(
            EsportsScanner._series_win_probability(0.5, 1, 0, 2),
            0.75,
        )
        self.assertEqual(
            EsportsScanner._series_win_probability(0.5, 2, 0, 2),
            1.0,
        )

    def test_esports_estimate_is_never_exposed_as_actionable_or_fair_price(self):
        scanner = EsportsScanner.__new__(EsportsScanner)
        result = scanner.analyze_match(self._esports_match())

        self.assertIsNotNone(result)
        self.assertFalse(result["calibrated"])
        self.assertFalse(result["actionable"])
        self.assertIsNone(result["model_price"])
        self.assertEqual(result["recommendation_type"], "EXPLORATORY_ESTIMATE")

    def test_esports_rejects_completed_or_invalid_series_state(self):
        scanner = EsportsScanner.__new__(EsportsScanner)

        self.assertIsNone(scanner.analyze_match(self._esports_match(2, 0)))
        self.assertIsNone(scanner.analyze_match(self._esports_match("bad", 0)))

    def test_best_bet_ranker_rejects_uncalibrated_inputs(self):
        result = BestBetFinder().find_best_bet(
            {
                "market_probabilities": [{
                    "market": "BTTS",
                    "selection": "YES",
                    "probability": 80,
                    "source": "test",
                    "calibrated": False,
                }]
            },
            minute=20,
            stats={},
        )

        self.assertEqual(result["status"], "NO_CALIBRATED_SIGNALS")
        self.assertEqual(result["all_bets"], [])


class V3EngineTests(unittest.TestCase):
    @staticmethod
    def _initialize_logistic_only(ensemble):
        ensemble.models = {
            "logistic": LogisticRegression(max_iter=1000, random_state=42),
        }

    def test_model_selection_requires_untouched_final_holdout(self):
        rng = np.random.default_rng(42)
        features = rng.normal(size=(300, len(MatchFeatures.feature_names())))
        labels = (features[:, 0] + 0.2 * features[:, 1] > 0).astype(int)

        with patch.object(
            MLEnsemble,
            "_initialize_models",
            self._initialize_logistic_only,
        ):
            ensemble = MLEnsemble(target="btts")
            scores = ensemble.train(features, labels, target="btts")

        self.assertTrue(ensemble.is_trained)
        self.assertTrue(scores["logistic"]["holdout_passed"])
        self.assertEqual(scores["logistic"]["selection_sample_size"], 240)
        self.assertEqual(scores["logistic"]["holdout_sample_size"], 60)

    def test_regime_reversal_fails_untouched_final_holdout(self):
        rng = np.random.default_rng(7)
        features = rng.normal(size=(300, len(MatchFeatures.feature_names())))
        labels = (features[:, 0] > 0).astype(int)
        labels[-60:] = 1 - labels[-60:]

        with patch.object(
            MLEnsemble,
            "_initialize_models",
            self._initialize_logistic_only,
        ):
            ensemble = MLEnsemble(target="btts")
            scores = ensemble.train(features, labels, target="btts")

        self.assertFalse(ensemble.is_trained)
        self.assertFalse(scores["logistic"]["holdout_passed"])

    def test_active_feature_schema_has_only_ten_reproducible_values(self):
        features = MatchFeatures(
            home_attack_strength=1,
            home_defense_strength=2,
            away_attack_strength=3,
            away_defense_strength=4,
            home_form_goals_scored=5,
            home_form_goals_conceded=6,
            away_form_goals_scored=7,
            away_form_goals_conceded=8,
            home_form_points=9,
            away_form_points=10,
            home_xg_for=99,
        )

        self.assertEqual(len(features.to_array()), 10)
        self.assertEqual(len(MatchFeatures.feature_names()), 10)
        self.assertNotIn(99, features.to_array())

    def test_no_string_truthiness_in_backtest_result(self):
        backtest = BacktestingEngine()
        prediction_time = datetime.now(timezone.utc) - timedelta(days=1)
        backtest.add_prediction(
            {"btts": {"prediction": "NO", "no": 70}},
            {"btts": "NO"},
            fixture_id=1,
            league_id=39,
            predicted_at=prediction_time,
            fixture_kickoff=prediction_time + timedelta(hours=2),
            model_trained_until=prediction_time - timedelta(days=1),
            model_version="test-v1",
        )

        metrics = backtest.calculate_accuracy("btts")
        self.assertEqual(metrics["accuracy"], 1.0)
        self.assertIsNone(metrics["roi"])

    def test_backtest_rejects_prediction_before_training_cutoff(self):
        backtest = BacktestingEngine()
        prediction_time = datetime.now(timezone.utc) - timedelta(days=1)

        with self.assertRaises(ValueError):
            backtest.add_prediction(
                {"btts": {"prediction": "YES", "yes": 70}},
                {"btts": "YES"},
                fixture_id=1,
                league_id=39,
                predicted_at=prediction_time,
                fixture_kickoff=prediction_time + timedelta(hours=2),
                model_trained_until=prediction_time + timedelta(minutes=1),
                model_version="test-v1",
            )

    def test_feature_engineer_waits_for_five_prior_matches(self):
        rows = []
        for index in range(12):
            rows.append({
                "fixture_id": index + 1,
                "date": f"2026-01-{index + 1:02d}",
                "league_id": 39,
                "home_team_id": 1,
                "away_team_id": 2,
                "home_goals": index % 3,
                "away_goals": (index + 1) % 2,
                "result_code": 0,
                "btts": 0,
                "over_25": 0,
                "total_goals": 1,
            })

        features = FeatureEngineer(pd.DataFrame(rows)).calculate_features()
        self.assertEqual(len(features), 7)
        self.assertEqual(features.iloc[0]["fixture_id"], 6)

    def test_historical_collector_skips_missing_final_score(self):
        collector = HistoricalDataCollector("test")
        frame = collector._parse_fixtures([
            {
                "fixture": {"id": 1, "date": "2026-01-01"},
                "teams": {"home": {"id": 1}, "away": {"id": 2}},
                "goals": {"home": None, "away": 0},
                "score": {},
            },
            {
                "fixture": {"id": 2, "date": "2026-01-02"},
                "teams": {"home": {"id": 1}, "away": {"id": 2}},
                "goals": {"home": 0, "away": 0},
                "score": {},
            },
        ], 39)

        self.assertEqual(frame["fixture_id"].tolist(), [2])


if __name__ == "__main__":
    unittest.main()
