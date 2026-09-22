"""Read-only settlement comparison for a captured football ORIGINAL v2.

This regenerates the raw joint cells from their captured count parameters and
verifies that raw/effective cells settle to the stored market triplets and
effective count means. It does not re-run source selection, model fitting,
calibration targets, or the SLSQP projection. In particular it
is neither a replay-grade C1 bundle nor an injury-effect/evaluation adapter.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import math

import challenge_engine as engine
from context_models.contracts import ContextContractError, ContextIntegrityError
from context_models.football_original_storage import MAX_ORIGINAL_BYTES, _packet
from football_joint_calibration import LAW_VERSION
from football_original import FootballOriginal
from model_artifacts import _decode_object


COMPARISON_VERSION = "football-captured-joint-settlement-comparison-v1"
_VARIANTS = ("active", "season", "form")
_FAMILIES = {
    "goals": engine.GOAL_MARKET_SPECS,
    "corners": engine.CORNER_MARKET_SPECS,
    "yellow": engine.YELLOW_MARKET_SPECS,
}


def _captured_matrix(cells):
    # _packet validates cell types, mass, and uniqueness. The sorted order is
    # additionally required because the owning settlement uses ordered sums.
    coordinates = [(h, a) for h, a, _ in cells]
    if coordinates != sorted(coordinates):
        raise ContextIntegrityError("captured joint cells are not in owning order")
    return {(h, a): mass for h, a, mass in cells}


def _require_same(actual, expected, label):
    # Both sides use the same ordered Python sums and the same decoded floats.
    # A tolerance here could hide an altered captured probability or cell.
    if actual != expected:
        raise ContextIntegrityError("captured joint differs from " + label)


def _checked_triplets(packet, keys):
    for field in ("raw_probabilities", "probabilities"):
        values = packet[field]
        if set(values) != keys:
            raise ContextIntegrityError("captured market triplets differ from joint catalog")
        for key, triplet in values.items():
            if (type(triplet) is not list or len(triplet) != 3
                    or any(type(value) not in (int, float) or not math.isfinite(value)
                           or not 0 <= value <= 1 for value in triplet)):
                raise ContextIntegrityError("invalid captured market triplet " + key)


def _checked_model_means(model, field):
    pair = model.get(field)
    if (type(pair) is not list or len(pair) != 2
            or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                   for value in pair)):
        raise ContextIntegrityError("invalid captured effective means " + field)
    return pair


def _expected_raw_matrix(family, record, model):
    """Use the owning count generator, not the truncated cells' moment."""
    try:
        if family == "goals":
            return engine.score_matrix(*record["raw_means"])
        dispersion = model.get("dispersion")
        if (type(dispersion) is not list or len(dispersion) != 2
                or any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                       for value in dispersion)):
            raise ValueError("invalid captured count dispersion")
        return engine._count_matrix(*record["raw_means"], *dispersion,
                                    25 if family == "corners" else 12)
    except (TypeError, ValueError, OverflowError, FloatingPointError) as exc:
        raise ContextIntegrityError("captured raw distribution parameters are invalid") from exc


def compare_captured_joint(original: FootballOriginal) -> dict:
    """Verify and return detached market-level raw/effective comparisons.

    Input is the owning v2 ORIGINAL, optionally returned by ``load_original``.
    The result deliberately has no BaseDistribution/approval shape and cannot
    be accepted by the old raw-Poisson training or effect contracts.
    """
    if type(original) is not FootballOriginal or type(original._bytes) is not bytes:
        raise TypeError("joint comparison requires an owning FootballOriginal")
    if len(original._bytes) > MAX_ORIGINAL_BYTES:
        raise ContextContractError("joint comparison exceeds ORIGINAL byte bound")
    # The owning decoder also rejects duplicate fields and non-canonical bytes.
    try:
        packet = _decode_object(original._bytes, label="football ORIGINAL")
    except RecursionError as exc:
        raise ContextIntegrityError("football ORIGINAL exceeds supported JSON depth") from exc
    _packet(packet)
    if packet["schema"] != 2:
        raise ContextContractError("joint comparison requires ORIGINAL v2")
    if (packet["prediction_version"] != engine.CHALLENGE_PREDICTION_VERSION
            or packet["model_contract_signature"] != engine.CHALLENGE_MODEL_CONTRACT_SIGNATURE
            or packet["distribution_capture"]["law_version"] != LAW_VERSION):
        raise ContextContractError("joint comparison has no matching installed law")

    families = packet["distribution_capture"]["families"]
    included_kinds = {spec.kind for family in families for spec in _FAMILIES[family]}
    expected_specs = [asdict(spec) for spec in engine.MARKET_SPECS if spec.kind in included_kinds]
    if packet["market_specs"] != expected_specs:
        raise ContextIntegrityError("captured market catalog differs from installed law")
    keys = {spec["key"] for spec in expected_specs}
    _checked_triplets(packet, keys)

    raw_markets, effective_markets, means = {}, {}, {}
    for family, variants in families.items():
        specs = _FAMILIES[family]
        means[family] = {}
        for index, variant in enumerate(_VARIANTS):
            record = variants[variant]
            model = packet["goal_model"] if family == "goals" else packet["count_models"][family]
            if type(model) is not dict:
                raise ContextIntegrityError("invalid captured count model")
            raw = _captured_matrix(record["raw_cells"])
            _require_same(raw, _expected_raw_matrix(family, record, model),
                          family + " " + variant + " raw cells/means")
            effective = _captured_matrix(record["effective_cells"])
            if set(raw) != set(effective):
                raise ContextIntegrityError("raw/effective joint support differs")
            actual_targets = record["diagnostics"]["targets"]
            if set(actual_targets) != {spec.key for spec in specs}:
                raise ContextIntegrityError("projection targets differ from joint catalog")
            if record["diagnostics"]["status"] in {"identity", "raw-fallback"}:
                _require_same(effective, raw, "identity/fallback law")
            raw_values = engine._market_probabilities(raw, specs)
            effective_values = engine._market_probabilities(effective, specs)
            for spec in specs:
                key = spec.key
                if key not in raw_markets:
                    raw_markets[key], effective_markets[key] = [], []
                raw_markets[key].append(raw_values[key])
                effective_markets[key].append(effective_values[key])
                _require_same(packet["raw_probabilities"][key][index], raw_values[key], "raw market " + key)
                _require_same(packet["probabilities"][key][index], effective_values[key], "effective market " + key)
            pair = [sum(cell[side] * mass for cell, mass in effective.items()) for side in (0, 1)]
            field = variant + ("_lambdas" if family == "goals" else "_counts")
            _require_same(_checked_model_means(model, field), pair,
                          family + " " + variant + " effective means")
            means[family][variant] = pair
    return {
        "version": COMPARISON_VERSION,
        "scope": "captured-settlement-only",
        "original_logical_digest": hashlib.sha256(original._bytes).hexdigest(),
        "law_version": LAW_VERSION,
        "raw_probabilities": raw_markets,
        "probabilities": effective_markets,
        "delta_pp": {key: [100.0 * (new - old) for old, new in zip(raw_markets[key], effective_markets[key])]
                     for key in sorted(keys)},
        "effective_means": means,
    }
