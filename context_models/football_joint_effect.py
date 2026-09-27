"""Residual mechanics on the ACTUAL calibrated football joint distribution.

This closes the numerical mismatch with the old independent-Poisson adapter.
It does not certify source availability, fit historical cases or enable a live
effect. A joint-log-tilt fit is deliberately not an old log-rate artifact.
Chronological fitting/qualification must use this same joint likelihood, not
reuse coefficients or losses fitted against the discarded raw Poisson law.
"""
from copy import deepcopy
import math

import numpy as np
from scipy import optimize, special

import challenge_engine as engine
from context_models.contracts import ContextContractError, ContextIntegrityError, require_number, require_object
from context_models.football_joint_comparison import compare_captured_joint
from context_models.offset import ContextModelError, _array
from model_artifacts import canonical_bytes

VERSION = "football-joint-log-tilt-v1"


def _curve(recipe, depth=0):
    if type(recipe) is not dict or depth > 8:
        raise ContextContractError("unsupported captured calibration recipe")
    kind = recipe.get("kind")
    if kind == "identity":
        require_object(recipe, {"kind"}, label="identity calibration")
        return engine.MarketCalibration((), 0)
    if kind == "legacy-minimum-source-calibration-v1":
        require_object(recipe, {"kind", "source_curves"}, label="source calibration")
        if type(recipe["source_curves"]) is not list:
            raise ContextContractError("source calibration requires an actual list")
        return engine.ConservativeMarketCalibration(tuple(_curve(item, depth + 1) for item in recipe["source_curves"]))
    require_object(recipe, {"kind", "points", "samples"}, label="market calibration")
    if kind != "legacy-market-calibration-v1" or type(recipe["samples"]) is not int or recipe["samples"] < 0:
        raise ContextContractError("unsupported market calibration")
    if type(recipe["points"]) is not list:
        raise ContextContractError("calibration points require an actual list")
    points = []
    for point in recipe["points"]:
        if type(point) is not list or len(point) != 2:
            raise ContextContractError("invalid calibration point")
        for number in point:
            require_number(number, "calibration coordinate", minimum=0, maximum=1)
        if points and (point[0] <= points[-1][0] or point[1] < points[-1][1]):
            raise ContextContractError("calibration points must be monotone")
        points.append(tuple(point))
    return engine.MarketCalibration(tuple(points), recipe["samples"])


def replay_joint_calculation(original):
    """Recalculate captured inputs/curves; this is NOT a native-source replay.

    Full exact equality is intentional: no different solver result is silently
    substituted for a saved original. Native receipt and pre-match publication
    binding are separate obligations before this can become a training case.
    """
    comparison = compare_captured_joint(original)
    packet = original.to_dict()
    if set(packet["calibration_recipes"]) != set(packet["probabilities"]):
        raise ContextIntegrityError("captured calibration catalog differs")
    curves = {key: _curve(recipe) for key, recipe in packet["calibration_recipes"].items()}
    captures = []
    engine.fixture_market_probabilities(packet["fixture"], packet["league_history"], curves,
        team_history=packet["team_history"], original_capture=captures.append)
    if len(captures) != 1:
        raise ContextIntegrityError("captured football calculation cannot be reproduced")
    recalculated = captures[0].to_dict()
    fields = ("goal_model", "count_models", "raw_probabilities", "probabilities", "distribution_capture")
    if any(canonical_bytes(recalculated[key]) != canonical_bytes(packet[key]) for key in fields):
        raise ContextIntegrityError("captured joint differs from actual model recalculation")
    return comparison


def _matrix(matrix):
    if type(matrix) is not dict or not matrix or len(matrix) > 26 * 26:
        raise ContextModelError("joint must be a bounded goal distribution")
    for score, mass in matrix.items():
        if type(score) is not tuple or len(score) != 2 or any(type(n) is not int or not 0 <= n <= 25 for n in score):
            raise ContextModelError("invalid joint score support")
        require_number(mass, "joint mass", minimum=0, maximum=1)
    if not math.isclose(math.fsum(matrix.values()), 1., rel_tol=0., abs_tol=1e-10):
        raise ContextModelError("joint mass must be normalized")
    return matrix


def tilt_joint(matrix, home_delta, away_delta):
    """q(h,a) proportional to original(h,a)*exp(dh*h+da*a).

    Zero is EXACT identity, including calibration and dependence. No independent
    Poisson replacement, new scalar calibration, probability floor or clipping.
    Existing tail buckets remain the owning score_matrix categories (25+).
    """
    matrix = _matrix(matrix)
    delta = np.array([require_number(home_delta, "home effect"), require_number(away_delta, "away effect")])
    if np.all(delta == 0):
        return dict(matrix)
    positive = [key for key, mass in matrix.items() if mass > 0]
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            logmass = np.log([matrix[key] for key in positive]) + np.asarray(positive) @ delta
            weights = np.exp(logmass - special.logsumexp(logmass))
        if not np.all(np.isfinite(weights)) or np.any(weights <= 0):
            raise ContextModelError("joint effect loses positive support")
        changed = dict(zip(positive, weights.tolist()))
        result = {key: changed.get(key, 0.) for key in matrix}
        return dict(_matrix(result))
    except (ValueError, ArithmeticError) as exc:
        raise ContextModelError("joint effect is numerically unrepresentable") from exc


def compare_joint_effect(original, *, home_delta, away_delta):
    """One coherent numerical contrast for every original goal-market variant.

    Not accepted by the activation registry. Callers cannot turn illustrative
    deltas into a qualified live artifact by hashing this return value.
    """
    comparison = replay_joint_calculation(original)
    packet = original.to_dict()
    result = deepcopy(comparison)
    result.update(version=VERSION, scope="numerical-comparison-not-empirical-approval")
    for index, variant in enumerate(("active", "season", "form")):
        cells = packet["distribution_capture"]["families"]["goals"][variant]["effective_cells"]
        adjusted = tilt_joint({(h, a): p for h, a, p in cells}, home_delta, away_delta)
        for spec in engine.GOAL_MARKET_SPECS:
            result["probabilities"][spec.key][index] = engine.market_probability(adjusted, spec)
        result["effective_means"]["goals"][variant] = [
            sum(score[side] * mass for score, mass in adjusted.items()) for side in (0, 1)]
    result["delta_pp"] = {key: [100 * (new - old) for new, old in zip(values, packet["probabilities"][key])]
                          for key, values in result["probabilities"].items()}
    return result


def joint_offset_delta(fit, x):
    """Apply a fitted joint law using only its stored training scale."""
    require_object(fit, {"version", "scale", "coef", "alpha", "n_rows"}, label="joint fit")
    if fit["version"] != VERSION or type(fit["n_rows"]) is not int or fit["n_rows"] < 2:
        raise ContextModelError("unreviewed joint fit version or row count")
    require_number(fit["alpha"], "regularization", minimum=0)
    if type(fit["scale"]) is not list or type(fit["coef"]) is not list or not fit["scale"]:
        raise ContextModelError("joint fit needs scale and two-head coefficients")
    for scale in fit["scale"]:
        if require_number(scale, "training scale", minimum=0) == 0:
            raise ContextModelError("joint scale must be positive")
    for pair in fit["coef"]:
        if type(pair) is not list or len(pair) != 2:
            raise ContextModelError("joint coefficients must have two coupled heads")
        for value in pair:
            require_number(value, "joint coefficient")
    if len(fit["coef"]) != len(fit["scale"]):
        raise ContextModelError("joint scale and coefficients disagree")
    x = _array(x, "prediction features", 2)
    if x.shape[1] != len(fit["scale"]):
        raise ContextModelError("joint prediction feature width differs")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result = (x / np.asarray(fit["scale"], dtype=float)) @ np.asarray(fit["coef"], dtype=float)
        if not np.all(np.isfinite(result)):
            raise ContextModelError("nonfinite joint prediction")
        return result
    except (ValueError, ArithmeticError) as exc:
        raise ContextModelError("joint prediction is numerically unrepresentable") from exc


def fit_joint_offset(matrices, x, outcomes, *, alpha):
    """Coupled regularized likelihood, only on supplied training rows.

    Pure fitting primitive, like fit_offset: chronological membership, native
    results and untouched evaluation belong to the owning dataset runner.
    Outcomes must already be owning score buckets; none are silently censored.
    """
    x, outcomes = _array(x, "joint features", 2), _array(outcomes, "joint targets", 2)
    n, width = x.shape
    alpha = require_number(alpha, "regularization", minimum=0)
    if type(matrices) is not tuple or len(matrices) != n or n < 2 or outcomes.shape != (n, 2):
        raise ContextModelError("joint training shapes must align with at least two events")
    if np.any(outcomes < 0) or np.any(outcomes != np.floor(outcomes)):
        raise ContextModelError("joint targets must be observed integer score buckets")
    prepared = []
    for matrix, target in zip(matrices, outcomes):
        matrix = _matrix(matrix)
        if matrix.get(tuple(target), 0.) <= 0:
            raise ContextModelError("observed score lies outside positive baseline support")
        coords = np.asarray([key for key, mass in matrix.items() if mass > 0], dtype=float)
        masses = np.asarray([mass for mass in matrix.values() if mass > 0])
        prepared.append((coords, np.log(masses), math.log(matrix[tuple(target)])))
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            scale = np.maximum(np.std(x, axis=0), 1e-8)
            z = x / scale  # no intercept or centering: reference delta zero stays zero
    except (ValueError, ArithmeticError) as exc:
        raise ContextModelError("invalid joint training scale") from exc
    if not np.all(np.isfinite(z)):
        raise ContextModelError("invalid joint training scale")

    def objective(flat):
        beta = flat.reshape(width, 2)
        residuals, losses = [], []
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            deltas = z @ beta
            for delta, target, (coords, logmass, logtarget) in zip(deltas, outcomes, prepared):
                score = logmass + coords @ delta
                norm = special.logsumexp(score)
                weights = np.exp(score - norm)
                losses.append(norm - logtarget - target @ delta)
                residuals.append(weights @ coords - target)
            loss = float(np.mean(losses) + .5 * alpha * np.sum(beta * beta))
            gradient = (z.T @ np.asarray(residuals) / n + alpha * beta).ravel()
        if not math.isfinite(loss) or not np.all(np.isfinite(gradient)):
            raise ContextModelError("nonfinite joint likelihood")
        return loss, gradient

    try:
        fit = optimize.minimize(objective, np.zeros(width * 2), jac=True, method="L-BFGS-B")
        if fit.success is not True:
            raise ContextModelError("joint offset optimizer did not converge")
        coef = _array(fit.x, "joint coefficients", 1)
        if coef.shape != (width * 2,):
            raise ContextModelError("invalid joint coefficient shape")
        require_number(float(fit.fun), "fitted joint likelihood", minimum=0)
        gradient = _array(fit.jac, "fitted joint gradient", 1)
        if gradient.shape != coef.shape:
            raise ContextModelError("invalid joint gradient shape")
        objective(coef)
        coef = coef.reshape(width, 2)
        if np.any(coef[np.all(x == 0, axis=0)] != 0):
            raise ContextModelError("unidentifiable zero feature changed")
        return {"version": VERSION, "scale": scale.tolist(), "coef": coef.tolist(), "alpha": alpha, "n_rows": n}
    except ContextModelError:
        raise
    except (ValueError, ArithmeticError) as exc:
        raise ContextModelError("joint offset fitting failed") from exc
