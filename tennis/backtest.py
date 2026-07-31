"""Walk-forward backtest of the tennis model against closing prices.

Protocol (strictly causal, same discipline as the football pipeline):

1. Model state (Surface-Elo + serve/return tracker) is built ONLY from
   the odds-blind stats plane (ManTennisData).  A stats row enters the
   state only when its tournament start date lies before a conservative
   cutoff: match date minus 10 days (15 for Grand Slams).  Retirements
   (``match_ret``) never update the state — a retired match is not a
   real result.  Serve/return ratings consume tour-level matches only
   (challenger box scores measure the wrong opposition level; Elo still
   sees everything because Elo is opponent-adjusted by construction).
2. For every market row (tennis-data.co.uk, Pinnacle closing prices)
   we predict BEFORE knowing the result.  Retired matches are VOID for
   settlement and excluded from scoring.
3. Raw model probabilities pass a WALK-FORWARD Platt recalibration
   (2-parameter logistic on logit(p), refit as history grows, applied
   only to future rows).  Raw ratings are range-compressed; the
   calibrator restores market-level sharpness without peeking.
4. Pinnacle prices are de-vigged proportionally.  Both sides of the
   market are evaluated; a bet is placed on the side with the larger
   edge whenever it clears the threshold (never forced) AND both
   players clear the experience gate.
5. Only AFTER the prediction may a result move the state (WTA path:
   results from the odds file itself update the Elo, prediction first).

Calibration uses a stochastic outcome: rows are encoded alphabetically
(player A = alphabetically first key), so y is a real Bernoulli
variable — not the degenerate 'Winner column always won'.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import hashlib
import math
import pandas as pd

from .data_loader import load_atp_stats, load_market_odds, load_wta_ta_stats, add_normalized_names
from .elo import SurfaceElo
from .serve_model import (
    ServeReturnModel,
    is_tour_level,
    WTA_TOUR_HOLD_AVG,
    WTA_TOUR_BREAK_AVG,
)
from .simulator import simulate_match

GRAND_SLAMS = ("Australian Open", "Roland Garros", "Wimbledon", "US Open")
CUTOFF_DAYS = 10
CUTOFF_DAYS_SLAM = 15
MIN_SERVE_GAMES = 60.0   # both players need this many tracked service games
MIN_ELO_MATCHES = 20     # experience gate: below this we do not bet
RETIRED_FLAGS = {"retired", "ret", "walkover", "w/o", "def", "default"}


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

    def predict(self, p: float) -> float:
        if not self.trained:
            return p
        return _sigmoid(self.a * _logit(p) + self.b)

    def add(self, p: float, y: float) -> None:
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
    bet_won: bool
    gated: bool
    y_alpha: int
    p_alpha: float           # calibrated prob for alphabetically-first player
    p_alpha_raw: float       # raw prob for alphabetically-first player


@dataclass
class BacktestReport:
    rows: List[BacktestRow] = field(default_factory=list)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([r.__dict__ for r in self.rows])

    def summary(self, edge_thresholds=(0.0, 0.02, 0.05, 0.08, 0.10)) -> pd.DataFrame:
        frame = self.to_frame()
        out = []
        for thr in edge_thresholds:
            bets = frame[(frame["chosen_edge"] >= thr) & frame["gated"]]
            if len(bets) == 0:
                out.append({"edge>=": thr, "bets": 0})
                continue
            pnl = bets.apply(
                lambda r: (r["chosen_odds"] - 1.0) if r["bet_won"] else -1.0, axis=1
            )
            out.append(
                {
                    "edge>=": thr,
                    "bets": int(len(bets)),
                    "win_rate": round(float(bets["bet_won"].mean()), 4),
                    "roi": round(float(pnl.mean()), 4),
                    "avg_edge": round(float(bets["chosen_edge"].mean()), 4),
                    "avg_odds": round(float(bets["chosen_odds"].mean()), 3),
                }
            )
        return pd.DataFrame(out)

    def calibration(self) -> Dict[str, float]:
        frame = self.to_frame()
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

    def bias_table(self) -> pd.DataFrame:
        frame = self.to_frame()
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


def _cutoff(date: pd.Timestamp, tournament: str) -> pd.Timestamp:
    days = CUTOFF_DAYS_SLAM if tournament in GRAND_SLAMS else CUTOFF_DAYS
    return date - pd.Timedelta(days=days)


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
) -> BacktestReport:
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
    """
    stats_records = None
    stats_dates = None
    if "atp" in tours:
        stats = load_atp_stats(stats_years)
        stats = add_normalized_names(stats, "winner_name", "loser_name")
        stats = stats.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)
        stats_records = stats.to_dict("records")
        stats_dates = stats["tourney_date"].tolist()

    # WTA serve plane: Tennis Abstract leaderboard box scores (2024 -> today).
    # Same schema as the ATP stats plane; consumed through its own causal
    # pointer so serve ratings only ever see the past.
    wta_records = None
    wta_dates = None
    if "wta" in tours:
        wta_stats = load_wta_ta_stats()
        wta_stats = add_normalized_names(wta_stats, "winner_name", "loser_name")
        wta_stats = wta_stats.sort_values("tourney_date", kind="mergesort").reset_index(drop=True)
        wta_records = wta_stats.to_dict("records")
        wta_dates = wta_stats["tourney_date"].tolist()

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
    calibrators: Dict[str, WalkForwardCalibrator] = {
        t: WalkForwardCalibrator() for t in tours
    }
    stats_ptr = 0
    wta_ptr = 0
    result = BacktestReport()

    for tour in tours:
        odds = load_market_odds(odds_years, tour=tour)
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
                        serve_wta.update_from_match_row(s)

            w_key, l_key = row.winner_key, row.loser_key
            if not w_key or not l_key:
                continue
            if _is_retired(getattr(row, "Comment", None)):
                continue  # retired matches are void — no scoring, no state
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
                    p_serve = simulate_match(hold_w, hold_l, best_of=best_of).p_a_win
            p_model = (
                (1.0 - serve_weight) * p_elo + serve_weight * p_serve
                if p_serve is not None
                else p_elo
            )

            prices = _devig(row.PSW, row.PSL)
            if prices is None:
                if tour == "wta":
                    elo.update(w_key, l_key, surface)
                continue
            implied_w, implied_l = prices

            # warmup rows (pre score_from): feed state, never scored and
            # never fed to the calibrator (their p_model is Elo-only when
            # the serve plane has no coverage yet — a distribution the
            # calibrator must NOT learn)
            if score_from_ts is not None and row.Date < score_from_ts:
                if tour == "wta":
                    elo.update(w_key, l_key, surface)
                continue

            alpha_first_is_w = w_key <= l_key
            p_alpha_raw = p_model if alpha_first_is_w else 1.0 - p_model
            p_market_alpha = implied_w if alpha_first_is_w else implied_l

            # 3) walk-forward recalibration: applied BEFORE scoring this
            #    row, trained only on already-scored rows
            p_cal = cal.predict(p_model) if recalibrate else p_model
            p_alpha_cal = p_cal if alpha_first_is_w else 1.0 - p_cal

            gated = (
                elo.overall.matches(w_key) >= min_elo_matches
                and elo.overall.matches(l_key) >= min_elo_matches
            )

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
                    bet_won=chosen_side == "W",
                    gated=gated,
                    y_alpha=1 if alpha_first_is_w else 0,
                    p_alpha=round(p_alpha_cal, 4),
                    p_alpha_raw=round(p_alpha_raw, 4),
                )
            )

            # 4) only now may anything learn from this result
            if recalibrate:
                cal.add(p_alpha_raw, 1 if alpha_first_is_w else 0)
            if tour == "wta":
                elo.update(w_key, l_key, surface)

    return result
