"""Shadow-Logging der Rotkarten-Nächstes-Tor-Signale.

Loggt jede angezeigte Platzverweis-Prediction still mit — unabhaengig davon,
ob der User wettet. Gespeichert werden alle drei Modellwahrscheinlichkeiten
(11-Mann trifft / 10-Mann trifft / kein Tor mehr) zum Modell-Snapshot.

Nach Abpfiff wird jedes offene Signal gegen die echten API-Events
abgerechnet: Das erste Tor NACH dem Modell-Snapshot entscheidet das Outcome
(opponent / red_team / no_goal). Ergebnis: Kalibrierungs-Beweis
(Trefferquote + Brier-Score) gegen die 1.132-Faelle-Historie.

CLI:
    python redcard_signal_log.py --settle [--max 25]
    python redcard_signal_log.py --stats
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path(__file__).resolve().parent / "redcard_signals.db"

FINISHED_STATUSES = {"FT", "AET", "PEN"}

# Modell-Horizont: reguläre Spielzeit. 93 deckt Nachspielzeit im alten
# API-Stil ab (elapsed ohne extra-Feld). Tore mit elapsed 91-93 zählen nur
# bei Endstatus "FT" — bei AET/PEN sind sie bereits Verlängerung. Tore in
# der Verlängerung (bis 120) und im Elfmeterschießen liegen außerhalb des
# Modell-Horizonts und dürfen das Outcome nicht verfälschen.
# Halte diese Regel synchron mit redcard_pattern_report.py.
MODEL_HORIZON_MINUTES = 93


def _goal_in_model_horizon(elapsed: int, status: Optional[str]) -> bool:
    """True, wenn das Tor im Modell-Horizont (reguläre Spielzeit) fiel."""
    if elapsed > MODEL_HORIZON_MINUTES:
        return False
    if elapsed > 90 and status != "FT":
        return False
    return True

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc TEXT NOT NULL,
    fixture_id INTEGER NOT NULL,
    home TEXT,
    away TEXT,
    minute INTEGER NOT NULL,
    red_side TEXT,
    red_card_minute INTEGER,
    score_home INTEGER,
    score_away INTEGER,
    p_opponent REAL,
    p_red_team REAL,
    p_no_goal REAL,
    data_quality TEXT,
    context_json TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    outcome TEXT,
    settled_at TEXT,
    brier REAL,
    UNIQUE(fixture_id, minute)
);
"""


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN-Wache


def _parse_score(score: Any) -> tuple[Optional[int], Optional[int]]:
    if not isinstance(score, str) or "-" not in score:
        return None, None
    left, _, right = score.partition("-")
    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return None, None


def log_signal(entry: Dict[str, Any], db_path: Path = DB_PATH) -> bool:
    """Loggt einen Rotkarten-Snapshot-Eintrag (app.py _red_card_entry).

    Still und fail-safe: Gibt True zurueck, wenn ein neues Signal geschrieben
    wurde, False bei Duplikat (gleiche fixture_id + Minute) oder ungenuegenden
    Daten. Wirft niemals.
    """
    try:
        if not isinstance(entry, dict) or entry.get("error"):
            return False
        prediction = entry.get("prediction")
        if not isinstance(prediction, dict):
            return False
        if prediction.get("too_late_for_signal") is True:
            return False
        card = entry.get("card") or {}
        match = card.get("match") or {}
        fixture = match.get("fixture") or {}
        fixture_id = fixture.get("id")
        minute = entry.get("prediction_minute")
        if not isinstance(fixture_id, int) or not isinstance(minute, int):
            return False
        p_opponent = _finite(prediction.get("next_goal_by_opponent"))
        p_red_team = _finite(prediction.get("next_goal_by_red_team"))
        p_no_goal = _finite(prediction.get("no_more_goals"))
        if p_opponent is None and p_red_team is None and p_no_goal is None:
            return False
        score_home, score_away = _parse_score(entry.get("score"))
        league = match.get("league") or {}
        context = {
            "league": league.get("name"),
            "context_effects": prediction.get("context_effects"),
        }
        conn = _connect(db_path)
        try:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO signals
                   (ts_utc, fixture_id, home, away, minute, red_side,
                    red_card_minute, score_home, score_away,
                    p_opponent, p_red_team, p_no_goal, data_quality,
                    context_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    fixture_id,
                    entry.get("home"),
                    entry.get("away"),
                    minute,
                    entry.get("red_side"),
                    card.get("minute"),
                    score_home,
                    score_away,
                    p_opponent,
                    p_red_team,
                    p_no_goal,
                    prediction.get("data_quality"),
                    json.dumps(context, ensure_ascii=False),
                ),
            )
            conn.commit()
            return cursor.rowcount == 1
        finally:
            conn.close()
    except Exception:
        return False


def _first_goal_after(
    events: list, minute: int, status: Optional[str] = None
) -> Optional[tuple[int, Optional[int]]]:
    """(elapsed, team_id) des ersten Tors nach dem Modell-Snapshot, sonst None.

    Zählt nur Tore im Modell-Horizont (reguläre Spielzeit, siehe
    _goal_in_model_horizon) — Verlängerung und Elfmeterschießen sind
    kein Modell-Outcome.
    """
    first: Optional[tuple[int, Optional[int]]] = None
    for event in events or []:
        if not isinstance(event, dict) or event.get("type") != "Goal":
            continue
        elapsed = (event.get("time") or {}).get("elapsed")
        if not isinstance(elapsed, int) or elapsed <= minute:
            continue
        if not _goal_in_model_horizon(elapsed, status):
            continue
        team_id = (event.get("team") or {}).get("id")
        if first is None or elapsed < first[0]:
            first = (elapsed, team_id)
    return first


def settle_open_signals(
    api,
    *,
    max_fixtures: int = 25,
    sleep_seconds: float = 0.15,
    db_path: Path = DB_PATH,
) -> Dict[str, int]:
    """Rechnet offene Signale gegen die API ab (2 Calls pro Fixture).

    outcome: 'opponent' (11-Mann-Team traf zuerst), 'red_team' (10-Mann-Team
    traf zuerst) oder 'no_goal'. Brier = Summe (p_i - o_i)^2 ueber 3 Klassen.
    """
    conn = _connect(db_path)
    stats = {"settled": 0, "still_running": 0, "skipped": 0}
    try:
        rows = conn.execute(
            "SELECT * FROM signals WHERE status = 'open' ORDER BY ts_utc LIMIT ?",
            (max_fixtures,),
        ).fetchall()
        for row in rows:
            fixture_id = row["fixture_id"]
            try:
                fixture_response = api._request("fixtures", {"id": fixture_id})
                payload = (fixture_response or {}).get("response") or []
                if not payload:
                    stats["skipped"] += 1
                    continue
                fixture_data = payload[0]
                status = (
                    ((fixture_data.get("fixture") or {}).get("status") or {})
                    .get("short")
                )
                time.sleep(sleep_seconds)
                if status not in FINISHED_STATUSES:
                    stats["still_running"] += 1
                    continue
                events_response = api._request("events", {"fixture": fixture_id})
                events = (events_response or {}).get("response") or []
                time.sleep(sleep_seconds)
            except Exception:
                stats["skipped"] += 1
                continue

            home_id = ((fixture_data.get("teams") or {}).get("home") or {}).get("id")
            first_goal = _first_goal_after(events, row["minute"], status)
            if first_goal is None:
                outcome = "no_goal"
            elif row["red_side"] == "home":
                outcome = "red_team" if first_goal[1] == home_id else "opponent"
            elif row["red_side"] == "away":
                outcome = "opponent" if first_goal[1] == home_id else "red_team"
            else:
                outcome = None
            if outcome is None:
                stats["skipped"] += 1
                continue
            probs = {
                "opponent": row["p_opponent"] or 0.0,
                "red_team": row["p_red_team"] or 0.0,
                "no_goal": row["p_no_goal"] or 0.0,
            }
            brier = sum(
                (prob - (1.0 if key == outcome else 0.0)) ** 2
                for key, prob in probs.items()
            )
            conn.execute(
                """UPDATE signals
                   SET status = 'settled', outcome = ?, settled_at = ?, brier = ?
                   WHERE id = ?""",
                (outcome, datetime.now(timezone.utc).isoformat(), brier, row["id"]),
            )
            conn.commit()
            stats["settled"] += 1
    finally:
        conn.close()
    return stats


def settlement_stats(db_path: Path = DB_PATH) -> Dict[str, Any]:
    conn = _connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        open_count = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE status = 'open'"
        ).fetchone()[0]
        settled = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE status = 'settled'"
        ).fetchone()[0]
        rows = conn.execute(
            """SELECT outcome, COUNT(*) AS n, AVG(brier) AS brier
               FROM signals WHERE status = 'settled' GROUP BY outcome"""
        ).fetchall()
        by_outcome = {
            row["outcome"]: {"n": row["n"], "brier": round(row["brier"] or 0.0, 4)}
            for row in rows
        }
        # Top-Auswahl-Trefferquote: wie oft traf die hoechste Wahrscheinlichkeit
        top_rows = conn.execute(
            """SELECT p_opponent, p_red_team, p_no_goal, outcome
               FROM signals WHERE status = 'settled'"""
        ).fetchall()
        hits = 0
        for row in top_rows:
            probs = {
                "opponent": row["p_opponent"] or 0.0,
                "red_team": row["p_red_team"] or 0.0,
                "no_goal": row["p_no_goal"] or 0.0,
            }
            if probs and max(probs, key=probs.get) == row["outcome"]:
                hits += 1
        return {
            "total": total,
            "open": open_count,
            "settled": settled,
            "top_pick_hit_rate": round(hits / settled, 4) if settled else None,
            "by_outcome": by_outcome,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--settle", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--max", type=int, default=25)
    args = parser.parse_args()

    if args.settle:
        from api_football import APIFootball
        from config_loader import load_app_config

        config = load_app_config()
        api = APIFootball(config.api_football_key)
        result = settle_open_signals(api, max_fixtures=args.max)
        print(f"Settlement: {result}")
    if args.stats or not (args.settle or args.stats):
        print(json.dumps(settlement_stats(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
