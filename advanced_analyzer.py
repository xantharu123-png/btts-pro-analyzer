"""
Advanced BTTS Analyzer with Machine Learning - CORRECTED VERSION
Mathematisch korrekte Poisson-basierte BTTS-Berechnung
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
import sqlite3
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pickle
from pathlib import Path
import math

from data_engine import DataEngine

try:
    from weather_analyzer import WeatherAnalyzer
    WEATHER_AVAILABLE = True
except ImportError:
    WEATHER_AVAILABLE = False
    print("⚠️ Weather module not available")


class AdvancedBTTSAnalyzer:
    """
    Pro-level BTTS Analyzer mit korrigierter Poisson-Logik
    """
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "btts_data.db", 
                 weather_api_key: Optional[str] = None, api_football_key: Optional[str] = None):
        self.engine = DataEngine(api_key, db_path)
        self.db_path = db_path
        self.api_football_key = api_football_key
        
        # Weather Analyzer
        if WEATHER_AVAILABLE and weather_api_key:
            self.weather = WeatherAnalyzer(weather_api_key)
            print("✅ Weather analysis enabled!")
        else:
            self.weather = None
        
        # ML Models
        self.ml_model = None
        self.scaler = StandardScaler()
        self.model_trained = False
        
        # Weights für Ensemble
        self.weights = {
            'ml_model': 0.25,
            'statistical': 0.35,
            'form': 0.20,
            'h2h': 0.20
        }
        
        # Load or train model
        self.load_or_train_model()
    
    def prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data from historical matches"""
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT 
                m.match_id,
                m.home_team_id,
                m.away_team_id,
                m.btts,
                hs.btts_rate as home_btts_rate,
                hs.avg_goals_scored as home_goals_scored,
                hs.avg_goals_conceded as home_goals_conceded,
                hs.wins as home_wins,
                hs.matches_played as home_matches,
                aws.btts_rate as away_btts_rate,
                aws.avg_goals_scored as away_goals_scored,
                aws.avg_goals_conceded as away_goals_conceded,
                aws.wins as away_wins,
                aws.matches_played as away_matches
            FROM matches m
            JOIN team_stats hs ON m.home_team_id = hs.team_id 
                AND m.league_code = hs.league_code 
                AND hs.venue = 'home'
            JOIN team_stats aws ON m.away_team_id = aws.team_id 
                AND m.league_code = aws.league_code 
                AND aws.venue = 'away'
            WHERE m.btts IS NOT NULL
                AND hs.matches_played >= 3
                AND aws.matches_played >= 3
        '''
        
        try:
            df = pd.read_sql_query(query, conn)
        except:
            df = pd.DataFrame()
        finally:
            conn.close()
        
        if df.empty or len(df) < 50:
            print(f"⚠️ Not enough training data ({len(df)} matches)")
            return np.array([]), np.array([])
        
        features = [
            'home_btts_rate', 'away_btts_rate',
            'home_goals_scored', 'away_goals_scored',
            'home_goals_conceded', 'away_goals_conceded',
        ]
        
        X = df[features].values
        y = df['btts'].values
        
        # Remove NaN
        mask = ~np.isnan(X).any(axis=1)
        X = X[mask]
        y = y[mask]
        
        return X, y
    
    def train_model(self):
        """Train ML model"""
        X, y = self.prepare_training_data()
        
        if len(X) < 50:
            print("⚠️ Not enough data to train model")
            return
        
        print(f"📚 Training on {len(X)} matches...")
        
        X_scaled = self.scaler.fit_transform(X)
        
        self.ml_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            random_state=42
        )
        
        self.ml_model.fit(X_scaled, y)
        self.model_trained = True
        
        scores = cross_val_score(self.ml_model, X_scaled, y, cv=5)
        print(f"✅ Model trained! CV Accuracy: {scores.mean():.1%}")
        
        self.save_model()
    
    def save_model(self):
        """Save model to disk"""
        if not self.model_trained:
            return
        
        with open('ml_model.pkl', 'wb') as f:
            pickle.dump(self.ml_model, f)
        with open('scaler.pkl', 'wb') as f:
            pickle.dump(self.scaler, f)
        print("💾 Model saved")
    
    def load_model(self) -> bool:
        """Load model from disk"""
        model_path = Path("ml_model.pkl")
        scaler_path = Path("scaler.pkl")
        
        if not model_path.exists() or not scaler_path.exists():
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
    
    def load_or_train_model(self):
        """Load existing or train new model"""
        if not self.load_model():
            print("📚 Training new model...")
            self.train_model()
    
    def ml_predict(self, features: List[float]) -> Tuple[float, float]:
        """Get ML prediction"""
        if not self.model_trained or self.ml_model is None:
            return 0.5, 0.0
        
        try:
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            proba = self.ml_model.predict_proba(X_scaled)[0][1]
            return proba, 0.6
        except:
            return 0.5, 0.0
    
    def _poisson_at_least_one(self, expected_goals: float) -> float:
        """
        Poisson: P(X ≥ 1) = 1 - e^(-λ)
        """
        if expected_goals <= 0:
            return 20.0
        p_zero = math.exp(-expected_goals)
        return max(20, min(95, (1 - p_zero) * 100))
    
    def _poisson_over(self, expected: float, goals_needed: int) -> float:
        """P(X >= goals_needed)"""
        if expected <= 0:
            return 20.0
        p_under = sum((expected ** k) * math.exp(-expected) / math.factorial(k) 
                      for k in range(goals_needed))
        return max(10, min(90, (1 - p_under) * 100))
    
    def analyze_match(self, home_team_id: int, away_team_id: int, 
                     league_code: str) -> Dict:
        """
        KORRIGIERTE Match-Analyse mit Poisson-basierter BTTS-Berechnung
        """
        # Get team stats
        home_stats = self.engine.get_team_stats(home_team_id, league_code, 'home')
        away_stats = self.engine.get_team_stats(away_team_id, league_code, 'away')
        
        if not home_stats or not away_stats:
            return {'error': 'Insufficient data for teams'}
        
        # Get form
        home_form = self.engine.get_recent_form(home_team_id, league_code, 'home', 5)
        away_form = self.engine.get_recent_form(away_team_id, league_code, 'away', 5)
        
        # Get H2H
        h2h = self.engine.calculate_head_to_head(home_team_id, away_team_id)
        
        # =============================================
        # POISSON-BASIERTE BTTS BERECHNUNG
        # =============================================
        
        # Expected Goals berechnen
        home_scored = home_stats.get('avg_goals_scored', 1.2)
        away_conceded = away_stats.get('avg_goals_conceded', 1.2)
        exp_home = (home_scored + away_conceded) / 2 * 1.08  # Heimvorteil
        
        away_scored = away_stats.get('avg_goals_scored', 1.0)
        home_conceded = home_stats.get('avg_goals_conceded', 1.0)
        exp_away = (away_scored + home_conceded) / 2 * 0.92
        
        # Poisson-Wahrscheinlichkeiten
        p_home_scores = self._poisson_at_least_one(exp_home)
        p_away_scores = self._poisson_at_least_one(exp_away)
        
        # Statistische BTTS (Poisson)
        stat_btts = (p_home_scores * p_away_scores) / 100
        
        # Historische BTTS-Raten
        home_btts = home_stats.get('btts_rate', 50)
        away_btts = away_stats.get('btts_rate', 50)
        historical_btts = (home_btts + away_btts) / 2
        
        # Form BTTS
        form_btts = (home_form.get('btts_rate', 50) + away_form.get('btts_rate', 50)) / 2
        
        # H2H BTTS
        h2h_btts = h2h.get('btts_rate', historical_btts) if h2h.get('matches_played', 0) >= 3 else historical_btts
        
        # ML Prediction
        ml_features = [
            home_stats.get('btts_rate', 50),
            away_stats.get('btts_rate', 50),
            home_stats.get('avg_goals_scored', 1.2),
            away_stats.get('avg_goals_scored', 1.0),
            home_stats.get('avg_goals_conceded', 1.0),
            away_stats.get('avg_goals_conceded', 1.2),
        ]
        ml_prob, ml_conf = self.ml_predict(ml_features)
        
        # Gewichtete Kombination
        if self.model_trained:
            ensemble_prob = (
                self.weights['ml_model'] * ml_prob * 100 +
                self.weights['statistical'] * stat_btts +
                self.weights['form'] * form_btts +
                self.weights['h2h'] * h2h_btts
            )
        else:
            # Ohne ML: Mehr Gewicht auf Statistik
            ensemble_prob = (
                0.40 * stat_btts +
                0.30 * historical_btts +
                0.20 * form_btts +
                0.10 * h2h_btts
            )
        
        # Weather adjustment
        weather_adj = 0
        weather_data = None
        if self.weather:
            try:
                weather_data = self.weather.get_weather(home_stats.get('team_name', ''))
                if weather_data:
                    weather_adj = weather_data.get('btts_adjustment', 0)
            except:
                pass
        
        ensemble_prob += weather_adj
        ensemble_prob = max(20, min(85, ensemble_prob))
        
        # Over/Under
        expected_total = exp_home + exp_away
        over_25_prob = self._poisson_over(expected_total, 3)
        
        # Confidence
        confidence = self._calculate_confidence(home_stats, away_stats, h2h)
        
        # Recommendation
        recommendation = self._get_recommendation(ensemble_prob, confidence)
        
        return {
            'home_team': home_stats.get('team_name', 'Home'),
            'away_team': away_stats.get('team_name', 'Away'),
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            
            # BTTS
            'btts_probability': round(ensemble_prob, 1),
            'ensemble_probability': round(ensemble_prob, 1),
            'confidence': confidence,
            'recommendation': recommendation,
            
            # Breakdown
            'breakdown': {
                'p_home_scores': round(p_home_scores, 1),
                'p_away_scores': round(p_away_scores, 1),
                'statistical_btts': round(stat_btts, 1),
                'historical_btts': round(historical_btts, 1),
                'form_btts': round(form_btts, 1),
                'h2h_btts': round(h2h_btts, 1),
                'ml_prediction': round(ml_prob * 100, 1) if self.model_trained else None,
                'expected_home_goals': round(exp_home, 2),
                'expected_away_goals': round(exp_away, 2),
                'weather_adjustment': weather_adj
            },
            
            # Over/Under
            'over_under': {
                'expected_total': round(expected_total, 2),
                'over_25_probability': round(over_25_prob, 1),
                'over_35_probability': round(self._poisson_over(expected_total, 4), 1),
            },
            
            # Stats
            'home_stats': {
                'btts_rate': home_stats.get('btts_rate', 50),
                'avg_goals_scored': home_stats.get('avg_goals_scored', 1.2),
                'avg_goals_conceded': home_stats.get('avg_goals_conceded', 1.0),
                'matches_played': home_stats.get('matches_played', 0),
                'clean_sheets': home_stats.get('clean_sheets', 0),
                'wins': home_stats.get('wins', 0)
            },
            'away_stats': {
                'btts_rate': away_stats.get('btts_rate', 50),
                'avg_goals_scored': away_stats.get('avg_goals_scored', 1.0),
                'avg_goals_conceded': away_stats.get('avg_goals_conceded', 1.2),
                'matches_played': away_stats.get('matches_played', 0),
                'clean_sheets': away_stats.get('clean_sheets', 0),
                'wins': away_stats.get('wins', 0)
            },
            
            'h2h': h2h,
            'form': {
                'home': home_form,
                'away': away_form
            },
            'weather': weather_data
        }
    
    def _calculate_confidence(self, home_stats: Dict, away_stats: Dict, h2h: Dict) -> str:
        """Berechne Konfidenz"""
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
        
        if self.model_trained:
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
        """Generiere Empfehlung"""
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
    
    # ===== LEGACY METHODS für Kompatibilität =====
    
    def statistical_predict(self, home_btts: float, away_btts: float, 
                          home_goals: float, away_goals: float,
                          home_conceded: float, away_conceded: float) -> float:
        """Legacy method"""
        exp_home = (home_goals + away_conceded) / 2
        exp_away = (away_goals + home_conceded) / 2
        p_home = self._poisson_at_least_one(exp_home)
        p_away = self._poisson_at_least_one(exp_away)
        return (p_home * p_away) / 100


# Export
__all__ = ['AdvancedBTTSAnalyzer']
