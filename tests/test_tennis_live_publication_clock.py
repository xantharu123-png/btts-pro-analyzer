"""Publication/append ordering on actual A1/B3/Shadow writes, synthetic source."""
from datetime import timedelta
import json
import sqlite3

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from scripts import tennis_daily as daily
from tennis import live_context, shadow
from test_tennis_live_worker import NOW, competition, configure, run_batch


def stored_original(db):
    with sqlite3.connect(db) as connection:
        return connection.execute("SELECT digest,payload,created_at FROM artifacts WHERE kind=?",
            ("tennis-live-winner-original-v1",)).fetchone()


def stored_revisions(db):
    if not db.exists():
        return []
    with sqlite3.connect(db) as connection:
        return connection.execute("SELECT * FROM prediction_revisions ORDER BY revision_id").fetchall()


def with_append(batch, fixtures, result, append):
    for item in batch.pending:
        item["kwargs"]["append_observed_at"] = append


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_initial_publication_clock_boundary_preserves_actual_append(monkeypatch, tmp_path, explicit, offset):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    publication = NOW + timedelta(seconds=10)
    append = publication + timedelta(microseconds=offset)
    monkeypatch.setattr(live_context, "_now", lambda: publication)
    reads = []
    def final_clock(value):
        reads.append(value)
        moment = value if value is not None else append
        return moment.timestamp(), moment.isoformat()
    monkeypatch.setattr(shadow, "_prediction_append_time", final_clock)
    execute = lambda: run_batch(db, predictions, before_finish=lambda *args: with_append(*args, append if explicit else None))
    if offset < 0:
        with pytest.raises(ContextContractError):
            execute()
        assert not predictions.exists() and reads == [append if explicit else None]
    else:
        result, _ = execute()
        assert result["stored"] == 1
        revision = json.loads(stored_revisions(predictions)[0][3])
        assert canonical_timestamp(revision["append_observed_at"]) == canonical_timestamp(append)
        assert canonical_timestamp(revision["append_observed_at"]) >= canonical_timestamp(publication)
        assert reads == [append if explicit else None] * 2
    assert canonical_timestamp(stored_original(db)[2]) == canonical_timestamp(publication)


def test_real_idempotent_existing_original_uses_stored_not_new_requested_clock(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    first, _ = run_batch(db, predictions)
    actual_before, revisions_before = stored_original(db), stored_revisions(predictions)
    monkeypatch.setattr(live_context, "_now", lambda: NOW + timedelta(minutes=30))
    second, _ = run_batch(db, predictions)
    assert first["stored"] == 1 and second["stored"] == 0
    assert stored_original(db) == actual_before
    assert stored_revisions(predictions) == revisions_before
    assert canonical_timestamp(actual_before[2]) == canonical_timestamp(NOW + timedelta(seconds=1))


def test_actual_daily_backward_append_preserves_prior_fixture_status_but_no_forecast(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    monkeypatch.setattr(daily, "auto_settle_completed", lambda: 0)
    monkeypatch.setattr(daily, "tournament_surface_map", lambda *args: {})
    monkeypatch.setattr(daily, "fetch_fixtures", daily.fetch_fixtures_espn)
    monkeypatch.setattr(daily.sys, "argv", ["tennis_daily.py", "2026-09-09"])
    monkeypatch.setattr(live_context, "_now", lambda: NOW + timedelta(minutes=30))
    monkeypatch.setattr(shadow, "_prediction_append_time", lambda value: (
        (NOW + timedelta(seconds=2)).timestamp(), (NOW + timedelta(seconds=2)).isoformat()))
    before, actual_store = [], shadow.store_prediction
    def record_before_append(*args, **kwargs):
        # The ordinary fetch's observe_status callback has already created this
        # database. That independent, truthful fixture observation must survive.
        assert predictions.exists()
        with sqlite3.connect(predictions) as connection:
            assert connection.execute("SELECT count(*) FROM predictions").fetchone()[0] == 0
            before.extend(connection.execute("SELECT * FROM fixture_status_observations").fetchall())
        return actual_store(*args, **kwargs)
    monkeypatch.setattr(shadow, "store_prediction", record_before_append)
    with pytest.raises(ContextContractError):
        daily.main()
    assert before and stored_revisions(predictions) == []
    with sqlite3.connect(predictions) as connection:
        assert connection.execute("SELECT count(*) FROM predictions").fetchone()[0] == 0
        assert connection.execute("SELECT * FROM fixture_status_observations").fetchall() == before


def test_actual_existing_later_publication_rejects_earlier_requested_put_and_append(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    publication = NOW + timedelta(seconds=30)
    original_put = live_context.put_artifact
    def prior_publication(*args, **kwargs):
        # A real earlier writer already published these identical payload bytes.
        original_put(*args, **{**kwargs, "created_at": publication})
        return original_put(*args, **kwargs)  # Idempotent call cannot replace its clock.
    monkeypatch.setattr(live_context, "put_artifact", prior_publication)
    with pytest.raises(ContextContractError):
        run_batch(db, predictions)
    assert not predictions.exists()
    assert canonical_timestamp(stored_original(db)[2]) == canonical_timestamp(publication)


@pytest.mark.parametrize("existing", [False, True])
def test_final_transaction_clock_is_rechecked_after_successful_preflight(monkeypatch, tmp_path, existing):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    if existing:
        run_batch(db, predictions)
    before = stored_revisions(predictions)
    decision = NOW + timedelta(seconds=10)
    publication = decision + timedelta(seconds=1)
    monkeypatch.setattr(live_context, "_now", lambda: publication)
    clocks = iter((publication + timedelta(seconds=1), publication - timedelta(microseconds=1)))
    reads, statements = [], []
    actual_connect = shadow._connect
    def traced_connect(*args, **kwargs):
        connection = actual_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection
    monkeypatch.setattr(shadow, "_connect", traced_connect)
    def moved_clock(value):
        assert value is None
        assert any(sql == "BEGIN IMMEDIATE" for sql in statements) is bool(reads)
        moment = next(clocks)
        reads.append(moment)
        return moment.timestamp(), moment.isoformat()
    monkeypatch.setattr(shadow, "_prediction_append_time", moved_clock)
    with pytest.raises(ContextContractError):
        run_batch(db, predictions, decision=decision,
            before_finish=lambda *args: with_append(*args, None))
    assert len(reads) == 2
    assert stored_revisions(predictions) == before
    with sqlite3.connect(predictions) as connection:
        assert connection.execute("SELECT count(*) FROM predictions").fetchone()[0] == int(existing)


@pytest.mark.parametrize("bad", [None, True, 0, 1.5, [], {}, "", "2026-09-09T12:00:01",
    "2026-09-09T12:00:01+00:00", "2026-09-09T14:00:01.000000+02:00",
    canonical_timestamp(NOW - timedelta(microseconds=1))])
def test_context_cannot_omit_or_supply_noncanonical_publication_clock(monkeypatch, tmp_path, bad):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    actual_store = shadow.store_prediction
    def changed(*args, **kwargs):
        kwargs["context_original_published_at"] = bad
        return actual_store(*args, **kwargs)
    monkeypatch.setattr(shadow, "store_prediction", changed)
    with pytest.raises(ContextContractError):
        run_batch(db, predictions)
    assert not predictions.exists()


def test_orphan_publication_clock_cannot_turn_a_legacy_row_into_context(monkeypatch, tmp_path):
    comp = competition()
    comp["competitors"][0]["id"] = "unverified"
    db, predictions, _, _ = configure(monkeypatch, tmp_path, comp=comp)
    actual_store = shadow.store_prediction
    def changed(*args, **kwargs):
        assert kwargs.get("context_model") is None
        kwargs["context_original_published_at"] = canonical_timestamp(NOW + timedelta(seconds=1))
        return actual_store(*args, **kwargs)
    monkeypatch.setattr(shadow, "store_prediction", changed)
    with pytest.raises(ContextContractError):
        run_batch(db, predictions)
    assert not predictions.exists()


@pytest.mark.parametrize("explicit_null", [False, True])
def test_legacy_without_context_keeps_single_original_clock_read(monkeypatch, tmp_path, explicit_null):
    comp = competition()
    comp["competitors"][0]["id"] = "unverified"
    db, predictions, _, _ = configure(monkeypatch, tmp_path, comp=comp)
    actual_clock, reads = shadow._prediction_append_time, []
    def counted(value):
        reads.append(value)
        return actual_clock(value)
    monkeypatch.setattr(shadow, "_prediction_append_time", counted)
    actual_store = shadow.store_prediction
    if explicit_null:
        def null_path(*args, **kwargs):
            kwargs.update(context_model=None, context_original=None, context_original_published_at=None)
            return actual_store(*args, **kwargs)
        monkeypatch.setattr(shadow, "store_prediction", null_path)
    result, rows = run_batch(db, predictions)
    assert result["stored"] == 1 and len(reads) == 1
    assert "context_model" not in json.loads(rows[0]["context_json"])
    assert stored_original(db) is None
