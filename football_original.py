"""Detached same-call football calculation, not a context/source approval.

The legacy model slices history at kickoff, not at the later capture clock.
These are its actual unrounded inputs/outputs and calibration recipes; the
per-market calibrated marginals are NOT a new coherent joint distribution.
No provider, file, database, training or replay operation lives here.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math


_SCALAR = object()
_FIXTURE = {
    "fixture": {"id": _SCALAR, "date": _SCALAR, "timestamp": _SCALAR,
                "referee": _SCALAR, "status": {"short": _SCALAR, "long": _SCALAR}},
    "league": {"id": _SCALAR, "season": _SCALAR},
    "teams": {side: {"id": _SCALAR} for side in ("home", "away")},
    "goals": {side: _SCALAR for side in ("home", "away")},
    "challenge_stats": {key: _SCALAR for key in ("xg_home", "xg_away", "corners_home", "corners_away",
                                                 "yellow_cards_home", "yellow_cards_away")},
    "challenge_source": _SCALAR,
}
_GOAL_FIELDS = ("active_lambdas", "season_lambdas", "form_lambdas", "venue_samples",
                "form_samples", "league_sample", "freshness_days", "freshness_observed_at", "xg_coverage")
_COUNT_FIELDS = ("active_counts", "season_counts", "form_counts", "venue_samples", "form_samples",
                 "league_sample", "dispersion", "referee_sample", "referee_mean")


@dataclass(frozen=True)
class FootballOriginal:
    """Immutable internal capture; each projection returns fresh detached data."""

    _bytes: bytes

    def to_dict(self):
        return json.loads(self._bytes)


def _capture_now():
    return datetime.now(timezone.utc)


def _unavailable(kind, issues):
    issues.add("input-or-result-not-json-representable")
    return {"unavailable_value": kind}


def _scalar(value, issues):
    if value is None or type(value) is bool:
        return value
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            return _unavailable("invalid-utf8", issues)
        return value
    if type(value) in (int, float):
        try:
            if math.isfinite(value):
                return value
        except OverflowError:
            return _unavailable("unsupported-integer", issues)
        return _unavailable("nonfinite-number", issues)
    return _unavailable("unsupported-type", issues)


def _project(value, schema, issues):
    if schema is _SCALAR:
        return _scalar(value, issues)
    if type(value) is not dict:
        return _unavailable("non-object", issues)
    return {key: _project(value[key], child, issues) for key, child in schema.items() if key in value}


def _json_value(value, issues):
    if type(value) in (tuple, list):
        return [_json_value(item, issues) for item in value]
    if type(value) is dict:
        return {key: _json_value(item, issues) for key, item in value.items()}
    return _scalar(value, issues)


def _probabilities(values, issues):
    # Arbitrary legacy callables remain executable, but their nonnumeric
    # results are not an allowlisted source of arbitrary capture payloads.
    return {key: [_scalar(value, issues) if type(value) in (int, float, bool)
                  else _unavailable("non-numeric-market-value", issues)
                  for value in triplet] for key, triplet in values.items()}


def calibration_recipe(curve):
    """Describe only owning laws, never inspect or execute arbitrary callables."""
    from challenge_engine import ConservativeMarketCalibration, MarketCalibration
    if curve is None:
        return {"kind": "identity"}
    if type(curve) is MarketCalibration:
        issues = set()
        if type(curve.points) not in (tuple, list) or type(curve.samples) is not int:
            return {"kind": "unsupported-callable"}
        # Samples are ancillary to __call__, but must obey the same numeric
        # capture boundary as points; huge integers cannot enter recipe JSON.
        samples = _scalar(curve.samples, issues)
        points = []
        for point in curve.points:
            if (type(point) not in (tuple, list) or len(point) != 2
                    or any(type(value) not in (int, float) for value in point)):
                return {"kind": "unsupported-callable"}
            points.append([_scalar(value, issues) for value in point])
        if issues:
            return {"kind": "unsupported-callable"}
        return {"kind": "legacy-market-calibration-v1", "points": points, "samples": samples}
    if type(curve) is ConservativeMarketCalibration:
        if type(curve.source_curves) is not tuple:
            return {"kind": "unsupported-callable"}
        return {"kind": "legacy-minimum-source-calibration-v1",
                "source_curves": [calibration_recipe(source) for source in curve.source_curves]}
    return {"kind": "unsupported-callable"}


def _unsupported_recipe(recipe):
    return recipe["kind"] == "unsupported-callable" or any(
        _unsupported_recipe(child) for child in recipe.get("source_curves", ()))


def football_original_inputs(fixture, history, team_history, *, logical_history_cutoff):
    """Detach the allowlisted inputs before the actual model consumes them."""
    from context_models.contracts import canonical_timestamp
    issues = set()
    try:
        canonical_timestamp(fixture["fixture"]["date"])
    except (ValueError, KeyError, TypeError, OverflowError):
        issues.add("aware-native-schedule-unavailable")
    result = {"fixture": _project(fixture, _FIXTURE, issues),
              "league_history": [_project(row, _FIXTURE, issues) for row in history],
              "team_history": None if team_history is None else [_project(row, _FIXTURE, issues) for row in team_history],
              "logical_history_cutoff": (canonical_timestamp(logical_history_cutoff)
                                         if logical_history_cutoff is not None else None)}
    result["limitations"] = sorted(issues)
    return result


def capture_football_original(*, inputs, model, raw_probabilities,
                             calibration_recipes, provenance, market_specs,
                             prediction_version, model_contract_signature):
    """Copy an already executed original without fitting/evaluating it again.

    Unknown native/source or ancillary metadata never invalidates the original
    calculation. Unrepresentable accepted legacy values receive explicit typed
    markers and a limitation, not a fabricated number or a context approval.
    The callback is an internal observing seam, not an authoritative input API.
    """
    from context_models.contracts import canonical_timestamp
    captured_at = canonical_timestamp(_capture_now())
    issues = set(inputs["limitations"])
    if any(_unsupported_recipe(recipe) for recipe in calibration_recipes.values()):
        issues.add("calibration-recipe-unavailable")
    # Raw IDs are preserved without silently becoming verified native aliases.
    if provenance["reference_weights"].get("kind") == "unavailable":
        issues.add("goal-reference-provenance-unavailable")
    payload = {
        "schema": 1, "kind": "football-original-market-calculation-v1",
        "prediction_version": prediction_version, "model_contract_signature": model_contract_signature,
        "captured_at": captured_at, "logical_history_cutoff": inputs["logical_history_cutoff"],
        "source_evidence": "unresolved-receipts-not-in-this-capture",
        "fixture": inputs["fixture"], "league_history": inputs["league_history"],
        "team_history": inputs["team_history"],
        "goal_model": _json_value({key: model[key] for key in _GOAL_FIELDS}, issues),
        "count_models": {family: _json_value({key: value[key] for key in _COUNT_FIELDS}, issues)
                         for family, value in model["count_models"].items()},
        "raw_probabilities": _probabilities(raw_probabilities, issues),
        "probabilities": _probabilities(model["probabilities"], issues),
        "calibration_recipes": calibration_recipes,
        "market_specs": [{key: getattr(spec, key) for key in
                          ("key", "market", "selection", "kind", "side", "threshold", "low", "high")}
                         for spec in market_specs if spec.key in model["probabilities"]],
        "goal_provenance": _json_value(provenance, issues),
    }
    payload["limitations"] = sorted(issues)
    return FootballOriginal(json.dumps(payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8"))
