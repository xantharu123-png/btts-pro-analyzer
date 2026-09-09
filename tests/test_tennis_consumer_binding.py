"""Permanent regressions for the independent real-store consumer findings.

Synthetic mechanics only. A public rehash cannot waive an actual tour mismatch;
these tests do not claim source authenticity or a learned context improvement.
"""
from contextlib import closing
from copy import deepcopy
from datetime import timedelta
import json
import sqlite3

import pytest

from context_consumers import load_context_market
from context_models.contracts import ContextContractError
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, original_base
from context_models.tennis_v3 import tennis_reference_hash_v3
from context_snapshots import _payload_digest, compute_once
from context_transport import calculate_context_payload, context_consumer_reference, context_payload_key
from model_artifacts import canonical_bytes, put_artifact
from tennis.context_consumer import load_tennis_winner_context
from tennis.prediction_revisions import _canonical, _revision_digest
from test_tennis_live_worker import NOW, configure, context_rows, run_batch
from test_tennis_shared_consumer import stored


def repoint_state(db, row, state_hash):
    """Rebuild every public original/feature/B3/sidecar identity, not one hash."""
    row = deepcopy(row)
    context = json.loads(row["context_json"])
    packet = deepcopy(dict(context_rows(db))[context["context_model"]["reference"]["key"]])
    origin = deepcopy(packet["base"]["reference_weights"])
    origin["state_hash"] = state_hash
    published = put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND,
        payload={"schema": 1, "origin": origin}, created_at=NOW+timedelta(seconds=1))
    base = original_base(origin)
    features = deepcopy(packet["features"])
    features["reference_hash"] = tennis_reference_hash_v3(base, packet["event"])
    rebuilt = calculate_context_payload(event=packet["event"], base=base, features=features,
        observation_refs=packet["observation_refs"], preprocessing_refs=[],
        effect_artifact=None, effect_hash=None, approval=None)
    key = context_payload_key(rebuilt)
    assert compute_once(db, key, lambda: rebuilt) == rebuilt
    context["context_model"].update(reference=context_consumer_reference(key, rebuilt),
        original_artifact_hash=published)
    context["model_inputs"]["model_artifact_hash"] = state_hash
    row["context_json"] = json.dumps(context)
    return row


def replace_disposable_revision(predictions, row):
    """Only a temporary test store; keep the actual revision reader/schema.

    Restore the exact immutable trigger after a raw SQL/public-hash witness.
    Synthetic green model gates exercise adapters, never real model approval.
    """
    with closing(sqlite3.connect(predictions)) as conn, conn:
        old_id, raw = conn.execute(
            "SELECT revision_id,payload_json FROM prediction_revisions WHERE prediction_id=?", (row["id"],),
        ).fetchone()
        payload = json.loads(raw)
        payload.update(context_json=row["context_json"],
            gates_json='{"synthetic-qa":{"passed":true},"Quote/Risiko-EV":{"passed":false}}',
            verdict="WETTE", recommended_side="A")
        serialized = _canonical(payload)
        revision = _revision_digest(row["id"], serialized)
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='tennis_model_revision_no_update'").fetchone()[0]
        conn.execute("DROP TRIGGER tennis_model_revision_no_update")
        conn.execute("UPDATE prediction_revisions SET revision_id=?,payload_json=? WHERE revision_id=?",
            (revision, serialized, old_id))
        conn.execute(sql)
        assert conn.execute("SELECT sql FROM sqlite_master WHERE name='tennis_model_revision_no_update'").fetchone()[0] == sql
    return revision


def forbid_production_work(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("consumer called model decoding, prediction, publication or provider")
    for name in ("tennis.tour_state._decode_wrapper", "tennis.state_codec.decode_state",
                 "tennis.predict.predict_match", "model_artifacts.put_artifact",
                 "context_snapshots.compute_once", "requests.get"):
        monkeypatch.setattr(name, forbidden)


@pytest.mark.parametrize("adapter", ["normal", "strict", "risk"])
@pytest.mark.parametrize("different_tour", [False, True])
def test_actual_adapters_bind_the_actual_state_tour(monkeypatch, tmp_path, adapter, different_tour):
    from ev_signal_sources import tennis_model_signals, tennis_signals
    from riskobet_candidates import adapt_tennis_shadow
    from tennis.shadow import latest_predictions
    db, predictions, refs, _ = configure(monkeypatch, tmp_path, tours=("ATP", "WTA"))
    _, rows = run_batch(db, predictions)
    row = next(r for r in rows if r["tour"] == "ATP")
    altered = repoint_state(db, row, refs["WTA" if different_tour else "ATP"])
    revision = replace_disposable_revision(predictions, altered)
    now = NOW+timedelta(seconds=3)
    observed = next(r for r in latest_predictions(predictions, as_of=now) if r["id"] == row["id"])
    assert observed["model_revision_id"] == revision and observed["context_json"] == altered["context_json"]
    reader = {"normal": lambda: tennis_model_signals(predictions, today="2026-09-09", now=now),
        "strict": lambda: tennis_signals(predictions, today="2026-09-09", now=now),
        "risk": lambda: adapt_tennis_shadow(predictions, as_of=now)}[adapter]
    before = db.read_bytes(), predictions.read_bytes()
    forbid_production_work(monkeypatch)
    if different_tour:
        with pytest.raises(ContextContractError):
            reader()
    else:
        output = reader()
        assert output
        if adapter == "risk":
            assert next(r for r in output if r.snapshot.event_label == "Alpha A vs Beta B").snapshot.context_ref is not None
        else:
            assert output[0].context_ref is not None
    assert (db.read_bytes(), predictions.read_bytes()) == before


@pytest.mark.parametrize("header,bad", [
    ("wrapper_schema", True), ("wrapper_schema", 1.), ("wrapper_schema", 2),
    ("wrapper_schema", None), ("wrapper_schema", "1"),
    ("state_schema", True), ("state_schema", 1.), ("state_schema", 2),
    ("state_schema", None), ("state_schema", "1"),
    ("tour", None), ("tour", []), ("tour", {}), ("tour", False), ("tour", "atp"),
    ("state", None), ("state", []), ("state", {"schema": 1, "tour": "ATP"}),
    ("missing_wrapper_key", None), ("extra_wrapper_key", None), ("extra_state_key", None),
])
def test_rehashed_known_state_header_is_still_checked(monkeypatch, tmp_path, header, bad):
    db, predictions, refs, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    with closing(sqlite3.connect(db)) as conn:
        payload = json.loads(conn.execute("SELECT payload FROM artifacts WHERE digest=?", (refs["ATP"],)).fetchone()[0])
    if header == "wrapper_schema": payload["schema"] = bad
    elif header == "state_schema": payload["state"]["schema"] = bad
    elif header == "tour": payload["state"]["tour"] = bad
    elif header == "state": payload["state"] = bad
    elif header == "missing_wrapper_key": payload.pop("training_cutoff")
    elif header == "extra_wrapper_key": payload["unknown"] = None
    else: payload["state"]["unknown"] = None
    state_hash = put_artifact(db, kind="tennis-tour-state", payload=payload, created_at=NOW-timedelta(hours=1))
    altered = repoint_state(db, rows[0], state_hash)
    forbid_production_work(monkeypatch)
    before = db.read_bytes()
    with pytest.raises(ContextContractError):
        load_tennis_winner_context(altered, path=db)
    assert db.read_bytes() == before


@pytest.mark.parametrize("bad", [False, 0, [], {}, True, 1, b"{}"])
def test_present_nontext_context_is_not_optional_absence(monkeypatch, tmp_path, bad):
    monkeypatch.setattr("context_consumers._reader", lambda *a, **k: pytest.fail("malformed context opened DB"))
    with pytest.raises(ContextContractError):
        load_tennis_winner_context({"context_json": bad}, path=tmp_path/"absent.db")
    assert not (tmp_path/"absent.db").exists()


@pytest.mark.parametrize("bad", [False, 0, [], {}])
def test_actual_risk_reader_rejects_falsey_corruption(monkeypatch, tmp_path, bad):
    from riskobet_candidates import adapt_tennis_shadow
    from tennis.shadow import latest_predictions
    db, predictions, rows = stored(monkeypatch, tmp_path)
    altered = deepcopy(rows[0])
    altered["context_json"] = bad
    revision = replace_disposable_revision(predictions, altered)
    now = NOW+timedelta(seconds=3)
    observed = latest_predictions(predictions, as_of=now)[0]
    assert observed["model_revision_id"] == revision
    assert type(observed["context_json"]) is type(bad)
    before = db.read_bytes(), predictions.read_bytes()
    with pytest.raises(ContextContractError):
        adapt_tennis_shadow(predictions, as_of=now)
    assert (db.read_bytes(), predictions.read_bytes()) == before


@pytest.mark.parametrize("row", [{}, {"context_json": None}, {"context_json": ""},
    {"context_json": "{}"}, {"context_json": '{"players":{}}'}])
def test_explicit_legacy_absence_is_still_optional(monkeypatch, tmp_path, row):
    monkeypatch.setattr("context_consumers._reader", lambda *a, **k: pytest.fail("legacy opened DB"))
    assert load_tennis_winner_context(row, path=tmp_path/"absent.db") is None
    assert not (tmp_path/"absent.db").exists()


@pytest.mark.parametrize("bad", [None, [], False, 7, {}, {"cutoff": None}])
def test_generic_reader_keeps_typed_errors_for_invalid_base(monkeypatch, tmp_path, bad):
    db, _, rows = stored(monkeypatch, tmp_path)
    key, packet = context_rows(db)[0]
    sidecar = json.loads(rows[0]["context_json"])["context_model"]
    packet["base"] = bad
    ref = deepcopy(sidecar["reference"])
    ref["payload_digest"] = _payload_digest(key, packet)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE context_snapshots SET payload=?,payload_digest=? WHERE key=?",
            (canonical_bytes(packet), ref["payload_digest"], key))
    before = db.read_bytes()
    with pytest.raises(ContextContractError):
        load_context_market(db, ref, "winner_a", expected_event=sidecar["event"], expected_cutoff=sidecar["cutoff"])
    assert db.read_bytes() == before
