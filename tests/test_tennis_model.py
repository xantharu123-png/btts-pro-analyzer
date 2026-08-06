"""Tennis package regression tests.

Anchors the mathematics (simulator closed forms), the causal
discipline (odds-blind loader, walk-forward calibrator) and the name
normalisation that joins the two data planes.
"""

from __future__ import annotations

import math

import pytest

from tennis import simulator as sim
from tennis.data_loader import (
    _assert_odds_blind,
    normalize_player_name,
    resolve_player_name_key,
)
from tennis.elo import SurfaceElo
from tennis.serve_model import ServeReturnModel, _log5, TOUR_HOLD_AVG
from tennis.backtest import WalkForwardCalibrator, _is_retired, _devig


# ------------------------------------------------------------------ simulator


class TestSimulator:
    def test_game_win_prob_half(self):
        assert sim.game_win_prob(0.5) == pytest.approx(0.5, abs=1e-9)

    def test_game_win_prob_monotonic(self):
        assert sim.game_win_prob(0.6) > sim.game_win_prob(0.5)
        assert sim.game_win_prob(0.7) > 0.9  # servers dominate

    def test_hold_to_point_roundtrip(self):
        for hold in (0.60, 0.77, 0.90):
            p = sim.hold_to_point_prob(hold)
            assert sim.game_win_prob(p) == pytest.approx(hold, abs=1e-3)

    def test_tiebreak_half(self):
        assert sim.tiebreak_win_prob(0.5) == pytest.approx(0.5, abs=1e-9)

    def test_symmetric_match_is_fifty_fifty(self):
        for best_of in (3, 5):
            m = sim.simulate_match(0.77, 0.77, best_of=best_of)
            assert m.p_a_win == pytest.approx(0.5, abs=1e-6)
            assert sum(m.games_total.values()) == pytest.approx(1.0, abs=1e-9)
            assert sum(m.sets_played.values()) == pytest.approx(1.0, abs=1e-9)
            assert sum(m.correct_scores.values()) == pytest.approx(1.0, abs=1e-9)

    def test_bo3_over_25_sets_symmetric(self):
        m = sim.simulate_match(0.77, 0.77, best_of=3)
        assert m.over_sets(2.5) == pytest.approx(0.5, abs=1e-6)

    def test_stronger_player_wins_more(self):
        m = sim.simulate_match(0.88, 0.62, best_of=3)
        assert m.p_a_win > 0.9
        # handicap lines must be ordered
        assert m.handicap_a(-3.5) > m.handicap_a(-4.5)

    def test_bo5_set_totals_only_3_4_5(self):
        m = sim.simulate_match(0.80, 0.75, best_of=5)
        assert set(m.sets_played) <= {3, 4, 5}
        assert m.over_sets(3.5) == pytest.approx(
            m.sets_played.get(4, 0) + m.sets_played.get(5, 0), abs=1e-9
        )

    def test_even_bo5_over_35_is_high(self):
        # the user's Djokovic-Alcaraz case: two even top players
        m = sim.simulate_match(0.80, 0.79, best_of=5)
        assert m.over_sets(3.5) > 0.70

    def test_big_servers_raise_tiebreak_probability(self):
        normal = sim.simulate_match(0.77, 0.77, best_of=3)
        servers = sim.simulate_match(0.93, 0.92, best_of=3)
        assert servers.p_tiebreak_in_match > normal.p_tiebreak_in_match
        assert servers.expected_total_games > normal.expected_total_games

    def test_invalid_best_of_rejected(self):
        with pytest.raises(ValueError):
            sim.simulate_match(0.77, 0.77, best_of=7)


# ------------------------------------------------------------------------ elo


class TestSurfaceElo:
    def test_upset_moves_ratings(self):
        elo = SurfaceElo()
        before_w = elo.overall.rating("a")
        before_l = elo.overall.rating("b")
        elo.update("a", "b", "Hard")
        assert elo.overall.rating("a") > before_w
        assert elo.overall.rating("b") < before_l

    def test_unknown_players_are_even(self):
        elo = SurfaceElo()
        assert elo.win_probability("x", "y", "Hard") == pytest.approx(0.5)

    def test_dominance_separates(self):
        elo = SurfaceElo()
        for _ in range(30):
            elo.update("goat", "journeyman", "Hard")
        assert elo.win_probability("goat", "journeyman", "Hard") > 0.9

    def test_surface_specificity(self):
        elo = SurfaceElo()
        for _ in range(15):
            elo.update("clayking", "grinder", "Clay")
        for _ in range(15):
            elo.update("grinder", "clayking", "Hard")
        p_clay = elo.win_probability("clayking", "grinder", "Clay")
        p_hard = elo.win_probability("clayking", "grinder", "Hard")
        assert p_clay > p_hard


# --------------------------------------------------------------- serve model


class TestServeModel:
    def test_log5_league_average_is_identity(self):
        # a league-average returner (break% = 1 - L) must not move the hold%
        assert _log5(0.85, 1.0 - TOUR_HOLD_AVG) == pytest.approx(0.85, abs=1e-9)
        assert _log5(0.70, 1.0 - TOUR_HOLD_AVG) == pytest.approx(0.70, abs=1e-9)

    def test_log5_strong_returner_lowers_hold(self):
        assert _log5(0.85, 0.30) < 0.85
        assert _log5(0.85, 0.15) > 0.85

    def test_unknown_player_gets_tour_average(self):
        model = ServeReturnModel()
        hold, brk = model.hold_and_break("nobody", "Hard")
        assert hold == pytest.approx(TOUR_HOLD_AVG)


# --------------------------------------------------------------- name joining


class TestNormalize:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Roger Federer", "federer r"),
            ("Federer R.", "federer r"),
            ("Roman Andres Burruchaga", "burruchaga r"),
            ("Burruchaga R.", "burruchaga r"),
            ("Alex de Minaur", "de minaur a"),
            ("De Minaur A.", "de minaur a"),
            ("Christopher O'Connell", "oconnell c"),
            ("O Connell C.", "oconnell c"),
            ("Botic van de Zandschulp", "van de zandschulp b"),
            ("Van de Zandschulp B.", "van de zandschulp b"),
            ("Giovanni Mpetshi Perricard", "mpetshi perricard g"),
            ("Mpetshi Perricard G.", "mpetshi perricard g"),
        ],
    )
    def test_sources_agree(self, raw, expected):
        assert normalize_player_name(raw) == expected

    def test_surname_first_provider_name_uses_proven_historical_key(self):
        known = frozenset({"shang j", "darderi l"})
        assert resolve_player_name_key("Shang Juncheng", known) == "shang j"

    def test_unknown_reversed_name_is_not_guessed(self):
        assert resolve_player_name_key("Unknown Player", frozenset()) == "player u"


# ------------------------------------------------------------ causal hygiene


class TestHygiene:
    def test_odds_blind_allowlist(self):
        _assert_odds_blind(["Date", "Winner", "w_ace", "surface"])  # must pass
        with pytest.raises(AssertionError):
            _assert_odds_blind(["Date", "PSW"])
        with pytest.raises(AssertionError):
            _assert_odds_blind(["B365W"])

    def test_retired_detection(self):
        assert _is_retired("(RET)")
        assert _is_retired("Retired")
        assert not _is_retired("Completed")
        assert not _is_retired(None)
        assert not _is_retired(float("nan"))

    def test_devig_sums_to_one(self):
        pw, pl = _devig(1.80, 2.10)
        assert pw + pl == pytest.approx(1.0, abs=1e-9)
        assert _devig(1.0, 2.0) is None  # corrupt price rejected

    def test_calibrator_is_causal(self):
        cal = WalkForwardCalibrator(min_samples=10, refit_every=5)
        # before training: identity
        assert cal.predict(0.9) == pytest.approx(0.9)
        # compressed history: several probability levels, each actually 80%
        for x in (0.55, 0.60, 0.65, 0.70):
            for i in range(10):
                cal.add(x, 0.0 if i % 5 == 0 else 1.0)  # true rate 0.8
        # after training the calibrator must move probabilities UP
        assert cal.predict(0.6) > 0.6
        assert cal.predict(0.55) > 0.55
