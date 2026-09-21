"""Bind already received winners to existing original native Tennis events.

This is collection, not D1 replay, outcome selection for training, settlement,
or effect approval. Original artifacts and their indexed native target/state
references are checked; no whole-tour history, provider request or fit occurs.
"""
from copy import deepcopy
from datetime import datetime
import os

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from context_models.dataset import _artifact, _reader
from context_models.experiments import _artifact_created_at
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, original_base, validate_original_publication
from context_observations import _SELECT, _decode_receipt
from context_sources.outcomes import normalize_tennis_revised_outcome
from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt
from model_artifacts import _load_artifact
from tennis.forecast_retirements import original_is_retired


def source_for_normal_winner(status, competition):
    """Closed same-reception sports projection; discard prices/display names.

    False as the first value means this terminal is not an eligible winner
    source. A true first value with no source preserves an ambiguous flag set
    as unavailable, including when another same-clock answer has valid flags.
    The unchanged status normalizer already classified all terminal notes.
    """
    payload = status["payload"]
    native = payload["native_status"]
    if (status["format"] != "singles" or payload["status"] != "completed" or payload["issues"]
            or native["retired"] or native["walkover"] or native["unsupported"]):
        return False, None
    players = competition["competitors"]
    flags = [player.get("winner") for player in players]
    if any(type(flag) is not bool for flag in flags) or sum(flags) != 1:
        return True, None
    projected = []
    for player in players:
        item = {"id": player["id"], "winner": player["winner"]}
        if "linescores" in player:
            item["linescores"] = (None if player["linescores"] is None else
                [{key: deepcopy(line[key]) for key in ("value", "winner") if key in line}
                    for line in player["linescores"]])
        projected.append(item)
    return True, {"source_schema": "espn-scoreboard-v1", "tour": payload["tour"],
        "tournament_id": payload["tournament_id"], "competition": {
            "id": competition["id"], "date": competition["date"],
            "status": {"type": {key: competition["status"]["type"][key]
                for key in ("state", "name", "completed")}}, "competitors": projected}}


def _native_binding(connection, origin):
    """Resolve only this original's native target as of its actual cutoff."""
    event = origin["event"]
    latest = connection.execute(_SELECT + " WHERE r.event_key=? AND r.observed_at<=?"
        " ORDER BY r.observed_at DESC,r.digest LIMIT 2", (event["event_key"], origin["cutoff"])).fetchall()
    selected = [_decode_receipt(row) for row in latest]
    if (not selected or selected[0]["digest"] != origin["native_receipt"]
            or len(selected) == 2 and selected[0]["observed_at"] == selected[1]["observed_at"]):
        raise ContextIntegrityError("original Tennis native target is missing or had a conflicting revision")
    row = {**selected[0], "evidence_class": "prospective", "effective_at": selected[0]["observed_at"],
        "publication_resolution": None}
    validate_selected_tennis_receipt(row)
    value = row["payload"]
    if (row["source_schema"] != STATUS_SCHEMA or row["kind"] != "event_status"
            or row["observed_at"] != origin["native_observed_at"]
            or row["competition"] != event["competition"] or row["format"] != event["format"]
            or row["schedule_revision"] != event["schedule_revision"]
            or value["competition_revision"] != origin["competition_revision"]
            or value["participant_ids"] != [event["home_id"], event["away_id"]]
            or value["tour"] != event["tour"] or value["scheduled_start"] != event["scheduled_start"]
            or value["status"] != "scheduled" or value["issues"]):
        raise ContextIntegrityError("original Tennis identity differs from its actual native receipt")


def _originals(path, wanted, *, retired_events=None):
    """Read the small typed original catalog, not the historical receipt pool.

    Artifact bodies are verified BEFORE their event field is used for pruning;
    a broken original must not vanish as an apparently absent watch. Only
    relevant originals resolve their state and at most two indexed target rows.
    No untrusted payload filter stands in for its owning A1 hash decoder.
    """
    result = {}
    if not wanted or not os.path.lexists(path):
        return result
    from tennis.tour_state import _decode_wrapper
    with _reader(path) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='artifacts'").fetchone():
            raise ContextIntegrityError("stored context database lacks its owning artifact table")
        states = {}
        for (ref,) in connection.execute("SELECT digest FROM artifacts WHERE kind=? ORDER BY digest",
                (ORIGINAL_ARTIFACT_KIND,)):
            envelope = _load_artifact(connection, ref)
            created = _artifact_created_at(connection, ref)
            try:
                publication = validate_original_publication(envelope["payload"], created_at=created)
                origin = publication["origin"]
                original_base(origin)
                key = origin["event"]["event_key"]
                if key not in wanted:
                    continue
                state_ref = origin["state_hash"]
                if state_ref not in states:
                    state = _artifact(connection, state_ref, "tennis-tour-state", latest=origin["cutoff"])
                    states[state_ref] = (_decode_wrapper(state["payload"], origin["event"]["tour"]),
                        _artifact_created_at(connection, state_ref))
                state, state_created = states[state_ref]
                if (state.tour_scope != origin["event"]["tour"] or state_created > origin["cutoff"]
                        or state.built_at > datetime.fromisoformat(origin["cutoff"]).timestamp()):
                    raise ContextIntegrityError("original Tennis state was unavailable at its decision")
                _native_binding(connection, origin)
            except ContextContractError as exc:
                raise ContextIntegrityError("invalid stored Tennis original binding") from exc
            # Retire only the explicitly approved immutable publication, after
            # all its integrity checks. New originals of this event stay active.
            if original_is_retired(ref, key):
                if retired_events is not None:
                    retired_events.add(key)
                continue
            result.setdefault(key, []).append((created, origin["event"]))
    return result


def collect_outcomes(path, pending, sources, *, retired_events=None):
    """Return additions by batch position, preserving all actual receive clocks.

    Repeated persistence is B1-idempotent. Multiple forecasts of the exact same
    native event do not multiply outcomes. Replaced participants never inherit
    the replacement's result. Scope selection uses native IDs, never a winner.
    """
    wanted = {pending[index][1][0]["event_key"] for index in sources}
    originals = _originals(path, wanted, retired_events=retired_events)
    groups = {}
    for index, (clock, rows) in enumerate(pending):
        if rows[0]["event_key"] in wanted:
            groups.setdefault((rows[0]["event_key"], canonical_timestamp(clock)), []).append(index)
    additions, issues = {}, set()
    for (key, received), indices in groups.items():
        events = {}
        for created, event in originals.get(key, ()):
            if created <= received and created < event["scheduled_start"]:
                ref = digest(event)
                # Many pre-match recalculations do not multiply an outcome.
                # Retain the earliest actual publication for each exact scope.
                if ref not in events or created < events[ref][0]:
                    events[ref] = (created, event)
        if not events:
            continue
        # A provider may reuse its match ID after replacing an opponent. Bind
        # only originals for the actual received native pair/tournament. Keep
        # all old originals untouched and unscored; do not choose by outcome.
        from context_sources.tennis import _espn
        scopes, missing = set(), False
        for index in indices:
            try:
                native = _espn(sources[index])
                prefix = f"espn:tennis:{native['tour']}:player:"
                scopes.add((native["tour"], f"espn:{native['tour']}:tournament:{native['tournament_id']}",
                    f"espn:tennis:{native['tour']}:match:{native['event_id']}",
                    frozenset((prefix+native["player_a_id"], prefix+native["player_b_id"]))))
            except (ContextContractError, TypeError, ValueError, KeyError):
                missing = True
        if len(scopes) > 1 or missing and len(indices) > 1:
            issues.add("native-outcome-conflicting")
            continue
        if missing or not scopes:
            issues.add("native-outcome-unavailable")
            continue
        scope = next(iter(scopes))
        events = {ref: (created, event) for ref, (created, event) in events.items()
            if (event["tour"], event["competition"], event["event_key"],
                frozenset((event["home_id"], event["away_id"]))) == scope}
        if not events:
            issues.add("native-outcome-unavailable")
            continue
        bound = []
        for created, event in events.values():
            answers, unavailable = {}, False
            for index in indices:
                source = sources.get(index)
                if source is None:
                    unavailable = True
                    continue
                try:
                    answer = normalize_tennis_revised_outcome(event, source,
                        observed_at=pending[index][0], original_published_at=created)
                except (ContextContractError, TypeError, ValueError, KeyError, OverflowError):
                    answer = None
                if answer is None:
                    unavailable = True
                else:
                    answers[digest(answer)] = answer
            if len(answers) > 1 or unavailable and len(indices) > 1:
                issues.add("native-outcome-conflicting")
            elif unavailable:
                issues.add("native-outcome-unavailable")
            elif answers:
                bound.append(next(iter(answers.values())))
        if bound:
            additions[indices[0]] = tuple(sorted(bound, key=digest))
    return additions, issues
