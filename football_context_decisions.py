"""Freeze the actual post-capture decision even before an effect is fitted.

An ORIGINAL is captured before injuries/weather are fetched. A later genuine
worker decision is therefore a separate immutable record, not a retrospectively
chosen training cutoff. No probability, source fetch or approval is produced.
"""
from datetime import datetime, timezone
from pathlib import Path
from copy import deepcopy

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    require_digest, require_object,
)
from context_models.dataset import _reader
from context_models.football_training import _load_publication
from context_models.replay import ReplayUnavailable
from football_joint_worker import _bounded_receipts, _native_binding
from contextlib import closing
from model_artifacts import canonical_bytes, _connect, _insert_artifact, prepare_artifact

DECISION_KIND = "football-native-context-decision-v1"
MAX_DECISION_EVENTS = 32
MAX_DECISION_BYTES = 1024


def _now():
    return datetime.now(timezone.utc)


def validate_decision(payload):
    require_object(payload, {"schema", "binding_ref", "event_key", "decision_at",
        "observation_refs_hash", "observation_count"}, label="football native context decision")
    if type(payload["schema"]) is not int or payload["schema"] != 1:
        raise ContextContractError("unsupported football context decision")
    for name in ("binding_ref", "observation_refs_hash"):
        require_digest(payload[name], name)
    prefix = "api-football:football:"
    key = payload["event_key"]
    if (type(key) is not str or not key.startswith(prefix)
            or not key[len(prefix):].isascii() or not key[len(prefix):].isdecimal()
            or str(int(key[len(prefix):])) != key[len(prefix):] or int(key[len(prefix):]) <= 0):
        raise ContextContractError("decision requires an exact native event key")
    if (type(payload["decision_at"]) is not str
            or canonical_timestamp(payload["decision_at"]) != payload["decision_at"]):
        raise ContextContractError("decision requires a canonical actual clock")
    if type(payload["observation_count"]) is not int or not 1 <= payload["observation_count"] <= 4096:
        raise ContextContractError("decision source count is unbounded")
    if len(canonical_bytes(payload)) > MAX_DECISION_BYTES:
        raise ContextContractError("decision payload is unbounded")
    return dict(payload)


def resolve_decision(connection, decision_ref, *, latest):
    """Verify existing source/physical-clock ownership, never choose a cutoff."""
    from context_models.dataset import _artifact
    from context_models.experiments import _artifact_created_at
    envelope = _artifact(connection, decision_ref, DECISION_KIND, latest=latest)
    payload = validate_decision(envelope["payload"])
    binding, original, _ = _load_publication(connection, payload["binding_ref"], latest=latest)
    event = binding["payload"]["native_event"]
    created = _artifact_created_at(connection, decision_ref)
    if _artifact_created_at(connection, payload["binding_ref"]) > payload["decision_at"]:
        raise ContextIntegrityError("context decision precedes physical original publication")
    if (payload["event_key"] != event["event_key"]
            or not binding["payload"]["decision_at"] <= payload["decision_at"] <= created < event["scheduled_start"]):
        raise ContextIntegrityError("decision is not a genuine prematch publication of this original")
    rows = _bounded_receipts(connection, original.to_dict(), cutoff=payload["decision_at"])
    _native_binding(binding["payload"], original, rows)
    refs = sorted(row["digest"] for row in rows)
    if len(refs) != payload["observation_count"] or digest(refs) != payload["observation_refs_hash"]:
        raise ContextIntegrityError("decision source revision differs from its frozen prematch inventory")
    return envelope


def _previous(connection, payload):
    previous = connection.execute("SELECT digest FROM artifacts WHERE kind=? "
        "AND json_extract(CAST(payload AS TEXT),'$.binding_ref')=? "
        "AND json_extract(CAST(payload AS TEXT),'$.observation_refs_hash')=? "
        "ORDER BY created_at,digest LIMIT 2", (DECISION_KIND, payload["binding_ref"], payload["observation_refs_hash"])).fetchall()
    if len(previous) > 1:
        raise ContextIntegrityError("duplicate first context decision for one source revision")
    return None if not previous else previous[0][0]


def _publish(path, payload, event, *, remaining):
    """A simultaneous worker cannot publish two first clocks for one revision."""
    with closing(_connect(Path(path))) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            read_at = canonical_timestamp(_now())
            binding, _, _ = _load_publication(connection, payload["binding_ref"], latest=read_at)
            if binding["payload"]["native_event"]["scheduled_start"] != event["scheduled_start"]:
                raise ContextIntegrityError("deferred decision kickoff differs from its physical original")
            existing = _previous(connection, payload)
            if existing is not None:
                resolve_decision(connection, existing, latest=read_at)
                connection.rollback()
                return existing, "reused", 0
            prepared = prepare_artifact(kind=DECISION_KIND, payload=payload)
            if len(prepared.payload_bytes) > remaining:
                connection.rollback()
                return None, "budget-exhausted", 0
            # Native owner/source validation may be expensive. It cannot make
            # an old loop-start timestamp stand in for this physical insert.
            created = canonical_timestamp(_now())
            if not payload["decision_at"] <= created < event["scheduled_start"]:
                raise ReplayUnavailable("decision_publication_missed_prematch")
            _insert_artifact(connection, prepared, created)
            ref = prepared.digest
            # Complete readback rechecks source clocks and hashes in this writer
            # image. A changed predecision source pool rolls back the insert.
            resolve_decision(connection, ref, latest=created)
            finished = canonical_timestamp(_now())
            if finished < created:
                raise ContextIntegrityError("decision writer clock moved before its actual insert")
            if finished >= event["scheduled_start"]:
                raise ReplayUnavailable("decision_readback_missed_prematch")
            connection.commit()
            return ref, "captured", len(prepared.payload_bytes)
        except BaseException:
            connection.rollback()
            raise


def prepare_capture_decisions(path, capture_report, *, decision_at, max_events=MAX_DECISION_EVENTS):
    """Freeze compact source revisions now; do not consume ORIGINAL bytes."""
    from context_models.football_original_publication import original_capture_report_fields
    if not isinstance(decision_at, datetime) or decision_at.utcoffset() is None:
        raise ContextContractError("post-capture decisions need an aware actual worker clock")
    if type(max_events) is not int or not 0 <= max_events <= MAX_DECISION_EVENTS:
        raise ContextContractError("post-capture decision count must be bounded")
    clock = canonical_timestamp(decision_at)
    checked = original_capture_report_fields({"football_original_capture": capture_report})["football_original_capture"]
    candidates = [row for row in checked["events"] if row["status"] == "captured"]
    events = []
    for row in candidates[:max_events]:
        try:
            with _reader(Path(path)) as connection:
                binding, original, _ = _load_publication(connection, row["binding_ref"], latest=clock)
                event = binding["payload"]["native_event"]
                if not binding["payload"]["decision_at"] <= clock < event["scheduled_start"]:
                    raise ReplayUnavailable("post_capture_decision_not_prematch")
                receipts = _bounded_receipts(connection, original.to_dict(), cutoff=clock)
                _native_binding(binding["payload"], original, receipts)
                refs = sorted(receipt["digest"] for receipt in receipts)
                payload = validate_decision({"schema": 1, "binding_ref": row["binding_ref"],
                    "event_key": event["event_key"], "decision_at": clock,
                    "observation_refs_hash": digest(refs), "observation_count": len(refs)})
            events.append({"binding_ref": row["binding_ref"], "payload": payload,
                           "scheduled_start": event["scheduled_start"]})
        except ReplayUnavailable as exc:
            events.append({"binding_ref": row["binding_ref"], "payload": None,
                           "scheduled_start": None, "reason": str(exc)})
    return {"events": events, "unprocessed_events": len(candidates)-len(events)}


def publish_deferred_decisions(path, prepared, *, max_run_bytes, on_commit=None):
    """Publish only after all ORIGINAL batches, with the actual new clock.

    A callback accounts each committed row immediately, even if a later row
    fails integrity. No source bodies or mutable worker snapshots are retained.
    """
    require_object(prepared, {"events", "unprocessed_events"}, label="deferred decisions")
    if type(prepared["events"]) is not list or len(prepared["events"]) > MAX_DECISION_EVENTS:
        raise ContextContractError("deferred decision inventory must be bounded")
    from challenge_15k import MAX_SCAN_FIXTURES
    if type(prepared["unprocessed_events"]) is not int or not 0 <= prepared["unprocessed_events"] <= MAX_SCAN_FIXTURES:
        raise ContextContractError("deferred decision remainder must be bounded")
    if type(max_run_bytes) is not int or not 0 <= max_run_bytes <= MAX_DECISION_EVENTS*MAX_DECISION_BYTES:
        raise ContextContractError("post-capture decision bytes must be bounded")
    if on_commit is not None and not callable(on_commit):
        raise ContextContractError("decision accounting callback must be callable")
    events, inserted, seen = [], 0, set()
    for row in prepared["events"]:
        require_object(row, {"binding_ref", "payload", "scheduled_start"}, optional={"reason"}, label="deferred decision")
        require_digest(row["binding_ref"], "deferred original binding")
        if row["binding_ref"] in seen:
            raise ContextContractError("duplicate deferred original binding")
        seen.add(row["binding_ref"])
        if row["payload"] is None:
            if row["scheduled_start"] is not None or type(row.get("reason")) is not str:
                raise ContextContractError("unavailable deferred decision lacks its actual reason")
            events.append({"binding_ref": row["binding_ref"], "status": "unavailable",
                           "decision_ref": None, "reason": row["reason"]})
            continue
        payload = validate_decision(row["payload"])
        if payload["binding_ref"] != row["binding_ref"] or "reason" in row:
            raise ContextIntegrityError("deferred source proof differs from its original")
        start = canonical_timestamp(row["scheduled_start"])
        try:
            # _publish resolves the owning native event and source revision
            # inside its transaction, and rejects actual publication after start.
            ref, status, size = _publish(path, payload, {"scheduled_start": start}, remaining=max_run_bytes-inserted)
            inserted += size
            if size and on_commit is not None:
                on_commit(size)
            events.append({"binding_ref": row["binding_ref"], "status": status, "decision_ref": ref})
        except ReplayUnavailable as exc:
            events.append({"binding_ref": row["binding_ref"], "status": "unavailable",
                           "decision_ref": None, "reason": str(exc)})
    return {"schema": 1, "scope": "football-post-capture-decisions", "events": events,
        "unprocessed_events": prepared["unprocessed_events"], "inserted_payload_bytes": inserted}


def publish_capture_decisions(path, capture_report, *, decision_at, max_events=MAX_DECISION_EVENTS,
                              max_run_bytes=MAX_DECISION_EVENTS*MAX_DECISION_BYTES):
    """Standalone owning publication; ordinary workers defer until finalization."""
    return publish_deferred_decisions(path,
        prepare_capture_decisions(path, capture_report, decision_at=decision_at, max_events=max_events),
        max_run_bytes=max_run_bytes)


def decision_report_fields(snapshot):
    """Compact administration metadata only; no customer or effect claim."""
    if "football_context_decisions" not in snapshot:
        return {}
    if (type(snapshot["football_context_decisions"]) is dict
            and snapshot["football_context_decisions"].get("scope") == "football-postcapture-unresolved-header-inventory-v2"):
        from football_context_inventory import inventory_report_fields
        return inventory_report_fields(snapshot)
    report = require_object(snapshot["football_context_decisions"],
        {"schema", "scope", "events", "unprocessed_events", "inserted_payload_bytes"},
        label="football context decision report")
    if (type(report["schema"]) is not int or report["schema"] != 1
            or report["scope"] != "football-post-capture-decisions"
            or type(report["events"]) is not list or len(report["events"]) > MAX_DECISION_EVENTS):
        raise ContextContractError("invalid context decision report version or bound")
    from challenge_15k import MAX_SCAN_FIXTURES
    for name, limit in (("unprocessed_events", MAX_SCAN_FIXTURES),
                        ("inserted_payload_bytes", MAX_DECISION_EVENTS*MAX_DECISION_BYTES)):
        if type(report[name]) is not int or not 0 <= report[name] <= limit:
            raise ContextContractError("decision report counters must be bounded integers")
    seen = set()
    for row in report["events"]:
        require_object(row, {"binding_ref", "status", "decision_ref"}, optional={"reason"}, label="decision report event")
        require_digest(row["binding_ref"], "decision original binding")
        if row["binding_ref"] in seen:
            raise ContextContractError("duplicate original in context decision report")
        seen.add(row["binding_ref"])
        if row["status"] not in {"captured", "reused", "unavailable", "budget-exhausted"}:
            raise ContextContractError("unknown context decision status")
        if row["status"] in {"captured", "reused"}:
            require_digest(row["decision_ref"], "actual decision reference")
            if "reason" in row:
                raise ContextContractError("stored decisions cannot claim missing sources")
        elif row["decision_ref"] is not None:
            raise ContextContractError("unstored decisions cannot claim a reference")
        if "reason" in row and (row["status"] != "unavailable"
                or type(row["reason"]) is not str or not 1 <= len(row["reason"]) <= 256):
            raise ContextContractError("decision unavailability reason is invalid")
    if report["inserted_payload_bytes"] > sum(row["status"] == "captured" for row in report["events"])*MAX_DECISION_BYTES:
        raise ContextContractError("decision report claims bytes without a new decision")
    return {"football_context_decisions": deepcopy(report)}

