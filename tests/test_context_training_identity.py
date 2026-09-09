"""Native identity maps are dataset-wide, with actual B1 reference resolution."""
from copy import deepcopy

import pytest

from context_models.contracts import ContextContractError, digest
from context_observations import append_observation, observations_as_of
from test_context_outcomes import NOW, football_input


def envelope(kind, payload):
    value = {"kind": kind, "payload": payload}
    return {"digest": digest(value), **value}


def identity_inputs(tmp_path):
    from context_sources.outcomes import normalize_football_base_input
    event, raw = football_input()
    path = tmp_path / "native.db"
    append_observation(path, normalize_football_base_input(raw, observed_at=NOW), observed_at=NOW)
    rows = observations_as_of(path, event["event_key"], cutoff=NOW, schedule_revision=event["schedule_revision"])
    value = envelope("context-native-identity-map-v1", {"schema": 1, "policy": "native-source-only-v1",
        "bindings": [{"event_key": event["event_key"], "home_id": event["home_id"], "away_id": event["away_id"],
                      "source_refs": [rows[0]["digest"]]}]})
    return value, rows


def test_native_identity_hash_binds_whole_map_not_an_event_name(tmp_path):
    from context_models.training_contracts import resolve_identity_map, validate_identity_map
    value, rows = identity_inputs(tmp_path)
    assert validate_identity_map(value) == value
    assert resolve_identity_map(value, observations=rows) == value
    assert value["digest"] != digest(value["payload"]["bindings"][0]["event_key"])
    with pytest.raises(ContextContractError):
        resolve_identity_map(value, observations=())


@pytest.mark.parametrize("change", ["foreign_event", "foreign_team", "duplicate", "missing_ref", "fake_hash", "free_verified"])
def test_identity_shape_or_a_public_hash_cannot_replace_native_receipts(tmp_path, change):
    from context_models.training_contracts import resolve_identity_map
    value, rows = identity_inputs(tmp_path)
    binding = value["payload"]["bindings"][0]
    if change == "foreign_event":
        binding["event_key"] = "csv:football:1570343"
    elif change == "foreign_team":
        binding["home_id"] = "api-football:team:999999"
    elif change == "duplicate":
        value["payload"]["bindings"].append(deepcopy(binding))
    elif change == "missing_ref":
        binding["source_refs"] = ["c" * 64]
    elif change == "free_verified":
        binding["verified"] = True
    value = envelope(value["kind"], value["payload"])
    if change == "fake_hash":
        value["digest"] = "a" * 64
    with pytest.raises(ContextContractError):
        resolve_identity_map(value, observations=rows)


def test_unresolved_native_state_alias_is_not_implicitly_accepted():
    from context_models.training_contracts import validate_identity_map
    value = envelope("context-native-identity-map-v1", {"schema": 1, "policy": "native-source-only-v1", "bindings": [
        {"event_key": "espn:tennis:ATP:match:1", "home_id": "state:tennis:jannik.sinner",
         "away_id": "espn:tennis:ATP:player:2", "source_refs": ["a" * 64]}]})
    with pytest.raises(ContextContractError):
        validate_identity_map(value)


def test_subset_resolution_does_not_open_other_event_receipts(tmp_path):
    from context_models.training_contracts import resolve_identity_map
    value, rows = identity_inputs(tmp_path)
    original_key = value["payload"]["bindings"][0]["event_key"]
    value["payload"]["bindings"].append({"event_key": "api-football:football:9999999",
        "home_id": "api-football:team:1", "away_id": "api-football:team:2", "source_refs": ["b" * 64]})
    value["payload"]["bindings"].sort(key=lambda item: item["event_key"])
    value = envelope(value["kind"], value["payload"])
    assert resolve_identity_map(value, observations=rows, event_keys=(original_key,)) == value
    with pytest.raises(ContextContractError):
        resolve_identity_map(value, observations=rows)


@pytest.mark.parametrize("keys", [(), ([],), ({},), (True,), ["event"]])
def test_subset_keys_remain_strict_json_identities(tmp_path, keys):
    from context_models.training_contracts import resolve_identity_map
    value, rows = identity_inputs(tmp_path)
    with pytest.raises(ContextContractError):
        resolve_identity_map(value, observations=rows, event_keys=keys)
