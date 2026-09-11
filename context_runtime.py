"""Read-only A1/B1/B3 and owning D2 evidence verification, never activation.

Unknown artifact schemas and opaque legacy snapshots retain their bytes and
report transport_only. Actual D2 reports replay their original sources/fits;
D3 transports still need their separate owning source/feature replay. Public
hashes cannot prove source truth or substitute for either evidence contract.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import sqlite3

from context_models.contracts import (
    canonical_timestamp, digest, require_digest, require_object, require_text,
    validate_context_approval, validate_context_result, validate_effect_artifact,
    validate_event, validate_feature_vector,
)
from context_observations import _SELECT, _decode_receipt
from context_snapshots import _decode_snapshot
from context_runtime_transaction import TrackedConnection
from model_artifacts import (
    ArtifactIntegrityError, _decode_object, _load_artifact,
    _validate_stored_timestamp, canonical_bytes,
)
from runtime_paths import (
    RuntimeArtifactTrustError, _assert_no_symlink_components,
    _validate_trusted_runtime_ancestor_chain, _validate_trusted_runtime_database_stat,
)


ROLLBACK_REASON = "operator-requested-model-rollback"
# Limit the input image, NOT total process RAM (SQLite/JSON need extra memory).
MAX_CONTEXT_IMAGE_BYTES = 64 * 1024 * 1024
MAX_SEALED_CONTEXT_BYTES = 1024 * 1024 * 1024
MAX_TENNIS_HISTORY_BYTES = 256 * 1024 * 1024
_IMAGE_CHUNK_BYTES = 1024 * 1024
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
# Only owning routes present/reviewed at this packet's exact base revision.
# New versions retain transport-only status until separately integrated.
_WORKER_REPLAY_CAPABILITIES = frozenset({
    ("football:goals:90min", "football-roster-components-v2"),
    ("tennis:winner", "tennis-performed-load-v2"),
    ("tennis:serve", "tennis-performed-load-v2"),
    ("basketball:margin:including_ot", "basketball-rotation-observed-load-v1"),
})


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


def _file_version(info):
    return (info.st_dev, info.st_ino, info.st_nlink, info.st_mode, info.st_uid, info.st_gid,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _require_no_companions(path):
    for suffix in ("-wal", "-shm", "-journal"):
        companion = path.with_name(path.name + suffix)
        if os.path.lexists(companion):
            _trusted_existing_file(companion)
            raise RuntimeArtifactTrustError("context verification requires a sealed stage without SQLite companions")


def _check_read_state(path, descriptor, expected, *, header=None):
    """The read descriptor and its still-trusted pathname must remain one version."""
    _trusted_existing_file(path)
    _require_no_companions(path)
    current, named = os.fstat(descriptor), os.lstat(path)
    _validate_trusted_runtime_database_stat(path, current)
    if _file_version(current) != expected[0] or _file_version(named) != expected[1]:
        raise RuntimeArtifactTrustError("context stage changed during read-only verification")
    if header is not None:
        position = os.lseek(descriptor, 0, os.SEEK_CUR)
        os.lseek(descriptor, 0, os.SEEK_SET)
        actual = os.read(descriptor, 100)
        os.lseek(descriptor, position, os.SEEK_SET)
        if actual != header:
            raise RuntimeArtifactTrustError("context stage header changed during read-only verification")
        _check_read_state(path, descriptor, expected)


def _validate_image_header(header, size):
    if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
        raise ArtifactIntegrityError("context database is not a complete SQLite image")
    if header[18:20] != b"\x01\x01":
        raise RuntimeArtifactTrustError("context verification requires an online sealed stage in DELETE mode")
    encoded = int.from_bytes(header[16:18], "big")
    page_size = 65536 if encoded == 1 else encoded
    if page_size < 512 or page_size > 65536 or page_size & (page_size-1) or size < page_size or size % page_size:
        raise ArtifactIntegrityError("context SQLite image has an invalid page size or length")


def _read_sealed_image(path, descriptor, expected):
    _check_read_state(path, descriptor, expected)
    size = os.fstat(descriptor).st_size
    if size > MAX_CONTEXT_IMAGE_BYTES:
        raise RuntimeArtifactTrustError("context image size exceeds the read-only input limit")
    header = os.read(descriptor, 100)
    _validate_image_header(header, size)
    _check_read_state(path, descriptor, expected)
    os.lseek(descriptor, 0, os.SEEK_SET)
    image = bytearray(size)
    position = 0
    while position < size:
        _check_read_state(path, descriptor, expected)
        block = os.read(descriptor, min(_IMAGE_CHUNK_BYTES, size-position))
        if not block:
            raise RuntimeArtifactTrustError("context image became truncated while reading")
        image[position:position+len(block)] = block
        position += len(block)
        _check_read_state(path, descriptor, expected)
    if os.read(descriptor, 1) or image[:100] != header:
        raise RuntimeArtifactTrustError("context image changed while reading")
    _check_read_state(path, descriptor, expected, header=header)
    return image, header


@contextmanager
def _open_sealed_image(path, identity):
    # SQLite NEVER receives this mutable source pathname. Even an interleaved
    # writer cannot make this verifier create/recover/update a source sidecar.
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    connection = None
    try:
        info = os.fstat(descriptor)
        _validate_trusted_runtime_database_stat(path, info)
        if (info.st_dev, info.st_ino) != identity or info.st_nlink != 1:
            raise RuntimeArtifactTrustError("context stage changed identity while opening its read descriptor")
        # Windows Python 3.12 may expose different ctime semantics through
        # fstat and lstat. Track BOTH exact series, never round/ignore either.
        expected = (_file_version(info), _file_version(os.lstat(path)))
        if expected[0][:-1] != expected[1][:-1]:
            raise RuntimeArtifactTrustError("context stage differs between its descriptor and pathname")
        image, header = _read_sealed_image(path, descriptor, expected)
        connection = sqlite3.connect(":memory:", timeout=5, factory=TrackedConnection)
        deserialize = getattr(connection, "deserialize", None)
        if not callable(deserialize):
            raise RuntimeArtifactTrustError("SQLite deserialize capability is required for read-only verification")
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute("PRAGMA query_only=ON")
        try:
            deserialize(image)
        except sqlite3.NotSupportedError as exc:
            raise RuntimeArtifactTrustError("SQLite deserialize capability is unavailable") from exc
        # Connection settings are explicit after loading, not inferred from a
        # version number, serialized header, or the source's connection state.
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute("PRAGMA query_only=ON")
        _check_read_state(path, descriptor, expected, header=header)
        yield connection
        _check_read_state(path, descriptor, expected, header=header)
    except MemoryError as exc:
        raise RuntimeArtifactTrustError("insufficient memory for bounded context image verification") from exc
    except sqlite3.Error as exc:
        raise ArtifactIntegrityError("context in-memory SQLite verification failed") from exc
    finally:
        if connection is not None:
            connection.close()
        os.close(descriptor)


@contextmanager
def _open_database(path, *, writable=False):
    path, identity = _trusted_existing_file(path)
    if not writable:
        with _open_sealed_image(path, identity) as connection:
            yield connection
        return
    for suffix in ("-wal", "-shm", "-journal"):
        companion = path.with_name(path.name + suffix)
        if os.path.lexists(companion):
            _trusted_existing_file(companion)
    connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=5, factory=TrackedConnection)
    try:
        if _trusted_existing_file(path)[1] != identity:
            raise RuntimeArtifactTrustError("context database changed file identity while opening")
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
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


def _verify_artifact_types(connection, artifacts, created_at, limitations):
    # These are owning structural validators, not test-only fit approvals.
    from tennis.tour_state import _check_predictions, _decode_wrapper
    from context_runtime_semantics import D2_KINDS, verify_d2_artifacts

    for key, envelope in artifacts.items():
        kind, payload = envelope["kind"], envelope["payload"]
        if kind == "tennis-tour-state":
            if type(payload.get("state")) is not dict:
                raise ArtifactIntegrityError("missing typed tour state")
            tour = payload["state"].get("tour")
            if tour not in ("ATP", "WTA"):
                raise ArtifactIntegrityError("legacy or unknown tour schema")
            _check_predictions(_decode_wrapper(payload, tour, decision_cutoff=created_at[key].timestamp()))
        elif kind == "tennis-live-winner-original-v1":
            # Full A1/current-B1/known-code numerical binding follows after
            # observation decoding, including originals with no B3 consumer.
            from context_models.tennis_live import validate_original_publication
            validate_original_publication(payload, created_at=created_at[key])
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
        elif kind in D2_KINDS:
            pass  # All typed references, including inactive ones, below.
        else:
            limitations.add("unrecognized-artifact-schema")
    return verify_d2_artifacts(connection, artifacts, created_at, limitations)


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


def _verify_observations(connection, tables, *, protected_receipts=()):
    if "context_observations" not in tables:
        return {}, 0
    from context_runtime_inventory import VerifiedReceiptMapping
    receipts = VerifiedReceiptMapping(connection, protected_receipts=protected_receipts)
    return receipts, receipts.validate_all()


def _verify_worker_snapshot(payload, key, artifacts, receipts, limitations, live_originals):
    from context_transport import _BASE_KEYS, _INPUTS, _input_key, _refs, replay_context_payload
    require_object(payload, _INPUTS | {"result"}, label="stored worker transport")
    if type(payload["schema"]) is not int or payload["schema"] != 1:
        raise ArtifactIntegrityError("known worker transport has an invalid schema")
    effect = approval = None
    if payload["effect_hash"] is not None:
        ref = payload["effect_hash"]
        effect = {"kind": "context-effect-v1",
            "payload": _resolve(artifacts, ref, kind="context-effect-v1")}
    if payload["approval_hash"] is not None:
        ref = payload["approval_hash"]
        approval = {"digest": ref, "kind": "context-approval-v1",
            "payload": _resolve(artifacts, ref, kind="context-approval-v1")}
    if (canonical_bytes(effect) != canonical_bytes(payload["effect_artifact"])
            or canonical_bytes(approval) != canonical_bytes(payload["approval"])
            or approval is not None and effect is None):
        raise ArtifactIntegrityError("worker artifact transport differs from its actual A1 references")
    for name in ("observation_refs", "preprocessing_refs"):
        _refs(payload[name], name)
    if not set(payload["observation_refs"]) <= set(receipts):
        raise ArtifactIntegrityError("worker snapshot references missing physical receipts")
    for ref in payload["preprocessing_refs"]:
        _resolve(artifacts, ref)
    event = validate_event(payload["event"])
    features = validate_feature_vector(payload["features"])
    base = require_object(payload["base"], _BASE_KEYS, label="stored worker base transport")
    require_text(base["family"], "stored worker family", code=True)
    if (event["event_key"] != base["event_key"] or features["event_key"] != base["event_key"]
            or features["cutoff"] != base["cutoff"] or canonical_timestamp(base["cutoff"]) != base["cutoff"]
            or not all(set(refs) <= set(payload["observation_refs"]) for refs in features["refs"].values())
            or _input_key(payload, event, base, features) != key):
        raise ArtifactIntegrityError("worker transport does not bind its complete input revision")
    from context_runtime_tennis import verify_live_snapshot
    if verify_live_snapshot(payload, key, live_originals, effect=effect, approval=approval, limitations=limitations):
        return
    pair = base["family"], features["version"]
    if pair not in _WORKER_REPLAY_CAPABILITIES:
        limitations.add("d3-owning-family-replay-unavailable")
        return
    replay_context_payload(payload, key=key, effect_artifact=effect, approval=approval)
    limitations.add("d3-owning-source-feature-replay-unavailable")


def _verify_snapshots(connection, tables, artifacts, receipts, limitations, live_originals):
    if "context_snapshots" not in tables:
        return 0
    count = 0
    for key, raw, payload_hash in connection.execute("SELECT key,payload,payload_digest FROM context_snapshots"):
        require_digest(key, "snapshot key")
        payload = _decode_snapshot(key, raw, payload_hash)
        count += 1
        if payload.get("kind") == "context-worker-snapshot-v1":
            _verify_worker_snapshot(payload, key, artifacts, receipts, limitations, live_originals)
            continue
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
            family = families[frozenset(payload["base_params"])]
            consumed_effect = effect
            if effect is not None and effect["family"] != family:
                # B3 retains the inspected identity on an inapplicable effect.
                # This exception is ONLY the actual unchanged baseline case;
                # its artifact/hash is still fully validated/resolved above.
                if (payload["role"] != "not_applied" or payload["comparison_params"] is not None
                        or payload["comparison_markets"] is not None
                        or type(payload["factor_roles"]) is not dict
                        or any(role != "not_applied" for role in payload["factor_roles"].values())
                        or payload.get("approval_hash") is not None or payload.get("certified_markets", [])
                        or payload["used_params"] != payload["base_params"]
                        or payload["used_markets"] != payload["base_markets"]):
                    raise ArtifactIntegrityError("inapplicable context effect cannot claim a modeled distribution")
                consumed_effect = None
            validate_context_result(payload, family=family, effect_artifact=consumed_effect)
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


def _verify_connection(connection, *, history_max_bytes=None):
    """Inspect one caller-held SQLite transaction without any schema writes."""
    tables = _verify_schema(connection)
    from context_runtime_inventory import VerifiedArtifactMapping
    artifacts, created_at = VerifiedArtifactMapping(connection), {}
    for key, created in connection.execute("SELECT digest,created_at FROM artifacts"):
        require_digest(key, "artifact identity")
        if key in created_at:
            raise ArtifactIntegrityError("duplicate artifact identity")
        artifacts[key]
        created_at[key] = datetime.fromisoformat(_validate_stored_timestamp(created, label="artifact creation time"))
    limitations = set()
    semantics = _verify_artifact_types(connection, artifacts, created_at, limitations)
    manifests, current, chain = _manifest_rows(connection, artifacts, created_at)
    for manifest in manifests.values():
        _verify_slots(manifest["slots"], artifacts)
    history_cache = None
    if "context_observations" in tables:
        from context_runtime_inventory import VerifiedReceiptMapping
        receipts = VerifiedReceiptMapping(connection, protected_receipts=semantics["protected_receipts"])
        content_count, history_cache = receipts._validate_all_with_tennis(artifacts)
    else:
        receipts, content_count = {}, 0
    from context_runtime_tennis import verify_live_originals
    live_originals = verify_live_originals(artifacts, created_at, receipts, limitations,
                                         history_max_bytes=history_max_bytes, history_cache=history_cache)
    snapshot_count = _verify_snapshots(connection, tables, artifacts, receipts, limitations, live_originals)
    rollback_count = _verify_rollbacks(connection, tables, manifests, chain)
    slots = manifests[current]["slots"] if current is not None else {}
    report = {"schema": 1, "verification_level": "transport_only" if limitations else "structural",
              "empirical_approval_verified": False, "limitations": sorted(limitations),
              "d2_verified": semantics["verified"],
              "counts": {"artifacts": len(artifacts), "manifests": len(manifests),
                         "contents": content_count, "observations": len(receipts),
                         "snapshots": snapshot_count, "rollbacks": rollback_count},
              "active_manifest": current, "active_slots": dict(slots),
              "tour_states": {tour: slots[f"tennis:{tour}"] for tour in ("ATP", "WTA") if f"tennis:{tour}" in slots}}
    return {"report": report, "manifests": manifests, "chain": chain, "artifacts": artifacts, "tables": tables}


def verify_context_database(path: Path, *, input_mode="memory") -> dict:
    """Verify an existing sealed DB read-only; unsupported evidence is explicit.

    For a live WAL/journal use stage_databases first. SQLite receives only a
    bounded private in-memory DELETE image by default. Explicit sealed_file
    mode requires a proven Linux root-owned app-unwritable file and ancestry.
    Neither mode creates companions or repairs a source DB; no auto fallback.
    Structural means current known storage schemas/links, NOT approved bets.
    """
    history_max_bytes = None  # Preserve admission of existing <=64-MiB images.
    if input_mode == "memory":
        reader = _open_database(path)
    elif input_mode == "sealed_file":
        from context_runtime_input import open_sealed_connection
        reader = open_sealed_connection(path, max_bytes=MAX_SEALED_CONTEXT_BYTES)
        history_max_bytes = MAX_TENNIS_HISTORY_BYTES
    else:
        raise RuntimeArtifactTrustError("unsupported context input mode")
    with reader as connection:
        if not connection.in_transaction:
            connection.execute("BEGIN")
        try:
            checked = (_verify_connection(connection) if history_max_bytes is None else
                       _verify_connection(connection, history_max_bytes=history_max_bytes))
            report = checked["report"]
            connection.rollback()
            return report
        except MemoryError as exc:
            connection.rollback()
            raise RuntimeArtifactTrustError("insufficient memory for context verification") from exc
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
