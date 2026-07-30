import sqlite3

DB_PATH = r"C:\Users\miros\Desktop\BetBoy\betboy-app\shadow_clv.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== shadow_fixtures columns ===")
cur.execute("PRAGMA table_info(shadow_fixtures)")
for r in cur.fetchall():
    print(r)

print("\n=== predictions columns ===")
cur.execute("PRAGMA table_info(predictions)")
for r in cur.fetchall():
    print(r)

print("\n=== Sample shadow_fixtures (today, first 5) ===")
cur.execute("SELECT * FROM shadow_fixtures WHERE zurich_date = date('now') LIMIT 5")
for r in cur.fetchall():
    print(dict(r))

print("\n=== Sample shadow_fixtures (today, evaluated=0, first 5) ===")
cur.execute("SELECT * FROM shadow_fixtures WHERE zurich_date = date('now') AND evaluated = 0 LIMIT 5")
for r in cur.fetchall():
    print(dict(r))

conn.close()
