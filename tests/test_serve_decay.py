"""Exponential decay of the serve/return accumulators (F1).

Career sums treat a match from 2019 the same as yesterday's — ratings
must follow current form.  The decay is O(1): the past is folded into
the accumulator at each update (multiply by 0.5 ** (dt / half_life)),
never re-walked.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tennis.serve_model import ServeReturnModel

T0 = datetime(2025, 1, 1)


def _row(sv_gms=10.0, ret_gms=10.0, brk_made=3.0, brk_conceded=2.0,
         winner="alpha", loser="beta", when=T0, surface="Hard"):
    return {
        "winner_key": winner,
        "loser_key": loser,
        "win_service_games_played": sv_gms,
        "win_return_games_played": sv_gms,
        "los_service_games_played": ret_gms,
        "los_return_games_played": ret_gms,
        "win_break_points_converted": brk_made,
        "los_break_points_converted": brk_conceded,
        "surface": surface,
        "tourney_date": when,
    }


class TestDecay:
    def test_weight_halves_after_one_half_life(self):
        m = ServeReturnModel(half_life_days=180.0)
        m.update_from_match_row(_row())
        assert m.service_games("alpha", as_of=T0) == pytest.approx(10.0)
        assert m.service_games("alpha", as_of=T0 + timedelta(days=180)) == pytest.approx(5.0)
        assert m.service_games("alpha", as_of=T0 + timedelta(days=360)) == pytest.approx(2.5)

    def test_none_half_life_is_cumulative(self):
        m = ServeReturnModel(half_life_days=None)
        m.update_from_match_row(_row())
        assert m.service_games("alpha", as_of=T0 + timedelta(days=3650)) == pytest.approx(10.0)

    def test_update_decays_past_before_adding(self):
        m = ServeReturnModel(half_life_days=180.0)
        m.update_from_match_row(_row(when=T0))
        m.update_from_match_row(_row(when=T0 + timedelta(days=180)))
        # 10 old games halved + 10 new games, measured at the second match
        assert m.service_games("alpha", as_of=T0 + timedelta(days=180)) == pytest.approx(15.0)

    def test_missing_last_date_slot_means_no_decay(self):
        # pickles written before the slot existed must load and predict
        m = ServeReturnModel(half_life_days=180.0)
        m.update_from_match_row(_row())
        acc = m._table[("alpha", "__overall__")]
        del acc.last_date  # simulate an old pickle
        assert m.service_games("alpha", as_of=T0 + timedelta(days=3650)) == pytest.approx(10.0)

    def test_out_of_order_update_never_inflates(self):
        m = ServeReturnModel(half_life_days=180.0)
        m.update_from_match_row(_row(when=T0))
        # a late-arriving match from BEFORE the last one: factor clamped
        # to 1.0 (decay would otherwise *inflate* the newer past)
        m.update_from_match_row(_row(when=T0 - timedelta(days=30), brk_made=4.0))
        acc = m._table[("alpha", "__overall__")]
        assert acc.last_date == T0  # max() wins, clock never runs back
        assert m.service_games("alpha", as_of=T0) == pytest.approx(20.0)

    def test_rates_follow_recent_form(self):
        # "vet" held every serve a year ago (2 half-lives -> weight 1/4),
        # "rookie" holds 80% today.  Cumulative sums would keep the vet
        # near 1.0 (shrunk: ~0.885); with decay his stale peak must be
        # pulled much harder toward the tour average.
        m = ServeReturnModel(half_life_days=180.0)
        old = T0 - timedelta(days=360)
        for _ in range(6):  # vet: 60 service games, 0 breaks conceded, a year ago
            m.update_from_match_row(_row(winner="vet", loser="vetopp", brk_conceded=0.0, when=old))
        for _ in range(6):  # rookie: 60 service games, 2 breaks each, today
            m.update_from_match_row(_row(winner="rookie", loser="rokopp", brk_conceded=2.0, when=T0))
        hold_vet, _ = m.hold_and_break("vet", None, as_of=T0)
        hold_rookie, _ = m.hold_and_break("rookie", None, as_of=T0)
        # 100% (even discounted) still beats 80% — but only barely now
        assert hold_vet > hold_rookie
        assert hold_vet < 0.84  # cumulative sums would say ~0.885
        assert hold_vet - hold_rookie < 0.06  # cumulative would say ~0.10

    def test_match_date_argument_overrides_row(self):
        m = ServeReturnModel(half_life_days=180.0)
        m.update_from_match_row(_row(when=None), match_date=T0)
        acc = m._table[("alpha", "__overall__")]
        assert acc.last_date == T0
