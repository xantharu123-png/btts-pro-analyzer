"""C4 real synthetic fit, signed model properties and reference mutations."""
from copy import deepcopy
from datetime import timedelta

import numpy as np
import pytest
from scipy.special import logit

from context_models.contracts import ContextContractError, digest, validate_base_distribution
from context_models.esports import apply_esports_effect, esports_features, series_probability
from context_models.offset import fit_offset
from multi_sport_recommendations import esports_match_winner_candidate
from test_esports_context import NOW, case, effect, ingest, make_case


@pytest.mark.parametrize("p,delta", [(0., 0.), (1., 0.), (-.1, 0.), (.5, float("nan")), (.5, float("inf")),
    (.5, -float("inf")), (True, 0.), (.5, True), (.5, []), (.5, 2**53+1), (.5, 1000.), (.5, -1000.)])
def test_invalid_or_saturated_series_inputs_are_typed_errors(p, delta):
    with pytest.raises(ContextContractError):
        series_probability(p, delta)


@pytest.mark.parametrize("p", [.01, .2, .49999999999, .5, .8, .99])
@pytest.mark.parametrize("delta", [-3., -.1, 0., .1, 3.])
def test_series_probabilities_are_interior_complementary_and_monotone(p, delta):
    changed = series_probability(p, delta)
    assert 0 < changed < 1
    assert changed + series_probability(1-p, -delta) == pytest.approx(1., abs=1e-14)
    if delta == 0:
        assert changed.hex() == p.hex()
    else:
        assert (changed > p) is (delta > 0)


def test_actual_b2_fit_consumes_source_sqlite_features_from_unique_synthetic_cases(case, tmp_path):
    key = "participation_delta/1/2026/pandascore:esports:player:701"
    training = [make_case(tmp_path / f"case-{i}.sqlite", missing_player=i % 2 == 0,
                          decision=NOW - timedelta(days=2) + timedelta(minutes=i), identity=9100+i) for i in range(4)]
    assert len({row["event"]["event_key"] for row in training}) == 4
    x = np.array([[row["features"]["values"][key]] for row in training], dtype=float)
    offset = np.array([logit(row["base"]["params"]["p_a"]) for row in training])
    # Explicitly synthetic event labels. No claim of source-qualified D1
    # outcome assembly or untouched real validation is made by this test.
    fit = fit_offset(x, offset, np.array([0., 1., 0., 1.]), link="logit", alpha=.05, trials=np.ones(4))
    assert fit["n_rows"] == 4 and fit["coef"][0] > 0
    artifact = effect(case)
    artifact["heads"]["winner"] = fit
    artifact["training_refs_hash"] = digest(sorted(row["event"]["event_key"] for row in training))
    comparison = apply_esports_effect(case["base"], case["features"], artifact, event=case["event"])
    assert comparison["params"]["p_a"] < case["base"]["params"]["p_a"]
    assert all(row["base"]["cutoff"] < artifact["training_end"] for row in training)


def test_native_side_swap_mirrors_base_features_and_fitted_effect(case, tmp_path):
    match, event, records = deepcopy(case["match"]), deepcopy(case["event"]), deepcopy(case["records"])
    for suffix in ("", "_id", "_score", "_stats", "_history"):
        one, two = "team1" + suffix, "team2" + suffix
        match[one], match[two] = match[two], match[one]
    event["home_id"], event["away_id"] = event["away_id"], event["home_id"]
    records[-1][0]["event"] = event
    observations = ingest(tmp_path / "mirror.sqlite", event, records)
    mirrored = esports_match_winner_candidate(match, now=NOW, base_request={"event": event, "observations": observations})["base"]
    features = esports_features(event, observations, mirrored, cutoff=NOW)
    name = "participation_delta/1/2026/pandascore:esports:player:701"
    assert features["values"][name] == -case["features"]["values"][name]
    assert mirrored["params"]["p_a"] + case["base"]["params"]["p_a"] == pytest.approx(1., abs=1e-14)
    original = apply_esports_effect(case["base"], case["features"], effect(case), event=case["event"])
    changed = apply_esports_effect(mirrored, features, effect({**case, "features": features, "event": event}), event=event)
    assert original["params"]["p_a"] + changed["params"]["p_a"] == pytest.approx(1., abs=1e-14)


@pytest.mark.parametrize("field,value", [("scheduled_start", "2026-09-09T19:00:00.000000Z"), ("schedule_revision", "revision-2"),
    ("status", "cancelled"), ("home_id", "pandascore:esports:team:9"), ("competition", "pandascore:title:2:competition:9"),
    ("format", "series_best_of_5")])
def test_unchanged_feature_vector_cannot_follow_event_revision(case, field, value):
    event = {**case["event"], field: value}
    with pytest.raises(ContextContractError):
        apply_esports_effect(case["base"], case["features"], effect(case), event=event)


@pytest.mark.parametrize("mutate", [
    lambda ref: ref["constants"].update(ELO_ITERATIONS=1),
    lambda ref: ref["constants"].update(ELO_BASE=1500),
    lambda ref: ref["ratings"].__setitem__(0, ref["ratings"][0] + .01),
    lambda ref: ref["windows"]["home"].reverse(),
    lambda ref: ref["subgraph"][0].update(won=not ref["subgraph"][0]["won"]),
    lambda ref: ref["code_hashes"].update({"esports_elo.py": "0" * 64}),
    lambda ref: ref["scope"].update(season_id=2025),
    lambda ref: ref["scope"].update(title="lol"),
    lambda ref: ref["participation"]["teams"]["pandascore:esports:team:7"][0].update(weight=.5),
    lambda ref: ref["receipts"][0]["payload"].update(status="cancelled"),
])
def test_original_native_replay_and_participation_are_immutable(case, mutate):
    base = deepcopy(case["base"])
    mutate(base["reference_weights"])
    base["model_hash"] = digest({"version": base["version"], "reference": base["reference_weights"]})
    with pytest.raises(ContextContractError):
        validate_base_distribution(base)


def test_series_comparison_cannot_be_reapplied_as_original_base(case):
    comparison = apply_esports_effect(case["base"], case["features"], effect(case), event=case["event"])
    with pytest.raises(ContextContractError):
        apply_esports_effect(comparison, case["features"], effect(case), event=case["event"])


@pytest.mark.parametrize("name", ["at_least_one_map", "map_winner_a", "winner_a", "series_exact_2_0"])
def test_only_owning_complementary_series_markets_are_supported(case, name):
    base = deepcopy(case["base"])
    base["markets"][name] = .5
    with pytest.raises(ContextContractError):
        validate_base_distribution(base)


def test_no_native_receipts_preserves_original_candidate_and_available_base(case):
    exported = esports_match_winner_candidate(case["match"], now=NOW, base_request={"event": case["event"], "observations": ()})
    assert exported["candidate"] == case["candidate"]
    assert exported["base"]["params"] == case["base"]["params"]
    assert exported["base"]["reference_weights"]["kind"] == "unavailable"
    assert exported["base"]["markets"] == case["base"]["markets"]


def test_price_mutations_do_not_enter_original_native_base_or_features(case):
    match = deepcopy(case["match"])
    match.update(odds=1.01, bookmaker="irrelevant", minimum_odds=999.)
    output = esports_match_winner_candidate(match, now=NOW, base_request={"event": case["event"], "observations": case["observations"]})
    assert output["base"] == case["base"] and output["candidate"] == case["candidate"]


def test_b3_rejects_a_different_actual_a1_effect_from_the_comparison(case):
    from context_snapshots import select_context_result
    artifact = effect(case)
    comparison = apply_esports_effect(case["base"], case["features"], artifact, event=case["event"])
    artifact["heads"]["winner"]["coef"][0] = .9
    envelope = {"kind": "context-effect-v1", "payload": artifact}
    with pytest.raises(ContextContractError):
        select_context_result(case["base"], comparison, event=case["event"], features=case["features"],
            effect_artifact=envelope, effect_hash=digest(envelope), approval=None,
            factor_roles={name: "not_applied" for name in case["features"]["values"]}, factor_states=case["features"]["states"], limitations=[])


@pytest.mark.parametrize("mutate", [
    lambda a, f: a.update(training_end="2027-01-01T00:00:00.000000Z"),
    lambda a, f: a.update(feature_version="esports-not-reviewed-v9"),
    lambda a, f: a.update(model_variant="a-free-penalty"),
    lambda a, f: a["heads"]["winner"].update(link="identity"),
    lambda a, f: a["heads"]["winner"].update(coef=[2**53+1]),
    lambda a, f: a["heads"]["winner"].update(scale=[True]),
    lambda a, f: a.update(preprocessing_artifacts={"unresolved": "1" * 64}),
    lambda a, f: a["population"].update(formats=["series_best_of_5"]),
    lambda a, f: f["coverage"].update(case=f["coverage"]["case"] + ".all-healthy"),
    lambda a, f: f["states"].update({a["feature_names"][0]: "conflicting"}),
    lambda a, f: f["refs"].update({a["feature_names"][0]: []}),
    lambda a, f: f["values"].update({a["feature_names"][0]: -.5}),
    lambda a, f: f.update(reference_hash="2" * 64),
])
def test_strict_order_scope_coverage_clock_numeric_and_reference_guards(case, mutate):
    artifact, features = effect(case), deepcopy(case["features"])
    mutate(artifact, features)
    with pytest.raises(ContextContractError):
        apply_esports_effect(case["base"], features, artifact, event=case["event"])


def test_artifact_feature_order_is_fixed_not_dictionary_iteration(case):
    names = ["participation_delta/1/2026/pandascore:esports:player:701", "participation_delta/1/2026/pandascore:esports:player:706"]
    artifact = effect(case, names=names)
    original = apply_esports_effect(case["base"], case["features"], artifact, event=case["event"])
    features = deepcopy(case["features"])
    for key in ("values", "states", "refs"):
        features[key] = dict(reversed(list(features[key].items())))
    assert apply_esports_effect(case["base"], features, artifact, event=case["event"]) == original
    artifact["feature_names"].reverse()
    with pytest.raises(ContextContractError):
        apply_esports_effect(case["base"], features, artifact, event=case["event"])


def test_esports_context_result_does_not_tolerate_a_one_ulp_parameter_market_mismatch(case):
    from math import nextafter
    from context_models.contracts import validate_context_result
    from context_models.esports import FAMILY, esports_context_result
    artifact = effect(case)
    envelope = {"kind": "context-effect-v1", "payload": artifact}
    result = esports_context_result(case["base"], case["features"], envelope, event=case["event"], effect_hash=digest(envelope))
    result["base_params"]["p_a"] = nextafter(result["base_params"]["p_a"], 1.)
    result["used_params"] = deepcopy(result["base_params"])
    with pytest.raises(ContextContractError):
        validate_context_result(result, family=FAMILY, effect_artifact=artifact)
