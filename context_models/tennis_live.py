"""Pure original live-winner identity, not a native historical state resolver.

No file/database access, fitting, source call or probability recalculation here.
The owning worker verifies the actual A1 model and B1 current-event receipts.
"""
from copy import deepcopy
import re

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest, require_digest,
    require_number, require_object, require_text, validate_base_distribution, validate_event,
)
from model_artifacts import canonical_bytes

BASE_VERSION = "tennis-live-calibrated-winner-v1"
ORIGIN_KIND = "tennis-live-winner-origin-v1"
ORIGINAL_ARTIFACT_KIND = "tennis-live-winner-original-v1"
SIDECAR_KIND = "tennis-live-winner-context-v1"
CODE_PATHS = ("tennis/predict.py", "tennis/model_state.py", "tennis/elo.py",
              "tennis/serve_model.py", "tennis/simulator.py", "tennis/data_loader.py")
MARKETS = {"A": "winner_a", "B": "winner_b"}


def _exact(a, b):
    return canonical_bytes(a) == canonical_bytes(b)


def live_event(value):
    event = validate_event(value)
    tour = event.get("tour")
    if (event["sport"] != "tennis" or event["format"] != "singles" or tour not in {"ATP", "WTA"}
            or event["status"] != "scheduled"):
        raise ContextContractError("live winner requires a native scheduled singles tour event")
    if re.fullmatch(rf"espn:tennis:{tour}:match:[1-9][0-9]*", event["event_key"]) is None:
        raise ContextContractError("live winner has no native ESPN match identity")
    if re.fullmatch(rf"espn:{tour}:tournament:[1-9][0-9]*(?:-[1-9][0-9]*)?", event["competition"]) is None:
        raise ContextContractError("live winner has no native ESPN tournament identity")
    for side in ("home_id", "away_id"):
        if re.fullmatch(rf"espn:tennis:{tour}:player:[1-9][0-9]*", event[side]) is None:
            raise ContextContractError("live winner has no native current player identity")
    require_digest(event["schedule_revision"], "actual schedule revision")
    # This exact v1 relies on status-v1, which does not project native
    # surface/indoor metadata. Executed model inputs remain separate below.
    if ("surface" not in event or "indoor" not in event
            or event["surface"] is not None or event["indoor"] is not None):
        raise ContextContractError("status-v1 does not establish native environment metadata")
    if event["schedule_revision"] != digest({"event_key": event["event_key"], "scheduled_start": event["scheduled_start"]}):
        raise ContextIntegrityError("live schedule does not match its native status revision")
    if not _exact(event, value):
        raise ContextContractError("live event must be canonical")
    return deepcopy(event)


def validate_live_winner_reference(value, history_refs):
    require_object(value, {"schema", "kind", "event", "cutoff", "state_hash", "native_receipt",
        "native_observed_at", "competition_revision", "native_state_identity", "code_hashes", "inputs", "values"},
        label="live original winner reference")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != ORIGIN_KIND:
        raise ContextContractError("unknown live winner original version")
    if history_refs != [] or type(history_refs) is not list or value["native_state_identity"] != "unresolved":
        raise ContextContractError("live original does not establish native historical state identities")
    event = live_event(value["event"])
    for field in ("cutoff", "native_observed_at"):
        if type(value[field]) is not str or canonical_timestamp(value[field]) != value[field]:
            raise ContextContractError("live original clock must be canonical")
    if not value["native_observed_at"] <= value["cutoff"] < event["scheduled_start"]:
        raise ContextIntegrityError("original decision precedes actual input or follows scheduled start")
    for field in ("state_hash", "native_receipt", "competition_revision"):
        require_digest(value[field], field)
    hashes = require_object(value["code_hashes"], set(CODE_PATHS), label="actual original code identity")
    for code_hash in hashes.values():
        require_digest(code_hash, "original source code hash")
    inputs = require_object(value["inputs"], {"player_a", "player_b", "state_key_a", "state_key_b",
        "surface", "best_of", "tour", "indoor"}, label="actual original prediction inputs")
    for field in ("player_a", "player_b", "state_key_a", "state_key_b"):
        require_text(inputs[field], field)
    if inputs["player_a"] == inputs["player_b"] or inputs["state_key_a"] == inputs["state_key_b"]:
        raise ContextContractError("original calculation participants must remain distinct")
    if (inputs["tour"] != event["tour"] or inputs["surface"] not in (None, "Hard", "Clay", "Grass", "Carpet")
            or type(inputs["best_of"]) is not int or inputs["best_of"] not in {3, 5}
            or inputs["indoor"] is not None and type(inputs["indoor"]) is not bool):
        raise ContextContractError("invalid original tour/environment/calculation format")
    # The executed legacy best_of may be a catalog assumption. It does not
    # change the current Event's intentionally winner-only singles format.
    values = require_object(value["values"], {"p_a_raw", "p_a_cal", "p_b_cal"}, label="direct original probabilities")
    for number in values.values():
        require_number(number, "original probability", minimum=0, maximum=1)
    if not _exact(values["p_b_cal"], 1-values["p_a_cal"]):
        raise ContextIntegrityError("original winner complement differs")
    return deepcopy(value)


def validate_live_winner_origin(base, event=None):
    """Exact ORIGINAL only, never a comparison disguised as original output."""
    original = validate_base_distribution(base)
    if original["version"] != BASE_VERSION or original["family"] != "tennis:winner":
        raise ContextContractError("this identity validator accepts only its original live winner version")
    ref = validate_live_winner_reference(original["reference_weights"], original["history_refs"])
    if event is not None and not _exact(live_event(event), ref["event"]):
        raise ContextIntegrityError("original and supplied current Event differ")
    values = ref["values"]
    expected = {"event_key": ref["event"]["event_key"], "model_hash": ref["state_hash"], "cutoff": ref["cutoff"],
        "params": {"p_a": values["p_a_cal"]}, "markets": {"winner_a": values["p_a_cal"], "winner_b": values["p_b_cal"]}}
    if any(not _exact(original[field], content) for field, content in expected.items()) or not _exact(original, base):
        raise ContextIntegrityError("original live winner inputs/parameters/markets differ")
    return deepcopy(original)


def original_base(origin):
    origin = validate_live_winner_reference(origin, [])
    values = origin["values"]
    return validate_live_winner_origin({"version": BASE_VERSION, "model_hash": origin["state_hash"],
        "event_key": origin["event"]["event_key"], "cutoff": origin["cutoff"], "family": "tennis:winner",
        "params": {"p_a": values["p_a_cal"]}, "markets": {"winner_a": values["p_a_cal"], "winner_b": values["p_b_cal"]},
        "history_refs": [], "reference_weights": origin})


def validate_original_publication(payload, *, created_at):
    require_object(payload, {"schema", "origin"}, label="original publication")
    if type(payload["schema"]) is not int or payload["schema"] != 1:
        raise ContextContractError("unknown original publication schema")
    origin = validate_live_winner_reference(payload["origin"], [])
    if canonical_timestamp(created_at) < origin["cutoff"]:
        raise ContextIntegrityError("original publication cannot precede its actual calculation")
    return deepcopy(payload)


def validate_context_model(value):
    require_object(value, {"schema", "kind", "reference", "event", "cutoff", "markets", "original_artifact_hash"},
                   label="revision-bound live winner context")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != SIDECAR_KIND:
        raise ContextContractError("unknown live context sidecar")
    event = live_event(value["event"])
    if (type(value["cutoff"]) is not str or canonical_timestamp(value["cutoff"]) != value["cutoff"]
            or value["cutoff"] >= event["scheduled_start"] or not _exact(value["markets"], MARKETS)):
        raise ContextContractError("live context decision or market orientation differs")
    ref = require_object(value["reference"], {"schema", "kind", "key", "payload_digest"}, label="context reference")
    if type(ref["schema"]) is not int or ref["schema"] != 1 or ref["kind"] != "context-consumer-reference-v1":
        raise ContextContractError("unknown shared context reference")
    for field in ("key", "payload_digest"):
        require_digest(ref[field], field)
    require_digest(value["original_artifact_hash"], "original publication identity")
    return deepcopy(value)
