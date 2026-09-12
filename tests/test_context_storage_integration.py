"""Actual closed source -> raw inventory -> one spool -> streaming features.

Offline equivalence only: this is not a migration, a complete-input quota owner,
native capacity evidence, a B proof, an empirical model approval or release.
"""
from contextlib import contextmanager
from datetime import timedelta
import hashlib
from pathlib import Path
import sqlite3

import pytest

from context_models.tennis_v3 import tennis_features_v3
from context_runtime_inventory import VerifiedReceiptMapping
from context_runtime_tennis import _cold_replay_history
from context_runtime_transaction import TrackedConnection
from context_storage_v2.contracts import StorageIntegrityError
from context_storage_v2.history import build_history
from context_storage_v2.inventory import inventory_raw
from context_storage_v2.tennis import tennis_features_streaming
from model_artifacts import canonical_bytes
from test_context_tennis_capture import NOW, competition, persist, records
from test_tennis_context_features import base, event


@contextmanager
def sealed_shape_reader(db):
    # A real read-only file/held transaction, not a claimed Linux DAC seal.
    con = sqlite3.connect(db.absolute().as_uri() + "?mode=ro", uri=True,
                          factory=TrackedConnection)
    con.execute("PRAGMA trusted_schema=OFF")
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("BEGIN")
    try:
        yield con
    finally:
        con.close()


@pytest.mark.parametrize("shift", [0, -90, -180])
def test_complete_inventory_and_earlier_views_share_one_source_generation(tmp_path, shift):
    db = tmp_path / "original.sqlite"
    for ident, hours in (("101", 4), ("101", 2), ("102", 1)):
        at = NOW - timedelta(hours=hours)
        persist(db, records(competition(id=ident), clock=at), clock=at)
    # Future and foreign-tour physical receipts must stay in the full inventory.
    at = NOW + timedelta(seconds=1)
    persist(db, records(competition(id="400"), clock=at), clock=at)
    at = NOW - timedelta(hours=2)
    persist(db, records(competition(id="401"), clock=at, tour="WTA",
                        slug="womens-singles"), clock=at)
    original_sha = hashlib.sha256(db.read_bytes()).hexdigest()
    cutoff = NOW + timedelta(minutes=shift)
    ev, work = event(), tmp_path / "private"
    work.mkdir()
    with sealed_shape_reader(db) as con:
        before = inventory_raw(con)
        receipts = VerifiedReceiptMapping(con)
        receipts.validate_all()
        with build_history(receipts, directory=work, cutoff=NOW, tour="ATP",
                           input_identity=original_sha) as maximum:
            with maximum.as_of(cutoff) as prefix:
                assert prefix.path == maximum.path
                expected_history = _cold_replay_history(receipts, cutoff=cutoff,
                                                       tour="ATP", max_bytes=None)
                basis = base(ev, cutoff=cutoff)
                expected = tennis_features_v3(ev, expected_history, basis, cutoff=cutoff)
                with tennis_features_streaming(ev, prefix, basis, cutoff=cutoff,
                                               work_directory=work) as features:
                    assert b"".join(features.iter_canonical_chunks()) == canonical_bytes(expected)
                    assert features.canonical_digest() == hashlib.sha256(canonical_bytes(expected)).hexdigest()
                    assert features.history_binding.input_identity == original_sha
                assert prefix.binding.source_receipt_count == 15
                assert len(list(work.rglob("history.sqlite"))) == 1
            maximum.assert_intact()
        assert inventory_raw(con) == before
    assert hashlib.sha256(db.read_bytes()).hexdigest() == original_sha


def test_actual_result_cannot_outlive_source_transaction(tmp_path):
    db = tmp_path / "original.sqlite"
    at = NOW - timedelta(hours=1)
    persist(db, records(competition(), clock=at), clock=at)
    original_sha = hashlib.sha256(db.read_bytes()).hexdigest()
    with sealed_shape_reader(db) as con:
        inventory_raw(con)
        receipts = VerifiedReceiptMapping(con)
        receipts.validate_all()
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=original_sha) as history:
            ev = event()
            result = tennis_features_streaming(ev, history, base(ev), cutoff=NOW,
                                               work_directory=tmp_path)
            try:
                stream = result.iter_canonical_chunks()
                next(stream)
                con.commit()
                con.execute("BEGIN")
                with pytest.raises((StorageIntegrityError, RuntimeError, ValueError)):
                    next(stream)
            finally:
                result.close()
            # Explicit close prevents __exit__ from interpreting the deliberately
            # invalidated source as a successful normal-completion assertion.
            history.close()


def test_private_history_temp_schema_cannot_hide_complete_rows(tmp_path):
    db = tmp_path / "original.sqlite"
    at = NOW - timedelta(hours=1)
    persist(db, records(competition(), clock=at), clock=at)
    with sealed_shape_reader(db) as con:
        receipts = VerifiedReceiptMapping(con)
        receipts.validate_all()
        history = build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                                input_identity=hashlib.sha256(db.read_bytes()).hexdigest())
        try:
            assert len(list(history.iter_rows())) == 3
            private = history._state.connection
            changes = private.total_changes
            private.execute("PRAGMA query_only=OFF")
            private.execute("CREATE TEMP VIEW history AS SELECT * FROM main.history WHERE 0")
            private.execute("PRAGMA query_only=ON")
            assert private.total_changes == changes
            # DDL has no row-change count and changes no main file byte. It
            # nevertheless invalidates the complete private read generation.
            with pytest.raises(StorageIntegrityError):
                list(history.iter_rows())
        finally:
            history.close()


def test_actual_source_to_lossless_copy_to_parts_reopens_with_complete_raw_coverage(tmp_path):
    from context_storage_v2.copying import copy_legacy
    from context_storage_v2 import refs, snapshots, snapshot_source
    from context_storage_v2.contracts import DEFAULT_LIMITS
    from test_context_storage_snapshot_source import packet, source, target

    known = [packet(family=family, with_effect=effect)
             for family in ("tennis:winner", "tennis:serve") for effect in (False, True)]
    opaque = ("e" * 64, {"kind": "legacy-opaque", "original": "do not reinterpret"})
    work = tmp_path / "whole-private-job"
    work.mkdir()
    with source(tmp_path, [*known, opaque]) as (original_path, original):
        original_hash = hashlib.sha256(original_path.read_bytes()).hexdigest()
        copied = copy_legacy(original, directory=work, expected_source_sha256=original_hash)
        assert copied.copy_sha256 == copied.source_sha256 == original_hash
        with sealed_shape_reader(copied.path) as copy_reader:
            with target(work) as output:
                parts_path = output.execute("PRAGMA database_list").fetchone()[2]
                coverage = snapshot_source.adapt_source_snapshots(copy_reader, output, copied.inventory)
                assert coverage.snapshot_count == 5
                assert coverage.adapted_count == 4 and coverage.unadapted_count == 1
                # Equal raw source generations remain interchangeable inputs,
                # but every call freshly checks all source rows and output keys.
                snapshot_source.validate_source_coverage(original, output, coverage)
                output.commit()
            with sealed_shape_reader(Path(parts_path)) as reopened:
                reopened.execute("PRAGMA cache_size=-4096")
                reopened.execute("PRAGMA mmap_size=0")
                reopened.execute(f"PRAGMA max_page_count={DEFAULT_LIMITS.input_bytes // 4096}")
                snapshot_source.validate_source_coverage(copy_reader, reopened, coverage)
                snapshot_source.validate_source_coverage(original, reopened, coverage)
                for key, payload in known:
                    descriptor = snapshots._read_descriptor(reopened, key)
                    assert b"".join(snapshots.iter_snapshot_bytes(reopened, descriptor)) == canonical_bytes(payload)
                assert reopened.execute("SELECT count(*) FROM v2_snapshot_parts WHERE key=?", (opaque[0],)).fetchone() == (0,)
                refs.validate_all(reopened)
            assert inventory_raw(copy_reader) == copied.inventory
        assert inventory_raw(original) == copied.inventory
        assert hashlib.sha256(original_path.read_bytes()).hexdigest() == original_hash
        assert hashlib.sha256(copied.path.read_bytes()).hexdigest() == original_hash
