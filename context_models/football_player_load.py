"""Reported player exposure across clubs and national teams, not a fatigue label.

Windows use scheduled fixture dates because this source lacks actual starts.
They are explicitly observed-only: no omitted match becomes a zero-minute game.
Recovery uses terminal receipts as a lower bound, never kickoff plus 90 minutes.
Club role estimation remains club-only; international minutes enter load only.
"""
from datetime import datetime, timedelta
import re

from context_models.contracts import ContextContractError, canonical_timestamp, validate_event
from context_models.football import (
    _appearance_payload, _collection_conflicts, _is_empty_collection, _selected,
    expected_roster,
)

VERSION = "football-player-observed-load-v1"
FIELDS = ("reported_minutes_schedule_7d", "reported_minutes_schedule_14d",
          "recovery_min_hours", "recovery_exact_hours", "expected_minutes")
LOAD_COLUMN = re.compile(r"load\.(home|away)\.(" + "|".join(FIELDS) + r")")


def _player_values(player, past, original, *, cutoff, next_start):
    samples = [row for row in past if row["subject_id"] == player]
    if player in _collection_conflicts(tuple(samples)):
        return None, "conflicting"
    fixtures = {}
    for row in samples:
        fixtures.setdefault(row["event_key"], []).append(row)
    if any(len({(r["payload"]["team_id"], r["payload"]["minutes"],
                 r["payload"]["scheduled_start"], r["payload"]["event_end"]) for r in group}) > 1
           for group in fixtures.values()):
        return None, "conflicting"
    rows = [group[0] for group in fixtures.values()]
    result = {}
    for days in (7, 14):
        lower = canonical_timestamp(cutoff - timedelta(days=days))
        within = [row for row in rows if lower <= canonical_timestamp(row["payload"]["scheduled_start"])
                  < canonical_timestamp(cutoff)]
        key = f"reported_minutes_schedule_{days}d"
        result[key] = (None, ()) if not within or any(r["payload"]["minutes"] is None for r in within) else (
            sum(r["payload"]["minutes"] for r in within), tuple(r["digest"] for r in within))
    # Unknown participation can hide a later played fixture. Do not call the
    # previous known match the player's last match or manufacture a rest value.
    recent = [r for r in rows if canonical_timestamp(cutoff - timedelta(days=14))
              <= canonical_timestamp(r["payload"]["scheduled_start"]) < canonical_timestamp(cutoff)]
    played = [r for r in recent if r["payload"]["minutes"] is not None and r["payload"]["minutes"] > 0]
    if not played or any(r["payload"]["minutes"] is None for r in recent):
        result["recovery_min_hours"] = result["recovery_exact_hours"] = (None, ())
        return result, "available"
    bounds, ends, refs = [], [], set()
    for row in played:
        payload = row["payload"]
        # A later unchanged FT recheck does not restart recovery. But scheduled
        # order alone cannot establish which of these fixtures ended last.
        proofs = [r for r in original if r["event_key"] == row["event_key"] and r["subject_id"] == player
                  and r["payload"]["team_id"] == payload["team_id"]
                  and r["payload"]["scheduled_start"] == payload["scheduled_start"]
                  and r["payload"]["minutes"] is not None and r["payload"]["minutes"] > 0]
        proof = min(proofs, key=lambda r: r["payload"]["result_observed_at"])
        refs.update((row["digest"], proof["digest"]))
        bound = datetime.fromisoformat(proof["payload"]["result_observed_at"])
        ended = datetime.fromisoformat(payload["event_end"]) if payload["event_end"] else None
        bounds.append(ended or bound)
        ends.append(ended)
    latest_bound = max(bounds)
    result["recovery_min_hours"] = ((next_start - latest_bound).total_seconds() / 3600., tuple(refs))
    known = [end for end in ends if end is not None]
    latest_end = max(known) if known else None
    exact = latest_end is not None and all(end is not None or bound <= latest_end for end, bound in zip(ends, bounds))
    result["recovery_exact_hours"] = ((next_start - latest_end).total_seconds() / 3600., tuple(refs)) if exact else (None, ())
    return result, "available"


def player_load_features(event, observations, *, cutoff):
    """Expected-role-weighted reported load for each explicitly supported cohort.

    Values are predictors to be learned/validated, not assigned percentages.
    This does not claim a complete match schedule or a complete healthy squad.
    """
    event = validate_event(event)
    if event["sport"] != "football" or type(observations) is not tuple:
        raise ContextContractError("player load requires native football B1 tuples")
    decision = canonical_timestamp(cutoff)
    applicable = event["status"] == "scheduled" and decision < event["scheduled_start"]
    relevant = tuple(r for r in observations if r["kind"] in {"appearance", "availability", "confirmed_lineup"})
    selected = _selected(relevant, cutoff=cutoff)
    past = tuple(r for r in selected if r["kind"] == "appearance" and not _is_empty_collection(r))
    for row in past:
        _appearance_payload(row, cutoff=cutoff)
    original = tuple(r for r in relevant if r["kind"] == "appearance" and not _is_empty_collection(r)
                     and r["evidence_class"] == "prospective" and r["observed_at"] <= decision)
    for row in original:
        _appearance_payload(row, cutoff=cutoff)
    values, states, refs = {}, {}, {}
    for side in ("home", "away"):
        team = event[side + "_id"]
        club = tuple(r for r in past if r["payload"]["team_id"] == team)
        facts = tuple(r for r in selected if r["kind"] in {"availability", "confirmed_lineup"}
            and r["event_key"] == event["event_key"] and r["schedule_revision"] == event["schedule_revision"]
            and r["payload"]["team_id"] == team)
        if any((r["competition"], r["format"], canonical_timestamp(r["payload"]["scheduled_start"]))
               != (event["competition"], event["format"], event["scheduled_start"]) for r in facts):
            raise ContextContractError("player load current role belongs to another native event")
        cohort = frozenset(r["subject_id"] for r in facts if r["subject_id"].startswith("api-football:player:"))
        roster = expected_roster(club, facts, cutoff=cutoff, reference_players=cohort)
        expected = roster["central_minutes"]
        weights = {p: minutes for p, minutes in (expected or {}).items() if minutes > 0}
        total = sum(weights.values())
        player_values = {p: _player_values(p, past, original, cutoff=cutoff,
                         next_start=datetime.fromisoformat(event["scheduled_start"])) for p in weights}
        conflicting = roster["coverage"]["case"] == "conflicting" or any(state == "conflicting" for _, state in player_values.values())
        for field in FIELDS:
            key = "load." + side + "." + field
            number, used = None, set()
            if total and not conflicting:
                if field == "expected_minutes":
                    number = total
                elif all(block is not None and block[field][0] is not None for block, _ in player_values.values()):
                    number = sum(weights[p] * block[field][0] for p, (block, _) in player_values.items()) / total
                    used.update(ref for block, _ in player_values.values() for ref in block[field][1])
                if number is not None:
                    used.update(roster["refs"])
            values[key] = number if applicable else None
            states[key] = ("conflicting" if conflicting else "available" if number is not None else "missing") if applicable else "not_applicable"
            refs[key] = sorted(used) if applicable and number is not None else []
    return {"version": VERSION, "values": values, "states": states, "refs": refs}
