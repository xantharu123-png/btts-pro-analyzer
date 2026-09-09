"""Regularized residual fits against immutable link-space baseline offsets.

Pure numerical routines: no source loading, empirical selection, live model
activation, intercept or feature centering. The caller owns causal training
windows, exact feature order, family routing and separate approval evidence.
"""

from __future__ import annotations

import numpy as np
from scipy import optimize, special

from context_models.contracts import (
    ContextContractError, validate_offset_fit,
)


class ContextModelError(ContextContractError):
    """Invalid numerical input or fit; callers must retain the valid baseline."""


def _link(value: str) -> str:
    if type(value) is not str or value not in {"log_rate", "logit", "identity"}:
        raise ContextModelError("unsupported offset link")
    return value


def _array(value: np.ndarray, name: str, ndim: int) -> np.ndarray:
    # Check BEFORE dtype conversion. In particular, np.asarray(masked_array)
    # discards the mask, and mixed Python lists can quietly coerce booleans.
    if type(value) is not np.ndarray or value.dtype.kind not in "fiu":
        raise ContextModelError(f"{name} must be a real numeric ndarray without bool, object, complex or masks")
    if value.ndim != ndim or not value.size:
        raise ContextModelError(f"{name} must be a nonempty {ndim}-dimensional array")
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = np.array(value, dtype=np.float64, copy=True)
        if not np.all(np.isfinite(result)):
            raise ContextModelError(f"{name} must contain only finite values")
        if value.dtype.kind in "iu" and any(int(original) != int(converted) for original, converted in zip(value.flat, result.flat)):
            raise ContextModelError(f"{name} contains an integer not exactly representable in float64")
        return result
    except (ValueError, TypeError, OverflowError, FloatingPointError) as exc:
        raise ContextModelError(f"invalid numeric {name}") from exc


def _finite_scalar(value, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ContextModelError(f"{name} must be a real finite numeric scalar")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ContextModelError(f"invalid {name}") from exc
    if not np.isfinite(number):
        raise ContextModelError(f"{name} must be finite")
    return number


def _objective_and_gradient(beta, z, offset, target, *, link, alpha, trials):
    """Specified mean losses (up to target-only constants) and exact gradients."""
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            eta = offset + z @ beta
            if not np.all(np.isfinite(eta)):
                raise ContextModelError("nonfinite offset linear predictor")
            if link == "log_rate":
                rate = np.exp(eta)
                if np.any(rate <= 0):
                    raise ContextModelError("Poisson rate underflowed outside its positive domain")
                loss = np.mean(rate - target * eta)
                residual = rate - target
            elif link == "logit":
                loss = np.mean(trials * np.logaddexp(0., eta) - target * eta)
                residual = trials * special.expit(eta) - target
            else:
                residual = eta - target
                loss = .5 * np.mean(residual ** 2)
            penalty = .5 * alpha * np.dot(beta, beta) if alpha else 0.
            objective = float(loss + penalty)
            gradient = z.T @ residual / len(z) + alpha * beta
        if not np.isfinite(objective) or not np.all(np.isfinite(gradient)):
            raise ContextModelError("nonfinite offset objective or gradient")
        return objective, gradient
    except (FloatingPointError, OverflowError, ValueError) as exc:
        raise ContextModelError("invalid offset objective or gradient") from exc


def fit_offset(
    x: np.ndarray, offset: np.ndarray, target: np.ndarray, *, link: str,
    alpha: float, trials: np.ndarray | None = None,
) -> dict:
    """Fit one named head's ordered features, using training data only.

    ``offset`` is already in link space. Alpha is supplied by the owning
    causal inner-window selection; this routine never chooses or tunes it.
    """
    link = _link(link)
    alpha = _finite_scalar(alpha, "alpha")
    if alpha < 0:
        raise ContextModelError("alpha must be nonnegative")
    x, offset, target = _array(x, "x", 2), _array(offset, "offset", 1), _array(target, "target", 1)
    n_rows, n_features = x.shape
    if n_rows < 2 or n_features < 1 or offset.shape != (n_rows,) or target.shape != (n_rows,):
        raise ContextModelError("training shapes must align with at least two rows and one feature")
    if link != "identity" and (np.any(target < 0) or np.any(target != np.floor(target))):
        raise ContextModelError("count/binomial targets must be nonnegative integer-valued observations")
    if link == "logit":
        trials = np.ones(n_rows) if trials is None else _array(trials, "trials", 1)
        if trials.shape != (n_rows,) or np.any(trials < 1) or np.any(trials != np.floor(trials)) or np.any(target > trials):
            raise ContextModelError("binomial trials and successes must be aligned legal observed counts")
    elif trials is not None:
        raise ContextModelError("trials belong only to the binomial logit link")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            scale = np.maximum(np.std(x, axis=0, ddof=0), 1e-8)
            z = x / scale  # Deliberately no mean subtraction or fitted intercept.
        if not np.all(np.isfinite(scale)) or not np.all(np.isfinite(z)):
            raise ContextModelError("nonfinite training scale or standardized features")
    except (FloatingPointError, OverflowError, ValueError) as exc:
        raise ContextModelError("invalid training scale or standardized features") from exc

    def objective(beta):
        return _objective_and_gradient(beta, z, offset, target, link=link, alpha=alpha, trials=trials)

    initial = np.zeros(n_features)
    objective(initial)  # Reject an invalid baseline even for all-zero features.
    try:
        fitted = optimize.minimize(objective, initial, jac=True, method="L-BFGS-B")
        if fitted.success is not True:
            raise ContextModelError("offset optimizer did not converge")
        coef = _array(fitted.x, "fitted coefficients", 1)
        gradient = _array(fitted.jac, "fitted gradient", 1)
        if coef.shape != (n_features,) or gradient.shape != (n_features,):
            raise ContextModelError("optimizer returned inconsistent coefficient/gradient shapes")
        _finite_scalar(fitted.fun, "fitted objective")
        if np.any(coef[np.all(x == 0, axis=0)] != 0):
            raise ContextModelError("optimizer changed an unidentifiable all-zero feature")
        objective(coef)  # Independently recheck the actual returned parameters.
        return validate_offset_fit({
            "link": link, "scale": scale.tolist(), "coef": coef.tolist(),
            "alpha": alpha, "n_rows": n_rows,
        })
    except ContextModelError:
        raise
    except Exception as exc:
        # A numerical backend exception is not permission to publish zeros,
        # old coefficients, clipped parameters or a partially fitted artifact.
        raise ContextModelError("offset optimization failed") from exc


def offset_delta(model: dict, x: np.ndarray) -> np.ndarray:
    """Apply the stored training-only scale in the original feature order."""
    try:
        model = validate_offset_fit(model)
    except ContextContractError as exc:
        raise ContextModelError(f"invalid stored offset fit: {exc}") from exc
    x = _array(x, "prediction x", 2)
    if x.shape[1] != len(model["coef"]):
        raise ContextModelError("prediction features do not match fitted feature dimensions")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            # The shared JSON contract allows finite ints beyond int64. Avoid
            # implicit object arrays for these valid stored numeric values.
            scale = np.asarray(model["scale"], dtype=np.float64)
            coef = np.asarray(model["coef"], dtype=np.float64)
            delta = (x / scale) @ coef
        if not np.all(np.isfinite(delta)):
            raise ContextModelError("nonfinite offset prediction")
        return delta
    except (FloatingPointError, OverflowError, ValueError, TypeError) as exc:
        raise ContextModelError("invalid offset prediction") from exc


def adjust_parameters(base: np.ndarray, delta: np.ndarray, *, link: str) -> np.ndarray:
    """Invert the declared link, preserving exact baseline values at zero delta."""
    link = _link(link)
    base, delta = _array(base, "base", 1), _array(delta, "delta", 1)
    if base.shape != delta.shape:
        raise ContextModelError("base and delta shapes must match without broadcasting")
    if link == "log_rate" and np.any(base <= 0):
        raise ContextModelError("base rates must be positive")
    if link == "logit" and np.any((base <= 0) | (base >= 1)):
        raise ContextModelError("base probabilities must be strictly interior")
    result = base.copy()
    changed = delta != 0
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            if link == "log_rate":
                result[changed] = np.exp(np.log(base[changed]) + delta[changed])
            elif link == "logit":
                result[changed] = special.expit(special.logit(base[changed]) + delta[changed])
            else:
                result[changed] = base[changed] + delta[changed]
        if not np.all(np.isfinite(result)):
            raise ContextModelError("adjusted parameters must be finite")
        if link == "log_rate" and np.any(result <= 0):
            raise ContextModelError("adjusted rates must remain positive")
        if link == "logit" and np.any((result <= 0) | (result >= 1)):
            raise ContextModelError("adjusted probabilities saturated outside the interior domain")
        return result
    except (FloatingPointError, OverflowError, ValueError) as exc:
        raise ContextModelError("invalid adjusted parameters") from exc
