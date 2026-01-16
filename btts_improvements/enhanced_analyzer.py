"""
ENHANCED BTTS ANALYZER - VOLLSTÄNDIGE INTEGRATION
==================================================
Kombiniert alle drei Verbesserungen:
1. Dixon-Coles Korrektur (statistische Verbesserung)
2. CLV Tracking (professionelle Validierung)
3. Wetter-Integration (exogene Variablen)

Dieses Modul ersetzt/erweitert den bestehenden AdvancedAnalyzer
mit allen drei von Gemini kritisierten fehlenden Features.
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

# Importiere die neuen Module
from dixon_coles import DixonColesModel, compare_models
from clv_tracker import CLVTracker, CLVAnalyzer
from weather_analyzer import WeatherAnalyzer


class EnhancedBTTSAnalyzer:
    """
    Verbesserter BTTS-Analyzer mit:
    - Dixon-Coles Korrektur für niedrige Ergebnisse
    - CLV Tracking für professionelle Validierung
    - Wetter-Integration für exogene Faktoren
    """
    
    def __init__(self, data_engine, api_key: str = None, 
                 openweather_key: str = None, db_path: str = "btts_data.db"):
        """
        Initialisiere den Enhanced Analyzer
        
        Args:
            data_engine: DataEngine Instanz für API-Daten
            api_key: API-Football Key
            openweather_key: OpenWeatherMap API Key für Wetter
            db_path: Pfad zur Datenbank
        """
        self.engine = data_engine
        self.api_key = api_key
        
        # Initialisiere die drei neuen Module
        self.dixon_coles = DixonColesModel(rho=-0.05)
        self.clv_tracker = CLVTracker(db_path=db_path.replace('.db', '_clv.db'))
        self.weather = WeatherAnalyzer(api_key=openweather_key)
        
        # Gewichtung für Ensemble-Methode
        self.weights = {
            'poisson_dc': 0.35,      # Dixon-Coles Poisson
            'statistical': 0.25,      # Basis-Statistiken
            'form': 0.20,             # Form (letzte 5 Spiele)
            'h2h': 0.10,              # Head-to-Head
            'weather': 0.10           # Wetter-Einfluss
        }
        
        # Liga-Durchschnitte Cache
        self.league_averages = {}
    
    def calculate_team_strength(self, team_stats: Dict, league_avg: Dict,
                               venue: str = 'all') -> Dict:
        """
        Berechne Angriffs- und Verteidigungsstärke relativ zum Liga-Durchschnitt
        """
        if venue == 'home':
            scored = team_stats.get('home_scored', team_stats.get('avg_scored', 1.3))
            conceded = team_stats.get('home_conceded', team_stats.get('avg_conceded', 1.2))
        elif venue == 'away':
            scored = team_stats.get('away_scored', team_stats.get('avg_scored', 1.1))
            conceded = team_stats.get('away_conceded', team_stats.get('avg_conceded', 1.4))
        else:
            scored = team_stats.get('avg_scored', 1.2)
            conceded = team_stats.get('avg_conceded', 1.3)
        
        league_scored = league_avg.get('avg_home_scored', 1.5)
        league_conceded = league_avg.get('avg_away_conceded', 1.2)
        
        attack_strength = scored / league_scored if league_scored > 0 else 1.0
        defense_strength = conceded / league_conceded if league_conceded > 0 else 1.0
        
        return {
            'attack_strength': attack_strength,
            'defense_strength': defense_strength,
            'scored_per_game': scored,
            'conceded_per_game': conceded
        }
    
    def calculate_expected_goals(self, home_strength: Dict, away_strength: Dict,
                                league_avg: Dict, weather_factor: float = 1.0) -> Tuple[float, float]:
        """
        Berechne erwartete Tore (λ_home, μ_away) mit allen Faktoren
        """
        league_home = league_avg.get('avg_home_scored', 1.5)
        league_away = league_avg.get('avg_away_scored', 1.2)
        
        lambda_home = (
            home_strength['attack_strength'] *
            away_strength['defense_strength'] *
            league_home *
            weather_factor *
            1.08  # Heimvorteil
        )
        
        mu_away = (
            away_strength['attack_strength'] *
            home_strength['defense_strength'] *
            league_away *
            weather_factor
        )
        
        lambda_home = max(0.3, min(4.0, lambda_home))
        mu_away = max(0.2, min(3.5, mu_away))
        
        return lambda_home, mu_away
    
    def analyze_match_enhanced(self, home_team_id: int, away_team_id: int,
                              league_code: str, fixture_id: int = None,
                              match_datetime: datetime = None,
                              stadium: str = None, city: str = None) -> Dict:
        """
        VOLLSTÄNDIGE Match-Analyse mit allen Verbesserungen
        """
        # SCHRITT 1: Basis-Daten sammeln
        home_stats = self._get_team_stats_safe(home_team_id, league_code, 'home')
        away_stats = self._get_team_stats_safe(away_team_id, league_code, 'away')
        league_avg = self._get_league_averages(league_code)
        
        home_form = self._get_form_safe(home_team_id, league_code, 'home')
        away_form = self._get_form_safe(away_team_id, league_code, 'away')
        h2h = self._get_h2h_safe(home_team_id, away_team_id)
        
        # SCHRITT 2: Wetter-Analyse
        weather_analysis = {'factor': 1.0, 'details': None}
        
        if stadium or city:
            weather_data = self.weather.get_match_weather_analysis(
                stadium_name=stadium,
                city=city,
                match_datetime=match_datetime
            )
            weather_analysis = {
                'factor': weather_data['impact']['total_factor'],
                'details': weather_data
            }
        
        # SCHRITT 3: Team-Stärken berechnen
        home_strength = self.calculate_team_strength(home_stats, league_avg, 'home')
        away_strength = self.calculate_team_strength(away_stats, league_avg, 'away')
        
        # SCHRITT 4: Expected Goals mit Wetter-Anpassung
        lambda_home, mu_away = self.calculate_expected_goals(
            home_strength, away_strength, league_avg,
            weather_factor=weather_analysis['factor']
        )
        
        # SCHRITT 5: Dixon-Coles Analyse
        dc_analysis = self.dixon_coles.full_analysis(lambda_home, mu_away)
        model_comparison = compare_models(lambda_home, mu_away)
        
        # SCHRITT 6: Ensemble-BTTS-Berechnung
        dc_btts = dc_analysis['btts']['btts_yes']
        stat_btts = (home_stats.get('btts_rate', 50) + away_stats.get('btts_rate', 50)) / 2
        form_btts = (home_form.get('btts_rate', 50) + away_form.get('btts_rate', 50)) / 2
        h2h_btts = h2h.get('btts_rate', 50)
        
        final_btts = (
            dc_btts * self.weights['poisson_dc'] +
            stat_btts * self.weights['statistical'] +
            form_btts * self.weights['form'] +
            h2h_btts * self.weights['h2h']
        )
        
        # Wetter-Anpassung auf BTTS
        if weather_analysis['factor'] < 0.95:
            weather_adjustment = (1 - weather_analysis['factor']) * 10
            final_btts -= weather_adjustment
        
        final_btts = max(25, min(85, final_btts))
        
        # SCHRITT 7: Confidence berechnen
        data_quality = min(100, (home_stats.get('matches_played', 0) + 
                                 away_stats.get('matches_played', 0)) * 3)
        prediction_spread = abs(dc_btts - stat_btts) + abs(dc_btts - form_btts)
        agreement_factor = max(0, 100 - prediction_spread * 2)
        confidence = max(30, min(95, (data_quality * 0.4 + agreement_factor * 0.6)))
        
        # ERGEBNIS
        return {
            'btts_probability': round(final_btts, 1),
            'btts_confidence': round(confidence, 1),
            'btts_recommendation': self._get_btts_recommendation(final_btts, confidence),
            
            'dixon_coles': {
                'btts_yes': round(dc_btts, 1),
                'btts_no': round(dc_analysis['btts']['btts_no'], 1),
                'prob_0_0': round(dc_analysis['btts']['prob_0_0'], 2),
                'rho': self.dixon_coles.rho
            },
            
            'expected_goals': {
                'home': round(lambda_home, 2),
                'away': round(mu_away, 2),
                'total': round(lambda_home + mu_away, 2)
            },
            
            'match_result': {
                'home_win': round(dc_analysis['result']['home_win'], 1),
                'draw': round(dc_analysis['result']['draw'], 1),
                'away_win': round(dc_analysis['result']['away_win'], 1)
            },
            
            'over_under': {
                'over_1_5': round(dc_analysis['over_under']['over_1.5'], 1),
                'over_2_5': round(dc_analysis['over_under']['over_2.5'], 1),
                'over_3_5': round(dc_analysis['over_under']['over_3.5'], 1),
                'under_2_5': round(dc_analysis['over_under']['under_2.5'], 1)
            },
            
            'top_scores': dc_analysis['top_scores'][:5],
            
            'weather': {
                'factor': round(weather_analysis['factor'], 3),
                'adjustment_percent': round((weather_analysis['factor'] - 1) * 100, 1),
                'details': weather_analysis.get('details')
            },
            
            'model_comparison': {
                'standard_poisson_btts': round(model_comparison['btts_comparison']['poisson_btts_yes'], 1),
                'dixon_coles_btts': round(model_comparison['btts_comparison']['dixon_coles_btts_yes'], 1),
                'correction_difference': round(model_comparison['btts_comparison']['difference'], 2)
            },
            
            'components': {
                'dc_poisson': round(dc_btts, 1),
                'statistical': round(stat_btts, 1),
                'form': round(form_btts, 1),
                'h2h': round(h2h_btts, 1)
            },
            
            'team_strength': {
                'home': {
                    'attack': round(home_strength['attack_strength'], 2),
                    'defense': round(home_strength['defense_strength'], 2)
                },
                'away': {
                    'attack': round(away_strength['attack_strength'], 2),
                    'defense': round(away_strength['defense_strength'], 2)
                }
            },
            
            'fixture_id': fixture_id,
            'league_code': league_code,
            'analysis_timestamp': datetime.now().isoformat(),
            'model_version': '2.0_enhanced'
        }
    
    def _get_btts_recommendation(self, probability: float, confidence: float) -> Dict:
        """Generiere BTTS-Empfehlung"""
        if probability >= 65 and confidence >= 60:
            return {'action': 'BTTS YES', 'strength': '⭐⭐⭐ STARK', 'emoji': '🔥'}
        elif probability >= 55 and confidence >= 50:
            return {'action': 'BTTS YES', 'strength': '⭐⭐ MODERAT', 'emoji': '✅'}
        elif probability <= 35 and confidence >= 60:
            return {'action': 'BTTS NO', 'strength': '⭐⭐⭐ STARK', 'emoji': '🔥'}
        elif probability <= 45 and confidence >= 50:
            return {'action': 'BTTS NO', 'strength': '⭐⭐ MODERAT', 'emoji': '✅'}
        else:
            return {'action': 'SKIP', 'strength': '⚠️ UNSICHER', 'emoji': '⏭️'}
    
    def _get_team_stats_safe(self, team_id: int, league_code: str, venue: str) -> Dict:
        """Sichere Team-Stats Abfrage"""
        try:
            stats = self.engine.get_team_stats(team_id, league_code, venue)
            if stats:
                return stats
        except Exception:
            pass
        return {'avg_scored': 1.4, 'avg_conceded': 1.3, 'btts_rate': 55, 'matches_played': 5}
    
    def _get_form_safe(self, team_id: int, league_code: str, venue: str) -> Dict:
        """Sichere Form-Abfrage"""
        try:
            form = self.engine.get_recent_form(team_id, league_code, venue, 5)
            if form:
                return form
        except Exception:
            pass
        return {'btts_rate': 50, 'avg_scored': 1.3, 'avg_conceded': 1.2}
    
    def _get_h2h_safe(self, home_id: int, away_id: int) -> Dict:
        """Sichere H2H-Abfrage"""
        try:
            h2h = self.engine.calculate_head_to_head(home_id, away_id)
            if h2h:
                return h2h
        except Exception:
            pass
        return {'btts_rate': 50, 'avg_goals': 2.5}
    
    def _get_league_averages(self, league_code: str) -> Dict:
        """Hole Liga-Durchschnitte"""
        if league_code in self.league_averages:
            return self.league_averages[league_code]
        
        try:
            stats = self.engine.get_league_stats(league_code)
            if stats:
                self.league_averages[league_code] = stats
                return stats
        except Exception:
            pass
        
        return {'avg_home_scored': 1.5, 'avg_away_scored': 1.2, 'btts_rate': 52}
    
    # CLV TRACKING
    def record_prediction_with_clv(self, analysis: Dict, current_odds: float,
                                   home_team: str, away_team: str) -> int:
        """Speichere Vorhersage für CLV-Tracking"""
        prediction = analysis['btts_recommendation']['action']
        return self.clv_tracker.record_prediction(
            fixture_id=analysis.get('fixture_id', 0),
            home_team=home_team,
            away_team=away_team,
            market_type='BTTS',
            prediction='Yes' if 'YES' in prediction else 'No',
            odds=current_odds,
            model_probability=analysis['btts_probability'],
            confidence=analysis['btts_confidence']
        )
    
    def get_clv_performance(self, days: int = 30) -> Dict:
        """Hole CLV-Performance"""
        return self.clv_tracker.get_clv_statistics(days)
    
    def print_clv_report(self, days: int = 30):
        """Drucke CLV-Report"""
        analyzer = CLVAnalyzer(self.clv_tracker)
        analyzer.print_summary_report(days)


# STANDALONE QUICK ANALYSIS
def quick_btts_analysis(lambda_home: float, mu_away: float, 
                       weather_factor: float = 1.0) -> Dict:
    """Schnelle BTTS-Analyse ohne Datenbank"""
    adj_home = lambda_home * weather_factor
    adj_away = mu_away * weather_factor
    
    model = DixonColesModel(rho=-0.05)
    analysis = model.full_analysis(adj_home, adj_away)
    
    return {
        'expected_goals': {'home': round(adj_home, 2), 'away': round(adj_away, 2)},
        'btts': {'yes': round(analysis['btts']['btts_yes'], 1), 'no': round(analysis['btts']['btts_no'], 1)},
        'result': {
            'home': round(analysis['result']['home_win'], 1),
            'draw': round(analysis['result']['draw'], 1),
            'away': round(analysis['result']['away_win'], 1)
        },
        'over_under': {
            'over_2_5': round(analysis['over_under']['over_2.5'], 1),
            'under_2_5': round(analysis['over_under']['under_2.5'], 1)
        },
        'top_scores': analysis['top_scores'][:5]
    }


if __name__ == '__main__':
    print("=" * 60)
    print("ENHANCED BTTS ANALYZER TEST")
    print("=" * 60)
    
    result = quick_btts_analysis(2.1, 1.3, 1.0)
    
    print(f"\n⚽ Bayern vs Dortmund:")
    print(f"   BTTS Ja: {result['btts']['yes']}%")
    print(f"   BTTS Nein: {result['btts']['no']}%")
    print(f"   Over 2.5: {result['over_under']['over_2_5']}%")
    
    print("\n✅ Enhanced Analyzer geladen!")
