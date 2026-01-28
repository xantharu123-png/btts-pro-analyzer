"""
Advanced BTTS Analyzer V3.0 - MIT VOLLSTÄNDIGEM ML ENSEMBLE
============================================================

🚀 V3.0 ÄNDERUNGEN:
- 20 Features statt 6
- ML Ensemble (XGBoost + RandomForest + GradientBoosting + NeuralNetwork)
- Verletzungen & Sperren
- Müdigkeit/Rotation
- Motivation (Tabellensituation)
- Trainerwechsel (New Manager Bounce)

Mit Supabase/PostgreSQL Support
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
import sqlite3
import os
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pickle
from pathlib import Path
import math
import requests

# XGBoost (optional)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False

from data_engine import DataEngine


def _get_supabase_url() -> Optional[str]:
    """Get Supabase URL from Streamlit secrets or environment"""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'SUPABASE_DB_URL' in st.secrets:
            return st.secrets['SUPABASE_DB_URL']
    except:
        pass
    return os.environ.get('SUPABASE_DB_URL')


def _get_db_connection(db_path: str = "btts_data.db"):
    """Get database connection (PostgreSQL or SQLite)"""
    supabase_url = _get_supabase_url()
    
    if supabase_url:
        try:
            import psycopg2
            conn = psycopg2.connect(supabase_url)
            return conn, True
        except ImportError:
            print("⚠️ psycopg2 not installed")
        except Exception as e:
            print(f"⚠️ PostgreSQL connection error: {e}")
    
    return sqlite3.connect(db_path), False


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


# =============================================================================
# STATISTISCHE MODELLE
# =============================================================================

class DixonColesModel:
    """
    Dixon-Coles Correction for Poisson Distribution
    V3.0: Standardisiert auf rho = -0.10
    """
    def __init__(self, rho: float = -0.10):
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
        return (math.exp(-lambda_val) * (lambda_val ** k)) / math.factorial(k)
    
    def joint_probability(self, home_goals: int, away_goals: int,
                          home_lambda: float, away_lambda: float) -> float:
        return (self.poisson_prob(home_goals, home_lambda) *
                self.poisson_prob(away_goals, away_lambda) *
                self.tau(home_goals, away_goals))


class BivariatePoissonModel:
    """Bivariate Poisson für korrelierte Tore"""
    def __init__(self, covariance: float = 0.10):
        self.covariance = covariance
    
    def joint_probability(self, home_goals: int, away_goals: int,
                          home_lambda: float, away_lambda: float) -> float:
        l1 = max(0.01, home_lambda - self.covariance)
        l2 = max(0.01, away_lambda - self.covariance)
        l3 = max(0.01, self.covariance)
        
        min_goals = min(home_goals, away_goals)
        prob = 0.0
        
        for k in range(min_goals + 1):
            p1 = self._poisson(home_goals - k, l1)
            p2 = self._poisson(away_goals - k, l2)
            p3 = self._poisson(k, l3)
            prob += p1 * p2 * p3
        
        return max(0.001, prob)
    
    def _poisson(self, k: int, lam: float) -> float:
        if k < 0:
            return 0.0
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return (math.exp(-lam) * (lam ** k)) / math.factorial(k)


# =============================================================================
# V3.0: INJURY TRACKER
# =============================================================================

class InjuryTracker:
    """Verletzungen & Sperren - NEU in V3.0"""
    
    STAR_PLAYERS = {
        'E. Haaland': 0.35, 'M. Salah': 0.30, 'K. De Bruyne': 0.28,
        'B. Saka': 0.25, 'H. Kane': 0.35, 'J. Musiala': 0.28,
        'F. Wirtz': 0.30, 'J. Bellingham': 0.30, 'Vinicius Jr': 0.32,
        'R. Lewandowski': 0.30, 'K. Mbappe': 0.35, 'L. Martinez': 0.28,
    }
    
    POSITION_IMPORTANCE = {
        'Goalkeeper': 0.15, 'Defender': 0.10, 'Midfielder': 0.12, 'Attacker': 0.18,
    }
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key} if api_key else {}
        self.cache = {}
    
    def get_team_injuries(self, team_id: int) -> Dict:
        if not self.api_key or not team_id:
            return {'total_out': 0, 'impact_score': 0.0, 'key_players_out': []}
        
        cache_key = f"injuries_{team_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            response = requests.get(
                f"{self.base_url}/injuries",
                headers=self.headers,
                params={'team': team_id, 'season': 2025},
                timeout=10
            )
            
            if response.status_code == 200:
                injuries = response.json().get('response', [])
                result = self._analyze(injuries)
                self.cache[cache_key] = result
                return result
        except:
            pass
        
        return {'total_out': 0, 'impact_score': 0.0, 'key_players_out': []}
    
    def _analyze(self, injuries: List) -> Dict:
        impact = 0.0
        key_out = []
        
        for inj in injuries:
            name = inj.get('player', {}).get('name', '')
            pos = inj.get('player', {}).get('type', 'Midfielder')
            
            if name in self.STAR_PLAYERS:
                impact += self.STAR_PLAYERS[name]
                key_out.append(name)
            else:
                impact += self.POSITION_IMPORTANCE.get(pos, 0.10)
        
        return {'total_out': len(injuries), 'impact_score': min(impact, 0.60), 'key_players_out': key_out}


# =============================================================================
# V3.0: FATIGUE ANALYZER
# =============================================================================

class FatigueAnalyzer:
    """Müdigkeit/Rotation - NEU in V3.0"""
    
    REST_IMPACT = {1: 0.85, 2: 0.92, 3: 0.97, 4: 1.00}
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key} if api_key else {}
    
    def analyze(self, team_id: int, fixture_date: datetime = None) -> Dict:
        if not self.api_key or not team_id:
            return {'fatigue_factor': 1.0, 'days_rest': 4, 'games_14d': 2}
        
        fixture_date = fixture_date or datetime.now()
        
        try:
            from_date = (fixture_date - timedelta(days=14)).strftime('%Y-%m-%d')
            to_date = fixture_date.strftime('%Y-%m-%d')
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'team': team_id, 'from': from_date, 'to': to_date, 'status': 'FT'},
                timeout=10
            )
            
            if response.status_code == 200:
                fixtures = response.json().get('response', [])
                return self._calc_fatigue(fixtures, fixture_date)
        except:
            pass
        
        return {'fatigue_factor': 1.0, 'days_rest': 4, 'games_14d': 2}
    
    def _calc_fatigue(self, fixtures: List, target: datetime) -> Dict:
        if not fixtures:
            return {'fatigue_factor': 1.0, 'days_rest': 7, 'games_14d': 0}
        
        last_date = None
        for fix in fixtures:
            try:
                d = datetime.fromisoformat(fix['fixture']['date'].replace('Z', '+00:00')).replace(tzinfo=None)
                if d.date() < target.date():
                    if last_date is None or d > last_date:
                        last_date = d
            except:
                pass
        
        days = (target - last_date).days if last_date else 7
        factor = self.REST_IMPACT.get(min(days, 4), 1.0)
        
        if len(fixtures) >= 4:
            factor *= 0.95
        
        return {'fatigue_factor': round(factor, 3), 'days_rest': days, 'games_14d': len(fixtures)}


# =============================================================================
# V3.0: MOTIVATION ANALYZER
# =============================================================================

class MotivationAnalyzer:
    """Motivation basierend auf Tabelle - NEU in V3.0"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key} if api_key else {}
        self.cache = {}
    
    def get_motivation(self, team_id: int, league_id: int) -> Dict:
        if not self.api_key or not league_id:
            return {'motivation_score': 1.0, 'situation': 'MID_TABLE', 'position': 10}
        
        standings = self._get_standings(league_id)
        if not standings:
            return {'motivation_score': 1.0, 'situation': 'MID_TABLE', 'position': 10}
        
        for team in standings:
            if team.get('team', {}).get('id') == team_id:
                pos = team.get('rank', 10)
                total = len(standings)
                
                if pos <= 1:
                    return {'motivation_score': 1.20, 'situation': 'TITLE_RACE', 'position': pos}
                elif pos <= 6:
                    return {'motivation_score': 1.12, 'situation': 'EUROPA_RACE', 'position': pos}
                elif pos >= total - 2:
                    return {'motivation_score': 1.25, 'situation': 'RELEGATION', 'position': pos}
                else:
                    return {'motivation_score': 1.0, 'situation': 'MID_TABLE', 'position': pos}
        
        return {'motivation_score': 1.0, 'situation': 'MID_TABLE', 'position': 10}
    
    def _get_standings(self, league_id: int) -> List:
        if league_id in self.cache:
            return self.cache[league_id]
        
        try:
            response = requests.get(
                f"{self.base_url}/standings",
                headers=self.headers,
                params={'league': league_id, 'season': 2025},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json().get('response', [])
                if data:
                    table = data[0].get('league', {}).get('standings', [[]])[0]
                    self.cache[league_id] = table
                    return table
        except:
            pass
        
        return []


# =============================================================================
# V3.0: MANAGER CHANGE TRACKER
# =============================================================================

class ManagerChangeTracker:
    """New Manager Bounce - NEU in V3.0"""
    
    CHANGES = {}  # team_id -> {'date': datetime, 'manager': str}
    
    def get_effect(self, team_id: int, fixture_date: datetime = None) -> Dict:
        fixture_date = fixture_date or datetime.now()
        
        if team_id in self.CHANGES:
            days = (fixture_date - self.CHANGES[team_id]['date']).days
            games = max(1, days // 4)
            
            if games <= 3:
                boost = 1.15
            elif games <= 6:
                boost = 1.08
            elif games <= 10:
                boost = 1.03
            else:
                boost = 1.0
            
            return {'has_new_manager': True, 'boost_factor': boost, 'games_since': games}
        
        return {'has_new_manager': False, 'boost_factor': 1.0, 'games_since': None}
    
    def register(self, team_id: int, manager: str, date: datetime):
        self.CHANGES[team_id] = {'date': date, 'manager': manager}


# =============================================================================
# V3.0: ML ENSEMBLE (XGBoost + RandomForest + GradientBoosting + Neural Network)
# =============================================================================

class MLEnsembleV3:
    """
    ML Ensemble V3.0 mit 4 Modellen
    
    GEWICHTE:
    - XGBoost: 35%
    - RandomForest: 30%
    - GradientBoosting: 20%
    - Neural Network: 15%
    
    FEATURES: 20 statt 6!
    """
    
    def __init__(self, model_path: str = 'models/'):
        self.model_path = model_path
        self.models = {}
        self.weights = {'xgboost': 0.35, 'random_forest': 0.30, 'gradient_boosting': 0.20, 'neural_network': 0.15}
        self.scaler = StandardScaler()
        self.is_trained = False
        self.last_trained = None
        
        self._init_models()
    
    def _init_models(self):
        if XGBOOST_AVAILABLE:
            self.models['xgboost'] = xgb.XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                random_state=42, use_label_encoder=False, eval_metric='logloss'
            )
        
        self.models['random_forest'] = RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_split=5, random_state=42
        )
        
        self.models['gradient_boosting'] = GradientBoostingClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.1, random_state=42
        )
        
        self.models['neural_network'] = MLPClassifier(
            hidden_layer_sizes=(64, 32), activation='relu', max_iter=500,
            random_state=42, early_stopping=True
        )
    
    def train(self, X: np.ndarray, y: np.ndarray):
        """Train all models"""
        if len(X) < 100:
            print("⚠️ Nicht genug Daten für Training")
            return False
        
        print(f"🔄 Training ML Ensemble V3.0 mit {len(X)} Samples und {X.shape[1]} Features...")
        
        X_scaled = self.scaler.fit_transform(X)
        
        for name, model in self.models.items():
            print(f"   Training {name}...", end=" ")
            try:
                model.fit(X_scaled, y)
                scores = cross_val_score(model, X_scaled, y, cv=min(5, len(X)//20))
                print(f"✅ CV: {scores.mean():.1%}")
            except Exception as e:
                print(f"⚠️ Error: {e}")
        
        self.is_trained = True
        self.last_trained = datetime.now()
        self.save()
        print(f"✅ Training complete! Last trained: {self.last_trained}")
        return True
    
    def predict_proba(self, X: np.ndarray) -> float:
        """Ensemble prediction for BTTS"""
        if not self.is_trained:
            return 0.55
        
        X_2d = X.reshape(1, -1) if X.ndim == 1 else X
        X_scaled = self.scaler.transform(X_2d)
        
        predictions = []
        total_weight = 0
        
        for name, model in self.models.items():
            try:
                proba = model.predict_proba(X_scaled)[0]
                btts_prob = proba[1] if len(proba) > 1 else proba[0]
                weight = self.weights.get(name, 0.25)
                predictions.append(btts_prob * weight)
                total_weight += weight
            except:
                pass
        
        if predictions and total_weight > 0:
            return sum(predictions) / total_weight
        
        return 0.55
    
    def save(self):
        if not self.is_trained:
            return
        
        os.makedirs(self.model_path, exist_ok=True)
        
        try:
            for name, model in self.models.items():
                with open(os.path.join(self.model_path, f'{name}.pkl'), 'wb') as f:
                    pickle.dump(model, f)
            
            with open(os.path.join(self.model_path, 'scaler.pkl'), 'wb') as f:
                pickle.dump(self.scaler, f)
            
            with open(os.path.join(self.model_path, 'meta.pkl'), 'wb') as f:
                pickle.dump({'last_trained': self.last_trained}, f)
            
            print(f"✅ Models saved to {self.model_path}")
        except Exception as e:
            print(f"⚠️ Save error: {e}")
    
    def load(self) -> bool:
        if not os.path.exists(self.model_path):
            return False
        
        try:
            for name in list(self.models.keys()):
                path = os.path.join(self.model_path, f'{name}.pkl')
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        self.models[name] = pickle.load(f)
            
            scaler_path = os.path.join(self.model_path, 'scaler.pkl')
            if os.path.exists(scaler_path):
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
            
            meta_path = os.path.join(self.model_path, 'meta.pkl')
            if os.path.exists(meta_path):
                with open(meta_path, 'rb') as f:
                    meta = pickle.load(f)
                    self.last_trained = meta.get('last_trained')
            
            self.is_trained = True
            print(f"✅ ML Models V3.0 loaded! Last trained: {self.last_trained}")
            return True
        except Exception as e:
            print(f"⚠️ Load error: {e}")
            return False


# =============================================================================
# HAUPTKLASSE: ADVANCED BTTS ANALYZER V3.0
# =============================================================================

class AdvancedBTTSAnalyzer:
    """
    Pro-level BTTS Analyzer V3.0
    
    KOMBINATION:
    - Statistische Modelle (Dixon-Coles, Bivariate Poisson)
    - ML Ensemble V3.0 (XGBoost, RandomForest, GradientBoosting, Neural Network)
    - Verletzungen & Sperren
    - Müdigkeit & Rotation
    - Motivation (Tabellensituation)
    - Trainerwechsel (New Manager Bounce)
    """
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "btts_data.db", 
                 weather_api_key: Optional[str] = None, api_football_key: Optional[str] = None):
        
        self.engine = DataEngine(api_football_key or api_key, db_path)
        self.db_path = db_path
        self.api_football_key = api_football_key or api_key
        
        # Statistische Modelle
        self.dixon_coles = DixonColesModel(rho=-0.10)
        self.bivariate_poisson = BivariatePoissonModel(covariance=0.10)
        
        # V3.0 Komponenten
        self.injury_tracker = InjuryTracker(self.api_football_key)
        self.fatigue_analyzer = FatigueAnalyzer(self.api_football_key)
        self.motivation_analyzer = MotivationAnalyzer(self.api_football_key)
        self.manager_tracker = ManagerChangeTracker()
        
        # ML Ensemble V3.0
        self.ml_model = MLEnsembleV3('models/')
        self.scaler = self.ml_model.scaler
        self.model_trained = False
        
        # Ensemble Weights
        self.weights = {
            'ml_model': 0.35,
            'statistical': 0.30,
            'form': 0.20,
            'h2h': 0.15
        }
        
        # CLV Tracker
        if CLV_AVAILABLE:
            try:
                self.clv_tracker = CLVTracker(db_path=db_path.replace('.db', '_clv.db'))
            except:
                self.clv_tracker = None
        else:
            self.clv_tracker = None
        
        # Weather
        if WEATHER_AVAILABLE and weather_api_key:
            self.weather = WeatherAnalyzer(weather_api_key)
        else:
            self.weather = None
        
        # Load or train
        self.load_or_train_model()
        
        print("=" * 60)
        print("🚀 BTTS Pro Analyzer V3.0 initialized!")
        print(f"   ML Ensemble: {'✅' if self.model_trained else '⚠️ Not trained'}")
        print(f"   XGBoost: {'✅' if XGBOOST_AVAILABLE else '❌'}")
        print(f"   Features: 20 (V3.0)")
        print(f"   Injuries/Fatigue/Motivation: {'✅' if self.api_football_key else '❌'}")
        print("=" * 60)
    
    def prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """V3.0: 20 Features statt 6"""
        conn, is_postgres = _get_db_connection(self.db_path)
        
        query = '''
            SELECT home_team, away_team, home_goals, away_goals, btts, league_code
            FROM matches
            WHERE btts IS NOT NULL AND home_goals IS NOT NULL AND away_goals IS NOT NULL
        '''
        
        try:
            df = pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"⚠️ SQL error: {e}")
            df = pd.DataFrame()
        finally:
            conn.close()
        
        if df.empty or len(df) < 100:
            print(f"⚠️ Not enough training data ({len(df) if not df.empty else 0} matches)")
            return np.array([]), np.array([])
        
        print(f"📊 Processing {len(df)} matches for V3.0 training...")
        
        # Build team stats
        team_stats = {}
        for team in set(df['home_team'].tolist() + df['away_team'].tolist()):
            home_matches = df[df['home_team'] == team]
            away_matches = df[df['away_team'] == team]
            
            team_stats[team] = {
                'goals_avg': (home_matches['home_goals'].mean() if len(home_matches) > 0 else 1.2 +
                             away_matches['away_goals'].mean() if len(away_matches) > 0 else 1.1) / 2,
                'conceded_avg': (home_matches['away_goals'].mean() if len(home_matches) > 0 else 1.2 +
                                away_matches['home_goals'].mean() if len(away_matches) > 0 else 1.3) / 2,
                'btts_rate': pd.concat([home_matches, away_matches])['btts'].mean() if len(home_matches) + len(away_matches) > 0 else 0.5,
            }
        
        features_list = []
        labels = []
        
        for idx, row in df.iterrows():
            try:
                home = row['home_team']
                away = row['away_team']
                
                hs = team_stats.get(home, {'goals_avg': 1.2, 'conceded_avg': 1.2, 'btts_rate': 0.5})
                aws = team_stats.get(away, {'goals_avg': 1.1, 'conceded_avg': 1.3, 'btts_rate': 0.5})
                
                # V3.0: 20 Features!
                features = [
                    hs['goals_avg'],           # 1. Home goals avg
                    aws['goals_avg'],          # 2. Away goals avg
                    hs['conceded_avg'],        # 3. Home conceded avg
                    aws['conceded_avg'],       # 4. Away conceded avg
                    hs['goals_avg'] * 1.1,     # 5. Home xG (approx)
                    aws['goals_avg'] * 0.9,    # 6. Away xG (approx)
                    1.5,                       # 7. Home form points
                    1.4,                       # 8. Away form points
                    hs['btts_rate'],           # 9. H2H BTTS rate
                    hs['goals_avg'] + aws['goals_avg'],  # 10. H2H avg goals
                    0.0,                       # 11. Home injury impact
                    0.0,                       # 12. Away injury impact
                    1.0,                       # 13. Home fatigue
                    1.0,                       # 14. Away fatigue
                    1.0,                       # 15. Home motivation
                    1.0,                       # 16. Away motivation
                    1.0,                       # 17. Home manager boost
                    1.0,                       # 18. Away manager boost
                    0,                         # 19. Is derby
                    2.75,                      # 20. League avg goals
                ]
                
                features_list.append(features)
                labels.append(int(row['btts']))
            except:
                continue
        
        if len(features_list) < 100:
            print(f"⚠️ Not enough valid data ({len(features_list)} matches)")
            return np.array([]), np.array([])
        
        print(f"✅ Prepared {len(features_list)} samples with 20 features")
        return np.array(features_list), np.array(labels)
    
    def train_model(self):
        """Train V3.0 ML Ensemble"""
        X, y = self.prepare_training_data()
        
        if len(X) < 100:
            print("⚠️ Not enough data to train model")
            return
        
        success = self.ml_model.train(X, y)
        self.model_trained = success
    
    def save_model(self):
        """Save model"""
        self.ml_model.save()
    
    def load_model(self) -> bool:
        """Load model"""
        success = self.ml_model.load()
        self.model_trained = success
        return success
    
    def load_or_train_model(self):
        """Load existing or train new model"""
        if not self.load_model():
            print("📚 Training new V3.0 ML Ensemble...")
            self.train_model()
    
    def build_features(self, home_data: Dict, away_data: Dict, 
                       fixture_date: datetime = None) -> np.ndarray:
        """Build V3.0 feature array"""
        fixture_date = fixture_date or datetime.now()
        
        home_id = home_data.get('team_id')
        away_id = away_data.get('team_id')
        league_id = home_data.get('league_id')
        
        # V3.0 Faktoren
        home_inj = self.injury_tracker.get_team_injuries(home_id)
        away_inj = self.injury_tracker.get_team_injuries(away_id)
        
        home_fat = self.fatigue_analyzer.analyze(home_id, fixture_date)
        away_fat = self.fatigue_analyzer.analyze(away_id, fixture_date)
        
        home_mot = self.motivation_analyzer.get_motivation(home_id, league_id)
        away_mot = self.motivation_analyzer.get_motivation(away_id, league_id)
        
        home_mgr = self.manager_tracker.get_effect(home_id, fixture_date)
        away_mgr = self.manager_tracker.get_effect(away_id, fixture_date)
        
        return np.array([
            home_data.get('goals_avg', 1.3),
            away_data.get('goals_avg', 1.1),
            home_data.get('conceded_avg', 1.1),
            away_data.get('conceded_avg', 1.3),
            home_data.get('xg', 1.4),
            away_data.get('xg', 1.2),
            home_data.get('form_points', 1.5),
            away_data.get('form_points', 1.4),
            home_data.get('h2h_btts_rate', 0.5),
            home_data.get('h2h_avg_goals', 2.5),
            home_inj['impact_score'],
            away_inj['impact_score'],
            home_fat['fatigue_factor'],
            away_fat['fatigue_factor'],
            home_mot['motivation_score'],
            away_mot['motivation_score'],
            home_mgr['boost_factor'],
            away_mgr['boost_factor'],
            1 if home_data.get('is_derby', False) else 0,
            home_data.get('league_avg_goals', 2.75),
        ])
    
    def get_ml_prediction(self, features: np.ndarray) -> float:
        """Get ML prediction"""
        if not self.model_trained:
            return 0.55
        return self.ml_model.predict_proba(features)
    
    def calculate_btts_probability(self, home_lambda: float, away_lambda: float) -> Dict:
        """Calculate BTTS with statistical models"""
        p_home = 1 - math.exp(-home_lambda)
        p_away = 1 - math.exp(-away_lambda)
        
        stat_btts = p_home * p_away
        
        bp_btts = 0.0
        for h in range(1, 8):
            for a in range(1, 8):
                bp_btts += self.bivariate_poisson.joint_probability(h, a, home_lambda, away_lambda)
        
        return {'statistical': stat_btts, 'bivariate': bp_btts}
    
    def analyze_match(self, home_data: Dict, away_data: Dict, 
                      fixture_date: datetime = None) -> Dict:
        """Full V3.0 analysis"""
        fixture_date = fixture_date or datetime.now()
        
        # Lambdas
        home_lambda = home_data.get('xg', home_data.get('goals_avg', 1.3))
        away_lambda = away_data.get('xg', away_data.get('goals_avg', 1.1))
        
        # V3.0 adjustments
        home_id = home_data.get('team_id')
        away_id = away_data.get('team_id')
        
        home_inj = self.injury_tracker.get_team_injuries(home_id)
        away_inj = self.injury_tracker.get_team_injuries(away_id)
        
        home_fat = self.fatigue_analyzer.analyze(home_id, fixture_date)
        away_fat = self.fatigue_analyzer.analyze(away_id, fixture_date)
        
        # Apply
        home_lambda *= (1 - home_inj['impact_score']) * home_fat['fatigue_factor']
        away_lambda *= (1 - away_inj['impact_score']) * away_fat['fatigue_factor']
        
        # Statistical
        stat = self.calculate_btts_probability(home_lambda, away_lambda)
        
        # ML
        features = self.build_features(home_data, away_data, fixture_date)
        ml_prob = self.get_ml_prediction(features)
        
        # Ensemble
        final = (
            self.weights['ml_model'] * ml_prob +
            self.weights['statistical'] * stat['statistical'] +
            self.weights['form'] * stat['bivariate'] +
            self.weights['h2h'] * home_data.get('h2h_btts_rate', 0.5)
        )
        
        final = max(0.15, min(0.85, final))
        
        return {
            'btts_yes': round(final * 100, 1),
            'btts_no': round((1 - final) * 100, 1),
            'confidence': 'HIGH' if abs(final - 0.5) > 0.15 else 'MEDIUM',
            'ml_prediction': round(ml_prob * 100, 1),
            'statistical_prediction': round(stat['statistical'] * 100, 1),
            'home_xg_adjusted': round(home_lambda, 2),
            'away_xg_adjusted': round(away_lambda, 2),
            'v3_adjustments': {
                'home_injury': f"-{home_inj['impact_score']*100:.0f}%",
                'away_injury': f"-{away_inj['impact_score']*100:.0f}%",
                'home_fatigue': f"-{(1-home_fat['fatigue_factor'])*100:.0f}%",
                'away_fatigue': f"-{(1-away_fat['fatigue_factor'])*100:.0f}%",
                'key_players_out': home_inj['key_players_out'] + away_inj['key_players_out'],
            },
            'model_version': '3.0',
            'features_used': 20,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'AdvancedBTTSAnalyzer',
    'DixonColesModel',
    'BivariatePoissonModel', 
    'InjuryTracker',
    'FatigueAnalyzer',
    'MotivationAnalyzer',
    'ManagerChangeTracker',
    'MLEnsembleV3',
]
