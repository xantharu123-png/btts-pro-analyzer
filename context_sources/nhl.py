"""Native NHL boxscore facts, NOT complete internal C3 exposure envelopes.

No network, implicit clock, model, source truth flag or pregame inference lives
here. The caller owns the actual bound HTTP receipt. Whole-game TOI remains
whole-game, even for REG: no manpower coverage or actual end is manufactured.
"""
from __future__ import annotations

from datetime import datetime
import re

from context_models.contracts import (
    ContextContractError, OBSERVATION_FIELDS, canonical_timestamp, digest,
    normalize_observation, require_number, require_object,
)
from context_observations import append_bounded_observation_batch
from model_artifacts import canonical_bytes


SCHEMA = "nhl-boxscore-measured-v1"
_SEASONS = frozenset({20252026, 20262027})
_FORMATS = {2: "nhl_reg60_regular_ot_so", 3: "nhl_reg60_playoff_ot"}
_GROUPS = ("forwards", "defense", "goalies")
_SKATER_STATS = {"shifts": "shifts", "goals": "goals", "assists": "assists",
                 "points": "points", "sog": "shots_on_goal"}
_GOALIE_STATS = {"shotsAgainst": "shots_against", "saves": "saves",
                 "goalsAgainst": "goals_against", "savePctg": "save_pctg"}
_PLAYER_FIELDS = {"playerId", "teamId", "toi", "starter", "position", *_SKATER_STATS, *_GOALIE_STATS}
MAX_SOURCE_BYTES = 256 * 1024
MAX_TEAM_PLAYERS = 100
MAX_BATCH = 512


def _need(condition, message):
    if not condition:
        raise ContextContractError(message)


def _object(value, label):
    _need(type(value) is dict, f"native NHL {label} must be an object")
    return value


def _select(value, fields, label):
    """Bound only owned sport scalars; never traverse media/odds/history trees."""
    _object(value, label)
    result = {}
    for name in sorted(fields.intersection(value)):
        item = value[name]
        _need(item is None or type(item) in (str, bool, int, float), f"native NHL {name} must be scalar")
        if type(item) is str:
            _need(len(item) <= 128, f"native NHL {name} is not bounded")
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise ContextContractError(f"native NHL {name} is not valid UTF-8") from exc
        if type(item) in (int, float):
            require_number(item, f"native NHL {name}", minimum=-10**12, maximum=10**12)
        result[name] = item
    return result


def _native(payload):
    raw = _select(payload, {"id", "season", "gameType", "startTimeUTC", "gameState", "gameScheduleState", "neutralSite"}, "boxscore")
    for key, fields in (("homeTeam", {"id", "score"}), ("awayTeam", {"id", "score"}),
                        ("gameOutcome", {"lastPeriodType"}),
                        ("periodDescriptor", {"number", "periodType", "maxRegulationPeriods"}),
                        ("clock", {"secondsRemaining", "running"})):
        if key in payload:
            raw[key] = None if payload[key] is None else _select(payload[key], fields, key)
    if "playerByGameStats" in payload:
        collection = payload["playerByGameStats"]
        if collection is None:
            raw["playerByGameStats"] = None
        else:
            _object(collection, "playerByGameStats")
            raw["playerByGameStats"] = {}
            for side in ("homeTeam", "awayTeam"):
                if side not in collection:
                    continue
                team = collection[side]
                if team is None:
                    raw["playerByGameStats"][side] = None
                    continue
                _object(team, "player statistics side")
                projected, count = {}, 0
                for group in _GROUPS:
                    if group not in team:
                        continue
                    items = team[group]
                    if items is None:
                        projected[group] = None
                        continue
                    _need(type(items) is list, "native NHL player group must be a list")
                    count += len(items)
                    _need(count <= MAX_TEAM_PLAYERS, "native NHL player inventory is not bounded")
                    projected[group] = [_select(item, _PLAYER_FIELDS, "player") for item in items]
                    # Source order is not a starter, participation or revision fact.
                    projected[group].sort(key=canonical_bytes)
                raw["playerByGameStats"][side] = projected
    try:
        _need(len(canonical_bytes(raw)) <= MAX_SOURCE_BYTES, "native NHL relevant source bytes exceed bound")
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ContextContractError("native NHL source is not bounded finite JSON") from exc
    return raw


def _integer(value, label, *, minimum=0, maximum=10**9, optional=False):
    if optional and value is None:
        return None
    _need(type(value) is int and minimum <= value <= maximum, f"native NHL {label} must be an integer in range, not bool")
    return value


def _game_id(value):
    _need(type(value) is int and re.fullmatch(r"20[0-9]{2}0[23][0-9]{4}", str(value)) is not None,
          "native NHL requested game ID must be a supported integer identity")
    _need(value % 10000 > 0, "native NHL game sequence is invalid")
    return value


def _toi(value, maximum):
    if value is None:
        return None
    _need(type(value) is str and re.fullmatch(r"[0-9]{1,3}:[0-5][0-9]", value) is not None,
          "native NHL TOI must be nonnegative minutes:seconds")
    minutes, seconds = map(int, value.split(":"))
    total = minutes * 60 + seconds
    _need(total <= maximum, "native NHL TOI exceeds its reported game phase")
    return total


def _terminal(raw, game_type, completed):
    if not completed:
        _need(raw.get("gameOutcome") in (None, {}), "uncompleted NHL game cannot claim completed outcome")
        return None, 0
    outcome = _object(raw.get("gameOutcome"), "completed outcome")
    phase = outcome.get("lastPeriodType")
    _need(type(phase) is str and phase in {"REG", "OT", "SO"}, "native NHL terminal phase is missing or unsupported")
    _need(phase != "SO" or game_type == 2, "native NHL playoffs cannot finish by shootout")
    descriptor = raw.get("periodDescriptor")
    number = None
    if descriptor is not None:
        _object(descriptor, "periodDescriptor")
        number = _integer(descriptor.get("number"), "terminal period", minimum=3, maximum=20)
        _need(descriptor.get("periodType") == phase, "native NHL terminal period contradicts outcome")
        if "maxRegulationPeriods" in descriptor:
            _need(type(descriptor["maxRegulationPeriods"]) is int and descriptor["maxRegulationPeriods"] == 3,
                  "native NHL regulation period count is unsupported")
        _need((phase == "REG" and number == 3) or (phase == "SO" and number == 5)
              or (phase == "OT" and (number == 4 if game_type == 2 else number >= 4)),
              "native NHL terminal phase and period number differ")
    clock = raw.get("clock")
    if clock is not None:
        _object(clock, "clock")
        if clock.get("running") is not None:
            _need(type(clock["running"]) is bool and clock["running"] is False, "native NHL completed clock is running")
        if clock.get("secondsRemaining") is not None:
            remaining = _integer(clock["secondsRemaining"], "remaining clock",
                                 maximum=300 if phase == "OT" and game_type == 2 else 1200)
            _need(phase == "OT" or remaining == 0, "native NHL completed regulation/shootout clock is not zero")
    if phase == "REG":
        return phase, 3600
    if game_type == 2:
        return phase, 3900
    _need(number is not None, "native NHL playoff OT requires reported period number to bound TOI")
    return phase, number * 1200


def _players(raw, *, team_id, maximum, completed, seen):
    missing = [group for group in _GROUPS if raw is None or raw.get(group) is None]
    result, starters = [], 0
    if raw is None:
        return {"players": None, "missing_groups": missing, "availability": None, "pregame_starter": None}
    for group in _GROUPS:
        for player in raw.get(group) or []:
            _need(completed, "uncompleted NHL player statistics are not completed usage")
            identifier = _integer(player.get("playerId"), "player ID", minimum=1)
            _need(identifier not in seen, "native NHL player occurs twice or across teams")
            seen.add(identifier)
            if player.get("teamId") is not None:
                _need(_integer(player["teamId"], "player team ID", minimum=1) == team_id, "native NHL player team contradicts side")
            role = "goalie" if group == "goalies" else "skater"
            position = player.get("position")
            _need(position is None or (type(position) is str and position in ({"G"} if role == "goalie" else {"C", "L", "R", "LW", "RW", "D"})),
                  "native NHL player position contradicts group")
            stats = {}
            for field, key in (_GOALIE_STATS if role == "goalie" else _SKATER_STATS).items():
                value = player.get(field)
                if field == "savePctg":
                    stats[key] = None if value is None else require_number(value, "native NHL save percentage", minimum=0, maximum=1)
                else:
                    stats[key] = _integer(value, field, maximum=10000, optional=True)
            actual_starter = player.get("starter") if role == "goalie" else None
            _need(actual_starter is None or type(actual_starter) is bool, "native NHL actual goalie starter must be boolean or unknown")
            if role == "goalie":
                starters += actual_starter is True
                shots, saves, goals, pct = (stats[key] for key in ("shots_against", "saves", "goals_against", "save_pctg"))
                _need(shots is None or saves is None or saves <= shots, "native NHL saves exceed shots against")
                _need(shots is None or goals is None or goals <= shots, "native NHL goals exceed shots against")
                _need(None in (shots, saves, goals) or saves + goals == shots, "native NHL save/goal arithmetic differs")
                _need(shots in (None, 0) or saves is None or pct is None or abs(saves/shots - pct) <= .000000500001,
                      "native NHL reported rounded save percentage differs")
            else:
                goals, assists, points = (stats[key] for key in ("goals", "assists", "points"))
                _need(None in (goals, assists, points) or goals + assists == points, "native NHL skater point arithmetic differs")
            result.append({"player_id": f"nhl:ice_hockey:player:{identifier}", "role": role, "source_group": group,
                           "toi": player.get("toi"), "total_seconds": _toi(player.get("toi"), maximum),
                           "regulation_seconds": None, "overtime_seconds": None,
                           "actual_starter": actual_starter, "stats": stats})
    _need(starters <= 1, "native NHL side declares multiple actual starting goalies")
    return {"players": sorted(result, key=lambda item: item["player_id"]), "missing_groups": missing,
            "availability": None, "pregame_starter": None}


def normalize_nhl_boxscore(payload, *, requested_game_id, observed_at, expected_teams=None):
    """Normalize one actual native body; optional teams bind an owning request.

    Only reviewed regular-season/playoff seasons are supported. OFF is the
    measured terminal state; FUT/PRE can retain unavailable source coverage,
    never completed exposure. No preevent publication proof is invented.
    """
    _need(isinstance(observed_at, datetime), "native NHL observed_at must be an actual aware datetime")
    receipt = canonical_timestamp(observed_at)
    requested = _game_id(requested_game_id)
    native = _native(payload)
    _need(_game_id(native.get("id")) == requested, "native NHL response ID differs from requested game")
    season = native.get("season")
    game_type = native.get("gameType")
    _need(type(season) is int and season in _SEASONS and season == requested // 1000000 * 10000 + requested // 1000000 + 1,
          "native NHL season is unsupported or contradicts game ID")
    _need(type(game_type) is int and game_type in _FORMATS and game_type == requested // 10000 % 100,
          "native NHL game type is unsupported or contradicts game ID")
    _need(type(native.get("startTimeUTC")) is str, "native NHL scheduled start is missing")
    start = canonical_timestamp(native["startTimeUTC"])
    state = native.get("gameState")
    _need(type(state) is str and state in {"OFF", "FUT", "PRE"}, "native NHL game is not reviewed terminal/future state")
    _need(native.get("gameScheduleState") in (None, "OK"), "native NHL schedule state is unsupported")
    completed = state == "OFF"
    _need(not completed or start < receipt, "native NHL completed start must precede actual receipt")
    neutral = native.get("neutralSite")
    _need(neutral is None or type(neutral) is bool, "native NHL neutral-site fact must be boolean or unknown")
    sides = {side: _object(native.get(side + "Team"), side + "Team") for side in ("home", "away")}
    identifiers = {side: _integer(team.get("id"), "team ID", minimum=1) for side, team in sides.items()}
    _need(identifiers["home"] != identifiers["away"], "native NHL home/away IDs coincide")
    if expected_teams is not None:
        _need(type(expected_teams) is tuple and len(expected_teams) == 2, "native NHL expected team binding must be home/away tuple")
        expected = tuple(_integer(value, "expected team ID", minimum=1) for value in expected_teams)
        _need(expected == (identifiers["home"], identifiers["away"]), "native NHL response teams differ from requested context")
    phase, maximum = _terminal(native, game_type, completed)
    scores = {side: _integer(team.get("score"), "team score", maximum=100, optional=not completed) for side, team in sides.items()}
    if completed:
        _need(scores["home"] != scores["away"], "native NHL terminal score cannot be tied")
        _need(phase == "REG" or abs(scores["home"] - scores["away"]) == 1, "native NHL OT/SO terminal winner gap differs")
    else:
        _need(all(score is None for score in scores.values()), "native NHL future boxscore cannot claim played score")
    key = f"nhl:ice_hockey:{requested}"
    event = {"event_key": key, "sport": "ice_hockey", "competition": "nhl", "format": _FORMATS[game_type],
             "home_id": f"nhl:ice_hockey:team:{identifiers['home']}", "away_id": f"nhl:ice_hockey:team:{identifiers['away']}",
             "scheduled_start": start, "schedule_revision": digest({"event_key": key, "scheduled_start": start}),
             "status": "completed" if completed else "scheduled"}
    collection = native.get("playerByGameStats") or {}
    seen = set()
    teams = {event[side + "_id"]: _players(collection.get(side + "Team"), team_id=identifiers[side],
              maximum=maximum, completed=completed, seen=seen) for side in ("home", "away")}
    data = {"total_toi_scope": "whole_game", "actual_start": None, "actual_end": None,
            "terminal_phase": phase, "final_score": scores,
            "regulation_score": dict(scores) if phase == "REG" else None, "teams": teams}
    content = {"schema": 1, "source_schema": SCHEMA,
               "request": {"game_id": requested, "endpoint": f"https://api-web.nhle.com/v1/gamecenter/{requested}/boxscore"},
               "native": native, "event": event,
               "scope": {"season": season, "game_type": game_type, "neutral_site": neutral},
               "data": data, "status": event["status"]}
    row = normalize_observation({"event_key": key, "sport": "ice_hockey", "competition": "nhl", "format": event["format"],
        "subject_id": key + ":participants:" + digest(identifiers), "kind": "native_boxscore", "source": "nhl",
        "source_schema": SCHEMA, "source_revision": digest(content), "schedule_revision": event["schedule_revision"],
        "published_at": None, "publication_proof": None, "valid_from": start, "valid_until": None,
        "complete": False, "payload": content}, observed_at=observed_at)
    _need(len(canonical_bytes(row)) <= MAX_SOURCE_BYTES, "native NHL normalized content bytes exceed bound")
    return row


def validate_nhl_boxscore_receipt(row):
    """Replay the owning native rules, not just B1's content/hash envelope."""
    _need(type(row) is dict and OBSERVATION_FIELDS.issubset(row), "native NHL receipt is incomplete")
    payload = row["payload"]
    require_object(payload, {"schema", "source_schema", "request", "native", "event", "scope", "data", "status"}, label="native NHL stored payload")
    require_object(payload["request"], {"game_id", "endpoint"}, label="native NHL stored request")
    _need(type(row.get("observed_at")) is str, "native NHL stored receipt lacks actual clock")
    try:
        observed = datetime.fromisoformat(row["observed_at"])
    except ValueError as exc:
        raise ContextContractError("native NHL stored receipt clock is invalid") from exc
    expected = normalize_nhl_boxscore(payload["native"], requested_game_id=payload["request"]["game_id"], observed_at=observed)
    _need(canonical_bytes(expected) == canonical_bytes({key: row[key] for key in OBSERVATION_FIELDS}),
          "native NHL stored source projection differs")
    return payload


def append_nhl_boxscore_batch(path, responses, *, max_new_payload_bytes):
    """Persist at most 512 actual receipts through existing atomic bounded B1.

    Each tuple is (actual native body, actual requested game ID, actual aware
    receipt). One content BLOB per revision, never copied into predictions.
    """
    _need(type(responses) is tuple and len(responses) <= MAX_BATCH, "native NHL source batch must be bounded tuple")
    rows = []
    for response in responses:
        _need(type(response) is tuple and len(response) == 3, "native NHL source batch item must bind body/ID/receipt")
        payload, requested, observed = response
        rows.append((normalize_nhl_boxscore(payload, requested_game_id=requested, observed_at=observed), observed))
    return append_bounded_observation_batch(path, tuple(rows), max_new_payload_bytes=max_new_payload_bytes)
