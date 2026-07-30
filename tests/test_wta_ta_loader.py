"""Offline tests for the Tennis Abstract WTA box-score loader."""

from __future__ import annotations

import json

from tennis.data_loader import load_wta_ta_stats


def _row(overrides=None):
    row = [""] * 45
    base = {
        0: "20250110", 1: "Auckland", 2: "Hard", 3: "I", 4: "W",
        5: "Test Alpha", 9: "R32", 12: "Test Beta",
        33: "10", 34: "3", 35: "5",      # my games / saved / chances
        42: "10", 43: "2", 44: "6",      # opp games / saved / chances
    }
    base.update(overrides or {})
    for idx, value in base.items():
        row[idx] = value
    return row


def _write_fake_js(cache_dir, filename, rows):
    payload = "var matchmx = " + json.dumps(rows) + ";\n"
    (cache_dir / filename).write_text(payload, encoding="utf-8")


class TestWtaTaLoader:
    def test_winner_view_mapping(self, tmp_path):
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [_row()])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])
        frame = load_wta_ta_stats(cache_dir=tmp_path)
        assert len(frame) == 1
        m = frame.iloc[0]
        assert m["winner_name"] == "Test Alpha"
        assert m["loser_name"] == "Test Beta"
        assert m["surface"] == "Hard"
        # winner breaks = loser's failed saves: 6 chances - 2 saved = 4
        assert m["win_break_points_converted"] == 4
        # loser breaks = winner's failed saves: 5 chances - 3 saved = 2
        assert m["los_break_points_converted"] == 2
        assert m["win_service_games_played"] == 10
        assert m["series_category_id"] == "wta_tour"

    def test_loser_only_view_is_inverted(self, tmp_path):
        """Match where only the LOSER is in the leaderboard pool."""
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [_row(
            {4: "L", 5: "Test Gamma", 12: "Test Delta",
             33: "9", 34: "1", 35: "4",     # Gamma (loser) box
             42: "11", 43: "4", 44: "5"}    # Delta (winner) box
        )])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])
        frame = load_wta_ta_stats(cache_dir=tmp_path)
        assert len(frame) == 1
        m = frame.iloc[0]
        assert m["winner_name"] == "Test Delta"
        assert m["loser_name"] == "Test Gamma"
        assert m["win_service_games_played"] == 11
        # winner Delta breaks = Gamma chances (4) - Gamma saved (1) = 3
        assert m["win_break_points_converted"] == 3
        # loser Gamma breaks = Delta chances (5) - Delta saved (4) = 1
        assert m["los_break_points_converted"] == 1

    def test_bjk_cup_and_125s_dropped(self, tmp_path):
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [
            _row({3: "D"}),   # BJK Cup — team event
            _row({3: "W"}),   # WTA 125 — challenger level
            _row({3: "G"}),   # Grand Slam — kept
        ])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])
        frame = load_wta_ta_stats(cache_dir=tmp_path)
        assert len(frame) == 1

    def test_winner_view_wins_dedup(self, tmp_path):
        match_w = _row()
        match_l = _row({4: "L", 5: "Test Beta", 12: "Test Alpha",
                        33: "10", 34: "2", 35: "6", 42: "10", 43: "3", 44: "5"})
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [match_w, match_l])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])
        frame = load_wta_ta_stats(cache_dir=tmp_path)
        assert len(frame) == 1
