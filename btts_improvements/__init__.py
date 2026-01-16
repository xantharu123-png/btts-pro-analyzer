"""
BTTS PRO ANALYZER - ERWEITERTE MODULE
======================================
Drei professionelle Verbesserungen für akkuratere Wettvorhersagen:

1. Dixon-Coles Korrektur
   - Korrigiert Poisson-Unterschätzung bei niedrigen Ergebnissen
   - Verbessert 0:0, 1:0, 0:1, 1:1 Wahrscheinlichkeiten
   
2. CLV Tracking (Closing Line Value)
   - Professionelle Validierung der Vorhersagequalität
   - Trackt ob du den Markt schlägst (unabhängig von Gewinn/Verlust)
   
3. Wetter-Integration
   - Passt erwartete Tore bei extremem Wetter an
   - Wind, Regen, Temperatur Faktoren

Installation:
    Kopiere alle Dateien nach /mount/src/btts-pro-analyzer/
    
Verwendung:
    from btts_improvements import EnhancedBTTSAnalyzer, quick_btts_analysis
    from btts_improvements import DixonColesModel
    from btts_improvements import CLVTracker
    from btts_improvements import WeatherAnalyzer
"""

from .dixon_coles import DixonColesModel, compare_models
from .clv_tracker import CLVTracker, CLVAnalyzer
from .weather_analyzer import WeatherAnalyzer
from .enhanced_analyzer import EnhancedBTTSAnalyzer, quick_btts_analysis

__version__ = '2.0.0'
__author__ = 'BTTS Pro Analyzer'

__all__ = [
    'DixonColesModel',
    'compare_models',
    'CLVTracker',
    'CLVAnalyzer', 
    'WeatherAnalyzer',
    'EnhancedBTTSAnalyzer',
    'quick_btts_analysis'
]
