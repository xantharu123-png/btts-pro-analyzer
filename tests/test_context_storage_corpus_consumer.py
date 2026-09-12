"""Small real Corpus -> Source/D2 -> History -> Tennis consumer acceptance.

The independently built legacy database is the complete small oracle.  This is
not a native-capacity, global-C, B, restore, or release certificate.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import pytest

import context_runtime
from context_observations import append_observation
from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
from context_runtime_transaction import TrackedConnection
from context_sources.tennis_status import normalize_tennis_status
from context_storage_v2 import refs, snapshots, snapshot_source
from context_storage_v2.history import _configure_read_connection, build_history
from context_storage_v2.inventory import inventory_raw
from context_storage_v2.receipt_corpus import build_receipt_corpus
from context_storage_v2.sqlite_profile import SQLiteWriterPlan, open_fresh_writer
from context_storage_v2.workspace_budget import ExternalInput, FileSlot, WorkspaceBudget
from model_artifacts import _load_artifact, canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_tennis_live_worker import NOW, competition, configure, context_rows, response, run_batch


MAIN_CAP = 4 * 1024**2
LEDGER_CAP = 1024**2
DIRECTORY_METADATA = 1024**2


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _table_rows(connection):
    return {
        name: tuple(connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid'))
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
        )
    }


@contextmanager
def _profiled_source(path, *, cap=MAIN_CAP):
    connection = sqlite3.connect(
        Path(path).absolute().as_uri() + "?mode=ro",
        uri=True,
        timeout=0,
        factory=TrackedConnection,
    )
    _configure_read_connection(connection, SQLiteWriterPlan(cap))
    connection.execute("BEGIN")
    # Establish the snapshot without assuming a particular owned schema; this
    # helper also opens the independent parts/consumer stores.
    connection.execute("SELECT count(*) FROM main.sqlite_schema").fetchone()
    try:
        yield connection
    finally:
        connection.close()


def _native(tour, number):
    suffix = str(number)
    return competition(
        id=suffix,
        competitors=[
            {"id": "1", "athlete": {"displayName": "Alpha A"}},
            {"id": "2", "athlete": {"displayName": "Beta B"}},
        ],
    )


def _ordinary(tour, number):
    suffix = str(number)
    return competition(
        id=suffix,
        competitors=[
            {"id": suffix + "1", "athlete": {"displayName": "Other " + suffix + " A"}},
            {"id": suffix + "2", "athlete": {"displayName": "Other " + suffix + " B"}},
        ],
    )


def _normalized(tour, native, clock):
    return normalize_tennis_status(
        tour,
        "189-2026",
        native,
        grouping_slug="mens-singles" if tour == "ATP" else "womens-singles",
        observed_at=clock,
    )[0]


def _make_baseline(setup_root, monkeypatch):
    database, predictions, _states, _calls = configure(
        monkeypatch, setup_root, tours=("ATP", "WTA")
    )
    result, rows = run_batch(database, predictions)
    assert result["stored"] == 2 and not result["errors"] and len(rows) == 2
    packets = dict(context_rows(database))
    with sqlite3.connect(database) as connection:
        counts = {
            name: connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            for name in ("artifacts", "context_observations", "context_snapshots")
        }
        states = {
            json.loads(payload)["state"]["tour"]
            for kind, payload in connection.execute(
                "SELECT kind,payload FROM artifacts WHERE kind='tennis-tour-state'"
            )
        }
    assert counts["context_observations"] == 2
    assert counts["context_snapshots"] == 2
    assert counts["artifacts"] == 4
    assert states == {"ATP", "WTA"}
    assert len(packets) == 2
    baseline = database.read_bytes()
    oracle = setup_root / "legacy-oracle.sqlite"
    oracle.write_bytes(baseline)
    assert oracle.read_bytes() == baseline
    return database, oracle, baseline, packets


def _phase_values(tour):
    offset = 0 if tour == "ATP" else 100
    first_clock = NOW + timedelta(minutes=1)
    second_clock = NOW + timedelta(minutes=2)
    received = NOW + timedelta(minutes=3)
    cutoff = NOW + timedelta(minutes=4)
    created = cutoff + timedelta(seconds=1)
    first = _ordinary(tour, 710 + offset)
    second = _ordinary(tour, 720 + offset)
    native = _native(tour, 910 + offset)
    observations = (
        (_normalized(tour, first, first_clock), first_clock),
        (_normalized(tour, second, second_clock), second_clock),
        (_normalized(tour, native, received), received),
    )
    return {
        "tour": tour,
        "first_clock": first_clock,
        "second_clock": second_clock,
        "received": received,
        "cutoff": cutoff,
        "created": created,
        "native": native,
        "observations": observations,
    }


def _run_oracle(setup_root, monkeypatch, oracle, values):
    """Return the real post-reception/pre-Original inventory and final output."""
    from context_sources import tennis_capture
    from context_sources.tennis_capture import capture_tennis_worker
    from scripts import tennis_daily as daily
    from tennis import live_context, shadow
    from tennis.live_context import live_worker
    from tennis.tour_state import load_tour_state

    ordinary_refs = [
        append_observation(oracle, row, observed_at=clock)
        for row, clock in values["observations"][:2]
    ]
    monkeypatch.setattr(
        daily,
        "load_tour_state",
        lambda *args, **kwargs: load_tour_state(
            *args, **{**kwargs, "path": oracle}
        ),
    )
    monkeypatch.setattr(tennis_capture, "_receipt_now", lambda: values["received"])
    monkeypatch.setattr(daily, "_refresh_now", lambda: values["received"])
    monkeypatch.setattr(live_context, "_now", lambda: values["created"])
    shadow_path = setup_root / "oracle-shadow.sqlite"
    monkeypatch.setattr(shadow, "DB_PATH", shadow_path)

    class Reply:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return deepcopy(self._payload)

    def get(url, **_kwargs):
        requested = "WTA" if "/wta/" in url else "ATP"
        payload = (
            response(values["native"], requested)
            if requested == values["tour"]
            else {"events": []}
        )
        return Reply(payload)

    monkeypatch.setattr(daily.requests, "get", get)
    with live_worker(path=oracle) as batch:
        with capture_tennis_worker(path=oracle) as capture:
            batch.attach_capture(capture)
            fixtures = daily.fetch_fixtures_espn("2026-09-09")
            result = daily.scan_fixtures(
                "2026-09-09",
                fixtures,
                decision_at=values["cutoff"],
                db_path=shadow_path,
                surfaces={},
                workload_history=(),
                append_observed_at=values["created"] + timedelta(seconds=1),
            )
            assert result["stored"] == 0
        report = capture.report()
        assert report["status"] == "captured" and len(report["receipt_refs"]) == 1
        with _profiled_source(oracle) as source:
            before_original = inventory_raw(source)
            before_rows = _table_rows(source)
        batch.finish()
        reasons = tuple(batch.reasons)
    assert result["stored"] == 1 and not result["errors"]
    shadow_rows = shadow.latest_predictions(
        shadow_path, as_of=values["created"] + timedelta(seconds=2)
    )
    assert len(shadow_rows) == 1
    sidecar = json.loads(shadow_rows[0]["context_json"])["context_model"]
    packets = dict(context_rows(oracle))
    packet = packets[sidecar["reference"]["key"]]
    with sqlite3.connect(oracle) as connection:
        original = connection.execute(
            "SELECT kind,payload,created_at FROM artifacts WHERE digest=?",
            (sidecar["original_artifact_hash"],),
        ).fetchone()
        receipt_count = connection.execute(
            "SELECT count(*) FROM context_observations"
        ).fetchone()[0]
    assert len(set(ordinary_refs) | set(report["receipt_refs"])) == 3
    assert len(reasons) == 1
    return {
        "pre_original_inventory": before_original,
        "pre_original_rows": before_rows,
        "receipt_refs": tuple(ordinary_refs) + tuple(report["receipt_refs"]),
        "receipt_count": receipt_count,
        "packet": packet,
        "sidecar": sidecar,
        "row": shadow_rows[0],
        "original": original,
        "selection_reason": reasons[0],
    }


def _setup_workspace(tmp_path):
    root = tmp_path / "legacy-setup"
    root.mkdir()
    slots = []
    for name in ("context.db", "shadow.db", "legacy-oracle.sqlite", "oracle-shadow.sqlite"):
        slots.extend((FileSlot(name, MAIN_CAP), FileSlot(name + "-journal", MAIN_CAP)))
    budget = WorkspaceBudget(
        root,
        slots,
        directory_metadata_bytes=DIRECTORY_METADATA,
    )
    return root, budget


def _workspace(tmp_path, source):
    root = tmp_path / "whole-job"
    root.mkdir()
    for name in ("corpus", "old-parts", "history", "feature", "new-consumers"):
        (root / name).mkdir()
    slots = [
        FileSlot("corpus/legacy-copy.sqlite", MAIN_CAP, True),
        FileSlot("corpus/legacy-copy.sqlite-journal", MAIN_CAP),
        FileSlot("corpus/receipt-additions.bin", LEDGER_CAP),
    ]
    for directory, main in (
        ("old-parts", "snapshot-parts.sqlite"),
        ("history", "history.sqlite"),
        ("feature", "features.sqlite"),
        ("new-consumers", "consumers.sqlite"),
    ):
        slots.extend(
            (FileSlot(f"{directory}/{main}", MAIN_CAP),
             FileSlot(f"{directory}/{main}-journal", MAIN_CAP))
        )
    budget = WorkspaceBudget(
        root,
        slots,
        external_inputs=(ExternalInput(Path(source).absolute()),),
        directory_metadata_bytes=DIRECTORY_METADATA,
    )
    return root, budget


def _artifact_semantics(source):
    artifacts = VerifiedArtifactMapping(source)
    created = {
        reference: datetime.fromisoformat(
            context_runtime._validate_stored_timestamp(
                created_at, label="artifact creation time"
            )
        )
        for reference, created_at in source.execute(
            "SELECT digest,created_at FROM artifacts"
        )
    }
    limitations = set()
    semantics = context_runtime._verify_artifact_types(
        source, artifacts, created, limitations
    )
    receipts = VerifiedReceiptMapping(
        source, protected_receipts=semantics["protected_receipts"]
    )
    receipts.validate_all()
    return artifacts, created, limitations, semantics, receipts


def _completed_corpus_phase(tmp_path, monkeypatch, tour="ATP"):
    """Complete only the retained private corpus phase for negative boundaries."""
    setup_root, setup_budget = _setup_workspace(tmp_path)
    source_path, _oracle_path, baseline, _packets = _make_baseline(
        setup_root, monkeypatch
    )
    setup_observation = setup_budget.check_quiescent()
    root, budget = _workspace(tmp_path, source_path)
    values = _phase_values(tour)
    baseline_hash = hashlib.sha256(baseline).hexdigest()
    with _profiled_source(source_path) as source:
        corpus = build_receipt_corpus(
            source,
            values["observations"],
            expected_source_sha256=baseline_hash,
            workspace=root,
            owned_directory=root / "corpus",
            main_cap_bytes=MAIN_CAP,
            ledger_cap_bytes=LEDGER_CAP,
        )
    corpus_observation = budget.check_quiescent()
    return {
        "setup_budget": setup_budget,
        "setup_observation": setup_observation,
        "root": root,
        "budget": budget,
        "corpus_observation": corpus_observation,
        "source": source_path,
        "source_sha256": baseline_hash,
        "corpus": corpus,
        "values": values,
    }


def run_small_corpus_consumer_acceptance(
    tmp_path, monkeypatch, tour, *, record_property=None
):
    """Callable positive ATP/WTA orchestration for the guarded native follow-on."""
    if tour not in {"ATP", "WTA"}:
        raise ValueError("small acceptance tour must be ATP or WTA")
    if record_property is None:
        record_property = lambda _name, _value: None
    setup_root, setup_budget = _setup_workspace(tmp_path)
    setup_initial = setup_budget.check_quiescent()
    source_path, oracle_path, baseline_bytes, baseline_packets = _make_baseline(
        setup_root, monkeypatch
    )
    values = _phase_values(tour)
    oracle = _run_oracle(setup_root, monkeypatch, oracle_path, values)
    setup_final = setup_budget.check_quiescent()
    root, budget = _workspace(tmp_path, source_path)
    initial_budget = budget.check_quiescent()
    baseline_hash = hashlib.sha256(baseline_bytes).hexdigest()

    with _profiled_source(source_path) as sealed_source:
        corpus = build_receipt_corpus(
            sealed_source,
            values["observations"],
            expected_source_sha256=baseline_hash,
            workspace=root,
            owned_directory=root / "corpus",
            main_cap_bytes=MAIN_CAP,
            ledger_cap_bytes=LEDGER_CAP,
        )
    after_corpus = budget.check_quiescent()
    assert corpus.source_sha256 == baseline_hash == _sha256(source_path)
    assert corpus.submitted_observations == corpus.new_receipts == 3
    assert corpus.new_contents == 3
    assert corpus.inventory == oracle["pre_original_inventory"]
    assert corpus.output_sha256 == _sha256(corpus.path)
    assert corpus.ledger_sha256 == _sha256(corpus.ledger_path)

    source = None
    history = None
    prepared = None
    output_writer = None
    try:
        source_context = _profiled_source(corpus.path)
        source = source_context.__enter__()
        actual_inventory = inventory_raw(source)
        assert actual_inventory == oracle["pre_original_inventory"]
        assert _table_rows(source) == oracle["pre_original_rows"]
        artifacts, created, limitations, semantics, receipt_mapping = _artifact_semantics(source)
        assert len(receipt_mapping) == oracle["receipt_count"]
        assert type(semantics["protected_receipts"]) is set
        assert semantics["protected_receipts"] <= set(receipt_mapping)
        assert semantics["verified"]
        assert set(artifacts) == set(created)

        parts_path = root / "old-parts" / "snapshot-parts.sqlite"
        with open_fresh_writer(parts_path, plan=SQLiteWriterPlan(MAIN_CAP)) as parts_writer:
            refs.create_schema(parts_writer.connection)
            snapshots.create_schema(parts_writer.connection)
            coverage = snapshot_source.adapt_source_snapshots(
                source, parts_writer.connection, actual_inventory
            )
            parts_writer.commit_build()
        after_parts = budget.check_quiescent()
        with _profiled_source(parts_path) as parts_reader:
            snapshot_source.validate_source_coverage(source, parts_reader, coverage)
            assert coverage.snapshot_count == coverage.adapted_count == len(baseline_packets)
            assert coverage.unadapted_count == 0
            for key, packet in baseline_packets.items():
                descriptor = snapshots._read_descriptor(parts_reader, key)
                assert b"".join(snapshots.iter_snapshot_bytes(parts_reader, descriptor)) == canonical_bytes(packet)

        history = build_history(
            receipt_mapping,
            directory=root,
            owned_directory=root / "history",
            cutoff=values["cutoff"],
            tour=tour,
            input_identity=corpus.output_sha256,
            main_cap_bytes=MAIN_CAP,
        )
        after_history = budget.check_quiescent()
        from context_storage_v2.tennis_consumer import (
            prepare_tennis_consumer,
            put_tennis_consumer,
        )

        prepared = prepare_tennis_consumer(
            history,
            native_competition=values["native"],
            tournament_id="189-2026",
            grouping_slug="mens-singles" if tour == "ATP" else "womens-singles",
            observed_at=values["received"],
            surface="Hard",
            best_of=3,
            indoor=None,
            cutoff=values["cutoff"],
            work_directory=root,
            owned_directory=root / "feature",
            main_cap_bytes=MAIN_CAP,
        )
        after_feature = budget.check_quiescent()
        feature_bytes = b"".join(prepared.features.iter_canonical_chunks())
        feature_sha256 = hashlib.sha256(feature_bytes).hexdigest()
        assert feature_bytes == canonical_bytes(oracle["packet"]["features"])
        assert prepared.prediction.p_a_cal == oracle["row"]["p_cal"]
        assert prepared.origin == oracle["packet"]["base"]["reference_weights"]
        assert prepared.selection_reason == oracle["selection_reason"]

        output_path = root / "new-consumers" / "consumers.sqlite"
        output_writer = open_fresh_writer(output_path, plan=SQLiteWriterPlan(MAIN_CAP))
        published = put_tennis_consumer(
            output_writer.connection, prepared, created_at=values["created"]
        )
        assert output_writer.connection.in_transaction
        actual_snapshot = b"".join(
            snapshots.iter_snapshot_bytes(output_writer.connection, published.snapshot)
        )
        assert actual_snapshot == canonical_bytes(oracle["packet"])
        assert published.snapshot.key == oracle["sidecar"]["reference"]["key"]
        assert published.snapshot.payload_digest == oracle["sidecar"]["reference"]["payload_digest"]
        assert tuple(refs.iter_refset(output_writer.connection, published.snapshot.observation_refs)) == tuple(
            oracle["packet"]["observation_refs"]
        )
        assert published.reference == oracle["sidecar"]["reference"]
        assert published.original_hash == oracle["sidecar"]["original_artifact_hash"]
        assert _load_artifact(output_writer.connection, published.original_hash) == {
            "kind": oracle["original"][0],
            "payload": json.loads(oracle["original"][1]),
        }
        assert oracle["original"][2] == values["created"].isoformat()

        # Detached Published data cannot authorize commit.  Release every live
        # input owner first; any cleanup error falls into the rollback path.
        prepared.close()
        prepared = None
        history.close()
        history = None
        source_context.__exit__(None, None, None)
        source = None
        output_writer.commit_build()
        output_writer = None
        final_budget = budget.check_quiescent()

        with _profiled_source(output_path) as reopened:
            descriptor = snapshots._read_descriptor(reopened, published.snapshot.key)
            assert descriptor == published.snapshot
            assert b"".join(snapshots.iter_snapshot_bytes(reopened, descriptor)) == canonical_bytes(
                oracle["packet"]
            )
            assert tuple(refs.iter_refset(reopened, descriptor.observation_refs)) == tuple(
                oracle["packet"]["observation_refs"]
            )
            assert _load_artifact(reopened, published.original_hash) == {
                "kind": oracle["original"][0],
                "payload": json.loads(oracle["original"][1]),
            }

        assert _sha256(source_path) == baseline_hash
        record_property("tour", tour)
        record_property("source_sha256", baseline_hash)
        record_property("corpus_sha256", corpus.output_sha256)
        record_property("ledger_sha256", corpus.ledger_sha256)
        record_property("parts_sha256", _sha256(parts_path))
        record_property("history_sha256", _sha256(root / "history" / "history.sqlite"))
        record_property("features_sha256", _sha256(root / "feature" / "features.sqlite"))
        record_property("consumer_sha256", _sha256(output_path))
        record_property("receipt_inventory_digest", corpus.inventory.logical_digest)
        record_property("old_coverage_digest", coverage.descriptor_digest)
        record_property("feature_canonical_sha256", feature_sha256)
        record_property("snapshot_key", published.snapshot.key)
        record_property("snapshot_raw_sha256", published.snapshot.raw_payload_sha256)
        record_property("snapshot_payload_digest", published.snapshot.payload_digest)
        record_property("original_hash", published.original_hash)
        record_property("protected_receipt_count", len(semantics["protected_receipts"]))
        record_property("semantic_limitations", json.dumps(sorted(limitations)))
        record_property("budget_plan", budget.plan_digest)
        record_property("budget_reserved", initial_budget.workspace_ceiling_bytes)
        record_property("setup_budget_plan", setup_budget.plan_digest)
        record_property("setup_budget_reserved", setup_initial.workspace_ceiling_bytes)
        record_property("setup_workspace_bytes", setup_final.workspace_bytes)
        record_property(
            "union_reserved_bytes",
            setup_initial.workspace_ceiling_bytes + initial_budget.workspace_ceiling_bytes,
        )
        record_property(
            "union_observed_bytes",
            setup_final.workspace_bytes + final_budget.workspace_bytes,
        )
        record_property("after_corpus_bytes", after_corpus.workspace_bytes)
        record_property("after_parts_bytes", after_parts.workspace_bytes)
        record_property("after_history_bytes", after_history.workspace_bytes)
        record_property("after_feature_bytes", after_feature.workspace_bytes)
        record_property("final_workspace_bytes", final_budget.workspace_bytes)
        record_property("final_free_bytes", final_budget.free_bytes)
        return {
            "source_sha256": baseline_hash,
            "corpus_sha256": corpus.output_sha256,
            "ledger_sha256": corpus.ledger_sha256,
            "parts_sha256": _sha256(parts_path),
            "history_sha256": _sha256(root / "history" / "history.sqlite"),
            "features_sha256": _sha256(root / "feature" / "features.sqlite"),
            "consumer_sha256": _sha256(output_path),
            "receipt_inventory_digest": corpus.inventory.logical_digest,
            "old_coverage_digest": coverage.descriptor_digest,
            "feature_canonical_sha256": feature_sha256,
            "workspace_plan": budget.plan_digest,
            "setup_plan": setup_budget.plan_digest,
            "workspace_observation": final_budget,
            "setup_observation": setup_final,
            "union_reserved_bytes": (
                setup_initial.workspace_ceiling_bytes + initial_budget.workspace_ceiling_bytes
            ),
            "union_observed_bytes": setup_final.workspace_bytes + final_budget.workspace_bytes,
            "published": published,
        }
    finally:
        active_error = sys.exc_info()[1]
        cleanup_error = None
        for value, close in (
            (prepared, lambda item: item.close()),
            (history, lambda item: item.close()),
            (source, lambda _item: source_context.__exit__(None, None, None)),
            (output_writer, lambda item: item.close()),
        ):
            if value is not None:
                try:
                    close(value)
                except BaseException as error:
                    cleanup_error = cleanup_error or error
        if active_error is None and cleanup_error is not None:
            raise cleanup_error


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_actual_three_receipt_corpus_reaches_byte_identical_real_consumer(
    tmp_path, monkeypatch, tour, record_property
):
    result = run_small_corpus_consumer_acceptance(
        tmp_path, monkeypatch, tour, record_property=record_property
    )
    assert result["published"].snapshot.key


def test_source_transaction_drift_after_corpus_cannot_start_history(
    tmp_path, monkeypatch
):
    case = _completed_corpus_phase(tmp_path, monkeypatch)
    root = case["root"]
    with _profiled_source(case["corpus"].path) as source:
        inventory_raw(source)
        _artifacts, _created, _limitations, _semantics, receipts = _artifact_semantics(source)
        source.commit()
        source.execute("BEGIN")
        with pytest.raises(RuntimeArtifactTrustError, match="transaction|changed"):
            build_history(
                receipts,
                directory=root,
                owned_directory=root / "history",
                cutoff=case["values"]["cutoff"],
                tour="ATP",
                input_identity=case["corpus"].output_sha256,
                main_cap_bytes=MAIN_CAP,
            )
    assert list((root / "history").iterdir()) == []
    assert _sha256(case["source"]) == case["source_sha256"]


def test_abort_after_completed_private_corpus_retains_it_without_final_generation(
    tmp_path, monkeypatch
):
    case = _completed_corpus_phase(tmp_path, monkeypatch)

    class PlannedAbort(Exception):
        pass

    with pytest.raises(PlannedAbort):
        case["budget"].check_quiescent()
        raise PlannedAbort("stop before Source/History/consumer completion")
    assert case["corpus"].path.exists()
    assert case["corpus"].ledger_path.exists()
    assert _sha256(case["source"]) == case["source_sha256"]
    assert list((case["root"] / "old-parts").iterdir()) == []
    assert list((case["root"] / "history").iterdir()) == []
    assert list((case["root"] / "feature").iterdir()) == []
    assert list((case["root"] / "new-consumers").iterdir()) == []
    observed = case["budget"].check_quiescent()
    assert observed.existing_files == 2


def test_real_late_prepared_cleanup_failure_rolls_back_consumer_before_commit(
    tmp_path, monkeypatch
):
    from context_storage_v2.tennis_consumer import PreparedTennisConsumer

    class LateCleanupFailure(RuntimeError):
        pass

    actual_close = PreparedTennisConsumer.close
    calls = 0

    def failing_close(prepared):
        nonlocal calls
        calls += 1
        actual_close(prepared)
        if calls == 1:
            raise LateCleanupFailure("actual prepared feature close failed late")

    monkeypatch.setattr(PreparedTennisConsumer, "close", failing_close)
    with pytest.raises(LateCleanupFailure, match="failed late"):
        run_small_corpus_consumer_acceptance(tmp_path, monkeypatch, "ATP")
    output = tmp_path / "whole-job" / "new-consumers" / "consumers.sqlite"
    assert output.exists()
    with sqlite3.connect(output) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table'"
        ).fetchall() == []
    assert calls >= 2
    assert (tmp_path / "whole-job" / "corpus" / "legacy-copy.sqlite").exists()
    assert (tmp_path / "whole-job" / "old-parts" / "snapshot-parts.sqlite").exists()
    assert (tmp_path / "whole-job" / "history" / "history.sqlite").exists()
    assert (tmp_path / "whole-job" / "feature" / "features.sqlite").exists()
