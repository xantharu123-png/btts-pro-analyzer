"""Observed live-winner residual training, not a native historical state join.

The baseline is the actual pre-match, stored, reproducible app forecast. Native
status receipts bind today's players; they do NOT prove the legacy name-keyed
model's historical identities. Unknown environment is a separate population,
never a surface claim. D2 still has to qualify every effect on held-out events.
No network, database mutation, invented durations or automatic activation.
"""
from copy import deepcopy
from datetime import datetime

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, original_base, validate_original_publication
from context_models.tennis_v3 import tennis_features_v3
from context_models.training_contracts import resolve_identity_map, validate_artifact_envelope
from context_models.replay import ReplayUnavailable
from context_observations import _SELECT, _check_selected_row, _decode_receipt
from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt
from model_artifacts import canonical_bytes


def _same(actual, expected, message):
    if canonical_bytes(actual) != canonical_bytes(expected):
        raise ContextIntegrityError(message)


def relevant_receipts(connection, event, cutoff):
    """All revisions of any native match ever associated with either player.

    This is equivalent to v3's participant filter, not 'take latest wins'. A
    correction removing a participant stays included. Only context bodies are
    opened; match-outcome labels and other sports are never selected here.
    """
    clock = canonical_timestamp(cutoff)
    keys = {event["event_key"]}
    params = (clock, event["tour"], event["home_id"], event["away_id"])
    query = """SELECT DISTINCT r.event_key FROM context_observations r
        JOIN context_contents c ON c.content_digest=r.content_digest
        WHERE r.source='espn' AND r.kind IN ('event_status','workload') AND r.observed_at<=?1
        AND json_extract(CAST(c.payload AS TEXT),'$.payload.tour')=?2
        AND (json_extract(CAST(c.payload AS TEXT),'$.payload.player_id') IN (?3,?4)
          OR json_extract(CAST(c.payload AS TEXT),'$.payload.opponent_id') IN (?3,?4)
          OR EXISTS (SELECT 1 FROM json_each(CAST(c.payload AS TEXT),'$.payload.participant_ids')
                     WHERE value IN (?3,?4)))"""
    keys.update(row[0] for row in connection.execute(query, params))
    selected = []
    for key in sorted(keys):
        for raw in connection.execute(_SELECT + " WHERE r.event_key=? AND r.observed_at<=?"
                " AND r.source='espn' AND r.kind IN ('event_status','workload') ORDER BY r.observed_at,r.digest",
                (key, clock)):
            row = _decode_receipt(raw)
            row.update(evidence_class="prospective", effective_at=row["observed_at"], publication_resolution=None)
            validate_selected_tennis_receipt(row)
            if row["payload"]["tour"] != event["tour"]:
                raise ContextIntegrityError("native match revision crosses tennis tours")
            selected.append(row)
    return tuple(sorted(selected, key=lambda row: (row["observed_at"], row["digest"])))


def live_case_artifacts(connection, payload, *, latest):
    """Resolve physical publication clocks, not just hash-shaped metadata."""
    from context_models.dataset import _artifact
    from context_models.experiments import _artifact_created_at
    original = _artifact(connection, payload["replay_ref"], ORIGINAL_ARTIFACT_KIND, latest=latest)
    created = _artifact_created_at(connection, original["digest"])
    publication = validate_original_publication(original["payload"], created_at=created)
    base = original_base(publication["origin"])
    _same(base, payload["base"], "case differs from actual published original")
    _same(publication["origin"]["event"], payload["event"], "case differs from original event")
    if created >= payload["event"]["scheduled_start"]:
        raise ContextIntegrityError("training original was not stored before scheduled start")
    state = _artifact(connection, base["model_hash"], "tennis-tour-state", latest=base["cutoff"])
    identity = _artifact(connection, payload["event_identity_hash"], "context-native-identity-map-v1", latest=latest)
    return {item["digest"]: item for item in (original, state, identity)}


def validate_live_training_case(resolved, *, config, payload):
    from context_models.tennis_effect import _feature_input
    from context_models.offset import ContextModelError
    from context_sources.outcomes import validate_outcome_record
    from context_runtime_tennis import _code_variants, _native_event
    from tennis.predict import predict_match
    from tennis.tour_state import _decode_wrapper
    event, base, features = (payload[name] for name in ("event", "base", "features"))
    decision = base["cutoff"]
    artifacts = resolved["artifacts"]
    expected = {payload["replay_ref"], base["model_hash"], payload["event_identity_hash"]}
    if type(artifacts) is not dict or set(artifacts) != expected:
        raise ContextIntegrityError("live case lacks its exact original, tour state or native map")
    original = validate_artifact_envelope(artifacts[payload["replay_ref"]], kind=ORIGINAL_ARTIFACT_KIND)
    origin = original["payload"]["origin"]
    _same(original["payload"], {"schema": 1, "origin": origin}, "unknown original publication fields")
    _same(original_base(origin), base, "case substituted its original live forecast")
    _same(origin["event"], event, "live case changed the original native event")
    for ref, artifact in artifacts.items():
        if artifact.get("digest") != ref:
            raise ContextIntegrityError("miskeyed original artifact")
    state_envelope = validate_artifact_envelope(artifacts[base["model_hash"]], kind="tennis-tour-state")
    state = _decode_wrapper(state_envelope["payload"], event["tour"])
    if state.built_at > datetime.fromisoformat(decision).timestamp():
        raise ContextIntegrityError("original tour state was built after the decision")
    variants = _code_variants()
    if any(value not in variants[name] for name, value in origin["code_hashes"].items()):
        raise ContextIntegrityError("original calculation has no supported exact source replay")
    if type(resolved["observations"]) is not tuple:
        raise ContextContractError("live training requires immutable source receipts")
    by_ref, history, outcomes = {}, [], []
    for row in resolved["observations"]:
        _check_selected_row(row)
        if row["digest"] in by_ref:
            raise ContextIntegrityError("duplicate physical live training receipt")
        by_ref[row["digest"]] = row
        if row["kind"] == "match_outcome":
            outcomes.append(row)
            continue
        if row["observed_at"] > decision or row["effective_at"] > decision or row["evidence_class"] != "prospective":
            raise ReplayUnavailable("late_feature_receipt_is_not_predecision_evidence")
        validate_selected_tennis_receipt(row)
        if row["payload"]["tour"] != event["tour"]:
            raise ContextIntegrityError("live training includes another tour")
        history.append(row)
    if len(outcomes) != 1 or outcomes[0]["digest"] != payload["outcome_ref"]:
        raise ContextIntegrityError("live case must resolve exactly its own frozen outcome")
    outcome = validate_outcome_record(outcomes[0], event=event)
    if outcome["observed_at"] <= decision or outcome["payload"]["outcome_contract"] != config["outcome_contract"]:
        raise ContextIntegrityError("live outcome is not a later normal winner of this contract")
    identity = resolve_identity_map(artifacts[payload["event_identity_hash"]],
        observations=tuple(history), event_keys=(event["event_key"],))
    binding = next(row for row in identity["payload"]["bindings"] if row["event_key"] == event["event_key"])
    _same(binding, {"event_key": event["event_key"], "home_id": event["home_id"], "away_id": event["away_id"],
        "source_refs": [origin["native_receipt"]]}, "live identity map differs from original source binding")
    target = [row for row in history if row["event_key"] == event["event_key"]]
    newest = max((row["observed_at"] for row in target), default=None)
    latest = [row for row in target if row["observed_at"] == newest]
    if (len(latest) != 1 or latest[0]["digest"] != origin["native_receipt"]
            or latest[0]["source_schema"] != STATUS_SCHEMA
            or latest[0]["observed_at"] != origin["native_observed_at"]
            or latest[0]["payload"]["competition_revision"] != origin["competition_revision"]
            or latest[0]["payload"]["status"] != "scheduled" or latest[0]["payload"]["issues"]):
        raise ContextIntegrityError("original native target was missing, conflicting or superseded")
    _same(_native_event(latest[0]), event, "original native target differs from case")
    captures = []
    predict_match(state, **{key: origin["inputs"][key] for key in (
        "player_a", "player_b", "surface", "best_of", "tour", "indoor")},
        as_of=datetime.fromisoformat(decision), workload_history=(), original_capture=captures.append)
    _same(captures, [{"inputs": origin["inputs"], "values": origin["values"]}],
        "stored original does not reproduce from the actual tour model")
    rebuilt = tennis_features_v3(event, tuple(history), base, cutoff=datetime.fromisoformat(decision))
    _same(rebuilt, features, "live feature vector differs from causal source receipts")
    if features["coverage"] != config["coverage"]:
        raise ReplayUnavailable("feature_coverage_outside_frozen_cohort")
    try:
        _feature_input(features, config["feature_names"], family="tennis:winner")
    except ContextModelError as exc:
        raise ReplayUnavailable("consumed_feature_unavailable") from exc
    return deepcopy(resolved)


def build_live_training_case(path, *, original_ref, outcome_ref, identity_ref, config, as_of):
    """Build, do not publish, a case from existing immutable app receipts.

    Caller freezes one native event/decision per cohort before evaluation.
    This function never picks profitable results or an alpha, and cannot
    manufacture an original for a match which was not actually predicted.
    """
    from context_models.dataset import _artifact, _reader, _receipt
    from context_models.training_contracts import validate_family_config, validate_resolved_case
    config = validate_family_config(config)
    clock = canonical_timestamp(as_of)
    with _reader(path) as connection:
        original = _artifact(connection, original_ref, ORIGINAL_ARTIFACT_KIND, latest=clock)
        origin = original["payload"]["origin"]
        base, event = original_base(origin), origin["event"]
        history = relevant_receipts(connection, event, base["cutoff"])
        features = tennis_features_v3(event, history, base, cutoff=datetime.fromisoformat(base["cutoff"]))
        payload = {"schema": 1, "event": event, "base": base, "features": features, "replay_ref": original_ref,
            "outcome_ref": outcome_ref, "event_identity_hash": identity_ref, "family_config_hash": digest(config),
            "preprocessing_refs": []}
        artifacts = live_case_artifacts(connection, payload, latest=clock)
        outcome = _receipt(connection, outcome_ref)
        if outcome["observed_at"] > clock:
            raise ContextIntegrityError("outcome was received after case construction")
        outcome.update(effective_at=outcome["observed_at"], evidence_class="prospective", publication_resolution=None)
        case = {"kind": "context-training-case-v1", "payload": payload}
        resolved = {"case": {"digest": digest(case), **case}, "artifacts": artifacts, "observations": history+(outcome,)}
        return validate_resolved_case(resolved, config=config)
