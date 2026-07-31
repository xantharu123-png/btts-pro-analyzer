"""F2: indoor/outdoor environment split for the serve model.

Hard Indoor holds 0.800 vs 0.792 not-indoor (tour-level 2015-2026,
~9 sigma).  The model keeps a pure Hard@Indoor bucket, shrinks each
bucket toward its own environment average, translates sparse players
between scales in odds form, and feeds log5 the environment constant —
two average players must combine to EXACTLY the environment average.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from tennis.serve_model import (
    HARD_INDOOR_HOLD_AVG,
    HARD_INDOOR_KEY,
    HARD_NOTINDOOR_HOLD_AVG,
    ServeReturnModel,
    _shift,
)

T0 = datetime(2025, 1, 1)


def _row(winner="alpha", loser="beta", brk_made=3.0, brk_conceded=2.0,
         when=T0, surface="Hard", env="Outdoor"):
    return {
        "winner_key": winner,
        "loser_key": loser,
        "win_service_games_played": 10.0,
        "win_return_games_played": 10.0,
        "los_service_games_played": 10.0,
        "los_return_games_played": 10.0,
        "win_break_points_converted": brk_made,
        "los_break_points_converted": brk_conceded,
        "surface": surface,
        "indoor_outdoor": env,
        "tourney_date": when,
    }


class TestBuckets:
    def test_indoor_match_feeds_compound_bucket_only(self):
        m = ServeReturnModel(split_indoor=True)
        m.update_from_match_row(_row(env="Indoor"))
        assert ("alpha", HARD_INDOOR_KEY) in m._table
        assert ("alpha", "Hard") not in m._table  # stays not-indoor-pure
        assert ("alpha", "__overall__") in m._table

    def test_unsplit_model_ignores_the_flag(self):
        m = ServeReturnModel(split_indoor=False)
        m.update_from_match_row(_row(env="Indoor"))
        assert ("alpha", "Hard") in m._table
        assert ("alpha", HARD_INDOOR_KEY) not in m._table


class TestTranslation:
    def test_shift_identity_at_source_average(self):
        assert _shift(HARD_NOTINDOOR_HOLD_AVG,
                      HARD_NOTINDOOR_HOLD_AVG,
                      HARD_INDOOR_HOLD_AVG) == pytest.approx(HARD_INDOOR_HOLD_AVG)

    def test_strong_server_stays_relatively_strong(self):
        shifted = _shift(0.85, HARD_NOTINDOOR_HOLD_AVG, HARD_INDOOR_HOLD_AVG)
        assert shifted > 0.85  # indoor world is easier for servers
        assert shifted < 0.86  # but only by the environment gap

    def test_fallback_translates_when_no_indoor_data(self):
        m = ServeReturnModel(split_indoor=True)
        for _ in range(6):  # 60 outdoor games, 0 breaks conceded
            m.update_from_match_row(_row(brk_conceded=0.0, env="Outdoor"))
        hold_in, _ = m.hold_and_break("alpha", "Hard", as_of=T0, indoor=True)
        hold_out, _ = m.hold_and_break("alpha", "Hard", as_of=T0, indoor=False)
        assert hold_in > hold_out  # same player, translated upward


class TestCompoundPreference:
    def test_indoor_form_wins_over_outdoor_form(self):
        m = ServeReturnModel(split_indoor=True)
        for _ in range(6):  # perfect indoor record
            m.update_from_match_row(_row(brk_conceded=0.0, env="Indoor"))
        for _ in range(6):  # leaky outdoor record
            m.update_from_match_row(_row(brk_conceded=5.0, env="Outdoor"))
        hold_in, _ = m.hold_and_break("alpha", "Hard", as_of=T0, indoor=True)
        hold_out, _ = m.hold_and_break("alpha", "Hard", as_of=T0, indoor=False)
        assert hold_in > hold_out
        assert hold_in > 0.85  # mostly his perfect indoor data
        assert hold_out < 0.75  # mostly his leaky outdoor data


class TestLog5EnvironmentIdentity:
    def test_unknown_players_combine_to_environment_average(self):
        m = ServeReturnModel(split_indoor=True)
        p_in, _ = m.expected_hold_probabilities("x", "y", "Hard", as_of=T0, indoor=True)
        p_out, _ = m.expected_hold_probabilities("x", "y", "Hard", as_of=T0, indoor=False)
        assert p_in == pytest.approx(HARD_INDOOR_HOLD_AVG, abs=1e-9)
        assert p_out == pytest.approx(HARD_NOTINDOOR_HOLD_AVG, abs=1e-9)

    def test_unsplit_model_keeps_overall_average(self):
        m = ServeReturnModel(split_indoor=False)
        p, _ = m.expected_hold_probabilities("x", "y", "Hard", as_of=T0, indoor=True)
        assert p == pytest.approx(0.770, abs=1e-9)
