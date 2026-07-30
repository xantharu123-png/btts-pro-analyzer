import sqlite3
import sys

conn = sqlite3.connect('shadow_clv.db')
c = conn.cursor()

print("=== TABLES ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
for r in c.fetchall():
    print(r[0])

print("\n=== predictions SCHEMA ===")
c.execute("PRAGMA table_info(predictions)")
for r in c.fetchall():
    print(r)

print("\n=== shadow_fixtures SCHEMA ===")
c.execute("PRAGMA table_info(shadow_fixtures)")
for r in c.fetchall():
    print(r)

print("\n=== predictions COUNT ===")
c.execute("SELECT COUNT(*) FROM predictions")
print(c.fetchone()[0])

print("\n=== predictions LAST 15 ===")
c.execute("SELECT home_team, away_team, market_type, prediction, odds, closing_odds, model_probability, confidence, result, profit, created_at FROM predictions ORDER BY id DESC LIMIT 15")
for r in c.fetchall():
    print(r)

print("\n=== TODAY PREDICTIONS (by created_at date) ===")
c.execute("SELECT COUNT(*) FROM predictions WHERE date(created_at) = date('now', 'localtime')")
print(c.fetchone()[0])

print("\n=== shadow_fixtures TODAY ===")
c.execute("SELECT COUNT(*), SUM(CASE WHEN evaluated=1 THEN 1 ELSE 0 END), SUM(CASE WHEN evaluated=0 THEN 1 ELSE 0 END) FROM shadow_fixtures WHERE date(kickoff) = date('now', 'localtime')")
print(c.fetchone())

conn.close()
