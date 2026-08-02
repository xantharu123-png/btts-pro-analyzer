"""EV-Rechner: fairen Preis, Break-even und Urteilslogik prüfen."""

from __future__ import annotations

import unittest

from ev_calculator import (
    DEFAULT_PROBABILITY_UNCERTAINTY,
    MIN_EXPECTED_ROI_FOR_BET,
    VERDICT_BET,
    VERDICT_CLOSE,
    VERDICT_NO_BET,
    breakeven_probability,
    conservative_probability,
    edge_points,
    expected_profit,
    expected_value,
    verdict,
)


class BreakevenTests(unittest.TestCase):
    def test_breakeven_is_inverse_odds(self):
        self.assertAlmostEqual(breakeven_probability(2.0), 0.5)
        self.assertAlmostEqual(breakeven_probability(1.5), 2.0 / 3.0)

    def test_breakeven_rejects_invalid_odds(self):
        for bad in (1.0, 0.95, 0.0, -2.0, float("nan"), "1.5", True, None):
            with self.assertRaises(ValueError, msg=f"odds={bad}"):
                breakeven_probability(bad)


class ExpectedValueTests(unittest.TestCase):
    def test_bayern_gift_example_is_positive(self):
        # Fair 1,40 (= 71,4 %), Buchmacher zahlt 1,50 -> +7,1 %
        self.assertAlmostEqual(expected_value(1 / 1.4, 1.5), 0.0714, places=3)

    def test_bayern_too_expensive_is_negative(self):
        # Fair 1,50 (= 66,7 %), Buchmacher zahlt nur 1,40 -> -6,7 %
        self.assertAlmostEqual(expected_value(1 / 1.5, 1.4), -0.0667, places=3)

    def test_rigged_coin_bleeds_five_percent(self):
        self.assertAlmostEqual(expected_value(0.5, 1.9), -0.05)

    def test_fair_price_is_zero(self):
        self.assertAlmostEqual(expected_value(0.5, 2.0), 0.0)

    def test_expected_profit_scales_with_stake(self):
        self.assertAlmostEqual(expected_profit(0.5, 1.9, 100.0), -5.0)
        self.assertAlmostEqual(expected_profit(1 / 1.4, 1.5, 25.0), 1.7857, places=3)

    def test_rejects_invalid_inputs(self):
        for bad_p in (-0.1, 1.2, float("nan"), "0.5", True, None):
            with self.assertRaises(ValueError, msg=f"p={bad_p}"):
                expected_value(bad_p, 1.5)
        for bad_stake in (-5.0, float("nan"), "25", True, None):
            with self.assertRaises(ValueError, msg=f"stake={bad_stake}"):
                expected_profit(0.5, 2.0, bad_stake)


class VerdictTests(unittest.TestCase):
    def test_clear_edge_says_yes(self):
        # 75% minus 5pp uncertainty at 1.50 -> +5% risk-adjusted EV.
        label, reason = verdict(0.75, 1.5)
        self.assertEqual(label, VERDICT_BET)
        self.assertIn("Risiko-EV", reason)

    def test_risk_adjusted_roi_boundary_says_yes(self):
        required_adjusted_probability = (1.0 + MIN_EXPECTED_ROI_FOR_BET) / 1.5
        point_probability = (
            required_adjusted_probability + DEFAULT_PROBABILITY_UNCERTAINTY
        )
        label, _ = verdict(point_probability, 1.5)
        self.assertEqual(label, VERDICT_BET)

    def test_thin_positive_says_close(self):
        # +2 % EV, aber nur 1,3 Punkte über Break-even -> Schätzfehler frisst es
        label, reason = verdict(0.68, 1.5)
        self.assertEqual(label, VERDICT_CLOSE)
        self.assertIn("Unsicherheitsabschlag", reason)

    def test_negative_says_no(self):
        label, reason = verdict(0.60, 1.5)
        self.assertEqual(label, VERDICT_NO_BET)
        self.assertIn("-10.0", reason)

    def test_exactly_breakeven_says_no(self):
        # +-0 ist kein Grund zu wetten (Buchmacher-Marge bleibt)
        label, _ = verdict(breakeven_probability(2.0), 2.0)
        self.assertEqual(label, VERDICT_NO_BET)

    def test_edge_points_matches_breakeven_distance(self):
        self.assertAlmostEqual(edge_points(0.75, 1.5), 0.75 - 2.0 / 3.0)

    def test_conservative_probability_is_explicit_and_bounded(self):
        self.assertAlmostEqual(conservative_probability(0.70, 0.05), 0.65)
        self.assertEqual(conservative_probability(0.03, 0.05), 0.0)


if __name__ == "__main__":
    unittest.main()
