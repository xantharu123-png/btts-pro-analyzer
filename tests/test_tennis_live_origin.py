"""Exact original winner transport, not native historical/effect certification."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import math

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp, digest, validate_base_distribution
from model_artifacts import canonical_bytes

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def origin():
    from context_models.tennis_live import CODE_PATHS, ORIGIN_KIND
    event = {"event_key": "espn:tennis:ATP:match:201", "sport": "tennis",
        "competition": "espn:ATP:tournament:189-2026", "format": "singles",
        "home_id": "espn:tennis:ATP:player:1", "away_id": "espn:tennis:ATP:player:2",
        "scheduled_start": canonical_timestamp(NOW + timedelta(hours=5)),
        "schedule_revision": "a" * 64, "status": "scheduled", "tour": "ATP", "surface": None, "indoor": None}
    event["schedule_revision"] = digest({"event_key": event["event_key"], "scheduled_start": event["scheduled_start"]})
    return {"schema": 1, "kind": ORIGIN_KIND, "event": event, "cutoff": canonical_timestamp(NOW),
        "state_hash": "b" * 64, "native_receipt": "c" * 64,
        "native_observed_at": canonical_timestamp(NOW-timedelta(seconds=2)),
        "competition_revision": "d" * 64, "native_state_identity": "unresolved",
        "code_hashes": {path: "e" * 64 for path in CODE_PATHS},
        "inputs": {"player_a": "Alpha A", "player_b": "Beta B", "state_key_a": "alpha a",
            "state_key_b": "beta b", "surface": "Hard", "best_of": 3, "tour": "ATP", "indoor": None},
        "values": {"p_a_raw": .617382761092, "p_a_cal": .623419378613, "p_b_cal": 1-.623419378613}}


def base():
    from context_models.tennis_live import BASE_VERSION
    ref = origin()
    p = ref["values"]["p_a_cal"]
    return {"version": BASE_VERSION, "model_hash": ref["state_hash"], "event_key": ref["event"]["event_key"],
        "cutoff": ref["cutoff"], "family": "tennis:winner", "params": {"p_a": p},
        "markets": {"winner_a": p, "winner_b": ref["values"]["p_b_cal"]}, "history_refs": [], "reference_weights": ref}


def test_original_preserves_every_nonrounded_value_and_default_contract_is_detached():
    from context_models.tennis_live import validate_live_winner_origin
    original = base()
    checked = validate_live_winner_origin(original, event=original["reference_weights"]["event"])
    assert canonical_bytes(checked) == canonical_bytes(original)
    assert canonical_bytes(validate_base_distribution(original)) == canonical_bytes(original)
    checked["reference_weights"]["inputs"]["surface"] = "Clay"
    assert original["reference_weights"]["inputs"]["surface"] == "Hard"


@pytest.mark.parametrize("field,value", [
    ("schema", True), ("native_state_identity", "verified_native"), ("state_hash", "bad"),
    ("cutoff", "2026-09-09T12:00:00"),
    ("native_observed_at", "2026-09-09T12:00:00.000001Z"),
    ("competition_revision", None), ("native_receipt", 0),
])
def test_origin_rejects_bad_clock_native_claim_or_identity(field, value):
    from context_models.tennis_live import validate_live_winner_reference
    ref = origin()
    ref[field] = value
    with pytest.raises(ContextContractError):
        validate_live_winner_reference(ref, [])


@pytest.mark.parametrize("field,value", [
    ("p_a_raw", True), ("p_a_cal", float("nan")), ("p_a_cal", "0.62"),
    ("p_b_cal", .4), ("p_b_cal", math.nextafter(1-.623419378613, 1.)),
])
def test_original_values_are_exact_numeric_and_complementary(field, value):
    from context_models.tennis_live import validate_live_winner_reference
    ref = origin()
    ref["values"][field] = value
    with pytest.raises(ContextContractError):
        validate_live_winner_reference(ref, [])


@pytest.mark.parametrize("mutation", [
    lambda b: b.update(model_hash="f"*64),
    lambda b: b.update(version="tennis-context-comparison-v1"),
    lambda b: b.update(cutoff=canonical_timestamp(NOW-timedelta(seconds=1))),
    lambda b: b["params"].update(p_a=math.nextafter(b["params"]["p_a"], 1.)),
    lambda b: b["markets"].update(winner_a=math.nextafter(b["markets"]["winner_a"], 1.)),
    lambda b: b["markets"].update(winner_b=math.nextafter(b["markets"]["winner_b"], 1.)),
])
def test_original_binding_cannot_borrow_comparison_label_or_ulp(mutation):
    from context_models.tennis_live import validate_live_winner_origin
    original = base()
    mutation(original)
    with pytest.raises(ContextContractError):
        validate_live_winner_origin(original)


@pytest.mark.parametrize("field,value", [("home_id", "espn:tennis:ATP:player:9"),
    ("surface", "Clay"), ("schedule_revision", "f"*64), ("indoor", True),
    ("competition", "espn:ATP:tournament:888-2026")])
def test_supplied_full_event_must_equal_original(field, value):
    from context_models.tennis_live import validate_live_winner_origin
    original = base()
    event = deepcopy(original["reference_weights"]["event"])
    event[field] = value
    with pytest.raises(ContextContractError):
        validate_live_winner_origin(original, event=event)


def test_no_native_historical_or_price_fields_can_be_injected():
    from context_models.tennis_live import validate_live_winner_reference
    for key in ("quote", "history_refs", "approval", "verified"):
        ref = origin()
        ref[key] = 1
        with pytest.raises(ContextContractError):
            validate_live_winner_reference(ref, [])


def test_predict_opt_in_is_same_call_and_default_dataclass_bytes_unchanged():
    from tennis.elo import SurfaceElo
    from tennis.model_state import ModelState
    from tennis.serve_model import ServeReturnModel
    from tennis.predict import predict_match
    elo = SurfaceElo()
    for _ in range(5):
        elo.update("alpha a", "beta b", "Hard")
    state = ModelState(elo, ServeReturnModel(), 1.0173, .00182, 800,
        (NOW-timedelta(days=1)).timestamp(), "2026-09-07", 0., tour_scope="ATP")
    original = predict_match(state, "Alpha A", "Beta B", "Hard", as_of=NOW)
    captures = []
    current = predict_match(state, "Alpha A", "Beta B", "Hard", as_of=NOW, original_capture=captures.append)
    assert asdict(current) == asdict(original)
    assert len(captures) == 1
    assert captures[0]["values"]["p_a_cal"] != current.p_a_cal
    assert round(captures[0]["values"]["p_a_cal"], 4) == current.p_a_cal
    assert captures[0]["values"]["p_b_cal"] == 1-captures[0]["values"]["p_a_cal"]
    assert captures[0]["inputs"]["state_key_a"] == "alpha a"


@pytest.mark.parametrize("field,value", [("surface", "Hard"), ("indoor", True),
    ("surface", "Clay"), ("schedule_revision", "a"*64), ("format", "singles_best_of_3")])
def test_current_origin_v1_cannot_claim_uncaptured_native_environment_or_rules(field, value):
    from context_models.tennis_live import validate_live_winner_reference
    ref = origin()
    ref["event"][field] = value
    with pytest.raises(ContextContractError):
        validate_live_winner_reference(ref, [])
