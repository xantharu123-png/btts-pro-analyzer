"""Normalize bound API-Football fixture facts, never estimated player effects.

``lineups`` and ``appearances`` accept full fixture-detail envelopes, not bare
team/season objects: only the envelope proves event, team and schedule scope.
This adapter makes no network calls. Callers persist its B1 records with the
actual fetch clock. Endpoint success is not a claim of a complete absence list.
"""
from __future__ import annotations

from datetime import datetime

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, normalize_observation,
    require_list, require_number, validate_event,
)


def _id(value, kind):
    if type(value) is not int or value <= 0:
        raise ContextContractError(f"football {kind} requires a positive native integer ID")
    return f"api-football:{kind}:{value}"


def _detail_event(detail):
    try:
        fixture = detail["fixture"]
        key = _id(fixture["id"], "football")
        start = canonical_timestamp(fixture["date"])
        status = fixture["status"]["short"]
        home = _id(detail["teams"]["home"]["id"], "team")
        away = _id(detail["teams"]["away"]["id"], "team")
        league = detail["league"]["id"]
        _id(league, "league")
    except (KeyError, TypeError) as exc:
        raise ContextContractError("football context needs a complete native fixture envelope") from exc
    return validate_event({
        "event_key": key, "sport": "football", "competition": str(league), "format": "90min",
        "home_id": home, "away_id": away, "scheduled_start": start,
        "schedule_revision": digest({"event_key": key, "scheduled_start": start}),
        "status": ("completed" if status in {"FT", "AET", "PEN"} else
                   "scheduled" if status in {"NS", "TBD", "PST"} else
                   "cancelled" if status in {"CANC", "ABD", "AWD", "WO"} else "started"),
    })


def _bind(event, fixture, *, league, team=None):
    if _id(fixture.get("id"), "football") != event["event_key"]:
        return False
    if canonical_timestamp(fixture.get("date")) != event["scheduled_start"]:
        raise ContextContractError("football fact belongs to a different schedule revision")
    _id(league.get("id"), "league")
    if str(league["id"]) != event["competition"]:
        raise ContextContractError("football fact has a conflicting competition identity")
    if team is not None and _id(team.get("id"), "team") not in {event["home_id"], event["away_id"]}:
        raise ContextContractError("football fact has a conflicting team identity")
    return True


def _collection_digest(event_key, schedule_revision, kind, team_id, payloads):
    """Bind the WHOLE content revision, not merely the list of player IDs."""
    rows = [{key: value for key, value in payload.items()
             if key not in {"reported_player_ids", "collection_hash"}} for payload in payloads]
    return digest({"event_key": event_key, "schedule_revision": schedule_revision,
                   "kind": kind, "team_id": team_id,
                   "players": sorted(rows, key=lambda row: row["player_id"])})


def _record(event, subject, kind, payload, *, observed_at, complete, schema, collection_payloads=None):
    payload = {"scheduled_start": event["scheduled_start"], **payload}
    if kind in {"appearance", "confirmed_lineup"}:
        # Every projected player retains its reported TEAM cohort. B1 selects
        # per subject; downstream readers also need to revoke removed members
        # when the source replaces a whole fixture's team list.
        payload = dict(payload)
        members = [payload] if collection_payloads is None else [
            {"scheduled_start": event["scheduled_start"], **item} for item in collection_payloads]
        payload["reported_player_ids"] = sorted(item["player_id"] for item in members)
        payload["collection_hash"] = _collection_digest(event["event_key"], event["schedule_revision"],
                                                        kind, payload["team_id"], members)
    return normalize_observation({
        "event_key": event["event_key"], "sport": "football", "competition": event["competition"],
        "format": event["format"], "subject_id": subject, "kind": kind, "source": "api-football",
        "source_schema": schema, "source_revision": digest(payload),
        "schedule_revision": event["schedule_revision"], "published_at": None, "publication_proof": None,
        "valid_from": canonical_timestamp(observed_at), "valid_until": None,
        "complete": complete, "payload": payload,
    }, observed_at=observed_at)


def _empty_collection(event, team, kind, *, observed_at):
    """A received empty team list withdraws old projections, not their history."""
    payload = {"team_id": team, "scheduled_start": event["scheduled_start"], "reported_player_ids": [],
               "collection_hash": _collection_digest(event["event_key"], event["schedule_revision"], kind, team, [])}
    return normalize_observation({
        "event_key": event["event_key"], "sport": "football", "competition": event["competition"],
        "format": event["format"], "subject_id": team, "kind": kind, "source": "api-football",
        "source_schema": "fixture-players-v3-empty-v1" if kind == "appearance" else "lineups-v3-empty-v1",
        "source_revision": digest(payload), "schedule_revision": event["schedule_revision"],
        "published_at": None, "publication_proof": None, "valid_from": canonical_timestamp(observed_at),
        "valid_until": None, "complete": False, "payload": payload,
    }, observed_at=observed_at)


def _lineup_players(detail, event):
    output = {}
    teams_seen = set()
    for group in require_list(detail.get("lineups", []), "fixture lineups"):
        team = _id(group["team"]["id"], "team")
        if team not in {event["home_id"], event["away_id"]} or team in teams_seen:
            raise ContextContractError("lineup team is duplicated or outside its fixture")
        teams_seen.add(team)
        starters = require_list(group.get("startXI"), "starting eleven")
        bench = require_list(group.get("substitutes"), "substitutes")
        if len(starters) != 11:
            raise ContextContractError("confirmed lineup requires eleven distinct starters")
        for started, players in ((True, starters), (False, bench)):
            for item in players:
                player = _id(item["player"]["id"], "player")
                if player in output:
                    raise ContextContractError("lineup player identity is duplicated")
                output[player] = {"player_id": player, "team_id": team, "started": started,
                                  "role": item["player"].get("pos")}
    return output


def _appearance_records(detail, *, observed_at):
    event = _detail_event(detail)
    if event["status"] != "completed":
        return []
    observed = canonical_timestamp(observed_at)
    if event["scheduled_start"] >= observed:
        raise ContextContractError("completed appearance cannot follow its actual receipt")
    lineup = _lineup_players(detail, event)
    regulation = detail["fixture"]["status"]["short"] == "FT"
    records, seen, seen_teams = [], set(), set()
    for group in require_list(detail.get("players", []), "fixture player statistics"):
        team = _id(group["team"]["id"], "team")
        if team not in {event["home_id"], event["away_id"]} or team in seen_teams:
            raise ContextContractError("player statistics have a conflicting team binding")
        seen_teams.add(team)
        player_rows = require_list(group.get("players"), "team player statistics")
        team_payloads = []
        for item in player_rows:
            player = _id(item["player"]["id"], "player")
            if player in seen:
                raise ContextContractError("duplicate player appearance in one fixture")
            seen.add(player)
            stats = require_list(item.get("statistics"), "per-fixture statistics")
            if len(stats) != 1 or type(stats[0]) is not dict or type(stats[0].get("games")) is not dict:
                raise ContextContractError("appearance requires one match-specific statistics row")
            stats = stats[0]
            games = stats["games"]
            minutes = games.get("minutes")
            if minutes is not None:
                require_number(minutes, "reported match minutes", minimum=0, maximum=90 if regulation else 120)
            substitute = games.get("substitute")
            if substitute is not None and type(substitute) is not bool:
                raise ContextContractError("substitute flag must be boolean or unknown")
            listed = lineup.get(player)
            if listed is not None and listed["team_id"] != team:
                raise ContextContractError("appearance and lineup disagree on player team")
            started = None if substitute is None else not substitute
            if listed is not None:
                if started is not None and started != listed["started"]:
                    raise ContextContractError("appearance and lineup disagree on actual start")
                started = listed["started"]
            payload = {
                "player_id": player, "team_id": team, "fixture_id": event["event_key"],
                "minutes": minutes, "regulation_minutes": minutes if regulation else None,
                "exposure_kind": "regulation_reported" if regulation else "total_only",
                "started": started, "role": games.get("position"),
                "result_observed_at": observed, "event_start": None, "event_end": None,
                "scheduled_start": event["scheduled_start"],
                "performance": {key: stats.get(key) for key in ("goals", "shots", "passes", "tackles", "duels", "cards")},
            }
            team_payloads.append(payload)
        for payload in team_payloads:
            records.append(_record(event, payload["player_id"], "appearance", payload, observed_at=observed_at,
                                   complete=payload["minutes"] is not None, schema="fixture-players-v3-context-v1",
                                   collection_payloads=team_payloads))
    reported_teams = {row["payload"]["team_id"] for row in records}
    for team in sorted({event["home_id"], event["away_id"]} - reported_teams):
        records.append(_empty_collection(event, team, "appearance", observed_at=observed_at))
    return records


def normalize_football_context(event: dict, *, injuries: list[dict], lineups: list[dict],
                               appearances: list[dict], observed_at: datetime) -> tuple[dict, ...]:
    """Return B1 content, preserving partial coverage and original native facts.

    A ``Missing Fixture`` row is a source-reported absence, not an independently
    verified diagnosis. Lineup facts are separate revisions and are not turned
    into 90-minute forecasts. Historical fixture dates remain planned times.
    """
    event = validate_event(event)
    if (event["sport"] != "football" or event["format"] != "90min"
            or not event["event_key"].startswith("api-football:football:")):
        raise ContextContractError("this source owns only native API-Football fixtures")
    canonical_timestamp(observed_at)
    for rows in (injuries, lineups, appearances):
        require_list(rows, "football context source rows")
    records, absent = [], {event["home_id"]: set(), event["away_id"]: set()}
    for injury in injuries:
        try:
            if not _bind(event, injury["fixture"], league=injury["league"], team=injury["team"]):
                continue
            raw = injury["player"]
            player, team = _id(raw["id"], "player"), _id(injury["team"]["id"], "team")
        except (KeyError, TypeError) as exc:
            raise ContextContractError("absence requires fixture/team/player source binding") from exc
        reported_type, reason = raw.get("type"), raw.get("reason")
        if reason is not None and type(reason) is not str:
            raise ContextContractError("absence reason must be source text or unknown")
        category = {"Coach's decision": "selection", "Inactive": "inactive",
                    "Transfer negotiations": "transfer", "Red Card": "suspension"}.get(reason)
        category = category or ("injury" if reason and "injury" in reason.lower() else "unspecified")
        status = ("suspended" if reported_type == "Missing Fixture" and category == "suspension" else
                  "out" if reported_type == "Missing Fixture" else
                  "doubtful" if reported_type == "Doubtful" else "unknown")
        payload = {"player_id": player, "team_id": team, "status": status,
                   "reported_type": reported_type, "reported_reason": reason, "absence_category": category}
        records.append(_record(event, player, "availability", payload, observed_at=observed_at,
                               complete=False, schema="injuries-v3-context-v1"))
        absent[team].add(player)
    for team, players in absent.items():
        records.append(_record(event, team, "availability", {"team_id": team,
                               "reported_players": sorted(players), "collection_complete": False},
                               observed_at=observed_at, complete=False, schema="injuries-v3-coverage-v1"))
    for detail in lineups:
        actual = _detail_event(detail)
        if actual["event_key"] != event["event_key"]:
            continue
        _bind(event, detail["fixture"], league=detail["league"])
        if (actual["home_id"], actual["away_id"]) != (event["home_id"], event["away_id"]):
            raise ContextContractError("lineup fixture has a different participant orientation")
        player_rows = _lineup_players(detail, event)
        for player, payload in player_rows.items():
            members = [{**item, "status": "available"} for item in player_rows.values() if item["team_id"] == payload["team_id"]]
            records.append(_record(event, player, "confirmed_lineup", {**payload, "status": "available"},
                                   observed_at=observed_at, complete=True, schema="lineups-v3-context-v1",
                                   collection_payloads=members))
        for team in sorted({event["home_id"], event["away_id"]} - {row["team_id"] for row in player_rows.values()}):
            records.append(_empty_collection(event, team, "confirmed_lineup", observed_at=observed_at))
    for detail in appearances:
        records.extend(_appearance_records(detail, observed_at=observed_at))
    # Identical repeated envelopes are idempotent; genuinely conflicting facts
    # remain distinct for B1's conflict handling, never "last row wins".
    return tuple({digest(row): row for row in records}.values())
