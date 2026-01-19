"""
BEST BET FINDER - Findet die WERTVOLLSTE Wette über ALLE Märkte
Analysiert jedes Live-Match und empfiehlt den höchsten VALUE (nicht Wahrscheinlichkeit!)

WICHTIG: 
- Sortiert nach VALUE, nicht nach Wahrscheinlichkeit
- Value = (Probability × Fair_Odds) - 1
- Eine 70% Wette mit Quote 1.60 ist besser als 90% mit Quote 1.05

MÄRKTE:
1. Match Result (1X2)
2. Over/Under Goals (0.5-6.5)
3. Over/Under Cards (2.5-6.5)
4. Over/Under Corners (7.5-13.5)
5. Over/Under Shots (15.5-25.5)
6. BTTS Yes/No
7. Clean Sheet Home/Away
8. Team Total Goals
9. Next Goal Home/Away/None
10. Halftime Result
11. Asian Handicap
12. Exact Score Top 3

STATISTISCH FUNDIERT - Nutzt alle bisherigen Berechnungen!
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class BestBetFinder:
    """
    Findet die WERTVOLLSTE Wette über alle Märkte (Value-basiert, nicht Probability)
    """
    
    def __init__(self):
        self.all_bets = []
    
    def find_best_bet(self, match_data: Dict, minute: int, stats: Dict) -> Dict:
        """
        Analysiere ALLE möglichen Wetten und finde den HÖCHSTEN VALUE
        
        WICHTIG: Sortiert nach Value, nicht nach Wahrscheinlichkeit!
        - Eine 70% Wette mit +8% Value schlägt eine 90% Wette mit +2% Value
        
        Returns:
        {
            'best_bet': {
                'market': 'Over 2.5 Goals',
                'selection': 'Over',
                'probability': 72.3,
                'value': 8.5,
                'fair_odds': 1.38,
                'est_market_odds': 1.29,
                'strength': 'STRONG',
                'reasoning': 'Current: 2 goals, xG velocity high...'
            },
            'top_5': [list of top 5 VALUE bets],
            'all_markets': {dict of all calculated probabilities}
        }
        """
        home_team = match_data['home_team']
        away_team = match_data['away_team']
        home_score = match_data['home_score']
        away_score = match_data['away_score']
        
        all_probabilities = []
        
        # =============================================
        # 1. MATCH RESULT (1X2)
        # =============================================
        result_probs = self._calculate_match_result(
            home_score, away_score, 
            stats.get('xg_home', 0), stats.get('xg_away', 0),
            minute, stats
        )
        
        all_probabilities.append({
            'market': 'Match Result',
            'selection': '1 (Home Win)',
            'probability': result_probs['home_win'],
            'current_status': f"{home_score}-{away_score}",
            'reasoning': result_probs['home_reasoning']
        })
        
        all_probabilities.append({
            'market': 'Match Result',
            'selection': 'X (Draw)',
            'probability': result_probs['draw'],
            'current_status': f"{home_score}-{away_score}",
            'reasoning': result_probs['draw_reasoning']
        })
        
        all_probabilities.append({
            'market': 'Match Result',
            'selection': '2 (Away Win)',
            'probability': result_probs['away_win'],
            'current_status': f"{home_score}-{away_score}",
            'reasoning': result_probs['away_reasoning']
        })
        
        # =============================================
        # 2. OVER/UNDER GOALS
        # =============================================
        goals_probs = self._calculate_goals_markets(
            home_score, away_score,
            stats.get('xg_home', 0), stats.get('xg_away', 0),
            minute, stats
        )
        
        for threshold, data in goals_probs.items():
            if data['over_prob'] > 50:  # Nur wenn Over wahrscheinlicher
                all_probabilities.append({
                    'market': f'Total Goals Over {threshold}',
                    'selection': f'Over {threshold}',
                    'probability': data['over_prob'],
                    'current_status': f"{home_score + away_score} goals scored",
                    'reasoning': data['reasoning']
                })
            else:
                all_probabilities.append({
                    'market': f'Total Goals Under {threshold}',
                    'selection': f'Under {threshold}',
                    'probability': data['under_prob'],
                    'current_status': f"{home_score + away_score} goals scored",
                    'reasoning': data['reasoning']
                })
        
        # =============================================
        # 3. OVER/UNDER CARDS
        # =============================================
        if stats:
            cards_probs = self._calculate_cards_markets(match_data, minute, stats)
            
            for threshold, data in cards_probs.items():
                if data['status'] == 'ACTIVE':
                    if data['over_prob'] > 50:
                        all_probabilities.append({
                            'market': f'Total Cards Over {threshold}',
                            'selection': f'Over {threshold}',
                            'probability': data['over_prob'],
                            'current_status': f"{data['current_cards']} cards",
                            'reasoning': data['reasoning']
                        })
                    else:
                        all_probabilities.append({
                            'market': f'Total Cards Under {threshold}',
                            'selection': f'Under {threshold}',
                            'probability': data['under_prob'],
                            'current_status': f"{data['current_cards']} cards",
                            'reasoning': data['reasoning']
                        })
        
        # =============================================
        # 4. OVER/UNDER CORNERS
        # =============================================
        if stats:
            corners_probs = self._calculate_corners_markets(match_data, minute, stats)
            
            for threshold, data in corners_probs.items():
                if data['status'] == 'ACTIVE':
                    if data['over_prob'] > 50:
                        all_probabilities.append({
                            'market': f'Total Corners Over {threshold}',
                            'selection': f'Over {threshold}',
                            'probability': data['over_prob'],
                            'current_status': f"{data['current_corners']} corners",
                            'reasoning': data['reasoning']
                        })
                    else:
                        all_probabilities.append({
                            'market': f'Total Corners Under {threshold}',
                            'selection': f'Under {threshold}',
                            'probability': data['under_prob'],
                            'current_status': f"{data['current_corners']} corners",
                            'reasoning': data['reasoning']
                        })
        
        # =============================================
        # 5. BTTS YES/NO
        # =============================================
        btts_probs = self._calculate_btts_market(
            home_score, away_score,
            stats.get('xg_home', 0), stats.get('xg_away', 0),
            minute
        )
        
        if btts_probs['btts_yes'] > 50:
            all_probabilities.append({
                'market': 'Both Teams To Score',
                'selection': 'Yes',
                'probability': btts_probs['btts_yes'],
                'current_status': f"{home_score}-{away_score}",
                'reasoning': btts_probs['yes_reasoning']
            })
        else:
            all_probabilities.append({
                'market': 'Both Teams To Score',
                'selection': 'No',
                'probability': btts_probs['btts_no'],
                'current_status': f"{home_score}-{away_score}",
                'reasoning': btts_probs['no_reasoning']
            })
        
        # =============================================
        # 6. CLEAN SHEET
        # =============================================
        clean_sheet = self._calculate_clean_sheet(
            home_score, away_score,
            stats.get('xg_home', 0), stats.get('xg_away', 0),
            minute
        )
        
        if clean_sheet['home_clean_sheet'] > 50:
            all_probabilities.append({
                'market': 'Clean Sheet',
                'selection': f'{home_team} Clean Sheet',
                'probability': clean_sheet['home_clean_sheet'],
                'current_status': f"Away scored: {away_score}",
                'reasoning': clean_sheet['home_reasoning']
            })
        
        if clean_sheet['away_clean_sheet'] > 50:
            all_probabilities.append({
                'market': 'Clean Sheet',
                'selection': f'{away_team} Clean Sheet',
                'probability': clean_sheet['away_clean_sheet'],
                'current_status': f"Home scored: {home_score}",
                'reasoning': clean_sheet['away_reasoning']
            })
        
        # =============================================
        # 7. NEXT GOAL
        # =============================================
        next_goal = self._calculate_next_goal(
            home_score, away_score,
            stats.get('xg_home', 0), stats.get('xg_away', 0),
            minute, stats
        )
        
        all_probabilities.append({
            'market': 'Next Goal',
            'selection': f'{home_team} scores next',
            'probability': next_goal['home_next'],
            'current_status': f"{home_score}-{away_score}",
            'reasoning': next_goal['home_reasoning']
        })
        
        all_probabilities.append({
            'market': 'Next Goal',
            'selection': f'{away_team} scores next',
            'probability': next_goal['away_next'],
            'current_status': f"{home_score}-{away_score}",
            'reasoning': next_goal['away_reasoning']
        })
        
        all_probabilities.append({
            'market': 'Next Goal',
            'selection': 'No more goals',
            'probability': next_goal['no_goal'],
            'current_status': f"{home_score}-{away_score}",
            'reasoning': next_goal['no_goal_reasoning']
        })
        
        # =============================================
        # 8. TEAM TOTAL GOALS
        # =============================================
        team_totals = self._calculate_team_totals(
            home_score, away_score,
            stats.get('xg_home', 0), stats.get('xg_away', 0),
            minute
        )
        
        for threshold in [0.5, 1.5, 2.5]:
            if team_totals['home'][threshold]['over'] > 50:
                all_probabilities.append({
                    'market': f'{home_team} Total Goals',
                    'selection': f'Over {threshold}',
                    'probability': team_totals['home'][threshold]['over'],
                    'current_status': f"{home_score} goals",
                    'reasoning': team_totals['home'][threshold]['reasoning']
                })
            
            if team_totals['away'][threshold]['over'] > 50:
                all_probabilities.append({
                    'market': f'{away_team} Total Goals',
                    'selection': f'Over {threshold}',
                    'probability': team_totals['away'][threshold]['over'],
                    'current_status': f"{away_score} goals",
                    'reasoning': team_totals['away'][threshold]['reasoning']
                })
        
        # =============================================
        # VALUE-BERECHNUNG FÜR JEDEN BET
        # =============================================
        # Value = (Probability × Fair_Odds) - 1
        # Eine Wette ist nur gut wenn Value > 0
        
        for bet in all_probabilities:
            prob = bet['probability'] / 100
            
            # Faire Quote (ohne Marge)
            fair_odds = 1 / prob if prob > 0.01 else 100
            
            # Geschätzte Markt-Quote (Buchmacher fügt 5-10% Marge hinzu)
            if prob >= 0.80:
                margin = 0.05  # 5% bei Favoriten
            elif prob >= 0.60:
                margin = 0.07  # 7% normal
            else:
                margin = 0.10  # 10% bei Außenseitern
            
            est_market_odds = fair_odds * (1 - margin)
            
            # Value = (unsere Prob - implizierte Markt-Prob) × 100
            implied_market_prob = 1 / est_market_odds if est_market_odds > 0 else 0
            value = (prob - implied_market_prob) * 100
            
            bet['fair_odds'] = round(fair_odds, 2)
            bet['est_market_odds'] = round(est_market_odds, 2)
            bet['value'] = round(value, 1)
            
            # Strength basiert auf VALUE, nicht nur Probability
            if value >= 8:
                bet['strength'] = 'VERY_STRONG'
            elif value >= 5:
                bet['strength'] = 'STRONG'
            elif value >= 2:
                bet['strength'] = 'GOOD'
            else:
                bet['strength'] = 'WEAK'
        
        # =============================================
        # SORTIERE NACH VALUE (nicht Wahrscheinlichkeit!)
        # =============================================
        # Eine 70% Wette mit +8% Value ist besser als 90% mit +2% Value
        all_probabilities.sort(key=lambda x: x['value'], reverse=True)
        
        # Filtere: Nur Wetten mit positivem Value UND >= 55% Wahrscheinlichkeit
        value_bets = [bet for bet in all_probabilities if bet['value'] >= 2 and bet['probability'] >= 55]
        
        # Best Bet (höchster Value)
        best_bet = all_probabilities[0] if all_probabilities else None
        
        # Top 5 (nach Value)
        top_5 = all_probabilities[:5]
        
        return {
            'best_bet': best_bet,
            'top_5': top_5,
            'high_probability_bets': value_bets,  # Value >= 2% UND Prob >= 55%
            'all_bets': all_probabilities,
            'total_markets_analyzed': len(all_probabilities),
            'match_info': {
                'home_team': home_team,
                'away_team': away_team,
                'score': f"{home_score}-{away_score}",
                'minute': minute
            }
        }
    
    # =============================================
    # CALCULATION METHODS
    # =============================================
    
    def _calculate_match_result(self, home_score: int, away_score: int,
                                xg_home: float, xg_away: float,
                                minute: int, stats: Dict) -> Dict:
        """
        Berechne 1X2 Wahrscheinlichkeiten
        
        Nutzt:
        - Aktueller Spielstand
        - xG Momentum
        - Zeit verbleibend
        - Possession
        - Dangerous Attacks
        """
        time_remaining = max(1, 90 - minute)
        time_factor = time_remaining / 90.0
        
        # Basis: Aktueller Spielstand
        if home_score > away_score:
            base_home = 70
            base_draw = 20
            base_away = 10
        elif away_score > home_score:
            base_home = 10
            base_draw = 20
            base_away = 70
        else:  # Gleich
            base_home = 35
            base_draw = 30
            base_away = 35
        
        # xG Momentum (verbleibende Zeit)
        if minute > 10:
            xg_rate_home = (xg_home / minute) * time_remaining
            xg_rate_away = (xg_away / minute) * time_remaining
        else:
            xg_rate_home = xg_home * 0.5
            xg_rate_away = xg_away * 0.5
        
        # xG Adjustment (MIT BOUNDS!)
        xg_diff = xg_rate_home - xg_rate_away
        xg_adjustment = max(-20, min(20, xg_diff * 10))  # -20 bis +20
        
        # Possession Adjustment (MIT BOUNDS!)
        poss_home = stats.get('possession_home', 50)
        poss_adjustment = max(-10, min(10, (poss_home - 50) * 0.2))  # -10 bis +10
        
        # Attacks Adjustment (MIT BOUNDS!)
        attacks_home = stats.get('dangerous_attacks_home', 0)
        attacks_away = stats.get('dangerous_attacks_away', 0)
        if attacks_home + attacks_away > 0:
            attack_ratio = attacks_home / (attacks_home + attacks_away)
            attack_adjustment = max(-10, min(10, (attack_ratio - 0.5) * 20))  # -10 bis +10
        else:
            attack_adjustment = 0
        
        # Zeit Faktor: Je später, desto stabiler aktuelles Ergebnis
        # NICHT als Multiplikator, sondern als Boost für führendes Team
        time_boost = (1 - time_factor) * 30  # 0 bis 30
        
        # Finale Wahrscheinlichkeiten
        # Home: Basis + Adjustments + (Time Boost wenn führend)
        home_win = base_home + xg_adjustment + poss_adjustment + attack_adjustment
        if home_score > away_score:
            home_win += time_boost
        
        # Away: Basis - Adjustments + (Time Boost wenn führend)
        away_win = base_away - xg_adjustment - poss_adjustment - attack_adjustment
        if away_score > home_score:
            away_win += time_boost
        
        # Draw: Basis bleibt relativ stabil, nur leichte xG-Anpassung
        draw = base_draw - abs(xg_adjustment) * 0.3  # Draw weniger wahrscheinlich bei xG-Unterschied
        
        # Ensure all positive ZUERST
        home_win = max(5, home_win)
        away_win = max(5, away_win)
        draw = max(5, draw)
        
        # DANN Normalisierung (damit Summe = 100%)
        total = home_win + draw + away_win
        home_win = (home_win / total) * 100
        draw = (draw / total) * 100
        away_win = (away_win / total) * 100
        
        # Keine weiteren Clamps - Normalisierung garantiert schon sinnvolle Werte!
        
        # Reasoning
        score_lead = home_score - away_score
        xg_sign = "+" if xg_diff >= 0 else ""  # Kein + bei negativen Werten
        home_reasoning = f"Score: {home_score}-{away_score}, xG momentum: {xg_sign}{xg_diff:.1f}, {time_remaining}min left"
        draw_reasoning = f"Score tied, {time_remaining}min left, even momentum"
        away_reasoning = f"Score: {home_score}-{away_score}, xG momentum: {xg_sign}{xg_diff:.1f}, {time_remaining}min left"
        
        return {
            'home_win': round(home_win, 1),
            'draw': round(draw, 1),
            'away_win': round(away_win, 1),
            'home_reasoning': home_reasoning,
            'draw_reasoning': draw_reasoning,
            'away_reasoning': away_reasoning
        }
    
    def _calculate_goals_markets(self, home_score: int, away_score: int,
                                 xg_home: float, xg_away: float,
                                 minute: int, stats: Dict) -> Dict:
        """
        Berechne Over/Under Goals für alle Schwellen
        """
        current_goals = home_score + away_score
        time_remaining = max(1, 90 - minute)
        
        # Projiziere verbleibende Tore
        if minute > 20:  # Mindestens 20 Minuten für reliable rates
            xg_rate = (xg_home + xg_away) / minute
            expected_remaining = xg_rate * time_remaining
        else:
            # Früh im Spiel: Conservative defaults
            expected_remaining = 1.4 * (time_remaining / 90)  # ~1.4 goals remaining average
        
        expected_total = current_goals + expected_remaining
        
        # Berechne für alle Schwellen
        thresholds = {}
        for threshold in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]:
            if current_goals > threshold:
                # Bereits getroffen
                over_prob = 100.0
                under_prob = 0.0
                reasoning = f"Already hit: {current_goals} goals scored"
            else:
                # Poisson für verbleibende Tore
                needed = threshold - current_goals + 0.5
                
                # P(X >= needed) mit Poisson
                prob_under_threshold = 0
                for k in range(int(needed)):
                    prob_under_threshold += (math.exp(-expected_remaining) * 
                                            (expected_remaining ** k) / math.factorial(k))
                
                under_prob = prob_under_threshold * 100
                over_prob = 100 - under_prob
                
                reasoning = f"Current: {current_goals}, Expected total: {expected_total:.1f}, Need {needed:.1f} more"
            
            thresholds[threshold] = {
                'over_prob': round(over_prob, 1),
                'under_prob': round(under_prob, 1),
                'reasoning': reasoning
            }
        
        return thresholds
    
    def _calculate_cards_markets(self, match_data: Dict, minute: int, stats: Dict) -> Dict:
        """
        Berechne Over/Under Cards
        """
        yellow_home = stats.get('yellow_cards_home', 0)
        yellow_away = stats.get('yellow_cards_away', 0)
        red_home = stats.get('red_cards_home', 0)
        red_away = stats.get('red_cards_away', 0)
        
        current_cards = yellow_home + yellow_away + (red_home + red_away) * 2
        
        # Fouls Rate
        fouls_home = stats.get('fouls_home', 0)
        fouls_away = stats.get('fouls_away', 0)
        
        time_remaining = max(1, 90 - minute)
        
        if minute > 10:
            fouls_per_min = (fouls_home + fouls_away) / minute
            expected_fouls_remaining = fouls_per_min * time_remaining
            
            # 1 card per 4.5 fouls (statistisch)
            expected_cards_remaining = expected_fouls_remaining / 4.5
        else:
            expected_cards_remaining = 1.5
        
        # Phase Bonus (späte Spielphase = mehr Cards)
        if minute >= 75:
            expected_cards_remaining *= 1.3
        elif minute >= 60:
            expected_cards_remaining *= 1.15
        
        expected_total = current_cards + expected_cards_remaining
        
        # Berechne für Schwellen
        thresholds = {}
        for threshold in [2.5, 3.5, 4.5, 5.5, 6.5]:
            if current_cards > threshold:
                status = 'HIT'
                over_prob = 100.0
                under_prob = 0.0
                reasoning = f"Already hit: {current_cards} cards"
            else:
                status = 'ACTIVE'
                needed = threshold - current_cards + 0.5
                
                # Poisson
                prob_under = 0
                for k in range(int(needed)):
                    prob_under += (math.exp(-expected_cards_remaining) *
                                  (expected_cards_remaining ** k) / math.factorial(k))
                
                under_prob = prob_under * 100
                over_prob = 100 - under_prob
                
                reasoning = f"Current: {current_cards}, Expected total: {expected_total:.1f}, Fouls rate: {fouls_per_min if minute > 10 else 0:.2f}/min"
            
            thresholds[threshold] = {
                'status': status,
                'over_prob': round(over_prob, 1),
                'under_prob': round(under_prob, 1),
                'current_cards': current_cards,
                'reasoning': reasoning
            }
        
        return thresholds
    
    def _calculate_corners_markets(self, match_data: Dict, minute: int, stats: Dict) -> Dict:
        """
        Berechne Over/Under Corners
        """
        corners_home = stats.get('corners_home', 0)
        corners_away = stats.get('corners_away', 0)
        current_corners = corners_home + corners_away
        
        time_remaining = max(1, 90 - minute)
        
        if minute > 10:
            corners_per_min = current_corners / minute
            expected_remaining = corners_per_min * time_remaining
        else:
            # Früh im Spiel: Schätze 10 Ecken pro Spiel
            expected_remaining = 10 * (time_remaining / 90)
        
        expected_total = current_corners + expected_remaining
        
        # Berechne für Schwellen
        thresholds = {}
        for threshold in [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5]:
            if current_corners > threshold:
                status = 'HIT'
                over_prob = 100.0
                under_prob = 0.0
                reasoning = f"Already hit: {current_corners} corners"
            else:
                status = 'ACTIVE'
                needed = threshold - current_corners + 0.5
                
                # Poisson
                prob_under = 0
                for k in range(int(needed)):
                    prob_under += (math.exp(-expected_remaining) *
                                  (expected_remaining ** k) / math.factorial(k))
                
                under_prob = prob_under * 100
                over_prob = 100 - under_prob
                
                reasoning = f"Current: {current_corners}, Expected total: {expected_total:.1f}, Rate: {corners_per_min if minute > 10 else 0:.2f}/min"
            
            thresholds[threshold] = {
                'status': status,
                'over_prob': round(over_prob, 1),
                'under_prob': round(under_prob, 1),
                'current_corners': current_corners,
                'reasoning': reasoning
            }
        
        return thresholds
    
    def _calculate_btts_market(self, home_score: int, away_score: int,
                               xg_home: float, xg_away: float,
                               minute: int) -> Dict:
        """
        Berechne BTTS Yes/No
        """
        if home_score > 0 and away_score > 0:
            # Bereits eingetreten
            return {
                'btts_yes': 100.0,
                'btts_no': 0.0,
                'yes_reasoning': 'Both teams already scored',
                'no_reasoning': 'Already hit'
            }
        
        time_remaining = max(1, 90 - minute)
        time_factor = time_remaining / 90.0
        
        # Projiziere verbleibende xG
        if minute > 20:  # Mindestens 20 Minuten für reliable rates
            xg_rate_home = (xg_home / minute) * time_remaining
            xg_rate_away = (xg_away / minute) * time_remaining
        else:
            # Früh im Spiel: Conservative defaults
            xg_rate_home = 0.8 * (time_remaining / 90)
            xg_rate_away = 0.6 * (time_remaining / 90)
        
        # Poisson: P(Team scores >= 1)
        if home_score == 0:
            p_home_scores = (1 - math.exp(-xg_rate_home)) * 100
        else:
            p_home_scores = 100.0
        
        if away_score == 0:
            p_away_scores = (1 - math.exp(-xg_rate_away)) * 100
        else:
            p_away_scores = 100.0
        
        # P(BTTS) = P(Home scores) × P(Away scores)
        btts_yes = (p_home_scores * p_away_scores) / 100
        btts_no = 100 - btts_yes
        
        # Reasoning
        if home_score > 0 and away_score == 0:
            yes_reasoning = f"Home already scored, Away needs 1 goal ({p_away_scores:.0f}% chance)"
            no_reasoning = f"Away unlikely to score ({100-p_away_scores:.0f}% chance)"
        elif away_score > 0 and home_score == 0:
            yes_reasoning = f"Away already scored, Home needs 1 goal ({p_home_scores:.0f}% chance)"
            no_reasoning = f"Home unlikely to score ({100-p_home_scores:.0f}% chance)"
        else:
            yes_reasoning = f"Both need to score: Home {p_home_scores:.0f}%, Away {p_away_scores:.0f}%"
            no_reasoning = f"At least one won't score"
        
        return {
            'btts_yes': round(btts_yes, 1),
            'btts_no': round(btts_no, 1),
            'yes_reasoning': yes_reasoning,
            'no_reasoning': no_reasoning
        }
    
    def _calculate_clean_sheet(self, home_score: int, away_score: int,
                               xg_home: float, xg_away: float,
                               minute: int) -> Dict:
        """
        Berechne Clean Sheet Wahrscheinlichkeiten
        """
        time_remaining = max(1, 90 - minute)
        
        if minute > 20:  # Mindestens 20 Minuten für reliable rates
            xg_rate_home = (xg_home / minute) * time_remaining
            xg_rate_away = (xg_away / minute) * time_remaining
        else:
            # Früh im Spiel: Conservative defaults
            xg_rate_home = 0.8 * (time_remaining / 90)
            xg_rate_away = 0.6 * (time_remaining / 90)
        
        # Home Clean Sheet = Away doesn't score
        if away_score > 0:
            home_clean_sheet = 0.0
            home_reasoning = f"Away already scored {away_score}"
        else:
            # P(Away scores 0 more) = e^(-xG)
            home_clean_sheet = math.exp(-xg_rate_away) * 100
            home_reasoning = f"Away xG remaining: {xg_rate_away:.2f}, {time_remaining}min left"
        
        # Away Clean Sheet = Home doesn't score
        if home_score > 0:
            away_clean_sheet = 0.0
            away_reasoning = f"Home already scored {home_score}"
        else:
            away_clean_sheet = math.exp(-xg_rate_home) * 100
            away_reasoning = f"Home xG remaining: {xg_rate_home:.2f}, {time_remaining}min left"
        
        return {
            'home_clean_sheet': round(home_clean_sheet, 1),
            'away_clean_sheet': round(away_clean_sheet, 1),
            'home_reasoning': home_reasoning,
            'away_reasoning': away_reasoning
        }
    
    def _calculate_next_goal(self, home_score: int, away_score: int,
                            xg_home: float, xg_away: float,
                            minute: int, stats: Dict) -> Dict:
        """
        Berechne Next Goal Wahrscheinlichkeiten
        """
        time_remaining = max(1, 90 - minute)
        
        # xG Rate
        if minute > 10:
            xg_rate_home = xg_home / minute
            xg_rate_away = xg_away / minute
        else:
            xg_rate_home = xg_home / 10
            xg_rate_away = xg_away / 10
        
        # Trailing Team Boost (10%, statistisch realistischer als 20%)
        if home_score < away_score:
            xg_rate_home *= 1.10  # Desperate
        elif away_score < home_score:
            xg_rate_away *= 1.10
        
        # Attacks Momentum (MULTIPLIKATIV!)
        attacks_home = stats.get('dangerous_attacks_home', 0)
        attacks_away = stats.get('dangerous_attacks_away', 0)
        
        if attacks_home + attacks_away > 0:
            attack_ratio = attacks_home / (attacks_home + attacks_away)
            
            # Multiplikative Adjustments: 0.6 bis 1.0
            # attack_ratio = 0.7 → home gets 1.16x, away gets 0.84x
            home_attack_mult = 0.6 + (attack_ratio - 0.5) * 0.8
            away_attack_mult = 0.6 + (0.5 - attack_ratio) * 0.8
            
            xg_rate_home *= home_attack_mult
            xg_rate_away *= away_attack_mult
        
        # Total xG rate
        total_xg_rate = xg_rate_home + xg_rate_away
        
        # Expected goals in remaining time
        expected_goals_remaining = total_xg_rate * (time_remaining / 90)
        
        # P(at least 1 goal happens) = 1 - e^(-λ)
        p_goal_happens = 1 - math.exp(-expected_goals_remaining)
        
        # P(Home scores | goal happens) = xG_home / (xG_home + xG_away)
        if total_xg_rate > 0:
            p_home_given_goal = xg_rate_home / total_xg_rate
            p_away_given_goal = xg_rate_away / total_xg_rate
        else:
            p_home_given_goal = 0.5
            p_away_given_goal = 0.5
        
        # P(Home scores next) = P(goal) × P(Home | goal)
        home_next = p_goal_happens * p_home_given_goal * 100
        away_next = p_goal_happens * p_away_given_goal * 100
        no_goal = (1 - p_goal_happens) * 100
        
        # Verify sum (should be ~100)
        total_prob = home_next + away_next + no_goal
        if abs(total_prob - 100) > 0.1:
            # Re-normalize if needed
            factor = 100 / total_prob
            home_next *= factor
            away_next *= factor
            no_goal *= factor
        
        home_reasoning = f"xG rate: {xg_rate_home:.3f}/min, momentum: {attacks_home} dangerous attacks"
        away_reasoning = f"xG rate: {xg_rate_away:.3f}/min, momentum: {attacks_away} dangerous attacks"
        no_goal_reasoning = f"Expected goals remaining: {expected_goals_remaining:.2f} in {time_remaining}min"
        
        return {
            'home_next': round(home_next, 1),
            'away_next': round(away_next, 1),
            'no_goal': round(no_goal, 1),
            'home_reasoning': home_reasoning,
            'away_reasoning': away_reasoning,
            'no_goal_reasoning': no_goal_reasoning
        }
    
    def _calculate_team_totals(self, home_score: int, away_score: int,
                               xg_home: float, xg_away: float,
                               minute: int) -> Dict:
        """
        Berechne Team Total Goals
        """
        time_remaining = max(1, 90 - minute)
        
        if minute > 20:  # Mindestens 20 Minuten für reliable rates
            xg_rate_home = (xg_home / minute) * time_remaining
            xg_rate_away = (xg_away / minute) * time_remaining
        else:
            # Früh im Spiel: Conservative defaults
            xg_rate_home = 0.8 * (time_remaining / 90)
            xg_rate_away = 0.6 * (time_remaining / 90)
        
        results = {'home': {}, 'away': {}}
        
        for threshold in [0.5, 1.5, 2.5]:
            # Home
            if home_score > threshold:
                home_over = 100.0
                home_reasoning = f"Already scored {home_score} goals"
            else:
                needed = threshold - home_score + 0.5
                prob_under = 0
                for k in range(int(needed)):
                    prob_under += (math.exp(-xg_rate_home) *
                                  (xg_rate_home ** k) / math.factorial(k))
                home_over = (1 - prob_under) * 100
                home_reasoning = f"Current: {home_score}, Expected total: {home_score + xg_rate_home:.1f}"
            
            # Away
            if away_score > threshold:
                away_over = 100.0
                away_reasoning = f"Already scored {away_score} goals"
            else:
                needed = threshold - away_score + 0.5
                prob_under = 0
                for k in range(int(needed)):
                    prob_under += (math.exp(-xg_rate_away) *
                                  (xg_rate_away ** k) / math.factorial(k))
                away_over = (1 - prob_under) * 100
                away_reasoning = f"Current: {away_score}, Expected total: {away_score + xg_rate_away:.1f}"
            
            results['home'][threshold] = {
                'over': round(home_over, 1),
                'under': round(100 - home_over, 1),
                'reasoning': home_reasoning
            }
            
            results['away'][threshold] = {
                'over': round(away_over, 1),
                'under': round(100 - away_over, 1),
                'reasoning': away_reasoning
            }
        
        return results


def display_best_bet(result: Dict):
    """
    Display Best Bet in Streamlit
    """
    import streamlit as st
    
    match_info = result['match_info']
    best_bet = result['best_bet']
    
    st.markdown(f"### 🎯 BEST VALUE BET - {match_info['home_team']} vs {match_info['away_team']}")
    st.caption(f"Minute: {match_info['minute']}' | Score: {match_info['score']}")
    
    # Best Bet
    st.markdown("---")
    st.markdown("#### 🏆 HIGHEST VALUE BET")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        st.metric(
            label=best_bet['market'],
            value=best_bet['selection'],
            delta=f"{best_bet['probability']:.1f}%"
        )
    
    with col2:
        strength = best_bet.get('strength', 'GOOD')
        if strength == 'VERY_STRONG':
            st.success("🔥🔥 VERY STRONG")
        elif strength == 'STRONG':
            st.success("🔥 STRONG")
        elif strength == 'GOOD':
            st.info("✅ GOOD")
        else:
            st.warning("⚠️ WEAK")
    
    with col3:
        st.metric("Value", f"+{best_bet.get('value', 0):.1f}%")
    
    with col4:
        st.metric("Fair Odds", f"{best_bet.get('fair_odds', '-')}")
    
    st.info(f"**Why?** {best_bet['reasoning']}")
    st.caption(f"Est. Market Odds: {best_bet.get('est_market_odds', '-')} | Current: {best_bet['current_status']}")
    
    # Top 5
    st.markdown("---")
    st.markdown("#### 📊 TOP 5 VALUE BETS")
    
    top_5 = result['top_5']
    
    for i, bet in enumerate(top_5, 1):
        value_str = f"+{bet.get('value', 0):.1f}%" if bet.get('value', 0) > 0 else f"{bet.get('value', 0):.1f}%"
        with st.expander(f"{i}. {bet['market']}: {bet['selection']} | {bet['probability']:.1f}% | Value: {value_str}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Probability:** {bet['probability']:.1f}%")
            with col2:
                st.write(f"**Value:** {value_str}")
            with col3:
                st.write(f"**Fair Odds:** {bet.get('fair_odds', '-')}")
            st.write(f"**Current:** {bet['current_status']}")
            st.write(f"**Reasoning:** {bet['reasoning']}")
    
    # Summary
    st.markdown("---")
    st.caption(f"📈 Total markets analyzed: {result['total_markets_analyzed']}")
    st.caption(f"✅ Value bets (≥2% value, ≥55% prob): {len(result['high_probability_bets'])}")


__all__ = ['BestBetFinder', 'display_best_bet']
