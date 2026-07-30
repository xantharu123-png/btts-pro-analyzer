import sqlite3, json, sys
from pathlib import Path

db_path = Path(r"C:\Users\miros\Desktop\BetBoy\betboy-app\shadow_clv.db")
if not db_path.exists():
    print(json.dumps({"error": "DB nicht gefunden"}))
    sys.exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

result = {}

# 1. Neueste 15 Predictions (insgesamt, da heute eh 0)
cur.execute("""
    SELECT home_team, away_team, market_type, prediction, odds, closing_odds,
           model_probability, confidence, result, profit, created_at
    FROM predictions
    ORDER BY created_at DESC
    LIMIT 15
""")
rows = [dict(r) for r in cur.fetchall()]
result["latest_predictions"] = rows

# 2. Tagesbilanz heute (Zurich-Date = heute)
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN closing_odds IS NOT NULL THEN 1 ELSE 0 END) as with_closing,
        SUM(CASE WHEN result IN ('Won','Lost') THEN 1 ELSE 0 END) as settled,
        SUM(CASE WHEN result = 'Won' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN result = 'Lost' THEN 1 ELSE 0 END) as lost,
        SUM(profit) as profit
    FROM predictions
    WHERE date(created_at) = date('now', 'localtime')
""")
result["daily_stats"] = dict(cur.fetchone())

# 3. Kumuliert - CLV berechnen aus odds/closing_odds
cur.execute("""
    SELECT 
        COUNT(*) as total_bets,
        SUM(CASE WHEN closing_odds IS NOT NULL AND odds IS NOT NULL THEN 1 ELSE 0 END) as with_closing,
        SUM(CASE WHEN result = 'Won' THEN 1 ELSE 0 END) as won,
        SUM(CASE WHEN result = 'Lost' THEN 1 ELSE 0 END) as lost,
        SUM(CASE WHEN result IN ('Won','Lost') THEN 1 ELSE 0 END) as settled,
        SUM(profit) as profit,
        AVG(
            CASE 
                WHEN closing_odds IS NOT NULL AND odds IS NOT NULL AND odds > 0 
                THEN (odds / closing_odds - 1.0) * 100.0 
                ELSE NULL 
            END
        ) as avg_clv
    FROM predictions
""")
result["all_time_stats"] = dict(cur.fetchone())

# 4. shadow_fixtures heute (zurich_date = heute)
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN evaluated = 1 THEN 1 ELSE 0 END) as evaluated_count,
        SUM(CASE WHEN evaluated = 0 THEN 1 ELSE 0 END) as pending_count
    FROM shadow_fixtures
    WHERE zurich_date = date('now', 'localtime')
""")
result["fixture_stats"] = dict(cur.fetchone())

conn.close()
print(json.dumps(result, indent=2, default=str))
