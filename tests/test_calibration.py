import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import challenge_engine  # noqa: E402
from challenge_engine import (  # noqa: E402
    CALIBRATION_MIN_SAMPLES,
    MARKET_SPECS,
    MarketCalibration,
    _fit_calibration_map,
    _pava,
    build_fixture_candidates,
    fit_market_calibration,
    fixture_market_probabilities,
    validate_league_markets,
)


def fixture(
    fixture_id,
    played_at,
    home_id,
    away_id,
    home_goals=None,
    away_goals=None,
    league_id=39,
    stats=None,
):
    return {
        "fixture": {
            "id": fixture_id,
            "date": played_at.astimezone(timezone.utc).isoformat(),
            "venue": {"city": "London"},
            "referee": "R Test",
        },
        "league": {"id": league_id, "name": "Test League", "country": "England"},
        "teams": {
            "home": {"id": home_id, "name": f"Team {home_id}"},
            "away": {"id": away_id, "name": f"Team {away_id}"},
        },
        "goals": {"home": home_goals, "away": away_goals},
        "challenge_stats": stats or {},
    }


def league_history(cycles=12):
    start = datetime(2025, 8, 1, tzinfo=timezone.utc)
    teams = list(range(1, 9))
    history = []
    fixture_id = 1
    for cycle in range(cycles):
        for index, home_id in enumerate(teams):
            away_id = teams[(index + cycle + 1) % len(teams)]
            if away_id == home_id:
                away_id = teams[(index + 2) % len(teams)]
            history.append(
                fixture(
                    fixture_id,
                    start + timedelta(days=fixture_id),
                    home_id,
                    away_id,
                    (home_id + cycle) % 4,
                    (away_id + cycle) % 3,
                    stats={
                        "corners_home": 3 + (home_id + cycle) % 5,
                        "corners_away": 2 + (away_id + cycle) % 5,
                        "yellow_cards_home": 1 + (home_id + cycle) % 3,
                        "yellow_cards_away": 1 + (away_id + cycle) % 3,
                    },
                )
            )
            fixture_id += 1
    return history


def small_history():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    history = []
    fixture_id = 1
    for index in range(10):
        history.append(fixture(fixture_id, start + timedelta(days=index * 4), 1, 3, 2, 1))
        fixture_id += 1
        history.append(fixture(fixture_id, start + timedelta(days=index * 4 + 1), 4, 2, 1, 1))
        fixture_id += 1
        history.append(fixture(fixture_id, start + timedelta(days=index * 4 + 2), 5, 6, 1, 0))
        fixture_id += 1
        history.append(fixture(fixture_id, start + timedelta(days=index * 4 + 3), 6, 5, 0, 1))
        fixture_id += 1
    return history, start


class FitCalibrationMapTest(unittest.TestCase):
    def test_returns_none_below_min_samples(self):
        probabilities = [0.6] * (CALIBRATION_MIN_SAMPLES - 1)
        outcomes = [1] * (CALIBRATION_MIN_SAMPLES - 1)
        self.assertIsNone(_fit_calibration_map(probabilities, outcomes))

    def test_returns_none_on_length_mismatch(self):
        probabilities = [0.6] * (CALIBRATION_MIN_SAMPLES + 10)
        outcomes = [1] * CALIBRATION_MIN_SAMPLES
        self.assertIsNone(_fit_calibration_map(probabilities, outcomes))

    def test_overconfident_probabilities_are_pulled_down(self):
        total = 2 * CALIBRATION_MIN_SAMPLES
        probabilities = [[0.70, 0.75, 0.80][index % 3] for index in range(total)]
        # Trefferrate 45 %, unkorreliert mit der Sortierung der Wahrscheinlichkeiten
        outcomes = [1 if (index * 37) % 100 < 45 else 0 for index in range(total)]
        curve = _fit_calibration_map(probabilities, outcomes)
        self.assertIsNotNone(curve)
        self.assertEqual(curve.samples, total)
        calibrated = curve(0.75)
        # klar unter der rohen Vorhersage (Bias-Korrektur)
        self.assertLess(calibrated, 0.70)
        # aber über der rohen Trefferrate (Schrumpfung zur Identität)
        self.assertGreater(calibrated, 0.45)

    def test_underconfident_probabilities_are_pulled_up(self):
        total = 2 * CALIBRATION_MIN_SAMPLES
        probabilities = [[0.25, 0.30, 0.35][index % 3] for index in range(total)]
        outcomes = [1 if (index * 37) % 100 < 55 else 0 for index in range(total)]
        curve = _fit_calibration_map(probabilities, outcomes)
        self.assertIsNotNone(curve)
        calibrated = curve(0.30)
        self.assertGreater(calibrated, 0.35)
        self.assertLess(calibrated, 0.55)

    def test_points_are_monotone_and_bounded(self):
        total = 4 * CALIBRATION_MIN_SAMPLES
        probabilities = [0.05 + 0.9 * (index / total) for index in range(total)]
        outcomes = [1 if (index * 7) % 13 < 6 else 0 for index in range(total)]
        curve = _fit_calibration_map(probabilities, outcomes)
        self.assertIsNotNone(curve)
        xs = [point[0] for point in curve.points]
        ys = [point[1] for point in curve.points]
        self.assertEqual(xs, sorted(xs))
        self.assertGreater(len(set(xs)), 1)
        for left, right in zip(ys, ys[1:]):
            self.assertLessEqual(left, right + 1e-9)
        for value in xs + ys:
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


class MarketCalibrationCallTest(unittest.TestCase):
    def test_empty_points_are_identity(self):
        curve = MarketCalibration(points=(), samples=0)
        self.assertAlmostEqual(curve(0.42), 0.42)

    def test_flat_extrapolation_outside_support(self):
        curve = MarketCalibration(points=((0.30, 0.40), (0.70, 0.60)), samples=200)
        self.assertAlmostEqual(curve(0.0), 0.40)
        self.assertAlmostEqual(curve(0.29), 0.40)
        self.assertAlmostEqual(curve(0.71), 0.60)
        self.assertAlmostEqual(curve(1.0), 0.60)

    def test_linear_interpolation_between_points(self):
        curve = MarketCalibration(points=((0.30, 0.40), (0.70, 0.60)), samples=200)
        self.assertAlmostEqual(curve(0.50), 0.50, places=9)

    def test_input_is_clamped(self):
        curve = MarketCalibration(points=((0.30, 0.40), (0.70, 0.60)), samples=200)
        self.assertAlmostEqual(curve(-1.0), 0.40)
        self.assertAlmostEqual(curve(2.0), 0.60)


class PavaTest(unittest.TestCase):
    def test_merges_adjacent_violations(self):
        merged = _pava([[0.5, 0.8, 1.0], [0.7, 0.3, 1.0]])
        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0][0], 1.2)
        self.assertAlmostEqual(merged[0][1], 1.1)
        self.assertAlmostEqual(merged[0][2], 2.0)

    def test_keeps_monotone_blocks_separate(self):
        merged = _pava([[0.4, 0.2, 1.0], [0.6, 0.5, 1.0], [0.8, 0.9, 1.0]])
        self.assertEqual(len(merged), 3)


class FitMarketCalibrationIntegrationTest(unittest.TestCase):
    def test_walk_forward_hides_all_same_day_results(self):
        start = datetime(2026, 4, 1, 10, tzinfo=timezone.utc)
        history = [
            fixture(1, start, 1, 2, 1, 0),
            fixture(2, start + timedelta(hours=8), 3, 4, 0, 1),
            fixture(3, start + timedelta(days=1), 1, 3, 1, 1),
        ]
        prior_sizes = []

        def fake_probabilities(_fixture, prior, calibration=None):
            prior_sizes.append(len(prior))
            return {
                "probabilities": {
                    spec.key: (0.5, 0.5, 0.5)
                    for spec in MARKET_SPECS
                }
            }

        with patch(
            "challenge_engine.fixture_market_probabilities",
            side_effect=fake_probabilities,
        ):
            fit_market_calibration(history)

        self.assertEqual(prior_sizes, [0, 0, 2])

    def test_returns_curves_when_enough_predictions_exist(self):
        history = league_history()
        with patch.object(challenge_engine, "CALIBRATION_MIN_SAMPLES", 10):
            maps = fit_market_calibration(history)
        self.assertTrue(maps)
        for curve in maps.values():
            self.assertIsInstance(curve, MarketCalibration)
            self.assertGreaterEqual(curve.samples, 10)
            xs = [point[0] for point in curve.points]
            self.assertEqual(xs, sorted(xs))


class CalibrationInPipelineTest(unittest.TestCase):
    def test_fixture_probabilities_expose_calibrated_markets(self):
        history, start = small_history()
        target = fixture(999, start + timedelta(days=45), 1, 2)
        halving = {
            spec.key: MarketCalibration(points=((0.0, 0.0), (1.0, 0.5)), samples=500)
            for spec in MARKET_SPECS
        }
        raw_model = fixture_market_probabilities(target, history)
        calibrated_model = fixture_market_probabilities(target, history, halving)
        self.assertIsNotNone(raw_model)
        self.assertIsNotNone(calibrated_model)
        self.assertIn("calibrated_markets", calibrated_model)
        for key, values in calibrated_model["probabilities"].items():
            raw_values = raw_model["probabilities"][key]
            for calibrated_value, raw_value in zip(values, raw_values):
                self.assertAlmostEqual(calibrated_value, raw_value * 0.5, places=9)

    def test_candidates_shift_with_calibration(self):
        history, start = small_history()
        target = fixture(999, start + timedelta(days=45), 1, 2)
        halving = {
            spec.key: MarketCalibration(points=((0.0, 0.0), (1.0, 0.5)), samples=500)
            for spec in MARKET_SPECS
        }

        plain = build_fixture_candidates(target, history, {})
        shifted = build_fixture_candidates(target, history, {}, halving)

        self.assertTrue(plain)
        self.assertEqual(len(plain), len(shifted))
        for raw_candidate, shifted_candidate in zip(plain, shifted):
            self.assertLess(shifted_candidate.probability, raw_candidate.probability)

    def test_validation_reports_raw_brier_score(self):
        metrics = validate_league_markets(league_history())
        self.assertTrue(metrics)
        for metric in metrics.values():
            if metric.observations > 0:
                self.assertIsNotNone(metric.raw_brier_score)
                self.assertGreaterEqual(metric.raw_brier_score, 0.0)


if __name__ == "__main__":
    unittest.main()
