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
from .sqlite_profile import SQLiteWriterPlan, open_fresh_writer


HISTORY_VERSION = "context-complete-tennis-history-v3"
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
_HISTORY_COLUMNS = "digest,observed_at,event_key,content_digest,mode,canonical_size,canonical_sha,payload"


def _physical_query():
    return context_observations._SELECT.replace(
        "FROM context_observations AS r", "FROM main.context_observations AS r").replace(
        "LEFT JOIN context_contents AS c", "LEFT JOIN main.context_contents AS c")


def _update_bytes(digest, payload, block_bytes):
    # This bounds hashing updates, NOT the actual old reader's allocation.
    # The source decoder and canonical_bytes still hold one complete old value.
    data = memoryview(payload)
    for offset in range(0, len(data), block_bytes):
        digest.update(data[offset:offset + block_bytes])


def _canonical_sha(payload, block_bytes):
    result = hashlib.sha256()
    _update_bytes(result, payload, block_bytes)
    return result.hexdigest()


def _resolve_row(source, stored, *, cutoff, tour, limits):
    """One common build/read resolver on the SAME actual held Source owner.

    Source mode keeps the old object admission contract, bounded by complete
    source/tour limits and the outer native worker envelope, not a new row cap.
    SQL logical index keys may themselves be large old values: they are not
    encoded processing blocks and no SQLITE_LIMIT_LENGTH is installed for them.
    """
    source.check()
    ref, observed, event_key, content, mode, size, sha, payload = stored
    require_digest(ref)
    require_digest(content)
    require_digest(sha)
    require_native_key(event_key, sport="tennis")
    if (type(size) is not int or not 0 < size <= limits.tour_history_bytes
            or canonical_timestamp(observed) != observed or observed > cutoff):
        raise StorageIntegrityError("history locator size or cutoff is invalid")
    if mode == "inline":
        if type(payload) is not bytes or len(payload) > limits.block_bytes:
            raise StorageIntegrityError("inline history row is not a bounded canonical blob")
        row = _decode_object(payload, label="complete history row")
        validate_selected_tennis_receipt(row)
    elif mode == "source":
        if payload is not None or size <= limits.block_bytes or ref in source.protected:
            raise StorageIntegrityError("source history locator has ambiguous mode or protected receipt")
        cursor = sqlite3.Connection.execute(source.connection,
            _physical_query() + " WHERE r.digest=?", (ref,))
        try:
            raw = cursor.fetchone()
        finally:
            cursor.close()
        source.check()
        if raw is None:
            raise StorageIntegrityError("source history receipt is absent")
        decoded = VerifiedReceiptMapping._decode_row(source.receipts, raw)
        source.check()
        selected = select_tennis_observations((decoded,),
            cutoff=datetime.fromisoformat(cutoff), tour=tour)
        if len(selected) != 1:
            raise StorageIntegrityError("source history receipt no longer selects exactly one row")
        row = selected[0]
        payload = canonical_bytes(row)
    else:
        raise StorageIntegrityError("history row has an unknown storage mode")
    if ((row["digest"], row["observed_at"], row["event_key"], row["content_digest"])
            != (ref, observed, event_key, content)
            or row["payload"]["tour"] != tour or len(payload) != size
            or _canonical_sha(payload, limits.block_bytes) != sha):
        raise StorageIntegrityError("history row differs from its complete indexed identity")
    source.check()
    return row, payload


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


def _private_build_directory(root, owned_directory, *, prefix):
    """Known-slot mode or local-only allocation; neither is global admission.

    The native owner MUST supply its already reserved, private empty directory.
    Random local allocations require complete outer enumeration, including all
    failed attempts; an exception note alone is not an inventory or a seal.
    """
    root = Path(root).absolute()
    if not root.is_dir() or root.is_symlink():
        raise StorageIntegrityError("C build allocation root must be an existing real directory")
    if owned_directory is None:
        private = Path(tempfile.mkdtemp(prefix=prefix, dir=root))
        try:
            os.chmod(private, 0o700)
        except BaseException as exc:
            exc.add_note("Failed private C directory allocation retained: " + str(private))
            raise
        return private
    private = Path(owned_directory)
    if not private.is_absolute() or private.parent != root:
        raise StorageIntegrityError("owned C build directory must be an absolute direct child")
    info = private.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or info.st_dev != root.stat().st_dev):
        raise StorageIntegrityError("owned C build directory must be ordinary and on the same device")
    if next(private.iterdir(), None) is not None:
        raise StorageIntegrityError("owned C build directory must be empty; no resume or replacement")
    return private


def _read_policy_epoch(connection):
    return (
        connection.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED),
        connection.getlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS),
        connection.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION),
        connection.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE),
        connection.getconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA),
    )


def _configure_read_connection(connection, plan):
    """Configure a NEW RO connection before TEMP work, never the source owner.

    Reader temp memory remains subject to the outer native AS/RSS limits. The
    exact existing reader types/lifetime checks are not replaced by a wrapper.
    """
    connection.execute("PRAGMA temp_store=MEMORY")  # FIRST SQL on this reader.
    if connection.execute("PRAGMA temp_store").fetchone() != (2,):
        raise StorageIntegrityError("C reader MEMORY temp_store is unavailable")
    cursor = connection.execute("PRAGMA compile_options")
    try:
        rows = cursor.fetchmany(257)
    finally:
        cursor.close()
    if (len(rows) > 256 or any(type(row[0]) is not str or len(row[0]) > 256 for row in rows)
            or [row[0] for row in rows if row[0].startswith("TEMP_STORE=")]
            not in (["TEMP_STORE=1"], ["TEMP_STORE=2"], ["TEMP_STORE=3"])):
        raise StorageIntegrityError("C reader build does not establish effective MEMORY temp_store")
    for category in (sqlite3.SQLITE_LIMIT_ATTACHED, sqlite3.SQLITE_LIMIT_WORKER_THREADS):
        connection.setlimit(category, 0)
    for category, value in (
        (sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, False),
        (sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True),
        (sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False),
    ):
        connection.setconfig(category, value)
    for name, value in (
        ("query_only", 1), ("main.cache_size", -plan.cache_kib),
        ("main.mmap_size", 0), ("main.max_page_count", plan.max_page_count),
        ("threads", 0), ("trusted_schema", 0),
    ):
        connection.execute(f"PRAGMA {name}={value}")
        if connection.execute(f"PRAGMA {name}").fetchone() != (value,):
            raise StorageIntegrityError("C reader could not install its bounded policy: " + name)
    if _read_policy_epoch(connection) != (0, 0, False, True, False):
        raise StorageIntegrityError("C reader attachment/thread/configuration limits are unavailable")


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
                                  "PRAGMA main.max_page_count", "PRAGMA temp_store", "PRAGMA threads"))
    databases = tuple(sqlite3.Connection.execute(connection, "PRAGMA database_list"))
    return schema, databases, _read_policy_epoch(connection)


class HistoryView:
    """A repeated complete, canonical-order view, valid only in its held lifetime.

    The object is deliberately not a tuple and has no public alternate-connection
    constructor. It does not confer HMAC or source/provider completeness approval.
    """
    __slots__ = ("_state", "_binding", "_failed", "_closed", "_owns_connection", "_parent")

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
            if self._parent is not None:
                self._parent.assert_intact()
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
        query = ("SELECT " + _HISTORY_COLUMNS + " FROM main.history WHERE observed_at<=? "
                 + ("AND " + where if where else "") + " ORDER BY observed_at,digest")
        cursor = sqlite3.Connection.execute(self._state.connection, query, (self.cutoff, *arguments))
        try:
            for stored in cursor:
                self.assert_intact()
                row, payload = _resolve_row(self._state.source, stored,
                    cutoff=self.cutoff, tour=self.tour, limits=self._state.limits)
                self.assert_intact()
                del payload
                yield row
                self.assert_intact()
                del row, stored
        except BaseException as error:
            if not isinstance(error, GeneratorExit):
                object.__setattr__(self, "_failed", True)
            raise
        finally:
            cursor.close()
        self.assert_intact()

    def iter_rows(self):
        return self._rows()

    def _receipt(self, ref):
        """Resolve a chosen receipt through this bound view, never caller data."""
        require_digest(ref)
        iterator = self._rows("digest=?", (ref,))
        try:
            row = next(iterator, None)
            if row is None or next(iterator, None) is not None:
                raise StorageIntegrityError("chosen history receipt is absent or ambiguous")
            self.assert_intact()
            return row
        except BaseException:
            object.__setattr__(self, "_failed", True)
            raise
        finally:
            iterator.close()

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
        object.__setattr__(result, "_parent", self)
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
                _update_bytes(digest, len(payload).to_bytes(8, "big"), self._state.limits.block_bytes)
                _update_bytes(digest, payload, self._state.limits.block_bytes)
                del row, payload
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
                  input_identity: str, main_cap_bytes: int, owned_directory=None,
                  limits=DEFAULT_LIMITS) -> HistoryView:
    """Visit the full validated mapping and atomically complete a private spool.

    ``directory`` is an existing QA allocation root. This function never edits
    source data and never returns a partial view. Failed private files are left
    for the caller's bounded cleanup policy, not silently deleted or reused.
    ``main_cap_bytes`` reserves logical main M plus journal M, not a global or
    physical quota. The native owner must pre-admit those and all other slots,
    enforce file/AS/RSS/CPU limits and use a known empty ``owned_directory``.
    Its fixed names are history.sqlite and history.sqlite-journal. Without an
    owned directory this is only a local convenience allocation, to be fully
    enumerated by its caller. Success exposes ``view.path``; failure retains
    the directory and adds its path to the exception, never a budget release.
    """
    limits_stamp = _limits_stamp(limits)
    plan = SQLiteWriterPlan(main_cap_bytes=main_cap_bytes, cache_kib=8192)
    SQLiteWriterPlan._validate_limits(plan, limits)
    select_tennis_observations((), cutoff=cutoff, tour=tour)
    decision = canonical_timestamp(cutoff)
    source = _source(receipts, input_identity, limits)
    allocation_root = Path(directory)
    if not allocation_root.is_dir() or allocation_root.is_symlink():
        raise StorageIntegrityError("history allocation root must be an existing directory")
    if shutil.disk_usage(allocation_root).free < limits.min_free_bytes:
        raise StorageLimitError("history build lacks its free-space reserve")
    private = _private_build_directory(allocation_root, owned_directory, prefix="context-history-")
    path = private / "history.sqlite"
    writer = None
    published = None
    try:
        writer = open_fresh_writer(path, plan=plan, limits=limits)
        connection = writer.connection  # Exact TrackedConnection; BEGIN precedes all DDL.

        def check_build():
            writer.check_profile()
            _resource_check(private, path, limits)

        check_build()
        connection.execute("CREATE TABLE main.history(digest TEXT PRIMARY KEY, observed_at TEXT NOT NULL, event_key TEXT NOT NULL, content_digest TEXT NOT NULL, mode TEXT NOT NULL, canonical_size INTEGER NOT NULL, canonical_sha TEXT NOT NULL, payload BLOB) WITHOUT ROWID")
        connection.execute("CREATE INDEX main.history_order ON history(observed_at,digest)")
        connection.execute("CREATE INDEX main.history_event_order ON history(event_key,observed_at,digest)")
        connection.execute("CREATE TABLE main.events(event_key TEXT PRIMARY KEY, first_observed_at TEXT NOT NULL, first_digest TEXT NOT NULL, latest_observed_at TEXT NOT NULL) WITHOUT ROWID")
        connection.execute("CREATE INDEX main.events_order ON events(first_observed_at,first_digest)")
        connection.execute("CREATE TABLE main.seen(digest TEXT PRIMARY KEY) WITHOUT ROWID")
        check_build()
        count = used = source_count = opaque_count = 0
        # No SQL cutoff/tour filter: corrupt future/foreign physical records may
        # not hide behind metadata. The unchanged source selector owns causality.
        # Preserve the physical owner's column projection, qualifying only its
        # two actual source tables; TEMP names must never change resolution.
        for raw in sqlite3.Connection.execute(source.connection, _physical_query()):
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
                    check_build()
                del row, raw
                continue
            if "source_schema" not in row:
                raise StorageIntegrityError("unprotected receipt has no physical source schema")
            for selected in select_tennis_observations((row,), cutoff=cutoff, tour=tour):
                payload = canonical_bytes(selected)
                used += len(payload)
                if used > limits.tour_history_bytes:
                    raise StorageLimitError("complete Tennis history exceeds v2 canonical budget")
                count += 1
                inline = len(payload) <= limits.block_bytes
                connection.execute("INSERT INTO main.history VALUES (?,?,?,?,?,?,?,?)", (
                    selected["digest"], selected["observed_at"], selected["event_key"],
                    selected["content_digest"], "inline" if inline else "source", len(payload),
                    _canonical_sha(payload, limits.block_bytes), payload if inline else None))
                connection.execute("""INSERT INTO main.events VALUES (?,?,?,?)
                    ON CONFLICT(event_key) DO UPDATE SET
                    first_observed_at=CASE WHEN (excluded.first_observed_at,excluded.first_digest)<(first_observed_at,first_digest) THEN excluded.first_observed_at ELSE first_observed_at END,
                    first_digest=CASE WHEN (excluded.first_observed_at,excluded.first_digest)<(first_observed_at,first_digest) THEN excluded.first_digest ELSE first_digest END,
                    latest_observed_at=max(latest_observed_at,excluded.latest_observed_at)""", (
                    selected["event_key"], selected["observed_at"], selected["digest"], selected["observed_at"]))
                del selected, payload
            source.check()
            del row, raw
            if source_count % 256 == 0:
                check_build()
        source.check()
        if source_count != sqlite3.Connection.execute(source.connection, "SELECT count(*) FROM main.context_observations").fetchone()[0]:
            raise StorageIntegrityError("complete history did not visit every receipt")
        if opaque_count != len(source.protected):
            raise StorageIntegrityError("history protected reference is absent from the full inventory")
        digest = hashlib.sha256()
        verified_count = verified_used = 0
        for stored in connection.execute("SELECT " + _HISTORY_COLUMNS + " FROM main.history ORDER BY observed_at,digest"):
            writer.check_profile()
            resolved, payload = _resolve_row(source, stored, cutoff=decision, tour=tour, limits=limits)
            writer.check_profile()
            _update_bytes(digest, len(payload).to_bytes(8, "big"), limits.block_bytes)
            _update_bytes(digest, payload, limits.block_bytes)
            verified_count += 1
            verified_used += len(payload)
            del resolved, payload
            if verified_count % 256 == 0:
                check_build()
        if (count, used) != (verified_count, verified_used):
            raise StorageIntegrityError("completed history count or canonical byte total changed")
        source.check()
        check_build()  # Reserve/profile failure must precede the only build commit.
        writer.commit_build()  # Closes all normal writer cursors/blobs/connection/FD.
        _resource_check(private, path, limits)
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
        _configure_read_connection(published, plan)
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
        object.__setattr__(result, "_parent", None)
        result.assert_intact()
        return result
    except BaseException as exc:
        exc.add_note("Unpublished or failed C history directory retained: " + str(private))
        if published is not None:
            published.close()
        raise
    finally:
        if writer is not None:
            writer.close()
