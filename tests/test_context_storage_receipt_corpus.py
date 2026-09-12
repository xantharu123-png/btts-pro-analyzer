"""Actual small copy/append/cold-read chains; no native or global admission."""
from contextlib import closing, contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3

import pytest

import context_observations as legacy
from context_runtime import _SCHEMA
from context_runtime_transaction import TrackedConnection
from context_sources.tennis_status import normalize_tennis_status, validate_tennis_status_record
from context_storage_v2 import receipt_corpus as owner
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2.copying import _configure_copy_reader
from context_storage_v2.inventory import inventory_raw
from context_models.contracts import ContextIntegrityError, canonical_timestamp, digest, normalize_observation


NOW = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)


def observations(count=3):
    for number in range(count):
        clock = NOW + timedelta(minutes=number)
        rows = normalize_tennis_status("ATP", "100", {
            "id": str(2000 + number), "date": (NOW + timedelta(days=1)).isoformat(),
            "competitors": [{"id": "1"}, {"id": "2"}],
            "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}},
        }, grouping_slug="mens-singles", observed_at=clock)
        assert len(rows) == 1
        yield rows[0], clock


@contextmanager
def source(tmp_path, *, encoding="UTF-8", page_size=4096, large=False, max_rowid=False, all_rows=False):
    path = tmp_path / "source.sqlite"
    with closing(sqlite3.connect(path)) as writer:
        writer.execute(f"PRAGMA page_size={page_size}")
        writer.execute(f"PRAGMA encoding='{encoding}'")
        for sql in _SCHEMA.values():
            writer.execute(sql)
        raw = b'{ "unknown-future": true }\x00' * (10000 if large else 1)
        key = "legacy\x00Ж東京" + ("x" * 5000 if large else "")
        writer.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (key, "future\x00kind", raw, "old\x00clock"))
        writer.execute("INSERT INTO context_snapshots VALUES(?,?,?)", (key, raw, "raw-only\x00digest"))
        writer.execute("INSERT INTO context_contents(rowid,content_digest,payload) VALUES(?,?,?)",
                       (2**63 - 1 if max_rowid else -7, key, raw))
        if all_rows:
            writer.execute("INSERT INTO manifests VALUES(?,?,?,?)", (key, None, raw, "old\x00clock"))
            writer.execute("INSERT INTO active_manifest VALUES(1,?)", (key,))
            writer.execute("INSERT INTO context_model_rollbacks VALUES(?,?)", (key, raw))
            writer.execute("INSERT INTO context_observations VALUES(?,?,?,?,?,?,?,?)",
                           (key, key, "unknown\x00event", "old\x00clock", "old\x00schedule",
                            "old\x00source", "unknown\x00subject", "future\x00kind"))
        writer.commit()
    raw_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                                factory=TrackedConnection, isolation_level=None)) as reader:
        _configure_copy_reader(reader, page_size=page_size, page_count=path.stat().st_size // page_size)
        reader.execute("BEGIN").close()
        yield path, raw_hash, reader


def options(tmp_path, **changes):
    workspace, owned = tmp_path / "work", tmp_path / "work" / "corpus"
    owned.mkdir(parents=True)
    return dict(workspace=workspace, owned_directory=owned, main_cap_bytes=2 * 1024**2,
                ledger_cap_bytes=8192, **changes)


@contextmanager
def reader(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                                factory=TrackedConnection, isolation_level=None)) as connection:
        header = path.read_bytes()[:100]
        page_size = int.from_bytes(header[16:18], "big") or 65536
        if page_size == 1:
            page_size = 65536
        _configure_copy_reader(connection, page_size=page_size, page_count=path.stat().st_size // page_size)
        connection.execute("BEGIN").close()
        yield connection


@pytest.mark.parametrize("encoding,page_size", [("UTF-8", 512), ("UTF-8", 4096),
    ("UTF-16le", 8192), ("UTF-16be", 65536)], ids=["utf8-512", "utf8-4096", "utf16le-8192", "utf16be-65536"])
def test_real_copy_three_receipts_commit_close_and_full_legacy_differential(tmp_path, encoding, page_size):
    settings = options(tmp_path)
    settings["limits"] = replace(DEFAULT_LIMITS, block_bytes=max(32768, page_size))
    with source(tmp_path, encoding=encoding, page_size=page_size, large=True) as (path, sealed, connection):
        before = path.read_bytes()
        original = inventory_raw(connection)
        reference_path = tmp_path / "legacy-reference.sqlite"
        shutil.copyfile(path, reference_path)
        expected = [legacy.append_observation(reference_path, value, observed_at=clock)
                    for value, clock in observations()]
        result = owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        assert result.path == settings["owned_directory"] / "legacy-copy.sqlite"
        assert result.ledger_path == settings["owned_directory"] / "receipt-additions.bin"
        assert result.submitted_observations == result.new_contents == result.new_receipts == 3
        assert result.source_inventory == original
        assert result.source_sha256 == sealed and path.read_bytes() == before
        assert result.output_sha256 == hashlib.sha256(result.path.read_bytes()).hexdigest()
        assert result.ledger_sha256 == hashlib.sha256(result.ledger_path.read_bytes()).hexdigest()
        assert result.page_size == page_size and result.encoding == encoding
        with reader(result.path) as output, reader(reference_path) as reference:
            assert inventory_raw(output) == result.inventory == inventory_raw(reference)
            actual = output.execute(legacy._SELECT + " ORDER BY r.digest").fetchall()
            assert sorted(row[0] for row in actual) == sorted(expected)
            for stored in actual:
                validate_tennis_status_record(legacy._decode_receipt(stored))
        assert sorted(item.name for item in settings["owned_directory"].iterdir()) == [
            "legacy-copy.sqlite", "receipt-additions.bin"]
        assert connection.in_transaction


def test_int64_max_existing_rowid_does_not_assume_monotonic_sqlite_new_rowids(tmp_path):
    settings = options(tmp_path)
    with source(tmp_path, max_rowid=True) as (path, sealed, connection):
        result = owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        with reader(result.path) as output:
            rowids = [row[0] for row in output.execute("SELECT rowid FROM context_contents")]
            assert len(rowids) == 4 and max(rowids) == 2**63 - 1
            assert all(rowid < 2**63 - 1 for rowid in rowids if rowid != 2**63 - 1)


def test_iterator_rechecks_are_not_counted_as_new_rows_and_no_input_list_is_built(tmp_path):
    settings = options(tmp_path)
    seen = []
    def streamed():
        for item in observations():
            seen.append(item[0]["event_key"])
            yield item
            yield item
    with source(tmp_path) as (_path, sealed, connection):
        result = owner.build_receipt_corpus(connection, streamed(), expected_source_sha256=sealed, **settings)
        assert len(seen) == 3 and result.submitted_observations == 6
        assert result.new_contents == result.new_receipts == 3


def test_owned_directory_cannot_be_reused_even_after_a_success(tmp_path):
    settings = options(tmp_path)
    with source(tmp_path) as (_path, sealed, connection):
        result = owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        before = {path.name: path.read_bytes() for path in settings["owned_directory"].iterdir()}
        with pytest.raises(StorageIntegrityError, match="empty|reuse"):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        assert {path.name: path.read_bytes() for path in settings["owned_directory"].iterdir()} == before


@pytest.mark.parametrize("stop", ["source-end", "iterator-error"], ids=["source-end", "iterator-error"])
def test_abort_before_commit_closes_outputs_retains_failed_files_and_keeps_source(tmp_path, stop):
    settings = options(tmp_path)
    with source(tmp_path) as (path, sealed, connection):
        before = path.read_bytes()
        def interrupted():
            yield next(observations())
            if stop == "source-end":
                connection.commit()
            else:
                raise ValueError("actual generator stopped")
        with pytest.raises((StorageIntegrityError, ValueError)):
            owner.build_receipt_corpus(connection, interrupted(), expected_source_sha256=sealed, **settings)
        assert path.read_bytes() == before
        output = settings["owned_directory"] / "legacy-copy.sqlite"
        assert output.exists() and (settings["owned_directory"] / "receipt-additions.bin").exists()
        with reader(output) as reopened:
            assert reopened.execute("SELECT count(*) FROM context_observations").fetchone() == (0,)


def test_reservations_count_main_journal_ledger_and_all_active_inputs_before_copy(tmp_path):
    settings = options(tmp_path)
    with source(tmp_path) as (path, sealed, connection):
        tight = replace(DEFAULT_LIMITS, input_bytes=path.stat().st_size + settings["main_cap_bytes"])
        with pytest.raises(StorageLimitError):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed,
                                       limits=tight, **settings)
        assert list(settings["owned_directory"].iterdir()) == []


def test_small_ledger_reservation_fails_without_a_partial_success(tmp_path):
    settings = options(tmp_path)
    settings["ledger_cap_bytes"] = 128
    with source(tmp_path) as (path, sealed, connection):
        with pytest.raises(StorageLimitError):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        assert path.exists()
        with reader(settings["owned_directory"] / "legacy-copy.sqlite") as output:
            assert output.execute("SELECT count(*) FROM context_observations").fetchone() == (0,)


def test_ledger_larger_than_main_cannot_escape_the_single_fsize_envelope(tmp_path):
    settings = options(tmp_path)
    settings["ledger_cap_bytes"] = settings["main_cap_bytes"] + 1
    with source(tmp_path) as (_path, sealed, connection):
        with pytest.raises(StorageLimitError):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
    assert list(settings["owned_directory"].iterdir()) == []


def test_identical_byte_replacement_between_writer_close_and_reader_open_is_rejected(tmp_path, monkeypatch):
    settings = options(tmp_path)
    verify = owner._Build.verify_complete
    replacements = []
    def replaced(build):
        fresh = tmp_path / "different-inode.sqlite"
        shutil.copyfile(build.path, fresh)
        replacement_identity = fresh.stat().st_ino
        assert replacement_identity != build.path.stat().st_ino
        os.replace(fresh, build.path)
        replacements.append((replacement_identity, build.path.read_bytes()))
        return verify(build)
    monkeypatch.setattr(owner._Build, "verify_complete", replaced)
    with source(tmp_path) as (_path, sealed, connection):
        with pytest.raises(StorageIntegrityError):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
    assert len(replacements) == 1
    output = settings["owned_directory"] / "legacy-copy.sqlite"
    assert (output.stat().st_ino, output.read_bytes()) == replacements[0]


@pytest.mark.parametrize("target", ["main", "ledger"], ids=["main", "ledger"])
def test_late_terminal_close_cannot_accept_replacement_of_already_hashed_file(tmp_path, monkeypatch, target):
    settings = options(tmp_path)
    close = owner._Ledger.close
    replaced = []
    def late_close(ledger):
        should_replace = ledger.fd is not None and ledger.final_identity is not None
        close(ledger)
        if should_replace:
            path = ledger.build.path if target == "main" else ledger.build.ledger_path
            fresh = tmp_path / "terminal-replacement.bin"
            shutil.copyfile(path, fresh)
            replaced.append(fresh.stat().st_ino)
            os.replace(fresh, path)
    monkeypatch.setattr(owner._Ledger, "close", late_close)
    with source(tmp_path) as (_path, sealed, connection):
        with pytest.raises(StorageIntegrityError):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
    assert len(replaced) == 1


def test_actual_ledger_fd_is_closed_when_its_initial_identity_read_fails(tmp_path, monkeypatch):
    settings = options(tmp_path)
    opened, fstat = os.open, os.fstat
    descriptors, failed = [], []
    def captured(path, *args, **kwargs):
        descriptor = opened(path, *args, **kwargs)
        if Path(path).name == "receipt-additions.bin":
            descriptors.append(descriptor)
        return descriptor
    def denied(descriptor):
        if descriptors and descriptor == descriptors[0] and not failed:
            failed.append(True)
            raise OSError("actual ledger identity lookup failed")
        return fstat(descriptor)
    with source(tmp_path) as (_path, sealed, connection):
        monkeypatch.setattr(os, "open", captured)
        monkeypatch.setattr(os, "fstat", denied)
        try:
            with pytest.raises((OSError, StorageIntegrityError)):
                owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
            assert failed == [True] and len(descriptors) == 1
            with pytest.raises(OSError):
                fstat(descriptors[0])
        finally:
            # Test-only cleanup if the RED implementation leaked its real FD.
            for descriptor in descriptors:
                try:
                    fstat(descriptor)
                except OSError:
                    continue
                os.close(descriptor)


def test_failed_tracked_connection_close_still_disposes_the_actual_native_connection(tmp_path, monkeypatch):
    settings = options(tmp_path)
    opened, closed = owner._Build.open_copied_writer, TrackedConnection.close
    captured, failed = [], []
    def capture(build, *args):
        opened(build, *args)
        captured.append(build.connection)
    def failure(connection):
        if captured and connection is captured[0] and not failed:
            failed.append(True)
            raise sqlite3.OperationalError("tracked close failed before native close")
        return closed(connection)
    with source(tmp_path) as (_path, sealed, connection):
        monkeypatch.setattr(owner._Build, "open_copied_writer", capture)
        monkeypatch.setattr(TrackedConnection, "close", failure)
        try:
            with pytest.raises(StorageIntegrityError):
                owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
            assert len(captured) == 1 and failed == [True]
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                sqlite3.Connection.execute(captured[0], "SELECT 1")
        finally:
            for target in captured:
                sqlite3.Connection.close(target)


def test_terminal_capacity_work_is_charged_to_the_original_deadline(tmp_path, monkeypatch):
    settings = options(tmp_path)
    started, captured, advanced = owner.time.monotonic(), [], []
    current = [started]
    run, walk = owner._Build.run, owner._workspace_bytes
    def running(build, *args):
        captured.append(build)
        return run(build, *args)
    def late_walk(path):
        result = walk(path)
        if (captured and captured[0].ledger is not None
                and captured[0].ledger.fd is None and not advanced):
            advanced.append(True)
            current[0] += 301
        return result
    with source(tmp_path) as (_path, sealed, connection):
        monkeypatch.setattr(owner._Build, "run", running)
        monkeypatch.setattr(owner, "_workspace_bytes", late_walk)
        monkeypatch.setattr(owner.time, "monotonic", lambda: current[0])
        with pytest.raises(StorageLimitError, match="deadline"):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
    assert advanced == [True]


def test_wal_raw_header_is_rejected_before_held_reader_schema_access_creates_companions(tmp_path):
    settings = options(tmp_path)
    path = tmp_path / "wal-source.sqlite"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        for sql in _SCHEMA.values():
            connection.execute(sql)
        connection.commit()
    before = path.read_bytes()
    assert before[18:20] == b"\x02\x02"
    assert not Path(str(path) + "-wal").exists()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                                factory=TrackedConnection, isolation_level=None)) as connection:
        connection.execute("PRAGMA temp_store=MEMORY").close()
        connection.execute("PRAGMA query_only=ON").close()
        connection.execute("PRAGMA trusted_schema=OFF").close()
        connection.execute("BEGIN").close()
        with pytest.raises(StorageIntegrityError):
            owner.build_receipt_corpus(connection, observations(),
                expected_source_sha256=hashlib.sha256(before).hexdigest(), **settings)
        assert not Path(str(path) + "-wal").exists()
        assert not Path(str(path) + "-shm").exists()
        assert path.read_bytes() == before
    assert list(settings["owned_directory"].iterdir()) == []


def test_source_merge_cursor_closes_if_opening_its_output_peer_fails(tmp_path, monkeypatch):
    settings = options(tmp_path)
    query, opened = owner._row_query, []
    with source(tmp_path) as (_path, sealed, connection):
        def failed_peer(target, table, **kwargs):
            if kwargs.get("rowid") is None and table == "active_manifest":
                if target is connection:
                    cursor = query(target, table, **kwargs)
                    opened.append(cursor)
                    return cursor
                raise sqlite3.OperationalError("actual output cursor open failed")
            return query(target, table, **kwargs)
        monkeypatch.setattr(owner, "_row_query", failed_peer)
        try:
            with pytest.raises(StorageIntegrityError):
                owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
            assert len(opened) == 1
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                opened[0].fetchone()
        finally:
            for cursor in opened:
                cursor.close()


def test_all_seven_nonempty_original_tables_keep_every_old_rowid_type_and_byte(tmp_path):
    settings = options(tmp_path)
    settings["limits"] = replace(DEFAULT_LIMITS, block_bytes=32768)
    with source(tmp_path, encoding="UTF-16le", large=True, all_rows=True) as (path, sealed, connection):
        original = inventory_raw(connection, limits=settings["limits"])
        assert len(original.tables) == 7 and all(table.row_count == 1 for table in original.tables)
        reference_path = tmp_path / "legacy-reference.sqlite"
        shutil.copyfile(path, reference_path)
        for value, clock in observations():
            legacy.append_observation(reference_path, value, observed_at=clock)
        result = owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        with reader(result.path) as output, reader(reference_path) as reference:
            assert inventory_raw(output) == inventory_raw(reference) == result.inventory
            # Independent physical row checks, including a NULL predecessor,
            # a real INTEGER id, raw future JSON and NUL-bearing UTF-16 TEXT.
            for table in ("artifacts", "manifests", "active_manifest", "context_contents",
                          "context_observations", "context_snapshots", "context_model_rollbacks"):
                old_row = connection.execute(f'SELECT rowid,* FROM "{table}"').fetchone()
                assert output.execute(f'SELECT rowid,* FROM "{table}" WHERE rowid=?', (old_row[0],)).fetchone() == old_row
        assert result.new_contents == result.new_receipts == 3


def test_next_input_is_not_requested_until_the_previous_actual_append_completed(tmp_path, monkeypatch):
    settings = options(tmp_path)
    append_one, appended = owner._Build.append_one, []
    def recorded(build, item):
        append_one(build, item)
        appended.append(item[0]["event_key"])
    def stream():
        for index, item in enumerate(observations()):
            assert len(appended) == index
            yield item
        assert len(appended) == 3
    monkeypatch.setattr(owner._Build, "append_one", recorded)
    with source(tmp_path) as (_path, sealed, connection):
        result = owner.build_receipt_corpus(connection, stream(), expected_source_sha256=sealed, **settings)
    assert result.submitted_observations == 3


def test_multirun_external_merge_uses_only_reserved_regions_and_strict_actual_membership(tmp_path, monkeypatch):
    settings = options(tmp_path)
    settings["ledger_cap_bytes"] = 8192
    settings["limits"] = replace(DEFAULT_LIMITS, block_bytes=512)
    requests, read_requests = [], []
    write, read = owner._Ledger._write, owner._Ledger._read
    def measured_write(ledger, offset, data):
        requests.append((offset, len(data)))
        return write(ledger, offset, data)
    def measured_read(ledger, offset, count):
        read_requests.append(count)
        return read(ledger, offset, count)
    monkeypatch.setattr(owner._Ledger, "_write", measured_write)
    monkeypatch.setattr(owner._Ledger, "_read", measured_read)
    with source(tmp_path, page_size=512, max_rowid=True) as (_path, sealed, connection):
        result = owner.build_receipt_corpus(connection, observations(19), expected_source_sha256=sealed, **settings)
        assert result.new_contents == result.new_receipts == 19
        assert result.ledger_bytes <= 8192 and max(read_requests) <= 512
        assert all(length <= 512 and offset + length <= 8192 for offset, length in requests)
        # 38 records do not fit a 512-byte run (12 entries), so real merge
        # passes must have written both banks after their initial input writes.
        assert sum(1 for offset, length in requests if offset >= 4099 and length > 41) > 2
        assert sorted(path.name for path in settings["owned_directory"].iterdir()) == [
            "legacy-copy.sqlite", "receipt-additions.bin"]


@pytest.mark.parametrize("kind", ["duplicate", "missing", "extra", "changed-member"],
                         ids=["duplicate", "missing", "extra", "same-count-member"])
def test_terminal_exact_membership_rejects_real_sorted_ledger_corruption(tmp_path, monkeypatch, kind):
    settings = options(tmp_path)
    finished = owner._Ledger.finish
    def corrupted(ledger):
        finished(ledger)
        offset = ledger._offset(ledger.bank, 0)
        records = [ledger._read(offset + index * 41, 41) for index in range(ledger.count)]
        entries = [owner._RECORD.unpack(raw) for raw in records]
        if kind == "duplicate":
            entries[1] = entries[0]
        elif kind == "missing":
            entries.pop()
            ledger.count -= 1
        elif kind == "extra":
            entries.append((2, 999, b"x" * 32))
            ledger.count += 1
        else:
            tag, rowid, row_hash = entries[-1]
            entries[-1] = (tag, rowid + 999, row_hash)
        # Model a real bad merge result before sealing, not a forged success
        # return. All terminal code and the actual source/output scans run.
        ledger.final_identity = None
        ledger._write(offset, b"".join(owner._RECORD.pack(*entry) for entry in entries))
        ledger._write(0, ledger._header())
        os.fsync(ledger.fd)
        ledger.final_identity = owner._file_identity(ledger.build.ledger_path)
    monkeypatch.setattr(owner._Ledger, "finish", corrupted)
    with source(tmp_path) as (_path, sealed, connection):
        with pytest.raises(StorageIntegrityError, match="ledger|membership"):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)


@pytest.mark.parametrize("mutation", ["old-bytes", "missing-old", "new-bytes", "missing-new", "extra-new", "same-count-member"],
                         ids=["old-bytes", "missing-old", "new-bytes", "missing-new", "extra-new", "same-count-member"])
def test_full_after_commit_scan_rejects_unauthorized_real_sql_mutation(tmp_path, monkeypatch, mutation):
    settings = options(tmp_path)
    finished = owner._Ledger.finish
    def changed(ledger):
        finished(ledger)
        connection = ledger.build.connection
        if mutation == "old-bytes":
            connection.execute("UPDATE artifacts SET kind='rewritten'").close()
        elif mutation == "missing-old":
            connection.execute("DELETE FROM artifacts").close()
        elif mutation == "new-bytes":
            connection.execute("UPDATE context_observations SET source='rewritten'").close()
        elif mutation == "missing-new":
            connection.execute("DELETE FROM context_observations WHERE rowid=(SELECT min(rowid) FROM context_observations)").close()
        elif mutation == "extra-new":
            connection.execute("INSERT INTO context_contents VALUES('extra',x'0102')").close()
        else:
            connection.execute("UPDATE context_observations SET digest='same-count-other-key' WHERE rowid=1").close()
    monkeypatch.setattr(owner._Ledger, "finish", changed)
    with source(tmp_path) as (_path, sealed, connection):
        with pytest.raises(StorageIntegrityError):
            owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        assert (settings["owned_directory"] / "legacy-copy.sqlite").exists()


@pytest.mark.parametrize("target,when", [("main", "before"), ("main", "after"),
    ("ledger", "before"), ("ledger", "after")], ids=["main-before", "main-after", "ledger-before", "ledger-after"])
def test_late_os_close_error_never_succeeds_or_leaves_a_known_owned_fd(tmp_path, monkeypatch, target, when):
    settings = options(tmp_path)
    opened, closed, fstat = os.open, os.close, os.fstat
    descriptor, failed = [], []
    def capture(path, flags, *args, **kwargs):
        value = opened(path, flags, *args, **kwargs)
        is_target = (Path(path).name == "receipt-additions.bin" if target == "ledger" else
                     Path(path).name == "legacy-copy.sqlite" and not flags & os.O_CREAT)
        if is_target:
            descriptor.append(value)
        return value
    def failure(value):
        if descriptor and value == descriptor[-1] and not failed:
            failed.append(True)
            if when == "after":
                closed(value)
            raise OSError("deliberate terminal OS close error")
        return closed(value)
    with source(tmp_path) as (_path, sealed, connection):
        monkeypatch.setattr(os, "open", capture)
        monkeypatch.setattr(os, "close", failure)
        try:
            with pytest.raises((OSError, StorageIntegrityError)):
                owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
            assert descriptor and failed == [True]
            with pytest.raises(OSError):
                fstat(descriptor[-1])
        finally:
            for value in descriptor:
                try:
                    fstat(value)
                except OSError:
                    continue
                closed(value)


def error_codes(error):
    codes = []
    while error is not None:
        codes.append(getattr(error, "sqlite_errorcode", None))
        error = error.__cause__
    return codes


@pytest.mark.parametrize("failure", ["full", "too-big"], ids=["sqlite-full", "sqlite-toobig"])
def test_real_sqlite_hard_allocation_errors_roll_back_and_retain_corpus(tmp_path, monkeypatch, failure):
    settings = options(tmp_path)
    opened, captured = owner._Build.open_copied_writer, []
    def capture(build, *args):
        opened(build, *args)
        captured.append(build.connection)
        if failure == "too-big":
            build.connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 2048)
    monkeypatch.setattr(owner._Build, "open_copied_writer", capture)
    with source(tmp_path) as (path, sealed, connection):
        if failure == "full":
            settings["main_cap_bytes"] = path.stat().st_size + 8 * 4096
        before = path.read_bytes()
        def actual_inputs():
            yield next(observations())
            value, clock = next(observations(2))
            # Real normalization/SQL allocation fixture, not source-truth proof.
            value = dict(value, payload={"status": "x" * (256 * 1024 if failure == "full" else 4096)})
            yield value, clock
        with pytest.raises(StorageLimitError) as caught:
            owner.build_receipt_corpus(connection, actual_inputs(), expected_source_sha256=sealed, **settings)
        expected = sqlite3.SQLITE_FULL if failure == "full" else sqlite3.SQLITE_TOOBIG
        assert expected in error_codes(caught.value)
        assert path.read_bytes() == before
        assert (settings["owned_directory"] / "receipt-additions.bin").exists()
        with reader(settings["owned_directory"] / "legacy-copy.sqlite") as output:
            assert output.execute("SELECT count(*) FROM context_observations").fetchone() == (0,)
            assert inventory_raw(output) == inventory_raw(connection)
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            captured[0].execute("SELECT 1")


@pytest.mark.parametrize("failure", ["denied", "busy", "before", "after"], ids=["denied", "busy", "before", "after"])
def test_actual_commit_failure_never_returns_partial_or_unverified_success(tmp_path, monkeypatch, failure):
    settings = options(tmp_path)
    opened, committed = owner._Build.open_copied_writer, TrackedConnection.commit
    captured, commits, locks, denied = [], [], [], []
    def capture(build, *args):
        opened(build, *args)
        captured.append(build.connection)
        if failure == "denied":
            def authorizer(code, operation, _name, _database, _source):
                if code == sqlite3.SQLITE_TRANSACTION and operation == "COMMIT":
                    denied.append(operation)
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            build.connection.set_authorizer(authorizer)
    def commit(connection):
        if captured and connection is captured[0]:
            commits.append(True)
            if failure == "before":
                raise sqlite3.OperationalError("failure before actual commit")
            result = committed(connection)
            if failure == "after":
                raise sqlite3.OperationalError("failure after actual commit")
            return result
        return committed(connection)
    def actual_inputs():
        yield from observations()
        if failure == "busy":
            lock = sqlite3.connect((settings["owned_directory"] / "legacy-copy.sqlite").as_uri() + "?mode=ro",
                                   uri=True, isolation_level=None)
            locks.append(lock)
            lock.execute("BEGIN").close()
            assert lock.execute("SELECT count(*) FROM context_observations").fetchone() == (0,)
    with source(tmp_path) as (path, sealed, connection):
        before = path.read_bytes()
        monkeypatch.setattr(owner._Build, "open_copied_writer", capture)
        monkeypatch.setattr(TrackedConnection, "commit", commit)
        try:
            with pytest.raises(StorageIntegrityError) as caught:
                owner.build_receipt_corpus(connection, actual_inputs(), expected_source_sha256=sealed, **settings)
            if failure == "busy":
                assert sqlite3.SQLITE_BUSY in error_codes(caught.value)
        finally:
            for lock in locks:
                lock.close()
        assert commits == [True] and path.read_bytes() == before
        if failure == "denied":
            assert denied == ["COMMIT"]
        with reader(settings["owned_directory"] / "legacy-copy.sqlite") as output:
            assert output.execute("SELECT count(*) FROM context_observations").fetchone() == (3 if failure == "after" else 0,)
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            captured[0].execute("SELECT 1")


@pytest.mark.parametrize("collision", ["content", "receipt"], ids=["content", "receipt"])
def test_actual_source_collisions_match_legacy_rejection_and_leave_all_old_rows(tmp_path, collision):
    settings = options(tmp_path)
    with source(tmp_path) as (path, _sealed, held):
        held.commit()  # Fixture setup ends before the actual sealed admission.
    record, clock = next(observations())
    content = normalize_observation(record, observed_at=clock)
    content_hash = digest(content)
    receipt_hash = digest({"content_digest": content_hash, "observed_at": canonical_timestamp(clock)})
    with closing(sqlite3.connect(path)) as seed:
        if collision == "content":
            seed.execute("INSERT INTO context_contents VALUES(?,?)", (content_hash, b"wrong\x00raw"))
        else:
            old = seed.execute("SELECT content_digest FROM context_contents").fetchone()[0]
            seed.execute("INSERT INTO context_observations VALUES(?,?,?,?,?,?,?,?)",
                         (receipt_hash, old, "wrong", "wrong", "wrong", "wrong", "wrong", "wrong"))
        seed.commit()
    before = path.read_bytes()
    reference = tmp_path / "collision-reference.sqlite"
    shutil.copyfile(path, reference)
    with pytest.raises(ContextIntegrityError):
        legacy.append_observation(reference, record, observed_at=clock)
    with reader(path) as held:
        with pytest.raises(ContextIntegrityError):
            owner.build_receipt_corpus(held, [(record, clock)], expected_source_sha256=hashlib.sha256(before).hexdigest(), **settings)
        with reader(settings["owned_directory"] / "legacy-copy.sqlite") as output:
            assert inventory_raw(output) == inventory_raw(held)
    assert path.read_bytes() == before


def test_all_normal_cursor_blob_handles_close_and_writer_runs_exactly_one_commit(tmp_path, monkeypatch):
    settings = options(tmp_path)
    opened, verified, execute = owner._Build.open_copied_writer, owner._Build.verify_complete, owner.TrackedCursor.execute
    connections, writer_sql, retained = [], [], []
    def capture_query(cursor, sql, *args, **kwargs):
        if (getattr(cursor.connection, "cursor", None) is not None
                and "cursor" in cursor.connection.__dict__):
            writer_sql.append(sql)
        return execute(cursor, sql, *args, **kwargs)
    def capture(build, *args):
        opened(build, *args)
        connections.append(build.connection)
        retained.extend([build.connection.execute("SELECT * FROM artifacts"),
                         build.connection.blobopen("context_contents", "payload", -7, readonly=True)])
    def verify(build):
        for handle in retained:
            with pytest.raises(sqlite3.ProgrammingError):
                handle.fetchone() if isinstance(handle, sqlite3.Cursor) else handle.read(1)
        return verified(build)
    with source(tmp_path) as (_path, sealed, connection):
        generation, policy = connection.transaction_generation, dict(connection.__dict__)
        pragmas = ("temp_store", "cache_size", "mmap_size", "max_page_count", "query_only", "trusted_schema", "threads")
        values = [connection.execute("PRAGMA " + name).fetchone() for name in pragmas]
        monkeypatch.setattr(owner.TrackedCursor, "execute", capture_query)
        monkeypatch.setattr(owner._Build, "open_copied_writer", capture)
        monkeypatch.setattr(owner._Build, "verify_complete", verify)
        committed, commits = TrackedConnection.commit, []
        def commit(target):
            if connections and target is connections[0]:
                commits.append(True)
            return committed(target)
        monkeypatch.setattr(TrackedConnection, "commit", commit)
        result = owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        assert result.new_receipts == 3 and commits == [True]
        assert writer_sql[0] == "PRAGMA temp_store=MEMORY"
        assert [sql for sql in writer_sql if sql.startswith("BEGIN")] == ["BEGIN IMMEDIATE"]
        assert not any(sql.startswith(("CREATE", "ALTER", "DROP", "VACUUM", "ATTACH")) for sql in writer_sql)
        assert connection.transaction_generation == generation and connection.__dict__ == policy
        assert [connection.execute("PRAGMA " + name).fetchone() for name in pragmas] == values
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connections[0].execute("SELECT 1")


def test_same_real_content_at_distinct_ingestion_clocks_matches_all_legacy_fields(tmp_path):
    settings = options(tmp_path)
    value, clock = next(observations())
    inputs = [(value, clock), (value, clock + timedelta(minutes=1)), (value, clock)]
    with source(tmp_path) as (path, sealed, connection):
        reference = tmp_path / "clock-reference.sqlite"
        shutil.copyfile(path, reference)
        expected = [legacy.append_observation(reference, row, observed_at=at) for row, at in inputs]
        result = owner.build_receipt_corpus(connection, iter(inputs), expected_source_sha256=sealed, **settings)
        assert result.submitted_observations == 3 and result.new_contents == 1 and result.new_receipts == 2
        assert expected[0] == expected[2] != expected[1]
        with reader(result.path) as output, reader(reference) as old:
            assert output.execute(legacy._SELECT + " ORDER BY r.digest").fetchall() == old.execute(legacy._SELECT + " ORDER BY r.digest").fetchall()


def test_receipt_already_in_sealed_source_is_preserved_and_not_ledger_added(tmp_path):
    settings = options(tmp_path)
    with source(tmp_path) as (path, _sealed, connection):
        connection.commit()
    first, clock = next(observations())
    receipt = legacy.append_observation(path, first, observed_at=clock)
    sealed = hashlib.sha256(path.read_bytes()).hexdigest()
    with reader(path) as connection:
        result = owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        assert result.new_contents == result.new_receipts == 2 and result.submitted_observations == 3
        with reader(result.path) as output:
            assert output.execute(legacy._SELECT + " WHERE r.digest=?", (receipt,)).fetchone() == connection.execute(legacy._SELECT + " WHERE r.digest=?", (receipt,)).fetchone()


@pytest.mark.parametrize("drift", ["commit-restart", "rollback-restart", "script-restart", "temp-ddl", "main-ddl", "query-only",
    "row-factory", "text-factory", "isolation", "attach-limit", "thread-limit", "defensive", "cache", "mmap"],
    ids=["commit", "rollback", "script", "temp", "ddl", "readonly", "row", "text", "isolation", "attach", "threads", "defensive", "cache", "mmap"])
def test_real_writer_lifetime_and_profile_drift_stops_and_closes(tmp_path, monkeypatch, drift):
    settings = options(tmp_path)
    opened, captured = owner._Build.open_copied_writer, []
    def capture(build, *args):
        opened(build, *args)
        captured.append(build.connection)
    monkeypatch.setattr(owner._Build, "open_copied_writer", capture)
    def changed():
        yield next(observations())
        connection = captured[0]
        if drift == "commit-restart":
            connection.commit()
            connection.execute("BEGIN IMMEDIATE").close()
        elif drift == "rollback-restart":
            connection.rollback()
            connection.execute("BEGIN IMMEDIATE").close()
        elif drift == "script-restart":
            connection.executescript("COMMIT; BEGIN IMMEDIATE;").close()
        elif drift == "temp-ddl":
            connection.execute("CREATE TEMP TABLE extra(value)").close()
        elif drift == "main-ddl":
            connection.execute("CREATE TABLE extra(value)").close()
        elif drift == "query-only":
            connection.execute("PRAGMA query_only=ON").close()
        elif drift == "row-factory":
            connection.row_factory = sqlite3.Row
        elif drift == "text-factory":
            connection.text_factory = bytes
        elif drift == "isolation":
            connection.isolation_level = "DEFERRED"
        elif drift == "attach-limit":
            connection.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 1)
        elif drift == "thread-limit":
            connection.setlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS, 1)
        elif drift == "defensive":
            connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, False)
        elif drift == "cache":
            connection.execute("PRAGMA cache_size=-100").close()
        else:
            connection.execute("PRAGMA mmap_size=65536").close()
    with source(tmp_path) as (path, sealed, connection):
        before = path.read_bytes()
        with pytest.raises(StorageIntegrityError):
            owner.build_receipt_corpus(connection, changed(), expected_source_sha256=sealed, **settings)
        assert path.read_bytes() == before
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            sqlite3.Connection.execute(captured[0], "SELECT 1")
        with reader(settings["owned_directory"] / "legacy-copy.sqlite") as output:
            expected = 1 if drift in {"commit-restart", "script-restart"} else 0
            # An unsupported caller's already performed commit cannot be undone.
            assert output.execute("SELECT count(*) FROM context_observations").fetchone() == (expected,)


@pytest.mark.parametrize("boundary", ["workspace", "free", "limits", "source-restart", "sidecar"],
                         ids=["workspace", "free", "limits", "source", "sidecar"])
def test_full_slot_and_midbuild_observed_boundaries_are_not_silent_success(tmp_path, monkeypatch, boundary):
    settings = options(tmp_path)
    limits = replace(DEFAULT_LIMITS)
    settings["limits"] = limits
    if boundary == "workspace":
        (settings["workspace"] / "other-qa.bin").write_bytes(b"x" * 1024)
        settings["limits"] = replace(limits, workspace_bytes=2 * settings["main_cap_bytes"] + settings["ledger_cap_bytes"] + 65536 + 1023)
    elif boundary == "free":
        actual = owner.shutil.disk_usage(settings["workspace"])
        remaining = 2 * settings["main_cap_bytes"] + settings["ledger_cap_bytes"] + 65536
        monkeypatch.setattr(owner.shutil, "disk_usage", lambda _: type(actual)(actual.total, actual.used, limits.min_free_bytes + remaining - 1))
    with source(tmp_path) as (path, sealed, connection):
        before = path.read_bytes()
        def changes():
            yield next(observations())
            if boundary == "limits":
                object.__setattr__(limits, "workspace_bytes", limits.workspace_bytes - 1)
            elif boundary == "source-restart":
                connection.commit()
                connection.execute("BEGIN").close()
            elif boundary == "sidecar":
                (settings["owned_directory"] / "unexpected.sqlite-wal").write_bytes(b"held evidence")
        with pytest.raises((StorageLimitError, StorageIntegrityError)):
            owner.build_receipt_corpus(connection, changes(), expected_source_sha256=sealed, **settings)
        assert path.read_bytes() == before
        if boundary in {"workspace", "free"}:
            assert list(settings["owned_directory"].iterdir()) == []
        else:
            with reader(settings["owned_directory"] / "legacy-copy.sqlite") as output:
                assert output.execute("SELECT count(*) FROM context_observations").fetchone() == (0,)


@pytest.mark.parametrize("failure", ["short", "zero", "read-eof", "fsync", "bad-bytes"],
                         ids=["short", "zero", "eof", "fsync", "torn"])
def test_real_ledger_io_progress_and_durability_failures_are_checked(tmp_path, monkeypatch, failure):
    settings = options(tmp_path)
    created, read, write, sync = owner._Ledger.__init__, os.read, os.write, os.fsync
    ledger, events = [], []
    def capture(self, *args):
        created(self, *args)
        ledger.append(self)
    def writes(fd, data):
        if ledger and fd == ledger[0].fd:
            events.append("write")
            if failure == "short":
                return write(fd, data[:max(1, len(data) // 2)])
            if failure == "zero":
                return 0
            if failure == "bad-bytes":
                damaged = bytearray(data)
                damaged[-1] ^= 1
                return write(fd, damaged)
        return write(fd, data)
    def reads(fd, amount):
        if ledger and fd == ledger[0].fd:
            if failure == "short":
                events.append("read")
                amount = max(1, amount // 2)
            elif failure == "read-eof":
                events.append("eof")
                return b""
        return read(fd, amount)
    def fsync(fd):
        if ledger and fd == ledger[0].fd and failure == "fsync":
            events.append("fsync")
            raise OSError("actual ledger fsync failed")
        return sync(fd)
    with source(tmp_path) as (_path, sealed, connection):
        monkeypatch.setattr(owner._Ledger, "__init__", capture)
        monkeypatch.setattr(os, "write", writes)
        monkeypatch.setattr(os, "read", reads)
        monkeypatch.setattr(os, "fsync", fsync)
        if failure == "short":
            result = owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
            assert result.new_receipts == 3 and "read" in events
        else:
            with pytest.raises((StorageIntegrityError, OSError)):
                owner.build_receipt_corpus(connection, observations(), expected_source_sha256=sealed, **settings)
        assert ledger and ledger[0].fd is None and events
        assert (settings["owned_directory"] / "receipt-additions.bin").exists()
