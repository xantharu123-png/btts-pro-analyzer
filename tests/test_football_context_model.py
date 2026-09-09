"""B5 mathematical mechanics on synthetic fixtures, never empirical approval."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import math

import numpy as np
import pytest

import challenge_engine as engine
from context_models.contracts import ContextContractError, canonical_timestamp, digest, validate_base_distribution, validate_effect_artifact, validate_event
from context_models.offset import fit_offset
from test_context_contracts import football_reference_base


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
GOAL_KINDS = {"result", "double_chance", "btts", "total", "team_total", "team_range", "result_total", "mixed_or"}
FEATURE_NAMES = ["availability", "workload", "availability_workload"]


def event(**changes):
    return {"event_key": "api-football:football:1", "sport": "football", "competition": "39",
            "format": "90min", "home_id": "api-football:team:1", "away_id": "api-football:team:2",
            "scheduled_start": (NOW + timedelta(hours=6)).isoformat(), "schedule_revision": "s1",
            "status": "scheduled", **changes}


def reference_hash(base, *, event_value=None, preprocessing=()):
    return digest({"version": "football-context-reference-v2", "base_hash": digest(validate_base_distribution(base)),
                   "event_hash": digest(validate_event(event() if event_value is None else event_value)),
                   "preprocessing": sorted(set(preprocessing))})


def inputs(*, rates=(2., 1.), values=(1., .5, .5), home_coef=(-.3, -.1, -.2), away_coef=(.1, 0., 0.)):
    matrix = engine.score_matrix(*rates)
    base = football_reference_base()
    base.update(cutoff=NOW.isoformat(), params=dict(zip(("home_lambda", "away_lambda"), rates)),
                markets={spec.key: engine.market_probability(matrix, spec) if spec.kind in GOAL_KINDS else .37
                         for spec in engine.MARKET_SPECS})
    base = validate_base_distribution(base)
    coverage = {"version": "football-roster-v1", "case": "reported_players"}
    features = {"version": "football-roster-components-v2", "event_key": base["event_key"], "cutoff": base["cutoff"],
                "values": dict(zip(FEATURE_NAMES, values)), "states": {name: "available" for name in FEATURE_NAMES},
                "refs": {name: [str(index + 4) * 64] for index, name in enumerate(FEATURE_NAMES)},
                "coverage": coverage, "reference_hash": reference_hash(base)}
    artifact = {"schema": 1, "sport": "football", "family": "football:goals:90min",
                "feature_version": features["version"], "feature_names": list(FEATURE_NAMES),
                "heads": {side: {"link": "log_rate", "scale": [1., 1., 1.], "coef": list(coef), "alpha": .1, "n_rows": 200}
                          for side, coef in (("home", home_coef), ("away", away_coef))},
                "preprocessing_artifacts": {}, "joint_calibration": {"kind": "identity"},
                "training_end": (NOW - timedelta(days=1)).isoformat(), "training_refs_hash": "a" * 64,
                "population": {"sport": "football", "competitions": ["39"], "formats": ["90min"],
                               "tours": [None], "surfaces": [None], "indoor": [None]},
                "coverage": deepcopy(coverage), "model_variant": "synthetic-football-roster-v1"}
    return base, features, validate_effect_artifact(artifact)


def implementation():
    # Import inside the test: the integration RED must fail on the absent B5
    # function, not be accidentally satisfied by the already working B2 fit.
    return importlib.import_module("context_models.football_effect")


def test_fitted_absence_changes_one_goal_distribution_and_preserves_other_markets():
    module = implementation()
    base, features, artifact = inputs(values=(1., 0., 0.), away_coef=(0., 0., 0.))
    x = np.array([[0., 0., 0.], [1., 0., 0.]] * 100)
    artifact["heads"]["home"] = fit_offset(x, np.full(200, np.log(2.)), np.array([2., 1.] * 100), link="log_rate", alpha=.1)
    frozen = deepcopy((base, features, artifact))
    result = module.apply_football_effect(base, features, artifact, event=event())
    assert 0 < result["params"]["home_lambda"] < 2.
    assert result["params"]["away_lambda"] == 1.
    assert result["markets"]["HOME_OVER_0_5"] < base["markets"]["HOME_OVER_0_5"]
    assert result["markets"]["CORNERS_OVER_5_5"] == base["markets"]["CORNERS_OVER_5_5"]
    assert result["markets"]["YELLOW_OVER_1_5"] == base["markets"]["YELLOW_OVER_1_5"]
    assert result["family"] == base["family"]
    assert result["model_hash"] != base["model_hash"]
    assert result["history_refs"] == base["history_refs"] and result["reference_weights"] == base["reference_weights"]
    assert set(result["markets"]) == set(base["markets"])
    assert validate_base_distribution(result) == result
    assert (base, features, artifact) == frozen


def test_existing_b2_numerical_fit_alone_is_not_b5_completion():
    fit = fit_offset(np.array([[0.], [1.]] * 100), np.full(200, np.log(2.)), np.array([2., 1.] * 100), link="log_rate", alpha=.1)
    assert fit["coef"][0] < 0


def test_all_goal_contracts_use_exactly_one_authoritative_matrix(monkeypatch):
    module = implementation()
    base, features, artifact = inputs()
    original_matrix, original_probability = engine.score_matrix, engine.market_probability
    matrices, contracts = [], []
    def counted_matrix(*args, **kwargs):
        result = original_matrix(*args, **kwargs)
        matrices.append(result)
        return result
    def counted_probability(matrix, spec):
        assert matrix is matrices[0]
        contracts.append(spec)
        return original_probability(matrix, spec)
    monkeypatch.setattr(engine, "score_matrix", counted_matrix)
    monkeypatch.setattr(engine, "market_probability", counted_probability)
    result = module.apply_football_effect(base, features, artifact, event=event())
    assert len(matrices) == 1
    assert {spec.key for spec in contracts} == {spec.key for spec in engine.MARKET_SPECS if spec.kind in GOAL_KINDS}
    assert len(contracts) == len({spec.key for spec in contracts})
    assert {spec.kind for spec in contracts} == GOAL_KINDS
    for spec in engine.MARKET_SPECS:
        if spec.kind in GOAL_KINDS:
            assert result["markets"][spec.key] == original_probability(matrices[0], spec)
        else:
            assert result["markets"][spec.key] == base["markets"][spec.key]


@pytest.mark.parametrize("rates", [(1e-100, 1e-100), (1e-10, 8.), (8., 1e-10), (.1, .1), (2., 1.), (8., 8.)])
def test_goal_properties_at_valid_rate_boundaries(rates):
    base, features, artifact = inputs(rates=rates, values=(0., 0., 0.))
    result = implementation().apply_football_effect(base, features, artifact, event=event())
    markets = result["markets"]
    assert result["params"] == base["params"]  # No rounding of exact zero deltas.
    assert sum(markets[name] for name in ("RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY")) == pytest.approx(1, abs=1e-12)
    assert markets["BTTS_YES"] + markets["BTTS_NO"] == pytest.approx(1, abs=1e-12)
    assert markets["DC_1X"] == pytest.approx(1 - markets["RESULT_AWAY"], abs=1e-12)
    for prefix, lines in (("TOTAL", (.5, 1.5, 2.5, 3.5, 4.5)), ("HOME", (.5, 1.5, 2.5)), ("AWAY", (.5, 1.5, 2.5))):
        overs = []
        for line in lines:
            token = str(line).replace(".", "_")
            over, under = markets[f"{prefix}_OVER_{token}"], markets[f"{prefix}_UNDER_{token}"]
            assert over + under == pytest.approx(1, abs=1e-12)
            overs.append(over)
        assert overs == sorted(overs, reverse=True)
    assert markets["RESULT_TOTAL_1X_UNDER_3_5"] <= markets["DC_1X"] + 1e-12
    assert markets["RESULT_TOTAL_1X_UNDER_3_5"] <= markets["TOTAL_UNDER_3_5"] + 1e-12
    assert markets["MIXED_BTTS_OR_OVER_2_5"] + 1e-12 >= max(markets["BTTS_YES"], markets["TOTAL_OVER_2_5"])
    assert all(math.isfinite(p) and 0 <= p <= 1 for p in markets.values())


def test_side_swap_swaps_rates_and_winner_contracts_without_inventing_home_advantage():
    base, features, artifact = inputs()
    first = implementation().apply_football_effect(base, features, artifact, event=event())
    swapped_base, swapped_features, swapped_artifact = inputs(rates=(1., 2.), home_coef=(.1, 0., 0.), away_coef=(-.3, -.1, -.2))
    # Existing home advantage is part of the original rates; this layer adds none.
    second = implementation().apply_football_effect(swapped_base, swapped_features, swapped_artifact, event=event())
    assert second["params"]["home_lambda"] == first["params"]["away_lambda"]
    assert second["params"]["away_lambda"] == first["params"]["home_lambda"]
    assert second["markets"]["RESULT_HOME"] == pytest.approx(first["markets"]["RESULT_AWAY"], abs=1e-12)
    assert second["markets"]["RESULT_DRAW"] == pytest.approx(first["markets"]["RESULT_DRAW"], abs=1e-12)
    assert second["markets"]["HOME_OVER_1_5"] == pytest.approx(first["markets"]["AWAY_OVER_1_5"], abs=1e-12)


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), "2", None, 0., -1.])
def test_invalid_original_rates_never_coerce_or_clip(bad):
    base, features, artifact = inputs()
    base["params"]["home_lambda"] = bad
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())


@pytest.mark.parametrize("delta", [3., 1000., -1000.])
def test_unrepresentable_or_unsupported_adjusted_rate_does_not_return_partial_markets(delta):
    base, features, artifact = inputs(values=(1., 0., 0.), home_coef=(delta, 0., 0.))
    before = deepcopy((base, features, artifact))
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())
    assert (base, features, artifact) == before


@pytest.mark.parametrize("key", ["RESULT_HOEM", "HT_HOME", "FIRST_HALF_OVER_0_5", "other-provider:result_home"])
def test_unknown_market_identity_fails_whole_comparison_instead_of_guessing_family(key):
    base, features, artifact = inputs()
    base["markets"][key] = .5
    features["reference_hash"] = reference_hash(base)
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())


def test_dictionary_iteration_order_does_not_reorder_artifact_features():
    base, features, artifact = inputs()
    first = implementation().apply_football_effect(base, features, artifact, event=event())
    for key in ("values", "states", "refs"):
        features[key] = dict(reversed(list(features[key].items())))
    second = implementation().apply_football_effect(base, features, artifact, event=event())
    assert second == first


@pytest.mark.parametrize("state", ["missing", "stale", "conflicting", "not_applicable"])
def test_every_consumed_feature_requires_available_actual_evidence(state):
    base, features, artifact = inputs()
    features["states"]["availability"] = state
    features["values"]["availability"] = None
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())


@pytest.mark.parametrize("bad", [True, float("nan"), "1", None])
def test_invalid_feature_values_never_coerce(bad):
    base, features, artifact = inputs()
    features["values"]["availability"] = bad
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())


@pytest.mark.parametrize("change", [
    {"event_key": "api-football:football:2"}, {"competition": "61"}, {"format": "45min"},
    {"status": "started"}, {"status": "cancelled"}, {"scheduled_start": NOW.isoformat()},
    {"home_id": "api-football:team:2", "away_id": "api-football:team:1"},
])
def test_explicit_event_scope_and_original_team_orientation_are_required(change):
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(*inputs(), event=event(**change))


@pytest.mark.parametrize("change", [
    {"scheduled_start": (NOW + timedelta(hours=7)).isoformat()},
    {"scheduled_start": (NOW + timedelta(hours=5)).isoformat()},
    {"schedule_revision": "s2"}, {"home_id": "api-football:team:99"},
    {"away_id": "api-football:team:99"}, {"competition": "61"},
    {"format": "45min"}, {"status": "started"}, {"status": "cancelled"},
    {"event_key": "api-football:football:2"},
])
def test_changed_event_cannot_reuse_unchanged_feature_reference(change):
    base, features, artifact = inputs()
    # Remove independent orientation/population blockers where that is a valid
    # contract, so this exercises binding of the complete original event.
    for head in base["reference_weights"]["heads"].values():
        for component in head["components"].values():
            component.update(team_id=None, team_join="unresolved")
    artifact["population"]["competitions"] = ["39", "61"]
    features["reference_hash"] = reference_hash(base)
    frozen = deepcopy((base, features, artifact))
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event(**change))
    assert (base, features, artifact) == frozen


def test_legacy_unversioned_base_only_reference_is_not_a_current_event_binding():
    base, features, artifact = inputs()
    features["reference_hash"] = digest({"base_hash": digest(base), "preprocessing": []})
    with pytest.raises(ContextContractError, match="reference"):
        implementation().apply_football_effect(base, features, artifact, event=event())


@pytest.mark.parametrize("version", ["football-roster-components-v1", "football-roster-components-v3", "other-context-v2"])
def test_effect_matching_another_feature_version_does_not_define_the_b4_v2_variant(version):
    base, features, artifact = inputs()
    features["version"] = artifact["feature_version"] = version
    with pytest.raises(ContextContractError, match="feature"):
        implementation().apply_football_effect(base, features, artifact, event=event())


def test_changed_schedule_requires_a_new_v2_feature_reference_for_every_comparison():
    base, features, artifact = inputs()
    original = implementation().apply_football_effect(base, features, artifact, event=event())
    changed_event = event(schedule_revision="s2", scheduled_start=(NOW + timedelta(hours=7)).isoformat())
    groups = {"all": list(FEATURE_NAMES)}
    with pytest.raises(ContextContractError, match="reference"):
        implementation().football_factor_comparisons(base, features, artifact, event=changed_event, groups=groups)
    changed_features = deepcopy(features)
    changed_features["reference_hash"] = reference_hash(base, event_value=changed_event)
    # A synthetic fresh-v2 transport, not a source feature recomputation proof.
    updated = implementation().apply_football_effect(base, changed_features, artifact, event=changed_event)
    assert updated["params"] == original["params"]
    assert updated["model_hash"] != original["model_hash"]
    assert implementation().football_factor_comparisons(
        base, changed_features, artifact, event=changed_event, groups=groups)["full"] == updated
    assert changed_features["reference_hash"] != features["reference_hash"]


def test_same_event_in_another_timezone_has_the_same_canonical_v2_reference():
    base, features, artifact = inputs()
    same_event = event(scheduled_start="2026-09-09T20:00:00+02:00")
    assert reference_hash(base, event_value=same_event) == features["reference_hash"]
    assert implementation().apply_football_effect(base, features, artifact, event=same_event) == (
        implementation().apply_football_effect(base, features, artifact, event=event()))


@pytest.mark.parametrize("side", ["home", "away"])
@pytest.mark.parametrize("foreign", ["api-football:team:99", "swapped"])
def test_known_target_team_remains_binding_with_unresolved_historical_join(side, foreign):
    base, features, artifact = inputs()
    original_team = event()[side + "_id"]
    other_team = event()["away_id" if side == "home" else "home_id"]
    for head in base["reference_weights"]["heads"].values():
        for component in head["components"].values():
            component["team_join"] = "unresolved"
    changed = {side + "_id": foreign if foreign != "swapped" else other_team}
    if foreign == "swapped":
        changed["away_id" if side == "home" else "home_id"] = original_team
    # Deliberately bind the new event correctly: known baseline team identity
    # must still reject it independently of the earlier reference check.
    features["reference_hash"] = reference_hash(base, event_value=event(**changed))
    original = deepcopy((base, features, artifact))
    with pytest.raises(ContextContractError, match="orientation"):
        implementation().apply_football_effect(base, features, artifact, event=event(**changed))
    assert (base, features, artifact) == original


@pytest.mark.parametrize("known", [True, False])
def test_unresolved_history_is_not_itself_an_additional_team_identity_gate(known):
    base, features, artifact = inputs()
    for head in base["reference_weights"]["heads"].values():
        for component in head["components"].values():
            component["team_join"] = "unresolved"
            if not known:
                component["team_id"] = None
    features["reference_hash"] = reference_hash(base)
    # Synthetic available features exercise only this identity guard. This is
    # not proof that unknown historical joins support real B4 roster features.
    assert implementation().apply_football_effect(base, features, artifact, event=event())["params"]


@pytest.mark.parametrize("field,values", [
    ("coef", [2 ** 53 + 1, -(2 ** 53), 0.]),
    ("scale", [2 ** 53 + 1, 1., 1.]),
])
def test_fitted_json_integer_heads_cannot_round_before_b5_prediction(field, values):
    base, features, artifact = inputs(values=(1., 1., 0.), home_coef=(.1, 0., 0.))
    artifact["heads"]["home"][field] = values
    frozen = deepcopy((base, features, artifact))
    with pytest.raises(ContextContractError, match="represent"):
        implementation().apply_football_effect(base, features, artifact, event=event())
    assert (base, features, artifact) == frozen


@pytest.mark.parametrize("part,key,value", [
    ("features", "event_key", "api-football:football:2"),
    ("features", "cutoff", (NOW - timedelta(seconds=1)).isoformat()),
    ("features", "version", "other-features-v1"),
    ("features", "reference_hash", "f" * 64),
    ("artifact", "coverage", {"version": "football-roster-v1", "case": "other"}),
    ("artifact", "training_end", canonical_timestamp(NOW + timedelta(seconds=1))),
    ("artifact", "feature_names", ["workload", "availability"]),
    ("artifact", "joint_calibration", {"kind": "legacy-isotonic"}),
    ("artifact", "schema", True),
])
def test_feature_artifact_identity_guards(part, key, value):
    base, features, artifact = inputs()
    (features if part == "features" else artifact)[key] = value
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())


def test_reference_and_preprocessing_identity_cannot_be_changed_or_counted_twice():
    base, features, artifact = inputs()
    artifact["preprocessing_artifacts"] = {"participation": "d" * 64, "same_participation": "d" * 64}
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())
    features["reference_hash"] = reference_hash(base, preprocessing=["d" * 64])
    result = implementation().apply_football_effect(base, features, artifact, event=event())
    assert result["model_hash"] != base["model_hash"]


def test_missing_numeric_refs_and_consumed_feature_are_rejected():
    base, features, artifact = inputs()
    features["refs"]["availability"] = []
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())
    for key in ("values", "states", "refs"):
        features[key].pop("availability")
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())


def test_counterfactuals_are_separate_original_base_contrasts_with_bound_overlapping_groups():
    module = implementation()
    base, features, artifact = inputs()
    groups = {"availability": ["availability", "availability_workload"], "workload": ["workload", "availability_workload"]}
    original = deepcopy((base, features, artifact, groups))
    result = module.football_factor_comparisons(base, features, artifact, event=event(), groups=groups)
    assert result["kind"] == "model_counterfactual" and result["additive"] is False
    assert result["base_hash"] == digest(base)
    assert result["feature_hash"] == digest(features)
    assert result["effect_hash"] == digest({"kind": "context-effect-v1", "payload": artifact})
    assert result["full"] == module.apply_football_effect(base, features, artifact, event=event())
    for name, names in groups.items():
        modified = deepcopy(features)
        modified["values"].update({feature: 0. for feature in names})
        expected = module.apply_football_effect(base, modified, artifact, event=event())
        comparison = result["groups"][name]
        assert comparison["comparison"] == expected
        assert comparison["feature_names"] == names
        assert comparison["counterfactual_feature_hash"] == digest(modified)
        assert comparison["delta_pp_vs_full"]["RESULT_HOME"] == pytest.approx(100 * (expected["markets"]["RESULT_HOME"] - result["full"]["markets"]["RESULT_HOME"]))
    all_zero = deepcopy(features)
    all_zero["values"] = dict.fromkeys(FEATURE_NAMES, 0.)
    zero_result = module.apply_football_effect(base, all_zero, artifact, event=event())
    summed = sum(contrast["delta_pp_vs_full"]["RESULT_HOME"] for contrast in result["groups"].values())
    total = 100 * (zero_result["markets"]["RESULT_HOME"] - result["full"]["markets"]["RESULT_HOME"])
    assert summed != pytest.approx(total, abs=1e-6)
    assert (base, features, artifact, groups) == original


@pytest.mark.parametrize("groups", [
    {}, {"only": ["availability"]}, {"all": FEATURE_NAMES + ["unknown"]},
    {"all": FEATURE_NAMES + ["availability"]}, {"all": list(reversed(FEATURE_NAMES))},
    {"all": tuple(FEATURE_NAMES)}, {"": FEATURE_NAMES}, {"all": FEATURE_NAMES, "empty": []},
])
def test_invalid_factor_group_contract_is_not_inferred_or_silently_repaired(groups):
    with pytest.raises(ContextContractError):
        implementation().football_factor_comparisons(*inputs(), event=event(), groups=groups)


def test_named_head_scales_and_feature_order_are_used_without_extra_home_factor():
    base, features, artifact = inputs(values=(.6, 1.2, -.3), home_coef=(.4, -.2, .3), away_coef=(-.1, .1, -.2))
    artifact["heads"]["home"]["scale"] = [2., 3., 4.]
    artifact["heads"]["away"]["scale"] = [3., 4., 5.]
    result = implementation().apply_football_effect(base, features, artifact, event=event())
    assert result["params"]["home_lambda"] == pytest.approx(2 * math.exp(.6 / 2 * .4 + 1.2 / 3 * -.2 + -.3 / 4 * .3))
    assert result["params"]["away_lambda"] == pytest.approx(math.exp(.6 / 3 * -.1 + 1.2 / 4 * .1 + -.3 / 5 * -.2))


@pytest.mark.parametrize("field,value", [("coef", [True, 0., 0.]), ("coef", [float("nan"), 0., 0.]),
                                         ("scale", [0., 1., 1.]), ("coef", [0.]), ("link", "logit")])
def test_each_head_keeps_closed_b2_numeric_and_family_guards(field, value):
    base, features, artifact = inputs()
    artifact["heads"]["away"][field] = value
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())


def test_future_training_guard_is_reached_for_an_otherwise_canonical_artifact():
    base, features, artifact = inputs()
    artifact["training_end"] = canonical_timestamp(NOW + timedelta(microseconds=1))
    with pytest.raises(ContextContractError, match="training"):
        implementation().apply_football_effect(base, features, artifact, event=event())
    artifact["training_end"] = canonical_timestamp(NOW)
    assert implementation().apply_football_effect(base, features, artifact, event=event())


def test_only_goal_subset_can_change_and_an_all_foreign_family_cannot_be_mislabelled():
    base, features, artifact = inputs()
    base["markets"] = {"RESULT_HOME": base["markets"]["RESULT_HOME"], "CORNERS_OVER_5_5": .12, "YELLOW_OVER_1_5": .8}
    features["reference_hash"] = reference_hash(base)
    result = implementation().apply_football_effect(base, features, artifact, event=event())
    assert result["markets"]["CORNERS_OVER_5_5"] == .12 and result["markets"]["YELLOW_OVER_1_5"] == .8
    base["markets"].pop("RESULT_HOME")
    features["reference_hash"] = reference_hash(base)
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(base, features, artifact, event=event())


def test_valid_wrong_tennis_family_is_rejected_not_disguised_as_football():
    from test_context_snapshots import family_arguments
    args = family_arguments("tennis:winner")
    with pytest.raises(ContextContractError):
        implementation().apply_football_effect(args["base"], args["features"], args["effect_artifact"]["payload"], event=args["event"])


def test_partial_matrix_failure_cannot_mutate_or_return_updated_market_subset(monkeypatch):
    base, features, artifact = inputs()
    frozen = deepcopy((base, features, artifact))
    monkeypatch.setattr(engine, "score_matrix", lambda *_: {(0, 0): .4, (1, 0): .5})
    with pytest.raises(ContextContractError, match="mass"):
        implementation().apply_football_effect(base, features, artifact, event=event())
    assert (base, features, artifact) == frozen


def test_a1_effect_identity_b3_experimental_boundary_and_no_other_market_certification(tmp_path):
    from context_snapshots import select_context_result
    from model_artifacts import put_artifact, load_artifact
    base, features, artifact = inputs()
    path = tmp_path / "b5-artifacts.db"
    effect_hash = put_artifact(path, kind="context-effect-v1", payload=artifact, created_at=NOW - timedelta(hours=1))
    assert effect_hash == digest({"kind": "context-effect-v1", "payload": artifact})
    envelope = load_artifact(path, effect_hash)
    comparison = implementation().apply_football_effect(base, features, envelope["payload"], event=event())
    result = select_context_result(base, comparison, event=event(), features=features, effect_artifact=envelope,
        effect_hash=effect_hash, approval=None, factor_roles=dict.fromkeys(FEATURE_NAMES, "experimental"),
        factor_states=features["states"], limitations=["synthetic-mechanics-only"])
    assert result["role"] == "experimental" and result["effect_hash"] == effect_hash
    assert result["used_params"] == base["params"] and result["used_markets"] == base["markets"]
    assert result["comparison_markets"] == comparison["markets"]
    assert result["approval_hash"] is None and result["certified_markets"] == []


def test_returned_comparison_is_detached_and_cannot_be_used_as_the_original_again():
    base, features, artifact = inputs()
    comparison = implementation().apply_football_effect(base, features, artifact, event=event())
    repeated_features = deepcopy(features)
    repeated_features["reference_hash"] = reference_hash(comparison)
    with pytest.raises(ContextContractError, match="original"):
        implementation().apply_football_effect(comparison, repeated_features, artifact, event=event())
    comparison["history_refs"][0]["roster_join"] = "unresolved"
    assert base["history_refs"][0]["roster_join"] == "verified_native"


def test_model_identity_binds_base_feature_evidence_and_every_head_even_at_zero_change():
    base, features, artifact = inputs(values=(0., 0., 0.))
    first = implementation().apply_football_effect(base, features, artifact, event=event())
    features["refs"]["availability"] = ["e" * 64]
    second = implementation().apply_football_effect(base, features, artifact, event=event())
    assert second["params"] == first["params"] and second["model_hash"] != first["model_hash"]
    artifact["heads"]["away"]["coef"][0] = .2
    third = implementation().apply_football_effect(base, features, artifact, event=event())
    assert third["params"] == second["params"] and third["model_hash"] != second["model_hash"]


def test_groups_identity_is_order_independent_but_binds_the_explicit_membership():
    base, features, artifact = inputs()
    first = {"medical": ["availability", "availability_workload"], "load": ["workload", "availability_workload"]}
    result = implementation().football_factor_comparisons(base, features, artifact, event=event(), groups=first)
    reordered = implementation().football_factor_comparisons(base, features, artifact, event=event(), groups=dict(reversed(list(first.items()))))
    assert result == reordered
    second = {"medical": ["availability"], "load": ["workload", "availability_workload"]}
    changed = implementation().football_factor_comparisons(base, features, artifact, event=event(), groups=second)
    assert changed["full"] == result["full"] and changed["groups_hash"] != result["groups_hash"]


def test_unconsumed_missing_context_does_not_invent_a_consumed_value():
    base, features, artifact = inputs()
    original = implementation().apply_football_effect(base, features, artifact, event=event())
    features["values"]["unused_weather"] = None
    features["states"]["unused_weather"] = "missing"
    features["refs"]["unused_weather"] = []
    result = implementation().apply_football_effect(base, features, artifact, event=event())
    assert result["params"] == original["params"] and result["markets"] == original["markets"]


def test_legacy_independent_market_curve_is_not_reapplied_to_zero_delta_rates():
    base, features, artifact = inputs(values=(0., 0., 0.))
    base["markets"]["BTTS_YES"] = .99  # Explicitly synthetic legacy inconsistency.
    features["reference_hash"] = reference_hash(base)
    result = implementation().apply_football_effect(base, features, artifact, event=event())
    expected = engine.market_probability(engine.score_matrix(2., 1.), engine.MARKET_BY_KEY["BTTS_YES"])
    assert result["params"] == base["params"]
    assert result["markets"]["BTTS_YES"] == expected != .99


def test_integer_feature_cannot_lose_precision_before_entering_b2():
    base, features, artifact = inputs(home_coef=(0., 0., 0.), away_coef=(0., 0., 0.))
    features["values"]["availability"] = 2 ** 53 + 1
    with pytest.raises(ContextContractError, match="represent"):
        implementation().apply_football_effect(base, features, artifact, event=event())


@pytest.mark.parametrize("seed", range(8))
def test_synthetic_rate_feature_grid_keeps_goal_lattice_properties(seed):
    random = np.random.default_rng(seed)
    rates = tuple(random.uniform(.2, 2., 2))
    values = tuple(random.uniform(-1., 1., 3))
    coefficients = random.uniform(-.2, .2, (2, 3))
    # These are test mechanics, not an estimate of real player coefficients.
    base, features, artifact = inputs(rates=tuple(map(float, rates)), values=tuple(map(float, values)),
        home_coef=tuple(map(float, coefficients[0])), away_coef=tuple(map(float, coefficients[1])))
    result = implementation().apply_football_effect(base, features, artifact, event=event())
    markets = result["markets"]
    assert markets["RESULT_HOME"] + markets["RESULT_DRAW"] + markets["RESULT_AWAY"] == pytest.approx(1, abs=1e-12)
    assert markets["BTTS_YES"] + markets["BTTS_NO"] == pytest.approx(1, abs=1e-12)
    assert markets["TOTAL_OVER_0_5"] >= markets["TOTAL_OVER_1_5"] >= markets["TOTAL_OVER_2_5"] >= markets["TOTAL_OVER_3_5"]
    assert all(math.isfinite(p) and 0 <= p <= 1 for p in markets.values())
