"""Normalize measured ESPN tennis facts, not assumed fitness or source coverage.

``espn-scoreboard-v1`` consumes the existing competition response with its tour
and tournament identity. ``tennis-shadow-native-v1`` accepts an owning ingestion
path's already measured native facts; the legacy name-only shadow database does
not satisfy that interface. No I/O, provider expansion or name matching occurs.
"""

from __future__ import annotations

from datetime import datetime
from itertools import zip_longest
import re

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, normalize_observation,
    require_number, require_object, require_text,
)


SOURCE_SCHEMA = "espn-tennis-workload-v1"
PAYLOAD_FIELDS = {
    "tour", "player_id", "opponent_id", "status", "scheduled_start",
    "actual_start", "actual_end", "result_observed_at", "sets", "games",
    "minutes", "set_scores", "incomplete_match", "history_scope",
}
_NATIVE_ID = re.compile(r"[1-9][0-9]*\Z")


def _id(value: object) -> str:
    if type(value) is int:
        value = str(value)
    if type(value) is not str or _NATIVE_ID.fullmatch(value) is None:
        raise ContextContractError("tennis requires positive native ESPN IDs")
    return value


def _time(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise ContextContractError("source times must be aware ISO strings or null")
    return canonical_timestamp(value)


def _count(value: object, name: str) -> int | None:
    if value is None:
        return None
    number = require_number(value, name, minimum=0)
    if int(number) != number:
        raise ContextContractError(f"{name} must contain whole observed counts")
    return int(number)


def _counts(scores: object) -> tuple[list, int | None, int | None]:
    if scores is None:
        return [], None, None
    if type(scores) is not list:
        raise ContextContractError("set scores must be an observed list")
    normalized = []
    for item in scores:
        require_object(item, {"a", "b", "completed"}, label="observed set")
        a, b = _count(item["a"], "set games"), _count(item["b"], "set games")
        if item["completed"] is not None and type(item["completed"]) is not bool:
            raise ContextContractError("set completion must be observed or unknown")
        if item["completed"] and a is not None and b is not None and a == b:
            raise ContextContractError("completed singles set cannot have tied games")
        normalized.append({"a": a, "b": b, "completed": item["completed"]})
    if not normalized:
        return [], None, None
    sets = sum(item["completed"] for item in normalized) if all(item["completed"] is not None for item in normalized) else None
    games = sum(item["a"] + item["b"] for item in normalized) if all(
        item["a"] is not None and item["b"] is not None for item in normalized
    ) else None
    return normalized, sets, games


def _espn(row: dict) -> dict | None:
    require_object(row, {"source_schema", "tour", "tournament_id", "competition"}, label="ESPN workload input")
    comp = row["competition"]
    if type(comp) is not dict:
        raise ContextContractError("ESPN competition must be an object")
    status = comp.get("status") or {}
    if type(status) is not dict or type(status.get("type", {})) is not dict:
        raise ContextContractError("ESPN terminal status must be an object")
    status = status.get("type", {})
    if status.get("state") != "post" or status.get("completed") is not True:
        return None
    # Same terminal vocabulary as the existing source. Text classifies only the
    # match terminal, never a player's injury, diagnosis or travel.
    text = " ".join(str(status.get(key, "")) for key in ("name", "description", "detail", "shortDetail"))
    notes = comp.get("notes", [])
    if type(notes) is list:
        text += " " + " ".join(str(note.get("text", "")) for note in notes if type(note) is dict)
    text = text.casefold()
    retirement = any(token in text for token in ("retired", "retirement", "ret.", "ret'd"))
    walkover = any(token in text for token in ("walkover", "w/o", "walk-over"))
    if retirement and walkover or any(token in text for token in ("abandoned", "defaulted")):
        return None
    if not retirement and not walkover and status.get("name") != "STATUS_FINAL":
        return None
    competitors = comp.get("competitors")
    if type(competitors) is not list or len(competitors) != 2 or any(type(c) is not dict for c in competitors):
        raise ContextContractError("completed singles match requires two native competitors")
    a, b = competitors
    scores = None
    left, right = a.get("linescores"), b.get("linescores")
    if any(lines is not None and type(lines) is not list for lines in (left, right)):
        raise ContextContractError("ESPN set lines must be lists or absent")
    if left or right:
        scores = []
        for x, y in zip_longest(left or [], right or [], fillvalue={}):
            if type(x) is not dict or type(y) is not dict:
                raise ContextContractError("ESPN set lines must be objects")
            flags = (x.get("winner"), y.get("winner"))
            if any(flag is not None and type(flag) is not bool for flag in flags) or flags == (True, True):
                raise ContextContractError("contradictory set completion flags")
            completed = True if True in flags else False if flags == (False, False) else None
            scores.append({"a": x.get("value"), "b": y.get("value"), "completed": completed})
    return {
        "event_id": _id(comp.get("id")), "player_a_id": _id(a.get("id")),
        "player_b_id": _id(b.get("id")), "tour": row["tour"],
        "tournament_id": row["tournament_id"],
        "status": "walkover" if walkover else "retired" if retirement else "completed",
        "scheduled_start": comp.get("date"), "actual_start": None, "actual_end": None,
        "result_observed_at": None, "set_scores": scores, "sets": None,
        "games": None, "minutes": None,
    }


def _shadow(row: dict) -> dict | None:
    fields = {"source_schema", "fixture_source", "provider_event_id", "tour", "tournament_id",
              "player_a_id", "player_b_id", "settled", "termination", "result_observed_at"}
    optional = {"scheduled_start_utc", "actual_start_utc", "actual_end_utc", "set_scores",
                "player_a_sets", "player_b_sets", "match_duration_minutes", "total_games"}
    require_object(row, fields, optional=optional, label="native shadow workload input")
    if row["fixture_source"] != "ESPN":
        raise ContextContractError("unreviewed tennis source schema")
    if type(row["settled"]) is not int or row["settled"] not in (0, 1):
        raise ContextContractError("settlement flag must be an actual integer")
    if row["settled"] != 1 or row["termination"] not in {"normal", "retirement", "walkover"}:
        return None
    a_sets, b_sets = _count(row.get("player_a_sets"), "set wins"), _count(row.get("player_b_sets"), "set wins")
    return {
        "event_id": _id(row["provider_event_id"]), "player_a_id": _id(row["player_a_id"]),
        "player_b_id": _id(row["player_b_id"]), "tour": row["tour"], "tournament_id": row["tournament_id"],
        "status": {"normal": "completed", "retirement": "retired", "walkover": "walkover"}[row["termination"]],
        "scheduled_start": row.get("scheduled_start_utc"), "actual_start": row.get("actual_start_utc"),
        "actual_end": row.get("actual_end_utc"), "result_observed_at": row["result_observed_at"],
        "set_scores": row.get("set_scores"), "sets": a_sets + b_sets if a_sets is not None and b_sets is not None else None,
        "games": row.get("total_games"), "minutes": row.get("match_duration_minutes"),
    }


def validate_workload_payload(payload: dict, *, subject_id: str, observed_at: str) -> dict:
    """A source-specific closed numeric allowlist, in addition to B1 validation."""
    require_object(payload, PAYLOAD_FIELDS, label="tennis workload payload")
    if payload["tour"] not in {"ATP", "WTA"}:
        raise ContextContractError("native tennis tour must be ATP or WTA")
    prefix = f"espn:tennis:{payload['tour']}:player:"
    for key in ("player_id", "opponent_id"):
        value = require_text(payload[key], key, code=True)
        if not value.startswith(prefix):
            raise ContextContractError("player identity does not match source/sport/tour")
        _id(value[len(prefix):])
    if payload["player_id"] != subject_id or payload["player_id"] == payload["opponent_id"]:
        raise ContextContractError("workload subject must be a distinct native player")
    if payload["status"] not in {"completed", "retired", "walkover"}:
        raise ContextContractError("workload is not a supported completed terminal")
    if type(payload["incomplete_match"]) is not bool or payload["incomplete_match"] != (payload["status"] != "completed"):
        raise ContextContractError("terminal and observed incomplete-match flag disagree")
    if payload["history_scope"] != "observed_matches_only":
        raise ContextContractError("this source does not prove complete player history")
    for key in ("scheduled_start", "actual_start", "actual_end", "result_observed_at"):
        if _time(payload[key]) != payload[key]:
            raise ContextContractError("workload timestamps must be canonical")
    receipt = payload["result_observed_at"]
    if receipt is None or receipt > observed_at:
        raise ContextContractError("result receipt must precede the actual import")
    start, end, schedule = payload["actual_start"], payload["actual_end"], payload["scheduled_start"]
    if ((start is not None and start > receipt) or (end is not None and end > receipt)
            or (start is not None and end is not None and start > end)
            or (schedule is not None and schedule > receipt)):
        raise ContextContractError("inconsistent completed-match chronology")
    scores, counted_sets, counted_games = _counts(payload["set_scores"])
    sets, games = _count(payload["sets"], "observed sets"), _count(payload["games"], "observed games")
    if scores and (sets != counted_sets or games != counted_games):
        raise ContextContractError("observed totals disagree with measured set scores")
    if payload["minutes"] is not None:
        require_number(payload["minutes"], "observed minutes", minimum=0)
        if payload["minutes"] == 0:
            raise ContextContractError("missing duration is not zero minutes")
        if start is not None and end is not None:
            elapsed_minutes = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60
            if payload["minutes"] > elapsed_minutes:
                raise ContextContractError("observed duration exceeds the actual match interval")
    if payload["status"] == "walkover" and any(payload[key] is not None for key in ("sets", "games", "minutes")):
        raise ContextContractError("walkover has no invented played workload")
    return payload


def validate_workload_record(row: dict) -> dict:
    """Check bindings owned by this normalizer after B1 checks receipt integrity."""
    payload = validate_workload_payload(row["payload"], subject_id=row["subject_id"], observed_at=row["observed_at"])
    prefix = f"espn:tennis:{payload['tour']}:match:"
    if not row["event_key"].startswith(prefix) or not row["competition"].startswith(f"espn:{payload['tour']}:tournament:"):
        raise ContextContractError("workload native event and tour scope disagree")
    _id(row["event_key"][len(prefix):])
    expected_schedule = digest({"event_key": row["event_key"], "scheduled_start": payload["scheduled_start"]})
    if (row["source_revision"] != digest(payload) or row["schedule_revision"] != expected_schedule
            or row["valid_from"] != payload["result_observed_at"] or row["valid_until"] is not None
            or row["published_at"] is not None or row["publication_proof"] is not None):
        raise ContextContractError("normalized tennis source clock/content binding mismatch")
    if row["complete"] is not False:
        raise ContextContractError("the measured source cannot certify complete player history")
    return payload


def normalize_tennis_workload(rows: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]:
    """Produce B1 records, preserving each participant's native tour namespace.

    Records are content, not receipts. B1 ingestion must receive this same actual
    ``observed_at``; historical imports cannot be passed off as past observations.
    """
    if type(rows) is not tuple or not isinstance(observed_at, datetime):
        raise ContextContractError("tennis inputs require a tuple and actual ingestion datetime")
    observed = canonical_timestamp(observed_at)
    result = []
    for row in rows:
        if type(row) is not dict:
            raise ContextContractError("tennis source rows must be objects")
        schema = row.get("source_schema")
        if schema == "espn-scoreboard-v1":
            item = _espn(row)
        elif schema == "tennis-shadow-native-v1":
            item = _shadow(row)
        else:
            raise ContextContractError("unreviewed tennis source schema")
        if item is None:
            continue
        tour = item["tour"]
        if tour not in {"ATP", "WTA"}:
            raise ContextContractError("native tennis tour must be ATP or WTA")
        tournament = require_text(item["tournament_id"], "native tournament ID", code=True)
        event_key = f"espn:tennis:{tour}:match:{item['event_id']}"
        scores, sets, games = _counts(item["set_scores"])
        if not scores:
            sets, games = _count(item["sets"], "observed sets"), _count(item["games"], "observed games")
        else:
            for name, count in (("sets", sets), ("games", games)):
                if item[name] is not None and item[name] != count:
                    raise ContextContractError("source totals disagree with measured set scores")
        minutes = item["minutes"]
        if item["status"] == "walkover":
            scores, sets, games, minutes = [], None, None, None
        for side, other in (("a", "b"), ("b", "a")):
            player = f"espn:tennis:{tour}:player:{item[f'player_{side}_id']}"
            opponent = f"espn:tennis:{tour}:player:{item[f'player_{other}_id']}"
            payload = {
                "tour": tour, "player_id": player, "opponent_id": opponent,
                "status": item["status"], "scheduled_start": _time(item["scheduled_start"]),
                "actual_start": _time(item["actual_start"]), "actual_end": _time(item["actual_end"]),
                "result_observed_at": _time(item["result_observed_at"]) or observed,
                "sets": sets, "games": games, "minutes": minutes,
                "set_scores": [dict(score) if side == "a" else {"a": score["b"], "b": score["a"], "completed": score["completed"]} for score in scores],
                "incomplete_match": item["status"] != "completed", "history_scope": "observed_matches_only",
            }
            validate_workload_payload(payload, subject_id=player, observed_at=observed)
            record = {
                "event_key": event_key, "sport": "tennis", "competition": f"espn:{tour}:tournament:{tournament}",
                "format": "singles", "subject_id": player, "kind": "workload", "source": "espn",
                "source_schema": SOURCE_SCHEMA, "source_revision": digest(payload),
                "schedule_revision": digest({"event_key": event_key, "scheduled_start": payload["scheduled_start"]}),
                "published_at": None, "publication_proof": None,
                "valid_from": payload["result_observed_at"], "valid_until": None,
                "complete": False, "payload": payload,
            }
            result.append(normalize_observation(record, observed_at=observed_at))
    return tuple(result)
