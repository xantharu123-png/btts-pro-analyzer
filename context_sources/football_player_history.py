"""Bounded context-only discovery of already observed native player events.

Headers identify candidate event keys, not certified appearances or complete
history. The caller must load and validate each WHOLE predecision event pool,
including revisions/withdrawals, under its existing byte and receipt bounds.
No provider call, outcome label, population rewrite or player-name join belongs
here. The fourteen-day receipt scope is not an actual match-end load window.
"""
from datetime import datetime, timedelta

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp,
    require_object, validate_event,
)
from context_models.football import (
    _AVAILABILITY_FIELDS, _LINEUP_FIELDS,
    _appearance_payload, _collection_conflicts, _is_empty_collection,
    _native_identity, _selected,
)
from context_models.replay import ReplayUnavailable
from context_observations import _check_selected_row, factor_state, freshness_policy


MAX_EVENTS = 4096


def _target_players(rows, *, event, cutoff):
    """Use validated selected membership, not every historical receipt header."""
    relevant = tuple(row for row in rows if row["kind"] in {
        "appearance", "availability", "confirmed_lineup"})
    chosen = _selected(relevant, cutoff=cutoff)
    conflicts = _collection_conflicts(chosen)
    players, current = set(), {}
    target_teams = {event["home_id"], event["away_id"]}
    for row in chosen:
        if _is_empty_collection(row):
            continue  # The selector has already withdrawn obsolete members.
        if row["kind"] == "appearance":
            payload = _appearance_payload(row, cutoff=cutoff)
            if payload["team_id"] in target_teams and row["subject_id"] not in conflicts:
                players.add(row["subject_id"])
            continue
        if row["event_key"] != event["event_key"] or row["schedule_revision"] != event["schedule_revision"]:
            continue
        if not _native_identity(row["subject_id"], "player"):
            continue  # Team coverage diagnostics cannot authorize player joins.
        fields = _LINEUP_FIELDS if row["kind"] == "confirmed_lineup" else _AVAILABILITY_FIELDS
        schema = "lineups-v3-context-v1" if row["kind"] == "confirmed_lineup" else "injuries-v3-context-v1"
        payload = require_object(row["payload"], fields, label="current native football player")
        if (row["source_schema"] != schema or payload["player_id"] != row["subject_id"]
                or not _native_identity(payload["player_id"], "player")
                or payload["team_id"] not in target_teams
                or (row["competition"], row["format"]) != (event["competition"], event["format"])
                or canonical_timestamp(payload["scheduled_start"]) != event["scheduled_start"]):
            raise ContextIntegrityError("current player history cohort binding mismatch")
        current.setdefault((row["subject_id"], row["kind"]), []).append(row)
    kickoff = datetime.fromisoformat(event["scheduled_start"])
    for (player, kind), group in current.items():
        if player in conflicts:
            continue
        state = factor_state(tuple(group), cutoff=cutoff, scheduled_start=kickoff,
            policy=freshness_policy(kind, schedule_revision=event["schedule_revision"], requires_complete=False))
        if state["state"] == "available":
            players.add(player)
    return tuple(sorted(players))


def player_event_keys(connection, rows, *, event, cutoff, max_events):
    """Additional native appearance event keys for a fixed target cohort.

    Candidate receipts are in [cutoff - 14 days, cutoff]. Already supplied
    event pools are omitted; unrelated players never extend the cohort. Only
    index headers are read. Admission failure rejects the whole expansion,
    never an arbitrary convenient subset. The owning reader validates actual
    bodies and collection withdrawals after retrieving these whole events.
    """
    if type(rows) is not tuple:
        raise ContextContractError("player history needs selected B1 receipt tuples")
    if type(max_events) is not int or not 0 <= max_events <= MAX_EVENTS:
        raise ContextContractError("player history event bound must be a finite integer")
    decision = canonical_timestamp(cutoff)
    if type(cutoff) is str and cutoff != decision:
        raise ContextContractError("player history cutoff must use canonical UTC")
    instant = datetime.fromisoformat(decision)
    event = validate_event(event)
    if (event["sport"] != "football" or event["format"] != "90min"
            or not _native_identity(event["event_key"], "football")
            or any(not _native_identity(event[side], "team") for side in ("home_id", "away_id"))
            or event["status"] != "scheduled" or decision >= event["scheduled_start"]):
        raise ContextContractError("player history requires a native prematch football event")
    for row in rows:
        _check_selected_row(row)
    players = _target_players(rows, event=event, cutoff=instant)
    if not players:
        return ()
    if len(players) > MAX_EVENTS:
        raise ReplayUnavailable("player_history_cohort_bound_exceeded")
    known = tuple(sorted({event["event_key"], *(row["event_key"] for row in rows)}))
    if len(known) > MAX_EVENTS:
        raise ReplayUnavailable("player_history_known_event_bound_exceeded")
    player_marks = ",".join("?" for _ in players)
    known_marks = ",".join("?" for _ in known)
    candidates = connection.execute(
        "SELECT DISTINCT event_key FROM context_observations "
        "WHERE source='api-football' AND kind='appearance' "
        f"AND subject_id IN ({player_marks}) AND observed_at>=? AND observed_at<=? "
        f"AND event_key NOT IN ({known_marks}) ORDER BY event_key LIMIT ?",
        (*players, canonical_timestamp(instant - timedelta(days=14)), decision, *known, max_events + 1),
    ).fetchall()
    if len(candidates) > max_events:
        raise ReplayUnavailable("player_history_event_bound_exceeded")
    keys = tuple(row[0] for row in candidates)
    if any(not _native_identity(key, "football") for key in keys):
        raise ContextIntegrityError("player history header has a nonnative event key")
    return keys
