"""
Advanced BTTS Analyzer with Machine Learning
Combines multiple approaches for maximum accuracy
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

from data_engine import DataEngine

try:
    from weather_analyzer import WeatherAnalyzer
    WEATHER_AVAILABLE = True
except ImportError:
    WEATHER_AVAILABLE = False
    print("⚠️ Weather module not available - install if you want weather analysis")


class AdvancedBTTSAnalyzer:
    """
    Pro-level BTTS Analyzer with:
    - Machine Learning predictions
    - Ensemble approach
    - Form analysis
    - Head-to-head
    - Confidence scoring
    """
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "btts_data.db", 
                 weather_api_key: Optional[str] = None, api_football_key: Optional[str] = None):
        self.engine = DataEngine(api_key, db_path)
        self.db_path = db_path
        
        # Store api_football_key for use in other components
        self.api_football_key = api_football_key
        
        # Weather Analyzer
        if WEATHER_AVAILABLE and weather_api_key:
            self.weather = WeatherAnalyzer(weather_api_key)
            print("✅ Weather analysis enabled!")
        else:
            self.weather = None
            if not WEATHER_AVAILABLE:
                print("⚠️ Weather module not available")
            elif not weather_api_key:
                print("⚠️ Weather API key not provided")
        
        # ML Models
        self.ml_model = None
        self.scaler = StandardScaler()
        self.model_trained = False
        
        # Weights for ensemble
        self.weights = {
            'ml_model': 0.40,
            'statistical': 0.30,
            'form': 0.20,
            'h2h': 0.10
        }
        
        # Load or train model
        self.load_or_train_model()
    
    def prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare training data from historical matches
        Returns: (X, y) where X is features and y is labels (1=BTTS, 0=No BTTS)
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get all finished matches with team stats
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
            WHERE m.status = 'FINISHED'
                AND hs.matches_played >= 5
                AND aws.matches_played >= 5
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            print("⚠️ No training data available")
            return np.array([]), np.array([])
        
        # Feature engineering
        features = []
        labels = []
        
        for _, row in df.iterrows():
            feature_vector = [
                row['home_btts_rate'],
                row['away_btts_rate'],
                row['home_goals_scored'],
                row['away_goals_scored'],
                row['home_goals_conceded'],
                row['away_goals_conceded'],
                (row['home_btts_rate'] + row['away_btts_rate']) / 2,  # Combined BTTS
                row['home_goals_scored'] + row['away_goals_conceded'],  # Expected home goals
                row['away_goals_scored'] + row['home_goals_conceded'],  # Expected away goals
                row['home_wins'] / row['home_matches'] if row['home_matches'] > 0 else 0,
                row['away_wins'] / row['away_matches'] if row['away_matches'] > 0 else 0,
            ]
            
            features.append(feature_vector)
            labels.append(row['btts'])
        
        X = np.array(features)
        y = np.array(labels)
        
        print(f"📊 Training data: {len(X)} matches")
        print(f"   BTTS: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
        print(f"   No BTTS: {len(y)-sum(y)} ({(len(y)-sum(y))/len(y)*100:.1f}%)")
        
        return X, y
    
    def train_model(self):
        """Train the Random Forest model"""
        print("\n🤖 Training Machine Learning Model...")
        
        X, y = self.prepare_training_data()
        
        if len(X) == 0:
            print("⚠️ Cannot train model - no data available")
            return
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Random Forest
        self.ml_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        )
        
        self.ml_model.fit(X_scaled, y)
        
        # Cross-validation
        cv_scores = cross_val_score(self.ml_model, X_scaled, y, cv=5)
        
        print(f"✅ Model trained successfully")
        print(f"   Accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std() * 2:.3f})")
        
        # Feature importance
        feature_names = [
            'Home BTTS%', 'Away BTTS%', 'Home Goals Avg', 'Away Goals Avg',
            'Home Conceded Avg', 'Away Conceded Avg', 'Combined BTTS%',
            'Expected Home Goals', 'Expected Away Goals', 'Home Win%', 'Away Win%'
        ]
        
        importances = self.ml_model.feature_importances_
        top_features = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:5]
        
        print(f"\n   Top 5 Features:")
        for name, importance in top_features:
            print(f"   - {name}: {importance:.3f}")
        
        self.model_trained = True
        
        # Save model
        self.save_model()
    
    def save_model(self):
        """Save trained model to disk"""
        model_path = Path("ml_model.pkl")
        scaler_path = Path("scaler.pkl")
        
        with open(model_path, 'wb') as f:
            pickle.dump(self.ml_model, f)
        
        with open(scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
        
        print(f"💾 Model saved to {model_path}")
    
    def load_model(self) -> bool:
        """Load trained model from disk"""
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
            print("✅ ML Model loaded from disk")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to load model: {e}")
            return False
    
    def load_or_train_model(self):
        """Load existing model or train new one"""
        if not self.load_model():
            print("📚 No existing model found. Training new model...")
            self.train_model()
    
    def ml_predict(self, features: List[float]) -> Tuple[float, float]:
        """
        Get ML prediction for BTTS
        Returns: (probability, confidence)
        """
        if not self.model_trained or self.ml_model is None:
            return 0.5, 0.0
        
        X = np.array([features])
        X_scaled = self.scaler.transform(X)
        
        # Get probability
        proba = self.ml_model.predict_proba(X_scaled)[0][1]  # Probability of BTTS=1
        
        # Confidence based on tree agreement
        # Get predictions from all trees
        tree_predictions = np.array([tree.predict(X_scaled)[0] for tree in self.ml_model.estimators_])
        agreement = np.abs(tree_predictions.mean() - 0.5) * 2  # 0 to 1 scale
        
        return proba, agreement
    
    def statistical_predict(self, home_btts: float, away_btts: float, 
                          home_goals: float, away_goals: float,
                          home_conceded: float, away_conceded: float) -> float:
        """
        Statistical prediction based on team stats
        """
        # Combined BTTS rate with weighting
        combined_btts = (home_btts + away_btts) / 2
        
        # Goal expectation bonus
        expected_home_goals = (home_goals + away_conceded) / 2
        expected_away_goals = (away_goals + home_conceded) / 2
        
        goal_bonus = 0
        if expected_home_goals >= 1.0 and expected_away_goals >= 1.0:
            goal_bonus = 10  # Both likely to score
        
        # Final probability
        probability = min(combined_btts + goal_bonus, 95.0)
        
        return probability
    
    def analyze_match(self, home_team_id: int, away_team_id: int, 
                     league_code: str) -> Dict:
        """
        Complete analysis of a match
        Returns comprehensive analysis with multiple predictions
        """
        # Get team stats
        home_stats = self.engine.get_team_stats(home_team_id, league_code, 'home')
        away_stats = self.engine.get_team_stats(away_team_id, league_code, 'away')
        
        if not home_stats or not away_stats:
            return {'error': 'Insufficient data for teams'}
        
        # Get recent form
        home_form = self.engine.get_recent_form(home_team_id, league_code, 'home', 5)
        away_form = self.engine.get_recent_form(away_team_id, league_code, 'away', 5)
        
        # Get head-to-head
        h2h = self.engine.calculate_head_to_head(home_team_id, away_team_id)
        
        # NEW: Get rest days analysis
        home_rest = self.engine.get_rest_days(home_team_id, league_code)
        away_rest = self.engine.get_rest_days(away_team_id, league_code)
        
        # NEW: Get momentum analysis
        home_momentum = self.engine.get_momentum(home_team_id, league_code, 'home')
        away_momentum = self.engine.get_momentum(away_team_id, league_code, 'away')
        
        # NEW: Get motivation factor
        home_motivation = self.engine.get_motivation_factor(home_team_id, league_code)
        away_motivation = self.engine.get_motivation_factor(away_team_id, league_code)
        
        # Prepare features for ML
        ml_features = [
            home_stats['btts_rate'],
            away_stats['btts_rate'],
            home_stats['avg_goals_scored'],
            away_stats['avg_goals_scored'],
            home_stats['avg_goals_conceded'],
            away_stats['avg_goals_conceded'],
            (home_stats['btts_rate'] + away_stats['btts_rate']) / 2,
            home_stats['avg_goals_scored'] + away_stats['avg_goals_conceded'],
            away_stats['avg_goals_scored'] + home_stats['avg_goals_conceded'],
            home_stats['wins'] / home_stats['matches_played'] if home_stats['matches_played'] > 0 else 0,
            away_stats['wins'] / away_stats['matches_played'] if away_stats['matches_played'] > 0 else 0,
        ]
        
        # Get predictions
        ml_prob, ml_confidence = self.ml_predict(ml_features)
        stat_prob = self.statistical_predict(
            home_stats['btts_rate'], away_stats['btts_rate'],
            home_stats['avg_goals_scored'], away_stats['avg_goals_scored'],
            home_stats['avg_goals_conceded'], away_stats['avg_goals_conceded']
        )
        
        # Form-based adjustment
        form_prob = (home_form['btts_rate'] + away_form['btts_rate']) / 2
        
        # H2H-based adjustment
        # H2H-based adjustment with TIME WEIGHTING (recent matches more important!)
        h2h_prob = h2h.get('weighted_btts_rate', h2h.get('btts_rate', stat_prob)) if h2h['matches_played'] >= 3 else stat_prob
        
        # NEW: Apply rest days factor
        rest_factor = (home_rest['fatigue_factor'] + away_rest['fatigue_factor']) / 2
        
        # NEW: Apply momentum bonus
        momentum_bonus = (home_momentum['momentum_bonus'] + away_momentum['momentum_bonus']) / 2
        
        # NEW: Apply motivation factor
        motivation_adjustment = (home_motivation['btts_adjustment'] + away_motivation['btts_adjustment']) / 2
        
        # NEW: Weather analysis
        weather_adjustment = 0
        weather_data = None
        if self.weather:
            try:
                home_weather = self.weather.get_weather(home_stats['team_name'])
                if home_weather:
                    weather_adjustment = home_weather['btts_adjustment']
                    weather_data = home_weather
            except Exception as e:
                print(f"⚠️ Weather API error: {e}")
        
        # NEW: Advanced Stats (Injuries, H2H Deep, etc.)
        advanced_adjustment = 0
        advanced_data = None
        if hasattr(self.engine, 'advanced_stats') and self.engine.advanced_stats:
            try:
                advanced_data = self.engine.get_advanced_match_stats(
                    home_team_id, 
                    away_team_id
                )
                
                # Apply injury impact
                if advanced_data.get('injuries_available'):
                    advanced_adjustment += advanced_data.get('injury_impact', 0)
                
                # Apply H2H deep adjustment
                if advanced_data.get('h2h_deep'):
                    advanced_adjustment += advanced_data['h2h_deep'].get('btts_adjustment', 0)
                
            except Exception as e:
                print(f"⚠️ Advanced Stats error: {e}")
        
        # Ensemble prediction with new factors
        base_ensemble = (
            self.weights['ml_model'] * ml_prob * 100 +
            self.weights['statistical'] * stat_prob +
            self.weights['form'] * form_prob +
            self.weights['h2h'] * h2h_prob
        )
        
        # Apply enhancement factors
        enhanced_prob = base_ensemble * rest_factor  # Multiply by fatigue
        enhanced_prob += momentum_bonus  # Add momentum
        enhanced_prob += motivation_adjustment  # Add motivation
        enhanced_prob += weather_adjustment  # Add weather
        enhanced_prob += advanced_adjustment  # Add injuries, h2h deep, etc.
        
        # Ensure reasonable bounds
        ensemble_prob = max(20, min(enhanced_prob, 95))
        
        # Calculate overall confidence
        confidence_factors = []
        
        # Data availability
        if home_stats['matches_played'] >= 10 and away_stats['matches_played'] >= 10:
            confidence_factors.append(0.9)
        else:
            confidence_factors.append(0.6)
        
        # Form availability
        if home_form['matches'] >= 5 and away_form['matches'] >= 5:
            confidence_factors.append(0.9)
        else:
            confidence_factors.append(0.7)
        
        # H2H availability
        if h2h['matches_played'] >= 5:
            confidence_factors.append(0.9)
        elif h2h['matches_played'] >= 3:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.5)
        
        # ML confidence
        confidence_factors.append(ml_confidence)
        
        # Agreement between methods
        predictions = [ml_prob * 100, stat_prob, form_prob, h2h_prob]
        std_dev = np.std(predictions)
        if std_dev < 10:
            confidence_factors.append(0.9)
        elif std_dev < 20:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.5)
        
        overall_confidence = np.mean(confidence_factors) * 100
        
        # Determine confidence level
        if overall_confidence >= 85:
            confidence_level = "🔥 VERY HIGH"
        elif overall_confidence >= 70:
            confidence_level = "✅ HIGH"
        elif overall_confidence >= 55:
            confidence_level = "👍 MEDIUM"
        else:
            confidence_level = "⚠️ LOW"
        
        # Recommendation
        if ensemble_prob >= 75 and overall_confidence >= 70:
            recommendation = "🔥 TOP TIP"
        elif ensemble_prob >= 65 and overall_confidence >= 60:
            recommendation = "✅ STRONG"
        elif ensemble_prob >= 55:
            recommendation = "👍 GOOD"
        else:
            recommendation = "⚠️ AVOID"
        
        return {
            'ensemble_probability': round(ensemble_prob, 1),
            'ml_probability': round(ml_prob * 100, 1),
            'statistical_probability': round(stat_prob, 1),
            'form_probability': round(form_prob, 1),
            'h2h_probability': round(h2h_prob, 1),
            'confidence': round(overall_confidence, 1),
            'confidence_level': confidence_level,
            'recommendation': recommendation,
            'home_stats': home_stats,
            'away_stats': away_stats,
            'home_form': home_form,
            'away_form': away_form,
            'h2h': h2h,
            'enhancements': {
                'rest_days': {
                    'home': home_rest,
                    'away': away_rest,
                    'factor': round(rest_factor, 3)
                },
                'momentum': {
                    'home': home_momentum,
                    'away': away_momentum,
                    'bonus': round(momentum_bonus, 1)
                },
                'motivation': {
                    'home': home_motivation,
                    'away': away_motivation,
                    'adjustment': round(motivation_adjustment, 1)
                },
                'weather': weather_data if weather_data else {
                    'enabled': False,
                    'message': 'Weather analysis not enabled'
                },
                'advanced': advanced_data if advanced_data else {
                    'enabled': False,
                    'message': 'Advanced stats not available'
                }
            },
            'details': {
                'expected_home_goals': round(home_stats['avg_goals_scored'] + away_stats['avg_goals_conceded'], 2) / 2,
                'expected_away_goals': round(away_stats['avg_goals_scored'] + home_stats['avg_goals_conceded'], 2) / 2,
                'expected_total_goals': round(
                    (home_stats['avg_goals_scored'] + away_stats['avg_goals_scored'] +
                     home_stats['avg_goals_conceded'] + away_stats['avg_goals_conceded']) / 2, 1
                )
            }
        }
    
    def get_upcoming_matches(self, league_code: str, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming matches using API-Football
        
        Returns list of upcoming fixtures for the specified league
        """
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
                # Convert to old format for compatibility
                matches = []
                for fixture in fixtures:
                    matches.append({
                        'fixture_id': fixture['fixture_id'],
                        'date': fixture['date'],
                        'homeTeam': {
                            'id': fixture['home_team_id'],
                            'name': fixture['home_team']
                        },
                        'awayTeam': {
                            'id': fixture['away_team_id'],
                            'name': fixture['away_team']
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
        """
        Analyze all upcoming matches and return recommendations
        """
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
                # Parse date - handle different formats
                try:
                    date_str = match.get('date', match.get('utcDate', ''))
                    if 'T' in date_str:
                        date_obj = datetime.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S')
                        formatted_date = date_obj.strftime('%d.%m.%Y %H:%M')
                    else:
                        formatted_date = date_str
                except:
                    formatted_date = str(match.get('date', 'Unknown'))
                
                results.append({
                    'Date': formatted_date,
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
                    '_analysis': analysis  # Full analysis for detail view
                })
        
        if not results:
            print("⚠️ No matches meet the criteria")
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        df = df.sort_values('BTTS %', ascending=False)
        
        print(f"✅ Found {len(results)} recommendations")
        
        return df


if __name__ == "__main__":
    print("=== Advanced BTTS Analyzer Test ===\n")
    
    analyzer = AdvancedBTTSAnalyzer(api_key='ef8c2eb9be6b43fe8353c99f51904c0f')
    
    # Analyze upcoming Bundesliga matches
    recommendations = analyzer.analyze_upcoming_matches('BL1', days_ahead=7, min_probability=60.0)
    
    if not recommendations.empty:
        print("\n" + "="*80)
        print("📊 TOP BTTS RECOMMENDATIONS")
        print("="*80)
        print(recommendations.drop('_analysis', axis=1).to_string(index=False))
    
    print("\n=== Test Complete ===")
