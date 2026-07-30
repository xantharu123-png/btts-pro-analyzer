#!/usr/bin/env python3
"""Tägliche Shadow-CLV-Zusammenfassung."""
import sqlite3, os, sys, json, traceback
from datetime import datetime, timezone, timedelta

db_path = r"C:\Users\miros\Desktop\BetBoy\betboy-app\shadow_clv.db"
output = []

def log(*args):
    output.append(" ".join(str(a) for a in args))

try:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    # --- Schema ---------------------------------------------------------------
    log("=== SCHEMA ===")
    for row in c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        log(f"\n--- {row['name']} ---")
        log(row['sql'])

    # --- Prüfen welche Spalten es gibt in predictions -------------------------
    cols = [r[1] for r in c.execute("PRAGMA table_info(predictions)").fetchall()]
    log(f"\n=== predictions columns: {cols} ===")

    # --- Fixtures heute (Zürich) ---------------------------------------------
    zurich_now = datetime.now(timezone(timedelta(hours=2)))
    today_str = zurich_now.strftime("%Y-%m-%d")
    log(f"\n=== FIXTURES (Zürich heute = {today_str}) ===")
    total_fix = c.execute("SELECT COUNT(*) FROM shadow_fixtures WHERE DATE(kickoff)=?", (today_str,)).fetchone()[0]
    evaluated = c.execute("SELECT COUNT(*) FROM shadow_fixtures WHERE DATE(kickoff)=? AND evaluated=1", (today_str,)).fetchone()[0]
    unevaluated = c.execute("SELECT COUNT(*) FROM shadow_fixtures WHERE DATE(kickoff)=? AND (evaluated=0 OR evaluated IS NULL)", (today_str,)).fetchone()[0]
    log(f"Total: {total_fix} | Evaluated: {evaluated} | Unevaluated: {unevaluated}")

    # --- Heutige Picks --------------------------------------------------------
    log(f"\n=== TODAY'S PICKS ({today_str}) ===")
    today_preds = c.execute(f"""
        SELECT * FROM predictions
        WHERE DATE(created_at)=?
        ORDER BY id DESC
    """, (today_str,)).fetchall()
    log(f"Anzahl heute geloggte Picks: {len(today_preds)}")

    # Neueste 15 insgesamt (für Übersicht)
    latest_15 = c.execute(f"""
        SELECT id, home_team, away_team, market_type, prediction, odds, closing_odds,
               model_probability, confidence, result, profit, created_at
        FROM predictions
        ORDER BY id DESC
        LIMIT 15
    """).fetchall()
    log(f"\nNeueste 15 Predictions (nach id DESC):")
    for p in latest_15:
        profit_str = f"  Profit={p['profit']}" if p['profit'] is not None else ""
        closing_str = f"  closing={p['closing_odds']}" if p['closing_odds'] is not None else "  closing=—"
        log(f"  #{p['id']} {p['home_team']} v {p['away_team']} | {p['market_type']} | {p['prediction']} | Quote={p['odds']}{closing_str} | Modell={p['model_probability']}%{profit_str} | {p['created_at']}")

    # --- Tagesbilanz ----------------------------------------------------------
    log(f"\n=== TAGESBILANZ ({today_str}) ===")
    total_today = len(today_preds)
    with_closing = sum(1 for p in today_preds if p['closing_odds'] is not None)
    settled = sum(1 for p in today_preds if p['result'] in ('won','lost'))
    day_profit = sum(p['profit'] or 0 for p in today_preds)
    log(f"Geloggte Picks: {total_today}")
    log(f"Mit Closing-Quote: {with_closing}")
    log(f"Abgerechnet (won/lost): {settled}")
    log(f"Tages-Profit: {day_profit:.2f}")

    # --- Kumulierte Statistik -------------------------------------------------
    log(f"\n=== KUMULIERT ===")
    all_preds = c.execute("SELECT * FROM predictions").fetchall()
    total_all = len(all_preds)
    with_closing_all = sum(1 for p in all_preds if p['closing_odds'] is not None)
    settled_all = sum(1 for p in all_preds if p['result'] in ('won','lost'))
    wins_all = sum(1 for p in all_preds if p['result'] == 'won')
    total_profit = sum((p['profit'] or 0) for p in all_preds)
    winrate = (wins_all / settled_all * 100) if settled_all > 0 else 0

    log(f"Gesamtanzahl Wetten: {total_all}")
    log(f"Mit Closing-Quote: {with_closing_all}")
    log(f"Abgerechnet: {settled_all} (Won: {wins_all})")
    log(f"Win-Rate: {winrate:.1f}%")
    log(f"Gesamt-Profit: {total_profit:.2f}")

    # CLV Berechnung
    if 'clv' in cols:
        clv_rows = c.execute("SELECT clv FROM predictions WHERE clv IS NOT NULL").fetchall()
        if clv_rows:
            avg_clv = sum(r['clv'] for r in clv_rows) / len(clv_rows)
            log(f"Durchschnittlicher CLV (Spalte): {avg_clv:.2f}%")
        else:
            log("CLV-Spalte vorhanden, aber keine Werte.")
    if with_closing_all > 0:
        clv_vals = []
        for p in all_preds:
            if p['closing_odds'] is not None and p['odds'] is not None and p['closing_odds'] > 0:
                clv = (p['odds'] / p['closing_odds'] - 1) * 100
                clv_vals.append(clv)
        if clv_vals:
            avg_clv_calc = sum(clv_vals) / len(clv_vals)
            log(f"Durchschnittlicher CLV (berechnet aus odds/closing_odds): {avg_clv_calc:.2f}% (n={len(clv_vals)})")
        else:
            log("Keine CLV-berechenbaren Daten.")
    else:
        log("Keine Closing-Odds vorhanden → CLV nicht berechenbar.")

    # --- Recent 30 days for trend ---------------------------------------------
    thirty_days_ago = (zurich_now - timedelta(days=30)).strftime("%Y-%m-%d")
    recent_preds = c.execute("SELECT * FROM predictions WHERE DATE(created_at)>=?", (thirty_days_ago,)).fetchall()
    recent_settled = sum(1 for p in recent_preds if p['result'] in ('won','lost'))
    recent_wins = sum(1 for p in recent_preds if p['result'] == 'won')
    recent_profit = sum((p['profit'] or 0) for p in recent_preds)
    log(f"\n=== LETZTE 30 TAGE ===")
    log(f"Wetten: {len(recent_preds)} | Abgerechnet: {recent_settled} | Wins: {recent_wins} | Profit: {recent_profit:.2f}")

except Exception as e:
    log(f"FEHLER: {e}")
    traceback.print_exc()

print("\n".join(output))
