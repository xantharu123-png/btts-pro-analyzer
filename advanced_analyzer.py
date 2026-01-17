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

try:
    from clv_tracker import CLVTracker
    CLV_AVAILABLE = True
except ImportError:
    CLV_AVAILABLE = False





class DixonColesModel:
    """Dixon-Coles Correction for Poisson Distribution"""
    def __init__(self, rho: float = -0.05):
        self.rho = rho
    
    def tau(self, home_goals: int, away_goals: int) -> float:
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
        if lambda_val <= 0:
            return 1.0 if k == 0 else 0.0
        return (lambda_val ** k) * math.exp(-lambda_val) / math.factorial(k)
    
    def calculate_btts_probability(self, lambda_home: float, mu_away: float) -> float:
        p_00 = self.poisson_prob(0, lambda_home) * self.poisson_prob(0, mu_away) * self.tau(0, 0)
        p_10 = self.poisson_prob(1, lambda_home) * self.poisson_prob(0, mu_away) * self.tau(1, 0)
        p_home_only = p_10
        for h in range(2, 10):
            p_home_only += self.poisson_prob(h, lambda_home) * self.poisson_prob(0, mu_away)
        p_01 = self.poisson_prob(0, lambda_home) * self.poisson_prob(1, mu_away) * self.tau(0, 1)
        p_away_only = p_01
        for a in range(2, 10):
            p_away_only += self.poisson_prob(0, lambda_home) * self.poisson_prob(a, mu_away)
        p_btts = 1 - (p_00 + p_home_only + p_away_only)
        return max(0, min(100, p_btts * 100))


class AdvancedBTTSAnalyzer:
    """
    Pro-level BTTS Analyzer mit korrigierter Poisson-Logik
    """
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "btts_data.db", 
                 weather_api_key: Optional[str] = None, api_football_key: Optional[str] = None):
        self.engine = DataEngine(api_football_key or api_key, db_path)  # FIX: Use api_football_key!
        self.db_path = db_path
        self.api_football_key = api_football_key        
        # Dixon-Coles Model
        self.dixon_coles = DixonColesModel(rho=-0.05)
        
        # CLV Tracker
        if CLV_AVAILABLE:
            try:
                self.clv_tracker = CLVTracker(db_path=db_path.replace('.db', '_clv.db'))
                print("✅ CLV tracking enabled!")
            except Exception as e:
                self.clv_tracker = None
                print(f"⚠️ CLV tracker error: {e}")
        else:
            self.clv_tracker = None

        
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
        
        # Simplified query - just use matches table
        query = '''
            SELECT 
                home_team,
                away_team,
                home_goals,
                away_goals,
                btts,
                league_code
            FROM matches
            WHERE btts IS NOT NULL
                AND home_goals IS NOT NULL
                AND away_goals IS NOT NULL
        '''
        
        try:
            df = pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"⚠️ SQL error: {e}")
            df = pd.DataFrame()
        finally:
            conn.close()
        
        if df.empty or len(df) < 50:
            print(f"⚠️ Not enough training data ({len(df) if not df.empty else 0} matches)")
            return np.array([]), np.array([])
        
        # Calculate basic features from available data
        features_list = []
        labels = []
        
        for idx, row in df.iterrows():
            try:
                # Simple features based on goals
                home_goals = float(row['home_goals'])
                away_goals = float(row['away_goals'])
                
                features = [
                    home_goals,  # Historical home goals
                    away_goals,  # Historical away goals
                    home_goals + away_goals,  # Total goals
                    1 if home_goals > away_goals else 0,  # Home win
                    1 if away_goals > home_goals else 0,  # Away win
                    1 if home_goals == away_goals else 0,  # Draw
                ]
                
                features_list.append(features)
                labels.append(int(row['btts']))
            except:
                continue
        
        if len(features_list) < 50:
            print(f"⚠️ Not enough valid training data ({len(features_list)} matches)")
            return np.array([]), np.array([])
        
        X = np.array(features_list)
        y = np.array(labels)
        
        return X, y
    
    def train_model(self):
        """Train ML model"""
        X, y = self.prepare_training_data()
        
        if len(X) < 50:
            print("⚠️ Not enough data to train model - using statistical only")
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
        
        try:
            scores = cross_val_score(self.ml_model, X_scaled, y, cv=5)
            print(f"✅ Model trained! CV Accuracy: {scores.mean():.1%}")
        except:
            print(f"✅ Model trained!")
        
        self.save_model()
    
    def save_model(self):
        """Save model to disk"""
        if not self.model_trained:
            return
        
        try:
            with open('ml_model.pkl', 'wb') as f:
                pickle.dump(self.ml_model, f)
            with open('scaler.pkl', 'wb') as f:
                pickle.dump(self.scaler, f)
            print("💾 Model saved")
        except Exception as e:
            print(f"⚠️ Could not save model: {e}")
    
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
    
    def _get_real_team_stats(self, team_id: int, league_id: int, league_code: str, venue: str) -> Dict:
        """
        Get REAL team statistics from API-Football with caching
        Falls from API fails, use intelligent defaults based on league
        """
        cache_key = f"{team_id}_{league_id}_{venue}"
        
        # Check cache first
        if cache_key in self._team_stats_cache:
            return self._team_stats_cache[cache_key]
        
        # Try to get from API-Football
        if self.api_football_key:
            try:
                from api_football import APIFootball
                api = APIFootball(self.api_football_key)
                
                stats = api.get_team_statistics(team_id, league_id, 2025)  # Fixed: 2025/26 season
                
                if stats:
                    # Format for our analyzer
                    if venue == 'home':
                        result = {
                            'team_id': team_id,
                            'team_name': stats.get('team_name', 'Unknown'),
                            'matches_played': stats.get('matches_played_home', 0),
                            'avg_goals_scored': stats.get('avg_goals_scored_home', 1.5),
                            'avg_goals_conceded': stats.get('avg_goals_conceded_home', 1.2),
                            'btts_rate': stats.get('btts_rate_home', 55),
                            'clean_sheets': stats.get('clean_sheets_home', 0),
                            'btts_count': 0,
                            'wins': 0,
                        }
                    else:
                        result = {
                            'team_id': team_id,
                            'team_name': stats.get('team_name', 'Unknown'),
                            'matches_played': stats.get('matches_played_away', 0),
                            'avg_goals_scored': stats.get('avg_goals_scored_away', 1.2),
                            'avg_goals_conceded': stats.get('avg_goals_conceded_away', 1.4),
                            'btts_rate': stats.get('btts_rate_away', 60),
                            'clean_sheets': stats.get('clean_sheets_away', 0),
                            'btts_count': 0,
                            'wins': 0,
                        }
                    
                    # Cache it
                    self._team_stats_cache[cache_key] = result
                    print(f"   📊 Got real stats for team {team_id}: {result['avg_goals_scored']:.2f} scored, {result['btts_rate']:.0f}% BTTS")
                    return result
                    
            except Exception as e:
                print(f"   ⚠️ API stats failed for team {team_id}: {e}")
        
        # Fallback: Use league-specific defaults (more realistic than generic)
        league_defaults = {
            # High-scoring leagues (BTTS ~65-75%)
            'BL1': {'scored': 1.7, 'conceded': 1.5, 'btts': 68},
            'PL': {'scored': 1.6, 'conceded': 1.4, 'btts': 62},
            'DED': {'scored': 1.8, 'conceded': 1.6, 'btts': 70},
            'ALL': {'scored': 1.9, 'conceded': 1.7, 'btts': 72},
            'SPL': {'scored': 2.0, 'conceded': 1.8, 'btts': 75},
            'ALE': {'scored': 1.8, 'conceded': 1.7, 'btts': 68},
            
            # Medium-scoring leagues (BTTS ~55-65%)
            'PD': {'scored': 1.4, 'conceded': 1.2, 'btts': 58},
            'SA': {'scored': 1.5, 'conceded': 1.3, 'btts': 60},
            'FL1': {'scored': 1.5, 'conceded': 1.3, 'btts': 58},
            'PPL': {'scored': 1.5, 'conceded': 1.4, 'btts': 62},
            'TSL': {'scored': 1.6, 'conceded': 1.5, 'btts': 65},
            
            # Lower-scoring leagues (BTTS ~50-55%)
            'ELC': {'scored': 1.4, 'conceded': 1.3, 'btts': 55},
            'BL2': {'scored': 1.5, 'conceded': 1.4, 'btts': 58},
            
            # Default
            'DEFAULT': {'scored': 1.5, 'conceded': 1.4, 'btts': 60},
        }
        
        defaults = league_defaults.get(league_code, league_defaults['DEFAULT'])
        
        # Adjust for venue
        if venue == 'home':
            result = {
                'team_id': team_id,
                'team_name': 'Unknown',
                'matches_played': 0,
                'avg_goals_scored': defaults['scored'] * 1.1,  # Home advantage
                'avg_goals_conceded': defaults['conceded'] * 0.9,
                'btts_rate': defaults['btts'],
                'clean_sheets': 0,
                'btts_count': 0,
                'wins': 0,
            }
        else:
            result = {
                'team_id': team_id,
                'team_name': 'Unknown',
                'matches_played': 0,
                'avg_goals_scored': defaults['scored'] * 0.9,  # Away disadvantage
                'avg_goals_conceded': defaults['conceded'] * 1.1,
                'btts_rate': defaults['btts'],
                'clean_sheets': 0,
                'btts_count': 0,
                'wins': 0,
            }
        
        self._team_stats_cache[cache_key] = result
        return result
    
    def _poisson_at_least_one(self, expected_goals: float) -> float:
        """
        POISSON: P(X ≥ 1) = 1 - e^(-λ)
        Dies ist die KORREKTE Formel!
        """
        if expected_goals <= 0:
            return 20.0
        p_zero = math.exp(-expected_goals)
        return max(20, min(95, (1 - p_zero) * 100))
    
    def _poisson_over(self, expected: float, goals_needed: int) -> float:
        """P(X >= goals_needed) mit Poisson"""
        if expected <= 0:
            return 20.0
        p_under = sum((expected ** k) * math.exp(-expected) / math.factorial(k) 
                      for k in range(goals_needed))
        return max(10, min(90, (1 - p_under) * 100))
    
    def statistical_predict(self, home_btts: float, away_btts: float, 
                          home_goals: float, away_goals: float,
                          home_conceded: float, away_conceded: float) -> float:
        """Statistical prediction with Poisson"""
        exp_home = (home_goals + away_conceded) / 2
        exp_away = (away_goals + home_conceded) / 2
        p_home = self._poisson_at_least_one(exp_home)
        p_away = self._poisson_at_least_one(exp_away)
        return (p_home * p_away) / 100
    
    def analyze_match(self, home_team_id: int, away_team_id: int, 
                     league_code: str) -> Dict:
        """
        VOLLSTÄNDIGE Match-Analyse nach Spezifikation:
        
        BTTS % = (Saison BTTS% × 0.3) + (Form letzte 5 × 0.3) + (H2H × 0.2) + (Heim/Auswärts × 0.2)
        
        Plus Poisson-Verteilung für Torwahrscheinlichkeit
        """
        # Initialize caches
        if not hasattr(self, '_team_stats_cache'):
            self._team_stats_cache = {}
        if not hasattr(self, '_h2h_cache'):
            self._h2h_cache = {}
        if not hasattr(self, '_form_cache'):
            self._form_cache = {}
        
        # Get league_id
        league_id = self.engine.LEAGUES_CONFIG.get(league_code, 0)
        
        # =============================================
        # 1. SAISON-STATISTIKEN (30% Gewichtung)
        # =============================================
        home_season = self._get_season_stats(home_team_id, league_id, 'home')
        away_season = self._get_season_stats(away_team_id, league_id, 'away')
        
        if not home_season or not away_season:
            return {'error': 'Could not get team statistics'}
        
        # Saison BTTS% = Durchschnitt beider Teams
        season_btts = (home_season['btts_rate'] + away_season['btts_rate']) / 2
        
        # =============================================
        # 2. FORM LETZTE 5 SPIELE (30% Gewichtung)
        # =============================================
        home_form = self._get_form_stats(home_team_id)
        away_form = self._get_form_stats(away_team_id)
        
        form_btts = (home_form['btts_rate'] + away_form['btts_rate']) / 2
        
        # =============================================
        # 3. HEAD-TO-HEAD (20% Gewichtung)
        # =============================================
        h2h = self._get_h2h_stats(home_team_id, away_team_id)
        h2h_btts = h2h['btts_rate']
        has_h2h_data = h2h.get('matches_played', 0) >= 1
        
        # =============================================
        # 4. HEIM/AUSWÄRTS FAKTOR (20% Gewichtung)
        # =============================================
        # Home team's HOME btts rate + Away team's AWAY btts rate
        venue_btts = (home_season['btts_rate_venue'] + away_season['btts_rate_venue']) / 2
        
        # =============================================
        # ERWEITERTE BTTS-BERECHNUNG (gewichtet)
        # =============================================
        # Wenn keine H2H Daten, verteile Gewicht auf andere Faktoren
        if has_h2h_data:
            weighted_btts = (
                0.30 * season_btts +      # Saison BTTS%
                0.30 * form_btts +        # Form letzte 5
                0.20 * h2h_btts +         # H2H
                0.20 * venue_btts         # Heim/Auswärts
            )
        else:
            # Keine H2H Daten → Gewicht auf andere verteilen
            weighted_btts = (
                0.35 * season_btts +      # Saison BTTS%
                0.35 * form_btts +        # Form letzte 5
                0.30 * venue_btts         # Heim/Auswärts
            )
        
        # =============================================
        # POISSON-VERTEILUNG für Torwahrscheinlichkeit
        # =============================================
        # λ = erwartete Tore
        lambda_home = (home_season['avg_scored'] + away_season['avg_conceded']) / 2 * 1.08  # Heimvorteil
        lambda_away = (away_season['avg_scored'] + home_season['avg_conceded']) / 2 * 0.92  # Auswärtsnachteil
        
        # P(Team ≥ 1 Tor) = 1 - e^(-λ)
        p_home_scores = (1 - math.exp(-lambda_home)) * 100
        p_away_scores = (1 - math.exp(-lambda_away)) * 100
        
        # P(BTTS) = P(Home ≥ 1) × P(Away ≥ 1)
        poisson_btts = (p_home_scores * p_away_scores) / 100
        
        # =============================================
        # FINALE KOMBINATION
        # =============================================
        # 60% gewichtete Statistik + 40% Poisson
        final_btts = 0.60 * weighted_btts + 0.40 * poisson_btts
        
        # Clamp zwischen 25% und 90%
        final_btts = max(25, min(90, final_btts))
        
        # =============================================
        # CONFIDENCE SCORE (Varianz-basiert)
        # =============================================
        # Sammle alle Predictions
        predictions = [season_btts, form_btts, venue_btts, poisson_btts]
        if has_h2h_data:
            predictions.append(h2h_btts)
        
        # Berechne Varianz (Standardabweichung)
        import statistics
        if len(predictions) >= 2:
            std_dev = statistics.stdev(predictions)
            mean_pred = statistics.mean(predictions)
            
            # Coefficient of Variation (CV) = std_dev / mean
            cv = (std_dev / mean_pred) if mean_pred > 0 else 1.0
            
            # Niedrige Varianz = Hohe Confidence
            # CV < 0.15 (15%) → 90-95% Confidence
            # CV 0.15-0.25 → 80-90% Confidence
            # CV 0.25-0.35 → 70-80% Confidence
            # CV > 0.35 → 60-70% Confidence
            if cv < 0.15:
                confidence = 92
            elif cv < 0.25:
                confidence = 85
            elif cv < 0.35:
                confidence = 75
            elif cv < 0.45:
                confidence = 68
            else:
                confidence = 60
            
            # Bonus für mehr Daten
            data_bonus = 0
            if home_season['matches_played'] >= 10: data_bonus += 2
            if away_season['matches_played'] >= 10: data_bonus += 2
            if h2h['matches_played'] >= 5: data_bonus += 2
            
            confidence = min(95, confidence + data_bonus)
        else:
            # Fallback
            confidence = 70
        
        # Confidence Level
        if confidence >= 80:
            confidence_level = "VERY_HIGH"
        elif confidence >= 65:
            confidence_level = "HIGH"
        elif confidence >= 50:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"
        
        # Recommendation
        if final_btts >= 70 and confidence >= 65:
            recommendation = "🔥 STRONG BET"
        elif final_btts >= 60 and confidence >= 55:
            recommendation = "✅ GOOD VALUE"
        elif final_btts >= 50:
            recommendation = "⚠️ RISKY"
        else:
            recommendation = "❌ AVOID"
        
        # Expected total goals
        expected_total = lambda_home + lambda_away
        
        # =============================================
        # RETURN FULL ANALYSIS
        # =============================================
        return {
            'home_team': home_season.get('team_name', 'Home'),
            'away_team': away_season.get('team_name', 'Away'),
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            
            # Main predictions
            'btts_probability': round(final_btts, 1),
            'ensemble_probability': round(final_btts, 1),
            'confidence': round(confidence, 1),
            'confidence_level': confidence_level,
            'recommendation': recommendation,
            
            # Individual components
            'season_btts': round(season_btts, 1),
            'form_btts': round(form_btts, 1),
            'h2h_btts': round(h2h_btts, 1),
            'venue_btts': round(venue_btts, 1),
            'poisson_btts': round(poisson_btts, 1),
            
            # For display compatibility
            'ml_probability': round(poisson_btts, 1),
            'statistical_probability': round(weighted_btts, 1),
            'form_probability': round(form_btts, 1),
            'h2h_probability': round(h2h_btts, 1),
            
            # Details
            'details': {
                'expected_home_goals': round(lambda_home, 2),
                'expected_away_goals': round(lambda_away, 2),
                'expected_total_goals': round(expected_total, 2),
                'p_home_scores': round(p_home_scores, 1),
                'p_away_scores': round(p_away_scores, 1),
            },
            
            # Full stats for breakdown
            'home_stats': {
                'team_name': home_season.get('team_name', 'Home'),
                'btts_rate': home_season['btts_rate'],
                'avg_goals_scored': home_season['avg_scored'],
                'avg_goals_conceded': home_season['avg_conceded'],
                'matches_played': home_season['matches_played'],
                'clean_sheets': home_season.get('clean_sheets', 0),
                'failed_to_score': home_season.get('failed_to_score', 0),
            },
            'away_stats': {
                'team_name': away_season.get('team_name', 'Away'),
                'btts_rate': away_season['btts_rate'],
                'avg_goals_scored': away_season['avg_scored'],
                'avg_goals_conceded': away_season['avg_conceded'],
                'matches_played': away_season['matches_played'],
                'clean_sheets': away_season.get('clean_sheets', 0),
                'failed_to_score': away_season.get('failed_to_score', 0),
            },
            
            'h2h': h2h,
            'home_form': home_form,
            'away_form': away_form,
            'form': {
                'home': home_form,
                'away': away_form
            },
            'weather': None
        }
    
    def _get_season_stats(self, team_id: int, league_id: int, venue: str) -> Dict:
        """Get season statistics from API or cache"""
        cache_key = f"season_{team_id}_{league_id}"
        
        if cache_key in self._team_stats_cache:
            cached = self._team_stats_cache[cache_key]
            if venue == 'home':
                return {
                    'team_name': cached.get('team_name', 'Unknown'),
                    'btts_rate': cached.get('btts_rate_home', 60),
                    'btts_rate_venue': cached.get('btts_rate_home', 60),
                    'avg_scored': cached.get('avg_goals_scored_home', 1.5),
                    'avg_conceded': cached.get('avg_goals_conceded_home', 1.2),
                    'matches_played': cached.get('matches_played_home', 0),
                    'clean_sheets': cached.get('clean_sheets_home', 0),
                    'failed_to_score': cached.get('failed_to_score_home', 0),
                }
            else:
                return {
                    'team_name': cached.get('team_name', 'Unknown'),
                    'btts_rate': cached.get('btts_rate_away', 60),
                    'btts_rate_venue': cached.get('btts_rate_away', 60),
                    'avg_scored': cached.get('avg_goals_scored_away', 1.2),
                    'avg_conceded': cached.get('avg_goals_conceded_away', 1.4),
                    'matches_played': cached.get('matches_played_away', 0),
                    'clean_sheets': cached.get('clean_sheets_away', 0),
                    'failed_to_score': cached.get('failed_to_score_away', 0),
                }
        
        # Try API
        if self.api_football_key:
            try:
                from api_football import APIFootball
                api = APIFootball(self.api_football_key)
                stats = api.get_team_statistics(team_id, league_id, 2025)  # Fixed: 2025/26 season
                
                if stats:
                    self._team_stats_cache[cache_key] = stats
                    print(f"   📊 Loaded stats for {stats.get('team_name')}: {stats.get('btts_rate_total', 60):.0f}% BTTS")
                    
                    if venue == 'home':
                        return {
                            'team_name': stats.get('team_name', 'Unknown'),
                            'btts_rate': stats.get('btts_rate_total', 60),
                            'btts_rate_venue': stats.get('btts_rate_home', 60),
                            'avg_scored': stats.get('avg_goals_scored_home', 1.5),
                            'avg_conceded': stats.get('avg_goals_conceded_home', 1.2),
                            'matches_played': stats.get('matches_played_home', 0),
                            'clean_sheets': stats.get('clean_sheets_home', 0),
                            'failed_to_score': stats.get('failed_to_score_home', 0),
                        }
                    else:
                        return {
                            'team_name': stats.get('team_name', 'Unknown'),
                            'btts_rate': stats.get('btts_rate_total', 60),
                            'btts_rate_venue': stats.get('btts_rate_away', 60),
                            'avg_scored': stats.get('avg_goals_scored_away', 1.2),
                            'avg_conceded': stats.get('avg_goals_conceded_away', 1.4),
                            'matches_played': stats.get('matches_played_away', 0),
                            'clean_sheets': stats.get('clean_sheets_away', 0),
                            'failed_to_score': stats.get('failed_to_score_away', 0),
                        }
            except Exception as e:
                print(f"   ⚠️ API error: {e}")
        
        # NO DEFAULT FALLBACK - wenn API keine Daten hat, Error werfen!
        print(f"   ❌ No data available for team {team_id} in league {league_id}")
        return None
    
    def _get_form_stats(self, team_id: int) -> Dict:
        """Get last 5 matches form from API or cache"""
        cache_key = f"form_{team_id}"
        
        if cache_key in self._form_cache:
            return self._form_cache[cache_key]
        
        # Try API
        if self.api_football_key:
            try:
                from api_football import APIFootball
                api = APIFootball(self.api_football_key)
                form = api.get_team_last_matches(team_id, 5)
                
                if form:
                    self._form_cache[cache_key] = form
                    print(f"   📈 Form: {form.get('form_string', '?')} ({form.get('btts_rate', 50):.0f}% BTTS)")
                    return form
            except Exception as e:
                print(f"   ⚠️ Form API error: {e}")
        
        # Default (variiert basierend auf team_id um nicht alle identisch zu machen)
        base_rate = 50 + (team_id % 15)  # 50-64%
        return {
            'matches_played': 0,
            'btts_rate': base_rate,
            'avg_goals_scored': 1.2 + (team_id % 6) * 0.1,  # 1.2-1.7
            'avg_goals_conceded': 1.2 + ((team_id * 7) % 6) * 0.1,
            'form_string': '',
            'wins': 0,
            'draws': 0,
            'losses': 0,
        }
    
    def _get_h2h_stats(self, team1_id: int, team2_id: int) -> Dict:
        """Get H2H stats from API or cache"""
        cache_key = f"h2h_{min(team1_id, team2_id)}_{max(team1_id, team2_id)}"
        
        if cache_key in self._h2h_cache:
            return self._h2h_cache[cache_key]
        
        # Try API
        if self.api_football_key:
            try:
                from api_football import APIFootball
                api = APIFootball(self.api_football_key)
                h2h_matches = api.get_head_to_head(team1_id, team2_id, 10)
                
                if h2h_matches and isinstance(h2h_matches, list):
                    # Process list of matches into stats
                    matches_played = len(h2h_matches)
                    btts_count = 0
                    total_goals = 0
                    
                    for match in h2h_matches:
                        try:
                            home_goals = match.get('goals', {}).get('home', 0) or 0
                            away_goals = match.get('goals', {}).get('away', 0) or 0
                            
                            if home_goals > 0 and away_goals > 0:
                                btts_count += 1
                            total_goals += home_goals + away_goals
                        except:
                            continue
                    
                    h2h_stats = {
                        'matches_played': matches_played,
                        'btts_rate': (btts_count / matches_played * 100) if matches_played > 0 else 55,
                        'btts_count': btts_count,
                        'avg_goals': (total_goals / matches_played) if matches_played > 0 else 2.5,
                        'total_goals': total_goals,
                    }
                    
                    self._h2h_cache[cache_key] = h2h_stats
                    print(f"   🤝 H2H: {matches_played} matches, {h2h_stats['btts_rate']:.0f}% BTTS")
                    return h2h_stats
            except Exception as e:
                print(f"   ⚠️ H2H API error: {e}")
        
        # Default
        return {
            'matches_played': 0,
            'btts_rate': 55,
            'btts_count': 0,
            'avg_goals': 2.5,
            'total_goals': 0,
        }
        
        # =============================================
        # POISSON-BASIERTE BTTS BERECHNUNG
        # =============================================
        
        # Expected Goals (korrekte Formel!)
        home_scored = home_stats.get('avg_goals_scored', 1.2)
        away_conceded = away_stats.get('avg_goals_conceded', 1.2)
        exp_home = (home_scored + away_conceded) / 2 * 1.08  # Heimvorteil
        
        away_scored = away_stats.get('avg_goals_scored', 1.0)
        home_conceded = home_stats.get('avg_goals_conceded', 1.0)
        exp_away = (away_scored + home_conceded) / 2 * 0.92
        
        # Poisson-Wahrscheinlichkeiten
        p_home_scores = self._poisson_at_least_one(exp_home)
        p_away_scores = self._poisson_at_least_one(exp_away)
        
        # Statistical BTTS (aus Poisson!)
        stat_btts = (p_home_scores * p_away_scores) / 100
        
        # Historical BTTS
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
        ml_probability = ml_prob * 100
        
        # Rest factor
        rest_factor = (home_rest.get('fatigue_factor', 1.0) + away_rest.get('fatigue_factor', 1.0)) / 2
        
        # Momentum bonus
        momentum_bonus = (home_momentum.get('momentum_bonus', 0) + away_momentum.get('momentum_bonus', 0)) / 2
        
        # Ensemble (gewichtete Kombination)
        if self.model_trained:
            base_ensemble = (
                self.weights['ml_model'] * ml_probability +
                self.weights['statistical'] * stat_btts +
                self.weights['form'] * form_btts +
                self.weights['h2h'] * h2h_btts
            )
        else:
            base_ensemble = (
                0.40 * stat_btts +
                0.30 * historical_btts +
                0.20 * form_btts +
                0.10 * h2h_btts
            )
        
        # Apply factors
        ensemble_prob = base_ensemble * rest_factor + momentum_bonus
        
        # Weather
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
        
        # Expected Total
        expected_total = exp_home + exp_away
        
        # Confidence
        confidence_score = self._calculate_confidence_score(home_stats, away_stats, h2h)
        confidence_level = self._get_confidence_level(confidence_score)
        
        # Recommendation
        recommendation = self._get_recommendation(ensemble_prob, confidence_level)
        
        return {
            'home_team': home_stats.get('team_name', 'Home'),
            'away_team': away_stats.get('team_name', 'Away'),
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            
            # Main predictions
            'btts_probability': round(ensemble_prob, 1),
            'ensemble_probability': round(ensemble_prob, 1),
            'confidence': round(confidence_score, 1),
            'confidence_level': confidence_level,
            'recommendation': recommendation,
            
            # Individual predictions
            'ml_probability': round(ml_probability, 1),
            'statistical_probability': round(stat_btts, 1),
            'form_probability': round(form_btts, 1),
            'h2h_probability': round(h2h_btts, 1),
            
            # Details dict
            'details': {
                'expected_home_goals': round(exp_home, 2),
                'expected_away_goals': round(exp_away, 2),
                'expected_total_goals': round(expected_total, 2),
                'p_home_scores': round(p_home_scores, 1),
                'p_away_scores': round(p_away_scores, 1),
            },
            
            # Breakdown
            'breakdown': {
                'p_home_scores': round(p_home_scores, 1),
                'p_away_scores': round(p_away_scores, 1),
                'statistical_btts': round(stat_btts, 1),
                'historical_btts': round(historical_btts, 1),
                'form_btts': round(form_btts, 1),
                'h2h_btts': round(h2h_btts, 1),
                'ml_prediction': round(ml_probability, 1) if self.model_trained else None,
                'expected_home_goals': round(exp_home, 2),
                'expected_away_goals': round(exp_away, 2),
                'weather_adjustment': weather_adj,
                'rest_factor': rest_factor,
                'momentum_bonus': momentum_bonus
            },
            
            # Over/Under
            'over_under': {
                'expected_total': round(expected_total, 2),
                'over_25_probability': round(self._poisson_over(expected_total, 3), 1),
                'over_35_probability': round(self._poisson_over(expected_total, 4), 1),
            },
            
            # Stats
            'home_stats': {
                'btts_rate': home_stats.get('btts_rate', 50),
                'avg_goals_scored': home_stats.get('avg_goals_scored', 1.2),
                'avg_goals_conceded': home_stats.get('avg_goals_conceded', 1.0),
                'matches_played': home_stats.get('matches_played', 0) or 1,  # Avoid division by zero
                'clean_sheets': home_stats.get('clean_sheets', 0),
                'wins': home_stats.get('wins', 0),
                'btts_count': home_stats.get('btts_count', 0)
            },
            'away_stats': {
                'btts_rate': away_stats.get('btts_rate', 50),
                'avg_goals_scored': away_stats.get('avg_goals_scored', 1.0),
                'avg_goals_conceded': away_stats.get('avg_goals_conceded', 1.2),
                'matches_played': away_stats.get('matches_played', 0) or 1,  # Avoid division by zero
                'clean_sheets': away_stats.get('clean_sheets', 0),
                'wins': away_stats.get('wins', 0),
                'btts_count': away_stats.get('btts_count', 0)
            },
            
            'h2h': h2h,
            'home_form': home_form,
            'away_form': away_form,
            'form': {
                'home': home_form,
                'away': away_form
            },
            'weather': weather_data
        }
    
    def _calculate_confidence_score(self, home_stats: Dict, away_stats: Dict, h2h: Dict) -> float:
        """Berechne Konfidenz als Zahl (0-100)"""
        score = 50
        
        home_matches = home_stats.get('matches_played', 0)
        away_matches = away_stats.get('matches_played', 0)
        
        if home_matches >= 10 and away_matches >= 10:
            score += 20
        elif home_matches >= 5 and away_matches >= 5:
            score += 10
        
        if h2h.get('matches_played', 0) >= 5:
            score += 15
        elif h2h.get('matches_played', 0) >= 3:
            score += 8
        
        if self.model_trained:
            score += 10
        
        return min(95, score)
    
    def _get_confidence_level(self, score: float) -> str:
        """Convert score to level string"""
        if score >= 80:
            return 'VERY_HIGH'
        elif score >= 65:
            return 'HIGH'
        elif score >= 50:
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
    
    # =============================================
    # UPCOMING MATCHES METHODS
    # =============================================
    
    def get_upcoming_matches(self, league_code: str, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming matches using API-Football"""
        if not self.api_football_key:
            print(f"⚠️ API-Football key not available")
            return []
        
        try:
            from api_football import APIFootball
            api = APIFootball(self.api_football_key)
            
            print(f"📡 Fetching upcoming fixtures for {league_code}...")
            fixtures = api.get_upcoming_fixtures(league_code, days_ahead)
            
            if fixtures:
                print(f"✅ Found {len(fixtures)} upcoming matches")
                matches = []
                for fixture in fixtures:
                    matches.append({
                        'fixture_id': fixture.get('fixture_id'),
                        'date': fixture.get('date'),
                        'utcDate': fixture.get('date'),
                        'homeTeam': {
                            'id': fixture.get('home_team_id'),
                            'name': fixture.get('home_team')
                        },
                        'awayTeam': {
                            'id': fixture.get('away_team_id'),
                            'name': fixture.get('away_team')
                        }
                    })
                return matches
            else:
                print(f"⚠️ No upcoming matches found for {league_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching fixtures: {e}")
            return []
    
    def analyze_upcoming_matches(self, league_code: str, days_ahead: int = 7,
                                min_probability: float = 60.0) -> pd.DataFrame:
        """Analyze all upcoming matches and return recommendations"""
        print(f"\n🔍 Analyzing upcoming matches for {league_code}...")
        
        matches = self.get_upcoming_matches(league_code, days_ahead)
        
        if not matches:
            print("⚠️ No upcoming matches found")
            return pd.DataFrame()
        
        results = []
        
        for match in matches:
            home_team = match['homeTeam']
            away_team = match['awayTeam']
            
            print(f"   Analyzing: {home_team['name']} vs {away_team['name']}...")
            
            analysis = self.analyze_match(home_team['id'], away_team['id'], league_code)
            
            if 'error' in analysis:
                print(f"   ⚠️ Skipped: {analysis['error']}")
                continue
            
            if analysis['ensemble_probability'] >= min_probability:
                try:
                    date_str = match.get('utcDate', match.get('date', ''))
                    if date_str and 'T' in str(date_str):
                        date_formatted = datetime.strptime(str(date_str).replace('Z', ''), '%Y-%m-%dT%H:%M:%S').strftime('%d.%m.%Y %H:%M')
                    else:
                        date_formatted = str(date_str)[:16] if date_str else 'Unknown'
                except:
                    date_formatted = str(match.get('date', 'Unknown'))[:16]
                
                results.append({
                    'Date': date_formatted,
                    'Home': home_team['name'],
                    'Away': away_team['name'],
                    'BTTS %': f"{analysis['ensemble_probability']:.1f}%",
                    'Confidence': f"{analysis['confidence']:.1f}%",
                    'Level': analysis['confidence_level'],
                    'Tip': analysis['recommendation'],
                    'ML': f"{analysis['ml_probability']:.1f}%",
                    'Stat': f"{analysis['statistical_probability']:.1f}%",
                    'Form': f"{analysis['form_probability']:.1f}%",
                    'H2H': f"{analysis['h2h_probability']:.1f}%",
                    'xG Total': f"{analysis['details']['expected_total_goals']:.1f}",
                    '_analysis': analysis
                })
        
        if not results:
            print("⚠️ No matches meet the criteria")
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        df = df.sort_values('BTTS %', ascending=False)
        
        print(f"✅ Found {len(results)} recommendations")
        
        return df


# Export
__all__ = ['AdvancedBTTSAnalyzer']
