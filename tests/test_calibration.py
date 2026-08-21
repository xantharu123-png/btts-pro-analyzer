import hashlib
import json
import math
import sys
import unittest
from dataclasses import asdict
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


def canonical_digest(value):
    def normalize(item):
        if isinstance(item, float) and not math.isfinite(item):
            if item > 0:
                return "Infinity"
            if item < 0:
                return "-Infinity"
            return "NaN"
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(child) for child in item]
        return item

    encoded = json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


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


class BuildMarketModelArtifactTest(unittest.TestCase):
    def test_combined_artifact_uses_one_same_day_safe_walk_forward_pass(self):
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
            validation, calibration = challenge_engine.build_market_model_artifact(history)

        self.assertEqual(prior_sizes, [0, 0, 2])
        self.assertEqual(set(validation), {spec.key for spec in MARKET_SPECS})
        self.assertEqual(calibration, {})
        for spec in MARKET_SPECS:
            expected_observations = (
                0 if spec.kind in challenge_engine.COUNT_MARKET_KINDS else len(history)
            )
            self.assertEqual(
                validation[spec.key].observations,
                expected_observations,
            )

    def test_combined_artifact_is_bit_exact_to_previous_two_pass_results(self):
        start = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
        history = []
        for index in range(18):
            fixture_id = index + 1
            home_id = index % 8 + 1
            away_id = (index * 3 + 2) % 8 + 1
            if away_id == home_id:
                away_id = away_id % 8 + 1
            history.append(
                fixture(
                    fixture_id,
                    start + timedelta(days=index // 3, hours=(index % 3) * 4),
                    home_id,
                    away_id,
                    (fixture_id * 3 + home_id) % 5,
                    (fixture_id * 2 + away_id) % 4,
                    stats={
                        "corners_home": 2 + (fixture_id + home_id) % 8,
                        "corners_away": 1 + (fixture_id * 2 + away_id) % 8,
                        "yellow_cards_home": (fixture_id + home_id) % 5,
                        "yellow_cards_away": (fixture_id * 3 + away_id) % 5,
                    },
                )
            )
        spec_indices = {spec.key: index for index, spec in enumerate(MARKET_SPECS)}

        def fake_probabilities(current_fixture, prior, calibration=None):
            fixture_id = current_fixture["fixture"]["id"]
            probabilities = {}
            for spec in MARKET_SPECS:
                value = 0.06 + (
                    (fixture_id * 17 + spec_indices[spec.key] * 11) % 88
                ) / 100
                probabilities[spec.key] = (
                    value,
                    min(0.99, value + 0.01),
                    max(0.01, value - 0.01),
                )
            return {"probabilities": probabilities}

        with (
            patch.object(challenge_engine, "CALIBRATION_MIN_SAMPLES", 5),
            patch.object(challenge_engine, "CALIBRATION_REFIT_NEW_SAMPLES", 4),
        ):
            with patch(
                "challenge_engine.fixture_market_probabilities",
                side_effect=fake_probabilities,
            ) as reference_probability_mock:
                reference_validation = validate_league_markets(history)
                reference_calibration = fit_market_calibration(history)
            with patch(
                "challenge_engine.fixture_market_probabilities",
                side_effect=fake_probabilities,
            ) as probability_mock:
                validation, calibration = challenge_engine.build_market_model_artifact(history)

        payload = {
            "validation": {
                spec.key: asdict(validation[spec.key])
                for spec in MARKET_SPECS
            },
            "calibration": {
                spec.key: {
                    "points": [list(point) for point in calibration[spec.key].points],
                    "samples": calibration[spec.key].samples,
                }
                for spec in MARKET_SPECS
                if spec.key in calibration
            },
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()

        self.assertEqual(reference_probability_mock.call_count, 2 * len(history))
        self.assertEqual(probability_mock.call_count, len(history))
        self.assertEqual(validation, reference_validation)
        self.assertEqual(calibration, reference_calibration)
        self.assertEqual(
            hashlib.sha256(encoded).hexdigest(),
            "767a3c7b378d5f87b20ec4b5a665a8c6c2ccfc46b4d624682c9a6a6c14493afb",
        )

    def test_real_90_market_outputs_match_de20e74_production_golden(self):
        history = league_history(cycles=20)
        validation, calibration = challenge_engine.build_market_model_artifact(history)
        artifact = {
            "validation": {
                spec.key: asdict(validation[spec.key])
                for spec in MARKET_SPECS
            },
            "calibration": {
                spec.key: {
                    "points": [list(point) for point in calibration[spec.key].points],
                    "samples": calibration[spec.key].samples,
                }
                for spec in MARKET_SPECS
                if spec.key in calibration
            },
        }
        latest = max(
            datetime.fromisoformat(item["fixture"]["date"])
            for item in history
        )
        target = fixture(99_999, latest + timedelta(days=2), 1, 2)
        candidates = [
            asdict(item)
            for item in build_fixture_candidates(
                target,
                history,
                validation,
                calibration,
            )
        ]

        # Recorded by executing the unmodified de20e74 two-pass engine against
        # this same history at the production calibration thresholds (100/60).
        self.assertEqual(len(calibration), 59)
        self.assertEqual(len(candidates), 90)
        self.assertEqual(
            canonical_digest(artifact),
            "bb71006f0d32ef835878cf79b647ac7aaa7c759bae206e5426ae4336a544771e",
        )
        self.assertEqual(
            canonical_digest(candidates),
            "0446b526b2506e69ef942748de2e96437a541eee5704f3b985665c136e6b7a3c",
        )


class BatchedMarketProbabilityTest(unittest.TestCase):
    def test_matches_reference_values_exactly_for_all_90_markets(self):
        cases = (
            (
                challenge_engine.score_matrix(1.55, 1.15),
                challenge_engine.GOAL_MARKET_SPECS,
            ),
            (
                challenge_engine._count_matrix(5.2, 4.4, 0.25, 0.30, 25),
                challenge_engine.CORNER_MARKET_SPECS,
            ),
            (
                challenge_engine._count_matrix(2.1, 1.8, 0.35, 0.40, 12),
                challenge_engine.YELLOW_MARKET_SPECS,
            ),
        )

        checked = 0
        for matrix, specs in cases:
            expected = {
                spec.key: challenge_engine.market_probability(matrix, spec)
                for spec in specs
            }
            actual = challenge_engine._market_probabilities(matrix, specs)
            self.assertEqual(actual, expected)
            checked += len(actual)

        self.assertEqual(checked, 90)

    def test_reuses_settlement_masks_for_matrices_with_the_same_grid(self):
        first_matrix = challenge_engine._count_matrix(2.1, 1.8, 0.35, 0.40, 12)
        second_matrix = challenge_engine._count_matrix(2.8, 2.2, 0.30, 0.45, 12)
        specs = challenge_engine.YELLOW_MARKET_SPECS
        challenge_engine._market_score_masks.cache_clear()
        original = challenge_engine.market_outcome

        with patch.object(challenge_engine, "market_outcome", wraps=original) as outcome_mock:
            challenge_engine._market_probabilities(first_matrix, specs)
            first_call_count = outcome_mock.call_count
            challenge_engine._market_probabilities(second_matrix, specs)

        self.assertEqual(first_call_count, len(first_matrix) * len(specs))
        self.assertEqual(outcome_mock.call_count, first_call_count)


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
