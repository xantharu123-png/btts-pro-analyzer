"""Persistent tennis model state for daily use.

Building Surface-Elo + serve/return ratings from 25+ years of stats
takes about a minute — far too slow for a daily scan.  This module
builds the state once, pickles it, and reloads it in milliseconds.

SECURITY: pickle is executable Python input.  Until the state format is
replaced, this module only loads a regular, non-symlink file owned by the
service account or root (and not group/world writable on POSIX).  Never copy a
model-state pickle from an untrusted PC or provider into the runtime path.

Refresh policy: the upstream stats repo (ManTennisData) updates every
few days.  A weekly state rebuild (plus an optional manual refresh)
keeps ratings fresh; between rebuilds predictions use the persisted
state, which is honest and documented.

The persisted calibrator (Platt a/b) comes from a causal walk-forward
backtest over the most recent seasons — i.e. it was only ever fitted
on the past relative to the fixtures it will now score.
"""

from __future__ import annotations

import hashlib
import pickle
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd

from runtime_paths import (
    PACKAGED_TENNIS_MODEL_STATE_PATH,
    TENNIS_MODEL_STATE_PATH,
    RuntimeArtifactTrustError,
    atomic_write_bytes,
    open_trusted_pickle,
    validate_trusted_pickle_path,
)

from .backtest import run_backtest, WalkForwardCalibrator, _is_retired
from .data_loader import load_atp_stats, load_market_odds, add_normalized_names
from .elo import SurfaceElo
from .serve_model import ServeReturnModel, is_tour_level

DEFAULT_STATE_PATH = TENNIS_MODEL_STATE_PATH
PACKAGED_STATE_PATH = PACKAGED_TENNIS_MODEL_STATE_PATH


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
    tour_scope: str = "legacy-combined"
    stats_through_kind: str = "tournament_start_proxy"
    artifact_hash: str | None = None
    training_cutoff: str | None = None

    def calibrate(self, p: float, tour: str = "ATP") -> float:
        from .backtest import _sigmoid, _logit

        a, b = (self.cal_wta_a, self.cal_wta_b) if str(tour).upper() == "WTA" else (self.cal_a, self.cal_b)
        return _sigmoid(a * _logit(p) + b)

    def calibrate_match(
        self,
        p_a: float,
        player_a_key: str,
        player_b_key: str,
        tour: str = "ATP",
    ) -> float:
        """Apply the alphabetically trained calibrator without side-order bias."""
        if player_a_key <= player_b_key:
            return self.calibrate(p_a, tour=tour)
        return 1.0 - self.calibrate(1.0 - p_a, tour=tour)


def build_state(
    stats_years: Optional[Iterable[int]] = None,
    calibration_odds_years: Tuple[int, ...] = (2022, 2023, 2024),
    serve_weight: float = 0.3,
    verbose: bool = True,
    serve_half_life_days: Optional[float] = 365.0,
    serve_split_indoor: bool = True,
    refresh_training_data: bool = False,
) -> ModelState:
    """Build ratings from the stats plane and fit the calibrator on a
    causal walk-forward backtest of the recent seasons.

    ``serve_half_life_days`` must match between the production ratings
    and the calibrator fit — the calibrator learns the distribution the
    decayed serve model produces, not the old cumulative one.

    ``serve_split_indoor`` likewise: production, calibrator fit and the
    A/B evidence must all see the same environment split.

    ``refresh_training_data`` revalidates active-year ATP/WTA sources before
    publication. A failed refresh is fatal; it never silently downgrades a
    previously combined model to ATP-only. Cache-only callers retain their API.
    """
    if stats_years is None:
        stats_years = range(2010, datetime.fromtimestamp(time.time(), timezone.utc).year + 1)

    build_cutoff = pd.Timestamp(time.time(), unit="s", tz="UTC")
    stats_years = tuple(stats_years)
    refresh_options = {"refresh_current": True} if refresh_training_data else {}
    stats = load_atp_stats(stats_years, **refresh_options)
    stats = add_normalized_names(stats, "winner_name", "loser_name")
    stats["tourney_date"] = pd.to_datetime(stats["tourney_date"], errors="coerce", utc=True)
    stats = stats[stats["tourney_date"].notna() & (stats["tourney_date"] <= build_cutoff)]
    stats = stats.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)

    elo = SurfaceElo()
    serve = ServeReturnModel(half_life_days=serve_half_life_days,
                             split_indoor=serve_split_indoor)
    n = 0
    consumed_dates = []
    for s in stats.to_dict("records"):
        if _is_retired(s.get("match_ret")):
            continue
        if s.get("winner_key") and s.get("loser_key"):
            elo.update(s["winner_key"], s["loser_key"], s.get("surface"))
            if is_tour_level(s):
                serve.update_from_match_row(s)
            n += 1
            consumed_dates.append(s["tourney_date"])
    if not consumed_dates:
        raise ValueError("no dated, completed ATP training results before build cutoff")
    through = str(max(consumed_dates))[:10]
    if verbose:
        print(f"State: {n} Matches verarbeitet, ATP-Turnierstart-Abdeckung bis {through}")

    # --- WTA: no serve boxscore feed exists, so ratings are Elo-only.
    # Built chronologically from the tennis-data.co.uk WTA results files
    # (odds-blind: only winner/loser/surface are used, never prices).
    n_wta = 0
    wta_through = through
    try:
        wta = load_market_odds(list(stats_years), tour="wta", **refresh_options)
        wta = add_normalized_names(wta, "Winner", "Loser")
        # A dated future result cannot train today's ratings, including the
        # known future-date typo rows in this source.
        wta["Date"] = pd.to_datetime(wta["Date"], errors="coerce", utc=True)
        wta = wta[wta["Date"].notna() & (wta["Date"] <= build_cutoff)]
        wta = wta.sort_values("Date", kind="mergesort")
        for row in wta.itertuples():
            if _is_retired(getattr(row, "Comment", None)):
                continue
            w_key, l_key = row.winner_key, row.loser_key
            if w_key and l_key:
                elo.update(w_key, l_key, row.Surface if isinstance(row.Surface, str) else None)
                n_wta += 1
        if refresh_training_data and not n_wta:
            raise ValueError("no dated, completed WTA training results before build cutoff")
        if len(wta):
            wta_through = str(pd.to_datetime(wta["Date"]).max())[:10]
        if verbose:
            print(f"State WTA: {n_wta} Matches verarbeitet, Daten bis {wta_through}")
    except Exception as exc:  # WTA feed down -> ATP-only state still valid
        if refresh_training_data:
            raise
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
        serve_split_indoor=serve_split_indoor,
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


def _state_path_for_read(path: Path | None) -> Path:
    if path is not None:
        return validate_trusted_pickle_path(Path(path))
    if DEFAULT_STATE_PATH.is_symlink() or DEFAULT_STATE_PATH.exists():
        return validate_trusted_pickle_path(DEFAULT_STATE_PATH)
    return validate_trusted_pickle_path(PACKAGED_STATE_PATH)


def save_state(state: ModelState, path: Path | None = None) -> Path:
    path = Path(path) if path is not None else DEFAULT_STATE_PATH
    if not isinstance(state, ModelState):
        raise TypeError("state must be a ModelState")
    if path.is_symlink():
        raise RuntimeArtifactTrustError(
            f"model-state target must not be a symlink: {path}"
        )
    if path.exists():
        validate_trusted_pickle_path(path)
    payload = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
    return atomic_write_bytes(path, payload)


def load_state(path: Path | None = None) -> ModelState:
    path = _state_path_for_read(path)
    with open_trusted_pickle(path) as fh:
        payload = fh.read()
    state = pickle.loads(payload)
    if not isinstance(state, ModelState):
        raise RuntimeArtifactTrustError(
            f"model-state pickle has an unexpected object type: {path}"
        )
    # forward-migration for pickles written before constructor-parametrised
    # tour averages existed: default to the ATP constants
    serve = getattr(state, "serve", None)
    if serve is not None:
        if not hasattr(serve, "_hold_avg"):
            serve._hold_avg = 0.770
        if not hasattr(serve, "_break_avg"):
            serve._break_avg = 0.230
        if not hasattr(serve, "_split_indoor"):
            serve._split_indoor = False  # pre-F2 pickle: unsplit behaviour
    state.tour_scope = getattr(state, "tour_scope", "legacy-combined")
    state.stats_through_kind = getattr(
        state, "stats_through_kind", "tournament_start_proxy"
    )
    state.artifact_hash = hashlib.sha256(payload).hexdigest()
    return state


def state_exists(path: Path | None = None) -> bool:
    explicit = Path(path) if path is not None else None
    if explicit is not None and not explicit.is_symlink() and not explicit.exists():
        return False
    if (
        explicit is None
        and not DEFAULT_STATE_PATH.is_symlink()
        and not DEFAULT_STATE_PATH.exists()
        and not PACKAGED_STATE_PATH.is_symlink()
        and not PACKAGED_STATE_PATH.exists()
    ):
        return False
    trusted_path = _state_path_for_read(explicit)
    return trusted_path.stat().st_size > 0
