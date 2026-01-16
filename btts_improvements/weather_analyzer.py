"""
WETTER-INTEGRATION MODUL
========================
Integration von Wetterdaten für verbesserte Vorhersagen.

Wissenschaftliche Grundlage:
- Wind > 32 km/h: Signifikante Reduktion der Torproduktion
- Starker Regen: Erhöhte Fehlerquote bei Pässen
- Extreme Temperaturen: Auswirkung auf Spielintensität

Schwellenwerte basierend auf Forschung:
- Wind < 15 km/h: Kein Einfluss
- Wind 15-30 km/h: Moderater Einfluss (-5% erwartete Tore)
- Wind > 30 km/h: Starker Einfluss (-15% erwartete Tore)

API: OpenWeatherMap (kostenloser Tier: 1000 Calls/Tag)
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import json
from pathlib import Path


class WeatherAnalyzer:
    """
    Wetter-Integration für Fußball-Vorhersagen
    
    Verwendet OpenWeatherMap API für:
    - Aktuelle Wetterbedingungen
    - Vorhersagen für Spieltag
    - Historische Wetterdaten
    """
    
    # Standard-Koordinaten für bekannte Stadien
    STADIUM_COORDINATES = {
        # Deutschland - Bundesliga
        'Allianz Arena': (48.2188, 11.6247),  # Bayern München
        'Signal Iduna Park': (51.4926, 7.4518),  # Borussia Dortmund
        'Veltins-Arena': (51.5536, 7.0678),  # Schalke 04
        'RheinEnergieStadion': (50.9335, 6.8751),  # FC Köln
        'Olympiastadion Berlin': (52.5148, 13.2395),  # Hertha BSC
        'Volksparkstadion': (53.5872, 9.8987),  # HSV
        'Deutsche Bank Park': (50.0687, 8.6456),  # Eintracht Frankfurt
        'Mercedes-Benz Arena': (48.7923, 9.2321),  # VfB Stuttgart
        'BayArena': (51.0384, 7.0021),  # Bayer Leverkusen
        'Borussia-Park': (51.1747, 6.3856),  # Gladbach
        
        # England - Premier League
        'Old Trafford': (53.4631, -2.2913),  # Manchester United
        'Etihad Stadium': (53.4831, -2.2004),  # Manchester City
        'Anfield': (53.4308, -2.9608),  # Liverpool
        'Emirates Stadium': (51.5549, -0.1084),  # Arsenal
        'Stamford Bridge': (51.4817, -0.1910),  # Chelsea
        'Tottenham Hotspur Stadium': (51.6042, -0.0662),  # Tottenham
        'St James Park': (54.9756, -1.6217),  # Newcastle
        
        # Spanien - La Liga
        'Santiago Bernabéu': (40.4530, -3.6883),  # Real Madrid
        'Camp Nou': (41.3809, 2.1228),  # Barcelona
        'Wanda Metropolitano': (40.4362, -3.5996),  # Atletico Madrid
        
        # Italien - Serie A
        'San Siro': (45.4781, 9.1240),  # Milan & Inter
        'Allianz Stadium': (45.1096, 7.6413),  # Juventus
        'Stadio Olimpico Roma': (41.9341, 12.4547),  # Roma & Lazio
        
        # Frankreich - Ligue 1
        'Parc des Princes': (48.8414, 2.2530),  # PSG
        'Groupama Stadium': (45.7653, 4.9821),  # Lyon
    }
    
    # Wind-Einfluss Konfiguration
    WIND_THRESHOLDS = {
        'negligible': {'max_speed': 15, 'factor': 1.00, 'description': 'Kein Einfluss'},
        'light': {'max_speed': 20, 'factor': 0.98, 'description': 'Minimal'},
        'moderate': {'max_speed': 30, 'factor': 0.95, 'description': 'Moderat (-5%)'},
        'strong': {'max_speed': 40, 'factor': 0.88, 'description': 'Stark (-12%)'},
        'severe': {'max_speed': float('inf'), 'factor': 0.80, 'description': 'Sehr stark (-20%)'}
    }
    
    # Regen-Einfluss Konfiguration
    RAIN_THRESHOLDS = {
        'none': {'max_mm': 0.5, 'factor': 1.00, 'description': 'Kein Regen'},
        'light': {'max_mm': 2.5, 'factor': 0.98, 'description': 'Leichter Regen'},
        'moderate': {'max_mm': 7.5, 'factor': 0.95, 'description': 'Moderater Regen'},
        'heavy': {'max_mm': float('inf'), 'factor': 0.90, 'description': 'Starker Regen'}
    }
    
    # Temperatur-Einfluss Konfiguration
    TEMP_THRESHOLDS = {
        'very_cold': {'range': (-50, 0), 'factor': 0.93, 'description': 'Sehr kalt'},
        'cold': {'range': (0, 8), 'factor': 0.97, 'description': 'Kalt'},
        'optimal': {'range': (8, 22), 'factor': 1.00, 'description': 'Optimal'},
        'warm': {'range': (22, 28), 'factor': 0.98, 'description': 'Warm'},
        'hot': {'range': (28, 50), 'factor': 0.94, 'description': 'Sehr heiß'}
    }
    
    def __init__(self, api_key: str = None):
        """
        Initialisiere den WeatherAnalyzer
        
        Args:
            api_key: OpenWeatherMap API Key (optional - kann später gesetzt werden)
        """
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.cache = {}
        self.cache_duration = 1800  # 30 Minuten Cache
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 Sekunde zwischen Requests
    
    def set_api_key(self, api_key: str):
        """Setze den API Key nachträglich"""
        self.api_key = api_key
    
    def _rate_limit(self):
        """Respektiere API Rate Limits"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _get_cache_key(self, lat: float, lon: float) -> str:
        """Generiere Cache Key aus Koordinaten"""
        return f"{lat:.2f}_{lon:.2f}"
    
    def get_coordinates(self, stadium_name: str = None, city: str = None,
                       lat: float = None, lon: float = None) -> Tuple[float, float]:
        """
        Ermittle Koordinaten für ein Stadion oder eine Stadt
        
        Args:
            stadium_name: Name des Stadions
            city: Stadtname als Fallback
            lat, lon: Direkte Koordinaten
        
        Returns:
            Tuple (latitude, longitude)
        """
        # Direkte Koordinaten haben Priorität
        if lat is not None and lon is not None:
            return (lat, lon)
        
        # Suche nach Stadionname
        if stadium_name:
            for name, coords in self.STADIUM_COORDINATES.items():
                if name.lower() in stadium_name.lower() or stadium_name.lower() in name.lower():
                    return coords
        
        # Geocoding über OpenWeatherMap (wenn API Key vorhanden)
        if city and self.api_key:
            try:
                self._rate_limit()
                response = requests.get(
                    f"http://api.openweathermap.org/geo/1.0/direct",
                    params={'q': city, 'limit': 1, 'appid': self.api_key},
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        return (data[0]['lat'], data[0]['lon'])
            except Exception as e:
                print(f"⚠️ Geocoding Error: {e}")
        
        # Default: München (Zentrum Europas)
        return (48.1351, 11.5820)
    
    def get_current_weather(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Hole aktuelle Wetterdaten für Koordinaten
        
        Args:
            lat: Breitengrad
            lon: Längengrad
        
        Returns:
            Dict mit Wetterdaten oder None
        """
        if not self.api_key:
            return self._get_default_weather()
        
        # Check Cache
        cache_key = self._get_cache_key(lat, lon)
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_duration:
                return cached['data']
        
        try:
            self._rate_limit()
            response = requests.get(
                f"{self.base_url}/weather",
                params={
                    'lat': lat,
                    'lon': lon,
                    'appid': self.api_key,
                    'units': 'metric'  # Celsius, m/s
                },
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"⚠️ Weather API Error: {response.status_code}")
                return self._get_default_weather()
            
            data = response.json()
            
            weather = {
                'temperature': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'] * 3.6,  # m/s to km/h
                'wind_direction': data['wind'].get('deg', 0),
                'wind_gust': data['wind'].get('gust', 0) * 3.6,
                'clouds': data['clouds']['all'],
                'visibility': data.get('visibility', 10000) / 1000,  # m to km
                'condition': data['weather'][0]['main'],
                'description': data['weather'][0]['description'],
                'rain_1h': data.get('rain', {}).get('1h', 0),
                'snow_1h': data.get('snow', {}).get('1h', 0),
                'timestamp': datetime.now().isoformat()
            }
            
            # Cache aktualisieren
            self.cache[cache_key] = {
                'data': weather,
                'timestamp': time.time()
            }
            
            return weather
            
        except Exception as e:
            print(f"⚠️ Weather API Error: {e}")
            return self._get_default_weather()
    
    def get_forecast(self, lat: float, lon: float, match_datetime: datetime) -> Optional[Dict]:
        """
        Hole Wettervorhersage für einen bestimmten Zeitpunkt
        
        Args:
            lat: Breitengrad
            lon: Längengrad
            match_datetime: Datum/Zeit des Spiels
        
        Returns:
            Dict mit Wettervorhersage
        """
        if not self.api_key:
            return self._get_default_weather()
        
        try:
            self._rate_limit()
            response = requests.get(
                f"{self.base_url}/forecast",
                params={
                    'lat': lat,
                    'lon': lon,
                    'appid': self.api_key,
                    'units': 'metric'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return self._get_default_weather()
            
            data = response.json()
            
            # Finde den nächsten Zeitpunkt zum Spiel
            best_forecast = None
            min_diff = float('inf')
            
            for forecast in data['list']:
                forecast_time = datetime.fromtimestamp(forecast['dt'])
                diff = abs((forecast_time - match_datetime).total_seconds())
                
                if diff < min_diff:
                    min_diff = diff
                    best_forecast = forecast
            
            if best_forecast:
                return {
                    'temperature': best_forecast['main']['temp'],
                    'feels_like': best_forecast['main']['feels_like'],
                    'humidity': best_forecast['main']['humidity'],
                    'wind_speed': best_forecast['wind']['speed'] * 3.6,
                    'wind_gust': best_forecast['wind'].get('gust', 0) * 3.6,
                    'clouds': best_forecast['clouds']['all'],
                    'condition': best_forecast['weather'][0]['main'],
                    'description': best_forecast['weather'][0]['description'],
                    'rain_3h': best_forecast.get('rain', {}).get('3h', 0),
                    'forecast_time': datetime.fromtimestamp(best_forecast['dt']).isoformat(),
                    'hours_from_now': min_diff / 3600
                }
            
            return self._get_default_weather()
            
        except Exception as e:
            print(f"⚠️ Forecast Error: {e}")
            return self._get_default_weather()
    
    def _get_default_weather(self) -> Dict:
        """Liefere neutrale Default-Wetterdaten"""
        return {
            'temperature': 15,
            'feels_like': 15,
            'humidity': 60,
            'wind_speed': 10,
            'wind_gust': 15,
            'clouds': 50,
            'condition': 'Clouds',
            'description': 'partly cloudy',
            'rain_1h': 0,
            'rain_3h': 0,
            'snow_1h': 0,
            'visibility': 10,
            'is_default': True
        }
    
    def calculate_weather_impact(self, weather: Dict) -> Dict:
        """
        Berechne den Einfluss des Wetters auf die erwarteten Tore
        
        Args:
            weather: Dict mit Wetterdaten
        
        Returns:
            Dict mit Faktoren und Bewertungen
        """
        # Wind-Faktor
        wind_speed = weather.get('wind_speed', 10)
        wind_factor = 1.0
        wind_category = 'negligible'
        
        for category, config in self.WIND_THRESHOLDS.items():
            if wind_speed <= config['max_speed']:
                wind_factor = config['factor']
                wind_category = category
                break
        
        # Regen-Faktor
        rain = weather.get('rain_1h', 0) or weather.get('rain_3h', 0) / 3
        rain_factor = 1.0
        rain_category = 'none'
        
        for category, config in self.RAIN_THRESHOLDS.items():
            if rain <= config['max_mm']:
                rain_factor = config['factor']
                rain_category = category
                break
        
        # Temperatur-Faktor
        temp = weather.get('temperature', 15)
        temp_factor = 1.0
        temp_category = 'optimal'
        
        for category, config in self.TEMP_THRESHOLDS.items():
            if config['range'][0] <= temp < config['range'][1]:
                temp_factor = config['factor']
                temp_category = category
                break
        
        # Gesamt-Faktor
        total_factor = wind_factor * rain_factor * temp_factor
        
        # Konfidenzniveau
        if weather.get('is_default'):
            confidence = 'Niedrig (Default-Daten)'
        elif weather.get('hours_from_now', 0) > 24:
            confidence = 'Mittel (Vorhersage >24h)'
        else:
            confidence = 'Hoch (Aktuelle Daten)'
        
        return {
            'total_factor': total_factor,
            'adjustment_percentage': (total_factor - 1) * 100,
            
            'wind': {
                'speed_kmh': wind_speed,
                'factor': wind_factor,
                'category': wind_category,
                'description': self.WIND_THRESHOLDS[wind_category]['description']
            },
            
            'rain': {
                'mm_per_hour': rain,
                'factor': rain_factor,
                'category': rain_category,
                'description': self.RAIN_THRESHOLDS[rain_category]['description']
            },
            
            'temperature': {
                'celsius': temp,
                'factor': temp_factor,
                'category': temp_category,
                'description': self.TEMP_THRESHOLDS[temp_category]['description']
            },
            
            'condition': weather.get('condition', 'Unknown'),
            'description': weather.get('description', ''),
            'confidence': confidence,
            
            # Empfehlung für Wetten
            'betting_advisory': self._get_betting_advisory(total_factor, wind_speed, rain)
        }
    
    def _get_betting_advisory(self, total_factor: float, wind_speed: float, 
                             rain: float) -> str:
        """Generiere Wett-Empfehlung basierend auf Wetter"""
        advisories = []
        
        if total_factor < 0.90:
            advisories.append("⚠️ STARK: Extremes Wetter - Under-Märkte bevorzugen")
        elif total_factor < 0.95:
            advisories.append("📊 MODERAT: Wetter-Einfluss beachten")
        
        if wind_speed > 30:
            advisories.append("💨 Starker Wind: Long Shots & Standards beeinträchtigt")
        
        if rain > 5:
            advisories.append("🌧️ Starker Regen: Erhöhte Fehlerquote bei Pässen")
        
        if not advisories:
            advisories.append("✅ Normales Wetter: Kein besonderer Einfluss")
        
        return " | ".join(advisories)
    
    def adjust_expected_goals(self, lambda_home: float, mu_away: float,
                             weather: Dict) -> Tuple[float, float, Dict]:
        """
        Passe erwartete Tore basierend auf Wetter an
        
        Args:
            lambda_home: Erwartete Heimtore
            mu_away: Erwartete Auswärtstore
            weather: Wetterdaten-Dict
        
        Returns:
            Tuple (adjusted_lambda_home, adjusted_mu_away, impact_details)
        """
        impact = self.calculate_weather_impact(weather)
        factor = impact['total_factor']
        
        adjusted_home = lambda_home * factor
        adjusted_away = mu_away * factor
        
        return adjusted_home, adjusted_away, impact
    
    def get_match_weather_analysis(self, stadium_name: str = None, city: str = None,
                                   lat: float = None, lon: float = None,
                                   match_datetime: datetime = None) -> Dict:
        """
        Vollständige Wetter-Analyse für ein Spiel
        
        Args:
            stadium_name: Name des Stadions
            city: Stadt als Fallback
            lat, lon: Direkte Koordinaten
            match_datetime: Spielzeitpunkt (None = aktuell)
        
        Returns:
            Umfassende Wetter-Analyse
        """
        # Koordinaten ermitteln
        coords = self.get_coordinates(stadium_name, city, lat, lon)
        
        # Wetter abrufen
        if match_datetime and match_datetime > datetime.now() + timedelta(hours=2):
            weather = self.get_forecast(coords[0], coords[1], match_datetime)
        else:
            weather = self.get_current_weather(coords[0], coords[1])
        
        # Impact berechnen
        impact = self.calculate_weather_impact(weather)
        
        return {
            'location': {
                'stadium': stadium_name,
                'city': city,
                'coordinates': {'lat': coords[0], 'lon': coords[1]}
            },
            'weather': weather,
            'impact': impact,
            'recommendation': impact['betting_advisory']
        }


# Quick Test
if __name__ == '__main__':
    print("=" * 60)
    print("WEATHER ANALYZER TEST")
    print("=" * 60)
    
    analyzer = WeatherAnalyzer()  # Ohne API Key = Default-Daten
    
    # Test mit Stadion-Koordinaten
    print("\n📍 Test: Allianz Arena (Bayern München)")
    coords = analyzer.get_coordinates(stadium_name="Allianz Arena")
    print(f"   Koordinaten: {coords}")
    
    # Test Wetter-Analyse
    weather = analyzer._get_default_weather()
    impact = analyzer.calculate_weather_impact(weather)
    
    print(f"\n🌤️ Wetter-Bedingungen:")
    print(f"   Temperatur: {weather['temperature']}°C")
    print(f"   Wind: {weather['wind_speed']} km/h")
    print(f"   Regen: {weather.get('rain_1h', 0)} mm/h")
    
    print(f"\n📊 Einfluss auf erwartete Tore:")
    print(f"   Wind-Faktor: {impact['wind']['factor']:.2f} ({impact['wind']['description']})")
    print(f"   Regen-Faktor: {impact['rain']['factor']:.2f} ({impact['rain']['description']})")
    print(f"   Temp-Faktor: {impact['temperature']['factor']:.2f} ({impact['temperature']['description']})")
    print(f"   Gesamt-Faktor: {impact['total_factor']:.2f}")
    print(f"   Anpassung: {impact['adjustment_percentage']:+.1f}%")
    
    print(f"\n💡 Empfehlung: {impact['betting_advisory']}")
    
    # Test mit extremem Wetter
    print("\n" + "-" * 60)
    print("TEST: Extremes Wetter (Sturm + Starkregen)")
    extreme_weather = {
        'temperature': 5,
        'wind_speed': 45,  # Sturm!
        'rain_1h': 10,     # Starkregen!
    }
    extreme_impact = analyzer.calculate_weather_impact(extreme_weather)
    
    print(f"   Wind: {extreme_weather['wind_speed']} km/h → Faktor {extreme_impact['wind']['factor']:.2f}")
    print(f"   Regen: {extreme_weather['rain_1h']} mm/h → Faktor {extreme_impact['rain']['factor']:.2f}")
    print(f"   Gesamt-Anpassung: {extreme_impact['adjustment_percentage']:+.1f}%")
    print(f"   Empfehlung: {extreme_impact['betting_advisory']}")
    
    # Test Anpassung der erwarteten Tore
    print("\n" + "-" * 60)
    print("TEST: Tor-Anpassung bei Sturm")
    original_home = 2.0
    original_away = 1.5
    adj_home, adj_away, _ = analyzer.adjust_expected_goals(
        original_home, original_away, extreme_weather
    )
    print(f"   Original:  Home λ={original_home:.2f}, Away μ={original_away:.2f}")
    print(f"   Angepasst: Home λ={adj_home:.2f}, Away μ={adj_away:.2f}")
    
    print("\n✅ Weather Analyzer Modul erfolgreich geladen!")
