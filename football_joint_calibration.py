"""Versioned price-free projection of scalar targets onto one joint count law.

The unit prior anchor is a declared numerical design choice, not an empirical
optimality claim. Failure returns only the coherent raw law, never target
marginals, and explicitly disqualifies calibrated release.
"""
from functools import lru_cache
import math
import numbers

import numpy as np
from scipy.optimize import minimize

LEGACY_LAW_VERSION = "football-joint-settlement-projection-v1"
LEGACY_RECIPE = {
    "objective": "0.5*mean((A@q-t)**2)+0.5*sum((q-r)**2)",
    "prior_anchor": 1.0, "solver": "scipy-SLSQP", "ftol": 1e-12,
    "maxiter": 200, "constraints": "q>=0;sum(q)=1",
    "atoms": "identical-full-settlement-vectors-positive-raw-support",
    "split": "raw-cell-proportions", "ordering": "sorted-spec-key-cell-and-settlement-vector",
    "initial": "normalized-prior-atom-masses", "raw_normalization": "divide-by-total-mass",
    "output_normalization": "divide-fitted-atom-masses-by-their-sum", "mass_tolerance": 1e-10,
    "gradient": "A.T@(A@q-t)/len(t)+(q-r)", "identity": "exact-target-equality",
    "missing_target": "raw-marginal", "failure": "raw-distribution-no-release",
}
LAW_VERSION = "football-joint-settlement-projection-v2"
# The corrected weight is a candidate, not empirically accepted merely because
# its optimizer succeeds. The 304-game chronological comparison regressed in
# both sampled leagues; keep existing production probabilities unchanged.
ACTIVE_LAW_VERSION = LEGACY_LAW_VERSION
RECIPE = {
    **LEGACY_RECIPE,
    "objective": "0.5*sum((A@q-t)**2)+0.5*sum((q-r)**2)",
    "gradient": "A.T@(A@q-t)+(q-r)",
}
_RECIPES = {LEGACY_LAW_VERSION: LEGACY_RECIPE, LAW_VERSION: RECIPE}
_PREDICTION_VERSIONS = {
    LEGACY_LAW_VERSION: "challenge-engine:coherent-joint-calibration-v14",
    LAW_VERSION: "challenge-engine:coherent-joint-calibration-v15",
}


def recipe_for_law(law_version):
    """Read a known immutable recipe; previous captures are never relabelled."""
    if type(law_version) is not str or law_version not in _RECIPES:
        raise ValueError("unsupported joint calibration law")
    return dict(_RECIPES[law_version])


def prediction_version_for_law(law_version):
    recipe_for_law(law_version)
    return _PREDICTION_VERSIONS[law_version]


@lru_cache(maxsize=32)
def _atoms(cells, specs):
    from challenge_engine import market_outcome
    groups = {}
    for index, cell in enumerate(cells):
        vector = tuple(int(market_outcome(spec, *cell)) for spec in specs)
        groups.setdefault(vector, []).append(index)
    vectors = sorted(groups)
    return np.asarray(vectors, dtype=float).T, tuple(tuple(groups[v]) for v in vectors)


def calibrate_joint_distribution(raw_matrix, specs, calibration, *, law_version=None):
    """Return a joint matrix and reproducible solver/target diagnostics."""
    law_version = ACTIVE_LAW_VERSION if law_version is None else law_version
    recipe = recipe_for_law(law_version)
    from challenge_engine import PROJECTION_ONLY_MARKET_KEYS
    # Both published laws keep their original fit catalog. Extended ranges are
    # marginals of this same effective q, never new objective rows/atoms.
    ordered = tuple(sorted((spec for spec in specs
                            if spec.key not in PROJECTION_ONLY_MARKET_KEYS), key=lambda s: s.key))
    cells = tuple(sorted(raw_matrix))
    if not cells or any(isinstance(raw_matrix[c], bool) or not isinstance(raw_matrix[c], numbers.Real)
                        or not math.isfinite(raw_matrix[c]) or raw_matrix[c] < 0 for c in cells):
        raise ValueError("joint raw distribution has invalid masses")
    total = math.fsum(raw_matrix[c] for c in cells)
    if total <= 0 or not math.isclose(total, 1.0, abs_tol=RECIPE["mass_tolerance"], rel_tol=0):
        raise ValueError("joint raw distribution must have positive unit mass")
    positive = tuple(c for c in cells if raw_matrix[c] > 0)
    incidence, groups = _atoms(positive, ordered)
    masses = np.asarray([raw_matrix[c] / total for c in positive])
    prior = np.asarray([math.fsum(masses[i] for i in indices) for indices in groups])
    raw_targets = incidence @ prior
    targets = []
    for spec, value in zip(ordered, raw_targets):
        curve = (calibration or {}).get(spec.key)
        target = curve(float(value)) if curve is not None else float(value)
        if isinstance(target, bool) or not isinstance(target, numbers.Real) or not math.isfinite(target) or not 0 <= target <= 1:
            raise ValueError("joint calibration target must be finite and in [0,1]: " + spec.key)
        targets.append(float(target))
    diagnostics = {"law_version": law_version, "success": True, "status": "identity",
                   "iterations": 0, "atoms": len(groups), "cells": len(positive),
                   "targets": dict(zip((s.key for s in ordered), targets)), "message": "identity"}
    if not ordered or np.array_equal(np.asarray(targets), raw_targets):
        return dict(raw_matrix), diagnostics
    target = np.asarray(targets)
    # A target keeps unit strength regardless of how many other catalog
    # markets exist. The previous /n version is retained only for replay.
    if law_version == LEGACY_LAW_VERSION:
        # Keep the previous operation order bit-for-bit for frozen originals.
        hessian = incidence.T @ incidence / len(ordered) + np.eye(len(prior))
        linear = incidence.T @ target / len(ordered) + prior
    else:
        hessian = incidence.T @ incidence + np.eye(len(prior))
        linear = incidence.T @ target + prior
    try:
        result = minimize(lambda q: .5 * q @ hessian @ q - linear @ q,
            prior, jac=lambda q: hessian @ q - linear,
            bounds=[(0, None)] * len(prior),
            constraints={"type": "eq", "fun": lambda q: q.sum() - 1,
                         "jac": lambda q: np.ones(len(q))},
            method="SLSQP", options={"ftol": recipe["ftol"], "maxiter": recipe["maxiter"]})
        diagnostics.update(iterations=int(result.nit), message=str(result.message))
        if not result.success or not np.all(np.isfinite(result.x)) or np.any(result.x < 0) or abs(float(result.x.sum())-1) > RECIPE["mass_tolerance"]:
            raise ArithmeticError("solver did not return a finite nonnegative unit law: " + str(result.message))
        fitted = result.x / result.x.sum()
        effective = {c: 0.0 for c in cells}
        for atom, indices in enumerate(groups):
            for index in indices:
                effective[positive[index]] = float(fitted[atom] * masses[index] / prior[atom])
        if (any(not math.isfinite(p) or p < 0 for p in effective.values())
                or not math.isclose(math.fsum(effective.values()), 1.0, rel_tol=0, abs_tol=RECIPE["mass_tolerance"])):
            raise ArithmeticError("split cells are not a finite nonnegative unit law")
        diagnostics["status"] = "projected"
        return effective, diagnostics
    except (ArithmeticError, ValueError, RuntimeError) as exc:
        diagnostics.update(success=False, status="raw-fallback", message=str(exc))
        return dict(raw_matrix), diagnostics


def projection_target_diagnostics(matrix, specs, targets):
    """Opt-in measurement of an already returned law, without fitting it again.

    Values and signed residuals (attained minus target) are probability
    fractions; the mean squared residual is in squared fractions. This report
    is not part of frozen projection diagnostics/original bytes or a release
    gate, and its size is not evidence of predictive quality.
    """
    from challenge_engine import market_outcome
    if not isinstance(matrix, dict) or not matrix or not isinstance(targets, dict):
        raise ValueError("projection measurement requires a law and target mapping")
    for cell, mass in matrix.items():
        if (not isinstance(cell, tuple) or len(cell) != 2
                or any(isinstance(value, bool) or not isinstance(value, numbers.Integral)
                       or value < 0 for value in cell)
                or isinstance(mass, bool) or not isinstance(mass, numbers.Real)
                or not math.isfinite(mass) or mass < 0):
            raise ValueError("projection measurement requires valid score masses")
    if not math.isclose(math.fsum(matrix.values()), 1., abs_tol=LEGACY_RECIPE["mass_tolerance"], rel_tol=0):
        raise ValueError("projection measurement requires unit mass")
    catalog = {}
    for spec in specs:
        if spec.key in catalog:
            raise ValueError("projection measurement requires unique market keys")
        catalog[spec.key] = spec
    attained, residuals = {}, {}
    for key in sorted(targets):
        target = targets[key]
        if (key not in catalog or isinstance(target, bool) or not isinstance(target, numbers.Real)
                or not math.isfinite(target) or not 0 <= target <= 1):
            raise ValueError("projection measurement target is invalid or unknown")
        attained[key] = math.fsum(mass for cell, mass in matrix.items()
                                  if market_outcome(catalog[key], *cell))
        residuals[key] = attained[key] - target
    return {"attained": attained, "residuals": residuals,
            "max_abs_residual": max((abs(value) for value in residuals.values()), default=0.),
            "mean_squared_residual": (math.fsum(value * value for value in residuals.values())
                                      / len(residuals) if residuals else 0.)}
