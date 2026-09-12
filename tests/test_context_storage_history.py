"""C3 differential tests use genuine source normalization and physical receipts."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import hashlib
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_observations import append_observation
from context_runtime_inventory import VerifiedReceiptMapping
from context_runtime_tennis import _cold_replay_history
from context_runtime_transaction import TrackedConnection
from context_storage_v2.contracts import StorageIntegrityError, StorageLimitError, StorageLimits
from context_storage_v2.history import EventHistory, HistoryView, build_history
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_context_tennis_capture import NOW, competition, persist, records


TEST_MAIN_CAP_BYTES = 4 * 1024**2


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def source(db, *, protected=(), validate=True):
    connection = sqlite3.connect(Path(db).absolute().as_uri() + "?mode=ro", uri=True,
                                 factory=TrackedConnection)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        receipts = VerifiedReceiptMapping(connection, protected_receipts=protected)
        if validate:
            receipts.validate_all()
        yield connection, receipts
    finally:
        connection.close()


@pytest.fixture
def real_history(tmp_path):
    db = tmp_path / "input.db"
    # Interleaved event order, same-time bilateral receipts, an earlier revision,
    # foreign tour and future rows all go through the actual capture owner.
    for ident, hours in (("302", 3), ("101", 4), ("302", 1), ("203", 4)):
        at = NOW - timedelta(hours=hours)
        persist(db, records(competition(id=ident), clock=at), clock=at)
    at = NOW - timedelta(hours=2)
    persist(db, records(competition(id="101"), clock=at, tour="WTA", slug="womens-singles"), clock=at)
    at = NOW + timedelta(microseconds=1)
    persist(db, records(competition(id="400"), clock=at), clock=at)
    return db


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
@pytest.mark.parametrize("shift", [-240, -120, 0, 1])
def test_matches_entire_unchanged_cold_tuple_bytes_order_and_repeated_reads(real_history, tmp_path, tour, shift):
    cutoff = NOW + timedelta(minutes=shift)
    with source(real_history) as (_, receipts):
        expected = _cold_replay_history(receipts, cutoff=cutoff, tour=tour, max_bytes=None)
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=cutoff, tour=tour,
                           input_identity=_sha(real_history)) as view:
            assert type(view) is HistoryView
            assert canonical_bytes(tuple(view.iter_rows())) == canonical_bytes(expected)
            assert view.row_count == len(expected)
            assert view.canonical_bytes == sum(len(canonical_bytes(row)) for row in expected)
            assert canonical_bytes(tuple(view.iter_rows())) == canonical_bytes(expected)
            actual_digest = hashlib.sha256()
            for row in expected:
                raw = canonical_bytes(row)
                actual_digest.update(len(raw).to_bytes(8, "big"))
                actual_digest.update(raw)
            assert view.binding.selected_digest == actual_digest.hexdigest()
            assert view.binding.source_receipt_count == 18
            assert view.binding.opaque_receipt_count == 0
            assert view.cutoff == canonical_timestamp(cutoff) and view.tour == tour


def test_events_preserve_first_occurrence_and_every_revision_without_materialized_groups(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        expected = _cold_replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        ordered = {}
        for row in expected:
            ordered.setdefault(row["event_key"], []).append(row)
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            groups = list(view.iter_events())
            assert [group.event_key for group in groups] == list(ordered)
            for group in groups:
                assert type(group) is EventHistory
                assert canonical_bytes(tuple(group.iter_rows())) == canonical_bytes(ordered[group.event_key])
                latest = max(row["observed_at"] for row in ordered[group.event_key])
                assert group.latest_observed_at == latest
                assert canonical_bytes(tuple(group.iter_latest_rows())) == canonical_bytes(
                    [row for row in ordered[group.event_key] if row["observed_at"] == latest])
            skip = groups[0].event_key
            assert [group.event_key for group in view.iter_events(exclude_event=skip)] == list(ordered)[1:]
            assert view.event("espn:tennis:ATP:match:999") is None
            assert len(list(view.event("espn:tennis:ATP:match:302").iter_rows())) == 6


def test_caller_mutating_returned_rows_never_changes_repeated_read(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            iterator = view.iter_rows()
            row = next(iterator)
            expected = deepcopy(row)
            row["payload"].clear()
            iterator.close()  # Partial reading is not a partial publication.
            assert next(view.iter_rows()) == expected
            view.assert_intact()


@pytest.mark.parametrize("operation", ["commit", "rollback", "restart", "close", "factory", "callback_override"])
def test_source_lifetime_or_custom_connection_invalidates_all_repeatable_handles(real_history, tmp_path, operation):
    with source(real_history) as (connection, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            group = next(view.iter_events())
            iterator = view.iter_rows()
            next(iterator)
            if operation == "restart":
                connection.commit()
                connection.execute("BEGIN")
            elif operation == "factory":
                connection.row_factory = sqlite3.Row
            elif operation == "callback_override":
                connection.execute = lambda *args, **kwargs: None
            else:
                getattr(connection, operation)()
            with pytest.raises((StorageIntegrityError, RuntimeArtifactTrustError, sqlite3.Error)):
                next(iterator)
            with pytest.raises((StorageIntegrityError, RuntimeArtifactTrustError, sqlite3.Error)):
                list(group.iter_rows())


@pytest.mark.parametrize("operation", ["commit", "rollback", "restart", "factory", "trace", "progress", "authorizer"])
def test_private_output_connection_mutation_or_callbacks_fail_closed(real_history, tmp_path, operation):
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            connection = view._state.connection
            try:
                if operation == "restart":
                    connection.commit()
                    connection.execute("BEGIN")
                elif operation == "factory":
                    connection.row_factory = sqlite3.Row
                elif operation == "trace":
                    connection.set_trace_callback(lambda *_: None)
                elif operation == "progress":
                    connection.set_progress_handler(lambda: 0, 1)
                elif operation == "authorizer":
                    connection.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
                else:
                    getattr(connection, operation)()
            except StorageIntegrityError:
                pass
            with pytest.raises(StorageIntegrityError):
                list(view.iter_rows())


@pytest.mark.parametrize("operation", ["history_view", "history_table", "events_view",
                                      "unrelated_temp", "create_drop", "attach", "temp_journal",
                                      "cache", "mmap", "max_pages"])
def test_readonly_spool_schema_database_and_journal_changes_invalidate_next_row(real_history, tmp_path, operation):
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            iterator = view.iter_rows()
            next(iterator)
            if operation == "create_drop":
                # SQLite will not DROP any table while this connection has an
                # active read cursor. Test the reverted DDL before a new read.
                iterator.close()
            connection = view._state.connection
            before = (_sha(view.path), connection.total_changes, connection.transaction_generation)
            connection.execute("PRAGMA query_only=OFF")
            if operation == "history_view":
                connection.execute("CREATE TEMP VIEW history AS SELECT * FROM main.history WHERE 0")
                assert connection.execute("SELECT count(*) FROM history").fetchone() == (0,)
            elif operation == "history_table":
                connection.execute("CREATE TEMP TABLE history(digest TEXT, observed_at TEXT, event_key TEXT, payload BLOB)")
            elif operation == "events_view":
                connection.execute("CREATE TEMP VIEW events AS SELECT * FROM main.events WHERE 0")
            elif operation == "unrelated_temp":
                connection.execute("CREATE TEMP TABLE unrelated(x TEXT)")
            elif operation == "create_drop":
                connection.execute("CREATE TEMP TABLE discarded(x TEXT)")
                connection.execute("DROP TABLE temp.discarded")
                assert connection.execute("SELECT count(*) FROM temp.sqlite_schema").fetchone() == (0,)
            elif operation == "attach":
                with pytest.raises(sqlite3.OperationalError, match="too many attached"):
                    connection.execute("ATTACH DATABASE ':memory:' AS unrelated")
                connection.execute("PRAGMA query_only=ON")
                view.assert_intact()  # The stricter reader rejected the mutation itself.
                assert next(iterator)
                iterator.close()
                return
            elif operation == "temp_journal":
                assert connection.execute("PRAGMA temp.journal_mode=OFF").fetchone() == ("memory",)
                connection.execute("PRAGMA query_only=ON")
                view.assert_intact()  # Defensive mode prevented the journal change.
                assert next(iterator)
                iterator.close()
                return
            elif operation == "cache":
                connection.execute("PRAGMA main.cache_size=-4194304")
            elif operation == "mmap":
                connection.execute("PRAGMA main.mmap_size=1073741824")
            else:
                connection.execute("PRAGMA main.max_page_count=2147483646")
            connection.execute("PRAGMA query_only=ON")
            # These changes do not affect main-file bytes, row writes or the
            # held transaction, so the original checks alone could miss them.
            assert (_sha(view.path), connection.total_changes, connection.transaction_generation) == before
            assert connection.execute("SELECT count(*) FROM main.history").fetchone() == (view.row_count,)
            if operation == "create_drop":
                iterator = view.iter_rows()
            with pytest.raises(StorageIntegrityError):
                next(iterator)
            with pytest.raises(StorageIntegrityError):
                view.assert_intact()


def test_held_history_reader_cannot_switch_temporary_storage_to_file(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            connection = view._state.connection
            assert connection.execute("PRAGMA temp_store").fetchone() == (2,)
            with pytest.raises(sqlite3.OperationalError, match="within a transaction"):
                connection.execute("PRAGMA temp_store=FILE")
            # SQLite refuses the change without ending the held transaction;
            # ending/restarting that transaction is independently rejected.
            assert connection.execute("PRAGMA temp_store").fetchone() == (2,)
            view.assert_intact()
            assert len(list(view.iter_rows())) == view.row_count


@pytest.mark.parametrize("consumer", ["rows", "events", "event", "latest_rows", "prefix"])
def test_temp_shadow_cannot_silently_change_any_complete_history_consumer(real_history, tmp_path, consumer):
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            group = next(view.iter_events())
            connection = view._state.connection
            connection.execute("PRAGMA query_only=OFF")
            connection.execute("CREATE TEMP VIEW history AS SELECT * FROM main.history WHERE 0")
            connection.execute("PRAGMA query_only=ON")
            with pytest.raises(StorageIntegrityError):
                if consumer == "rows":
                    list(view.iter_rows())
                elif consumer == "events":
                    list(view.iter_events())
                elif consumer == "event":
                    view.event(group.event_key)
                elif consumer == "latest_rows":
                    list(group.iter_latest_rows())
                else:
                    view.as_of(NOW - timedelta(hours=2))


def test_source_owner_changed_connection_and_protected_set_are_rejected(real_history, tmp_path):
    with source(real_history) as (connection, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            receipts._protected = frozenset({"0" * 64})
            with pytest.raises(StorageIntegrityError):
                view.assert_intact()
        receipts._protected = frozenset()
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            receipts._connection = sqlite3.connect(real_history)
            try:
                with pytest.raises(StorageIntegrityError):
                    view.assert_intact()
            finally:
                receipts._connection.close()
                receipts._connection = connection


def test_source_file_mutation_after_publication_invalidates_view(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            with real_history.open("ab") as stream:
                stream.write(b"changed")
            with pytest.raises(StorageIntegrityError):
                list(view.iter_rows())


def test_clean_context_exit_checks_mutation_after_the_last_read(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageIntegrityError):
            with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                               input_identity=_sha(real_history)) as view:
                assert len(list(view.iter_rows())) == 12
                with real_history.open("ab") as stream:
                    stream.write(b"late change")


def test_output_connection_is_really_read_only_and_other_writer_cannot_commit(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history)) as view:
            with pytest.raises(sqlite3.OperationalError):
                view._state.connection.execute("DELETE FROM history")
            connection = sqlite3.connect(view.path, timeout=0)
            try:
                connection.execute("DELETE FROM history")
                with pytest.raises(sqlite3.OperationalError):
                    connection.commit()
                connection.rollback()
            finally:
                connection.close()
            # A write attempt may touch the file metadata; either permanent
            # rejection or the unchanged held complete image is acceptable.
            try:
                assert len(list(view.iter_rows())) == view.row_count
            except StorageIntegrityError:
                pass


@pytest.mark.parametrize("which", ["tour", "block", "input", "workspace", "free"])
def test_hard_budgets_do_not_return_a_partial_history(real_history, tmp_path, which):
    kwargs = {"tour_history_bytes": 1} if which == "tour" else {"block_bytes": 1} if which == "block" else (
        {"input_bytes": 1} if which == "input" else {"workspace_bytes": 1} if which == "workspace"
        else {"min_free_bytes": 2**63})
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageLimitError):
            build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                          input_identity=_sha(real_history), limits=StorageLimits(**kwargs))


def test_sqlite_page_cap_prevents_oversized_allocation_before_periodic_measurement(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        with pytest.raises(sqlite3.DatabaseError) as caught:
            build_history(receipts, main_cap_bytes=4096, directory=tmp_path, cutoff=NOW, tour="ATP",
                          input_identity=_sha(real_history), limits=StorageLimits(workspace_bytes=8192))
        assert caught.value.sqlite_errorcode == sqlite3.SQLITE_FULL
        unfinished = list(tmp_path.glob("context-history-*/history.sqlite"))
        assert len(unfinished) == 1 and unfinished[0].stat().st_size <= 8192


@pytest.mark.parametrize("bad", [-1, 0, True, 1.5, 2**80])
def test_invalid_or_overflow_history_budget_rejected(bad):
    with pytest.raises(StorageLimitError):
        StorageLimits(tour_history_bytes=bad)


def test_limits_instance_cannot_shadow_its_owner_validation(real_history, tmp_path):
    limits = StorageLimits()
    object.__setattr__(limits, "block_bytes", 1024**3)
    object.__setattr__(limits, "__post_init__", lambda: None)
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageLimitError):
            build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                          input_identity=_sha(real_history), limits=limits)


def test_later_valid_limits_change_cannot_redefine_published_history(real_history, tmp_path):
    limits = StorageLimits()
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP",
                           input_identity=_sha(real_history), limits=limits) as view:
            iterator = view.iter_rows()
            next(iterator)
            object.__setattr__(limits, "block_bytes", 8 * 1024**2)
            StorageLimits.__post_init__(limits)  # Still valid, but a different contract.
            with pytest.raises(StorageLimitError):
                next(iterator)
            with pytest.raises(StorageIntegrityError):
                view.assert_intact()


def test_unvalidated_owner_direct_iterables_and_wrong_identity_never_become_views(real_history, tmp_path):
    with source(real_history, validate=False) as (_, receipts):
        for value in (receipts, [], {}, iter(())):
            with pytest.raises(StorageIntegrityError):
                build_history(value, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history))
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageIntegrityError):
            build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity="0" * 64)
    with pytest.raises(StorageIntegrityError):
        HistoryView(complete=True)


@pytest.mark.parametrize("tour,clock", [("ATP", NOW + timedelta(days=1)), ("WTA", NOW - timedelta(days=1))])
def test_physical_corruption_cannot_hide_as_future_or_other_tour(tmp_path, tour, clock):
    db = tmp_path / "input.db"
    persist(db, records(clock=clock, tour=tour, slug="mens-singles" if tour == "ATP" else "womens-singles"), clock=clock)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE context_observations SET event_key='espn:tennis:ATP:match:999'")
    with pytest.raises(ContextIntegrityError):
        with source(db):
            pytest.fail("corrupt physical row acquired a completed source validation")


def test_invalid_recognized_other_tour_source_payload_is_validated_before_filter(tmp_path):
    db = tmp_path / "input.db"
    at = NOW - timedelta(hours=1)
    invalid = records(clock=at, tour="WTA", slug="womens-singles")[0]
    invalid["payload"]["competition_revision"] = "0" * 64
    append_observation(db, invalid, observed_at=at)  # Generic physical transport remains valid.
    with source(db) as (_, receipts):
        with pytest.raises(ContextIntegrityError):
            build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(db))


def test_unknown_source_not_promoted_and_protected_final_stays_unopened(tmp_path):
    db = tmp_path / "input.db"
    at = NOW - timedelta(hours=1)
    row = records(clock=at)[0]
    row["source_schema"] = "unrecognized-other-source-v1"
    unknown = append_observation(db, row, observed_at=at)
    final = records(clock=at)[0]
    final["kind"] = "match_outcome"
    protected = append_observation(db, final, observed_at=at)
    with source(db, protected=(protected,)) as (_, receipts):
        expected = _cold_replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(db)) as view:
            assert expected == () and list(view.iter_rows()) == []
            assert view.binding.source_receipt_count == 2 and view.binding.opaque_receipt_count == 1
            assert unknown != protected


def test_unknown_protected_reference_and_nonfinal_protection_fail_closed(real_history, tmp_path):
    with source(real_history, protected=("0" * 64,)) as (_, receipts):
        with pytest.raises(StorageIntegrityError, match="protected reference"):
            build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history))
    with sqlite3.connect(real_history) as connection:
        ref = connection.execute("SELECT digest FROM context_observations LIMIT 1").fetchone()[0]
    with source(real_history, protected=(ref,)) as (_, receipts):
        with pytest.raises(StorageIntegrityError, match="closed final"):
            build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history))


def test_builder_interruption_never_publishes_or_reuses_partial_file(real_history, tmp_path, monkeypatch):
    import context_storage_v2.history as implementation
    original = implementation.select_tennis_observations
    seen = 0
    def interrupted(rows, **kwargs):
        nonlocal seen
        seen += len(rows)
        if seen == 4:
            raise RuntimeError("controlled build interruption")
        return original(rows, **kwargs)
    with source(real_history) as (_, receipts):
        with monkeypatch.context() as local:
            local.setattr(implementation, "select_tennis_observations", interrupted)
            with pytest.raises(RuntimeError, match="controlled build interruption"):
                build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history))
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history)) as view:
            assert view.row_count == 12
            assert len(list(tmp_path.glob("context-history-*"))) == 2


def test_same_source_digest_cannot_appear_twice_in_complete_physical_scan(real_history, tmp_path, monkeypatch):
    import context_storage_v2.history as implementation
    with source(real_history) as (_, receipts):
        original = implementation.context_observations._SELECT
        with monkeypatch.context() as local:
            local.setattr(implementation.context_observations, "_SELECT", original + " UNION ALL " + original)
            with pytest.raises(sqlite3.IntegrityError):
                build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history))


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_earlier_cutoffs_share_one_complete_spool_and_exact_cold_prefixes(real_history, tmp_path, tour):
    with source(real_history) as (_, receipts):
        with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour=tour,
                           input_identity=_sha(real_history)) as parent:
            for delta in (timedelta(days=20), timedelta(hours=4, microseconds=1),
                          timedelta(hours=4), timedelta(hours=2), timedelta()):
                cutoff = NOW - delta
                expected = _cold_replay_history(receipts, cutoff=cutoff, tour=tour, max_bytes=None)
                with parent.as_of(cutoff) as prefix:
                    assert prefix.path == parent.path
                    assert prefix.binding.maximum_cutoff == parent.cutoff
                    assert prefix.cutoff == canonical_timestamp(cutoff)
                    assert prefix.row_count == len(expected)
                    assert prefix.canonical_bytes == sum(len(canonical_bytes(row)) for row in expected)
                    assert canonical_bytes(tuple(prefix.iter_rows())) == canonical_bytes(expected)
                    events = {}
                    for row in expected:
                        events.setdefault(row["event_key"], []).append(row)
                    assert [event.event_key for event in prefix.iter_events()] == list(events)
                    for event in prefix.iter_events():
                        assert event.latest_observed_at == max(row["observed_at"] for row in events[event.event_key])
                        assert canonical_bytes(tuple(event.iter_rows())) == canonical_bytes(events[event.event_key])
                parent.assert_intact()
            assert len(list(tmp_path.glob("context-history-*"))) == 1


def test_prefix_cannot_widen_and_parent_close_invalidates_every_child(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        parent = build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history))
        prefix = parent.as_of(NOW - timedelta(hours=2))
        with pytest.raises(StorageIntegrityError):
            prefix.as_of(NOW)
        parent.assert_intact()
        parent.close()
        with pytest.raises((StorageIntegrityError, sqlite3.Error)):
            list(prefix.iter_rows())
        prefix.close()


def test_large_single_event_uses_bounded_row_and_group_iteration(tmp_path):
    import tracemalloc
    db = tmp_path / "input.db"
    # One event with hundreds of distinct genuine observed revisions is the
    # adversarial grouping case. Use source-valid status-only records, not a
    # preselected tuple or a manufactured complete-history permission flag.
    comp = competition(status={"type": {"state": "pre", "completed": False, "name": "STATUS_SCHEDULED"}})
    for number in range(600):
        at = NOW - timedelta(seconds=600 - number)
        for row in normalize_tennis_status("ATP", "189-2026", comp, grouping_slug="mens-singles", observed_at=at):
            append_observation(db, row, observed_at=at)
    with source(db) as (_, receipts):
        tracemalloc.start()
        try:
            with build_history(receipts, main_cap_bytes=TEST_MAIN_CAP_BYTES, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(db)) as view:
                groups = view.iter_events()
                group = next(groups)
                assert next(groups, None) is None
                assert sum(1 for _ in group.iter_rows()) == 600
                assert sum(1 for _ in group.iter_latest_rows()) == 1
                assert sum(1 for _ in view.iter_rows()) == 600
                _, peak = tracemalloc.get_traced_memory()
                # Python allocation evidence only, not process RSS/AS or VPS
                # capacity acceptance. No 600-row decoded tuple is retained.
                assert peak < 8 * 1024**2
        finally:
            tracemalloc.stop()


def _trace_build_connections(monkeypatch, filename):
    """Test-only base callback injection, before the new reader is bound."""
    original, captured = sqlite3.connect, []
    def traced(database, *args, **kwargs):
        connection = original(database, *args, **kwargs)
        if filename in str(database):
            statements = []
            sqlite3.Connection.set_trace_callback(connection, statements.append)
            captured.append((connection, statements))
        return connection
    monkeypatch.setattr(sqlite3, "connect", traced)
    return captured


def _assert_single_memory_build(captured, *, main_cap, cache_kib):
    assert len(captured) == 2  # Exactly one writer, then one new read-only reader.
    writer, sql = captured[0]
    reader, read_sql = captured[1]
    assert type(writer) is TrackedConnection
    assert sql[0] == read_sql[0] == "PRAGMA temp_store=MEMORY"
    assert "PRAGMA main.synchronous=FULL" in sql
    assert "PRAGMA main.journal_mode=DELETE" in sql
    assert "PRAGMA temp_store=FILE" not in sql + read_sql
    assert [item for item in sql if item.startswith("BEGIN")] == ["BEGIN IMMEDIATE"]
    assert sql.count("COMMIT") == 1
    assert sql.index("BEGIN IMMEDIATE") < next(i for i, item in enumerate(sql) if item.startswith("CREATE"))
    assert not any(item.startswith("ROLLBACK") for item in sql)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        writer.execute("SELECT 1")
    assert reader.execute("PRAGMA temp_store").fetchone() == (2,)
    assert reader.execute("PRAGMA main.cache_size").fetchone() == (-cache_kib,)
    assert reader.execute("PRAGMA main.max_page_count").fetchone() == (main_cap // 4096,)
    assert reader.execute("PRAGMA main.mmap_size").fetchone() == (0,)
    assert reader.execute("PRAGMA threads").fetchone() == (0,)
    assert reader.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED) == 0
    assert reader.getlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS) == 0


def test_fresh_profile_and_owned_slots_preserve_every_cold_row(real_history, tmp_path, monkeypatch):
    import context_storage_v2.history as implementation
    owned = tmp_path / "reserved-history"
    owned.mkdir()
    before = _sha(real_history)
    with source(real_history) as (_, receipts):
        expected = _cold_replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        captured = _trace_build_connections(monkeypatch, "history.sqlite")
        with build_history(receipts, directory=tmp_path, owned_directory=owned,
                           cutoff=NOW, tour="ATP", input_identity=before,
                           main_cap_bytes=TEST_MAIN_CAP_BYTES) as view:
            assert view.path == owned / "history.sqlite"
            _assert_single_memory_build(captured, main_cap=TEST_MAIN_CAP_BYTES, cache_kib=8192)
            assert type(captured[1][0]) is implementation._ReadConnection
            assert canonical_bytes(tuple(view.iter_rows())) == canonical_bytes(expected)
            assert view.binding.spool_digest == _sha(view.path)
        assert list(owned.iterdir()) == [owned / "history.sqlite"]
        with pytest.raises(StorageIntegrityError, match="empty"):
            build_history(receipts, directory=tmp_path, owned_directory=owned,
                          cutoff=NOW, tour="ATP", input_identity=before,
                          main_cap_bytes=TEST_MAIN_CAP_BYTES)
        assert _sha(real_history) == before
    assert not list(tmp_path.glob("context-history-*"))


@pytest.mark.parametrize("bad", [None, 0, -4096, 1, 4097, True, 4096.0, 2**32 + 4096])
def test_explicit_history_main_slot_never_silently_rounds_or_widens(real_history, tmp_path, bad):
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageLimitError):
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                          input_identity=_sha(real_history), main_cap_bytes=bad)
    assert not list(tmp_path.glob("context-history-*"))


@pytest.mark.parametrize("limits", [StorageLimits(input_bytes=TEST_MAIN_CAP_BYTES - 1),
                                    StorageLimits(workspace_bytes=2 * TEST_MAIN_CAP_BYTES - 1)])
def test_history_requires_both_full_logical_slots_within_limits(real_history, tmp_path, limits):
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageLimitError):
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                          input_identity=_sha(real_history), main_cap_bytes=TEST_MAIN_CAP_BYTES, limits=limits)
    assert not list(tmp_path.glob("context-history-*"))


@pytest.mark.parametrize("kind", ["file", "journal", "extra", "nested", "relative"])
def test_owned_history_namespace_is_never_adopted_or_replaced(real_history, tmp_path, kind):
    owned = tmp_path / "reserved-history"
    owned.mkdir()
    names = {"file": "history.sqlite", "journal": "history.sqlite-journal", "extra": "unplanned.bin"}
    foreign = None
    if kind in names:
        foreign = owned / names[kind]
        foreign.write_bytes(b"unrelated existing bytes")
    elif kind == "nested":
        owned = owned / "unreserved-child"
        owned.mkdir()
    else:
        owned = Path("reserved-history")
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageIntegrityError):
            build_history(receipts, directory=tmp_path, owned_directory=owned,
                          cutoff=NOW, tour="ATP", input_identity=_sha(real_history),
                          main_cap_bytes=TEST_MAIN_CAP_BYTES)
    if foreign is not None:
        assert foreign.read_bytes() == b"unrelated existing bytes"
    assert not list(tmp_path.glob("context-history-*"))


@pytest.mark.parametrize("phase", ["after_schema", "before_commit", "after_commit"])
def test_history_reserve_loss_stops_without_publishing_and_retains_charged_path(real_history, tmp_path, monkeypatch, phase):
    import context_storage_v2.history as implementation
    original_open, original_check = implementation.open_fresh_writer, implementation._resource_check
    writers = []
    def captured(*args, **kwargs):
        result = original_open(*args, **kwargs)
        writers.append(result)
        return result
    def checked(*args, **kwargs):
        original_check(*args, **kwargs)
        writer = writers[0]
        connection = writer.connection
        if writer.committed:
            fail = phase == "after_commit"
        else:
            schema_ready = connection.execute("SELECT count(*) FROM sqlite_schema WHERE name='seen'").fetchone() == (1,)
            complete = schema_ready and connection.execute("SELECT count(*) FROM seen").fetchone() == (18,)
            fail = (phase == "after_schema" and schema_ready) or (phase == "before_commit" and complete)
        if fail:
            raise StorageLimitError("controlled observed reserve loss")
    monkeypatch.setattr(implementation, "open_fresh_writer", captured)
    monkeypatch.setattr(implementation, "_resource_check", checked)
    before = _sha(real_history)
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageLimitError, match="reserve loss") as failure:
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=before,
                          main_cap_bytes=TEST_MAIN_CAP_BYTES)
    writer = writers[0]
    assert writer.closed and writer.committed == (phase == "after_commit")
    assert writer.connection is None and writer.path.exists()
    assert any(str(writer.path.parent) in note for note in failure.value.__notes__)
    with sqlite3.connect(writer.path.as_uri() + "?mode=ro", uri=True) as check:
        names = check.execute("SELECT name FROM sqlite_schema").fetchall()
        assert bool(names) == (phase == "after_commit")
    assert _sha(real_history) == before


@pytest.mark.parametrize("change", ["cache", "max_pages", "threads", "attach_limit", "extensions"])
def test_history_builder_profile_drift_abandons_the_complete_transaction(real_history, tmp_path, monkeypatch, change):
    import context_storage_v2.history as implementation
    original = implementation.select_tennis_observations
    opened = implementation.open_fresh_writer
    writers, changed = [], False
    def capture(*args, **kwargs):
        writer = opened(*args, **kwargs)
        writers.append(writer)
        return writer
    def drift(rows, **kwargs):
        nonlocal changed
        selected = original(rows, **kwargs)
        if rows and not changed:
            changed = True
            c = writers[0].connection
            if change == "attach_limit":
                c.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 1)
            elif change == "extensions":
                c.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, True)
            else:
                c.execute({"cache": "PRAGMA cache_size=-1", "max_pages": "PRAGMA max_page_count=2048",
                           "threads": "PRAGMA threads=1"}[change])
        return selected
    monkeypatch.setattr(implementation, "open_fresh_writer", capture)
    monkeypatch.setattr(implementation, "select_tennis_observations", drift)
    with source(real_history) as (_, receipts):
        with pytest.raises(StorageIntegrityError):
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                          input_identity=_sha(real_history), main_cap_bytes=TEST_MAIN_CAP_BYTES)
    assert writers[0].closed and not writers[0].committed
    with sqlite3.connect(writers[0].path.as_uri() + "?mode=ro", uri=True) as check:
        assert check.execute("SELECT name FROM sqlite_schema").fetchall() == []


@pytest.mark.parametrize("change", ["attach_limit", "threads_limit", "extensions", "defensive", "trusted_schema"])
def test_history_reader_new_native_policy_fields_are_lifetime_bound(real_history, tmp_path, change):
    with source(real_history) as (_, receipts):
        with build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history),
                           main_cap_bytes=TEST_MAIN_CAP_BYTES) as view:
            c = view._state.connection
            if change.endswith("limit"):
                c.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED if change == "attach_limit"
                           else sqlite3.SQLITE_LIMIT_WORKER_THREADS, 1)
            else:
                c.setconfig({"extensions": sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION,
                             "defensive": sqlite3.SQLITE_DBCONFIG_DEFENSIVE,
                             "trusted_schema": sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA}[change],
                            change != "defensive")
            with pytest.raises(StorageIntegrityError):
                list(view.iter_rows())


@pytest.mark.parametrize("cap", [4096, 16384, 32768])
def test_real_history_full_rolls_back_the_first_schema_and_all_rows(real_history, tmp_path, monkeypatch, cap):
    import context_storage_v2.history as implementation
    opened, writers = implementation.open_fresh_writer, []
    def capture(*args, **kwargs):
        writer = opened(*args, **kwargs)
        writers.append(writer)
        return writer
    monkeypatch.setattr(implementation, "open_fresh_writer", capture)
    before = _sha(real_history)
    with source(real_history) as (_, receipts):
        with pytest.raises(sqlite3.DatabaseError) as failure:
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP",
                          input_identity=before, main_cap_bytes=cap)
    assert failure.value.sqlite_errorcode == sqlite3.SQLITE_FULL
    writer = writers[0]
    assert writer.closed and not writer.committed and writer.connection is None
    assert writer.path.stat().st_size <= cap
    assert any(str(writer.path.parent) in note for note in failure.value.__notes__)
    with sqlite3.connect(writer.path.as_uri() + "?mode=ro", uri=True) as check:
        assert check.execute("SELECT name FROM sqlite_schema").fetchall() == []
    assert _sha(real_history) == before


def test_history_main_cap_has_no_implicit_default(real_history, tmp_path):
    with source(real_history) as (_, receipts):
        with pytest.raises(TypeError, match="main_cap_bytes"):
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history))
    assert not list(tmp_path.glob("context-history-*"))


@pytest.mark.parametrize("failure", ["memory_setting", "memory_readback", "compile_override"])
def test_readonly_profile_failure_never_returns_a_history_or_deletes_completed_bytes(real_history, tmp_path, monkeypatch, failure):
    import context_storage_v2.history as implementation
    original, captured = sqlite3.connect, []
    def connect(database, *args, **kwargs):
        connection = original(database, *args, **kwargs)
        if kwargs.get("factory") is implementation._ReadConnection:
            captured.append(connection)
            execute = connection.execute
            def controlled(sql, *args):
                if failure == "memory_setting" and sql == "PRAGMA temp_store=MEMORY":
                    raise sqlite3.OperationalError("controlled unavailable reader setting")
                if failure == "memory_readback" and sql == "PRAGMA temp_store":
                    return execute("SELECT 1")
                if failure == "compile_override" and sql == "PRAGMA compile_options":
                    return execute("SELECT 'TEMP_STORE=0'")
                return execute(sql, *args)
            connection.execute = controlled  # Explicit test injection before reader binding.
        return connection
    with source(real_history) as (_, receipts):
        monkeypatch.setattr(sqlite3, "connect", connect)
        with pytest.raises((sqlite3.OperationalError, StorageIntegrityError)) as caught:
            build_history(receipts, directory=tmp_path, cutoff=NOW, tour="ATP", input_identity=_sha(real_history),
                          main_cap_bytes=TEST_MAIN_CAP_BYTES)
    assert len(captured) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        sqlite3.Connection.execute(captured[0], "SELECT 1")
    completed = list(tmp_path.glob("context-history-*/history.sqlite"))
    assert len(completed) == 1
    assert any(str(completed[0].parent) in note for note in caught.value.__notes__)
    with original(completed[0].as_uri() + "?mode=ro", uri=True) as check:
        assert check.execute("SELECT count(*) FROM history").fetchone() == (12,)
