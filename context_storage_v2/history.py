"""Complete disk-backed Tennis history, not a reusable verification proof.

This explicit C3 adapter accepts only an already physically validated legacy
receipt mapping in its held, query-only transaction. That caller still owns
D2's unopened-final authorization, the sealed input, and complete inventory
coverage; a public input digest is not a grant of any of those properties.

Every source row is visited without SQL tour/cutoff pruning. The unchanged
source owner selects and validates recognized causal Tennis rows before its
tour filter. Unknown sources and unopened D2 finals remain outside Tennis.
The completed private spool is bound to that source lifetime, then reopened
read-only. No decoded complete history or complete event group is retained.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile

import context_observations
from context_models.contracts import canonical_timestamp, digest as content_digest, require_digest, require_native_key
from context_runtime_inventory import VerifiedReceiptMapping
from context_runtime_transaction import TrackedConnection
from context_sources.tennis import SOURCE_SCHEMA
from context_sources.tennis_status import STATUS_SCHEMA, select_tennis_observations, validate_selected_tennis_receipt
from model_artifacts import _decode_object, canonical_bytes

from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError, StorageLimits


HISTORY_VERSION = "context-complete-tennis-history-v2"
SELECTION_VERSION = "espn-tennis-complete-tour-v1"
_TRACKED_METHODS = {name: getattr(TrackedConnection, name) for name in (
    "execute", "cursor", "commit", "rollback", "close", "deserialize", "executescript")}
_RECEIPT_METHODS = {name: getattr(VerifiedReceiptMapping, name) for name in (
    "_decode_row", "_check_validation", "_check_transaction", "_inventory_stamp")}
_RECEIPT_ATTRIBUTES = frozenset({"_connection", "_generation", "_validation_failed",
    "_protected", "_validation_stamp", "_validating", "_validated_content_count"})
_OPAQUE_FIELDS = frozenset({"digest", "content_digest", "event_key", "observed_at", "kind"})
_LIMIT_FIELDS = ("input_bytes", "tour_history_bytes", "block_bytes", "workspace_bytes",
                 "min_free_bytes", "blocks_per_set")


def _limits_stamp(limits):
    if type(limits) is not StorageLimits or set(vars(limits)) != set(_LIMIT_FIELDS):
        raise StorageLimitError("history needs its unchanged exact v2 limits")
    # Calling the class owner avoids a caller shadowing this method on the
    # otherwise exact dataclass instance and bypassing its approved maxima.
    StorageLimits.__post_init__(limits)
    return tuple(getattr(limits, name) for name in _LIMIT_FIELDS)


def _identity(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise StorageIntegrityError("history requires a single-link regular file")
    return (info.st_dev, info.st_ino, info.st_nlink, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _companions_absent(path):
    if any(os.path.lexists(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal")):
        raise StorageIntegrityError("history source/spool has a SQLite companion")


def _hash_file(path, block_bytes):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(min(block_bytes, 1024**2)):
            result.update(block)
    return result.hexdigest()


def _resource_check(directory, path, limits):
    if shutil.disk_usage(directory).free < limits.min_free_bytes:
        raise StorageLimitError("history build would consume its free-space reserve")
    # This is this adapter's allocation, not a claim about the caller's entire
    # QA workspace. The parent preparation owner must charge all allocations.
    allocated = sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
    if allocated > limits.workspace_bytes:
        raise StorageLimitError("private history workspace exceeds its budget")
    if path.exists() and path.stat().st_size > limits.input_bytes:
        raise StorageLimitError("history spool exceeds the complete-input envelope")


@dataclass(frozen=True)
class HistoryBinding:
    version: str
    selection_version: str
    source_versions: tuple
    ordering: str
    input_identity: str
    source_receipt_count: int
    opaque_receipt_count: int
    tour: str
    cutoff: str
    maximum_cutoff: str
    row_count: int
    canonical_bytes: int
    selected_digest: str
    spool_digest: str


@dataclass(frozen=True)
class _Source:
    receipts: object
    connection: object
    validation_stamp: tuple
    protected: frozenset
    path: Path
    identity: tuple
    databases: tuple

    def check(self):
        receipts, connection = self.receipts, self.connection
        if (type(receipts) is not VerifiedReceiptMapping
                or type(connection) is not TrackedConnection
                or receipts._connection is not connection
                or receipts.__dict__.keys() - _RECEIPT_ATTRIBUTES
                or connection.__dict__.keys() - {"_transaction_generation"}
                or connection.row_factory is not None or connection.text_factory is not str
                or any(getattr(TrackedConnection, name) is not method for name, method in _TRACKED_METHODS.items())
                or any(getattr(VerifiedReceiptMapping, name) is not method for name, method in _RECEIPT_METHODS.items())
                or receipts._validation_stamp is None
                or receipts._validation_stamp != self.validation_stamp
                or receipts._protected != self.protected):
            raise StorageIntegrityError("history source owner or completed validation changed")
        VerifiedReceiptMapping._check_validation(receipts)
        if sqlite3.Connection.execute(connection, "PRAGMA query_only").fetchone() != (1,):
            raise StorageIntegrityError("history source is not query-only")
        if tuple(sqlite3.Connection.execute(connection, "PRAGMA database_list")) != self.databases:
            raise StorageIntegrityError("history source attached database set changed")
        if _identity(self.path) != self.identity:
            raise StorageIntegrityError("history source file changed identity or bytes")
        _companions_absent(self.path)


def _source(receipts, input_identity, limits):
    require_digest(input_identity, "complete history input identity")
    if type(receipts) is not VerifiedReceiptMapping:
        raise StorageIntegrityError("history requires the actual completed physical receipt owner")
    connection = receipts._connection
    if type(connection) is not TrackedConnection or receipts._validation_stamp is None:
        raise StorageIntegrityError("history cannot publish from an incomplete receipt builder")
    # No caller-supplied connection, callback, iterator or claimed proof flag is
    # installed on the private output. Source callbacks remain the input owner's
    # responsibility; direct base SQL plus pre/post lifetime checks are used here.
    databases = tuple(sqlite3.Connection.execute(connection, "PRAGMA database_list"))
    if (len(databases) not in (1, 2) or databases[0][1] != "main" or not databases[0][2]
            or len(databases) == 2 and (databases[1][1:] != ("temp", "")
                or sqlite3.Connection.execute(connection, "SELECT count(*) FROM temp.sqlite_schema").fetchone() != (0,))):
        raise StorageIntegrityError("history source must be one concrete file database")
    path = Path(databases[0][2])
    identity = _identity(path)
    if identity[4] > limits.input_bytes:
        raise StorageLimitError("complete history input exceeds v2 budget")
    source = _Source(receipts, connection, receipts._validation_stamp,
                     receipts._protected, path, identity, databases)
    source.check()
    if _hash_file(path, limits.block_bytes) != input_identity:
        raise StorageIntegrityError("history input identity differs from the actual file")
    source.check()
    return source


class _ReadConnection(TrackedConnection):
    """Private read connection rejects executable customizations after binding."""
    def _reject_customization(self, *args, **kwargs):
        self._history_poisoned = True
        raise StorageIntegrityError("history read connection cannot install callbacks or extensions")

    set_authorizer = _reject_customization
    set_progress_handler = _reject_customization
    set_trace_callback = _reject_customization
    create_function = _reject_customization
    create_aggregate = _reject_customization
    create_window_function = _reject_customization
    enable_load_extension = _reject_customization
    load_extension = _reject_customization

    def __setattr__(self, name, value):
        if name in {"row_factory", "text_factory"} and getattr(self, "_history_bound", False):
            self._history_poisoned = True
            raise StorageIntegrityError("history read connection factory cannot change")
        super().__setattr__(name, value)


@dataclass(frozen=True)
class _State:
    source: _Source
    connection: _ReadConnection
    generation: int
    path: Path
    identity: tuple
    limits: StorageLimits
    limits_stamp: tuple
    storage_epoch: tuple


def _storage_epoch(connection):
    # mode=ro protects main bytes, but SQLite still permits TEMP DDL and ATTACH.
    # Touch temp before database_list: opening its empty schema is legitimate at
    # publication, whereas any later schema/database change invalidates reuse.
    schema = tuple(sqlite3.Connection.execute(connection, pragma).fetchone()
                   for pragma in ("PRAGMA main.schema_version", "PRAGMA temp.schema_version",
                                  "PRAGMA main.journal_mode", "PRAGMA temp.journal_mode",
                                  "PRAGMA main.cache_size", "PRAGMA main.mmap_size",
                                  "PRAGMA main.max_page_count", "PRAGMA temp_store"))
    databases = tuple(sqlite3.Connection.execute(connection, "PRAGMA database_list"))
    return schema, databases


class HistoryView:
    """A repeated complete, canonical-order view, valid only in its held lifetime.

    The object is deliberately not a tuple and has no public alternate-connection
    constructor. It does not confer HMAC or source/provider completeness approval.
    """
    __slots__ = ("_state", "_binding", "_failed", "_closed", "_owns_connection")

    def __init__(self, *args, **kwargs):
        raise StorageIntegrityError("build_history owns complete history publication")

    def __setattr__(self, name, value):
        raise StorageIntegrityError("published history bindings cannot be changed")

    @property
    def binding(self):
        return self._binding

    @property
    def tour(self):
        return self._binding.tour

    @property
    def cutoff(self):
        return self._binding.cutoff

    @property
    def row_count(self):
        return self._binding.row_count

    @property
    def canonical_bytes(self):
        return self._binding.canonical_bytes

    @property
    def path(self):
        """Diagnostic path only; neither a seal nor permission to mutate it."""
        return self._state.path

    def assert_intact(self):
        try:
            if type(self) is not HistoryView or self._closed or self._failed:
                raise StorageIntegrityError("history view is closed, failed, or not its owning type")
            state, connection = self._state, self._state.connection
            state.source.check()
            if _limits_stamp(state.limits) != state.limits_stamp:
                raise StorageLimitError("published history resource contract changed")
            if (type(connection) is not _ReadConnection or connection._history_poisoned
                    or not connection.in_transaction
                    or connection.transaction_generation != state.generation
                    or connection.row_factory is not None or connection.text_factory is not str
                    or connection.total_changes != 0
                    or connection.__dict__.keys() - {"_transaction_generation", "_history_poisoned", "_history_bound"}
                    or sqlite3.Connection.execute(connection, "PRAGMA query_only").fetchone() != (1,)
                    or _storage_epoch(connection) != state.storage_epoch
                    or _identity(state.path) != state.identity):
                raise StorageIntegrityError("published history lifetime or read connection changed")
            _companions_absent(state.path)
        except BaseException:
            object.__setattr__(self, "_failed", True)
            raise

    def _rows(self, where="", arguments=()):
        self.assert_intact()
        query = ("SELECT digest,observed_at,event_key,payload FROM main.history WHERE observed_at<=? "
                 + ("AND " + where if where else "") + " ORDER BY observed_at,digest")
        cursor = sqlite3.Connection.execute(self._state.connection, query, (self.cutoff, *arguments))
        try:
            for ref, observed, event_key, payload in cursor:
                self.assert_intact()
                if type(payload) is not bytes or len(payload) > self._state.limits.block_bytes:
                    raise StorageIntegrityError("history row is not its bounded canonical blob")
                row = _decode_object(payload, label="complete history row")
                if (row["digest"], row["observed_at"], row["event_key"]) != (ref, observed, event_key):
                    raise StorageIntegrityError("history row differs from its indexed identity")
                yield row
                self.assert_intact()
        except BaseException as error:
            if not isinstance(error, GeneratorExit):
                object.__setattr__(self, "_failed", True)
            raise
        finally:
            cursor.close()
        self.assert_intact()

    def iter_rows(self):
        return self._rows()

    def as_of(self, cutoff: datetime):
        """An owning-validated earlier prefix on this same complete tour spool.

        The maximum build must already have completed. Earlier consumers cannot
        widen beyond their own view or manufacture a new source generation.
        This is a full bounded pass over prefix rows, not cached proof reuse.
        """
        self.assert_intact()
        select_tennis_observations((), cutoff=cutoff, tour=self.tour)
        decision = canonical_timestamp(cutoff)
        if decision > self.cutoff:
            raise StorageIntegrityError("history prefix cannot widen its completed cutoff")
        result = object.__new__(HistoryView)
        object.__setattr__(result, "_state", self._state)
        object.__setattr__(result, "_binding", replace(self.binding, cutoff=decision))
        object.__setattr__(result, "_failed", False)
        object.__setattr__(result, "_closed", False)
        object.__setattr__(result, "_owns_connection", False)
        count = used = 0
        digest = hashlib.sha256()
        try:
            for row in result.iter_rows():
                # Identical selected source contract, before any participant or
                # event projection. The parent built every recognized tour row.
                validate_selected_tennis_receipt(row)
                if row["payload"]["tour"] != self.tour:
                    raise StorageIntegrityError("history prefix contains another tour")
                payload = canonical_bytes(row)
                used += len(payload)
                count += 1
                if used > self._state.limits.tour_history_bytes:
                    raise StorageLimitError("complete prefix exceeds canonical history budget")
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
            self.assert_intact()
            object.__setattr__(result, "_binding", replace(result.binding, row_count=count,
                canonical_bytes=used, selected_digest=digest.hexdigest()))
            result.assert_intact()
            return result
        except BaseException:
            result.close()
            raise

    def iter_events(self, *, exclude_event=None):
        """Event handles in original first-observation order, never full groups."""
        self.assert_intact()
        if exclude_event is not None:
            require_native_key(exclude_event, sport="tennis")
        cursor = sqlite3.Connection.execute(self._state.connection,
            "SELECT e.event_key,(SELECT max(h.observed_at) FROM main.history h "
            "WHERE h.event_key=e.event_key AND h.observed_at<=?) FROM main.events e "
            "WHERE e.first_observed_at<=? "
            + ("AND e.event_key!=? " if exclude_event is not None else "")
            + "ORDER BY e.first_observed_at,e.first_digest",
            (self.cutoff, self.cutoff, exclude_event) if exclude_event is not None
            else (self.cutoff, self.cutoff))
        try:
            for event_key, latest in cursor:
                self.assert_intact()
                yield EventHistory(self, event_key, latest)
                self.assert_intact()
        finally:
            cursor.close()
        self.assert_intact()

    def event(self, event_key):
        self.assert_intact()
        require_native_key(event_key, sport="tennis")
        value = sqlite3.Connection.execute(self._state.connection,
            "SELECT max(observed_at) FROM main.history WHERE event_key=? AND observed_at<=?",
            (event_key, self.cutoff)).fetchone()
        self.assert_intact()
        return None if value == (None,) else EventHistory(self, event_key, value[0])

    def close(self):
        if not self._closed:
            object.__setattr__(self, "_closed", True)
            if self._owns_connection:
                self._state.connection.close()

    def __enter__(self):
        self.assert_intact()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None and not self._failed:
                self.assert_intact()
        finally:
            self.close()


@dataclass(frozen=True)
class EventHistory:
    """A bounded group cursor on an owning complete HistoryView."""
    _view: HistoryView
    event_key: str
    latest_observed_at: str

    def _check(self):
        if type(self) is not EventHistory or type(self._view) is not HistoryView:
            raise StorageIntegrityError("event history lacks its exact owning view")
        self._view.assert_intact()
        actual = sqlite3.Connection.execute(self._view._state.connection,
            "SELECT max(observed_at) FROM main.history WHERE event_key=? AND observed_at<=?",
            (self.event_key, self._view.cutoff)).fetchone()
        if actual != (self.latest_observed_at,):
            raise StorageIntegrityError("event history latest bound changed")

    def iter_rows(self):
        self._check()
        return self._view._rows("event_key=?", (self.event_key,))

    def iter_latest_rows(self):
        self._check()
        return self._view._rows("event_key=? AND observed_at=?", (self.event_key, self.latest_observed_at))


def build_history(receipts, *, directory, cutoff: datetime, tour: str,
                  input_identity: str, limits=DEFAULT_LIMITS) -> HistoryView:
    """Visit the full validated mapping and atomically complete a private spool.

    ``directory`` is an existing QA allocation root. This function never edits
    source data and never returns a partial view. Failed private files are left
    for the caller's bounded cleanup policy, not silently deleted or reused.
    """
    limits_stamp = _limits_stamp(limits)
    select_tennis_observations((), cutoff=cutoff, tour=tour)
    decision = canonical_timestamp(cutoff)
    source = _source(receipts, input_identity, limits)
    allocation_root = Path(directory)
    if not allocation_root.is_dir() or allocation_root.is_symlink():
        raise StorageIntegrityError("history allocation root must be an existing directory")
    if shutil.disk_usage(allocation_root).free < limits.min_free_bytes:
        raise StorageLimitError("history build lacks its free-space reserve")
    private = Path(tempfile.mkdtemp(prefix="context-history-", dir=allocation_root))
    os.chmod(private, 0o700)
    path = private / "history.sqlite"
    connection = sqlite3.connect(path, timeout=0)
    published = None
    try:
        os.chmod(path, 0o600)
        connection.execute("PRAGMA main.journal_mode=DELETE")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute("PRAGMA main.cache_size=-8192")
        connection.execute("PRAGMA main.mmap_size=0")
        connection.execute("PRAGMA trusted_schema=OFF")
        page_size = connection.execute("PRAGMA main.page_size").fetchone()[0]
        max_pages = min(limits.input_bytes, limits.workspace_bytes) // page_size
        if max_pages < 1:
            raise StorageLimitError("history allocation cannot hold one SQLite page")
        actual_max = connection.execute(f"PRAGMA main.max_page_count={max_pages}").fetchone()[0]
        if actual_max != max_pages:
            raise StorageLimitError("history could not install its hard SQLite allocation cap")
        connection.execute("CREATE TABLE main.history(digest TEXT PRIMARY KEY, observed_at TEXT NOT NULL, event_key TEXT NOT NULL, payload BLOB NOT NULL) WITHOUT ROWID")
        connection.execute("CREATE INDEX main.history_order ON history(observed_at,digest)")
        connection.execute("CREATE INDEX main.history_event_order ON history(event_key,observed_at,digest)")
        connection.execute("CREATE TABLE main.events(event_key TEXT PRIMARY KEY, first_observed_at TEXT NOT NULL, first_digest TEXT NOT NULL, latest_observed_at TEXT NOT NULL) WITHOUT ROWID")
        connection.execute("CREATE INDEX main.events_order ON events(first_observed_at,first_digest)")
        connection.execute("CREATE TABLE main.seen(digest TEXT PRIMARY KEY) WITHOUT ROWID")
        connection.execute("BEGIN")
        count = used = source_count = opaque_count = 0
        # No SQL cutoff/tour filter: corrupt future/foreign physical records may
        # not hide behind metadata. The unchanged source selector owns causality.
        # Preserve the physical owner's column projection, qualifying only its
        # two actual source tables; TEMP names must never change resolution.
        physical_query = context_observations._SELECT.replace(
            "FROM context_observations AS r", "FROM main.context_observations AS r").replace(
            "LEFT JOIN context_contents AS c", "LEFT JOIN main.context_contents AS c")
        for raw in sqlite3.Connection.execute(source.connection, physical_query):
            source.check()
            row = VerifiedReceiptMapping._decode_row(receipts, raw)
            source.check()
            if type(row) is not dict:
                raise StorageIntegrityError("physical receipt owner returned an ambiguous row")
            ref = require_digest(row["digest"])
            connection.execute("INSERT INTO main.seen VALUES (?)", (ref,))
            source_count += 1
            if ref in source.protected:
                if (frozenset(row) != _OPAQUE_FIELDS or row["kind"] != "match_outcome"
                        or canonical_timestamp(row["observed_at"]) != row["observed_at"]
                        or content_digest({"content_digest": require_digest(row["content_digest"]),
                                           "observed_at": row["observed_at"]}) != ref):
                    raise StorageIntegrityError("protected receipt is not its closed final outer binding")
                require_native_key(row["event_key"])
                opaque_count += 1
                if source_count % 256 == 0:
                    _resource_check(private, path, limits)
                continue
            if "source_schema" not in row:
                raise StorageIntegrityError("unprotected receipt has no physical source schema")
            for selected in select_tennis_observations((row,), cutoff=cutoff, tour=tour):
                payload = canonical_bytes(selected)
                if len(payload) > limits.block_bytes:
                    raise StorageLimitError("one canonical history row exceeds v2 block budget")
                used += len(payload)
                if used > limits.tour_history_bytes:
                    raise StorageLimitError("complete Tennis history exceeds v2 canonical budget")
                count += 1
                connection.execute("INSERT INTO main.history VALUES (?,?,?,?)", (
                    selected["digest"], selected["observed_at"], selected["event_key"], payload))
                connection.execute("""INSERT INTO main.events VALUES (?,?,?,?)
                    ON CONFLICT(event_key) DO UPDATE SET
                    first_observed_at=CASE WHEN (excluded.first_observed_at,excluded.first_digest)<(first_observed_at,first_digest) THEN excluded.first_observed_at ELSE first_observed_at END,
                    first_digest=CASE WHEN (excluded.first_observed_at,excluded.first_digest)<(first_observed_at,first_digest) THEN excluded.first_digest ELSE first_digest END,
                    latest_observed_at=max(latest_observed_at,excluded.latest_observed_at)""", (
                    selected["event_key"], selected["observed_at"], selected["digest"], selected["observed_at"]))
            source.check()
            if source_count % 256 == 0:
                _resource_check(private, path, limits)
        source.check()
        if source_count != sqlite3.Connection.execute(source.connection, "SELECT count(*) FROM main.context_observations").fetchone()[0]:
            raise StorageIntegrityError("complete history did not visit every receipt")
        if opaque_count != len(source.protected):
            raise StorageIntegrityError("history protected reference is absent from the full inventory")
        digest = hashlib.sha256()
        verified_count = verified_used = 0
        for (payload,) in connection.execute("SELECT payload FROM main.history ORDER BY observed_at,digest"):
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
            verified_count += 1
            verified_used += len(payload)
        if (count, used) != (verified_count, verified_used):
            raise StorageIntegrityError("completed history count or canonical byte total changed")
        connection.commit()
        _resource_check(private, path, limits)
        connection.close()
        connection = None
        _companions_absent(path)
        before = _identity(path)
        spool_digest = _hash_file(path, limits.block_bytes)
        if _identity(path) != before or _hash_file(source.path, limits.block_bytes) != input_identity:
            raise StorageIntegrityError("history input or output changed while binding")
        source.check()
        published = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True,
                                    timeout=0, factory=_ReadConnection)
        published._history_poisoned = False
        published._history_bound = False
        published.execute("PRAGMA trusted_schema=OFF")
        published.execute("PRAGMA query_only=ON")
        published.execute("PRAGMA main.cache_size=-8192")
        published.execute("PRAGMA main.mmap_size=0")
        published.execute("PRAGMA temp_store=FILE")
        if published.execute(f"PRAGMA main.max_page_count={max_pages}").fetchone() != (max_pages,):
            raise StorageLimitError("history reader could not preserve its SQLite allocation cap")
        published.execute("BEGIN")
        published.execute("SELECT count(*) FROM main.history").fetchone()
        storage_epoch = _storage_epoch(published)
        published._history_bound = True
        result = object.__new__(HistoryView)
        object.__setattr__(result, "_state", _State(source, published, published.transaction_generation,
                                                 path, before, limits, limits_stamp, storage_epoch))
        object.__setattr__(result, "_binding", HistoryBinding(HISTORY_VERSION, SELECTION_VERSION,
            (SOURCE_SCHEMA, STATUS_SCHEMA), "observed_at,digest", input_identity, source_count,
            opaque_count, tour, decision, decision, count, used, digest.hexdigest(), spool_digest))
        object.__setattr__(result, "_failed", False)
        object.__setattr__(result, "_closed", False)
        object.__setattr__(result, "_owns_connection", True)
        result.assert_intact()
        return result
    except BaseException:
        if published is not None:
            published.close()
        raise
    finally:
        if connection is not None:
            connection.close()
