"""Unrounded same-call legacy E-sport transport, NOT native source evidence.

Capture/form checks do not execute Elo, a history selector or a predictor.
Only the explicitly named offline replay recomputes the legacy recipe. Raw
non-JSON inputs are marked unavailable, never stringified or made healthy.
No B1/C4/consumer/runtime capability is registered by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import math

from model_artifacts import canonical_bytes
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    require_object,
)

KIND = "esports-live-original-v1"
PROJECTION = "esports-legacy-input-projection-v1"
RECIPE = "subgraph-elo-post-iid-series-v1"
EVENT_FIELDS = frozenset({"game_id", "match_id", "id", "game", "team1", "team2", "team1_id", "team2_id",
                         "status", "begin_at", "team1_score", "team2_score", "series_type"})
STATS_FIELDS = frozenset({"matches", "wins"})
HISTORY_FIELDS = frozenset({"match_id", "begin_at", "end_at", "opponent_id", "won", "number_of_games"})
CONSUMED_FIELDS = (
    "team1_id", "team2_id", "score1", "score2", "series_type", "maps_to_win",
    "matches1", "matches2", "wins1", "wins2", "reported_matches1", "reported_matches2",
    "reported_wins1", "reported_wins2", "is_prematch", "scheduled_start",
)
OUTPUT_FIELDS = (
    "elo1", "elo2", "subgraph_size", "team1_series_probability", "team1_map_probability",
    "team1_live_probability", "point_probability", "conservative_series_probability",
    "conservative_map_probability", "conservative_live_probability", "adjusted_probability",
    "probability_percent", "haircut",
)


def _same(a, b):
    try:
        return canonical_bytes(a) == canonical_bytes(b)
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise ContextContractError("original comparison requires canonical JSON values") from exc


def _constants():
    # This identifies the unchanged legacy law, not estimated coefficients.
    return {"base": 1500.0, "scale": 400.0, "k_factor": 40.0,
            "bo1_multiplier": .75, "iterations": 2, "history_window": 20,
            "map_inversion_steps": 70, "uncertainty_elo": 150.0,
            "heuristic_percentage_points": 5.0}


def _cell(value):
    if type(value) in (type(None), bool, int, float, str):
        try:
            canonical_bytes(value)
        except (ValueError, OverflowError, UnicodeError):
            pass
        else:
            return {"kind": "value", "value": value}
    # Never repr(object), arbitrary nested provider/price dictionaries, or
    # runtime class names. Unsupported values cannot be replayed from JSON.
    return {"kind": "unavailable", "reason": "non-json-legacy-value"}


def _record(value, fields):
    if type(value) is dict:
        return {"kind": "object", "values": {key: _cell(value[key]) for key in sorted(fields) if key in value}}
    return {"kind": "other", "value": _cell(value)}


def project_esports_inputs(match):
    """Price-free projection before calculation; missing is not JSON null."""
    histories = {}
    for side in ("team1", "team2"):
        value = match.get(side + "_history")
        histories[side] = ({"kind": "list", "items": [_record(row, HISTORY_FIELDS) for row in value]}
                           if type(value) is list else {"kind": "other", "value": _cell(value)})
    return {"version": PROJECTION, "event": _record(match, EVENT_FIELDS),
            "stats": {side: _record(match.get(side + "_stats"), STATS_FIELDS) for side in ("team1", "team2")},
            "history": histories}


def _validate_cell(value):
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise ContextContractError("original field requires a typed primitive cell")
    if value.get("kind") == "value":
        require_object(value, {"kind", "value"}, label="original primitive")
        if not _same(_cell(value["value"]), value):
            raise ContextContractError("original primitive is not transportable")
    else:
        require_object(value, {"kind", "reason"}, label="unavailable original primitive")
        if value != {"kind": "unavailable", "reason": "non-json-legacy-value"}:
            raise ContextContractError("unknown original unavailability marker")


def _validate_record(value, fields):
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise ContextContractError("original record requires an object")
    if value.get("kind") == "object":
        require_object(value, {"kind", "values"}, label="original record")
        require_object(value["values"], set(), optional=fields, label="allowlisted original fields")
        for cell in value["values"].values():
            _validate_cell(cell)
    else:
        require_object(value, {"kind", "value"}, label="non-object original record")
        if value["kind"] != "other":
            raise ContextContractError("unknown original record shape")
        _validate_cell(value["value"])


def _validate_inputs(value):
    require_object(value, {"version", "event", "stats", "history"}, label="original input projection")
    if type(value["version"]) is not str or value["version"] != PROJECTION:
        raise ContextContractError("unknown original input projection version")
    _validate_record(value["event"], EVENT_FIELDS)
    for name in ("stats", "history"):
        require_object(value[name], {"team1", "team2"}, label="two original team inputs")
    for side in ("team1", "team2"):
        _validate_record(value["stats"][side], STATS_FIELDS)
        history = value["history"][side]
        if type(history) is not dict or type(history.get("kind")) is not str:
            raise ContextContractError("original history requires an object")
        if history.get("kind") == "list":
            require_object(history, {"kind", "items"}, label="raw original history positions")
            if type(history["items"]) is not list:
                raise ContextContractError("raw history positions require a list")
            for row in history["items"]:
                _validate_record(row, HISTORY_FIELDS)
        else:
            _validate_record(history, frozenset())


def _unavailable_paths(value, prefix="inputs"):
    if type(value) is dict:
        if value.get("kind") == "unavailable":
            return [prefix]
        return [path for key, item in sorted(value.items()) for path in _unavailable_paths(item, prefix + "/" + key)]
    if type(value) is list:
        return [path for index, item in enumerate(value) for path in _unavailable_paths(item, prefix + "/" + str(index))]
    return []


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ContextContractError(f"{label} requires an actual integer")


def _float(value, label, lower=None, upper=None):
    if type(value) is not float or not math.isfinite(value) or (lower is not None and value < lower) or (upper is not None and value > upper):
        raise ContextContractError(f"{label} requires a finite original float")


def validate_esports_original(value):
    """Closed form and hash checks only. This is NOT a fitted/source replay."""
    require_object(value, {"schema", "kind", "model_version", "recipe", "constants", "cutoff", "inputs",
        "inputs_hash", "consumed", "outputs", "source_evidence", "unavailable_inputs"}, label="same-call esports original")
    if (type(value["schema"]) is not int or any(type(value[key]) is not str for key in ("kind", "recipe", "model_version"))
            or value["schema"] != 1 or value["kind"] != KIND
            or value["recipe"] != RECIPE or value["model_version"] != "subgraph-elo-v3"):
        raise ContextContractError("unknown esports original recipe/version")
    if type(value["source_evidence"]) is not str or value["source_evidence"] != "unresolved":
        raise ContextContractError("captured legacy inputs cannot certify source evidence")
    if not _same(value["constants"], _constants()):
        raise ContextIntegrityError("original recipe constants differ")
    if type(value["cutoff"]) is not str or canonical_timestamp(value["cutoff"]) != value["cutoff"]:
        raise ContextContractError("original cutoff must be canonical and aware")
    _validate_inputs(value["inputs"])
    if value["inputs_hash"] != digest(value["inputs"]):
        raise ContextIntegrityError("original full input hash differs")
    if not _same(value["unavailable_inputs"], sorted(_unavailable_paths(value["inputs"]))):
        raise ContextIntegrityError("original unavailability inventory differs")
    consumed = require_object(value["consumed"], set(CONSUMED_FIELDS) | {"history_indices", "windows"}, label="actual consumed legacy values")
    for key in CONSUMED_FIELDS:
        item = consumed[key]
        if key.startswith("reported_") and item is None:
            continue
        if key == "is_prematch":
            if type(item) is not bool:
                raise ContextContractError("prematch flag requires bool")
        elif key == "scheduled_start":
            if item is not None and (type(item) is not str or canonical_timestamp(item) != item):
                raise ContextContractError("consumed schedule must be canonical or unknown")
        else:
            _integer(item, key)
    if (consumed["team1_id"] == consumed["team2_id"] or consumed["series_type"] < 1 or consumed["series_type"] % 2 != 1
            or consumed["maps_to_win"] != consumed["series_type"] // 2 + 1
            or max(consumed["score1"], consumed["score2"]) >= consumed["maps_to_win"]):
        raise ContextIntegrityError("consumed original identity/score/format differs")
    if consumed["is_prematch"] and (consumed["scheduled_start"] is None or consumed["scheduled_start"] <= value["cutoff"]
                                    or consumed["score1"] != 0 or consumed["score2"] != 0):
        raise ContextIntegrityError("consumed prematch decision is not before its start")
    for name in ("history_indices", "windows"):
        require_object(consumed[name], {"team1", "team2"}, label="two consumed histories")
    for index, side in enumerate(("team1", "team2"), 1):
        indices, window = consumed["history_indices"][side], consumed["windows"][side]
        if (type(indices) is not list or type(window) is not list or len(indices) != 20 or len(window) != 20
                or any(type(item) is not int or item < 0 for item in indices) or len(set(indices)) != 20
                or consumed[f"matches{index}"] != 20 or consumed[f"wins{index}"] > 20):
            raise ContextContractError("consumed history requires twenty distinct raw positions")
        history = value["inputs"]["history"][side]
        for position, item in zip(indices, window):
            _validate_record(item, HISTORY_FIELDS)
            if history["kind"] == "list" and (position >= len(history["items"]) or not _same(item, history["items"][position])):
                raise ContextIntegrityError("consumed row does not bind its actual raw position")
    outputs = require_object(value["outputs"], set(OUTPUT_FIELDS) | {"selection_side"}, label="unrounded original results")
    for key in OUTPUT_FIELDS:
        if key == "subgraph_size":
            _integer(outputs[key], key)
            if outputs[key] > 40:
                raise ContextIntegrityError("original subgraph exceeds both twenty-row windows")
        elif key in {"elo1", "elo2"}:
            _float(outputs[key], key)
        else:
            _float(outputs[key], key, 0., 100. if key in {"probability_percent", "haircut", "adjusted_probability"} else 1.)
    side = "team1" if outputs["team1_live_probability"] >= .5 else "team2"
    point = outputs["team1_live_probability"] if side == "team1" else 1. - outputs["team1_live_probability"]
    percent = point * 100.
    adjusted = max(0., min(point, outputs["conservative_live_probability"]) * 100. - 5.)
    if (type(outputs["selection_side"]) is not str or outputs["selection_side"] != side or not _same(outputs["point_probability"], point)
            or not _same(outputs["probability_percent"], percent) or not _same(outputs["adjusted_probability"], adjusted)
            or not _same(outputs["haircut"], percent - adjusted)):
        raise ContextIntegrityError("original selection or percent transport differs")
    return json.loads(canonical_bytes(value))


@dataclass(frozen=True, slots=True)
class EsportsOriginal:
    """Closed immutable JSON bytes; every exported dictionary is detached."""
    _payload: bytes

    def __post_init__(self):
        try:
            if type(self._payload) is not bytes:
                raise ContextContractError("original payload must be immutable bytes")
            value = json.loads(self._payload)
            checked = validate_esports_original(value)
            if canonical_bytes(checked) != self._payload:
                raise ContextContractError("original bytes must be canonical JSON")
        except ContextContractError:
            raise
        except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError) as exc:
            raise ContextContractError("invalid original JSON transport") from exc

    @classmethod
    def from_dict(cls, value):
        return cls(canonical_bytes(validate_esports_original(value)))

    @property
    def content_hash(self):
        return sha256(self._payload).hexdigest()

    def to_dict(self):
        return json.loads(self._payload)


def capture_esports_original(inputs, *, cutoff, history_indices, windows, consumed, outputs):
    """Only package values supplied from the actual owning calculation."""
    values = {key: consumed[key] for key in CONSUMED_FIELDS}
    if values["scheduled_start"] is not None:
        values["scheduled_start"] = canonical_timestamp(values["scheduled_start"])
    values["history_indices"] = {side: list(items) for side, items in zip(("team1", "team2"), history_indices)}
    values["windows"] = {side: [_record(row, HISTORY_FIELDS) for row in items] for side, items in zip(("team1", "team2"), windows)}
    result = {key: outputs[key] for key in OUTPUT_FIELDS}
    result["selection_side"] = "team1" if result["team1_live_probability"] >= .5 else "team2"
    return EsportsOriginal.from_dict({"schema": 1, "kind": KIND, "model_version": "subgraph-elo-v3", "recipe": RECIPE,
        "constants": _constants(), "cutoff": canonical_timestamp(cutoff), "inputs": inputs, "inputs_hash": digest(inputs),
        "consumed": values, "outputs": result, "source_evidence": "unresolved",
        "unavailable_inputs": sorted(_unavailable_paths(inputs))})


def _restore_record(value):
    if value["kind"] == "object":
        return {key: cell["value"] for key, cell in value["values"].items()}
    return value["value"]["value"]


def replay_esports_original(original):
    """Explicit offline recipe replay. Never called by capture or a worker."""
    value = validate_esports_original(original.to_dict() if isinstance(original, EsportsOriginal) else original)
    if value["unavailable_inputs"]:
        raise ContextContractError("offline replay unavailable for nontransportable legacy inputs")
    inputs = value["inputs"]
    match = _restore_record(inputs["event"])
    if type(match) is not dict:
        raise ContextIntegrityError("offline original event is not a replayable object")
    for side in ("team1", "team2"):
        match[side + "_stats"] = _restore_record(inputs["stats"][side])
        history = inputs["history"][side]
        match[side + "_history"] = ([_restore_record(row) for row in history["items"]]
                                    if history["kind"] == "list" else _restore_record(history))
    from multi_sport_recommendations import esports_match_winner_candidate
    try:
        replay = esports_match_winner_candidate(match, now=datetime.fromisoformat(value["cutoff"]), capture_original=True)["original"]
    except ContextContractError:
        raise
    except (TypeError, ValueError, AttributeError, OverflowError) as exc:
        raise ContextIntegrityError("original inputs cannot produce the claimed legacy calculation") from exc
    if replay is None or not _same(replay.to_dict(), value):
        raise ContextIntegrityError("captured original does not replay from its complete original inputs")
    return value
