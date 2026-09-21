"""Played-load windows proven by native in-progress/terminal receipt intervals.

Never equate a receipt or scheduled start with the real match end. A measured
load belongs to a window only when the WHOLE possible end interval lies inside
it. Old v2/v3 features/replays remain unchanged. Missing duration stays missing.
"""
from copy import deepcopy
from datetime import datetime, timedelta

from context_models.contracts import (ContextContractError, canonical_timestamp, digest,
    validate_event, validate_base_distribution, validate_feature_vector)
from context_models.tennis import METRICS, WINDOWS, _joint_match_identity, _usable_history
from context_models.tennis_v3 import (tennis_features_v3, _history, _target_status,
    _resolved_history, _features_from_history)
from context_sources.tennis import SOURCE_SCHEMA
from context_sources.tennis_status import STATUS_SCHEMA

FEATURE_VERSION = "tennis-performed-load-v4"
COVERAGE_VERSION = "tennis-performed-load-coverage-v3"
TRAINING_VARIANT = "tennis-live-winner-bounded-load-antisymmetric-v1"


def tennis_reference_hash_v4(base, event):
    from context_models.contracts import validate_base_distribution, validate_event
    return digest({"version": "tennis-context-reference-v4",
        "base_hash": digest(validate_base_distribution(base)), "event_hash": digest(validate_event(event))})


def _signature(row):
    p = row["payload"]
    return (row["competition"], row["schedule_revision"], p["scheduled_start"],
            frozenset(p["participant_ids"]))


def _work_signature(row):
    payload = deepcopy(row["payload"])
    payload.pop("result_observed_at")
    return digest(payload)


def _end_intervals(observations, selected, *, decision):
    """A last running receipt < real end <= first matching final receipt.

    Repeated terminal polling does not move that upper bound. A retraction,
    identity change, schedule change, unknown state or partial pair is a barrier:
    old bounds cannot be borrowed across it. No source observation is changed.
    """
    groups = {}
    keys = {r["event_key"] for r in selected}
    for row in observations:
        if row["event_key"] in keys and row["observed_at"] <= decision:
            groups.setdefault(row["event_key"], {}).setdefault(row["observed_at"], {})[row["digest"]] = row
    intervals = {}
    for selected_row in selected:
        p = selected_row["payload"]
        if p["actual_end"] is not None:
            intervals[selected_row["digest"]] = (p["actual_end"], p["actual_end"], [selected_row["digest"]])
            continue
        lower = upper = None
        refs = []
        expected_players = {p["player_id"], p["opponent_id"]}
        expected = (selected_row["competition"], selected_row["schedule_revision"],
                    p["scheduled_start"], frozenset(expected_players))
        for clock, received_by_ref in sorted(groups.get(selected_row["event_key"], {}).items()):
            received = list(received_by_ref.values())
            statuses = [r for r in received if r["source_schema"] == STATUS_SCHEMA]
            if len(statuses) != 1 or statuses[0]["payload"]["issues"] or _signature(statuses[0]) != expected:
                lower = upper = None
                refs = []
                continue
            status = statuses[0]
            if status["payload"]["status"] == "started":
                lower, upper, refs = clock, None, [status["digest"]]
                continue
            if status["payload"]["status"] != "completed":
                lower = upper = None
                refs = []
                continue
            pair = [r for r in received if r["source_schema"] == SOURCE_SCHEMA]
            required = set(status["payload"]["workload_receipts"])
            own = [r for r in pair if r["subject_id"] == selected_row["subject_id"]]
            compatible = (len(pair) == 2 and len(own) == 1
                and {r["digest"] for r in pair} == required
                and {r["subject_id"] for r in pair} == expected_players
                and len({_joint_match_identity(r) for r in pair}) == 1
                and _work_signature(own[0]) == _work_signature(selected_row)
                and all(r["schedule_revision"] == selected_row["schedule_revision"]
                        and r["competition"] == selected_row["competition"]
                        and r["payload"]["result_observed_at"] == clock for r in pair))
            if not compatible:
                # A corrected score may describe the same physical game, but
                # this contract declines to transfer its earlier timing proof.
                lower = upper = None
                refs = []
            elif upper is None:
                upper = clock
                refs += [status["digest"], *sorted(required)]
        if upper is not None:
            intervals[selected_row["digest"]] = (lower, upper, sorted(set(refs)))
    return intervals


def tennis_features_v4(event, observations, base, *, cutoff):
    event, base = validate_event(event), validate_base_distribution(base)
    if not isinstance(cutoff, datetime):
        raise ContextContractError("tennis v4 requires an aware cutoff datetime")
    decision = canonical_timestamp(cutoff)
    scope = dict(cutoff=decision, tour=event.get("tour"), target=event["event_key"],
        participants={event["home_id"], event["away_id"]})
    resolved = _history(observations, **scope)
    # A separately scheduled FUTURE match with no ever-observed play is not
    # missing past workload. Retain every retraction/reopening of actual play.
    # The owning selector validated the complete input before this projection.
    future = {}
    for row in observations:
        if row["observed_at"] <= decision and row["event_key"] != event["event_key"]:
            future.setdefault(row["event_key"], []).append(row)
    excluded = set()
    for key, history in future.items():
        latest = max(row["observed_at"] for row in history)
        heads = [row for row in history if row["observed_at"] == latest and row["source_schema"] == STATUS_SCHEMA]
        if (len(heads) == 1 and not heads[0]["payload"]["issues"]
                and heads[0]["payload"]["status"] == "scheduled"
                and heads[0]["payload"]["scheduled_start"] > decision
                and not any(row["source_schema"] == SOURCE_SCHEMA or
                    row["source_schema"] == STATUS_SCHEMA and row["payload"]["status"] in {"started", "completed"}
                    for row in history)):
            excluded.add(key)
    if excluded:
        observations = tuple(row for row in observations if row["event_key"] not in excluded)
        resolved = _resolved_history(observations, **scope)
    result = deepcopy(_features_from_history(event, observations, base, cutoff=cutoff, resolved=resolved))
    selected, associations, conflicts, unknown, _ = resolved
    # Legacy receipts have no owning status pair. Apply the same newest-whole-
    # event selector as v2/v3 before summing; repeated or corrected receipts
    # are not additional matches.
    selected, legacy_conflicts = _usable_history(selected, cutoff=cutoff,
        next_start=datetime.fromisoformat(canonical_timestamp(event["scheduled_start"])))
    conflicts |= legacy_conflicts
    target_state, target_refs = _target_status(observations, event, decision)
    intervals = _end_intervals(observations, selected, decision=decision)

    def put(name, value, refs=(), blocked=None):
        state = blocked or ("available" if value is not None else "missing")
        result["values"][name] = value if state == "available" else None
        result["states"][name] = state
        result["refs"][name] = sorted(set(refs) | set(target_refs)) if state == "available" else []

    roots = []
    for side, player in (("a", event["home_id"]), ("b", event["away_id"])):
        blocked = target_state or ("conflicting" if player in conflicts else "missing" if player in unknown else None)
        if result["states"].get("observed_recovery_minimum_hours_"+side) == "not_applicable":
            blocked = "not_applicable"
        if event["status"] != "scheduled" or decision >= canonical_timestamp(event["scheduled_start"]):
            blocked = "not_applicable"
        rows = [r for r in selected if r["subject_id"] == player]
        # First consistent terminal receipt is an end UPPER bound even without
        # a running lower bound. Re-polling a final result cannot erase rest.
        rest_root = 'bounded_recovery_minimum_hours'
        if rest_root not in roots:
            roots.append(rest_root)
        ends, rest_refs = [], []
        for row in rows:
            _, upper, refs = intervals.get(row['digest'], (None, row['payload']['result_observed_at'], []))
            ends.append(upper)
            rest_refs.extend([*refs, *associations.get(row['digest'], [row['digest']])])
        recovery = ((datetime.fromisoformat(canonical_timestamp(event['scheduled_start']))
            - datetime.fromisoformat(max(ends))).total_seconds()/3600) if ends else None
        put(rest_root+'_'+side, recovery, rest_refs, blocked)
        for days in WINDOWS:
            start = canonical_timestamp(cutoff-timedelta(days=days))
            inside, uncertain, timing_refs = [], False, []
            for row in rows:
                lower, upper, refs = intervals.get(row["digest"], (None, row["payload"]["result_observed_at"], []))
                timing_refs.extend([*refs, *associations.get(row["digest"], [row["digest"]])])
                if upper < start:
                    continue
                if lower is not None and start <= lower and upper < decision:
                    inside.append(row)
                else:
                    uncertain = True
            for metric in METRICS:
                root = f"bounded_{metric}_{days}d"
                if root not in roots:
                    roots.append(root)
                measured = [r for r in inside if r["payload"][metric] is not None]
                value = sum(r["payload"][metric] for r in measured) if measured else None
                put(root+"_"+side, value, timing_refs, blocked)
                complete = int(bool(inside) and len(measured) == len(inside) and not uncertain) if rows else None
                put(f"bounded_{metric}_complete_{days}d_{side}", complete, timing_refs, blocked)
    for root in roots:
        a, b, delta = root+"_a", root+"_b", root+"_delta"
        states = result["states"][a], result["states"][b]
        if states == ("available", "available"):
            put(delta, result["values"][a]-result["values"][b], result["refs"][a]+result["refs"][b])
        else:
            put(delta, None, blocked="not_applicable" if "not_applicable" in states else "conflicting" if "conflicting" in states else "missing")
    result.update(version=FEATURE_VERSION, reference_hash=tennis_reference_hash_v4(base, event),
        coverage={"version": COVERAGE_VERSION, "case": result["coverage"]["case"]})
    return validate_feature_vector(result)


def live_tennis_features(version, event, observations, base, *, cutoff):
    from context_models.contracts import ContextContractError
    if version == FEATURE_VERSION:
        return tennis_features_v4(event, observations, base, cutoff=cutoff)
    if version == "tennis-performed-load-v3":
        return tennis_features_v3(event, observations, base, cutoff=cutoff)
    raise ContextContractError("unsupported live tennis feature version")
