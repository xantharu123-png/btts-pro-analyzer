"""Explicit status-aware B6 successor, without changing legacy v2 replay.

Whole native competition revisions are resolved BEFORE the unchanged performed
load arithmetic. A new terminal must carry its own entire bilateral receipt
pair. Missing and conflicting revisions never regain an old load/rest value.
"""
from copy import deepcopy
from datetime import datetime

from context_models.contracts import (
    ContextContractError, canonical_timestamp, digest, validate_base_distribution,
    validate_event, validate_feature_vector,
)
from context_models.tennis import _joint_match_identity, tennis_features
from context_sources.tennis import SOURCE_SCHEMA
from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt


FEATURE_VERSION = "tennis-performed-load-v3"
COVERAGE_VERSION = "tennis-performed-load-coverage-v2"
STATUS_CASES = {"status-paired", "legacy-only", "mixed-status-legacy", "unavailable-status", "no-history"}


def tennis_reference_hash_v3(base: dict, event: dict) -> str:
    return digest({"version": "tennis-context-reference-v3", "base_hash": digest(validate_base_distribution(base)),
                   "event_hash": digest(validate_event(event))})


def _players(row):
    payload = row["payload"]
    if row["source_schema"] == STATUS_SCHEMA:
        return {player for player in payload["participant_ids"] if player is not None}
    return {payload["player_id"], payload["opponent_id"]}


def _history(observations, *, cutoff, tour, target, participants):
    if type(observations) is not tuple:
        raise ContextContractError("status-aware tennis requires the complete owning B1 tuple")
    by_event = {}
    for row in observations:
        validate_selected_tennis_receipt(row)
        if row["observed_at"] <= cutoff and row["payload"]["tour"] == tour and row["event_key"] != target:
            by_event.setdefault(row["event_key"], {})[row["digest"]] = row
    selected, associations, conflicting, unavailable = [], {}, set(), set()
    modes = set()
    for keyed in by_event.values():
        history = list(keyed.values())
        all_players = set().union(*(_players(row) for row in history))
        if not all_players & participants:
            continue
        statuses = [row for row in history if row["source_schema"] == STATUS_SCHEMA]
        if not statuses:
            # These are genuinely old unpaired facts, not a newly confirmed
            # status. The v2 selector still handles their participant conflicts.
            selected.extend(history)
            modes.add("legacy-only")
            continue
        newest = max(row["observed_at"] for row in history)
        group = [row for row in history if row["observed_at"] == newest]
        heads = [row for row in group if row["source_schema"] == STATUS_SCHEMA]
        if len(heads) > 1:
            conflicting.update(all_players)
            modes.add("unavailable-status")
            continue
        if not heads or not heads[0]["payload"]["workload_receipts"]:
            unavailable.update(all_players)
            modes.add("unavailable-status")
            continue
        status = heads[0]
        payload = status["payload"]
        pair = [row for row in group if row["source_schema"] == SOURCE_SCHEMA]
        actual, required = {row["digest"] for row in pair}, set(payload["workload_receipts"])
        if actual - required:
            conflicting.update(all_players)
            modes.add("unavailable-status")
            continue
        if actual != required:
            unavailable.update(all_players)
            modes.add("unavailable-status")
            continue
        players = set(payload["participant_ids"])
        terminal = "walkover" if payload["native_status"]["walkover"] else "retired" if payload["native_status"]["retired"] else "completed"
        coherent = (len(pair) == 2 and {row["subject_id"] for row in pair} == players
            and len({_joint_match_identity(row) for row in pair}) == 1
            and all(row["competition"] == status["competition"] and row["schedule_revision"] == status["schedule_revision"]
                and row["payload"]["status"] == terminal
                and row["payload"]["scheduled_start"] == payload["scheduled_start"]
                and row["payload"]["result_observed_at"] == status["observed_at"]
                and all(row["payload"][field] is None for field in ("actual_start", "actual_end", "minutes"))
                for row in pair))
        if not coherent:
            conflicting.update(all_players)
            modes.add("unavailable-status")
            continue
        if not players & participants:
            # A complete later revision removed an old target participant.
            # Its old workload is gone; another player's match is not coverage.
            continue
        refs = sorted(required | {status["digest"]})
        for row in pair:
            associations[row["digest"]] = refs
        selected.extend(pair)
        modes.add("status-paired")
    mode = "no-history" if not modes else "unavailable-status" if "unavailable-status" in modes else (
        "mixed-status-legacy" if len(modes) > 1 else next(iter(modes)))
    return tuple(selected), associations, conflicting, unavailable, mode


def _target_status(observations, event, cutoff):
    history = {row["digest"]: row for row in observations
        if row["event_key"] == event["event_key"] and row["observed_at"] <= cutoff}
    if not any(row["source_schema"] == STATUS_SCHEMA for row in history.values()):
        return None, []
    newest = max(row["observed_at"] for row in history.values())
    latest = [row for row in history.values() if row["observed_at"] == newest]
    statuses = [row for row in latest if row["source_schema"] == STATUS_SCHEMA]
    if len(statuses) > 1:
        return "conflicting", []
    if not statuses:
        return "missing", []
    row, payload = statuses[0], statuses[0]["payload"]
    if payload["status"] in {"started", "completed", "cancelled"}:
        return "not_applicable", []
    if (payload["status"] != "scheduled" or payload["issues"]
            or row["competition"] != event["competition"]
            or payload["scheduled_start"] != event["scheduled_start"]
            or set(payload["participant_ids"]) != {event["home_id"], event["away_id"]}):
        return "missing", []
    return None, [row["digest"]]


def tennis_features_v3(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime) -> dict:
    """New, explicit identity; never relabel a caller's saved v2 FeatureVector.

    Unsupported latest native history leaves that participant's context
    unknown (not zero), even if some other history remains known. This first
    status variant does not guess whether a defective correction is physically
    irrelevant to current load/rest. Stored facts and the original base remain.
    """
    event, base = validate_event(event), validate_base_distribution(base)
    if not isinstance(cutoff, datetime):
        raise ContextContractError("tennis v3 requires an aware cutoff datetime")
    decision = canonical_timestamp(cutoff)
    selected, associations, conflicts, unknown, mode = _history(observations, cutoff=decision,
        tour=event.get("tour"), target=event["event_key"], participants={event["home_id"], event["away_id"]})
    target_state, target_refs = _target_status(observations, event, decision)
    result = deepcopy(tennis_features(event, selected, base, cutoff=cutoff))
    for name, refs in result["refs"].items():
        result["refs"][name] = sorted({ref for original in refs for ref in associations.get(original, [original])}
            | (set(target_refs) if result["states"][name] == "available" else set()))
    for side, player in (("a", event["home_id"]), ("b", event["away_id"])):
        if player in conflicts | unknown:
            for name in result["values"]:
                if name.endswith("_" + side) and result["states"][name] != "not_applicable":
                    result["values"][name] = None
                    result["states"][name] = "conflicting" if player in conflicts else "missing"
                    result["refs"][name] = []
    for name in result["values"]:
        if name.endswith("_delta"):
            root = name[:-6]
            a, b = root + "_a", root + "_b"
            states = (result["states"][a], result["states"][b])
            if states == ("available", "available"):
                result["values"][name] = result["values"][a] - result["values"][b]
                result["refs"][name] = sorted(set(result["refs"][a]) | set(result["refs"][b]))
            else:
                result["values"][name], result["refs"][name] = None, []
                result["states"][name] = "not_applicable" if "not_applicable" in states else "conflicting" if "conflicting" in states else "missing"
    case = result["coverage"]["case"]
    if target_state is not None:
        for name in result["values"]:
            result["values"][name], result["refs"][name] = None, []
            result["states"][name] = target_state
        mode = "unavailable-status"
    if target_state is not None or event["home_id"] in conflicts | unknown or event["away_id"] in conflicts | unknown:
        _, _, timing = case.split(".")
        case = "observed-only.missing-rest." + timing
    result.update(version=FEATURE_VERSION, coverage={"version": COVERAGE_VERSION, "case": mode + "." + case},
                  reference_hash=tennis_reference_hash_v3(base, event))
    return validate_feature_vector(result)
