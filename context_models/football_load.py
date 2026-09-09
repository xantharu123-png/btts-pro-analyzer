"""C1 observed football load and source-qualified weather feature mechanics.

No coefficient, probability adjustment, provider request or full-history claim.
The raw API-Football projection uses only already measured native fixture/status
fields. Exact end/duration can enter only through a separate internally resolved
transport, never from scheduled date, elapsed=90, or a guessed travel schedule.
New feature versions deliberately do not inherit the injury-only B5 artifact.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import re

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, normalize_observation,
    require_number, require_object, validate_base_distribution, validate_event,
    validate_feature_vector,
)
from context_models.tennis import recovery_bounds
from context_observations import factor_state, freshness_policy
from context_sources.weather import (
    METRICS, SOURCE_SCHEMA as WEATHER_SCHEMA, validate_weather_record, weather_metadata_gap, weather_window,
)

SCHEDULE_SCHEMA = "api-football-workload-v1"
RAW_SCHEMA = "api-football-fixtures-v3"
INTERNAL_SCHEMA = "football-completed-transport-v1"
WINDOWS = (1, 3, 7)
TERMINALS = {"FT": "completed", "AET": "completed", "PEN": "completed",
             "NS": "scheduled", "TBD": "scheduled", "PST": "scheduled",
             "CANC": "cancelled", "ABD": "cancelled", "AWD": "cancelled", "WO": "cancelled",
             **{key: "started" for key in ("1H", "HT", "2H", "ET", "BT", "P", "INT", "SUSP", "LIVE")}}
INPUT_FIELDS = {"fixture_id", "home_id", "away_id", "competition_id", "season", "status", "scheduled_start",
                "actual_start", "actual_end", "minutes", "result_observed_at"}
PAYLOAD_FIELDS = INPUT_FIELDS | {"schema", "input_schema", "team_id", "opponent_id", "terminal", "history_scope"}


def _instant(value):
    return datetime.fromisoformat(canonical_timestamp(value))


def _id(value, label):
    if type(value) is not int or value <= 0:
        raise ContextContractError(f"{label} requires a positive native integer")
    return value


def _native(value, kind):
    if type(value) is not str or re.fullmatch(rf"api-football:{kind}:[1-9][0-9]*", value) is None:
        raise ContextContractError(f"invalid native football {kind} identity")
    return value


def _time(value):
    if value is None:
        return None
    if type(value) is not str:
        raise ContextContractError("source times must be ISO strings or unknown")
    return canonical_timestamp(value)


def _raw_fixture(row, observed):
    """Explicit price-free projection of the measured fixture endpoint shape."""
    if type(row) is not dict or row.get("challenge_source") not in (None, "api-football", "api-football-ft-tail"):
        raise ContextContractError("CSV or unknown source cannot become a native completed fixture")
    try:
        fixture, league, teams = row["fixture"], row["league"], row["teams"]
        return {"fixture_id": fixture["id"], "home_id": teams["home"]["id"], "away_id": teams["away"]["id"],
                "competition_id": league["id"], "season": league["season"], "status": fixture["status"]["short"],
                "scheduled_start": fixture["date"], "actual_start": None, "actual_end": None,
                "minutes": None, "result_observed_at": observed}
    except (KeyError, TypeError) as exc:
        raise ContextContractError("fixture has no complete native schedule/status identity") from exc


def _checked_input(row, *, observed):
    require_object(row, INPUT_FIELDS, label="resolved football timeline input")
    item = deepcopy(row)
    for key in ("fixture_id", "home_id", "away_id", "competition_id", "season"):
        _id(item[key], key)
    if item["home_id"] == item["away_id"]:
        raise ContextContractError("completed participants must be distinct")
    if type(item["status"]) is not str or item["status"] not in TERMINALS:
        raise ContextContractError("unreviewed football terminal status")
    for key in ("scheduled_start", "actual_start", "actual_end", "result_observed_at"):
        item[key] = _time(item[key])
    receipt = item["result_observed_at"]
    if receipt is None or receipt > observed or item["scheduled_start"] is None:
        raise ContextContractError("timeline must retain schedule and actual causal receipt")
    start, end = item["actual_start"], item["actual_end"]
    if ((start is not None and start > receipt) or (end is not None and end > receipt)
            or (start is not None and end is not None and start >= end)):
        raise ContextContractError("completed timeline chronology is inconsistent")
    if TERMINALS[item["status"]] == "completed":
        if item["scheduled_start"] >= receipt:
            raise ContextContractError("a future scheduled fixture is not an observed completion")
    elif end is not None or item["minutes"] is not None:
        raise ContextContractError("unplayed/unfinished status cannot claim completed load")
    if item["minutes"] is not None:
        minutes = require_number(item["minutes"], "observed match minutes", minimum=0)
        if minutes == 0:
            raise ContextContractError("unknown played duration is not zero minutes")
        if start is not None and end is not None and minutes > (_instant(end) - _instant(start)).total_seconds() / 60:
            raise ContextContractError("observed duration exceeds the actual match interval")
    return item


def normalize_football_schedule(rows: tuple[dict, ...], *, observed_at: datetime,
                                source_schema: str = RAW_SCHEMA) -> tuple[dict, ...]:
    """Native timeline revisions, including nonplayed withdrawals of old claims.

    No completed fixture here proves an exhaustive domestic/international history.
    The optional internal schema is mechanics for a source-resolved actual end;
    it is not a new provider or a verified historical publication-time claim.
    """
    if type(rows) is not tuple or not isinstance(observed_at, datetime):
        raise ContextContractError("football schedule needs tuple rows and actual ingestion datetime")
    if source_schema not in (RAW_SCHEMA, INTERNAL_SCHEMA):
        raise ContextContractError("unreviewed football schedule input schema")
    observed = canonical_timestamp(observed_at)
    result = []
    for raw in rows:
        item = _checked_input(_raw_fixture(raw, observed) if source_schema == RAW_SCHEMA else raw, observed=observed)
        identity = f"api-football:football:{item['fixture_id']}"
        home, away = f"api-football:team:{item['home_id']}", f"api-football:team:{item['away_id']}"
        for team, opponent in ((home, away), (away, home)):
            payload = {**item, "schema": 1, "input_schema": source_schema, "fixture_id": identity,
                       "home_id": home, "away_id": away, "team_id": team, "opponent_id": opponent,
                       "terminal": item["status"], "status": TERMINALS[item["status"]],
                       "history_scope": "observed-matches-only"}
            result.append(normalize_observation({
                "event_key": identity, "sport": "football", "competition": str(item["competition_id"]), "format": "90min",
                "subject_id": team, "kind": "workload", "source": "api-football", "source_schema": SCHEDULE_SCHEMA,
                "source_revision": digest(payload), "schedule_revision": digest({"event_key": identity, "scheduled_start": item["scheduled_start"]}),
                "published_at": None, "publication_proof": None, "valid_from": item["result_observed_at"], "valid_until": None,
                "complete": False, "payload": payload,
            }, observed_at=observed_at))
    return tuple({digest(row): row for row in result}.values())


def _validate_schedule_record(row):
    payload = require_object(row["payload"], PAYLOAD_FIELDS, label="football performed-load payload")
    if type(payload["schema"]) is not int or payload["schema"] != 1 or payload["input_schema"] not in (RAW_SCHEMA, INTERNAL_SCHEMA):
        raise ContextContractError("unreviewed normalized load schema")
    for key, kind in (("fixture_id", "football"), ("home_id", "team"), ("away_id", "team"), ("team_id", "team"), ("opponent_id", "team")):
        _native(payload[key], kind)
    raw = {key: payload[key] for key in INPUT_FIELDS}
    for key in ("fixture_id", "home_id", "away_id"):
        raw[key] = int(raw[key].rsplit(":", 1)[1])
    raw["status"] = payload["terminal"]
    normalized = _checked_input(raw, observed=row["observed_at"])
    if any(normalized[key] != raw[key] for key in raw):
        raise ContextContractError("normalized timeline clocks are not canonical")
    if (payload["status"] != TERMINALS[payload["terminal"]] or payload["history_scope"] != "observed-matches-only"
            or {payload["team_id"], payload["opponent_id"]} != {payload["home_id"], payload["away_id"]}
            or row["event_key"] != payload["fixture_id"] or row["subject_id"] != payload["team_id"]
            or row["source"] != "api-football" or row["source_schema"] != SCHEDULE_SCHEMA
            or row["sport"] != "football" or row["format"] != "90min" or row["kind"] != "workload"
            or row["competition"] != str(payload["competition_id"]) or row["complete"] is not False
            or row["source_revision"] != digest(payload) or row["published_at"] is not None
            or row["publication_proof"] is not None or row["valid_from"] != payload["result_observed_at"]
            or row["valid_until"] is not None or row["schedule_revision"] != digest({
                "event_key": row["event_key"], "scheduled_start": payload["scheduled_start"]})):
        raise ContextContractError("native load identity/source/receipt binding mismatch")
    if payload["input_schema"] == RAW_SCHEMA and any(payload[key] is not None for key in ("actual_start", "actual_end", "minutes")):
        raise ContextContractError("this raw API projection has no observed end or duration")
    return payload


def _context(event, base, cutoff):
    if not isinstance(cutoff, datetime):
        raise ContextContractError("football context cutoff must be an aware datetime")
    event, base = validate_event(event), validate_base_distribution(base)
    cutoff = _instant(cutoff)
    if event["sport"] != "football" or event["format"] != "90min" or base["family"] != "football:goals:90min":
        raise ContextContractError("football weather/load owns only the regulation goal context")
    if event["event_key"] != base["event_key"] or base["cutoff"] != canonical_timestamp(cutoff):
        raise ContextContractError("football event/base/decision revision mismatch")
    if base["reference_weights"]["kind"] == "football-goals-v1":
        for side, head in base["reference_weights"]["heads"].items():
            for name, component in head["components"].items():
                participant = "home_id" if (side == "home") == name.endswith("attack") else "away_id"
                if component["team_id"] is not None and component["team_id"] != event[participant]:
                    raise ContextContractError("football baseline team orientation differs from the target")
    if cutoff >= _instant(event["scheduled_start"]):
        raise ContextContractError("football context decision must precede kickoff")
    reference = digest({"version": "football-context-reference-v2", "base_hash": digest(base),
                        "event_hash": digest(event), "preprocessing": []})
    return event, cutoff, reference


def _feature_builder(event, decision, reference, version):
    values, states, refs = {}, {}, {}

    def put(name, value, used=(), state=None):
        state = state or ("missing" if value is None else "available")
        values[name] = value if state == "available" else None
        states[name] = state
        refs[name] = sorted({row["digest"] for row in used}) if state == "available" else []

    def finish(case):
        return validate_feature_vector({"version": version, "event_key": event["event_key"], "cutoff": canonical_timestamp(decision),
            "values": values, "states": states, "refs": refs, "coverage": {"version": version + ".coverage", "case": case},
            "reference_hash": reference})
    return values, states, refs, put, finish


def _checked_receipts(rows, *, kind, cutoff, kickoff):
    if type(rows) is not tuple:
        raise ContextContractError("context features require selected B1 receipt tuples")
    for row in rows:
        if type(row) is not dict:
            raise ContextContractError("context features require selected B1 receipts")
        factor_state((row,), cutoff=cutoff, scheduled_start=kickoff,
                     policy=freshness_policy(kind, schedule_revision=row.get("schedule_revision"), requires_complete=False))


def football_weather_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime) -> dict:
    """Strict current outdoor-forecast features; no archive/proxy-time shortcut."""
    event, decision, reference = _context(event, base, cutoff)
    kickoff = _instant(event["scheduled_start"])
    _, _, _, put, finish = _feature_builder(event, decision, reference, "football-weather-features-v1")
    _checked_receipts(observations, kind="weather", cutoff=decision, kickoff=kickoff)
    statuses = tuple(row for row in observations if row["kind"] == "event_status" and row["event_key"] == event["event_key"])
    if any((row["sport"], row["competition"], row["format"]) != (event["sport"], event["competition"], event["format"]) for row in statuses):
        raise ContextContractError("target status and weather scope differ")
    status_check = factor_state(statuses, cutoff=decision, scheduled_start=kickoff,
        policy=freshness_policy("weather", schedule_revision=event["schedule_revision"], requires_complete=False))
    eligible = []
    for row in observations:
        if row["kind"] != "weather" or row["source_schema"] != WEATHER_SCHEMA:
            continue
        validate_weather_record(row)
        if row["event_key"] != event["event_key"] or row["competition"] != event["competition"]:
            raise ContextContractError("weather observations mix distinct native event scopes")
        if row["evidence_class"] == "prospective" and row["observed_at"] <= canonical_timestamp(decision):
            eligible.append(row)
    # Recency orders revisions WITHIN a source, never gives one source an
    # implicit priority over a different fresh source. Select before checking
    # metadata/intervals so a newer unknown revision cannot revive an older one.
    latest = {}
    for row in eligible:
        latest[row["source"]] = max(latest.get(row["source"], row["observed_at"]), row["observed_at"])
    selected = {row["digest"]: row for row in eligible if row["observed_at"] == latest[row["source"]]}
    current = tuple(row for row in selected.values() if row["schedule_revision"] == event["schedule_revision"]
                    and row["payload"]["event_hash"] == digest(event))
    policy = freshness_policy("weather", schedule_revision=event["schedule_revision"], requires_complete=False)
    evaluated = factor_state((*current, *statuses), cutoff=decision, scheduled_start=kickoff, policy=policy)
    source_revisions = {}
    for row in current:
        seconds = min(policy["weather_max_age_seconds"],
                      policy["source_max_age_seconds"].get(row["source"], policy["weather_max_age_seconds"]))
        if decision < _instant(row["observed_at"]) + timedelta(seconds=seconds):
            source_revisions.setdefault(row["source"], set()).add(row["content_digest"])
    state, case, payload, used = "missing", "missing-source", None, ()
    if event["status"] != "scheduled" or status_check["state"] == "not_applicable":
        state, case = "not_applicable", "event-not-scheduled"
    elif selected and not current:
        state, case = "stale", "different-event-revision"
    elif any(len(revisions) > 1 for revisions in source_revisions.values()) or evaluated["state"] == "conflicting":
        # A simultaneous unknown alternative from the same fresh source must
        # not disappear merely because its interval cannot be used numerically.
        state, case = "conflicting", "conflicting-source-revision"
    elif current:
        usable = tuple(row for row in current if row["digest"] in evaluated["usable_refs"])
        if evaluated["state"] == "available" and usable:
            payload = usable[0]["payload"]
            if (gap := weather_metadata_gap(payload)) is not None:
                case = gap
            elif not weather_window(issued_at=_instant(payload["issued_at"]), valid_from=_instant(payload["valid_from"]),
                    valid_until=_instant(payload["valid_until"]), decision_at=decision, kickoff=kickoff):
                state, case = "stale", "ineligible-forecast-window"
            elif payload["venue"]["roof"] == "closed":
                state, case = "not_applicable", "closed-roof-outdoor-factor"
            else:
                state, case, used = "available", "strict-current-outdoor-forecast", usable
        elif len(current) == 1 and (gap := weather_metadata_gap(current[0]["payload"])) is not None:
            case = gap
        else:
            state, case = evaluated["state"], evaluated["state"] + "-forecast-receipt"
    for key in METRICS:
        value = payload[key] if state == "available" else None
        put(key, value, used if value is not None else (), None if state == "available" else state)
    horizon = (_instant(payload["valid_at"]) - _instant(payload["issued_at"])).total_seconds() / 3600 if state == "available" else None
    put("forecast_horizon_hours", horizon, used, None if state == "available" else state)
    if state == "available" and any(payload[key] is None for key in METRICS):
        case += ".partial-values"
    return finish(case)


def _usable_schedule(rows, *, cutoff, kickoff):
    _checked_receipts(rows, kind="workload", cutoff=cutoff, kickoff=kickoff)
    by_event = {}
    for row in rows:
        if row["kind"] != "workload" or row["source_schema"] != SCHEDULE_SCHEMA:
            continue
        _validate_schedule_record(row)
        if row["evidence_class"] == "prospective" and row["observed_at"] <= canonical_timestamp(cutoff):
            by_event.setdefault(row["event_key"], []).append(row)
    usable, conflicts = [], set()
    for history in by_event.values():
        newest = max(row["observed_at"] for row in history)
        group = list({row["digest"]: row for row in history if row["observed_at"] == newest}.values())
        teams = {row["payload"][key] for row in group for key in ("home_id", "away_id")}
        identities = {digest({key: value for key, value in row["payload"].items() if key not in {"team_id", "opponent_id"}}) for row in group}
        if len(teams) != 2 or len(identities) != 1 or {row["subject_id"] for row in group} != teams:
            # A partial newest joint revision invalidates every old/new
            # participant's load claim. Never borrow an older counterpart or
            # silently erase the fixture so another match certifies exact rest.
            conflicts.update(row["payload"][key] for row in history for key in ("home_id", "away_id"))
            continue
        # Latest event-wide withdrawal wins even if an older terminal was valid.
        if group[0]["payload"]["status"] != "completed":
            continue
        ended = group[0]["payload"]["actual_end"]
        if ended is not None and ended >= canonical_timestamp(cutoff):
            continue
        evaluated = factor_state(tuple(group), cutoff=cutoff, scheduled_start=kickoff,
            policy=freshness_policy("workload", schedule_revision=group[0]["schedule_revision"], requires_complete=False))
        if evaluated["state"] == "conflicting":
            conflicts.update(teams)
        elif evaluated["state"] == "available":
            usable.extend(row for row in group if row["digest"] in evaluated["usable_refs"])
    return usable, conflicts


def football_schedule_features(event: dict, completed: tuple[dict, ...], *, cutoff: datetime, base: dict) -> dict:
    """Observed native domestic+international load, not complete team history.

    Performed windows are [cutoff - N days, cutoff) by actual match END. Unknown
    end cannot enter a performed window. Recovery exactness refers only to the
    observed subset; prospective receipt supplies a conservative lower bound.
    """
    event, decision, reference = _context(event, base, cutoff)
    kickoff = _instant(event["scheduled_start"])
    values, states, refs, put, finish = _feature_builder(event, decision, reference, "football-observed-load-v1")
    usable, conflicts = _usable_schedule(completed, cutoff=decision, kickoff=kickoff)
    cases, side_metrics = [], set()
    for side in ("home", "away"):
        team = event[f"{side}_id"]
        blocked = "not_applicable" if event["status"] != "scheduled" else "conflicting" if team in conflicts else None
        rows = [row for row in usable if row["subject_id"] == team and row["event_key"] != event["event_key"]] if not blocked else []
        known = [row for row in rows if row["payload"]["actual_end"] is not None]
        unknown = [row for row in rows if row["payload"]["actual_end"] is None]
        put(f"observed_matches_total_{side}", len(rows) if rows else None, rows, blocked)
        side_metrics.add("observed_matches_total")
        for days in WINDOWS:
            first, last = canonical_timestamp(decision - timedelta(days=days)), canonical_timestamp(decision)
            window = [row for row in known if first <= row["payload"]["actual_end"] < last]
            measured = [row for row in window if row["payload"]["minutes"] is not None]
            # A terminal receipt proves only an end upper bound. Strictly
            # earlier bounds exclude an unknown end; equality remains possible
            # at the inclusive window edge. No receipt is treated as an end.
            uncertain_window = any(row["payload"]["result_observed_at"] >= first for row in unknown)
            for name, value, used in ((f"observed_matches_{days}d", len(window) if window else None, window),
                                      (f"observed_minutes_{days}d", sum(row["payload"]["minutes"] for row in measured) if measured else None, measured),
                                      (f"observed_minutes_complete_{days}d", int(bool(window) and len(measured) == len(window) and not uncertain_window) if rows else None, rows),
                                      (f"history_complete_{days}d", 0 if rows else None, rows)):
                put(f"{name}_{side}", value, used, blocked)
                side_metrics.add(name)
        bounds = {"minimum_hours": None, "exact_hours": None}
        if rows:
            latest_receipt = max(_instant(row["payload"]["result_observed_at"]) for row in rows)
            latest_end = max((_instant(row["payload"]["actual_end"]) for row in known), default=None)
            exact_end = latest_end if latest_end is not None and all(
                _instant(row["payload"]["result_observed_at"]) <= latest_end for row in unknown
            ) else None
            bounds = recovery_bounds(next_start=kickoff, result_observed_at=latest_receipt, ended_at=exact_end)
        for kind in ("minimum", "exact"):
            name = f"observed_recovery_{kind}_hours"
            put(f"{name}_{side}", bounds[f"{kind}_hours"], rows, blocked)
            side_metrics.add(name)
        put(f"travel_hours_{side}", None, state=blocked)
        case = "no-history" if not rows else "receipt-bound" if unknown else "exact-observed"
        if unknown and bounds["exact_hours"] is not None:
            case = "bounded-irrelevant-end-times" if all(
                _instant(row["payload"]["result_observed_at"]) < decision - timedelta(days=max(WINDOWS)) for row in unknown
            ) else "partial-end-times-exact-rest"
        cases.append(blocked or case)
    for name in sorted(side_metrics):
        home, away = f"{name}_home", f"{name}_away"
        a, b = values[home], values[away]
        # Signed terms do not turn a missing side into a zero opponent.
        operands = set(refs[home]) | set(refs[away])
        used = [row for row in usable if row["digest"] in operands]
        state = next((flag for flag in ("not_applicable", "conflicting", "stale", "missing") if flag in (states[home], states[away])), None)
        put(name + "_delta", a - b if a is not None and b is not None else None, used, state)
    return finish("observed-only." + ".".join(cases))
