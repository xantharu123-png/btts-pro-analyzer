"""Opt-in projection diagnostics must never alter a frozen calculation."""
from copy import deepcopy

import pytest

import challenge_engine as engine
import football_joint_calibration as joint


def test_analytic_attained_marginals_and_signed_residuals_are_read_only():
    matrix = {(0, 0): .6, (1, 0): .4}
    specs = (engine.MARKET_BY_KEY["RESULT_HOME"], engine.MARKET_BY_KEY["RESULT_DRAW"])
    targets = {"RESULT_HOME": .5, "RESULT_DRAW": .5}
    before = deepcopy((matrix, targets))
    report = joint.projection_target_diagnostics(matrix, specs, targets)
    assert report["attained"] == {"RESULT_HOME": .4, "RESULT_DRAW": .6}
    assert report["residuals"] == pytest.approx({"RESULT_HOME": -.1, "RESULT_DRAW": .1})
    assert report["max_abs_residual"] == pytest.approx(.1)
    assert report["mean_squared_residual"] == pytest.approx(.01)
    assert (matrix, targets) == before


def test_exact_targets_and_empty_diagnostic_family_have_zero_residual():
    spec = engine.MARKET_BY_KEY["RESULT_HOME"]
    report = joint.projection_target_diagnostics({(0, 0): .6, (1, 0): .4},
        (spec,), {"RESULT_HOME": .4})
    assert report == {"attained": {"RESULT_HOME": .4}, "residuals": {"RESULT_HOME": 0.},
        "max_abs_residual": 0., "mean_squared_residual": 0.}
    assert joint.projection_target_diagnostics({(0, 0): 1.}, (), {}) == {
        "attained": {}, "residuals": {}, "max_abs_residual": 0., "mean_squared_residual": 0.}


def test_legacy_projection_error_is_measured_without_refit_or_capture_change(monkeypatch):
    matrix, diagnostics = joint.calibrate_joint_distribution(
        {(0, 0): .6, (1, 0): .4}, engine.GOAL_MARKET_SPECS,
        {"RESULT_HOME": lambda p: p + .1})
    before = deepcopy((matrix, diagnostics))
    def forbidden(*args, **kwargs):
        pytest.fail("Reporting attained marginals must not refit the solver")
    monkeypatch.setattr(joint, "minimize", forbidden)
    report = joint.projection_target_diagnostics(matrix, engine.GOAL_MARKET_SPECS,
        diagnostics["targets"])
    assert matrix[1, 0] == pytest.approx(36.5 / 91, abs=1e-8)
    assert report["attained"]["RESULT_HOME"] == matrix[1, 0]
    assert report["residuals"]["RESULT_HOME"] == pytest.approx(-.0989010989010989, abs=1e-8)
    assert report["max_abs_residual"] == pytest.approx(.0989010989010989, abs=1e-8)
    assert diagnostics["law_version"] == "football-joint-settlement-projection-v1"
    assert set(diagnostics) == {"law_version", "success", "status", "iterations", "atoms",
        "cells", "targets", "message"}
    assert (matrix, diagnostics) == before


@pytest.mark.parametrize("matrix,targets", [
    ({(0, 0): .5}, {"RESULT_HOME": .4}),
    ({(0, 0): True}, {"RESULT_HOME": .4}),
    ({(0, 0): float("nan")}, {"RESULT_HOME": .4}),
    ({(0, 0): 1.}, {"RESULT_HOME": True}),
    ({(0, 0): 1.}, {"RESULT_HOME": 1.1}),
    ({(0, 0): 1.}, {"MISSING_MARKET": .4}),
])
def test_malformed_diagnostic_inputs_are_not_reported_as_valid(matrix, targets):
    with pytest.raises(ValueError):
        joint.projection_target_diagnostics(matrix, (engine.MARKET_BY_KEY["RESULT_HOME"],), targets)
