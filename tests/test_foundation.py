import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from config_loader import load_app_config
import data_engine
from smart_bet_finder import SmartBetFinder


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


class SmartBetFinderTests(unittest.TestCase):
    def test_value_bets_require_real_market_price(self):
        finder = SmartBetFinder()
        finder.odds_client.get_match_odds = lambda home, away: {}

        bets = finder.find_value_bets(
            {"btts_probability": 80},
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(bets, [])

    def test_value_bet_uses_market_price_only_after_model_probability(self):
        finder = SmartBetFinder()
        finder.odds_client.get_match_odds = lambda home, away: {
            "btts_yes": {"best_odds": 2.1, "bookmaker": "TestBook", "all_odds": {}}
        }

        bets = finder.find_value_bets(
            {"btts_probability": 80},
            home_team="Home",
            away_team="Away",
        )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].sub_market, "btts_yes")
        self.assertGreater(bets[0].edge, 30)
        self.assertEqual(bets[0].bookmaker, "TestBook")


class DataEngineMigrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
