"""Complete typed copy identity and narrowly permitted private-index delta."""
from contextlib import closing, contextmanager
from dataclasses import replace
import hashlib
import sqlite3

import pytest

import context_observations as observations
import context_tennis_index as index
from context_storage_v2 import receipt_corpus as corpus
from context_storage_v2.receipt_append import append_observation_in_connection
from context_runtime_transaction import TrackedConnection
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2.inventory import inventory_raw
from context_tennis_index_build import build_index
from test_context_storage_receipt_corpus import options, reader
from test_tennis_player_index_append import CLOCK, database, record, snapshot


@contextmanager
def indexed_source(tmp_path, *, max_rowid=False, encoding="UTF-8"):
    path = database(tmp_path)
    # Recreate the fixture for actual UTF-16 scalar-byte inventory coverage.
    if encoding != "UTF-8":
        from context_runtime import _SCHEMA
        from context_tennis_index_build import initialize_index
        path = tmp_path / "encoded.sqlite"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(f"PRAGMA encoding='{encoding}'")
            for sql in _SCHEMA.values():
                connection.execute(sql)
            connection.commit()
        initialize_index(path)
        build_index(path)
    observations.append_observation(path, record(), observed_at=CLOCK)
    if max_rowid:
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("UPDATE context_observations SET rowid=?", (2**63 - 1,))
            connection.commit()
        assert build_index(path).status == "ready"
    before = path.read_bytes()
    with reader(path) as source:
        yield path, hashlib.sha256(before).hexdigest(), source, before


@pytest.mark.parametrize("encoding", ["UTF-8", "UTF-16le", "UTF-16be"])
def test_without_rowid_inventory_is_complete_and_typed(tmp_path, encoding):
    with indexed_source(tmp_path, encoding=encoding) as (path, sealed, source, before):
        original = inventory_raw(source)
        derived = {table.name: table for table in original.tables if table.name.startswith("tennis_")}
        assert set(derived) == {"tennis_player_events", "tennis_player_index_state"}
        assert derived["tennis_player_events"].row_count == 2
        assert derived["tennis_player_index_state"].row_count == 1
        settings = options(tmp_path)
        result = corpus.build_receipt_corpus(source, (), expected_source_sha256=sealed, **settings)
        assert path.read_bytes() == before
        assert result.source_inventory == original
        assert next(table for table in result.inventory.tables if table.name == "tennis_player_events") == derived["tennis_player_events"]
    # A same-length changed TEXT must change the complete derived identity.
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("UPDATE tennis_player_events SET player_id='espn:tennis:ATP:player:8' WHERE player_id='espn:tennis:ATP:player:9'").rowcount == 1
        connection.commit()
    with reader(path) as changed:
        assert inventory_raw(changed).logical_digest != original.logical_digest


@pytest.mark.parametrize("duplicates", [False, True])
def test_copy_empty_or_duplicate_iterator_is_index_invalid(tmp_path, monkeypatch, duplicates):
    settings = options(tmp_path)
    opened = corpus._Build.open_copied_writer
    writers = []
    def capture(self, sealed):
        opened(self, sealed)
        writers.append(self.connection)
    monkeypatch.setattr(corpus._Build, "open_copied_writer", capture)
    with indexed_source(tmp_path) as (path, sealed, source, before):
        original_state, original_memberships, _, _ = snapshot(path)
        class Inputs:
            def __iter__(self):
                assert index.read_index_state(writers[0]).status == "invalid"
                return iter(((record(), CLOCK),) * (2 if duplicates else 0))
        result = corpus.build_receipt_corpus(source, Inputs(), expected_source_sha256=sealed, **settings)
        with reader(result.path) as copied:
            assert index.read_index_state(copied) == replace(original_state, status="invalid")
            assert copied.execute("SELECT * FROM tennis_player_events ORDER BY tour,player_id,event_key").fetchall() == original_memberships
        assert result.new_receipts == 0
        assert path.read_bytes() == before


@pytest.mark.parametrize("max_rowid", [False, True])
def test_corpus_checks_only_expected_control_delta(tmp_path, max_rowid):
    settings = options(tmp_path)
    with indexed_source(tmp_path, max_rowid=max_rowid) as (path, sealed, source, before):
        original_state, memberships, _, _ = snapshot(path)
        values = ((record(), CLOCK), (record(102), CLOCK), (record(102), CLOCK))
        result = corpus.build_receipt_corpus(source, values, expected_source_sha256=sealed, **settings)
        assert result.submitted_observations == 3 and result.new_receipts == 1
        with reader(result.path) as copied:
            assert index.read_index_state(copied) == replace(original_state,
                source_generation=original_state.source_generation + 1,
                rewrite_generation=original_state.rewrite_generation + int(max_rowid), status="invalid")
            assert copied.execute("SELECT * FROM tennis_player_events ORDER BY tour,player_id,event_key").fetchall() == memberships
        assert path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["membership", "original", "control", "extra-control", "hidden-receipt"])
def test_wrong_player_row_or_original_mutation_is_rejected(tmp_path, monkeypatch, mutation):
    settings = options(tmp_path)
    close_writer = corpus._Build.close_writer
    def corrupt(self, *, commit=False):
        if commit:
            if mutation == "membership":
                assert self.connection.execute("UPDATE tennis_player_events SET player_id='wrong' WHERE player_id='espn:tennis:ATP:player:9'").rowcount == 1
                # Hide the trigger's counter: the full mapping comparison must still fail.
                self.connection.execute("UPDATE tennis_player_index_state SET index_generation=index_generation-1")
            elif mutation == "original":
                self.connection.execute("UPDATE context_contents SET payload=x'00'")
                self.connection.execute("UPDATE tennis_player_index_state SET source_generation=source_generation-1,rewrite_generation=rewrite_generation-1")
            elif mutation == "control":
                self.connection.execute("UPDATE tennis_player_index_state SET logical_bytes=logical_bytes+1")
            elif mutation == "extra-control":
                self.connection.execute("PRAGMA ignore_check_constraints=ON")
                self.connection.execute("INSERT INTO tennis_player_index_state SELECT 2,schema_version,projector_sha256,db_identity,source_generation,index_generation,rewrite_generation,verified_source_generation,verified_index_generation,verified_rewrite_generation,logical_bytes,covered_rowid,status FROM tennis_player_index_state")
            else:
                self.connection.execute("INSERT INTO context_observations SELECT 'unregistered',content_digest,event_key,observed_at,schedule_revision,source,subject_id,kind FROM context_observations LIMIT 1")
                self.connection.execute("UPDATE tennis_player_index_state SET source_generation=source_generation-1")
        return close_writer(self, commit=commit)
    monkeypatch.setattr(corpus._Build, "close_writer", corrupt)
    with indexed_source(tmp_path) as (path, sealed, source, before):
        with pytest.raises(StorageIntegrityError):
            corpus.build_receipt_corpus(source, ((record(102), CLOCK),), expected_source_sha256=sealed, **settings)
        assert path.read_bytes() == before


def test_derived_values_are_bounded_before_materialization(tmp_path):
    with indexed_source(tmp_path) as (path, _sealed, _source, _before):
        pass
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("UPDATE tennis_player_events SET player_id=? WHERE player_id='espn:tennis:ATP:player:9'", ("x" * 70000,)).rowcount == 1
        connection.commit()
    with reader(path) as source:
        with pytest.raises(StorageLimitError):
            inventory_raw(source, limits=replace(DEFAULT_LIMITS, block_bytes=32768))


def test_derived_storage_coercion_is_not_raw_identity(tmp_path):
    with indexed_source(tmp_path) as (path, _sealed, _source, _before):
        pass
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        assert connection.execute("UPDATE tennis_player_events SET player_id=x'39' WHERE player_id='espn:tennis:ATP:player:9'").rowcount == 1
        connection.commit()
    with reader(path) as source:
        with pytest.raises(StorageIntegrityError):
            inventory_raw(source)


def test_v2_receipt_hook_preserves_ready_same_file_and_rolls_back_together(tmp_path):
    path = database(tmp_path)
    before = snapshot(path)
    with closing(sqlite3.connect(path, factory=TrackedConnection, isolation_level=None,
                                autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        append_observation_in_connection(connection, record(), observed_at=CLOCK)
        state = index.read_index_state(connection)
        assert state.status == "ready"
        assert state.source_generation == state.verified_source_generation == 1
        assert state.index_generation == state.verified_index_generation == 2
        assert connection.execute("SELECT count(*) FROM tennis_player_events").fetchone() == (2,)
        # Both the derived rows and their sources belong to the caller's transaction.
        connection.rollback()
    assert snapshot(path) == before


@pytest.mark.parametrize("status", ["building", "ready", "invalid"])
def test_copy_empty_source_preserves_null_cursor_and_never_certifies(tmp_path, status):
    path = database(tmp_path)
    with closing(sqlite3.connect(path)) as writer:
        writer.execute("UPDATE tennis_player_index_state SET status=?", (status,))
        writer.commit()
    state = snapshot(path)[0]
    before = path.read_bytes()
    with reader(path) as source:
        result = corpus.build_receipt_corpus(source, (), expected_source_sha256=hashlib.sha256(before).hexdigest(),
                                             **options(tmp_path))
        with reader(result.path) as copied:
            assert index.read_index_state(copied) == replace(state, status="invalid")
            assert index.read_index_state(copied).covered_rowid is None
            assert copied.execute("SELECT count(*) FROM tennis_player_events").fetchone() == (0,)
    assert path.read_bytes() == before
