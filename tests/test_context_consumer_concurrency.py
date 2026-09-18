"""Consumer CPU validation must not retain the physical SQLite read image."""
from contextlib import closing
import hashlib
import sqlite3

import pytest

from context_models.contracts import ContextIntegrityError, canonical_timestamp
from context_observations import append_observation_batch, observations_as_of
from context_snapshot_storage import MAGIC
from context_snapshots import compute_once
from context_transport import (
    calculate_context_payload,
    context_consumer_reference,
    context_payload_key,
)
from test_context_consumers import read as read_generic, saved
from test_context_observations import NOW as OBSERVED_AT, normalized_record
from test_tennis_shared_consumer import read as read_tennis, stored
from test_context_transport import inputs
from test_tennis_live_worker import context_rows


def _append_and_read_receipt(path):
    record = normalized_record()
    receipt = append_observation_batch(path, ((record, OBSERVED_AT),))
    rows = observations_as_of(
        path,
        record["event_key"],
        cutoff=OBSERVED_AT,
        schedule_revision=record["schedule_revision"],
    )
    assert len(receipt) == len(rows) == 1
    assert rows[0]["digest"] == receipt[0]
    assert rows[0]["event_key"] == record["event_key"]
    assert rows[0]["subject_id"] == record["subject_id"]
    assert rows[0]["kind"] == record["kind"]
    assert rows[0]["payload"] == record["payload"]
    assert rows[0]["observed_at"] == canonical_timestamp(OBSERVED_AT)
    return receipt[0]


def _saved_compact_snapshot(tmp_path):
    arguments = inputs(with_effect=True)
    extra = [
        hashlib.sha256(f"consumer-reference-{index}".encode()).hexdigest()
        for index in range(128)
    ]
    arguments["observation_refs"] = sorted(
        set(arguments["observation_refs"] + extra)
    )
    payload = calculate_context_payload(**arguments)
    key = context_payload_key(payload)
    path = tmp_path / "compact-models.db"
    compute_once(path, key, lambda: payload)
    reference = context_consumer_reference(key, payload)
    with sqlite3.connect(path) as connection:
        raw = connection.execute(
            "SELECT payload FROM context_snapshots WHERE key=?",
            (key,),
        ).fetchone()[0]
        assert raw.startswith(MAGIC)
        assert connection.execute(
            "SELECT count(*) FROM context_snapshot_reference_blocks"
        ).fetchone()[0] > 0
    return path, reference, payload


def test_generic_consumer_releases_sql_before_projection_writer_commit(monkeypatch, tmp_path):
    import context_consumers

    path, reference, payload = saved(tmp_path)
    actual_project = context_consumers.project_context_market
    committed = []

    def project(detached, bound_reference, market):
        committed.append(_append_and_read_receipt(path))
        return actual_project(detached, bound_reference, market)

    monkeypatch.setattr(context_consumers, "project_context_market", project)
    result = read_generic(path, reference, payload)

    assert len(committed) == 1
    assert result["projection"]["used_probability"] == payload["result"]["used_markets"]["winner_a"]


def test_tennis_consumer_releases_sql_before_projection_writer_commit(monkeypatch, tmp_path):
    import tennis.context_consumer as consumer

    path, _, rows = stored(monkeypatch, tmp_path)
    actual_project = consumer.project_context_market
    committed = []

    def project(detached, bound_reference, market):
        if not committed:
            committed.append(_append_and_read_receipt(path))
        return actual_project(detached, bound_reference, market)

    monkeypatch.setattr(consumer, "project_context_market", project)
    result = read_tennis(rows[0], path)

    assert len(committed) == 1
    assert set(result["probabilities"]) == {"A", "B"}


def test_consumer_uses_one_detached_revision_when_writer_changes_snapshot_after_freeze(
        monkeypatch, tmp_path):
    import context_consumers

    path, reference, payload = saved(tmp_path)
    actual_project = context_consumers.project_context_market
    committed = []

    def project(detached, bound_reference, market):
        with closing(sqlite3.connect(path, timeout=.1)) as writer, writer:
            writer.execute(
                "UPDATE context_snapshots SET payload=? WHERE key=?",
                (b"not-json", reference["key"]),
            )
        committed.append("new revision")
        return actual_project(detached, bound_reference, market)

    monkeypatch.setattr(context_consumers, "project_context_market", project)
    result = read_generic(path, reference, payload)

    assert committed == ["new revision"]
    assert result["projection"]["used_probability"] == payload["result"]["used_markets"]["winner_a"]
    with pytest.raises(ContextIntegrityError):
        read_generic(path, reference, payload)


def test_compact_reference_blocks_are_frozen_before_projection_writer_commit(
        monkeypatch, tmp_path):
    import context_consumers

    path, reference, payload = _saved_compact_snapshot(tmp_path)
    actual_project = context_consumers.project_context_market
    committed = []

    def project(detached, bound_reference, market):
        with closing(sqlite3.connect(path, timeout=.1)) as writer, writer:
            writer.execute("DELETE FROM context_snapshot_reference_blocks")
        committed.append("reference blocks removed")
        return actual_project(detached, bound_reference, market)

    monkeypatch.setattr(context_consumers, "project_context_market", project)
    result = read_generic(path, reference, payload)

    assert committed == ["reference blocks removed"]
    assert result["projection"]["used_probability"] == payload["result"]["used_markets"]["winner_a"]
    with pytest.raises(ContextIntegrityError):
        read_generic(path, reference, payload)


def test_tennis_artifacts_remain_one_packet_when_writer_changes_state_after_freeze(
        monkeypatch, tmp_path):
    import tennis.context_consumer as consumer

    path, _, rows = stored(monkeypatch, tmp_path)
    _, packet = context_rows(path)[0]
    state_hash = packet["base"]["model_hash"]
    actual_decode = consumer._decode_artifact_row
    committed = []

    def decode(digest, frozen_row):
        if not committed:
            with closing(sqlite3.connect(path, timeout=.1)) as writer, writer:
                writer.execute(
                    "UPDATE artifacts SET payload=? WHERE digest=?",
                    (b"not-json", state_hash),
                )
            committed.append("state changed")
        return actual_decode(digest, frozen_row)

    monkeypatch.setattr(consumer, "_decode_artifact_row", decode)
    result = read_tennis(rows[0], path)

    assert committed == ["state changed"]
    assert result["probabilities"] == {
        "A": packet["result"]["used_markets"]["winner_a"],
        "B": packet["result"]["used_markets"]["winner_b"],
    }
    with pytest.raises(ContextIntegrityError):
        read_tennis(rows[0], path)
