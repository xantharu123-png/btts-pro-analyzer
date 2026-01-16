"""
CLV (Closing Line Value) Tracker
Tracks predictions and calculates CLV to validate model performance
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class CLVTracker:
    """Track predictions and calculate Closing Line Value"""
    
    def __init__(self, db_path: str = "btts_clv.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize CLV database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id INTEGER NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                market_type TEXT NOT NULL,
                prediction TEXT NOT NULL,
                odds REAL,
                closing_odds REAL,
                model_probability REAL,
                confidence INTEGER,
                result TEXT,
                profit REAL,
                home_score INTEGER,
                away_score INTEGER,
                created_at TEXT NOT NULL,
                settled_at TEXT
            )
        ''')
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_fixture ON predictions(fixture_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_created ON predictions(created_at)')
        
        conn.commit()
        conn.close()
    
    def record_prediction(self, fixture_id: int, home_team: str, away_team: str,
                         market_type: str, prediction: str, odds: float,
                         model_probability: float, confidence: int) -> int:
        """
        Record a prediction
        
        Returns:
            prediction_id
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO predictions 
            (fixture_id, home_team, away_team, market_type, prediction, odds,
             model_probability, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (fixture_id, home_team, away_team, market_type, prediction, odds,
              model_probability, confidence, datetime.now().isoformat()))
        
        pred_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return pred_id
    
    def update_closing_odds(self, prediction_id: int, closing_odds: float):
        """Update closing odds for a prediction"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            UPDATE predictions 
            SET closing_odds = ?
            WHERE id = ?
        ''', (closing_odds, prediction_id))
        
        conn.commit()
        conn.close()
    
    def settle_prediction(self, prediction_id: int, result: str,
                         home_score: int, away_score: int):
        """
        Settle a prediction
        
        Args:
            result: 'Won', 'Lost', 'Push'
            home_score: Final home score
            away_score: Final away score
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get prediction details
        c.execute('SELECT odds FROM predictions WHERE id = ?', (prediction_id,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return
        
        odds = row[0]
        
        # Calculate profit
        if result == 'Won':
            profit = odds - 1
        elif result == 'Lost':
            profit = -1
        else:  # Push
            profit = 0
        
        c.execute('''
            UPDATE predictions
            SET result = ?, profit = ?, home_score = ?, away_score = ?,
                settled_at = ?
            WHERE id = ?
        ''', (result, profit, home_score, away_score, 
              datetime.now().isoformat(), prediction_id))
        
        conn.commit()
        conn.close()
    
    def get_clv_statistics(self, days: int = 30) -> Dict:
        """
        Get CLV statistics for the last N days
        
        Returns:
            Dict with CLV metrics
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Date filter
        date_filter = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Get predictions with both opening and closing odds
        c.execute('''
            SELECT odds, closing_odds, result, profit, confidence
            FROM predictions
            WHERE created_at > ?
            AND closing_odds IS NOT NULL
            AND result IS NOT NULL
        ''', (date_filter,))
        
        predictions = c.fetchall()
        conn.close()
        
        if not predictions:
            return {
                'total_bets': 0,
                'avg_clv': 0,
                'win_rate': 0,
                'profit': 0,
                'roi': 0
            }
        
        # Calculate metrics
        total_bets = len(predictions)
        clv_values = []
        wins = 0
        total_profit = 0
        
        for odds, closing_odds, result, profit, confidence in predictions:
            # CLV = (Opening Odds / Closing Odds - 1) * 100
            if closing_odds > 0:
                clv = (odds / closing_odds - 1) * 100
                clv_values.append(clv)
            
            if result == 'Won':
                wins += 1
            
            if profit is not None:
                total_profit += profit
        
        avg_clv = sum(clv_values) / len(clv_values) if clv_values else 0
        win_rate = (wins / total_bets) * 100 if total_bets > 0 else 0
        roi = (total_profit / total_bets) * 100 if total_bets > 0 else 0
        
        return {
            'total_bets': total_bets,
            'avg_clv': round(avg_clv, 2),
            'win_rate': round(win_rate, 1),
            'profit': round(total_profit, 2),
            'roi': round(roi, 1)
        }
    
    def get_recent_predictions(self, limit: int = 10) -> List[Dict]:
        """Get recent predictions"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT id, fixture_id, home_team, away_team, market_type, 
                   prediction, odds, closing_odds, result, profit, created_at
            FROM predictions
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = c.fetchall()
        conn.close()
        
        predictions = []
        for row in rows:
            pred = {
                'id': row[0],
                'fixture_id': row[1],
                'home_team': row[2],
                'away_team': row[3],
                'market_type': row[4],
                'prediction': row[5],
                'odds': row[6],
                'closing_odds': row[7],
                'result': row[8],
                'profit': row[9],
                'created_at': row[10]
            }
            
            # Calculate CLV if both odds available
            if pred['odds'] and pred['closing_odds']:
                pred['clv'] = round((pred['odds'] / pred['closing_odds'] - 1) * 100, 2)
            else:
                pred['clv'] = None
            
            predictions.append(pred)
        
        return predictions


if __name__ == "__main__":
    # Test
    from datetime import timedelta
    
    tracker = CLVTracker()
    
    # Record test prediction
    pred_id = tracker.record_prediction(
        fixture_id=12345,
        home_team="Bayern",
        away_team="Dortmund",
        market_type="BTTS",
        prediction="Yes",
        odds=1.85,
        model_probability=62.5,
        confidence=75
    )
    print(f"Recorded prediction ID: {pred_id}")
    
    # Update closing odds
    tracker.update_closing_odds(pred_id, 1.72)
    clv = (1.85 / 1.72 - 1) * 100
    print(f"CLV: {clv:.2f}%")
    
    # Settle
    tracker.settle_prediction(pred_id, 'Won', 2, 1)
    
    # Stats
    stats = tracker.get_clv_statistics(days=30)
    print(f"\nCLV Statistics:")
    print(f"  Total Bets: {stats['total_bets']}")
    print(f"  Avg CLV: {stats['avg_clv']}%")
    print(f"  Win Rate: {stats['win_rate']}%")
    print(f"  ROI: {stats['roi']}%")
