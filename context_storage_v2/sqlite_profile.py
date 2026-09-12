"""Checked configuration/lifecycle for a NEW private C SQLite build.

``fresh-single-main-v1`` owns one exact TrackedConnection, begins before DDL,
and exposes one explicit build commit which also closes the connection. There
is deliberately no resume, overwrite, unlink, or implicit successful commit.

IMPORTANT OWNER PRECONDITIONS: the containing namespace must remain private,
quiescent and exclusive for the entire lifetime (including SQLite's sidecars).
The owner must admit all inputs, archives and failed attempts globally, reserve
physical allocation/metadata, monitor actual free space, and enforce native
CPU/AS/RSS/output/deadline and file limits. This is NOT that native owner.

The retained O_EXCL descriptor and repeated identity checks detect observed
replacement. Python sqlite3 opens a pathname, not that descriptor; database_list
exposes a pathname, not SQLite's VFS descriptor. Therefore neither ABA races nor
hostile callers are excluded here. The exposed Python connection is mutable:
checks invalidate detected drift, but cannot undo an illicit prior commit or
stop another connection, backup(), extensions, arbitrary I/O or hidden files.
An outer closed writer catalogue must exclude these operations, VACUUM/INTO,
ATTACH, WAL, extra commits and all additional writable connections.

The plan reserves LOGICAL main/journal file lengths M + M. Its journal ceiling
requires an external RLIMIT_FSIZE=M (or equivalent native enforcement); SQLite's
max_page_count bounds only main pages. Neither bound proves physical allocation
or that exactly these two files exist. temp_store=MEMORY is configured/read back
before any other SQL and checked against compile-time TEMP_STORE. Memory sorts
and subjournals still consume the unchanged native AS/RSS budget; OOM is failure,
not permission to spill to disk or increase memory.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sqlite3
import stat
import weakref

from context_runtime_transaction import TrackedConnection, TrackedCursor

from .contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError, StorageLimits


PROFILE_ID = "fresh-single-main-v1"
MAX_REGISTERED_HANDLES = 256
_SIDECARS = ("-journal", "-wal", "-shm")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z", re.ASCII)
_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
            *(f"LPT{i}" for i in range(10))}


@dataclass(frozen=True)
class SQLiteWriterPlan:
    """Only a per-build logical reservation; NOT global/native admission."""

    main_cap_bytes: int
    page_size: int = 4096
    cache_kib: int = 8192

    def __post_init__(self):
        if (type(self.page_size) is not int or not 512 <= self.page_size <= 65536
                or self.page_size & (self.page_size - 1)):
            raise StorageLimitError("invalid private SQLite page size")
        if (type(self.main_cap_bytes) is not int or self.main_cap_bytes < self.page_size
                or self.main_cap_bytes % self.page_size):
            raise StorageLimitError("private SQLite main ceiling must be complete positive pages")
        if type(self.cache_kib) is not int or not 1 <= self.cache_kib <= 8192:
            raise StorageLimitError("private SQLite cache cannot exceed 8192 KiB")
        # Constructor validation is fixed, not overridable by a limits instance.
        SQLiteWriterPlan._validate_limits(self, DEFAULT_LIMITS)

    def _validate_limits(self, limits):
        if type(limits) is not StorageLimits:
            raise StorageLimitError("private SQLite requires exact C limits")
        StorageLimits.__post_init__(limits)
        if (self.main_cap_bytes > limits.input_bytes
                or 2 * self.main_cap_bytes > limits.workspace_bytes):
            raise StorageLimitError("private SQLite logical slots exceed the C envelope")

    @property
    def max_page_count(self):
        return self.main_cap_bytes // self.page_size

    @property
    def journal_cap_bytes(self):
        """Reserved file length, NOT a journal limit installed by this module."""
        return self.main_cap_bytes

    @property
    def logical_reserved_bytes(self):
        return 2 * self.main_cap_bytes


@dataclass(frozen=True)
class SQLiteProfileReadback:
    """An observation, not a source/model/publication or native-budget proof."""

    profile_id: str
    sqlite_version: str
    compile_temp_store: int
    transaction_generation: int
    page_count: int
    main_file_bytes: int
    journal_file_bytes: int
    cache_spill_threshold: int


def _identity(info):
    if (type(info.st_dev) is not int or info.st_dev < 0
            or type(info.st_ino) is not int or info.st_ino <= 0):
        raise StorageIntegrityError("private SQLite filesystem identity is unavailable")
    return info.st_dev, info.st_ino


def _not_link(info):
    return not (stat.S_ISLNK(info.st_mode) or
                getattr(info, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _regular(info, device):
    return (stat.S_ISREG(info.st_mode) and _not_link(info)
            and info.st_nlink == 1 and info.st_dev == device)


def _parents(path):
    if not path.is_absolute() or ".." in path.parts or len(path.parts) > 64:
        raise StorageIntegrityError("private SQLite needs a bounded absolute path")
    if (not _NAME.fullmatch(path.name) or path.name.endswith(".")
            or path.name.split(".", 1)[0].upper() in _DEVICES
            or path.anchor.startswith("\\\\")):
        raise StorageIntegrityError("invalid private SQLite filename or network namespace")
    result = []
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or not _not_link(info):
            raise StorageIntegrityError("private SQLite parent is not an ordinary directory")
        result.append((parent, _identity(info)))
    return tuple(result)


def _absent(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise StorageIntegrityError("private SQLite target or sidecar already exists")


class FreshSQLiteWriter:
    """Use open_fresh_writer(); context exit ALWAYS abandons uncommitted work.

    Readbacks occur at this API's boundaries, not between arbitrary caller SQL.
    Directly changing the connection or namespace violates the owner contract.
    Any detected deviation permanently closes this handle. A successful commit
    closes it too; calling commit_build() twice is an error, never a resume.
    """

    def __init__(self, *args, **kwargs):
        raise TypeError("use open_fresh_writer for exclusive private creation")

    @property
    def connection(self):
        return self._connection

    @property
    def plan(self):
        return self._plan

    @property
    def path(self):
        return self._path

    @property
    def closed(self):
        return self._state != "building"

    @property
    def committed(self):
        return self._state == "committed"

    def _namespace(self, *, empty=False, allow_journal=True):
        for parent, expected in self._parents:
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or not _not_link(info) or _identity(info) != expected:
                raise StorageIntegrityError("private SQLite parent identity changed")
        held, named = os.fstat(self._fd), self._path.lstat()
        device = self._file_identity[0]
        if (not _regular(held, device) or not _regular(named, device)
                or _identity(held) != self._file_identity or _identity(named) != self._file_identity
                or held.st_size != named.st_size):
            raise StorageIntegrityError("private SQLite main identity changed")
        if empty and held.st_size != 0:
            raise StorageIntegrityError("private SQLite initial main is no longer empty")
        if held.st_size > self._plan.main_cap_bytes:
            raise StorageLimitError("private SQLite main file exceeds its logical slot")
        journal_bytes = 0
        for suffix in _SIDECARS:
            candidate = Path(str(self._path) + suffix)
            try:
                info = candidate.lstat()
            except FileNotFoundError:
                continue
            if empty or not allow_journal or suffix != "-journal" or not _regular(info, device):
                raise StorageIntegrityError("unexpected private SQLite sidecar")
            observed = _identity(info)
            if self._journal_identity is not None and observed != self._journal_identity:
                raise StorageIntegrityError("private SQLite journal identity changed")
            self._journal_identity = observed
            journal_bytes = info.st_size
            if journal_bytes > self._plan.journal_cap_bytes:
                raise StorageLimitError("private SQLite journal exceeds its reserved logical slot")
        return held.st_size, journal_bytes

    def _sql(self, sql):
        # Class-bound normal tracked methods retain the exact connection type.
        # This is not protection against mutation of Python classes/callbacks.
        cursor = TrackedConnection.execute(self._connection, sql)
        try:
            cursor.row_factory = None
            return cursor.fetchone()
        finally:
            cursor.close()

    def _register_handles(self):
        # sqlite3_close_v2 can retain the native file while a cursor/Blob lives.
        # Register normal APIs without changing TrackedConnection's exact type.
        # Bypassing/replacing these instance methods is not a supported caller.
        self._handles = weakref.WeakSet()
        connection = self._connection

        def capacity():
            if len(self._handles) >= MAX_REGISTERED_HANDLES:
                raise StorageLimitError("too many retained private SQLite handles")

        def cursor(factory=TrackedCursor):
            capacity()
            result = TrackedConnection.cursor(connection, factory)
            self._handles.add(result)
            return result

        def blobopen(*args, **kwargs):
            capacity()
            result = sqlite3.Connection.blobopen(connection, *args, **kwargs)
            self._handles.add(result)
            return result

        self._cursor_method, self._blob_method = cursor, blobopen
        connection.cursor, connection.blobopen = cursor, blobopen

    def _close_handles(self):
        error = None
        for handle in tuple(getattr(self, "_handles", ())):
            try:
                if isinstance(handle, sqlite3.Cursor):
                    sqlite3.Cursor.close(handle)
                else:
                    sqlite3.Blob.close(handle)
            except sqlite3.Error as exc:
                error = error or exc
        if hasattr(self, "_handles"):
            self._handles.clear()
        if error is not None:
            raise StorageIntegrityError("private SQLite cursor/blob close failed") from error

    def _value(self, name):
        row = self._sql("PRAGMA " + name)
        if row is None or len(row) != 1:
            raise StorageIntegrityError("private SQLite profile readback is unavailable")
        return row[0]

    def _main_binding(self):
        cursor = TrackedConnection.execute(self._connection, "PRAGMA database_list")
        try:
            cursor.row_factory = None
            databases = cursor.fetchmany(3)
        finally:
            cursor.close()
        if (not databases or databases[0][1] != "main" or len(databases) > 2
                or Path(databases[0][2]) != self._path
                or (len(databases) == 2 and databases[1][1:] != ("temp", ""))):
            raise StorageIntegrityError("private SQLite main pathname or database set changed")
        if self._sql("SELECT 1 FROM temp.sqlite_schema LIMIT 1") is not None:
            raise StorageIntegrityError("private SQLite profile excludes explicit TEMP objects")

    def _read_profile(self, *, active):
        if type(self._plan) is not SQLiteWriterPlan or type(self._limits) is not StorageLimits:
            raise StorageIntegrityError("private SQLite plan type changed")
        SQLiteWriterPlan.__post_init__(self._plan)
        SQLiteWriterPlan._validate_limits(self._plan, self._limits)
        if ((self._plan.main_cap_bytes, self._plan.page_size, self._plan.cache_kib) != self._plan_values
                or tuple(vars(self._limits).items()) != self._limit_values):
            raise StorageIntegrityError("private SQLite plan or limits changed")
        connection = self._connection
        if (type(connection) is not TrackedConnection or connection.text_factory is not str
                or connection.row_factory is not None or connection.isolation_level is not None
                or connection.autocommit != sqlite3.LEGACY_TRANSACTION_CONTROL
                or connection.cursor is not self._cursor_method or connection.blobopen is not self._blob_method):
            raise StorageIntegrityError("private SQLite connection policy changed")
        if connection.in_transaction is not active or (active and
                connection.transaction_generation != self._generation):
            raise StorageIntegrityError("private SQLite build transaction ended or changed")
        main_bytes, journal_bytes = self._namespace(allow_journal=active)
        self._main_binding()
        for name, expected in self._expected.items():
            actual = self._value(name)
            if type(actual) is not type(expected) or actual != expected:
                raise StorageIntegrityError("private SQLite profile readback changed: " + name)
        for category in (sqlite3.SQLITE_LIMIT_ATTACHED, sqlite3.SQLITE_LIMIT_WORKER_THREADS):
            if connection.getlimit(category) != 0:
                raise StorageIntegrityError("private SQLite attach/thread limit changed")
        for category, expected in self._configs:
            if connection.getconfig(category) is not expected:
                raise StorageIntegrityError("private SQLite connection configuration changed")
        count = self._value("main.page_count")
        if type(count) is not int or not 0 <= count <= self._plan.max_page_count:
            raise StorageLimitError("private SQLite page count exceeds the planned main slot")
        # Readback SQL can run caller callbacks. Recheck lifetime/path afterward;
        # callback or ABA exclusion itself remains the closed native owner's job.
        if connection.in_transaction is not active or (active and
                connection.transaction_generation != self._generation):
            raise StorageIntegrityError("private SQLite build changed during profile readback")
        main_bytes, journal_bytes = self._namespace(allow_journal=active)
        return SQLiteProfileReadback(PROFILE_ID, sqlite3.sqlite_version,
            self._compile_temp_store, connection.transaction_generation, count,
            main_bytes, journal_bytes, self._expected["cache_spill"])

    def _dispose(self):
        connection, self._connection = self._connection, None
        descriptor, self._fd = self._fd, None
        error = None
        try:
            if connection is not None:
                try:
                    self._close_handles()
                except StorageIntegrityError as exc:
                    error = exc
                try:
                    if connection.in_transaction:
                        if type(connection) is TrackedConnection:
                            TrackedConnection.rollback(connection)
                        else:
                            sqlite3.Connection.rollback(connection)
                except sqlite3.Error as exc:
                    error = exc
                finally:
                    try:
                        if type(connection) is TrackedConnection:
                            TrackedConnection.close(connection)
                        else:
                            sqlite3.Connection.close(connection)
                    except sqlite3.Error as exc:
                        error = error or exc
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError as exc:
                    error = error or exc
        if error is not None:
            raise StorageIntegrityError("private SQLite close/rollback did not finish cleanly") from error

    def _abort(self, error):
        self._state = "aborted"
        try:
            self._dispose()
        except StorageIntegrityError as close_error:
            error.add_note(str(close_error))

    def check_profile(self) -> SQLiteProfileReadback:
        if self._state != "building":
            raise StorageIntegrityError("private SQLite writer is already closed")
        try:
            return self._read_profile(active=True)
        except BaseException as exc:
            self._abort(exc)
            if isinstance(exc, (OSError, sqlite3.Error)):
                raise StorageIntegrityError("private SQLite profile could not be read") from exc
            raise

    def commit_build(self) -> None:
        """One explicit commit, then close; not a coverage/publication grant."""
        self.check_profile()
        try:
            self._close_handles()
            self.check_profile()
            TrackedConnection.commit(self._connection)
            self._read_profile(active=False)
            self._dispose()
        except BaseException as exc:
            self._abort(exc)
            if isinstance(exc, (OSError, sqlite3.Error)):
                raise StorageIntegrityError("private SQLite build commit failed") from exc
            raise
        self._state = "committed"

    def close(self) -> None:
        """Abandon uncommitted work and retain the failed main file on disk."""
        if self._state != "building":
            return
        self._state = "abandoned"
        self._dispose()

    def __enter__(self):
        self.check_profile()
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc is not None and self._state == "building":
            self._abort(exc)
        else:
            self.close()
        return False


def open_fresh_writer(path, *, plan: SQLiteWriterPlan, limits=DEFAULT_LIMITS) -> FreshSQLiteWriter:
    """Create exclusively in an ALREADY private, existing, exclusive directory.

    The owner must keep the returned handle alive and close it explicitly (or
    use ``with``). No directory is created and no existing file is overwritten.
    This function does not install native limits, inspect global free space, or
    admit additional file slots. Failed new files remain charged to their owner.
    """
    if type(plan) is not SQLiteWriterPlan:
        raise StorageLimitError("private SQLite requires an exact writer plan")
    SQLiteWriterPlan.__post_init__(plan)
    SQLiteWriterPlan._validate_limits(plan, limits)
    path = Path(path)
    writer = object.__new__(FreshSQLiteWriter)
    writer._state, writer._connection, writer._fd = "building", None, None
    writer._journal_identity = None
    writer._path, writer._plan, writer._limits = path, plan, limits
    writer._plan_values = (plan.main_cap_bytes, plan.page_size, plan.cache_kib)
    writer._limit_values = tuple(vars(limits).items())
    try:
        writer._parents = _parents(path)
        for candidate in (path, *(Path(str(path) + suffix) for suffix in _SIDECARS)):
            _absent(candidate)
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        writer._fd = os.open(path, flags, 0o600)
        writer._file_identity = _identity(os.fstat(writer._fd))
        writer._namespace(empty=True)
        writer._connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True,
            factory=TrackedConnection, timeout=0, isolation_level=None,
            autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL, cached_statements=0)
        if type(writer._connection) is not TrackedConnection:
            raise StorageIntegrityError("private SQLite needs the exact tracked connection")
        writer._register_handles()
        writer._namespace(empty=True)
        # FIRST SQL. No compile_options, schema, database_list, BEGIN or DDL first.
        writer._sql("PRAGMA temp_store=MEMORY")
        if writer._value("temp_store") != 2:
            raise StorageIntegrityError("private SQLite MEMORY temp_store is unavailable")
        # Check the compile-time override BEFORE even opening the empty TEMP
        # schema: TEMP_STORE=0 can defeat the runtime readback's apparent value.
        options = []
        cursor = TrackedConnection.execute(writer._connection, "PRAGMA compile_options")
        try:
            for _ in range(257):
                row = cursor.fetchone()
                if row is None:
                    break
                if type(row[0]) is not str or len(row[0]) > 256:
                    raise StorageIntegrityError("unbounded private SQLite compile options")
                if row[0].startswith("TEMP_STORE="):
                    options.append(row[0])
            else:
                raise StorageIntegrityError("too many private SQLite compile options")
        finally:
            cursor.close()
        if len(options) != 1 or options[0] not in {"TEMP_STORE=1", "TEMP_STORE=2", "TEMP_STORE=3"}:
            raise StorageIntegrityError("SQLite build does not establish effective MEMORY temp_store")
        writer._compile_temp_store = int(options[0][-1])
        writer._main_binding()
        writer._namespace(empty=True)
        if writer._value("main.page_count") != 0 or writer._sql("SELECT 1 FROM main.sqlite_schema LIMIT 1"):
            raise StorageIntegrityError("private SQLite did not open an empty main")
        writer._configs = (
            (sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, False),
            (sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True),
            (sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False),
        )
        for category, value in writer._configs:
            writer._connection.setconfig(category, value)
        for category in (sqlite3.SQLITE_LIMIT_ATTACHED, sqlite3.SQLITE_LIMIT_WORKER_THREADS):
            writer._connection.setlimit(category, 0)
        writer._expected = {
            "temp_store": 2, "main.journal_mode": "delete", "main.synchronous": 2,
            "main.page_size": plan.page_size, "main.auto_vacuum": 0,
            "main.encoding": "UTF-8", "main.cache_size": -plan.cache_kib,
            "main.mmap_size": 0, "main.max_page_count": plan.max_page_count,
            "threads": 0, "main.locking_mode": "normal", "main.journal_size_limit": 0,
            "busy_timeout": 0, "query_only": 0, "trusted_schema": 0,
        }
        for statement in (
            "PRAGMA main.journal_mode=DELETE", "PRAGMA main.synchronous=FULL",
            f"PRAGMA main.page_size={plan.page_size}", "PRAGMA main.auto_vacuum=NONE",
            "PRAGMA main.encoding='UTF-8'", f"PRAGMA main.cache_size=-{plan.cache_kib}",
            "PRAGMA main.mmap_size=0", f"PRAGMA main.max_page_count={plan.max_page_count}",
            "PRAGMA threads=0", "PRAGMA main.locking_mode=NORMAL",
            "PRAGMA main.journal_size_limit=0", "PRAGMA main.cache_spill=ON",
            "PRAGMA busy_timeout=0", "PRAGMA query_only=OFF",
        ):
            writer._namespace(empty=True)
            writer._sql(statement)
        spill = writer._value("cache_spill")
        if type(spill) is not int or spill <= 0:
            raise StorageIntegrityError("private SQLite cache spilling was not enabled")
        writer._expected["cache_spill"] = spill
        writer._generation = writer._connection.transaction_generation
        writer._read_profile(active=False)
        writer._sql("BEGIN IMMEDIATE")
        writer._generation = writer._connection.transaction_generation
        writer.check_profile()
        return writer
    except BaseException as exc:
        writer._abort(exc)
        if isinstance(exc, (OSError, sqlite3.Error, AttributeError)):
            raise StorageIntegrityError("private SQLite writer could not be opened") from exc
        raise
