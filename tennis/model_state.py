"""Persistent tennis model state for daily use.

Building Surface-Elo + serve/return ratings from 25+ years of stats
takes about a minute — far too slow for a daily scan.  This module
builds the state once, pickles it, and reloads it in milliseconds.

Refresh policy: the upstream stats repo (ManTennisData) updates every
few days.  A weekly state rebuild (plus an optional manual refresh)
keeps ratings fresh; between rebuilds predictions use the persisted
state, which is honest and documented.

The persisted calibrator (Platt a/b) comes from a causal walk-forward
backtest over the most recent seasons — i.e. it was only ever fitted
on the past relative to the fixtures it will now score.
"""

from __future__ import annotations

import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd

from .backtest import run_backtest, WalkForwardCalibrator, _is_retired
from .data_loader import load_atp_stats, load_market_odds, add_normalized_names
from .elo import SurfaceElo
from .serve_model import ServeReturnModel, is_tour_level

DEFAULT_STATE_PATH = Path(__file__).resolve().parent / "data" / "model_state.pkl"


@dataclass
class ModelState:
    elo: SurfaceElo
    serve: ServeReturnModel
    cal_a: float
    cal_b: float
    cal_samples: int
    built_at: float
    stats_through: str
    serve_weight: float
    # Separate Platt calibration for WTA (Elo-only mode). NOTE: the real
    # WTA backtest shows no exploitable edge (Hard -0.7% ROI @ >=12%), so
    # WTA runs in shadow-observation mode — see predict.py "WTA-Freigabe".
    cal_wta_a: float = 1.0
    cal_wta_b: float = 0.0
    cal_wta_samples: int = 0

    def calibrate(self, p: float, tour: str = "ATP") -> float:
        from .backtest import _sigmoid, _logit

        a, b = (self.cal_wta_a, self.cal_wta_b) if str(tour).upper() == "WTA" else (self.cal_a, self.cal_b)
        return _sigmoid(a * _logit(p) + b)


def build_state(
    stats_years: Optional[Iterable[int]] = None,
    calibration_odds_years: Tuple[int, ...] = (2022, 2023, 2024),
    serve_weight: float = 0.3,
    verbose: bool = True,
    serve_half_life_days: Optional[float] = 365.0,
) -> ModelState:
    """Build ratings from the stats plane and fit the calibrator on a
    causal walk-forward backtest of the recent seasons.

    ``serve_half_life_days`` must match between the production ratings
    and the calibrator fit — the calibrator learns the distribution the
    decayed serve model produces, not the old cumulative one.
    """
    if stats_years is None:
        stats_years = range(2010, 2027)

    stats = load_atp_stats(stats_years)
    stats = add_normalized_names(stats, "winner_name", "loser_name")
    stats = stats.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)

    elo = SurfaceElo()
    serve = ServeReturnModel(half_life_days=serve_half_life_days)
    n = 0
    for s in stats.to_dict("records"):
        if _is_retired(s.get("match_ret")):
            continue
        if s.get("winner_key") and s.get("loser_key"):
            elo.update(s["winner_key"], s["loser_key"], s.get("surface"))
            if is_tour_level(s):
                serve.update_from_match_row(s)
            n += 1
    through = str(stats["tourney_date"].max())[:10]
    if verbose:
        print(f"State: {n} Matches verarbeitet, Daten bis {through}")

    # --- WTA: no serve boxscore feed exists, so ratings are Elo-only.
    # Built chronologically from the tennis-data.co.uk WTA results files
    # (odds-blind: only winner/loser/surface are used, never prices).
    n_wta = 0
    wta_through = through
    try:
        wta = load_market_odds(list(stats_years), tour="wta")
        wta = add_normalized_names(wta, "Winner", "Loser")
        # source hygiene: drop rows with impossible future dates (the WTA
        # files contain e.g. one 2029 typo row for Iasi 2026)
        cutoff = pd.Timestamp.now() + pd.Timedelta(days=2)
        wta = wta[wta["Date"] <= cutoff]
        wta = wta.sort_values("Date", kind="mergesort")
        for row in wta.itertuples():
            if _is_retired(getattr(row, "Comment", None)):
                continue
            w_key, l_key = row.winner_key, row.loser_key
            if w_key and l_key:
                elo.update(w_key, l_key, row.Surface if isinstance(row.Surface, str) else None)
                n_wta += 1
        if len(wta):
            wta_through = str(pd.to_datetime(wta["Date"]).max())[:10]
        if verbose:
            print(f"State WTA: {n_wta} Matches verarbeitet, Daten bis {wta_through}")
    except Exception as exc:  # WTA feed down -> ATP-only state still valid
        if verbose:
            print(f"WARNUNG: WTA-Elo konnte nicht gebaut werden ({exc})")

    # calibrator: causal walk-forward backtest over recent seasons
    report = run_backtest(
        odds_years=calibration_odds_years,
        stats_years=stats_years,
        tours=("atp",),
        serve_weight=serve_weight,
        recalibrate=False,  # we want RAW probabilities for the fit
        serve_half_life_days=serve_half_life_days,
    )
    cal = WalkForwardCalibrator(min_samples=1500, refit_every=250)
    for row in report.rows:
        cal.add(row.p_alpha_raw, row.y_alpha)
    cal._fit()  # final fit on the full (past) history
    if verbose:
        print(f"Kalibrator: a={cal.a:.4f} b={cal.b:.4f} auf {len(report.rows)} Matches")

    # WTA calibrator: same walk-forward protocol, Elo-only (serve_weight=0)
    cal_wta_a, cal_wta_b, cal_wta_n = 1.0, 0.0, 0
    if n_wta:
        report_wta = run_backtest(
            odds_years=calibration_odds_years,
            stats_years=stats_years,
            tours=("wta",),
            serve_weight=0.0,
            recalibrate=False,
        )
        cal_wta = WalkForwardCalibrator(min_samples=1500, refit_every=250)
        for row in report_wta.rows:
            cal_wta.add(row.p_alpha_raw, row.y_alpha)
        cal_wta._fit()
        cal_wta_a, cal_wta_b, cal_wta_n = cal_wta.a, cal_wta.b, len(report_wta.rows)
        if verbose:
            print(f"Kalibrator WTA: a={cal_wta_a:.4f} b={cal_wta_b:.4f} auf {cal_wta_n} Matches")

    return ModelState(
        elo=elo,
        serve=serve,
        cal_a=cal.a,
        cal_b=cal.b,
        cal_samples=len(report.rows),
        built_at=time.time(),
        stats_through=through,
        serve_weight=serve_weight,
        cal_wta_a=cal_wta_a,
        cal_wta_b=cal_wta_b,
        cal_wta_samples=cal_wta_n,
    )


def save_state(state: ModelState, path: Path = DEFAULT_STATE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(state, fh)
    return path


def load_state(path: Path = DEFAULT_STATE_PATH) -> ModelState:
    with open(path, "rb") as fh:
        state = pickle.load(fh)
    # forward-migration for pickles written before constructor-parametrised
    # tour averages existed: default to the ATP constants
    serve = getattr(state, "serve", None)
    if serve is not None:
        if not hasattr(serve, "_hold_avg"):
            serve._hold_avg = 0.770
        if not hasattr(serve, "_break_avg"):
            serve._break_avg = 0.230
    return state


def state_exists(path: Path = DEFAULT_STATE_PATH) -> bool:
    return path.exists() and path.stat().st_size > 0
