"""Actual POINT producer/immutable source roundtrip, entirely offline."""
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
import json
import sqlite3

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp
from context_models.tennis_point_original import (
    POINT_ORIGINAL_KIND, market_projection, point_scores_as_of, read_point_score, validate_point_capture,
)
from model_artifacts import canonical_bytes, put_artifact, publish_slots, load_manifest
from tennis import shadow
from tennis.model_state import ModelState
from tennis.elo import SurfaceElo
from tennis.serve_model import ServeReturnModel
from tennis.state_codec import encode_state
from tennis.simulator import POINT_MODEL_VERSION
from tennis.predict import predict_match
from test_tennis_live_worker import NOW, configure, run_batch, competition, response
from test_tennis_live_legacy_parity import exact_structure
from test_context_tennis_outcome_capture import completed, RECEIVED


def point_state(*, tour="ATP"):
    elo, serve = SurfaceElo(), ServeReturnModel()
    for _ in range(25):
        elo.update("alpha a", "beta b", "Hard")
        serve.update_from_match_row({"winner_key": "alpha a", "loser_key": "beta b", "surface": "Hard",
            "win_service_games_played": 10, "win_return_games_played": 10,
            "los_service_games_played": 10, "los_return_games_played": 10,
            "win_break_points_converted": 3, "los_break_points_converted": 1,
            "win_break_points_saved": 2})
    return ModelState(elo, serve if tour == "ATP" else ServeReturnModel(), 1.0173, .00182, 800,
        (NOW-timedelta(hours=2)).timestamp(), "2026-09-08", .3 if tour == "ATP" else 0.,
        tour_scope=tour, training_cutoff=(NOW-timedelta(hours=3)).isoformat(),
        stats_through_kind="tournament_start_proxy" if tour == "ATP" else "result_date",
        market_model_version=POINT_MODEL_VERSION)


def publish_point_state(db, *, tour="ATP", coefficient=None):
    state = point_state(tour=tour)
    ref = put_artifact(db, kind="tennis-tour-state", payload={"schema": 1,
        "training_cutoff": state.training_cutoff, "state": encode_state(state, tour=tour)},
        created_at=NOW-timedelta(hours=1))
    current, _ = load_manifest(db)
    publish_slots(db, {"tennis:"+tour: ref}, expected_manifest=current, published_at=NOW-timedelta(minutes=50))
    return ref


def setup_point(monkeypatch, tmp_path, **options):
    monkeypatch.setattr("test_tennis_live_worker.publish_state", publish_point_state)
    return configure(monkeypatch, tmp_path, **options)


def originals(db):
    with sqlite3.connect(db) as connection:
        return [(ref, json.loads(payload)) for ref, payload in connection.execute(
            "SELECT digest,payload FROM artifacts WHERE kind=? ORDER BY digest", (POINT_ORIGINAL_KIND,))]


@pytest.mark.parametrize("scope", [["espn:tennis:ATP:match:123"], {"espn:tennis:ATP:match:0123"},
    {"espn:tennis:ATP:match:0"}, {"espn:tennis:ATP:player:2"}, {str(n) for n in range(501)}])
def test_point_collection_requires_bounded_explicit_native_events(tmp_path, scope):
    with pytest.raises(ContextContractError, match="native event scopes"):
        point_scores_as_of(tmp_path / "absent.db", as_of=NOW, event_keys=scope)


@pytest.mark.parametrize("budget", ["count", "bytes", "oversized"])
def test_point_batch_admission_precedes_original_body_decode(monkeypatch, tmp_path, budget):
    import context_models.tennis_point_original as point
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    ref, payload = originals(db)[0]
    if budget == "count": monkeypatch.setattr(point, "MAX_ADMITTED_ORIGINALS", 0)
    elif budget == "bytes": monkeypatch.setattr(point, "MAX_ADMITTED_BYTES", 1)
    else:
        with sqlite3.connect(db) as connection:
            connection.execute("UPDATE artifacts SET payload=? WHERE digest=?",
                (b" "*(point.MAX_PUBLICATION_BYTES+1), ref))
    monkeypatch.setattr(point, "_native_score", lambda *a, **kw: pytest.fail("unadmitted body decoded"))
    with pytest.raises(ContextContractError, match="admission"):
        point_scores_as_of(db, as_of=NOW+timedelta(seconds=3), event_keys={payload["event_key"]})


def test_point_collection_does_not_expand_other_event_originals(monkeypatch, tmp_path):
    import context_models.tennis_point_original as point
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    ref, payload = originals(db)[0]
    # Valid physical metadata for a different native event; its deliberately
    # incomplete body cannot be expanded by this received-event batch.
    put_artifact(db, kind=POINT_ORIGINAL_KIND, payload={"schema": 1, "event_key": "espn:tennis:ATP:match:999",
        "winner_original_hash": "f"*64, "capture": {}}, created_at=NOW)
    selected = []
    monkeypatch.setattr(point, "_native_score", lambda con, key, **kw: selected.append(key))
    assert point_scores_as_of(db, as_of=NOW+timedelta(seconds=3), event_keys={payload["event_key"]}) == ()
    assert selected == [ref]


def test_point_final_rejects_oversized_native_winner_before_body_decode(monkeypatch, tmp_path):
    from context_sources.tennis_capture import capture_tennis_worker
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    ref = originals(db)[0][0]
    with capture_tennis_worker(path=db) as observer:
        observer.record("atp", response(completed()), observed_at=RECEIVED)
    with sqlite3.connect(db) as connection:
        content = connection.execute("SELECT content_digest FROM context_observations WHERE kind='match_outcome'").fetchone()[0]
        connection.execute("UPDATE context_contents SET payload=? WHERE content_digest=?", (b" "*(64*1024+1), content))
    with pytest.raises(ContextIntegrityError, match="native winner admission"):
        read_point_score(db, ref, as_of=RECEIVED)


@pytest.mark.parametrize("crosses_start", [False, True])
def test_point_publication_samples_actual_clock_after_heavy_preparation(monkeypatch, tmp_path, crosses_start):
    import context_models.tennis_point_original as point
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    actual = [NOW+timedelta(seconds=1)]
    monkeypatch.setattr("tennis.live_context._now", lambda: actual[0])
    publish, validate = point.publish_point_original, point.validate_point_capture
    def delayed_publish(*args, **kwargs):
        def validate_then_advance(value):
            result = validate(value)
            actual[0] = NOW+(timedelta(hours=6) if crosses_start else timedelta(seconds=2))
            return result
        with monkeypatch.context() as scoped:
            scoped.setattr(point, "validate_point_capture", validate_then_advance)
            return publish(*args, **kwargs)
    monkeypatch.setattr(point, "publish_point_original", delayed_publish)
    append = NOW+timedelta(hours=6, seconds=2) if crosses_start else NOW+timedelta(seconds=3)
    result, rows = run_batch(db, predictions, append_observed_at=append)
    with sqlite3.connect(db) as connection:
        owner = connection.execute("SELECT created_at FROM artifacts WHERE kind='tennis-live-winner-original-v1'").fetchone()[0]
        points = connection.execute("SELECT created_at FROM artifacts WHERE kind=?", (POINT_ORIGINAL_KIND,)).fetchall()
    assert canonical_timestamp(owner) == canonical_timestamp(NOW+timedelta(seconds=1))
    if crosses_start:
        assert points == [] and result["stored"] == 0 and result["skipped"] == 1 and rows == []
    else:
        assert [(canonical_timestamp(row[0]),) for row in points] == [(canonical_timestamp(actual[0]),)]
        assert result["stored"] == 1 and len(rows) == 1


@pytest.mark.parametrize("best_of", [3, 5])
def test_optional_capture_is_exact_actual_joint_law_without_changing_prediction(best_of):
    state = point_state()
    old, point = [], []
    expected = predict_match(state, "Alpha A", "Beta B", "Hard", best_of, as_of=NOW, original_capture=old.append)
    same = []
    actual = predict_match(state, "Alpha A", "Beta B", "Hard", best_of, as_of=NOW,
        original_capture=same.append, point_original_capture=point.append)
    assert canonical_bytes(exact_structure(asdict(actual))) == canonical_bytes(exact_structure(asdict(expected)))
    assert same == old and len(point) == 1
    assert validate_point_capture(point[0]) == point[0]
    assert point[0]["markets"] == market_projection(actual.markets)
    assert point[0]["params"]["winner_anchor"] == actual.p_a_cal


@pytest.mark.parametrize("mode", ["legacy", "no_serve"])
def test_no_fake_point_original_without_actual_point_simulation(mode):
    from tennis.simulator import LEGACY_MODEL_VERSION
    state = point_state()
    if mode == "legacy": state.market_model_version = LEGACY_MODEL_VERSION
    else: state.serve = ServeReturnModel()
    captures = []
    predict_match(state, "Alpha A", "Beta B", "Hard", as_of=NOW, point_original_capture=captures.append)
    assert captures == []


@pytest.mark.parametrize("reversed_source", [False, True])
def test_actual_daily_capture_and_native_final_score_roundtrip(monkeypatch, tmp_path, reversed_source):
    from context_sources.tennis_capture import capture_tennis_worker
    from tennis.live_context import live_worker
    db, predictions, _, calls = setup_point(monkeypatch, tmp_path)
    result, rows = run_batch(db, predictions)
    assert result["stored"] == 1 and not result["errors"] and len(rows) == 1
    ref, payload = originals(db)[0]
    context = json.loads(rows[0]["context_json"])
    assert payload["winner_original_hash"] == context["context_model"]["original_artifact_hash"]
    assert "point_original" not in context  # No technical artifact prose in customer output.
    before = predictions.read_bytes()
    assert read_point_score(db, ref, as_of=NOW+timedelta(seconds=3)) is None
    raw = completed(winner=1)
    if reversed_source: raw["competitors"].reverse()
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("final binding fetched"))
    monkeypatch.setattr("tennis.live_context._now", lambda: RECEIVED+timedelta(seconds=1))
    with live_worker(path=db) as batch:
        with capture_tennis_worker(path=db) as observer:
            batch.attach_capture(observer)
            observer.record("atp", response(raw), observed_at=RECEIVED)
        batch.finish()
    score = read_point_score(db, ref, as_of=RECEIVED+timedelta(seconds=2))
    assert batch.point_outcomes == (score,)
    assert score["result"] == {"winner_id": "espn:tennis:ATP:player:2",
        "set_scores": [{"home": 2, "away": 6}, {"home": 4, "away": 6}]}
    assert score["native_best_of"] is None and score["model_best_of"] == 3
    assert score["observed_at"] == canonical_timestamp(RECEIVED)
    assert len(score["workload_receipts"]) == 2 and predictions.read_bytes() == before and len(calls) == 2
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE kind IN ('context-effect-v1','context-approval-v1')").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM context_observations WHERE kind='match_outcome'").fetchone()[0] == 1


def test_refresh_owning_daily_callsite_captures_new_original_and_keeps_old_bytes(monkeypatch, tmp_path):
    from scripts import tennis_daily as daily
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    before = originals(db)
    later = NOW+timedelta(hours=2)
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("refresh fetched"))
    monkeypatch.setattr("tennis.live_context._now", lambda: later+timedelta(seconds=1))
    result = daily.refresh_pending_predictions(db_path=predictions, as_of=later, append_observed_at=later+timedelta(seconds=2))
    assert result["refreshed"] == 1 and not result["errors"]
    after = originals(db)
    assert len(after) == 2 and all(item in after for item in before)


@pytest.mark.parametrize("correction", ["scheduled", "participant", "partial", "retired", "walkover", "score_after_end"])
def test_latest_native_correction_never_reuses_old_convenient_score(monkeypatch, tmp_path, correction):
    from context_sources.tennis_capture import capture_tennis_worker
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    ref = originals(db)[0][0]
    with capture_tennis_worker(path=db) as observer:
        observer.record("atp", response(completed()), observed_at=RECEIVED)
    assert read_point_score(db, ref, as_of=RECEIVED) is not None
    raw = competition() if correction == "scheduled" else completed()
    if correction == "participant": raw["competitors"][1]["id"] = "3"
    elif correction == "partial": raw["competitors"][0]["linescores"][0]["winner"] = False
    elif correction in ("retired", "walkover"):
        raw["notes"] = [{"text": correction}]
    elif correction == "score_after_end":
        raw["competitors"][0]["linescores"].append({"value": 6, "winner": True})
        raw["competitors"][1]["linescores"].append({"value": 2, "winner": False})
    later = RECEIVED+timedelta(seconds=10)
    with capture_tennis_worker(path=db) as observer:
        observer.record("atp", response(raw), observed_at=later)
    assert read_point_score(db, ref, as_of=later) is None
    assert read_point_score(db, ref, as_of=RECEIVED) is not None


def test_capture_rejects_tampered_mass_before_publication():
    captures = []
    predict_match(point_state(), "Alpha A", "Beta B", "Hard", as_of=NOW, point_original_capture=captures.append)
    altered = deepcopy(captures[0])
    altered["markets"]["games_total"][0][1] += .001
    with pytest.raises(ContextIntegrityError, match="joint law"):
        validate_point_capture(altered)


def test_missing_physical_pair_fails_integrity_not_silent_old_final(monkeypatch, tmp_path):
    from context_sources.tennis_capture import capture_tennis_worker
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    ref = originals(db)[0][0]
    with capture_tennis_worker(path=db) as observer:
        observer.record("atp", response(completed()), observed_at=RECEIVED)
    score = read_point_score(db, ref, as_of=RECEIVED)
    with sqlite3.connect(db) as connection:
        connection.execute("DELETE FROM context_observations WHERE digest=?", (score["workload_receipts"][0],))
    with pytest.raises(ContextIntegrityError, match="actual native workload pair"):
        read_point_score(db, ref, as_of=RECEIVED)


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_native_tour_is_bound_without_cross_tour_name_join(monkeypatch, tmp_path, tour):
    from context_sources.tennis_capture import capture_tennis_worker
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path, tours=(tour,))
    result, rows = run_batch(db, predictions)
    assert result["stored"] == 1 and not result["errors"] and len(rows) == 1
    if tour == "WTA":
        # The actual owning WTA state contract is Elo-only: never fabricate
        # POINT/serve parameters just to make its missing scores fit a family.
        assert originals(db) == []
        assert json.loads(rows[0]["context_json"])["context_model"]["event"]["tour"] == "WTA"
        return
    ref = originals(db)[0][0]
    event_id = "201" if tour == "ATP" else "202"
    with capture_tennis_worker(path=db) as observer:
        observer.record(tour.lower(), response(completed(event_id=event_id), tour), observed_at=RECEIVED)
    score = read_point_score(db, ref, as_of=RECEIVED)
    assert score["event"]["tour"] == tour
    assert score["result"]["winner_id"] == f"espn:tennis:{tour}:player:1"
    assert read_point_score(db, ref, as_of=RECEIVED-timedelta(microseconds=1)) is None


@pytest.mark.parametrize("flags", ["missing", "contradictory"])
def test_legal_scores_cannot_replace_missing_or_different_native_winner_flag(monkeypatch, tmp_path, flags):
    from context_sources.tennis_capture import capture_tennis_worker
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    ref = originals(db)[0][0]
    raw = completed()
    for item in raw["competitors"]:
        if flags == "missing": item.pop("winner")
        else: item["winner"] = not item["winner"]
    with capture_tennis_worker(path=db) as observer:
        observer.record("atp", response(raw), observed_at=RECEIVED)
    assert read_point_score(db, ref, as_of=RECEIVED) is None


def test_simultaneous_native_final_conflict_is_not_selected_by_digest_order(monkeypatch, tmp_path):
    from context_sources.tennis_capture import capture_tennis_worker
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    ref = originals(db)[0][0]
    altered = completed()
    altered["competitors"][1]["linescores"][0]["value"] = 3
    with capture_tennis_worker(path=db) as observer:
        observer.record("atp", response(completed()), observed_at=RECEIVED)
        observer.record("atp", response(altered), observed_at=RECEIVED)
    assert read_point_score(db, ref, as_of=RECEIVED) is None


def test_rehashed_point_capture_with_fake_holds_cannot_replay_from_original_state(monkeypatch, tmp_path):
    from context_models.tennis_point_original import point_capture
    from tennis.simulator import simulate_match
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    run_batch(db, predictions)
    _, payload = originals(db)[0]
    p = payload["capture"]["params"]
    altered = deepcopy(payload)
    false_hold = p["hold_a"]-.05
    sheet = simulate_match(false_hold, p["hold_b"], p["best_of"], strict=True,
        model_version=POINT_MODEL_VERSION, winner_probability=p["winner_anchor"])
    altered["capture"] = point_capture(false_hold, p["hold_b"], p["best_of"], p["winner_anchor"], sheet)
    ref = put_artifact(db, kind=POINT_ORIGINAL_KIND, payload=altered, created_at=NOW+timedelta(seconds=1))
    with pytest.raises(ContextIntegrityError, match="immutable state"):
        read_point_score(db, ref, as_of=RECEIVED)


def test_slow_late_worker_cannot_claim_new_point_prematch_publication(monkeypatch, tmp_path):
    db, predictions, _, _ = setup_point(monkeypatch, tmp_path)
    monkeypatch.setattr("tennis.live_context._now", lambda: NOW+timedelta(hours=6))
    result, rows = run_batch(db, predictions, append_observed_at=NOW+timedelta(hours=6, seconds=2))
    assert result["stored"] == 0 and result["skipped"] == 1 and not result["errors"] and rows == []
    assert originals(db) == []
