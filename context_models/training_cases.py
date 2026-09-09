"""Assemble unchanged B1 scalar rows from fully resolved event/replay cases.

Free arrays, hashes without bytes and later participation coefficients cannot
stand in for a historical feature computation. Unsupported source paths have
explicit exclusions; malformed claimed evidence is an integrity error.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    event_in_population, require_digest, require_list, require_object,
    validate_base_distribution, validate_event, validate_feature_vector, validate_training_row,
)
from context_models.training_contracts import validate_artifact_envelope, validate_family_config
from context_models.replay import ReplayUnavailable, replay_base_distribution

CASE_FIELDS = {"schema", "event", "base", "features", "replay_ref", "outcome_ref",
               "event_identity_hash", "family_config_hash", "preprocessing_refs"}


def case_header(resolved: dict, *, config: dict) -> dict:
    """Validate label-free case identity before any train/tune label is read."""
    require_object(resolved, {"case", "artifacts", "observations"}, label="resolved training case")
    case = validate_artifact_envelope(resolved["case"], kind="context-training-case-v1")
    payload = case["payload"]
    require_object(payload, CASE_FIELDS, label="training case")
    if type(payload["schema"]) is not int or payload["schema"] != 1:
        raise ContextContractError("unknown event case schema")
    event = validate_event(payload["event"])
    base = validate_base_distribution(payload["base"])
    features = validate_feature_vector(payload["features"])
    if (event["status"] != "scheduled" or event["scheduled_start"] <= base["cutoff"]
            or base["event_key"] != event["event_key"] or features["event_key"] != event["event_key"]
            or features["cutoff"] != base["cutoff"]):
        raise ContextIntegrityError("case must retain its original predecision event/base/feature binding")
    if (base["family"] != config["family"] or base["version"] not in config["base_versions"]
            or features["version"] != config["feature_version"] or not event_in_population(event, config["population"])
            or payload["family_config_hash"] != digest(config)):
        raise ContextIntegrityError("case belongs to a different frozen family configuration")
    for key in ("replay_ref", "outcome_ref", "event_identity_hash", "family_config_hash"):
        require_digest(payload[key], key)
    refs = require_list(payload["preprocessing_refs"], "case preprocessing refs")
    for ref in refs:
        require_digest(ref)
    if refs != sorted(set(config["preprocessing_artifacts"].values())):
        raise ContextIntegrityError("case preprocessing differs from the exact configured artifacts")
    return {**payload, "event": event, "base": base, "features": features}


def _validate_case(resolved: dict, *, config: dict) -> dict:
    from context_observations import _check_selected_row
    from context_sources.outcomes import validate_outcome_record
    from context_models.football import football_features
    config = validate_family_config(config)
    payload = case_header(resolved, config=config)
    event, base, features = (payload[key] for key in ("event", "base", "features"))
    decision = base["cutoff"]
    # No freely supplied source/state mapping may open this real replay path.
    if event["sport"] == "tennis":
        raise ReplayUnavailable("native_to_state_key_source_resolver_unavailable")
    artifacts = resolved["artifacts"]
    if type(artifacts) is not dict:
        raise ContextContractError("resolved artifacts must map actual hashes to A1 bytes")
    replay = artifacts.get(payload["replay_ref"])
    replay = validate_artifact_envelope(replay, kind="context-base-replay-v1")
    replay_data = replay["payload"]
    require_object(replay_data, {"schema", "base", "event_hash", "recipe_hash", "input_refs_hash",
        "event_identity_hash", "logical_training_cutoff", "reconstructed_at", "evidence_class"}, label="base replay evidence")
    if (type(replay_data["schema"]) is not int or replay_data["schema"] != 1
            or replay_data["event_hash"] != digest(event) or replay_data["base"] != base
            or replay_data["event_identity_hash"] != payload["event_identity_hash"]
            or replay_data["logical_training_cutoff"] != decision):
        raise ContextIntegrityError("case and original replay identities differ")
    expected_artifacts = {payload["replay_ref"], replay_data["recipe_hash"], payload["event_identity_hash"], *payload["preprocessing_refs"]}
    if set(artifacts) != expected_artifacts or any(key != value.get("digest") for key, value in artifacts.items() if type(value) is dict):
        raise ContextIntegrityError("case has missing, extra or miskeyed artifact bytes")
    recipe = validate_artifact_envelope(artifacts[replay_data["recipe_hash"]], kind="context-base-replay-recipe-v1")
    if payload["preprocessing_refs"]:
        # B4's artifact has a training_refs_hash, not resolved training rows.
        # Even an earlier training_end is insufficient evidence by itself.
        raise ReplayUnavailable("participation_training_receipts_unresolved")
    observations = resolved["observations"]
    if type(observations) is not tuple:
        raise ContextContractError("resolved case observations must be a fixed B1 tuple")
    by_ref, outcomes = {}, []
    for row in observations:
        _check_selected_row(row)
        if row["digest"] in by_ref:
            raise ContextIntegrityError("duplicate physical case receipt")
        by_ref[row["digest"]] = row
        if row["kind"] == "match_outcome":
            outcomes.append(row)
        elif row["observed_at"] > decision or row["effective_at"] > decision:
            raise ReplayUnavailable("late_feature_receipt_is_not_predecision_evidence")
    if len(outcomes) != 1 or outcomes[0]["digest"] != payload["outcome_ref"]:
        raise ContextIntegrityError("case must resolve exactly its own frozen outcome receipt")
    outcome = validate_outcome_record(outcomes[0], event=event)
    if outcome["payload"]["outcome_contract"] != config["outcome_contract"]:
        raise ContextIntegrityError("native outcome does not match the frozen target contract")
    if outcome["observed_at"] <= decision:
        raise ContextIntegrityError("target result was not strictly after the decision")
    # Resolve latest native revisions over the complete declared source pool
    # BEFORE matching the recipe. Selecting its older IDs first could hide an
    # already-known result/player correction from an apparently coherent case.
    if any(ref not in by_ref for ref in recipe["payload"]["input_refs"]):
        raise ContextIntegrityError("case is missing a native baseline input receipt")
    history = tuple(row for row in observations if row["kind"] == "base_fixture")
    rebuilt = replay_base_distribution(event["sport"], event, history,
        decision_at=datetime.fromisoformat(decision), reconstructed_at=datetime.fromisoformat(replay_data["reconstructed_at"]),
        recipe=recipe, identity_map=artifacts[payload["event_identity_hash"]])
    if rebuilt != replay:
        raise ContextIntegrityError("supplied replay does not reproduce from its original inputs")
    source_rows = tuple(row for row in observations if row["kind"] != "match_outcome")
    # The newly introduced native detail receipt and its B4 projections share
    # the same actual source clock. A newer full player collection cannot be
    # paired with older normalized minutes (including removed participants).
    from context_sources.football import _detail_event, normalize_football_context
    content_hashes = {row["content_digest"] for row in source_rows}
    for ref in recipe["payload"]["input_refs"]:
        native = by_ref[ref]
        raw = native["payload"]["detail"]
        own_event = _detail_event(raw)
        target = own_event["event_key"] == event["event_key"]
        projections = normalize_football_context(own_event, injuries=[],
            lineups=[raw] if target and "lineups" in raw else [],
            appearances=[raw] if not target and "players" in raw else [],
            observed_at=datetime.fromisoformat(native["observed_at"]))
        if any(digest(projection) not in content_hashes for projection in projections):
            raise ReplayUnavailable("native_context_projection_missing_or_superseded")
    rebuilt_features = football_features(event, source_rows, base, cutoff=datetime.fromisoformat(decision))
    if rebuilt_features != features:
        raise ContextIntegrityError("supplied feature vector does not reproduce from causal source receipts")
    if features["coverage"] != config["coverage"]:
        raise ReplayUnavailable("feature_coverage_outside_frozen_cohort")
    for name in config["feature_names"]:
        if features["states"].get(name) != "available" or not features["refs"].get(name):
            raise ReplayUnavailable("consumed_feature_unavailable")
        for ref in features["refs"][name]:
            row = by_ref.get(ref)
            if row is None or row["kind"] == "match_outcome" or row["observed_at"] > decision or row["effective_at"] > decision:
                raise ContextIntegrityError("consumed numeric feature lacks its original predecision receipt")
            if row["evidence_class"] != "prospective":
                raise ReplayUnavailable("consumed_feature_has_no_owning_archival_resolver")
    if not set(config["target_markets"]) <= set(base["markets"]):
        raise ReplayUnavailable("base_lacks_declared_target_markets")
    return deepcopy(resolved)


def _case_rows(resolved: dict, config: dict) -> tuple[dict, ...]:
    """Internal projection after full resolution, also unit-tested synthetically."""
    payload = resolved["case"]["payload"]
    base, features, event = (payload[key] for key in ("base", "features", "event"))
    outcome = next(row for row in resolved["observations"] if row["digest"] == payload["outcome_ref"])
    result = outcome["payload"]["result"]
    names = config["feature_names"]
    decision = base["cutoff"]
    block = "train" if decision < config["train_end"] else "tune" if decision < config["tune_end"] else "evaluation"
    output = []
    for head in sorted(config["head_links"]):
        if base["family"] == "football:goals:90min":
            offset, target, trials = math.log(base["params"][head + "_lambda"]), result["goals_" + head], None
        else:
            side = "home" if head in {"winner", "hold_a"} else "away"
            probability = base["params"]["p_a" if head == "winner" else head]
            if not 0 < probability < 1:
                raise ReplayUnavailable("base_probability_has_no_finite_logit")
            offset = math.log(probability / (1-probability))
            target = int(result["winner_id"] == event["home_id"]) if head == "winner" else result["held_games_" + side]
            trials = 1 if head == "winner" else result["service_games_" + side]
        row = {"event_key": event["event_key"], "decision_at": decision,
            "result_observed_at": outcome["observed_at"], "block": block,
            "population": config["population"], "coverage": config["coverage"],
            "feature_names": names, "x": [features["values"][name] for name in names],
            "offset": offset, "target": target, "trials": trials, "base_hash": digest(base),
            "feature_refs": {name: features["refs"][name] for name in names},
            "evidence_class": "prospective", "family": base["family"], "head": head}
        output.append(validate_training_row(row))
    return tuple(output)


def assemble_training_cases(cases: tuple[dict, ...], config: dict) -> dict:
    """Return rows + explicit exclusions, not a trained effect or approval."""
    from context_models.training_contracts import validate_resolved_case
    config = validate_family_config(config)
    if type(cases) is not tuple:
        raise ContextContractError("training cases must be a frozen tuple")
    seen, map_hashes, checked = set(), set(), []
    for case in cases:
        payload = case_header(case, config=config)
        key = payload["event"]["event_key"]
        if key in seen:
            raise ContextIntegrityError("duplicate native event case in one family cohort")
        seen.add(key)
        map_hashes.add(payload["event_identity_hash"])
        checked.append((payload["base"]["cutoff"], key, case))
    if len(map_hashes) > 1:
        raise ContextIntegrityError("one dataset cohort needs one global native identity map")
    rows, accepted, excluded = [], [], []
    for _, key, case in sorted(checked):
        try:
            resolved = validate_resolved_case(case, config=config)
            projected = _case_rows(resolved, config)
        except ReplayUnavailable as exc:
            excluded.append({"event_key": key, "case_hash": case["case"]["digest"], "status": exc.status, "reason": exc.reason})
            continue
        accepted.append(resolved)
        rows.extend(projected)
    return {"schema": 1, "family_config_hash": digest(config), "rows": tuple(rows),
            "cases": tuple(accepted), "excluded": tuple(excluded), "canonical_events": len(accepted)}
