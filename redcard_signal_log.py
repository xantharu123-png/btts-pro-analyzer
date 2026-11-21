"""Shadow-Logging der Rotkarten-Nächstes-Tor-Signale.

Sammelt geeignete, frische Platzverweis-Prognosen des Scans, auch wenn niemand
die Detailkarte öffnet. Diese Forschungsreihe ist nicht die öffentliche
Live-Bilanz. Gespeichert werden alle drei Modellwahrscheinlichkeiten
(11-Mann trifft / 10-Mann trifft / kein Tor mehr) zum Modell-Snapshot.

Nach Abpfiff wird jedes offene Signal gegen die echten API-Events
abgerechnet: Das erste Tor NACH dem Modell-Snapshot entscheidet das Outcome
(opponent / red_team / no_goal). Ergebnis: Kalibrierungsdaten
(Trefferquote + Brier-Score) als neue, zeitlich nachgelagerte Shadow-Stichprobe.

CLI:
    python redcard_signal_log.py --settle [--max 25]
    python redcard_signal_log.py --stats
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from red_card_impact_predictor import RED_CARD_MODEL_VERSION
from redcard_events import (FINISHED_STATUSES, period_clock as _period_clock, regulation_clock,
                            response_rows as _response_rows, scoring_goal, verified_next_goal)

DB_PATH = Path(__file__).resolve().parent / "redcard_signals.db"
RED_CARD_POLICY_VERSION = "next-goal-shadow-v3"

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
    model_version TEXT,
    policy_version TEXT,
    UNIQUE(fixture_id, minute)
);
"""


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(signals)")
    }
    for column in ("model_version", "policy_version"):
        if column not in existing:
            conn.execute(f"ALTER TABLE signals ADD COLUMN {column} TEXT")
    return conn


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_score(score: Any) -> tuple[Optional[int], Optional[int]]:
    if not isinstance(score, str) or "-" not in score:
        return None, None
    left, _, right = score.partition("-")
    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return None, None


def _snapshot_order(row) -> Optional[tuple[int, int, int]]:
    minute = row["minute"]
    raw = row["context_json"] if "context_json" in row.keys() else None
    try:
        context = json.loads(raw) if raw is not None else {}
    except (ValueError, TypeError):
        return None
    if not isinstance(context, dict):
        return None
    native = context.get("snapshot_clock")
    if native is not None:
        if (not isinstance(native, dict) or set(native) != {"phase", "elapsed", "extra"}
                or native["elapsed"] != minute):
            return None
        return _period_clock(native["phase"], native["elapsed"], native["extra"])
    # Legacy rows have no native phase. The score/timeline consistency check
    # below keeps ambiguous 45+x snapshots open instead of inventing a phase.
    return _period_clock("1H" if minute <= 45 else "2H", minute)


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
        probabilities = (p_opponent, p_red_team, p_no_goal)
        if (
            any(value is None or not 0.0 <= value <= 1.0 for value in probabilities)
            or not math.isclose(sum(probabilities), 1.0, abs_tol=1e-4)
        ):
            return False
        if entry.get("fixture_red_card_count") != 1:
            return False
        score_home, score_away = _parse_score(entry.get("score"))
        league = match.get("league") or {}
        context = {
            "league": league.get("name"),
            "context_effects": prediction.get("context_effects"),
            "snapshot_clock": None,
        }
        native_status = fixture.get("status")
        if native_status is not None:
            if not isinstance(native_status, dict):
                return False
            if "short" in native_status:
                native = {"phase": native_status["short"], "elapsed": native_status.get("elapsed"),
                          "extra": 0 if native_status.get("extra") is None else native_status["extra"]}
                if native["elapsed"] != minute or _period_clock(**native) is None:
                    return False
                context["snapshot_clock"] = native
        conn = _connect(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute(
                "SELECT 1 FROM signals WHERE fixture_id = ? LIMIT 1",
                (fixture_id,),
            ).fetchone():
                conn.rollback()
                return False
            cursor = conn.execute(
                """INSERT OR IGNORE INTO signals
                   (ts_utc, fixture_id, home, away, minute, red_side,
                    red_card_minute, score_home, score_away,
                    p_opponent, p_red_team, p_no_goal, data_quality,
                    context_json, model_version, policy_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    RED_CARD_MODEL_VERSION,
                    RED_CARD_POLICY_VERSION,
                ),
            )
            conn.commit()
            return cursor.rowcount == 1
        finally:
            conn.close()
    except Exception:
        return False


def _first_goal_after(
    events: list, minute: int, status: Optional[str] = None,
    *, snapshot_order: Optional[tuple[int, int, int]] = None,
) -> Optional[tuple[int, Optional[int]]]:
    """Clock-only convenience for callers without a snapshot score; not evidence."""
    snapshot_order = snapshot_order or _period_clock("1H" if minute <= 45 else "2H", minute)
    if snapshot_order is None:
        return None
    later = []
    for event in events or []:
        try:
            if not isinstance(event, dict) or not scoring_goal(event):
                continue
            clock = regulation_clock(event, status)
        except ValueError:
            return None
        if clock is not None and clock > snapshot_order:
            later.append((clock, (event.get("team") or {}).get("id")))
    if not later:
        return None
    first = min(clock for clock, _ in later)
    teams = {team for clock, team in later if clock == first}
    return (sum(first[1:]), teams.pop()) if len(teams) == 1 else None


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
    stats = {"settled": 0, "still_running": 0, "skipped": 0,
             "provider_errors": 0, "unverified_events": 0}
    try:
        rows = conn.execute(
            "SELECT * FROM signals WHERE status = 'open' ORDER BY ts_utc LIMIT ?",
            (max_fixtures,),
        ).fetchall()
        for row in rows:
            fixture_id = row["fixture_id"]
            try:
                fixture_response = api._request("fixtures", {"id": fixture_id})
                payload = _response_rows(fixture_response, api)
                if payload is None:
                    stats["provider_errors"] += 1
                    stats["skipped"] += 1
                    continue
                if len(payload) != 1 or not isinstance(payload[0], dict):
                    stats["skipped"] += 1
                    continue
                fixture_data = payload[0]
                native_id = (fixture_data.get("fixture") or {}).get("id")
                if isinstance(native_id, bool) or not isinstance(native_id, int) or native_id != fixture_id:
                    stats["skipped"] += 1
                    continue
                status = (
                    ((fixture_data.get("fixture") or {}).get("status") or {})
                    .get("short")
                )
                time.sleep(sleep_seconds)
                if status not in FINISHED_STATUSES:
                    stats["still_running"] += 1
                    continue
                events_response = api._request("fixtures/events", {"fixture": fixture_id})
                events = _response_rows(events_response, api)
                if events is None:
                    stats["provider_errors"] += 1
                    stats["skipped"] += 1
                    continue
                time.sleep(sleep_seconds)
            except Exception:
                stats["provider_errors"] += 1
                stats["skipped"] += 1
                continue

            verified = verified_next_goal(
                fixture_data, events, snapshot_order=_snapshot_order(row),
                baseline=(row["score_home"], row["score_away"]),
            )
            if verified is None or row["red_side"] not in ("home", "away"):
                stats["unverified_events"] += 1
                stats["skipped"] += 1
                continue
            side, _ = verified
            outcome = ("no_goal" if side == "no_goal" else
                       "red_team" if side == row["red_side"] else "opponent")
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


def settlement_stats(
    db_path: Path = DB_PATH,
    *,
    model_version: str = RED_CARD_MODEL_VERSION,
    policy_version: str = RED_CARD_POLICY_VERSION,
) -> Dict[str, Any]:
    model = str(model_version or "").strip()
    policy = str(policy_version or "").strip()
    if not model or not policy:
        raise ValueError("model_version and policy_version are required")
    version_where = "model_version = ? AND policy_version = ?"
    version_params = (model, policy)
    conn = _connect(db_path)
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM signals WHERE {version_where}",
            version_params,
        ).fetchone()[0]
        open_count = conn.execute(
            f"SELECT COUNT(*) FROM signals WHERE status = 'open' AND {version_where}",
            version_params,
        ).fetchone()[0]
        settled = conn.execute(
            f"SELECT COUNT(*) FROM signals WHERE status = 'settled' AND {version_where}",
            version_params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT outcome, COUNT(*) AS n, AVG(brier) AS brier
                FROM signals
                WHERE status = 'settled' AND {version_where}
                GROUP BY outcome""",
            version_params,
        ).fetchall()
        by_outcome = {
            row["outcome"]: {"n": row["n"], "brier": round(row["brier"] or 0.0, 4)}
            for row in rows
        }
        # Top-Auswahl-Trefferquote: wie oft traf die hoechste Wahrscheinlichkeit
        top_rows = conn.execute(
            f"""SELECT p_opponent, p_red_team, p_no_goal, outcome
                FROM signals
                WHERE status = 'settled' AND {version_where}""",
            version_params,
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
            "model_version": model,
            "policy_version": policy,
        }
    finally:
        conn.close()


def _has_open_shadow(path: Path) -> bool:
    """Probe the existing queue without creating/migrating its database."""
    if not path.exists():
        return False
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return conn.execute("SELECT 1 FROM signals WHERE status='open' LIMIT 1").fetchone() is not None
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--settle", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--max", type=int, default=25)
    args = parser.parse_args()
    exit_status = 0

    if args.settle:
        from api_football import APIFootball
        from config_loader import load_app_config
        from live_tip_ledger import settle_displayed_live_tips

        config = load_app_config()
        api = APIFootball(
            config.api_football_key,
            budget_priority="critical",
        )
        # The existing result timer has one fixture budget, not one per ledger.
        limit = max(0, args.max)
        shadow_waiting = limit > 0 and _has_open_shadow(DB_PATH)
        # Public gets first use of all but one slot when both queues have work.
        # The existing timer is daily; for a one-fixture budget alternate UTC days.
        reserve = int(shadow_waiting and (limit > 1 or datetime.now(timezone.utc).date().toordinal() % 2 == 1))
        public = settle_displayed_live_tips(api, max_fixtures=limit - reserve)
        print(f"Live-Anzeigen: {public}")
        remaining = limit - public["fixtures_checked"]
        if public["provider_errors"]:
            exit_status = 1
        elif shadow_waiting and remaining > 0:
            result = settle_open_signals(api, max_fixtures=remaining)
            print(f"Settlement: {result}")
            if result.get("provider_errors", 0) > 0:
                exit_status = 1
    if args.stats or not (args.settle or args.stats):
        print(json.dumps(settlement_stats(), indent=2, ensure_ascii=False))
    return exit_status


if __name__ == "__main__":
    raise SystemExit(main())
