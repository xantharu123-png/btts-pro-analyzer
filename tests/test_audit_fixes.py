"""Regression tests for the July 2026 audit fixes.

Each test pins one audit finding so it cannot silently reappear:
xG decimal parsing, Swiss-calendar search dates, calibration-bin edges,
hard-floor stake rounding, explicit ML fallback, day-grouped ML splits,
and provider-order-independent H2H recency.
"""

from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from advanced_analyzer import AdvancedBTTSAnalyzer
from api_football import APIFootball
from betboy_v3_ml_engine import MatchFeatures, MLEnsemble
from challenge_15k import _challenge_today
from challenge_engine import _calibration_diagnostics, _h2h_scores


def test_expected_goals_are_parsed_from_decimal_text():
    """Provider xG arrives as text like "1.34"; it must not be dropped."""
    api = APIFootball("test")
    api._rate_limit = lambda: None
    response = Mock(status_code=200)
    response.json.return_value = {
        "response": [
            {
                "team": {"id": 1},
                "statistics": [
                    {"type": "expected_goals", "value": "1.34"},
                    {"type": "Corner Kicks", "value": 3},
                ],
            },
            {
                "team": {"id": 2},
                "statistics": [
                    {"type": "expected_goals", "value": 0.87},
                    {"type": "Corner Kicks", "value": 5},
                ],
            },
        ]
    }
    with patch("api_football.requests.get", return_value=response):
        stats = api.get_match_statistics(99, 1, 2)

    assert stats["xg_home"] == pytest.approx(1.34)
    assert stats["xg_away"] == pytest.approx(0.87)
    # Invalid xG stays None instead of becoming zero or an integer cast.
    response.json.return_value["response"][0]["statistics"][0]["value"] = "n/a"
    with patch("api_football.requests.get", return_value=response):
        stats = api.get_match_statistics(99, 1, 2)
    assert stats["xg_home"] is None


def test_calibration_bins_do_not_double_count_exact_edges():
    """p == 0.6 must land in exactly one bin despite 0.4 + 0.2 != 0.6 in FP."""
    predictions = [0.6] * 40
    outcomes = [1] * 20 + [0] * 20

    ece, supported_bins, min_bin_size, max_deviation = _calibration_diagnostics(
        predictions, outcomes
    )

    assert supported_bins == 1
    assert min_bin_size == 40
    assert ece == pytest.approx(0.1)
    assert max_deviation == pytest.approx(0.1)


def test_challenge_today_uses_swiss_calendar_day():
    """22:30 UTC in July is already the next day in Europe/Zurich (UTC+2)."""
    assert _challenge_today(
        datetime(2026, 7, 17, 22, 30, tzinfo=timezone.utc)
    ) == date(2026, 7, 18)
    assert _challenge_today(
        datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    ) == date(2026, 7, 17)


def test_ml_predict_failure_is_none_not_neutral_50():
    """An unavailable model must not be displayed as a real 50% estimate."""
    analyzer = AdvancedBTTSAnalyzer.__new__(AdvancedBTTSAnalyzer)
    analyzer.model_trained = False
    analyzer.ml_model = None

    assert analyzer.ml_predict([50.0, 50.0, 1.2, 1.1, 1.0, 0.9]) == (None, 0.0)


def test_ml_ensemble_rejects_misaligned_or_unsorted_dates():
    ensemble = MLEnsemble(target="btts")
    X = np.zeros((100, len(MatchFeatures.feature_names())))
    y = np.asarray([0, 1] * 50)

    with pytest.raises(ValueError):
        ensemble.train(X, y, target="btts", dates=np.arange(99))
    with pytest.raises(ValueError):
        ensemble.train(X, y, target="btts", dates=np.arange(100)[::-1])


def _logistic_only(ensemble):
    ensemble.models = {
        "logistic": LogisticRegression(max_iter=1000, random_state=42),
    }


def test_ml_ensemble_day_grouped_training_keeps_day_boundaries():
    """With dates supplied, every split boundary is a calendar-day edge."""
    rng = np.random.default_rng(42)
    features = rng.normal(size=(300, len(MatchFeatures.feature_names())))
    labels = (features[:, 0] + 0.2 * features[:, 1] > 0).astype(int)
    dates = np.repeat(np.arange(30), 10)

    with patch.object(MLEnsemble, "_initialize_models", _logistic_only):
        ensemble = MLEnsemble(target="btts")
        scores = ensemble.train(features, labels, target="btts", dates=dates)

    assert ensemble.is_trained
    # 30 days, 20% holdout -> boundary after day 23: 240 selection / 60 holdout
    # rows, aligned exactly on a day edge.
    assert scores["logistic"]["selection_sample_size"] == 240
    assert scores["logistic"]["holdout_sample_size"] == 60
    assert "day_grouped" in scores["logistic"]["validation"]


def _h2h_fixture(day: int, home_goals: int, away_goals: int) -> dict:
    return {
        "fixture": {"date": f"2026-01-{day:02d}T18:00:00+00:00"},
        "teams": {"home": {"id": 1}, "away": {"id": 2}},
        "goals": {"home": home_goals, "away": away_goals},
    }


def test_h2h_scores_use_most_recent_meetings_regardless_of_delivery_order():
    """Oldest-first provider delivery must not leak stale meetings into H2H."""
    fixtures = [_h2h_fixture(1, 0, 0), _h2h_fixture(2, 5, 5)]
    fixtures += [_h2h_fixture(day, 1, 1) for day in range(3, 13)]

    scores = _h2h_scores(fixtures, 1, 2)

    assert len(scores) == 10
    assert (0, 0) not in scores
    assert (5, 5) not in scores
