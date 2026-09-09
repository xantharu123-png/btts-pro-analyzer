"""Closed INTERNAL hockey envelopes; NOT a source-qualified NHL TOI adapter.

Actual measured usage, explicit conditional projections, availability and
starter declarations remain distinct. A hash proves consistency, not source
truth. No HTTP, inferred starter, guessed shift time or probability weight.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from context_models.contracts import (
    ContextContractError, OBSERVATION_FIELDS, canonical_timestamp, digest,
    normalize_observation, require_list, require_number, require_object, require_text,
)
from context_models.ice_hockey import hockey_event, hockey_scope, native_id

SCHEMA = "hockey-internal-context-v1"
KINDS = {"appearance", "projection", "starter", "availability"}


def _clock(value):
    if type(value) is not str:
        raise ContextContractError("hockey source clocks require actual aware strings")
    return canonical_timestamp(value)


def _seconds(value, maximum=None):
    if value is None:
        return None
    require_number(value, "reported hockey seconds", minimum=0, maximum=maximum)
    if type(value) is not int:
        raise ContextContractError("hockey v1 uses actual integer seconds, not inferred fractional times")
    return value


def _intervals(value, players, *, phase, duration, full):
    if value is None:
        return None
    require_list(value, "reported manpower intervals")
    if len(value) > 10000:
        raise ContextContractError("hockey interval inventory exceeds the bounded transport")
    for interval in value:
        require_object(interval, {"start", "end", "skaters", "goalie"}, label="native manpower interval")
        if _seconds(interval["start"], duration) is None or _seconds(interval["end"], duration) is None:
            raise ContextContractError("actual manpower interval endpoints cannot be missing")
    result, previous, totals = [], 0, {player: 0 for player in players}
    for interval in sorted(value, key=lambda row: row["start"]):
        start, end = _seconds(interval["start"], duration), _seconds(interval["end"], duration)
        if start is None or end is None or end <= start or start < previous or (full and start != previous):
            raise ContextContractError("overlapping/gapped full hockey interval revision")
        skaters = require_list(interval["skaters"], "on-ice native skaters")
        for player in skaters: native_id(player, "player:")
        if not 3 <= len(skaters) <= 6 or len(set(skaters)) != len(skaters):
            raise ContextContractError("invalid reported native skater collection")
        goalie = interval["goalie"]
        if goalie is not None:
            native_id(goalie, "player:")
            if goalie not in players or players[goalie]["role"] != "goalie" or len(skaters) > 5:
                raise ContextContractError("goalie presence/role is not the reported manpower")
        for player in skaters:
            native_id(player, "player:")
            if player not in players or players[player]["role"] != "skater":
                raise ContextContractError("interval names an undeclared or wrong-role skater")
        for player in [*skaters, *([goalie] if goalie else [])]: totals[player] += end-start
        result.append({"start": start, "end": end, "skaters": sorted(skaters), "goalie": goalie})
        previous = end
    if full and duration is not None and previous != duration:
        raise ContextContractError("full hockey interval collection does not cover the phase")
    if full and duration is not None:
        for player, record in players.items():
            reported = record[phase+"_seconds"]
            if reported is not None and reported != totals[player]:
                raise ContextContractError("reported individual TOI and manpower integral differ")
    return result


def _usage(value, *, regulation, overtime, measured, seen):
    require_object(value, {"complete", "players", "regulation_intervals", "overtime_intervals"}, label="whole hockey team exposure")
    if type(value["complete"]) is not bool:
        raise ContextContractError("hockey collection coverage must be explicit")
    require_list(value["players"], "native hockey player collection")
    if len(value["players"]) > 100:
        raise ContextContractError("hockey collection is not bounded")
    players = {}
    for row in value["players"]:
        require_object(row, {"player_id", "role", "regulation_seconds", "overtime_seconds"}, label="reported individual hockey TOI")
        player = native_id(row["player_id"], "player:")
        if player in seen:
            raise ContextContractError("native player occurs twice in a joint event revision")
        seen.add(player)
        if type(row["role"]) is not str or row["role"] not in {"skater", "goalie"}:
            raise ContextContractError("hockey skater/goalie role is unknown")
        reg, ot = _seconds(row["regulation_seconds"], regulation), _seconds(row["overtime_seconds"], overtime)
        if not measured and ot is not None:
            raise ContextContractError("regulation projection cannot invent performed overtime")
        players[player] = {"player_id": player, "role": row["role"], "regulation_seconds": reg, "overtime_seconds": ot}
    full = value["complete"]
    reg_intervals = _intervals(value["regulation_intervals"], players, phase="regulation", duration=regulation, full=full)
    if not measured and value["overtime_intervals"] is not None:
        raise ContextContractError("a regulation scenario does not supply overtime intervals")
    ot_intervals = _intervals(value["overtime_intervals"], players, phase="overtime", duration=overtime, full=full) if measured else None
    return {"complete": full, "players": [players[key] for key in sorted(players)],
            "regulation_intervals": reg_intervals, "overtime_intervals": ot_intervals}


def exposure_complete(team, phase, duration):
    """Only after owning validation; no free completeness flag is sufficient."""
    intervals = team[phase+"_intervals"]
    return (team["complete"] and bool(team["players"]) and duration is not None and intervals is not None
            and all(player[phase+"_seconds"] is not None for player in team["players"]))


def _team_collection(teams, event, *, regulation, overtime, measured):
    require_object(teams, {event["home_id"], event["away_id"]}, label="whole native hockey participants")
    seen = set()
    result = {key: _usage(teams[key], regulation=regulation, overtime=overtime, measured=measured, seen=seen)
              for key in sorted(teams)}
    complete = all(exposure_complete(value, "regulation", regulation) and (
        not measured or exposure_complete(value, "overtime", overtime)) for value in result.values())
    return result, complete


def normalize_ice_hockey_context(event: dict, responses: tuple[dict, ...], *, observed_at: datetime) -> tuple[dict, ...]:
    target = hockey_event(event)
    if type(responses) is not tuple or not isinstance(observed_at, datetime):
        raise ContextContractError("hockey source requires tuple responses and actual aware receipt")
    receipt = canonical_timestamp(observed_at)
    output = []
    for raw in responses:
        require_object(raw, {"schema", "source_schema", "kind", "event", "scope", "valid_from", "valid_until", "data"}, label="internal hockey response")
        if type(raw["schema"]) is not int or raw["schema"] != 1 or raw["source_schema"] != SCHEMA or type(raw["kind"]) is not str or raw["kind"] not in KINDS:
            raise ContextContractError("unreviewed internal hockey source version")
        event, kind = hockey_event(raw["event"]), raw["kind"]
        scope = hockey_scope(raw["scope"], event)
        if kind != "appearance" and event != target:
            raise ContextContractError("current hockey source belongs to another full event revision")
        data = deepcopy(raw["data"])
        complete = False
        if kind == "appearance":
            require_object(data, {"actual_start", "actual_end", "result_observed_at", "regulation_seconds", "overtime_seconds", "terminal_phase", "teams"}, label="measured hockey appearance")
            if event["status"] not in {"completed", "cancelled"}:
                raise ContextContractError("appearance must be an observed terminal event revision")
            terminal = data["result_observed_at"] = _clock(data["result_observed_at"])
            if terminal > receipt:
                raise ContextContractError("hockey terminal receipt is not causal")
            for key in ("actual_start", "actual_end"):
                data[key] = None if data[key] is None else _clock(data[key])
                if data[key] is not None and data[key] > terminal:
                    raise ContextContractError("actual hockey play follows terminal receipt")
            if data["actual_start"] is not None and data["actual_end"] is not None and data["actual_start"] >= data["actual_end"]:
                raise ContextContractError("actual hockey end must follow actual start")
            reg, ot = _seconds(data["regulation_seconds"], 3600), _seconds(data["overtime_seconds"])
            if reg is not None and reg != 3600:
                raise ContextContractError("this completed NHL format requires actual full regulation")
            phase = data["terminal_phase"]
            if phase not in (None, "REG", "OT", "SO") or (phase == "SO" and scope["game_type"] != 2):
                raise ContextContractError("terminal NHL phase conflicts with game type")
            if (phase == "REG" and ot not in (0, None)) or (phase == "OT" and ot == 0) or (phase == "SO" and ot not in (300, None)):
                raise ContextContractError("actual OT exposure conflicts with terminal phase")
            if scope["game_type"] == 2 and ot is not None and ot > 300:
                raise ContextContractError("regular-season actual OT exceeds its five-minute phase")
            if data["actual_start"] is not None and data["actual_end"] is not None and reg is not None and ot is not None:
                if reg+ot > (datetime.fromisoformat(data["actual_end"])-datetime.fromisoformat(data["actual_start"])).total_seconds():
                    raise ContextContractError("reported phase play exceeds the actual wall-clock interval")
            data["teams"], complete = _team_collection(data["teams"], event, regulation=reg, overtime=ot, measured=True)
            if event["status"] == "cancelled" and (any(data[key] is not None for key in (
                "actual_start", "actual_end", "regulation_seconds", "overtime_seconds", "terminal_phase"))
                or any(value["complete"] or value["players"] or value["regulation_intervals"] or value["overtime_intervals"] for value in data["teams"].values())):
                raise ContextContractError("hockey withdrawal cannot claim performed player exposure")
        else:
            if event["status"] != "scheduled":
                raise ContextContractError("current hockey context requires a scheduled event")
            if kind == "projection":
                require_object(data, {"scenarios"}, label="explicit unweighted hockey scenarios")
                scenarios = require_list(data["scenarios"], "hockey scenario inventory")
                if len(scenarios) > 16:
                    raise ContextContractError("hockey scenario inventory is not bounded")
                seen, clean, coverage = set(), [], []
                for scenario in scenarios:
                    require_object(scenario, {"scenario_id", "teams"}, label="explicit conditional hockey projection")
                    key = require_text(scenario["scenario_id"], "native scenario identity", code=True)
                    if key in seen: raise ContextContractError("duplicate hockey scenario identity")
                    seen.add(key)
                    teams, good = _team_collection(scenario["teams"], event, regulation=3600, overtime=None, measured=False)
                    clean.append({"scenario_id": key, "teams": teams})
                    coverage.append(good)
                data["scenarios"] = sorted(clean, key=lambda row: row["scenario_id"])
                complete = bool(clean) and all(coverage)
            elif kind == "starter":
                require_object(data, {"teams"}, label="reported hockey starter facts")
                require_object(data["teams"], {event["home_id"], event["away_id"]}, label="joint starter participants")
                starters = []
                for value in data["teams"].values():
                    require_object(value, {"status", "player_id"}, label="actual goalie confirmation")
                    if type(value["status"]) is not str or value["status"] not in {"confirmed", "unconfirmed", "unknown"}:
                        raise ContextContractError("unreviewed goalie confirmation state")
                    if value["player_id"] is not None: native_id(value["player_id"], "player:")
                    if (value["status"] == "unknown") != (value["player_id"] is None):
                        raise ContextContractError("starter identity cannot be inferred")
                    if value["player_id"] is not None: starters.append(value["player_id"])
                if len(set(starters)) != len(starters): raise ContextContractError("same goalie declared for both teams")
                complete = all(value["status"] == "confirmed" for value in data["teams"].values())
            else:
                require_object(data, {"teams"}, label="reported hockey availability")
                require_object(data["teams"], {event["home_id"], event["away_id"]}, label="joint availability participants")
                seen, coverage = set(), []
                for value in data["teams"].values():
                    require_object(value, {"complete", "players"}, label="reported availability collection")
                    if type(value["complete"]) is not bool: raise ContextContractError("explicit availability coverage required")
                    for player in require_list(value["players"], "native availability players"):
                        require_object(player, {"player_id", "status"}, label="reported player availability")
                        native_id(player["player_id"], "player:")
                        if player["player_id"] in seen or type(player["status"]) is not str or player["status"] not in {"available", "out", "questionable", "unknown"}:
                            raise ContextContractError("duplicate/unknown hockey availability")
                        seen.add(player["player_id"])
                    value["players"].sort(key=lambda row: row["player_id"])
                    coverage.append(value["complete"] and bool(value["players"]))
                complete = all(coverage)
        # B1's workload contract inspects this terminal state. It is derived
        # from the exact owning Event, never another independent declaration.
        payload = {"schema": 1, "source_schema": SCHEMA, "kind": kind, "event": event, "scope": scope, "data": data,
                   "status": event["status"]}
        b1_kind = {"appearance": "workload", "projection": "expected_lineup", "starter": "confirmed_lineup", "availability": "availability"}[kind]
        output.append(normalize_observation({"event_key": event["event_key"], "sport": "ice_hockey", "competition": "nhl", "format": event["format"],
            "subject_id": event["event_key"]+":participants:"+digest({key: event[key] for key in ("home_id", "away_id")}),
            "kind": b1_kind, "source": "nhl", "source_schema": SCHEMA, "source_revision": digest(payload),
            "schedule_revision": event["schedule_revision"], "published_at": None, "publication_proof": None,
            "valid_from": _clock(raw["valid_from"]), "valid_until": None if raw["valid_until"] is None else _clock(raw["valid_until"]),
            "complete": complete, "payload": payload}, observed_at=observed_at))
    return tuple(output)


def validate_hockey_receipt(row):
    require_object(row["payload"], {"schema", "source_schema", "kind", "event", "scope", "data", "status"}, label="stored hockey source payload")
    raw = {**deepcopy(row["payload"]), "valid_from": row["valid_from"], "valid_until": row["valid_until"]}
    raw.pop("status")
    expected = normalize_ice_hockey_context(raw["event"], (raw,), observed_at=datetime.fromisoformat(row["observed_at"]))[0]
    if expected != {key: row[key] for key in OBSERVATION_FIELDS}:
        raise ContextContractError("stored hockey source projection differs")
    return row["payload"]


def hockey_observations_as_of(path: Path, event_key: str, *, cutoff: datetime, schedule_revision: str) -> tuple[dict, ...]:
    """Full causal historical lineage; current facts remain exact-schedule only."""
    from context_observations import _connect, _decode_receipt, _SELECT
    native_id(event_key, "")
    require_text(schedule_revision, "current hockey schedule", code=True)
    if not isinstance(cutoff, datetime): raise ContextContractError("hockey cutoff must be actual aware datetime")
    stamp = canonical_timestamp(cutoff)
    with closing(_connect(Path(path))) as db:
        try:
            db.execute("BEGIN")
            rows = [_decode_receipt(row) for row in db.execute(_SELECT+" WHERE r.event_key=?", (event_key,))]
            db.commit()
        except BaseException:
            db.rollback()
            raise
    result = []
    for row in rows:
        if row["observed_at"] > stamp or row["source_schema"] != SCHEMA: continue
        payload = validate_hockey_receipt(row)
        if payload["kind"] != "appearance" and row["schedule_revision"] != schedule_revision: continue
        result.append({**row, "evidence_class": "prospective", "effective_at": row["observed_at"], "publication_resolution": None})
    return tuple(sorted(result, key=lambda row: (row["observed_at"], row["digest"])))
