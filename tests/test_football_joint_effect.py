"""Numerical regression, not evidence that a real context factor is useful."""
import numpy as np
import pytest

import challenge_engine as engine
from context_models.contracts import ContextContractError, ContextIntegrityError
from context_models.football_joint_effect import (
    compare_joint_effect, fit_joint_offset, joint_offset_delta, replay_joint_calculation, tilt_joint,
)
from context_models.offset import ContextModelError
from football_original import FootballOriginal
from model_artifacts import canonical_bytes
from tests.test_football_original_capture import calibration, values
from tests.test_football_original_storage import capture


@pytest.mark.parametrize("mode", ["identity", "fitted", "conservative"])
def test_replay_recalculates_actual_calibrated_law(monkeypatch, mode):
    current, rows = values()
    curves = None if mode == "identity" else calibration()
    if mode == "conservative":
        curves = {key: engine.ConservativeMarketCalibration((curve,)) for key, curve in curves.items()}
    original = capture(monkeypatch, current=current, rows=rows, curves=curves)
    assert replay_joint_calculation(original)["probabilities"] == original.to_dict()["probabilities"]


def test_altered_calibration_recipe_cannot_pass_replay(monkeypatch):
    original = capture(monkeypatch, curves=calibration())
    packet = original.to_dict()
    packet["calibration_recipes"]["RESULT_HOME"]["points"][1][1] -= .1
    with pytest.raises(ContextIntegrityError, match="recalculation"):
        replay_joint_calculation(FootballOriginal(canonical_bytes(packet)))


def test_zero_effect_retains_every_original_calibrated_market_exactly(monkeypatch):
    original = capture(monkeypatch, curves=calibration())
    result = compare_joint_effect(original, home_delta=0., away_delta=0.)
    assert result["probabilities"] == original.to_dict()["probabilities"]
    assert result["scope"] == "numerical-comparison-not-empirical-approval"
    assert result["effective_means"]["goals"]["active"] == original.to_dict()["goal_model"]["active_lambdas"]


def test_one_joint_change_recalculates_all_goal_markets_not_corners_or_cards(monkeypatch):
    current, rows = values()
    original = capture(monkeypatch, current=current, rows=rows, curves=calibration())
    baseline = original.to_dict()
    result = compare_joint_effect(original, home_delta=-.2, away_delta=.1)
    assert result["probabilities"]["RESULT_HOME"][0] < baseline["probabilities"]["RESULT_HOME"][0]
    for index in range(3):
        assert sum(result["probabilities"][key][index] for key in ("RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY")) == pytest.approx(1)
    for spec in engine.MARKET_SPECS:
        if spec.kind in {"corner_total", "team_corners", "yellow_total", "team_yellow"}:
            assert result["probabilities"][spec.key] == baseline["probabilities"][spec.key]
    assert original.to_dict() == baseline


def test_joint_tilt_keeps_dependence_and_exact_zero_mass():
    matrix = {(0, 0): .4, (0, 1): 0., (1, 0): .1, (1, 1): .5}
    assert tilt_joint(matrix, 0., 0.) == matrix
    adjusted = tilt_joint(matrix, -.3, .2)
    assert sum(adjusted.values()) == pytest.approx(1)
    assert adjusted[(0, 1)] == 0.
    assert adjusted[(1, 1)] / adjusted[(1, 0)] == pytest.approx(5 * np.exp(.2))


@pytest.mark.parametrize("delta", [True, float("nan"), float("inf"), 1e308])
def test_invalid_or_unrepresentable_effect_never_clips_or_replaces_law(delta):
    with pytest.raises(ContextContractError):
        tilt_joint({(0, 0): .5, (1, 1): .5}, delta, 0.)


def test_joint_fit_uses_coupled_likelihood_and_training_only_scaling():
    # Synthetic associated scores, not independent Poisson head targets.
    matrices = tuple({(0, 0): .45, (0, 1): .05, (1, 0): .05, (1, 1): .45} for _ in range(8))
    x = np.array([[-1.], [-1.], [-1.], [-1.], [1.], [1.], [1.], [1.]])
    outcomes = np.array([[0, 0]] * 4 + [[1, 1]] * 4)
    fitted = fit_joint_offset(matrices, x, outcomes, alpha=1.)
    assert fitted["version"] == "football-joint-log-tilt-v1"
    assert fitted["scale"] == [1.]
    assert fitted["coef"][0][0] > 0 and fitted["coef"][0][1] > 0
    assert fitted["n_rows"] == 8
    assert set(fitted) == {"version", "scale", "coef", "alpha", "n_rows"}
    assert np.array_equal(joint_offset_delta(fitted, np.zeros((1, 1))), np.zeros((1, 2)))
    assert np.all(joint_offset_delta(fitted, np.ones((1, 1))) > 0)
    from context_models.contracts import validate_effect_artifact
    with pytest.raises(ContextContractError):
        validate_effect_artifact(fitted)  # cannot reuse old empirical/activation law


def test_joint_fit_rejects_observation_outside_declared_support():
    with pytest.raises(ContextModelError, match="support"):
        fit_joint_offset(({(0, 0): .5, (1, 1): .5},) * 2,
            np.array([[0.], [1.]]), np.array([[0, 0], [0, 1]]), alpha=1.)


def test_joint_fit_does_not_emit_artifact_after_optimizer_failure(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("context_models.football_joint_effect.optimize.minimize",
        lambda *args, **kwargs: SimpleNamespace(success=False))
    with pytest.raises(ContextModelError, match="converge"):
        fit_joint_offset(({(0, 0): .5, (1, 1): .5},) * 2,
            np.array([[0.], [1.]]), np.array([[0, 0], [1, 1]]), alpha=1.)


def test_optimizer_receives_correct_coupled_gradient(monkeypatch):
    from scipy.optimize import minimize
    inspected = []
    def checked(objective, initial, **kwargs):
        probe = np.array([.13, -.27, .04, .19])
        _, analytic = objective(probe)
        step = 1e-6
        numeric = []
        for index in range(len(probe)):
            movement = np.zeros(len(probe))
            movement[index] = step
            numeric.append((objective(probe + movement)[0] - objective(probe - movement)[0]) / (2 * step))
        np.testing.assert_allclose(analytic, numeric, atol=1e-8, rtol=1e-8)
        inspected.append(True)
        return minimize(objective, initial, **kwargs)
    monkeypatch.setattr("context_models.football_joint_effect.optimize.minimize", checked)
    fit_joint_offset(({(0, 0): .6, (1, 0): .2, (1, 1): .2},) * 4,
        np.array([[-1., 2.], [1., 3.], [2., 4.], [0., 1.]]),
        np.array([[0, 0], [1, 0], [1, 1], [0, 0]]), alpha=.1)
    assert inspected == [True]


@pytest.mark.parametrize("field,value", [("version", "independent-poisson"), ("n_rows", True),
    ("scale", [0.]), ("scale", [True]), ("coef", [[float("nan"), 0.]]), ("coef", [[.1]])])
def test_malformed_fitted_models_cannot_be_applied(field, value):
    fit = dict(version="football-joint-log-tilt-v1", scale=[1.], coef=[[.1, -.1]], alpha=1., n_rows=3)
    fit[field] = value
    with pytest.raises(ContextContractError):
        joint_offset_delta(fit, np.ones((1, 1)))
