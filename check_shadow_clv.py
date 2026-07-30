import sqlite3

DB_PATH = r"C:\Users\miros\Desktop\BetBoy\betboy-app\shadow_clv.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Latest predictions
print("=== predictions (latest 10) ===")
cur.execute("""
    SELECT fixture_id, home_team, away_team, market_type, prediction, odds, closing_odds,
           model_probability, confidence, result
    FROM predictions ORDER BY rowid DESC LIMIT 10
""")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(dict(row))
else:
    print("(empty)")

# 2. Last 2 fixture days
print("\n=== shadow_fixtures (last 2 days) ===")
cur.execute("""
    SELECT zurich_date, COUNT(*) as total, SUM(evaluated) as evaluated_sum
    FROM shadow_fixtures GROUP BY zurich_date ORDER BY zurich_date DESC LIMIT 2
""")
rows = cur.fetchall()
for row in rows:
    print(dict(row))

# 3. Today deferred fixtures
print("\n=== today fixtures evaluated=0 ===")
cur.execute("""
    SELECT COUNT(*) FROM shadow_fixtures
    WHERE zurich_date = date('now') AND evaluated = 0
""")
print("today evaluated=0:", cur.fetchone()[0])

# 4. General stats
print("\n=== overall stats ===")
cur.execute("SELECT COUNT(*) FROM predictions")
print("total predictions:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM predictions WHERE closing_odds IS NOT NULL")
print("predictions with closing_odds:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM shadow_fixtures WHERE evaluated = 0")
print("total fixtures evaluated=0:", cur.fetchone()[0])

conn.close()
