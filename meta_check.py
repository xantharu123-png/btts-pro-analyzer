import sqlite3, json
conn = sqlite3.connect(r"C:\Users\miros\Desktop\BetBoy\betboy-app\shadow_clv.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM shadow_meta")
rows = [dict(r) for r in cur.fetchall()]
print(json.dumps(rows, indent=2, default=str))
conn.close()
