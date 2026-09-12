"""Actual same-call Tennis prediction into the explicit C storage transport.

Preparation uses the caller's live, fully validated History/Source and the old
in-connection state and D2 owners. It neither fetches nor calls Daily/Shadow or
legacy path writers. Publication requires a different caller-owned transaction.
The complete tour and observation-reference array are never Python lists.

Only the new C2 non-observation header is bounded at 1 MiB. Old A1/D2 loaders
still allocate complete objects; observing their physical bytes is not native
AS/RSS enforcement, protected-receipt authority, a seal, or B approval. The
outer owner must bind the actual code/dependency closure and total resources.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import sqlite3

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    require_digest, require_text, validate_base_distribution,
    validate_context_result, validate_event, validate_feature_vector,
)
from context_models.dataset import _artifact
from context_models.offset import ContextModelError
from context_models.tennis_live import (
    CODE_PATHS, MARKETS, ORIGINAL_ARTIFACT_KIND, ORIGIN_KIND, SIDECAR_KIND,
    original_base, validate_context_model, validate_original_publication,
)
from context_snapshots import _finite_json, _verified_payload, select_context_result
from context_sources.tennis_status import STATUS_SCHEMA, normalize_tennis_status
from context_transport import KIND, _approved, _comparison, _eligible, _feature_binding
from model_artifacts import _decode_object, _load_active, _load_artifact, _timestamp, canonical_bytes
from tennis import predict
from tennis.live_context import _Inventory, _event, _receipt
from tennis.state_codec import encode_state
from tennis.tour_state import TourUnavailable, _decode_wrapper

from . import refs, snapshots
from .contracts import StorageIntegrityError, StorageLimitError
from .history import HISTORY_VERSION, HistoryView
from .ref_chunks import iter_canonical_ref_chunks
from .tennis import FORMAT_VERSION as TENNIS_FORMAT_VERSION, tennis_features_streaming


FORMAT_VERSION = "context-tennis-consumer-v1"


def _same(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


def _physical_metadata(history):
    """Incremental physical observations, NOT alternate artifact admission.

    No raw values/keys are fetched, and no new size/type filter is imposed on
    opaque rows. The actual closed ordinary schemas already require rowids;
    bind those integers in rowid order, alongside an ordinal and row count.
    The held Source's actual complete input/file identity remains authoritative
    for byte binding; equal types/lengths alone never establish equal content.
    """
    connection = history._state.source.connection
    result = {}
    for table, columns in (
        ("artifacts", ("digest", "kind", "payload", "created_at")),
        ("manifests", ("digest", "predecessor", "payload", "published_at")),
        ("active_manifest", ("id", "digest")),
    ):
        history.assert_intact()
        hasher = hashlib.sha256(canonical_bytes({"table": table, "columns": columns}))
        count = total = largest = 0
        previous = None
        fields = ",".join(f"typeof({name}),octet_length({name})" for name in columns)
        with closing(connection.execute(f"SELECT rowid,{fields} FROM main.{table} ORDER BY rowid")) as cursor:
            for rowid, *row in cursor:
                history.assert_intact()
                if type(rowid) is not int or (previous is not None and rowid <= previous):
                    raise StorageIntegrityError("physical artifact rowids are not ordered integers")
                previous = rowid
                # SQLite's built-in typeof/octet_length results have fixed
                # metadata shape regardless of the actual stored value size.
                sizes = row[1::2]
                if (any(type(kind) is not str or kind not in {"null", "integer", "real", "text", "blob"}
                        for kind in row[::2])
                        or any(size is not None and (type(size) is not int or size < 0) for size in sizes)):
                    raise StorageIntegrityError("physical artifact metadata is not measurable")
                count += 1
                framed = canonical_bytes([count, rowid, *row])
                hasher.update(len(framed).to_bytes(8, "big"))
                hasher.update(framed)
                total += sum(size for size in sizes if size is not None)
                largest = max(largest, *(size or 0 for size in sizes))
                history.assert_intact()
        result[table] = {"rows": count, "octets": total, "largest_value_octets": largest,
                         "metadata_sha256": hasher.hexdigest()}
    history.assert_intact()
    return result


def _code_hashes():
    # Same code identity fields as the actual legacy Original. This is not a
    # claim that path hashes authenticate imported bytecode or dependencies.
    root = Path(__file__).resolve().parents[1]
    result = {}
    for name in CODE_PATHS:
        path = root / name
        with path.open("rb") as stream:
            hasher = hashlib.sha256()
            while chunk := stream.read(65536):
                hasher.update(chunk)
        result[name] = hasher.hexdigest()
    return result


def _bounded_canonical(value, maximum):
    _finite_json(value)
    output = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False)
    for token in encoder.iterencode(value):
        for start in range(0, len(token), 16384):
            piece = token[start:start + 16384].encode("utf-8")
            if len(output) + len(piece) > maximum:
                raise StorageLimitError("complete C Tennis non-observation header exceeds its 1 MiB adapter envelope")
            output.extend(piece)
    return bytes(output)


def _complete_features(features, maximum):
    expected = features.canonical_size
    if expected > maximum:
        raise StorageLimitError("complete Tennis features cannot fit the C2 non-observation header")
    output = bytearray()
    with closing(features.iter_canonical_chunks()) as chunks:
        for chunk in chunks:
            if len(output) + len(chunk) > expected:
                raise StorageIntegrityError("actual streamed feature bytes exceeded their complete size")
            output.extend(chunk)
    if len(output) != expected:
        raise StorageIntegrityError("actual streamed feature bytes are incomplete")
    value = _decode_object(bytes(output), label="complete C Tennis feature vector")
    checked = validate_feature_vector(value)
    if not _same(value, checked):
        raise ContextIntegrityError("actual streaming Tennis features are not canonical")
    features.assert_intact()
    return checked


def _header(event, base, features, inventory):
    """Reuse the actual selectors/math; only whole-reference transport differs."""
    event, base, features = validate_event(event), validate_base_distribution(base), validate_feature_vector(features)
    if (event["event_key"] != base["event_key"] or features["event_key"] != event["event_key"]
            or features["cutoff"] != base["cutoff"] or event["sport"] != base["family"].split(":")[0]):
        raise ContextIntegrityError("actual consumer event/base/features have different scope")
    _feature_binding(event, base, features, [])
    effect, effect_hash, approval, reason = inventory.select(event, base, features)
    artifact = None
    if effect is not None:
        _, artifact = _verified_payload(effect, kind="context-effect-v1", expected_hash=effect_hash)
    elif effect_hash is not None:
        raise ContextIntegrityError("resolved effect identity has no immutable envelope")
    approved = None
    approval_hash = None
    if approval is not None:
        approval_hash, approved = _verified_payload(approval, kind="context-approval-v1")
        if artifact is None:
            raise ContextIntegrityError("resolved approval has no bound effect")
    comparison, limitations = None, []
    if artifact is None:
        limitations.append("context-effect-unavailable")
    elif _eligible(event, base, features, artifact):
        try:
            comparison = _comparison(event, base, features, artifact)
        except ContextModelError:
            limitations.append("context-numerical-comparison-unavailable")
    result = select_context_result(base, comparison, event=event, features=features,
        effect_artifact=effect, effect_hash=effect_hash, approval=approval,
        factor_roles={name: "applied" if artifact is not None and name in artifact["feature_names"] else "not_applied"
                      for name in features["values"]},
        factor_states=features["states"], limitations=limitations)
    # Exact result invariants of context_transport._validate_payload, without
    # presenting a made-up/shortened observation list to that closed old API.
    consumed = artifact if artifact is not None and artifact["family"] == base["family"] else None
    checked = validate_context_result(result, family=base["family"], effect_artifact=consumed)
    expected = {"event_key": event["event_key"], "base_hash": digest(base), "effect_hash": effect_hash,
        "base_params": base["params"], "base_markets": base["markets"],
        "factor_states": features["states"], "feature_refs": features["refs"]}
    if not _same(checked, result) or any(not _same(result[name], value) for name, value in expected.items()):
        raise ContextIntegrityError("consumer result differs from its actual original inputs")
    prefix = "comparison" if result["role"] == "applied" else "base"
    if any(not _same(result["used_" + name], result[prefix + "_" + name]) for name in ("params", "markets")):
        raise ContextIntegrityError("consumer used distribution differs from its actual role")
    roles = {name: result["role"] if artifact is not None and name in artifact["feature_names"] else "not_applied"
             for name in features["values"]}
    delta = {name: 100 * (value - base["markets"][name]) for name, value in result["used_markets"].items()}
    if result["factor_roles"] != roles or not _same(result["delta_pp"], delta):
        raise ContextIntegrityError("consumer roles or probability deltas differ")
    if result["role"] != "not_applied" and not _eligible(event, base, features, artifact):
        raise ContextIntegrityError("ineligible consumer cannot claim a comparison")
    if result["role"] == "applied":
        if (not _approved(event, base, features, artifact, approved, effect_hash)
                or result.get("approval_hash") != approval_hash
                or result.get("certified_markets") != approved["target_markets"]):
            raise ContextIntegrityError("consumer application differs from its actual scoped approval")
    elif result.get("approval_hash") is not None or result.get("certified_markets"):
        raise ContextIntegrityError("unapplied consumer cannot inherit approval")
    return {"schema": 1, "kind": KIND, "event": event, "base": base, "features": features,
        "preprocessing_refs": [], "effect_artifact": effect, "effect_hash": effect_hash,
        "approval": approval, "approval_hash": approval_hash, "result": result}, reason


class PreparedTennisConsumer:
    """Live preparation, not a serializable or caller-constructible authority."""
    __slots__ = ("_history", "_features", "_header", "_prediction", "_reason", "_metadata",
                 "_code", "_closed", "_failed", "_publication_started")

    def __init__(self, *args, **kwargs):
        raise StorageIntegrityError("prepare_tennis_consumer owns actual prediction preparation")

    def __setattr__(self, name, value):
        raise StorageIntegrityError("prepared consumer bindings cannot be changed")

    def assert_intact(self):
        try:
            if type(self) is not PreparedTennisConsumer or self._closed or self._failed:
                raise StorageIntegrityError("prepared Tennis consumer is closed or invalid")
            self._history.assert_intact()
            self._features.assert_intact()
            if self._features.history_binding != self._history.binding:
                raise StorageIntegrityError("prepared features no longer belong to the actual history")
        except BaseException:
            object.__setattr__(self, "_failed", True)
            raise

    @property
    def features(self):
        self.assert_intact()
        return self._features

    @property
    def prediction(self):
        self.assert_intact()
        return deepcopy(self._prediction)

    @property
    def origin(self):
        self.assert_intact()
        return json.loads(self._header)["base"]["reference_weights"]

    @property
    def selection_reason(self):
        self.assert_intact()
        return self._reason

    @property
    def physical_metadata(self):
        """Detached observations only; not a proof of artifact/D2 admission."""
        self.assert_intact()
        return json.loads(self._metadata)

    def close(self):
        if not self._closed:
            object.__setattr__(self, "_closed", True)
            self._features.close()  # Does not delete or release an allocation.

    def __enter__(self):
        self.assert_intact()
        return self

    def __exit__(self, exc_type, *_):
        try:
            if exc_type is None and not self._closed and not self._failed:
                self.assert_intact()
        finally:
            self.close()


def prepare_tennis_consumer(history, *, native_competition, tournament_id,
        grouping_slug, observed_at, surface, best_of, indoor, cutoff,
        work_directory, owned_directory, main_cap_bytes):
    """Predict exactly once; finish/close the feature writer before returning.

    The fixed empty owned_directory is mandatory here. The caller retains the
    Source/History and reserves M plus journal-M and all failed feature files.
    Native worker/heap/code seals and whole-workspace admission remain outside.
    """
    if type(history) is not HistoryView:
        raise StorageIntegrityError("consumer requires its actual complete HistoryView")
    history.assert_intact()
    if (history.binding.version != HISTORY_VERSION or HISTORY_VERSION != "context-complete-tennis-history-v3"
            or TENNIS_FORMAT_VERSION != "context-tennis-features-stream-v3"):
        raise StorageIntegrityError("consumer is not connected to its reviewed history/feature format")
    if not isinstance(cutoff, datetime) or canonical_timestamp(cutoff) != history.cutoff:
        raise StorageIntegrityError("consumer cutoff differs from its actual complete history")
    if owned_directory is None:
        raise StorageIntegrityError("consumer needs its pre-reserved fixed feature directory")
    clock = canonical_timestamp(observed_at)
    if clock > history.cutoff:
        raise ContextIntegrityError("native receipt follows the actual decision")
    normalized = normalize_tennis_status(history.tour, tournament_id, native_competition,
        grouping_slug=grouping_slug, observed_at=observed_at)[0]
    if normalized["payload"]["issues"] or normalized["payload"]["status"] != "scheduled":
        raise ContextIntegrityError("native current event is not an intact scheduled singles pair")
    receipt, event = _receipt(normalized, observed_at), _event(normalized)
    group = history.event(event["event_key"])
    actual, count = None, 0
    if group is not None:
        with closing(group.iter_latest_rows()) as rows:
            for row in rows:
                count += 1
                if count == 1:
                    actual = row
    if (count != 1 or actual["source_schema"] != STATUS_SCHEMA or actual["digest"] != receipt
            or actual["observed_at"] != clock or actual["payload"]["issues"]
            or actual["payload"]["status"] != "scheduled" or not _same(_event(actual), event)):
        raise ContextIntegrityError("current native event is absent, revised or ambiguous")
    players = native_competition["competitors"]
    player_a = require_text(players[0].get("athlete", {}).get("displayName"), "actual prediction player A")
    player_b = require_text(players[1].get("athlete", {}).get("displayName"), "actual prediction player B")
    history.assert_intact()
    metadata = _physical_metadata(history)
    connection = history._state.source.connection
    _, slots = _load_active(connection, decision_cutoff=cutoff)
    state_hash = slots.get("tennis:" + history.tour)
    if state_hash is None:
        raise TourUnavailable(history.tour)
    envelope = _artifact(connection, state_hash, "tennis-tour-state", latest=history.cutoff)
    state = _decode_wrapper(envelope["payload"], history.tour, decision_cutoff=cutoff.timestamp())
    state.artifact_hash = state_hash
    code = _code_hashes()
    captured, capturing = None, True

    def capture(value):
        nonlocal captured
        if not capturing or captured is not None:
            raise ContextIntegrityError("actual original capture must occur once within this predictor call")
        if type(value) is not dict or set(value) != {"inputs", "values"}:
            raise ContextIntegrityError("actual original capture cannot replace its owning source/state identity")
        _finite_json(value)
        captured = canonical_bytes(value)

    try:
        prediction = predict.predict_match(state, player_a, player_b, surface,
            best_of=best_of, tour=history.tour, indoor=indoor, as_of=cutoff,
            workload_history=(), original_capture=capture)
    finally:
        capturing = False
    history.assert_intact()
    if (captured is None or not _same(envelope["payload"]["state"], encode_state(state, tour=history.tour))
            or state.training_cutoff != envelope["payload"]["training_cutoff"]
            or state.artifact_hash != state_hash or _code_hashes() != code):
        raise ContextIntegrityError("actual same-call capture, state or implementation changed")
    origin = {"schema": 1, "kind": ORIGIN_KIND, "event": event, "cutoff": history.cutoff,
        "state_hash": state_hash, "native_receipt": receipt, "native_observed_at": clock,
        "competition_revision": actual["payload"]["competition_revision"],
        "native_state_identity": "unresolved", "code_hashes": code, **json.loads(captured)}
    base = original_base(origin)
    # Active A1/D2 inventory uses the exact held source and genuine verification.
    # In particular, this does not manufacture a protected-empty receipt map.
    inventory = _Inventory(connection)
    history.assert_intact()
    feature_stream = None
    try:
        feature_stream = tennis_features_streaming(event, history, base, cutoff=cutoff,
            work_directory=work_directory, owned_directory=owned_directory,
            main_cap_bytes=main_cap_bytes, limits=history._state.limits)
        maximum = min(snapshots.MAX_HEADER_BYTES, history._state.limits.block_bytes)
        features = _complete_features(feature_stream, maximum)
        header, reason = _header(event, base, features, inventory)
        encoded = _bounded_canonical(header, maximum)
        history.assert_intact()
        feature_stream.assert_intact()
        if _code_hashes() != code:
            raise ContextIntegrityError("actual prediction code changed during preparation")
        prepared = object.__new__(PreparedTennisConsumer)
        for name, value in (
            ("_history", history), ("_features", feature_stream), ("_header", encoded),
            ("_prediction", deepcopy(prediction)), ("_reason", reason),
            ("_metadata", canonical_bytes(metadata)), ("_code", canonical_bytes(code)),
            ("_closed", False), ("_failed", False), ("_publication_started", False),
        ):
            object.__setattr__(prepared, name, value)
        prepared.assert_intact()
        return prepared
    except BaseException:
        if feature_stream is not None:
            feature_stream.close()
        raise


def _source_references(prepared):
    """Validate the entire selected canonical history before staging each key."""
    history = prepared._history
    count = used = 0
    hasher = hashlib.sha256()
    with closing(history.iter_rows()) as rows:
        for row in rows:
            prepared.assert_intact()
            raw = canonical_bytes(row)  # Old actual row allocation, not a new value cap.
            count += 1
            used += len(raw)
            hasher.update(len(raw).to_bytes(8, "big"))
            for start in range(0, len(raw), history._state.limits.block_bytes):
                hasher.update(raw[start:start + history._state.limits.block_bytes])
            reference = row["digest"]
            del raw, row
            yield reference
            prepared.assert_intact()
    if (count != history.row_count or used != history.canonical_bytes
            or hasher.hexdigest() != history.binding.selected_digest):
        raise StorageIntegrityError("complete consumer history differs from its owning selection")
    prepared.assert_intact()


def _ordered_history_keys(prepared):
    """Small key-only order on the same guarded v3 spool, after full row replay.

    This does not re-decode an oversized row merely to sort its 64-byte receipt
    key. No public hashes or SQL projection replace the complete replay above.
    """
    history = prepared._history
    prepared.assert_intact()
    cursor = sqlite3.Connection.execute(history._state.connection,
        "SELECT digest FROM main.history WHERE observed_at<=? ORDER BY digest", (history.cutoff,))
    previous, count = None, 0
    try:
        for (reference,) in cursor:
            prepared.assert_intact()
            require_digest(reference, "actual selected history key")
            if previous is not None and reference <= previous:
                raise StorageIntegrityError("complete selected history keys are not unique")
            previous = reference
            count += 1
            yield reference
            prepared.assert_intact()
        if count != history.row_count:
            raise StorageIntegrityError("complete selected history key count differs")
        prepared.assert_intact()
    finally:
        cursor.close()


def _bind_membership(connection, prepared, descriptor, header):
    limits = prepared._history._state.limits
    if descriptor.reference_count != prepared._history.row_count:
        raise StorageIntegrityError("published observation set is not the complete selected history")
    # This set is bounded by the complete 1-MiB header, never by tour length.
    required = {ref for group in header["features"]["refs"].values() for ref in group}
    required.add(header["base"]["reference_weights"]["native_receipt"])
    hasher = hashlib.sha256(b'{"kind":' + canonical_bytes(KIND) + b',"observation_refs":[')
    missing = object()
    with closing(_ordered_history_keys(prepared)) as expected, closing(
            refs.iter_refset(connection, descriptor, limits=limits)) as stored:
        for index, (left, right) in enumerate(zip_longest(expected, stored, fillvalue=missing)):
            prepared.assert_intact()
            if left != right:
                raise StorageIntegrityError("published observation membership differs from actual full history")
            required.discard(right)
            hasher.update((b"," if index else b"") + canonical_bytes(right))
    if required:
        raise ContextIntegrityError("consumer omitted an actual feature/native observation reference")
    hasher.update(b'],"preprocessing_refs":[]}')
    prepared.assert_intact()
    return hasher.hexdigest()


def _object_pieces(header, name, stream):
    yield b"{"
    for index, key in enumerate(sorted((*header, name))):
        yield (b"," if index else b"") + canonical_bytes(key) + b":"
        if key == name:
            yield from stream
        else:
            yield canonical_bytes(header[key])
    yield b"}"


def _context_keys(connection, descriptor, input_descriptor, limits):
    yield b"["
    first, inserted = True, False
    with closing(refs.iter_refset(connection, descriptor, limits=limits)) as references:
        for reference in references:
            if not inserted and input_descriptor <= reference:
                yield (b"" if first else b",") + canonical_bytes(input_descriptor)
                first, inserted = False, True
            if reference != input_descriptor:
                yield (b"" if first else b",") + canonical_bytes(reference)
                first = False
        if not inserted:
            yield (b"" if first else b",") + canonical_bytes(input_descriptor)
    yield b"]"


def _snapshot_identity(connection, prepared, descriptor, header, input_descriptor):
    limits = prepared._history._state.limits
    key_header = {"schema": 1, "event": header["event"], "base_hash": digest(header["base"]),
        "feature_version": header["features"]["version"], "feature_hash": digest(header["features"]),
        "effect_hash": header["effect_hash"], "approval_hash": header["approval_hash"],
        "decision_at": header["base"]["cutoff"]}
    key_hasher = hashlib.sha256()
    with closing(_context_keys(connection, descriptor, input_descriptor, limits)) as keys:
        for piece in _object_pieces(key_header, "context_refs", keys):
            prepared.assert_intact()
            key_hasher.update(piece)
    key = key_hasher.hexdigest()
    raw = hashlib.sha256()
    old = hashlib.sha256(b'{"key":' + canonical_bytes(key) + b',"payload":')
    size = 0
    with closing(iter_canonical_ref_chunks(connection, descriptor, limits=limits,
            chunk_bytes=min(65536, limits.block_bytes))) as observation_bytes:
        for piece in _object_pieces(header, "observation_refs", observation_bytes):
            prepared.assert_intact()
            size += len(piece)
            if size > limits.input_bytes:
                raise StorageLimitError("complete consumer snapshot exceeds its C input envelope")
            raw.update(piece)
            old.update(piece)
    old.update(b"}")
    prepared.assert_intact()
    return key, raw.hexdigest(), size, old.hexdigest()


def _put_original(connection, origin, created_at):
    publication = validate_original_publication({"schema": 1, "origin": origin}, created_at=created_at)
    encoded = canonical_bytes(publication)
    reference = digest({"kind": ORIGINAL_ARTIFACT_KIND, "payload": publication})
    connection.execute("CREATE TABLE IF NOT EXISTS artifacts(digest TEXT PRIMARY KEY, kind TEXT NOT NULL, payload BLOB NOT NULL, created_at TEXT NOT NULL)")
    if connection.execute("SELECT type FROM main.sqlite_schema WHERE name='artifacts'").fetchall() != [("table",)]:
        raise StorageIntegrityError("original publication needs its actual artifact table")
    columns = connection.execute("PRAGMA main.table_xinfo(artifacts)").fetchall()
    expected = [(0, "digest", "TEXT", 0, None, 1, 0), (1, "kind", "TEXT", 1, None, 0, 0),
                (2, "payload", "BLOB", 1, None, 0, 0), (3, "created_at", "TEXT", 1, None, 0, 0)]
    if columns != expected or connection.execute(
            "SELECT 1 FROM main.sqlite_schema WHERE type='trigger' AND tbl_name='artifacts' LIMIT 1").fetchone():
        raise StorageIntegrityError("original artifact schema or trigger semantics differ")
    connection.execute("INSERT OR IGNORE INTO main.artifacts(digest,kind,payload,created_at) VALUES(?,?,?,?)",
        (reference, ORIGINAL_ARTIFACT_KIND, encoded, _timestamp(created_at)))
    stored = _load_artifact(connection, reference)
    if not _same(stored, {"kind": ORIGINAL_ARTIFACT_KIND, "payload": publication}):
        raise ContextIntegrityError("actual Original publication identity collision")
    published_at = connection.execute("SELECT created_at FROM main.artifacts WHERE digest=?", (reference,)).fetchone()[0]
    validate_original_publication(stored["payload"], created_at=published_at)
    return reference


@dataclass(frozen=True)
class PublishedTennisConsumer:
    """Detached result data, not transaction durability or reuse authority."""
    snapshot: snapshots.SnapshotPartsDescriptor
    original_hash: str
    reference: dict


def put_tennis_consumer(connection, prepared, *, created_at):
    """One publication attempt under one savepoint; never commit the caller.

    FULL/TOOBIG may make SQLite itself roll back the entire caller transaction.
    No successful result escapes an incomplete write or changed input lifetime.
    Files, retained attempts, physical quotas and later commit belong outside.
    Complete caller-required cleanup (including prepared.close) before accepting
    or committing a whole build. Returned data cannot certify later cleanup.
    """
    if type(prepared) is not PreparedTennisConsumer:
        raise StorageIntegrityError("publication needs the actual live prediction preparation")
    prepared.assert_intact()
    limits = prepared._history._state.limits
    output_path = refs._require_connection(connection, limits)
    for path in (prepared._history.path, prepared._history._state.source.path, prepared._features.path):
        if output_path.samefile(path):
            raise StorageIntegrityError("consumer output must not be a held source/history/feature file")
    if prepared._publication_started:
        raise StorageIntegrityError("actual prepared consumer publication has already been attempted")
    object.__setattr__(prepared, "_publication_started", True)
    try:
        if canonical_bytes(_code_hashes()) != prepared._code:
            raise ContextIntegrityError("actual prediction code changed before publication")
        header = _decode_object(prepared._header, label="prepared complete consumer header")
        # Check the caller's actual publication clock before allocating output.
        validate_original_publication({"schema": 1, "origin": header["base"]["reference_weights"]}, created_at=created_at)
        _timestamp(created_at)
        with refs._atomic(connection, limits, final_validate=prepared.assert_intact):
            refs.create_schema(connection)
            snapshots.create_schema(connection)
            with closing(_source_references(prepared)) as complete_history:
                observations = refs.put_refset(connection, complete_history, limits=limits)
            input_descriptor = _bind_membership(connection, prepared, observations, header)
            key, raw, size, payload_digest = _snapshot_identity(connection, prepared, observations, header, input_descriptor)
            original_hash = _put_original(connection, header["base"]["reference_weights"], created_at)
            snapshot = snapshots.put_snapshot_parts(connection, key=key, header_bytes=prepared._header,
                observation_refs=observations, expected_raw_payload_sha256=raw,
                expected_payload_bytes=size, expected_payload_digest=payload_digest,
                expected_observation_count=prepared._history.row_count, limits=limits)
            reference = {"schema": 1, "kind": "context-consumer-reference-v1", "key": key,
                         "payload_digest": payload_digest}
            validate_context_model({"schema": 1, "kind": SIDECAR_KIND, "reference": reference,
                "event": header["event"], "cutoff": header["base"]["cutoff"], "markets": MARKETS,
                "original_artifact_hash": original_hash})
            prepared.assert_intact()
            if canonical_bytes(_code_hashes()) != prepared._code:
                raise ContextIntegrityError("actual prediction code changed during publication")
            # Include a lifetime change during the final code-file I/O in this
            # same rollback scope, not in a check after releasing the savepoint.
            prepared.assert_intact()
        return PublishedTennisConsumer(snapshot, original_hash, reference)
    except BaseException:
        object.__setattr__(prepared, "_failed", True)
        raise
