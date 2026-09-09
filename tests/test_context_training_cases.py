"""Full native Football case reconstruction, never trusted free row.x values."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from context_observations import append_observation, observations_as_of
from context_training_helpers import NOW, detail, envelope, football_inventory, football_recipe


def football_case(tmp_path, *, decision=NOW-timedelta(days=7), event_id=9000, minute_shift=0, goals=(2, 1), omit_base_target_lineups=False):
    from context_models.football import football_features
    from context_models.replay import replay_base_distribution
    from context_sources.outcomes import normalize_football_outcome
    event, history, observations, identities = football_inventory(tmp_path, decision=decision, event_id=event_id,
        minute_shift=minute_shift, omit_base_target_lineups=omit_base_target_lineups)
    recipe = football_recipe(history)
    replay = replay_base_distribution("football", event, history, decision_at=decision, reconstructed_at=NOW,
                                       recipe=recipe, identity_map=identities)
    base = replay["payload"]["base"]
    features = football_features(event, observations, base, cutoff=decision)
    name = "home.venue_attack.goals.api-football:player:1"
    assert features["states"][name] == "available"
    config = {"schema": 1, "sport": "football", "family": "football:goals:90min",
        "feature_version": features["version"], "feature_names": [name],
        "population": {"sport": "football", "competitions": ["39"], "formats": ["90min"],
                       "tours": [None], "surfaces": [None], "indoor": [None]},
        "coverage": features["coverage"], "model_variant": "football-roster-two-head-log-rate-v1",
        "base_versions": [base["version"]], "head_links": {"home": "log_rate", "away": "log_rate"},
        "reference_version": "football-context-reference-v2", "preprocessing_artifacts": {},
        "groups": {"roster": [name]}, "joint_calibration": {"kind": "identity"},
        "target_markets": ["RESULT_AWAY", "RESULT_DRAW", "RESULT_HOME"],
        "outcome_contract": "football-regulation-ft-v1",
        "train_end": canonical_timestamp(decision+timedelta(days=1)),
        "tune_end": canonical_timestamp(decision+timedelta(days=3)), "alpha_grid": [.01, .1, 1., 10., 100.]}
    outcome = normalize_football_outcome(event, detail(event_id, decision+timedelta(hours=2), goals=goals), observed_at=decision+timedelta(hours=4))
    path = tmp_path / f"synthetic-outcome-{event_id}.db"
    append_observation(path, outcome, observed_at=decision+timedelta(hours=4))
    results = observations_as_of(path, event["event_key"], cutoff=NOW, schedule_revision=event["schedule_revision"])
    case = envelope("context-training-case-v1", {"schema": 1, "event": event, "base": base, "features": features,
        "replay_ref": replay["digest"], "outcome_ref": results[0]["digest"], "event_identity_hash": identities["digest"],
        "family_config_hash": digest(config), "preprocessing_refs": []})
    resolved = {"case": case, "artifacts": {obj["digest"]: obj for obj in (replay, recipe, identities)},
                "observations": observations + results}
    return resolved, config


@pytest.fixture(scope="module")
def case_fixture(tmp_path_factory):
    return football_case(tmp_path_factory.mktemp("d1-case"))


def test_full_case_rebuilds_base_and_features_from_resolved_native_receipts(case_fixture):
    from context_models.training_contracts import validate_resolved_case
    resolved, config = deepcopy(case_fixture)
    assert validate_resolved_case(resolved, config=config) == resolved
    from context_models.training_cases import assemble_training_cases
    result = assemble_training_cases((resolved,), config)
    assert result["canonical_events"] == 1
    assert len(result["rows"]) == 2 and result["excluded"] == ()
    assert {row["head"] for row in result["rows"]} == {"home", "away"}
    assert {row["target"] for row in result["rows"]} == {1, 2}
    assert all(row["x"] == [resolved["case"]["payload"]["features"]["values"][config["feature_names"][0]]] for row in result["rows"])


@pytest.mark.parametrize("change", ["base", "feature", "missing_source", "unknown_x", "map", "outcome", "preprocessing"])
def test_case_hash_cannot_certify_fabricated_features_or_source_replay(case_fixture, change):
    from context_models.training_contracts import validate_resolved_case
    resolved, config = deepcopy(case_fixture)
    payload = resolved["case"]["payload"]
    if change == "base":
        payload["base"]["params"]["home_lambda"] += .1
    elif change == "feature":
        payload["features"]["values"][config["feature_names"][0]] += 1
    elif change == "missing_source":
        resolved["observations"] = resolved["observations"][1:]
    elif change == "unknown_x":
        payload["x"] = [123.]
    elif change == "map":
        payload["event_identity_hash"] = "e" * 64
    elif change == "outcome":
        payload["outcome_ref"] = "b" * 64
    else:
        payload["preprocessing_refs"] = ["a" * 64]
    resolved["case"] = envelope(resolved["case"]["kind"], payload)
    with pytest.raises(ContextContractError):
        validate_resolved_case(resolved, config=config)


def test_absent_player_column_is_excluded_not_zero_filled(case_fixture):
    from context_models.training_cases import assemble_training_cases
    resolved, config = deepcopy(case_fixture)
    name = config["feature_names"][0].replace("player:1", "player:999999")
    config["feature_names"], config["groups"] = [name], {"roster": [name]}
    resolved["case"]["payload"]["family_config_hash"] = digest(config)
    resolved["case"] = envelope(resolved["case"]["kind"], resolved["case"]["payload"])
    report = assemble_training_cases((resolved,), config)
    assert report["rows"] == () and report["canonical_events"] == 0
    assert report["excluded"][0]["reason"] == "consumed_feature_unavailable"


def test_duplicate_native_case_is_not_a_second_training_event(case_fixture):
    from context_models.training_cases import assemble_training_cases
    resolved, config = deepcopy(case_fixture)
    with pytest.raises(ContextContractError, match="duplicate|one native"):
        assemble_training_cases((resolved, deepcopy(resolved)), config)


def test_known_newer_native_result_cannot_be_hidden_by_an_older_recipe_subset(case_fixture, tmp_path):
    from context_models.training_contracts import validate_resolved_case
    from context_sources.outcomes import normalize_football_base_input
    from context_sources.football import _detail_event
    resolved, config = deepcopy(case_fixture)
    payload = resolved["case"]["payload"]
    old = next(row for row in resolved["observations"] if row["kind"] == "base_fixture" and row["event_key"] != payload["event"]["event_key"])
    raw = deepcopy(old["payload"]["detail"])
    raw["goals"]["home"] += 1
    from datetime import datetime
    received = datetime.fromisoformat(payload["base"]["cutoff"]) - timedelta(hours=1)
    record = normalize_football_base_input(raw, observed_at=received)
    path = tmp_path / "corrected-native.db"
    append_observation(path, record, observed_at=received)
    ev = _detail_event(raw)
    rows = observations_as_of(path, ev["event_key"], cutoff=received, schedule_revision=ev["schedule_revision"])
    resolved["observations"] += rows
    with pytest.raises(ContextContractError, match="latest|recipe|replay"):
        validate_resolved_case(resolved, config=config)


def test_new_native_player_revision_cannot_reuse_older_normalized_minutes(case_fixture, tmp_path):
    from datetime import datetime
    from context_models.training_contracts import validate_resolved_case
    from context_sources.outcomes import normalize_football_base_input
    from context_sources.football import _detail_event
    from context_models.football import football_features
    from context_models.replay import replay_base_distribution
    resolved, config = deepcopy(case_fixture)
    payload = resolved["case"]["payload"]
    old = next(row for row in resolved["observations"] if row["kind"] == "base_fixture" and row["event_key"] != payload["event"]["event_key"])
    raw = deepcopy(old["payload"]["detail"])
    raw["players"][0]["players"][0]["statistics"][0]["games"]["minutes"] = 15
    decision = datetime.fromisoformat(payload["base"]["cutoff"])
    received = decision-timedelta(hours=1)
    path = tmp_path / "corrected-player.db"
    append_observation(path, normalize_football_base_input(raw, observed_at=received), observed_at=received)
    ev = _detail_event(raw)
    changed = observations_as_of(path, ev["event_key"], cutoff=received, schedule_revision=ev["schedule_revision"])
    resolved["observations"] += changed
    history = tuple(row for row in resolved["observations"] if row["kind"] == "base_fixture" and row["digest"] != old["digest"])
    recipe = football_recipe(history)
    identities = resolved["artifacts"][payload["event_identity_hash"]]
    replay = replay_base_distribution("football", payload["event"], history, decision_at=decision, reconstructed_at=NOW,
                                      recipe=recipe, identity_map=identities)
    base = replay["payload"]["base"]
    # Maliciously coherent hashes around OLD normalized appearance minutes.
    feats = football_features(payload["event"], tuple(row for row in resolved["observations"] if row["kind"] != "match_outcome"), base, cutoff=decision)
    payload.update(base=base, features=feats, replay_ref=replay["digest"])
    resolved["artifacts"] = {obj["digest"]: obj for obj in (replay, recipe, identities)}
    resolved["case"] = envelope("context-training-case-v1", payload)
    with pytest.raises(ContextContractError, match="projection|revision|native"):
        validate_resolved_case(resolved, config=config)


def test_omitted_base_lineup_field_does_not_revoke_separately_observed_lineup(tmp_path):
    from context_models.training_contracts import validate_resolved_case
    resolved, config = football_case(tmp_path, omit_base_target_lineups=True)
    assert validate_resolved_case(resolved, config=config) == resolved
