"""Price-free football roster differences against a frozen base reference."""
from __future__ import annotations

from datetime import datetime

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest, require_digest,
    require_number, require_object, require_text, validate_offset_fit, validate_population,
    validate_base_distribution, validate_event, validate_feature_vector,
)
from context_observations import _check_selected_row, factor_state, freshness_policy
from context_sources.football import _collection_digest


def roster_delta(reference_minutes: dict[str, float], expected_minutes: dict[str, float]) -> dict[str, float]:
    if type(reference_minutes) is not dict or type(expected_minutes) is not dict:
        raise ContextContractError("roster minutes must be complete player mappings")
    if set(reference_minutes) != set(expected_minutes):
        raise ContextContractError("incomplete roster identity coverage")
    for values in (reference_minutes, expected_minutes):
        for player, minutes in values.items():
            require_text(player, "roster player", code=True)
            require_number(minutes, "known regulation minutes", minimum=0, maximum=90)
    return {player: (expected_minutes[player] - reference_minutes[player]) / 90.
            for player in sorted(reference_minutes)}


_APPEARANCE_FIELDS = {"player_id", "team_id", "fixture_id", "minutes", "regulation_minutes", "exposure_kind",
                      "started", "role", "result_observed_at", "event_start", "event_end", "scheduled_start", "performance",
                      "reported_player_ids", "collection_hash"}
_AVAILABILITY_FIELDS = {"player_id", "team_id", "status", "reported_type", "reported_reason", "absence_category", "scheduled_start"}
_LINEUP_FIELDS = {"player_id", "team_id", "status", "started", "role", "scheduled_start", "reported_player_ids", "collection_hash"}


def _is_empty_collection(row):
    return (row["kind"], row["source_schema"]) in {
        ("appearance", "fixture-players-v3-empty-v1"), ("confirmed_lineup", "lineups-v3-empty-v1")}


def _collection_key(row):
    payload = row["payload"]
    members = payload.get("reported_player_ids")
    if _is_empty_collection(row):
        require_object(payload, {"team_id", "scheduled_start", "reported_player_ids", "collection_hash"}, label="empty football collection")
        if members != [] or row["subject_id"] != payload["team_id"] or row["complete"] is not False:
            raise ContextIntegrityError("empty collection cannot claim a player or healthy coverage")
        if not _native_identity(payload["team_id"], "team") or payload["collection_hash"] != _collection_digest(
                row["event_key"], row["schedule_revision"], row["kind"], payload["team_id"], []):
            raise ContextIntegrityError("empty collection content binding mismatch")
        canonical_timestamp(payload["scheduled_start"])
        return row["event_key"], row["source"], row["kind"], payload["team_id"]
    if type(members) is not list or not members or any(type(p) is not str for p in members) or members != sorted(set(members)):
        raise ContextContractError("football collection members must be explicit canonical native IDs")
    if row["subject_id"] not in members or any(not _native_identity(p, "player") for p in members):
        raise ContextIntegrityError("projected football player is outside the reported collection")
    require_digest(payload.get("collection_hash"), "football team content revision")
    if not _native_identity(payload.get("team_id"), "team"):
        raise ContextContractError("football team collection requires a canonical native team")
    return row["event_key"], row["source"], row["kind"], payload["team_id"]


def _native_identity(value, kind):
    prefix = "api-football:" + kind + ":"
    if type(value) is not str or not value.startswith(prefix):
        return False
    number = value[len(prefix):]
    return number.isascii() and number.isdecimal() and int(number) > 0 and str(int(number)) == number


def _collection_conflicts(rows):
    collections = {}
    for row in rows:
        if row["kind"] in {"appearance", "confirmed_lineup"}:
            collections.setdefault(_collection_key(row), []).append(row)
    return {player for group in collections.values() if len({r["payload"]["collection_hash"] for r in group}) > 1
            for row in group for player in row["payload"]["reported_player_ids"]}


def _selected(rows, *, cutoff):
    """Retain real causal B1 receipts; do not trust a hand-made 'available' flag."""
    if type(rows) is not tuple:
        raise ContextContractError("football observations must be selected B1 tuples")
    decision = canonical_timestamp(cutoff)
    groups = {}
    for row in rows:
        _check_selected_row(row)
        if row["source"] != "api-football" or row["sport"] != "football":
            raise ContextContractError("football roster source is not a supported native adapter")
        if row["evidence_class"] != "prospective" or row["observed_at"] > decision:
            continue
        if (row["valid_from"] != row["observed_at"] or row["valid_until"] is not None
                or row["published_at"] is not None or row["publication_proof"] is not None
                or row["source_revision"] != digest(row["payload"])):
            raise ContextIntegrityError("football source validity/receipt binding mismatch")
        key = (row["event_key"], row["subject_id"], row["kind"], row["source"])
        previous = groups.get(key)
        if previous is None or row["observed_at"] > previous[0]["observed_at"]:
            groups[key] = [row]
        elif row["observed_at"] == previous[0]["observed_at"] and row["digest"] not in {r["digest"] for r in previous}:
            previous.append(row)
    selected = tuple(r for group in groups.values() for r in group)
    latest_collections = {}
    for row in selected:
        if row["kind"] in {"appearance", "confirmed_lineup"}:
            key = _collection_key(row)
            latest_collections[key] = max(latest_collections.get(key, row["observed_at"]), row["observed_at"])
    current = tuple(r for r in selected if r["kind"] not in {"appearance", "confirmed_lineup"}
                    or r["observed_at"] == latest_collections[_collection_key(r)])
    collection_rows = {}
    for row in current:
        if row["kind"] in {"appearance", "confirmed_lineup"}:
            collection_rows.setdefault(_collection_key(row), []).append(row)
    incomplete = set()
    for key, group in collection_rows.items():
        if len({r["payload"]["collection_hash"] for r in group}) != 1:
            continue  # Preserve all competing revisions for explicit conflict handling.
        first = group[0]
        if all(_is_empty_collection(row) for row in group):
            continue  # Retain the withdrawal for latest-revision/conflict checks.
        if {r["subject_id"] for r in group} != set(first["payload"]["reported_player_ids"]):
            incomplete.add(key)
            continue
        actual = _collection_digest(first["event_key"], first["schedule_revision"], first["kind"],
                                    first["payload"]["team_id"], [r["payload"] for r in group])
        if actual != first["payload"]["collection_hash"]:
            raise ContextIntegrityError("football projections do not reconstruct their complete content revision")
    return tuple(r for r in current if r["kind"] not in {"appearance", "confirmed_lineup"}
                 or _collection_key(r) not in incomplete)


def _appearance_payload(row, *, cutoff):
    if row["kind"] != "appearance" or row["source_schema"] != "fixture-players-v3-context-v1":
        raise ContextContractError("unsupported football appearance schema")
    payload = row["payload"]
    require_object(payload, _APPEARANCE_FIELDS, label="normalized match appearance")
    if payload["player_id"] != row["subject_id"] or payload["fixture_id"] != row["event_key"]:
        raise ContextIntegrityError("appearance native player/event binding mismatch")
    for name, kind in (("player_id", "player"), ("team_id", "team")):
        if not _native_identity(payload[name], kind):
            raise ContextContractError("appearance requires canonical native player/team IDs")
    for name, maximum in (("minutes", 120), ("regulation_minutes", 90)):
        if payload[name] is not None:
            require_number(payload[name], name, minimum=0, maximum=maximum)
    if payload["started"] is not None and type(payload["started"]) is not bool:
        raise ContextContractError("appearance start flag must remain boolean or unknown")
    if payload["exposure_kind"] not in {"regulation_reported", "total_only"}:
        raise ContextContractError("unknown match exposure type")
    if payload["exposure_kind"] == "total_only" and payload["regulation_minutes"] is not None:
        raise ContextContractError("extra-time total cannot claim regulation exposure")
    if payload["exposure_kind"] == "regulation_reported" and payload["minutes"] != payload["regulation_minutes"]:
        raise ContextContractError("regulation exposure differs from the reported regulation minutes")
    result_at = canonical_timestamp(payload["result_observed_at"])
    if result_at > row["observed_at"] or result_at > canonical_timestamp(cutoff):
        raise ContextContractError("appearance result was not actually known at the decision")
    planned = canonical_timestamp(payload["scheduled_start"])
    if planned >= result_at:
        raise ContextContractError("appearance result precedes its fixture schedule")
    if payload["event_end"] is not None:
        ended = canonical_timestamp(payload["event_end"])
        if ended > result_at or (payload["event_start"] is not None and canonical_timestamp(payload["event_start"]) > ended):
            raise ContextContractError("inconsistent actual appearance chronology")
    return payload


def _participation_probability(envelope, *, cutoff, rows):
    """Mechanics for a D1-fitted, A1-resolved status model, not model approval.

    The owning training resolver must validate the causal training inventory.
    A content hash only binds that transport; it does not certify its quality.
    There is intentionally no default participation percentage.
    """
    if envelope is None:
        return None
    require_object(envelope, {"digest", "kind", "payload"}, label="participation artifact envelope")
    require_digest(envelope["digest"])
    if envelope["kind"] != "football-participation-v1" or digest({"kind": envelope["kind"], "payload": envelope["payload"]}) != envelope["digest"]:
        raise ContextIntegrityError("participation artifact identity mismatch")
    payload = envelope["payload"]
    require_object(payload, {"schema", "version", "training_end", "training_refs_hash", "population",
                             "feature_names", "base_probability", "fit"}, label="participation artifact")
    if type(payload["schema"]) is not int or payload["schema"] != 1 or payload["version"] != "football-doubtful-v1":
        raise ContextContractError("unsupported participation variant")
    if payload["feature_names"] != ["doubtful"]:
        raise ContextContractError("participation feature order/definition mismatch")
    if canonical_timestamp(payload["training_end"]) > canonical_timestamp(cutoff):
        raise ContextContractError("participation fit follows the prediction cutoff")
    require_digest(payload["training_refs_hash"])
    population = validate_population(payload["population"])
    if population["sport"] != "football" or any(row["competition"] not in population["competitions"] or row["format"] not in population["formats"] for row in rows):
        raise ContextContractError("participation model cannot transfer to an untrained population")
    fit = validate_offset_fit(payload["fit"])
    if fit["link"] != "logit" or len(fit["coef"]) != 1:
        raise ContextContractError("participation requires its trained one-column binomial model")
    base_p = require_number(payload["base_probability"], "participation baseline", minimum=0, maximum=1)
    if not 0 < base_p < 1:
        raise ContextContractError("participation baseline must be interior")
    import numpy as np
    from context_models.offset import adjust_parameters, offset_delta
    return float(adjust_parameters(np.array([base_p]), offset_delta(fit, np.array([[1.]])), link="logit")[0])


def expected_roster(appearances: tuple[dict, ...], availability: tuple[dict, ...], *,
                    cutoff: datetime, participation: dict | None = None) -> dict:
    """Expected regulation exposure for the explicitly reported player cohort.

    Historical minutes are conditional on a confirmed starter/bench role; a
    doubtful player's present scenario uses observed positive participation.
    With no status model, named all-present/all-absent scenarios are contrasts,
    not an exhaustive scenario distribution or an implied 50/50 mixture.
    Missing team coverage never becomes a 'healthy' roster.
    """
    past, facts = _selected(appearances, cutoff=cutoff), _selected(availability, cutoff=cutoff)
    chance = _participation_probability(participation, cutoff=cutoff, rows=facts)
    history, facts_by_player, conflicts = {}, {}, _collection_conflicts(past + facts)
    refs = set()
    for row in past:
        if _is_empty_collection(row):
            continue
        payload = _appearance_payload(row, cutoff=cutoff)
        history.setdefault(payload["player_id"], []).append(row)
    scopes = {(r["event_key"], r["competition"], r["format"], r["schedule_revision"],
               canonical_timestamp(r["payload"].get("scheduled_start"))) for r in facts}
    if len(scopes) > 1:
        raise ContextContractError("expected lineup facts must share one native event and schedule")
    for row in facts:
        if not row["subject_id"].startswith("api-football:player:"):
            continue  # Collection diagnostics are not player numerical inputs.
        fields = _LINEUP_FIELDS if row["kind"] == "confirmed_lineup" else _AVAILABILITY_FIELDS
        schema = "lineups-v3-context-v1" if row["kind"] == "confirmed_lineup" else "injuries-v3-context-v1"
        if row["kind"] not in {"availability", "confirmed_lineup"} or row["source_schema"] != schema:
            raise ContextContractError("unsupported availability source schema")
        require_object(row["payload"], fields, label="normalized player availability")
        if row["payload"]["player_id"] != row["subject_id"]:
            raise ContextIntegrityError("availability player identity mismatch")
        facts_by_player.setdefault(row["subject_id"], []).append(row)
    central, present, absent, missing, uncertain = {}, {}, {}, set(), set()
    for player in sorted(set(history) | set(facts_by_player)):
        if player in conflicts:
            continue
        selected_fact = None
        for kind in ("confirmed_lineup", "availability"):
            group = tuple(r for r in facts_by_player.get(player, ()) if r["kind"] == kind)
            if not group:
                continue
            row = group[0]
            state = factor_state(group, cutoff=cutoff, scheduled_start=datetime.fromisoformat(row["payload"]["scheduled_start"]),
                                 policy=freshness_policy(kind, schedule_revision=row["schedule_revision"], requires_complete=False))
            if state["state"] == "conflicting":
                conflicts.add(player)
                break
            if state["state"] == "available":
                selected_fact = next(r for r in group if r["digest"] in state["usable_refs"])
                refs.update(state["usable_refs"])
                break
        if selected_fact is None:
            missing.add(player)
            continue
        status = selected_fact["payload"]["status"]
        if status in {"out", "suspended"}:
            central[player] = present[player] = absent[player] = 0.
            continue
        if status not in {"available", "doubtful"}:
            missing.add(player)
            continue
        samples = history.get(player, [])
        by_fixture = {}
        for row in samples:
            by_fixture.setdefault(row["event_key"], []).append(row)
        if any(len({digest(r["payload"]) for r in rows}) > 1 for rows in by_fixture.values()):
            conflicts.add(player)
            continue
        samples = [rows[0] for rows in by_fixture.values()]
        if any(r["payload"]["team_id"] != selected_fact["payload"]["team_id"] for r in samples):
            missing.add(player)  # Transfer/team history is not an automatic population bridge.
            continue
        if selected_fact["kind"] == "confirmed_lineup":
            started = selected_fact["payload"]["started"]
            if type(started) is not bool:
                raise ContextContractError("confirmed lineup requires an actual starter/bench role")
            samples = [r for r in samples if r["payload"]["started"] is started]
        elif status == "doubtful":
            samples = [r for r in samples if r["payload"]["regulation_minutes"] is not None and r["payload"]["regulation_minutes"] > 0]
        if not samples or any(r["payload"]["regulation_minutes"] is None for r in samples):
            missing.add(player)
            continue
        minutes = sum(r["payload"]["regulation_minutes"] for r in samples) / len(samples)
        refs.update(r["digest"] for r in samples)
        present[player] = minutes
        absent[player] = 0. if status == "doubtful" else minutes
        if status == "doubtful":
            uncertain.add(player)
            if chance is not None:
                central[player] = chance * minutes
        else:
            central[player] = minutes
    unresolved = bool(missing or conflicts or (uncertain and chance is None))
    case = "conflicting" if conflicts else "incomplete" if missing or not facts_by_player else "doubtful_scenarios" if uncertain and chance is None else "reported_players"
    scenarios = ({"all_doubtful_present": present, "all_doubtful_absent": absent}
                 if uncertain and not missing and not conflicts else {})
    return {"central_minutes": None if unresolved or not central else central, "scenarios": scenarios,
            "coverage": {"version": "football-roster-v1", "case": case}, "refs": sorted(refs)}


def football_features(event: dict, observations: tuple[dict, ...], base: dict, *, cutoff: datetime,
                      preprocessing: dict | None = None) -> dict:
    """Build versioned roster columns against the exact base sample support.

    For each player/component/metric the column is
    outer * pair * metric * sum(sample_weight * (expected - historical)) / 90.
    The league pseudo-count has no named roster: its unchanged contribution is
    never reinterpreted as a healthy team or given a fictitious player. Every
    history sample needs explicitly known regulation minutes for every joined
    player; missing rows are not zero. These are features, not assigned effects.
    """
    event, base = validate_event(event), validate_base_distribution(base)
    decision = canonical_timestamp(cutoff)
    if event["sport"] != "football" or base["family"] != "football:goals:90min":
        raise ContextContractError("football roster features require the 90-minute goal family")
    if event["event_key"] != base["event_key"] or base["cutoff"] != decision:
        raise ContextIntegrityError("football event/base/feature revision differs")
    if type(observations) is not tuple:
        raise ContextContractError("football feature observations must be a B1 tuple")
    for row in observations:
        _check_selected_row(row)
    relevant = tuple(r for r in observations if r["kind"] in {"appearance", "availability", "confirmed_lineup"})
    chosen = _selected(relevant, cutoff=cutoff)
    past = tuple(r for r in chosen if r["kind"] == "appearance")
    facts = tuple(r for r in chosen if r["kind"] in {"availability", "confirmed_lineup"}
                  and r["event_key"] == event["event_key"] and r["schedule_revision"] == event["schedule_revision"])
    for row in facts:
        if (row["competition"], row["format"]) != (event["competition"], event["format"]):
            raise ContextIntegrityError("football fact event scope mismatch")
        if row["payload"].get("team_id") not in {event["home_id"], event["away_id"]}:
            raise ContextIntegrityError("football fact participant binding mismatch")
        if canonical_timestamp(row["payload"].get("scheduled_start")) != event["scheduled_start"]:
            raise ContextIntegrityError("football fact kickoff differs from the worker revision")
    participation, preprocessing_refs = None, []
    if preprocessing is not None:
        if type(preprocessing) is not dict:
            raise ContextContractError("preprocessing must map immutable hashes to verified A1 payloads")
        for key, value in preprocessing.items():
            require_digest(key)
            require_object(value, {"kind", "payload"}, label="verified preprocessing transport")
            if value["kind"] != "football-participation-v1" or participation is not None:
                raise ContextContractError("unsupported or ambiguous football preprocessing")
            participation = {"digest": key, **value}
            _participation_probability(participation, cutoff=cutoff, rows=facts)
            preprocessing_refs.append(key)
    expected = expected_roster(past, facts, cutoff=cutoff, participation=participation)
    values, states, refs = {}, {}, {}
    provenance = base["reference_weights"]
    reference_hash = digest({"version": "football-context-reference-v2", "base_hash": digest(base),
                             "event_hash": digest(event), "preprocessing": sorted(preprocessing_refs)})
    case = expected["coverage"]["case"]
    applicable = event["status"] == "scheduled" and decision < event["scheduled_start"]

    def add(key, value, references=()):
        values[key] = value if applicable else None
        states[key] = ("available" if value is not None else "missing") if applicable else "not_applicable"
        refs[key] = sorted(set(references)) if value is not None and applicable else []

    if provenance["kind"] == "unavailable":
        add("roster_reference", None)
        case = "reference_unavailable"
    else:
        historical = {r["ref"]: r for r in base["history_refs"]}
        appearances_by_event_team = {}
        for row in past:
            if _is_empty_collection(row):
                continue
            payload = _appearance_payload(row, cutoff=cutoff)
            appearances_by_event_team.setdefault((row["event_key"], payload["team_id"]), []).append(row)
        consumed = set(expected["refs"])
        for side, head in provenance["heads"].items():
            for component_name, component in head["components"].items():
                component_team = event["home_id"] if ((side == "home") == component_name.endswith("attack")) else event["away_id"]
                if component["team_join"] == "verified_native" and component["team_id"] != component_team:
                    raise ContextIntegrityError("baseline roster component has another target team")
                group_name, role = component_name.split("_")
                for metric in ("goals", "xg"):
                    term = component[metric]
                    if term is None:
                        continue
                    prefix = f"{side}.{component_name}.{metric}"
                    matches, players, valid = [], set(), component["team_join"] == "verified_native"
                    for sample in term["samples"]:
                        historical_row = historical[sample["ref"]]
                        if historical_row["event_join"] != "verified_native" or historical_row["roster_join"] != "verified_native":
                            valid = False
                            continue
                        rows = appearances_by_event_team.get((historical_row["native_event_key"], component["team_id"]), [])
                        if not rows:
                            valid = False
                        by_player = {}
                        for row in rows:
                            by_player.setdefault(row["subject_id"], []).append(row)
                        players.update(by_player)
                        matches.append((sample["weight"], by_player))
                    if not players:
                        add(prefix + ".reference", None)
                        case = "reference_unavailable"
                        continue
                    for player in sorted(players):
                        references = set()
                        expected_minutes = expected["central_minutes"]
                        supported = valid and expected_minutes is not None and player in expected_minutes
                        weighted_change = 0.
                        for weight, by_player in matches:
                            rows = by_player.get(player, [])
                            if len(rows) != 1 or rows[0]["payload"]["regulation_minutes"] is None:
                                supported = False
                                continue
                            references.add(rows[0]["digest"])
                            if expected_minutes is not None and player in expected_minutes:
                                weighted_change += weight * (expected_minutes[player] - rows[0]["payload"]["regulation_minutes"])
                        # The receipt-level dependency is this player's usable
                        # expected-role history/status, never other diagnostic refs.
                        references.update(r["digest"] for r in (*past, *facts)
                                          if r["subject_id"] == player and r["digest"] in consumed)
                        coefficient = head["outer_weights"][group_name] * head["pair_weights"][group_name][role] * component["metric_weights"][metric]
                        add(prefix + "." + player, coefficient * weighted_change / 90. if supported else None, references)
                        if not valid:
                            case = "reference_unavailable"
    return validate_feature_vector({"version": "football-roster-components-v2", "event_key": event["event_key"],
                                    "cutoff": decision, "values": values, "states": states, "refs": refs,
                                    "coverage": {"version": "football-roster-v1", "case": case},
                                    "reference_hash": reference_hash})
