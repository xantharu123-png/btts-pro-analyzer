"""Offline tests for the Tennis Abstract WTA box-score loader."""

from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from tennis import data_loader
from tennis.data_loader import add_normalized_names, load_wta_ta_stats
from tennis.serve_model import ServeReturnModel


def _row(overrides=None):
    row = [""] * 45
    base = {
        0: "20250110", 1: "Auckland", 2: "Hard", 3: "I", 4: "W",
        5: "Test Alpha", 9: "R32", 12: "Test Beta", 26: "97",
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
        assert m["match_duration"] == 97
        assert m["match_duration_state"] == "available"
        assert m["match_duration_source"] == "tennis_abstract_matchmx"
        assert m["match_duration_coverage"] == "wta_leaderboard_pool"
        assert "actual_end_at" not in frame.columns

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
        assert m["match_duration"] == 97
        assert m["match_duration_state"] == "available"

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

    @pytest.mark.parametrize(("native", "minutes", "state"), [
        ("", None, "missing"),
        (None, None, "missing"),
        ("0", None, "invalid"),
        (0, None, "invalid"),
        ("-4", None, "invalid"),
        (-4, None, "invalid"),
        ("97.5", None, "invalid"),
        (97.5, None, "invalid"),
        (float("nan"), None, "invalid"),
        (float("inf"), None, "invalid"),
        (True, None, "invalid"),
        ("n/a", None, "invalid"),
        (97, 97, "available"),
        (97.0, 97, "available"),
        ("97", 97, "available"),
    ])
    def test_duration_parser_accepts_only_positive_whole_minutes(self, native, minutes, state):
        parser = getattr(data_loader, "_ta_duration", None)
        assert callable(parser), "Tennis Abstract duration parser is missing"
        assert parser(native) == (minutes, state)

    @pytest.mark.parametrize(("native", "state"), [
        ("", "missing"),
        ("0", "invalid"),
        ("-4", "invalid"),
        ("97.5", "invalid"),
        ("NaN", "invalid"),
        ("Infinity", "invalid"),
        ("True", "invalid"),
        ("n/a", "invalid"),
    ])
    def test_unavailable_duration_does_not_drop_boxscore(self, tmp_path, native, state):
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [_row({26: native})])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])

        frame = load_wta_ta_stats(cache_dir=tmp_path)

        assert len(frame) == 1
        assert pd.isna(frame.iloc[0]["match_duration"])
        assert frame.iloc[0]["match_duration_state"] == state
        assert frame.iloc[0]["win_service_games_played"] == 10

    def test_equal_duplicate_durations_preserve_one_winner_precedence_match(self, tmp_path):
        winner_view = _row({26: "97"})
        loser_view = _row({4: "L", 5: "Test Beta", 12: "Test Alpha", 26: "97",
                            33: "10", 34: "2", 35: "6", 42: "12", 43: "3", 44: "5"})
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [loser_view, winner_view])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])

        frame = load_wta_ta_stats(cache_dir=tmp_path)

        assert len(frame) == 1
        assert frame.iloc[0]["match_duration"] == 97
        assert frame.iloc[0]["match_duration_state"] == "available"
        assert frame.iloc[0]["win_service_games_played"] == 10

    def test_conflicting_durations_do_not_choose_either_view(self, tmp_path):
        winner_view = _row({26: "97"})
        loser_view = _row({4: "L", 5: "Test Beta", 12: "Test Alpha", 26: "101",
                            33: "10", 34: "2", 35: "6", 42: "12", 43: "3", 44: "5"})
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [loser_view, winner_view])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])

        frame = load_wta_ta_stats(cache_dir=tmp_path)

        assert len(frame) == 1
        assert pd.isna(frame.iloc[0]["match_duration"])
        assert frame.iloc[0]["match_duration_state"] == "conflicting"
        assert frame.iloc[0]["win_service_games_played"] == 10

    def test_valid_duration_survives_missing_winner_view_with_partial_coverage(self, tmp_path):
        winner_view = _row({26: ""})
        loser_view = _row({4: "L", 5: "Test Beta", 12: "Test Alpha", 26: "97",
                            33: "10", 34: "2", 35: "6", 42: "12", 43: "3", 44: "5"})
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [loser_view, winner_view])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])

        frame = load_wta_ta_stats(cache_dir=tmp_path)

        assert len(frame) == 1
        assert frame.iloc[0]["match_duration"] == 97
        assert frame.iloc[0]["match_duration_state"] == "available"
        assert frame.iloc[0]["match_duration_coverage"] == "wta_leaderboard_pool_partial"
        assert frame.iloc[0]["win_service_games_played"] == 10

    def test_duration_from_incomplete_boxscore_view_is_still_reconciled(self, tmp_path):
        winner_view = _row({26: "", 33: ""})
        loser_view = _row({4: "L", 5: "Test Beta", 12: "Test Alpha", 26: "97",
                            33: "10", 34: "2", 35: "6", 42: "12", 43: "3", 44: "5"})
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [loser_view, winner_view])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])

        frame = load_wta_ta_stats(cache_dir=tmp_path)

        assert len(frame) == 1
        assert frame.iloc[0]["match_duration"] == 97
        assert frame.iloc[0]["match_duration_state"] == "available"
        assert frame.iloc[0]["match_duration_coverage"] == "wta_leaderboard_pool_partial"
        assert frame.iloc[0]["win_service_games_played"] == 12

    def test_conflicting_duration_from_incomplete_boxscore_view_is_not_hidden(self, tmp_path):
        winner_view = _row({26: "101", 33: ""})
        loser_view = _row({4: "L", 5: "Test Beta", 12: "Test Alpha", 26: "97",
                            33: "10", 34: "2", 35: "6", 42: "12", 43: "3", 44: "5"})
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [loser_view, winner_view])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])

        frame = load_wta_ta_stats(cache_dir=tmp_path)

        assert len(frame) == 1
        assert pd.isna(frame.iloc[0]["match_duration"])
        assert frame.iloc[0]["match_duration_state"] == "conflicting"
        assert frame.iloc[0]["win_service_games_played"] == 12

    def test_invalid_companion_takes_precedence_over_one_valid_duration(self, tmp_path):
        winner_view = _row({26: "n/a"})
        loser_view = _row({4: "L", 5: "Test Beta", 12: "Test Alpha", 26: "97",
                            33: "10", 34: "2", 35: "6", 42: "12", 43: "3", 44: "5"})
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [loser_view, winner_view])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])

        frame = load_wta_ta_stats(cache_dir=tmp_path)

        assert len(frame) == 1
        assert pd.isna(frame.iloc[0]["match_duration"])
        assert frame.iloc[0]["match_duration_state"] == "invalid"
        assert frame.iloc[0]["match_duration_coverage"] == "wta_leaderboard_pool_partial"

    def test_optional_duration_metadata_does_not_change_serve_state_or_prediction(self, tmp_path):
        _write_fake_js(tmp_path, "wta_top50_leadersource.js", [_row({26: "97"})])
        _write_fake_js(tmp_path, "wta_51_100_leadersource.js", [])
        observed = add_normalized_names(load_wta_ta_stats(cache_dir=tmp_path),
                                        "winner_name", "loser_name").iloc[0].to_dict()
        legacy = {name: value for name, value in observed.items()
                  if name not in {"match_duration", "match_duration_state",
                                  "match_duration_source", "match_duration_coverage"}}
        current_model = ServeReturnModel(half_life_days=None)
        legacy_model = ServeReturnModel(half_life_days=None)

        current_model.update_from_match_row(observed)
        legacy_model.update_from_match_row(legacy)

        assert current_model.to_payload() == legacy_model.to_payload()
        current = current_model.expected_hold_probabilities("test alpha", "test beta", "Hard")
        previous = legacy_model.expected_hold_probabilities("test alpha", "test beta", "Hard")
        assert current == previous
        assert all(math.isfinite(value) for value in current)
