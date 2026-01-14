"""
MULTI-MARKET PREDICTOR - CORRECTED
Mathematisch korrekte Over/Under + Next Goal Berechnung
Mit ORIGINALEN Klassennamen für Kompatibilität
"""

import math
from typing import Dict, List, Optional
from datetime import datetime


class OverUnderPredictor:
    """
    Korrigierte Over/Under Vorhersage mit Poisson
    ORIGINAL KLASSENNAME für Kompatibilität
    """
    
    def __init__(self):
        self.prediction_history = []
    
    def predict_over_under(self, match_data: Dict, minute: int) -> Dict:
        """Berechne Over/Under für alle Thresholds"""
        home_score = match_data.get('home_score', 0)
        away_score = match_data.get('away_score', 0)
        current_goals = home_score + away_score
        
        stats = match_data.get('stats') or {}
        xg_home = stats.get('xg_home') or 0
        xg_away = stats.get('xg_away') or 0
        current_xg = xg_home + xg_away
        
        expected_total = self._calculate_expected_total(current_goals, current_xg, minute)
        remaining_expected = max(0, expected_total - current_goals)
        
        thresholds_list = self._get_relevant_thresholds(current_goals)
        
        results = {}
        primary_bet = None
        
        for threshold in thresholds_list:
            analysis = self._analyze_threshold(threshold, current_goals, remaining_expected, minute)
            results[f"over_{threshold}"] = analysis
            
            if analysis['is_bettable'] and analysis['strength'] in ['VERY_STRONG', 'STRONG']:
                if not primary_bet:
                    primary_bet = threshold
        
        over_25_data = results.get('over_2.5', {})
        over_25_prob = over_25_data.get('over_probability', 50)
        
        recommendation = self._get_recommendation(results, primary_bet)
        
        return {
            'current_goals': current_goals,
            'expected_total_goals': round(expected_total, 2),
            'time_remaining': 90 - minute,
            'over_25_probability': round(over_25_prob, 1),
            'thresholds': results,
            'primary_threshold': primary_bet,
            'recommendation': recommendation,
            'confidence': self._calculate_confidence(minute, current_xg)
        }
    
    def _calculate_expected_total(self, current_goals: int, current_xg: float, minute: int) -> float:
        if minute <= 0:
            minute = 1
        
        time_remaining = max(1, 90 - minute)
        time_remaining_ratio = time_remaining / 90.0
        
        goals_rate = current_goals / minute * 90
        xg_rate = current_xg / minute * 90 if current_xg > 0 else 2.5
        
        if minute >= 60:
            expected = current_goals + (xg_rate - current_xg) * 0.6 + (goals_rate - current_goals) * 0.2
        elif minute >= 30:
            expected = current_goals + (xg_rate - current_xg) * 0.5 + time_remaining_ratio * 1.2
        else:
            expected = current_goals + current_xg * 0.4 + time_remaining_ratio * 1.5
        
        return max(current_goals, min(8.0, expected))
    
    def _get_relevant_thresholds(self, current_goals: int) -> List[float]:
        if current_goals == 0:
            return [0.5, 1.5, 2.5, 3.5]
        elif current_goals == 1:
            return [1.5, 2.5, 3.5, 4.5]
        elif current_goals == 2:
            return [2.5, 3.5, 4.5, 5.5]
        elif current_goals == 3:
            return [3.5, 4.5, 5.5]
        else:
            base = current_goals - 0.5
            return [base, base + 1, base + 2]
    
    def _analyze_threshold(self, threshold: float, current_goals: int,
                          remaining_expected: float, minute: int) -> Dict:
        goals_needed = max(0, int(threshold + 0.5) - current_goals)
        
        if current_goals > threshold:
            return {
                'threshold': threshold,
                'status': 'HIT',
                'is_bettable': False,
                'goals_needed': 0,
                'over_probability': 100.0,
                'under_probability': 0.0,
                'strength': 'HIT',
                'recommendation': f'✅ Over {threshold} HIT!'
            }
        
        over_prob = self._poisson_probability(remaining_expected, goals_needed)
        under_prob = 100 - over_prob
        
        time_remaining = 90 - minute
        if time_remaining < 15 and goals_needed >= 2:
            over_prob *= 0.7
        elif time_remaining < 30 and goals_needed >= 3:
            over_prob *= 0.8
        
        over_prob = max(5, min(95, over_prob))
        under_prob = 100 - over_prob
        
        strength = self._calculate_strength(over_prob, under_prob, goals_needed, minute)
        rec = self._threshold_recommendation(threshold, over_prob, under_prob, strength)
        
        return {
            'threshold': threshold,
            'status': 'ACTIVE',
            'is_bettable': True,
            'goals_needed': goals_needed,
            'over_probability': round(over_prob, 1),
            'under_probability': round(under_prob, 1),
            'strength': strength,
            'recommendation': rec
        }
    
    def _poisson_probability(self, expected: float, goals_needed: int) -> float:
        if expected <= 0:
            return 10.0 if goals_needed <= 1 else 5.0
        
        p_under = sum((expected ** k) * math.exp(-expected) / math.factorial(k) 
                      for k in range(goals_needed))
        return max(5, min(95, (1 - p_under) * 100))
    
    def _calculate_strength(self, over_prob: float, under_prob: float,
                           goals_needed: int, minute: int) -> str:
        difficulty_penalty = goals_needed * 3
        time_remaining = 90 - minute
        if time_remaining < 15:
            difficulty_penalty += 15
        elif time_remaining < 30:
            difficulty_penalty += 8
        
        adjusted_over = over_prob - difficulty_penalty
        
        if adjusted_over >= 75:
            return 'VERY_STRONG'
        elif adjusted_over >= 65:
            return 'STRONG'
        elif adjusted_over >= 55:
            return 'GOOD'
        elif under_prob >= 75:
            return 'UNDER_STRONG'
        elif under_prob >= 65:
            return 'UNDER_GOOD'
        else:
            return 'NEUTRAL'
    
    def _threshold_recommendation(self, threshold: float, over_prob: float,
                                  under_prob: float, strength: str) -> str:
        if strength == 'VERY_STRONG':
            return f'🔥🔥 OVER {threshold} SEHR STARK! ({over_prob:.0f}%)'
        elif strength == 'STRONG':
            return f'🔥 OVER {threshold} STARK! ({over_prob:.0f}%)'
        elif strength == 'GOOD':
            return f'✅ Over {threshold} Gut ({over_prob:.0f}%)'
        elif strength == 'UNDER_STRONG':
            return f'🔥 UNDER {threshold} STARK! ({under_prob:.0f}%)'
        elif strength == 'UNDER_GOOD':
            return f'✅ Under {threshold} Gut ({under_prob:.0f}%)'
        else:
            return f'⚠️ {threshold} Neutral'
    
    def _get_recommendation(self, results: Dict, primary_bet: Optional[float]) -> str:
        if not primary_bet:
            for key, data in results.items():
                if data.get('strength') in ['UNDER_STRONG', 'UNDER_GOOD']:
                    return data['recommendation']
            return '⚠️ Keine starke Wettmöglichkeit'
        return results[f'over_{primary_bet}']['recommendation']
    
    def _calculate_confidence(self, minute: int, xg_total: float) -> str:
        score = 0
        if minute >= 45:
            score += 30
        elif minute >= 30:
            score += 20
        if xg_total > 0:
            score += 40
        if minute >= 60:
            score += 20
        
        if score >= 70:
            return 'VERY_HIGH'
        elif score >= 50:
            return 'HIGH'
        elif score >= 30:
            return 'MEDIUM'
        else:
            return 'LOW'


class NextGoalPredictor:
    """
    Korrigierte Next Goal Vorhersage
    ORIGINAL KLASSENNAME für Kompatibilität
    """
    
    def __init__(self):
        pass
    
    def predict_next_goal(self, match_data: Dict, minute: int) -> Dict:
        stats = match_data.get('stats') or {}
        home_score = match_data.get('home_score', 0)
        away_score = match_data.get('away_score', 0)
        
        xg_home = stats.get('xg_home') or 0
        xg_away = stats.get('xg_away') or 0
        
        shots_home = stats.get('shots_home') or 0
        shots_away = stats.get('shots_away') or 0
        sot_home = stats.get('shots_on_target_home') or 0
        sot_away = stats.get('shots_on_target_away') or 0
        
        home_share, away_share = self._calculate_shares(
            xg_home, xg_away, shots_home, shots_away, sot_home, sot_away
        )
        
        no_goal_prob = self._calculate_no_goal_prob(minute, xg_home + xg_away, home_score, away_score)
        
        goal_prob = 100 - no_goal_prob
        home_prob = goal_prob * home_share
        away_prob = goal_prob * away_share
        
        home_prob, away_prob, no_goal_prob = self._apply_desperation(
            home_prob, away_prob, no_goal_prob, home_score, away_score, minute
        )
        
        total = home_prob + away_prob + no_goal_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        no_goal_prob = no_goal_prob / total * 100
        
        favorite = 'HOME' if home_prob > away_prob else 'AWAY'
        edge = abs(home_prob - away_prob)
        recommendation = self._get_recommendation(home_prob, away_prob, edge, favorite)
        
        return {
            'home_next_goal_prob': round(home_prob, 1),
            'away_next_goal_prob': round(away_prob, 1),
            'no_goal_prob': round(no_goal_prob, 1),
            'favorite': favorite,
            'edge': round(edge, 1),
            'recommendation': recommendation,
            'confidence': 'HIGH' if (xg_home + xg_away) > 0.5 else 'MEDIUM',
            'time_remaining': 90 - minute
        }
    
    def _calculate_shares(self, xg_home: float, xg_away: float,
                         shots_home: int, shots_away: int,
                         sot_home: int, sot_away: int) -> tuple:
        if xg_home + xg_away > 0:
            total = xg_home + xg_away
            return xg_home / total, xg_away / total
        elif sot_home + sot_away > 0:
            total = sot_home + sot_away
            return sot_home / total, sot_away / total
        elif shots_home + shots_away > 0:
            total = shots_home + shots_away
            return shots_home / total, shots_away / total
        else:
            return 0.53, 0.47
    
    def _calculate_no_goal_prob(self, minute: int, total_xg: float,
                                home_score: int, away_score: int) -> float:
        time_remaining = 90 - minute
        
        if time_remaining >= 60:
            base = 15
        elif time_remaining >= 45:
            base = 20
        elif time_remaining >= 30:
            base = 28
        elif time_remaining >= 15:
            base = 40
        elif time_remaining >= 5:
            base = 55
        else:
            base = 70
        
        if total_xg > 3:
            base -= 12
        elif total_xg > 2:
            base -= 8
        elif total_xg > 1:
            base -= 4
        elif total_xg < 0.5:
            base += 10
        
        current_goals = home_score + away_score
        if current_goals >= 4:
            base -= 8
        elif current_goals == 0 and minute > 60:
            base += 10
        
        return max(10, min(75, base))
    
    def _apply_desperation(self, home_prob: float, away_prob: float,
                          no_goal_prob: float, home_score: int,
                          away_score: int, minute: int) -> tuple:
        if minute < 65:
            return home_prob, away_prob, no_goal_prob
        
        if home_score < away_score:
            boost = 8 if minute >= 80 else 5
            home_prob += boost
            no_goal_prob -= boost * 0.5
        elif away_score < home_score:
            boost = 8 if minute >= 80 else 5
            away_prob += boost
            no_goal_prob -= boost * 0.5
        
        return home_prob, away_prob, max(5, no_goal_prob)
    
    def _get_recommendation(self, home_prob: float, away_prob: float,
                           edge: float, favorite: str) -> str:
        max_prob = max(home_prob, away_prob)
        
        if max_prob >= 55 and edge >= 25:
            return f'🔥🔥 {favorite} NEXT GOAL! ({max_prob:.0f}%)'
        elif max_prob >= 50 and edge >= 20:
            return f'🔥 {favorite} Next Goal ({max_prob:.0f}%)'
        elif max_prob >= 45 and edge >= 15:
            return f'✅ {favorite} leichter Vorteil ({max_prob:.0f}%)'
        elif edge < 10:
            return '⚠️ ZU KNAPP - SKIP'
        else:
            return f'⚠️ {favorite} minimaler Vorteil'


__all__ = ['OverUnderPredictor', 'NextGoalPredictor']
