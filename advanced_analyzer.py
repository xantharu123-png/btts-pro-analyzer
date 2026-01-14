"""
ADVANCED ANALYZER - CORRECTED VERSION
Mathematisch korrekte Pre-Match BTTS-Berechnung
Mit ORIGINALEM Klassennamen für Kompatibilität

KERNFORMEL:
BTTS = P(Home ≥ 1) × P(Away ≥ 1)
P(Team ≥ 1) = 1 - e^(-Expected_Goals)
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import pickle


class AdvancedBTTSAnalyzer:
    """
    Korrigierte Pre-Match BTTS-Analyse
    ORIGINAL KLASSENNAME für Kompatibilität
    """
    
    def __init__(self, data_engine, weather_analyzer=None):
        self.engine = data_engine
        self.weather = weather_analyzer
        
        # ML Model (optional)
        self.ml_model = None
        self.scaler = None
        self.model_trained = False
        
        # Weights für Ensemble
        self.weights = {
            'ml_model': 0.25,
            'statistical': 0.35,
            'form': 0.20,
            'h2h': 0.20
        }
    
    def load_or_train_model(self):
        """Load existing model or skip if not available"""
        self.load_model()
    
    def load_model(self) -> bool:
        """Load trained model from disk"""
        model_path = Path("ml_model.pkl")
        scaler_path = Path("scaler.pkl")
        
        if not model_path.exists() or not scaler_path.exists():
            print("⚠️ No ML model found - using statistical prediction only")
            return False
        
        try:
            with open(model_path, 'rb') as f:
                self.ml_model = pickle.load(f)
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            self.model_trained = True
            print("✅ ML Model loaded")
            return True
        except Exception as e:
            print(f"⚠️ Failed to load model: {e}")
            return False
    
    def analyze_match(self, home_team_id: int, away_team_id: int, 
                     league_code: str) -> Dict:
        """
        Komplette Pre-Match Analyse mit korrigierter BTTS-Berechnung
        """
        # Hole Team-Statistiken
        home_stats = self.engine.get_team_stats(home_team_id, league_code, 'home')
        away_stats = self.engine.get_team_stats(away_team_id, league_code, 'away')
        
        if not home_stats or not away_stats:
            return {'error': 'Insufficient data', 'btts_probability': 50.0}
        
        # Hole Form
        home_form = self.engine.get_recent_form(home_team_id, league_code, 'home', 5)
        away_form = self.engine.get_recent_form(away_team_id, league_code, 'away', 5)
        
        # Hole H2H
        h2h = self.engine.calculate_head_to_head(home_team_id, away_team_id)
        
        # =============================================
        # BTTS BERECHNUNG (Mathematisch korrekt!)
        # =============================================
        
        btts_result = self._calculate_btts_poisson(home_stats, away_stats, home_form, away_form, h2h)
        
        # Over/Under Berechnung
        ou_result = self._calculate_over_under_prematch(home_stats, away_stats)
        
        # Konfidenz
        confidence = self._calculate_confidence(home_stats, away_stats, h2h)
        
        # Empfehlung
        recommendation = self._get_recommendation(btts_result['probability'], confidence)
        
        return {
            'home_team': home_stats.get('team_name', 'Home'),
            'away_team': away_stats.get('team_name', 'Away'),
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            
            # BTTS
            'btts_probability': round(btts_result['probability'], 1),
            'btts_confidence': confidence,
            'btts_recommendation': recommendation,
            
            # Für Kompatibilität
            'ensemble_probability': round(btts_result['probability'], 1),
            'confidence': confidence,
            'recommendation': recommendation,
            
            # Breakdown
            'breakdown': {
                'home_scoring_prob': btts_result['p_home_scores'],
                'away_scoring_prob': btts_result['p_away_scores'],
                'statistical_btts': btts_result['stat_btts'],
                'form_btts': btts_result['form_btts'],
                'h2h_btts': btts_result['h2h_btts'],
                'expected_home_goals': btts_result['exp_home'],
                'expected_away_goals': btts_result['exp_away']
            },
            
            # Over/Under
            'over_under': ou_result,
            
            # Stats für UI
            'home_stats': {
                'btts_rate': home_stats.get('btts_rate', 50),
                'avg_goals_scored': home_stats.get('avg_goals_scored', 1.2),
                'avg_goals_conceded': home_stats.get('avg_goals_conceded', 1.0),
                'matches_played': home_stats.get('matches_played', 0)
            },
            'away_stats': {
                'btts_rate': away_stats.get('btts_rate', 50),
                'avg_goals_scored': away_stats.get('avg_goals_scored', 1.0),
                'avg_goals_conceded': away_stats.get('avg_goals_conceded', 1.2),
                'matches_played': away_stats.get('matches_played', 0)
            },
            'h2h': h2h,
            'form': {
                'home': home_form,
                'away': away_form
            }
        }
    
    def _calculate_btts_poisson(self, home_stats: Dict, away_stats: Dict,
                                home_form: Dict, away_form: Dict, h2h: Dict) -> Dict:
        """
        MATHEMATISCH KORREKTE BTTS-Berechnung mit Poisson
        """
        
        # ===== ERWARTETE TORE =====
        
        # Home Expected = (Home Scored + Away Conceded) / 2
        home_scored = home_stats.get('avg_goals_scored', 1.2)
        away_conceded = away_stats.get('avg_goals_conceded', 1.2)
        exp_home = (home_scored + away_conceded) / 2
        
        # Away Expected = (Away Scored + Home Conceded) / 2
        away_scored = away_stats.get('avg_goals_scored', 1.0)
        home_conceded = home_stats.get('avg_goals_conceded', 1.0)
        exp_away = (away_scored + home_conceded) / 2
        
        # Heimvorteil
        exp_home *= 1.08
        exp_away *= 0.92
        
        # ===== SCORING-WAHRSCHEINLICHKEITEN =====
        
        p_home_scores = self._poisson_at_least_one(exp_home)
        p_away_scores = self._poisson_at_least_one(exp_away)
        
        # ===== BTTS aus verschiedenen Quellen =====
        
        # 1. Statistische BTTS (Poisson)
        stat_btts = (p_home_scores * p_away_scores) / 100
        
        # 2. Historische BTTS-Raten
        home_btts = home_stats.get('btts_rate', 50)
        away_btts = away_stats.get('btts_rate', 50)
        historical_btts = (home_btts + away_btts) / 2
        
        # 3. Form BTTS
        form_btts = (home_form.get('btts_rate', 50) + away_form.get('btts_rate', 50)) / 2
        
        # 4. H2H BTTS
        h2h_btts = h2h.get('btts_rate', historical_btts) if h2h.get('matches_played', 0) >= 3 else historical_btts
        
        # ===== GEWICHTETE KOMBINATION =====
        
        weights = {
            'statistical': 0.35,
            'historical': 0.30,
            'form': 0.20,
            'h2h': 0.15
        }
        
        if h2h.get('matches_played', 0) >= 5:
            weights['h2h'] = 0.25
            weights['historical'] = 0.20
        
        final_btts = (
            weights['statistical'] * stat_btts +
            weights['historical'] * historical_btts +
            weights['form'] * form_btts +
            weights['h2h'] * h2h_btts
        )
        
        final_btts = max(20, min(85, final_btts))
        
        return {
            'probability': final_btts,
            'p_home_scores': p_home_scores,
            'p_away_scores': p_away_scores,
            'stat_btts': stat_btts,
            'form_btts': form_btts,
            'h2h_btts': h2h_btts,
            'exp_home': exp_home,
            'exp_away': exp_away
        }
    
    def _poisson_at_least_one(self, expected_goals: float) -> float:
        """P(X ≥ 1) = 1 - e^(-λ)"""
        if expected_goals <= 0:
            return 20.0
        p_zero = math.exp(-expected_goals)
        return max(20, min(95, (1 - p_zero) * 100))
    
    def _calculate_over_under_prematch(self, home_stats: Dict, away_stats: Dict) -> Dict:
        """Over/Under für Pre-Match"""
        
        exp_home = (home_stats.get('avg_goals_scored', 1.2) + 
                   away_stats.get('avg_goals_conceded', 1.2)) / 2 * 1.08
        exp_away = (away_stats.get('avg_goals_scored', 1.0) + 
                   home_stats.get('avg_goals_conceded', 1.0)) / 2 * 0.92
        
        expected_total = exp_home + exp_away
        
        thresholds = {}
        for threshold in [1.5, 2.5, 3.5, 4.5]:
            goals_needed = int(threshold + 0.5)
            over_prob = self._poisson_over(expected_total, goals_needed)
            
            if over_prob >= 70:
                strength, rec = 'STRONG', f'🔥 OVER {threshold}'
            elif over_prob >= 55:
                strength, rec = 'GOOD', f'✅ Over {threshold}'
            elif over_prob <= 35:
                strength, rec = 'UNDER_GOOD', f'✅ Under {threshold}'
            else:
                strength, rec = 'NEUTRAL', f'⚠️ {threshold} Neutral'
            
            thresholds[f'over_{threshold}'] = {
                'over_probability': round(over_prob, 1),
                'under_probability': round(100 - over_prob, 1),
                'strength': strength,
                'recommendation': rec
            }
        
        over_25 = thresholds['over_2.5']
        if over_25['over_probability'] >= 65:
            main_rec = f"🔥 OVER 2.5 ({over_25['over_probability']}%)"
        elif over_25['under_probability'] >= 65:
            main_rec = f"🔥 UNDER 2.5 ({over_25['under_probability']}%)"
        else:
            main_rec = f"⚠️ 2.5 Goals - Neutral"
        
        return {
            'expected_total': round(expected_total, 2),
            'thresholds': thresholds,
            'recommendation': main_rec
        }
    
    def _poisson_over(self, expected: float, goals_needed: int) -> float:
        """P(X >= goals_needed)"""
        if expected <= 0:
            return 20.0
        p_under = sum((expected ** k) * math.exp(-expected) / math.factorial(k) 
                      for k in range(goals_needed))
        return max(10, min(90, (1 - p_under) * 100))
    
    def _calculate_confidence(self, home_stats: Dict, away_stats: Dict, h2h: Dict) -> str:
        score = 0
        
        home_matches = home_stats.get('matches_played', 0)
        away_matches = away_stats.get('matches_played', 0)
        
        if home_matches >= 10 and away_matches >= 10:
            score += 40
        elif home_matches >= 5 and away_matches >= 5:
            score += 25
        else:
            score += 10
        
        if h2h.get('matches_played', 0) >= 5:
            score += 25
        elif h2h.get('matches_played', 0) >= 3:
            score += 15
        
        home_btts = home_stats.get('btts_rate', 50)
        away_btts = away_stats.get('btts_rate', 50)
        if abs(home_btts - away_btts) < 15:
            score += 20
        
        if score >= 70:
            return 'VERY_HIGH'
        elif score >= 50:
            return 'HIGH'
        elif score >= 30:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _get_recommendation(self, probability: float, confidence: str) -> str:
        if probability >= 70 and confidence in ['VERY_HIGH', 'HIGH']:
            return '🔥🔥 STRONG BET - BTTS YES'
        elif probability >= 65 and confidence in ['VERY_HIGH', 'HIGH']:
            return '🔥 GOOD BET - BTTS YES'
        elif probability >= 55:
            return '✅ CONSIDER - BTTS YES'
        elif probability <= 35 and confidence in ['VERY_HIGH', 'HIGH']:
            return '🔥 GOOD BET - BTTS NO'
        elif probability <= 45:
            return '✅ CONSIDER - BTTS NO'
        else:
            return '⚠️ SKIP - Too close'
    
    # ===== LEGACY METHODEN für Kompatibilität =====
    
    def statistical_predict(self, home_btts: float, away_btts: float, 
                          home_goals: float, away_goals: float,
                          home_conceded: float, away_conceded: float) -> float:
        """Legacy method - benutzt jetzt Poisson"""
        exp_home = (home_goals + away_conceded) / 2
        exp_away = (away_goals + home_conceded) / 2
        
        p_home = self._poisson_at_least_one(exp_home)
        p_away = self._poisson_at_least_one(exp_away)
        
        return (p_home * p_away) / 100
    
    def ml_predict(self, features: List[float]) -> Tuple[float, float]:
        """ML Prediction (falls Model geladen)"""
        if not self.model_trained or self.ml_model is None:
            return 0.5, 0.0
        
        try:
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            proba = self.ml_model.predict_proba(X_scaled)[0][1]
            return proba, 0.5
        except:
            return 0.5, 0.0


# Export
__all__ = ['AdvancedBTTSAnalyzer']
