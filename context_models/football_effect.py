"""Pure B5 two-head goal comparisons; no training, prices or live activation.

Only the existing full-time Goal MarketSpec contracts are recalculated. A
comparison is not an approved forecast: B3/D2/D3 retain that separate decision.
No old per-market calibration is applied to the one shared goal distribution.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import math

import numpy as np

import challenge_engine as engine
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, digest, event_in_population,
    require_number, require_text, validate_base_distribution, validate_effect_artifact,
    validate_event, validate_feature_vector,
)
from context_models.offset import ContextModelError, adjust_parameters, offset_delta
from model_artifacts import canonical_bytes


FAMILY = "football:goals:90min"
COMPARISON_VERSION = "football-context-goal-rates-v1"
GROUP_VERSION = "football-counterfactual-groups-v1"
GOAL_KINDS = frozenset({"result", "double_chance", "btts", "total", "team_total", "team_range", "result_total", "mixed_or"})
UNCHANGED_KINDS = frozenset({"corner_total", "team_corners", "yellow_total", "team_yellow"})


def _market_contracts(base):
    catalog = {}
    for spec in engine.MARKET_SPECS:
        if type(spec) is not engine.MarketSpec or spec.key in catalog:
            raise ContextIntegrityError("football market catalog contains ambiguous contracts")
        catalog[spec.key] = spec
    requested = []
    for key in sorted(base["markets"]):
        spec = catalog.get(key)
        if spec is None or spec.kind not in GOAL_KINDS | UNCHANGED_KINDS:
            # There is currently no halftime MarketSpec in this catalog. An
            # unknown key is not evidence of a foreign family to carry forward.
            raise ContextContractError("unknown or unsupported football market contract")
        requested.append(spec)
    if not any(spec.kind in GOAL_KINDS for spec in requested):
        raise ContextContractError("goal-family comparison needs a declared goal market")
    return tuple(requested)


def _checked(base, features, artifact, event):
    base, features, event = validate_base_distribution(base), validate_feature_vector(features), validate_event(event)
    effect = validate_effect_artifact(artifact)
    if canonical_bytes(effect) != canonical_bytes(artifact):
        raise ContextIntegrityError("effect must retain the canonical verified A1 payload")
    if base["family"] != FAMILY or effect["family"] != FAMILY or event["sport"] != "football" or event["format"] != "90min":
        raise ContextContractError("football effects own only the regulation goal family")
    if base["version"] == COMPARISON_VERSION:
        raise ContextIntegrityError("an effect comparison cannot replace its original baseline")
    if base["event_key"] != features["event_key"] or base["event_key"] != event["event_key"] or base["cutoff"] != features["cutoff"]:
        raise ContextIntegrityError("football comparison event or decision revision differs")
    if event["status"] != "scheduled" or base["cutoff"] >= event["scheduled_start"]:
        raise ContextContractError("football comparison requires a prematch scheduled event")
    if not event_in_population(event, effect["population"]):
        raise ContextContractError("football effect population does not cover this event")
    if effect["feature_version"] != features["version"] or effect["coverage"] != features["coverage"]:
        raise ContextContractError("football effect feature version or coverage differs")
    if effect["training_end"] > base["cutoff"]:
        raise ContextContractError("football effect training follows the decision cutoff")
    preprocessing = sorted(set(effect["preprocessing_artifacts"].values()))
    if features["reference_hash"] != digest({"base_hash": digest(base), "preprocessing": preprocessing}):
        raise ContextIntegrityError("football features do not belong to the original base reference")
    if base["reference_weights"]["kind"] == "football-goals-v1":
        for side, participant in (("home", "home_id"), ("away", "away_id")):
            component = base["reference_weights"]["heads"][side]["components"]["venue_attack"]
            if component["team_join"] == "verified_native" and component["team_id"] != event[participant]:
                raise ContextIntegrityError("football base reference has a different team orientation")
    for name in effect["feature_names"]:
        if name not in features["values"] or features["states"][name] != "available" or not features["refs"][name]:
            raise ContextContractError("every consumed football feature needs available referenced evidence")
    return base, features, effect, event, _market_contracts(base)


def _validated_matrix(home, away):
    # Existing engine limits (currently >0 through 8 for this positive-rate
    # family) remain authoritative. Unsupported rates are errors, never clips.
    matrix = engine.score_matrix(home, away)
    if type(matrix) is not dict or not matrix:
        raise ContextModelError("goal matrix must be a nonempty score distribution")
    for score, probability in matrix.items():
        if type(score) is not tuple or len(score) != 2 or any(type(n) is not int or n < 0 for n in score):
            raise ContextModelError("goal matrix has an invalid regulation score")
        require_number(probability, "goal score probability", minimum=0, maximum=1)
    if not math.isclose(math.fsum(matrix.values()), 1., rel_tol=0., abs_tol=1e-12):
        raise ContextModelError("goal matrix probability mass is not normalized")
    return matrix


def _numeric_array(values):
    # Preserve B2's integer-input guard before creating a float array. Casting
    # a mixed JSON list first would irreversibly hide a rounded large integer.
    if any(type(value) is int and int(float(value)) != value for value in values):
        raise ContextModelError("football numeric integer is not exactly representable in float64")
    return np.array(values, dtype=np.float64)


def apply_football_effect(base: dict, features: dict, artifact: dict, *, event: dict) -> dict:
    """Return a complete comparison BaseDistribution from ORIGINAL base rates.

    The caller supplies an already A1-resolved canonical effect payload. Its
    public digest binds transport, not empirical approval. Feature names are
    read in the artifact's exact order, independently of JSON mapping order.
    Any invalid input/distribution raises a typed contract/model error before
    returning; the caller retains the unchanged original baseline.
    """
    base, features, effect, event, specs = _checked(base, features, artifact, event)
    try:
        x = _numeric_array([features["values"][name] for name in effect["feature_names"]]).reshape(1, -1)
        params = {}
        for side in ("home", "away"):
            delta = offset_delta(effect["heads"][side], x)
            name = side + "_lambda"
            params[name] = float(adjust_parameters(_numeric_array([base["params"][name]]), delta, link="log_rate")[0])
        matrix = _validated_matrix(params["home_lambda"], params["away_lambda"])
        markets = dict(base["markets"])
        for spec in specs:
            if spec.kind in GOAL_KINDS:
                markets[spec.key] = engine.market_probability(matrix, spec)
        effect_hash = digest({"kind": "context-effect-v1", "payload": effect})
        model_hash = digest({
            "version": COMPARISON_VERSION, "family": FAMILY,
            "base_hash": digest(base), "feature_hash": digest(features), "event": event,
            "effect_hash": effect_hash, "market_contracts": [asdict(spec) for spec in specs],
            "joint_calibration": effect["joint_calibration"],
        })
        return validate_base_distribution({**deepcopy(base), "version": COMPARISON_VERSION,
                                           "model_hash": model_hash, "params": params, "markets": markets})
    except ContextModelError:
        raise
    except (ValueError, TypeError, OverflowError, FloatingPointError) as exc:
        raise ContextModelError("football effect cannot produce a complete valid goal distribution") from exc


def _groups(value, names):
    if type(value) is not dict or not value:
        raise ContextContractError("counterfactual groups must be an explicit nonempty mapping")
    normalized, covered = {}, set()
    for group, members in value.items():
        require_text(group, "counterfactual group", code=True)
        if type(members) is not list or not members or any(type(name) is not str for name in members):
            raise ContextContractError("each group needs an actual nonempty feature-name list")
        if len(members) != len(set(members)) or not set(members) <= set(names):
            raise ContextContractError("group contains duplicate or unconsumed features")
        if members != [name for name in names if name in members]:
            raise ContextContractError("group members must preserve the artifact feature order")
        normalized[group] = list(members)
        covered.update(members)
    if covered != set(names):
        raise ContextContractError("counterfactual groups must cover every consumed feature")
    return {group: normalized[group] for group in sorted(normalized)}


def football_factor_comparisons(base: dict, features: dict, artifact: dict, *, event: dict, groups: dict) -> dict:
    """Separate model counterfactuals, NOT observed causal or additive effects.

    Zero each declared group's reference-difference columns. Shared interaction
    columns may belong to several groups and are zeroed in each independent
    contrast. No feature-name guessing, sequential subtraction or total-effect
    allocation occurs. D1/D3 own the later versioned grouping provenance.
    ``delta_pp_vs_full`` is counterfactual minus full, including unchanged zero
    differences for other registered market families; none is newly certified.
    """
    base, features, effect, event, _ = _checked(base, features, artifact, event)
    groups = _groups(groups, effect["feature_names"])
    full = apply_football_effect(base, features, effect, event=event)
    contrasts = {}
    for name, members in groups.items():
        counterfactual = deepcopy(features)
        counterfactual["values"].update({feature: 0. for feature in members})
        comparison = apply_football_effect(base, counterfactual, effect, event=event)
        contrasts[name] = {
            "feature_names": members, "counterfactual_feature_hash": digest(counterfactual),
            "comparison": comparison,
            "delta_pp_vs_full": {key: 100. * (probability - full["markets"][key]) for key, probability in comparison["markets"].items()},
        }
    return {
        "version": GROUP_VERSION, "kind": "model_counterfactual", "additive": False,
        "base_hash": digest(base), "feature_hash": digest(features),
        "effect_hash": digest({"kind": "context-effect-v1", "payload": effect}),
        "groups_hash": digest({"version": GROUP_VERSION, "groups": groups}),
        "full": full, "groups": contrasts,
    }
