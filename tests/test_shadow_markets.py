"""Tests für das Shadow-Automation-Modul (Quoten-Mapping + Settlement-Integrität)."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

AUTOMATION_PATH = (
    Path.home()
    / "AppData/Roaming/kimi-desktop/daimon-share/daimon/agents/main/blueprint/automations"
    / "automation_14f34375-c87b-4932-b9cd-efc6be447879/assets/automation.py"
)

spec = importlib.util.spec_from_file_location("shadow_automation", AUTOMATION_PATH)
shadow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shadow)

from challenge_engine import MARKET_BY_KEY, MARKET_SPECS, market_outcome  # noqa: E402


def _odds_response(bookmaker_name="Bet365", bets=None):
    return [{
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


class QuoteMappingIntegrityTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
