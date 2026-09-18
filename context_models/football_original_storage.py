"""Bounded, lossless ORIGINAL transport; no source/model/replay approval.

Only fixed owning arrays are externalized. No history migration, compression,
generic tree store, active model slot or numerical computation is performed.
Budgets count newly inserted payload bytes, NOT physical SQLite disk usage.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import hashlib
import sqlite3

from football_original import FootballOriginal
import model_artifacts as a1
from context_models.contracts import canonical_timestamp
from context_models.dataset import _reader


CHUNK_KIND = "football-original-json-chunk-v1"
BODY_KIND = "football-original-body-v1"
MANIFEST_KIND = "football-original-storage-manifest-v1"
ORIGINAL_KIND = "football-original-market-calculation-v1"
MAX_ORIGINAL_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024
_FIELDS = frozenset({"schema", "kind", "prediction_version", "model_contract_signature",
    "captured_at", "logical_history_cutoff", "source_evidence", "fixture", "league_history",
    "team_history", "goal_model", "count_models", "raw_probabilities", "probabilities",
    "calibration_recipes", "market_specs", "goal_provenance", "limitations"})
_COMPONENTS = ("venue_attack", "venue_defense", "form_attack", "form_defense")
_PRIOR_PATHS = tuple(("goal_provenance", "reference_weights", "heads", side,
    "components", component, metric, "prior_refs") for side in ("home", "away")
    for component in _COMPONENTS for metric in ("goals", "xg"))
_ALL_PATHS = (("league_history",), ("team_history",), ("goal_provenance", "history_refs"), *_PRIOR_PATHS)


class StorageBudgetExceeded(ValueError):
    """This publication would exceed its explicit new-payload-byte budget."""


@dataclass(frozen=True)
class PreparedOriginal:
    artifacts: tuple[a1.PreparedArtifact, ...]
    manifest_digest: str
    body_digest: str
    logical_digest: str

    @property
    def payload_bytes(self):
        return sum(len(item.payload_bytes) for item in self.artifacts)


@dataclass(frozen=True)
class StoredOriginal:
    manifest_digest: str
    logical_digest: str
    inserted_payload_bytes: int
    created_at: str


def _object(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise a1.ArtifactIntegrityError(label + " has invalid fields/type")
    return value


def _version(value):
    if type(value) is not int or value != 1:
        raise a1.ArtifactIntegrityError("unsupported storage/original schema")


def _clock(value):
    if type(value) is not str or canonical_timestamp(value) != value:
        raise a1.ArtifactIntegrityError("timestamp must be canonical UTC microseconds")
    return value


def _reference(value, kind):
    _object(value, {"schema", "kind", "digest"}, "typed storage reference")
    _version(value["schema"])
    if value["kind"] != kind:
        raise a1.ArtifactIntegrityError("wrong storage reference kind")
    return a1._validate_digest(value["digest"])


def _ref(artifact):
    return {"schema": 1, "kind": artifact.kind, "digest": artifact.digest}


def _location(packet, path):
    current = packet
    for key in path[:-1]:
        current = current[key]
    return current, path[-1]


def _paths(packet):
    paths = [("league_history",)]
    if packet["team_history"] is not None:
        paths.append(("team_history",))
    provenance = _object(packet["goal_provenance"], {"history_refs", "reference_weights"}, "goal provenance")
    weights = provenance["reference_weights"]
    if type(weights) is not dict:
        raise a1.ArtifactIntegrityError("invalid reference weights")
    _version(weights.get("schema"))
    if weights.get("kind") == "unavailable":
        _object(weights, {"schema", "kind", "reason"}, "unavailable provenance")
        if type(weights["reason"]) is not str or not weights["reason"] or provenance["history_refs"] != []:
            raise a1.ArtifactIntegrityError("invalid unavailable provenance")
        return paths
    _object(weights, {"schema", "kind", "heads"}, "reference weights")
    if weights["kind"] != "football-goals-v1":
        raise a1.ArtifactIntegrityError("unsupported reference weights")
    paths.append(("goal_provenance", "history_refs"))
    heads = _object(weights["heads"], {"home", "away"}, "reference heads")
    for side in ("home", "away"):
        head = _object(heads[side], {"outer_weights", "pair_weights", "components"}, "head")
        components = _object(head["components"], _COMPONENTS, "components")
        for name in _COMPONENTS:
            component = _object(components[name], {"team_id", "team_join", "scope", "prior_raw_weight",
                "metric_weights", "goals", "xg"}, "component")
            for metric in ("goals", "xg"):
                term = component[metric]
                if term is not None:
                    _object(term, {"samples", "prior_weight", "prior_value", "prior_refs"}, "metric")
                    paths.append(("goal_provenance", "reference_weights", "heads", side,
                        "components", name, metric, "prior_refs"))
    return paths


def _no_storage_references(value):
    # Validation only: never traverse/resolve a reference recursively.
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > 64:
            raise a1.ArtifactIntegrityError("original exceeds supported JSON depth")
        if type(item) is dict:
            if item.get("kind") in (CHUNK_KIND, BODY_KIND, MANIFEST_KIND):
                raise a1.ArtifactIntegrityError("recursive or misplaced storage reference")
            stack.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            stack.extend((child, depth + 1) for child in item)


def _packet(packet):
    _object(packet, _FIELDS, "ORIGINAL packet")
    _version(packet["schema"])
    if packet["kind"] != ORIGINAL_KIND:
        raise a1.ArtifactIntegrityError("wrong ORIGINAL kind")
    _clock(packet["captured_at"])
    if packet["logical_history_cutoff"] is not None:
        _clock(packet["logical_history_cutoff"])
    for field in ("prediction_version", "model_contract_signature", "source_evidence"):
        if type(packet[field]) is not str:
            raise a1.ArtifactIntegrityError("invalid ORIGINAL text field")
    for field in ("fixture", "goal_model", "count_models", "raw_probabilities", "probabilities", "calibration_recipes"):
        if type(packet[field]) is not dict:
            raise a1.ArtifactIntegrityError("invalid ORIGINAL object field")
    for field in ("market_specs", "limitations"):
        if type(packet[field]) is not list:
            raise a1.ArtifactIntegrityError("invalid ORIGINAL array field")
    for path in _paths(packet):
        parent, key = _location(packet, path)
        if type(parent[key]) is not list:
            raise a1.ArtifactIntegrityError("fixed ORIGINAL path must be an array")
    _no_storage_references(packet)


def prepare_original(original: FootballOriginal) -> PreparedOriginal:
    """Plan all unique immutable objects, with no DB access or expanded copy kept."""
    if type(original) is not FootballOriginal or type(original._bytes) is not bytes:
        raise TypeError("storage accepts only an owning FootballOriginal")
    if len(original._bytes) > MAX_ORIGINAL_BYTES:
        raise a1.ArtifactIntegrityError("expanded ORIGINAL exceeds 4 MiB")
    try:
        packet = a1._decode_object(original._bytes, label="ORIGINAL")
    except RecursionError as exc:
        raise a1.ArtifactIntegrityError("ORIGINAL exceeds supported depth") from exc
    _packet(packet)
    logical = hashlib.sha256(original._bytes).hexdigest()
    captured = packet.pop("captured_at")
    unique = {}
    for path in _paths(packet):
        parent, key = _location(packet, path)
        chunk = a1.prepare_artifact(kind=CHUNK_KIND, payload={"schema": 1, "values": parent[key]})
        unique[chunk.digest] = chunk
        parent[key] = _ref(chunk)
    body = a1.prepare_artifact(kind=BODY_KIND, payload=packet)
    manifest = a1.prepare_artifact(kind=MANIFEST_KIND, payload={"schema": 1,
        "body": _ref(body), "captured_at": captured, "logical_digest": logical})
    if len(manifest.payload_bytes) > MAX_MANIFEST_BYTES:
        raise a1.ArtifactIntegrityError("storage manifest exceeds 8 KiB")
    unique[body.digest] = body
    unique[manifest.digest] = manifest
    return PreparedOriginal(tuple(unique.values()), manifest.digest, body.digest, logical)


def _decode(rows, ref, kind):
    row = rows.get(ref)
    if row is None:
        raise a1.ArtifactIntegrityError("missing required ORIGINAL artifact")
    try:
        value = a1._decode_artifact_row(ref, row)
    except RecursionError as exc:
        raise a1.ArtifactIntegrityError("artifact exceeds supported JSON depth") from exc
    if value["kind"] != kind:
        raise a1.ArtifactIntegrityError("wrong ORIGINAL artifact kind")
    _clock(row[2])
    return value["payload"]


def _expand(rows, manifest_ref):
    manifest = _decode(rows, manifest_ref, MANIFEST_KIND)
    if len(rows[manifest_ref][1]) > MAX_MANIFEST_BYTES:
        raise a1.ArtifactIntegrityError("storage manifest exceeds 8 KiB")
    _object(manifest, {"schema", "body", "captured_at", "logical_digest"}, "manifest")
    _version(manifest["schema"])
    captured = _clock(manifest["captured_at"])
    logical = a1._validate_digest(manifest["logical_digest"])
    if rows[manifest_ref][2] < captured:
        raise a1.ArtifactIntegrityError("manifest creation precedes capture")
    body_ref = _reference(manifest["body"], BODY_KIND)
    packet = _decode(rows, body_ref, BODY_KIND)
    _object(packet, _FIELDS - {"captured_at"}, "stable ORIGINAL body")
    required = {manifest_ref, body_ref}
    # Account for every occurrence before installing reconstructed arrays.
    # Small arrays can shrink typed references, so only the final total is a
    # bound on the expanded packet, not an intermediate replacement estimate.
    expanded_size = len(rows[body_ref][1]) + len(a1.canonical_bytes({"captured_at": captured})) - 1
    locations = []
    for path in _paths(packet):
        parent, key = _location(packet, path)
        ref = _reference(parent[key], CHUNK_KIND)
        chunk = _decode(rows, ref, CHUNK_KIND)
        _object(chunk, {"schema", "values"}, "ORIGINAL chunk")
        _version(chunk["schema"])
        if type(chunk["values"]) is not list:
            raise a1.ArtifactIntegrityError("chunk values must be an array")
        _no_storage_references(chunk["values"])
        expanded_size += len(a1.canonical_bytes(chunk["values"])) - len(a1.canonical_bytes(parent[key]))
        locations.append((parent, key, chunk["values"]))
        required.add(ref)
    if expanded_size > MAX_ORIGINAL_BYTES:
        raise a1.ArtifactIntegrityError("expanded ORIGINAL exceeds 4 MiB")
    if required != set(rows):
        raise a1.ArtifactIntegrityError("raw addressing hints differ from validated references")
    if any(rows[ref][2] > rows[manifest_ref][2] for ref in required):
        raise a1.ArtifactIntegrityError("dependency creation follows manifest creation")
    for parent, key, values in locations:
        parent[key] = values
    packet["captured_at"] = captured
    _packet(packet)
    encoded = a1.canonical_bytes(packet)
    if len(encoded) > MAX_ORIGINAL_BYTES or hashlib.sha256(encoded).hexdigest() != logical:
        raise a1.ArtifactIntegrityError("expanded ORIGINAL size or logical hash mismatch")
    return FootballOriginal(encoded), body_ref, logical


def _budget(value):
    if type(value) is not int or value < 0:
        raise ValueError("new payload budget must be a finite nonnegative integer")


def publish_prepared(connection, prepared: PreparedOriginal, *, created_at: datetime,
                     max_new_payload_bytes: int) -> StoredOriginal:
    """Publish inside the caller's transaction; failure rolls back this unit only.

    Later live publication can add decision/code/B1 artifacts before committing
    that same outer transaction. This helper neither fabricates nor commits them.
    The caller must own a write transaction (normally BEGIN IMMEDIATE).
    """
    _budget(max_new_payload_bytes)
    created = canonical_timestamp(created_at)
    if not connection.in_transaction:
        raise ValueError("publication requires an owning write transaction")
    if type(prepared) is not PreparedOriginal or type(prepared.artifacts) is not tuple:
        raise TypeError("publication requires PreparedOriginal")
    if not 2 <= len(prepared.artifacts) <= 21:
        raise a1.ArtifactIntegrityError("invalid prepared object count")
    rows = {}
    for obj in prepared.artifacts:
        if type(obj) is not a1.PreparedArtifact or type(obj.payload_bytes) is not bytes or len(obj.payload_bytes) > MAX_ORIGINAL_BYTES:
            raise a1.ArtifactIntegrityError("invalid prepared artifact")
        if obj.digest in rows:
            raise a1.ArtifactIntegrityError("duplicate prepared artifact")
        rows[obj.digest] = (obj.kind, obj.payload_bytes, created)
    _, body, logical = _expand(rows, prepared.manifest_digest)
    if (body, logical) != (prepared.body_digest, prepared.logical_digest):
        raise a1.ArtifactIntegrityError("prepared identity mismatch")
    connection.execute("SAVEPOINT football_original_publication")
    try:
        # This is inside the serialized writer image, not a stale preflight.
        missing = [obj for obj in prepared.artifacts if connection.execute(
            "SELECT 1 FROM artifacts WHERE digest=?", (obj.digest,)).fetchone() is None]
        needed = sum(len(obj.payload_bytes) for obj in missing)
        if needed > max_new_payload_bytes:
            raise StorageBudgetExceeded(f"publication requires {needed} new payload bytes; budget is {max_new_payload_bytes}")
        actual_rows = {}
        inserted_bytes = 0
        for obj in prepared.artifacts:
            actual, inserted = a1._insert_artifact(connection, obj, created)
            actual_rows[obj.digest] = (obj.kind, obj.payload_bytes, actual)
            inserted_bytes += len(obj.payload_bytes) if inserted else 0
        # A later INSERT trigger could have modified an earlier dependency.
        # Freeze final actual rows, never validate fabricated expected readback.
        actual_rows = {obj.digest: _raw(connection, obj.digest,
            MAX_MANIFEST_BYTES if obj.kind == MANIFEST_KIND else MAX_ORIGINAL_BYTES)
            for obj in prepared.artifacts}
        _expand(actual_rows, prepared.manifest_digest)
        if inserted_bytes > max_new_payload_bytes:
            raise StorageBudgetExceeded("actual insertion exceeded publication budget")
        connection.execute("RELEASE football_original_publication")
        return StoredOriginal(prepared.manifest_digest, logical, inserted_bytes,
            actual_rows[prepared.manifest_digest][2])
    except BaseException:
        connection.execute("ROLLBACK TO football_original_publication")
        connection.execute("RELEASE football_original_publication")
        raise


def store_original(path, original: FootballOriginal, *, created_at: datetime,
                   max_new_payload_bytes: int) -> StoredOriginal:
    """Own one atomic publication; all encoding and limits precede mutation."""
    _budget(max_new_payload_bytes)
    created = canonical_timestamp(created_at)
    prepared = prepare_original(original)
    manifest = next(obj for obj in prepared.artifacts if obj.digest == prepared.manifest_digest)
    if created < a1._decode_object(manifest.payload_bytes, label="manifest")["captured_at"]:
        raise a1.ArtifactIntegrityError("manifest creation precedes capture")
    with closing(a1._connect(path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            result = publish_prepared(connection, prepared, created_at=created_at,
                max_new_payload_bytes=max_new_payload_bytes)
            connection.commit()
            return result
        except BaseException:
            connection.rollback()
            raise


def _raw(connection, ref, limit):
    a1._validate_digest(ref)
    metadata = connection.execute("SELECT typeof(payload),length(payload) FROM artifacts WHERE digest=?", (ref,)).fetchone()
    if metadata is None or metadata[0] != "blob" or not 0 < metadata[1] <= limit:
        raise a1.ArtifactIntegrityError("missing, mistyped or oversized required artifact")
    return connection.execute("SELECT kind,payload,created_at FROM artifacts WHERE digest=?", (ref,)).fetchone()


def _hint(connection, ref, path):
    # Untrusted bounded addressing hints ONLY. Closed JSON/hash validation follows
    # after snapshot release. CAST avoids SQLite 3.45 BLOB/JSONB ambiguity.
    value = connection.execute("SELECT json_extract(CAST(payload AS TEXT), ?) FROM artifacts WHERE digest=?",
        ("$." + ".".join(path) + ".digest", ref)).fetchone()[0]
    if value is not None:
        a1._validate_digest(value, label="raw reference hint")
    return value


def load_original(path, manifest_digest: str) -> FootballOriginal:
    """Freeze only required raw rows in one read image, then decode after release."""
    a1._validate_digest(manifest_digest)
    rows = {}
    try:
        with _reader(path) as connection:
            rows[manifest_digest] = _raw(connection, manifest_digest, MAX_MANIFEST_BYTES)
            body_ref = _hint(connection, manifest_digest, ("body",))
            if body_ref is None:
                raise a1.ArtifactIntegrityError("manifest has no body reference hint")
            rows[body_ref] = _raw(connection, body_ref, MAX_ORIGINAL_BYTES)
            for path_keys in _ALL_PATHS:
                ref = _hint(connection, body_ref, path_keys)
                if ref is not None and ref not in rows:
                    remaining = MAX_ORIGINAL_BYTES + 32 * 1024 - sum(len(row[1]) for row in rows.values())
                    rows[ref] = _raw(connection, ref, min(MAX_ORIGINAL_BYTES, remaining))
    except sqlite3.DatabaseError as exc:
        raise a1.ArtifactIntegrityError("invalid ORIGINAL addressing JSON/database") from exc
    return _expand(rows, manifest_digest)[0]
