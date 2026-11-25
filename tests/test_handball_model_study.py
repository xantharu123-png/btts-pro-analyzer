from datetime import datetime, timezone
import json
from math import log
import sys
from zoneinfo import ZoneInfo

import pytest


def _at(day):
    return datetime.fromisoformat(f"{day}T12:00:00+00:00")


def _game(id_, day, scores=(30, 30), teams=(1, 2)):
    return (id_, _at(day).isoformat(), *teams, *scores)


def _archive(rows, observed="2027-03-03"):
    return {"version": 1, "observed_at": _at(observed).isoformat(), "games": rows}


def _evaluate(archive, as_of="2027-03-04"):
    from handball_model_study import evaluate_study_input

    return evaluate_study_input(
        archive, as_of=_at(as_of), season=2026, league_clock=ZoneInfo("Europe/Berlin"),
    )


def _balanced_warmup():
    pairs = [(home, away) for home in range(1, 5) for away in range(1, 5) if home != away]
    return [_game(i, "2027-01-01", teams=teams) for i, teams in enumerate(pairs * 4, start=1)]


def test_weighted_variant_can_follow_a_reversal_without_changing_the_incumbent():
    from handball_pilot_model import predict_1x2

    rows = [(1, 2, 36, 30)] * 20 + [(2, 1, 30, 36)] * 20
    rows += [(2, 1, 36, 30)] * 4 + [(1, 2, 30, 36)] * 4
    incumbent = predict_1x2(rows, home_id=1, away_id=2)
    assert incumbent["home"] == pytest.approx(0.7622791100605094, rel=1e-13)
    assert predict_1x2(rows, home_id=1, away_id=2, weights=[1.] * 48) == incumbent
    weighted = predict_1x2(rows, home_id=1, away_id=2, weights=[0.125] * 40 + [1.] * 8)
    assert weighted["away"] > weighted["home"]


@pytest.mark.parametrize("weights", [[1.] * 47, [1.] * 47 + [0.], [1.] * 47 + [float("nan")]])
def test_bad_study_weights_do_not_silently_fall_back(weights):
    from handball_pilot_model import predict_1x2

    rows = [(1, 2, 30, 30)] * 24 + [(2, 1, 30, 30)] * 24
    assert predict_1x2(rows, home_id=1, away_id=2, weights=weights) is None


def test_same_day_results_do_not_train_each_other_and_brier_uses_the_common_cohort():
    warmup = _balanced_warmup()
    report = _evaluate(_archive([
        _game(51, "2027-02-02", (30, 45)),
        *reversed(warmup),
        _game(50, "2027-02-02", (45, 30)),
        _game(52, "2027-02-03", (30, 30), (1, 5)),  # Team 5 has no history.
    ]))
    assert report["status"] == "collecting"
    assert report["test"] == {"eligible": 2, "fixtures": 3, "weeks": 1, "draws": 0}
    assert report["calibration"]["eligible"] == 0
    assert report["draw_offset"] is None
    baseline = report["scores"]["v1"]
    # Equal teams and margin SD=4: p(home)=p(away)=0.4502617752.
    assert baseline["brier_1x2"] == pytest.approx(.5148433460555052)
    assert baseline["brier_draw"] == pytest.approx(.009895564037003434)
    assert baseline["log_loss"] == pytest.approx(-log(.4502617752))
    assert report["scores"]["form_90d"] == pytest.approx(baseline)
    assert report["scores"]["draw_calibrated"] is None
    assert report["paired_intervals_97_5"] == {"form_90d_brier_1x2": None, "draw_calibrated_brier_draw": None}


def test_draw_offset_uses_only_calibration_and_keeps_test_sample_size_paired():
    calibration_days = ["2027-01-04", "2027-01-11", "2027-01-18", "2027-01-25"]
    calibration = [_game(100 + i, day) for i, day in enumerate(calibration_days * 10)]
    test_days = ["2027-02-01", "2027-02-08", "2027-02-15", "2027-02-22", "2027-03-01", "2027-03-08"]
    test = [_game(200 + i, day) for i, day in enumerate(test_days * 10)]
    all_draw = _evaluate(_archive(_balanced_warmup() + calibration + test, "2027-03-09"), "2027-03-10")
    first_test_flipped = [(*test[0][:-2], 34, 31), *test[1:]]
    mixed = _evaluate(_archive(_balanced_warmup() + calibration + first_test_flipped, "2027-03-09"), "2027-03-10")
    assert all_draw["status"] == "descriptive"
    assert all_draw["calibration"]["eligible"] == 40
    assert all_draw["test"] == {"eligible": 60, "fixtures": 60, "weeks": 6, "draws": 60}
    assert mixed["test"]["draws"] == 59
    assert all_draw["draw_offset"] == mixed["draw_offset"]
    assert all_draw["draw_offset"] > 0
    assert all_draw["paired_improvement"]["draw_calibrated"]["brier_draw"] > 0
    bands = all_draw["paired_intervals_97_5"]
    assert bands["form_90d_brier_1x2"] == [0., 0.]
    improvement = all_draw["paired_improvement"]["draw_calibrated"]["brier_draw"]
    assert bands["draw_calibrated_brier_draw"] == pytest.approx([improvement, improvement])
    mixed_bands = mixed["paired_intervals_97_5"]
    low, high = mixed_bands["draw_calibrated_brier_draw"]
    assert low < high
    assert mixed_bands == _evaluate(
        _archive(list(reversed(_balanced_warmup() + calibration + first_test_flipped)), "2027-03-09"), "2027-03-10",
    )["paired_intervals_97_5"]


def test_draw_calibration_preserves_home_to_away_odds_ratio_and_probability_mass():
    from handball_model_study import _recalibrate_draw

    moved = _recalibrate_draw({"home": .60, "draw": .10, "away": .30}, log(2))
    assert moved == pytest.approx({"home": 6 / 11, "draw": 2 / 11, "away": 3 / 11})
    assert sum(moved.values()) == pytest.approx(1.)


@pytest.mark.parametrize("variant", ["duplicate", "after_archive", "naive_time", "bad_team"])
def test_corrupt_archive_fails_closed(variant):
    rows = [_game(1, "2027-02-02")]
    if variant == "duplicate":
        rows *= 2
    elif variant == "after_archive":
        rows = [_game(1, "2027-03-04")]
    elif variant == "naive_time":
        rows = [(1, "2027-02-02T12:00:00", 1, 2, 30, 30)]
    elif variant == "bad_team":
        rows = [_game(1, "2027-02-02", teams=(1, True))]
    assert _evaluate(_archive(rows))["status"] == "unavailable"


def test_archive_after_as_of_cannot_be_used_as_historical_evidence():
    report = _evaluate(_archive(_balanced_warmup(), "2027-03-03"), "2027-03-02")
    assert report["status"] == "unavailable"


def test_reader_uses_only_compact_scores_and_does_not_touch_files(tmp_path):
    from handball_model_study import read_study

    before = read_study(as_of=datetime.now(timezone.utc), directory=tmp_path)
    assert before["status"] == "unavailable"
    assert list(tmp_path.iterdir()) == []
    archive = _archive(_balanced_warmup())
    payload = json.dumps({"version": 3, "study_input": archive, "forecasts": {"odds": "not consulted"}})
    path = tmp_path / "handball_pilot_2026.json"
    path.write_text(payload, encoding="utf-8")
    report = read_study(as_of=_at("2027-03-04"), directory=tmp_path)
    assert report["status"] == "collecting"
    assert report["leagues"]["DE"]["input_games"] == 48
    assert report["leagues"]["DK"]["status"] == "unavailable"
    assert path.read_text(encoding="utf-8") == payload


def test_reader_does_not_echo_unvalidated_archive_fields(tmp_path):
    from handball_model_study import read_study

    path = tmp_path / "handball_pilot_2026.json"
    path.write_text(json.dumps({
        "study_input": {"status": "unavailable", "untrusted_field": "not for stdout"},
    }), encoding="utf-8")
    result = read_study(as_of=_at("2027-03-04"), directory=tmp_path)
    assert result["leagues"]["DE"] == {"status": "unavailable", "reason": "invalid_or_future_study_input"}


def test_cli_does_not_turn_invalid_as_of_into_current_time(monkeypatch, capsys):
    from handball_model_study import main

    monkeypatch.setattr(sys, "argv", ["handball_model_study", "--as-of", "2027-03-04T00:00:00"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert not capsys.readouterr().out
