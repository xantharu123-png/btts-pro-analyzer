"""Bounded prematch joint comparison from an existing committed capture.

No source fetch, fitting, historical rewrite or effect activation belongs here.
An absent fitted effect creates no new database record. A fitted comparison
uses the first actual worker decision for its ORIGINAL/source/model revision;
later readers reuse that revision instead of persisting every clock tick.
Unqualified comparisons remain internal and preserve the original markets.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    event_in_population, require_digest, validate_effect_artifact,
    require_object, require_number, require_text,
)
from context_models.dataset import _reader
from context_models.experiments import _artifact_created_at
from context_models.football_joint_context import COVERAGE, FEATURE_VERSION, VERSION, joint_features
from context_models.football_original_storage import StorageBudgetExceeded
from context_models.football_training import _load_publication, joint_base
from context_models.replay import ReplayUnavailable
from context_snapshots import _decode_snapshot, compute_once
from context_transport import (
    KIND, calculate_context_payload, context_consumer_reference, context_payload_key,
)
from model_artifacts import _load_active, _load_artifact, canonical_bytes
from context_observations import _SELECT, _decode_receipt

POINTER_KIND = "football-joint-worker-revision-v1"
MAX_EVENT_BYTES = 512 * 1024
MAX_RUN_BYTES = 1024 * 1024
MAX_RUN_EVENTS = 32
MAX_SOURCE_RECEIPTS = 4096
MAX_SOURCE_BYTES = 4 * 1024 * 1024


def _bounded_receipts(connection, packet, *, cutoff):
    """Read the owning complete revision pool or decline it; never truncate.

    Count and physical content byte sizes are inspected before retrieving or
    decoding each body. Same reader transaction owns both queries. Limits are
    resource admission, not permission to select a convenient older revision.
    """
    import challenge_engine as engine
    ids = {engine.football_base_history_record(raw)["fixture_id"] for raw in
           [packet["fixture"], *packet["league_history"], *(packet["team_history"] or [])]}
    result, content_bytes = [], 0
    for native_id in sorted(ids):
        headers = connection.execute(
            "SELECT r.digest,typeof(c.payload),length(CAST(c.payload AS BLOB)) "
            "FROM context_observations r LEFT JOIN context_contents c ON c.content_digest=r.content_digest "
            "WHERE r.event_key=? AND r.observed_at<=? AND r.kind!='match_outcome' "
            "ORDER BY r.observed_at,r.digest LIMIT ?",
            ("api-football:football:" + str(native_id), cutoff, MAX_SOURCE_RECEIPTS-len(result)+1),
        ).fetchall()
        if len(headers) > MAX_SOURCE_RECEIPTS-len(result):
            raise ReplayUnavailable("joint_source_receipt_bound_exceeded")
        for ref, kind, size in headers:
            if kind != "blob" or type(size) is not int or size <= 0:
                raise ContextIntegrityError("joint source content is missing or not a canonical blob")
            if content_bytes + size > MAX_SOURCE_BYTES:
                raise ReplayUnavailable("joint_source_byte_bound_exceeded")
            raw = connection.execute(_SELECT + " WHERE r.digest=?", (ref,)).fetchone()
            if raw is None or type(raw[-1]) is not bytes or len(raw[-1]) != size:
                raise ContextIntegrityError("joint source body differs from its bounded header")
            row = _decode_receipt(raw)
            row.update(evidence_class="prospective", effective_at=row["observed_at"], publication_resolution=None)
            result.append(row)
            content_bytes += size
    return tuple(sorted(result, key=lambda row: (row["observed_at"], row["digest"])))


def _active_fits(connection, *, decision):
    """Read the existing active fitted effect; never inherit an approval hash.

    This first connection is explicitly experimental. Enabling a public
    replacement requires the separately verified D2 owning-evidence boundary.
    """
    manifest, slots = _load_active(connection)
    if manifest is None:
        return None, (), "effect-unavailable"
    published = connection.execute(
        "SELECT published_at FROM manifests WHERE digest=?", (manifest,),
    ).fetchone()[0]
    if canonical_timestamp(published) > decision:
        return manifest, (), "effect-after-decision"
    matches = []
    for ref in sorted(set(slots.values())):
        # ATP/WTA slots can contain large tour models. Inspect only their kind;
        # do not deserialize unrelated sport models in this context worker.
        kind = connection.execute("SELECT kind FROM artifacts WHERE digest=?", (ref,)).fetchone()
        if kind is None:
            raise ContextIntegrityError("active manifest references a missing artifact")
        if kind != ("context-effect-v1",):
            continue
        envelope = _load_artifact(connection, ref)
        effect = validate_effect_artifact(envelope["payload"])
        if canonical_bytes(effect) != canonical_bytes(envelope["payload"]):
            raise ContextIntegrityError("active joint effect is not canonical")
        created = _artifact_created_at(connection, ref)
        if effect["training_end"] > created:
            raise ContextIntegrityError("joint effect was published before its stated training end")
        if (effect["sport"] == "football" and effect["family"] == "football:goals:90min"
                and effect["feature_version"] == FEATURE_VERSION and effect["coverage"] == COVERAGE
                and effect["model_variant"] == VERSION and effect["training_end"] <= decision
                and created <= decision):
            matches.append((ref, envelope))
    return manifest, tuple(matches), "effect-unavailable" if not matches else "experimental-no-owning-approval"


def _stored_pointer(connection, key):
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='context_snapshots'").fetchone():
        return None
    row = connection.execute("SELECT payload,payload_digest FROM context_snapshots WHERE key=?", (key,)).fetchone()
    return None if row is None else _decode_snapshot(key, *row, connection=connection)


def _native_binding(binding, original, rows):
    """Verify exact consumed inputs without rerunning the sport calculation."""
    import challenge_engine as engine
    from context_sources.football import _detail_event
    from context_models.football_training import _check_goal_source
    packet = original.to_dict()
    expected = {row["ref"] for row in packet["goal_provenance"]["history_refs"]} | {binding["target_record"]}
    if set(binding["consumed_receipts"]) != expected or set(binding["inspected_receipts"]) != expected:
        raise ContextIntegrityError("joint worker binding differs from its original input union")
    by_ref = {row["digest"]: row for row in rows}
    raw_by_ref = {digest(engine.football_base_history_record(raw)): raw for raw in
                  [packet["fixture"], *packet["league_history"], *(packet["team_history"] or [])]}
    for record_ref in expected:
        consumed, inspected = binding["consumed_receipts"][record_ref], binding["inspected_receipts"][record_ref]
        if (record_ref not in raw_by_ref or type(consumed) is not list or not consumed
                or consumed != sorted(set(consumed)) or type(inspected) is not list or not inspected
                or inspected != sorted(set(inspected)) or not set(consumed) <= set(inspected)):
            raise ContextIntegrityError("joint worker original has incomplete receipt references")
        record = engine.football_base_history_record(raw_by_ref[record_ref])
        selected = []
        for ref in inspected:
            row = by_ref.get(ref)
            if (row is None or row["kind"] != "base_fixture"
                    or row["event_key"] != "api-football:football:" + str(record["fixture_id"])
                    or row["observed_at"] > binding["decision_at"]):
                raise ContextIntegrityError("joint worker original receipt belongs to another event or time")
            selected.append(row)
        newest = max(row["observed_at"] for row in selected)
        latest = [row for row in selected if row["observed_at"] == newest]
        if sorted(row["digest"] for row in latest) != consumed:
            raise ContextIntegrityError("joint worker changed the consumed original source revision")
        for row in latest:
            _check_goal_source(record, row["payload"]["detail"])
    target = [row for row in rows if row["kind"] == "base_fixture"
              and row["event_key"] == binding["native_event"]["event_key"]]
    newest = max((row["observed_at"] for row in target), default=None)
    if not target or any(_detail_event(row["payload"]["detail"]) != binding["native_event"]
                         for row in target if row["observed_at"] == newest):
        raise ReplayUnavailable("target_changed_before_context_decision")


def publish_joint_comparison(path, binding_ref, *, decision_at, max_payload_bytes=MAX_EVENT_BYTES):
    """Resolve one existing publication after source capture has committed.

    Returns a compact internal report, not a public prediction or certified
    probability. Missing sources/effects retain the caller's existing baseline.
    No prices, names-only joins or untrusted caller effect parameters accepted.
    """
    if not isinstance(decision_at, datetime) or decision_at.utcoffset() is None:
        raise ContextContractError("joint worker needs its actual aware decision clock")
    if type(max_payload_bytes) is not int or not 0 < max_payload_bytes <= MAX_EVENT_BYTES:
        raise ContextContractError("joint comparison payload budget is not bounded")
    binding_ref = require_digest(binding_ref, "committed original binding")
    decision = canonical_timestamp(decision_at)
    summary = {"binding_ref": binding_ref, "role": "not_applied", "reference": None}
    try:
        with _reader(Path(path)) as connection:
            manifest, fits, reason = _active_fits(connection, decision=decision)
            if not fits:
                # There is no numerical comparison to publish. In particular,
                # never expand original chunks or all player references here.
                return {**summary, "status": reason, "decision_at": decision}
            binding_envelope, original, _ = _load_publication(connection, binding_ref, latest=decision)
            binding = binding_envelope["payload"]
            if binding["native_event"]["scheduled_start"] <= decision:
                raise ReplayUnavailable("context_decision_not_prematch")
            base = joint_base(original, binding, decision_at=decision_at)
            rows = _bounded_receipts(connection, original.to_dict(), cutoff=decision)
            _native_binding(binding, original, rows)
            features = joint_features(binding["native_event"], rows, base, cutoff=decision_at)
            fits = tuple((ref, envelope) for ref, envelope in fits
                         if event_in_population(binding["native_event"], envelope["payload"]["population"]))
            effect_hash, effect = fits[0] if len(fits) == 1 else (None, None)
            reason = "effect-unavailable" if not fits else "effect-ambiguous" if len(fits) != 1 else reason
    except ReplayUnavailable as exc:
        return {"status": "source-unavailable", "binding_ref": binding_ref, "reason": str(exc),
                "role": "not_applied", "reference": None}
    summary = {"binding_ref": binding_ref, "event_key": binding["native_event"]["event_key"],
        "role": "not_applied", "reference": None,
        "available_features": sum(state == "available" for state in features["states"].values()),
        "missing_features": sum(state != "available" for state in features["states"].values())}
    if effect is None:
        return {**summary, "status": reason, "decision_at": decision}
    consumed = effect["payload"]["feature_names"]
    if any(features["states"].get(name) != "available" or not features["refs"].get(name) for name in consumed):
        return {**summary, "status": "effect-features-unavailable", "decision_at": decision}
    refs = sorted(row["digest"] for row in rows)
    revision = {"schema": 1, "kind": POINTER_KIND, "binding_ref": binding_ref,
                "observation_refs": refs, "manifest_ref": manifest, "effect_ref": effect_hash}
    revision_key = digest(revision)
    pointer = {**revision, "decision_at": decision}
    pointer_bytes = len(canonical_bytes(pointer))
    if pointer_bytes >= max_payload_bytes:
        return {**summary, "status": "payload-budget-exhausted", "decision_at": decision}
    with _reader(Path(path)) as connection:
        frozen = _stored_pointer(connection, revision_key)
    precomputed = None
    if frozen is None:
        inputs = {"event": binding["native_event"], "base": base, "features": features,
                  "observation_refs": refs, "preprocessing_refs": [],
                  "effect_artifact": effect, "effect_hash": effect_hash, "approval": None}
        precomputed = calculate_context_payload(**inputs)
        required_bytes = len(canonical_bytes(precomputed)) + pointer_bytes
        if required_bytes > max_payload_bytes:
            return {**summary, "status": "payload-budget-exhausted", "decision_at": decision,
                    "required_payload_bytes": required_bytes}
        # Size and numerical validity are established BEFORE the first write.
        frozen = compute_once(Path(path), revision_key, lambda: pointer)
    if ({key: frozen.get(key) for key in revision} != revision or set(frozen) != set(pointer)
            or canonical_timestamp(frozen["decision_at"]) != frozen["decision_at"]
            or not binding["decision_at"] <= frozen["decision_at"] <= decision):
        raise ContextIntegrityError("joint worker revision pointer differs from resolved inputs")
    actual_decision = datetime.fromisoformat(frozen["decision_at"])
    # First publication already bound these exact receipts. Later reuse cannot
    # pretend that any newly received source was available at that old decision.
    if any(row["observed_at"] > frozen["decision_at"] for row in rows):
        raise ContextIntegrityError("joint revision contains a receipt after its frozen decision")
    with _reader(Path(path)) as connection:
        if (_artifact_created_at(connection, effect_hash) > frozen["decision_at"]
                or canonical_timestamp(connection.execute("SELECT published_at FROM manifests WHERE digest=?",
                                        (manifest,)).fetchone()[0]) > frozen["decision_at"]):
            raise ContextIntegrityError("joint revision precedes its physical model publication")
    base = joint_base(original, binding, decision_at=actual_decision)
    features = joint_features(binding["native_event"], rows, base, cutoff=actual_decision)
    inputs = {"event": binding["native_event"], "base": base, "features": features,
              "observation_refs": refs, "preprocessing_refs": [],
              "effect_artifact": effect, "effect_hash": effect_hash, "approval": None}
    key = context_payload_key({"schema": 1, "kind": KIND, **inputs, "approval_hash": None})
    required_bytes = None
    def calculate():
        nonlocal required_bytes
        payload = (precomputed if precomputed is not None and frozen["decision_at"] == decision
                   else calculate_context_payload(**inputs))
        required_bytes = len(canonical_bytes(payload)) + pointer_bytes
        if required_bytes > max_payload_bytes:
            raise StorageBudgetExceeded("joint comparison exceeds its finite payload budget")
        return payload
    try:
        payload = compute_once(Path(path), key, calculate)
    except StorageBudgetExceeded:
        return {**summary, "status": "payload-budget-exhausted", "decision_at": frozen["decision_at"],
                "required_payload_bytes": required_bytes}
    expected = {"schema": 1, "kind": KIND, **inputs, "approval_hash": None}
    if canonical_bytes({name: payload.get(name) for name in expected}) != canonical_bytes(expected):
        raise ContextIntegrityError("stored joint comparison differs from resolved original inputs")
    if payload["result"]["role"] == "applied":
        raise ContextIntegrityError("experimental worker cannot activate a context effect")
    return deepcopy({**summary, "status": "comparison-stored", "decision_at": frozen["decision_at"],
        "role": payload["result"]["role"], "reference": context_consumer_reference(key, payload),
        "comparison_delta_pp": {market: 100 * (p - base["markets"][market])
            for market, p in (payload["result"]["comparison_markets"] or base["markets"]).items()}})


def publish_joint_capture_report(path, capture_report, *, decision_at,
                                 max_events=MAX_RUN_EVENTS, max_run_bytes=MAX_RUN_BYTES):
    """One bounded post-capture batch; no persistence without a fitted effect."""
    if not isinstance(decision_at, datetime) or decision_at.utcoffset() is None:
        raise ContextContractError("joint worker needs its actual aware decision clock")
    if type(max_events) is not int or not 0 <= max_events <= MAX_RUN_EVENTS:
        raise ContextContractError("joint worker event count is not bounded")
    if type(max_run_bytes) is not int or not 0 <= max_run_bytes <= MAX_RUN_BYTES:
        raise ContextContractError("joint worker total payload budget is not bounded")
    from context_models.football_original_publication import original_capture_report_fields
    checked = original_capture_report_fields({"football_original_capture": capture_report})["football_original_capture"]
    events = [row for row in checked["events"] if row["status"] == "captured"]
    result, remaining = [], max_run_bytes
    for row in events[:max_events]:
        allowance = min(MAX_EVENT_BYTES, remaining)
        if allowance <= 0:
            break
        event = publish_joint_comparison(path, row["binding_ref"], decision_at=decision_at,
                                         max_payload_bytes=allowance)
        result.append(event)
        # Reserve the maximum even after a crash/partial publication. No
        # refund needed for absent effects/features, which perform zero writes.
        if event["status"] in {"comparison-stored", "payload-budget-exhausted"}:
            remaining -= allowance
    return {"schema": 1, "scope": "football-post-capture-internal-joint-comparison",
            "events": result, "unprocessed_events": len(events) - len(result),
            "reserved_payload_bytes": max_run_bytes - remaining}


def joint_comparison_report_fields(snapshot):
    """Closed bounded administration report; not a customer/effect claim."""
    if "football_joint_comparison" not in snapshot:
        return {}
    report = require_object(snapshot["football_joint_comparison"],
        {"schema", "scope", "events", "unprocessed_events", "reserved_payload_bytes"},
        label="football joint worker report")
    if (type(report["schema"]) is not int or report["schema"] != 1
            or report["scope"] != "football-post-capture-internal-joint-comparison"
            or type(report["events"]) is not list or len(report["events"]) > MAX_RUN_EVENTS):
        raise ContextContractError("invalid joint worker report version or event bound")
    from challenge_15k import MAX_SCAN_FIXTURES
    for name, limit in (("unprocessed_events", MAX_SCAN_FIXTURES), ("reserved_payload_bytes", MAX_RUN_BYTES)):
        if type(report[name]) is not int or not 0 <= report[name] <= limit:
            raise ContextContractError("joint worker report counter is not bounded")
    statuses = {"source-unavailable", "effect-unavailable", "effect-after-decision", "effect-ambiguous",
                "effect-features-unavailable", "payload-budget-exhausted", "comparison-stored"}
    for row in report["events"]:
        require_object(row, {"binding_ref", "status", "role", "reference"},
            optional={"event_key", "decision_at", "available_features", "missing_features",
                      "comparison_delta_pp", "required_payload_bytes", "reason"}, label="joint worker event")
        require_digest(row["binding_ref"], "joint worker original binding")
        if row["status"] not in statuses or row["role"] not in {"not_applied", "experimental"}:
            raise ContextContractError("joint worker report cannot claim applied effects")
        if "event_key" in row:
            import re
            if type(row["event_key"]) is not str or re.fullmatch(r"api-football:football:[1-9][0-9]*", row["event_key"]) is None:
                raise ContextContractError("joint worker report has no native event")
        if "decision_at" in row and canonical_timestamp(row["decision_at"]) != row["decision_at"]:
            raise ContextContractError("joint worker report has a noncanonical decision")
        for field in ("available_features", "missing_features", "required_payload_bytes"):
            if field in row and (type(row[field]) is not int or not 0 <= row[field] <= 32 * 1024 * 1024):
                raise ContextContractError("joint worker detail counter is not bounded")
        if "reason" in row:
            require_text(row["reason"], "joint source-unavailability reason")
            if len(row["reason"]) > 256:
                raise ContextContractError("joint source-unavailability reason is too long")
        stored = row["status"] == "comparison-stored"
        if stored != (row["reference"] is not None) or row["role"] == "experimental" and not stored:
            raise ContextContractError("joint worker stored/reference status differs")
        if stored:
            from context_consumers import validate_context_reference
            validate_context_reference(row["reference"])
        if "comparison_delta_pp" in row:
            import challenge_engine as engine
            require_object(row["comparison_delta_pp"], {spec.key for spec in engine.GOAL_MARKET_SPECS}, label="joint internal deltas")
            if not stored:
                raise ContextContractError("unstored worker cannot claim numerical comparison deltas")
            for number in row["comparison_delta_pp"].values():
                require_number(number, "internal joint probability-point delta", minimum=-100, maximum=100)
    return {"football_joint_comparison": deepcopy(report)}
