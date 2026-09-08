"""Bounded synthetic public-API review probes; no source or empirical claims."""

from copy import deepcopy
from decimal import Decimal, localcontext
import json
import math
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
from scipy.optimize import brentq
import context_models.offset as numerical
from context_models.offset import ContextModelError, fit_offset, offset_delta, adjust_parameters
from context_models.contracts import ContextContractError, validate_effect_artifact, validate_offset_fit

BASE = "0c50c5ab2a30c1ffd1f35a62be9c4dda863306b3"
HEAD = "a71d0955a74884a152c90fddd9bfae2e20602b34"
FILES = ["context_models/offset.py", "context_models/contracts.py",
         "tests/test_context_offset.py", "tests/test_context_contracts.py"]


def mean_loss(beta, z, offsets, targets, link, alpha, trials):
    losses = []
    for index, row in enumerate(z):
        eta = offsets[index] + math.fsum(float(a) * float(b) for a, b in zip(row, beta))
        if link == "identity":
            loss = (eta - targets[index]) ** 2 / 2
        elif link == "log_rate":
            loss = math.exp(eta) - targets[index] * eta
        else:
            softplus = max(eta, 0) + math.log1p(math.exp(-abs(eta)))
            loss = trials[index] * softplus - targets[index] * eta
        losses.append(float(loss))
    return math.fsum(losses) / len(losses) + alpha * math.fsum(float(b) ** 2 for b in beta) / 2


def run():
    subprocess.run(["git", "diff", "--quiet", HEAD, "--", *FILES], cwd=ROOT, check=True)
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == HEAD
    counts = {"public_gradient_cases": 0, "identity_closed_form_cases": 0,
              "scalar_score_roots": 0, "invalid_public_cases": 0, "B1_compatibility_cases": 0}
    x = np.array([[1.2, -.3, 0.], [2., 1.1, 0.], [-.4, .8, 0.], [.7, -1.2, 0.],
                  [1.5, .1, 0.], [-.8, -.5, 0.], [.3, 1.7, 0.]])
    offsets = np.array([.2, -.3, .5, .1, -.2, .4, .3])
    trial_counts = np.array([4., 3., 5., 2., 6., 4., 3.])
    target_counts = np.array([1., 0., 3., 1., 4., 2., 1.])
    original_minimize = numerical.optimize.minimize
    for link in ("identity", "log_rate", "logit"):
        targets = np.array([-1.5, 2., .3, -.2, 1.1, -.4, .6]) if link == "identity" else target_counts
        trials = trial_counts if link == "logit" else None
        scale = np.array([max(math.sqrt(math.fsum((float(v) - float(np.mean(col))) ** 2 for v in col) / len(col)), 1e-8) for col in x.T])
        z = x / scale
        for alpha in (0., .27):
            saved = [item.copy() for item in (x, offsets, targets)]
            def inspect(objective, initial, **kwargs):
                assert kwargs == {"jac": True, "method": "L-BFGS-B"}
                np.testing.assert_array_equal(initial, np.zeros(3))
                probe = np.array([.17, -.23, .11])
                actual_loss, actual_gradient = objective(probe)
                expected_loss = mean_loss(probe, z, offsets, targets, link, alpha, trials)
                np.testing.assert_allclose(actual_loss, expected_loss, rtol=2e-14, atol=1e-14)
                reference_gradient = []
                for feature in range(3):
                    step = np.zeros(3)
                    step[feature] = 1e-5
                    reference_gradient.append((mean_loss(probe + step, z, offsets, targets, link, alpha, trials)
                        - mean_loss(probe - step, z, offsets, targets, link, alpha, trials)) / 2e-5)
                np.testing.assert_allclose(actual_gradient, reference_gradient, rtol=2e-7, atol=2e-9)
                return original_minimize(objective, initial, **kwargs)
            with patch.object(numerical.optimize, "minimize", inspect):
                model = fit_offset(x, offsets, targets, link=link, alpha=alpha, trials=trials)
            counts["public_gradient_cases"] += 1
            np.testing.assert_allclose(model["scale"], scale, rtol=2e-15)
            assert model["coef"][2] == 0.
            assert offset_delta(model, np.zeros((1, 3)))[0] == 0.
            for before, after in zip(saved, (x, offsets, targets)):
                np.testing.assert_array_equal(before, after)
            if link == "identity":
                gram = z.T @ z / len(z) + alpha * np.eye(3)
                rhs = z.T @ (targets - offsets) / len(z)
                expected = np.linalg.lstsq(gram, rhs, rcond=None)[0]
                np.testing.assert_allclose(model["coef"], expected, rtol=2e-5, atol=2e-5)
                counts["identity_closed_form_cases"] += 1
            assert json.loads(json.dumps(model, allow_nan=False)) == model

    scalar_x = np.array([[-1.], [0.], [1.]] * 20)
    z1 = scalar_x[:, 0] / np.std(scalar_x[:, 0], ddof=0)
    for link in ("log_rate", "logit"):
        for alpha in (0., .1):
            off = np.full(60, math.log(2.) if link == "log_rate" else .2)
            y = np.array([1., 2., 4.] * 20) if link == "log_rate" else np.array([2., 5., 8.] * 20)
            trials = None if link == "log_rate" else np.full(60, 10.)
            def score(coefficient):
                residual = []
                for zi, oi, yi in zip(z1, off, y):
                    eta = oi + zi * coefficient
                    mu = math.exp(eta) if link == "log_rate" else 10. / (1. + math.exp(-eta))
                    residual.append(zi * (mu - yi))
                return math.fsum(residual) / len(residual) + alpha * coefficient
            expected = brentq(score, -5., 5., xtol=1e-13)
            model = fit_offset(scalar_x, off, y, link=link, alpha=alpha, trials=trials)
            np.testing.assert_allclose(model["coef"][0], expected, rtol=2e-5, atol=2e-5)
            assert abs(model["coef"][0]) > .1
            counts["scalar_score_roots"] += 1

    with localcontext() as ctx:
        ctx.prec = 80
        for base, change in ((1e-300, 800.), (1e300, -800.), (1e-100, 230.), (1e100, -230.)):
            expected = float(Decimal.from_float(base) * Decimal.from_float(change).exp())
            actual = adjust_parameters(np.array([base]), np.array([change]), link="log_rate")[0]
            np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=0.)
    probability = np.array([.01, .2, .5, .8, .99])
    delta = np.array([-1., .3, 0., -.3, 1.])
    np.testing.assert_allclose(adjust_parameters(probability, delta, link="logit")
        + adjust_parameters(1 - probability, -delta, link="logit"), np.ones(5), rtol=0, atol=2e-15)
    for link, values in (("identity", [-0., -1., 1e308]), ("log_rate", [1e-300, 1., 1e300]), ("logit", [.1, .5, .9])):
        original = np.array(values)
        assert adjust_parameters(original, np.zeros(3), link=link).tobytes() == original.tobytes()

    basic = {"x": np.array([[-1.], [1.]]), "offset": np.zeros(2), "target": np.ones(2), "link": "identity", "alpha": .1}
    invalid = [np.array([2**64 - 1, 1], dtype=np.uint64), np.array([1., np.nan]),
               np.array([True, False]), np.array([None, 1.], dtype=object), np.ma.array([1., 2.]),
               np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[D]")]
    for bad in invalid:
        for field in ("x", "offset", "target"):
            args = {**basic, field: bad.reshape(2, 1) if field == "x" else bad}
            try:
                fit_offset(**args)
            except ContextModelError:
                counts["invalid_public_cases"] += 1
            else:
                raise AssertionError((field, str(bad.dtype)))
    for changes in ({"link": "log_rate", "target": np.array([1., .5])},
                    {"link": "logit", "trials": np.array([2., 1.5])},
                    {"link": "logit", "target": np.array([2., 1.])},
                    {"alpha": 10**400}, {"alpha": np.bool_(False)}, {"offset": np.array(1.)}):
        try:
            fit_offset(**{**basic, **changes})
        except ContextModelError:
            counts["invalid_public_cases"] += 1
        else:
            raise AssertionError(changes)
    assert type(fit_offset(**{**basic, "alpha": np.float64(.1)})["alpha"]) is float
    for key in ("scale", "coef"):
        model = {"link": "identity", "scale": [1], "coef": [1], "alpha": 0, "n_rows": 2, key: [10**20]}
        validate_offset_fit(model)
        expected = 1e-20 if key == "scale" else 1e20
        np.testing.assert_allclose(offset_delta(model, np.ones((1, 1)))[0], expected, rtol=1e-14, atol=0)

    previous = {"__name__": "review_previous_context_contracts"}
    exec(compile(subprocess.check_output(["git", "show", BASE + ":context_models/contracts.py"], cwd=ROOT),
                 "frozen_previous_context_contracts.py", "exec"), previous)
    head = {"link": "logit", "scale": [2., 3.], "coef": [.2, -.1], "alpha": .1, "n_rows": 20}
    artifact = {"schema": 1, "sport": "tennis", "family": "tennis:serve", "feature_version": "v1",
        "feature_names": ["zeta", "alpha"], "heads": {"hold_a": head, "hold_b": deepcopy(head)},
        "preprocessing_artifacts": {}, "joint_calibration": {"kind": "identity"},
        "training_end": "2026-01-01T00:00:00Z", "training_refs_hash": "b" * 64,
        "population": {"sport": "tennis", "competitions": ["atp"], "formats": ["best-of-3"],
            "tours": ["ATP"], "surfaces": ["Hard"], "indoor": [False]},
        "coverage": {"version": "v1", "case": "complete"}, "model_variant": "offset-v1"}
    for mutation in ({}, {"scale": []}, {"coef": [1.]}, {"coef": [True, 1.]}, {"link": "identity"},
                     {"alpha": -1}, {"n_rows": True}, {"n_rows": 2.}, {"scale": [1e-9, 2.]}, {"extra": 1}):
        candidate = deepcopy(artifact)
        candidate["heads"]["hold_a"].update(mutation)
        results = []
        for validator in (previous["validate_effect_artifact"], validate_effect_artifact):
            try:
                results.append((True, validator(candidate)))
            except ValueError:
                results.append((False, None))
        assert results[0] == results[1]
        counts["B1_compatibility_cases"] += 1
    assert validate_effect_artifact(artifact)["feature_names"] == ["zeta", "alpha"]
    counts["decimal_rate_references"] = 4
    counts["zero_delta_byte_preservation_links"] = 3
    counts["logit_complement_cases"] = 5
    counts["large_JSON_integer_regressions"] = 2
    print(json.dumps({"reviewed_head": HEAD, **counts, "scope": "synthetic numerical mechanics only"}, sort_keys=True))


if __name__ == "__main__":
    run()
