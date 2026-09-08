from copy import deepcopy

import pytest

from context_models.contracts import (
    ContextContractError, normalize_population, validate_population, validate_event,
    validate_feature_vector, validate_base_distribution, validate_effect_artifact,
    validate_context_result, validate_training_row, event_in_population,
)


TIME = "2026-09-07T12:00:00.000000Z"
HASH = "a" * 64
REF = "b" * 64


def population():
    return {"sport": "tennis", "competitions": ["atp:us-open"], "formats": ["best_of_5"],
            "tours": ["ATP"], "surfaces": ["Hard"], "indoor": [False]}


def event():
    return {"event_key": "espn:tennis:1", "sport": "tennis", "competition": "atp:us-open",
            "format": "best_of_5", "home_id": "espn:player:1", "away_id": "espn:player:2",
            "scheduled_start": "2026-09-07T18:00:00.000000Z", "schedule_revision": "s1",
            "status": "scheduled", "tour": "ATP", "surface": "Hard", "indoor": False}


def features():
    return {"version": "tennis-load-v1", "event_key": "espn:tennis:1", "cutoff": TIME,
            "values": {"load_difference": None}, "states": {"load_difference": "missing"},
            "refs": {"load_difference": []}, "coverage": {"version": "load-v1", "case": "unknown-duration"},
            "reference_hash": HASH}


def base():
    return {"version": "tennis-winner-v1", "model_hash": HASH, "event_key": "espn:tennis:1",
            "cutoff": TIME, "family": "tennis:winner", "params": {"p_a": .6},
            "markets": {"winner_a": .6, "winner_b": .4}, "history_refs": [],
            "reference_weights": {"schema": 1, "kind": "unavailable", "reason": "legacy-reference-unavailable"}}


def effect():
    return {"schema": 1, "sport": "tennis", "family": "tennis:winner", "feature_version": "tennis-load-v1",
            "feature_names": ["load_difference"],
            "heads": {"winner": {"link": "logit", "scale": [1.0], "coef": [.2], "alpha": .1, "n_rows": 100}},
            "preprocessing_artifacts": {}, "joint_calibration": {"kind": "identity"},
            "training_end": TIME, "training_refs_hash": REF, "population": population(),
            "coverage": {"version": "load-v1", "case": "complete"}, "model_variant": "load-difference-v1"}


def test_closed_contracts_roundtrip_without_promoting_missingness():
    assert validate_event(event()) == event()
    assert validate_feature_vector(features()) == features()
    assert validate_base_distribution(base()) == base()
    assert validate_effect_artifact(effect()) == effect()
    assert features()["values"]["load_difference"] is None


def test_population_has_canonical_explicit_tested_sets():
    value = population()
    value["competitions"] = ["atp:us-open", "atp:other", "atp:us-open"]
    with pytest.raises(ContextContractError):
        validate_population(value)
    normalized = normalize_population(value)
    assert normalized["competitions"] == ["atp:other", "atp:us-open"]
    assert validate_population(normalized) == normalized


@pytest.mark.parametrize("name,value", [("competitions", []), ("formats", ["*"]), ("competitions", [None]),
                                        ("indoor", [0]), ("tours", ["ATP", "ATP"]), ("tours", ["WTA", "ATP"])])
def test_population_rejects_wildcard_empty_noncanonical_and_wrong_real_types(name, value):
    row = population()
    row[name] = value
    with pytest.raises(ContextContractError):
        validate_population(row)


def test_scope_membership_requires_actual_explicit_tour_surface_and_indoor():
    assert event_in_population(event(), population())
    changed = event()
    changed["surface"] = None
    assert not event_in_population(changed, population())
    unknown = population()
    unknown["surfaces"] = [None]
    assert event_in_population(changed, unknown)
    changed["competition"] = "atp:unseen"
    assert not event_in_population(changed, unknown)


@pytest.mark.parametrize("sport", ["football", "tennis", "basketball", "ice_hockey", "esports"])
def test_event_namespaces_follow_actual_existing_five_sport_keys(sport):
    value = event()
    value["sport"] = sport
    value["event_key"] = f"test-native:{sport}:1"
    if sport != "tennis":
        for key in ("tour", "surface", "indoor"):
            value.pop(key)
    assert validate_event(value)["sport"] == sport


@pytest.mark.parametrize("factory,validator", [(event, validate_event), (features, validate_feature_vector),
                                              (base, validate_base_distribution), (effect, validate_effect_artifact)])
@pytest.mark.parametrize("field", ["odds", "approved", "surprise_key"])
def test_all_public_contracts_reject_unknown_top_level_fields(factory, validator, field):
    value = factory()
    value[field] = True
    with pytest.raises(ContextContractError):
        validator(value)


@pytest.mark.parametrize("changes", [{"home_id": "Same Name"}, {"away_id": "espn:player:1"}, {"tour": "all"},
                                    {"indoor": 1}, {"scheduled_start": "2026-09-07T18:00:00"},
                                    {"scheduled_start": 1788825600}, {"event_key": "espn:football:1"}])
def test_event_requires_native_distinct_identity_and_actual_aware_metadata(changes):
    with pytest.raises(ContextContractError):
        validate_event({**event(), **changes})


def test_feature_contract_never_promotes_unknown_to_numeric_zero_or_missing_refs():
    value = features()
    value["values"]["load_difference"] = 0
    with pytest.raises(ContextContractError):
        validate_feature_vector(value)
    value["states"]["load_difference"] = "available"
    assert validate_feature_vector(value)["values"]["load_difference"] == 0
    value["refs"] = {"unrelated": []}
    with pytest.raises(ContextContractError):
        validate_feature_vector(value)


@pytest.mark.parametrize("number", [True, float("nan"), float("inf"), "1", object()])
def test_feature_values_are_real_finite_json_numbers(number):
    value = features()
    value["states"]["load_difference"] = "available"
    value["values"]["load_difference"] = number
    with pytest.raises(ContextContractError):
        validate_feature_vector(value)


@pytest.mark.parametrize("name", ["bestOdds", "closingPrice", "bookmakerIdentity", "ROI1", "minQuote"])
def test_feature_names_cannot_hide_price_semantics_in_camel_case(name):
    value = features()
    value["values"], value["states"], value["refs"] = {name: .2}, {name: "available"}, {name: []}
    with pytest.raises(ContextContractError):
        validate_feature_vector(value)


def test_feature_hash_binds_values_states_coverage_and_reference_without_mutating_input():
    from context_models.contracts import digest
    original = features()
    original_hash = digest(validate_feature_vector(original))
    for change in ({"reference_hash": REF}, {"coverage": {"version": "load-v1", "case": "other"}},
                   {"states": {"load_difference": "not_applicable"}}, {"refs": {"load_difference": [REF]}}):
        assert digest(validate_feature_vector({**original, **change})) != original_hash
    assert original == features()


@pytest.mark.parametrize("probability", [0, 1])
def test_endpoint_winner_base_remains_visible_without_claiming_logit_applicability(probability):
    value = base()
    value["params"] = {"p_a": probability}
    value["markets"] = {"winner_a": probability, "winner_b": 1 - probability}
    assert validate_base_distribution(value) == value


@pytest.mark.parametrize("changes", [
    {"family": "basketball:margin"}, {"params": {"p_a": .6, "odds": 1.2}},
    {"markets": {"winner_a": {"probability": .6}, "winner_b": .4}},
    {"markets": {"winner_a": .6, "winner_b": .3}},
    {"markets": {"winner_a": .5, "winner_b": .5}},
    {"markets": {"winner_a": .6, "winner_b": .4, "unproven": .5}},
    {"markets": {"winner_a": True, "winner_b": 0}},
    {"params": {"p_a": float("nan")}},
])
def test_base_closed_shape_and_winner_contract_never_coerce_objects_or_probabilities(changes):
    with pytest.raises(ContextContractError):
        validate_base_distribution({**base(), **changes})


@pytest.mark.parametrize("hold_a,best_of", [(0, 5), (1, 5), (.7, True), (.7, 3.0), (.7, 7)])
def test_serve_base_requires_actual_match_format_and_interior_holds(hold_a, best_of):
    value = {**base(), "family": "tennis:serve", "params": {"hold_a": hold_a, "hold_b": .7, "best_of": best_of}}
    with pytest.raises(ContextContractError):
        validate_base_distribution(value)


def football_reference_base():
    history = [{"ref": REF, "source": "api-football", "source_event_id": "99", "native_event_key": "api-football:football:99",
                "event_join": "verified_native", "roster_join": "verified_native"}]
    heads = {}
    for side in ("home", "away"):
        components = {}
        for name in ("venue_attack", "venue_defense", "form_attack", "form_defense"):
            home_team = (side == "home") == name.endswith("attack")
            form = name.startswith("form")
            components[name] = {
                "team_id": "api-football:team:1" if home_team else "api-football:team:2", "team_join": "verified_native",
                "scope": "all_form" if form else ("home_venue" if home_team else "away_venue"),
                "prior_raw_weight": 3 if form else 4, "metric_weights": {"goals": 1, "xg": 0},
                "goals": {"samples": [{"ref": REF, "weight": .25}], "prior_weight": .75,
                          "prior_value": 1.3, "prior_refs": [{"ref": REF, "weight": 1.0}]}, "xg": None,
            }
        heads[side] = {"outer_weights": {"venue": .75, "form": .25},
                       "pair_weights": {"venue": {"attack": .5, "defense": .5}, "form": {"attack": .5, "defense": .5}},
                       "components": components}
    return {"version": "football-base-v1", "model_hash": HASH, "event_key": "api-football:football:1", "cutoff": TIME,
            "family": "football:goals:90min", "params": {"home_lambda": 1.53, "away_lambda": 1.13},
            "markets": {"RESULT_HOME": .464, "RESULT_DRAW": .276, "RESULT_AWAY": .260}, "history_refs": history,
            "reference_weights": {"schema": 1, "kind": "football-goals-v1", "heads": heads}}


def test_reference_components_preserve_actual_base_venue_form_prior_and_metric_weights():
    value = football_reference_base()
    assert validate_base_distribution(value) == value
    component = value["reference_weights"]["heads"]["home"]["components"]["venue_attack"]
    component["xg"] = deepcopy(component["goals"])
    component["xg"]["samples"] = []
    component["xg"]["prior_weight"] = 1
    component["metric_weights"] = {"goals": .4, "xg": .6}
    assert validate_base_distribution(value) == value


@pytest.mark.parametrize("mutation", ["unnormalized", "undeclared", "prior_not_normalized", "empty_prior", "pseudo_count", "venue",
                                      "xg", "team_identity", "unknown_field", "pair", "outer", "same_team"])
def test_invalid_reference_weights_cannot_masquerade_as_verified_roster_provenance(mutation):
    value = football_reference_base()
    head = value["reference_weights"]["heads"]["home"]
    component = head["components"]["venue_attack"]
    if mutation == "unnormalized": component["goals"]["samples"][0]["weight"] = .5
    if mutation == "undeclared": component["goals"]["samples"][0]["ref"] = "c" * 64
    if mutation == "prior_not_normalized": component["goals"]["prior_refs"][0]["weight"] = .5
    if mutation == "empty_prior": component["goals"]["prior_refs"] = []
    if mutation == "pseudo_count": component["prior_raw_weight"] = 5
    if mutation == "venue": component["scope"] = "away_venue"
    if mutation == "xg": component["metric_weights"] = {"goals": .4, "xg": .6}
    if mutation == "team_identity": component["team_id"] = "api-football:team:55"
    if mutation == "unknown_field": component["guessed_star_penalty"] = .2
    if mutation == "pair": head["pair_weights"]["venue"] = {"attack": .6, "defense": .4}
    if mutation == "outer": head["outer_weights"] = {"venue": .5, "form": .5}
    if mutation == "same_team":
        for h in value["reference_weights"]["heads"].values():
            for c in h["components"].values():
                c["team_id"] = "api-football:team:1"
    with pytest.raises(ContextContractError):
        validate_base_distribution(value)


def test_unresolved_csv_reference_keeps_baseline_but_never_claims_native_roster_join():
    value = base()
    value["history_refs"] = [{"ref": REF, "source": "csv-fixture", "source_event_id": "-123",
                              "native_event_key": None, "event_join": "unresolved", "roster_join": "unresolved"}]
    # Genuine unresolved identity is legal; source_event_id is not a native join.
    assert validate_base_distribution(value) == value
    value["history_refs"][0]["roster_join"] = "verified_native"
    with pytest.raises(ContextContractError):
        validate_base_distribution(value)


@pytest.mark.parametrize("mutation", ["head", "link", "scale", "coef", "bool_scale", "count", "alpha", "numpy", "calibration", "coverage", "population", "price_feature"])
def test_effect_closed_heads_features_and_scope(mutation):
    value = effect()
    head = value["heads"]["winner"]
    if mutation == "head": value["heads"]["home"] = value["heads"].pop("winner")
    if mutation == "link": head["link"] = "identity"
    if mutation == "scale": head["scale"] = [0]
    if mutation == "coef": head["coef"] = [.1, .2]
    if mutation == "bool_scale": head["scale"] = [True]
    if mutation == "count": head["n_rows"] = 100.5
    if mutation == "alpha": head["alpha"] = -1
    if mutation == "numpy":
        import numpy as np
        head["coef"] = np.array([.2])
    if mutation == "calibration": value["joint_calibration"] = {"kind": "identity", "approved": True}
    if mutation == "coverage": value["coverage"] = "complete"
    if mutation == "population": value["population"]["sport"] = "football"
    if mutation == "price_feature": value["feature_names"] = ["minimum_odds"]
    with pytest.raises(ContextContractError):
        validate_effect_artifact(value)


def training_row():
    return {"event_key": "espn:tennis:1", "decision_at": "2026-09-06T12:00:00.000000Z", "result_observed_at": TIME,
            "block": "2026-week-36", "population": population(), "coverage": {"version": "load-v1", "case": "complete"},
            "feature_names": ["load_difference"], "x": [1.2], "offset": .5, "target": 1, "trials": 1,
            "base_hash": HASH, "feature_refs": {"load_difference": [REF]}, "evidence_class": "prospective",
            "family": "tennis:winner", "head": "winner"}


def test_training_row_routes_family_head_and_preserves_evidence_class():
    row = training_row()
    assert validate_training_row(row, effect_artifact=effect()) == row
    row["evidence_class"] = "retrospective"
    # Storage validity is NOT D1/D2 causal eligibility.
    assert validate_training_row(row)["evidence_class"] == "retrospective"


@pytest.mark.parametrize("changes", [{"head": "hold_a"}, {"x": [None]}, {"x": [True]}, {"x": [1, 2]},
                                    {"trials": 5}, {"target": 2}, {"target": .5}, {"offset": float("inf")},
                                    {"result_observed_at": "2026-09-06T12:00:00.000000Z"}, {"family": "tennis:serve"},
                                    {"feature_refs": {"load_difference": [REF, REF]}}])
def test_training_invalid_rows_fail_before_numerical_consumption(changes):
    with pytest.raises(ContextContractError):
        validate_training_row({**training_row(), **changes}, effect_artifact=effect())


def test_training_feature_order_and_result_cutoff_are_bound_to_artifact():
    row, artifact = training_row(), effect()
    row["feature_names"] = ["load_difference", "rest_difference"]
    row["x"] = [1.2, 0]
    row["feature_refs"]["rest_difference"] = [REF]
    artifact["feature_names"] = ["rest_difference", "load_difference"]
    artifact["heads"]["winner"]["coef"] = [0, .2]
    artifact["heads"]["winner"]["scale"] = [1, 1]
    with pytest.raises(ContextContractError, match="ordered"):
        validate_training_row(row, effect_artifact=artifact)
    artifact = effect()
    artifact["training_end"] = "2026-09-06T18:00:00.000000Z"
    with pytest.raises(ContextContractError, match="training cutoff"):
        validate_training_row(training_row(), effect_artifact=artifact)


def context_result():
    return {"event_key": "espn:tennis:1", "base_hash": HASH, "effect_hash": None, "role": "not_applied",
            "factor_roles": {"load_difference": "not_applied"}, "factor_states": {"load_difference": "missing"},
            "feature_refs": {"load_difference": []}, "base_params": {"p_a": .6}, "comparison_params": None,
            "used_params": {"p_a": .6}, "base_markets": {"winner_a": .6, "winner_b": .4}, "comparison_markets": None,
            "used_markets": {"winner_a": .6, "winner_b": .4}, "delta_pp": {"winner_a": 0, "winner_b": 0},
            "limitations": ["duration-unavailable"]}


def test_context_result_distinguishes_unapplied_experimental_and_applied_zero_effect():
    row = context_result()
    assert validate_context_result(row, family="tennis:winner") == row
    row.update(effect_hash=REF, role="experimental", comparison_params={"p_a": .7},
               comparison_markets={"winner_a": .7, "winner_b": .3}, limitations=[])
    row["factor_roles"]["load_difference"] = "experimental"
    row["factor_states"]["load_difference"] = "available"
    row["feature_refs"]["load_difference"] = [REF]
    assert validate_context_result(row, family="tennis:winner", effect_artifact=effect())["used_params"] == {"p_a": .6}
    row.update(role="applied", comparison_params={"p_a": .6}, comparison_markets={"winner_a": .6, "winner_b": .4})
    row["factor_roles"]["load_difference"] = "applied"
    assert validate_context_result(row, family="tennis:winner", effect_artifact=effect())["role"] == "applied"


@pytest.mark.parametrize("mutation", ["invented_effect", "excessive_factor_role", "wrong_used", "wrong_delta", "unconsumed_factor", "parameter_market_disagreement", "missing_factors"])
def test_context_result_cannot_claim_nonexistent_or_unused_context_effect(mutation):
    row = context_result()
    artifact = None
    if mutation == "invented_effect": row["role"] = "applied"
    if mutation == "excessive_factor_role": row["factor_roles"]["load_difference"] = "applied"
    if mutation == "wrong_used": row["used_params"]["p_a"] = .8
    if mutation == "wrong_delta": row["delta_pp"]["winner_a"] = 1
    if mutation == "parameter_market_disagreement":
        row["base_params"]["p_a"] = .7
        row["used_params"]["p_a"] = .7
    if mutation in {"unconsumed_factor", "missing_factors"}:
        artifact = effect()
        row.update(effect_hash=REF, role="experimental", comparison_params={"p_a": .7}, comparison_markets={"winner_a": .7, "winner_b": .3})
        row["factor_roles"] = {"unconsumed": "experimental"} if mutation == "unconsumed_factor" else {}
        row["factor_states"] = {key: "available" for key in row["factor_roles"]}
        row["feature_refs"] = {key: [] for key in row["factor_roles"]}
    with pytest.raises(ContextContractError):
        validate_context_result(row, family="tennis:winner", effect_artifact=artifact)
