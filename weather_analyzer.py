"""
Weather Analysis Module for BTTS Pro Analyzer
Analyzes weather impact on BTTS probability

OpenWeatherMap API: FREE (60 calls/minute)
Sign up: https://openweathermap.org/api
"""

import requests
from typing import Dict, Optional
from datetime import datetime

class WeatherAnalyzer:
    """Analyze weather conditions and their impact on BTTS"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        
        # Stadium coordinates for major teams
        self.stadium_coords = {
            # Bundesliga
            'FC Bayern München': (48.2188, 11.6247),  # Allianz Arena
            'Borussia Dortmund': (51.4925, 7.4517),   # Signal Iduna Park
            'RB Leipzig': (51.3458, 12.3481),         # Red Bull Arena
            'Bayer 04 Leverkusen': (51.0381, 7.0024), # BayArena
            'VfL Wolfsburg': (52.4319, 10.8036),      # Volkswagen Arena
            'Eintracht Frankfurt': (50.0686, 8.6452), # Deutsche Bank Park
            'VfB Stuttgart': (48.7921, 9.2316),       # Mercedes-Benz Arena
            'TSG 1899 Hoffenheim': (49.2390, 8.8876), # PreZero Arena
            'Borussia Mönchengladbach': (51.1745, 6.3856), # Borussia-Park
            'SC Freiburg': (47.9889, 7.8932),         # Europa-Park Stadion
            
            # Premier League
            'Manchester City': (53.4831, -2.2004),     # Etihad
            'Arsenal FC': (51.5549, -0.1084),          # Emirates
            'Liverpool FC': (53.4308, -2.9608),        # Anfield
            'Manchester United': (53.4631, -2.2913),   # Old Trafford
            'Tottenham Hotspur': (51.6042, -0.0662),   # Tottenham Stadium
            'Chelsea FC': (51.4817, -0.1910),          # Stamford Bridge
            'Brighton & Hove Albion': (50.8612, -0.0831), # Amex Stadium
            
            # Add more as needed...
        }
    
    def get_weather(self, team_name: str, match_time: Optional[datetime] = None) -> Optional[Dict]:
        """
        Get weather forecast for a team's stadium
        Returns weather conditions and BTTS impact
        """
        coords = self.stadium_coords.get(team_name)
        
        if not coords:
            return None
        
        lat, lon = coords
        
        try:
            response = requests.get(
                self.base_url,
                params={
                    'lat': lat,
                    'lon': lon,
                    'appid': self.api_key,
                    'units': 'metric'
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._analyze_weather(data)
            
        except Exception as e:
            print(f"Weather API error: {e}")
            return None
        
        return None
    
    def _analyze_weather(self, weather_data: Dict) -> Dict:
        """
        Analyze weather conditions and calculate BTTS impact
        
        Weather Impact on BTTS:
        - Heavy Rain: -10% (slippery ball, less precision)
        - Light Rain: -3% (slight impact)
        - Snow: -15% (very slow game)
        - Strong Wind: -5% (harder to shoot accurately)
        - Perfect Conditions: +3% (fast, precise play)
        - Extreme Heat: -2% (players tired)
        - Extreme Cold: -5% (stiff muscles)
        """
        main = weather_data.get('main', {})
        weather = weather_data.get('weather', [{}])[0]
        wind = weather_data.get('wind', {})
        
        temp = main.get('temp', 20)
        weather_id = weather.get('id', 800)
        weather_desc = weather.get('description', 'clear')
        wind_speed = wind.get('speed', 0)
        
        # Calculate BTTS adjustment
        btts_adjustment = 0
        condition = 'unknown'
        impact_level = 'neutral'
        
        # Rain (weather_id 5xx)
        if 500 <= weather_id < 600:
            if weather_id < 520:  # Light rain
                btts_adjustment = -3
                condition = 'light_rain'
                impact_level = 'low_negative'
            else:  # Heavy rain
                btts_adjustment = -10
                condition = 'heavy_rain'
                impact_level = 'high_negative'
        
        # Snow (weather_id 6xx)
        elif 600 <= weather_id < 700:
            btts_adjustment = -15
            condition = 'snow'
            impact_level = 'very_negative'
        
        # Thunderstorm (weather_id 2xx)
        elif 200 <= weather_id < 300:
            btts_adjustment = -8
            condition = 'thunderstorm'
            impact_level = 'high_negative'
        
        # Clear/Clouds (weather_id 800-8xx)
        elif weather_id == 800:  # Clear sky
            if 18 <= temp <= 25:  # Perfect temp
                btts_adjustment = +3
                condition = 'perfect'
                impact_level = 'slight_positive'
            elif temp > 30:  # Too hot
                btts_adjustment = -2
                condition = 'hot'
                impact_level = 'slight_negative'
            elif temp < 5:  # Too cold
                btts_adjustment = -5
                condition = 'cold'
                impact_level = 'low_negative'
        
        # Wind impact
        if wind_speed > 10:  # Strong wind (m/s)
            btts_adjustment -= 5
            condition += '_windy'
            impact_level = 'negative'
        
        return {
            'temperature': temp,
            'condition': condition,
            'description': weather_desc,
            'wind_speed': wind_speed,
            'btts_adjustment': btts_adjustment,
            'impact_level': impact_level,
            'weather_id': weather_id
        }
    
    def get_impact_emoji(self, impact_level: str) -> str:
        """Get emoji for weather impact"""
        emojis = {
            'very_negative': '❄️',
            'high_negative': '🌧️',
            'low_negative': '☁️',
            'slight_negative': '😐',
            'neutral': '😶',
            'slight_positive': '☀️',
            'positive': '🌞'
        }
        return emojis.get(impact_level, '❓')
