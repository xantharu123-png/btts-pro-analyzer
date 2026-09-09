"""Price-free, experimental tennis residual comparisons against ORIGINAL bases.

This numerical adapter neither loads sources nor fits/activates a live model.
Winner v1 uses signed B6 differences. Serve v1 uses mirror-constrained B2 heads
and the existing IID-set, hold-proxy/seven-point-tiebreak simulator, unrounded.
That scoring approximation is an explicit model variant, not a claim that all
actual tennis rules or point-level physiology have been identified.

B6 provenance, genuine serve-training successes/trials, chronological D1 rows,
D2 empirical approval and runtime integration remain separate obligations. A
well-formed coefficient/artifact hash alone proves none of those obligations.
"""

from __future__ import annotations

from copy import deepcopy
from math import fsum, isfinite

import numpy as np

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, digest, event_in_population,
    require_digest, require_object, validate_base_distribution,
    validate_effect_artifact, validate_event, validate_feature_vector,
    validate_markets, validate_parameters,
)
from context_models.offset import ContextModelError, adjust_parameters, offset_delta
from context_models.tennis import FEATURE_VERSION, METRICS, WINDOWS, tennis_reference_hash
from context_snapshots import select_context_result
from model_artifacts import canonical_bytes
from tennis.simulator import simulate_match


WINNER_VARIANT = "tennis-winner-performed-load-antisymmetric-v1"
SERVE_VARIANT = "tennis-serve-performed-load-mirrored-iidsets-holdproxy-tb7-strict-v1"
SERVE_BASE_VERSION = "tennis-serve-iidsets-holdproxy-tb7-strict-v1"
COMPARISON_VERSION = "tennis-context-comparison-v1"
SINGLES_FORMATS = {"singles_best_of_3": 3, "singles_best_of_5": 5}

# Closed measured B6 vocabulary. Completeness indicators are coverage, not
# sports effects; missing availability/travel/return has no v1 fitted input.
_ROOTS = {
    **{f"observed_{metric}_{days}d": "workload" for metric in METRICS for days in WINDOWS},
    "observed_recovery_minimum_hours": "recovery",
    "observed_recovery_exact_hours": "recovery",
}
_FEATURES = {f"{root}_{side}": (root, side, group)
             for root, group in _ROOTS.items() for side in ("a", "b", "delta")}
_COVERAGE_CASES = {
    "observed-only.exact-observed.known-end-times",
    "observed-only.receipt-bound-observed.missing-end-times",
    "observed-only.receipt-bound-observed.partial-end-times",
    *(f"observed-only.missing-rest.{timing}" for timing in
      ("no-history", "known-end-times", "missing-end-times", "partial-end-times")),
}


def tennis_serve_markets(params: dict) -> dict[str, float]:
    """Versioned probability-only catalog from one strict simulator result.

    No expected-games number masquerades as a probability. Half-game lines do
    not have pushes. All pairs/counts come from the same joint distribution;
    this method never recalibrates a winner separately or borrows Elo output.
    """
    try:
        params = validate_parameters(params, "tennis:serve")
        m = simulate_match(params["hold_a"], params["hold_b"], params["best_of"], strict=True)
        needed = params["best_of"] // 2 + 1
        markets = {"winner_a": m.p_a_win, "winner_b": m.p_b_win,
                   "tiebreak_yes": m.p_tiebreak_in_match, "tiebreak_no": 1 - m.p_tiebreak_in_match}
        for total in range(needed, params["best_of"] + 1):
            markets[f"exact_{total}_sets"] = m.sets_played[total]
        for lower in range(needed, params["best_of"]):
            markets[f"over_{lower}_5_sets"] = fsum(p for n, p in m.sets_played.items() if n > lower + .5)
            markets[f"under_{lower}_5_sets"] = fsum(p for n, p in m.sets_played.items() if n < lower + .5)
        for (sa, sb), probability in m.correct_scores.items():
            markets[f"correct_score_{sa}_{sb}"] = probability
        for side in ("a", "b"):
            markets[f"set_handicap_{side}_minus_1_5"] = fsum(
                p for (sa, sb), p in m.correct_scores.items()
                if (sa - sb if side == "a" else sb - sa) > 1.5
            )
        # All nontrivial physical half-game total lines, plus the declared
        # ordinary +/- half-game handicap grid. Other catalogs need a version.
        for lower in range(6 * needed, 13 * params["best_of"]):
            markets[f"over_{lower}.5_games"] = fsum(p for n, p in m.games_total.items() if n > lower + .5)
            markets[f"under_{lower}.5_games"] = fsum(p for n, p in m.games_total.items() if n < lower + .5)
        for half_line in range(-13, 14, 2):
            line = half_line / 2
            suffix = f"{'minus' if line < 0 else 'plus'}_{abs(half_line)//2}_5"
            for side in ("a", "b"):
                markets[f"game_handicap_{side}_{suffix}"] = fsum(
                    p for diff, p in m.games_diff.items() if (diff if side == "a" else -diff) + line > 0
                )
        return validate_markets(markets, family="tennis:serve")
    except (ContextContractError, ValueError, TypeError, ArithmeticError, KeyError) as exc:
        raise ContextModelError("tennis serve distribution is invalid or numerically unrepresentable") from exc


def _feature_input(features: dict, names: list[str], *, family: str) -> np.ndarray:
    for name in names:
        if name not in _FEATURES or (family == "tennis:winner" and _FEATURES[name][1] != "delta"):
            raise ContextModelError("unsupported tennis feature or non-antisymmetric winner input")
        root, side, _ = _FEATURES[name]
        if _FEATURES[name][2] == "workload":
            # B6's available total is an observed-subset sum, not necessarily
            # a fully measured observed subset. Never treat missing minutes in
            # another known match as zero through that partial sum. This still
            # does NOT certify complete player-history/schedule collection.
            _, metric, period = root.split("_")
            for participant in (("a", "b") if side == "delta" else (side,)):
                complete = f"observed_{metric}_complete_{period}_{participant}"
                if (features["states"].get(complete) != "available" or features["values"].get(complete) != 1
                        or not features["refs"].get(complete)):
                    raise ContextModelError("consumed tennis feature has incomplete observed-subset coverage")
        required = [name] if side != "delta" else [root + "_a", root + "_b", name]
        for key in required:
            if (features["states"].get(key) != "available" or not features["refs"].get(key)
                    or features["values"].get(key) is None):
                raise ContextModelError("tennis feature lacks available observed provenance")
            if key != root + "_delta" and features["values"][key] < 0:
                raise ContextModelError("observed tennis feature cannot be negative")
            value = features["values"][key]
            if type(value) is int and int(float(value)) != value:
                raise ContextModelError("tennis feature cannot be represented exactly in the fitted numeric domain")
        if side == "delta":
            a, b = features["values"][root + "_a"], features["values"][root + "_b"]
            if not isfinite(a - b) or features["values"][name] != a - b:
                raise ContextModelError("tennis signed feature does not match its observed A/B values")
            if features["refs"][name] != sorted(set(features["refs"][root + "_a"]) | set(features["refs"][root + "_b"])):
                raise ContextModelError("tennis signed feature provenance disagrees with its A/B inputs")
    return np.array([[features["values"][name] for name in names]], dtype=np.float64)


def _mirror_heads(artifact: dict) -> None:
    """The opposing head is the same learned law in exchanged coordinates.

    D1 must fit shared/mirror-constrained parameters. Independent unconstrained
    fits are not repaired by averaging predictions. Exact structural equality
    is required; tolerance is not a new free antisymmetric parameter.
    """
    names = artifact["feature_names"]
    a, b = artifact["heads"]["hold_a"], artifact["heads"]["hold_b"]
    if a["alpha"] != b["alpha"] or a["n_rows"] != b["n_rows"]:
        raise ContextModelError("serve mirror heads disagree on their shared fit")
    for index, name in enumerate(names):
        root, side, _ = _FEATURES[name]
        counterpart = root + ("_b" if side == "a" else "_a" if side == "b" else "_delta")
        if counterpart not in names:
            raise ContextModelError("serve feature routing lacks its mirror counterpart")
        other = names.index(counterpart)
        sign = -1 if side == "delta" else 1
        if a["scale"][index] != b["scale"][other] or sign * a["coef"][index] != b["coef"][other]:
            raise ContextModelError("serve heads violate the exact mirror constraint")


def _prepare(base: dict, features: dict, artifact: dict, event: dict):
    original = validate_base_distribution(base)
    event = validate_event(event)
    features = validate_feature_vector(features)
    artifact = validate_effect_artifact(artifact)
    family = original["family"]
    if family not in {"tennis:winner", "tennis:serve"} or artifact["family"] != family:
        raise ContextModelError("tennis effect and original family differ")
    if original["version"].startswith(COMPARISON_VERSION):
        raise ContextModelError("tennis effect requires an original baseline, never a prior comparison")
    if (original["event_key"] != event["event_key"] or features["event_key"] != event["event_key"]
            or original["cutoff"] != features["cutoff"]):
        raise ContextIntegrityError("tennis input event or cutoff identities differ")
    reference_hash = tennis_reference_hash(original, event)
    if features["reference_hash"] != reference_hash:
        raise ContextIntegrityError("tennis features were built against a different original reference")
    expected_variant = WINNER_VARIANT if family == "tennis:winner" else SERVE_VARIANT
    if artifact["model_variant"] != expected_variant or artifact["preprocessing_artifacts"]:
        raise ContextModelError("unsupported tennis model variant or preprocessing")
    if (event["status"] != "scheduled" or event["scheduled_start"] <= original["cutoff"]
            or artifact["training_end"] > original["cutoff"]):
        raise ContextModelError("tennis event or trained model is not eligible at the decision cutoff")
    allowed_formats = set(SINGLES_FORMATS) | ({"singles"} if family == "tennis:winner" else set())
    if (event["format"] not in allowed_formats or not set(artifact["population"]["formats"]) <= allowed_formats
            or not event_in_population(event, artifact["population"])):
        raise ContextModelError("tennis effect population or singles format mismatch")
    if (event.get("tour") not in {"ATP", "WTA"} or artifact["population"]["tours"] != [event["tour"]]
            or event.get("surface") not in {"Hard", "Clay", "Grass", "Carpet"}
            or artifact["population"]["surfaces"] != [event["surface"]]
            or artifact["population"]["indoor"] != [event.get("indoor")]):
        raise ContextModelError("tennis effect requires separately scoped tour/surface/environment")
    if (features["version"] != FEATURE_VERSION or artifact["feature_version"] != FEATURE_VERSION
            or features["coverage"] != artifact["coverage"]
            or features["coverage"]["version"] != "tennis-performed-load-coverage-v1"
            or features["coverage"]["case"] not in _COVERAGE_CASES):
        raise ContextModelError("tennis feature version or measured coverage mismatch")
    x = _feature_input(features, artifact["feature_names"], family=family)
    if family == "tennis:serve":
        if SINGLES_FORMATS[event["format"]] != original["params"]["best_of"]:
            raise ContextModelError("actual singles format differs from original best_of")
        if original["version"] != SERVE_BASE_VERSION:
            raise ContextModelError("serve basis must use the same explicit simulator version")
        _mirror_heads(artifact)
        catalog = tennis_serve_markets(original["params"])
        if any(name not in catalog or probability != catalog[name] for name, probability in original["markets"].items()):
            raise ContextModelError("serve basis markets do not match the original shared distribution")
    return original, features, artifact, event, x


def _comparison(original: dict, features: dict, artifact: dict, event: dict, x: np.ndarray, *, counterfactual: str | None = None) -> dict:
    if original["family"] == "tennis:winner":
        delta = offset_delta(artifact["heads"]["winner"], x)
        p = float(adjust_parameters(np.array([original["params"]["p_a"]], dtype=np.float64), delta, link="logit")[0])
        params, markets = {"p_a": p}, {"winner_a": p, "winner_b": 1-p}
    else:
        delta = np.array([float(offset_delta(artifact["heads"][head], x)[0]) for head in ("hold_a", "hold_b")])
        holds = adjust_parameters(np.array([original["params"][head] for head in ("hold_a", "hold_b")], dtype=np.float64), delta, link="logit")
        params = {"hold_a": float(holds[0]), "hold_b": float(holds[1]), "best_of": original["params"]["best_of"]}
        catalog = tennis_serve_markets(params)
        markets = {name: catalog[name] for name in original["markets"]}
    identity = {"schema": 1, "base_hash": digest(original),
                "effect_hash": digest({"kind": "context-effect-v1", "payload": artifact}),
                "feature_hash": digest(features), "event": event, "counterfactual_without": counterfactual}
    return validate_base_distribution({**deepcopy(original), "version": COMPARISON_VERSION,
                                      "model_hash": digest(identity), "params": params, "markets": markets})


def apply_tennis_effect(base: dict, features: dict, artifact: dict, *, event: dict) -> dict:
    """Return an internal comparison, never an approval or public replacement."""
    return _comparison(*_prepare(base, features, artifact, event))


def tennis_factor_comparisons(base: dict, features: dict, artifact: dict, *, event: dict) -> dict[str, dict]:
    """Leave-one-group-out contrasts, NOT additive causal explanations.

    Zero here is a declared mathematical counterfactual in the fitted input,
    never a replacement for missing observations in a FeatureVector. Wrapped
    contrasts cannot accidentally be passed to B3 as BaseDistributions.
    """
    original, features, artifact, event, x = _prepare(base, features, artifact, event)
    full = _comparison(original, features, artifact, event, x)
    comparisons = {}
    for group in sorted({_FEATURES[name][2] for name in artifact["feature_names"]}):
        without = x.copy()
        for index, name in enumerate(artifact["feature_names"]):
            if _FEATURES[name][2] == group:
                without[0, index] = 0.
        comparison = _comparison(original, features, artifact, event, without, counterfactual=group)
        comparisons[group] = {"kind": "tennis-group-counterfactual-v1", "additive": False,
                              "base_hash": digest(original), "comparison": comparison,
                              "delta_pp_vs_full": {name: 100 * (probability - full["markets"][name])
                                  for name, probability in comparison["markets"].items()}}
    return comparisons


def tennis_context_result(base: dict, features: dict, effect_artifact: dict, *, event: dict,
                          effect_hash: str, approval: dict | None = None) -> dict:
    """Narrow B3 boundary: typed model failure retains the unchanged valid base.

    The caller supplies A1's exact kind/payload and hash; only D2's trusted
    resolver may supply an approval. Invalid identity is not disguised as a
    data gap. The current adapter does not call runtime/15K or certify events.
    """
    require_object(effect_artifact, {"kind", "payload"}, label="tennis A1 effect envelope")
    require_digest(effect_hash, "tennis A1 effect hash")
    artifact = validate_effect_artifact(effect_artifact["payload"])
    if (effect_artifact["kind"] != "context-effect-v1" or digest(effect_artifact) != effect_hash
            or canonical_bytes(artifact) != canonical_bytes(effect_artifact["payload"])):
        raise ContextIntegrityError("tennis A1 effect identity mismatch")
    limitations = []
    try:
        comparison = apply_tennis_effect(base, features, artifact, event=event)
    except ContextModelError:
        comparison = None
        limitations.append("tennis-numerical-comparison-unavailable")
    return select_context_result(base, comparison, event=event, features=features,
                                 effect_artifact=effect_artifact, effect_hash=effect_hash, approval=approval,
                                 factor_roles={name: "applied" if name in artifact["feature_names"] else "not_applied"
                                               for name in features["values"]},
                                 factor_states=dict(features["states"]), limitations=limitations)
