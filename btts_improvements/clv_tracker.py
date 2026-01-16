"""
CLOSING LINE VALUE (CLV) TRACKING MODUL
========================================
Professionelles Validierungsframework für Wettvorhersagen.

CLV = Die einzige Metrik, die langfristige Profitabilität vorhersagt!

Konzept:
- Die "Closing Line" (Quoten zum Anpfiff) repräsentiert die effizienteste 
  Wahrscheinlichkeit, da sie alle Marktinformationen inkorporiert
- Ein positiver CLV bedeutet, dass das Modell "Value" gefunden hat
- Selbst bei einer verlorenen Wette war der Prozess korrekt, wenn CLV > 0

Formel:
CLV = (Genommene Quote / Schlussquote) - 1

Beispiel:
- Wette bei Quote 2.20, Markt schließt bei 2.00
- CLV = 2.20 / 2.00 - 1 = +10% → Value!
- Wette bei Quote 2.00, Markt schließt bei 2.20
- CLV = 2.00 / 2.20 - 1 = -9% → Kein Value

Warum CLV wichtiger ist als Gewinnquote:
- 55% Gewinnquote mit negativem CLV = langfristiger Verlust
- 48% Gewinnquote mit positivem CLV = langfristiger Gewinn
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import statistics


class CLVTracker:
    """
    Closing Line Value Tracking System
    
    Speichert und analysiert:
    - Zeitpunkt der Vorhersage mit aktueller Quote
    - Schlussquote zum Anpfiff
    - Tatsächliches Ergebnis
    - CLV-Berechnung und Performance-Metriken
    """
    
    def __init__(self, db_path: str = "clv_tracking.db"):
        """
        Initialisiere CLV Tracker mit SQLite Datenbank
        
        Args:
            db_path: Pfad zur SQLite Datenbank
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Erstelle die notwendigen Datenbanktabellen"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Haupttabelle für Wetten/Vorhersagen
        c.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                
                -- Match Identifikation
                fixture_id INTEGER NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                league_code TEXT,
                match_date TIMESTAMP,
                
                -- Vorhersage Details
                market_type TEXT NOT NULL,  -- 'BTTS', 'Over2.5', '1X2', etc.
                prediction TEXT NOT NULL,    -- 'Yes', 'No', 'Home', 'Over', etc.
                model_probability REAL,      -- Modell-Wahrscheinlichkeit in %
                confidence_score REAL,       -- Confidence 0-100
                
                -- Quoten zum Zeitpunkt der Vorhersage
                odds_at_prediction REAL NOT NULL,
                prediction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Schlussquoten (vor Anpfiff)
                odds_at_close REAL,
                close_timestamp TIMESTAMP,
                
                -- Ergebnis
                actual_outcome TEXT,  -- 'Won', 'Lost', 'Void'
                home_score INTEGER,
                away_score INTEGER,
                
                -- Berechnete Metriken
                clv_percentage REAL,
                implied_prob_at_pred REAL,  -- 1/odds in %
                implied_prob_at_close REAL,
                edge_at_prediction REAL,    -- model_prob - implied_prob
                
                -- Status
                status TEXT DEFAULT 'pending',  -- 'pending', 'closed', 'settled'
                
                -- Staking (optional)
                stake_units REAL DEFAULT 1.0,
                profit_loss REAL,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index für schnelle Abfragen
        c.execute('CREATE INDEX IF NOT EXISTS idx_fixture ON predictions(fixture_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_status ON predictions(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_market ON predictions(market_type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_date ON predictions(match_date)')
        
        # Aggregierte Performance-Tabelle
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_performance (
                date TEXT PRIMARY KEY,
                total_predictions INTEGER,
                won INTEGER,
                lost INTEGER,
                void INTEGER,
                total_clv REAL,
                avg_clv REAL,
                total_profit_loss REAL,
                roi_percentage REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_prediction(self, fixture_id: int, home_team: str, away_team: str,
                         market_type: str, prediction: str, odds: float,
                         model_probability: float = None, confidence: float = None,
                         league_code: str = None, match_date: datetime = None,
                         stake_units: float = 1.0) -> int:
        """
        Speichere eine neue Vorhersage
        
        Args:
            fixture_id: API-Football Fixture ID
            home_team: Name des Heimteams
            away_team: Name des Auswärtsteams
            market_type: Markttyp ('BTTS', 'Over2.5', '1X2_Home', etc.)
            prediction: Die Vorhersage ('Yes', 'No', 'Home', 'Away', 'Over', etc.)
            odds: Quote zum Zeitpunkt der Vorhersage
            model_probability: Modell-Wahrscheinlichkeit in %
            confidence: Confidence Score 0-100
            league_code: Liga-Code (z.B. 'BL1')
            match_date: Datum des Spiels
            stake_units: Einsatz in Einheiten
        
        Returns:
            ID des neuen Eintrags
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Berechne implizite Wahrscheinlichkeit
        implied_prob = (1 / odds) * 100 if odds > 0 else 0
        
        # Berechne Edge (wenn Modell-Wahrscheinlichkeit vorhanden)
        edge = model_probability - implied_prob if model_probability else None
        
        c.execute('''
            INSERT INTO predictions (
                fixture_id, home_team, away_team, league_code, match_date,
                market_type, prediction, model_probability, confidence_score,
                odds_at_prediction, implied_prob_at_pred, edge_at_prediction,
                stake_units, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (
            fixture_id, home_team, away_team, league_code, match_date,
            market_type, prediction, model_probability, confidence,
            odds, implied_prob, edge, stake_units
        ))
        
        prediction_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return prediction_id
    
    def update_closing_odds(self, prediction_id: int, closing_odds: float):
        """
        Aktualisiere die Schlussquote und berechne CLV
        
        Args:
            prediction_id: ID der Vorhersage
            closing_odds: Quote zum Anpfiff
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Hole die ursprüngliche Quote
        c.execute('SELECT odds_at_prediction FROM predictions WHERE id = ?', 
                  (prediction_id,))
        row = c.fetchone()
        
        if row:
            original_odds = row[0]
            
            # CLV Berechnung
            clv = (original_odds / closing_odds - 1) * 100 if closing_odds > 0 else 0
            implied_close = (1 / closing_odds) * 100 if closing_odds > 0 else 0
            
            c.execute('''
                UPDATE predictions 
                SET odds_at_close = ?,
                    close_timestamp = ?,
                    clv_percentage = ?,
                    implied_prob_at_close = ?,
                    status = 'closed',
                    updated_at = ?
                WHERE id = ?
            ''', (closing_odds, datetime.now(), clv, implied_close, 
                  datetime.now(), prediction_id))
            
            conn.commit()
        
        conn.close()
    
    def settle_prediction(self, prediction_id: int, actual_outcome: str,
                         home_score: int = None, away_score: int = None):
        """
        Schließe eine Vorhersage mit dem tatsächlichen Ergebnis ab
        
        Args:
            prediction_id: ID der Vorhersage
            actual_outcome: 'Won', 'Lost', oder 'Void'
            home_score: Tore Heimteam
            away_score: Tore Auswärtsteam
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Hole Wett-Details
        c.execute('''
            SELECT odds_at_prediction, stake_units 
            FROM predictions WHERE id = ?
        ''', (prediction_id,))
        row = c.fetchone()
        
        if row:
            odds, stake = row
            
            # Berechne Profit/Loss
            if actual_outcome == 'Won':
                profit_loss = (odds - 1) * stake
            elif actual_outcome == 'Lost':
                profit_loss = -stake
            else:  # Void
                profit_loss = 0
            
            c.execute('''
                UPDATE predictions 
                SET actual_outcome = ?,
                    home_score = ?,
                    away_score = ?,
                    profit_loss = ?,
                    status = 'settled',
                    updated_at = ?
                WHERE id = ?
            ''', (actual_outcome, home_score, away_score, profit_loss,
                  datetime.now(), prediction_id))
            
            conn.commit()
        
        conn.close()
    
    def auto_settle_by_fixture(self, fixture_id: int, home_score: int, away_score: int):
        """
        Automatisches Settlement aller Vorhersagen für ein Spiel
        
        Args:
            fixture_id: API-Football Fixture ID
            home_score: Tore Heimteam
            away_score: Tore Auswärtsteam
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Hole alle offenen Vorhersagen für dieses Spiel
        c.execute('''
            SELECT id, market_type, prediction 
            FROM predictions 
            WHERE fixture_id = ? AND status != 'settled'
        ''', (fixture_id,))
        
        predictions = c.fetchall()
        
        for pred_id, market_type, prediction in predictions:
            outcome = self._determine_outcome(market_type, prediction, 
                                             home_score, away_score)
            self.settle_prediction(pred_id, outcome, home_score, away_score)
        
        conn.close()
    
    def _determine_outcome(self, market_type: str, prediction: str,
                          home_score: int, away_score: int) -> str:
        """
        Bestimme das Ergebnis basierend auf Markt und Vorhersage
        
        Returns:
            'Won', 'Lost', oder 'Void'
        """
        total_goals = home_score + away_score
        btts_actual = home_score > 0 and away_score > 0
        
        market = market_type.upper()
        pred = prediction.upper()
        
        # BTTS Markt
        if market == 'BTTS':
            if pred in ['YES', 'JA']:
                return 'Won' if btts_actual else 'Lost'
            else:
                return 'Won' if not btts_actual else 'Lost'
        
        # Over/Under Märkte
        elif 'OVER' in market or 'UNDER' in market:
            line = float(market.replace('OVER', '').replace('UNDER', '').strip())
            if 'OVER' in pred or pred == 'YES':
                return 'Won' if total_goals > line else 'Lost'
            else:
                return 'Won' if total_goals <= line else 'Lost'
        
        # 1X2 Markt
        elif '1X2' in market or market in ['HOME', 'DRAW', 'AWAY']:
            if pred in ['HOME', '1', 'HEIMSIEG']:
                return 'Won' if home_score > away_score else 'Lost'
            elif pred in ['DRAW', 'X', 'UNENTSCHIEDEN']:
                return 'Won' if home_score == away_score else 'Lost'
            else:  # Away
                return 'Won' if away_score > home_score else 'Lost'
        
        return 'Void'
    
    def get_clv_statistics(self, days: int = 30, market_type: str = None) -> Dict:
        """
        Berechne CLV-Statistiken für einen Zeitraum
        
        Args:
            days: Anzahl Tage zurück
            market_type: Optional - Filter nach Markttyp
        
        Returns:
            Dict mit umfassenden CLV-Statistiken
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        query = '''
            SELECT 
                clv_percentage,
                actual_outcome,
                profit_loss,
                odds_at_prediction,
                odds_at_close,
                edge_at_prediction
            FROM predictions 
            WHERE status = 'settled' 
            AND created_at >= ?
        '''
        params = [since_date]
        
        if market_type:
            query += ' AND market_type = ?'
            params.append(market_type)
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return {
                'total_bets': 0,
                'message': 'Keine Daten im gewählten Zeitraum'
            }
        
        # Extrahiere Daten
        clv_values = [r[0] for r in rows if r[0] is not None]
        outcomes = [r[1] for r in rows]
        profits = [r[2] for r in rows if r[2] is not None]
        edges = [r[5] for r in rows if r[5] is not None]
        
        won = sum(1 for o in outcomes if o == 'Won')
        lost = sum(1 for o in outcomes if o == 'Lost')
        total = len(rows)
        
        # Berechne Statistiken
        stats = {
            'period_days': days,
            'total_bets': total,
            'won': won,
            'lost': lost,
            'win_rate': (won / total * 100) if total > 0 else 0,
            
            # CLV Metriken
            'avg_clv': statistics.mean(clv_values) if clv_values else 0,
            'median_clv': statistics.median(clv_values) if clv_values else 0,
            'total_clv': sum(clv_values) if clv_values else 0,
            'positive_clv_rate': (sum(1 for c in clv_values if c > 0) / len(clv_values) * 100) if clv_values else 0,
            
            # Edge Metriken
            'avg_edge': statistics.mean(edges) if edges else 0,
            
            # Profit/Loss
            'total_profit_loss': sum(profits) if profits else 0,
            'roi': (sum(profits) / total * 100) if total > 0 and profits else 0,
            
            # Qualitätsindikatoren
            'clv_stddev': statistics.stdev(clv_values) if len(clv_values) > 1 else 0,
        }
        
        # Bewertung der Strategie
        if stats['avg_clv'] > 3:
            stats['strategy_rating'] = '⭐⭐⭐ Exzellent'
        elif stats['avg_clv'] > 1:
            stats['strategy_rating'] = '⭐⭐ Gut'
        elif stats['avg_clv'] > 0:
            stats['strategy_rating'] = '⭐ Akzeptabel'
        else:
            stats['strategy_rating'] = '❌ Überarbeitung nötig'
        
        return stats
    
    def get_market_breakdown(self, days: int = 30) -> Dict:
        """
        Aufschlüsselung der Performance nach Markttyp
        
        Returns:
            Dict mit Performance pro Markt
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        c.execute('''
            SELECT 
                market_type,
                COUNT(*) as total,
                SUM(CASE WHEN actual_outcome = 'Won' THEN 1 ELSE 0 END) as won,
                AVG(clv_percentage) as avg_clv,
                SUM(profit_loss) as total_pl
            FROM predictions 
            WHERE status = 'settled' AND created_at >= ?
            GROUP BY market_type
        ''', (since_date,))
        
        rows = c.fetchall()
        conn.close()
        
        breakdown = {}
        for row in rows:
            market, total, won, avg_clv, total_pl = row
            breakdown[market] = {
                'total_bets': total,
                'won': won,
                'win_rate': (won / total * 100) if total > 0 else 0,
                'avg_clv': avg_clv or 0,
                'total_profit_loss': total_pl or 0,
                'roi': (total_pl / total * 100) if total > 0 and total_pl else 0
            }
        
        return breakdown
    
    def get_pending_for_close_update(self) -> List[Dict]:
        """
        Hole alle Vorhersagen, die noch Schlussquoten benötigen
        
        Returns:
            Liste der Vorhersagen mit fixture_id
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT id, fixture_id, home_team, away_team, market_type, 
                   prediction, odds_at_prediction
            FROM predictions 
            WHERE status = 'pending' AND odds_at_close IS NULL
        ''')
        
        rows = c.fetchall()
        conn.close()
        
        return [{
            'id': r[0],
            'fixture_id': r[1],
            'home_team': r[2],
            'away_team': r[3],
            'market_type': r[4],
            'prediction': r[5],
            'odds_at_prediction': r[6]
        } for r in rows]
    
    def export_to_json(self, filepath: str, days: int = 90):
        """
        Exportiere alle Daten als JSON für Analyse
        
        Args:
            filepath: Pfad zur JSON-Datei
            days: Anzahl Tage zurück
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        c.execute('''
            SELECT * FROM predictions 
            WHERE created_at >= ?
            ORDER BY created_at DESC
        ''', (since_date,))
        
        columns = [desc[0] for desc in c.description]
        rows = c.fetchall()
        conn.close()
        
        data = {
            'export_date': datetime.now().isoformat(),
            'period_days': days,
            'total_records': len(rows),
            'predictions': [dict(zip(columns, row)) for row in rows]
        }
        
        # Convert datetime objects to strings
        for pred in data['predictions']:
            for key, value in pred.items():
                if isinstance(value, datetime):
                    pred[key] = value.isoformat()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"✅ Exportiert: {len(rows)} Vorhersagen nach {filepath}")


class CLVAnalyzer:
    """
    Fortgeschrittene CLV-Analyse mit Visualisierungen
    """
    
    def __init__(self, tracker: CLVTracker):
        self.tracker = tracker
    
    def print_summary_report(self, days: int = 30):
        """
        Drucke einen formatierten Performance-Report
        """
        stats = self.tracker.get_clv_statistics(days)
        breakdown = self.tracker.get_market_breakdown(days)
        
        print("\n" + "=" * 70)
        print(f"📊 CLV PERFORMANCE REPORT - Letzte {days} Tage")
        print("=" * 70)
        
        if stats['total_bets'] == 0:
            print("\n⚠️ Keine Daten im gewählten Zeitraum")
            return
        
        print(f"\n📈 GESAMTÜBERSICHT:")
        print(f"   Total Wetten:      {stats['total_bets']}")
        print(f"   Gewonnen:          {stats['won']} ({stats['win_rate']:.1f}%)")
        print(f"   Verloren:          {stats['lost']}")
        
        print(f"\n💰 PROFITABILITÄT:")
        print(f"   Total P/L:         {stats['total_profit_loss']:+.2f} Einheiten")
        print(f"   ROI:               {stats['roi']:+.1f}%")
        
        print(f"\n🎯 CLV METRIKEN (Der wichtigste Indikator!):")
        print(f"   Durchschnitt CLV:  {stats['avg_clv']:+.2f}%")
        print(f"   Median CLV:        {stats['median_clv']:+.2f}%")
        print(f"   CLV > 0 Rate:      {stats['positive_clv_rate']:.1f}%")
        print(f"   CLV Std.Abw.:      {stats['clv_stddev']:.2f}%")
        
        print(f"\n📊 EDGE METRIKEN:")
        print(f"   Durchschnitt Edge: {stats['avg_edge']:+.2f}%")
        
        print(f"\n⭐ STRATEGIE-BEWERTUNG: {stats['strategy_rating']}")
        
        if breakdown:
            print(f"\n📋 AUFSCHLÜSSELUNG NACH MARKT:")
            print("-" * 70)
            print(f"{'Markt':<15} {'Wetten':<8} {'Win%':<8} {'Avg CLV':<10} {'P/L':<10} {'ROI':<8}")
            print("-" * 70)
            
            for market, data in breakdown.items():
                print(f"{market:<15} {data['total_bets']:<8} "
                      f"{data['win_rate']:.1f}%{'':<3} "
                      f"{data['avg_clv']:+.2f}%{'':<4} "
                      f"{data['total_profit_loss']:+.2f}{'':<5} "
                      f"{data['roi']:+.1f}%")
        
        print("\n" + "=" * 70)
        print("💡 INTERPRETATION:")
        print("   - CLV > 0: Du findest langfristig Value")
        print("   - CLV > 3%: Exzellente Linien-Timing")
        print("   - Positive CLV Rate > 55%: Konsistenter Edge")
        print("=" * 70)


# Quick Test
if __name__ == '__main__':
    print("=" * 60)
    print("CLV TRACKER TEST")
    print("=" * 60)
    
    # Erstelle Tracker
    tracker = CLVTracker(db_path="test_clv.db")
    
    # Simuliere einige Vorhersagen
    pred_id = tracker.record_prediction(
        fixture_id=12345,
        home_team="Bayern München",
        away_team="Borussia Dortmund",
        market_type="BTTS",
        prediction="Yes",
        odds=1.85,
        model_probability=58.0,
        confidence=72,
        league_code="BL1"
    )
    print(f"\n✅ Vorhersage gespeichert mit ID: {pred_id}")
    
    # Simuliere Schlussquote
    tracker.update_closing_odds(pred_id, closing_odds=1.72)
    print(f"✅ Schlussquote aktualisiert: 1.85 → 1.72")
    
    # Berechne CLV
    clv = (1.85 / 1.72 - 1) * 100
    print(f"📊 CLV: {clv:+.2f}% (Wir haben bessere Odds als der Markt!)")
    
    # Simuliere Ergebnis
    tracker.settle_prediction(pred_id, actual_outcome="Won", home_score=2, away_score=1)
    print(f"✅ Vorhersage abgeschlossen: Gewonnen!")
    
    # Zeige Statistiken
    analyzer = CLVAnalyzer(tracker)
    analyzer.print_summary_report(days=30)
    
    # Cleanup
    import os
    os.remove("test_clv.db")
    print("\n✅ Test-Datenbank gelöscht")
    print("\n✅ CLV Tracker Modul erfolgreich geladen!")
