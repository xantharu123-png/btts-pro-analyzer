"""Small complete private copy -> receipt append -> cold verification owner.

There is no public writer, existing-path admission, resume, or CopyReceipt
authorization API. The only writable main is the fresh copy created inside this
one call. FreshSQLiteWriter and the old product owners remain unchanged.

OWNER PRECONDITIONS: the source is genuinely sealed and its profiled reader is
held throughout. The reserved output namespace is private, exclusive and
quiescent throughout every pathname open and close/reopen transition. Python
callbacks, converters/adapters, foreign connections, concurrent writers, raw
base-class bypasses and ABA are excluded by the outer closed catalogue, not by
a claimed Python sandbox. Receipt normalization does not certify source truth.

Main M, DELETE journal M and ledger L are explicit logical reservations. The
ledger uses two bounded merge regions INSIDE L, not another file or SQL TEMP
table. Native FSIZE, CPU/AS/RSS, all-job accounting and physical allocation
overhead remain caller obligations. Named workspace/free-space checks are
observations, not a disk quota. This single-call chain is NOT a 490k-record
portion/resume owner, a native capacity pass, a VerifiedReceiptMapping or B.
Failed outputs are always retained. SQLite may remove its own DELETE journal.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import struct
import time
import weakref

from context_models.contracts import canonical_timestamp, digest, normalize_observation
from context_runtime_transaction import TrackedConnection, TrackedCursor

from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError, StorageLimits
from .copying import (
    _configure_copy_reader, _check_copy_reader, _copy_directory, _directory_identity,
    _file_identity, _hash_file, _no_companions, _workspace_bytes, copy_legacy,
)
from .inventory import RawInventory, _HeldRead, _TABLES, _field_hash, inventory_raw
from .receipt_append import append_observation_in_connection
from .sqlite_profile import SQLiteWriterPlan, _identity, _not_link, _parents


_RECORD = struct.Struct(">Bq32s")
_HEADER = struct.Struct(">16sQQB7x")
_MAGIC = b"BBCORPUS-ADD-v1\0\0"
_ADDITIONS = {1: "context_contents", 2: "context_observations"}
_MAX_SECONDS = 300
_METADATA_BYTES = 65536
_MAX_HANDLES = 256


@dataclass(frozen=True)
class ReceiptCorpusResult:
    """Closed, observed result data; never a seal or reusable authorization."""
    path: Path
    ledger_path: Path
    source_sha256: str
    output_sha256: str
    ledger_sha256: str
    source_inventory: RawInventory
    inventory: RawInventory
    submitted_observations: int
    new_contents: int
    new_receipts: int
    main_bytes: int
    ledger_bytes: int
    page_size: int
    encoding: str


def _query(connection, sql, parameters=(), *, max_rows=1):
    cursor = connection.cursor()
    try:
        cursor.row_factory = None
        cursor.execute(sql, parameters)
        result = cursor.fetchmany(max_rows + 1)
        if len(result) > max_rows:
            raise StorageIntegrityError("corpus metadata query exceeded its bound")
        return result
    finally:
        cursor.close()


def _value(connection, name):
    rows = _query(connection, "PRAGMA " + name)
    if len(rows) != 1 or len(rows[0]) != 1:
        raise StorageIntegrityError("corpus profile readback is unavailable")
    return rows[0][0]


def _close_connection(connection):
    try:
        TrackedConnection.close(connection)
    except BaseException:
        # A failed tracked boundary must still dispose our native connection.
        # This fallback grants no writer/transaction bypass to any caller.
        sqlite3.Connection.close(connection)
        raise


def _close_owned_fd(descriptor, identity):
    try:
        os.close(descriptor)
    except BaseException as original:
        # A reported close failure may already have released the number. In
        # the caller's exclusive, quiescent closure, retry only an FD which
        # still names our recorded inode, never a blindly reused descriptor.
        try:
            if identity is not None and _identity(os.fstat(descriptor)) == identity:
                os.close(descriptor)
        except BaseException as cleanup:
            original.add_note("owned FD cleanup readback/retry was uncertain: " + type(cleanup).__name__)
        raise


def _row_query(connection, table, *, block_bytes, rowid=None):
    columns = _TABLES[table]
    small = " + ".join(f'coalesce(octet_length("{name}"),0)' for name, _, _ in columns) + " <= ?"
    expressions = ["rowid"]
    for name, kind, _ in columns:
        value = f'"{name}"' if kind == "integer" else f'CAST("{name}" AS BLOB)'
        expressions += [f'typeof("{name}")', f'octet_length("{name}")',
                        f'CASE WHEN {small} THEN {value} ELSE NULL END']
    sql = f'SELECT {", ".join(expressions)} FROM main."{table}"'
    parameters = (block_bytes,) * len(columns)
    if rowid is not None:
        sql += " WHERE rowid=?"
        parameters += (rowid,)
    else:
        sql += " ORDER BY rowid"
    cursor = connection.cursor()
    try:
        cursor.row_factory = None
        cursor.execute(sql, parameters)
        return cursor
    except BaseException:
        cursor.close()
        raise


def _row_hash(connection, guard, table, raw, limits):
    if raw is None or type(raw[0]) is not int:
        raise StorageIntegrityError("corpus row is missing or has an invalid rowid")
    result = hashlib.sha256(b"betboy-context-v2-row\0")
    for index, (name, expected, nullable) in enumerate(_TABLES[table]):
        kind, size, value = raw[1 + index * 3:4 + index * 3]
        if kind != expected and not (nullable and kind == "null"):
            raise StorageIntegrityError("corpus row changed its SQLite storage type")
        _field_hash(connection, guard, table, raw[0], name, kind, size, value, result, limits)
    return result.digest()


class _Build:
    """Private state of exactly one call, never a public existing-main opener."""
    def __init__(self, source, workspace, owned_directory, main_cap_bytes, ledger_cap_bytes, limits):
        self.source, self.limits = source, limits
        self.deadline = time.monotonic() + _MAX_SECONDS
        if type(limits) is not StorageLimits:
            raise StorageLimitError("corpus requires exact C limits")
        StorageLimits.__post_init__(limits)
        self.limit_values = tuple(getattr(limits, field.name) for field in fields(StorageLimits))
        if (type(ledger_cap_bytes) is not int or not _HEADER.size <= ledger_cap_bytes <= limits.input_bytes):
            raise StorageLimitError("corpus ledger requires an explicit bounded file reservation")
        self.ledger_cap = ledger_cap_bytes
        if type(source) is not TrackedConnection:
            raise StorageIntegrityError("corpus requires its exact held source connection")
        databases = _query(source, "PRAGMA database_list", max_rows=2)
        mains = [row[2] for row in databases if row[1] == "main"]
        if len(mains) != 1 or not mains[0]:
            raise StorageIntegrityError("corpus source must be an on-disk held main")
        self.source_path = Path(mains[0])
        self.source_identity = _file_identity(self.source_path)
        _no_companions(self.source_path)
        # A RO SQLite schema read may itself create WAL/SHM companions. Refuse
        # the actual WAL header BEFORE _HeldRead performs any schema/page SQL.
        with self.source_path.open("rb") as stream:
            header = stream.read(100)
        if (len(header) != 100 or header[:16] != b"SQLite format 3\0"
                or header[18:20] != b"\x01\x01"):
            raise StorageIntegrityError("corpus requires a standalone rollback-mode source header")
        if _file_identity(self.source_path) != self.source_identity:
            raise StorageIntegrityError("corpus source changed during header admission")
        self.guard = _HeldRead(source)
        self.page_size, self.encoding = _value(source, "main.page_size"), _value(source, "main.encoding")
        self.plan = SQLiteWriterPlan(main_cap_bytes, page_size=self.page_size, cache_kib=8192)
        SQLiteWriterPlan._validate_limits(self.plan, limits)
        if ledger_cap_bytes > main_cap_bytes:
            raise StorageLimitError("corpus ledger must fit the same native FSIZE=M envelope")
        if self.encoding not in {"UTF-8", "UTF-16le", "UTF-16be"} or _value(source, "main.auto_vacuum") != 0:
            raise StorageIntegrityError("corpus source has an unsupported existing page format")
        if (self.source_identity[4] > main_cap_bytes
                or self.source_identity[4] + main_cap_bytes + ledger_cap_bytes > limits.input_bytes):
            raise StorageLimitError("corpus source, main and ledger exceed combined active input admission")
        self.workspace, self.directory = Path(workspace), Path(owned_directory)
        self.workspace_identity = _directory_identity(self.workspace)
        _copy_directory(self.workspace, self.directory)  # Existing, empty fixed slot only.
        self.directory_identity = _directory_identity(self.directory)
        self.path = self.directory / "legacy-copy.sqlite"
        self.ledger_path = self.directory / "receipt-additions.bin"
        self.parents = _parents(self.path)
        self.connection = self.reader = self.ledger = None
        self.fd = None
        self.file_identity = self.journal_identity = None
        self.closed_main_identity = None
        self.handles = weakref.WeakSet()
        self.generation = None
        self.source_inventory = None
        self.submitted = self.new_contents = self.new_receipts = 0
        self.capacity()

    def source_check(self):
        StorageLimits.__post_init__(self.limits)
        if tuple(getattr(self.limits, field.name) for field in fields(StorageLimits)) != self.limit_values:
            raise StorageLimitError("corpus limits changed during the build")
        if time.monotonic() > self.deadline:
            raise StorageLimitError("corpus exceeded its original single-call deadline")
        self.guard.check()
        if _file_identity(self.source_path) != self.source_identity:
            raise StorageIntegrityError("corpus source file changed")
        _no_companions(self.source_path)
        if (_directory_identity(self.workspace) != self.workspace_identity
                or _directory_identity(self.directory) != self.directory_identity):
            raise StorageIntegrityError("corpus workspace or allocation directory changed")
        for parent, identity in self.parents:
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or not _not_link(info) or _identity(info) != identity:
                raise StorageIntegrityError("corpus parent identity changed")

    def namespace(self, *, journal=True):
        self.source_check()
        sizes = {"main": 0, "journal": 0, "ledger": 0}
        expected = {"legacy-copy.sqlite"}
        if self.ledger is not None:
            expected.add("receipt-additions.bin")
        if journal:
            expected.add("legacy-copy.sqlite-journal")
        with os.scandir(self.directory) as entries:
            for entry in entries:
                if entry.name not in expected:
                    raise StorageIntegrityError("corpus contains an unexpected file or sidecar")
                info = Path(entry.path).lstat()
                if (not stat.S_ISREG(info.st_mode) or not _not_link(info) or info.st_nlink != 1
                        or info.st_dev != self.directory_identity[0]):
                    raise StorageIntegrityError("corpus file is not an ordinary private inode")
                key = "main" if entry.name == "legacy-copy.sqlite" else "ledger" if entry.name == "receipt-additions.bin" else "journal"
                sizes[key] = info.st_size
                if key == "journal":
                    if self.journal_identity is not None and _identity(info) != self.journal_identity:
                        raise StorageIntegrityError("corpus rollback journal identity changed")
                    self.journal_identity = _identity(info)
        if sizes["main"] > self.plan.main_cap_bytes or sizes["journal"] > self.plan.main_cap_bytes or sizes["ledger"] > self.ledger_cap:
            raise StorageLimitError("corpus file exceeded its reserved logical slot")
        if self.fd is not None:
            held, named = os.fstat(self.fd), self.path.lstat()
            if (_identity(held) != self.file_identity or _identity(named) != self.file_identity
                    or held.st_nlink != 1 or named.st_nlink != 1 or held.st_size != named.st_size
                    or held.st_mode != named.st_mode):
                raise StorageIntegrityError("corpus main descriptor/path binding changed")
        elif self.file_identity is not None:
            if _identity(self.path.lstat()) != self.file_identity:
                raise StorageIntegrityError("corpus closed main pathname was replaced")
        if self.closed_main_identity is not None and _file_identity(self.path) != self.closed_main_identity:
            raise StorageIntegrityError("corpus closed main changed across its read-only transition")
        if (self.ledger is not None and self.ledger.final_identity is not None
                and _file_identity(self.ledger_path) != self.ledger.final_identity):
            raise StorageIntegrityError("corpus finished ledger pathname or bytes changed")
        return sizes

    def capacity(self):
        sizes = self.namespace() if self.file_identity is not None else {"main": 0, "journal": 0, "ledger": 0}
        self.source_check()
        remaining = (self.plan.main_cap_bytes - sizes["main"]
                     + self.plan.main_cap_bytes - sizes["journal"]
                     + self.ledger_cap - sizes["ledger"] + _METADATA_BYTES)
        if _workspace_bytes(self.workspace) + remaining > self.limits.workspace_bytes:
            raise StorageLimitError("corpus main/journal/ledger and whole workspace exceed reservation")
        if shutil.disk_usage(self.workspace).free < self.limits.min_free_bytes + remaining:
            raise StorageLimitError("corpus cannot retain its reserved future bytes and free reserve")
        self.source_check()

    def _register_handles(self):
        connection = self.connection
        def capacity():
            if len(self.handles) >= _MAX_HANDLES:
                raise StorageLimitError("corpus retained too many SQLite handles")
        def cursor(factory=TrackedCursor):
            capacity()
            result = TrackedConnection.cursor(connection, factory)
            self.handles.add(result)
            return result
        def blobopen(*args, **kwargs):
            capacity()
            result = sqlite3.Connection.blobopen(connection, *args, **kwargs)
            self.handles.add(result)
            return result
        self.cursor_method, self.blob_method = cursor, blobopen
        connection.cursor, connection.blobopen = cursor, blobopen

    def open_copied_writer(self, sealed_sha256):
        # The only caller is run(), immediately after its own actual C1 copy.
        # No existing path or CopyReceipt can be supplied to the public API.
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
        self.fd = os.open(self.path, flags)
        info = os.fstat(self.fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise StorageIntegrityError("corpus copied main is not a held ordinary file")
        self.file_identity = _identity(info)
        self.namespace(journal=False)
        if _hash_file(self.path, self.limits.block_bytes, self.source_check) != sealed_sha256:
            raise StorageIntegrityError("corpus newly copied image changed before writable open")
        self.connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
            factory=TrackedConnection, timeout=0, isolation_level=None,
            autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL, cached_statements=0)
        if type(self.connection) is not TrackedConnection or self.connection.in_transaction:
            raise StorageIntegrityError("corpus writer requires a new exact tracked connection")
        self._register_handles()
        self.namespace(journal=False)
        _query(self.connection, "PRAGMA temp_store=MEMORY")  # FIRST SQL.
        if _value(self.connection, "temp_store") != 2:
            raise StorageIntegrityError("corpus effective MEMORY temp_store is unavailable")
        options = _query(self.connection, "PRAGMA compile_options", max_rows=256)
        if (any(len(row) != 1 or type(row[0]) is not str or len(row[0]) > 256 for row in options)
                or [row[0] for row in options if row[0].startswith("TEMP_STORE=")]
                not in (["TEMP_STORE=1"], ["TEMP_STORE=2"], ["TEMP_STORE=3"])):
            raise StorageIntegrityError("corpus SQLite build does not establish MEMORY TEMP")
        for category in (sqlite3.SQLITE_LIMIT_ATTACHED, sqlite3.SQLITE_LIMIT_WORKER_THREADS):
            self.connection.setlimit(category, 0)
        self.configs = ((sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, False),
                        (sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True),
                        (sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False))
        for category, value in self.configs:
            self.connection.setconfig(category, value)
        for statement in (
            "PRAGMA main.journal_mode=DELETE", "PRAGMA main.synchronous=FULL",
            "PRAGMA main.cache_size=-8192", "PRAGMA main.mmap_size=0",
            f"PRAGMA main.max_page_count={self.plan.max_page_count}", "PRAGMA threads=0",
            "PRAGMA main.locking_mode=NORMAL", "PRAGMA main.journal_size_limit=0",
            "PRAGMA main.cache_spill=ON", "PRAGMA busy_timeout=0", "PRAGMA query_only=OFF",
        ):
            self.namespace(journal=False)
            _query(self.connection, statement)
        # Never SET page_size, encoding, auto_vacuum or schema on this copy.
        self.expected = {"temp_store": 2, "main.journal_mode": "delete", "main.synchronous": 2,
            "main.page_size": self.page_size, "main.encoding": self.encoding, "main.auto_vacuum": 0,
            "main.cache_size": -8192, "main.mmap_size": 0, "main.max_page_count": self.plan.max_page_count,
            "threads": 0, "main.locking_mode": "normal", "main.journal_size_limit": 0,
            "busy_timeout": 0, "query_only": 0, "trusted_schema": 0,
            "main.user_version": 0, "main.application_id": 0,
            "main.schema_version": _value(self.source, "main.schema_version"),
            "cache_spill": _value(self.connection, "cache_spill")}
        if type(self.expected["cache_spill"]) is not int or self.expected["cache_spill"] <= 0:
            raise StorageIntegrityError("corpus cache spilling is unavailable")
        self.check_profile(active=False)
        _query(self.connection, "BEGIN IMMEDIATE")
        self.generation = self.connection.transaction_generation
        self.check()

    def check_profile(self, *, active):
        self.namespace(journal=active)
        connection = self.connection
        if (type(connection) is not TrackedConnection or connection.row_factory is not None
                or connection.text_factory is not str or connection.isolation_level is not None
                or connection.autocommit != sqlite3.LEGACY_TRANSACTION_CONTROL
                or connection.cursor is not self.cursor_method or connection.blobopen is not self.blob_method):
            raise StorageIntegrityError("corpus writer policy changed")
        if connection.in_transaction is not active or (active and connection.transaction_generation != self.generation):
            raise StorageIntegrityError("corpus build transaction ended or changed")
        databases = _query(connection, "PRAGMA database_list", max_rows=2)
        if (not databases or databases[0][1:] != ("main", str(self.path))
                or (len(databases) == 2 and databases[1][1:] != ("temp", ""))
                or _query(connection, "SELECT 1 FROM temp.sqlite_schema LIMIT 1")):
            raise StorageIntegrityError("corpus database namespace changed")
        for name, expected in self.expected.items():
            value = _value(connection, name)
            if type(value) is not type(expected) or value != expected:
                raise StorageIntegrityError("corpus writer readback changed: " + name)
        for category in (sqlite3.SQLITE_LIMIT_ATTACHED, sqlite3.SQLITE_LIMIT_WORKER_THREADS):
            if connection.getlimit(category) != 0:
                raise StorageIntegrityError("corpus attach/thread limit changed")
        for category, expected in self.configs:
            if connection.getconfig(category) is not expected:
                raise StorageIntegrityError("corpus SQLite configuration changed")
        count = _value(connection, "main.page_count")
        if type(count) is not int or not 1 <= count <= self.plan.max_page_count:
            raise StorageLimitError("corpus main exceeded its page ceiling")
        if connection.in_transaction is not active or (active and connection.transaction_generation != self.generation):
            raise StorageIntegrityError("corpus writer changed during profile readback")
        self.namespace(journal=active)

    def check(self):
        self.check_profile(active=True)
        self.capacity()

    def close_writer(self, *, commit=False):
        errors = []
        connection = self.connection
        try:
            if connection is not None:
                try:
                    for handle in tuple(self.handles):
                        try:
                            if isinstance(handle, sqlite3.Cursor):
                                sqlite3.Cursor.close(handle)
                            else:
                                sqlite3.Blob.close(handle)
                        except BaseException as exc:
                            errors.append(exc)
                    self.handles.clear()
                    if commit and not errors:
                        self.check()
                        TrackedConnection.commit(connection)  # The single build commit.
                        self.check_profile(active=False)
                    elif connection.in_transaction:
                        TrackedConnection.rollback(connection)
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    try:
                        _close_connection(connection)
                    except BaseException as exc:
                        errors.append(exc)
                    self.connection = None
        finally:
            if self.fd is not None:
                if commit and not errors:
                    try:
                        self.namespace(journal=False)
                        self.closed_main_identity = _file_identity(self.path)
                    except BaseException as exc:
                        errors.append(exc)
                descriptor, self.fd = self.fd, None
                try:
                    _close_owned_fd(descriptor, self.file_identity)
                except BaseException as exc:
                    errors.append(exc)
        if errors:
            raise StorageIntegrityError("corpus commit/close did not finish cleanly") from errors[0]

    def append_one(self, item):
        self.check()
        if type(item) is not tuple or len(item) != 2:
            raise StorageIntegrityError("corpus iterator must yield exact (record, observed_at) pairs")
        record, clock = item
        normalized = normalize_observation(record, observed_at=clock)
        content_hash = digest(normalized)
        receipt_hash = digest({"content_digest": content_hash, "observed_at": canonical_timestamp(clock)})
        self.check()
        keys = ((1, "context_contents", "content_digest", content_hash),
                (2, "context_observations", "digest", receipt_hash))
        new = []  # At most TWO scalar keys, never a corpus/input list.
        for tag, table, column, key in keys:
            if not _query(self.connection, f'SELECT rowid FROM main."{table}" WHERE "{column}"=?', (key,)):
                new.append((tag, table, column, key))
        self.ledger.admit(len(new))
        actual = append_observation_in_connection(self.connection, normalized, observed_at=clock)
        if actual != receipt_hash:
            raise StorageIntegrityError("corpus actual append identity differs from normalized input")
        self.check()
        for tag, table, column, key in new:
            row = _query(self.connection, f'SELECT rowid FROM main."{table}" WHERE "{column}"=?', (key,))
            if len(row) != 1 or type(row[0][0]) is not int:
                raise StorageIntegrityError("corpus new append has no actual physical row")
            cursor = _row_query(self.connection, table, block_bytes=self.limits.block_bytes, rowid=row[0][0])
            try:
                actual_hash = _row_hash(self.connection, self, table, cursor.fetchone(), self.limits)
            finally:
                cursor.close()
            self.ledger.append(tag, row[0][0], actual_hash)
            if tag == 1:
                self.new_contents += 1
            else:
                self.new_receipts += 1
        self.submitted += 1
        self.check()

    def verify_complete(self):
        self.source_check()
        self.namespace(journal=False)
        identity = _file_identity(self.path)
        self.reader = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True,
            factory=TrackedConnection, timeout=0, isolation_level=None,
            autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL, cached_statements=0)
        if identity[4] % self.page_size:
            raise StorageIntegrityError("corpus terminal image is not complete pages")
        pages = identity[4] // self.page_size
        _configure_copy_reader(self.reader, page_size=self.page_size, page_count=pages)
        self.reader.execute("BEGIN").close()
        output_guard = _HeldRead(self.reader)
        actual_source = inventory_raw(self.source, limits=self.limits)
        actual_output = inventory_raw(self.reader, limits=self.limits)
        if (actual_source != self.source_inventory or actual_output.schema_digest != actual_source.schema_digest
                or [table.name for table in actual_output.tables] != [table.name for table in actual_source.tables]):
            raise StorageIntegrityError("corpus complete source/schema identity changed")
        ledger = iter(self.ledger.records())
        addition = next(ledger, None)
        additions_seen = {1: 0, 2: 0}
        ordered_tables = sorted(_TABLES, key=lambda table: (next((tag for tag, name in _ADDITIONS.items() if name == table), 0), table))
        present = {table.name for table in actual_source.tables}
        for table in ordered_tables:
            if table not in present:
                continue
            tag = next((tag for tag, name in _ADDITIONS.items() if name == table), 0)
            old = _row_query(self.source, table, block_bytes=self.limits.block_bytes)
            new = None
            try:
                new = _row_query(self.reader, table, block_bytes=self.limits.block_bytes)
                left, right = old.fetchone(), new.fetchone()
                while left is not None or right is not None:
                    self.source_check()
                    output_guard.check()
                    if right is None or (left is not None and left[0] < right[0]):
                        raise StorageIntegrityError("corpus lost an old physical row")
                    actual_hash = _row_hash(self.reader, output_guard, table, right, self.limits)
                    if left is not None and left[0] == right[0]:
                        if _row_hash(self.source, self.guard, table, left, self.limits) != actual_hash:
                            raise StorageIntegrityError("corpus changed an old typed raw row")
                        left = old.fetchone()
                    else:
                        if tag == 0 or addition != (tag, right[0], actual_hash):
                            raise StorageIntegrityError("corpus extra row differs from actual append membership")
                        additions_seen[tag] += 1
                        addition = next(ledger, None)
                    right = new.fetchone()
            finally:
                try:
                    old.close()
                finally:
                    if new is not None:
                        new.close()
        if addition is not None or additions_seen != {1: self.new_contents, 2: self.new_receipts}:
            raise StorageIntegrityError("corpus append ledger is not completely represented")
        self.source_check()
        output_guard.check()
        _check_copy_reader(self.reader, page_size=self.page_size, page_count=pages)
        if _file_identity(self.path) != identity:
            raise StorageIntegrityError("corpus terminal image changed during verification")
        return actual_output, identity

    def run(self, observations, expected_source_sha256):
        try:
            copied = copy_legacy(self.source, directory=self.workspace, owned_directory=self.directory,
                                 expected_source_sha256=expected_source_sha256, limits=self.limits)
            if copied.path != self.path or copied.source_sha256 != expected_source_sha256:
                raise StorageIntegrityError("corpus own copy returned an inconsistent identity")
            self.source_inventory = copied.inventory
            if not {"context_contents", "context_observations"} <= {table.name for table in copied.inventory.tables}:
                raise StorageIntegrityError("corpus source lacks its existing complete receipt schema")
            self.source_check()
            self.open_copied_writer(expected_source_sha256)
            self.ledger = _Ledger(self)
            for item in observations:
                self.append_one(item)
                del item
            self.check()
            self.ledger.finish()
            self.check()
            self.close_writer(commit=True)
            inventory, terminal_identity = self.verify_complete()
            output_hash = _hash_file(self.path, self.limits.block_bytes, self.source_check)
            if _file_identity(self.path) != terminal_identity:
                raise StorageIntegrityError("corpus image changed after complete readback")
            if _hash_file(self.source_path, self.limits.block_bytes, self.source_check) != expected_source_sha256:
                raise StorageIntegrityError("corpus source bytes changed before completion")
            ledger_hash, ledger_bytes = self.ledger.digest()
            _close_connection(self.reader)
            self.reader = None
            self.ledger.close()
            self.source_check()
            self.namespace(journal=False)
            self.capacity()
            return ReceiptCorpusResult(self.path, self.ledger_path, expected_source_sha256,
                output_hash, ledger_hash, self.source_inventory, inventory, self.submitted,
                self.new_contents, self.new_receipts, terminal_identity[4], ledger_bytes,
                self.page_size, self.encoding)
        except BaseException as exc:
            exc.add_note("Unpublished corpus files retained: " + str(self.directory))
            if isinstance(exc, sqlite3.DatabaseError):
                if getattr(exc, "sqlite_errorcode", None) in (sqlite3.SQLITE_FULL, sqlite3.SQLITE_TOOBIG):
                    raise StorageLimitError("corpus hit SQLite's hard allocation limit") from exc
                raise StorageIntegrityError("corpus SQLite lifecycle failed") from exc
            raise
        finally:
            errors = []
            try:
                self.close_writer()
            except BaseException as exc:
                errors.append(exc)
            if self.reader is not None:
                try:
                    _close_connection(self.reader)
                except BaseException as exc:
                    errors.append(exc)
                self.reader = None
            if self.ledger is not None:
                try:
                    self.ledger.close()
                except BaseException as exc:
                    errors.append(exc)
            if errors:
                raise StorageIntegrityError("corpus final cleanup failed; abandon the entire build") from errors[0]


class _Ledger:
    """Fixed entries; bounded external merge, two regions in one reserved file."""
    def __init__(self, build):
        self.build, self.fd = build, None
        self.identity = None
        self.capacity = (build.ledger_cap - _HEADER.size) // (2 * _RECORD.size)
        self.count, self.bank = 0, 0
        self.block = max(_RECORD.size, min(build.limits.block_bytes, 1024**2))
        self.append_hash = hashlib.sha256()
        self.final_identity = None
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
        self.fd = os.open(build.ledger_path, flags, 0o600)
        try:
            self.identity = _identity(os.fstat(self.fd))
            self._write(0, self._header())
        except BaseException:
            self.close()
            raise

    def _header(self):
        return _HEADER.pack(_MAGIC, self.capacity, self.count, self.bank)

    def _check(self):
        self.build.source_check()
        held, named = os.fstat(self.fd), self.build.ledger_path.lstat()
        if (not stat.S_ISREG(named.st_mode) or not _not_link(named)
                or _identity(held) != self.identity or _identity(named) != self.identity
                or held.st_nlink != 1 or named.st_nlink != 1 or held.st_size != named.st_size
                or held.st_size > self.build.ledger_cap):
            raise StorageIntegrityError("corpus ledger descriptor/path binding changed")
        if self.final_identity is not None and _file_identity(self.build.ledger_path) != self.final_identity:
            raise StorageIntegrityError("corpus finished ledger changed")

    def _write(self, offset, data):
        if offset < 0 or offset + len(data) > self.build.ledger_cap:
            raise StorageLimitError("corpus ledger exceeded its reserved file regions")
        self._check()
        os.lseek(self.fd, offset, os.SEEK_SET)
        view = memoryview(data)
        while view:
            self._check()
            count = os.write(self.fd, view[:self.block])
            if type(count) is not int or not 0 < count <= min(len(view), self.block):
                raise StorageIntegrityError("corpus ledger write made invalid progress")
            view = view[count:]
        self._check()

    def _read(self, offset, size):
        if size < 0 or size > self.block or offset < 0 or offset + size > self.build.ledger_cap:
            raise StorageIntegrityError("corpus ledger read exceeds its bounded region")
        self._check()
        os.lseek(self.fd, offset, os.SEEK_SET)
        result = bytearray()
        while len(result) < size:
            self._check()
            part = os.read(self.fd, size - len(result))
            if not part:
                raise StorageIntegrityError("corpus ledger was truncated")
            result.extend(part)
        self._check()
        return bytes(result)

    def _offset(self, bank, index):
        return _HEADER.size + (bank * self.capacity + index) * _RECORD.size

    def admit(self, count):
        if self.count + count > self.capacity:
            raise StorageLimitError("corpus ledger merge-region capacity exceeded")

    def append(self, table, rowid, row_hash):
        self.admit(1)
        if table not in _ADDITIONS or type(rowid) is not int or type(row_hash) is not bytes or len(row_hash) != 32:
            raise StorageIntegrityError("corpus append ledger has an invalid typed entry")
        raw = _RECORD.pack(table, rowid, row_hash)
        self._write(self._offset(0, self.count), raw)
        self.append_hash.update(raw)
        self.count += 1

    def _entries(self, bank, start, stop):
        per_block = self.block // _RECORD.size
        while start < stop:
            count = min(per_block, stop - start)
            raw = self._read(self._offset(bank, start), count * _RECORD.size)
            for entry in _RECORD.iter_unpack(raw):
                if entry[0] not in _ADDITIONS:
                    raise StorageIntegrityError("corpus ledger has an unknown table tag")
                yield entry
            start += count

    def finish(self):
        original = hashlib.sha256()
        for entry in self._entries(0, 0, self.count):
            original.update(_RECORD.pack(*entry))
        if original.digest() != self.append_hash.digest():
            raise StorageIntegrityError("corpus actual append ledger changed before sorting")
        run = self.block // _RECORD.size
        for start in range(0, self.count, run):
            entries = sorted(self._entries(0, start, min(start + run, self.count)), key=lambda entry: entry[:2])
            self._write(self._offset(1, start), b"".join(_RECORD.pack(*entry) for entry in entries))
        self.bank = 1 if self.count else 0
        while run < self.count:
            destination = 1 - self.bank
            for start in range(0, self.count, run * 2):
                middle, stop = min(start + run, self.count), min(start + 2 * run, self.count)
                left = iter(self._entries(self.bank, start, middle))
                right = iter(self._entries(self.bank, middle, stop))
                a, b = next(left, None), next(right, None)
                index, buffer = start, bytearray()
                while a is not None or b is not None:
                    if b is None or (a is not None and a[:2] <= b[:2]):
                        chosen, a = a, next(left, None)
                    else:
                        chosen, b = b, next(right, None)
                    buffer.extend(_RECORD.pack(*chosen))
                    if len(buffer) + _RECORD.size > self.block:
                        self._write(self._offset(destination, index), buffer)
                        index += len(buffer) // _RECORD.size
                        buffer.clear()
                if buffer:
                    self._write(self._offset(destination, index), buffer)
            self.bank = destination
            run *= 2
        self._write(0, self._header())
        os.fsync(self.fd)
        self._check()
        self.final_identity = _file_identity(self.build.ledger_path)
        # Strict membership: a duplicate rowid cannot hide another same-count row.
        for _ in self.records():
            pass

    def records(self):
        if self._read(0, _HEADER.size) != self._header():
            raise StorageIntegrityError("corpus ledger header differs from its actual build")
        previous = None
        for entry in self._entries(self.bank, 0, self.count):
            if previous is not None and entry[:2] <= previous:
                raise StorageIntegrityError("corpus ledger membership is duplicated or unordered")
            previous = entry[:2]
            yield entry
        self._check()

    def digest(self):
        self._check()
        size = os.fstat(self.fd).st_size
        result, offset = hashlib.sha256(), 0
        while offset < size:
            part = self._read(offset, min(self.block, size - offset))
            result.update(part)
            offset += len(part)
        self._check()
        return result.hexdigest(), size

    def close(self):
        if self.fd is not None:
            descriptor, self.fd = self.fd, None
            _close_owned_fd(descriptor, self.identity)


def build_receipt_corpus(source, observations, *, expected_source_sha256,
                         workspace, owned_directory, main_cap_bytes,
                         ledger_cap_bytes, limits=DEFAULT_LIMITS) -> ReceiptCorpusResult:
    """Build only a newly created private copy, append records, close and rescan.

    ``observations`` is the caller's closed iterator of exact (dict, datetime)
    pairs. Only one record is normalized at a time. M, journal M and ledger L
    (including BOTH merge regions) must already be globally reserved. No input
    is adopted by path, no writer escapes, and failures retain every new file.
    The result is historical byte/membership evidence, never a native seal,
    semantic source approval, a resumable portion or permission to publish.
    """
    build = _Build(source, workspace, owned_directory, main_cap_bytes, ledger_cap_bytes, limits)
    return build.run(observations, expected_source_sha256)
