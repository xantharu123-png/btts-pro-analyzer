from copy import deepcopy

import pytest

from tennis.serve_model import ServeAdmissionDiagnostics, ServeReturnModel


def valid_row():
    return {
        "id": "2026-999-a-b-R32",
        "tournament_id": "2026-999",
        "tourney_date": "2026-03-02",
        "winner_name": "Alpha A",
        "loser_name": "Beta B",
        "winner_key": "alpha a",
        "loser_key": "beta b",
        "surface": "Hard",
        "indoor_outdoor": "Outdoor",
        "win_service_games_played": 12.0,
        "win_return_games_played": 10.0,
        "win_break_points_converted": 2.0,
        "los_break_points_converted": 1.0,
        "los_service_games_played": 10.0,
        "los_return_games_played": 12.0,
    }


def fawcett_source_row():
    """Smallest real-seed reproduction, with no raw-row data beyond the contract."""
    row = valid_row()
    row.update({
        "id": "2018-560-v717-f974-Q1",
        "tournament_id": "2018-560",
        "tourney_date": "2018-08-27",
        "winner_name": "Alexey Vatutin",
        "loser_name": "Tom Fawcett",
        "winner_key": "vatutin a",
        "loser_key": "fawcett t",
        "win_service_games_played": 0.0,
        "win_return_games_played": 0.0,
        "win_break_points_converted": 6.0,
        "los_break_points_converted": 4.0,
        "los_service_games_played": 0.0,
        "los_return_games_played": 0.0,
    })
    return row


def test_real_zero_denominator_row_is_skipped_atomically_with_provenance():
    model = ServeReturnModel(split_indoor=True)
    diagnostics = ServeAdmissionDiagnostics()

    assert model.update_from_match_row_if_valid(
        fawcett_source_row(), diagnostics=diagnostics
    ) is False

    assert model.to_payload()["rows"] == []
    assert diagnostics.as_dict() == {
        "admitted": 0,
        "skipped": 1,
        "admitted_match_count": 0,
        "skipped_match_count": 1,
        "admitted_tournament_count": 0,
        "skipped_tournament_count": 1,
        "unknown_match_identity": {"admitted_rows": 0, "skipped_rows": 0},
        "unknown_tournament_identity": {"admitted_rows": 0, "skipped_rows": 0},
        "unknown_year": {"admitted_rows": 0, "skipped_rows": 0},
        "reasons": {"nonpositive_game_denominator": 1},
        "admitted_years": {},
        "skipped_years": {"2018": 1},
        "skipped_matches": {"2018-560-v717-f974-Q1": 1},
        "skipped_tournaments": {"2018-560": 1},
    }


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("win_service_games_played", None, "missing_count"),
        ("win_service_games_played", "12", "non_numeric_count"),
        ("win_service_games_played", True, "non_numeric_count"),
        ("win_service_games_played", float("nan"), "nonfinite_count"),
        ("win_service_games_played", float("inf"), "nonfinite_count"),
        ("win_service_games_played", -1.0, "negative_count"),
        ("win_service_games_played", 12.5, "fractional_count"),
        ("win_return_games_played", 0.0, "nonpositive_game_denominator"),
        ("win_break_points_converted", 11.0, "breaks_exceed_games"),
        ("los_break_points_converted", 13.0, "breaks_exceed_games"),
    ],
)
def test_bad_bilateral_counts_skip_the_whole_row(field, value, reason):
    model = ServeReturnModel()
    diagnostics = ServeAdmissionDiagnostics()
    row = valid_row()
    row[field] = value

    assert model.update_from_match_row_if_valid(row, diagnostics=diagnostics) is False

    # Even an invalid loser-side/conceded-break field must not leave a winner half-update.
    assert model.to_payload()["rows"] == []
    assert diagnostics.as_dict()["reasons"] == {reason: 1}
    assert diagnostics.as_dict()["skipped"] == 1


def test_valid_admitted_update_is_payload_identical_to_default_path():
    row = valid_row()
    default_model = ServeReturnModel(split_indoor=True)
    admitted_model = ServeReturnModel(split_indoor=True)
    diagnostics = ServeAdmissionDiagnostics()

    default_model.update_from_match_row(deepcopy(row))
    assert admitted_model.update_from_match_row_if_valid(
        deepcopy(row), diagnostics=diagnostics
    ) is True

    assert admitted_model.to_payload() == default_model.to_payload()
    assert diagnostics.as_dict() == {
        "admitted": 1,
        "skipped": 0,
        "admitted_match_count": 1,
        "skipped_match_count": 0,
        "admitted_tournament_count": 1,
        "skipped_tournament_count": 0,
        "unknown_match_identity": {"admitted_rows": 0, "skipped_rows": 0},
        "unknown_tournament_identity": {"admitted_rows": 0, "skipped_rows": 0},
        "unknown_year": {"admitted_rows": 0, "skipped_rows": 0},
        "reasons": {},
        "admitted_years": {"2026": 1},
        "skipped_years": {},
        "skipped_matches": {},
        "skipped_tournaments": {},
    }


def test_diagnostics_count_distinct_events_and_disclose_unknown_provenance():
    diagnostics = ServeAdmissionDiagnostics()
    model = ServeReturnModel()
    first = valid_row()
    second = valid_row()
    second["id"] = "2026-999-c-d-R16"
    unknown = valid_row()
    unknown.pop("id")
    unknown.pop("tournament_id")
    unknown["tourney_date"] = "not-a-date"

    assert model.update_from_match_row_if_valid(first, diagnostics=diagnostics)
    assert model.update_from_match_row_if_valid(second, diagnostics=diagnostics)
    assert model.update_from_match_row_if_valid(unknown, diagnostics=diagnostics)

    summary = diagnostics.as_dict()
    assert summary["admitted"] == 3
    assert summary["admitted_match_count"] == 2
    assert summary["admitted_tournament_count"] == 1
    assert summary["unknown_match_identity"] == {"admitted_rows": 1, "skipped_rows": 0}
    assert summary["unknown_tournament_identity"] == {"admitted_rows": 1, "skipped_rows": 0}
    assert summary["admitted_years"] == {"2026": 2}
    assert summary["unknown_year"] == {"admitted_rows": 1, "skipped_rows": 0}
