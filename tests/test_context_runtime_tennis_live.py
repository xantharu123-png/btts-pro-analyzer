"""Real live originals in a sealed D4 image, never new empirical approval."""
from contextlib import closing
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import canonical_timestamp, digest
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, original_base
from context_models.tennis_v3 import tennis_reference_hash_v3
from context_observations import append_observation
from context_runtime import verify_context_database
from context_snapshots import _payload_digest
from context_sources.tennis_status import normalize_tennis_status
from context_transport import calculate_context_payload, context_payload_key, project_context_market
from model_artifacts import ArtifactIntegrityError, canonical_bytes
from test_tennis_live_worker import NOW, competition, configure, context_rows, run_batch


def _stored(monkeypatch, tmp_path, *, tours=("ATP",)):
    db, predictions, _, _ = configure(monkeypatch, tmp_path, tours=tours)
    _, rows = run_batch(db, predictions)
    return db, rows


def _replace_snapshot(db, old_key, payload):
    key = context_payload_key(payload)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DELETE FROM context_snapshots WHERE key=?", (old_key,))
        conn.execute("INSERT INTO context_snapshots VALUES(?,?,?)", (
            key, canonical_bytes(payload), _payload_digest(key, payload)))
    return key


def _replace_origin(db, change, *, keep_snapshot=True):
    """Rehash all public identities; failure must be the owning semantic check."""
    key, payload = context_rows(db)[0]
    old_origin = payload["base"]["reference_weights"]
    origin = deepcopy(old_origin)
    change(origin)
    old_hash = digest({"kind": ORIGINAL_ARTIFACT_KIND,
                       "payload": {"schema": 1, "origin": old_origin}})
    publication = {"schema": 1, "origin": origin}
    new_hash = digest({"kind": ORIGINAL_ARTIFACT_KIND, "payload": publication})
    with closing(sqlite3.connect(db)) as conn, conn:
        created = conn.execute("SELECT created_at FROM artifacts WHERE digest=?", (old_hash,)).fetchone()[0]
        conn.execute("DELETE FROM artifacts WHERE digest=?", (old_hash,))
        conn.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (
            new_hash, ORIGINAL_ARTIFACT_KIND, canonical_bytes(publication), created))
        if not keep_snapshot:
            conn.execute("DELETE FROM context_snapshots")
    if keep_snapshot:
        payload["base"] = original_base(origin)
        payload["event"] = origin["event"]
        payload["features"]["event_key"] = origin["event"]["event_key"]
        payload["features"]["cutoff"] = origin["cutoff"]
        payload["features"]["reference_hash"] = tennis_reference_hash_v3(payload["base"], payload["event"])
        args = {name: payload[name] for name in (
            "event", "base", "features", "observation_refs", "preprocessing_refs",
            "effect_artifact", "effect_hash", "approval")}
        _replace_snapshot(db, key, calculate_context_payload(**args))
    return new_hash


@pytest.mark.parametrize("tours", [("ATP",), ("WTA",), ("ATP", "WTA")])
def test_actual_tour_origins_are_known_but_native_history_is_not_certified(monkeypatch, tmp_path, tours):
    db, rows = _stored(monkeypatch, tmp_path, tours=tours)
    before = db.read_bytes()
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **k: pytest.fail("D4 fetched"))
    monkeypatch.setattr("requests.get", lambda *a, **k: pytest.fail("D4 fetched"))
    report = verify_context_database(db)
    assert "unrecognized-artifact-schema" not in report["limitations"]
    assert "d1-original-replay-context-unavailable" in report["limitations"]
    assert report["empirical_approval_verified"] is False
    assert report["verification_level"] == "transport_only"
    assert report["counts"]["snapshots"] == len(tours) == len(rows)
    assert db.read_bytes() == before


@pytest.mark.parametrize("change", ["probability", "raw_probability", "state_key", "state_missing",
    "receipt_missing", "receipt_clock", "competition_revision", "code_identity", "different_players",
    "different_event", "different_schedule"])
@pytest.mark.parametrize("keep_snapshot", [False, True])
def test_rehashed_original_must_match_actual_model_and_native_input(monkeypatch, tmp_path, change, keep_snapshot):
    db, _ = _stored(monkeypatch, tmp_path)
    def alter(origin):
        if change == "probability":
            origin["values"].update(p_a_cal=.777, p_b_cal=1-.777)
        elif change == "raw_probability": origin["values"]["p_a_raw"] = .613
        elif change == "state_key": origin["inputs"]["state_key_a"] = "unknown key"
        elif change == "state_missing": origin["state_hash"] = "0" * 64
        elif change == "receipt_missing": origin["native_receipt"] = "0" * 64
        elif change == "receipt_clock": origin["native_observed_at"] = canonical_timestamp(NOW-timedelta(minutes=2))
        elif change == "competition_revision": origin["competition_revision"] = "0" * 64
        elif change == "code_identity": origin["code_hashes"]["tennis/predict.py"] = "0" * 64
        elif change == "different_players": origin["event"]["home_id"] = "espn:tennis:ATP:player:9"
        elif change == "different_event":
            origin["event"]["event_key"] = "espn:tennis:ATP:match:999"
        else:
            origin["event"]["scheduled_start"] = canonical_timestamp(NOW+timedelta(hours=6))
        if change in {"different_event", "different_schedule"}:
            origin["event"]["schedule_revision"] = digest({"event_key": origin["event"]["event_key"],
                "scheduled_start": origin["event"]["scheduled_start"]})
    _replace_origin(db, alter, keep_snapshot=keep_snapshot)
    before = db.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(db)
    assert db.read_bytes() == before


@pytest.mark.parametrize("later_than_cutoff", [False, True])
def test_entire_native_inventory_prevents_omission_of_a_predecision_retraction(monkeypatch, tmp_path, later_than_cutoff):
    db, _ = _stored(monkeypatch, tmp_path)
    native = competition()
    native["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS")
    received = NOW+timedelta(seconds=10) if later_than_cutoff else NOW-timedelta(seconds=5)
    for row in normalize_tennis_status("ATP", "189-2026", native,
            grouping_slug="mens-singles", observed_at=received):
        append_observation(db, row, observed_at=received)
    if later_than_cutoff:
        assert "unrecognized-artifact-schema" not in verify_context_database(db)["limitations"]
    else:
        with pytest.raises(ArtifactIntegrityError):
            verify_context_database(db)


@pytest.mark.parametrize("change", ["missing_original", "missing_observation", "made_up_feature"])
def test_actual_live_snapshot_binds_original_and_complete_feature_inventory(monkeypatch, tmp_path, change):
    db, _ = _stored(monkeypatch, tmp_path)
    key, payload = context_rows(db)[0]
    if change == "missing_original":
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("DELETE FROM artifacts WHERE kind=?", (ORIGINAL_ARTIFACT_KIND,))
    elif change == "missing_observation":
        payload["observation_refs"] = []
        _replace_snapshot(db, key, payload)
    else:
        name = next(iter(payload["features"]["values"]))
        payload["features"]["values"][name] = 19.
        payload["features"]["states"][name] = "available"
        payload["features"]["refs"][name] = payload["observation_refs"]
        args = {name: payload[name] for name in (
            "event", "base", "features", "observation_refs", "preprocessing_refs",
            "effect_artifact", "effect_hash", "approval")}
        _replace_snapshot(db, key, calculate_context_payload(**args))
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(db)


@pytest.mark.parametrize("part", ["event", "distribution", "embedded_original"])
def test_read_only_projection_also_binds_exact_original_without_refitting(monkeypatch, tmp_path, part):
    from context_transport import _input_key
    db, rows = _stored(monkeypatch, tmp_path)
    _, payload = context_rows(db)[0]
    if part == "event":
        payload["event"]["home_id"] = "espn:tennis:ATP:player:9"
    elif part == "distribution":
        payload["base"]["params"]["p_a"] = .9
        payload["base"]["markets"] = {"winner_a": .9, "winner_b": 1-.9}
        for prefix in ("base", "used"):
            payload["result"][prefix+"_params"] = deepcopy(payload["base"]["params"])
            payload["result"][prefix+"_markets"] = deepcopy(payload["base"]["markets"])
    else:
        payload["base"]["reference_weights"]["values"].update(p_a_cal=.8, p_b_cal=1-.8)
    payload["result"]["base_hash"] = digest(payload["base"])
    # Preserve the old reference as the original and rehash every public layer.
    payload["features"]["reference_hash"] = digest({"version": "tennis-context-reference-v3",
        "base_hash": digest(payload["base"]), "event_hash": digest(payload["event"])})
    key = _input_key(payload, payload["event"], payload["base"], payload["features"])
    reference = {"schema": 1, "kind": "context-consumer-reference-v1", "key": key,
                 "payload_digest": _payload_digest(key, payload)}
    monkeypatch.setattr("tennis.predict.predict_match", lambda *a, **k: pytest.fail("card recalculated"))
    from context_models.contracts import ContextContractError
    with pytest.raises(ContextContractError):
        project_context_market(payload, reference, "winner_a")


def test_lf_crlf_equivalent_source_bytes_do_not_invent_a_different_recipe(monkeypatch, tmp_path):
    db, _ = _stored(monkeypatch, tmp_path)
    def equivalent(origin):
        for name in origin["code_hashes"]:
            raw = (Path(__file__).resolve().parents[1]/name).read_bytes()
            lf = raw.replace(b"\r\n", b"\n")
            origin["code_hashes"][name] = hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest()
    _replace_origin(db, equivalent)
    assert "unrecognized-artifact-schema" not in verify_context_database(db)["limitations"]


@pytest.mark.parametrize("corrupt_feature", [False, True])
def test_actual_prior_bilateral_status_history_is_replayed_not_only_empty_features(monkeypatch, tmp_path, corrupt_feature):
    from test_context_tennis_capture import competition as completed, records, persist
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    for match, player, other, hours in (("101", "1", "9", 3), ("102", "2", "8", 2)):
        raw = completed(id=match)
        raw["competitors"][0]["id"], raw["competitors"][1]["id"] = player, other
        at = NOW-timedelta(hours=hours)
        persist(db, records(raw, clock=at), clock=at)
    run_batch(db, predictions)
    key, payload = context_rows(db)[0]
    assert len(payload["observation_refs"]) == 7
    name = "observed_recovery_minimum_hours_delta"
    assert payload["features"]["values"][name] == 1.
    assert payload["features"]["values"]["observed_recovery_exact_hours_delta"] is None
    assert payload["result"]["used_markets"] == payload["base"]["markets"]
    if corrupt_feature:
        payload["features"]["values"][name] = 2.
        args = {name: payload[name] for name in (
            "event", "base", "features", "observation_refs", "preprocessing_refs",
            "effect_artifact", "effect_hash", "approval")}
        _replace_snapshot(db, key, calculate_context_payload(**args))
        with pytest.raises(ArtifactIntegrityError):
            verify_context_database(db)
    else:
        report = verify_context_database(db)
        assert report["counts"]["observations"] == 7
        assert "unrecognized-artifact-schema" not in report["limitations"]


def test_real_read_only_projection_uses_exact_unrounded_baseline_without_model_or_source_call(monkeypatch, tmp_path):
    from context_consumers import load_context_market
    db, rows = _stored(monkeypatch, tmp_path)
    sidecar = json.loads(rows[0]["context_json"])["context_model"]
    payload = context_rows(db)[0][1]
    before = db.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail("reading a card recalculated or fetched a model")
    monkeypatch.setattr("tennis.predict.predict_match", forbidden)
    monkeypatch.setattr("requests.get", forbidden)
    monkeypatch.setattr("context_transport.calculate_context_payload", forbidden)
    monkeypatch.setattr("context_snapshots.compute_once", forbidden)
    projected = [load_context_market(db, sidecar["reference"], sidecar["markets"][side],
        expected_event=sidecar["event"], expected_cutoff=sidecar["cutoff"])["projection"] for side in ("A", "B")]
    assert all(row["context_ref"] == sidecar["reference"] for row in projected)
    assert [row["used_probability"] for row in projected] == [payload["base"]["markets"][m] for m in ("winner_a", "winner_b")]
    assert projected[0]["used_probability"] != rows[0]["p_cal"]
    assert projected[0]["used_probability"] + projected[1]["used_probability"] == 1.
    assert db.read_bytes() == before
