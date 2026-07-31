"""
RED CARD IMPACT PREDICTOR
==========================
Berechnet WAS ALS NÄCHSTES PASSIERT nach einer Roten Karte

Basiert auf:
- Verbleibende Spielzeit (wichtigster Faktor!)
- Aktueller Spielstand
- Welches Team hat Rot (Heim/Auswärts)
- Live-Statistiken (Schüsse, xG, Druck)

The numerical factors are explicit model priors, not a validated betting edge.
"""

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class RedCardPrediction:
    """Vorhersage nach Roter Karte"""
    
    # Allgemeine Info
    minute: int  # Aktuelle Spielminute des Modell-Snapshots
    remaining_minutes: int
    red_card_team: str  # 'home' oder 'away'
    current_score: Tuple[int, int]  # (home, away)
    
    # Tor-Wahrscheinlichkeiten
    next_goal_probability: float  # Wahrscheinlichkeit dass noch ein Tor fällt
    next_goal_by_opponent: float  # Wahrscheinlichkeit dass 11-Mann-Team trifft
    next_goal_by_red_team: float  # Wahrscheinlichkeit dass 10-Mann-Team trifft
    no_more_goals: float  # Wahrscheinlichkeit kein Tor mehr
    
    # Zeit bis nächstes Tor
    expected_minutes_to_goal: float  # Erwartete Minuten bis zum nächsten Tor
    
    # Endstand-Prognose
    opponent_wins: float  # 11-Mann-Team gewinnt
    draw: float
    red_team_wins: float  # 10-Mann-Team gewinnt
    
    model_signals: list
    risk_flags: list
    
    data_quality: str
    too_late_for_signal: bool
    calibrated: bool = False
    actionable: bool = False
    context_effects: Optional[Dict] = None  # audit trail of adjustments


class RedCardImpactPredictor:
    """
    Berechnet Auswirkungen einer Roten Karte auf das Spiel
    
    All rates and red-card multipliers below are configurable priors. Outputs
    remain uncalibrated model signals until a chronological backtest says otherwise.
    """
    
    # Explicit league priors. They are inputs to the model, not measured facts
    # about the current fixture.
    BASE_TOTAL_GOALS_PER_MATCH = 2.70
    HOME_GOAL_SHARE = 0.54
    REGULAR_MATCH_MINUTES = 93
    XG_PRIOR_MINUTES = 30
    
    # Effekt der Roten Karte auf Tor-Wahrscheinlichkeit
    RED_CARD_EFFECTS = {
        'opponent_boost': 1.45,  # 11-Mann-Team +45% mehr Tore
        'red_team_penalty': 0.40,  # 10-Mann-Team nur 40% der normalen Tore
        'home_red_extra_penalty': 0.90,  # Heimrot = extra 10% Nachteil
        'away_red_extra_penalty': 0.95,  # Auswärtsrot = extra 5% Nachteil
    }

    # Context-layer priors, calibrated on the 1,132-dismissal history
    # (2025-10-22 to 2026-07-30, 6,660 matches, exposure-normalised per
    # 100 minutes at 11-v-10; baseline rates 2.81 for the 11-man team,
    # 0.69 for the 10-man team):
    # - Strength damping: a much stronger 10-man team (Barcelona vs Zuerich)
    #   stays competitive; the flat penalty would overstate the damage.
    # - Score state: U-shaped. A LEADING 10-man team concedes MORE, not
    #   less (history: 3.60/100min at +2) — the trailing favourite throws
    #   everything forward, and the 10-man attack goes to sleep (0.50).
    #   Level games are the quietest state (2.50). A trailing 10-man team
    #   opens up both ways (3.33 / 0.86 at -2).
    # - Late-game shell: history contradicts the "game falls asleep" prior.
    #   When the 10-man team still leads after minute 75, the 11-man rate
    #   rises to 3.70 vs the leading-baseline 3.14 (x1.18 escalation).
    SCORE_STATE_ADJUSTMENTS = {
        # goal_diff (red team view): (opponent_boost mult, red_penalty mult)
        2: (1.28, 0.72),
        1: (1.06, 0.93),
        0: (0.89, 1.03),
        -1: (1.04, 0.93),
        -2: (1.19, 1.25),
    }
    LATE_SHELL_MINUTE = 75
    LATE_SHELL_BOOST_MULT = 1.18
    BOOST_RANGE = (1.0, 2.0)
    PENALTY_RANGE = (0.15, 1.5)

    # Minutes-since-card layer, calibrated on the same 1,132-case history
    # (fine phase grid, per-100-min rates):
    # - SHOCK phase 0-10 min: the 10-man attack is at its weakest right
    #   after the card (0.52/100min = x0.75 vs baseline) — reorganisation,
    #   not fatigue. The 11-man rate is at baseline there (2.92).
    # - After minute 10 the 10-man attack RECOVERS above baseline
    #   (0.79-0.86 plateau = x1.15-1.25; modelled conservatively at +15%):
    #   the 11-man team opens up late and gets countered — the user's
    #   Ferencvaros pattern, confirmed by the large sample.
    # - The 11-man "fatigue cliff" from the 43-case probe did NOT survive
    #   the large sample: rates are flat (2.83/2.97/2.93). Modelled as a
    #   small +5% plateau between minutes 20-30 only.
    FATIGUE_SHOCK_MINUTES = 10
    FATIGUE_SHOCK_PENALTY = 0.25  # -25% red-team attack in the shock phase
    FATIGUE_LATE_PENALTY_GAIN = 0.15  # +15% red-team attack after the shock
    FATIGUE_FREE_MINUTES = 20
    FATIGUE_FULL_MINUTES = 30
    FATIGUE_BOOST_GAIN = 0.05   # +5% opponent rate plateau from minute 30

    @classmethod
    def _fatigue_multipliers(
        cls,
        minute: int,
        red_card_minute: Optional[int],
    ) -> Tuple[float, float, Optional[int]]:
        """Return (boost_mult, penalty_mult, minutes_since_card).

        Fails closed to (1.0, 1.0, None) when the card minute is unknown.
        """
        if (
            red_card_minute is None
            or isinstance(red_card_minute, bool)
            or not isinstance(red_card_minute, int)
            or red_card_minute < 0
            or red_card_minute > minute
        ):
            return 1.0, 1.0, None
        since = minute - red_card_minute
        ramp = min(
            1.0,
            max(0.0, (since - cls.FATIGUE_FREE_MINUTES))
            / (cls.FATIGUE_FULL_MINUTES - cls.FATIGUE_FREE_MINUTES),
        )
        if since <= cls.FATIGUE_SHOCK_MINUTES:
            penalty_mult = 1.0 - cls.FATIGUE_SHOCK_PENALTY
        else:
            penalty_mult = 1.0 + cls.FATIGUE_LATE_PENALTY_GAIN
        return (
            1.0 + cls.FATIGUE_BOOST_GAIN * ramp,
            penalty_mult,
            since,
        )

    @staticmethod
    def _clamp(value: float, bounds: Tuple[float, float]) -> float:
        return max(bounds[0], min(bounds[1], value))

    @classmethod
    def context_adjusted_effects(
        cls,
        red_card_team: str,
        home_goals: int,
        away_goals: int,
        minute: int,
        prior_home_goals: Optional[float] = None,
        prior_away_goals: Optional[float] = None,
        red_card_minute: Optional[int] = None,
    ) -> Dict:
        """Score-state-, strength- and fatigue-aware red card multipliers.

        Layers documented context priors on RED_CARD_EFFECTS. Missing priors
        fail closed to the unadjusted base effect. Returns the adjusted
        multipliers plus an audit trail of every applied adjustment.
        """
        if red_card_team not in {'home', 'away'}:
            raise ValueError("red_card_team must be 'home' or 'away'")
        base = cls.RED_CARD_EFFECTS
        boost = float(base['opponent_boost'])
        penalty = float(base['red_team_penalty'])
        applied = []

        # 1. Strength damping from pre-match goal priors.
        strength_ratio = None
        if (
            prior_home_goals is not None
            and prior_away_goals is not None
            and prior_home_goals > 0
            and prior_away_goals > 0
        ):
            if red_card_team == 'home':
                strength_ratio = prior_home_goals / prior_away_goals
            else:
                strength_ratio = prior_away_goals / prior_home_goals
            if strength_ratio > 1.0:
                log_r = math.log(strength_ratio)
                penalty = 1.0 - (1.0 - penalty) / (1.0 + log_r)
                boost = 1.0 + (boost - 1.0) / (1.0 + 0.7 * log_r)
                applied.append(
                    f"strength damping (red team {strength_ratio:.2f}x stronger)"
                )

        # 2. Score state from the red team's perspective.
        if red_card_team == 'home':
            goal_diff = home_goals - away_goals
        else:
            goal_diff = away_goals - home_goals
        clamped_diff = max(-2, min(2, goal_diff))
        boost_mult, penalty_mult = cls.SCORE_STATE_ADJUSTMENTS[clamped_diff]
        if (boost_mult, penalty_mult) != (1.00, 1.00):
            boost *= boost_mult
            penalty *= penalty_mult
            applied.append(
                f"score state {goal_diff:+d} (history-calibrated U-shape)"
            )

        # 3. Late-game escalation: history shows the trailing side throws
        # everything forward after minute 75 when the 10-man team still
        # leads (3.70 vs 3.14 baseline) — the shell cracks MORE, not less.
        if goal_diff >= 1 and minute >= cls.LATE_SHELL_MINUTE:
            boost *= cls.LATE_SHELL_BOOST_MULT
            applied.append(f"late escalation (minute {minute})")

        # 4. Minutes-since-card layer: shock phase first (10-man attack at
        # its weakest right after the card), then recovery above baseline
        # as the 11-man team opens up; small +5% opponent plateau 20-30.
        fatigue_boost, fatigue_penalty, since_card = cls._fatigue_multipliers(
            minute, red_card_minute
        )
        if since_card is not None and (fatigue_boost != 1.0 or fatigue_penalty != 1.0):
            boost *= fatigue_boost
            penalty *= fatigue_penalty
            phase = "shock phase" if since_card <= cls.FATIGUE_SHOCK_MINUTES else "fatigue ramp"
            applied.append(f"{phase} ({since_card} min at 10 men)")

        return {
            'opponent_boost': cls._clamp(boost, cls.BOOST_RANGE),
            'red_team_penalty': cls._clamp(penalty, cls.PENALTY_RANGE),
            'home_red_extra_penalty': base['home_red_extra_penalty'],
            'away_red_extra_penalty': base['away_red_extra_penalty'],
            'strength_ratio': strength_ratio,
            'goal_diff_red_team': goal_diff,
            'minutes_since_card': since_card,
            'adjustments': applied,
            'context_used': bool(applied),
        }
    
    def __init__(self):
        pass

    @staticmethod
    def _optional_nonnegative(value, maximum: float = 20.0) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric) or numeric < 0 or numeric > maximum:
            return None
        return numeric

    @staticmethod
    def _poisson_probability(goals: int, mean: float) -> float:
        if mean == 0:
            return 1.0 if goals == 0 else 0.0
        return math.exp(-mean) * mean ** goals / math.factorial(goals)

    @classmethod
    def _final_result_probabilities(
        cls,
        home_goals: int,
        away_goals: int,
        remaining_home_mean: float,
        remaining_away_mean: float,
    ) -> Tuple[float, float, float]:
        """Return home/draw/away probabilities conditional on the current score."""
        largest_mean = max(remaining_home_mean, remaining_away_mean)
        max_future_goals = max(10, math.ceil(largest_mean + 8 * math.sqrt(largest_mean + 1)))

        home_win = draw = away_win = total_mass = 0.0
        for future_home in range(max_future_goals + 1):
            home_probability = cls._poisson_probability(future_home, remaining_home_mean)
            for future_away in range(max_future_goals + 1):
                probability = home_probability * cls._poisson_probability(
                    future_away, remaining_away_mean
                )
                total_mass += probability
                final_home = home_goals + future_home
                final_away = away_goals + future_away
                if final_home > final_away:
                    home_win += probability
                elif final_home < final_away:
                    away_win += probability
                else:
                    draw += probability

        if total_mass <= 0:
            raise ValueError("could not normalize final-result probabilities")
        return home_win / total_mass, draw / total_mass, away_win / total_mass
    
    def predict(
        self,
        minute: int,
        home_goals: int,
        away_goals: int,
        red_card_team: str,  # 'home' oder 'away'
        live_stats: Optional[Dict] = None,
        prior_home_goals: Optional[float] = None,
        prior_away_goals: Optional[float] = None,
        red_card_minute: Optional[int] = None,
    ) -> RedCardPrediction:
        """
        Hauptfunktion: Berechne was als nächstes passiert

        Args:
            minute: Aktuelle Spielminute des Modell-Snapshots
            home_goals: Aktuelle Heimtore
            away_goals: Aktuelle Auswärtstore
            red_card_team: 'home' oder 'away' - wer hat Rot bekommen
            live_stats: Optional - {shots_home, shots_away, xg_home, xg_away, ...}
            prior_home_goals: Optional - Prematch-Torerwartung Heim (staerkt
                das Kontext-Adjustment: staerkeres 10-Mann-Team wird weniger
                bestraft; Spielstand-Layer ist an der 1.132-Faelle-Historie
                kalibriert: U-Form, führendes 10-Mann-Team kassiert mehr)
            prior_away_goals: Optional - Prematch-Torerwartung Auswaerts
            red_card_minute: Optional - Minute des Platzverweises. Steuert
                die Minuten-seit-Karte-Schicht: Schockphase 0-10 Minuten
                (10-Mann-Angriff gedämpft), danach Erholung ueber Baseline,
                kleine 11-Mann-Anhebung ab Minute 20-30.

        Returns:
            RedCardPrediction mit allen Berechnungen
        """
        if isinstance(minute, bool) or not isinstance(minute, int) or not 0 <= minute <= self.REGULAR_MATCH_MINUTES:
            raise ValueError("minute must be an integer between 0 and 93")
        if (
            isinstance(home_goals, bool)
            or isinstance(away_goals, bool)
            or not isinstance(home_goals, int)
            or not isinstance(away_goals, int)
            or home_goals < 0
            or away_goals < 0
            or home_goals > 30
            or away_goals > 30
        ):
            raise ValueError("goals cannot be negative")
        if red_card_team not in {'home', 'away'}:
            raise ValueError("red_card_team must be 'home' or 'away'")
        if live_stats is not None and not isinstance(live_stats, dict):
            raise ValueError("live_stats must be a mapping or None")
        
        remaining = max(0, self.REGULAR_MATCH_MINUTES - minute)
        
        # Zu spät für Wetten?
        too_late = remaining <= 3
        
        # =====================================================
        # 1. TOR-WAHRSCHEINLICHKEITEN BERECHNEN
        # =====================================================
        
        opponent = 'away' if red_card_team == 'home' else 'home'

        total_rate = self.BASE_TOTAL_GOALS_PER_MATCH / self.REGULAR_MATCH_MINUTES
        home_goal_rate = total_rate * self.HOME_GOAL_SHARE
        away_goal_rate = total_rate * (1.0 - self.HOME_GOAL_SHARE)

        xg_home = self._optional_nonnegative((live_stats or {}).get('xg_home'))
        xg_away = self._optional_nonnegative((live_stats or {}).get('xg_away'))
        has_live_xg = xg_home is not None and xg_away is not None and minute > 0
        if has_live_xg:
            # Gamma-Poisson style shrinkage: 30 prior minutes prevent a noisy
            # early xG reading from replacing the league-rate prior outright.
            home_goal_rate = (
                home_goal_rate * self.XG_PRIOR_MINUTES + xg_home
            ) / (self.XG_PRIOR_MINUTES + minute)
            away_goal_rate = (
                away_goal_rate * self.XG_PRIOR_MINUTES + xg_away
            ) / (self.XG_PRIOR_MINUTES + minute)

        effects = self.context_adjusted_effects(
            red_card_team,
            home_goals,
            away_goals,
            minute,
            prior_home_goals=prior_home_goals,
            prior_away_goals=prior_away_goals,
            red_card_minute=red_card_minute,
        )
        if red_card_team == 'home':
            home_goal_rate *= (
                effects['red_team_penalty']
                * effects['home_red_extra_penalty']
            )
            away_goal_rate *= effects['opponent_boost']
            opponent_goal_rate = away_goal_rate
            red_team_goal_rate = home_goal_rate
        else:
            away_goal_rate *= (
                effects['red_team_penalty']
                * effects['away_red_extra_penalty']
            )
            home_goal_rate *= effects['opponent_boost']
            opponent_goal_rate = home_goal_rate
            red_team_goal_rate = away_goal_rate
        
        # Berechne Wahrscheinlichkeiten für verbleibende Zeit
        opponent_scores = 1 - math.exp(-opponent_goal_rate * remaining)
        red_team_scores = 1 - math.exp(-red_team_goal_rate * remaining)
        
        # Mindestens einer trifft
        # P(mindestens 1 Tor) = 1 - P(keiner trifft)
        no_goals_prob = math.exp(-(opponent_goal_rate + red_team_goal_rate) * remaining)
        any_goal_prob = 1 - no_goals_prob
        
        # Normalisiere für "wer trifft als nächstes" (gegeben dass ein Tor fällt)
        total_goal_rate = opponent_goal_rate + red_team_goal_rate
        if total_goal_rate > 0:
            next_by_opponent = (opponent_goal_rate / total_goal_rate) * any_goal_prob
            next_by_red_team = (red_team_goal_rate / total_goal_rate) * any_goal_prob
        else:
            next_by_opponent = 0
            next_by_red_team = 0
        
        # =====================================================
        # 2. ERWARTETE ZEIT BIS NÄCHSTES TOR
        # =====================================================
        
        combined_goal_rate = opponent_goal_rate + red_team_goal_rate
        if combined_goal_rate > 0 and remaining > 0 and any_goal_prob > 0:
            expected_minutes = (
                1 / combined_goal_rate
                - remaining * math.exp(-combined_goal_rate * remaining) / any_goal_prob
            )
        else:
            expected_minutes = remaining
        
        # =====================================================
        # 3. ENDSTAND-PROGNOSE
        # =====================================================
        home_win, draw_prob, away_win = self._final_result_probabilities(
            home_goals,
            away_goals,
            home_goal_rate * remaining,
            away_goal_rate * remaining,
        )
        if red_card_team == 'home':
            opponent_wins = away_win
            red_team_wins = home_win
        else:
            opponent_wins = home_win
            red_team_wins = away_win
        
        # =====================================================
        # 4. MODEL SIGNALS (NO MARKET PRICE)
        # =====================================================
        
        model_signals = []
        risk_flags = []
        
        # Nur empfehlen wenn genug Zeit
        if remaining >= 10:
            # Gegner Over 0.5 Tore (in verbleibender Zeit)
            if next_by_opponent >= 0.55:
                model_signals.append(f"{opponent.upper()} next-goal estimate: {next_by_opponent*100:.0f}%")
            
            # Gegner gewinnt
            if opponent_wins >= 0.45 and remaining >= 20:
                model_signals.append(f"{opponent.upper()} result estimate: {opponent_wins*100:.0f}%")
            
            # Under X.5 (weil 10 Mann defensiver)
            if remaining >= 15 and no_goals_prob >= 0.35:
                model_signals.append(f"No-more-goals estimate: {no_goals_prob*100:.0f}%")
        
        # Risk flags for model outputs that remain especially weak
        # BTTS - 10-Mann-Team trifft selten
        if red_team_scores < 0.25:
            risk_flags.append(f"BTTS model probability is reduced: {red_team_scores*100:.0f}%")
        
        # 10-Mann-Team gewinnt - sehr unwahrscheinlich
        if red_team_wins < 0.25:
            risk_flags.append(f"{red_card_team.upper()} result model probability: {red_team_wins*100:.0f}%")
        
        if too_late:
            risk_flags.append("Too little remaining time for a useful model signal")
        
        # =====================================================
        # 5. DATA QUALITY
        # =====================================================
        
        if has_live_xg and minute >= 15:
            data_quality = 'MEDIUM'
        else:
            data_quality = 'LIMITED'
        
        # =====================================================
        # RETURN PREDICTION
        # =====================================================
        
        return RedCardPrediction(
            minute=minute,
            remaining_minutes=remaining,
            red_card_team=red_card_team,
            current_score=(home_goals, away_goals),
            
            next_goal_probability=any_goal_prob,
            next_goal_by_opponent=next_by_opponent,
            next_goal_by_red_team=next_by_red_team,
            no_more_goals=no_goals_prob,
            
            expected_minutes_to_goal=expected_minutes,
            
            opponent_wins=opponent_wins,
            draw=draw_prob,
            red_team_wins=red_team_wins,
            
            model_signals=model_signals,
            risk_flags=risk_flags,
            
            data_quality=data_quality,
            too_late_for_signal=too_late,
            context_effects=effects
        )
    
    def format_prediction(
        self, 
        prediction: RedCardPrediction,
        home_team: str,
        away_team: str,
        red_card_minute: Optional[int] = None,
    ) -> str:
        """
        Formatiere Prediction als lesbaren Text (für Telegram/Display)
        """
        
        # Wer hat Rot?
        red_team_name = home_team if prediction.red_card_team == 'home' else away_team
        opponent_name = away_team if prediction.red_card_team == 'home' else home_team
        
        # Score
        h, a = prediction.current_score
        
        red_card_minute_label = (
            f"Minute {red_card_minute}'"
            if red_card_minute is not None
            else "nicht erfasst"
        )

        output = f"""
🔴 *ROTE KARTE ANALYSE*

*Match:* {home_team} vs {away_team}
*Spielstand:* {h}-{a}
*Rot für:* {red_team_name}
*Platzverweis:* {red_card_minute_label}
*Modell-Snapshot:* Minute {prediction.minute}'
*Verbleibend:* ~{prediction.remaining_minutes} Minuten

━━━━━━━━━━━━━━━━━━━━━━

📊 *WAS PASSIERT ALS NÄCHSTES?*

*Nächstes Tor fällt:* {prediction.next_goal_probability*100:.0f}%
├─ {opponent_name}: {prediction.next_goal_by_opponent*100:.0f}%
├─ {red_team_name}: {prediction.next_goal_by_red_team*100:.0f}%
└─ Kein Tor mehr: {prediction.no_more_goals*100:.0f}%

⏱️ *Erwartete Zeit bis Tor:* ~{prediction.expected_minutes_to_goal:.0f} Min

━━━━━━━━━━━━━━━━━━━━━━

🏆 *ENDSTAND-PROGNOSE:*

{opponent_name} gewinnt: {prediction.opponent_wins*100:.0f}%
Unentschieden: {prediction.draw*100:.0f}%
{red_team_name} gewinnt: {prediction.red_team_wins*100:.0f}%

━━━━━━━━━━━━━━━━━━━━━━

💡 *EXPLORATORY ESTIMATES (NOT ACTIONABLE):*
"""
        
        if prediction.too_late_for_signal:
            output += "\nToo little time for a useful exploratory estimate.\n"
        else:
            if prediction.model_signals:
                for signal in prediction.model_signals:
                    output += f"\n{signal}"
            else:
                output += "\nNo clear exploratory estimate"
        
        output += "\n\n⚠️ *RISK FLAGS:*"
        if prediction.risk_flags:
            for flag in prediction.risk_flags:
                output += f"\n{flag}"
        
        output += f"\n\n📊 *Data quality:* {prediction.data_quality}"
        
        return output


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":
    predictor = RedCardImpactPredictor()
    
    print("="*60)
    print("TEST 1: Rot in Minute 35, Spielstand 1-1, Heimteam Rot")
    print("="*60)
    
    pred = predictor.predict(
        minute=35,
        home_goals=1,
        away_goals=1,
        red_card_team='home'
    )
    
    print(
        predictor.format_prediction(pred, "Bayern Munich", "Borussia Dortmund")
        .encode("ascii", "replace")
        .decode("ascii")
    )
    
    print("\n" + "="*60)
    print("TEST 2: Red card at minute 88, score 2-1, away team red")
    print("="*60)
    
    pred = predictor.predict(
        minute=88,
        home_goals=2,
        away_goals=1,
        red_card_team='away'
    )
    
    print(predictor.format_prediction(pred, "Real Madrid", "Barcelona"))
    
    print("\n" + "="*60)
    print("TEST 3: Red card at minute 60, score 0-0, away team red")
    print("="*60)
    
    pred = predictor.predict(
        minute=60,
        home_goals=0,
        away_goals=0,
        red_card_team='away'
    )
    
    print(predictor.format_prediction(pred, "Liverpool", "Manchester City"))
