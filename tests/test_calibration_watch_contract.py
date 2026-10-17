"""The watchdog must not certify an unobserved format or a different joint law.

Mutations caught: defaulting missing format to Bo3; scoring production v2 with
the unanchored v1 simulator; admitting Bo5 results to Bo3 side-market buckets.
Only the external historical source is replaced; serve fitting stays real.
"""
import pandas as pd
import pytest

from tennis import calibration_watch as watch


def _row(day, **metadata):
    return dict(tourney_date=pd.Timestamp(day), winner_name="Alpha A",
        loser_name="Beta B", surface="Hard", indoor_outdoor="Outdoor",
        series_category_id="atp250", match_ret="", winner_sets_won=2,
        loser_sets_won=0, winner_games_won=12, loser_games_won=6,
        win_service_games_played=10, win_return_games_played=10,
        los_service_games_played=10, los_return_games_played=10,
        win_break_points_converted=3, los_break_points_converted=1, **metadata)


def _history(monkeypatch, *observations):
    rows = [_row(f"2023-12-{i:02d}") for i in range(1, 11)]
    rows.extend(observations)
    monkeypatch.setattr(watch, "load_atp_stats", lambda *a: pd.DataFrame(rows))


def test_unknown_format_is_not_silently_scored_as_best_of_three(monkeypatch):
    _history(monkeypatch, _row("2024-02-01"))
    result = watch.collect_calibration()
    assert result["n_scored"] == 0
    assert result["skipped"] == {"format_not_observed": 1}


def test_production_joint_law_is_not_measured_with_legacy_unanchored_estimates(monkeypatch):
    _history(monkeypatch, _row("2024-02-01", best_of=3))
    result = watch.run_watch()
    assert result["n_scored"] == 0
    assert result["status"] == "unavailable"
    assert result["model_version"] == "serve-points-joint-v2"
    assert result["skipped"] == {"actual_joint_original_unavailable": 1}
    assert result["production_model_certified"] is False


def test_bo5_result_is_not_scored_against_bo3_side_market_outcomes(monkeypatch):
    row = _row("2024-02-01", best_of=5)
    row.update(winner_sets_won=3, loser_sets_won=0, winner_games_won=18)
    _history(monkeypatch, row)
    result = watch.collect_calibration()
    assert result["n_scored"] == 0


def test_explicit_legacy_analysis_keeps_only_observed_bo3_results(monkeypatch):
    _history(monkeypatch, _row("2024-02-01", best_of=3),
        _row("2024-02-02", best_of=5), _row("2024-02-03"))
    result = watch.run_watch(model_version="hold-proxy-v1")
    assert result["n_scored"] == 1
    assert result["model_version"] == "hold-proxy-v1"
    assert result["production_model_certified"] is False
    assert result["skipped"] == {
        "side_market_format_unsupported": 1, "format_not_observed": 1}
    assert result["status"] == "insufficient"


def test_legacy_observed_bo3_buckets_use_the_actual_two_set_outcome(monkeypatch):
    _history(monkeypatch, _row("2024-02-01", best_of=3))
    result = watch.collect_calibration(model_version="hold-proxy-v1")
    assert result["n_scored"] == 1
    observations = {market: values for (market, _), values in result["buckets"].items()}
    assert len(observations) == 5
    assert observations["over_2_5_sets"][0::2] == [1, 0.0]
    assert observations["under_2_5_sets"][0::2] == [1, 1.0]


@pytest.mark.parametrize("best_of", [True, "3", 4, 3.5])
def test_invalid_format_metadata_is_not_coerced_into_bo3(monkeypatch, best_of):
    _history(monkeypatch, _row("2024-02-01", best_of=best_of))
    result = watch.collect_calibration(model_version="hold-proxy-v1")
    assert result["n_scored"] == 0
    assert result["skipped"] == {"format_invalid": 1}


def test_bo3_metadata_cannot_certify_a_three_set_winner(monkeypatch):
    row = _row("2024-02-01", best_of=3)
    row.update(winner_sets_won=3)
    _history(monkeypatch, row)
    result = watch.collect_calibration(model_version="hold-proxy-v1")
    assert result["n_scored"] == 0
    assert result["skipped"] == {"score_format_conflict": 1}


def test_unknown_simulator_contract_is_rejected_before_source_reads(monkeypatch):
    def no_source(*a):
        pytest.fail("unsupported simulator contract reached source IO")

    monkeypatch.setattr(watch, "load_atp_stats", no_source)
    with pytest.raises(ValueError, match="model version"):
        watch.run_watch(model_version="unknown")
