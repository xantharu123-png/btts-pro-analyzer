"""Experimental chronological ML engine and backtest utilities.

The active classifier uses ten reproducible pre-match rolling features. Model
selection is chronological and based on multiclass Brier score versus a
training-prevalence baseline. Passing this gate is not a calibration or profit
claim.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from betting_math import BettingMathError, validate_decimal_odds


MODEL_BUNDLE_VERSION = 4

try:
    from sklearn.base import clone
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


def _optional_nonnegative(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric < 0:
        return None
    return numeric


class InjuryTracker:
    """Compatibility stub; no injury impact is inferred without validated data."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_team_injuries(self, team_id: int, fixture_id: int = None) -> Dict:
        return {'data_available': False, 'details': []}

    @staticmethod
    def adjust_team_strength(base_strength: float, injury_data: Dict) -> float:
        return float(base_strength)


class FatigueAnalyzer:
    """Compatibility stub; schedule effects are not guessed."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def analyze_fixture_congestion(self, *args, **kwargs) -> Dict:
        return {'data_available': False}


class MotivationAnalyzer:
    """Compatibility stub; standings do not receive an arbitrary multiplier."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_motivation_factors(self, team_id: int, league_id: int) -> Dict:
        return {'data_available': False}


class ManagerChangeTracker:
    """Compatibility stub; manager changes are descriptive only."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def check_manager_change(self, team_id: int) -> Dict:
        return {'data_available': False, 'changed': None}


@dataclass
class MatchFeatures:
    home_attack_strength: float = 0.0
    home_defense_strength: float = 0.0
    away_attack_strength: float = 0.0
    away_defense_strength: float = 0.0
    home_form_goals_scored: float = 0.0
    home_form_goals_conceded: float = 0.0
    away_form_goals_scored: float = 0.0
    away_form_goals_conceded: float = 0.0
    home_form_points: float = 0.0
    away_form_points: float = 0.0
    home_xg_for: float = 0.0
    home_xg_against: float = 0.0
    away_xg_for: float = 0.0
    away_xg_against: float = 0.0
    league_id: int = 0

    def to_array(self) -> np.ndarray:
        values = np.asarray([
            self.home_attack_strength,
            self.home_defense_strength,
            self.away_attack_strength,
            self.away_defense_strength,
            self.home_form_goals_scored,
            self.home_form_goals_conceded,
            self.away_form_goals_scored,
            self.away_form_goals_conceded,
            self.home_form_points,
            self.away_form_points,
        ], dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Active features must all be finite")
        return values

    @staticmethod
    def feature_names() -> List[str]:
        return [
            'home_attack_strength',
            'home_defense_strength',
            'away_attack_strength',
            'away_defense_strength',
            'home_form_goals_scored',
            'home_form_goals_conceded',
            'away_form_goals_scored',
            'away_form_goals_conceded',
            'home_form_points',
            'away_form_points',
        ]


class MLEnsemble:
    """Compatibility name for chronologically selecting one best classifier."""

    TARGET_CLASSES = {
        'match_result': np.asarray([0, 1, 2]),
        'btts': np.asarray([0, 1]),
        'over_25': np.asarray([0, 1]),
    }

    def __init__(self, model_path: str = None, target: str = 'match_result'):
        if target not in self.TARGET_CLASSES:
            raise ValueError(f"Unsupported target: {target}")
        self.model_path = Path(model_path or 'models')
        self.target = target
        self.models = {}
        self.weights = {}
        self.scaler = StandardScaler() if ML_AVAILABLE else None
        self.is_trained = False
        self.validation_scores = {}
        self.classes_ = self.TARGET_CLASSES[target].copy()
        self._initialize_models()

    def _initialize_models(self):
        self.models = {}
        if not ML_AVAILABLE:
            return
        if XGBOOST_AVAILABLE:
            self.models['xgboost'] = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                eval_metric='mlogloss',
            )
        self.models['random_forest'] = RandomForestClassifier(
            n_estimators=250,
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            class_weight='balanced_subsample',
            random_state=42,
            n_jobs=-1,
        )
        self.models['gradient_boosting'] = GradientBoostingClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.05,
            min_samples_leaf=5,
            random_state=42,
        )
        self.models['neural_network'] = MLPClassifier(
            hidden_layer_sizes=(64, 32),
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
        )

    @staticmethod
    def _align_probabilities(
        probabilities: np.ndarray,
        model_classes: np.ndarray,
        expected_classes: np.ndarray,
    ) -> np.ndarray:
        aligned = np.zeros((len(probabilities), len(expected_classes)), dtype=float)
        class_indices = {
            class_label: index for index, class_label in enumerate(expected_classes)
        }
        for source_index, class_label in enumerate(model_classes):
            if class_label in class_indices:
                aligned[:, class_indices[class_label]] = probabilities[:, source_index]
        row_sums = aligned.sum(axis=1, keepdims=True)
        if np.any(row_sums <= 0):
            raise ValueError("Classifier returned no mass for expected classes")
        return aligned / row_sums

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        target: str = 'match_result',
        dates: Optional[np.ndarray] = None,
    ) -> Dict:
        if not ML_AVAILABLE:
            raise RuntimeError("scikit-learn is required for training")
        if target not in self.TARGET_CLASSES:
            raise ValueError(f"Unsupported target: {target}")
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        if X.ndim != 2 or X.shape[1] != len(MatchFeatures.feature_names()):
            raise ValueError("Training data does not match the active feature schema")
        if len(X) != len(y) or len(X) < 100:
            raise ValueError("At least 100 aligned chronological samples are required")
        if not np.isfinite(X).all():
            raise ValueError("Training features must be finite")
        if dates is not None:
            dates = np.asarray(dates)
            if len(dates) != len(X):
                raise ValueError("dates must align one-to-one with the training rows")
            if len(dates) > 1 and np.any(dates[:-1] > dates[1:]):
                raise ValueError("dates must be chronologically ordered")

        expected_classes = self.TARGET_CLASSES[target]
        if set(np.unique(y)) != set(expected_classes):
            raise ValueError(f"Target {target} requires classes {expected_classes.tolist()}")
        self.target = target
        self.classes_ = expected_classes.copy()
        self._initialize_models()

        if dates is None:
            holdout_size = max(20, int(math.ceil(len(X) * 0.20)))
            selection_end = len(X) - holdout_size
        else:
            # Day-grouped boundary: the holdout starts at a calendar-day edge,
            # so matches of the same day never straddle selection and holdout.
            unique_days = np.unique(dates)
            if len(unique_days) < 12:
                self.models = {}
                self.weights = {}
                self.is_trained = False
                self.validation_scores = {}
                return {}
            holdout_day_count = max(1, int(math.ceil(len(unique_days) * 0.20)))
            boundary_day = unique_days[len(unique_days) - holdout_day_count]
            selection_end = int(np.searchsorted(dates, boundary_day, side='left'))
            if len(X) - selection_end < 20:
                self.models = {}
                self.weights = {}
                self.is_trained = False
                self.validation_scores = {}
                return {}
        X_selection, y_selection = X[:selection_end], y[:selection_end]
        X_holdout, y_holdout = X[selection_end:], y[selection_end:]
        if len(X_selection) < 100 or set(np.unique(y_selection)) != set(expected_classes):
            self.models = {}
            self.weights = {}
            self.is_trained = False
            self.validation_scores = {}
            return {}

        splitter = TimeSeriesSplit(n_splits=5)
        if dates is None:
            split_pairs = list(splitter.split(X_selection))
        else:
            # Day-grouped expanding window: fold boundaries are calendar days,
            # never rows, so same-day results cannot cross a fold boundary.
            selection_days = np.unique(dates[:selection_end])
            if len(selection_days) <= 5:
                self.models = {}
                self.weights = {}
                self.is_trained = False
                self.validation_scores = {}
                return {}
            dates_selection = dates[:selection_end]
            split_pairs = [
                (
                    np.flatnonzero(np.isin(dates_selection, selection_days[train_days])),
                    np.flatnonzero(np.isin(dates_selection, selection_days[validation_days])),
                )
                for train_days, validation_days in splitter.split(selection_days)
            ]
        accepted = {}
        scores_by_model = {}
        for name, template in self.models.items():
            fold_scores = []
            baseline_scores = []
            fold_accuracies = []
            valid = True
            for train_index, validation_index in split_pairs:
                y_train = y_selection[train_index]
                if len(np.unique(y_train)) < 2:
                    valid = False
                    break
                try:
                    scaler = StandardScaler()
                    X_train = scaler.fit_transform(X_selection[train_index])
                    X_validation = scaler.transform(X_selection[validation_index])
                    model = clone(template)
                    model.fit(X_train, y_train)
                    probabilities = self._align_probabilities(
                        model.predict_proba(X_validation),
                        np.asarray(model.classes_),
                        expected_classes,
                    )
                except Exception:
                    valid = False
                    break

                labels = y_selection[validation_index]
                one_hot = (labels[:, None] == expected_classes[None, :]).astype(float)
                fold_scores.append(
                    float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))
                )
                fold_accuracies.append(
                    float(accuracy_score(labels, expected_classes[np.argmax(probabilities, axis=1)]))
                )
                counts = np.asarray([
                    np.sum(y_train == class_label) for class_label in expected_classes
                ], dtype=float)
                prevalence = counts / counts.sum()
                baseline = np.tile(prevalence, (len(validation_index), 1))
                baseline_scores.append(
                    float(np.mean(np.sum((baseline - one_hot) ** 2, axis=1)))
                )

            if not valid or len(fold_scores) != 5:
                continue
            metrics = {
                'brier_score': float(np.mean(fold_scores)),
                'baseline_brier_score': float(np.mean(baseline_scores)),
                'accuracy': float(np.mean(fold_accuracies)),
                'fold_brier_scores': fold_scores,
                'fold_baseline_brier_scores': baseline_scores,
                'folds_beating_baseline': sum(
                    score < baseline
                    for score, baseline in zip(fold_scores, baseline_scores)
                ),
                'validation': (
                    'day_grouped_expanding_window'
                    if dates is not None
                    else 'expanding_window'
                ),
            }
            scores_by_model[name] = metrics
            if (
                metrics['brier_score'] < metrics['baseline_brier_score']
                and metrics['folds_beating_baseline'] >= 4
            ):
                accepted[name] = template

        self.validation_scores = scores_by_model
        if not accepted:
            self.models = {}
            self.weights = {}
            self.is_trained = False
            return scores_by_model

        best_name = min(
            accepted,
            key=lambda name: scores_by_model[name]['brier_score'],
        )

        # Model selection happened only on the earlier window. The newest
        # chronological block is now an untouched gate against selection bias.
        holdout_scaler = StandardScaler()
        X_selection_scaled = holdout_scaler.fit_transform(X_selection)
        X_holdout_scaled = holdout_scaler.transform(X_holdout)
        holdout_model = clone(accepted[best_name])
        try:
            holdout_model.fit(X_selection_scaled, y_selection)
            holdout_probabilities = self._align_probabilities(
                holdout_model.predict_proba(X_holdout_scaled),
                np.asarray(holdout_model.classes_),
                expected_classes,
            )
        except Exception:
            self.models = {}
            self.weights = {}
            self.is_trained = False
            return scores_by_model

        holdout_one_hot = (
            y_holdout[:, None] == expected_classes[None, :]
        ).astype(float)
        holdout_brier = float(np.mean(np.sum(
            (holdout_probabilities - holdout_one_hot) ** 2,
            axis=1,
        )))
        selection_counts = np.asarray([
            np.sum(y_selection == class_label) for class_label in expected_classes
        ], dtype=float)
        selection_prevalence = selection_counts / selection_counts.sum()
        holdout_baseline = np.tile(selection_prevalence, (len(y_holdout), 1))
        holdout_baseline_brier = float(np.mean(np.sum(
            (holdout_baseline - holdout_one_hot) ** 2,
            axis=1,
        )))
        holdout_accuracy = float(accuracy_score(
            y_holdout,
            expected_classes[np.argmax(holdout_probabilities, axis=1)],
        ))
        holdout_passed = holdout_brier < holdout_baseline_brier
        scores_by_model[best_name].update({
            'selection_sample_size': int(len(y_selection)),
            'holdout_sample_size': int(len(y_holdout)),
            'holdout_brier_score': holdout_brier,
            'holdout_baseline_brier_score': holdout_baseline_brier,
            'holdout_accuracy': holdout_accuracy,
            'holdout_passed': holdout_passed,
            'validation': (
                'inner_day_grouped_expanding_window_plus_untouched_final_holdout'
                if dates is not None
                else 'inner_expanding_window_plus_untouched_final_holdout'
            ),
        })
        self.validation_scores = scores_by_model
        if not holdout_passed:
            self.models = {}
            self.weights = {}
            self.is_trained = False
            return scores_by_model

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        best_model = clone(accepted[best_name])
        best_model.fit(X_scaled, y)
        self.models = {best_name: best_model}
        self.weights = {best_name: 1.0}
        self.is_trained = True
        return scores_by_model

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained or not self.models:
            raise RuntimeError("Model is not trained and chronologically validated")
        values = np.asarray(X, dtype=float).reshape(1, -1)
        if values.shape[1] != len(MatchFeatures.feature_names()) or not np.isfinite(values).all():
            raise ValueError("Prediction data does not match the active feature schema")
        scaled = self.scaler.transform(values)
        name, model = next(iter(self.models.items()))
        return self._align_probabilities(
            model.predict_proba(scaled),
            np.asarray(model.classes_),
            self.classes_,
        )[0]

    def save_models(self):
        if not self.is_trained or len(self.models) != 1:
            raise RuntimeError("No chronologically validated model to save")
        self.model_path.mkdir(parents=True, exist_ok=True)
        name, model = next(iter(self.models.items()))
        joblib.dump(model, self.model_path / f'{name}.joblib')
        joblib.dump(self.scaler, self.model_path / 'scaler.joblib')
        metadata = {
            'version': MODEL_BUNDLE_VERSION,
            'model': name,
            'feature_names': MatchFeatures.feature_names(),
            'target': self.target,
            'classes': self.classes_.tolist(),
            'validation_scores': self.validation_scores,
            'validated': True,
            'selection': 'inner_chronological_brier_then_untouched_final_holdout',
            'holdout_passed': True,
        }
        (self.model_path / 'metadata.json').write_text(
            json.dumps(metadata, indent=2),
            encoding='utf-8',
        )

    def load_models(self) -> bool:
        if not ML_AVAILABLE:
            return False
        metadata_path = self.model_path / 'metadata.json'
        scaler_path = self.model_path / 'scaler.joblib'
        if not metadata_path.exists() or not scaler_path.exists():
            return False
        try:
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            expected_classes = self.TARGET_CLASSES[self.target]
            if (
                metadata.get('version') != MODEL_BUNDLE_VERSION
                or metadata.get('validated') is not True
                or metadata.get('holdout_passed') is not True
                or metadata.get('selection')
                != 'inner_chronological_brier_then_untouched_final_holdout'
                or metadata.get('target') != self.target
                or metadata.get('feature_names') != MatchFeatures.feature_names()
                or metadata.get('classes') != expected_classes.tolist()
            ):
                return False
            model_name = str(metadata.get('model') or '')
            validation_scores = metadata.get('validation_scores')
            selected_metrics = (
                validation_scores.get(model_name)
                if isinstance(validation_scores, dict)
                else None
            )
            model_path = self.model_path / f'{model_name}.joblib'
            if (
                not model_name
                or not model_path.exists()
                or not isinstance(selected_metrics, dict)
                or selected_metrics.get('holdout_passed') is not True
            ):
                return False
            scaler = joblib.load(scaler_path)
            if int(scaler.n_features_in_) != len(MatchFeatures.feature_names()):
                return False
            self.models = {model_name: joblib.load(model_path)}
            self.weights = {model_name: 1.0}
            self.scaler = scaler
            self.classes_ = expected_classes.copy()
            self.validation_scores = validation_scores
            self.is_trained = True
            return True
        except (OSError, ValueError, TypeError, KeyError):
            return False


class BacktestingEngine:
    """Evaluate previously recorded out-of-sample predictions and prices."""

    def __init__(self):
        self.predictions = []
        self.results = []
        self.provenance = []

    @staticmethod
    def _utc_datetime(value) -> datetime:
        if isinstance(value, datetime):
            timestamp = value
        elif isinstance(value, str):
            timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            raise ValueError("timestamp must be datetime or ISO-8601 text")
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return timestamp.astimezone(timezone.utc)

    def add_prediction(
        self,
        prediction: Dict,
        actual_result: Dict,
        *,
        fixture_id: int,
        league_id: int,
        predicted_at,
        fixture_kickoff,
        model_trained_until,
        model_version: str,
    ):
        if not isinstance(prediction, dict) or not isinstance(actual_result, dict):
            raise ValueError("prediction and actual_result must be mappings")
        if (
            not isinstance(fixture_id, int)
            or isinstance(fixture_id, bool)
            or fixture_id <= 0
            or not isinstance(league_id, int)
            or isinstance(league_id, bool)
            or league_id <= 0
        ):
            raise ValueError("fixture_id and league_id must be positive integers")
        prediction_time = self._utc_datetime(predicted_at)
        kickoff_time = self._utc_datetime(fixture_kickoff)
        training_cutoff = self._utc_datetime(model_trained_until)
        version = model_version.strip() if isinstance(model_version, str) else ''
        if not version:
            raise ValueError("model_version is required")
        if not training_cutoff < prediction_time < kickoff_time:
            raise ValueError(
                "out-of-sample prediction requires training cutoff < prediction < kickoff"
            )
        if any(
            item['fixture_id'] == fixture_id and item['league_id'] == league_id
            for item in self.provenance
        ):
            raise ValueError("fixture already has an out-of-sample prediction")
        self.predictions.append(dict(prediction))
        self.results.append(dict(actual_result))
        self.provenance.append({
            'fixture_id': fixture_id,
            'league_id': league_id,
            'predicted_at': prediction_time,
            'fixture_kickoff': kickoff_time,
            'model_trained_until': training_cutoff,
            'model_version': version,
        })

    @staticmethod
    def _market_prediction(prediction: Dict, market: str) -> Dict:
        if market == 'over_25':
            return prediction.get('over_25') or prediction.get('over_under') or {}
        return prediction.get(market) or {}

    @staticmethod
    def _selection_and_probability(
        market: str,
        market_prediction: Dict,
    ) -> Tuple[Optional[str], Optional[float]]:
        selection = str(market_prediction.get('prediction') or '').upper()
        if not selection:
            return None, None
        explicit = market_prediction.get('probability')
        if (
            not isinstance(explicit, bool)
            and isinstance(explicit, (int, float))
            and math.isfinite(float(explicit))
            and 0 <= float(explicit) <= 1
        ):
            return selection, float(explicit)
        key_maps = {
            'match_result': {'HOME': 'home_win', 'DRAW': 'draw', 'AWAY': 'away_win'},
            'btts': {'YES': 'yes', 'NO': 'no'},
            'over_25': {'OVER': 'over_25', 'UNDER': 'under_25'},
        }
        key = key_maps.get(market, {}).get(selection)
        value = market_prediction.get(key) if key else None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, None
        probability = float(value) / 100.0
        return (
            (selection, probability)
            if math.isfinite(probability) and 0 <= probability <= 1
            else (None, None)
        )

    @classmethod
    def _verified_historical_price(
        cls,
        market_prediction: Dict,
        provenance: Dict,
    ) -> Optional[float]:
        if not str(market_prediction.get('bookmaker') or '').strip():
            return None
        if not str(market_prediction.get('quote_source') or '').strip():
            return None
        try:
            quote_time = cls._utc_datetime(market_prediction.get('quoted_at'))
            prediction_time = provenance['predicted_at']
            kickoff = provenance['fixture_kickoff']
            age = (prediction_time - quote_time).total_seconds()
            price = validate_decimal_odds(market_prediction.get('market_odds'))
        except (ValueError, KeyError, BettingMathError):
            return None
        if not 0 <= age <= 600 or quote_time >= kickoff:
            return None
        return price

    def calculate_accuracy(self, market: str = 'match_result') -> Dict:
        total = correct = price_sample = 0
        total_return = 0.0
        buckets = {
            'high': {'pred': 0, 'correct': 0},
            'medium': {'pred': 0, 'correct': 0},
            'low': {'pred': 0, 'correct': 0},
        }
        for index, (prediction, result) in enumerate(zip(self.predictions, self.results)):
            market_prediction = self._market_prediction(prediction, market)
            settled = result.get(market)
            if not market_prediction or settled is None:
                continue
            selection, probability = self._selection_and_probability(
                market, market_prediction
            )
            if selection is None or probability is None:
                continue
            settled = str(settled).upper()
            is_correct = selection == settled
            total += 1
            correct += int(is_correct)
            bucket = 'high' if probability >= 0.70 else 'medium' if probability >= 0.55 else 'low'
            buckets[bucket]['pred'] += 1
            buckets[bucket]['correct'] += int(is_correct)
            price = (
                self._verified_historical_price(
                    market_prediction,
                    self.provenance[index],
                )
                if index < len(self.provenance)
                else None
            )
            if price is not None:
                price_sample += 1
                total_return += price if is_correct else 0.0
        if total == 0:
            return {'error': f'No settled predictions for {market}'}
        for bucket in buckets.values():
            bucket['accuracy'] = (
                bucket['correct'] / bucket['pred'] if bucket['pred'] else None
            )
        return {
            'total_predictions': total,
            'correct': correct,
            'accuracy': correct / total,
            'by_confidence': buckets,
            'roi': (
                (total_return - price_sample) / price_sample
                if price_sample else None
            ),
            'total_staked': price_sample,
            'total_return': total_return,
        }

    def calibration_curve(
        self,
        market: str = 'btts',
        bins: int = 10,
        *,
        league_id: Optional[int] = None,
    ) -> Dict:
        if isinstance(bins, bool) or not isinstance(bins, int) or not 2 <= bins <= 100:
            raise ValueError("bins must be an integer between 2 and 100")
        if league_id is not None and (
            isinstance(league_id, bool)
            or not isinstance(league_id, int)
            or league_id <= 0
        ):
            raise ValueError("league_id must be a positive integer or None")
        observations = []
        for index, (prediction, result) in enumerate(zip(self.predictions, self.results)):
            if league_id is not None:
                if index >= len(self.provenance) or self.provenance[index]['league_id'] != league_id:
                    continue
            market_prediction = self._market_prediction(prediction, market)
            if not market_prediction or result.get(market) is None:
                continue
            selection, probability = self._selection_and_probability(
                market, market_prediction
            )
            if selection is not None and probability is not None:
                observations.append(
                    (probability, int(selection == str(result[market]).upper()))
                )
        if not observations:
            return {'error': f'No settled predictions for {market}'}

        edges = np.linspace(0.0, 1.0, bins + 1)
        predicted = []
        actual = []
        counts = []
        for index in range(bins):
            values = [
                item for item in observations
                if edges[index] <= item[0] < edges[index + 1]
                or (index == bins - 1 and item[0] == 1.0)
            ]
            counts.append(len(values))
            predicted.append(
                float(np.mean([item[0] for item in values]))
                if values else (edges[index] + edges[index + 1]) / 2.0
            )
            actual.append(
                float(np.mean([item[1] for item in values])) if values else None
            )

        eligible = [index for index, count in enumerate(counts) if count >= 20]
        eligible_count = sum(counts[index] for index in eligible)
        calibration_coverage = eligible_count / len(observations)
        deviations = [abs(predicted[index] - actual[index]) for index in eligible]
        ece = (
            sum(counts[index] * abs(predicted[index] - actual[index]) for index in eligible)
            / eligible_count
            if eligible_count else None
        )
        minimum_sample_met = (
            eligible_count >= 200
            and calibration_coverage >= 0.80
            and len(eligible) >= 3
        )
        max_deviation = max(deviations) if deviations else None
        brier = float(np.mean([
            (probability - outcome) ** 2 for probability, outcome in observations
        ]))
        return {
            'bins': [f'{edges[index]:.1f}-{edges[index + 1]:.1f}' for index in range(bins)],
            'predicted_probs': predicted,
            'actual_probs': actual,
            'counts': counts,
            'brier_score': round(brier, 4),
            'expected_calibration_error': round(ece, 3) if ece is not None else None,
            'max_deviation': round(max_deviation, 3) if max_deviation is not None else None,
            'minimum_sample_met': minimum_sample_met,
            'calibrated_predictions': eligible_count,
            'calibration_coverage': round(calibration_coverage, 4),
            'is_well_calibrated': bool(
                minimum_sample_met
                and ece is not None and ece < 0.05
                and max_deviation is not None and max_deviation < 0.10
            ),
            'evaluated_predictions': len(observations),
        }

    def market_validation_record(
        self,
        market: str = 'btts',
        *,
        method: str,
        bins: int = 10,
        league_id: Optional[int] = None,
    ) -> Optional[Dict]:
        """Build the exact SmartBet validation contract from OOS records."""
        method_name = str(method or '').strip()
        if not method_name or len(self.provenance) != len(self.predictions):
            return None
        available_leagues = {item['league_id'] for item in self.provenance}
        if league_id is None:
            if len(available_leagues) != 1:
                return None
            league_id = next(iter(available_leagues))
        if (
            not isinstance(league_id, int)
            or isinstance(league_id, bool)
            or league_id <= 0
        ):
            return None
        curve = self.calibration_curve(market, bins=bins, league_id=league_id)
        if curve.get('is_well_calibrated') is not True:
            return None
        observation_indices = []
        for index, (prediction, result) in enumerate(zip(self.predictions, self.results)):
            if self.provenance[index]['league_id'] != league_id:
                continue
            market_prediction = self._market_prediction(prediction, market)
            if not market_prediction or result.get(market) is None:
                continue
            selection, probability = self._selection_and_probability(
                market,
                market_prediction,
            )
            if selection is not None and probability is not None:
                observation_indices.append(index)
        if len(observation_indices) != curve['evaluated_predictions']:
            return None
        market_provenance = [self.provenance[index] for index in observation_indices]
        versions = {item['model_version'] for item in market_provenance}
        if len(versions) != 1:
            return None
        eligible_counts = [count for count in curve['counts'] if count >= 20]
        if len(eligible_counts) < 3:
            return None
        prediction_times = [item['predicted_at'] for item in market_provenance]
        return {
            'calibrated': True,
            'out_of_sample': True,
            'sample_size': int(curve['calibrated_predictions']),
            'calibration_bins': len(eligible_counts),
            'min_bin_size': min(eligible_counts),
            'expected_calibration_error': curve['expected_calibration_error'],
            'max_calibration_error': curve['max_deviation'],
            'calibration_coverage': curve['calibration_coverage'],
            'method': method_name,
            'model_version': next(iter(versions)),
            'validation_start': min(prediction_times).isoformat(),
            'validation_end': max(prediction_times).isoformat(),
            'league_ids': [league_id],
        }

    def generate_report(self) -> str:
        lines = ["BETBOY V3 - BACKTEST", f"Recorded predictions: {len(self.predictions)}"]
        for market in ('match_result', 'btts', 'over_25'):
            metrics = self.calculate_accuracy(market)
            if 'error' in metrics:
                continue
            roi = metrics['roi']
            lines.append(f"{market}: accuracy {metrics['accuracy'] * 100:.1f}%")
            lines.append(
                f"{market}: ROI {roi * 100:.1f}% ({metrics['total_staked']} priced)"
                if roi is not None else f"{market}: ROI n/a (no historical prices)"
            )
        return "\n".join(lines)


class BetBoyV3Predictor:
    """Result classifier plus independent-Poisson xG baselines."""

    def __init__(self, api_key: str, model_path: str = 'models/result/'):
        self.api_key = api_key
        self.ml_ensemble = MLEnsemble(model_path, target='match_result')
        self.backtest = BacktestingEngine()
        self.ml_ensemble.load_models()

    @staticmethod
    def _required_fixture_number(fixture: Dict, *keys: str) -> float:
        for key in keys:
            if key in fixture and fixture[key] is not None:
                value = _optional_nonnegative(fixture[key])
                if value is None:
                    raise ValueError(f"{key} must be finite and non-negative")
                return value
        raise ValueError(f"Missing required fixture field: {keys[0]}")

    def build_features(self, fixture: Dict) -> MatchFeatures:
        if not isinstance(fixture, dict):
            raise ValueError("fixture must be a mapping")
        aliases = {
            'home_attack_strength': ('home_attack_strength', 'home_attack'),
            'home_defense_strength': ('home_defense_strength', 'home_defense'),
            'away_attack_strength': ('away_attack_strength', 'away_attack'),
            'away_defense_strength': ('away_defense_strength', 'away_defense'),
            'home_form_goals_scored': ('home_form_goals_scored', 'home_form_scored'),
            'home_form_goals_conceded': ('home_form_goals_conceded', 'home_form_conceded'),
            'away_form_goals_scored': ('away_form_goals_scored', 'away_form_scored'),
            'away_form_goals_conceded': ('away_form_goals_conceded', 'away_form_conceded'),
            'home_form_points': ('home_form_points',),
            'away_form_points': ('away_form_points',),
        }
        values = {
            attribute: self._required_fixture_number(fixture, *keys)
            for attribute, keys in aliases.items()
        }
        league_id = fixture.get('league_id')
        if (
            isinstance(league_id, bool)
            or not isinstance(league_id, int)
            or league_id <= 0
        ):
            raise ValueError("league_id must be a positive integer")
        values.update({
            'home_xg_for': self._required_fixture_number(fixture, 'home_xg_for'),
            'home_xg_against': self._required_fixture_number(fixture, 'home_xg_against'),
            'away_xg_for': self._required_fixture_number(fixture, 'away_xg_for'),
            'away_xg_against': self._required_fixture_number(fixture, 'away_xg_against'),
            'league_id': league_id,
        })
        return MatchFeatures(**values)

    def predict(self, fixture: Dict) -> Dict:
        features = self.build_features(fixture)
        result_probabilities = self.ml_ensemble.predict_proba(features.to_array())
        if self.ml_ensemble.classes_.tolist() != [0, 1, 2]:
            raise RuntimeError("Loaded model is not a 1X2 classifier")

        home_xg = features.home_xg_for
        away_xg = features.away_xg_for
        btts_yes = (1.0 - math.exp(-home_xg)) * (1.0 - math.exp(-away_xg)) * 100.0
        total_xg = home_xg + away_xg
        over_25 = (
            1.0 - sum(
                math.exp(-total_xg) * total_xg ** k / math.factorial(k)
                for k in range(3)
            )
        ) * 100.0
        result_selection = ['HOME', 'DRAW', 'AWAY'][int(np.argmax(result_probabilities))]
        btts_selection = 'YES' if btts_yes >= 50.0 else 'NO'
        total_selection = 'OVER' if over_25 >= 50.0 else 'UNDER'
        over_payload = {
            'over_25': round(over_25, 1),
            'under_25': round(100.0 - over_25, 1),
            'probability_unit': 'percent',
            'total_xg': round(total_xg, 2),
            'prediction': total_selection,
            'signal_strength': 'HIGH' if abs(over_25 - 50.0) >= 15.0 else 'LOW',
            'calibrated': False,
        }
        return {
            'match_result': {
                'home_win': round(result_probabilities[0] * 100.0, 1),
                'draw': round(result_probabilities[1] * 100.0, 1),
                'away_win': round(result_probabilities[2] * 100.0, 1),
                'probability_unit': 'percent',
                'prediction': result_selection,
                'signal_strength': 'HIGH' if max(result_probabilities) >= 0.50 else 'LOW',
                'calibrated': False,
            },
            'btts': {
                'yes': round(btts_yes, 1),
                'no': round(100.0 - btts_yes, 1),
                'probability_unit': 'percent',
                'prediction': btts_selection,
                'signal_strength': 'HIGH' if abs(btts_yes - 50.0) >= 15.0 else 'LOW',
                'calibrated': False,
            },
            'over_25': over_payload,
            'over_under': over_payload,
            'calibrated': False,
            'actionable': False,
            'recommendation_type': 'EXPLORATORY_ESTIMATE',
            'model_info': {
                'version': '3.1',
                'ml_used': True,
                'selected_model': next(iter(self.ml_ensemble.models)),
                'features_count': len(features.to_array()),
                'validation_scores': self.ml_ensemble.validation_scores,
                'context_adjustments_active': False,
                'market_price_used': False,
            },
        }


__all__ = [
    'InjuryTracker',
    'FatigueAnalyzer',
    'MotivationAnalyzer',
    'ManagerChangeTracker',
    'MatchFeatures',
    'MLEnsemble',
    'BacktestingEngine',
    'BetBoyV3Predictor',
]
