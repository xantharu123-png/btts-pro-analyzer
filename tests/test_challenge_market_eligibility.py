from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from challenge_engine import (
    ValidationMetrics,
    build_fixture_candidates,
    market_is_basic_forecast,
    select_wettfinder_catalog,
)


def _credible_metric() -> ValidationMetrics:
    return ValidationMetrics(
        observations=300,
        brier_score=0.15,
        baseline_brier_score=0.20,
        relative_improvement=0.25,
        expected_calibration_error=0.04,
        passed=True,
        calibration_bins=4,
        min_bin_size=30,
        max_calibration_error=0.05,
        max_error_bin_size=30,
        max_error_bin_mean_probability=0.70,
        paired_loss_mean=0.05,
        paired_loss_hac_standard_error=0.005,
        paired_loss_lower_confidence_bound=0.0418,
        paired_loss_p_value=0.00001,
        fdr_q_value=0.0009,
        tested_hypotheses=90,
        statistical_release_passed=True,
    )


def test_high_probability_market_isolated_from_15k_challenge_corridor():
    kickoff = datetime.now(timezone.utc) + timedelta(days=1)
    fixture = {
        "fixture": {"id": 7001, "date": kickoff.isoformat()},
        "league": {"id": 39, "name": "Test League"},
        "teams": {
            "home": {"id": 10, "name": "Home"},
            "away": {"id": 11, "name": "Away"},
        },
    }
    model = {
        "freshness_days": 1.0,
        "active_lambdas": (1.4, 0.6),
        "venue_samples": (12, 12),
        "form_samples": (6, 6),
        "probabilities": {
            "AWAY_UNDER_2_5": (0.94, 0.93, 0.92),
        },
        "count_models": {},
        "xg_coverage": 0.0,
    }

    with patch(
        "challenge_engine.fixture_market_probabilities",
        return_value=model,
    ):
        rows = build_fixture_candidates(
            fixture,
            [],
            {"AWAY_UNDER_2_5": _credible_metric()},
        )

    assert len(rows) == 1
    assert rows[0].blocked_reasons == [
        "Modellwahrscheinlichkeit außerhalb des Challenge-Korridors"
    ]

    with patch(
        "challenge_engine.fixture_market_probabilities",
        return_value=model,
    ):
        normal_rows = build_fixture_candidates(
            fixture,
            [],
            {"AWAY_UNDER_2_5": _credible_metric()},
            allow_above_challenge_probability=True,
        )

    candidate = normal_rows[0]
    assert market_is_basic_forecast(candidate.market_key) is True
    assert candidate.probability > 0.92
    assert candidate.blocked_reasons == []
    assert any("konkrete Quote" in reason for reason in candidate.reasons)

    candidate.context = {
        "passed": True,
        "forecast_passed": True,
        "release_context_complete": True,
        "release_eligible": True,
        "blocked_reasons": [],
    }
    same_fixture_core_market = replace(
        candidate,
        candidate_id="7001:BTTS_YES",
        market_key="BTTS_YES",
        market="Beide Teams treffen",
        selection="Ja",
    )
    catalog = select_wettfinder_catalog(
        [candidate, same_fixture_core_market],
        require_release=True,
    )

    assert {row.candidate_id for row in catalog} == {
        "7001:AWAY_UNDER_2_5",
        "7001:BTTS_YES",
    }

    other_fixture = replace(
        same_fixture_core_market,
        candidate_id="7002:BTTS_YES",
        fixture_id=7002,
        home_team_id=20,
        away_team_id=21,
        home_team="Other Home",
        away_team="Other Away",
    )
    diverse = select_wettfinder_catalog(
        [candidate, same_fixture_core_market, other_fixture],
        max_candidates=2,
        max_per_fixture=1,
        require_release=True,
    )
    assert {row.fixture_id for row in diverse} == {7001, 7002}
