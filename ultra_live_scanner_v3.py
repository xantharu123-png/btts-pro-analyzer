"""
ULTRA LIVE SCANNER V3.0 - CORRECTED
Mathematisch korrekte BTTS/Over-Under Berechnung

KERNFORMEL (Poisson-basiert):
- P(Team scores) = 1 - e^(-xG)
- P(BTTS) = P(Home scores) × P(Away scores)
"""

import streamlit as st
import requests
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import time
import math


class UltraLiveScanner:
    """
    Mathematisch korrekte BTTS-Vorhersage
    Basiert auf Poisson-Verteilung und xG
    """
    
    def __init__(self, analyzer, api_football):
        self.analyzer = analyzer
        self.api_football = api_football
        self.match_data_cache = defaultdict(dict)
    
    def analyze_live_match_ultra(self, match: Dict) -> Optional[Dict]:
        """
        KORRIGIERTE Live-Analyse mit mathematisch fundierter BTTS-Berechnung
        """
        try:
            fixture = match['fixture']
            teams = match['teams']
            goals = match['goals']
            
            fixture_id = fixture['id']
            home_team = teams['home']['name']
            away_team = teams['away']['name']
            home_team_id = teams['home']['id']
            away_team_id = teams['away']['id']
            
            minute = fixture['status']['elapsed'] or 0
            home_score = goals['home'] if goals['home'] is not None else 0
            away_score = goals['away'] if goals['away'] is not None else 0
            score = f"{home_score}-{away_score}"
            
            print(f"\n{'='*60}")
            print(f"🔍 ANALYZING: {home_team} vs {away_team}")
            print(f"   Minute: {minute}' | Score: {score}")
            print(f"{'='*60}")
            
            # Get live statistics
            stats = self.api_football.get_match_statistics(fixture_id)
            
            # Extract xG
            xg_home = 0.0
            xg_away = 0.0
            
            if stats:
                xg_home = stats.get('xg_home') or 0.0
                xg_away = stats.get('xg_away') or 0.0
                print(f"   xG: {xg_home:.2f} - {xg_away:.2f}")
                
                if stats.get('shots_home'):
                    print(f"   Shots: {stats['shots_home']}-{stats['shots_away']}")
            
            # Wenn keine xG, schätze aus Schüssen
            if xg_home == 0 and stats:
                shots_home = stats.get('shots_home') or 0
                shots_away = stats.get('shots_away') or 0
                shots_target_home = stats.get('shots_on_target_home') or 0
                shots_target_away = stats.get('shots_on_target_away') or 0
                
                xg_home = shots_home * 0.08 + shots_target_home * 0.25
                xg_away = shots_away * 0.08 + shots_target_away * 0.25
                print(f"   xG (geschätzt): {xg_home:.2f} - {xg_away:.2f}")
            
            # BTTS BERECHNUNG
            btts_result = self._calculate_btts_probability(
                home_score, away_score, xg_home, xg_away, minute
            )
            
            btts_prob = btts_result['probability']
            btts_confidence = btts_result['confidence']
            btts_recommendation = self._get_btts_recommendation(btts_prob, btts_confidence, minute, score)
            
            print(f"\n📊 BTTS CALCULATION:")
            print(f"   P(Home scores): {btts_result['p_home_scores']:.1f}%")
            print(f"   P(Away scores): {btts_result['p_away_scores']:.1f}%")
            print(f"   P(BTTS): {btts_prob:.1f}%")
            
            # OVER/UNDER BERECHNUNG
            ou_result = self._calculate_over_under(
                home_score, away_score, xg_home, xg_away, minute
            )
            
            print(f"\n📊 OVER/UNDER:")
            print(f"   Expected Total: {ou_result['expected_total']:.2f}")
            print(f"   Over 2.5: {ou_result['over_25_prob']:.1f}%")
            
            # NEXT GOAL BERECHNUNG
            ng_result = self._calculate_next_goal(
                home_score, away_score, xg_home, xg_away, minute, stats
            )
            
            print(f"\n📊 NEXT GOAL:")
            print(f"   Home: {ng_result['home_prob']:.1f}%")
            print(f"   Away: {ng_result['away_prob']:.1f}%")
            
            print(f"\n💰 FINAL: BTTS {btts_prob:.1f}% | O/U {ou_result['recommendation']}")
            print(f"{'='*60}\n")
            
            return {
                'fixture_id': fixture_id,
                'home_team': home_team,
                'away_team': away_team,
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'minute': minute,
                'score': score,
                'home_score': home_score,
                'away_score': away_score,
                'btts_prob': round(btts_prob, 1),
                'btts_confidence': btts_confidence,
                'btts_recommendation': btts_recommendation,
                'over_under': {
                    'expected_total_goals': ou_result['expected_total'],
                    'over_25_probability': ou_result['over_25_prob'],
                    'thresholds': ou_result['thresholds'],
                    'recommendation': ou_result['recommendation'],
                    'confidence': ou_result['confidence']
                },
                'next_goal': {
                    'home_next_goal_prob': ng_result['home_prob'],
                    'away_next_goal_prob': ng_result['away_prob'],
                    'no_goal_prob': ng_result['no_goal_prob'],
                    'favorite': ng_result['favorite'],
                    'edge': ng_result['edge'],
                    'recommendation': ng_result['recommendation'],
                    'confidence': ng_result['confidence']
                },
                'league': match['league']['name'],
                'breakdown': {
                    'base': btts_result['base_prob'],
                    'xg_home': xg_home,
                    'xg_away': xg_away,
                    'time_factor': btts_result['time_factor'],
                    'score': btts_result['score_adj'],
                    'momentum': 0,
                    'xg_velocity': 0,
                    'game_phase': self._get_phase(minute),
                    'dangerous_attacks': 0,
                    'goalkeeper_saves': 0,
                    'corners': 0,
                    'cards': 0
                },
                'stats': stats,
                'xg_data': {'home_xg': xg_home, 'away_xg': xg_away},
                'momentum_data': {},
                'phase_data': {'phase': self._get_phase(minute)}
            }
        
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _calculate_btts_probability(self, home_score: int, away_score: int,
                                    xg_home: float, xg_away: float, 
                                    minute: int) -> Dict:
        """Mathematisch korrekte BTTS-Berechnung mit Poisson"""
        
        # BTTS bereits eingetreten
        if home_score > 0 and away_score > 0:
            return {
                'probability': 100.0,
                'confidence': 'COMPLETE',
                'p_home_scores': 100.0,
                'p_away_scores': 100.0,
                'base_prob': 100.0,
                'time_factor': 1.0,
                'score_adj': 0
            }
        
        time_remaining = max(1, 90 - minute)
        time_factor = time_remaining / 90.0
        
        # Projiziere xG
        if minute > 5:
            xg_rate_home = xg_home / minute * 90
            xg_rate_away = xg_away / minute * 90
        else:
            xg_rate_home = max(xg_home, 1.2)
            xg_rate_away = max(xg_away, 1.0)
        
        remaining_xg_home = xg_rate_home * time_factor
        remaining_xg_away = xg_rate_away * time_factor
        
        # Berechnung je nach Spielstand
        if home_score == 0 and away_score == 0:
            p_home_scores = self._poisson_at_least_one(remaining_xg_home)
            p_away_scores = self._poisson_at_least_one(remaining_xg_away)
            base_prob = p_home_scores * p_away_scores / 100
        elif home_score > 0:
            p_home_scores = 100.0
            p_away_scores = self._poisson_at_least_one(remaining_xg_away)
            base_prob = p_away_scores
        else:
            p_home_scores = self._poisson_at_least_one(remaining_xg_home)
            p_away_scores = 100.0
            base_prob = p_home_scores
        
        # Phase-Boost
        phase_boost = 5 if minute >= 75 else (3 if minute >= 60 else 0)
        
        # Score-Pressure
        score_adj = 5 if (home_score != away_score and minute >= 60) else 0
        
        final_prob = max(5, min(95, base_prob + phase_boost + score_adj))
        
        confidence = 'HIGH' if (xg_home > 0 and xg_away > 0 and minute >= 30) else 'MEDIUM'
        
        return {
            'probability': final_prob,
            'confidence': confidence,
            'p_home_scores': p_home_scores,
            'p_away_scores': p_away_scores,
            'base_prob': base_prob,
            'time_factor': time_factor,
            'score_adj': score_adj + phase_boost
        }
    
    def _poisson_at_least_one(self, expected_goals: float) -> float:
        """P(X ≥ 1) = 1 - e^(-λ)"""
        if expected_goals <= 0:
            return 5.0
        p_zero = math.exp(-expected_goals)
        return max(5.0, min(95.0, (1 - p_zero) * 100))
    
    def _calculate_over_under(self, home_score: int, away_score: int,
                              xg_home: float, xg_away: float, minute: int) -> Dict:
        """Korrigierte Over/Under Berechnung"""
        current_goals = home_score + away_score
        current_xg = xg_home + xg_away
        
        time_remaining = max(1, 90 - minute)
        time_factor = time_remaining / 90.0
        
        if minute > 5:
            goals_rate = current_goals / minute * 90
            xg_rate = current_xg / minute * 90
            expected_total = current_goals + (xg_rate - current_xg) * 0.7 + (goals_rate - current_goals) * 0.3
        else:
            expected_total = current_goals + current_xg + 1.5 * time_factor
        
        expected_total = max(current_goals, min(8.0, expected_total))
        
        thresholds = {}
        for threshold in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            if current_goals > threshold:
                thresholds[f'over_{threshold}'] = {
                    'threshold': threshold,
                    'status': 'HIT',
                    'over_probability': 100.0,
                    'under_probability': 0.0,
                    'goals_needed': 0,
                    'strength': 'HIT',
                    'recommendation': f'✅ Over {threshold} HIT!'
                }
            else:
                goals_needed = int(threshold + 0.5) - current_goals
                remaining_expected = expected_total - current_goals
                over_prob = self._poisson_over_threshold(remaining_expected, goals_needed)
                under_prob = 100 - over_prob
                
                if over_prob >= 80:
                    strength, rec = 'VERY_STRONG', f'🔥🔥 OVER {threshold}!'
                elif over_prob >= 70:
                    strength, rec = 'STRONG', f'🔥 OVER {threshold}!'
                elif over_prob >= 60:
                    strength, rec = 'GOOD', f'✅ Over {threshold}'
                elif under_prob >= 70:
                    strength, rec = 'UNDER_STRONG', f'🔥 UNDER {threshold}!'
                else:
                    strength, rec = 'NEUTRAL', f'⚠️ {threshold} Neutral'
                
                thresholds[f'over_{threshold}'] = {
                    'threshold': threshold,
                    'status': 'ACTIVE',
                    'over_probability': round(over_prob, 1),
                    'under_probability': round(under_prob, 1),
                    'goals_needed': goals_needed,
                    'strength': strength,
                    'recommendation': rec
                }
        
        over_25 = thresholds.get('over_2.5', {})
        over_25_prob = over_25.get('over_probability', 50)
        
        best_rec = '⚠️ Keine starke Wette'
        for data in thresholds.values():
            if data.get('strength') in ['VERY_STRONG', 'STRONG']:
                best_rec = data['recommendation']
                break
        
        return {
            'expected_total': round(expected_total, 2),
            'over_25_prob': over_25_prob,
            'thresholds': thresholds,
            'recommendation': best_rec,
            'confidence': 'HIGH' if minute >= 30 and current_xg > 0 else 'MEDIUM'
        }
    
    def _poisson_over_threshold(self, expected: float, goals_needed: int) -> float:
        """P(X >= goals_needed)"""
        if expected <= 0:
            return 10.0
        p_under = sum((expected ** k) * math.exp(-expected) / math.factorial(k) 
                      for k in range(goals_needed))
        return max(5, min(95, (1 - p_under) * 100))
    
    def _calculate_next_goal(self, home_score: int, away_score: int,
                             xg_home: float, xg_away: float,
                             minute: int, stats: Dict) -> Dict:
        """Next Goal Vorhersage"""
        time_remaining = max(1, 90 - minute)
        total_xg = xg_home + xg_away
        
        if total_xg > 0:
            home_share = xg_home / total_xg
            away_share = xg_away / total_xg
        else:
            home_share, away_share = 0.55, 0.45
        
        # No-Goal Wahrscheinlichkeit
        if time_remaining >= 60:
            no_goal_base = 15
        elif time_remaining >= 30:
            no_goal_base = 25
        elif time_remaining >= 15:
            no_goal_base = 40
        else:
            no_goal_base = 55
        
        if total_xg > 2:
            no_goal_base -= 10
        elif total_xg < 0.5:
            no_goal_base += 10
        
        no_goal_prob = max(5, min(60, no_goal_base))
        goal_prob = 100 - no_goal_prob
        home_prob = goal_prob * home_share
        away_prob = goal_prob * away_share
        
        # Desperation
        if minute >= 70:
            if home_score < away_score:
                home_prob += 5
            elif away_score < home_score:
                away_prob += 5
        
        total = home_prob + away_prob + no_goal_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        no_goal_prob = no_goal_prob / total * 100
        
        favorite = 'HOME' if home_prob > away_prob else 'AWAY'
        edge = abs(home_prob - away_prob)
        
        if max(home_prob, away_prob) >= 50 and edge >= 20:
            rec = f'🔥 {favorite} NEXT GOAL!'
        elif edge < 10:
            rec = '⚠️ ZU KNAPP'
        else:
            rec = f'✅ {favorite} leichter Vorteil'
        
        return {
            'home_prob': round(home_prob, 1),
            'away_prob': round(away_prob, 1),
            'no_goal_prob': round(no_goal_prob, 1),
            'favorite': favorite,
            'edge': round(edge, 1),
            'recommendation': rec,
            'confidence': 'HIGH' if total_xg > 0.5 else 'MEDIUM'
        }
    
    def _get_btts_recommendation(self, prob: float, confidence: str, 
                                  minute: int, score: str) -> str:
        if confidence == 'COMPLETE':
            return '✅ BTTS COMPLETE!'
        if prob >= 75 and confidence in ['HIGH', 'MEDIUM']:
            return '🔥🔥 STRONG BET!'
        elif prob >= 65:
            return '🔥 GOOD BET'
        elif prob >= 55:
            return '✅ CONSIDER'
        elif prob >= 45:
            return '⚠️ RISKY'
        else:
            return '❌ SKIP'
    
    def _get_phase(self, minute: int) -> str:
        if minute < 15:
            return 'OPENING'
        elif minute < 30:
            return 'PROBING'
        elif minute < 45:
            return 'PRE_HT_PUSH'
        elif minute < 60:
            return 'POST_HT_RESET'
        elif minute < 75:
            return 'DECISION_TIME'
        else:
            return 'DESPERATE'


def display_ultra_opportunity(match: Dict):
    """Display für Streamlit"""
    import streamlit as st
    
    phase = match.get('breakdown', {}).get('game_phase', 'UNKNOWN')
    
    st.markdown(f"### 🔴 LIVE - {match['minute']}' | {phase}")
    st.markdown(f"**{match['home_team']} vs {match['away_team']}**")
    st.caption(f"{match['league']} | Score: {match['score']}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        btts = match['btts_prob']
        delta = "🔥" if btts >= 70 else ("✅" if btts >= 50 else "⚠️")
        st.metric("BTTS", f"{btts}%", delta=delta)
    
    with col2:
        ou = match.get('over_under', {})
        st.metric("Expected Goals", f"{ou.get('expected_total_goals', 0):.1f}")
        st.caption(f"Over 2.5: {ou.get('over_25_probability', 50):.0f}%")
    
    with col3:
        ng = match.get('next_goal', {})
        fav = ng.get('favorite', 'HOME')
        prob = ng.get('home_next_goal_prob', 50) if fav == 'HOME' else ng.get('away_next_goal_prob', 50)
        st.metric(f"Next: {fav}", f"{prob:.0f}%")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        rec = match['btts_recommendation']
        (st.success if '🔥' in rec else st.info)(f"⚽ {rec}")
    with col2:
        ou_rec = ou.get('recommendation', 'N/A')
        (st.success if '🔥' in ou_rec else st.info)(f"🎲 {ou_rec}")
    with col3:
        ng_rec = ng.get('recommendation', 'N/A')
        (st.success if '🔥' in ng_rec else st.info)(f"🎯 {ng_rec}")


__all__ = ['UltraLiveScanner', 'display_ultra_opportunity']
