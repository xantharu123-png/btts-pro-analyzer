"""
Advanced BTTS Pro Analyzer - COMPLETE VERSION
Includes: Dixon-Coles, CLV Tracking, Weather Integration
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sqlite3
import joblib
import os
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import math

# Try Weather Import
try:
    from weather_analyzer import WeatherAnalyzer
    WEATHER_AVAILABLE = True
except ImportError:
    WEATHER_AVAILABLE = False
    print("⚠️ Weather module not available")

# Try CLV Import
try:
    from clv_tracker import CLVTracker
    CLV_AVAILABLE = True
except ImportError:
    CLV_AVAILABLE = False
    print("⚠️ CLV Tracker not available")

from data_engine import DataEngine


class DixonColesModel:
    """Dixon-Coles Korrektur für Poisson-Verteilung"""
    
    def __init__(self, rho: float = -0.05):
        """
        rho: Korrelationsparameter für niedrige Ergebnisse
        Typischer Wert: -0.05 bis -0.15
        """
        self.rho = rho
    
    def tau(self, home_goals: int, away_goals: int) -> float:
        """
        Dixon-Coles Korrektur-Faktor τ
        Korrigiert Wahrscheinlichkeiten für:
        - 0:0
        - 1:0
        - 0:1
        - 1:1
        """
        if home_goals == 0 and away_goals == 0:
            return 1 - self.rho
        elif home_goals == 1 and away_goals == 0:
            return 1 + self.rho / 2
        elif home_goals == 0 and away_goals == 1:
            return 1 + self.rho / 2
        elif home_goals == 1 and away_goals == 1:
            return 1 - self.rho
        else:
            return 1.0
    
    def poisson_prob(self, k: int, lambda_val: float) -> float:
        """Standard Poisson-Wahrscheinlichkeit"""
        if lambda_val <= 0:
            return 1.0 if k == 0 else 0.0
        return (lambda_val ** k) * math.exp(-lambda_val) / math.factorial(k)
    
    def calculate_btts_probability(self, lambda_home: float, mu_away: float) -> float:
        """
        Berechne BTTS-Wahrscheinlichkeit mit Dixon-Coles Korrektur
        
        Args:
            lambda_home: Erwartete Tore Heimteam
            mu_away: Erwartete Tore Auswärtsteam
        
        Returns:
            BTTS Wahrscheinlichkeit in %
        """
        # Dixon-Coles korrigiert die GEMEINSAMEN Wahrscheinlichkeiten P(home=h, away=a)
        # nicht die einzelnen Verteilungen!
        
        # P(BTTS=No) = P(0,0) + P(1+,0) + P(0,1+)
        
        # P(0,0) mit Korrektur
        p_00 = self.poisson_prob(0, lambda_home) * self.poisson_prob(0, mu_away) * self.tau(0, 0)
        
        # P(Home≥1, Away=0) = P(1,0) + P(2,0) + P(3,0) + ...
        # Nur P(1,0) braucht Korrektur
        p_10 = self.poisson_prob(1, lambda_home) * self.poisson_prob(0, mu_away) * self.tau(1, 0)
        # Summe P(2,0) + P(3,0) + ... (keine Korrektur)
        p_home_only = p_10
        for h in range(2, 10):  # Summiere bis 10 Tore
            p_home_only += self.poisson_prob(h, lambda_home) * self.poisson_prob(0, mu_away)
        
        # P(Home=0, Away≥1) = P(0,1) + P(0,2) + P(0,3) + ...
        # Nur P(0,1) braucht Korrektur
        p_01 = self.poisson_prob(0, lambda_home) * self.poisson_prob(1, mu_away) * self.tau(0, 1)
        # Summe P(0,2) + P(0,3) + ... (keine Korrektur)
        p_away_only = p_01
        for a in range(2, 10):  # Summiere bis 10 Tore
            p_away_only += self.poisson_prob(0, lambda_home) * self.poisson_prob(a, mu_away)
        
        # P(BTTS) = 1 - P(BTTS=No)
        p_btts_no = p_00 + p_home_only + p_away_only
        p_btts = 1 - p_btts_no
        
        return max(0, min(100, p_btts * 100))


class AdvancedBTTSAnalyzer:
    """
    Advanced BTTS Analyzer mit:
    - Dixon-Coles Korrektur
    - CLV Tracking
    - Weather Integration
    - ML-Modellen
    """
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "btts_data.db", 
                 weather_api_key: Optional[str] = None, api_football_key: Optional[str] = None):
        
        # FIX: Verwende api_football_key für DataEngine!
        actual_key = api_football_key or api_key
        self.engine = DataEngine(actual_key, db_path)
        self.db_path = db_path
        self.api_football_key = actual_key
        
        # Dixon-Coles Model
        self.dixon_coles = DixonColesModel(rho=-0.05)
        print("✅ Dixon-Coles correction enabled!")
        
        # Weather Analyzer
        if WEATHER_AVAILABLE and weather_api_key:
            self.weather = WeatherAnalyzer(weather_api_key)
            print("✅ Weather analysis enabled!")
        else:
            self.weather = None
        
        # CLV Tracker
        if CLV_AVAILABLE:
            self.clv_tracker = CLVTracker(db_path=db_path.replace('.db', '_clv.db'))
            print("✅ CLV tracking enabled!")
        else:
            self.clv_tracker = None
        
        # ML Models
        self.ml_model = None
        self.scaler = StandardScaler()
        self.model_trained = False
        
        # Weights für Ensemble
        self.weights = {
            'dixon_coles': 0.30,  # Erhöht wegen besserer Genauigkeit
            'ml_model': 0.25,
            'statistical': 0.25,
            'form': 0.10,
            'h2h': 0.10
        }
        
        # Load or train model
        self.load_or_train_model()
    
    def record_prediction(self, fixture_id: int, home_team: str, away_team: str,
                         btts_prob: float, odds: float = None) -> Optional[int]:
        """Record prediction for CLV tracking"""
        if not self.clv_tracker or not odds:
            return None
        
        try:
            pred_id = self.clv_tracker.record_prediction(
                fixture_id=fixture_id,
                home_team=home_team,
                away_team=away_team,
                market_type='BTTS',
                prediction='Yes' if btts_prob > 50 else 'No',
                odds=odds,
                model_probability=btts_prob,
                confidence=self._calculate_confidence(btts_prob)
            )
            return pred_id
        except Exception as e:
            print(f"CLV tracking error: {e}")
            return None
    
    def _calculate_confidence(self, probability: float) -> int:
        """Calculate confidence level from probability"""
        if probability >= 70 or probability <= 30:
            return 90
        elif probability >= 60 or probability <= 40:
            return 75
        elif probability >= 55 or probability <= 45:
            return 60
        else:
            return 40
    
    def prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare training data from historical matches"""
        conn = sqlite3.connect(self.db_path)
        
        # Simplified query - just use matches table
        query = """
        SELECT 
            home_team, away_team, home_goals, away_goals, btts,
            league_id
        FROM matches
        WHERE home_goals IS NOT NULL 
        AND away_goals IS NOT NULL
        ORDER BY date DESC
        LIMIT 5000
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(df) < 100:
            print(f"⚠️ Not enough data for ML training: {len(df)} matches")
            return np.array([]), np.array([])
        
        # Feature Engineering
        features = []
        labels = []
        
        for idx, row in df.iterrows():
            # Basic features
            feat = [
                row['home_goals'] if pd.notna(row['home_goals']) else 1.5,
                row['away_goals'] if pd.notna(row['away_goals']) else 1.2,
                row['league_id'] if pd.notna(row['league_id']) else 78,
            ]
            
            features.append(feat)
            labels.append(1 if row['btts'] == 1 else 0)
        
        return np.array(features), np.array(labels)
    
    def load_or_train_model(self):
        """Load existing model or train new one"""
        model_path = self.db_path.replace('.db', '_model.pkl')
        scaler_path = self.db_path.replace('.db', '_scaler.pkl')
        
        if os.path.exists(model_path) and os.path.exists(scaler_path):
            try:
                self.ml_model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                self.model_trained = True
                print("✅ ML model loaded")
                return
            except Exception as e:
                print(f"⚠️ Could not load model: {e}")
        
        # Train new model
        self.train_model()
    
    def train_model(self) -> bool:
        """Train ML model"""
        X, y = self.prepare_training_data()
        
        if len(X) == 0:
            print("⚠️ No training data available")
            return False
        
        print(f"🎯 Training ML model with {len(X)} matches...")
        
        try:
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            self.ml_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                random_state=42
            )
            self.ml_model.fit(X_scaled, y)
            self.model_trained = True
            
            # Save model
            model_path = self.db_path.replace('.db', '_model.pkl')
            scaler_path = self.db_path.replace('.db', '_scaler.pkl')
            joblib.dump(self.ml_model, model_path)
            joblib.dump(self.scaler, scaler_path)
            
            print(f"✅ Model trained and saved!")
            return True
            
        except Exception as e:
            print(f"❌ Training failed: {e}")
            return False
    
    def calculate_btts_probability(self, home_stats: Dict, away_stats: Dict, 
                                   minute: int = 0, home_score: int = 0, 
                                   away_score: int = 0) -> Dict:
        """
        Calculate BTTS probability using Dixon-Coles + ML + Weather
        
        Returns:
            Dict with probabilities and factors
        """
        # Already BTTS?
        if home_score > 0 and away_score > 0:
            return {
                'btts_yes': 100.0,
                'btts_no': 0.0,
                'confidence': 100,
                'method': 'CONFIRMED'
            }
        
        # Extract xG
        home_xg = home_stats.get('xg', home_stats.get('goals_avg', 1.5))
        away_xg = away_stats.get('xg', away_stats.get('goals_avg', 1.2))
        
        # Weather adjustment
        weather_factor = 1.0
        if self.weather:
            try:
                home_team_name = home_stats.get('name', '')
                weather_data = self.weather.get_weather(home_team_name)
                if weather_data:
                    weather_factor = 1.0 + (weather_data['btts_adjustment'] / 100)
                    home_xg *= weather_factor
                    away_xg *= weather_factor
            except Exception as e:
                print(f"Weather error: {e}")
        
        # Dixon-Coles Probability
        dixon_coles_prob = self.dixon_coles.calculate_btts_probability(home_xg, away_xg)
        
        # ML Probability (if available)
        ml_prob = 50.0
        if self.model_trained and self.ml_model:
            try:
                features = [[home_xg, away_xg, home_stats.get('league_id', 78)]]
                features_scaled = self.scaler.transform(features)
                ml_prob = self.ml_model.predict_proba(features_scaled)[0][1] * 100
            except Exception as e:
                ml_prob = 50.0
        
        # Statistical (simple Poisson)
        p_home = 1 - math.exp(-home_xg)
        p_away = 1 - math.exp(-away_xg)
        stat_prob = p_home * p_away * 100
        
        # Form/H2H (placeholder - could be enhanced)
        form_prob = 50.0
        h2h_prob = 50.0
        
        # Ensemble
        final_prob = (
            dixon_coles_prob * self.weights['dixon_coles'] +
            ml_prob * self.weights['ml_model'] +
            stat_prob * self.weights['statistical'] +
            form_prob * self.weights['form'] +
            h2h_prob * self.weights['h2h']
        )
        
        # Adjust for game state
        if minute > 60 and home_score == 0 and away_score == 0:
            final_prob *= 0.7  # Reduce probability in late 0-0
        
        return {
            'btts_yes': round(final_prob, 1),
            'btts_no': round(100 - final_prob, 1),
            'confidence': self._calculate_confidence(final_prob),
            'method': 'DIXON_COLES_ENSEMBLE',
            'components': {
                'dixon_coles': round(dixon_coles_prob, 1),
                'ml': round(ml_prob, 1),
                'statistical': round(stat_prob, 1),
                'weather_factor': round(weather_factor, 3)
            }
        }
    
    def analyze_match(self, home_team_id: int, away_team_id: int, 
                     league_code: str = 'BL1', fixture_id: int = None) -> Optional[Dict]:
        """Analyze a match for BTTS probability"""
        try:
            # Get team statistics
            home_stats = self.engine.get_team_statistics(home_team_id, league_code)
            away_stats = self.engine.get_team_statistics(away_team_id, league_code)
            
            if not home_stats or not away_stats:
                print(f"⚠️ Could not get statistics for teams {home_team_id} vs {away_team_id}")
                return None
            
            # Calculate BTTS
            result = self.calculate_btts_probability(home_stats, away_stats)
            
            # Add team info
            result['home_team'] = home_stats.get('name', f'Team {home_team_id}')
            result['away_team'] = away_stats.get('name', f'Team {away_team_id}')
            result['fixture_id'] = fixture_id
            
            return result
            
        except Exception as e:
            print(f"❌ Analysis error: {e}")
            return None


# Backward compatibility
if __name__ == "__main__":
    print("🚀 Advanced BTTS Analyzer with Dixon-Coles, CLV, Weather")
    print("=" * 60)
    
    # Test Dixon-Coles
    dc = DixonColesModel()
    test_btts = dc.calculate_btts_probability(2.1, 1.3)
    print(f"Test BTTS (λ=2.1, μ=1.3): {test_btts:.1f}%")
    
    # Compare with simple Poisson
    p_home = 1 - math.exp(-2.1)
    p_away = 1 - math.exp(-1.3)
    simple = p_home * p_away * 100
    print(f"Simple Poisson: {simple:.1f}%")
    print(f"Difference: {test_btts - simple:+.1f}%")
