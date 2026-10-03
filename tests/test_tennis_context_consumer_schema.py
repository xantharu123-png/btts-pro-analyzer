"""The header-only consumer shares both closed producer state contracts."""
from copy import deepcopy

import pytest

from context_models.contracts import ContextContractError
from tennis.context_consumer import _state_header, load_tennis_winner_context
from tennis.simulator import LEGACY_MODEL_VERSION, POINT_MODEL_VERSION
from tennis.state_codec import encode_state
from test_tennis_state_codec import _state


def packet(tour="ATP", version=POINT_MODEL_VERSION):
    state = _state(tour=tour)
    state.market_model_version = version
    return {"schema": 1, "training_cutoff": state.training_cutoff,
            "state": encode_state(state, tour=tour)}


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
@pytest.mark.parametrize("version", [LEGACY_MODEL_VERSION, POINT_MODEL_VERSION])
def test_actual_encoded_producer_header_is_supported_without_reconstruction(monkeypatch, tour, version):
    value = packet(tour, version)
    before = deepcopy(value)
    def forbidden(*args, **kwargs):
        pytest.fail("header reconstructed or predicted a model")
    monkeypatch.setattr("tennis.state_codec.decode_state", forbidden)
    monkeypatch.setattr("tennis.elo.SurfaceElo.from_payload", forbidden)
    monkeypatch.setattr("tennis.serve_model.ServeReturnModel.from_payload", forbidden)
    monkeypatch.setattr("tennis.predict.predict_match", forbidden)
    _state_header(value, tour=tour)
    assert value == before


@pytest.mark.parametrize("part,value", [
    ("outer-schema", True), ("outer-schema", 1.0), ("outer-schema", 2),
    ("inner-schema", True), ("inner-schema", 2.0), ("inner-schema", 0),
    ("inner-schema", 3), ("inner-schema", None),
    ("model-version", LEGACY_MODEL_VERSION), ("model-version", "future-model"),
    ("model-version", None), ("model-version", True),
    ("tour", "WTA"), ("tour", None),
    ("extra-state", "unexpected"), ("extra-envelope", "unexpected"),
    ("missing-version", None), ("missing-field", None),
])
def test_unknown_or_crossed_headers_still_fail_closed(part, value):
    data = packet()
    if part == "outer-schema": data["schema"] = value
    elif part == "inner-schema": data["state"]["schema"] = value
    elif part == "model-version": data["state"]["market_model_version"] = value
    elif part == "tour": data["state"]["tour"] = value
    elif part == "extra-state": data["state"][value] = 1
    elif part == "extra-envelope": data[value] = 1
    elif part == "missing-version": data["state"].pop("market_model_version")
    else: data["state"].pop("serve_weight")
    with pytest.raises(ContextContractError):
        _state_header(data, tour="ATP")


@pytest.mark.parametrize("version", [LEGACY_MODEL_VERSION, POINT_MODEL_VERSION])
def test_schema_one_must_not_smuggle_a_new_model_version(version):
    data = packet(version=LEGACY_MODEL_VERSION)
    data["state"]["market_model_version"] = version
    with pytest.raises(ContextContractError):
        _state_header(data, tour="ATP")


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_actual_schema_two_saved_winner_context_is_read_only_and_keeps_probabilities(monkeypatch, tmp_path, tour):
    from test_context_runtime_tennis_live import _point_stored
    db, rows = _point_stored(monkeypatch, tmp_path, tour=tour)
    before = db.read_bytes()
    def forbidden(*args, **kwargs):
        pytest.fail("consumer invoked a producer or model decoder")
    monkeypatch.setattr("tennis.state_codec.decode_state", forbidden)
    monkeypatch.setattr("tennis.predict.predict_match", forbidden)
    monkeypatch.setattr("tennis.tour_state.build_tour_state", forbidden)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)
    result = load_tennis_winner_context(rows[0], path=db)
    assert result is not None
    assert result["probabilities"]["A"] + result["probabilities"]["B"] == 1.0
    assert result["probabilities"] == result["base_probabilities"]
    assert db.read_bytes() == before
