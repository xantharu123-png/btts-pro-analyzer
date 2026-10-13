"""Synthetic, offline causal and one-set settlement regressions.

Mutations caught: ingesting tournament-start rows; inventing a completed set
or winner; dropping provider retirement evidence; scoring unknown/void as win.
"""
from datetime import datetime, timezone
from dataclasses import replace
import sqlite3
import json

import pandas as pd
import pytest

from scripts import tennis_daily as daily
from tennis import backtest, data_loader, shadow
from test_tennis_fixture_metadata import _Prediction
from streamlit.testing.v1 import AppTest


def market(day, tournament="Masters", comment="Completed", **sets):
    return dict(Date=pd.Timestamp(day), Tournament=tournament, Surface="Hard",
                Court="Outdoor", **{"Best of": 3}, Winner="Alpha", Loser="Beta",
                Comment=comment, PSW=2., PSL=2., **sets)


def stats(start="2026-05-01", finish="2026-05-12", winner="Alpha", loser="Beta"):
    return dict(tourney_date=pd.Timestamp(start), finish_dtm=finish.replace("-", "") if finish else None,
                winner_name=winner, loser_name=loser, surface="Hard", match_ret="",
                series_category_id="atp250")


def replay(monkeypatch, odds, rows):
    monkeypatch.setattr(backtest, "load_market_odds", lambda *a, **k: pd.DataFrame(odds))
    monkeypatch.setattr(backtest, "load_atp_stats", lambda *a, **k: pd.DataFrame(rows))
    return backtest.run_backtest((2026,), stats_years=(2026,), serve_weight=0.,
                                 recalibrate=False, min_elo_matches=0)


@pytest.mark.parametrize("tournament", ["Masters", "French Open", "Roland Garros"])
def test_final_result_cannot_change_its_own_forecast(monkeypatch, tournament):
    # 11-day Masters / French Open alias defeated the old 10-day start buffer.
    a = replay(monkeypatch, [market("2026-05-12", tournament)], [stats()]).rows[0]
    b = replay(monkeypatch, [market("2026-05-12", tournament)],
               [stats(winner="Beta", loser="Alpha")]).rows[0]
    assert a.p_model == b.p_model == .5


@pytest.mark.parametrize("finish", [None, "2026-04-30"])
def test_unknown_or_impossible_tournament_finish_never_enters_history(monkeypatch, finish):
    row = replay(monkeypatch, [market("2026-09-01")], [stats(finish=finish)]).rows[0]
    assert row.p_model == .5


def test_date_only_finish_waits_until_all_timezones_have_finished_that_day(monkeypatch):
    report = replay(monkeypatch, [market("2026-05-13"), market("2026-05-15")], [stats()])
    assert report.rows[0].p_model == .5
    assert report.rows[1].p_model > .5


def test_verified_aware_availability_is_strictly_before_aware_decision(monkeypatch):
    row = {**stats(), "stats_available_at": "2026-05-12T15:00:00+02:00"}
    report = replay(monkeypatch, [market("2026-05-12T12:59:59Z"),
        market("2026-05-12T13:00:00Z"), market("2026-05-12T13:00:01Z")], [row])
    assert [r.p_model for r in report.rows[:2]] == [.5, .5]
    assert report.rows[2].p_model > .5


@pytest.mark.parametrize("termination,winner,completed,want,pnl", [
    ("normal", "Alpha", None, "standing", 1.),
    ("walkover", None, None, "void", 0.),
    ("retirement", "Alpha", 0, "void", 0.),
    ("retirement", "Alpha", 1, "standing", 1.),
    ("retirement", "Beta", 1, "standing", -1.),
    ("retirement", "Alpha", None, "non_evaluable", None),
    ("retirement", None, 1, "non_evaluable", None),
])
def test_shared_one_set_policy_never_fabricates_missing_evidence(
        tmp_path, monkeypatch, termination, winner, completed, want, pnl):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "shadow.db")
    prediction_id = shadow.store_prediction("2026-05-12", "ATP", "Masters", _Prediction())
    with shadow._connect() as connection:
        connection.execute("UPDATE predictions SET recommended_side='A', odds_a=2., odds_b=2. WHERE id=?", (prediction_id,))
    shadow.settle(prediction_id, winner, termination=termination, ret_set=completed,
                  result_observed_at="2026-05-12T18:00:00Z")
    with sqlite3.connect(shadow.DB_PATH) as connection:
        result = connection.execute("SELECT settlement_status,pnl,actual_winner,ret_set FROM predictions WHERE id=?", (prediction_id,)).fetchone()
    assert result == (want, pnl, winner, completed)


@pytest.mark.parametrize("completed,status", [(0, "void"), (1, "standing"), (None, "non_evaluable")])
def test_backtest_retirement_uses_one_set_rule_not_blanket_exclusion(monkeypatch, completed, status):
    sets = {} if completed is None else dict(Wsets=completed, Lsets=0)
    report = replay(monkeypatch, [market("2026-05-12", comment="Retired", **sets)], [stats()])
    assert len(report.rows) == 1
    assert report.rows[0].settlement_status == status
    summary = report.policy_summary(probability_haircut=0., minimum_expected_roi=0., require_serve_model=False)
    assert summary["roi"] == ({"void": 0., "standing": 1., "non_evaluable": None}[status])


def test_retirement_set_pair_cannot_disagree_with_completed_count(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "shadow.db")
    prediction_id = shadow.store_prediction("2026-05-12", "ATP", "Masters", _Prediction())
    with pytest.raises(ValueError, match="completed"):
        shadow.settle(prediction_id, "Alpha", termination="retirement", ret_set=0,
                      player_a_sets=1, player_b_sets=0)


def test_auto_retirement_keeps_native_winner_completed_sets_and_same_return(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "shadow.db")
    prediction_id = shadow.store_prediction("2026-05-12", "ATP", "Masters", _Prediction(),
        fixture_source="ESPN", provider_event_id="123")
    with shadow._connect() as connection:
        connection.execute("UPDATE predictions SET recommended_side='A', odds_a=2., odds_b=2. WHERE id=?", (prediction_id,))
    monkeypatch.setattr(daily, "fetch_results_espn", lambda *a: [dict(provider_event_id="123",
        player_a="Alpha", player_b="Beta", winner="Beta", winner_sets=0, loser_sets=1,
        termination="retirement", completed_sets=1, result_observed_at="2026-05-12T18:00:00Z")])
    assert daily.auto_settle_completed(today="2026-05-14") == 1
    with sqlite3.connect(shadow.DB_PATH) as connection:
        result = connection.execute("SELECT actual_winner,ret_set,player_a_sets,player_b_sets,pnl,settlement_status FROM predictions").fetchone()
    assert result == ("Beta", 1, 1, 0, -1., "standing")


def test_espn_retirement_uses_explicit_completed_set_flags_without_partial_score_guess(monkeypatch):
    comp = dict(id="123", date="2026-05-12T12:00:00Z",
        status={"type": {"state": "post", "completed": True, "name": "STATUS_RETIRED"}},
        competitors=[dict(athlete={"displayName": "Alpha"}, winner=False,
            linescores=[dict(value=6, winner=True), dict(value=2)]),
            dict(athlete={"displayName": "Beta"}, winner=True,
            linescores=[dict(value=3, winner=False), dict(value=3)])])
    monkeypatch.setattr(daily, "_fetch_espn_events", lambda *a: [dict(groupings=[
        dict(grouping={"slug": "mens-singles"}, competitions=[comp])])])
    result, = daily.fetch_results_espn("2026-05-12", "ATP")
    assert (result["winner"], result["winner_sets"], result["loser_sets"], result["completed_sets"]) == ("Beta", 0, 1, 1)
    comp["competitors"][0]["linescores"][0].pop("winner")
    comp["competitors"][1]["linescores"][0].pop("winner")
    unknown, = daily.fetch_results_espn("2026-05-12", "ATP")
    assert unknown["completed_sets"] is None


def test_settled_legacy_record_is_not_rescored(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "shadow.db")
    prediction_id = shadow.store_prediction("2026-05-12", "ATP", "Masters", _Prediction())
    with shadow._connect() as connection:
        connection.execute("UPDATE predictions SET settled=1,actual_winner=NULL,ret_flag=1,ret_set=NULL,pnl=0. WHERE id=?", (prediction_id,))
    with sqlite3.connect(shadow.DB_PATH) as connection:
        before = connection.execute("SELECT * FROM predictions").fetchall()
    with pytest.raises(ValueError, match="already settled"):
        shadow.settle(prediction_id, "Beta", ret=True, ret_set=1)
    with sqlite3.connect(shadow.DB_PATH) as connection:
        assert connection.execute("SELECT * FROM predictions").fetchall() == before


def _manual_app(path):
    from pathlib import Path
    from tennis import shadow
    import tennis_tab
    shadow.DB_PATH = Path(path)
    tennis_tab._render_settlement(shadow.pending_predictions())


@pytest.mark.parametrize("completed,winner,want,pnl", [
    ("Nicht beobachtet", "Nicht beobachtet", "non_evaluable", None),
    ("0", "Alpha", "void", 0.),
    ("1", "Beta", "standing", -1.),
])
def test_manual_retirement_uses_observed_evidence_not_set_number_guess(
        tmp_path, monkeypatch, completed, winner, want, pnl):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "shadow.db")
    prediction_id = shadow.store_prediction("2026-05-12", "ATP", "Masters", _Prediction())
    with shadow._connect() as connection:
        connection.execute("UPDATE predictions SET recommended_side='A', odds_a=2., odds_b=2. WHERE id=?", (prediction_id,))
    app = AppTest.from_function(_manual_app, args=(str(shadow.DB_PATH),)).run(timeout=60)
    assert not app.exception
    app.radio(key=f"settle_mode_{prediction_id}").set_value("Aufgabe (Retirement)").run(timeout=60)
    app.radio(key=f"settle_winner_{prediction_id}").set_value(winner)
    app.radio(key=f"settle_completed_{prediction_id}").set_value(completed)
    app.button(key=f"settle_btn_{prediction_id}").click().run(timeout=60)
    assert not app.exception
    with sqlite3.connect(shadow.DB_PATH) as connection:
        result = connection.execute("SELECT settlement_status,pnl,ret_set FROM predictions").fetchone()
    assert result == (want, pnl, None if completed == "Nicht beobachtet" else int(completed))


@pytest.mark.parametrize("invalid", ["not-a-time", "2026-05-01T00:00:00", None])
def test_invalid_explicit_availability_never_falls_back_to_finished_tournament(monkeypatch, invalid):
    row = {**stats(), "stats_available_at": invalid}
    assert replay(monkeypatch, [market("2026-09-01")], [row]).rows[0].p_model == .5


@pytest.mark.parametrize("decision,expected", [
    ("2026-05-13T11:59:59Z", .5), ("2026-05-13T12:00:00Z", .5),
    ("2026-05-13T12:00:01Z", .6805),
])
def test_date_only_finish_latest_midnight_boundary_is_exclusive(monkeypatch, decision, expected):
    assert replay(monkeypatch, [market(decision)], [stats()]).rows[0].p_model == expected


@pytest.mark.parametrize("finish,expected", [
    ("20260512", "2026-05-13T12:00:00Z"), ("", None), ("20260430", None),
])
def test_loader_preserves_actual_finish_and_never_invents_unknown_availability(
        tmp_path, monkeypatch, finish, expected):
    (tmp_path / "atp_tournaments.csv").write_text(
        "id,name,year,indoor_outdoor,surface,series_category_id,start_dtm,finish_dtm\n"
        f"2026-1,Masters,2026,Outdoor,Hard,atp250,20260501,{finish}\n", encoding="utf-8")
    (tmp_path / "atp_matches_2026.csv").write_text(
        "id,tournament_id,winner_name,loser_name\n1,2026-1,Alpha,Beta\n", encoding="utf-8")
    monkeypatch.setattr(data_loader.requests, "get", lambda *a, **k: pytest.fail("network not authorized"))
    loaded = data_loader.load_atp_stats((2026,), cache_dir=tmp_path)
    assert loaded.iloc[0].tourney_date == pd.Timestamp("2026-05-01")
    if expected is None:
        assert pd.isna(loaded.iloc[0].stats_available_at)
    else:
        assert loaded.iloc[0].stats_available_at == pd.Timestamp(expected)


def test_retirement_with_unknown_completed_sets_does_not_enter_healthy_brier(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "shadow.db")
    prediction_id = shadow.store_prediction("2026-05-12", "ATP", "Masters", _Prediction())
    shadow.settle(prediction_id, "Alpha", termination="retirement", ret_set=None)
    assert shadow.summary()["brier_samples"] == 0


@pytest.mark.parametrize("fields", [dict(ret_set=3), dict(player_a_sets=2, player_b_sets=2)])
def test_retirement_cannot_claim_impossible_completed_set_count(tmp_path, monkeypatch, fields):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "shadow.db")
    prediction_id = shadow.store_prediction("2026-05-12", "ATP", "Masters", _Prediction())
    with pytest.raises(ValueError, match="completed"):
        shadow.settle(prediction_id, "Alpha", termination="retirement", **fields)


@pytest.mark.parametrize("odds", [float("inf"), float("nan"), True])
def test_nonfinite_or_boolean_odds_never_manufacture_profit(odds):
    from tennis.settlement_policy import unit_return
    assert unit_return("standing", True, odds) is None


def test_void_is_zero_return_not_a_win_in_legacy_summary(monkeypatch):
    report = replay(monkeypatch, [market("2026-05-12", comment="Retired", Wsets=0, Lsets=0)], [stats()])
    row = report.summary().iloc[0]
    assert row["roi"] == 0.
    assert pd.isna(row["win_rate"])


def test_mixed_win_loss_void_hit_rate_excludes_void_without_changing_roi(monkeypatch):
    report = replay(monkeypatch, [market("2026-05-12")], [stats()])
    win = report.rows[0]
    report.rows = [win, replace(win, bet_won=False), replace(win, settlement_status="void")]
    row = report.summary().iloc[0]
    assert row["bets"] == 3
    assert row["win_rate"] == .5
    assert row["roi"] == 0.


def test_abnormal_only_report_has_no_healthy_calibration_metric(monkeypatch):
    report = replay(monkeypatch, [market("2026-05-12", comment="Retired", Wsets=1, Lsets=0)], [stats()])
    result = report.calibration()
    assert result["n"] == 0
    assert result["brier_cal"] is None


def test_auto_unknown_retirement_reports_non_evaluable_coverage(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(shadow, "DB_PATH", tmp_path / "shadow.db")
    prediction_id = shadow.store_prediction("2026-05-12", "ATP", "Masters", _Prediction(),
        fixture_source="ESPN", provider_event_id="123")
    monkeypatch.setattr(daily, "fetch_results_espn", lambda *a: [dict(provider_event_id="123",
        player_a="Alpha", player_b="Beta", winner=None, winner_sets=None, loser_sets=None,
        termination="retirement", result_observed_at="2026-05-12T18:00:00Z")])
    assert daily.auto_settle_completed(today="2026-05-14") == 1
    messages = [json.loads(line.split(": ", 1)[1]) for line in capsys.readouterr().out.splitlines()
                if line.startswith("Abrechnungsabdeckung: ")]
    assert messages == [{"reason": "non_evaluable_retirement", "prediction_id": prediction_id,
                         "winner_observed": False, "completed_sets_observed": False,
                         "payout_evaluated": False}]


def test_numeric_native_set_winner_flags_do_not_prove_completed_sets():
    assert daily._espn_completed_sets([
        {"linescores": [{"winner": 1}]}, {"linescores": [{"winner": 0}]},
    ]) == (None, None)


@pytest.mark.parametrize("malformed", [None, 6])
@pytest.mark.parametrize("side", [0, 1])
def test_malformed_native_set_entry_is_unknown_not_batch_failure(malformed, side):
    lines = [[{"winner": True}, {"winner": True}], [{"winner": False}, {"winner": False}]]
    lines[side][1] = malformed
    assert daily._espn_completed_sets([
        {"linescores": lines[0]}, {"linescores": lines[1]},
    ]) == (None, None)
