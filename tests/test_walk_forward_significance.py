import math
from datetime import datetime, timezone
from unittest.mock import patch

import challenge_engine
from challenge_engine import (
    ChallengeCandidate,
    MARKET_SPECS,
    ValidationMetrics,
    candidate_is_forecast_credible,
    candidate_is_credible,
    candidate_is_wettfinder_release_credible,
    select_wettfinder_catalog,
)


def _records():
    return {
        spec.key: {
            "probabilities": [],
            "outcomes": [],
            "baselines": [],
            "raw": [],
        }
        for spec in MARKET_SPECS
    }


def _install_record(records, probabilities):
    target = records[MARKET_SPECS[0].key]
    target["probabilities"] = probabilities
    target["outcomes"] = [0] * len(probabilities)
    target["baselines"] = [0.5] * len(probabilities)
    target["raw"] = list(probabilities)


def _candidate(metric: ValidationMetrics) -> ChallengeCandidate:
    candidate = ChallengeCandidate(
        candidate_id="100:BTTS_YES",
        fixture_id=100,
        league_id=39,
        league_name="Test League",
        kickoff=datetime(2030, 1, 1, tzinfo=timezone.utc).isoformat(),
        home_team_id=1,
        away_team_id=2,
        home_team="Home",
        away_team="Away",
        market_key="BTTS_YES",
        market="Beide Teams treffen",
        selection="Ja",
        probability=0.70,
        conservative_probability=0.65,
        probability_haircut_pp=5.0,
        model_price=1.0 / 0.65,
        evidence_score=90.0,
        model_spread_pp=2.0,
        expected_home_goals=1.5,
        expected_away_goals=1.2,
        venue_samples=(10, 10),
        form_samples=(10, 10),
        validation=metric,
    )
    candidate.context = {
        "passed": True,
        "forecast_passed": True,
        "release_context_complete": True,
        "release_eligible": True,
        "model_transfer": {"status": "passed"},
        "blocked_reasons": [],
    }
    return candidate


def _good_calibration(*_args):
    return (0.01, 4, 50, 0.02, 50, 0.5)


def test_two_percent_point_estimate_at_n_200_is_not_statistical_release_evidence():
    records = _records()
    # Baseline Brier is 0.25. The paired advantages alternate between +0.10
    # and about -0.09: just over 2% relative improvement, but with uncertainty
    # far wider than the point estimate.
    probabilities = [math.sqrt(0.15)] * 100 + [math.sqrt(0.3399)] * 100
    _install_record(records, probabilities)

    with patch.object(
        challenge_engine,
        "_calibration_diagnostics",
        side_effect=_good_calibration,
    ):
        metric = challenge_engine._validation_metrics_from_records(records)[
            MARKET_SPECS[0].key
        ]

    assert metric.observations == 200
    assert 0.02 <= metric.relative_improvement < 0.021
    assert metric.passed is True  # point-estimate diagnostics remain visible
    assert metric.paired_loss_lower_confidence_bound < 0.0
    assert metric.paired_loss_p_value > 0.05
    assert metric.fdr_q_value > 0.05
    assert metric.tested_hypotheses == len(MARKET_SPECS) == 90
    assert metric.statistical_release_passed is False


def test_strong_paired_advantage_survives_all_90_bh_hypotheses():
    records = _records()
    probabilities = [math.sqrt(0.15), math.sqrt(0.18)] * 100
    _install_record(records, probabilities)

    with patch.object(
        challenge_engine,
        "_calibration_diagnostics",
        side_effect=_good_calibration,
    ):
        metric = challenge_engine._validation_metrics_from_records(records)[
            MARKET_SPECS[0].key
        ]

    assert metric.passed is True
    assert metric.paired_loss_lower_confidence_bound > 0.0
    assert metric.paired_loss_p_value < 0.05 / len(MARKET_SPECS)
    assert metric.fdr_q_value <= 0.05
    assert metric.statistical_release_passed is True


def test_bh_counts_unobserved_markets_in_the_configured_family():
    p_values = {spec.key: 1.0 for spec in MARKET_SPECS}
    target_key = MARKET_SPECS[0].key
    p_values[target_key] = 0.001

    adjusted = challenge_engine._benjamini_hochberg_q_values(p_values)

    assert len(adjusted) == 90
    assert math.isclose(adjusted[target_key], 0.09, abs_tol=1e-12)


def test_all_echtgeld_release_paths_require_hac_fdr_but_forecast_stays_visible():
    metric = ValidationMetrics(
        observations=300,
        brier_score=0.15,
        baseline_brier_score=0.20,
        relative_improvement=0.25,
        expected_calibration_error=0.04,
        passed=True,
        calibration_bins=4,
        min_bin_size=50,
        max_calibration_error=0.06,
        max_error_bin_size=50,
        max_error_bin_mean_probability=0.6,
        raw_brier_score=0.16,
    )
    candidate = _candidate(metric)

    assert candidate_is_forecast_credible(candidate) is True
    assert candidate_is_credible(candidate) is False
    assert candidate_is_wettfinder_release_credible(candidate) is False
    # The forecast catalog stays visible; only release/ticket paths are gated.
    assert select_wettfinder_catalog([candidate]) == [candidate]
    assert select_wettfinder_catalog([candidate], require_release=True) == []


def test_shared_echtgeld_gate_accepts_complete_current_hac_fdr_proof():
    metric = ValidationMetrics(
        observations=300,
        brier_score=0.15,
        baseline_brier_score=0.20,
        relative_improvement=0.25,
        expected_calibration_error=0.04,
        passed=True,
        calibration_bins=4,
        min_bin_size=50,
        max_calibration_error=0.06,
        max_error_bin_size=50,
        max_error_bin_mean_probability=0.6,
        raw_brier_score=0.16,
        paired_loss_mean=0.05,
        paired_loss_hac_standard_error=0.005,
        paired_loss_lower_confidence_bound=0.0418,
        paired_loss_p_value=0.00001,
        fdr_q_value=0.0009,
        tested_hypotheses=len(MARKET_SPECS),
        statistical_release_passed=True,
    )
    candidate = _candidate(metric)

    assert candidate_is_forecast_credible(candidate) is True
    assert candidate_is_credible(candidate) is True
    assert candidate_is_wettfinder_release_credible(candidate) is True
    assert select_wettfinder_catalog([candidate]) == [candidate]
    assert select_wettfinder_catalog([candidate], require_release=True) == [candidate]


def test_normal_release_rechecks_evidence_fields_instead_of_trusting_flag():
    metric = ValidationMetrics(
        observations=300,
        brier_score=0.15,
        baseline_brier_score=0.20,
        relative_improvement=0.25,
        expected_calibration_error=0.04,
        passed=True,
        calibration_bins=4,
        min_bin_size=50,
        max_calibration_error=0.06,
        max_error_bin_size=50,
        max_error_bin_mean_probability=0.6,
        raw_brier_score=0.16,
        paired_loss_mean=0.05,
        paired_loss_hac_standard_error=0.01,
        paired_loss_lower_confidence_bound=-0.01,
        paired_loss_p_value=0.001,
        fdr_q_value=0.01,
        tested_hypotheses=len(MARKET_SPECS),
        statistical_release_passed=True,
    )

    assert candidate_is_wettfinder_release_credible(_candidate(metric)) is False
