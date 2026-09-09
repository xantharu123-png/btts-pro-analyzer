"""Real B1 sources plus synthetic B2 fits, never empirical release evidence."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError, digest
from context_models.offset import ContextModelError
from context_models.tennis_effect import apply_tennis_effect, tennis_context_result
from context_snapshots import compute_once
from context_transport import calculate_context_payload, context_payload_key, replay_context_payload
from test_context_tennis_capture import NOW, competition, persist, records
from test_tennis_context_model import artifact, base, event


def case(tmp_path, family="tennis:winner"):
    from context_models.tennis_v3 import tennis_features_v3
    from context_sources.tennis_status import tennis_observations_as_of
    db = tmp_path / "v3-model.db"
    for match, player, opponent, hours in (("101", "1", "9", 2), ("102", "2", "8", 1)):
        raw = competition(id=match)
        raw["competitors"][0]["id"], raw["competitors"][1]["id"] = player, opponent
        at = NOW-timedelta(hours=hours)
        persist(db, records(raw, clock=at), clock=at)
    observations = tennis_observations_as_of(db, cutoff=NOW, tour="ATP")
    original, ev = base(family=family), event()
    feats = tennis_features_v3(ev, observations, original, cutoff=NOW)
    fitted = artifact(original, feats, ev)
    fitted.update(feature_version="tennis-performed-load-v3", feature_names=["observed_recovery_minimum_hours_delta"],
        model_variant="tennis-winner-status-load-antisymmetric-v1" if family == "tennis:winner" else
        "tennis-serve-status-load-mirrored-iidsets-holdproxy-tb7-strict-v1")
    return db, ev, original, feats, fitted, observations


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
def test_actual_paired_status_input_fitted_b2_comparison_is_not_used_without_approval(tmp_path, family):
    db, ev, original, feats, fitted, observations = case(tmp_path, family)
    assert feats["values"]["observed_recovery_minimum_hours_delta"] == 1.
    assert feats["values"]["observed_recovery_exact_hours_delta"] is None
    comparison = apply_tennis_effect(original, feats, fitted, event=ev)
    assert comparison["markets"]["winner_a"] != original["markets"]["winner_a"]
    envelope = {"kind": "context-effect-v1", "payload": fitted}
    answer = tennis_context_result(original, feats, envelope, event=ev, effect_hash=digest(envelope))
    assert answer["role"] == "experimental" and answer["used_markets"] == original["markets"]
    assert answer["used_params"] == original["params"] and answer["approval_hash"] is None
    assert answer["certified_markets"] == []
    payload = calculate_context_payload(event=ev, base=original, features=feats,
        observation_refs=sorted(row["digest"] for row in observations), preprocessing_refs=[],
        effect_artifact=envelope, effect_hash=digest(envelope), approval=None)
    key = context_payload_key(payload)
    assert replay_context_payload(payload, key=key, effect_artifact=envelope, approval=None) == payload
    count = []
    def run():
        count.append(1)
        return deepcopy(payload)
    assert compute_once(db, key, run) == compute_once(db, key, run)
    assert len(count) == 1


def test_v2_effect_cannot_be_silently_relabelled_for_status_v3(tmp_path):
    _, ev, original, feats, fitted, _ = case(tmp_path)
    fitted["feature_version"] = "tennis-performed-load-v2"
    with pytest.raises(ContextModelError):
        apply_tennis_effect(original, feats, fitted, event=ev)
    fitted["feature_version"] = "tennis-performed-load-v3"
    fitted["model_variant"] = "tennis-winner-performed-load-antisymmetric-v1"
    with pytest.raises(ContextModelError):
        apply_tennis_effect(original, feats, fitted, event=ev)


@pytest.mark.parametrize("change", ["schedule", "participants", "tour", "surface", "indoor", "base"])
def test_original_full_event_and_base_binding_cannot_reuse_v3_features(tmp_path, change):
    _, ev, original, feats, fitted, observations = case(tmp_path)
    if change == "schedule":
        ev.update(scheduled_start="2026-09-09T19:00:00.000000Z", schedule_revision="s2")
    elif change == "participants":
        ev["home_id"], ev["away_id"] = ev["away_id"], ev["home_id"]
    elif change == "tour":
        ev["tour"] = "WTA"
    elif change == "surface":
        ev["surface"] = "Clay"
    elif change == "indoor":
        ev["indoor"] = True
    else:
        original["params"]["p_a"] = .55
        original["markets"] = {"winner_a": .55, "winner_b": .45}
    with pytest.raises(ContextContractError):
        calculate_context_payload(event=ev, base=original, features=feats,
            observation_refs=sorted(row["digest"] for row in observations), preprocessing_refs=[],
            effect_artifact=None, effect_hash=None, approval=None)


def test_v3_does_not_accept_unowned_preprocessing_or_price_input(tmp_path):
    _, ev, original, feats, _, observations = case(tmp_path)
    args = dict(event=ev, base=original, features=feats, observation_refs=sorted(row["digest"] for row in observations),
                preprocessing_refs=[], effect_artifact=None, effect_hash=None, approval=None)
    with pytest.raises(ContextContractError):
        calculate_context_payload(**{**args, "preprocessing_refs": ["a"*64]})
    with pytest.raises(ContextContractError):
        calculate_context_payload(**{**args, "features": {**feats, "odds": 4.2}})


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
def test_v3_actual_receipt_counterpart_retains_the_mirrored_comparison_law(tmp_path, family):
    from context_models.tennis_v3 import tennis_features_v3
    from context_models.tennis_effect import tennis_serve_markets
    _, ev, original, feats, fitted, observations = case(tmp_path, family)
    first = apply_tennis_effect(original, feats, fitted, event=ev)
    ev["home_id"], ev["away_id"] = ev["away_id"], ev["home_id"]
    if family == "tennis:winner":
        original["params"]["p_a"] = 1-original["params"]["p_a"]
        original["markets"]["winner_a"], original["markets"]["winner_b"] = original["markets"]["winner_b"], original["markets"]["winner_a"]
    else:
        original["params"]["hold_a"], original["params"]["hold_b"] = original["params"]["hold_b"], original["params"]["hold_a"]
        original["markets"] = tennis_serve_markets(original["params"])
    opposite = tennis_features_v3(ev, observations, original, cutoff=NOW)
    assert opposite["values"]["observed_recovery_minimum_hours_delta"] == -feats["values"]["observed_recovery_minimum_hours_delta"]
    second = apply_tennis_effect(original, opposite, fitted, event=ev)
    assert first["markets"]["winner_a"] + second["markets"]["winner_a"] == pytest.approx(1., abs=1e-12)
