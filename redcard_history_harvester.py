"""Incremental red-card history harvester (rolling 12-month window).

Design: fixture lists cost one API call per league+season; the expensive
part is /fixtures/events per match. This script therefore keeps a local
SQLite backlog (redcard_history.db) and works through it with a per-run
API-call budget. Safe to kill and resume at any point — all state is in
the database, never in memory.

Usage:
    python redcard_history_harvester.py [--budget 350] [--report]
"""

import argparse
import json
import sqlite3
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from config_loader import load_app_config
from api_football import APIFootball
from league_catalog import LEAGUE_BY_ID
from redcard_events import (FINISHED_STATUSES, HISTORY_POLICY, regulation_clock, regulation_result,
                            score_pair, verified_goal_timeline)

DB_PATH = Path(__file__).parent / "redcard_history.db"
HISTORY_START = date(2025, 8, 1)
DISMISSAL_MARKERS = ("Red", "Second Yellow")

# Harvest order: leagues where the user actually bets, first.
PRIORITY_LEAGUE_IDS = [
    78, 39, 140, 135, 61,   # top 5
    88, 94, 203, 144, 179,  # NL, PT, TR, BE, SCO
    207, 218, 40, 79,       # CH, AT, ELC, BL2
    119, 103, 113, 106, 345,  # DEN, NOR, SWE, POL, CZE
    197, 283, 210, 286, 333,  # GRE, ROU, CRO, SRB, UKR
    271,                    # HUN (Ferencvaros & co.)
    71, 128,                # BRA, ARG
    2, 3, 848,              # UCL, UEL, UECL
]
SEASONS_IN_WINDOW = (2025, 2026)


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS fixtures (
            fixture_id INTEGER PRIMARY KEY,
            league_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            match_date TEXT NOT NULL,
            status_short TEXT NOT NULL,
            home_id INTEGER NOT NULL,
            away_id INTEGER NOT NULL,
            home_name TEXT NOT NULL,
            away_name TEXT NOT NULL,
            final_home INTEGER,
            final_away INTEGER,
            events_fetched INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS dismissals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id INTEGER NOT NULL,
            match_date TEXT NOT NULL,
            league_id INTEGER NOT NULL,
            league_name TEXT NOT NULL,
            home_name TEXT NOT NULL,
            away_name TEXT NOT NULL,
            final_home INTEGER,
            final_away INTEGER,
            red_minute INTEGER NOT NULL,
            red_side TEXT NOT NULL,
            red_team_name TEXT NOT NULL,
            score_at_red_home INTEGER NOT NULL,
            score_at_red_away INTEGER NOT NULL,
            red_team_goal_diff INTEGER NOT NULL,
            complex_state INTEGER NOT NULL DEFAULT 0,
            goals_after_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(fixture_id, red_minute)
        )"""
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    # Additive only. No backfill or automatic API re-scan of legacy cases.
    for table, additions in (
        ("fixtures", {"regulation_home": "INTEGER", "regulation_away": "INTEGER",
                      "halftime_home": "INTEGER", "halftime_away": "INTEGER"}),
        ("dismissals", {"evidence_policy": "TEXT", "exposure_usable": "INTEGER"}),
    ):
        columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for column, datatype in additions.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {datatype}")
    conn.commit()
    return conn


def _is_dismissal(event: Dict) -> bool:
    if event.get("type") != "Card":
        return False
    detail = str(event.get("detail") or "")
    return any(marker in detail for marker in DISMISSAL_MARKERS)


def extract_dismissal_case(fixture: Dict, events: List[Dict]) -> Optional[Dict]:
    """Research only: verify regulation goals, then isolate the first 11v10 phase."""
    goals = verified_goal_timeline(fixture, events)
    if goals is None:
        return None
    status = fixture["fixture"]["status"]["short"]
    sides = {fixture["teams"][s]["id"]: s for s in ("home", "away")}
    cards = []
    for event in events:
        if not _is_dismissal(event):
            continue
        try:
            clock = regulation_clock(event, status)
        except ValueError:
            return None
        if clock is None:  # ET dismissal after the regulation observation
            continue
        team = event.get("team")
        team_id = team.get("id") if isinstance(team, dict) else None
        if type(team_id) is not int or team_id not in sides:
            return None
        cards.append((clock, sides[team_id], team.get("name") or "?"))
    if not cards:
        return None
    cards.sort(key=lambda card: card[0])
    red, red_side, team_name = cards[0]
    second = cards[1][0] if len(cards) > 1 else None
    if red == second or any(clock == red or clock == second for clock, _ in goals):
        return None  # no evidenced ordering at the boundary
    score_h = sum(1 for clock, side in goals if clock < red and side == "home")
    score_a = sum(1 for clock, side in goals if clock < red and side == "away")
    red_minute = sum(red[1:])
    goals_after = []
    exposure_usable = not (red[0] == 1 and red[2])
    for clock, side in goals:
        if clock <= red or (second is not None and clock >= second):
            continue
        minute = sum(clock[1:])
        since = minute - red_minute
        if clock[0] == 1 and clock[2]:
            exposure_usable = False  # no first-half whistle for continuous exposure
        if red[0] == 1 and red[2] and clock[0] == 2:
            since = None
        goals_after.append({"minute": minute, "by_11_team": side != red_side, "since_card": since})
    final_home, final_away = regulation_result(fixture)
    return {
        "red_minute": red_minute, "red_side": red_side, "red_team_name": team_name,
        "score_at_red_home": score_h, "score_at_red_away": score_a,
        "red_team_goal_diff": (score_h - score_a) if red_side == "home" else (score_a - score_h),
        "complex_state": int(second is not None), "goals_after": goals_after,
        "final_home": final_home, "final_away": final_away, "exposure_usable": exposure_usable,
    }


class RedCardHistoryHarvester:
    def __init__(self, api: APIFootball, conn: sqlite3.Connection):
        self.api = api
        self.conn = conn
        self.calls_used = 0

    def _get(self, endpoint: str, params: Dict) -> List[Dict]:
        self.calls_used += 1
        response = self.api._get(
            f"{self.api.base_url}/{endpoint}",
            headers=self.api.headers,
            params=params,
            timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError(f"provider error on {endpoint}: HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("errors") or not isinstance(payload.get("response"), list):
            raise RuntimeError(f"invalid provider response on {endpoint}")
        return payload["response"]

    def ingest_fixture_lists(self, budget: int) -> None:
        """One call per league+season; skips combos already ingested."""
        for league_id in PRIORITY_LEAGUE_IDS:
            league = LEAGUE_BY_ID.get(league_id)
            if league is None:
                continue
            for season in SEASONS_IN_WINDOW:
                key = f"ingested_{league_id}_{season}"
                if self.conn.execute(
                    "SELECT value FROM meta WHERE key = ?", (key,)
                ).fetchone():
                    continue
                if self.calls_used >= budget:
                    return
                fixtures = self._get(
                    "fixtures", {"league": league_id, "season": season}
                )
                rows = []
                for fx in fixtures:
                    try:
                        fixture_id = fx["fixture"]["id"]
                        status = fx["fixture"]["status"]["short"]
                        match_date = fx["fixture"]["date"][:10]
                        home = fx["teams"]["home"]
                        away = fx["teams"]["away"]
                        final_home = fx["goals"]["home"]
                        final_away = fx["goals"]["away"]
                    except (KeyError, TypeError):
                        continue
                    if status not in FINISHED_STATUSES:
                        continue
                    regulation = regulation_result(fx)
                    if regulation is None:
                        continue
                    halftime = (fx.get("score") or {}).get("halftime")
                    half_pair = score_pair(halftime)
                    if half_pair is None and halftime is not None and halftime != {"home": None, "away": None}:
                        continue
                    if match_date < HISTORY_START.isoformat():
                        continue
                    rows.append(
                        (
                            fixture_id, league_id, season, match_date, status,
                            home["id"], away["id"], home["name"], away["name"],
                            final_home, final_away, *regulation, *(half_pair or (None, None)),
                        )
                    )
                self.conn.executemany(
                    """INSERT OR IGNORE INTO fixtures (
                        fixture_id, league_id, season, match_date,
                        status_short, home_id, away_id, home_name, away_name,
                        final_home, final_away, regulation_home, regulation_away, halftime_home, halftime_away
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
                self.conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    (key, datetime.now(timezone.utc).isoformat()),
                )
                self.conn.commit()
                print(
                    f"  Liste {league.name} ({league.country}) Saison {season}: "
                    f"{len(rows)} Spiele im Fenster"
                )

    def harvest_events(self, budget: int) -> Dict[str, int]:
        """Newest-first: recent matches matter most for current patterns."""
        stats = {"fetched": 0, "dismissals": 0}
        cursor = self.conn.execute(
            """SELECT fixture_id, league_id, match_date, home_name, away_name, status_short,
                      home_id, away_id, final_home, final_away, regulation_home, regulation_away,
                      halftime_home, halftime_away
               FROM fixtures
               WHERE events_fetched = 0
               ORDER BY match_date DESC, fixture_id DESC"""
        )
        for (fixture_id, league_id, match_date, home_name, away_name, status, home_id, away_id,
             final_home, final_away, regulation_home, regulation_away, halftime_home, halftime_away) in cursor:
            if self.calls_used >= budget:
                break
            try:
                events = self._get("fixtures/events", {"fixture": fixture_id})
            except Exception as exc:
                print(f"  WARN events {fixture_id}: {exc}")
                self.conn.execute(
                    "UPDATE fixtures SET events_fetched = -1 WHERE fixture_id = ?",
                    (fixture_id,),
                )
                self.conn.commit()
                continue
            stats["fetched"] += 1
            fixture_stub = {
                "fixture": {"status": {"short": status}},
                "teams": {
                    "home": {"id": home_id},
                    "away": {"id": away_id},
                },
                "goals": {"home": final_home, "away": final_away},
            }
            if regulation_home is not None or regulation_away is not None:
                fixture_stub["score"] = {"fulltime": {"home": regulation_home, "away": regulation_away}}
            if halftime_home is not None or halftime_away is not None:
                fixture_stub.setdefault("score", {})["halftime"] = {"home": halftime_home, "away": halftime_away}
            case = extract_dismissal_case(fixture_stub, events)
            if case is not None:
                league = LEAGUE_BY_ID.get(league_id)
                inserted = self.conn.execute(
                    """INSERT OR IGNORE INTO dismissals (
                        fixture_id, match_date, league_id, league_name,
                        home_name, away_name, final_home, final_away,
                        red_minute, red_side, red_team_name,
                        score_at_red_home, score_at_red_away,
                        red_team_goal_diff, complex_state,
                        goals_after_json, created_at, evidence_policy, exposure_usable
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        fixture_id, match_date, league_id,
                        league.name if league else str(league_id),
                        home_name, away_name,
                        case["final_home"], case["final_away"],
                        case["red_minute"], case["red_side"],
                        case["red_team_name"],
                        case["score_at_red_home"], case["score_at_red_away"],
                        case["red_team_goal_diff"], case["complex_state"],
                        json.dumps(case["goals_after"], ensure_ascii=False),
                        datetime.now(timezone.utc).isoformat(), HISTORY_POLICY, int(case["exposure_usable"]),
                    ),
                )
                stats["dismissals"] += inserted.rowcount
            self.conn.execute(
                "UPDATE fixtures SET events_fetched = 1 WHERE fixture_id = ?",
                (fixture_id,),
            )
            if stats["fetched"] % 50 == 0:
                self.conn.commit()
                print(
                    f"  ... {stats['fetched']} Spiele, "
                    f"{stats['dismissals']} Platzverweise"
                )
            time.sleep(0.12)  # provider politeness
        self.conn.commit()
        return stats

    def backlog(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM fixtures WHERE events_fetched = 0"
        ).fetchone()
        return row[0] if row else 0

    def totals(self) -> Dict[str, int]:
        fetched = self.conn.execute(
            "SELECT COUNT(*) FROM fixtures WHERE events_fetched = 1"
        ).fetchone()[0]
        dismissals = self.conn.execute(
            "SELECT COUNT(*) FROM dismissals"
        ).fetchone()[0]
        return {"events_fetched": fetched, "dismissals": dismissals}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=350,
                        help="max provider calls this run")
    parser.add_argument("--report", action="store_true",
                        help="run redcard_pattern_report.py afterwards")
    args = parser.parse_args()

    cfg = load_app_config()
    api = APIFootball(
        cfg.api_football_key,
        budget_priority="background",
    )
    conn = connect()
    harvester = RedCardHistoryHarvester(api, conn)

    print(f"Budget: {args.budget} Calls | Backlog vorher: {harvester.backlog()}")
    harvester.ingest_fixture_lists(args.budget)
    stats = harvester.harvest_events(args.budget)
    totals = harvester.totals()
    print(
        f"Fertig: {stats['fetched']} Spiele gescannt, "
        f"{stats['dismissals']} Platzverweise neu | "
        f"Historie gesamt: {totals['dismissals']} Platzverweise aus "
        f"{totals['events_fetched']} Spielen | "
        f"Backlog nachher: {harvester.backlog()} | "
        f"Calls: {harvester.calls_used}"
    )

    if args.report:
        import subprocess
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "redcard_pattern_report.py")],
            check=False,
        )


if __name__ == "__main__":
    main()
