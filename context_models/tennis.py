"""Causal tennis load features, without a learned or heuristic fitness effect.

Window v1 is [cutoff - N * 24h, cutoff) in UTC, attributed by actual match END.
Only previously received terminal facts are used. Scheduled/tournament dates and
result receipts cannot place played work inside these performed-load windows.
Observed-subset completeness is separate from complete player-history coverage:
the currently measured source does not establish the latter, even for empty lists.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, validate_base_distribution,
    validate_event, validate_feature_vector,
)
from context_observations import factor_state, freshness_policy
from context_sources.tennis import SOURCE_SCHEMA, validate_workload_record


FEATURE_VERSION = "tennis-performed-load-v1"
WINDOWS = (1, 3, 7)
METRICS = ("sets", "games", "minutes")


def _instant(value: datetime | str) -> datetime:
    return datetime.fromisoformat(canonical_timestamp(value))


def recovery_bounds(*, next_start: datetime, result_observed_at: datetime, ended_at: datetime | None) -> dict:
    """Bounds to the scheduled NEXT start, not measured future physiology."""
    if any(not isinstance(value, datetime) for value in (next_start, result_observed_at)) or (
        ended_at is not None and not isinstance(ended_at, datetime)
    ):
        raise ContextContractError("recovery clocks must be aware datetimes")
    start, receipt = _instant(next_start), _instant(result_observed_at)
    end = None if ended_at is None else _instant(ended_at)
    minimum = (start - receipt).total_seconds() / 3600.0
    if minimum < 0 or end is not None and end > receipt:
        raise ContextContractError("inconsistent completed-match chronology")
    return {"minimum_hours": minimum, "exact_hours": None if end is None else (start - end).total_seconds() / 3600.0}


def _joint_match_identity(row: dict) -> str:
    """The whole source revision, independent of its per-player projection."""
    payload = dict(row["payload"])
    if payload["player_id"] > payload["opponent_id"]:
        payload["player_id"], payload["opponent_id"] = payload["opponent_id"], payload["player_id"]
        payload["set_scores"] = [
            {"a": score["b"], "b": score["a"], "completed": score["completed"]}
            for score in payload["set_scores"]
        ]
    return digest({"payload": payload, "competition": row["competition"],
                   "format": row["format"], "schedule_revision": row["schedule_revision"]})


def _usable_history(observations: tuple[dict, ...], *, cutoff: datetime, next_start: datetime) -> tuple[list[dict], set[str]]:
    """Use B1's final usable_refs, not inspected/audit references.

    Each previous event is a completed *workload fact* about a later scheduled
    decision. Its terminal does not mean that this next decision has started.
    Group by the actual prior event/schedule before B1's factor evaluation.
    Unknown source schemas remain unconsumed; no field-name-based trust.
    """
    if type(observations) is not tuple:
        raise ContextContractError("tennis observations must be a tuple of B1 selected receipts")
    eligible = []
    for row in observations:
        if type(row) is not dict:
            raise ContextContractError("tennis observations must be selected B1 objects")
        # Validation precedes reading numeric fields, including discarded rows.
        policy = freshness_policy("workload", schedule_revision=row.get("schedule_revision"), requires_complete=False)
        factor_state((row,), cutoff=cutoff, scheduled_start=next_start, policy=policy)
        if (row["kind"] != "workload" or row["evidence_class"] != "prospective"
                or row["observed_at"] > canonical_timestamp(cutoff)):
            continue
        if row["sport"] != "tennis" or row["source"] != "espn" or row["source_schema"] != SOURCE_SCHEMA:
            continue
        if row["format"] != "singles":
            raise ContextContractError("tennis workload scope must be singles")
        validate_workload_record(row)
        eligible.append(row)

    # A source response describes one whole native match, not independent
    # player careers. Select its newest receipt EVENT-WIDE before examining
    # subjects: corrected participants must revoke an old player's match claim.
    # Late imports were excluded above; no prior receipt is changed in storage.
    by_event = {}
    for row in eligible:
        by_event.setdefault(row["event_key"], []).append(row)
    usable, conflicts = [], set()
    for history in by_event.values():
        newest = max(row["observed_at"] for row in history)
        group = [row for row in history if row["observed_at"] == newest]
        players = {row["payload"][key] for row in group for key in ("player_id", "opponent_id")}
        if len(players) != 2 or len({_joint_match_identity(row) for row in group}) != 1:
            # All participants in the contradictory native event are unsafe,
            # including any older player whose removal is not established.
            conflicts.update(row["payload"][key] for row in history for key in ("player_id", "opponent_id"))
            continue
        if {row["subject_id"] for row in group} != players:
            # Partial receipt delivery cannot borrow the opponent projection
            # from an earlier time or manufacture a second numeric reference.
            continue
        row = group[0]
        state = factor_state(tuple(group), cutoff=cutoff, scheduled_start=next_start,
                             policy=freshness_policy("workload", schedule_revision=row["schedule_revision"], requires_complete=False))
        if state["state"] == "conflicting":
            conflicts.update(players)
            continue
        chosen = [item for item in group if item["digest"] in state["usable_refs"]]
        for player in sorted(players):
            candidates = [item for item in chosen if item["subject_id"] == player]
            if candidates:
                # Genuine duplicate pages remain one fact per native player.
                usable.append(min(candidates, key=lambda item: item["digest"]))
    return usable, conflicts


def tennis_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime) -> dict:
    """Return observed A/B loads and signed A-minus-B features with their refs.

    Every sum is explicitly over observed attributable matches. Missing time or
    duration is not zero; observations alone do not prove all-played coverage.
    Availability, returning health and actual travel remain missing because no
    allowed source currently establishes them. Surface/indoor are not added a
    second time as numerical features; B7 may learn declared load interactions.
    """
    if not isinstance(cutoff, datetime):
        raise ContextContractError("tennis feature cutoff must be an aware datetime")
    event, base = validate_event(event), validate_base_distribution(base)
    decision = _instant(cutoff)
    next_start = _instant(event["scheduled_start"])
    if event["sport"] != "tennis" or base["family"] not in {"tennis:winner", "tennis:serve"}:
        raise ContextContractError("tennis load requires a tennis event and base family")
    if base["event_key"] != event["event_key"] or base["cutoff"] != canonical_timestamp(decision):
        raise ContextContractError("tennis feature/base identity or decision clock mismatch")
    if decision >= next_start:
        raise ContextContractError("tennis decision must precede the next scheduled start")
    usable, conflicts = _usable_history(observations, cutoff=decision, next_start=next_start)
    values, states, refs = {}, {}, {}

    def put(name, value, used=(), state=None):
        values[name] = value
        states[name] = state or ("missing" if value is None else "available")
        refs[name] = sorted({row["digest"] for row in used}) if states[name] == "available" else []

    applicable = event["status"] == "scheduled" and event["format"] == "singles" and event.get("tour") in {"ATP", "WTA"}
    side_names, coverage_rows = [], []
    for side, player in (("a", event["home_id"]), ("b", event["away_id"])):
        rows = [row for row in usable if row["subject_id"] == player and row["payload"]["tour"] == event.get("tour")
                and row["event_key"] != event["event_key"]] if applicable else []
        blocked = "not_applicable" if not applicable else "conflicting" if player in conflicts else None
        if blocked:
            rows = []
        coverage_rows.extend(rows)
        # Unknown end times may belong to any window, so they cannot make the
        # observed subset's window coverage complete or become exact rest.
        known_times = [row for row in rows if row["payload"]["actual_end"] is not None]
        unknown_times = [row for row in rows if row["payload"]["actual_end"] is None]
        for days in WINDOWS:
            start = canonical_timestamp(decision - timedelta(days=days))
            stop = canonical_timestamp(decision)
            window = [row for row in known_times if start <= row["payload"]["actual_end"] < stop]
            for metric in METRICS:
                measured = [row for row in window if row["payload"][metric] is not None]
                name = f"observed_{metric}_{days}d"
                side_names.append(name)
                # A sum exists only when at least one attributable actual value
                # exists. Empty incomplete history is not evidence for zero.
                total = sum(row["payload"][metric] for row in measured) if measured else None
                put(f"{name}_{side}", total, measured, blocked)
                complete = int(bool(window) and len(measured) == len(window) and not unknown_times) if rows else None
                put(f"observed_{metric}_complete_{days}d_{side}", complete, rows, blocked)
            put(f"observed_matches_{days}d_{side}", len(window) if window else None, window, blocked)
            put(f"incomplete_matches_{days}d_{side}", sum(row["payload"]["incomplete_match"] for row in window) if window else None, window, blocked)
            put(f"history_complete_{days}d_{side}", 0 if rows else None, rows, blocked)

        if rows:
            latest_receipt = max(_instant(row["payload"]["result_observed_at"]) for row in rows)
            latest_end = max((_instant(row["payload"]["actual_end"]) for row in known_times), default=None)
            exact_end = latest_end if not unknown_times else None
            bounds = recovery_bounds(next_start=next_start, result_observed_at=latest_receipt, ended_at=exact_end)
        else:
            bounds = {"minimum_hours": None, "exact_hours": None}
        for kind in ("minimum", "exact"):
            name = f"observed_recovery_{kind}_hours"
            side_names.append(name)
            put(f"{name}_{side}", bounds[f"{kind}_hours"], rows, blocked)
        put(f"recovery_is_exact_{side}", int(bounds["exact_hours"] is not None) if rows else None, rows, blocked)
        for name in ("availability", "return_from_absence", "travel_hours"):
            side_names.append(name)
            put(f"{name}_{side}", None, state=blocked)

    for name in sorted(set(side_names)):
        a, b = f"{name}_a", f"{name}_b"
        if states[a] == states[b] == "available":
            values[f"{name}_delta"] = values[a] - values[b]
            states[f"{name}_delta"] = "available"
            refs[f"{name}_delta"] = sorted(set(refs[a]) | set(refs[b]))
        else:
            value_state = "not_applicable" if "not_applicable" in (states[a], states[b]) else "conflicting" if "conflicting" in (states[a], states[b]) else "missing"
            put(f"{name}_delta", None, state=value_state)

    # Separate identities prevent a coefficient trained on exact recovery from
    # receiving a receipt bound under the same declared coverage case.
    rest = "exact-observed" if all(values[f"observed_recovery_exact_hours_{side}"] is not None for side in ("a", "b")) else (
        "receipt-bound-observed" if all(values[f"observed_recovery_minimum_hours_{side}"] is not None for side in ("a", "b")) else "missing-rest")
    known_end_count = sum(row["payload"]["actual_end"] is not None for row in coverage_rows)
    timing = "no-history" if not coverage_rows else "missing-end-times" if not known_end_count else (
        "known-end-times" if known_end_count == len(coverage_rows) else "partial-end-times")
    return validate_feature_vector({
        "version": FEATURE_VERSION, "event_key": event["event_key"], "cutoff": canonical_timestamp(decision),
        "values": values, "states": states, "refs": refs,
        "coverage": {"version": "tennis-performed-load-coverage-v1", "case": f"observed-only.{rest}.{timing}"},
        "reference_hash": digest({"history_refs": base["history_refs"], "reference_weights": base["reference_weights"]}),
    })
