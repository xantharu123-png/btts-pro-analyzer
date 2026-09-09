"""Actual B2 fits on synthetic counts. Approval envelopes are CPU stubs only."""
from copy import deepcopy
from datetime import timedelta
import math

import numpy as np
import pytest

from context_models.contracts import ContextContractError, canonical_bytes, canonical_timestamp, digest, validate_base_distribution
from context_models.offset import fit_offset, offset_delta
from test_ice_hockey_context import NOW, event, base, implementation
from test_ice_hockey_features import full_inputs, features


def replacement(items, side="home", role="skater", *, confirmed=True):
    projection = next(item for item in items if item["kind"] == "projection")
    usage = projection["data"]["scenarios"][0]["teams"][event()[side+"_id"]]
    player = next(player for player in usage["players"] if player["role"] == role)
    before, after = player["player_id"], f"nhl:ice_hockey:player:{1999 if side == 'home' else 8999}"
    player["player_id"] = after
    for interval in usage["regulation_intervals"]:
        interval["skaters"] = [after if key == before else key for key in interval["skaters"]]
        if interval["goalie"] == before: interval["goalie"] = after
    if role == "goalie" and confirmed:
        next(item for item in items if item["kind"] == "starter")["data"]["teams"][event()[side+"_id"]]["player_id"] = after
    return before, after


def fitted_artifact(fv, *, names=None):
    mod = implementation()
    names = names or ["observed_recovery_exact_hours_home", "observed_recovery_exact_hours_away"]
    n = len(names)
    assert n == 2
    # One role-pooled fit, then exactly mirror its columns, not two fits.
    x = np.array([[((i % 7)-3)/3, ((i*3 % 11)-5)/5] for i in range(80)], dtype=float)
    for column, name in enumerate(names):
        if "_home/goalie/" in name or ("_goalie_seconds_" in name and name.endswith("_home")):
            x[:, column] = 0.  # Home-scoring equation consumes the AWAY goalie.
    target = np.array([1+(i % 4) for i in range(80)])
    head = fit_offset(x, np.log(np.full(80, 2.5)), target, link="log_rate", alpha=1.)
    mirrored = {**deepcopy(head), "coef": list(reversed(head["coef"])), "scale": list(reversed(head["scale"]))}
    return {"schema": 1, "sport": "ice_hockey", "family": mod.FAMILY, "feature_version": mod.FEATURE_VERSION,
        "feature_names": names, "heads": {"home": head, "away": mirrored}, "preprocessing_artifacts": {},
        "joint_calibration": {"kind": "identity"}, "training_end": canonical_timestamp(NOW-timedelta(days=7)),
        "training_refs_hash": digest({"synthetic_rows": x.tolist(), "targets": target.tolist()}),
        "population": {"sport": "ice_hockey", "competitions": ["nhl"], "formats": [event()["format"]],
            "tours": [None], "surfaces": [None], "indoor": [None]}, "coverage": fv["coverage"], "model_variant": mod.MODEL_VARIANT}


def inputs(role="skater", *, confirmed=True):
    original, items = full_inputs()
    before, after = replacement(items, role=role, confirmed=confirmed)
    fv = features(items, original)
    names = [f"exposure_delta_{side}/{role}/20252026/{before}" for side in ("home", "away")]
    return original, fv, fitted_artifact(fv, names=names)


def approval(artifact):
    from test_context_snapshots import approval_payload, envelope
    wrapped = {"kind": "context-effect-v1", "payload": artifact}
    payload = approval_payload(digest(wrapped))
    for name in ("sport", "family", "feature_version", "population", "coverage", "model_variant"):
        payload[name] = deepcopy(artifact[name])
    payload.update(base_versions=[implementation().BASE_VERSION], target_markets=sorted(implementation().MARKETS),
        outcome_contract="synthetic-hockey-test-only-v1", evaluated_at=canonical_timestamp(NOW-timedelta(days=1)))
    return envelope(payload, "context-approval-v1")


def result(original, fv, artifact, *, approved=False):
    wrapped = {"kind": "context-effect-v1", "payload": artifact}
    return implementation().hockey_context_result(original, fv, wrapped, event=event(), effect_hash=digest(wrapped),
        approval=approval(artifact) if approved else None)


def test_genuine_fitted_two_head_log_rates_move_one_joint_law_with_fixed_original_ot():
    original, fv, artifact = inputs()
    adjusted = implementation().apply_hockey_effect(original, fv, artifact, event=event())
    x = np.array([[fv["values"][name] for name in artifact["feature_names"]]])
    for side in ("home", "away"):
        delta = float(offset_delta(artifact["heads"][side], x)[0])
        assert adjusted["params"][side+"_lambda"] == pytest.approx(original["params"][side+"_lambda"]*math.exp(delta), rel=1e-14)
    assert adjusted["params"] != original["params"]
    assert adjusted["params"]["overtime_home_probability"] == original["params"]["overtime_home_probability"]
    assert adjusted["markets"] == implementation().hockey_distribution(*[adjusted["params"][key] for key in (
        "home_lambda", "away_lambda", "overtime_home_probability")])
    assert validate_base_distribution(adjusted) == adjusted


def test_zero_effect_retains_exact_original_parameters_markets_and_separate_ot_bytes():
    original, fv, artifact = inputs()
    for head in artifact["heads"].values(): head["coef"] = [0., 0.]
    adjusted = implementation().apply_hockey_effect(original, fv, artifact, event=event())
    assert canonical_bytes(adjusted["params"]) == canonical_bytes(original["params"])
    assert canonical_bytes(adjusted["markets"]) == canonical_bytes(original["markets"])


def test_unapproved_comparison_keeps_base_while_matching_cpu_approval_selects_valid_observed_path():
    original, fv, artifact = inputs()
    experimental, applied = result(original, fv, artifact), result(original, fv, artifact, approved=True)
    assert experimental["role"] == "experimental"
    assert experimental["comparison_params"] != original["params"]
    assert experimental["used_params"] == original["params"]
    assert applied["role"] == "applied"
    assert applied["used_params"] == applied["comparison_params"]
    assert applied["certified_markets"] == sorted(implementation().MARKETS)


def test_unconfirmed_goalie_scenario_never_becomes_central_even_with_matching_approval():
    original, fv, artifact = inputs(role="goalie", confirmed=False)
    answer = result(original, fv, artifact, approved=True)
    assert answer["role"] == "experimental"
    assert answer["comparison_params"] != original["params"]
    assert answer["used_params"] == original["params"]
    assert answer["approval_hash"] is None
    assert "hockey-conditional-goalie-scenario" in answer["limitations"]


def test_actual_confirmed_goalie_and_workload_only_paths_are_not_blanket_banned():
    original, fv, artifact = inputs(role="goalie", confirmed=True)
    assert result(original, fv, artifact, approved=True)["role"] == "applied"
    from test_ice_hockey_sources import raw
    fv = features([raw()], original, scenario_id=None)
    artifact = fitted_artifact(fv)
    answer = result(original, fv, artifact, approved=True)
    assert fv["values"]["exposure_complete_home"] == 0
    assert fv["values"]["goalie_assumed_home"] is None
    assert answer["role"] == "applied"


def test_actual_goalie_change_only_moves_the_opponents_conceding_goal_rate():
    original, fv, artifact = inputs(role="goalie")
    adjusted = implementation().apply_hockey_effect(original, fv, artifact, event=event())
    assert adjusted["params"]["home_lambda"] == original["params"]["home_lambda"]
    assert adjusted["params"]["away_lambda"] != original["params"]["away_lambda"]


@pytest.mark.parametrize("mutation", ["head-coef", "head-scale", "head-alpha", "head-rows", "names", "season", "current", "reference",
    "delta", "refs", "base-hash", "event", "comparison-reuse", "ot", "market"])
def test_effect_and_comparison_reject_binding_or_role_rewrites(mutation):
    original, fv, artifact = inputs()
    current = event()
    adjusted = implementation().apply_hockey_effect(original, fv, artifact, event=current)
    if mutation.startswith("head-"):
        name = mutation.removeprefix("head-")
        name = {"rows": "n_rows"}.get(name, name)
        if name in ("coef", "scale"): artifact["heads"]["away"][name][0] += .001
        else: artifact["heads"]["away"][name] += 1
    elif mutation == "names": artifact["feature_names"] = list(reversed(artifact["feature_names"]))[:1]
    elif mutation == "season": artifact["feature_names"] = [name.replace("20252026", "20262027") for name in artifact["feature_names"]]
    elif mutation in ("current", "reference", "delta", "refs"):
        key = artifact["feature_names"][0]
        if mutation == "refs": fv["refs"][key] = ["1"*64]
        else: fv["values"][key.replace("delta", mutation)] += .1
    elif mutation == "base-hash": fv["reference_hash"] = "1"*64
    elif mutation == "event": current["schedule_revision"] = "moved"
    elif mutation == "comparison-reuse": original = adjusted
    elif mutation == "ot": adjusted["params"]["overtime_home_probability"] = .5
    else: adjusted["markets"]["home_reg"] += .001
    with pytest.raises(ContextContractError):
        if mutation in ("ot", "market"): validate_base_distribution(adjusted)
        else: implementation().apply_hockey_effect(original, fv, artifact, event=current)


@pytest.mark.parametrize("mutation", ["missing", "future-fit", "coverage", "population", "preprocessing", "overflow"])
def test_ineligible_or_numeric_comparison_retains_the_available_original(mutation):
    original, fv, artifact = inputs()
    if mutation == "missing":
        fv["states"][artifact["feature_names"][0]] = "missing"
        fv["values"][artifact["feature_names"][0]] = None
    elif mutation == "future-fit": artifact["training_end"] = canonical_timestamp(NOW+timedelta(microseconds=1))
    elif mutation == "coverage": artifact["coverage"] = {**artifact["coverage"], "case": "other"}
    elif mutation == "population": artifact["population"]["formats"] = ["nhl_reg60_playoff_ot"]
    elif mutation == "preprocessing": artifact["model_variant"] = "unimplemented-variant"
    else:
        artifact["heads"]["home"]["coef"] = [1e308, 1e308]
        artifact["heads"]["away"]["coef"] = [1e308, 1e308]
    answer = result(original, fv, artifact)
    assert answer["role"] == "not_applied"
    assert answer["used_params"] == original["params"]
    assert answer["used_markets"] == original["markets"]


def test_corrupt_approval_is_rejected_before_conditional_fallback():
    original, fv, artifact = inputs(role="goalie", confirmed=False)
    wrapped = {"kind": "context-effect-v1", "payload": artifact}
    corrupt = approval(artifact)
    corrupt["payload"]["effect_hash"] = "f"*64
    with pytest.raises(ContextContractError):
        implementation().hockey_context_result(original, fv, wrapped, event=event(), effect_hash=digest(wrapped), approval=corrupt)


def test_goaltender_head_is_conceding_role_not_an_own_attack_coefficient():
    original, fv, artifact = inputs(role="goalie")
    artifact["heads"]["home"]["coef"][0] = .1
    artifact["heads"]["away"]["coef"][1] = .1  # Mirrored but wrong hockey role.
    with pytest.raises(ContextContractError):
        implementation().apply_hockey_effect(original, fv, artifact, event=event())


def test_skater_only_from_hypothetical_whole_lineup_is_still_conditional_but_observed_load_is_not():
    original, items = full_inputs()
    before, _ = replacement(items, role="skater")
    starter = next(item for item in items if item["kind"] == "starter")
    starter["data"]["teams"][event()["home_id"]]["status"] = "unconfirmed"
    from test_ice_hockey_sources import raw
    items.append(raw())
    fv = features(items, original)
    scenario_effect = fitted_artifact(fv, names=[f"exposure_delta_{side}/skater/20252026/{before}" for side in ("home", "away")])
    observed_effect = fitted_artifact(fv)
    scenario = result(original, fv, scenario_effect, approved=True)
    observed = result(original, fv, observed_effect, approved=True)
    assert scenario["role"] == "experimental"
    assert scenario["used_params"] == original["params"]
    assert scenario["comparison_params"] != original["params"]
    assert observed["role"] == "applied"
    assert "hockey-conditional-goalie-scenario" not in observed["limitations"]
    for artifact in (scenario_effect, observed_effect):
        unapproved = result(original, fv, artifact)
        assert unapproved["role"] == "experimental"
        assert unapproved["used_params"] == original["params"]


def test_independent_confirmed_skater_subset_cannot_be_invented_in_whole_scenario_transport():
    from test_ice_hockey_sources import raw, normalized
    declaration = raw("projection")
    declaration["data"]["scenarios"][0]["independently_confirmed_skaters"] = True
    with pytest.raises(ContextContractError): normalized(declaration)
