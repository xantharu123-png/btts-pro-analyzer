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
    
    Ziel: 10,000+ Spiele mit allen Features
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_key}
    
    def collect_season_data(self, league_id: int, season: int) -> pd.DataFrame:
        """
        Sammle alle Spiele einer Saison
        
        Returns DataFrame mit Spielen und Ergebnissen
        """
        print(f"📥 Collecting {league_id} Season {season}...")
        
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
            
            if response.status_code == 200:
                data = response.json()
                fixtures = data.get('response', [])
                print(f"   Found {len(fixtures)} fixtures")
                
                return self._parse_fixtures(fixtures, league_id)
            else:
                print(f"   ⚠️ API Error: {response.status_code}")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            return pd.DataFrame()
    
    def _parse_fixtures(self, fixtures: list, league_id: int) -> pd.DataFrame:
        """Parse fixtures zu DataFrame"""
        rows = []
        
        for fix in fixtures:
            fixture = fix.get('fixture', {})
            teams = fix.get('teams', {})
            goals = fix.get('goals', {})
            score = fix.get('score', {})
            
            home_goals = goals.get('home', 0) or 0
            away_goals = goals.get('away', 0) or 0
            
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
                'fixture_id': fixture.get('id'),
                'date': fixture.get('date'),
                'league_id': league_id,
                'home_team_id': teams.get('home', {}).get('id'),
                'away_team_id': teams.get('away', {}).get('id'),
                'home_team': teams.get('home', {}).get('name'),
                'away_team': teams.get('away', {}).get('name'),
                'home_goals': home_goals,
                'away_goals': away_goals,
                'total_goals': home_goals + away_goals,
                'result': result,
                'result_code': result_code,
                'btts': btts,
                'over_25': over_25,
                'ht_home': score.get('halftime', {}).get('home', 0),
                'ht_away': score.get('halftime', {}).get('away', 0),
            })
        
        return pd.DataFrame(rows)
    
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
        self.df = df.sort_values('date')
        self.team_history = {}
    
    def calculate_features(self) -> pd.DataFrame:
        """Berechne Features für alle Spiele"""
        print("🔧 Calculating features...")
        
        features = []
        
        for idx, row in self.df.iterrows():
            home_id = row['home_team_id']
            away_id = row['away_team_id']
            match_date = row['date']
            
            # Get team history before this match
            home_history = self._get_team_history(home_id, match_date, is_home=True)
            away_history = self._get_team_history(away_id, match_date, is_home=False)
            
            feature_row = {
                # Basic info
                'fixture_id': row['fixture_id'],
                'league_id': row['league_id'],
                
                # Targets
                'result_code': row['result_code'],
                'btts': row['btts'],
                'over_25': row['over_25'],
                'total_goals': row['total_goals'],
                
                # Home team features
                'home_attack_strength': home_history['attack'],
                'home_defense_strength': home_history['defense'],
                'home_form_goals_scored': home_history['form_scored'],
                'home_form_goals_conceded': home_history['form_conceded'],
                'home_form_points': home_history['form_points'],
                'home_xg_for': home_history['attack'] * 1.1,  # Approximation
                'home_xg_against': home_history['defense'] * 0.9,
                
                # Away team features  
                'away_attack_strength': away_history['attack'],
                'away_defense_strength': away_history['defense'],
                'away_form_goals_scored': away_history['form_scored'],
                'away_form_goals_conceded': away_history['form_conceded'],
                'away_form_points': away_history['form_points'],
                'away_xg_for': away_history['attack'] * 0.9,
                'away_xg_against': away_history['defense'] * 1.1,
                
                # H2H (simplified)
                'h2h_home_wins': 0,
                'h2h_draws': 0,
                'h2h_away_wins': 0,
                'h2h_avg_goals': 2.5,
                'h2h_btts_rate': 0.5,
                
                # Placeholders for V3 features (would need more data)
                'home_injury_impact': 0.0,
                'away_injury_impact': 0.0,
                'home_key_players_out': 0,
                'away_key_players_out': 0,
                'home_fatigue_factor': 1.0,
                'away_fatigue_factor': 1.0,
                'home_days_rest': 4,
                'away_days_rest': 4,
                'home_congestion_games': 2,
                'away_congestion_games': 2,
                'home_position': home_history.get('position', 10),
                'away_position': away_history.get('position', 10),
                'home_motivation_score': 1.0,
                'away_motivation_score': 1.0,
                'home_in_relegation': 0,
                'away_in_relegation': 0,
                'home_in_title_race': 0,
                'away_in_title_race': 0,
                'home_new_manager_boost': 1.0,
                'away_new_manager_boost': 1.0,
                'is_derby': 0,
                'derby_intensity': 1.0,
                'league_avg_goals': 2.75,
                'referee_cards_avg': 4.0,
                'referee_has_data': 0,
                'wind_speed': 0,
                'is_raining': 0,
                'temperature': 15,
            }
            
            features.append(feature_row)
            
            # Update team history after this match
            self._update_team_history(home_id, row, is_home=True)
            self._update_team_history(away_id, row, is_home=False)
        
        print(f"   Generated {len(features)} feature rows")
        return pd.DataFrame(features)
    
    def _get_team_history(self, team_id: int, before_date: str, is_home: bool) -> dict:
        """Hole Team-Historie vor einem bestimmten Datum"""
        if team_id not in self.team_history:
            return {
                'attack': 1.2,
                'defense': 1.2,
                'form_scored': 1.3,
                'form_conceded': 1.2,
                'form_points': 1.5,
                'position': 10
            }
        
        history = self.team_history[team_id]
        
        # Use last 5 matches
        if len(history) < 3:
            return {
                'attack': 1.2,
                'defense': 1.2,
                'form_scored': 1.3,
                'form_conceded': 1.2,
                'form_points': 1.5,
                'position': 10
            }
        
        recent = history[-5:]
        
        scored = [h['scored'] for h in recent]
        conceded = [h['conceded'] for h in recent]
        points = [h['points'] for h in recent]
        
        return {
            'attack': np.mean(scored) if scored else 1.2,
            'defense': np.mean(conceded) if conceded else 1.2,
            'form_scored': np.mean(scored[-3:]) if len(scored) >= 3 else 1.3,
            'form_conceded': np.mean(conceded[-3:]) if len(conceded) >= 3 else 1.2,
            'form_points': np.mean(points[-5:]) if points else 1.5,
            'position': 10  # Would need standings data
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


def train_models(api_key: str = None, use_sample_data: bool = True):
    """
    Hauptfunktion zum Trainieren der Modelle
    """
    print("=" * 60)
    print("🚀 BETBOY V3.0 - ML TRAINING")
    print("=" * 60)
    
    # Option 1: Sammle echte Daten
    if api_key and not use_sample_data:
        collector = HistoricalDataCollector(api_key)
        
        # Top 5 Ligen, letzte 2 Saisons
        leagues = [39, 78, 140, 135, 61]  # PL, BL, LL, SA, L1
        seasons = [2024, 2023]
        
        raw_data = collector.collect_multiple_leagues(leagues, seasons)
        
        if raw_data.empty:
            print("⚠️ Keine Daten gesammelt - nutze Sample Data")
            use_sample_data = True
    
    # Option 2: Generiere Sample-Daten für Demo
    if use_sample_data:
        print("📊 Generating sample training data...")
        raw_data = generate_sample_data(n_matches=5000)
    
    print(f"\n📈 Total matches: {len(raw_data)}")
    
    # Feature Engineering
    engineer = FeatureEngineer(raw_data)
    features_df = engineer.calculate_features()
    
    # Prepare training data
    feature_columns = [
        'home_attack_strength', 'home_defense_strength',
        'away_attack_strength', 'away_defense_strength',
        'home_form_goals_scored', 'home_form_goals_conceded',
        'away_form_goals_scored', 'away_form_goals_conceded',
        'home_form_points', 'away_form_points',
        'home_xg_for', 'home_xg_against',
        'away_xg_for', 'away_xg_against',
        'h2h_home_wins', 'h2h_draws', 'h2h_away_wins',
        'h2h_avg_goals', 'h2h_btts_rate',
        'home_injury_impact', 'away_injury_impact',
        'home_key_players_out', 'away_key_players_out',
        'home_fatigue_factor', 'away_fatigue_factor',
        'home_days_rest', 'away_days_rest',
        'home_congestion_games', 'away_congestion_games',
        'home_position', 'away_position',
        'home_motivation_score', 'away_motivation_score',
        'home_in_relegation', 'away_in_relegation',
        'home_in_title_race', 'away_in_title_race',
        'home_new_manager_boost', 'away_new_manager_boost',
        'is_derby', 'derby_intensity',
        'league_avg_goals', 'referee_cards_avg', 'referee_has_data',
        'wind_speed', 'is_raining', 'temperature',
    ]
    
    X = features_df[feature_columns].values
    y_result = features_df['result_code'].values
    y_btts = features_df['btts'].values
    y_over25 = features_df['over_25'].values
    
    print(f"\n🎯 Training data shape: {X.shape}")
    
    # Train ML Ensemble
    print("\n" + "=" * 40)
    print("TRAINING MATCH RESULT MODEL")
    print("=" * 40)
    
    ml_result = MLEnsemble('models/result/')
    ml_result.train(X, y_result, target='match_result')
    ml_result.save_models()
    
    print("\n" + "=" * 40)
    print("TRAINING BTTS MODEL")
    print("=" * 40)
    
    ml_btts = MLEnsemble('models/btts/')
    ml_btts.train(X, y_btts, target='btts')
    ml_btts.save_models()
    
    print("\n" + "=" * 40)
    print("TRAINING OVER 2.5 MODEL")
    print("=" * 40)
    
    ml_over = MLEnsemble('models/over25/')
    ml_over.train(X, y_over25, target='over_25')
    ml_over.save_models()
    
    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE!")
    print("=" * 60)
    print("\nModels saved to:")
    print("  - models/result/")
    print("  - models/btts/")
    print("  - models/over25/")


def generate_sample_data(n_matches: int = 5000) -> pd.DataFrame:
    """
    Generiere realistische Sample-Daten für Training
    
    Basiert auf echten Fußball-Statistiken
    """
    np.random.seed(42)
    
    rows = []
    
    # Realistische Verteilungen
    # Home win: ~46%, Draw: ~26%, Away: ~28%
    # BTTS: ~52%
    # Over 2.5: ~50%
    
    for i in range(n_matches):
        # Generate realistic scores
        home_strength = np.random.normal(1.3, 0.3)
        away_strength = np.random.normal(1.1, 0.3)
        
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
    print(f"\n📊 Sample Data Statistics:")
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
    
    # Train with sample data if no API key
    train_models(api_key=api_key, use_sample_data=(api_key is None))
