"""Small actual legacy/C consumer differentials, not native capacity or B proof.

The old temporary provider/capture/predict/publication/Shadow owner is the byte
oracle. The NEW bridge never enters Daily, Shadow, provider or legacy writers.
All states/receipts are physically stored by their existing real test owners.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import sqlite3

import pytest

from context_runtime_inventory import VerifiedReceiptMapping
from context_runtime_transaction import TrackedConnection
from context_models.contracts import ContextContractError, ContextIntegrityError, digest
from context_storage_v2.contracts import DEFAULT_LIMITS, StorageIntegrityError, StorageLimitError
from context_storage_v2.history import _configure_read_connection, build_history
from context_storage_v2.inventory import inventory_raw
from context_storage_v2.sqlite_profile import SQLiteWriterPlan, open_fresh_writer
from context_storage_v2 import snapshots
from model_artifacts import ArtifactIntegrityError, _load_artifact, canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_tennis_live_worker import NOW, competition, configure, context_rows, run_batch


CAP = 4 * 1024**2


@contextmanager
def actual_case(tmp_path, monkeypatch, *, tour="ATP", catalog=None,
                on_configured=None, on_stored=None, rejects_raw_inventory=False,
                source_encoding=None):
    from test_tennis_live_integrity import fitted_catalog

    if source_encoding is not None:
        assert source_encoding in {"UTF-16le", "UTF-16be"}
        with sqlite3.connect(tmp_path / "context.db") as initial:
            initial.execute("PRAGMA encoding='"+source_encoding+"'")
            initial.execute("CREATE TABLE artifacts(digest TEXT PRIMARY KEY,kind TEXT NOT NULL,payload BLOB NOT NULL,created_at TEXT NOT NULL)")
    db, predictions, _states, _calls = configure(monkeypatch, tmp_path, tours=(tour,))
    if catalog is not None:
        fitted_catalog(db, monkeypatch, count=catalog[0], wrong_surface=catalog[1])
    if on_configured is not None:
        on_configured(db)
    result, rows = run_batch(db, predictions)
    assert result["stored"] == 1 and not result["errors"]
    key, packet = context_rows(db)[0]
    sidecar = json.loads(rows[0]["context_json"])["context_model"]
    with sqlite3.connect(db) as legacy:
        original_row = legacy.execute("SELECT kind,payload,created_at FROM artifacts WHERE digest=?",
            (sidecar["original_artifact_hash"],)).fetchone()
    if on_stored is not None:
        on_stored(db)
    before = db.read_bytes()
    work = tmp_path / "owned-work"
    work.mkdir()
    history_dir = work / "history"
    history_dir.mkdir()
    con = sqlite3.connect(db.absolute().as_uri() + "?mode=ro", uri=True, factory=TrackedConnection)
    # A reader's logical main-file plan must admit the actual fixture file.
    # This is NOT a new per-value admission cap; SQLITE_LIMIT_LENGTH is untouched.
    source_cap = max(CAP, ((len(before)+4095)//4096 + 1)*4096)
    _configure_read_connection(con, SQLiteWriterPlan(source_cap))
    con.execute("BEGIN")
    try:
        if rejects_raw_inventory:
            # The full raw owner already stops on these intentionally invalid
            # physical A1 types. Independently exercise the History/consumer
            # public boundary using its real receipt/source owner; no validator
            # result is replaced or presented as successful raw admission.
            with pytest.raises(StorageIntegrityError):
                inventory_raw(con)
            raw = None
        else:
            raw = inventory_raw(con)
        receipts = VerifiedReceiptMapping(con)
        receipts.validate_all()
        with build_history(receipts, directory=work, owned_directory=history_dir,
                cutoff=NOW, tour=tour, input_identity=hashlib.sha256(before).hexdigest(),
                main_cap_bytes=CAP) as history:
            yield dict(db=db, source=con, history=history, work=work, key=key, packet=packet,
                original_row=original_row, sidecar=sidecar, row=rows[0], before=before,
                native=competition(id="202" if tour == "WTA" else "201"), tour=tour)
        if rejects_raw_inventory:
            with pytest.raises(StorageIntegrityError):
                inventory_raw(con)
        else:
            assert inventory_raw(con) == raw
    finally:
        con.close()
    assert db.read_bytes() == before


def prepare(case, *, directory="feature-000", **overrides):
    from context_storage_v2 import tennis_consumer as owner
    private = case["work"] / directory
    private.mkdir()
    arguments = dict(native_competition=case["native"], tournament_id="189-2026",
        grouping_slug="mens-singles" if case["tour"] == "ATP" else "womens-singles",
        observed_at=NOW-timedelta(seconds=10), surface="Hard", best_of=3, indoor=None,
        cutoff=NOW, work_directory=case["work"], owned_directory=private, main_cap_bytes=CAP)
    arguments.update(overrides)
    return owner.prepare_tennis_consumer(case["history"], **arguments)


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_actual_same_call_original_and_entire_snapshot_match_legacy_bytes(tmp_path, monkeypatch, tour):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch, tour=tour) as case:
        with prepare(case) as prepared:
            with open_fresh_writer(tmp_path / "new-consumers.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
                published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
                assert writer.connection.in_transaction
                assert published.snapshot.key == case["key"]
                assert published.reference == case["sidecar"]["reference"]
                assert published.original_hash == case["sidecar"]["original_artifact_hash"]
                actual = b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot))
                assert actual == canonical_bytes(case["packet"])
                assert _load_artifact(writer.connection, published.original_hash) == {
                    "kind": case["original_row"][0], "payload": json.loads(case["original_row"][1])}
                assert prepared.prediction.p_a_cal == case["row"]["p_cal"]
                assert prepared.origin == case["packet"]["base"]["reference_weights"]
                assert prepared.origin["native_state_identity"] == "unresolved"
                assert prepared.origin["values"]["p_a_cal"] != prepared.prediction.p_a_cal
                assert b"".join(prepared.features.iter_canonical_chunks()) == canonical_bytes(case["packet"]["features"])
                writer.commit_build()


@pytest.mark.parametrize("catalog,reason", [
    ((1, False), "no-owning-approval"), ((2, False), "effect-ambiguous"), ((1, True), "effect-unavailable")])
def test_real_catalog_selection_and_unresolved_result_match_old_owner(tmp_path, monkeypatch, catalog, reason):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch, catalog=catalog) as case, prepare(case) as prepared:
        assert prepared.selection_reason == reason
        with open_fresh_writer(tmp_path / "new-consumers.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot)) == canonical_bytes(case["packet"])
            assert published.snapshot.key == case["key"]
            assert case["packet"]["result"]["role"] == "not_applied"
            assert case["packet"]["approval"] is None


def test_predict_is_called_once_and_detached_views_cannot_change_actual_publication(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner
    from tennis import predict

    with actual_case(tmp_path, monkeypatch) as case:
        original = predict.predict_match
        calls = []
        def observed(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)
        monkeypatch.setattr(predict, "predict_match", observed)
        with prepare(case) as prepared:
            assert len(calls) == 1
            assert calls[0][1]["as_of"] == NOW
            assert calls[0][1]["workload_history"] == ()
            assert calls[0][0][0].artifact_hash == case["packet"]["base"]["model_hash"]
            prepared.origin["values"]["p_a_cal"] = 0.01
            prepared.prediction.p_a_cal = 0.01
            with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
                published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
                assert b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot)) == canonical_bytes(case["packet"])
                assert len(calls) == 1
            with pytest.raises(ContextIntegrityError):
                calls[0][1]["original_capture"]({})


@pytest.mark.parametrize("fault", ["missing", "double", "state-changed"])
def test_real_prediction_cannot_publish_without_one_unchanged_same_call_capture(tmp_path, monkeypatch, fault):
    from context_storage_v2 import tennis_consumer as owner
    from tennis import predict

    with actual_case(tmp_path, monkeypatch) as case:
        original = predict.predict_match
        def interrupted(state, *args, **kwargs):
            callback = kwargs["original_capture"]
            if fault == "missing":
                kwargs["original_capture"] = None
            elif fault == "double":
                def twice(value):
                    callback(value)
                    callback(value)
                kwargs["original_capture"] = twice
            result = original(state, *args, **kwargs)
            if fault == "state-changed":
                state.built_at += 1
            return result
        monkeypatch.setattr(predict, "predict_match", interrupted)
        with pytest.raises(ContextIntegrityError):
            prepare(case)
        assert list(case["work"].glob("feature-000/*")) == []


@pytest.mark.parametrize("change", ["receipt-clock", "native-participant", "cutoff", "tour-group"])
def test_prepare_rejects_unstored_or_different_native_and_history_scope(tmp_path, monkeypatch, change):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case:
        overrides = {}
        if change == "receipt-clock":
            overrides["observed_at"] = NOW-timedelta(seconds=9)
        elif change == "native-participant":
            native = deepcopy(case["native"])
            native["competitors"][0]["id"] = "999"
            overrides["native_competition"] = native
        elif change == "cutoff":
            overrides["cutoff"] = NOW-timedelta(seconds=1)
        else:
            overrides["grouping_slug"] = "womens-singles"
        with pytest.raises((ContextIntegrityError, StorageIntegrityError)):
            prepare(case, **overrides)


@pytest.mark.parametrize("release", ["prepared", "features"])
def test_released_preparation_cannot_be_published_or_resurrected(tmp_path, monkeypatch, release):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case:
        with prepare(case) as prepared:
            (prepared if release == "prepared" else prepared.features).close()
            with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
                with pytest.raises(StorageIntegrityError):
                    owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
                assert writer.connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == []
            with pytest.raises(StorageIntegrityError):
                prepared.__enter__()
        case["history"].assert_intact()


def test_output_requires_the_callers_existing_tracked_transaction(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        with sqlite3.connect(tmp_path / "ordinary.sqlite") as ordinary:
            ordinary.execute("BEGIN")
            with pytest.raises(StorageIntegrityError):
                owner.put_tennis_consumer(ordinary, prepared, created_at=NOW+timedelta(seconds=1))
            assert ordinary.in_transaction
            assert ordinary.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == []


def test_caller_rollback_removes_original_and_parts_together_without_closing_inputs(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            connection = writer.connection
            owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert connection.in_transaction
            connection.rollback()
            assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == []
        case["history"].assert_intact()
        prepared.features.assert_intact()


def _additional_receipts(db):
    from context_observations import append_observation
    from context_sources.tennis_status import normalize_tennis_status
    for index in range(12):
        observed = NOW-timedelta(minutes=2, seconds=index)
        native = competition(id=str(300+index))
        native["competitors"][0]["id"] = str(1000+2*index)
        native["competitors"][1]["id"] = str(1001+2*index)
        row = normalize_tennis_status("ATP", "189-2026", native,
            grouping_slug="mens-singles", observed_at=observed)[0]
        append_observation(db, row, observed_at=observed)


@pytest.mark.parametrize("fault", ["missing", "additional", "same-count-swapped", "duplicate"])
def test_complete_membership_rejects_actual_wrong_refset_even_with_valid_new_hashes(tmp_path, monkeypatch, fault):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch, on_configured=_additional_receipts) as case, prepare(case) as prepared:
        assert len(case["packet"]["observation_refs"]) == 13
        assert {ref for group in case["packet"]["features"]["refs"].values() for ref in group} == set()
        actual_put = owner.refs.put_refset
        def altered(connection, stream, **kwargs):
            # A small test-only fault at the real transport boundary. The C2
            # owner still writes/validates its actual complete new descriptor.
            values = list(stream)
            if fault == "missing":
                values.pop(0)
            elif fault == "additional":
                values.append("f"*64)
            elif fault == "same-count-swapped":
                values[0] = "f"*64
            else:
                values.append(values[0])
            return actual_put(connection, iter(values), **kwargs)
        monkeypatch.setattr(owner.refs, "put_refset", altered)
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            connection = writer.connection
            connection.execute("CREATE TABLE caller_marker(value TEXT)")
            connection.execute("INSERT INTO caller_marker VALUES('untouched')")
            with pytest.raises(StorageIntegrityError):
                owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert connection.in_transaction
            assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == [("caller_marker",)]
            assert connection.execute("SELECT value FROM caller_marker").fetchall() == [("untouched",)]


def test_entire_history_not_only_feature_refs_survives_ordered_key_and_payload_serialization(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch, on_configured=_additional_receipts) as case, prepare(case) as prepared:
        actual_put = owner.refs.put_refset
        def reverse(connection, stream, **kwargs):
            return actual_put(connection, iter(reversed(list(stream))), **kwargs)
        monkeypatch.setattr(owner.refs, "put_refset", reverse)
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert published.snapshot.observation_refs.reference_count == 13
            assert published.snapshot.key == case["key"]
            assert published.reference == case["sidecar"]["reference"]
            payload = b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot, chunk_bytes=7))
            assert payload == canonical_bytes(case["packet"])
            assert hashlib.sha256(payload).hexdigest() == published.snapshot.raw_payload_sha256
            assert len(payload) == published.snapshot.payload_bytes


def test_old_admitted_active_state_blob_above_default_block_remains_admitted(tmp_path, monkeypatch, record_property):
    from context_storage_v2 import tennis_consumer as owner
    from model_artifacts import load_artifact, load_manifest, publish_slots, put_artifact

    def enlarge_state(db):
        manifest, slots = load_manifest(db)
        actual = load_artifact(db, slots["tennis:ATP"])
        # One non-participating old-codec-valid key enlarges the actual state
        # BLOB, not the native fixture, prediction participants or C2 header.
        actual["payload"]["state"]["elo"]["overall"]["z"*(DEFAULT_LIMITS.block_bytes+1)] = [1500.0, 1]
        reference = put_artifact(db, kind="tennis-tour-state", payload=actual["payload"],
            created_at=NOW-timedelta(hours=1))
        publish_slots(db, {"tennis:ATP": reference}, expected_manifest=manifest,
            published_at=NOW-timedelta(minutes=40))
    with actual_case(tmp_path, monkeypatch, on_configured=enlarge_state) as case:
        source = case["source"]
        before_limit = source.getlimit(sqlite3.SQLITE_LIMIT_LENGTH)
        actual_size, actual_type = source.execute(
            "SELECT octet_length(payload),typeof(payload) FROM artifacts WHERE digest=?",
            (case["packet"]["base"]["model_hash"],)).fetchone()
        assert actual_size > 16*1024**2 and actual_type == "blob"
        record_property("actual_old_state_blob_bytes", actual_size)
        record_property("actual_source_sqlite_limit_length", before_limit)
        with prepare(case) as prepared:
            assert prepared.physical_metadata["artifacts"]["largest_value_octets"] == actual_size
            assert prepared.origin["inputs"]["player_a"] == "Alpha A"
            assert prepared.origin["inputs"]["player_b"] == "Beta B"
            with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
                published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
                assert published.original_hash == case["sidecar"]["original_artifact_hash"]
                assert b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot)) == canonical_bytes(case["packet"])
                assert published.snapshot.header_bytes < snapshots.MAX_HEADER_BYTES
        assert source.getlimit(sqlite3.SQLITE_LIMIT_LENGTH) == before_limit


@pytest.mark.parametrize("corruption", ["payload-text", "kind-blob", "creation-blob"])
def test_original_physical_type_observation_does_not_bypass_actual_state_loader(tmp_path, monkeypatch, corruption):
    from context_storage_v2 import tennis_consumer as owner

    def corrupt(db):
        with sqlite3.connect(db) as connection:
            statement = {
                "payload-text": "UPDATE artifacts SET payload=CAST(payload AS TEXT) WHERE kind='tennis-tour-state'",
                "kind-blob": "UPDATE artifacts SET kind=CAST(kind AS BLOB) WHERE kind='tennis-tour-state'",
                "creation-blob": "UPDATE artifacts SET created_at=CAST(created_at AS BLOB) WHERE kind='tennis-tour-state'",
            }[corruption]
            connection.execute(statement)
    with actual_case(tmp_path, monkeypatch, on_stored=corrupt, rejects_raw_inventory=True) as case:
        with pytest.raises(ArtifactIntegrityError):
            _load_artifact(case["source"], case["packet"]["base"]["model_hash"])
        real_metadata = owner._physical_metadata
        observed = []
        def record(history):
            value = real_metadata(history)
            observed.append(value)
            return value
        monkeypatch.setattr(owner, "_physical_metadata", record)
        with pytest.raises(ArtifactIntegrityError):
            prepare(case)
        assert len(observed) == 1 and observed[0]["artifacts"]["rows"] == 2


def test_actual_corrupt_claimed_approval_is_not_silently_effect_absent(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner
    from model_artifacts import load_manifest, publish_slots, put_artifact
    from tennis.live_context import _Inventory

    def corrupt_claim(db):
        manifest, slots = load_manifest(db)
        effect = slots["experimental-live-test:0"]
        claim = put_artifact(db, kind="context-approval-v1", payload={"passed": True},
            created_at=NOW-timedelta(hours=1))
        publish_slots(db, {"context-approval:"+effect: claim}, expected_manifest=manifest,
            published_at=NOW-timedelta(seconds=30))
    with actual_case(tmp_path, monkeypatch, catalog=(1, False), on_stored=corrupt_claim) as case:
        with pytest.raises(ContextIntegrityError):
            _Inventory(case["source"])
        with pytest.raises(ContextIntegrityError):
            prepare(case)
        assert list(case["work"].glob("feature-000/*")) == []


@pytest.mark.parametrize("fault", ["history-close", "source-epoch", "feature-close", "late-generator-error"])
def test_lifetime_or_late_iterator_failure_rolls_back_all_output_inside_savepoint(tmp_path, monkeypatch, fault):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        if fault == "late-generator-error":
            actual_keys = owner._ordered_history_keys
            def late(value):
                yield from actual_keys(value)
                raise RuntimeError("test late completed iterator failure")
            monkeypatch.setattr(owner, "_ordered_history_keys", late)
            expected = RuntimeError
        else:
            actual_put = owner.snapshots.put_snapshot_parts
            def interrupted(*args, **kwargs):
                result = actual_put(*args, **kwargs)
                if fault == "history-close":
                    case["history"].close()
                elif fault == "source-epoch":
                    case["source"].rollback()
                    case["source"].execute("BEGIN")
                else:
                    prepared.features.close()
                return result
            monkeypatch.setattr(owner.snapshots, "put_snapshot_parts", interrupted)
            expected = (StorageIntegrityError, RuntimeArtifactTrustError)
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            connection = writer.connection
            connection.execute("CREATE TABLE caller_marker(value TEXT)")
            connection.execute("INSERT INTO caller_marker VALUES('prior')")
            with pytest.raises(expected):
                owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert connection.in_transaction
            assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == [("caller_marker",)]
            assert connection.execute("SELECT value FROM caller_marker").fetchall() == [("prior",)]
            with pytest.raises(StorageIntegrityError):
                owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))


@pytest.mark.parametrize("failure", ["full", "toobig"])
def test_actual_sqlite_allocation_failure_does_not_return_partial_original_or_parts(tmp_path, monkeypatch, failure):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        cap = 32768 if failure == "full" else CAP
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(cap)) as writer:
            connection = writer.connection
            if failure == "toobig":
                # Only this NEW private output, never the actual source owner.
                connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 512)
            with pytest.raises(StorageLimitError) as caught:
                owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))
            error = caught.value
            while error.__cause__ is not None:
                error = error.__cause__
            assert getattr(error, "sqlite_errorcode", None) == (sqlite3.SQLITE_FULL if failure == "full" else sqlite3.SQLITE_TOOBIG)
            assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == []
        assert (tmp_path / "output.sqlite").exists()
        case["history"].assert_intact()


def test_existing_original_identity_collision_preserves_callers_rows_and_removes_new_parts(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            connection = writer.connection
            connection.execute("CREATE TABLE artifacts(digest TEXT PRIMARY KEY,kind TEXT NOT NULL,payload BLOB NOT NULL,created_at TEXT NOT NULL)")
            broken = (case["sidecar"]["original_artifact_hash"], case["original_row"][0], b'{}', case["original_row"][2])
            connection.execute("INSERT INTO artifacts VALUES(?,?,?,?)", broken)
            with pytest.raises(ArtifactIntegrityError):
                owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert connection.in_transaction
            assert connection.execute("SELECT * FROM artifacts").fetchall() == [broken]
            assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == [("artifacts",)]


def test_snapshot_key_collision_with_real_different_transport_preserves_existing_parts(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            connection = writer.connection
            owner.refs.create_schema(connection)
            snapshots.create_schema(connection)
            packet = deepcopy(case["packet"])
            packet["result"]["limitations"].append("test-real-different-transport")
            observations = owner.refs.put_refset(connection, iter(packet["observation_refs"]))
            header = {name: value for name, value in packet.items() if name != "observation_refs"}
            raw = canonical_bytes(packet)
            previous = snapshots.put_snapshot_parts(connection, key=case["key"], header_bytes=canonical_bytes(header),
                observation_refs=observations, expected_raw_payload_sha256=hashlib.sha256(raw).hexdigest(),
                expected_payload_bytes=len(raw), expected_payload_digest=digest({"key": case["key"], "payload": packet}),
                expected_observation_count=len(packet["observation_refs"]))
            with pytest.raises(StorageIntegrityError):
                owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert b"".join(snapshots.iter_snapshot_bytes(connection, previous)) == raw
            assert not connection.execute("SELECT 1 FROM sqlite_schema WHERE name='artifacts'").fetchall()


def test_same_call_capture_cannot_replace_the_actually_loaded_state_identity(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner
    from tennis import predict

    with actual_case(tmp_path, monkeypatch) as case:
        actual_predict = predict.predict_match
        def extra_field(*args, **kwargs):
            callback = kwargs["original_capture"]
            kwargs["original_capture"] = lambda value: callback({**value, "state_hash": "f"*64})
            return actual_predict(*args, **kwargs)
        monkeypatch.setattr(predict, "predict_match", extra_field)
        with pytest.raises(ContextIntegrityError):
            prepare(case)


def test_final_code_read_lifetime_failure_is_still_inside_the_output_savepoint(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        actual_hashes = owner._code_hashes
        calls = 0
        def final_read_releases_feature():
            nonlocal calls
            value = actual_hashes()
            calls += 1
            if calls == 2:
                prepared.features.close()
            return value
        monkeypatch.setattr(owner, "_code_hashes", final_read_releases_feature)
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            connection = writer.connection
            connection.execute("CREATE TABLE caller_marker(value TEXT)")
            with pytest.raises(StorageIntegrityError):
                owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert connection.in_transaction
            assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == [("caller_marker",)]


def test_final_footprint_disk_usage_lifetime_failure_rolls_back_before_publication(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        feature = prepared.features
        actual_hashes = owner._code_hashes
        actual_usage = owner.refs.shutil.disk_usage
        code_reads = 0
        interruptions = []
        def actual_final_code_read():
            nonlocal code_reads
            value = actual_hashes()
            code_reads += 1
            return value
        def actual_usage_then_close_feature(path):
            measured = actual_usage(path)
            if code_reads == 2 and not interruptions:
                # The final body guard has already completed. This is real
                # post-yield footprint I/O, with the complete writes present.
                assert connection.execute("SELECT count(*) FROM v2_snapshot_headers").fetchone() == (1,)
                assert connection.execute("SELECT count(*) FROM artifacts").fetchone() == (1,)
                feature.close()
                interruptions.append(path)
            return measured
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            connection = writer.connection
            connection.execute("CREATE TABLE caller_marker(value TEXT)")
            connection.execute("INSERT INTO caller_marker VALUES('keep')")
            monkeypatch.setattr(owner, "_code_hashes", actual_final_code_read)
            monkeypatch.setattr(owner.refs.shutil, "disk_usage", actual_usage_then_close_feature)
            with pytest.raises(StorageIntegrityError):
                owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert len(interruptions) == 1
            assert connection.in_transaction
            assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == [("caller_marker",)]
            assert connection.execute("SELECT * FROM caller_marker").fetchall() == [("keep",)]
            with pytest.raises(StorageIntegrityError):
                prepared.__enter__()


def _paired_receipts(db):
    from test_context_tennis_capture import persist, records
    clock = NOW-timedelta(hours=1)
    persist(db, records(clock=clock), clock=clock)


@pytest.mark.parametrize("history_kind", ["paired-unknown-end", "legacy-known-end"])
def test_real_nonempty_performed_features_and_their_complete_refs_match_old_snapshot(tmp_path, monkeypatch, history_kind):
    from context_storage_v2 import tennis_consumer as owner

    def ended_receipts(db):
        from context_sources.tennis import normalize_tennis_workload
        from test_context_tennis_capture import persist
        from test_tennis_context_features import native_row
        clock = NOW-timedelta(hours=1)
        rows = normalize_tennis_workload((native_row("101", opponent="2"),), observed_at=clock)
        persist(db, rows, clock=clock)
    seed = _paired_receipts if history_kind == "paired-unknown-end" else ended_receipts
    with actual_case(tmp_path, monkeypatch, on_configured=seed) as case, prepare(case) as prepared:
        original_features = case["packet"]["features"]
        if history_kind == "paired-unknown-end":
            # Native receipt time is not an actual match end; old window sums
            # correctly remain missing while the receipt lower bound is six h.
            assert original_features["values"]["observed_sets_1d_a"] is None
            assert original_features["values"]["observed_sets_1d_b"] is None
            assert original_features["values"]["observed_recovery_minimum_hours_a"] == 6.0
            assert len(case["packet"]["observation_refs"]) == 4
        else:
            assert original_features["values"]["observed_sets_1d_a"] == 3
            assert original_features["values"]["observed_sets_1d_b"] == 3
            assert original_features["values"]["observed_recovery_exact_hours_a"] == 23.0
            assert len(case["packet"]["observation_refs"]) == 3
        assert any(original_features["refs"].values())
        assert b"".join(prepared.features.iter_canonical_chunks()) == canonical_bytes(original_features)
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert published.snapshot.key == case["key"]
            assert published.reference == case["sidecar"]["reference"]
            assert b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot)) == canonical_bytes(case["packet"])


@pytest.mark.parametrize("revision", ["newer", "same-time-conflict", "future"])
def test_latest_complete_native_revision_not_first_matching_receipt_controls_preparation(tmp_path, monkeypatch, revision):
    from context_storage_v2 import tennis_consumer as owner
    from context_observations import append_observation
    from context_sources.tennis_status import normalize_tennis_status, tennis_observations_as_of

    original_histories = []
    def append_revision(db):
        clock = NOW + timedelta(seconds=1) if revision == "future" else NOW-timedelta(seconds=9 if revision == "newer" else 10)
        native = competition()
        native["competitors"][0]["id"] = "999"
        for row in normalize_tennis_status("ATP", "189-2026", native, grouping_slug="mens-singles", observed_at=clock):
            append_observation(db, row, observed_at=clock)
        # This old path reader opens a schema-owning connection. Use it BEFORE
        # the held C Source, never concurrently with that real read lifetime.
        original_histories.append(tennis_observations_as_of(db, cutoff=NOW, tour="ATP"))
    with actual_case(tmp_path, monkeypatch, on_stored=append_revision) as case:
        assert len(original_histories[0]) == (1 if revision == "future" else 2)
        if revision != "future":
            with pytest.raises(ContextIntegrityError):
                prepare(case)
        else:
            with prepare(case) as prepared, open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
                published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
                assert published.snapshot.key == case["key"]
                assert b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot)) == canonical_bytes(case["packet"])


@pytest.mark.parametrize("source_encoding", ["UTF-16le", "UTF-16be"])
def test_actual_utf16_source_and_inactive_opaque_nul_bytes_do_not_change_owner_admission(tmp_path, monkeypatch, source_encoding):
    from context_storage_v2 import tennis_consumer as owner

    def opaque_row(db):
        with sqlite3.connect(db) as connection:
            connection.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (
                "a"*64, "opaque\x00unselected", b"\xff\x00not-json", NOW.isoformat()))
    with actual_case(tmp_path, monkeypatch, on_configured=opaque_row, source_encoding=source_encoding) as case, prepare(case) as prepared:
        assert case["source"].execute("PRAGMA encoding").fetchone()[0].casefold() == source_encoding.casefold()
        assert prepared.physical_metadata["artifacts"]["rows"] == 3
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert published.original_hash == case["sidecar"]["original_artifact_hash"]
            assert b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot)) == canonical_bytes(case["packet"])
        assert case["source"].execute("SELECT kind,payload FROM artifacts WHERE digest=?", ("a"*64,)).fetchone() == ("opaque\x00unselected", b"\xff\x00not-json")


def test_consumer_does_not_enter_provider_daily_shadow_or_any_legacy_path_writer(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner
    from context_sources import tennis_status
    import context_snapshots
    import model_artifacts
    from scripts import tennis_daily
    from tennis import live_context, shadow, tour_state

    with actual_case(tmp_path, monkeypatch) as case:
        def outside(*args, **kwargs):
            pytest.fail("consumer entered an out-of-scope fetch, tuple history or legacy path writer")
        for module, names in (
            (tennis_daily, ("fetch_fixtures_espn", "scan_fixtures")),
            (shadow, ("store_prediction",)), (tennis_daily.requests, ("get",)),
            (tour_state, ("load_tour_state",)), (model_artifacts, ("load_artifact", "load_manifest", "put_artifact", "_connect")),
            (context_snapshots, ("compute_once", "_connect")),
            (tennis_status, ("tennis_observations_as_of",)),
            (live_context, ("tennis_observations_as_of", "tennis_features_v3", "calculate_context_payload", "_reader")),
        ):
            for name in names:
                monkeypatch.setattr(module, name, outside)
        with prepare(case) as prepared, open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert b"".join(snapshots.iter_snapshot_bytes(writer.connection, published.snapshot)) == canonical_bytes(case["packet"])


def test_preparation_cannot_be_reconstructed_from_public_data_or_published_twice(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        with pytest.raises(StorageIntegrityError):
            owner.PreparedTennisConsumer(origin=prepared.origin, features=prepared.features,
                history=case["history"], metadata=prepared.physical_metadata)
        with open_fresh_writer(tmp_path / "first.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            with pytest.raises(StorageIntegrityError):
                owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
        with open_fresh_writer(tmp_path / "second.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            with pytest.raises(StorageIntegrityError):
                owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert writer.connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == []


@pytest.mark.parametrize("existing_age", [-1, 1])
def test_actual_existing_original_creation_time_is_validated_not_overwritten(tmp_path, monkeypatch, existing_age):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch) as case, prepare(case) as prepared:
        with open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            connection = writer.connection
            connection.execute("CREATE TABLE artifacts(digest TEXT PRIMARY KEY,kind TEXT NOT NULL,payload BLOB NOT NULL,created_at TEXT NOT NULL)")
            row = (case["sidecar"]["original_artifact_hash"], case["original_row"][0],
                   case["original_row"][1], (NOW+timedelta(seconds=existing_age)).isoformat())
            connection.execute("INSERT INTO artifacts VALUES(?,?,?,?)", row)
            if existing_age < 0:
                with pytest.raises(ContextIntegrityError):
                    owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=2))
                assert connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == [("artifacts",)]
            else:
                published = owner.put_tennis_consumer(connection, prepared, created_at=NOW+timedelta(seconds=2))
                assert published.original_hash == row[0]
            assert connection.execute("SELECT * FROM artifacts").fetchall() == [row]


def test_actual_feature_reference_subset_is_checked_against_all_owned_history(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner

    with actual_case(tmp_path, monkeypatch, on_configured=_paired_receipts) as case:
        actual_header = owner._header
        def additional_feature_ref(*args, **kwargs):
            value, reason = actual_header(*args, **kwargs)
            name = "observed_recovery_minimum_hours_a"
            value["features"]["refs"][name] = sorted([*value["features"]["refs"][name], "f"*64])
            value["result"]["feature_refs"][name] = list(value["features"]["refs"][name])
            return value, reason
        monkeypatch.setattr(owner, "_header", additional_feature_ref)
        with prepare(case) as prepared, open_fresh_writer(tmp_path / "output.sqlite", plan=SQLiteWriterPlan(CAP)) as writer:
            with pytest.raises(ContextIntegrityError):
                owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            assert writer.connection.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == []


def test_header_serializer_uses_exact_utf8_bytes_and_the_one_mib_c2_boundary():
    from context_storage_v2 import tennis_consumer as owner

    # Exact one-MiB serialized JSON: 12 punctuation/key bytes + 1,048,564 ASCII.
    value = {"value": "x"*(1024**2-12)}
    expected = canonical_bytes(value)
    assert len(expected) == 1024**2
    assert owner._bounded_canonical(value, owner.snapshots.MAX_HEADER_BYTES) == expected
    with pytest.raises(StorageLimitError):
        owner._bounded_canonical({"value": value["value"]+"x"}, owner.snapshots.MAX_HEADER_BYTES)
    unicode_value = {"value": "\u0000\u20ac\U0001f3be"}
    assert owner._bounded_canonical(unicode_value, 100) == b'{"value":"\\u0000\xe2\x82\xac\xf0\x9f\x8e\xbe"}'


def test_original_and_full_parts_reopen_after_caller_cleanup_and_one_explicit_commit(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner
    from context_snapshots import _decode_snapshot
    from context_transport import context_consumer_reference

    with actual_case(tmp_path, monkeypatch, on_configured=_paired_receipts) as case, prepare(case) as prepared:
        path = tmp_path / "output.sqlite"
        with open_fresh_writer(path, plan=SQLiteWriterPlan(CAP)) as writer:
            published = owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
            prepared.close()  # Caller-required owned cleanup precedes acceptance.
            writer.commit_build()
        reader = sqlite3.connect(path.absolute().as_uri()+"?mode=ro", uri=True, factory=TrackedConnection)
        try:
            _configure_read_connection(reader, SQLiteWriterPlan(CAP))
            reader.execute("BEGIN")
            raw = b"".join(snapshots.iter_snapshot_bytes(reader, published.snapshot))
            decoded = _decode_snapshot(published.snapshot.key, raw, published.snapshot.payload_digest)
            assert raw == canonical_bytes(case["packet"])
            assert context_consumer_reference(published.snapshot.key, decoded) == case["sidecar"]["reference"]
            assert _load_artifact(reader, published.original_hash) == {
                "kind": case["original_row"][0], "payload": json.loads(case["original_row"][1])}
        finally:
            reader.close()


def test_late_owned_feature_cleanup_error_stops_caller_commit_and_retains_failed_files(tmp_path, monkeypatch):
    from context_storage_v2 import tennis_consumer as owner
    from context_storage_v2.tennis import StreamingTennisFeatures

    with actual_case(tmp_path, monkeypatch) as case:
        prepared = prepare(case)
        feature_path = prepared.features.path
        real_close = StreamingTennisFeatures.close
        def late_close(feature):
            real_close(feature)
            raise RuntimeError("test actual handle closed but late cleanup failed")
        monkeypatch.setattr(StreamingTennisFeatures, "close", late_close)
        path = tmp_path / "output.sqlite"
        with pytest.raises(RuntimeError):
            with prepared, open_fresh_writer(path, plan=SQLiteWriterPlan(CAP)) as writer:
                owner.put_tennis_consumer(writer.connection, prepared, created_at=NOW+timedelta(seconds=1))
                prepared.close()
                writer.commit_build()
        with sqlite3.connect(path) as reader:
            assert reader.execute("SELECT name FROM sqlite_schema WHERE type='table'").fetchall() == []
        assert path.exists() and feature_path.exists()
        with pytest.raises(StorageIntegrityError):
            prepared.__enter__()


@pytest.mark.parametrize("table,offset", [("artifacts", 1000), ("manifests", -1000)])
def test_physical_metadata_binds_actual_rowids_without_changing_old_payloads(tmp_path, monkeypatch, table, offset):
    # These are the real unchanged ordinary tables. Moving only their rowids
    # preserves every column's type/length/value and the actual old prediction.
    # Positive and negative rowids must not collapse into scan ordinals.
    observations = []
    for moved in (False, True):
        directory = tmp_path / ("moved" if moved else "original")
        directory.mkdir()
        def move_rowids(db):
            if moved:
                with sqlite3.connect(db) as connection:
                    connection.execute(f"UPDATE {table} SET rowid=rowid+?", (offset,))
        with monkeypatch.context() as local_patch:
            with actual_case(directory, local_patch, on_stored=move_rowids) as case, prepare(case) as prepared:
                rowids = case["source"].execute(f"SELECT rowid FROM {table} ORDER BY rowid").fetchall()
                observations.append((prepared.physical_metadata, rowids,
                    hashlib.sha256(case["before"]).hexdigest(),
                    canonical_bytes(prepared.origin), canonical_bytes(case["packet"])))
    before, after = observations
    assert before[1] and after[1] == [(rowid+offset,) for (rowid,) in before[1]]
    assert before[2] != after[2]  # Actual complete Source bytes remain the binding.
    assert before[3:] == after[3:]  # Real Original and full legacy snapshot unchanged.
    for name in before[0]:
        left, right = before[0][name], after[0][name]
        assert {key: value for key, value in left.items() if key != "metadata_sha256"} == {
            key: value for key, value in right.items() if key != "metadata_sha256"}
        if name == table:
            assert left["metadata_sha256"] != right["metadata_sha256"]
        else:
            assert left == right
