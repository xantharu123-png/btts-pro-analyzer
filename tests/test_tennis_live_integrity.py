"""Adversarial real storage/revision checks for the opt-in live producer."""
from copy import deepcopy
from datetime import timedelta
import json
import math
import sqlite3

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from model_artifacts import canonical_bytes
from test_tennis_live_origin import origin, base
from test_tennis_live_worker import NOW, competition, configure, context_rows, run_batch
from tennis import shadow


@pytest.mark.parametrize("field", ["surface", "tour", "best_of", "indoor", "player_a", "state_key_a"])
@pytest.mark.parametrize("invalid", [[], {}, True, 0., "", " unknown "])
def test_origin_input_types_reject_without_raw_type_errors(field, invalid):
    from context_models.tennis_live import validate_live_winner_reference
    value = origin()
    value["inputs"][field] = invalid
    if field == "indoor" and invalid is True:
        assert validate_live_winner_reference(value, []) == value
        return  # True is a real executed-input flag, not native metadata proof.
    with pytest.raises(ContextContractError):
        validate_live_winner_reference(value, [])


@pytest.mark.parametrize("mutation", ["state", "missing_receipt", "hidden_event_index", "participant_revision", "same_time_conflict"])
def test_changed_actual_storage_or_same_event_revision_cannot_publish_shadow(monkeypatch, tmp_path, mutation):
    from context_observations import append_observation
    from context_sources.tennis_status import normalize_tennis_status
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    original_read = live_context.tennis_observations_as_of
    done = False
    def attack(*args, **kwargs):
        nonlocal done
        if not done:
            done = True
            with sqlite3.connect(db) as conn:
                if mutation == "state":
                    conn.execute("UPDATE artifacts SET payload=? WHERE kind='tennis-tour-state'", (b'{}',))
                elif mutation == "missing_receipt": conn.execute("DELETE FROM context_observations")
                elif mutation == "hidden_event_index": conn.execute("UPDATE context_observations SET event_key='espn:tennis:ATP:match:999'")
            if mutation in {"participant_revision", "same_time_conflict"}:
                comp = competition()
                comp["competitors"][0]["id"] = "9"
                received = NOW-timedelta(seconds=5 if mutation == "participant_revision" else 10)
                for row in normalize_tennis_status("ATP", "189-2026", comp, grouping_slug="mens-singles", observed_at=received):
                    append_observation(db, row, observed_at=received)
        return original_read(*args, **kwargs)
    monkeypatch.setattr(live_context, "tennis_observations_as_of", attack)
    with pytest.raises(ContextContractError):
        run_batch(db, predictions)
    assert not predictions.exists() and context_rows(db) == []


def test_original_publication_existing_actual_clock_cannot_be_backdated(monkeypatch, tmp_path):
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    put = live_context.put_artifact
    def tampered(*args, **kwargs):
        if kwargs["kind"] == "tennis-live-winner-original-v1":
            kwargs["created_at"] = NOW-timedelta(seconds=1)
        return put(*args, **kwargs)
    monkeypatch.setattr(live_context, "put_artifact", tampered)
    with pytest.raises(ContextContractError):
        run_batch(db, predictions)
    assert not predictions.exists() and context_rows(db) == []


def test_same_actual_fixture_revision_uses_one_snapshot_calculation(monkeypatch, tmp_path):
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    compute = live_context.calculate_context_payload
    calls = []
    def counted(**kwargs):
        calls.append(kwargs)
        # Actual source readers/model loaders are already closed here.
        with monkeypatch.context() as patch:
            patch.setattr(live_context, "tennis_observations_as_of", lambda *a, **k: pytest.fail("B1 inside compute"))
            patch.setattr(live_context, "_reader", lambda *a, **k: pytest.fail("DB inside compute"))
            return compute(**kwargs)
    monkeypatch.setattr(live_context, "calculate_context_payload", counted)
    first, rows = run_batch(db, predictions)
    old_id = rows[0]["model_revision_id"]
    second, rows = run_batch(db, predictions)
    assert first["stored"] == 1 and second["stored"] == 0
    assert len(calls) == 1 and len(context_rows(db)) == 1 and rows[0]["model_revision_id"] == old_id


@pytest.mark.parametrize("field", ["event", "cutoff", "reference", "markets", "original_artifact_hash"])
def test_new_shadow_revision_rejects_foreign_sidecar_atomically(monkeypatch, tmp_path, field):
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, old = run_batch(db, predictions)
    old_row = old[0]
    with sqlite3.connect(predictions) as conn:
        before = conn.execute("SELECT * FROM prediction_revisions").fetchall()
    original_store = shadow.store_prediction
    def changed(*args, **kwargs):
        link = deepcopy(kwargs["context_model"])
        if field == "event": link["event"]["home_id"] = "espn:tennis:ATP:player:9"
        elif field == "cutoff": link["cutoff"] = canonical_timestamp(NOW)
        elif field == "reference": link["reference"] = {"schema": 1, "kind": "other", "key": "a"*64, "payload_digest": "b"*64}
        elif field == "markets": link["markets"] = {"A": "winner_b", "B": "winner_a"}
        else: link["original_artifact_hash"] = "f"*64
        kwargs["context_model"] = link
        return original_store(*args, **kwargs)
    monkeypatch.setattr(shadow, "store_prediction", changed)
    later = NOW+timedelta(hours=2)
    monkeypatch.setattr(live_context, "_now", lambda: later+timedelta(seconds=1))
    from scripts import tennis_daily as daily
    with pytest.raises(ContextContractError):
        daily.refresh_pending_predictions(db_path=predictions, as_of=later, append_observed_at=later+timedelta(seconds=2))
    with sqlite3.connect(predictions) as conn:
        assert conn.execute("SELECT * FROM prediction_revisions").fetchall() == before
    assert shadow.latest_predictions(predictions, as_of=later)[0]["model_revision_id"] == old_row["model_revision_id"]


@pytest.mark.parametrize("source_tour", ["", "WTA"])
def test_missing_or_foreign_legacy_parent_tour_is_not_certified_as_current_tour(monkeypatch, tmp_path, source_tour):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    with sqlite3.connect(predictions) as conn:
        conn.execute("UPDATE predictions SET tour=?", (source_tour,))
        before = conn.execute("SELECT * FROM prediction_revisions").fetchall()
    with pytest.raises(ContextContractError):
        run_batch(db, predictions, decision=NOW+timedelta(seconds=1))
    with sqlite3.connect(predictions) as conn:
        assert conn.execute("SELECT * FROM prediction_revisions").fetchall() == before


def test_persisted_foreign_tour_revision_blocks_even_when_parent_tour_matches(monkeypatch, tmp_path):
    from tennis.prediction_revisions import _canonical, _revision_digest
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, rows = run_batch(db, predictions)
    with sqlite3.connect(predictions) as conn:
        item = conn.execute("SELECT payload_json FROM prediction_revisions LIMIT 1").fetchone()[0]
        payload = json.loads(item)
        payload.update(tour="WTA", created_utc=(NOW+timedelta(microseconds=1)).timestamp())
        # A real separately appended legacy revision; no trigger bypass/update.
        payload["context_json"] = "{}"
        serialized = _canonical(payload)
        conn.execute("INSERT INTO prediction_revisions VALUES (?,?,?,?)", (_revision_digest(rows[0]["id"], serialized),
            rows[0]["id"], payload["created_utc"], serialized))
        before = conn.execute("SELECT * FROM prediction_revisions").fetchall()
    with pytest.raises(ContextContractError):
        run_batch(db, predictions, decision=NOW+timedelta(seconds=1))
    with sqlite3.connect(predictions) as conn:
        assert conn.execute("SELECT * FROM prediction_revisions").fetchall() == before


def fitted_catalog(db, monkeypatch, *, count=1, extra_slots=None, wrong_surface=False):
    from context_models.tennis_v3 import FEATURE_VERSION
    from context_models.tennis_effect import STATUS_WINNER_VARIANT
    from model_artifacts import load_manifest, publish_slots, put_artifact
    from test_tennis_context_model import artifact, features
    from tennis.live_context import _event
    from context_sources.tennis_status import normalize_tennis_status
    native = normalize_tennis_status("ATP", "189-2026", competition(), grouping_slug="mens-singles",
        observed_at=NOW-timedelta(seconds=10))[0]
    ev = _event(native)
    original = base()
    fake_features = features()
    fake_features["coverage"] = {"version": "tennis-performed-load-coverage-v2", "case":
        "no-history.observed-only.missing-rest.no-history"}
    fitted = artifact(original, fake_features, ev)
    fitted.update(feature_version=FEATURE_VERSION, model_variant=STATUS_WINNER_VARIANT)
    if wrong_surface: fitted["population"]["surfaces"] = ["Hard"]
    slots, refs = {}, []
    for index in range(count):
        # Real B2 fit values; varying an identity does not create empirical data.
        model = {**deepcopy(fitted), "training_refs_hash": str(index+1)*64}
        ref = put_artifact(db, kind="context-effect-v1", payload=model, created_at=NOW-timedelta(hours=1))
        refs.append(ref)
        slots[f"experimental-live-test:{index}"] = ref
    slots.update(extra_slots or {})
    current, _ = load_manifest(db)
    publish_slots(db, slots, expected_manifest=current, published_at=NOW-timedelta(minutes=1))
    return refs


@pytest.mark.parametrize("count,wrong_surface", [(1, False), (2, False), (1, True)])
def test_actual_fitted_catalog_keeps_missing_native_context_on_original_basis(monkeypatch, tmp_path, count, wrong_surface):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    fitted = fitted_catalog(db, monkeypatch, count=count, wrong_surface=wrong_surface)
    result, rows = run_batch(db, predictions)
    packet = context_rows(db)[0][1]
    assert not result["errors"] and len(rows) == 1
    if count == 1 and not wrong_surface:
        assert packet["effect_hash"] == fitted[0]
    else:
        assert packet["effect_hash"] is None
    assert packet["result"]["role"] == "not_applied" and packet["result"]["comparison_params"] is None
    assert canonical_bytes(packet["result"]["used_markets"]) == canonical_bytes(packet["base"]["markets"])
    assert packet["approval"] is None and packet["result"]["certified_markets"] == []


@pytest.mark.parametrize("corruption", ["wrong_effect", "forged_approval", "unresolved_approval_slot", "broken_hash"])
def test_claimed_actual_active_model_or_approval_corruption_is_not_no_data(monkeypatch, tmp_path, corruption):
    from model_artifacts import load_manifest, publish_slots, put_artifact
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    effect = fitted_catalog(db, monkeypatch)[0]
    if corruption == "wrong_effect":
        ref = put_artifact(db, kind="context-effect-v1", payload={"unverified": True}, created_at=NOW-timedelta(hours=1))
        updates = {"invalid-fitted-model": ref}
    elif corruption == "broken_hash":
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE artifacts SET payload=? WHERE digest=?", (b'{}', effect))
        updates = None
    else:
        claim = put_artifact(db, kind="context-approval-v1", payload={"passed": True}, created_at=NOW-timedelta(hours=1))
        updates = {"context-approval:"+(effect if corruption == "forged_approval" else "f"*64): claim}
    if updates:
        current, _ = load_manifest(db)
        publish_slots(db, updates, expected_manifest=current, published_at=NOW-timedelta(seconds=30))
    with pytest.raises(ContextContractError):
        run_batch(db, predictions)
    assert not predictions.exists() and context_rows(db) == []
