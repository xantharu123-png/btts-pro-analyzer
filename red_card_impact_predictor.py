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
    minute: int
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
        live_stats: Optional[Dict] = None
    ) -> RedCardPrediction:
        """
        Hauptfunktion: Berechne was als nächstes passiert
        
        Args:
            minute: Minute der Roten Karte
            home_goals: Aktuelle Heimtore
            away_goals: Aktuelle Auswärtstore
            red_card_team: 'home' oder 'away' - wer hat Rot bekommen
            live_stats: Optional - {shots_home, shots_away, xg_home, xg_away, ...}
        
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

        if red_card_team == 'home':
            home_goal_rate *= (
                self.RED_CARD_EFFECTS['red_team_penalty']
                * self.RED_CARD_EFFECTS['home_red_extra_penalty']
            )
            away_goal_rate *= self.RED_CARD_EFFECTS['opponent_boost']
            opponent_goal_rate = away_goal_rate
            red_team_goal_rate = home_goal_rate
        else:
            away_goal_rate *= (
                self.RED_CARD_EFFECTS['red_team_penalty']
                * self.RED_CARD_EFFECTS['away_red_extra_penalty']
            )
            home_goal_rate *= self.RED_CARD_EFFECTS['opponent_boost']
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
            too_late_for_signal=too_late
        )
    
    def format_prediction(
        self, 
        prediction: RedCardPrediction,
        home_team: str,
        away_team: str
    ) -> str:
        """
        Formatiere Prediction als lesbaren Text (für Telegram/Display)
        """
        
        # Wer hat Rot?
        red_team_name = home_team if prediction.red_card_team == 'home' else away_team
        opponent_name = away_team if prediction.red_card_team == 'home' else home_team
        
        # Score
        h, a = prediction.current_score
        
        output = f"""
🔴 *ROTE KARTE ANALYSE*

*Match:* {home_team} vs {away_team}
*Spielstand:* {h}-{a}
*Rot für:* {red_team_name} (Minute {prediction.minute}')
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
