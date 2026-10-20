"""Walk-forward backtest of the tennis model against closing prices.

Protocol (strictly causal, same discipline as the football pipeline):

1. Model state (Surface-Elo + serve/return tracker) is built ONLY from
   the odds-blind stats plane (ManTennisData).  A stats row enters the
   state only after its actual tournament finish-date boundary, or verified
   aware individual publication availability, lies before the decision.
   Unknown finish evidence is excluded (no guessed event duration). Retirements
   (``match_ret``) never update the state — a retired match is not a
   real result.  Serve/return ratings consume tour-level matches only
   (challenger box scores measure the wrong opposition level; Elo still
   sees everything because Elo is opponent-adjusted by construction).
2. For every market row (tennis-data.co.uk, Pinnacle closing prices)
   we predict BEFORE knowing the result. Match-winner retirement settlement
   shares the declared one-set shadow rule; unknown evidence is non_evaluable.
   Retirements never train healthy-result calibration or ratings.
3. Raw model probabilities pass a WALK-FORWARD Platt recalibration
   (2-parameter logistic on logit(p), refit as history grows, applied
   only to future rows).  Raw ratings are range-compressed; the
   calibrator restores market-level sharpness without peeking.
4. Pinnacle prices are de-vigged proportionally. Both raw prices are
   retained. ``policy_summary`` replays the production rule exactly:
   evaluate both sides after an explicit probability haircut and select
   only the side with the larger risk-adjusted EV when it clears the
   minimum ROI and experience gates.
5. Only AFTER the prediction may a result move the state (WTA path:
   results from the odds file itself update the Elo, prediction first).

Calibration uses a stochastic outcome: rows are encoded alphabetically
(player A = alphabetically first key), so y is a real Bernoulli
variable — not the degenerate 'Winner column always won'.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import hashlib
import math
import pandas as pd

from betting_math import MINIMUM_RECOMMENDED_DECIMAL_ODDS

from .data_loader import load_atp_stats, load_market_odds, load_wta_ta_stats, add_normalized_names, stats_available_at
from .settlement_policy import match_winner_status, unit_return
from .elo import SurfaceElo
from .serve_model import (
    ServeAdmissionDiagnostics,
    ServeReturnModel,
    is_tour_level,
    WTA_TOUR_HOLD_AVG,
    WTA_TOUR_BREAK_AVG,
)
from .simulator import simulate_match, LEGACY_MODEL_VERSION, POINT_MODEL_VERSION, point_match_win_probability

MIN_SERVE_GAMES = 60.0   # both players need this many tracked service games
MIN_ELO_MATCHES = 20     # experience gate: below this we do not bet
RETIRED_FLAGS = {"retired", "ret", "walkover", "w/o", "def", "default"}
# Production surface gate (``predict.ALLOWED_SURFACES`` re-exports this).
BETTING_SURFACES = ("Hard",)

# Which rows the walk-forward Platt calibrator may learn from.
# ``all``     - legacy: every scored, non-abnormal row (all surfaces, Elo-only
#               rows without serve data, rows below the experience gate).
# ``betting`` - only rows that satisfy the production model gates replayed by
#               ``policy_summary``: surface in ``BETTING_SURFACES``, a serve
#               estimate exists (both >= MIN_SERVE_GAMES) and both players
#               >= ``min_elo_matches``. Audit 2026-10-16 H3.
CALIBRATION_POPULATION_ALL = "all"
CALIBRATION_POPULATION_BETTING = "betting"
CALIBRATION_POPULATIONS = (CALIBRATION_POPULATION_ALL, CALIBRATION_POPULATION_BETTING)
# Calibrator family used inside the walk-forward loop.
CALIBRATION_MODEL_PLATT = "platt"
CALIBRATION_MODEL_COVARIATE = "covariate"
CALIBRATION_MODELS = (CALIBRATION_MODEL_PLATT, CALIBRATION_MODEL_COVARIATE)

# No bookmaker columns, even for sample eligibility in the separated models.
RESULT_COLUMNS = ("Date", "Tournament", "Surface", "Court", "Best of",
                  "Winner", "Loser", "Comment", "tour")


@dataclass
class CalibrationRow:
    date: object
    tour: str
    p_alpha_raw: float
    y_alpha: int
    # Population markers (defaults keep older consumers unchanged).
    surface: Optional[str] = None
    has_serve: bool = False
    gated: bool = False
    betting_population: bool = False


@dataclass
class CalibrationReport:
    """Sport-only observations, deliberately not an odds evaluation report."""
    rows: List[CalibrationRow] = field(default_factory=list)


def in_betting_population(
    surface: Optional[str],
    p_serve: Optional[float],
    gated: bool,
    allowed_surfaces: Tuple[str, ...] = BETTING_SURFACES,
) -> bool:
    """True when a backtest row meets the production model gates.

    Mirrors ``predict.predict_match`` (ATP gates "Belag", "Erfahrung",
    "Aufschlag-Daten") and the default model-gate replay of
    ``BacktestReport.policy_summary``: Hard court, a serve-model estimate
    (both players >= MIN_SERVE_GAMES) and both players past the experience
    gate. Prices never enter this decision.
    """
    has_serve = p_serve is not None and not (
        isinstance(p_serve, float) and math.isnan(p_serve)
    )
    return bool(gated) and has_serve and surface in allowed_surfaces


def stable_flip(key: str) -> bool:
    """Deterministic, reproducible coin flip for neutral A/B orientation.

    ``hash()`` on str is salted per process (PYTHONHASHSEED) — the same
    match landed in a different orientation on every run, so any output
    built on it was irreproducible (F5).  md5 is stable across processes
    and platforms and just as uniform.
    """
    return hashlib.md5(key.encode("utf-8")).digest()[0] % 2 == 1


# --------------------------------------------------------------------------
# walk-forward Platt recalibration
# --------------------------------------------------------------------------


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


class WalkForwardCalibrator:
    """2-parameter Platt scaling on logit(p), refit as history grows.

    ``predict`` only ever uses parameters fitted on PAST observations;
    until ``min_samples`` exist it is the identity map.
    """

    def __init__(self, min_samples: int = 1500, refit_every: int = 500) -> None:
        self.min_samples = min_samples
        self.refit_every = refit_every
        self._xs: List[float] = []
        self._ys: List[float] = []
        self._since_fit = 0
        self.a = 1.0
        self.b = 0.0

    @property
    def trained(self) -> bool:
        return len(self._xs) >= self.min_samples

    def predict(self, p: float, **covariates) -> float:
        # ``covariates`` are accepted for interface parity with the
        # covariate calibrator and deliberately ignored here.
        if not self.trained:
            return p
        return _sigmoid(self.a * _logit(p) + self.b)

    def add(self, p: float, y: float, **covariates) -> None:
        self._xs.append(_logit(p))
        self._ys.append(float(y))
        self._since_fit += 1
        if self._since_fit >= self.refit_every:
            self._fit()

    def _fit(self) -> None:
        self._since_fit = 0
        n = len(self._xs)
        if n < self.min_samples:
            return
        a, b = self.a, self.b
        for _ in range(25):
            g_a = g_b = 0.0
            h_aa = h_ab = h_bb = 0.0
            for x, y in zip(self._xs, self._ys):
                p = _sigmoid(a * x + b)
                w = p * (1.0 - p) + 1e-9
                r = p - y
                g_a += r * x
                g_b += r
                h_aa += w * x * x
                h_ab += w * x
                h_bb += w
            det = h_aa * h_bb - h_ab * h_ab
            if abs(det) < 1e-12:
                break
            step_a = (h_bb * g_a - h_ab * g_b) / det
            step_b = (-h_ab * g_a + h_aa * g_b) / det
            a -= step_a
            b -= step_b
            if abs(step_a) + abs(step_b) < 1e-8:
                break
        # sane bounds: never allow inversion or insane steepness
        self.a = min(max(a, 0.2), 8.0)
        self.b = min(max(b, -3.0), 3.0)


def calibration_features(p: float, *, surface: Optional[str], has_serve: bool,
                         allowed_surfaces: Tuple[str, ...] = BETTING_SURFACES) -> List[float]:
    """Design row for the covariate calibrator (hypothesis 2 of audit H3).

    Slope and intercept may differ by serve availability (the blend with the
    serve simulator changes the raw-probability spread) and by betting
    surface; everything else is shared across rows.
    """
    x = _logit(p)
    serve = 1.0 if has_serve else 0.0
    hard = 1.0 if surface in allowed_surfaces else 0.0
    return [x, x * serve, x * hard, 1.0, serve, hard]


class CovariateWalkForwardCalibrator:
    """Walk-forward logistic recalibration with surface/serve covariates.

    logit(q) = (a0 + a1*serve + a2*hard) * logit(p) + b0 + b1*serve + b2*hard

    Experimental: it is NOT persisted in ``ModelState`` (which carries only
    Platt ``cal_a``/``cal_b``); it exists to test the second H3 hypothesis
    inside ``run_backtest``. Same causal contract as ``WalkForwardCalibrator``:
    ``predict`` only ever uses parameters fitted on past rows and is the
    identity until ``min_samples`` exist.
    """

    SLOPE_BOUNDS = (0.2, 8.0)
    INTERCEPT_BOUND = 3.0

    def __init__(self, min_samples: int = 1500, refit_every: int = 500,
                 allowed_surfaces: Tuple[str, ...] = BETTING_SURFACES) -> None:
        self.min_samples = min_samples
        self.refit_every = refit_every
        self.allowed_surfaces = tuple(allowed_surfaces)
        self._rows: List[List[float]] = []
        self._ys: List[float] = []
        self._since_fit = 0
        self.coef: List[float] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    @property
    def trained(self) -> bool:
        return len(self._rows) >= self.min_samples

    def _features(self, p: float, covariates: dict) -> List[float]:
        return calibration_features(
            p, surface=covariates.get("surface"),
            has_serve=bool(covariates.get("has_serve", False)),
            allowed_surfaces=self.allowed_surfaces,
        )

    def predict(self, p: float, **covariates) -> float:
        if not self.trained:
            return p
        z = sum(c * f for c, f in zip(self.coef, self._features(p, covariates)))
        return _sigmoid(z)

    def add(self, p: float, y: float, **covariates) -> None:
        self._rows.append(self._features(p, covariates))
        self._ys.append(float(y))
        self._since_fit += 1
        if self._since_fit >= self.refit_every:
            self._fit()

    def _fit(self) -> None:
        import numpy as np

        self._since_fit = 0
        n = len(self._rows)
        if n < self.min_samples:
            return
        X = np.asarray(self._rows, dtype=float)
        y = np.asarray(self._ys, dtype=float)
        coef = np.asarray(self.coef, dtype=float)
        ridge = 1e-6 * np.eye(X.shape[1])
        for _ in range(25):
            z = X @ coef
            p = 1.0 / (1.0 + np.exp(-np.clip(z, -35.0, 35.0)))
            w = p * (1.0 - p) + 1e-9
            grad = X.T @ (p - y)
            hess = (X * w[:, None]).T @ X + ridge
            try:
                step = np.linalg.solve(hess, grad)
            except np.linalg.LinAlgError:
                return
            coef = coef - step
            if float(np.abs(step).sum()) < 1e-8:
                break
        if not np.all(np.isfinite(coef)):
            return
        a0, a1, a2, b0, b1, b2 = (float(v) for v in coef)
        lo, hi = self.SLOPE_BOUNDS
        for serve in (0.0, 1.0):
            for hard in (0.0, 1.0):
                slope = a0 + a1 * serve + a2 * hard
                intercept = b0 + b1 * serve + b2 * hard
                if not lo <= slope <= hi or abs(intercept) > self.INTERCEPT_BOUND:
                    return  # keep the previous admissible parameters
        self.coef = [a0, a1, a2, b0, b1, b2]

    def effective_platt(self, *, surface: Optional[str], has_serve: bool) -> Tuple[float, float]:
        """(slope, intercept) the model applies to rows with these covariates."""
        serve = 1.0 if has_serve else 0.0
        hard = 1.0 if surface in self.allowed_surfaces else 0.0
        a0, a1, a2, b0, b1, b2 = self.coef
        return a0 + a1 * serve + a2 * hard, b0 + b1 * serve + b2 * hard


def _make_calibrator(model: str):
    if model == CALIBRATION_MODEL_COVARIATE:
        return CovariateWalkForwardCalibrator()
    return WalkForwardCalibrator()


def fit_platt_calibrator(
    rows: Iterable[object],
    *,
    calibration_population: str = CALIBRATION_POPULATION_ALL,
    min_samples: int = 1500,
    refit_every: int = 250,
) -> Tuple[WalkForwardCalibrator, int]:
    """Final Platt fit over reported rows, the way the state builders do it
    (``model_state.build_state`` / ``tour_state.build_tour_state``: add every
    row in order, then ``_fit``).

    ``betting`` keeps only rows flagged ``betting_population``; rows need
    ``p_alpha_raw`` and ``y_alpha``. Returns the calibrator and the number of
    fitted rows (what ``cal_samples`` of a state built from it must record).
    Deliberately not wired into the builders: ``tennis/predict.py`` and
    ``tennis/model_state.py`` are source-pinned replay owners
    (``context_runtime_tennis.CODE_PATHS``); adopting it there needs a new
    reviewed manifest entry and a population marker in the state contract.
    """
    if calibration_population not in CALIBRATION_POPULATIONS:
        raise ValueError("unknown calibration population")
    cal = WalkForwardCalibrator(min_samples=min_samples, refit_every=refit_every)
    fitted = 0
    for row in rows:
        if (calibration_population == CALIBRATION_POPULATION_BETTING
                and not getattr(row, "betting_population", False)):
            continue
        cal.add(row.p_alpha_raw, row.y_alpha)
        fitted += 1
    cal._fit()
    return cal, fitted


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------


@dataclass
class BacktestRow:
    date: object
    tour: str
    surface: str
    best_of: int
    winner: str
    loser: str
    p_elo: float
    p_serve: Optional[float]
    p_model: float           # raw model P('winner' column player wins)
    p_cal: float             # recalibrated P (used for edges/bets)
    p_market_alpha: float    # market prob for alphabetically-first player
    edge_w: float
    edge_l: float
    chosen_side: str
    chosen_edge: float
    chosen_odds: float
    odds_w: float
    odds_l: float
    bet_won: bool
    gated: bool
    y_alpha: int
    p_alpha: float           # calibrated prob for alphabetically-first player
    p_alpha_raw: float       # raw prob for alphabetically-first player
    settlement_status: str = "standing"
    termination: str = "normal"
    # Production model gates (surface, serve estimate, experience) replayed
    # per row; ``calibrator_trained`` records whether the walk-forward
    # calibrator had reached ``min_samples`` when this row was predicted.
    betting_population: bool = False
    calibrator_trained: bool = False


@dataclass
class BacktestReport:
    rows: List[BacktestRow] = field(default_factory=list)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([r.__dict__ for r in self.rows])

    def summary(self, edge_thresholds=(0.0, 0.02, 0.05, 0.08, 0.10)) -> pd.DataFrame:
        """Legacy diagnostic showing historical edge-threshold sensitivity."""
        frame = self.to_frame()
        if frame.empty:
            return pd.DataFrame([{"edge>=": thr, "bets": 0} for thr in edge_thresholds])
        out = []
        for thr in edge_thresholds:
            bets = frame[(frame["chosen_edge"] >= thr) & frame["gated"]
                         & frame["settlement_status"].isin(("standing", "void"))]
            if len(bets) == 0:
                out.append({"edge>=": thr, "bets": 0})
                continue
            pnl = bets.apply(
                lambda r: unit_return(r["settlement_status"], r["bet_won"], r["chosen_odds"]), axis=1
            )
            resolved = bets[bets["settlement_status"].eq("standing")]
            out.append(
                {
                    "edge>=": thr,
                    "bets": int(len(bets)),
                    "win_rate": round(float(resolved["bet_won"].mean()), 4) if len(resolved) else None,
                    "roi": round(float(pnl.mean()), 4),
                    "avg_edge": round(float(bets["chosen_edge"].mean()), 4),
                    "avg_odds": round(float(bets["chosen_odds"].mean()), 3),
                }
            )
        return pd.DataFrame(out)

    def policy_summary(
        self,
        *,
        probability_haircut: float,
        minimum_expected_roi: float = 0.03,
        minimum_published_odds: float = MINIMUM_RECOMMENDED_DECIMAL_ODDS,
        allowed_surfaces: Optional[Tuple[str, ...]] = ("Hard",),
        require_serve_model: bool = True,
    ) -> Dict[str, Optional[float]]:
        """Replay the exact two-sided production price policy.

        ``probability_haircut`` and ``minimum_expected_roi`` are decimals.
        By default the production model gates are also replayed: Hard court,
        sufficient Elo experience, and an available serve-model estimate.
        The confidence interval describes historical unit-stake returns, not
        uncertainty in the model probability and not a future-profit promise.
        """
        for value, label, upper_bound in (
            (probability_haircut, "probability_haircut", 1.0),
            (minimum_expected_roi, "minimum_expected_roi", None),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0.0
                or (upper_bound is not None and float(value) > upper_bound)
            ):
                raise ValueError(f"{label} must be finite and non-negative")
        if (
            isinstance(minimum_published_odds, bool)
            or not isinstance(minimum_published_odds, (int, float))
            or not math.isfinite(float(minimum_published_odds))
            or float(minimum_published_odds) <= 1.0
        ):
            raise ValueError("minimum_published_odds must be greater than 1.0")
        if not isinstance(require_serve_model, bool):
            raise ValueError("require_serve_model must be boolean")
        if allowed_surfaces is not None:
            if (
                not isinstance(allowed_surfaces, tuple)
                or not allowed_surfaces
                or any(
                    not isinstance(surface, str) or not surface.strip()
                    for surface in allowed_surfaces
                )
            ):
                raise ValueError("allowed_surfaces must be a non-empty tuple")
            allowed_surfaces = tuple(
                surface.strip() for surface in allowed_surfaces
            )

        frame = self.to_frame()
        if frame.empty:
            return {
                "bets": 0,
                "wins": 0,
                "roi": None,
                "roi_standard_error": None,
                "roi_ci95_low": None,
                "roi_ci95_high": None,
                "avg_odds": None,
                "avg_risk_ev": None,
                "model_gate_rows": 0,
                "probability_haircut": float(probability_haircut),
                "minimum_expected_roi": float(minimum_expected_roi),
                "minimum_published_odds": float(minimum_published_odds),
            }

        replay = frame[frame["gated"] & frame["settlement_status"].isin(("standing", "void"))].copy()
        if allowed_surfaces is not None:
            replay = replay[replay["surface"].isin(allowed_surfaces)]
        if require_serve_model:
            replay = replay[replay["p_serve"].notna()]
        model_gate_rows = int(len(replay))
        replay["risk_p_w"] = (
            replay["p_cal"].astype(float) - float(probability_haircut)
        ).clip(lower=0.0, upper=1.0)
        replay["risk_p_l"] = (
            1.0 - replay["p_cal"].astype(float) - float(probability_haircut)
        ).clip(lower=0.0, upper=1.0)
        replay["risk_ev_w"] = replay["risk_p_w"] * replay["odds_w"] - 1.0
        replay["risk_ev_l"] = replay["risk_p_l"] * replay["odds_l"] - 1.0
        replay["eligible_risk_ev_w"] = replay["risk_ev_w"].where(
            replay["odds_w"] + 1e-12 >= float(minimum_published_odds),
            float("-inf"),
        )
        replay["eligible_risk_ev_l"] = replay["risk_ev_l"].where(
            replay["odds_l"] + 1e-12 >= float(minimum_published_odds),
            float("-inf"),
        )
        replay["policy_side"] = replay.apply(
            lambda row: (
                "W"
                if row["eligible_risk_ev_w"] >= row["eligible_risk_ev_l"]
                else "L"
            ),
            axis=1,
        )
        replay["policy_risk_ev"] = replay[
            ["eligible_risk_ev_w", "eligible_risk_ev_l"]
        ].max(axis=1)
        replay = replay[
            replay["policy_risk_ev"] + 1e-12 >= float(minimum_expected_roi)
        ].copy()
        if replay.empty:
            return {
                "bets": 0,
                "wins": 0,
                "roi": None,
                "roi_standard_error": None,
                "roi_ci95_low": None,
                "roi_ci95_high": None,
                "avg_odds": None,
                "avg_risk_ev": None,
                "model_gate_rows": model_gate_rows,
                "probability_haircut": float(probability_haircut),
                "minimum_expected_roi": float(minimum_expected_roi),
                "minimum_published_odds": float(minimum_published_odds),
            }

        replay["policy_odds"] = replay.apply(
            lambda row: row["odds_w"] if row["policy_side"] == "W" else row["odds_l"],
            axis=1,
        )
        replay["policy_won"] = (replay["policy_side"] == "W") & (replay["settlement_status"] == "standing")
        returns = replay.apply(
            lambda row: unit_return(row["settlement_status"], row["policy_won"], row["policy_odds"]),
            axis=1,
        )
        roi = float(returns.mean())
        standard_error = (
            float(returns.std(ddof=1) / math.sqrt(len(returns)))
            if len(returns) >= 2
            else None
        )
        return {
            "bets": int(len(replay)),
            "wins": int(replay["policy_won"].sum()),
            "roi": round(roi, 6),
            "roi_standard_error": (
                round(standard_error, 6) if standard_error is not None else None
            ),
            "roi_ci95_low": (
                round(roi - 1.96 * standard_error, 6)
                if standard_error is not None else None
            ),
            "roi_ci95_high": (
                round(roi + 1.96 * standard_error, 6)
                if standard_error is not None else None
            ),
            "avg_odds": round(float(replay["policy_odds"].mean()), 4),
            "avg_risk_ev": round(float(replay["policy_risk_ev"].mean()), 6),
            "model_gate_rows": model_gate_rows,
            "probability_haircut": float(probability_haircut),
            "minimum_expected_roi": float(minimum_expected_roi),
            "minimum_published_odds": float(minimum_published_odds),
        }

    def calibration(self) -> Dict[str, float]:
        frame = self.to_frame()
        if not frame.empty:
            frame = frame[frame["termination"].eq("normal") & frame["settlement_status"].eq("standing")]
        if frame.empty:
            return {**dict.fromkeys(("brier_raw", "brier_cal", "brier_market",
                    "logloss_raw", "logloss_cal", "logloss_market",
                    "pick_accuracy", "gate_coverage")), "n": 0}
        y = frame["y_alpha"].astype(float)

        def _metrics(pcol: str) -> Tuple[float, float]:
            p = frame[pcol].clip(1e-6, 1 - 1e-6)
            brier = float(((p - y) ** 2).mean())
            logloss = float(
                -(y * p.map(math.log) + (1 - y) * (1 - p).map(math.log)).mean()
            )
            return round(brier, 4), round(logloss, 4)

        brier_raw, ll_raw = _metrics("p_alpha_raw")
        brier_cal, ll_cal = _metrics("p_alpha")
        pm = frame["p_market_alpha"].clip(1e-6, 1 - 1e-6)
        brier_mkt = float(((pm - y) ** 2).mean())
        ll_mkt = float(-(y * pm.map(math.log) + (1 - y) * (1 - pm).map(math.log)).mean())
        return {
            "brier_raw": brier_raw,
            "brier_cal": brier_cal,
            "brier_market": round(brier_mkt, 4),
            "logloss_raw": ll_raw,
            "logloss_cal": ll_cal,
            "logloss_market": round(ll_mkt, 4),
            "pick_accuracy": round(float((frame["p_model"] >= 0.5).mean()), 4),
            "gate_coverage": round(float(frame["gated"].mean()), 4),
            "n": len(frame),
        }

    def population_calibration(
        self,
        *,
        population: str = CALIBRATION_POPULATION_BETTING,
        trained_only: bool = True,
        since=None,
        bins: int = 10,
    ) -> Dict[str, Optional[float]]:
        """Calibration error on one population of normally completed rows.

        ``population`` is ``betting`` (rows that pass the production model
        gates) or ``all``. ``trained_only`` keeps rows predicted after the
        walk-forward calibrator had enough history; ``since`` (date-like)
        additionally drops earlier rows. ECE uses ``bins`` equal-width bins
        over the alphabetical-orientation probability.
        """
        if population not in CALIBRATION_POPULATIONS:
            raise ValueError("unknown calibration population")
        if not isinstance(bins, int) or isinstance(bins, bool) or bins < 2:
            raise ValueError("bins must be an integer >= 2")
        frame = self.to_frame()
        if not frame.empty:
            frame = frame[frame["termination"].eq("normal") & frame["settlement_status"].eq("standing")]
            if population == CALIBRATION_POPULATION_BETTING:
                frame = frame[frame["betting_population"].astype(bool)]
            if trained_only:
                frame = frame[frame["calibrator_trained"].astype(bool)]
            if since is not None and not frame.empty:
                frame = frame[pd.to_datetime(frame["date"]) >= pd.Timestamp(since)]
        keys = ("brier_raw", "brier_cal", "brier_market", "logloss_raw", "logloss_cal",
                "logloss_market", "ece_raw", "ece_cal", "ece_market")
        if frame.empty:
            return {**dict.fromkeys(keys), "n": 0, "population": population}
        y = frame["y_alpha"].astype(float)

        def _scores(pcol: str) -> Tuple[float, float, float]:
            p = frame[pcol].astype(float).clip(1e-6, 1 - 1e-6)
            brier = float(((p - y) ** 2).mean())
            logloss = float(-(y * p.map(math.log) + (1 - y) * (1 - p).map(math.log)).mean())
            edges = [i / bins for i in range(bins + 1)]
            bucket = pd.cut(p, bins=edges, labels=False, include_lowest=True)
            ece = 0.0
            for _, idx in bucket.groupby(bucket).groups.items():
                ece += len(idx) / len(p) * abs(float(p.loc[idx].mean()) - float(y.loc[idx].mean()))
            return round(brier, 5), round(logloss, 5), round(ece, 5)

        out: Dict[str, Optional[float]] = {"n": int(len(frame)), "population": population}
        for label, col in (("raw", "p_alpha_raw"), ("cal", "p_alpha"), ("market", "p_market_alpha")):
            brier, logloss, ece = _scores(col)
            out[f"brier_{label}"] = brier
            out[f"logloss_{label}"] = logloss
            out[f"ece_{label}"] = ece
        return out

    def bias_table(self) -> pd.DataFrame:
        frame = self.to_frame()
        if frame.empty:
            return frame
        frame = frame[frame["termination"].eq("normal") & frame["settlement_status"].eq("standing")].copy()
        if frame.empty:
            return frame
        frame["bucket"] = pd.cut(
            frame["p_market_alpha"],
            bins=[0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0],
            labels=["0-20%", "20-35%", "35-50%", "50-65%", "65-80%", "80-100%"],
        )
        frame["cal_minus_market"] = frame["p_alpha"] - frame["p_market_alpha"]
        return (
            frame.groupby("bucket", observed=True)
            .agg(
                n=("y_alpha", "size"),
                market_avg=("p_market_alpha", "mean"),
                actual_win=("y_alpha", "mean"),
                model_cal_avg=("p_alpha", "mean"),
                cal_minus_market=("cal_minus_market", "mean"),
            )
            .round(4)
            .reset_index()
        )


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _devig(odds_w: float, odds_l: float) -> Optional[Tuple[float, float]]:
    try:
        ow, ol = float(odds_w), float(odds_l)
    except (TypeError, ValueError):
        return None
    if ow <= 1.0 or ol <= 1.0:
        return None
    total = 1.0 / ow + 1.0 / ol
    return (1.0 / ow) / total, (1.0 / ol) / total


def _cutoff(date: pd.Timestamp, tournament: str = "") -> pd.Timestamp:
    """Aware decision or earliest possible start of an unzoned market day.

    An unknown venue date may start in UTC+14. Choosing its earliest boundary
    complements the latest UTC-12 end boundary of date-only training evidence.
    Tournament names/aliases never decide availability.
    """
    date = pd.Timestamp(date)
    if date.tzinfo is not None:
        return date.tz_convert("UTC")
    return date.normalize().tz_localize("UTC") - pd.Timedelta(hours=14)


def _is_retired(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().casefold().strip("()")
    return any(flag in text for flag in RETIRED_FLAGS)


# --------------------------------------------------------------------------
# main loop
# --------------------------------------------------------------------------


def run_backtest(
    odds_years: Iterable[int],
    stats_years: Optional[Iterable[int]] = None,
    tours: Tuple[str, ...] = ("atp",),
    serve_weight: float = 0.5,
    min_elo_matches: int = MIN_ELO_MATCHES,
    recalibrate: bool = True,
    score_from: Optional[str] = None,
    serve_half_life_days: Optional[float] = 365.0,
    serve_split_indoor: bool = True,
    end_cutoff: datetime | None = None,
    calibration_only: bool = False,
    diagnostics: dict | None = None,
    market_model_version: str = LEGACY_MODEL_VERSION,
    calibration_population: str = CALIBRATION_POPULATION_ALL,
    calibration_model: str = CALIBRATION_MODEL_PLATT,
) -> BacktestReport | CalibrationReport:
    """Full walk-forward backtest.

    ``serve_weight`` blends simulator and Elo when both players have
    enough tracked serve history (0 = Elo only).

    ``score_from`` (ISO date) splits warmup from evaluation: rows before
    it only update state (Elo / serve ratings), they are never scored and
    never feed the calibrator.  Needed for WTA, where the Tennis Abstract
    box-score plane starts 2024 — give the serve model a learning year
    and evaluate only 2025+.

    ``serve_half_life_days`` sets the exponential decay of the serve/return
    accumulators (None = plain career sums, the pre-2026-07 behaviour —
    kept for A/B testing).

    ``serve_split_indoor`` keeps a pure Hard@Indoor bucket and makes the
    log5 league constant environment-aware (WTA feed has no flag and
    always runs unsplit).

    ``end_cutoff`` is an inclusive aware input boundary. ``calibration_only``
    returns sport-only raw observations for exactly one tour: prices neither
    enter its copied input columns nor decide its sample population. The
    default remains the legacy odds-evaluation report and eligibility policy.

    ``calibration_population`` decides which rows the walk-forward calibrator
    learns from (``all`` = legacy, ``betting`` = only rows passing the
    production model gates; see ``in_betting_population``). Every row is still
    predicted and reported; in ``calibration_only`` mode only the learning
    population is returned. ``calibration_model`` selects the in-loop
    calibrator family: ``platt`` (persisted contract) or the experimental
    ``covariate`` calibrator, which needs the full population.
    """
    # An explicit cutoff bounds every input before causal pointer traversal.
    # Default evaluation preserves the established price/eligibility behavior.
    end_ts = None
    if end_cutoff is not None:
        if not isinstance(end_cutoff, datetime) or end_cutoff.tzinfo is None or end_cutoff.utcoffset() is None:
            raise ValueError("end_cutoff must be timezone-aware")
        end_ts = pd.Timestamp(end_cutoff.astimezone(timezone.utc))
    if calibration_only and (len(tours) != 1 or tours[0] not in ("atp", "wta")):
        raise ValueError("calibration requires exactly one explicit tour")
    if diagnostics is not None and not calibration_only:
        raise ValueError("serve diagnostics are available only for calibration")
    admission = ServeAdmissionDiagnostics(diagnostics) if calibration_only else None
    if market_model_version not in (LEGACY_MODEL_VERSION, POINT_MODEL_VERSION):
        raise ValueError("unknown tennis calibration simulator version")
    if calibration_population not in CALIBRATION_POPULATIONS:
        raise ValueError("unknown calibration population")
    if calibration_model not in CALIBRATION_MODELS:
        raise ValueError("unknown calibration model")
    if (calibration_model == CALIBRATION_MODEL_COVARIATE
            and calibration_population != CALIBRATION_POPULATION_ALL):
        raise ValueError("covariate calibration needs the full population")
    learn_all = calibration_population == CALIBRATION_POPULATION_ALL

    def bounded(frame, column, tour):
        if calibration_only and "tour" in frame and not frame["tour"].eq(tour.upper()).all():
            raise ValueError("input tour does not match calibration tour")
        if end_ts is None:
            return frame
        frame = frame.copy()
        values = pd.to_datetime(frame[column], errors="coerce", utc=True)
        return frame[values.notna() & values.le(end_ts)]

    def available_history(frame, tour, *, individual_match_date=False):
        if frame.empty:
            return [], []
        frame = frame.copy()
        frame["stats_available_at"] = pd.to_datetime([
            stats_available_at(row, individual_match_date=individual_match_date)
            for row in frame.to_dict("records")
        ], utc=True)
        frame = bounded(frame, "stats_available_at", tour)
        frame = frame[frame["stats_available_at"].notna()]
        frame = add_normalized_names(frame, "winner_name", "loser_name")
        frame = frame.sort_values("stats_available_at", kind="mergesort").reset_index(drop=True)
        return frame.to_dict("records"), frame["stats_available_at"].tolist()

    stats_records = None
    stats_dates = None
    if "atp" in tours:
        stats = load_atp_stats(stats_years)
        stats_records, stats_dates = available_history(stats, "atp")

    # WTA serve plane: Tennis Abstract leaderboard box scores (2024 -> today).
    # Same schema as the ATP stats plane; consumed through its own causal
    # pointer so serve ratings only ever see the past.
    wta_records = None
    wta_dates = None
    if "wta" in tours and serve_weight > 0:
        wta_stats = load_wta_ta_stats()
        wta_records, wta_dates = available_history(wta_stats, "wta", individual_match_date=True)

    score_from_ts = pd.Timestamp(score_from) if score_from else None

    elo = SurfaceElo()
    serve = ServeReturnModel(half_life_days=serve_half_life_days,
                             split_indoor=serve_split_indoor)
    serve_wta = (
        ServeReturnModel(hold_avg=WTA_TOUR_HOLD_AVG, break_avg=WTA_TOUR_BREAK_AVG,
                         half_life_days=serve_half_life_days)
        if "wta" in tours
        else None
    )
    calibrators: Dict[str, object] = {
        t: _make_calibrator(calibration_model) for t in tours
    }
    stats_ptr = 0
    wta_ptr = 0
    result = CalibrationReport() if calibration_only else BacktestReport()

    for tour in tours:
        odds = load_market_odds(odds_years, tour=tour)
        if calibration_only:
            odds = odds[[name for name in RESULT_COLUMNS if name in odds]].copy()
        odds = bounded(odds, "Date", tour)
        odds = odds.rename(columns={"Best of": "BestOf"})
        odds = add_normalized_names(odds, "Winner", "Loser")
        odds = odds.sort_values("Date", kind="mergesort").reset_index(drop=True)
        cal = calibrators[tour]

        for row in odds.itertuples(index=False):
            if pd.isna(row.Date):
                continue
            cutoff = _cutoff(row.Date, str(row.Tournament))

            # 1) advance the causal stats pointer (ATP only)
            if stats_records is not None:
                while stats_ptr < len(stats_records) and (
                    stats_dates[stats_ptr] is not None
                    and not pd.isna(stats_dates[stats_ptr])
                    and stats_dates[stats_ptr] < cutoff
                ):
                    s = stats_records[stats_ptr]
                    stats_ptr += 1
                    if _is_retired(s.get("match_ret")):
                        continue
                    if s.get("winner_key") and s.get("loser_key"):
                        elo.update(s["winner_key"], s["loser_key"], s.get("surface"))
                        if is_tour_level(s):
                            if calibration_only:
                                serve.update_from_match_row_if_valid(
                                    s, diagnostics=admission,
                                )
                            else:
                                serve.update_from_match_row(s)

            # 1b) WTA: advance the Tennis Abstract box-score pointer.
            # Serve ratings ONLY — Elo comes from the odds-file results
            # (odds-blind), so no double update when a match is in both.
            if tour == "wta" and wta_records is not None:
                while wta_ptr < len(wta_records) and (
                    wta_dates[wta_ptr] is not None
                    and not pd.isna(wta_dates[wta_ptr])
                    and wta_dates[wta_ptr] < cutoff
                ):
                    s = wta_records[wta_ptr]
                    wta_ptr += 1
                    if s.get("winner_key") and s.get("loser_key"):
                        if calibration_only:
                            serve_wta.update_from_match_row_if_valid(
                                s, diagnostics=admission,
                            )
                        else:
                            serve_wta.update_from_match_row(s)

            w_key, l_key = row.winner_key, row.loser_key
            if not w_key or not l_key:
                continue
            comment = str(getattr(row, "Comment", "")).strip().casefold()
            abnormal = _is_retired(comment)
            if abnormal and any(flag in comment for flag in ("def", "default")):
                continue  # unsupported terminal, not a retirement or normal win
            termination = ("walkover" if any(flag in comment for flag in ("walkover", "w/o"))
                           else "retirement" if abnormal else "normal")
            completed_sets = None
            if termination == "retirement":
                values = (getattr(row, "Wsets", None), getattr(row, "Lsets", None))
                if all(isinstance(value, (int, float)) and not isinstance(value, bool)
                       and math.isfinite(value) and value >= 0 and int(value) == value for value in values):
                    completed_sets = int(sum(values))
            settlement_status = match_winner_status(termination,
                str(row.Winner) if termination != "walkover" else None, completed_sets)
            surface = row.Surface if isinstance(row.Surface, str) else None
            try:
                best_of = int(row.BestOf)
            except (TypeError, ValueError):
                best_of = 3
            if best_of not in (3, 5):
                best_of = 3

            # 2) predict
            serve_model = serve_wta if tour == "wta" else serve
            have_serve_plane = serve_model is not None and (
                stats_records is not None or wta_records is not None
            )
            p_elo = elo.win_probability(w_key, l_key, surface)
            p_serve = None
            if have_serve_plane and serve_weight > 0:
                enough = (
                    serve_model.service_games(w_key, as_of=row.Date) >= MIN_SERVE_GAMES
                    and serve_model.service_games(l_key, as_of=row.Date) >= MIN_SERVE_GAMES
                )
                if enough:
                    indoor = str(getattr(row, "Court", "")) == "Indoor"
                    hold_w, hold_l = serve_model.expected_hold_probabilities(
                        w_key, l_key, surface, as_of=row.Date, indoor=indoor
                    )
                    p_serve = (point_match_win_probability(hold_w, hold_l, best_of)
                        if market_model_version == POINT_MODEL_VERSION else
                        simulate_match(hold_w, hold_l, best_of=best_of).p_a_win)
            p_model = (
                (1.0 - serve_weight) * p_elo + serve_weight * p_serve
                if p_serve is not None
                else p_elo
            )
            gated = (
                elo.overall.matches(w_key) >= min_elo_matches
                and elo.overall.matches(l_key) >= min_elo_matches
            )
            in_population = in_betting_population(surface, p_serve, gated)
            learns = learn_all or in_population
            covariates = {"surface": surface, "has_serve": p_serve is not None}

            if calibration_only:
                if abnormal:
                    continue
                if learns and (score_from_ts is None or row.Date >= score_from_ts):
                    alpha_first_is_w = w_key <= l_key
                    p_alpha_raw = p_model if alpha_first_is_w else 1.0 - p_model
                    if not math.isfinite(p_alpha_raw) or not 0. <= p_alpha_raw <= 1.:
                        raise ValueError("invalid calibration probability")
                    result.rows.append(CalibrationRow(
                        date=row.Date, tour=tour.upper(),
                        p_alpha_raw=round(p_alpha_raw, 4),
                        y_alpha=1 if alpha_first_is_w else 0,
                        surface=surface, has_serve=p_serve is not None,
                        gated=gated, betting_population=in_population,
                    ))
                if tour == "wta" and not abnormal:
                    elo.update(w_key, l_key, surface)
                continue

            prices = _devig(row.PSW, row.PSL)
            if prices is None:
                if tour == "wta" and not abnormal:
                    elo.update(w_key, l_key, surface)
                continue
            implied_w, implied_l = prices

            # warmup rows (pre score_from): feed state, never scored and
            # never fed to the calibrator (their p_model is Elo-only when
            # the serve plane has no coverage yet — a distribution the
            # calibrator must NOT learn)
            if score_from_ts is not None and row.Date < score_from_ts:
                if tour == "wta" and not abnormal:
                    elo.update(w_key, l_key, surface)
                continue

            alpha_first_is_w = w_key <= l_key
            p_alpha_raw = p_model if alpha_first_is_w else 1.0 - p_model
            p_market_alpha = implied_w if alpha_first_is_w else implied_l

            # 3) walk-forward recalibration: the calibrator is trained in
            #    alphabetical orientation, so prediction must use that same
            #    orientation before converting back to winner/loser order.
            calibrator_trained = bool(recalibrate and cal.trained)
            p_alpha_cal = (
                cal.predict(p_alpha_raw, **covariates) if recalibrate else p_alpha_raw
            )
            p_cal = p_alpha_cal if alpha_first_is_w else 1.0 - p_alpha_cal

            edge_w = p_cal - implied_w
            edge_l = (1.0 - p_cal) - implied_l
            if edge_w >= edge_l:
                chosen_side, chosen_edge, chosen_odds = "W", edge_w, float(row.PSW)
            else:
                chosen_side, chosen_edge, chosen_odds = "L", edge_l, float(row.PSL)

            result.rows.append(
                BacktestRow(
                    date=row.Date,
                    tour=tour.upper(),
                    surface=surface or "?",
                    best_of=best_of,
                    winner=str(row.Winner),
                    loser=str(row.Loser),
                    p_elo=round(p_elo, 4),
                    p_serve=round(p_serve, 4) if p_serve is not None else None,
                    p_model=round(p_model, 4),
                    p_cal=round(p_cal, 4),
                    p_market_alpha=round(p_market_alpha, 4),
                    edge_w=round(edge_w, 4),
                    edge_l=round(edge_l, 4),
                    chosen_side=chosen_side,
                    chosen_edge=round(chosen_edge, 4),
                    chosen_odds=chosen_odds,
                    odds_w=float(row.PSW),
                    odds_l=float(row.PSL),
                    bet_won=chosen_side == "W",
                    gated=gated,
                    y_alpha=1 if alpha_first_is_w else 0,
                    p_alpha=round(p_alpha_cal, 4),
                    p_alpha_raw=round(p_alpha_raw, 4),
                    settlement_status=settlement_status,
                    termination=termination,
                    betting_population=in_population,
                    calibrator_trained=calibrator_trained,
                )
            )

            # 4) only now may anything learn from this result
            if recalibrate and not abnormal and learns:
                cal.add(p_alpha_raw, 1 if alpha_first_is_w else 0, **covariates)
            if tour == "wta" and not abnormal:
                elo.update(w_key, l_key, surface)

    return result
