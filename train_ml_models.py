"""
BETBOY V3.0 - ML TRAINING SCRIPT
=================================

Dieses Skript trainiert die ML-Modelle mit historischen Daten.

USAGE:
1. Sammle historische Daten (oder nutze API-Football)
2. python train_ml_models.py
3. Modelle werden in /models/ gespeichert

REQUIREMENTS:
pip install scikit-learn xgboost pandas numpy requests joblib
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import json
import os
import time
from typing import Optional

# Import our V3 engine
from betboy_v3_ml_engine import (
    BetBoyV3Predictor,
    MatchFeatures,
    MLEnsemble,
    BacktestingEngine
)


class HistoricalDataCollector:
    """
    Sammelt historische Daten für ML-Training
    
    Collects historical fixtures; required sample size is enforced by training.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key}
        self.last_error = None
    
    def collect_season_data(self, league_id: int, season: int) -> pd.DataFrame:
        """
        Sammle alle Spiele einer Saison
        
        Returns DataFrame mit Spielen und Ergebnissen
        """
        if (
            isinstance(league_id, bool)
            or not isinstance(league_id, int)
            or league_id <= 0
            or isinstance(season, bool)
            or not isinstance(season, int)
            or not 1900 <= season <= 2100
        ):
            raise ValueError("league_id and season must be valid integers")
        self.last_error = None
        print(f"Collecting {league_id} season {season}...")
        
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={
                    'league': league_id,
                    'season': season,
                    'status': 'FT'  # Nur beendete Spiele
                },
                timeout=30
            )
            
            if response.status_code != 200:
                self.last_error = f"HTTP {response.status_code}"
                print(f"WARNING: API status {response.status_code}")
                return pd.DataFrame()
            data = response.json()
            if not isinstance(data, dict):
                self.last_error = "invalid provider payload"
                return pd.DataFrame()
            if data.get('errors'):
                self.last_error = str(data['errors'])
                return pd.DataFrame()
            fixtures = data.get('response')
            if not isinstance(fixtures, list):
                self.last_error = "invalid fixtures payload"
                return pd.DataFrame()
            print(f"   Found {len(fixtures)} fixtures")
            return self._parse_fixtures(fixtures, league_id)
                
        except (requests.RequestException, ValueError, TypeError) as exc:
            self.last_error = type(exc).__name__
            print(f"WARNING: {exc}")
            return pd.DataFrame()
    
    def _parse_fixtures(self, fixtures: list, league_id: int) -> pd.DataFrame:
        """Parse fixtures zu DataFrame"""
        rows = []
        if not isinstance(fixtures, list):
            return pd.DataFrame()
        for fix in fixtures:
            if not isinstance(fix, dict):
                continue
            fixture = fix.get('fixture', {})
            teams = fix.get('teams', {})
            goals = fix.get('goals', {})
            score = fix.get('score', {})
            if not all(isinstance(value, dict) for value in (fixture, teams, goals, score)):
                continue
            home_team = teams.get('home')
            away_team = teams.get('away')
            halftime = score.get('halftime')
            league = fix.get('league')
            if (
                not isinstance(home_team, dict)
                or not isinstance(away_team, dict)
                or not isinstance(league, dict)
                or halftime is not None and not isinstance(halftime, dict)
            ):
                continue
            
            home_goals = goals.get('home')
            away_goals = goals.get('away')
            home_team_id = home_team.get('id')
            away_team_id = away_team.get('id')
            fixture_id = fixture.get('id')
            fixture_date = fixture.get('date')
            if not isinstance(fixture_date, str) or not fixture_date.strip():
                continue
            try:
                parsed_date = datetime.fromisoformat(
                    fixture_date.replace('Z', '+00:00')
                )
            except ValueError:
                continue
            if parsed_date.tzinfo is None:
                continue
            if (
                isinstance(home_goals, bool)
                or isinstance(away_goals, bool)
                or not isinstance(home_goals, int)
                or not isinstance(away_goals, int)
                or home_goals < 0
                or away_goals < 0
                or home_goals > 30
                or away_goals > 30
                or isinstance(home_team_id, bool)
                or isinstance(away_team_id, bool)
                or not isinstance(home_team_id, int)
                or not isinstance(away_team_id, int)
                or home_team_id <= 0
                or away_team_id <= 0
                or home_team_id == away_team_id
                or isinstance(fixture_id, bool)
                or not isinstance(fixture_id, int)
                or fixture_id <= 0
                or isinstance(league.get('id'), bool)
                or league.get('id') != league_id
            ):
                continue
            home_name = home_team.get('name')
            away_name = away_team.get('name')
            if (
                not isinstance(home_name, str)
                or not home_name.strip()
                or not isinstance(away_name, str)
                or not away_name.strip()
            ):
                continue
            
            # Determine result
            if home_goals > away_goals:
                result = 'HOME'
                result_code = 0
            elif home_goals == away_goals:
                result = 'DRAW'
                result_code = 1
            else:
                result = 'AWAY'
                result_code = 2
            
            btts = 1 if (home_goals > 0 and away_goals > 0) else 0
            over_25 = 1 if (home_goals + away_goals) > 2.5 else 0
            
            rows.append({
                'fixture_id': fixture_id,
                'date': parsed_date.isoformat(),
                'league_id': league_id,
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'home_team': home_name.strip(),
                'away_team': away_name.strip(),
                'home_goals': home_goals,
                'away_goals': away_goals,
                'total_goals': home_goals + away_goals,
                'result': result,
                'result_code': result_code,
                'btts': btts,
                'over_25': over_25,
                'ht_home': halftime.get('home') if halftime else None,
                'ht_away': halftime.get('away') if halftime else None,
            })
        
        parsed = pd.DataFrame(rows)
        if parsed.empty:
            return parsed
        return parsed.drop_duplicates(subset=['fixture_id'], keep='last')
    
    def collect_multiple_leagues(self, leagues: list, seasons: list) -> pd.DataFrame:
        """Sammle Daten aus mehreren Ligen und Saisons"""
        all_data = []
        
        for league_id in leagues:
            for season in seasons:
                df = self.collect_season_data(league_id, season)
                if not df.empty:
                    all_data.append(df)
                time.sleep(1)  # Rate limiting
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()


class FeatureEngineer:
    """
    Berechnet Features aus historischen Daten
    
    Für jedes Spiel: Was war die Form/Stärke VOR dem Spiel?
    """
    
    def __init__(self, df: pd.DataFrame):
        sort_columns = ['date']
        if 'fixture_id' in df.columns:
            sort_columns.append('fixture_id')
        self.df = df.sort_values(sort_columns, kind='mergesort')
        self.team_history = {}
    
    def calculate_features(self) -> pd.DataFrame:
        """Berechne Features für alle Spiele"""
        print("Calculating features...")
        working = self.df.copy()
        working['_model_day'] = pd.to_datetime(
            working['date'], errors='coerce', utc=True
        ).dt.floor('D')
        working = working.dropna(subset=['_model_day'])
        features = []

        for _, day_rows in working.groupby('_model_day', sort=True):
            for _, row in day_rows.iterrows():
                home_id = row['home_team_id']
                away_id = row['away_team_id']
                match_date = row['date']
                home_history = self._get_team_history(home_id, match_date, is_home=True)
                away_history = self._get_team_history(away_id, match_date, is_home=False)
                if home_history is None or away_history is None:
                    continue

                features.append({
                    'fixture_id': row['fixture_id'],
                    'model_day': row['_model_day'],
                    'league_id': row['league_id'],
                    'result_code': row['result_code'],
                    'btts': row['btts'],
                    'over_25': row['over_25'],
                    'total_goals': row['total_goals'],
                    'home_attack_strength': home_history['attack'],
                    'home_defense_strength': home_history['defense'],
                    'home_form_goals_scored': home_history['form_scored'],
                    'home_form_goals_conceded': home_history['form_conceded'],
                    'home_form_points': home_history['form_points'],
                    'away_attack_strength': away_history['attack'],
                    'away_defense_strength': away_history['defense'],
                    'away_form_goals_scored': away_history['form_scored'],
                    'away_form_goals_conceded': away_history['form_conceded'],
                    'away_form_points': away_history['form_points'],
                })

            # Keep every result from this day invisible until every prediction
            # row for the day has been built.
            for _, row in day_rows.iterrows():
                self._update_team_history(row['home_team_id'], row, is_home=True)
                self._update_team_history(row['away_team_id'], row, is_home=False)

        print(f"   Generated {len(features)} feature rows")
        return pd.DataFrame(features)
    
    def _get_team_history(self, team_id: int, before_date: str, is_home: bool) -> Optional[dict]:
        """Hole Team-Historie vor einem bestimmten Datum"""
        if team_id not in self.team_history:
            return None
        
        history = self.team_history[team_id]
        
        # Use last 5 matches
        if len(history) < 5:
            return None
        
        recent = history[-5:]
        
        scored = [h['scored'] for h in recent]
        conceded = [h['conceded'] for h in recent]
        points = [h['points'] for h in recent]
        
        return {
            'attack': float(np.mean(scored)),
            'defense': float(np.mean(conceded)),
            'form_scored': float(np.mean(scored[-3:])),
            'form_conceded': float(np.mean(conceded[-3:])),
            'form_points': float(np.mean(points)),
        }
    
    def _update_team_history(self, team_id: int, row: pd.Series, is_home: bool):
        """Update Team-Historie nach einem Spiel"""
        if team_id not in self.team_history:
            self.team_history[team_id] = []
        
        if is_home:
            scored = row['home_goals']
            conceded = row['away_goals']
        else:
            scored = row['away_goals']
            conceded = row['home_goals']
        
        if scored > conceded:
            points = 3
        elif scored == conceded:
            points = 1
        else:
            points = 0
        
        self.team_history[team_id].append({
            'scored': scored,
            'conceded': conceded,
            'points': points,
            'date': row['date']
        })


def train_models(api_key: str = None, use_sample_data: bool = False):
    """
    Hauptfunktion zum Trainieren der Modelle
    """
    print("=" * 60)
    print("BETBOY V3.0 - ML TRAINING")
    print("=" * 60)
    
    if use_sample_data:
        raise ValueError(
            "Synthetic data may be used in tests, but never to train persisted models"
        )
    if not api_key:
        raise ValueError("API_FOOTBALL_KEY is required for historical training data")

    if api_key:
        collector = HistoricalDataCollector(api_key)
        
        # Top 5 Ligen, letzte 2 Saisons
        leagues = [39, 78, 140, 135, 61]  # PL, BL, LL, SA, L1
        from season_utils import current_season_start_year
        current_season = current_season_start_year()
        seasons = [current_season - 1, current_season - 2]
        
        raw_data = collector.collect_multiple_leagues(leagues, seasons)
        
        if raw_data.empty:
            raise RuntimeError("No historical fixtures were collected")
    
    print(f"\nTotal matches: {len(raw_data)}")
    
    # Feature Engineering
    engineer = FeatureEngineer(raw_data)
    features_df = engineer.calculate_features()
    if len(features_df) < 100:
        raise RuntimeError(
            "Fewer than 100 fixtures have at least five prior matches for both teams"
        )
    
    # Prepare training data
    feature_columns = MatchFeatures.feature_names()
    
    X = features_df[feature_columns].values
    y_result = features_df['result_code'].values
    y_btts = features_df['btts'].values
    y_over25 = features_df['over_25'].values
    # Calendar days per row: keeps every train/validation/holdout boundary
    # day-grouped inside MLEnsemble (handbook rule 7).
    feature_dates = features_df['model_day'].values
    
    print(f"\nTraining data shape: {X.shape}")
    
    # Train ML Ensemble
    print("\n" + "=" * 40)
    print("TRAINING MATCH RESULT MODEL")
    print("=" * 40)
    
    ml_result = MLEnsemble('models/result/')
    ml_result.train(X, y_result, target='match_result', dates=feature_dates)
    if not ml_result.is_trained:
        raise RuntimeError("Match-result ensemble failed the chronological Brier gate")
    ml_result.save_models()
    
    print("\n" + "=" * 40)
    print("TRAINING BTTS MODEL")
    print("=" * 40)
    
    ml_btts = MLEnsemble('models/btts/')
    ml_btts.train(X, y_btts, target='btts', dates=feature_dates)
    if not ml_btts.is_trained:
        raise RuntimeError("BTTS ensemble failed the chronological Brier gate")
    ml_btts.save_models()
    
    print("\n" + "=" * 40)
    print("TRAINING OVER 2.5 MODEL")
    print("=" * 40)
    
    ml_over = MLEnsemble('models/over25/')
    ml_over.train(X, y_over25, target='over_25', dates=feature_dates)
    if not ml_over.is_trained:
        raise RuntimeError("Over-2.5 ensemble failed the chronological Brier gate")
    ml_over.save_models()
    
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print("\nModels saved to:")
    print("  - models/result/")
    print("  - models/btts/")
    print("  - models/over25/")


def generate_sample_data(n_matches: int = 5000) -> pd.DataFrame:
    """
    Generate synthetic fixtures for isolated tests only.

    The output is not real football data and must never be persisted as a
    production model training set.
    """
    np.random.seed(42)
    
    rows = []
    
    # Realistische Verteilungen
    # Home win: ~46%, Draw: ~26%, Away: ~28%
    # BTTS: ~52%
    # Over 2.5: ~50%
    
    for i in range(n_matches):
        # Generate realistic scores - FIXED: ensure positive values!
        home_strength = max(0.5, np.random.normal(1.3, 0.3))
        away_strength = max(0.4, np.random.normal(1.1, 0.3))
        
        home_goals = np.random.poisson(home_strength)
        away_goals = np.random.poisson(away_strength)
        
        # Cap at realistic values
        home_goals = min(home_goals, 6)
        away_goals = min(away_goals, 5)
        
        if home_goals > away_goals:
            result = 'HOME'
            result_code = 0
        elif home_goals == away_goals:
            result = 'DRAW'
            result_code = 1
        else:
            result = 'AWAY'
            result_code = 2
        
        rows.append({
            'fixture_id': i + 1,
            'date': f"2024-{np.random.randint(1,13):02d}-{np.random.randint(1,29):02d}",
            'league_id': np.random.choice([39, 78, 140, 135, 61]),
            'home_team_id': np.random.randint(1, 100),
            'away_team_id': np.random.randint(100, 200),
            'home_team': f"Team_{np.random.randint(1, 50)}",
            'away_team': f"Team_{np.random.randint(50, 100)}",
            'home_goals': home_goals,
            'away_goals': away_goals,
            'total_goals': home_goals + away_goals,
            'result': result,
            'result_code': result_code,
            'btts': 1 if (home_goals > 0 and away_goals > 0) else 0,
            'over_25': 1 if (home_goals + away_goals) > 2.5 else 0,
            'ht_home': min(home_goals, np.random.poisson(0.6)),
            'ht_away': min(away_goals, np.random.poisson(0.5)),
        })
    
    df = pd.DataFrame(rows)
    
    # Print statistics
    print("\nSample data statistics:")
    print(f"   Home Win: {(df['result'] == 'HOME').mean()*100:.1f}%")
    print(f"   Draw: {(df['result'] == 'DRAW').mean()*100:.1f}%")
    print(f"   Away Win: {(df['result'] == 'AWAY').mean()*100:.1f}%")
    print(f"   BTTS: {df['btts'].mean()*100:.1f}%")
    print(f"   Over 2.5: {df['over_25'].mean()*100:.1f}%")
    print(f"   Avg Goals: {df['total_goals'].mean():.2f}")
    
    return df


if __name__ == "__main__":
    import sys
    
    # Get API key from environment or argument
    api_key = os.environ.get('API_FOOTBALL_KEY')
    
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    
    if not api_key:
        raise SystemExit("API_FOOTBALL_KEY is required; synthetic training is disabled")
    train_models(api_key=api_key, use_sample_data=False)
