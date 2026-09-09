"""An inner native original event cannot be relabeled by a new outer hash."""
from copy import deepcopy

import pytest

from context_models.contracts import ContextContractError, digest, validate_event
from context_snapshots import _payload_digest
from context_transport import (_input_key, calculate_context_payload,
    project_context_market, replay_context_payload)
from test_esports_context import case


def arguments(sport, case):
    if sport == "esports":
        from test_context_transport_esports import packet
        return deepcopy(packet(case, with_effect=False))
    if sport == "hockey":
        from test_context_transport_hockey import packet
        return deepcopy(packet(with_effect=False))
    from test_basketball_context import event, feature_packet, packet
    original, _, rows = packet()
    features = feature_packet(original, rows)
    return dict(event=validate_event(event()), base=original, features=features,
        observation_refs=sorted({ref for refs in features["refs"].values() for ref in refs}),
        preprocessing_refs=[], effect_artifact=None, effect_hash=None, approval=None)


def rebind(args, sport, change):
    if change == "opposing-teams":
        args["event"]["home_id"], args["event"]["away_id"] = args["event"]["away_id"], args["event"]["home_id"]
    else:
        args["event"]["schedule_revision"] = "different-native-revision"
    name = "esports" if sport == "esports" else "hockey" if sport == "hockey" else "basketball"
    suffix = {"preprocessing": []} if sport == "esports" else {"preprocessing_artifacts": {}}
    args["features"]["reference_hash"] = digest({"version": name+"-context-reference-v1",
        "base_hash": digest(args["base"]), "event_hash": digest(args["event"]), **suffix})


@pytest.mark.parametrize("sport", ["esports", "basketball", "hockey"])
@pytest.mark.parametrize("change", ["opposing-teams", "schedule"])
@pytest.mark.parametrize("boundary", ["calculate", "full-replay", "light-projection"])
def test_known_original_event_is_bound_before_every_fallback_or_reader(case, sport, change, boundary):
    args = arguments(sport, case)
    if boundary == "calculate":
        rebind(args, sport, change)
        with pytest.raises(ContextContractError):
            calculate_context_payload(**args)
        return
    payload = calculate_context_payload(**args)
    rebind(payload, sport, change)
    # Generate the raw input key without its public validator, so this really
    # tests the reader/replayer itself instead of an earlier key-API failure.
    key = _input_key(payload, payload["event"], payload["base"], payload["features"])
    with pytest.raises(ContextContractError):
        if boundary == "full-replay":
            replay_context_payload(payload, key=key, effect_artifact=None, approval=None)
        else:
            reference = {"schema": 1, "kind": "context-consumer-reference-v1",
                "key": key, "payload_digest": _payload_digest(key, payload)}
            project_context_market(payload, reference, next(iter(payload["base"]["markets"])))
