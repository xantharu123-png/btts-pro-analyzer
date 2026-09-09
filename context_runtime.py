"""Read-only A1/B1/B3 storage verification, never empirical certification.

Unknown artifact schemas and opaque legacy snapshots retain their bytes and
report transport_only. D2 report resolution and D3 complete snapshot envelopes
do not exist yet; public hashes cannot substitute for those evidence contracts.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import re
import sqlite3

from context_models.contracts import (
    digest, require_digest, require_object, validate_context_approval,
    validate_context_result, validate_effect_artifact,
)
from context_observations import _SELECT, _decode_receipt
from context_snapshots import _decode_snapshot
from model_artifacts import (
    ArtifactIntegrityError, _decode_object, _load_artifact,
    _validate_stored_timestamp, canonical_bytes,
)
from runtime_paths import (
    RuntimeArtifactTrustError, _assert_no_symlink_components,
    _validate_trusted_runtime_ancestor_chain, _validate_trusted_runtime_database_stat,
)


ROLLBACK_REASON = "operator-requested-model-rollback"
ROLLBACK_SQL = """CREATE TABLE context_model_rollbacks (
    digest TEXT PRIMARY KEY,
    payload BLOB NOT NULL
)"""

_SCHEMA = {
    "artifacts": """CREATE TABLE artifacts(
        digest TEXT PRIMARY KEY, kind TEXT NOT NULL,
        payload BLOB NOT NULL, created_at TEXT NOT NULL)""",
    "manifests": """CREATE TABLE manifests(
        digest TEXT PRIMARY KEY, predecessor TEXT,
        payload BLOB NOT NULL, published_at TEXT NOT NULL)""",
    "active_manifest": """CREATE TABLE active_manifest(
        id INTEGER PRIMARY KEY CHECK(id=1),
        digest TEXT NOT NULL REFERENCES manifests(digest))""",
    "context_contents": """CREATE TABLE context_contents (
        content_digest TEXT PRIMARY KEY, payload BLOB NOT NULL)""",
    "context_observations": """CREATE TABLE context_observations (
        digest TEXT PRIMARY KEY,
        content_digest TEXT NOT NULL REFERENCES context_contents(content_digest),
        event_key TEXT NOT NULL, observed_at TEXT NOT NULL,
        schedule_revision TEXT NOT NULL, source TEXT NOT NULL,
        subject_id TEXT NOT NULL, kind TEXT NOT NULL)""",
    "context_snapshots": """CREATE TABLE context_snapshots (
        key TEXT PRIMARY KEY NOT NULL, payload BLOB NOT NULL,
        payload_digest TEXT NOT NULL)""",
    "context_model_rollbacks": ROLLBACK_SQL,
    "context_event_receipts": """CREATE INDEX context_event_receipts
        ON context_observations(event_key,schedule_revision,observed_at)""",
}
_CORE = {"artifacts", "manifests", "active_manifest"}
_OBSERVATIONS = {"context_contents", "context_observations", "context_event_receipts"}


def _sql_identity(sql):
    if type(sql) is not str:
        raise ArtifactIntegrityError("context schema SQL must be text")
    return re.sub(r"\s+", "", sql).casefold().replace("ifnotexists", "")


def _trusted_existing_file(path):
    path = _assert_no_symlink_components(Path(path))
    _validate_trusted_runtime_ancestor_chain(path.parent)
    info = os.lstat(path)  # Never create a missing path or database.
    _validate_trusted_runtime_database_stat(path, info)
    if info.st_nlink != 1:
        raise RuntimeArtifactTrustError("context database must have one file identity")
    return path, (info.st_dev, info.st_ino)


@contextmanager
def _open_database(path, *, writable=False):
    path, identity = _trusted_existing_file(path)
    for suffix in ("-wal", "-shm", "-journal"):
        companion = path.with_name(path.name + suffix)
        if os.path.lexists(companion):
            _trusted_existing_file(companion)
    if not writable:
        # Opening an unsealed WAL database can create/write an SHM sidecar;
        # immutable=1 would instead IGNORE its WAL. Neither is a read-only full
        # verification. Use the existing online stager to produce DELETE mode.
        with path.open("rb") as handle:
            header = handle.read(20)
        if len(header) >= 20 and (header[18] == 2 or header[19] == 2):
            raise RuntimeArtifactTrustError("WAL context verification requires an online sealed stage")
        journal = path.with_name(path.name + "-journal")
        if journal.exists() and journal.stat().st_size:
            raise RuntimeArtifactTrustError("pending context journal requires an online sealed stage")
    mode = "rw" if writable else "ro"
    connection = sqlite3.connect(path.as_uri() + f"?mode={mode}", uri=True, timeout=5)
    try:
        if _trusted_existing_file(path)[1] != identity:
            raise RuntimeArtifactTrustError("context database changed file identity while opening")
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        if not writable:
            connection.execute("PRAGMA query_only=ON")
        yield connection
        if _trusted_existing_file(path)[1] != identity:
            raise RuntimeArtifactTrustError("context database changed file identity during verification")
    finally:
        connection.close()


def _verify_schema(connection):
    seen = set()
    for kind, name, table, sql in connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master"):
        if sql is None and kind == "index" and table in _SCHEMA and table != "active_manifest":
            if name != f"sqlite_autoindex_{table}_1":
                raise ArtifactIntegrityError("unexpected context automatic index")
            continue
        if name not in _SCHEMA or _sql_identity(sql) != _sql_identity(_SCHEMA[name]):
            raise ArtifactIntegrityError("unknown or modified context database schema")
        expected_kind = "index" if name == "context_event_receipts" else "table"
        expected_table = "context_observations" if expected_kind == "index" else name
        if kind != expected_kind or table != expected_table or name in seen:
            raise ArtifactIntegrityError("inconsistent context schema object")
        seen.add(name)
    if not _CORE <= seen or (seen & _OBSERVATIONS and not _OBSERVATIONS <= seen):
        raise ArtifactIntegrityError("incomplete context database schema")
    if connection.execute("PRAGMA user_version").fetchone() != (0,) or connection.execute("PRAGMA application_id").fetchone() != (0,):
        raise ArtifactIntegrityError("unknown context database schema version")
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ArtifactIntegrityError("context SQLite integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise ArtifactIntegrityError("context SQLite reference check failed")
    return seen


def _manifest_rows(connection, artifacts, created_at):
    manifests = {}
    for key, predecessor, raw, published in connection.execute("SELECT digest,predecessor,payload,published_at FROM manifests"):
        require_digest(key, "manifest identity")
        if predecessor is not None:
            require_digest(predecessor, "manifest predecessor")
        slots = _decode_object(raw, label="manifest payload")
        _validate_stored_timestamp(published, label="manifest publication time")
        for slot, ref in slots.items():
            if type(slot) is not str:
                raise ArtifactIntegrityError("manifest slot is not text")
            require_digest(ref, "manifest artifact reference")
            if ref not in artifacts:
                raise ArtifactIntegrityError("manifest references a missing artifact")
            if created_at[ref] > datetime.fromisoformat(published):
                raise ArtifactIntegrityError("manifest predates its artifact creation")
        row = {"predecessor": predecessor, "slots": slots, "published_at": published}
        if digest(row) != key or key in manifests:
            raise ArtifactIntegrityError("manifest identity mismatch")
        manifests[key] = row
    active = connection.execute("SELECT id,digest FROM active_manifest").fetchall()
    if len(active) > 1 or active and (type(active[0][0]) is not int or active[0][0] != 1):
        raise ArtifactIntegrityError("invalid active context manifest row")
    current = active[0][1] if active else None
    if current is not None:
        require_digest(current, "active manifest identity")
    chain, cursor = [], current
    while cursor is not None:
        if cursor in chain or cursor not in manifests:
            raise ArtifactIntegrityError("broken context manifest predecessor chain")
        chain.append(cursor)
        predecessor = manifests[cursor]["predecessor"]
        if predecessor in manifests and datetime.fromisoformat(manifests[cursor]["published_at"]) < datetime.fromisoformat(manifests[predecessor]["published_at"]):
            raise ArtifactIntegrityError("manifest publication precedes its predecessor")
        cursor = predecessor
    if set(chain) != set(manifests):
        raise ArtifactIntegrityError("context manifests are not one complete active history")
    return manifests, current, chain


def _resolve(artifacts, key, *, kind=None):
    require_digest(key, "referenced artifact")
    if key not in artifacts:
        raise ArtifactIntegrityError("missing context artifact reference")
    artifact = artifacts[key]
    if kind is not None and artifact["kind"] != kind:
        raise ArtifactIntegrityError("context reference has the wrong artifact kind")
    return artifact["payload"]


def _verify_artifact_types(artifacts, created_at, limitations):
    # These are owning structural validators, not test-only fit approvals.
    from tennis.tour_state import _check_predictions, _decode_wrapper

    for key, envelope in artifacts.items():
        kind, payload = envelope["kind"], envelope["payload"]
        if kind == "tennis-tour-state":
            if type(payload.get("state")) is not dict:
                raise ArtifactIntegrityError("missing typed tour state")
            tour = payload["state"].get("tour")
            if tour not in ("ATP", "WTA"):
                raise ArtifactIntegrityError("legacy or unknown tour schema")
            _check_predictions(_decode_wrapper(payload, tour, decision_cutoff=created_at[key].timestamp()))
        elif kind == "context-effect-v1":
            validated = validate_effect_artifact(payload)
            if canonical_bytes(validated) != canonical_bytes(payload):
                raise ArtifactIntegrityError("noncanonical context effect payload")
            if datetime.fromisoformat(payload["training_end"]) > created_at[key]:
                raise ArtifactIntegrityError("effect was created before its training ended")
            for key in payload["preprocessing_artifacts"].values():
                _resolve(artifacts, key)
        elif kind == "context-approval-v1":
            validated = validate_context_approval(payload)
            if canonical_bytes(validated) != canonical_bytes(payload):
                raise ArtifactIntegrityError("noncanonical context approval payload")
            if datetime.fromisoformat(payload["evaluated_at"]) > created_at[key]:
                raise ArtifactIntegrityError("approval was created before its evaluation")
            effect = _resolve(artifacts, payload["effect_hash"], kind="context-effect-v1")
            for name in ("sport", "family", "feature_version", "population", "coverage", "model_variant"):
                if payload[name] != effect[name]:
                    raise ArtifactIntegrityError("approval and effect scope mismatch")
            if payload["evaluated_at"] < effect["training_end"]:
                raise ArtifactIntegrityError("approval predates its model training")
            _resolve(artifacts, payload["report_hash"], kind="context-evaluation-v1")
            _resolve(artifacts, payload["experiment_hash"], kind="context-experiment-v1")
            limitations.add("d2-approval-evidence-resolution-unavailable")
        elif kind in {"context-evaluation-v1", "context-experiment-v1"}:
            limitations.add("d2-report-experiment-schema-unavailable")
        else:
            limitations.add("unrecognized-artifact-schema")


def _verify_slots(slots, artifacts):
    effect_refs = {ref for ref in slots.values() if artifacts[ref]["kind"] == "context-effect-v1"}
    for slot, ref in slots.items():
        envelope = artifacts[ref]
        if slot in {"tennis:ATP", "tennis:WTA"}:
            if envelope["kind"] != "tennis-tour-state" or envelope["payload"]["state"]["tour"] != slot.split(":")[1]:
                raise ArtifactIntegrityError("tour slot points to a different typed population")
        if slot.startswith("context-approval:"):
            effect = slot.removeprefix("context-approval:")
            require_digest(effect, "approval slot effect identity")
            if envelope["kind"] != "context-approval-v1" or envelope["payload"]["effect_hash"] != effect:
                raise ArtifactIntegrityError("approval slot does not bind its exact effect")
        if envelope["kind"] == "context-approval-v1":
            effect = envelope["payload"]["effect_hash"]
            if slot != f"context-approval:{effect}" or effect not in effect_refs:
                raise ArtifactIntegrityError("approval has no coupled effect in the same manifest")


def _verify_observations(connection, tables):
    if "context_observations" not in tables:
        return {}, 0
    contents = {}
    for key, raw in connection.execute("SELECT content_digest,payload FROM context_contents"):
        require_digest(key, "observation content identity")
        content = _decode_object(raw, label="observation content")
        if digest(content) != key or key in contents:
            raise ArtifactIntegrityError("observation content hash mismatch")
        contents[key] = content
    receipts = {}
    for row in connection.execute(_SELECT):
        decoded = _decode_receipt(row)
        if decoded["digest"] in receipts:
            raise ArtifactIntegrityError("duplicate observation receipt")
        receipts[decoded["digest"]] = decoded
    if {row["content_digest"] for row in receipts.values()} != set(contents):
        raise ArtifactIntegrityError("observation content has no validated receipt")
    return receipts, len(contents)


def _verify_snapshots(connection, tables, artifacts, receipts, limitations):
    if "context_snapshots" not in tables:
        return 0
    count = 0
    for key, raw, payload_hash in connection.execute("SELECT key,payload,payload_digest FROM context_snapshots"):
        require_digest(key, "snapshot key")
        payload = _decode_snapshot(key, raw, payload_hash)
        count += 1
        limitations.add("d3-snapshot-input-binding-unavailable")
        # Recognizable B3 ContextResult has additional typed references. Its
        # missing original Event/Base/FeatureVector still prevents key replay.
        if {"event_key", "base_hash", "effect_hash", "base_params", "factor_roles", "feature_refs"} <= set(payload):
            effect = None if payload["effect_hash"] is None else _resolve(artifacts, payload["effect_hash"], kind="context-effect-v1")
            families = {frozenset({"p_a"}): "tennis:winner",
                        frozenset({"hold_a", "hold_b", "best_of"}): "tennis:serve",
                        frozenset({"home_lambda", "away_lambda"}): "football:goals:90min"}
            if type(payload["base_params"]) is not dict or frozenset(payload["base_params"]) not in families:
                raise ArtifactIntegrityError("unknown stored context result parameter schema")
            validate_context_result(payload, family=families[frozenset(payload["base_params"])], effect_artifact=effect)
            for refs in payload["feature_refs"].values():
                if not set(refs) <= set(receipts):
                    raise ArtifactIntegrityError("snapshot references missing observation receipts")
            if payload.get("approval_hash") is not None:
                approval = _resolve(artifacts, payload["approval_hash"], kind="context-approval-v1")
                if approval["effect_hash"] != payload["effect_hash"] or payload["certified_markets"] != approval["target_markets"]:
                    raise ArtifactIntegrityError("snapshot and approval references contradict")
    return count


def _verify_rollbacks(connection, tables, manifests, chain):
    if "context_model_rollbacks" not in tables:
        return 0
    count, seen = 0, set()
    for key, raw in connection.execute("SELECT digest,payload FROM context_model_rollbacks"):
        require_digest(key, "rollback identity")
        payload = _decode_object(raw, label="model rollback audit")
        require_object(payload, {"schema", "expected_manifest", "target_manifest", "new_manifest", "reason", "published_at"}, label="model rollback")
        if type(payload["schema"]) is not int or payload["schema"] != 1 or payload["reason"] != ROLLBACK_REASON or digest(payload) != key:
            raise ArtifactIntegrityError("invalid model rollback audit identity")
        expected, target, new = (payload[name] for name in ("expected_manifest", "target_manifest", "new_manifest"))
        for ref in (expected, target, new):
            require_digest(ref, "rollback manifest")
            if ref not in manifests:
                raise ArtifactIntegrityError("rollback audit references a missing manifest")
        _validate_stored_timestamp(payload["published_at"], label="rollback time")
        if (new in seen or chain.index(target) <= chain.index(expected)
                or manifests[new]["predecessor"] != expected
                or manifests[new]["slots"] != manifests[target]["slots"]
                or manifests[new]["published_at"] != payload["published_at"]
                or datetime.fromisoformat(payload["published_at"]) < datetime.fromisoformat(manifests[expected]["published_at"])):
            raise ArtifactIntegrityError("model rollback audit contradicts manifest history")
        seen.add(new)
        count += 1
    return count


def _verify_connection(connection):
    """Inspect one caller-held SQLite transaction without any schema writes."""
    tables = _verify_schema(connection)
    artifacts, created_at = {}, {}
    for key, created in connection.execute("SELECT digest,created_at FROM artifacts"):
        require_digest(key, "artifact identity")
        if key in artifacts:
            raise ArtifactIntegrityError("duplicate artifact identity")
        artifacts[key] = _load_artifact(connection, key)
        created_at[key] = datetime.fromisoformat(_validate_stored_timestamp(created, label="artifact creation time"))
    limitations = set()
    _verify_artifact_types(artifacts, created_at, limitations)
    manifests, current, chain = _manifest_rows(connection, artifacts, created_at)
    for manifest in manifests.values():
        _verify_slots(manifest["slots"], artifacts)
    receipts, content_count = _verify_observations(connection, tables)
    snapshot_count = _verify_snapshots(connection, tables, artifacts, receipts, limitations)
    rollback_count = _verify_rollbacks(connection, tables, manifests, chain)
    slots = manifests[current]["slots"] if current is not None else {}
    report = {"schema": 1, "verification_level": "transport_only" if limitations else "structural",
              "empirical_approval_verified": False, "limitations": sorted(limitations),
              "counts": {"artifacts": len(artifacts), "manifests": len(manifests),
                         "contents": content_count, "observations": len(receipts),
                         "snapshots": snapshot_count, "rollbacks": rollback_count},
              "active_manifest": current, "active_slots": dict(slots),
              "tour_states": {tour: slots[f"tennis:{tour}"] for tour in ("ATP", "WTA") if f"tennis:{tour}" in slots}}
    return {"report": report, "manifests": manifests, "chain": chain, "artifacts": artifacts, "tables": tables}


def verify_context_database(path: Path) -> dict:
    """Verify an existing sealed DB read-only; unsupported evidence is explicit.

    For a live WAL/journal use stage_databases first. This function never
    creates directories, opens immutable=1 over a live WAL, or repairs a DB.
    Structural means current known storage schemas/links, NOT approved bets.
    """
    with _open_database(path) as connection:
        connection.execute("BEGIN")
        try:
            report = _verify_connection(connection)["report"]
            connection.rollback()
            return report
        except (ValueError, TypeError, KeyError, sqlite3.Error, ArithmeticError, RecursionError) as exc:
            connection.rollback()
            raise ArtifactIntegrityError("context database verification failed") from exc


def verify_context_backup_location(path: Path, *, application_root: Path) -> str:
    """Check an explicitly configured DB is inside existing discovery scope.

    No implicit production root/mapping and no broader secret read permission.
    Deployment must supply the actual configured path, not just its default.
    """
    from scripts.stage_runtime_databases import DATABASE_SUFFIXES, EXCLUDED_PARTS, _validated_directory

    root = _validated_directory(application_root, "Context backup application root")
    actual, _ = _trusted_existing_file(path)
    try:
        relative = actual.relative_to(root)
    except ValueError as exc:
        raise RuntimeArtifactTrustError("configured context database is outside the backup root") from exc
    if any(part in EXCLUDED_PARTS for part in relative.parts[:-1]) or actual.suffix.casefold() not in DATABASE_SUFFIXES:
        raise RuntimeArtifactTrustError("configured context database is outside backup discovery")
    return relative.as_posix()
