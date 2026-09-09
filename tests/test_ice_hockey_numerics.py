"""Independent math/legacy controls for C3, not observed out-of-sample evidence."""
from copy import deepcopy
from fractions import Fraction
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from datetime import timedelta
import hashlib
import math
import sys

import numpy as np
import pytest

from context_models.contracts import ContextContractError, canonical_bytes, canonical_timestamp, digest
from test_sports_prematch import event as old_event, history as old_history
from test_ice_hockey_context import NOW, event, scope, base, inputs as raw_inputs, implementation
from test_ice_hockey_sources import raw, normalized
from test_ice_hockey_features import full_inputs, receipt, features
from test_ice_hockey_effects import inputs, replacement, fitted_artifact, approval


@pytest.mark.parametrize("home,away,ot", [(1., 2., .2), (6., 1.5, .8), (.1, .1, .5), (3., 3., 0.), (3., 3., 1.)])
def test_independent_two_poisson_score_enumeration_matches_five_markets(home, away, ot):
    hp = [math.exp(-home)*home**k/math.factorial(k) for k in range(70)]
    ap = [math.exp(-away)*away**k/math.factorial(k) for k in range(70)]
    h = math.fsum(hp[i]*ap[j] for i in range(70) for j in range(i))
    d = math.fsum(hp[i]*ap[i] for i in range(70))
    a = math.fsum(hp[i]*ap[j] for i in range(70) for j in range(i+1, 70))
    law = implementation().hockey_distribution(home, away, ot)
    assert [law[key] for key in ("home_reg", "draw_reg", "away_reg")] == pytest.approx([h, d, a], abs=2e-14)
    assert law["home_inclusive"] == pytest.approx(h+ot*d, abs=2e-14)
    assert law["away_inclusive"] == pytest.approx(a+(1-ot)*d, abs=2e-14)


def test_original_constrained_recipe_rates_and_ot_rebuilt_from_actual_exported_sample():
    original = base()
    recipe, params = original["reference_weights"], original["params"]
    fit, matches = recipe["fit"], recipe["selected"]
    coefficients = fit["coefficients"]
    t, h, a = len(fit["teams"]), fit["teams"].index("id:1"), fit["teams"].index("id:8")
    # Independent scalar reconstruction of the actual design, not factors text.
    expected_h = math.exp(coefficients[-2]+coefficients[h]+coefficients[t+a]+coefficients[-1]/2)
    expected_a = math.exp(coefficients[-2]+coefficients[a]+coefficients[t+h]-coefficients[-1]/2)
    ot = [match for match in matches if match["extra_time"] and not match["neutral"]]
    expected_ot = float((sum(Fraction(match["winner_home"]) for match in ot)+Fraction(1,2))/(len(ot)+1))
    assert params == {"home_lambda": expected_h, "away_lambda": expected_a, "overtime_home_probability": expected_ot}
    assert recipe["recipe"]["team_penalty"] == 5.
    assert recipe["recipe"]["optimizer"] == "L-BFGS-B"
    assert all(lo <= coef <= hi for coef, (lo, hi) in zip(coefficients, recipe["recipe"]["bounds"]))
    assert "not-observed-period-totals" in recipe["recipe"]["regulation_outcomes"]
    assert "influences" not in recipe and "hessian" not in recipe


@pytest.mark.parametrize("sport", ["ice_hockey", "basketball", "cricket"])
@pytest.mark.parametrize("variant", ["normal", "fresh-import", "neutral", "insufficient", "extra-price"])
def test_exact_legacy_default_output_parity_from_frozen_pre_c2_source(sport, variant):
    import sports_prematch
    path = Path(__file__).parent/"fixtures/context/basketball/sports_prematch_legacy_0d000f6.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "b4e44d03d09a6c8f22ce52568ea36f9af1c7e563d094af98c135703a0a204677"
    key = "c3_pre_context_original"
    if key not in sys.modules:
        spec = spec_from_file_location(key, path)
        legacy = module_from_spec(spec)
        sys.modules[key] = legacy
        spec.loader.exec_module(legacy)
    legacy = sys.modules[key]
    target, history = old_event(sport), old_history(sport, newly_imported=variant == "fresh-import")
    if variant == "neutral": target["neutral_site"] = True
    elif variant == "insufficient": history = history[:5]
    elif variant == "extra-price":
        target.update(odds_home=1.01, user_bankroll=900)
        for row in history: row.update(close_odds=999, price={"unknown": "ignored"})
    assert canonical_bytes(sports_prematch.predict_prematch(sport, target, history, NOW).to_dict()) == canonical_bytes(
        legacy.predict_prematch(sport, target, history, NOW).to_dict())


def test_unknown_price_fields_do_not_change_original_export_or_input_records():
    import sports_prematch
    target, rows = raw_inputs()
    original = sports_prematch.hockey_base_distribution(target, rows, NOW, context_event=event(), scope=scope())
    original_rows, original_target = deepcopy(rows), deepcopy(target)
    for obj in [target, *rows]:
        for i in range(50): obj[f"unrecognized_price_{i}"] = {"odds": 1.12+i, "bankroll": 10*i, "pick": "away"}
    modified = sports_prematch.hockey_base_distribution(target, rows, NOW, context_event=event(), scope=scope())
    assert canonical_bytes(original) == canonical_bytes(modified)
    assert all(all(row[key] == value for key, value in old.items()) for row, old in zip(rows, original_rows))
    assert all(target[key] == value for key, value in original_target.items())


def test_full_orientation_replays_original_fit_and_two_context_heads_without_refitting_ot():
    import sports_prematch
    original, items = full_inputs()
    player, _ = replacement(items)
    fv = features(items, original)
    artifact = fitted_artifact(fv, names=[f"exposure_delta_{side}/skater/20252026/{player}" for side in ("home", "away")])
    first = implementation().apply_hockey_effect(original, fv, artifact, event=event())
    target, rows = raw_inputs()
    for obj in [target, *rows]:
        for a, b in (("home_team_id", "away_team_id"), ("home_team", "away_team"), ("home_score", "away_score")):
            if a in obj and b in obj: obj[a], obj[b] = obj[b], obj[a]
        if "winner_side" in obj: obj["winner_side"] = "away" if obj["winner_side"] == "home" else "home"
    current = event()
    current["home_id"], current["away_id"] = current["away_id"], current["home_id"]
    reverse = sports_prematch.hockey_base_distribution(target, rows, NOW, context_event=current, scope=scope())
    for item in items:
        item["event"]["home_id"], item["event"]["away_id"] = item["event"]["away_id"], item["event"]["home_id"]
    mirrored = implementation().hockey_features(current, tuple(receipt(item) for item in items), reverse, cutoff=NOW, scenario_id="candidate-a")
    for name in artifact["feature_names"]:
        assert mirrored["values"][name] == fv["values"][implementation()._mirror_name(name)]
    artifact = {**artifact, "coverage": mirrored["coverage"]}
    second = implementation().apply_hockey_effect(reverse, mirrored, artifact, event=current)
    assert second["params"]["home_lambda"] == pytest.approx(first["params"]["away_lambda"], rel=1e-12)
    assert second["params"]["away_lambda"] == pytest.approx(first["params"]["home_lambda"], rel=1e-12)
    assert second["params"]["overtime_home_probability"] == pytest.approx(1-first["params"]["overtime_home_probability"], abs=1e-15)
    assert second["markets"]["home_inclusive"] == pytest.approx(first["markets"]["away_inclusive"], abs=1e-12)


def b3_arguments(*, conditional=False):
    original, fv, artifact = inputs(role="goalie" if conditional else "skater", confirmed=not conditional)
    wrapped = {"kind": "context-effect-v1", "payload": artifact}
    return dict(base=original, comparison=implementation().apply_hockey_effect(original, fv, artifact, event=event()),
        event=event(), features=fv, effect_artifact=wrapped, effect_hash=digest(wrapped), approval=approval(artifact),
        factor_roles={key: "applied" if key in artifact["feature_names"] else "not_applied" for key in fv["values"]},
        factor_states=fv["states"], limitations=[])


def test_direct_b3_has_conditional_guard_not_only_friendly_facade():
    from context_snapshots import select_context_result
    args = b3_arguments(conditional=True)
    selected = select_context_result(**args)
    assert selected["role"] == "experimental"
    assert selected["used_params"] == args["base"]["params"]
    assert selected["comparison_params"] != args["base"]["params"]


@pytest.mark.parametrize("mutation", ["event", "feature-ref", "unused-feature", "original-ref", "effect-envelope", "effect-payload", "approval", "base-as-comparison"])
def test_direct_b3_rejects_full_identity_corruption_before_conditional_fallback(mutation):
    from context_snapshots import select_context_result
    args = b3_arguments(conditional=True)
    if mutation == "event": args["event"]["schedule_revision"] = "changed"
    elif mutation == "feature-ref": args["features"]["reference_hash"] = "f"*64
    elif mutation == "unused-feature": args["features"]["refs"]["travel_hours_home"] = ["f"*64]
    elif mutation == "original-ref": args["base"]["reference_weights"]["selected"][0]["ref"] = "f"*64
    elif mutation == "effect-envelope": args["effect_artifact"]["kind"] = "context-approval-v1"
    elif mutation == "effect-payload": args["effect_artifact"]["payload"]["training_refs_hash"] = "f"*64
    elif mutation == "approval": args["approval"]["payload"]["test_events_hash"] = "f"*64
    else: args["comparison"] = deepcopy(args["base"])
    with pytest.raises(ContextContractError): select_context_result(**args)
