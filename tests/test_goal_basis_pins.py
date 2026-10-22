"""Pins per rate basis: prediction version, contract signature, candidates, caches.

Plan: docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md. The legacy
basis keeps every existing token; the shadow candidate basis has its own, a
basis never borrows another basis's validation, and only legacy candidates
can ever be released.
"""
from dataclasses import replace

import pytest

import challenge_engine as engine
from challenge_engine import MARKET_SPECS, ValidationMetrics
from tests.test_football_base_provenance import history, target

HYBRID = engine.GOAL_MODEL_SHADOW_CANDIDATE


def _credible_metric(version):
    return ValidationMetrics(
        300, 0.15, 0.20, 0.25, 0.04, True,
        calibration_bins=4, min_bin_size=30, max_calibration_error=0.06, max_error_bin_size=30,
        max_error_bin_mean_probability=0.70, paired_loss_mean=0.05, paired_loss_hac_standard_error=0.005,
        paired_loss_lower_confidence_bound=0.0418, paired_loss_p_value=0.00001, fdr_q_value=0.0009,
        tested_hypotheses=len(MARKET_SPECS), statistical_release_passed=True, prediction_version=version,
    )


def test_registered_pins_are_distinct_and_analysis_variants_are_never_registered():
    legacy_version = engine.prediction_version_for_goal_model(engine.GOAL_MODEL_LEGACY)
    hybrid_version = engine.prediction_version_for_goal_model(HYBRID)
    assert legacy_version == engine.CHALLENGE_PREDICTION_VERSION
    assert hybrid_version == "challenge-engine:dc-hl365-hybrid-joint-calibration-v1"
    assert engine.model_contract_signature_for_goal_model(engine.GOAL_MODEL_LEGACY) == engine.CHALLENGE_MODEL_CONTRACT_SIGNATURE
    assert engine.model_contract_signature_for_goal_model(HYBRID).startswith(engine.CHALLENGE_MODEL_CONTRACT_SIGNATURE + "+")
    assert engine.goal_model_for_prediction_version(hybrid_version) == HYBRID
    assert engine.goal_model_for_prediction_version(legacy_version) == engine.GOAL_MODEL_LEGACY
    tokens = {legacy_version, hybrid_version}
    for variant in engine.GOAL_MODELS:
        if variant in (engine.GOAL_MODEL_LEGACY, HYBRID):
            continue
        version = engine.prediction_version_for_goal_model(variant)
        assert version not in tokens and engine.goal_model_for_prediction_version(version) is None
        tokens.add(version)
    with pytest.raises(ValueError):
        engine.prediction_version_for_goal_model("poisson")
    with pytest.raises(ValueError):
        engine.model_contract_signature_for_goal_model("")


def test_validation_metrics_carry_the_version_of_their_basis():
    legacy = engine.validate_league_markets([])
    hybrid = engine.validate_league_markets([], goal_model=HYBRID)
    assert {metric.prediction_version for metric in legacy.values()} == {engine.CHALLENGE_PREDICTION_VERSION}
    assert {metric.prediction_version for metric in hybrid.values()} == {engine.prediction_version_for_goal_model(HYBRID)}
    validation, _ = engine.build_market_model_artifact([], goal_model=HYBRID)
    assert {metric.prediction_version for metric in validation.values()} == {engine.prediction_version_for_goal_model(HYBRID)}


def test_candidates_of_the_hybrid_basis_carry_its_version_and_never_release():
    rows, current = history(), target()
    legacy_validation = {spec.key: _credible_metric(engine.CHALLENGE_PREDICTION_VERSION) for spec in MARKET_SPECS}
    hybrid_validation = {key: replace(metric, prediction_version=engine.prediction_version_for_goal_model(HYBRID))
                         for key, metric in legacy_validation.items()}
    legacy = engine.build_fixture_candidates(current, rows, legacy_validation, {})
    hybrid = engine.build_fixture_candidates(current, rows, hybrid_validation, {}, goal_model=HYBRID)
    borrowed = engine.build_fixture_candidates(current, rows, legacy_validation, {}, goal_model=HYBRID)
    assert legacy and hybrid and borrowed
    assert {candidate.prediction_version for candidate in legacy} == {engine.CHALLENGE_PREDICTION_VERSION}
    assert {candidate.prediction_version for candidate in hybrid} == {engine.prediction_version_for_goal_model(HYBRID)}
    gate = "Markt hat das Walk-forward-Gate nicht bestanden"
    assert all(gate in candidate.blocked_reasons for candidate in borrowed)
    assert not any(gate in candidate.blocked_reasons for candidate in hybrid)
    assert not any(gate in candidate.blocked_reasons for candidate in legacy)
    by_key = {candidate.market_key: candidate for candidate in legacy}
    assert any(by_key[c.market_key].probability != c.probability for c in hybrid if c.market_key == "RESULT_HOME")
    for candidate in hybrid:
        candidate.validation = hybrid_validation[candidate.market_key]
        candidate.context = {"passed": True, "release_context_complete": True, "release_eligible": True}
        assert not engine.candidate_is_15k_model_eligible(candidate)
        assert not engine.candidate_is_wettfinder_release_credible(candidate)
    for candidate in legacy:
        candidate.validation = legacy_validation[candidate.market_key]
        candidate.context = {"passed": True, "release_context_complete": True, "release_eligible": True}
    assert any(engine.candidate_is_wettfinder_release_credible(c) for c in legacy if not c.blocked_reasons)
    with pytest.raises(ValueError):
        engine.build_fixture_candidates(current, rows, {}, {}, goal_model="poisson")


def test_senior_international_fixtures_fail_closed_for_a_non_legacy_basis():
    national = {**target(), "league": {"id": 5, "season": 2026}, "challenge_senior_national_team": True}
    assert engine.fixture_market_probabilities(national, history(), None, goal_model=HYBRID) is None
    assert engine.build_fixture_candidates(national, history(), {}, {}, goal_model=HYBRID) == []
