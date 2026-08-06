"""Extra coverage for the daily prediction path (gates + verdicts)."""

from __future__ import annotations

import time

import pytest

from tennis.elo import SurfaceElo
from tennis.model_state import ModelState
from tennis.predict import predict_match
from tennis.serve_model import ServeReturnModel


def _synthetic_state() -> ModelState:
    """Tiny but non-empty state: 'hero' dominates 'grinder' on Hard."""
    elo = SurfaceElo()
    serve = ServeReturnModel()
    for _ in range(25):
        elo.update("hero h", "grinder g", "Hard")
        row = {
            "winner_key": "hero h",
            "loser_key": "grinder g",
            "winner_name": "Hero H.",
            "loser_name": "Grinder G.",
            "surface": "Hard",
            "win_service_games_played": 10,
            "win_return_games_played": 10,
            "win_break_points_converted": 3,
            "los_break_points_converted": 1,
            "los_service_games_played": 10,
            "los_return_games_played": 10,
            "los_break_points_converted": 1,
            "win_break_points_saved": 2,
        }
        serve.update_from_match_row(row)
    return ModelState(
        elo=elo,
        serve=serve,
        cal_a=1.0,
        cal_b=0.0,
        cal_samples=0,
        built_at=time.time(),
        stats_through="2026-07-27",
        serve_weight=0.3,
    )


class TestPredictGates:
    def test_known_players_hard_passes_model_gates(self):
        state = _synthetic_state()
        pred = predict_match(state, "Hero H.", "Grinder G.", "Hard", 3)
        assert pred.gates[0].passed  # surface
        assert pred.gates[1].passed  # experience
        assert pred.p_a_cal > 0.7    # hero clearly favoured

    def test_clay_is_blocked(self):
        state = _synthetic_state()
        pred = predict_match(state, "Hero H.", "Grinder G.", "Clay", 3)
        assert not pred.gates[0].passed
        assert pred.verdict == "KEINE WETTE"

    def test_unknown_players_blocked(self):
        state = _synthetic_state()
        pred = predict_match(state, "Niemand A.", "Hero H.", "Hard", 3)
        assert not pred.gates[1].passed  # experience gate
        assert not pred.gates[3].passed  # player identity gate
        assert pred.verdict == "KEINE WETTE"

    def test_surname_first_provider_name_reuses_known_player_history(self):
        state = _synthetic_state()
        pred = predict_match(state, "Hero Hector", "Grinder G.", "Hard", 3)
        assert pred.gates[1].passed
        assert pred.gates[2].passed
        assert pred.gates[3].passed
        assert pred.p_a_cal > 0.7

    def test_edge_gate_needs_real_value(self):
        state = _synthetic_state()
        # market prices hero correctly -> no edge -> no bet
        pred = predict_match(
            state, "Hero H.", "Grinder G.", "Hard", 3, odds_a=1.05, odds_b=9.0
        )
        assert pred.verdict == "KEINE WETTE"
        # market offers hero at a gift price -> bet
        pred2 = predict_match(
            state, "Hero H.", "Grinder G.", "Hard", 3, odds_a=1.80, odds_b=2.00
        )
        assert pred2.verdict == "WETTE"
        assert pred2.recommended_side == "A"

    def test_calibration_is_invariant_when_players_are_swapped(self):
        state = _synthetic_state()
        state.cal_a, state.cal_b = 0.8, 0.2
        forward = predict_match(state, "Hero H.", "Grinder G.", "Hard", 3)
        reverse = predict_match(state, "Grinder G.", "Hero H.", "Hard", 3)
        assert forward.p_a_cal + reverse.p_a_cal == pytest.approx(1.0, abs=1e-4)

    def test_corrupt_prices_blocked(self):
        state = _synthetic_state()
        pred = predict_match(
            state, "Hero H.", "Grinder G.", "Hard", 3, odds_a=0.95, odds_b=2.0
        )
        assert pred.verdict == "KEINE WETTE"


class TestPredictWTA:
    def test_wta_serve_gate_is_passthrough(self):
        """WTA has no boxscore feed: serve gate passes with an honest note."""
        state = _synthetic_state()
        pred = predict_match(state, "Hero H.", "Grinder G.", "Hard", 3, tour="WTA")
        serve_gate = pred.gates[2]
        assert serve_gate.passed
        assert "Elo-Modus" in serve_gate.detail

    def test_wta_uses_separate_calibration(self):
        """cal_wta_a/b must be applied for WTA, cal_a/b for ATP."""
        state = _synthetic_state()
        state.cal_a, state.cal_b = 1.0, 0.0
        state.cal_wta_a, state.cal_wta_b = 0.5, 0.0
        atp = predict_match(state, "Hero H.", "Grinder G.", "Hard", 3, tour="ATP")
        wta = predict_match(state, "Hero H.", "Grinder G.", "Hard", 3, tour="WTA")
        assert atp.p_a_raw == wta.p_a_raw
        assert wta.p_a_cal < atp.p_a_cal  # a=0.5 shrinks towards 0.5
        assert wta.p_a_cal > 0.5

    def test_wta_never_recommends_a_bet(self):
        """Real WTA backtest shows no edge -> shadow observation only."""
        state = _synthetic_state()
        pred = predict_match(
            state, "Hero H.", "Grinder G.", "Hard", 3,
            odds_a=1.80, odds_b=2.00, tour="WTA",
        )
        release_gate = pred.gates[0]
        assert release_gate.name == "WTA-Freigabe"
        assert not release_gate.passed
        assert pred.verdict == "KEINE WETTE"
        # ... but the card still carries the probability for shadow tracking
        assert pred.p_a_cal > 0.5

    def test_wta_still_blocks_unknown_players(self):
        state = _synthetic_state()
        pred = predict_match(state, "Niemand A.", "Hero H.", "Hard", 3, tour="WTA")
        assert not pred.gates[1].passed
        assert pred.verdict == "KEINE WETTE"

    def test_default_tour_is_atp(self):
        state = _synthetic_state()
        pred = predict_match(state, "Hero H.", "Grinder G.", "Hard", 3)
        assert "Service-Games" in pred.gates[2].detail

    def test_market_summary_has_calibrated_set_markets(self):
        state = _synthetic_state()
        pred = predict_match(state, "Hero H.", "Grinder G.", "Hard", 3)
        summary = pred.market_summary()
        assert "over_2_5_sets" in summary
        assert "under_2_5_sets" in summary
        assert abs(summary["over_2_5_sets"] + summary["under_2_5_sets"] - 1.0) < 0.01
        assert "set_handicap_a_minus_1_5" in summary
        assert "set_handicap_b_minus_1_5" in summary
        # hero dominates -> A 2:0 must be the likelier straight-sets side
        assert summary["set_handicap_a_minus_1_5"] > summary["set_handicap_b_minus_1_5"]
