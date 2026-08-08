"""Daily tennis prediction + gate evaluation.

One function turns a fixture into a full market sheet: calibrated win
probabilities plus every simulator market (set totals, game totals,
handicaps, correct scores, tiebreak).  A recommendation is only ever
issued when EVERY gate is green — the same discipline as football:

1. surface gate   — Hard court only (backtest: clay/grass negative)
2. experience     — both players >= MIN_ELO_MATCHES tracked matches
3. serve data     — both players >= MIN_SERVE_GAMES tracked games
                    (otherwise the blend is not what was backtested)
4. uncertainty    — selection-region calibration risk is deducted explicitly
5. expected value — risk-adjusted EV against the offered price >= 3%
6. price sanity   — no corrupt prices (<= 1.0)

Nothing here knows the result.  Feed N1Bet prices manually (the app
design requires manual price entry anyway) and the module tells you
BET or NO BET with the exact reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Dict, List, Optional, Tuple

from betting_math import (
    MINIMUM_RISK_ADJUSTED_ROI_PERCENT,
    BettingMathError,
    evaluate_market_price,
    minimum_recommendation_odds,
)

from .backtest import MIN_ELO_MATCHES, MIN_SERVE_GAMES
from .data_loader import resolve_player_name_key
from .model_state import ModelState
from .simulator import MatchMarkets, simulate_match

ALLOWED_SURFACES = ("Hard",)       # backtest evidence: clay/grass negative
MIN_EXPECTED_ROI = MINIMUM_RISK_ADJUSTED_ROI_PERCENT / 100.0
# The selected ATP-Hard backtest region was materially overconfident. This
# explicit deduction is conservative model risk, not a claimed confidence
# interval. It is separate from the offered price.
WINNER_PROBABILITY_HAIRCUT = 0.15
# Set markets passed calibration checks but have no historical price/ROI
# benchmark. They remain Shadow-only with a separate uncertainty deduction.
SIDE_MARKET_PROBABILITY_HAIRCUT = 0.10


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str


@dataclass
class TennisPrediction:
    player_a: str
    player_b: str
    surface: str
    best_of: int
    p_a_raw: float
    p_a_cal: float
    p_b_cal: float
    markets: Optional[MatchMarkets]
    gates: List[GateResult] = field(default_factory=list)
    recommended_side: Optional[str] = None   # 'A' or 'B'
    recommended_edge: float = 0.0
    recommended_odds: float = 0.0

    @property
    def all_green(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def verdict(self) -> str:
        if self.recommended_side and self.all_green:
            return "WETTE"
        return "KEINE WETTE"

    def market_summary(self) -> Dict[str, float]:
        """Headline numbers for the UI / shadow store."""
        out: Dict[str, float] = {
            "p_a_cal": round(self.p_a_cal, 4),
            "p_b_cal": round(self.p_b_cal, 4),
        }
        if self.markets is not None:
            m = self.markets
            out["expected_games"] = round(m.expected_total_games, 2)
            out["p_tiebreak"] = round(m.p_tiebreak_in_match, 4)
            if m.best_of == 3:
                over_25 = m.over_sets(2.5)
                out["over_2_5_sets"] = round(over_25, 4)
                out["under_2_5_sets"] = round(1.0 - over_25, 4)
                # set handicap ±1.5 == straight-sets win, calibration-tested
                # on 9.6k ATP matches (RMS 3.7% in the betting region)
                out["set_handicap_a_minus_1_5"] = round(m.correct_scores.get((2, 0), 0.0), 4)
                out["set_handicap_b_minus_1_5"] = round(m.correct_scores.get((0, 2), 0.0), 4)
            else:
                out["over_3_5_sets"] = round(m.over_sets(3.5), 4)
                out["over_4_5_sets"] = round(m.over_sets(4.5), 4)
            for line in (20.5, 21.5, 22.5, 23.5):
                out[f"over_{line}_games"] = round(m.over_games(line), 4)
        return out


def predict_match(
    state: ModelState,
    player_a: str,
    player_b: str,
    surface: Optional[str],
    best_of: int = 3,
    odds_a: Optional[float] = None,
    odds_b: Optional[float] = None,
    minimum_expected_roi: float = MIN_EXPECTED_ROI,
    tour: str = "ATP",
    indoor: Optional[bool] = None,
) -> TennisPrediction:
    """Full prediction + gate evaluation for one fixture.

    ``player_a`` / ``player_b`` may be any spelling — normalised here.
    Prices are optional: without them no price/EV gate is evaluated (the
    prediction itself is always computed).

    ``indoor`` selects the environment for Hard matches (pure indoor
    bucket + environment log5 constant); None means unknown and uses the
    not-indoor bucket, which also carries the unrated-flag matches.

    WTA runs in Elo-only mode: no serve boxscore feed exists, so the
    serve gate is reported as a pass-through and the separate (thinner)
    WTA Platt calibration is applied.
    """
    tour = str(tour or "ATP").upper()
    is_wta = tour == "WTA"
    if (
        isinstance(minimum_expected_roi, bool)
        or not isinstance(minimum_expected_roi, (int, float))
        or not math.isfinite(float(minimum_expected_roi))
        or not 0.0 <= float(minimum_expected_roi) <= 1.0
    ):
        raise ValueError("minimum_expected_roi must be between 0 and 1")
    known_players = state.elo.known_players()
    key_a = resolve_player_name_key(player_a, known_players)
    key_b = resolve_player_name_key(player_b, known_players)
    identity_a = key_a in known_players
    identity_b = key_b in known_players
    surface_model = surface if surface in ("Hard", "Clay", "Grass", "Carpet") else None
    surface = surface if surface else "Unbekannt"
    if best_of not in (3, 5):
        best_of = 3

    # --- model probabilities ------------------------------------------------
    now = datetime.now(timezone.utc)
    p_elo = state.elo.win_probability(key_a, key_b, surface_model)
    p_serve = None
    serve_games_a = state.serve.service_games(key_a, as_of=now)
    serve_games_b = state.serve.service_games(key_b, as_of=now)
    have_serve = serve_games_a >= MIN_SERVE_GAMES and serve_games_b >= MIN_SERVE_GAMES

    markets = None
    if have_serve:
        hold_a, hold_b = state.serve.expected_hold_probabilities(
            key_a, key_b, surface_model, as_of=now, indoor=indoor
        )
        markets = simulate_match(hold_a, hold_b, best_of=best_of)
        p_serve = markets.p_a_win
    p_raw = (
        (1.0 - state.serve_weight) * p_elo + state.serve_weight * p_serve
        if p_serve is not None
        else p_elo
    )
    p_cal = state.calibrate_match(p_raw, key_a, key_b, tour=tour)

    # --- gates ---------------------------------------------------------------
    matches_a = state.elo.overall.matches(key_a)
    matches_b = state.elo.overall.matches(key_b)
    experience = GateResult(
        "Erfahrung",
        matches_a >= MIN_ELO_MATCHES and matches_b >= MIN_ELO_MATCHES,
        f"{player_a}: {matches_a} Matches, {player_b}: {matches_b} (min. {MIN_ELO_MATCHES})",
    )
    identity = GateResult(
        "Spieler-Zuordnung",
        identity_a and identity_b,
        (
            "beide Spielernamen der historischen Datenbasis zugeordnet"
            if identity_a and identity_b
            else "nicht eindeutig gefunden: "
            + ", ".join(
                name
                for name, found in ((player_a, identity_a), (player_b, identity_b))
                if not found
            )
        ),
    )
    if is_wta:
        # WTA release verdict, tested twice with real data:
        #  - Elo-only, 2019-2024:            Hard -0.7% ROI @ >=12% edge
        #  - Elo+serve (TA boxscores), 2025+: Hard -16.6% ROI @ >=12% edge
        # Serve ratings don't separate WTA players (30% break rate vs 23%
        # ATP) — the market prices everything we know.  Shadow observation
        # ONLY: cards carry p_cal so we keep collecting out-of-sample data
        # against real bookmaker prices.
        gates: List[GateResult] = [
            GateResult(
                "WTA-Freigabe",
                False,
                "Zweifach getestet: Elo-only −0,7 % (2019–24), Elo+Serve −16,6 % (2025–26) ROI — kein Edge, nur Shadow-Beobachtung",
            ),
            experience,
            GateResult(
                "Aufschlag-Daten",
                True,
                "WTA: kein Boxscore-Feed — Elo-Modus",
            ),
            identity,
        ]
    else:
        gates = [
            GateResult(
                "Belag",
                surface in ALLOWED_SURFACES,
                f"{surface} ({'erlaubt' if surface in ALLOWED_SURFACES else 'nicht erlaubt: Backtest negativ'})",
            ),
            experience,
            GateResult(
                "Aufschlag-Daten",
                have_serve,
                f"{serve_games_a:.0f} / {serve_games_b:.0f} Service-Games (min. {MIN_SERVE_GAMES:.0f})",
            ),
            identity,
        ]

    recommended_side = None
    recommended_edge = 0.0
    recommended_odds = 0.0
    if odds_a is not None and odds_b is not None:
        prices_ok = odds_a > 1.0 and odds_b > 1.0
        metrics_a = metrics_b = None
        if prices_ok:
            try:
                metrics_a = evaluate_market_price(
                    p_cal * 100.0,
                    odds_a,
                    probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
                )
                metrics_b = evaluate_market_price(
                    (1.0 - p_cal) * 100.0,
                    odds_b,
                    probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
                )
            except BettingMathError:
                prices_ok = False
                metrics_a = metrics_b = None
        roi_a = (
            metrics_a.risk_adjusted_expected_roi / 100.0
            if metrics_a is not None
            else float("-inf")
        )
        roi_b = (
            metrics_b.risk_adjusted_expected_roi / 100.0
            if metrics_b is not None
            else float("-inf")
        )
        minimum_a = minimum_recommendation_odds(
            p_cal * 100.0,
            probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
            minimum_expected_roi_percent=minimum_expected_roi * 100.0,
        )
        minimum_b = minimum_recommendation_odds(
            (1.0 - p_cal) * 100.0,
            probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
            minimum_expected_roi_percent=minimum_expected_roi * 100.0,
        )
        options = []
        if (
            prices_ok
            and minimum_a is not None
            and odds_a + 1e-9 >= minimum_a
            and roi_a >= minimum_expected_roi
        ):
            options.append((roi_a, "A", metrics_a, odds_a))
        if (
            prices_ok
            and minimum_b is not None
            and odds_b + 1e-9 >= minimum_b
            and roi_b >= minimum_expected_roi
        ):
            options.append((roi_b, "B", metrics_b, odds_b))
        if options:
            _roi, recommended_side, selected_metrics, recommended_odds = max(options)
            recommended_edge = selected_metrics.risk_adjusted_edge / 100.0
        gates.append(
            GateResult(
                "Quote/Risiko-EV",
                bool(options),
                (
                    f"Nach {WINNER_PROBABILITY_HAIRCUT:+.0%} Modellabschlag: "
                    f"EV {player_a} {roi_a:+.1%}, {player_b} {roi_b:+.1%} "
                    f"(min. {minimum_expected_roi:+.1%})"
                    if prices_ok
                    else "unplausible Quote"
                ),
            )
        )

    return TennisPrediction(
        player_a=player_a,
        player_b=player_b,
        surface=surface,
        best_of=best_of,
        p_a_raw=round(p_raw, 4),
        p_a_cal=round(p_cal, 4),
        p_b_cal=round(1.0 - p_cal, 4),
        markets=markets,
        gates=gates,
        recommended_side=recommended_side,
        recommended_edge=round(recommended_edge, 4),
        recommended_odds=recommended_odds,
    )
