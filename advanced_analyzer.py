"""
Advanced BTTS Analyzer with leakage-gated machine learning
Poisson, Dixon-Coles, and bivariate score models
Mit Supabase/PostgreSQL Support
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, brier_score_loss
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
import sqlite3
import os
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pickle
from pathlib import Path
import math
from collections import defaultdict

from config_loader import load_app_config
from data_engine import DataEngine
from season_utils import current_season_start_year_for_id


ML_MODEL_VERSION = 4
ML_FEATURE_NAMES = (
    'home_btts_rate',
    'away_btts_rate',
    'home_goals_scored',
    'away_goals_scored',
    'home_goals_conceded',
    'away_goals_conceded',
)
ML_MIN_TEAM_HISTORY = 5
ML_HISTORY_WINDOW = 20
ML_MIN_TRAINING_ROWS = 200
ML_MIN_VALIDATION_ROWS = 100
ML_MODEL_PATH = Path(__file__).resolve().parent / "ml_model.pkl"


def beta_smoothed_percentage(
    rate_percent: float,
    sample_size: int,
    alpha: float = 1.0,
    beta: float = 1.0,
) -> float:
    """Shrink a binomial rate with an explicit Beta prior."""
    if (
        isinstance(rate_percent, bool)
        or isinstance(sample_size, bool)
        or isinstance(alpha, bool)
        or isinstance(beta, bool)
    ):
        raise ValueError("invalid beta-smoothing inputs")
    try:
        rate = float(rate_percent)
        sample_numeric = float(sample_size)
        prior_alpha = float(alpha)
        prior_beta = float(beta)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid beta-smoothing inputs") from exc
    if (
        not math.isfinite(rate)
        or not 0.0 <= rate <= 100.0
        or not math.isfinite(sample_numeric)
        or not sample_numeric.is_integer()
        or sample_numeric < 0
        or not math.isfinite(prior_alpha)
        or not math.isfinite(prior_beta)
        or prior_alpha <= 0.0
        or prior_beta <= 0.0
    ):
        raise ValueError("invalid beta-smoothing inputs")
    sample = int(sample_numeric)
    successes = rate / 100.0 * sample
    return (successes + prior_alpha) / (
        sample + prior_alpha + prior_beta
    ) * 100.0


def calculate_evidence_score(
    home_venue_matches: int,
    away_venue_matches: int,
    home_form_matches: int,
    away_form_matches: int,
    model_probabilities: List[float],
) -> Dict:
    """Score sample coverage and model agreement; this is not calibration."""
    if not isinstance(model_probabilities, (list, tuple)):
        raise ValueError("model probabilities must be a list or tuple")
    raw_counts = {
        'home_venue_matches': home_venue_matches,
        'away_venue_matches': away_venue_matches,
        'home_form_matches': home_form_matches,
        'away_form_matches': away_form_matches,
    }
    counts = {}
    for name, value in raw_counts.items():
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a non-negative count")
        try:
            count = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a non-negative count") from exc
        if not math.isfinite(count) or count < 0 or not count.is_integer():
            raise ValueError(f"{name} must be a non-negative count")
        counts[name] = int(count)

    probabilities = []
    for value in model_probabilities:
        if isinstance(value, bool):
            raise ValueError("model probabilities must be finite percentages")
        try:
            probability = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("model probabilities must be finite percentages") from exc
        if not math.isfinite(probability) or not 0.0 <= probability <= 100.0:
            raise ValueError("model probabilities must be finite percentages")
        probabilities.append(probability)
    if len(probabilities) < 2:
        raise ValueError("at least two model probabilities are required")

    coverage = {
        'home_venue': min(counts['home_venue_matches'] / 12.0, 1.0),
        'away_venue': min(counts['away_venue_matches'] / 12.0, 1.0),
        'home_form': min(counts['home_form_matches'] / 5.0, 1.0),
        'away_form': min(counts['away_form_matches'] / 5.0, 1.0),
    }
    agreement = max(0.0, 1.0 - float(np.std(probabilities)) / 25.0)
    contributions = {
        'home_venue': 30.0 * coverage['home_venue'],
        'away_venue': 30.0 * coverage['away_venue'],
        'home_form': 10.0 * coverage['home_form'],
        'away_form': 10.0 * coverage['away_form'],
        'model_agreement': 20.0 * agreement,
    }
    score = max(0.0, min(100.0, sum(contributions.values())))
    return {
        'score': score,
        'agreement_score': agreement * 100.0,
        'contributions': contributions,
        'samples': {name: int(value) for name, value in counts.items()},
    }


def build_prematch_training_rows(
    matches: pd.DataFrame,
    min_team_history: int = ML_MIN_TEAM_HISTORY,
    history_window: int = ML_HISTORY_WINDOW,
    *,
    return_dates: bool = False,
):
    """Convert chronological results into leakage-free pre-match rows."""
    if (
        isinstance(min_team_history, bool)
        or isinstance(history_window, bool)
        or not isinstance(min_team_history, int)
        or not isinstance(history_window, int)
        or min_team_history < 1
        or history_window < min_team_history
    ):
        raise ValueError("history settings must be positive coherent integers")
    matches = matches.copy()
    if 'date' not in matches.columns:
        empty = (np.array([]), np.array([]), np.array([], dtype='datetime64[D]'))
        return empty if return_dates else empty[:2]
    matches['_model_date'] = pd.to_datetime(
        matches['date'], errors='coerce', utc=True
    ).dt.floor('D')
    matches = matches.dropna(subset=['_model_date'])
    sort_columns = ['_model_date'] + (["id"] if 'id' in matches.columns else [])
    matches = matches.sort_values(sort_columns, kind='mergesort')
    team_history = defaultdict(list)
    features_list = []
    labels = []
    feature_dates = []

    def history_features(history: List[Tuple[float, float, int]]) -> Tuple[float, float, float]:
        sample = history[-history_window:]
        return (
            float(np.mean([entry[2] for entry in sample])) * 100.0,
            float(np.mean([entry[0] for entry in sample])),
            float(np.mean([entry[1] for entry in sample])),
        )

    for model_date, day_matches in matches.groupby('_model_date', sort=False):
        pending_updates = []
        for _, row in day_matches.iterrows():
            raw_home_team_id = row.get('home_team_id')
            raw_away_team_id = row.get('away_team_id')
            raw_home_goals = row.get('home_goals')
            raw_away_goals = row.get('away_goals')
            raw_label = row.get('btts')
            if any(
                isinstance(value, (bool, np.bool_))
                for value in (
                    raw_home_team_id,
                    raw_away_team_id,
                    raw_home_goals,
                    raw_away_goals,
                    raw_label,
                )
            ):
                continue
            try:
                raw_league_code = row.get('league_code')
                league_code = (
                    raw_league_code.strip()
                    if isinstance(raw_league_code, str)
                    else ''
                )
                home_team_numeric = float(raw_home_team_id)
                away_team_numeric = float(raw_away_team_id)
                home_goals = float(raw_home_goals)
                away_goals = float(raw_away_goals)
                label_numeric = float(raw_label)
            except (TypeError, ValueError, OverflowError):
                continue
            if (
                not league_code
                or not math.isfinite(home_team_numeric)
                or not math.isfinite(away_team_numeric)
                or not home_team_numeric.is_integer()
                or not away_team_numeric.is_integer()
                or not math.isfinite(home_goals)
                or not math.isfinite(away_goals)
                or not math.isfinite(label_numeric)
                or home_goals < 0
                or away_goals < 0
                or home_goals > 30
                or away_goals > 30
                or not home_goals.is_integer()
                or not away_goals.is_integer()
                or not label_numeric.is_integer()
                or label_numeric not in {0.0, 1.0}
            ):
                continue
            home_team_id = int(home_team_numeric)
            away_team_id = int(away_team_numeric)
            label = int(label_numeric)
            if home_team_id <= 0 or away_team_id <= 0 or home_team_id == away_team_id:
                continue

            home_key = (league_code, home_team_id)
            away_key = (league_code, away_team_id)
            home_history = team_history[home_key]
            away_history = team_history[away_key]
            if (
                len(home_history) >= min_team_history
                and len(away_history) >= min_team_history
            ):
                home_btts, home_scored, home_conceded = history_features(home_history)
                away_btts, away_scored, away_conceded = history_features(away_history)
                features_list.append([
                    home_btts,
                    away_btts,
                    home_scored,
                    away_scored,
                    home_conceded,
                    away_conceded,
                ])
                labels.append(label)
                feature_dates.append(model_date.to_datetime64())
            pending_updates.append((
                home_key,
                away_key,
                home_goals,
                away_goals,
                label,
            ))

        # Same-day results never enter another fixture's pre-match features.
        for home_key, away_key, home_goals, away_goals, label in pending_updates:
            team_history[home_key].append((home_goals, away_goals, label))
            team_history[away_key].append((away_goals, home_goals, label))

    result = (
        np.asarray(features_list, dtype=float),
        np.asarray(labels, dtype=int),
        np.asarray(feature_dates, dtype='datetime64[D]'),
    )
    return result if return_dates else result[:2]


def _get_supabase_url() -> Optional[str]:
    """Get Supabase URL from Streamlit secrets or environment"""
    st_module = None
    try:
        import streamlit as st
        st_module = st
    except Exception:
        pass

    return load_app_config(st_module).supabase_db_url


def _get_db_connection(db_path: str = "btts_data.db"):
    """Get database connection (PostgreSQL or SQLite)"""
    supabase_url = _get_supabase_url()
    
    if supabase_url:
        try:
            import psycopg2
            conn = psycopg2.connect(supabase_url)
            return conn, True  # (connection, is_postgres)
        except ImportError:
            print("WARNING: psycopg2 not installed")
        except Exception as e:
            print(f"WARNING: PostgreSQL connection error: {e}")
    
    return sqlite3.connect(db_path), False  # (connection, is_postgres)


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
    """
    Dixon-Coles Correction for Poisson Distribution
    
    Korrigiert die Unabhängigkeits-Annahme für niedrige Spielstände (0-0, 1-0, 0-1, 1-1)
    ``rho`` is a configured low-score dependence parameter.
    """
    def __init__(self, rho: float = -0.05):
        if not math.isfinite(rho) or not -0.3 <= rho <= 0.3:
            raise ValueError("rho must be finite and between -0.3 and 0.3")
        self.rho = rho
    
    def tau(self, home_goals: int, away_goals: int,
            lambda_home: float, lambda_away: float) -> float:
        """Return the standard Dixon-Coles low-score adjustment."""
        if home_goals == 0 and away_goals == 0:
            return 1 - lambda_home * lambda_away * self.rho
        elif home_goals == 1 and away_goals == 0:
            return 1 + lambda_away * self.rho
        elif home_goals == 0 and away_goals == 1:
            return 1 + lambda_home * self.rho
        elif home_goals == 1 and away_goals == 1:
            return 1 - self.rho
        return 1.0
    
    def poisson_prob(self, k: int, lambda_val: float) -> float:
        if lambda_val <= 0:
            return 1.0 if k == 0 else 0.0
        return (lambda_val ** k) * math.exp(-lambda_val) / math.factorial(k)
    
    def calculate_btts_probability(self, lambda_home: float, lambda_away: float) -> float:
        """Calculate BTTS from a normalized Dixon-Coles score matrix."""
        if lambda_home < 0 or lambda_away < 0:
            raise ValueError("Poisson rates cannot be negative")

        total_mass = 0.0
        btts_mass = 0.0
        for home_goals in range(13):
            for away_goals in range(13):
                probability = (
                    self.poisson_prob(home_goals, lambda_home)
                    * self.poisson_prob(away_goals, lambda_away)
                    * self.tau(
                        home_goals,
                        away_goals,
                        lambda_home,
                        lambda_away,
                    )
                )
                probability = max(0.0, probability)
                total_mass += probability
                if home_goals > 0 and away_goals > 0:
                    btts_mass += probability

        return btts_mass / total_mass * 100.0 if total_mass > 0 else 0.0


class BivariatePoissonModel:
    """Exact common-component bivariate Poisson score model."""
    
    def __init__(self, covariance: float = 0.10):
        """
        Args:
            covariance: Kovarianz zwischen Home und Away Toren
                       Höher = mehr "offene" Spiele mit vielen Toren für beide
        """
        if not math.isfinite(covariance) or covariance < 0:
            raise ValueError("covariance must be finite and non-negative")
        self.cov = covariance
    
    def joint_probability(self, home_goals: int, away_goals: int,
                          lambda_home: float, lambda_away: float) -> float:
        if lambda_home < 0 or lambda_away < 0:
            raise ValueError("Poisson rates cannot be negative")
        common = min(self.cov, lambda_home, lambda_away)
        home_only = lambda_home - common
        away_only = lambda_away - common
        probability = 0.0
        for shared_goals in range(min(home_goals, away_goals) + 1):
            probability += (
                home_only ** (home_goals - shared_goals)
                * away_only ** (away_goals - shared_goals)
                * common ** shared_goals
                / (
                    math.factorial(home_goals - shared_goals)
                    * math.factorial(away_goals - shared_goals)
                    * math.factorial(shared_goals)
                )
            )
        return math.exp(-(home_only + away_only + common)) * probability

    def calculate_btts_probability(self, lambda_home: float, lambda_away: float) -> float:
        """Calculate BTTS from the normalized exact joint score matrix."""
        total_mass = 0.0
        btts_mass = 0.0
        for home_goals in range(13):
            for away_goals in range(13):
                probability = self.joint_probability(
                    home_goals,
                    away_goals,
                    lambda_home,
                    lambda_away,
                )
                total_mass += probability
                if home_goals > 0 and away_goals > 0:
                    btts_mass += probability
        return btts_mass / total_mass * 100.0 if total_mass > 0 else 0.0


class AdvancedBTTSAnalyzer:
    """
    Pro-level BTTS Analyzer mit korrigierter Poisson-Logik
    """
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "btts_data.db", 
                 weather_api_key: Optional[str] = None, api_football_key: Optional[str] = None):
        self.engine = DataEngine(api_football_key or api_key, db_path)  # FIX: Use api_football_key!
        self.db_path = db_path
        self.api_football_key = api_football_key
        self._team_stats_cache = {}
        self._form_cache = {}
        self._h2h_cache = {}
        # Dixon-Coles Model (korrigiert niedrige Spielstände)
        self.dixon_coles = DixonColesModel(rho=-0.05)
        
        # Bivariate Poisson Model (modelliert Tor-Korrelation)
        self.bivariate_poisson = BivariatePoissonModel(covariance=0.10)
        
        # CLV Tracker
        if CLV_AVAILABLE:
            try:
                self.clv_tracker = CLVTracker(db_path=db_path.replace('.db', '_clv.db'))
                print("CLV tracking enabled")
            except Exception as e:
                self.clv_tracker = None
                print(f"WARNING: CLV tracker error: {e}")
        else:
            self.clv_tracker = None

        
        # Weather Analyzer
        if WEATHER_AVAILABLE and weather_api_key:
            self.weather = WeatherAnalyzer(weather_api_key)
            print("Weather analysis enabled")
        else:
            self.weather = None
        
        # ML Models
        self.ml_model = None
        self.scaler = StandardScaler()
        self.model_trained = False
        self.model_metrics = {}
        
        # Statistical fallback weights. A validated ML model is used directly;
        # it is not mixed with an ensemble that was never validated as a unit.
        self.weights = {
            'statistical': 0.60,
            'poisson': 0.40,
        }
        
        # Load or train model
        self.load_or_train_model()
    
    def prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build chronological features using only information available pre-match."""
        conn, is_postgres = _get_db_connection(self.db_path)

        query = '''
            SELECT
                id,
                date,
                home_team_id,
                away_team_id,
                home_goals,
                away_goals,
                btts,
                league_code
            FROM matches
            WHERE btts IS NOT NULL
                AND home_goals IS NOT NULL
                AND away_goals IS NOT NULL
                AND home_team_id IS NOT NULL
                AND away_team_id IS NOT NULL
            ORDER BY date ASC, id ASC
        '''

        try:
            df = pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"WARNING: SQL error: {e}")
            df = pd.DataFrame()
        finally:
            conn.close()

        if df.empty or len(df) < 50:
            print(f"WARNING: Not enough training data ({len(df) if not df.empty else 0} matches)")
            return np.array([]), np.array([]), np.array([], dtype='datetime64[D]')

        X, y, dates = build_prematch_training_rows(df, return_dates=True)
        if len(X) < 50:
            print(f"WARNING: Not enough valid training data ({len(X)} matches)")
            return np.array([]), np.array([]), np.array([], dtype='datetime64[D]')
        return X, y, dates
    
    def train_model(self) -> bool:
        """Train and gate the model with expanding-window validation."""
        X, y, dates = self.prepare_training_data()

        if len(X) < ML_MIN_TRAINING_ROWS or len(np.unique(y)) < 2:
            print("WARNING: Not enough data to train model; using statistical only")
            return False

        print(f"Training on {len(X)} matches...")

        unique_dates = np.unique(dates)
        if len(unique_dates) < 12:
            print("WARNING: Too few distinct match dates; using statistical only")
            return False
        splitter = TimeSeriesSplit(n_splits=5)
        validation_probabilities = []
        validation_labels = []
        baseline_probabilities = []
        fold_brier_scores = []
        fold_baseline_scores = []

        for train_dates, validation_dates in splitter.split(unique_dates):
            train_index = np.flatnonzero(np.isin(dates, unique_dates[train_dates]))
            validation_index = np.flatnonzero(
                np.isin(dates, unique_dates[validation_dates])
            )
            if (
                len(train_index) < ML_MIN_TRAINING_ROWS
                or len(validation_index) == 0
            ):
                continue
            y_train = y[train_index]
            if len(np.unique(y_train)) < 2:
                continue

            fold_scaler = StandardScaler()
            X_train = fold_scaler.fit_transform(X[train_index])
            X_validation = fold_scaler.transform(X[validation_index])
            fold_model = self._new_ml_model()
            fold_model.fit(X_train, y_train)

            fold_probabilities = fold_model.predict_proba(X_validation)[:, 1]
            fold_labels = y[validation_index]
            fold_baseline = np.full(len(validation_index), float(np.mean(y_train)))
            validation_probabilities.extend(fold_probabilities.tolist())
            validation_labels.extend(fold_labels.tolist())
            baseline_probabilities.extend(fold_baseline.tolist())
            fold_brier_scores.append(brier_score_loss(fold_labels, fold_probabilities))
            fold_baseline_scores.append(brier_score_loss(fold_labels, fold_baseline))

        if len(validation_labels) < ML_MIN_VALIDATION_ROWS:
            print("WARNING: Too few walk-forward predictions; using statistical only")
            return False

        validation_labels_array = np.asarray(validation_labels, dtype=int)
        validation_probabilities_array = np.asarray(validation_probabilities, dtype=float)
        baseline_probabilities_array = np.asarray(baseline_probabilities, dtype=float)
        model_brier = brier_score_loss(
            validation_labels_array,
            validation_probabilities_array,
        )
        baseline_brier = brier_score_loss(
            validation_labels_array,
            baseline_probabilities_array,
        )
        model_accuracy = accuracy_score(
            validation_labels_array,
            validation_probabilities_array >= 0.5,
        )
        baseline_accuracy = accuracy_score(
            validation_labels_array,
            baseline_probabilities_array >= 0.5,
        )

        model_metrics = {
            'training_matches': int(len(X)),
            'validation_matches': int(len(validation_labels_array)),
            'accuracy': float(model_accuracy),
            'baseline_accuracy': float(baseline_accuracy),
            'brier_score': float(model_brier),
            'baseline_brier_score': float(baseline_brier),
            'fold_brier_scores': [float(score) for score in fold_brier_scores],
            'fold_baseline_brier_scores': [
                float(score) for score in fold_baseline_scores
            ],
            'folds_beating_baseline': sum(
                model_score < baseline_score
                for model_score, baseline_score
                in zip(fold_brier_scores, fold_baseline_scores)
            ),
            'validation': 'date_grouped_expanding_window',
        }

        # A probability model must beat the prevalence baseline out of sample.
        required_winning_folds = math.ceil(len(fold_brier_scores) * 0.8)
        if (
            model_brier >= baseline_brier
            or model_metrics['folds_beating_baseline'] < required_winning_folds
        ):
            print(
                "WARNING: ML failed validation gate "
                f"(Brier {model_brier:.4f} vs baseline {baseline_brier:.4f})"
            )
            return False

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        self.ml_model = self._new_ml_model()
        self.ml_model.fit(X_scaled, y)
        self.model_metrics = model_metrics
        self.model_trained = True
        self.model_metrics['active'] = True
        print(
            "ML passed walk-forward gate "
            f"(Brier {model_brier:.4f} vs baseline {baseline_brier:.4f})"
        )
        self.save_model()
        return True

    @staticmethod
    def _new_ml_model() -> RandomForestClassifier:
        return RandomForestClassifier(
            n_estimators=250,
            max_depth=6,
            min_samples_split=12,
            min_samples_leaf=6,
            class_weight='balanced_subsample',
            random_state=42,
            n_jobs=-1,
        )
    
    def save_model(self):
        """Save model to disk"""
        if not self.model_trained:
            return
        
        try:
            with open(ML_MODEL_PATH, 'wb') as f:
                pickle.dump({
                    'version': ML_MODEL_VERSION,
                    'feature_names': ML_FEATURE_NAMES,
                    'model': self.ml_model,
                    'scaler': self.scaler,
                    'metrics': self.model_metrics,
                }, f)
            print("Model saved")
        except Exception as e:
            print(f"WARNING: Could not save model: {e}")
    
    def load_model(self) -> bool:
        """Load model from disk"""
        model_path = ML_MODEL_PATH

        if not model_path.exists():
            return False
        
        try:
            with open(model_path, 'rb') as f:
                bundle = pickle.load(f)
            if not isinstance(bundle, dict):
                return False
            if bundle.get('version') != ML_MODEL_VERSION:
                return False
            if tuple(bundle.get('feature_names', ())) != ML_FEATURE_NAMES:
                return False
            if not bundle.get('metrics', {}).get('active'):
                return False
            if 'folds_beating_baseline' not in bundle.get('metrics', {}):
                return False

            self.ml_model = bundle['model']
            self.scaler = bundle['scaler']
            self.model_metrics = bundle['metrics']
            self.model_trained = True
            print("ML model loaded")
            return True
        except Exception as e:
            print(f"WARNING: Failed to load model: {e}")
            return False
    
    def load_or_train_model(self):
        """Load existing or train new model"""
        if not self.load_model():
            print("Training new model...")
            self.train_model()
    
    def ml_predict(self, features: List[float]) -> Tuple[Optional[float], float]:
        """Return probability (or None) and relative out-of-sample Brier improvement.

        A failed prediction returns ``None`` so callers fall back explicitly;
        a silent neutral 0.5 would be displayed as a real 50% estimate.
        """
        if not self.model_trained or self.ml_model is None:
            return None, 0.0

        try:
            X = np.array([features])
            if X.shape[1] != len(ML_FEATURE_NAMES):
                return None, 0.0
            X_scaled = self.scaler.transform(X)
            proba = self.ml_model.predict_proba(X_scaled)[0][1]
            model_brier = self.model_metrics.get('brier_score')
            baseline_brier = self.model_metrics.get('baseline_brier_score')
            improvement = (
                (baseline_brier - model_brier) / baseline_brier
                if model_brier is not None and baseline_brier
                else 0.0
            )
            return proba, max(0.0, min(1.0, improvement))
        except Exception:
            return None, 0.0
    
    def _poisson_at_least_one(self, expected_goals: float) -> float:
        """
        POISSON: P(X ≥ 1) = 1 - e^(-λ)
        Dies ist die KORREKTE Formel!
        """
        if expected_goals < 0:
            raise ValueError("expected_goals cannot be negative")
        p_zero = math.exp(-expected_goals)
        return (1 - p_zero) * 100
    
    def _poisson_over(self, expected: float, goals_needed: int) -> float:
        """P(X >= goals_needed) mit Poisson"""
        if expected < 0:
            raise ValueError("expected cannot be negative")
        if goals_needed <= 0:
            return 100.0
        p_under = sum((expected ** k) * math.exp(-expected) / math.factorial(k) 
                      for k in range(goals_needed))
        return (1 - p_under) * 100
    
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
        """Analyze one fixture without using H2H or bookmaker prices as inputs.

        The statistical fallback uses season 50%, venue 30%, and recent form
        20% when both teams have at least three form matches. The Poisson
        baseline is blended separately; validated ML replaces that fallback.
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
        if not league_id:
            return {'error': f'Unknown league code: {league_code}'}
        
        # =============================================
        # 1. Season statistics (50% of the statistical fallback)
        # =============================================
        home_season = self._get_season_stats(home_team_id, league_id, 'home')
        away_season = self._get_season_stats(away_team_id, league_id, 'away')
        
        if not home_season or not away_season:
            return {'error': 'Could not get team statistics'}
        
        # Small empirical rates are shrunk before they enter the fallback.
        season_btts = (
            beta_smoothed_percentage(
                home_season['btts_rate'], home_season['total_sample']
            )
            + beta_smoothed_percentage(
                away_season['btts_rate'], away_season['total_sample']
            )
        ) / 2.0
        
        # =============================================
        # 2. Recent league form (20% when available)
        # =============================================
        home_form = self._get_form_stats(home_team_id, league_id)
        away_form = self._get_form_stats(away_team_id, league_id)

        has_form_data = (
            home_form.get('matches_played', 0) >= 3
            and away_form.get('matches_played', 0) >= 3
        )
        form_btts = (
            (
                beta_smoothed_percentage(
                    home_form['btts_rate'], home_form['matches_played']
                )
                + beta_smoothed_percentage(
                    away_form['btts_rate'], away_form['matches_played']
                )
            ) / 2.0
            if has_form_data
            else None
        )
        
        # =============================================
        # 3. HEAD-TO-HEAD (descriptive only)
        # =============================================
        h2h = self._get_h2h_stats(home_team_id, away_team_id)
        has_h2h_data = h2h.get('matches_played', 0) >= 3
        h2h_btts = h2h.get('btts_rate') if has_h2h_data else None
        
        # =============================================
        # 4. Venue-specific rate (30% of the statistical fallback)
        # =============================================
        # Home team's HOME btts rate + Away team's AWAY btts rate
        venue_btts = (
            beta_smoothed_percentage(
                home_season['btts_rate_venue'], home_season['venue_sample']
            )
            + beta_smoothed_percentage(
                away_season['btts_rate_venue'], away_season['venue_sample']
            )
        ) / 2.0
        
        # =============================================
        # ERWEITERTE BTTS-BERECHNUNG (gewichtet)
        # =============================================
        components = [
            (season_btts, 0.50),
            (venue_btts, 0.30),
        ]
        if has_form_data:
            components.append((form_btts, 0.20))

        available_weight = sum(weight for _, weight in components)
        weighted_btts = sum(value * weight for value, weight in components) / available_weight
        
        # =============================================
        # POISSON-VERTEILUNG für Torwahrscheinlichkeit
        # =============================================
        # λ = erwartete Tore
        # Inputs are already venue-specific. Applying another fixed home/away
        # multiplier would count venue effects twice.
        lambda_home = (
            home_season['avg_scored'] + away_season['avg_conceded']
        ) / 2
        lambda_away = (
            away_season['avg_scored'] + home_season['avg_conceded']
        ) / 2
        
        # P(Team ≥ 1 Tor) = 1 - e^(-λ) - für Anzeige
        p_home_scores = (1 - math.exp(-lambda_home)) * 100
        p_away_scores = (1 - math.exp(-lambda_away)) * 100
        
        # =============================================
        # DEPENDENCE-AWARE BTTS CALCULATION
        # =============================================
        # The product formula is the independent-Poisson baseline. These two
        # models add explicit low-score and common-component dependence.
        
        independent_btts = p_home_scores * p_away_scores / 100.0

        # Fixed dependence parameters are retained as sensitivity scenarios,
        # not blended into the active probability until they are fitted.
        dc_btts = self.dixon_coles.calculate_btts_probability(lambda_home, lambda_away)
        
        # 2. Bivariate Poisson: Modelliert Tor-Korrelation (Spieldynamik-Änderung nach Toren)
        bv_btts = self.bivariate_poisson.calculate_btts_probability(lambda_home, lambda_away)
        
        poisson_btts = independent_btts
        
        # =============================================
        # FINALE KOMBINATION
        # =============================================
        ml_probability = None
        # Serving features must match the training definition: rolling
        # last-N windows from the local match store, not provider season
        # aggregates. Mixing the two would create silent train/serve skew.
        ml_features = None
        home_recent = self.engine.get_recent_form(
            home_team_id, league_code, venue='all', last_n=ML_HISTORY_WINDOW
        )
        away_recent = self.engine.get_recent_form(
            away_team_id, league_code, venue='all', last_n=ML_HISTORY_WINDOW
        )
        if (
            isinstance(home_recent, dict)
            and isinstance(away_recent, dict)
            and home_recent.get('matches', 0) >= ML_MIN_TEAM_HISTORY
            and away_recent.get('matches', 0) >= ML_MIN_TEAM_HISTORY
        ):
            candidate_features = [
                home_recent.get('btts_rate'),
                away_recent.get('btts_rate'),
                home_recent.get('avg_scored'),
                away_recent.get('avg_scored'),
                home_recent.get('avg_conceded'),
                away_recent.get('avg_conceded'),
            ]
            if all(
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and math.isfinite(float(value))
                for value in candidate_features
            ):
                ml_features = [float(value) for value in candidate_features]
        if self.model_trained and ml_features is not None:
            predicted_probability = self.ml_predict(ml_features)[0]
            if predicted_probability is not None:
                ml_probability = predicted_probability * 100.0
        if ml_probability is not None:
            final_btts = ml_probability
            active_model = 'walk_forward_validated_ml'
        else:
            final_btts = (
                self.weights['statistical'] * weighted_btts
                + self.weights['poisson'] * poisson_btts
            )
            active_model = 'uncalibrated_statistical_fallback'
        
        final_btts = max(0.0, min(100.0, final_btts))
        
        # Evidence measures sample coverage and model agreement, not safety.
        predictions = [season_btts, venue_btts, poisson_btts]
        if has_form_data:
            predictions.append(form_btts)
        if ml_probability is not None:
            predictions.append(ml_probability)

        evidence = calculate_evidence_score(
            home_season.get('venue_sample', 0),
            away_season.get('venue_sample', 0),
            home_form.get('matches_played', 0),
            away_form.get('matches_played', 0),
            predictions,
        )
        confidence = evidence['score']
        agreement_score = evidence['agreement_score'] / 100.0
        
        # Evidence band measures data coverage/agreement, not betting confidence.
        if confidence >= 80:
            confidence_level = "VERY_HIGH"
        elif confidence >= 65:
            confidence_level = "HIGH"
        elif confidence >= 50:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"
        
        # This remains exploratory until a separate calibration and price gate.
        if final_btts >= 70 and confidence >= 65:
            recommendation = "LARGE EXPLORATORY MARGIN"
        elif final_btts >= 60 and confidence >= 55:
            recommendation = "POSITIVE EXPLORATORY MARGIN"
        elif final_btts >= 50:
            recommendation = "SMALL EXPLORATORY MARGIN"
        else:
            recommendation = "NO BTTS ESTIMATE MARGIN"
        
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
            'calibrated': False,
            'actionable': False,
            'recommendation_type': 'EXPLORATORY_ESTIMATE',
            
            # Individual components
            'season_btts': round(season_btts, 1),
            'form_btts': round(form_btts, 1) if form_btts is not None else None,
            'h2h_btts': round(h2h_btts, 1) if h2h_btts is not None else None,
            'venue_btts': round(venue_btts, 1),
            'poisson_btts': round(poisson_btts, 1),
            
            'ml_probability': round(ml_probability, 1) if ml_probability is not None else None,
            'statistical_probability': round(weighted_btts, 1),
            'form_probability': round(form_btts, 1) if form_btts is not None else None,
            'h2h_probability': round(h2h_btts, 1) if h2h_btts is not None else None,
            
            # Details
            'details': {
                'expected_home_goals': round(lambda_home, 2),
                'expected_away_goals': round(lambda_away, 2),
                'expected_total_goals': round(expected_total, 2),
                'p_home_scores': round(p_home_scores, 1),
                'p_away_scores': round(p_away_scores, 1),
                'dixon_coles_btts': round(dc_btts, 1),
                'bivariate_poisson_btts': round(bv_btts, 1),
                'independent_poisson_btts': round(independent_btts, 1),
                'data_quality_score': round(confidence, 1),
                'agreement_score': round(agreement_score * 100.0, 1),
                'evidence_breakdown': evidence,
                'fallback_weights': {
                    'season': 0.50,
                    'venue': 0.30,
                    'form_if_available': 0.20,
                },
                'rate_prior': 'Beta(1,1)',
                'h2h_active': False,
                'ml_active': ml_probability is not None,
                'ml_model_available': self.model_trained,
                'active_model': active_model,
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
    
    def _get_season_stats(
        self,
        team_id: int,
        league_id: int,
        venue: str,
    ) -> Optional[Dict]:
        """Get season statistics from API or cache"""
        season = current_season_start_year_for_id(league_id)
        cache_key = f"season_{team_id}_{league_id}_{season}"
        stats = self._team_stats_cache.get(cache_key)

        if stats is None and self.api_football_key:
            try:
                from api_football import APIFootball
                api = APIFootball(self.api_football_key)
                stats = api.get_team_statistics(
                    team_id,
                    league_id,
                    season,
                )
                if stats:
                    self._team_stats_cache[cache_key] = stats
            except Exception as e:
                print(f"WARNING: API error: {e}")

        venue_rate = stats.get(f'btts_rate_{venue}') if stats else None
        total_rate = stats.get('btts_rate_total') if stats else None
        scored = stats.get(f'avg_goals_scored_{venue}') if stats else None
        conceded = stats.get(f'avg_goals_conceded_{venue}') if stats else None
        venue_sample = stats.get(f'btts_sample_{venue}', 0) if stats else 0
        total_sample = stats.get('btts_sample_total', 0) if stats else 0

        if (
            total_rate is None
            or venue_rate is None
            or scored is None
            or conceded is None
            or total_sample < 5
            or venue_sample < 2
        ):
            print(f"Insufficient BTTS sample for team {team_id}")
            return None

        return {
            'team_name': stats.get('team_name', 'Unknown'),
            'btts_rate': total_rate,
            'btts_rate_venue': venue_rate,
            'avg_scored': scored,
            'avg_conceded': conceded,
            'ml_avg_scored': stats.get('avg_goals_scored_total'),
            'ml_avg_conceded': stats.get('avg_goals_conceded_total'),
            'matches_played': venue_sample,
            'venue_sample': venue_sample,
            'total_sample': total_sample,
            'clean_sheets': stats.get(f'clean_sheets_{venue}', 0),
            'failed_to_score': stats.get(f'failed_to_score_{venue}', 0),
        }

    def _get_form_stats(self, team_id: int, league_id: int) -> Dict:
        """Get last 5 matches form from API or cache"""
        cache_key = f"form_{team_id}_{league_id}"
        
        if cache_key in self._form_cache:
            return self._form_cache[cache_key]
        
        # Try API
        if self.api_football_key:
            try:
                from api_football import APIFootball
                api = APIFootball(self.api_football_key)
                form = api.get_team_last_matches(
                    team_id,
                    5,
                    league_id=league_id,
                    season=current_season_start_year_for_id(league_id),
                )
                
                if form and form.get('matches_played', 0) > 0:
                    self._form_cache[cache_key] = form
                    print(
                        f"   Form: {form.get('form_string', '?')} "
                        f"({form.get('btts_rate'):.0f}% BTTS)"
                    )
                    return form
            except Exception as e:
                print(f"WARNING: Form API error: {e}")
        
        # Missing form is neutral and explicitly carries zero observations.
        return {
            'matches_played': 0,
            'btts_rate': None,
            'avg_goals_scored': None,
            'avg_goals_conceded': None,
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
                    btts_count = 0
                    total_goals = 0
                    matches_played = 0
                    
                    for match in h2h_matches:
                        if not isinstance(match, dict):
                            return self._empty_h2h_stats()
                        teams = match.get('teams')
                        goals = match.get('goals')
                        if not isinstance(teams, dict) or not isinstance(goals, dict):
                            return self._empty_h2h_stats()
                        home = teams.get('home')
                        away = teams.get('away')
                        if not isinstance(home, dict) or not isinstance(away, dict):
                            return self._empty_h2h_stats()
                        home_id = home.get('id')
                        away_id = away.get('id')
                        home_goals = goals.get('home')
                        away_goals = goals.get('away')
                        if (
                            any(
                                isinstance(value, bool) or not isinstance(value, int)
                                for value in (home_id, away_id, home_goals, away_goals)
                            )
                            or set((home_id, away_id)) != {team1_id, team2_id}
                            or home_goals < 0
                            or away_goals < 0
                            or home_goals > 30
                            or away_goals > 30
                        ):
                            return self._empty_h2h_stats()
                        matches_played += 1
                        if home_goals > 0 and away_goals > 0:
                            btts_count += 1
                        total_goals += home_goals + away_goals

                    if matches_played == 0:
                        return self._empty_h2h_stats()

                    h2h_stats = {
                        'matches_played': matches_played,
                        'btts_rate': btts_count / matches_played * 100,
                        'btts_count': btts_count,
                        'avg_goals': total_goals / matches_played,
                        'total_goals': total_goals,
                    }
                    
                    self._h2h_cache[cache_key] = h2h_stats
                    print(f"H2H: {matches_played} matches, {h2h_stats['btts_rate']:.0f}% BTTS")
                    return h2h_stats
            except Exception as e:
                print(f"WARNING: H2H API error: {e}")
        
        return self._empty_h2h_stats()

    @staticmethod
    def _empty_h2h_stats() -> Dict:
        return {
            'matches_played': 0,
            'btts_rate': None,
            'btts_count': 0,
            'avg_goals': None,
            'total_goals': 0,
        }
        
    # =============================================
    # UPCOMING MATCHES METHODS
    # =============================================
    
    def get_upcoming_matches(self, league_code: str, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming matches using API-Football"""
        if not self.api_football_key:
            print("WARNING: API-Football key not available")
            return []
        
        try:
            from api_football import APIFootball
            api = APIFootball(self.api_football_key)
            
            print(f"Fetching upcoming fixtures for {league_code}...")
            fixtures = api.get_upcoming_fixtures(league_code, days_ahead)
            
            if fixtures:
                print(f"Found {len(fixtures)} upcoming matches")
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
                print(f"No upcoming matches found for {league_code}")
                return []
                
        except Exception as e:
            print(f"ERROR: Could not fetch fixtures: {e}")
            return []
    
    def analyze_upcoming_matches(self, league_code: str, days_ahead: int = 7,
                                min_probability: float = 60.0) -> pd.DataFrame:
        """Analyze upcoming matches and return non-actionable model estimates."""
        print(f"\nAnalyzing upcoming matches for {league_code}...")
        
        matches = self.get_upcoming_matches(league_code, days_ahead)
        
        if not matches:
            print("No upcoming matches found")
            return pd.DataFrame()
        
        results = []
        
        for match in matches:
            home_team = match['homeTeam']
            away_team = match['awayTeam']
            
            print(f"   Analyzing: {home_team['name']} vs {away_team['name']}...")
            
            analysis = self.analyze_match(home_team['id'], away_team['id'], league_code)
            
            if 'error' in analysis:
                print(f"Skipped: {analysis['error']}")
                continue
            
            if analysis['ensemble_probability'] >= min_probability:
                try:
                    date_str = match.get('utcDate', match.get('date', ''))
                    if date_str and 'T' in str(date_str):
                        parsed_date = datetime.fromisoformat(
                            str(date_str).replace('Z', '+00:00')
                        )
                        if parsed_date.tzinfo is not None:
                            parsed_date = parsed_date.astimezone()
                        date_formatted = parsed_date.strftime('%d.%m.%Y %H:%M')
                    else:
                        date_formatted = str(date_str)[:16] if date_str else 'Unknown'
                except (TypeError, ValueError):
                    date_formatted = str(match.get('date', 'Unknown'))[:16]
                
                results.append({
                    'Date': date_formatted,
                    'Home': home_team['name'],
                    'Away': away_team['name'],
                    'BTTS %': f"{analysis['ensemble_probability']:.1f}%",
                    'Data Quality': f"{analysis['confidence']:.1f}%",
                    'Quality Level': analysis['confidence_level'],
                    'Modellstatus': analysis['recommendation'],
                    'ML': (
                        f"{analysis['ml_probability']:.1f}%"
                        if analysis['ml_probability'] is not None
                        else "n/a"
                    ),
                    'Stat': f"{analysis['statistical_probability']:.1f}%",
                    'Form': (
                        f"{analysis['form_probability']:.1f}%"
                        if analysis['form_probability'] is not None
                        else "n/a"
                    ),
                    'H2H': (
                        f"{analysis['h2h_probability']:.1f}%"
                        if analysis['h2h_probability'] is not None
                        else "n/a"
                    ),
                    'xG Total': f"{analysis['details']['expected_total_goals']:.1f}",
                    '_analysis': analysis
                })
        
        if not results:
            print("No matches meet the criteria")
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        df = df.sort_values('BTTS %', ascending=False)
        
        print(f"Found {len(results)} exploratory estimates")
        
        return df


# Export
__all__ = ['AdvancedBTTSAnalyzer']
