#!/usr/bin/env python3
import sqlite3, json

db = sqlite3.connect(r"C:\Users\miros\Desktop\BetBoy\betboy-app\shadow_clv.db")
db.row_factory = sqlite3.Row
c = db.cursor()

print("=== shadow_meta ===")
for r in c.execute("SELECT * FROM shadow_meta").fetchall():
    print(r[0], r[1])

print("\n=== shadow_fixtures heute ===")
for r in c.execute("SELECT * FROM shadow_fixtures WHERE DATE(kickoff)='2026-07-27' ORDER BY kickoff").fetchall():
    print(json.dumps({k: r[k] for k in r.keys()}, default=str))
