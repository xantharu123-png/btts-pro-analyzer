"""Closed INTERNAL basketball transport, not an ESPN injury/roster adapter.

One receipt owns the full native event/team collection revision. A successful
score endpoint cannot populate this transport. Regulation rotation is measured
in player minutes; inclusive-OT workload is a separately reported quantity.
Expected minutes describe a source projection, never participation certainty.
No network I/O, source-time inference, medical diagnosis or default OT minutes.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from math import fsum

from context_models.contracts import (
    ContextContractError, OBSERVATION_FIELDS, canonical_timestamp, digest,
    normalize_observation, require_list, require_number, require_object,
)
from context_models.team_sports import FORMATS, _scope, basketball_event, native_subject

SCHEMA = "basketball-internal-context-v1"
KINDS = {"appearance", "rotation", "availability"}
AVAILABILITY = {"available", "out", "questionable", "unknown"}


def _time(value):
    if type(value) is not str:
        raise ContextContractError("basketball source time must be an actual aware string")
    return canonical_timestamp(value)


def _minutes(value, maximum):
    if value is not None:
        require_number(value, "reported player minutes", minimum=0, maximum=maximum)
    return value


def _team(value, *, source, kind, regulation, inclusive, seen):
    require_object(value, {"complete", "collection", "players"}, label="whole team rotation")
    if type(value["complete"]) is not bool or type(value["collection"]) is not str or value["collection"] not in {"full_rotation", "full_roster", "partial"}:
        raise ContextContractError("team collection requires explicit coverage")
    required = "full_roster" if kind == "availability" else "full_rotation"
    if value["complete"] and value["collection"] != required:
        raise ContextContractError("active roster or starting five is not a whole rotation")
    players = require_list(value["players"], "native roster")
    if len(players) > 100 or (value["complete"] and len(players) < 5):
        raise ContextContractError("invalid whole basketball roster size")
    clean = []
    keys = {"player_id", "regulation_minutes", "inclusive_minutes"} if kind == "appearance" else (
        {"player_id", "regulation_minutes", "availability"} if kind == "rotation" else {"player_id", "availability"})
    for player in players:
        require_object(player, keys, label="reported native basketball player")
        player = deepcopy(player)
        native_subject(player["player_id"], source, "player")
        if player["player_id"] in seen:
            raise ContextContractError("a player occurs more than once in the joint event revision")
        seen.add(player["player_id"])
        if kind != "appearance" and (type(player["availability"]) is not str or player["availability"] not in AVAILABILITY):
            raise ContextContractError("unreviewed availability state")
        if kind != "availability":
            minutes = _minutes(player["regulation_minutes"], regulation)
            if kind == "rotation":
                if player["availability"] in {"questionable", "unknown"} and minutes is not None:
                    raise ContextContractError("uncertain participation has no silently assumed minutes")
                if player["availability"] == "out" and minutes not in (None, 0):
                    raise ContextContractError("an explicitly out projection cannot assign positive minutes")
            else:
                total = _minutes(player["inclusive_minutes"], inclusive)
                if minutes is not None and total is not None and total < minutes:
                    raise ContextContractError("inclusive load cannot be less than regulation load")
        clean.append(player)
    clean.sort(key=lambda item: item["player_id"])
    for field, total in (("regulation_minutes", regulation * 5), ("inclusive_minutes", None if inclusive is None else inclusive * 5)):
        if kind == "availability" or (field == "inclusive_minutes" and kind != "appearance"):
            continue
        values = [player[field] for player in clean]
        if value["complete"] and values and all(item is not None for item in values) and total is not None and fsum(values) != total:
            raise ContextContractError("complete rotation does not conserve actual team player minutes")
    return {"complete": value["complete"], "collection": value["collection"], "players": clean}


def normalize_basketball_context(event: dict, rows: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]:
    """Normalize explicit internal envelopes, assigning no archival source proof."""
    if type(rows) is not tuple or not isinstance(observed_at, datetime):
        raise ContextContractError("basketball source input needs a tuple and actual ingestion time")
    target = basketball_event(event)
    receipt = canonical_timestamp(observed_at)
    output = []
    for raw in rows:
        require_object(raw, {"schema", "source_schema", "kind", "event", "season", "rules", "valid_from", "valid_until", "data"}, label="basketball internal transport")
        if type(raw["schema"]) is not int or raw["schema"] != 1 or raw["source_schema"] != SCHEMA or type(raw["kind"]) is not str or raw["kind"] not in KINDS:
            raise ContextContractError("unknown internal basketball source version or kind")
        event = basketball_event(raw["event"])
        if event["format"] != target["format"] or event["competition"] != target["competition"]:
            raise ContextContractError("basketball source response belongs to another rule/competition scope")
        if raw["kind"] != "appearance" and event != target:
            raise ContextContractError("current rotation/availability belongs to another complete event revision")
        scope = _scope({"season": raw["season"], "rules": raw["rules"]}, event["format"])
        source = FORMATS[event["format"]][0]
        kind, data = raw["kind"], deepcopy(raw["data"])
        required = {"teams", "actual_start", "actual_end", "result_observed_at", "overtime_periods"} if kind == "appearance" else (
            {"teams", "status"} if kind == "rotation" else {"teams"})
        require_object(data, required, label="joint basketball source data")
        regulation = scope["rules"]["regulation_minutes"]
        inclusive = None
        if kind == "appearance":
            if event["status"] not in {"completed", "cancelled"}:
                raise ContextContractError("appearance must be a reported completion or explicit withdrawal")
            data["result_observed_at"] = _time(data["result_observed_at"])
            if data["result_observed_at"] > receipt:
                raise ContextContractError("terminal result receipt cannot be in the future")
            for clock in ("actual_start", "actual_end"):
                data[clock] = None if data[clock] is None else _time(data[clock])
                if data[clock] is not None and data[clock] > data["result_observed_at"]:
                    raise ContextContractError("actual play cannot follow terminal result receipt")
            if data["actual_start"] is not None and data["actual_end"] is not None and data["actual_start"] >= data["actual_end"]:
                raise ContextContractError("actual basketball end must follow actual start")
            overtime = data["overtime_periods"]
            if overtime is not None:
                if type(overtime) is not int or not 0 <= overtime <= 100:
                    raise ContextContractError("overtime count must be an actual nonnegative integer")
                inclusive = regulation + overtime * scope["rules"]["overtime_period_minutes"]
        elif event["status"] != "scheduled":
            raise ContextContractError("future rotation/availability belongs to a scheduled event")
        if kind == "rotation" and (type(data["status"]) is not str or data["status"] not in {"expected", "confirmed"}):
            raise ContextContractError("current rotation needs an explicit projection identity")
        require_object(data["teams"], {event["home_id"], event["away_id"]}, label="whole native event participants")
        seen = set()
        data["teams"] = {team: _team(value, source=source, kind=kind, regulation=regulation, inclusive=inclusive, seen=seen)
                         for team, value in sorted(data["teams"].items())}
        if kind == "appearance" and event["status"] == "cancelled" and (
            data["actual_start"] is not None or data["actual_end"] is not None or data["overtime_periods"] is not None
            or any(team["complete"] or team["players"] for team in data["teams"].values())):
            raise ContextContractError("withdrawal cannot assert completed player load")
        complete = all(team["complete"] for team in data["teams"].values())
        if kind != "availability":
            fields = ("regulation_minutes", "inclusive_minutes") if kind == "appearance" else ("regulation_minutes",)
            complete &= all(player[field] is not None for team in data["teams"].values() for player in team["players"] for field in fields)
        payload = {"schema": 1, "source_schema": SCHEMA, "kind": kind, "event": event,
                   **scope, "status": event["status"] if kind == "appearance" else data.get("status", "reported"), "data": data}
        output.append(normalize_observation({
            "event_key": event["event_key"], "sport": "basketball", "competition": event["competition"], "format": event["format"],
            "subject_id": event["event_key"], "kind": "workload" if kind == "appearance" else "availability" if kind == "availability" else "expected_lineup" if data["status"] == "expected" else "confirmed_lineup",
            "source": source, "source_schema": SCHEMA, "source_revision": digest(payload), "schedule_revision": event["schedule_revision"],
            "published_at": None, "publication_proof": None, "valid_from": _time(raw["valid_from"]),
            "valid_until": None if raw["valid_until"] is None else _time(raw["valid_until"]), "complete": complete, "payload": payload,
        }, observed_at=observed_at))
    return tuple(output)


def validate_basketball_receipt(row):
    """Reconstruct the closed source projection; B1 separately verifies receipt."""
    payload = row["payload"]
    require_object(payload, {"schema", "source_schema", "kind", "event", "season", "rules", "status", "data"}, label="basketball stored source projection")
    raw = {key: deepcopy(value) for key, value in payload.items() if key != "status"}
    raw.update(valid_from=row["valid_from"], valid_until=row["valid_until"])
    replay = normalize_basketball_context(raw["event"], (raw,), observed_at=datetime.fromisoformat(row["observed_at"]))[0]
    if replay != {key: row[key] for key in OBSERVATION_FIELDS}:
        raise ContextContractError("stored basketball source projection changed")
    return payload
