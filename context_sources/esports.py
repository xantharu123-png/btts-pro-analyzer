"""Closed INTERNAL native esports receipts, not a PandaScore live adapter.

One whole event/participant revision per fact; no row stitching, name joins,
publication backdating, inferred map durations or medical fatigue assertions.
"""
from copy import deepcopy
from datetime import datetime

from context_models.contracts import (
    ContextContractError, OBSERVATION_FIELDS, canonical_timestamp, digest,
    normalize_observation, require_list, require_object, require_text,
)
from context_models.esports import esports_event, esports_scope, native_identity

SCHEMA = "esports-internal-native-context-v1"
SUBJECT_VERSION = "esports-native-status-subject-v2"
KINDS = {"series", "observed_lineup", "lineup", "map", "patch_veto"}


def _time(value):
    if type(value) is not str:
        raise ContextContractError("esports actual source time must be an aware string")
    return canonical_timestamp(value)


def _teams(value, event):
    require_object(value, {event["home_id"], event["away_id"]}, label="whole native lineup participants")
    copied, seen = {}, set()
    for team, lineup in sorted(value.items()):
        require_object(lineup, {"complete", "players"}, label="whole native esports lineup")
        if type(lineup["complete"]) is not bool:
            raise ContextContractError("lineup source coverage requires an actual boolean")
        players = require_list(lineup["players"], "native lineup players")
        if len(players) > 100 or (lineup["complete"] and not players):
            raise ContextContractError("complete measured/scenario lineup cannot be empty")
        output = []
        for player in players:
            require_object(player, {"player_id", "participated", "stand_in"}, label="native lineup participation")
            native_identity(player["player_id"], "player")
            if player["player_id"] in seen:
                raise ContextContractError("one native player occurs twice in the joint lineup revision")
            seen.add(player["player_id"])
            for key in ("participated", "stand_in"):
                if player[key] is not None and type(player[key]) is not bool:
                    raise ContextContractError("participation/stand-in must be reported boolean or unknown")
            output.append(deepcopy(player))
        copied[team] = {"complete": lineup["complete"], "players": sorted(output, key=lambda row: row["player_id"])}
    return copied


def normalize_esports_context(event: dict, responses: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]:
    """Internal source mechanics only; no proof registry or provider request."""
    target = esports_event(event)
    if type(responses) is not tuple or not isinstance(observed_at, datetime):
        raise ContextContractError("esports normalization requires tuple and actual receipt datetime")
    receipt = canonical_timestamp(observed_at)
    output = []
    for raw in responses:
        require_object(raw, {"schema", "source_schema", "kind", "event", "scope", "valid_until", "data"}, label="internal esports source")
        if (type(raw["schema"]) is not int or raw["schema"] != 1 or raw["source_schema"] != SCHEMA
                or type(raw["kind"]) is not str or raw["kind"] not in KINDS):
            raise ContextContractError("unreviewed internal esports source schema/kind")
        ev = esports_event(raw["event"])
        scope = esports_scope(raw["scope"], ev)
        if ev["competition"] != target["competition"]:
            raise ContextContractError("native esports response belongs to another title/competition")
        kind, data = raw["kind"], deepcopy(raw["data"])
        status = "completed"
        if kind in {"lineup", "patch_veto"}:
            if ev != target or ev["status"] != "scheduled":
                raise ContextContractError("current esports context requires its exact scheduled event")
            status = "scheduled"
        elif kind == "map":
            if ev["status"] not in {"completed", "started", "cancelled"}:
                raise ContextContractError("map completion requires actual performed series state")
        elif ev["status"] not in {"completed", "cancelled"}:
            raise ContextContractError("historical esports fact is not a completed series")
        complete = True
        if kind in {"series", "map"}:
            fields = {"actual_start", "actual_end", "winner_id"} | ({"map_id"} if kind == "map" else {"score_a", "score_b"})
            require_object(data, fields, label="native performed series/map")
            for clock in ("actual_start", "actual_end"):
                data[clock] = None if data[clock] is None else _time(data[clock])
                if data[clock] is not None and data[clock] > receipt:
                    raise ContextContractError("reported performed time cannot follow actual receipt")
            if data["actual_start"] is not None and data["actual_end"] is not None and data["actual_start"] >= data["actual_end"]:
                raise ContextContractError("actual performed end must follow actual start")
            if kind == "map":
                native_identity(data["map_id"], "map")
            if ev["status"] == "cancelled":
                status, complete = "cancelled", False
                if any(data[key] is not None for key in fields - {"map_id"}):
                    raise ContextContractError("withdrawal cannot retain performed result/clock data")
            else:
                if data["winner_id"] is not None:
                    native_identity(data["winner_id"], "team")
                if data["winner_id"] is None:
                    complete = False
                elif data["winner_id"] not in {ev["home_id"], ev["away_id"]}:
                    raise ContextContractError("native winner must be an actual series participant")
                if kind == "series":
                    a, b, needed = data["score_a"], data["score_b"], scope["rules"]["best_of"] // 2 + 1
                    if data["winner_id"] is None:
                        if a is not None or b is not None:
                            raise ContextContractError("partial series outcome cannot invent a winner from ambiguous scores")
                    elif (type(a) is not int or type(b) is not int or min(a, b) < 0
                        or max(a, b) != needed or min(a, b) >= needed
                        or data["winner_id"] != ev["home_id" if a > b else "away_id"]):
                        raise ContextContractError("native series result and actual best-of/winner differ")
        elif kind in {"observed_lineup", "lineup"}:
            require_object(data, {"status", "teams"}, label="native observed or explicit scenario lineup")
            allowed = {"observed"} if kind == "observed_lineup" else {"candidate", "confirmed"}
            if type(data["status"]) is not str or data["status"] not in allowed:
                raise ContextContractError("team roster is not a measured lineup or explicit current scenario")
            data["teams"] = _teams(data["teams"], ev)
            complete = all(team["complete"] and all(player["participated"] is not None for player in team["players"])
                           for team in data["teams"].values())
            if ev["status"] == "cancelled":
                if any(team["complete"] or team["players"] for team in data["teams"].values()):
                    raise ContextContractError("withdrawn lineup cannot retain observed participation")
                status, complete = "cancelled", False
        else:
            require_object(data, {"patch_id", "veto"}, label="reported patch/veto")
            if data["patch_id"] is not None:
                require_text(data["patch_id"], "reported native patch", code=True)
            if data["veto"] is not None:
                for identity in require_list(data["veto"], "reported ordered veto"):
                    native_identity(identity, "map_type")
                if len(set(data["veto"])) != len(data["veto"]):
                    raise ContextContractError("duplicate native map type in veto")
            complete = data["patch_id"] is not None and data["veto"] is not None
        valid_until = None if raw["valid_until"] is None else _time(raw["valid_until"])
        payload = {"schema": 1, "source_schema": SCHEMA, "kind": kind, "event": ev, "scope": scope, "status": status, "data": data}
        identity = digest({"version": SUBJECT_VERSION,
            "participants": {key: ev[key] for key in ("home_id", "away_id")}, "scope": scope,
            "event_status": ev["status"]})
        subject = ev["event_key"] + ":participants:" + identity
        if kind == "map":
            subject += ":" + data["map_id"]
        b1_kind = "workload" if kind in {"series", "observed_lineup", "map"} else "availability" if kind == "patch_veto" else (
            "confirmed_lineup" if data["status"] == "confirmed" else "expected_lineup")
        # Keep actual native status transitions through B1 latest-selection too:
        # a later map refresh must not erase an earlier series-end retraction.
        # These are source-bound identities, never independent caller flags.
        subject += ":fact:" + kind
        output.append(normalize_observation({
            "event_key": ev["event_key"], "sport": "esports", "competition": ev["competition"], "format": ev["format"],
            "subject_id": subject, "kind": b1_kind, "source": "pandascore", "source_schema": SCHEMA,
            "source_revision": digest(payload), "schedule_revision": ev["schedule_revision"], "published_at": None,
            "publication_proof": None, "valid_from": receipt, "valid_until": valid_until, "complete": complete, "payload": payload,
        }, observed_at=observed_at))
    return tuple(output)


def validate_esports_receipt(row):
    """Rebuild the entire closed source projection; B1 validates receipt bytes."""
    payload = row["payload"]
    require_object(payload, {"schema", "source_schema", "kind", "event", "scope", "status", "data"}, label="stored esports projection")
    raw = {key: deepcopy(value) for key, value in payload.items() if key != "status"}
    raw["valid_until"] = row["valid_until"]
    rebuilt = normalize_esports_context(raw["event"], (raw,), observed_at=datetime.fromisoformat(row["observed_at"]))[0]
    if rebuilt != {key: row[key] for key in OBSERVATION_FIELDS}:
        raise ContextContractError("stored esports source projection/clocks changed")
    return payload
