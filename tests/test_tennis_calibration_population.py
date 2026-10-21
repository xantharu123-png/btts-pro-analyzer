"""Calibrator population (Audit 2026-10-16 H3): fit on the betted population.

Contracts covered:
- ``in_betting_population`` selects exactly the rows the production gates
  (``predict_match``: Belag, Erfahrung, Aufschlag-Daten) and the policy replay
  (``policy_summary`` model gates) admit.
- Default ``calibration_population="all"`` reproduces the legacy fit
  (same parameters, same sample count) on a fixture.
- ``betting`` fits walk-forward without leakage: every row is predicted with
  parameters fitted only on betting rows dated strictly before it.
- ``calibration_only`` emits only the learning population when ``betting``.
- The experimental covariate calibrator recovers group slopes causally.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from tennis import backtest, predict
from tennis.backtest import (
    BacktestReport,
    BacktestRow,
    CovariateWalkForwardCalibrator,
    WalkForwardCalibrator,
    _logit,
    _sigmoid,
    in_betting_population,
)
from tennis.elo import SurfaceElo
from tennis.model_state import ModelState
from tennis.predict import predict_match
from tennis.serve_model import ServeReturnModel


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

AVAILABLE = "2025-01-01T00:00:00Z"
PLAYERS = {
    "A": "Alpha A", "B": "Beta B", "C": "Gamma C", "D": "Delta D",
    "E": "Echo E", "F": "Foxtrot F", "G": "Golf G", "H": "Hotel H",
}


def _boxscore(winner, loser, *, category="atp250"):
    return {
        "tourney_date": "2024-12-01", "stats_available_at": AVAILABLE, "tour": "ATP",
        "winner_name": PLAYERS[winner], "loser_name": PLAYERS[loser], "surface": "Hard",
        "indoor_outdoor": "Outdoor", "series_category_id": category, "match_ret": "",
        "win_service_games_played": 12., "win_return_games_played": 10.,
        "win_break_points_converted": 2., "los_break_points_converted": 1.,
        "los_service_games_played": 10., "los_return_games_played": 12.,
    }


def _stats_frame():
    rows = []
    rows += [_boxscore("A", "B") for _ in range(8)]                     # serve-rich, experienced
    rows += [_boxscore("C", "D") for _ in range(8)]                     # serve-rich, experienced
    rows += [_boxscore("E", "F", category="challenger") for _ in range(8)]  # Elo only, no serve plane
    rows += [_boxscore("G", "H") for _ in range(2)]                     # too little experience/serve
    return pd.DataFrame(rows)


# (winner, loser, surface, expected betting population)
CYCLE = [
    ("A", "B", "Hard", True),
    ("C", "D", "Hard", True),
    ("A", "B", "Clay", False),   # surface gate
    ("E", "F", "Hard", False),   # serve gate (challenger plane only)
    ("G", "H", "Hard", False),   # experience gate (and serve gate)
    ("A", "C", "Hard", True),
]


def _odds_frame(cycles=8):
    rows, day = [], pd.Timestamp("2025-02-01")
    for cycle in range(cycles):
        for winner, loser, surface, _ in CYCLE:
            if cycle % 2:
                winner, loser = loser, winner
            rows.append({
                "Date": day, "Tournament": "Test", "Surface": surface, "Court": "Outdoor",
                "Best of": 3, "Winner": PLAYERS[winner], "Loser": PLAYERS[loser],
                "Comment": "Completed", "PSW": 1.9, "PSL": 2.1,
            })
            day += pd.Timedelta(days=1)
    return pd.DataFrame(rows)


class _SmallPlatt(WalkForwardCalibrator):
    """Same algorithm, fixture-sized thresholds; refit after every row."""

    def __init__(self, min_samples: int = 8, refit_every: int = 1) -> None:
        super().__init__(min_samples=min_samples, refit_every=refit_every)


def _run(monkeypatch, **kw):
    monkeypatch.setattr(backtest, "load_market_odds", lambda *a, **k: _odds_frame())
    monkeypatch.setattr(backtest, "load_atp_stats", lambda *a, **k: _stats_frame())
    monkeypatch.setattr(backtest, "WalkForwardCalibrator", _SmallPlatt)
    return backtest.run_backtest(
        (2025,), stats_years=(2024,), tours=("atp",), serve_weight=0.3,
        min_elo_matches=5, **kw,
    )


def _replay(rows, population):
    """Reference walk-forward: predict before learning, learn only from ``population``."""
    cal = _SmallPlatt()
    expected = []
    for row in rows:
        expected.append(cal.predict(row.p_alpha_raw))
        if row.termination == "normal" and (population == "all" or row.betting_population):
            cal.add(row.p_alpha_raw, row.y_alpha)
    return expected


def _report_row(**overrides) -> BacktestRow:
    base = dict(
        date="2026-01-01", tour="ATP", surface="Hard", best_of=3, winner="W", loser="L",
        p_elo=0.6, p_serve=0.6, p_model=0.6, p_cal=0.6, p_market_alpha=0.5, edge_w=0., edge_l=0.,
        chosen_side="W", chosen_edge=0., chosen_odds=2., odds_w=2., odds_l=2., bet_won=True,
        gated=True, y_alpha=1, p_alpha=0.6, p_alpha_raw=0.6,
    )
    base.update(overrides)
    return BacktestRow(**base)


# ---------------------------------------------------------------------------
# filter == production gates
# ---------------------------------------------------------------------------

def _prediction_state() -> ModelState:
    elo, serve = SurfaceElo(), ServeReturnModel()
    for _ in range(25):
        elo.update("hero h", "grinder g", "Hard")
        elo.update("rookie r", "grinder g", "Hard")   # experienced, but no serve plane
        serve.update_from_match_row({
            "winner_key": "hero h", "loser_key": "grinder g", "winner_name": "Hero H.",
            "loser_name": "Grinder G.", "surface": "Hard",
            "win_service_games_played": 10, "win_return_games_played": 10,
            "win_break_points_converted": 3, "los_break_points_converted": 1,
            "los_service_games_played": 10, "los_return_games_played": 10,
            "win_break_points_saved": 2,
        })
    return ModelState(elo=elo, serve=serve, cal_a=1., cal_b=0., cal_samples=0,
                      built_at=time.time(), stats_through="2026-07-27", serve_weight=0.3)


@pytest.mark.parametrize("player_a,player_b,surface", [
    ("Hero H.", "Grinder G.", "Hard"),
    ("Hero H.", "Grinder G.", "Clay"),
    ("Rookie R.", "Grinder G.", "Hard"),
    ("Niemand N.", "Hero H.", "Hard"),
])
def test_filter_agrees_with_predict_match_model_gates(player_a, player_b, surface):
    pred = predict_match(_prediction_state(), player_a, player_b, surface, 3)
    gate = {g.name: g.passed for g in pred.gates}
    expected = gate["Belag"] and gate["Erfahrung"] and gate["Aufschlag-Daten"]
    serve_in_model = pred.context_evidence["model_inputs"]["serve_in_model"]
    assert in_betting_population(pred.surface, 0.5 if serve_in_model else None,
                                 gate["Erfahrung"]) is expected


def test_filter_covers_both_outcomes_and_shares_the_surface_constant():
    assert predict.ALLOWED_SURFACES == backtest.BETTING_SURFACES
    assert in_betting_population("Hard", 0.55, True)
    assert not in_betting_population("Clay", 0.55, True)
    assert not in_betting_population("Hard", None, True)
    assert not in_betting_population("Hard", float("nan"), True)
    assert not in_betting_population("Hard", 0.55, False)
    assert not in_betting_population(None, 0.55, True)


def test_filter_equals_policy_summary_model_gate_rows():
    rows = [
        _report_row(surface="Hard", p_serve=0.6, gated=True),
        _report_row(surface="Hard", p_serve=0.6, gated=True, odds_w=5.0),
        _report_row(surface="Clay", p_serve=0.6, gated=True),
        _report_row(surface="Hard", p_serve=None, gated=True),
        _report_row(surface="Hard", p_serve=0.6, gated=False),
        _report_row(surface="Grass", p_serve=None, gated=False),
    ]
    report = BacktestReport(rows=rows)
    selected = sum(in_betting_population(r.surface, r.p_serve, r.gated) for r in rows)
    replay = report.policy_summary(probability_haircut=0.0, minimum_expected_roi=0.0)
    assert selected == replay["model_gate_rows"] == 2


# ---------------------------------------------------------------------------
# run_backtest: flags, default behaviour, walk-forward without leakage
# ---------------------------------------------------------------------------

def test_rows_carry_population_flags_matching_the_fixture_design(monkeypatch):
    report = _run(monkeypatch)
    assert len(report.rows) == len(CYCLE) * 8
    flags = [r.betting_population for r in report.rows]
    assert flags == [expected for _ in range(8) for *_, expected in CYCLE]
    for row in report.rows:
        assert row.betting_population == in_betting_population(row.surface, row.p_serve, row.gated)
    assert sum(flags) == 24


def test_default_population_is_all_and_reproduces_legacy_walk_forward(monkeypatch):
    report = _run(monkeypatch)
    explicit = _run(monkeypatch, calibration_population="all")
    assert [r.p_alpha for r in report.rows] == [r.p_alpha for r in explicit.rows]
    expected = _replay(report.rows, "all")
    for row, value in zip(report.rows, expected):
        assert row.p_alpha == pytest.approx(value, abs=5e-4)
    # the legacy calibrator also learned from non-betting rows
    assert [r.calibrator_trained for r in report.rows][:8] == [False] * 8
    assert all(r.calibrator_trained for r in report.rows[8:])


def test_betting_population_learns_only_from_gated_rows_without_leakage(monkeypatch):
    report = _run(monkeypatch, calibration_population="betting")
    legacy = _run(monkeypatch)
    expected = _replay(report.rows, "betting")
    for row, value in zip(report.rows, expected):
        assert row.p_alpha == pytest.approx(value, abs=5e-4)
    # trained only once eight BETTING rows exist (cycle 3), later than legacy
    first_trained = next(i for i, r in enumerate(report.rows) if r.calibrator_trained)
    assert first_trained > next(i for i, r in enumerate(legacy.rows) if r.calibrator_trained)
    assert sum(r.betting_population for r in report.rows[:first_trained]) == 8
    # the two populations yield different parameters on betting rows
    assert any(
        a.p_alpha != b.p_alpha
        for a, b in zip(report.rows, legacy.rows) if a.betting_population and a.calibrator_trained
    )
    # explicit cutoff check: the last betting row is scored by a fit on
    # betting rows dated strictly before it, never including itself
    last = max(i for i, r in enumerate(report.rows) if r.betting_population)
    target = report.rows[last]
    before = _SmallPlatt()
    for row in report.rows[:last]:
        if row.betting_population and pd.Timestamp(row.date) < pd.Timestamp(target.date):
            before.add(row.p_alpha_raw, row.y_alpha)
    assert target.p_alpha == pytest.approx(before.predict(target.p_alpha_raw), abs=5e-4)
    params = (before.a, before.b)
    before.add(target.p_alpha_raw, target.y_alpha)
    assert (before.a, before.b) != params


def test_calibration_only_returns_only_the_learning_population(monkeypatch):
    everything = _run(monkeypatch, recalibrate=False, calibration_only=True)
    betting = _run(monkeypatch, recalibrate=False, calibration_only=True,
                   calibration_population="betting")
    assert len(everything.rows) == len(CYCLE) * 8
    assert len(betting.rows) == 24
    assert all(r.betting_population and r.has_serve and r.gated and r.surface == "Hard"
               for r in betting.rows)
    assert [r.p_alpha_raw for r in betting.rows] == [
        r.p_alpha_raw for r in everything.rows if r.betting_population
    ]


def test_run_backtest_rejects_unknown_population_and_covariates_on_subset():
    with pytest.raises(ValueError):
        backtest.run_backtest((2025,), calibration_population="hard-only")
    with pytest.raises(ValueError):
        backtest.run_backtest((2025,), calibration_model="isotonic")
    with pytest.raises(ValueError):
        backtest.run_backtest((2025,), calibration_model="covariate",
                              calibration_population="betting")


# ---------------------------------------------------------------------------
# builder-style final fit: default unchanged, betting fits the subset
# ---------------------------------------------------------------------------

def _synthetic_report(n=2400, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        p = float(rng.uniform(0.15, 0.85))
        betting = i % 2 == 0
        slope = 2.0 if betting else 0.8
        y = int(rng.random() < _sigmoid(slope * _logit(p)))
        rows.append(_report_row(p_alpha_raw=p, p_alpha=p, y_alpha=y, betting_population=betting,
                                surface="Hard" if betting else "Clay"))
    return SimpleNamespace(rows=rows)


def _reference_fit(rows):
    cal = WalkForwardCalibrator(min_samples=1500, refit_every=250)
    for row in rows:
        cal.add(row.p_alpha_raw, row.y_alpha)
    cal._fit()
    return cal.a, cal.b


def test_fit_helper_default_reproduces_the_builder_fit_on_every_row():
    report = _synthetic_report()
    cal, fitted = backtest.fit_platt_calibrator(report.rows)
    assert (cal.a, cal.b) == _reference_fit(report.rows)
    assert fitted == len(report.rows) == 2400


def test_fit_helper_betting_population_fits_only_flagged_rows():
    report = _synthetic_report()
    subset = [r for r in report.rows if r.betting_population]
    cal, fitted = backtest.fit_platt_calibrator(report.rows, calibration_population="betting")
    assert (cal.a, cal.b) == _reference_fit(subset)
    assert fitted == len(subset) == 1200
    assert cal.a != pytest.approx(_reference_fit(report.rows)[0], abs=0.05)
    with pytest.raises(ValueError):
        backtest.fit_platt_calibrator(report.rows, calibration_population="hard")


def test_pinned_replay_owners_are_untouched():
    # tennis/predict.py and tennis/model_state.py are source-pinned replay owners
    # (context_runtime_tennis.CODE_PATHS); this work must not alter their bytes.
    import context_runtime_tennis as runtime
    running = runtime._code_variants()
    manifests = [v for k, v in vars(runtime).items()
                 if k.startswith("_REVIEWED_") and isinstance(v, dict)]
    for name in ("tennis/predict.py", "tennis/model_state.py"):
        assert any(m.get(name, frozenset()) & running[name] for m in manifests), name

# ---------------------------------------------------------------------------
# covariate calibrator (hypothesis 2) and population metrics
# ---------------------------------------------------------------------------

def test_covariate_calibrator_is_identity_until_trained_and_recovers_group_slopes():
    rng = np.random.default_rng(11)
    cal = CovariateWalkForwardCalibrator(min_samples=500, refit_every=250)
    assert cal.predict(0.7, surface="Hard", has_serve=True) == 0.7
    for _ in range(4000):
        p = float(rng.uniform(0.1, 0.9))
        serve = bool(rng.random() < 0.5)
        surface = "Hard" if rng.random() < 0.5 else "Clay"
        slope = 2.0 if serve else 1.0
        y = float(rng.random() < _sigmoid(slope * _logit(p)))
        cal.add(p, y, surface=surface, has_serve=serve)
    cal._fit()
    assert cal.trained
    assert cal.effective_platt(surface="Hard", has_serve=True)[0] == pytest.approx(2.0, abs=0.35)
    assert cal.effective_platt(surface="Clay", has_serve=False)[0] == pytest.approx(1.0, abs=0.3)
    assert abs(cal.effective_platt(surface="Hard", has_serve=True)[1]) < 0.25
    q = cal.predict(0.7, surface="Hard", has_serve=True)
    assert q > 0.7 > cal.predict(0.7, surface="Clay", has_serve=False) - 0.1


def test_population_calibration_scores_only_normal_rows_of_the_population():
    rows = [
        _report_row(p_alpha=0.999999, y_alpha=1, betting_population=True, calibrator_trained=True),
        _report_row(p_alpha=0.000001, y_alpha=0, betting_population=True, calibrator_trained=True),
        _report_row(p_alpha=0.999999, y_alpha=1, betting_population=True, calibrator_trained=False),
        _report_row(p_alpha=0.2, y_alpha=1, betting_population=False, calibrator_trained=True),
        _report_row(p_alpha=0.999999, y_alpha=0, betting_population=True, calibrator_trained=True,
                    termination="retirement", settlement_status="void"),
    ]
    report = BacktestReport(rows=rows)
    trained = report.population_calibration()
    assert trained["n"] == 2 and trained["population"] == "betting"
    assert trained["brier_cal"] == pytest.approx(0.0, abs=1e-6)
    assert trained["ece_cal"] == pytest.approx(0.0, abs=1e-5)
    untrained = report.population_calibration(trained_only=False)
    assert untrained["n"] == 3
    everything = report.population_calibration(population="all", trained_only=True)
    assert everything["n"] == 3 and everything["brier_cal"] > 0.2
    assert report.population_calibration(since="2027-01-01")["n"] == 0
    assert BacktestReport().population_calibration()["brier_cal"] is None
    with pytest.raises(ValueError):
        report.population_calibration(population="clay")
