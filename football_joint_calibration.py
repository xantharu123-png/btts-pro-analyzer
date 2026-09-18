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

LAW_VERSION = "football-joint-settlement-projection-v1"
RECIPE = {
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


@lru_cache(maxsize=32)
def _atoms(cells, specs):
    from challenge_engine import market_outcome
    groups = {}
    for index, cell in enumerate(cells):
        vector = tuple(int(market_outcome(spec, *cell)) for spec in specs)
        groups.setdefault(vector, []).append(index)
    vectors = sorted(groups)
    return np.asarray(vectors, dtype=float).T, tuple(tuple(groups[v]) for v in vectors)


def calibrate_joint_distribution(raw_matrix, specs, calibration):
    """Return a joint matrix and reproducible solver/target diagnostics."""
    ordered = tuple(sorted(specs, key=lambda s: s.key))
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
    diagnostics = {"law_version": LAW_VERSION, "success": True, "status": "identity",
                   "iterations": 0, "atoms": len(groups), "cells": len(positive),
                   "targets": dict(zip((s.key for s in ordered), targets)), "message": "identity"}
    if not ordered or np.array_equal(np.asarray(targets), raw_targets):
        return dict(raw_matrix), diagnostics
    target = np.asarray(targets)
    hessian = incidence.T @ incidence / len(ordered) + np.eye(len(prior))
    linear = incidence.T @ target / len(ordered) + prior
    try:
        result = minimize(lambda q: .5 * q @ hessian @ q - linear @ q,
            prior, jac=lambda q: hessian @ q - linear,
            bounds=[(0, None)] * len(prior),
            constraints={"type": "eq", "fun": lambda q: q.sum() - 1,
                         "jac": lambda q: np.ones(len(q))},
            method="SLSQP", options={"ftol": RECIPE["ftol"], "maxiter": RECIPE["maxiter"]})
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
