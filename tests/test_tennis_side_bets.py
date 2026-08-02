"""Tests for the side-market shadow store (set totals / set handicap)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tennis import shadow


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "side_test.db")
    yield


def _prediction_id() -> int:
    class _Pred:
        player_a, player_b = "Alpha A.", "Beta B."
        surface, best_of = "Hard", 3
        p_a_raw = p_a_cal = 0.62
        gates = []
        verdict = "KEINE WETTE"
        recommended_side = None
        recommended_edge = 0.0

        def market_summary(self):
            return {"over_2_5_sets": 0.55}

    start = datetime.now(timezone.utc) + timedelta(minutes=30)
    return shadow.store_prediction(
        start.date().isoformat(),
        "ATP",
        "Test Open",
        _Pred(),
        scheduled_start_utc=start.isoformat(),
    )


class TestSideBets:
    def test_store_and_settle_win(self, tmp_db):
        pid = _prediction_id()
        bet_id = shadow.store_side_bet(pid, "over_2_5_sets", 0.55, 2.10, 0.074)
        captured = datetime.now(timezone.utc).timestamp()
        shadow.record_side_closing_price(
            bet_id,
            2.00,
            captured_utc=captured,
        )
        shadow.settle_side_bet(bet_id, "2:1")
        summary = shadow.side_bet_summary()
        assert summary["side_bets"] == 1
        assert summary["settled"] == 1
        assert summary["units"] == pytest.approx(1.10, abs=0.01)
        assert summary["clv_samples"] == 1
        assert summary["clv"] == pytest.approx(0.05, abs=0.001)

    def test_under_loses_on_three_sets(self, tmp_db):
        pid = _prediction_id()
        bet_id = shadow.store_side_bet(pid, "under_2_5_sets", 0.45, 1.80, 0.06)
        shadow.settle_side_bet(bet_id, "1:2")
        summary = shadow.side_bet_summary()
        assert summary["units"] == pytest.approx(-1.0, abs=0.01)

    def test_set_handicap_perspective(self, tmp_db):
        pid = _prediction_id()
        a_bet = shadow.store_side_bet(pid, "set_a_2_0", 0.30, 3.00, 0.10)
        b_bet = shadow.store_side_bet(pid, "set_b_2_0", 0.20, 4.50, 0.10)
        shadow.settle_side_bet(a_bet, "2:0")   # A covers
        shadow.settle_side_bet(b_bet, "2:0")   # B does NOT cover
        summary = shadow.side_bet_summary()
        assert summary["units"] == pytest.approx(2.00 - 1.00, abs=0.01)

    def test_retirement_voids_everything(self, tmp_db):
        pid = _prediction_id()
        bet_id = shadow.store_side_bet(pid, "set_a_2_0", 0.30, 3.00, 0.10)
        shadow.settle_side_bet(bet_id, "ret")
        summary = shadow.side_bet_summary()
        assert summary["units"] == pytest.approx(0.0, abs=0.01)
        assert summary["settled"] == 0  # void bets don't count as decided

    def test_unknown_market_rejected(self, tmp_db):
        with pytest.raises(ValueError):
            shadow.store_side_bet(1, "over_21_5_games", 0.5, 2.0, 0.1)

    def test_open_side_bets_joins_match_info(self, tmp_db):
        pid = _prediction_id()
        shadow.store_side_bet(pid, "over_2_5_sets", 0.55, 2.10, 0.074)
        rows = shadow.open_side_bets()
        assert len(rows) == 1
        assert rows[0]["player_a"] == "Alpha A."
        assert rows[0]["match_date"] == datetime.now(timezone.utc).date().isoformat()
