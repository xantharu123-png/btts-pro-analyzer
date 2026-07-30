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

import requests

sys.path.insert(0, str(Path(__file__).parent))

from config_loader import load_app_config
from api_football import APIFootball
from league_catalog import LEAGUES, LEAGUE_BY_ID

DB_PATH = Path(__file__).parent / "redcard_history.db"
HISTORY_START = date(2025, 8, 1)
FINISHED_STATUSES = {"FT", "AET"}
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
    conn.commit()
    return conn


def _is_dismissal(event: Dict) -> bool:
    if event.get("type") != "Card":
        return False
    detail = str(event.get("detail") or "")
    return any(marker in detail for marker in DISMISSAL_MARKERS)


def _elapsed(event: Dict) -> Optional[int]:
    value = event.get("time", {}).get("elapsed")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def extract_dismissal_case(fixture: Dict, events: List[Dict]) -> Optional[Dict]:
    """Reduce one fixture + its event timeline to the first 11-v-10 phase.

    Returns None when the fixture has no usable dismissal. A second
    dismissal ends the observation window (state becomes 10-v-10 or
    worse) and flags the case complex.
    """
    try:
        home_id = fixture["teams"]["home"]["id"]
        away_id = fixture["teams"]["away"]["id"]
    except (KeyError, TypeError):
        return None

    cards = sorted(
        (
            (minute, event)
            for event in events or []
            if isinstance(event, dict)
            for minute in [_elapsed(event)]
            if minute is not None and _is_dismissal(event)
        ),
        key=lambda item: item[0],
    )
    if not cards:
        return None
    red_minute, red_event = cards[0]
    second_red_minute = cards[1][0] if len(cards) > 1 else None

    try:
        red_team_id = red_event["team"]["id"]
    except (KeyError, TypeError):
        return None
    if red_team_id == home_id:
        red_side = "home"
    elif red_team_id == away_id:
        red_side = "away"
    else:
        return None

    goals = sorted(
        (
            (minute, event)
            for event in events or []
            if isinstance(event, dict) and event.get("type") == "Goal"
            for minute in [_elapsed(event)]
            if minute is not None
        ),
        key=lambda item: item[0],
    )
    score_h = score_a = 0
    for minute, goal in goals:
        if minute >= red_minute:
            break
        if goal.get("team", {}).get("id") == home_id:
            score_h += 1
        elif goal.get("team", {}).get("id") == away_id:
            score_a += 1

    goals_after = []
    for minute, goal in goals:
        if minute <= red_minute:
            continue
        if second_red_minute is not None and minute >= second_red_minute:
            break
        goal_team_id = goal.get("team", {}).get("id")
        if goal_team_id not in (home_id, away_id):
            continue
        by_11 = (goal_team_id != red_team_id)
        goals_after.append(
            {
                "minute": minute,
                "by_11_team": by_11,
                "since_card": minute - red_minute,
            }
        )

    final_home = fixture.get("goals", {}).get("home")
    final_away = fixture.get("goals", {}).get("away")
    goal_diff = (score_h - score_a) if red_side == "home" else (score_a - score_h)
    return {
        "red_minute": red_minute,
        "red_side": red_side,
        "red_team_name": red_event.get("team", {}).get("name", "?"),
        "score_at_red_home": score_h,
        "score_at_red_away": score_a,
        "red_team_goal_diff": goal_diff,
        "complex_state": 1 if second_red_minute is not None else 0,
        "goals_after": goals_after,
        "final_home": final_home if isinstance(final_home, int) else None,
        "final_away": final_away if isinstance(final_away, int) else None,
    }


class RedCardHistoryHarvester:
    def __init__(self, api: APIFootball, conn: sqlite3.Connection):
        self.api = api
        self.conn = conn
        self.calls_used = 0

    def _get(self, endpoint: str, params: Dict) -> List[Dict]:
        response = requests.get(
            f"{self.api.base_url}/{endpoint}",
            headers=self.api.headers,
            params=params,
            timeout=20,
        )
        self.calls_used += 1
        payload = response.json()
        errors = payload.get("errors")
        if errors:
            raise RuntimeError(f"provider error on {endpoint}: {errors}")
        data = payload.get("response", [])
        return data if isinstance(data, list) else []

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
                    if match_date < HISTORY_START.isoformat():
                        continue
                    rows.append(
                        (
                            fixture_id, league_id, season, match_date, status,
                            home["id"], away["id"], home["name"], away["name"],
                            final_home, final_away,
                        )
                    )
                self.conn.executemany(
                    """INSERT OR IGNORE INTO fixtures (
                        fixture_id, league_id, season, match_date,
                        status_short, home_id, away_id, home_name, away_name,
                        final_home, final_away
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            """SELECT fixture_id, league_id, match_date, home_name, away_name
               FROM fixtures
               WHERE events_fetched = 0
               ORDER BY match_date DESC, fixture_id DESC"""
        )
        for fixture_id, league_id, match_date, home_name, away_name in cursor:
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
                "teams": {
                    "home": {"id": self._team_id(fixture_id, "home_id")},
                    "away": {"id": self._team_id(fixture_id, "away_id")},
                },
                "goals": self._final_score(fixture_id),
            }
            case = extract_dismissal_case(fixture_stub, events)
            if case is not None:
                league = LEAGUE_BY_ID.get(league_id)
                self.conn.execute(
                    """INSERT OR IGNORE INTO dismissals (
                        fixture_id, match_date, league_id, league_name,
                        home_name, away_name, final_home, final_away,
                        red_minute, red_side, red_team_name,
                        score_at_red_home, score_at_red_away,
                        red_team_goal_diff, complex_state,
                        goals_after_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                stats["dismissals"] += 1
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

    def _team_id(self, fixture_id: int, column: str) -> int:
        row = self.conn.execute(
            f"SELECT {column} FROM fixtures WHERE fixture_id = ?",
            (fixture_id,),
        ).fetchone()
        return row[0] if row else -1

    def _final_score(self, fixture_id: int) -> Dict:
        row = self.conn.execute(
            "SELECT final_home, final_away FROM fixtures WHERE fixture_id = ?",
            (fixture_id,),
        ).fetchone()
        if not row:
            return {"home": None, "away": None}
        return {"home": row[0], "away": row[1]}

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
    api = APIFootball(cfg.api_football_key)
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
