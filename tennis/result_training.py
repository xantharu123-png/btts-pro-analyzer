"""Read-only Elo completion from existing, original-bound ESPN winner receipts.

This is not a whole-tour history loader, an effect approval or a CSV identity
resolver. Surface is the original executed model input, not native ESPN proof.
Receipt order supplements the CSV's declared tournament-date proxy order;
neither is presented as an actual match-end timestamp.
"""
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from context_models.contracts import canonical_timestamp, ContextIntegrityError
from context_models.dataset import _reader, _artifact
from context_models.experiments import _artifact_created_at
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, validate_original_publication
from context_observations import _SELECT, _decode_receipt
from context_sources.outcomes import TENNIS_WINNER_OUTCOME, validate_outcome_record
from context_sources.tennis_outcome_capture import _native_binding
from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt
from model_artifacts import _load_artifact
from tennis.forecast_retirements import original_is_retired


def _selected(raw):
    row = _decode_receipt(raw)
    return {**row, "evidence_class": "prospective", "effective_at": row["observed_at"],
        "publication_resolution": None}


def cached_elo_results(path, *, tour, cutoff, known_keys, diagnostics):
    """Use latest whole-event revisions; no migration, writes or network calls.

    Repeated or rescheduled original forecasts do not create extra matches.
    A newer ambiguous/retracted reception removes an older qualified winner.
    Only uninterrupted equivalent receptions retain their first known clock.
    """
    diagnostics.update(added=0, candidates=0, rejected=0, csv_overlap=0)
    if not Path(path).exists():
        return []
    clock = canonical_timestamp(cutoff)
    prefix = f"espn:tennis:{tour}:match:"
    with _reader(Path(path)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"artifacts", "context_observations", "context_contents"} <= tables:
            if "artifacts" in tables and connection.execute(
                    "SELECT 1 FROM artifacts WHERE kind=? LIMIT 1", (ORIGINAL_ARTIFACT_KIND,)).fetchone():
                raise ContextIntegrityError("original Tennis mapping lacks its native receipt tables")
            return []  # old/empty stores have no eligible local result bridge
        outcomes = defaultdict(lambda: defaultdict(list))
        for raw in connection.execute(_SELECT +
                " WHERE r.source='espn' AND r.kind='match_outcome' AND r.event_key LIKE ?"
                " AND r.observed_at<=? ORDER BY r.observed_at,r.digest", (prefix + "%", clock)):
            row = _selected(raw)
            outcomes[row["event_key"]][row["observed_at"]].append(row)
        if not outcomes:
            return []
        originals = defaultdict(list)
        states, native_keys, key_natives = {}, defaultdict(set), defaultdict(set)
        from .tour_state import _decode_wrapper
        for (ref,) in connection.execute("SELECT digest FROM artifacts WHERE kind=? ORDER BY digest",
                (ORIGINAL_ARTIFACT_KIND,)):
            created = _artifact_created_at(connection, ref)
            if created > clock:
                continue
            origin = validate_original_publication(_load_artifact(connection, ref)["payload"],
                created_at=created)["origin"]
            event = origin["event"]
            if (event["tour"] != tour or created >= event["scheduled_start"]
                    or event["scheduled_start"][:10] < f"{max(2023, cutoff.year - 3)}-01-01"
                    or original_is_retired(ref, event["event_key"])):
                continue
            _native_binding(connection, origin)
            state_ref = origin["state_hash"]
            if state_ref not in states:
                state = _decode_wrapper(_artifact(connection, state_ref,
                    "tennis-tour-state", latest=origin["cutoff"])["payload"], tour,
                    decision_cutoff=datetime.fromisoformat(origin["cutoff"]).timestamp())
                states[state_ref] = (state.built_at, _artifact_created_at(connection, state_ref))
            if (states[state_ref][0] > datetime.fromisoformat(origin["cutoff"]).timestamp()
                    or states[state_ref][1] > origin["cutoff"]):
                raise ContextIntegrityError("original Tennis mapping has a future model state")
            inputs = origin["inputs"]
            mapping = {event["home_id"]: inputs["state_key_a"], event["away_id"]: inputs["state_key_b"]}
            for native, player_key in mapping.items():
                native_keys[native].add(player_key)
                key_natives[player_key].add(native)
            originals[event["event_key"]].append((event, mapping, inputs["surface"], created))
        result = []
        for key, by_clock in outcomes.items():
            diagnostics["candidates"] += 1
            origins = originals[key]
            bindings = {(tuple(sorted(mapping.items())), surface, event["competition"])
                for event, mapping, surface, _ in origins}
            if len(bindings) != 1:
                diagnostics["rejected"] += 1
                continue
            _, mapping, surface, _ = origins[0]
            if (not set(mapping.values()) <= known_keys or surface is None
                    or any(len(native_keys[native]) != 1 or len(key_natives[player_key]) != 1
                        for native, player_key in mapping.items())):
                diagnostics["rejected"] += 1
                continue
            statuses = defaultdict(list)
            for raw in connection.execute(_SELECT +
                    " WHERE r.event_key=? AND r.source='espn' AND r.kind='event_status'"
                    " AND r.observed_at<=? ORDER BY r.observed_at,r.digest", (key, clock)):
                row = _selected(raw)
                statuses[row["observed_at"]].append(row)
            admitted = None
            for received, rows in statuses.items():
                if len(rows) != 1:
                    admitted = None
                    continue
                status = rows[0]
                if status["source_schema"] != STATUS_SCHEMA:
                    admitted = None
                    continue
                validate_selected_tennis_receipt(status)
                payload = status["payload"]
                if (payload["status"] != "completed" or payload["issues"]
                        or status["format"] != "singles" or payload["tour"] != tour
                        or status["competition"] != origins[0][0]["competition"]
                        or set(payload["participant_ids"]) != set(mapping)
                        or any(payload["native_status"][flag] for flag in ("retired", "walkover", "unsupported"))):
                    admitted = None
                    continue
                if not f"{max(2023, cutoff.year - 3)}-01-01" <= payload["scheduled_start"][:10] <= cutoff.date().isoformat():
                    admitted = None
                    continue
                facts = set()
                for outcome in by_clock.get(received, []):
                    # A final without usable winner flags has no SAME-reception
                    # outcome. Never borrow an earlier winner from that event.
                    if outcome["payload"].get("outcome_contract") != TENNIS_WINNER_OUTCOME:
                        continue
                    for event, _, _, published in origins:
                        target = outcome["payload"]
                        if (outcome["schedule_revision"] != event["schedule_revision"]
                                or target.get("home_id") != event["home_id"]
                                or target.get("away_id") != event["away_id"]
                                or target.get("scheduled_start") != event["scheduled_start"]):
                            continue
                        validate_outcome_record(outcome, event=event)
                        scheduled = target.get("reported_scheduled_start", target["scheduled_start"])
                        if scheduled == payload["scheduled_start"] and published < scheduled:
                            winner = target["result"]["winner_id"]
                            facts.add((mapping[winner], next(value for native, value in mapping.items() if native != winner), scheduled))
                if len(facts) != 1:
                    admitted = None
                    continue
                winner, loser, scheduled = next(iter(facts))
                identity = winner, loser, scheduled
                first = (admitted["result_observed_at"] if admitted is not None
                    and admitted["identity"] == identity else received)
                admitted = {"event_key": key, "winner_key": winner, "loser_key": loser,
                    "surface": surface, "scheduled_start": scheduled,
                    "result_observed_at": first, "identity": identity}
            if admitted is None:
                diagnostics["rejected"] += 1
            else:
                admitted.pop("identity")
                result.append(admitted)
    return sorted(result, key=lambda row: (row["result_observed_at"], row["event_key"]))


def missing_results(frame, cached, *, column, tour, diagnostics):
    """Conservative overlap exclusion, NOT a guessed cross-source event alias.

    Any same-pair ATP row within 30 days before the native start excludes the
    supplement, regardless of winner/surface. WTA uses its individual date
    within two days. Ambiguous overlap stays CSV-owned, never double-counted.
    """
    from pandas import Timestamp, Timedelta
    diagnostics.setdefault("csv_overlap", 0)
    pairs = defaultdict(list)
    for row in frame.to_dict("records"):
        pairs[frozenset((row["winner_key"], row["loser_key"]))].append(row[column])
    result = []
    for row in cached:
        day = Timestamp(row["scheduled_start"]).normalize()
        window = Timedelta(days=30 if tour == "ATP" else 2)
        overlap = any((date.normalize() <= day <= date.normalize() + window if tour == "ATP"
            else abs(day - date.normalize()) <= window)
            for date in pairs[frozenset((row["winner_key"], row["loser_key"]))])
        if overlap:
            diagnostics["csv_overlap"] += 1
        else:
            result.append(row)
    diagnostics["added"] = len(result)
    return result
