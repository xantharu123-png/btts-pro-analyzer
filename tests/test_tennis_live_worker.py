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


def run_batch(db, predictions, *, decision=NOW, before_finish=None, feature_version="tennis-performed-load-v4"):
    from context_sources.tennis_capture import capture_tennis_worker
    from tennis.live_context import live_worker
    with live_worker(path=db, feature_version=feature_version) as batch:
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


def test_two_tour_batch_uses_one_shared_physical_history_image(monkeypatch, tmp_path):
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path, tours=("ATP", "WTA"))
    calls = []
    actual = live_context.tennis_histories_as_of
    def shared(path, *, cutoff, tours):
        calls.append((path, cutoff, tours))
        return actual(path, cutoff=cutoff, tours=tours)
    monkeypatch.setattr(live_context, "tennis_histories_as_of", shared)
    def separate(*args, **kwargs):
        pytest.fail("two-tour batch must not reread the same complete physical inventory")
    monkeypatch.setattr(live_context, "tennis_observations_as_of", separate)
    result, rows = run_batch(db, predictions)
    assert result["stored"] == 2 and not result["errors"] and len(rows) == 2
    assert calls == [(db, NOW, ("ATP", "WTA"))]


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


def test_pending_refresh_reads_whole_history_once_at_publication(monkeypatch, tmp_path):
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    run_batch(db, predictions)
    original = live_context.tennis_observations_as_of
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(live_context, "tennis_observations_as_of", counted)
    later = NOW+timedelta(hours=2)
    monkeypatch.setattr(live_context, "_now", lambda: later+timedelta(seconds=1))
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=later,
        append_observed_at=later+timedelta(seconds=2))
    assert result["refreshed"] == 1 and not result["errors"]
    assert calls == [1]


@pytest.mark.parametrize("change", ["foreign_corruption", "schedule_after_bind", "players_after_bind"])
def test_event_preflight_never_replaces_full_final_history_check(monkeypatch, tmp_path, change):
    from context_observations import append_observation
    from context_sources.tennis_status import normalize_tennis_status
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, old = run_batch(db, predictions)
    later = NOW+timedelta(hours=2)
    predict = daily.predict_match
    def changed(*args, **kwargs):
        native = competition(id="999") if change == "foreign_corruption" else competition()
        if change == "schedule_after_bind": native["date"] = "2026-09-09T18:00Z"
        if change == "players_after_bind": native["competitors"][0]["id"] = "9"
        received = later-timedelta(seconds=1)
        for obs in normalize_tennis_status("ATP", "189-2026", native, grouping_slug="mens-singles", observed_at=received):
            append_observation(db, obs, observed_at=received)
        if change == "foreign_corruption":
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE context_observations SET subject_id='forged' WHERE event_key=?", ("espn:tennis:ATP:match:999",))
        return predict(*args, **kwargs)
    monkeypatch.setattr(daily, "predict_match", changed)
    monkeypatch.setattr(live_context, "_now", lambda: later+timedelta(seconds=1))
    with pytest.raises(ContextContractError):
        daily.refresh_pending_predictions(db_path=predictions, as_of=later,
            append_observed_at=later+timedelta(seconds=2))
    current = shadow.latest_predictions(predictions, as_of=later+timedelta(seconds=3))[0]
    assert current["model_revision_id"] == old[0]["model_revision_id"]
    assert len(context_rows(db)) == 1


@pytest.mark.parametrize("correction", ["started", "different_players", "broken_players", "unsupported"])
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
    elif correction == "broken_players": native["competitors"][0]["id"] = None
    else: native["status"]["type"].update(state="post", name="STATUS_ABANDONED", completed=True)
    received = NOW+timedelta(minutes=10)
    for row in normalize_tennis_status("ATP", "189-2026", native, grouping_slug="mens-singles", observed_at=received):
        append_observation(db, row, observed_at=received)
    monkeypatch.setattr(daily.requests, "get", lambda *a, **k: pytest.fail("refresh fetched"))
    monkeypatch.setattr(live_context, "_now", lambda: NOW+timedelta(hours=2, seconds=1))
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=NOW+timedelta(hours=2),
        append_observed_at=NOW+timedelta(hours=2, seconds=2))
    assert result["refreshed"] == 0
    if correction == "unsupported":
        assert result["errors"] and not result["native_unavailable"]
    else:
        assert not result["errors"] and result["status"] == "partial"
        assert len(result["native_unavailable"]) == 1
        assert result["native_unavailable"][0]["prediction_id"] == old[0]["id"]
    after = shadow.latest_predictions(predictions, as_of=NOW+timedelta(hours=2, seconds=3))[0]
    assert after["model_revision_id"] == old[0]["model_revision_id"]
    assert len(context_rows(db)) == 1


@pytest.mark.parametrize("new_start", ["2026-09-09T18:00Z", "2026-09-10T23:30Z", "2026-09-09T16:00Z", "2026-09-09T13:00Z"])
def test_pending_refresh_appends_confirmed_schedule_revision_without_rewriting_origin(monkeypatch, tmp_path, new_start):
    from context_observations import append_observation
    from context_sources.tennis_status import normalize_tennis_status
    from tennis import live_context
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    _, old = run_batch(db, predictions)
    with sqlite3.connect(predictions) as conn:
        old_revisions = conn.execute("SELECT * FROM prediction_revisions ORDER BY revision_id").fetchall()
    received = NOW+timedelta(minutes=10)
    native = competition(date=new_start)
    for row in normalize_tennis_status("ATP", "189-2026", native, grouping_slug="mens-singles", observed_at=received):
        append_observation(db, row, observed_at=received)
    later = NOW+timedelta(hours=2)
    monkeypatch.setattr(daily.requests, "get", lambda *a, **k: pytest.fail("refresh fetched"))
    monkeypatch.setattr(live_context, "_now", lambda: later+timedelta(seconds=1))
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=later,
        append_observed_at=later+timedelta(seconds=2))
    if canonical_timestamp(new_start) <= canonical_timestamp(later):
        assert result["refreshed"] == 0 and result["skipped"] == 1 and not result["errors"]
        latest = shadow.latest_predictions(predictions, as_of=later+timedelta(seconds=3))[0]
        assert latest["model_revision_id"] == old[0]["model_revision_id"]
        return
    assert result["refreshed"] == 1 and not result["errors"]
    latest = shadow.latest_predictions(predictions, as_of=later+timedelta(seconds=3))[0]
    assert canonical_timestamp(latest["scheduled_start_utc"]) == canonical_timestamp(new_start)
    assert latest["match_date"] == datetime.fromisoformat(new_start.replace("Z", "+00:00")).astimezone(daily.ZURICH_TZ).date().isoformat()
    old_link = json.loads(old[0]["context_json"])["context_model"]
    new_link = json.loads(latest["context_json"])["context_model"]
    assert new_link["event"]["scheduled_start"] == canonical_timestamp(new_start)
    assert new_link["event"]["schedule_revision"] != old_link["event"]["schedule_revision"]
    assert new_link["reference"] != old_link["reference"]
    with sqlite3.connect(predictions) as conn:
        after = conn.execute("SELECT * FROM prediction_revisions ORDER BY revision_id").fetchall()
    assert all(row in after for row in old_revisions) and len(after) == len(old_revisions)+1
    historical = shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3))[0]
    assert historical["model_revision_id"] == old[0]["model_revision_id"]
    assert json.loads(historical["context_json"])["context_model"] == old_link
