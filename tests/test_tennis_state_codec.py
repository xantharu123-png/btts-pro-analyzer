from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import math
import pickle

import pytest

from tennis.elo import INITIAL_RATING, SURFACES, SurfaceElo
from tennis.model_state import ModelState, load_state
from tennis.serve_model import (
    HARD_INDOOR_KEY,
    OVERALL_KEY,
    WTA_TOUR_BREAK_AVG,
    WTA_TOUR_HOLD_AVG,
    ServeReturnModel,
)
from tennis.state_codec import decode_state, encode_state


def _match_row(
    winner: str,
    loser: str,
    *,
    surface: str = "Hard",
    indoor: str = "Indoor",
) -> dict:
    return {
        "winner_key": winner,
        "loser_key": loser,
        "winner_name": winner,
        "loser_name": loser,
        "surface": surface,
        "indoor_outdoor": indoor,
        "win_service_games_played": 13.125,
        "win_return_games_played": 11.75,
        "win_break_points_converted": 2.25,
        "los_break_points_converted": 1.375,
        "los_service_games_played": 11.75,
        "los_return_games_played": 13.125,
    }


def _state(*, tour: str = "ATP", built_at: float = 1788739200.125) -> ModelState:
    elo = SurfaceElo()
    for _ in range(9):
        elo.update("player-a", "player-b", "Clay")

    if tour == "WTA":
        serve = ServeReturnModel(
            hold_avg=WTA_TOUR_HOLD_AVG,
            break_avg=WTA_TOUR_BREAK_AVG,
            half_life_days=None,
            split_indoor=False,
        )
    else:
        serve = ServeReturnModel(
            hold_avg=0.7700000000000001,
            break_avg=0.2299999999999999,
            half_life_days=123.45678901234567,
            split_indoor=True,
        )
        serve.update_from_match_row(
            _match_row("player-a", "player-b"),
            match_date=datetime(2026, 7, 1, 12, 34, 56, 789012),
        )
        serve.update_from_match_row(
            _match_row(
                "player-b",
                "player-a",
                surface="Clay",
                indoor="Outdoor",
            ),
            match_date=datetime(2026, 8, 2, 3, 4, 5, 678901),
        )

    return ModelState(
        elo=elo,
        serve=serve,
        cal_a=1.1234567890123457,
        cal_b=-0.03141592653589793,
        cal_samples=2001,
        built_at=built_at,
        stats_through="2026-09-01",
        serve_weight=0.30000000000000004,
        cal_wta_a=0.9876543210987654,
        cal_wta_b=0.0123456789012345,
        cal_wta_samples=1777,
        tour_scope=tour,
        stats_through_kind="tournament_start_proxy",
        artifact_hash="f" * 64,
    )


def test_tour_codec_preserves_all_fields_ratings_accumulators_and_calibration():
    state = _state()

    payload = encode_state(state, tour="ATP")
    result = decode_state(payload)

    assert set(payload) == {
        "schema",
        "tour",
        "elo",
        "serve",
        "cal_a",
        "cal_b",
        "cal_samples",
        "cal_wta_a",
        "cal_wta_b",
        "cal_wta_samples",
        "built_at",
        "stats_through",
        "stats_through_kind",
        "serve_weight",
    }
    assert payload["schema"] == 1
    assert result.tour_scope == "ATP"
    assert result.artifact_hash is None
    assert result.elo.to_payload() == state.elo.to_payload()
    assert result.serve.to_payload() == state.serve.to_payload()
    assert result.cal_a == state.cal_a
    assert result.cal_b == state.cal_b
    assert result.cal_samples == state.cal_samples
    assert result.cal_wta_a == state.cal_wta_a
    assert result.cal_wta_b == state.cal_wta_b
    assert result.cal_wta_samples == state.cal_wta_samples
    assert result.built_at == state.built_at
    assert result.stats_through == state.stats_through
    assert result.stats_through_kind == state.stats_through_kind
    assert result.serve_weight == state.serve_weight
    assert result.elo.win_probability("player-a", "player-b", "Clay") == (
        state.elo.win_probability("player-a", "player-b", "Clay")
    )
    assert result.calibrate_match(0.7, "a", "b", "ATP") == (
        state.calibrate_match(0.7, "a", "b", "ATP")
    )
    assert result.calibrate_match(0.7, "b", "a", "ATP") == (
        state.calibrate_match(0.7, "b", "a", "ATP")
    )


def test_codec_preserves_wta_serve_constants_and_calibration():
    state = _state(tour="WTA")

    result = decode_state(encode_state(state, tour="WTA"))

    assert result.serve.hold_and_break("unknown", "Clay") == (
        WTA_TOUR_HOLD_AVG,
        WTA_TOUR_BREAK_AVG,
    )
    assert result.calibrate_match(0.7, "a", "b", "WTA") == (
        state.calibrate_match(0.7, "a", "b", "WTA")
    )
    assert result.serve.to_payload()["half_life_days"] is None


def test_crossed_and_legacy_combined_tours_cannot_be_encoded():
    with pytest.raises(ValueError, match="tour"):
        encode_state(_state(tour="ATP"), tour="WTA")
    with pytest.raises(ValueError, match="legacy-combined"):
        encode_state(
            ModelState(
                SurfaceElo(),
                ServeReturnModel(),
                1.0,
                0.0,
                0,
                1.0,
                "1970-01-01",
                0.3,
            ),
            tour="ATP",
        )


def test_elo_payload_has_fixed_surfaces_and_unknown_lookup_creates_no_state():
    elo = SurfaceElo()
    elo.update("winner", "loser", "Grass")

    payload = elo.to_payload()
    restored = SurfaceElo.from_payload(payload)
    before = restored.to_payload()

    assert set(payload) == {"overall", "by_surface"}
    assert tuple(payload["by_surface"]) == SURFACES
    assert payload["overall"]["winner"][1] == 1
    assert restored.win_probability("never-seen-a", "never-seen-b", "Clay") == 0.5
    assert restored.overall.rating("never-seen-a") == INITIAL_RATING
    assert restored.to_payload() == before


def test_elo_payload_and_rehydrated_state_do_not_share_nested_lists():
    elo = SurfaceElo()
    elo.update("winner", "loser", "Hard")

    payload = elo.to_payload()
    restored = SurfaceElo.from_payload(payload)
    original_rating = elo.overall.rating("winner")
    restored_rating = restored.overall.rating("winner")

    payload["overall"]["winner"][0] = -1.0
    assert elo.overall.rating("winner") == original_rating
    assert restored.overall.rating("winner") == restored_rating

    second_payload = restored.to_payload()
    restored.overall._table["winner"][0] = -2.0
    assert second_payload["overall"]["winner"][0] == restored_rating


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(extra={}),
        lambda p: p.pop("overall"),
        lambda p: p["by_surface"].pop("Clay"),
        lambda p: p["by_surface"].update(Unknown={}),
        lambda p: p["overall"].update({"x": [math.nan, 0]}),
        lambda p: p["overall"].update({"x": [1500.0, -1]}),
        lambda p: p["overall"].update({"x": [1500.0, True]}),
        lambda p: p["overall"].update({"x": [1500.0, 0.5]}),
        lambda p: p["overall"].update({"x": [True, 0]}),
        lambda p: p["overall"].update({"x": (1500.0, 0)}),
    ],
    ids=[
        "unexpected-key",
        "missing-key",
        "missing-surface",
        "unknown-surface",
        "nonfinite-rating",
        "negative-matches",
        "bool-matches",
        "fractional-matches",
        "bool-rating",
        "tuple-is-not-json-array",
    ],
)
def test_elo_decoder_rejects_malformed_payloads(change):
    payload = SurfaceElo().to_payload()
    change(payload)

    with pytest.raises((TypeError, ValueError)):
        SurfaceElo.from_payload(payload)


def test_serve_payload_is_sorted_fixed_and_preserves_dates_and_precision():
    model = _state().serve

    payload = model.to_payload()
    restored = ServeReturnModel.from_payload(payload)

    assert set(payload) == {
        "hold_avg",
        "break_avg",
        "half_life_days",
        "split_indoor",
        "rows",
    }
    assert [(row["player"], row["bucket"]) for row in payload["rows"]] == sorted(
        (row["player"], row["bucket"]) for row in payload["rows"]
    )
    assert all(
        set(row)
        == {
            "player",
            "bucket",
            "sv_gms",
            "sv_held",
            "ret_gms",
            "ret_breaks",
            "sv_opp_break_sum",
            "ret_opp_hold_sum",
            "last_date",
        }
        for row in payload["rows"]
    )
    assert {row["bucket"] for row in payload["rows"]} == {
        OVERALL_KEY,
        "Clay",
        HARD_INDOOR_KEY,
    }
    assert any(row["last_date"] == "2026-08-02T03:04:05.678901" for row in payload["rows"])
    assert restored.to_payload() == payload
    assert restored.expected_hold_probabilities(
        "player-a",
        "player-b",
        "Hard",
        as_of=datetime(2026, 9, 1),
        indoor=True,
    ) == model.expected_hold_probabilities(
        "player-a",
        "player-b",
        "Hard",
        as_of=datetime(2026, 9, 1),
        indoor=True,
    )


def _valid_serve_payload() -> dict:
    return {
        "hold_avg": 0.77,
        "break_avg": 0.23,
        "half_life_days": 365.0,
        "split_indoor": True,
        "rows": [
            {
                "player": "player-a",
                "bucket": OVERALL_KEY,
                "sv_gms": 10.0,
                "sv_held": 8.0,
                "ret_gms": 10.0,
                "ret_breaks": 2.0,
                "sv_opp_break_sum": 2.3,
                "ret_opp_hold_sum": 7.7,
                "last_date": "2026-08-02T03:04:05.678901",
            }
        ],
    }


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(extra=1),
        lambda p: p.pop("rows"),
        lambda p: p.update(hold_avg=True),
        lambda p: p.update(break_avg=math.inf),
        lambda p: p.update(half_life_days=0.0),
        lambda p: p.update(half_life_days=True),
        lambda p: p.update(split_indoor=1),
        lambda p: p["rows"][0].update(extra=1),
        lambda p: p["rows"][0].update(bucket="Unknown"),
        lambda p: p["rows"][0].update(sv_gms=-1.0),
        lambda p: p["rows"][0].update(sv_gms=True),
        lambda p: p["rows"][0].update(sv_held=11.0),
        lambda p: p["rows"][0].update(ret_breaks=11.0),
        lambda p: p["rows"][0].update(sv_opp_break_sum=math.nan),
        lambda p: p["rows"][0].update(last_date="not-a-date"),
        lambda p: p["rows"].append(deepcopy(p["rows"][0])),
    ],
    ids=[
        "unexpected-key",
        "missing-key",
        "bool-hold",
        "nonfinite-break",
        "zero-half-life",
        "bool-half-life",
        "non-bool-split",
        "unexpected-row-key",
        "unknown-bucket",
        "negative-count",
        "bool-count",
        "holds-above-games",
        "breaks-above-games",
        "nonfinite-opponent-sum",
        "invalid-date",
        "duplicate-player-bucket",
    ],
)
def test_serve_decoder_rejects_malformed_payloads(change):
    payload = _valid_serve_payload()
    change(payload)

    with pytest.raises((TypeError, ValueError)):
        ServeReturnModel.from_payload(payload)


def test_encoded_payload_is_detached_from_models_and_decoded_state():
    state = _state()
    payload = encode_state(state, tour="ATP")
    restored = decode_state(payload)
    encoded_rating = payload["elo"]["overall"]["player-a"][0]
    restored_rating = restored.elo.overall.rating("player-a")

    state.elo.overall._table["player-a"][0] = -10.0
    restored.elo.overall._table["player-a"][0] = -20.0

    assert payload["elo"]["overall"]["player-a"][0] == encoded_rating
    assert restored_rating != -10.0


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(schema=2),
        lambda p: p.update(schema=True),
        lambda p: p.update(schema=1.0),
        lambda p: p.update(tour="atp"),
        lambda p: p.update(tour="MIXED"),
        lambda p: p.update(built_at=math.nan),
        lambda p: p.update(built_at=True),
        lambda p: p.update(cal_a=math.inf),
        lambda p: p.update(cal_samples=-1),
        lambda p: p.update(cal_wta_samples=1.5),
        lambda p: p.update(serve_weight=True),
        lambda p: p.update(stats_through_kind=""),
        lambda p: p.pop("elo"),
        lambda p: p.update(extra="not allowed"),
    ],
    ids=[
        "unsupported-schema",
        "bool-schema",
        "float-schema",
        "lowercase-tour",
        "unsupported-tour",
        "nonfinite-built-at",
        "bool-built-at",
        "nonfinite-calibrator",
        "negative-samples",
        "fractional-wta-samples",
        "bool-serve-weight",
        "empty-coverage-kind",
        "missing-key",
        "unexpected-key",
    ],
)
def test_state_decoder_rejects_bad_envelopes(change):
    payload = encode_state(_state(), tour="ATP")
    change(payload)

    with pytest.raises((TypeError, ValueError)):
        decode_state(payload)


def test_decision_cutoff_is_explicit_finite_and_inclusive():
    future = encode_state(_state(built_at=200.0), tour="ATP")

    assert decode_state(future).built_at == 200.0
    assert decode_state(future, decision_cutoff=200.0).built_at == 200.0
    with pytest.raises(ValueError, match="decision cutoff"):
        decode_state(future, decision_cutoff=199.999)
    for invalid in (True, math.nan, math.inf, "200"):
        with pytest.raises((TypeError, ValueError), match="decision_cutoff"):
            decode_state(future, decision_cutoff=invalid)


def test_legacy_pickle_load_applies_new_in_memory_defaults(tmp_path):
    state = _state()
    del state.tour_scope
    del state.stats_through_kind
    del state.artifact_hash
    path = tmp_path / "legacy.pkl"
    path.write_bytes(pickle.dumps(state))

    loaded = load_state(path)

    assert loaded.tour_scope == "legacy-combined"
    assert loaded.stats_through_kind == "tournament_start_proxy"
    assert loaded.artifact_hash == hashlib.sha256(path.read_bytes()).hexdigest()
