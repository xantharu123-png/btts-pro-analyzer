"""Closed owning POINT source/replay completion, real offline SQLite evidence."""
import sqlite3
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from context_runtime import verify_context_database
from context_models.contracts import ContextContractError, ContextIntegrityError
from model_artifacts import ArtifactIntegrityError, put_artifact
from test_context_runtime_tennis_live import _point_stored, _replace_origin
from test_tennis_live_worker import NOW


POINT_KIND = "tennis-point-joint-original-v1"
CAPTURE_PREDICT_HASHES = frozenset({
    "1bcfd397dabda9a0cf075894d2d3c1dc4a191fe9ce880652e050b6e3257dfebe",
    "5c730696f81b621ef02a461d32d91cddf118dbb40d65264c9699b4bff28a7a2d",
})


def capture_source_manifest(acquisition="cached"):
    from context_runtime_tennis import _REVIEWED_CACHED_TRAINING_MANIFEST, _REVIEWED_POINT_JOINT_MANIFEST
    base = (_REVIEWED_CACHED_TRAINING_MANIFEST if acquisition == "cached"
            else _REVIEWED_POINT_JOINT_MANIFEST)
    return {**base,
            "tennis/predict.py": CAPTURE_PREDICT_HASHES}


def test_actual_daily_call_publishes_its_point_original(monkeypatch, tmp_path):
    db, _ = _point_stored(monkeypatch, tmp_path)
    with sqlite3.connect(db) as connection:
        count = connection.execute("SELECT count(*) FROM artifacts WHERE kind=?", (POINT_KIND,)).fetchone()[0]
    assert count == 1


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
@pytest.mark.parametrize("acquisition", ["inherited", "cached"])
def test_inherited_capture_source_family_replays_actual_point_state(monkeypatch, tmp_path, tour, acquisition):
    db, _ = _point_stored(monkeypatch, tmp_path, tour=tour)
    # Diagnostic uses the exact reviewed inherited predict source and the
    # canonical cache-only loader family. No data-loader/training side effect.
    family = capture_source_manifest(acquisition)
    _replace_origin(db, lambda origin: origin.__setitem__("code_hashes", {
        name: sorted(hashes)[0] for name, hashes in family.items()}))
    monkeypatch.setattr("context_runtime_tennis._code_variants", lambda: family)
    before = db.read_bytes()
    report = verify_context_database(db)
    assert report["empirical_approval_verified"] is False
    assert "unrecognized-artifact-schema" not in report["limitations"]
    assert db.read_bytes() == before


def point_rows(db):
    with sqlite3.connect(db) as connection:
        return [(ref, json.loads(raw)) for ref, raw in connection.execute(
            "SELECT digest,payload FROM artifacts WHERE kind=?", (POINT_KIND,))]


def test_unknown_running_owner_cannot_certify_its_own_source_family():
    from context_runtime_tennis import _code_manifest_supported
    recorded = {name: sorted(hashes)[0] for name, hashes in capture_source_manifest().items()}
    recorded["tennis/elo.py"] = "0" * 64
    running = {name: frozenset({value}) for name, value in recorded.items()}
    assert not _code_manifest_supported(recorded, running)


@pytest.mark.parametrize("orphan", [False, True])
def test_d4_owns_point_original_even_without_a_snapshot(monkeypatch, tmp_path, orphan):
    from context_models.tennis_point_original import read_point_score
    db, _ = _point_stored(monkeypatch, tmp_path)
    ref, _ = point_rows(db)[0]
    if orphan:
        with sqlite3.connect(db) as connection:
            connection.execute("DELETE FROM context_snapshots")
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("POINT replay fetched"))
    before = db.read_bytes()
    report = verify_context_database(db)
    assert "unrecognized-artifact-schema" not in report["limitations"]
    assert not report["empirical_approval_verified"]
    assert read_point_score(db, ref, as_of=NOW+timedelta(seconds=3)) is None
    assert db.read_bytes() == before


@pytest.mark.parametrize("corruption", ["owner", "event", "capture", "too_early", "at_start"])
@pytest.mark.parametrize("orphan", [False, True])
def test_d4_rejects_self_hashed_corrupt_point_originals(monkeypatch, tmp_path, corruption, orphan):
    db, _ = _point_stored(monkeypatch, tmp_path)
    _, payload = point_rows(db)[0]
    altered = deepcopy(payload)
    created = NOW+timedelta(seconds=1)
    if corruption == "owner": altered["winner_original_hash"] = "0" * 64
    elif corruption == "event": altered["event_key"] = "espn:tennis:ATP:match:999"
    elif corruption == "capture": altered["capture"]["markets"]["games_total"][0][1] += .001
    elif corruption == "too_early": created = NOW
    else: created = NOW+timedelta(hours=5)
    ref = put_artifact(db, kind=POINT_KIND, payload=altered, created_at=created)
    if corruption in {"too_early", "at_start"}:
        with sqlite3.connect(db) as connection:
            connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?", (created.isoformat(), ref))
    if orphan:
        with sqlite3.connect(db) as connection:
            connection.execute("DELETE FROM context_snapshots")
    before = db.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(db)
    assert db.read_bytes() == before


def test_direct_point_reader_replays_full_winner_not_a_stored_scalar(monkeypatch, tmp_path):
    from context_models.tennis_point_original import read_point_score
    db, _ = _point_stored(monkeypatch, tmp_path)
    _replace_origin(db, lambda origin: origin["values"].__setitem__("p_a_raw", .123))
    ref, _ = point_rows(db)[0]
    before = db.read_bytes()
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        read_point_score(db, ref, as_of=NOW+timedelta(seconds=3))
    assert db.read_bytes() == before


@pytest.mark.parametrize("owner", ["tennis/predict.py", "tennis/model_state.py", "tennis/elo.py", "tennis/data_loader.py",
    "tennis/simulator.py", "tennis/serve_model.py"])
def test_direct_point_reader_binds_every_winner_source_owner(monkeypatch, tmp_path, owner):
    from context_models.tennis_point_original import read_point_score
    db, _ = _point_stored(monkeypatch, tmp_path)
    _replace_origin(db, lambda origin: origin["code_hashes"].__setitem__(owner, "0" * 64))
    ref, _ = point_rows(db)[0]
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        read_point_score(db, ref, as_of=NOW+timedelta(seconds=3))


def test_line_ending_equivalent_whole_family_replays_direct_point_reader(monkeypatch, tmp_path):
    from context_models.tennis_point_original import read_point_score
    db, _ = _point_stored(monkeypatch, tmp_path)
    _replace_origin(db, lambda origin: origin.__setitem__("code_hashes", {
        name: sorted(hashes)[0] for name, hashes in capture_source_manifest("inherited").items()}))
    ref, _ = point_rows(db)[0]
    assert read_point_score(db, ref, as_of=NOW+timedelta(seconds=3)) is None


@pytest.mark.parametrize("reader", ["point", "d4"])
def test_prior_winner_source_may_not_be_relabelled_as_point_capture(monkeypatch, tmp_path, reader):
    from context_runtime_tennis import _REVIEWED_CACHED_TRAINING_MANIFEST
    from context_models.tennis_point_original import read_point_score
    db, _ = _point_stored(monkeypatch, tmp_path)
    _replace_origin(db, lambda origin: origin.__setitem__("code_hashes", {
        name: sorted(hashes)[0] for name, hashes in _REVIEWED_CACHED_TRAINING_MANIFEST.items()}))
    ref, _ = point_rows(db)[0]
    before = db.read_bytes()
    if reader == "point":
        with pytest.raises(ContextIntegrityError, match="actual capture source family"):
            read_point_score(db, ref, as_of=NOW+timedelta(seconds=3))
    else:
        with pytest.raises(ArtifactIntegrityError) as caught:
            verify_context_database(db)
        assert "actual capture source family" in str(caught.value.__cause__)
    assert db.read_bytes() == before


def test_capture_cannot_be_synthesized_from_an_elo_only_wta_winner(monkeypatch, tmp_path):
    from context_models.dataset import _reader
    from context_models.tennis_point_original import read_point_score, point_capture
    from model_artifacts import _load_artifact
    from tennis.tour_state import _decode_wrapper
    from tennis.simulator import POINT_MODEL_VERSION, simulate_match
    db, _ = _point_stored(monkeypatch, tmp_path, tour="WTA")
    assert point_rows(db) == []
    with sqlite3.connect(db) as connection:
        winner, raw = connection.execute("SELECT digest,payload FROM artifacts WHERE kind=?",
            ("tennis-live-winner-original-v1",)).fetchone()
        origin = json.loads(raw)["origin"]
    with _reader(db) as connection:
        state = _decode_wrapper(_load_artifact(connection, origin["state_hash"])["payload"], "WTA")
    holds = state.serve.expected_hold_probabilities("alpha a", "beta b", "Hard", as_of=NOW)
    anchor = round(origin["values"]["p_a_cal"], 4)
    markets = simulate_match(*holds, best_of=3, model_version=POINT_MODEL_VERSION,
        winner_probability=anchor, strict=True)
    payload = {"schema": 1, "event_key": origin["event"]["event_key"], "winner_original_hash": winner,
        "capture": point_capture(*holds, 3, anchor, markets)}
    ref = put_artifact(db, kind=POINT_KIND, payload=payload, created_at=NOW+timedelta(seconds=1))
    with pytest.raises(ContextIntegrityError, match="actual full Winner/POINT calculation"):
        read_point_score(db, ref, as_of=NOW+timedelta(seconds=3))


def test_point_publisher_cannot_relabel_a_prior_winner_source(monkeypatch, tmp_path):
    from context_models.tennis_point_original import publish_point_original
    from context_runtime_tennis import _REVIEWED_CACHED_TRAINING_MANIFEST
    from model_artifacts import _load_artifact
    from context_models.dataset import _reader
    from tennis.tour_state import load_tour_state
    db, _ = _point_stored(monkeypatch, tmp_path)
    _replace_origin(db, lambda origin: origin.__setitem__("code_hashes", {
        name: sorted(hashes)[0] for name, hashes in _REVIEWED_CACHED_TRAINING_MANIFEST.items()}))
    _, payload = point_rows(db)[0]
    with _reader(db) as connection:
        origin = _load_artifact(connection, payload["winner_original_hash"])["payload"]["origin"]
    before = db.read_bytes()
    with pytest.raises(ContextIntegrityError, match="actual capture source family"):
        publish_point_original(db, winner_original_hash=payload["winner_original_hash"], origin=origin,
            capture=payload["capture"], state=load_tour_state("ATP", path=db),
            clock=lambda: NOW+timedelta(seconds=2))
    assert db.read_bytes() == before


def test_inactive_point_state_and_orphan_publication_remain_verified(monkeypatch, tmp_path):
    from test_tennis_live_worker import publish_state
    db, _ = _point_stored(monkeypatch, tmp_path)
    before_points = point_rows(db)
    new_active = publish_state(db, coefficient=.987)
    with sqlite3.connect(db) as connection:
        connection.execute("DELETE FROM context_snapshots")
    before = db.read_bytes()
    report = verify_context_database(db)
    assert report["tour_states"]["ATP"] == new_active
    assert report["counts"]["snapshots"] == 0
    assert "unrecognized-artifact-schema" not in report["limitations"]
    assert not report["empirical_approval_verified"]
    assert point_rows(db) == before_points and db.read_bytes() == before


@pytest.mark.parametrize("recorded_family,running_family,want", [
    ("inherited", "cached", True), ("cached", "inherited", False),
    ("old_cached", "cached", True), ("old_cached", "inherited", False),
    ("inherited", "old_cached", False), ("cached", "old_cached", False),
    ("old_point", "inherited", True), ("old_point", "cached", True),
])
def test_capture_source_transitions_are_closed_and_directional(recorded_family, running_family, want):
    from context_runtime_tennis import _REVIEWED_CACHED_TRAINING_MANIFEST, _REVIEWED_POINT_JOINT_MANIFEST
    from context_runtime_tennis import _code_manifest_supported
    families = {"inherited": capture_source_manifest("inherited"), "cached": capture_source_manifest(),
        "old_cached": _REVIEWED_CACHED_TRAINING_MANIFEST, "old_point": _REVIEWED_POINT_JOINT_MANIFEST}
    recorded = {name: sorted(hashes)[0] for name, hashes in families[recorded_family].items()}
    assert _code_manifest_supported(recorded, families[running_family]) is want


def test_current_executor_is_the_literal_canonical_capture_family():
    from context_runtime_tennis import _code_variants
    running = _code_variants()
    assert all(hashes <= running[name] for name, hashes in capture_source_manifest().items())


@pytest.mark.parametrize("owner", ["tennis/predict.py", "tennis/model_state.py", "tennis/elo.py", "tennis/data_loader.py",
    "tennis/simulator.py", "tennis/serve_model.py"])
def test_capture_state_rejects_unknown_or_unreviewed_full_family(owner):
    from types import SimpleNamespace
    from context_runtime_tennis import _code_manifest_supported, _code_variants, _state_code_manifest_supported
    from tennis.simulator import POINT_MODEL_VERSION
    recorded = {name: sorted(hashes)[0] for name, hashes in capture_source_manifest().items()}
    recorded[owner] = "0" * 64
    assert not _code_manifest_supported(recorded, _code_variants())
    assert not _state_code_manifest_supported(recorded, SimpleNamespace(market_model_version=POINT_MODEL_VERSION))


def test_known_but_unreviewed_capture_causal_loader_mix_is_rejected():
    from context_runtime_tennis import _REVIEWED_CAUSAL_AVAILABILITY_MANIFEST
    from context_runtime_tennis import _code_manifest_supported, _code_variants, _state_code_manifest_supported
    from types import SimpleNamespace
    from tennis.simulator import POINT_MODEL_VERSION
    recorded = {name: sorted(hashes)[0] for name, hashes in capture_source_manifest().items()}
    recorded["tennis/data_loader.py"] = sorted(_REVIEWED_CAUSAL_AVAILABILITY_MANIFEST["tennis/data_loader.py"])[0]
    assert not _code_manifest_supported(recorded, _code_variants())
    assert not _state_code_manifest_supported(recorded, SimpleNamespace(market_model_version=POINT_MODEL_VERSION))
