"""Real temporary A1/B1/B3/Shadow integration, synthetic provider responses."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from model_artifacts import canonical_bytes, put_artifact, publish_slots
from scripts import tennis_daily as daily
from tennis import shadow
from tennis.elo import SurfaceElo
from tennis.model_state import ModelState
from tennis.serve_model import ServeReturnModel
from tennis.state_codec import encode_state

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def publish_state(db, *, tour="ATP", coefficient=1.0173):
    elo = SurfaceElo()
    for _ in range(5):
        elo.update("alpha a", "beta b", "Hard")
    state = ModelState(elo, ServeReturnModel(), coefficient if tour == "ATP" else 1., .00182, 800,
        (NOW-timedelta(hours=2)).timestamp(), "2026-09-08", 0., tour_scope=tour,
        stats_through_kind="tournament_start_proxy" if tour == "ATP" else "result_date",
        training_cutoff=(NOW-timedelta(hours=3)).isoformat())
    payload = {"schema": 1, "training_cutoff": state.training_cutoff, "state": encode_state(state, tour=tour)}
    ref = put_artifact(db, kind="tennis-tour-state", payload=payload, created_at=NOW-timedelta(hours=1))
    from model_artifacts import load_manifest
    current, _ = load_manifest(db)
    publish_slots(db, {"tennis:"+tour: ref}, expected_manifest=current, published_at=NOW-timedelta(minutes=50))
    return ref


def competition(**changes):
    return {"id": "201", "date": "2026-09-09T17:00Z", "surface": "Hard",
        "status": {"type": {"state": "pre", "name": "STATUS_SCHEDULED", "completed": False}},
        "competitors": [{"id": "1", "athlete": {"displayName": "Alpha A"}},
                        {"id": "2", "athlete": {"displayName": "Beta B"}}], **changes}


def response(comp=None, tour="ATP"):
    return {"events": [{"id": "189-2026", "name": "Example Open", "groupings": [{
        "grouping": {"slug": "mens-singles" if tour == "ATP" else "womens-singles"},
        "competitions": [comp or competition()]}]}]}


def configure(monkeypatch, tmp_path, *, comp=None, tours=("ATP",), same_id=False):
    from context_sources import tennis_capture
    import runtime_paths
    from tennis import live_context
    db, predictions = tmp_path/"context.db", tmp_path/"shadow.db"
    refs = {tour: publish_state(db, tour=tour) for tour in tours}
    monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", db)
    from tennis.tour_state import load_tour_state
    def actual_tour_state(*args, **kwargs):
        kwargs.setdefault("path", db)
        return load_tour_state(*args, **kwargs)
    monkeypatch.setattr(daily, "load_tour_state", actual_tour_state)
    monkeypatch.setattr(shadow, "DB_PATH", predictions)
    monkeypatch.setattr(tennis_capture, "_receipt_now", lambda: NOW-timedelta(seconds=10))
    monkeypatch.setattr(live_context, "_now", lambda: NOW+timedelta(seconds=1))
    monkeypatch.setattr(daily, "_refresh_now", lambda: NOW)
    calls = []
    class Reply:
        def __init__(self, raw): self.raw = raw
        def raise_for_status(self): pass
        def json(self): return deepcopy(self.raw)
    def get(url, **kwargs):
        calls.append(url)
        tour = "WTA" if "/wta/" in url else "ATP"
        actual = deepcopy(comp or competition())
        if tour == "WTA" and not same_id:
            actual["id"] = "202"
        return Reply(response(actual, tour) if tour in tours else {"events": []})
    monkeypatch.setattr(daily.requests, "get", get)
    return db, predictions, refs, calls


def run_batch(db, predictions, *, decision=NOW, before_finish=None):
    from context_sources.tennis_capture import capture_tennis_worker
    from tennis.live_context import live_worker
    with live_worker(path=db) as batch:
        with capture_tennis_worker(path=db) as capture:
            batch.attach_capture(capture)
            fixtures = daily.fetch_fixtures_espn("2026-09-09")
            result = daily.scan_fixtures("2026-09-09", fixtures, decision_at=decision,
                db_path=predictions, surfaces={}, workload_history=(),
                append_observed_at=NOW+timedelta(seconds=2))
            assert result["stored"] == 0
            if before_finish: before_finish(batch, fixtures, result)
        batch.finish()
    return result, shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))


def context_rows(db):
    with sqlite3.connect(db) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='context_snapshots'").fetchone():
            return []
        return [(key, json.loads(payload)) for key, payload in conn.execute("SELECT key,payload FROM context_snapshots")]


def test_real_producer_preserves_full_original_and_links_only_after_capture_commit(monkeypatch, tmp_path):
    db, predictions, states, calls = configure(monkeypatch, tmp_path)
    from tennis import live_context
    original_read = live_context.tennis_observations_as_of
    def checked_read(*args, **kwargs):
        from context_sources.tennis_capture import _CURRENT
        assert _CURRENT.get() is None
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT count(*) FROM context_observations").fetchone()[0] == 1
        return original_read(*args, **kwargs)
    monkeypatch.setattr(live_context, "tennis_observations_as_of", checked_read)
    result, rows = run_batch(db, predictions)
    assert result["stored"] == 1 and not result["errors"] and len(rows) == 1
    sidecar = json.loads(rows[0]["context_json"])["context_model"]
    key, packet = context_rows(db)[0]
    assert sidecar["reference"]["key"] == key
    assert sidecar["cutoff"] == packet["base"]["cutoff"] == canonical_timestamp(NOW)
    assert sidecar["event"] == packet["event"]
    assert sidecar["markets"] == {"A": "winner_a", "B": "winner_b"}
    assert packet["base"]["model_hash"] == states["ATP"]
    assert packet["base"]["params"]["p_a"] != rows[0]["p_cal"]
    assert round(packet["base"]["params"]["p_a"], 4) == rows[0]["p_cal"]
    assert packet["result"]["role"] == "not_applied"
    assert packet["result"]["used_markets"] == packet["base"]["markets"]
    assert packet["approval"] is None and packet["base"]["history_refs"] == []
    assert packet["base"]["reference_weights"]["native_state_identity"] == "unresolved"
    assert packet["event"]["surface"] is None and packet["event"]["indoor"] is None
    with sqlite3.connect(db) as conn:
        kind, data, created = conn.execute("SELECT kind,payload,created_at FROM artifacts WHERE digest=?",
            (sidecar["original_artifact_hash"],)).fetchone()
    assert kind == "tennis-live-winner-original-v1" and canonical_timestamp(created) > sidecar["cutoff"]
    assert json.loads(data)["origin"] == packet["base"]["reference_weights"]
    assert len(calls) == 2


def test_atp_wta_native_namespaces_and_actual_loaded_states_are_separate(monkeypatch, tmp_path):
    db, predictions, states, _ = configure(monkeypatch, tmp_path, tours=("ATP", "WTA"))
    result, rows = run_batch(db, predictions)
    assert not result["errors"] and result["stored"] == 2
    packets = [p for _, p in context_rows(db)]
    assert {p["event"]["event_key"] for p in packets} == {"espn:tennis:ATP:match:201", "espn:tennis:WTA:match:202"}
    assert {p["base"]["model_hash"] for p in packets} == set(states.values())
    assert len(rows) == 2


def test_legacy_shadow_id_cannot_absorb_context_from_a_different_tour(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path, tours=("ATP", "WTA"), same_id=True)
    with pytest.raises(ContextContractError, match="different tour"):
        run_batch(db, predictions)
    rows = shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))
    assert len(rows) == 1 and rows[0]["tour"] == "ATP"
    assert json.loads(rows[0]["context_json"])["context_model"]["event"]["tour"] == "ATP"


@pytest.mark.parametrize("bad", [True, None, "alias", "01"])
def test_unqualified_native_current_identity_keeps_ordinary_forecast_without_fake_link(monkeypatch, tmp_path, bad):
    comp = competition()
    comp["competitors"][0]["id"] = bad
    db, predictions, _, _ = configure(monkeypatch, tmp_path, comp=comp)
    result, rows = run_batch(db, predictions)
    assert result["stored"] == 1 and not result["errors"]
    assert "context_model" not in json.loads(rows[0]["context_json"])
    assert context_rows(db) == []


def test_before_capture_finish_is_rejected_without_loading_or_publishing_context(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    def before(batch, fixtures, result):
        with pytest.raises(ContextContractError, match="capture"):
            batch.finish()
    run_batch(db, predictions, before_finish=before)


def test_source_after_original_decision_cannot_be_backdated(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    with pytest.raises(ContextContractError):
        run_batch(db, predictions, decision=NOW-timedelta(minutes=1))
    assert context_rows(db) == []
    assert not predictions.exists()


def test_daily_main_reaches_actual_postcapture_snapshot_and_shadow_store(monkeypatch, tmp_path):
    db, predictions, _, calls = configure(monkeypatch, tmp_path)
    monkeypatch.setattr(daily, "auto_settle_completed", lambda: 0)
    monkeypatch.setattr(daily, "tournament_surface_map", lambda *a: {})
    monkeypatch.setattr(daily, "fetch_fixtures", daily.fetch_fixtures_espn)
    monkeypatch.setattr(daily.sys, "argv", ["tennis_daily.py", "2026-09-09"])
    monkeypatch.setattr(shadow, "_prediction_append_time", lambda value: ((NOW+timedelta(seconds=2)).timestamp(), (NOW+timedelta(seconds=2)).isoformat()))
    assert daily.main() == 0
    assert len(context_rows(db)) == 1 and len(calls) == 2
    rows = shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))
    assert "context_model" in json.loads(rows[0]["context_json"])


def test_empty_main_batch_does_not_create_any_runtime_store(monkeypatch, tmp_path):
    import runtime_paths
    from tennis.live_context import live_worker
    target = tmp_path/"unused.db"
    monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", target)
    with live_worker() as batch:
        batch.finish()
    assert not target.exists()


def test_pending_refresh_uses_real_stored_native_origin_and_new_ref_without_network(monkeypatch, tmp_path):
    from tennis import live_context
    db, predictions, _, calls = configure(monkeypatch, tmp_path)
    _, old = run_batch(db, predictions)
    old_link = json.loads(old[0]["context_json"])["context_model"]
    later = NOW+timedelta(hours=2)
    monkeypatch.setattr(daily.requests, "get", lambda *a, **k: pytest.fail("pending refresh fetched"))
    monkeypatch.setattr(live_context, "_now", lambda: later+timedelta(seconds=1))
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=later,
        append_observed_at=later+timedelta(seconds=2))
    assert result["refreshed"] == 1 and not result["errors"] and not result["provider_checked"]
    new = shadow.latest_predictions(predictions, as_of=later+timedelta(seconds=3))[0]
    link = json.loads(new["context_json"])["context_model"]
    assert link["reference"] != old_link["reference"]
    assert link["event"] == old_link["event"] and link["cutoff"] == canonical_timestamp(later)
    packets = dict(context_rows(db))
    assert packets[link["reference"]["key"]]["base"]["reference_weights"]["native_observed_at"] == canonical_timestamp(NOW-timedelta(seconds=10))
    historical = shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))[0]
    assert json.loads(historical["context_json"])["context_model"] == old_link
    assert len(calls) == 2


@pytest.mark.parametrize("correction", ["started", "different_players", "rescheduled", "broken_players", "unsupported"])
def test_pending_refresh_cannot_reuse_retracted_native_fixture(monkeypatch, tmp_path, correction):
    from context_observations import append_observation
    from context_sources.tennis_status import normalize_tennis_status
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, old = run_batch(db, predictions)
    native = competition()
    if correction == "started":
        native["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS")
    elif correction == "different_players": native["competitors"][0]["id"] = "9"
    elif correction == "rescheduled": native["date"] = "2026-09-09T18:00Z"
    elif correction == "broken_players": native["competitors"][0]["id"] = None
    else: native["status"]["type"].update(state="post", name="STATUS_ABANDONED", completed=True)
    received = NOW+timedelta(minutes=10)
    for row in normalize_tennis_status("ATP", "189-2026", native, grouping_slug="mens-singles", observed_at=received):
        append_observation(db, row, observed_at=received)
    monkeypatch.setattr(daily.requests, "get", lambda *a, **k: pytest.fail("refresh fetched"))
    monkeypatch.setattr(live_context, "_now", lambda: NOW+timedelta(hours=2, seconds=1))
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=NOW+timedelta(hours=2),
        append_observed_at=NOW+timedelta(hours=2, seconds=2))
    assert result["refreshed"] == 0 and result["errors"]
    after = shadow.latest_predictions(predictions, as_of=NOW+timedelta(hours=2, seconds=3))[0]
    assert after["model_revision_id"] == old[0]["model_revision_id"]
    assert len(context_rows(db)) == 1
