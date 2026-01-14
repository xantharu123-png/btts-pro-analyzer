"""
BTTS PRO - MIGRATION GUIDE
==========================

Dieses Dokument erklärt die Änderungen und wie man die korrigierten Module integriert.

KRITISCHE FEHLER DIE BEHOBEN WURDEN:
====================================

1. BTTS BASE = 70% IMMER (BEHOBEN)
   --------------------------------
   VORHER: base_btts = 70  # Willkürlicher Startwert
   NACHHER: BTTS wird mathematisch aus xG berechnet
   
   Formel: P(BTTS) = P(Home ≥ 1) × P(Away ≥ 1)
           P(Team ≥ 1) = 1 - e^(-xG)

2. OVER/UNDER ZEIGTE 0.0% (BEHOBEN)
   ---------------------------------
   VORHER: ou_prediction.get('over_25_probability', 0)  # Key existierte nicht!
   NACHHER: Korrekter Key + Poisson-basierte Berechnung

3. ALLE ADJUSTMENTS WAREN ADDITIV (BEHOBEN)
   -----------------------------------------
   VORHER: Nur positive Adjustments (+5, +8, +12)
   NACHHER: xG-basiert, kann auch sinken

4. MOMENTUM TRACKER ZÄHLTE DOPPELT (BEHOBEN)
   ------------------------------------------
   VORHER: Globaler Tracker, akkumulierte bei jedem API-Call
   NACHHER: Match-spezifisches Tracking

5. GAME PHASE GAB IMMER BONUS (BEHOBEN)
   --------------------------------------
   VORHER: Ab Minute 75 immer +12%
   NACHHER: Phase beeinflusst nur leicht, xG ist Hauptfaktor


MATHEMATISCHE GRUNDLAGEN:
=========================

1. POISSON-VERTEILUNG
   P(X = k) = (λ^k × e^(-λ)) / k!
   
   Wobei λ = Expected Goals (xG)
   
   Beispiel bei xG = 1.5:
   P(0 Tore) = e^(-1.5) = 22.3%
   P(≥1 Tor) = 1 - 22.3% = 77.7%

2. BTTS BERECHNUNG
   P(BTTS) = P(Home ≥ 1) × P(Away ≥ 1)
   
   Beispiel:
   Home xG = 1.5 → P(Home scores) = 77.7%
   Away xG = 0.8 → P(Away scores) = 55.1%
   P(BTTS) = 77.7% × 55.1% = 42.8%

3. OVER/UNDER BERECHNUNG
   P(Over 2.5) = 1 - [P(0) + P(1) + P(2)]
   
   Bei Expected Total = 2.8:
   P(0) = e^(-2.8) = 6.1%
   P(1) = 2.8 × e^(-2.8) = 17.0%
   P(2) = (2.8² / 2) × e^(-2.8) = 23.8%
   P(Over 2.5) = 1 - 46.9% = 53.1%


INTEGRATION:
============

1. LIVE SCANNER ERSETZEN:
   
   # Alt:
   from ultra_live_scanner_v3 import UltraLiveScanner
   
   # Neu:
   from ultra_live_scanner_v3_fixed import UltraLiveScannerFixed
   
   # Verwendung bleibt gleich:
   scanner = UltraLiveScannerFixed(analyzer, api_football)
   result = scanner.analyze_live_match_ultra(match)

2. MULTI-MARKET PREDICTOR ERSETZEN:
   
   # Alt:
   from multi_market_predictor import OverUnderPredictor, NextGoalPredictor
   
   # Neu:
   from multi_market_predictor_fixed import OverUnderPredictorFixed, NextGoalPredictorFixed

3. PRE-MATCH ANALYZER ERSETZEN:
   
   # Alt:
   from advanced_analyzer import AdvancedAnalyzer
   
   # Neu (oder als Ergänzung):
   from prematch_analyzer_fixed import PreMatchAnalyzerFixed


VERGLEICH ALTE VS NEUE WERTE:
=============================

Beispiel: Spiel mit xG 0.5 - 0.3, Minute 35, Score 0-0

ALTE BERECHNUNG:
- Base BTTS: 70%
- Momentum: +5%
- Phase: +8%
- Score: 0%
- Final: 83% BTTS ❌ FALSCH!

NEUE BERECHNUNG:
- P(Home scores): 1 - e^(-0.5) = 39.3%
- P(Away scores): 1 - e^(-0.3) = 25.9%
- Zeit-Projektion: xG hochgerechnet
- P(BTTS): ~25-35% ✅ KORREKT!


TESTFÄLLE:
==========

def test_btts_calculation():
    '''Teste ob Berechnung korrekt'''
    
    # Test 1: Niedrige xG = Niedrige BTTS
    result = calculate_btts(xg_home=0.3, xg_away=0.2, minute=45)
    assert result < 30, f"BTTS sollte <30% sein bei niedriger xG, war {result}%"
    
    # Test 2: Hohe xG = Hohe BTTS
    result = calculate_btts(xg_home=2.0, xg_away=1.5, minute=60)
    assert result > 60, f"BTTS sollte >60% sein bei hoher xG, war {result}%"
    
    # Test 3: BTTS bereits eingetreten
    result = calculate_btts(xg_home=0.5, xg_away=0.5, minute=30, 
                           home_score=1, away_score=1)
    assert result == 100, "BTTS sollte 100% sein wenn beide getroffen haben"
    
    # Test 4: Späte Phase, 0-0, niedrige xG
    result = calculate_btts(xg_home=0.4, xg_away=0.3, minute=80)
    assert result < 25, "BTTS sollte sehr niedrig sein bei 0-0 in Minute 80 mit niedriger xG"
    
    print("✅ Alle Tests bestanden!")


EMPFOHLENE SCHWELLWERTE:
========================

BTTS:
- ≥ 65%: 🔥 STRONG BET
- 55-65%: ✅ GOOD BET
- 45-55%: ⚠️ RISKY
- < 45%: ❌ SKIP (oder BTTS NO)

OVER/UNDER:
- ≥ 70%: 🔥 STRONG
- 60-70%: ✅ GOOD
- 50-60%: ⚠️ SLIGHT EDGE
- < 50%: Gegenteil betrachten

NEXT GOAL:
- Edge ≥ 25%: 🔥 STRONG
- Edge 15-25%: ✅ GOOD
- Edge < 15%: ⚠️ TOO CLOSE


BEKANNTE LIMITIERUNGEN:
=======================

1. xG nicht immer verfügbar
   → Fallback auf Schuss-basierte Schätzung
   
2. Frühe Spielminuten haben wenig Daten
   → Konservativere Vorhersagen in ersten 15 Min

3. Keine Lineup-Berücksichtigung
   → Kann bei wichtigen Ausfällen ungenau sein

4. Wetter-Faktor noch nicht integriert
   → Kann bei Extremwetter abweichen
"""

# =============================================
# QUICK MIGRATION SCRIPT
# =============================================

def migrate_app():
    """
    Schnelle Migration für bestehende App
    """
    
    migration_code = '''
# In deiner Haupt-App (z.B. app.py), ersetze:

# === ALT ===
# from ultra_live_scanner_v3 import UltraLiveScanner, display_ultra_opportunity
# from multi_market_predictor import OverUnderPredictor, NextGoalPredictor

# === NEU ===
from ultra_live_scanner_v3_fixed import UltraLiveScannerFixed, display_ultra_opportunity_fixed
from multi_market_predictor_fixed import OverUnderPredictorFixed, NextGoalPredictorFixed
from prematch_analyzer_fixed import PreMatchAnalyzerFixed

# Dann in deinem Code:
# scanner = UltraLiveScanner(analyzer, api)  # ALT
scanner = UltraLiveScannerFixed(analyzer, api)  # NEU

# Für Pre-Match:
prematch = PreMatchAnalyzerFixed(data_engine, api)
result = prematch.analyze_match(home_id, away_id, league_code)

# Display bleibt ähnlich:
# display_ultra_opportunity(match)  # ALT
display_ultra_opportunity_fixed(match)  # NEU
'''
    
    print(migration_code)


if __name__ == "__main__":
    print(__doc__)
    print("\n" + "=" * 60)
    print("MIGRATION CODE:")
    print("=" * 60)
    migrate_app()
