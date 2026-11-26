"""Prospective, public live selections. Separate from shadow research and money."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time

import redcard_events as evidence
from runtime_paths import RUNTIME_STATE_DIR


DB_PATH = RUNTIME_STATE_DIR / "live_displayed_tips.db"
POLICY_VERSION = "first-displayed-fixture-market-side-regulation-v1"
COMPARISON_POLICY_VERSION = "first-displayed-live-market-uplift-regulation-v1"
LIVE_ONLY_COMPARISON_POLICY_VERSION = "first-displayed-live-market-xg-neutral-split-regulation-v1"
COMPARISON_POLICIES = frozenset({COMPARISON_POLICY_VERSION, LIVE_ONLY_COMPARISON_POLICY_VERSION})
MAX_SNAPSHOT_AGE_SECONDS = 120
SIDES = {"next_goal": ("any",), "team_scores": ("home", "away"), "btts": ("yes",),
         "red_next": ("home", "away", "none")}
TIMELINE_MARKETS = frozenset({"next_goal", "team_scores", "red_next", "next_scorer"})
VOID = {"CANC", "ABD", "AWD", "WO"}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS live_tips (
    id INTEGER PRIMARY KEY,
    fixture_id INTEGER NOT NULL, market TEXT NOT NULL, side TEXT NOT NULL,
    home_id INTEGER NOT NULL, away_id INTEGER NOT NULL,
    minute INTEGER NOT NULL, phase TEXT NOT NULL, extra INTEGER NOT NULL,
    home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL,
    probability REAL NOT NULL CHECK(probability BETWEEN 0 AND 1),
    model_version TEXT NOT NULL, policy_version TEXT NOT NULL,
    snapshot_at TEXT NOT NULL, shown_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','won','lost','void')),
    checks INTEGER NOT NULL DEFAULT 0, settled_at TEXT, result_status TEXT,
    result_home INTEGER, result_away INTEGER, result_next TEXT, result_minute INTEGER,
    UNIQUE(fixture_id,market,side)
);
CREATE INDEX IF NOT EXISTS live_tips_queue ON live_tips(fixture_id) WHERE status='open';
"""


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp needs an explicit timezone")
    return value.astimezone(timezone.utc)


def _now(value):
    return datetime.now(timezone.utc) if value is None else _utc(value)


def _id(value):
    return type(value) is int and 0 < value <= 2**63 - 1


def record_displayed_live_tip(*, fixture_id, market, side, minute, phase, extra,
                              home_goals, away_goals, home_id, away_id, probability,
                              snapshot_at, model_version, policy_version=None, db_path=DB_PATH, now=None) -> bool:
    """Freeze the first valid display only. False = existing receipt, never an error."""
    shown, snapshot = _now(now), _utc(snapshot_at)
    extra = 0 if extra is None else extra
    if not 0 <= (shown - snapshot).total_seconds() <= MAX_SNAPSHOT_AGE_SECONDS:
        raise ValueError("Snapshot is stale or in the future")
    if (not isinstance(market, str) or not isinstance(side, str)
            or not all(_id(x) for x in (fixture_id, home_id, away_id)) or home_id == away_id
            or evidence.period_clock(phase, minute, extra) is None
            or evidence.score_pair({"home": home_goals, "away": away_goals}) is None
            or (market == "btts" and min(home_goals, away_goals) > 0)
            or isinstance(probability, bool) or not isinstance(probability, (int, float))
            or not 0 <= probability <= 1 or not isinstance(model_version, str)
            or not model_version.strip()):
        raise ValueError("Invalid or already decided live selection")
    legacy = side in SIDES.get(market, ())
    if policy_version is None:
        policy_version = POLICY_VERSION if legacy else COMPARISON_POLICY_VERSION
    from live_market_comparison import LIVE_ONLY_MODEL_VERSION, catalog_sides, market_open
    # A live-only forecast may never gain a historical policy via the default
    # path, nor acquire the new policy through an approximate version match.
    if (not isinstance(policy_version, str)
            or (policy_version == LIVE_ONLY_COMPARISON_POLICY_VERSION) != (model_version == LIVE_ONLY_MODEL_VERSION)
            or (model_version.strip() == LIVE_ONLY_MODEL_VERSION and model_version != LIVE_ONLY_MODEL_VERSION)):
        raise ValueError("Live-only model and policy must match exactly")
    if policy_version in COMPARISON_POLICIES:
        if (side not in catalog_sides().get(market, ())
                or not market_open(market, side, home_goals, away_goals)):
            raise ValueError("Unknown or closed live comparison outcome")
    elif policy_version != POLICY_VERSION or not legacy:
        raise ValueError("Unknown live selection policy or outcome")

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript(_SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute(
            "SELECT 1 FROM live_tips WHERE fixture_id=? AND "
            "(home_id!=? OR away_id!=? OR status!='open') LIMIT 1",
            (fixture_id, home_id, away_id),
        ).fetchone():
            raise ValueError("Fixture identity changed or fixture already finished")
        cursor = conn.execute(
            """INSERT INTO live_tips
            (fixture_id,market,side,minute,phase,extra,home_goals,away_goals,home_id,away_id,
             probability,snapshot_at,shown_at,model_version,policy_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fixture_id,market,side) DO NOTHING""",
            (fixture_id, market, side, minute, phase, extra, home_goals, away_goals, home_id, away_id,
             probability, snapshot.isoformat(), shown.isoformat(), model_version.strip(), policy_version),
        )
        return cursor.rowcount == 1


def live_tip_stats(db_path=DB_PATH) -> dict[str, dict[str, int]]:
    """Read only; an absent ledger has no tips. An unreadable ledger is not an empty one."""
    counts = {market: dict(won=0, lost=0, open=0, void=0) for market in SIDES}
    path = Path(db_path)
    if path.exists():
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            for market, status, count in conn.execute(
                "SELECT market,status,COUNT(*) FROM live_tips GROUP BY market,status"
            ):
                if market not in counts:
                    from live_market_comparison import catalog_sides
                    if market not in catalog_sides():
                        raise sqlite3.DatabaseError("Unknown public live market or result status")
                    counts[market] = dict(won=0, lost=0, open=0, void=0)
                if status not in counts[market]:
                    raise sqlite3.DatabaseError("Unknown public live market or result status")
                counts[market][status] = count
    return counts


def _response(api, endpoint, params, delay):
    try:
        payload = api._request(endpoint, params)
    except Exception:
        # The API adapter may raise a transport error instead of returning its error payload.
        return None
    finally:
        if delay > 0:
            time.sleep(delay)
    return evidence.response_rows(payload, api)


def _nested(item, *keys):
    for key in keys:
        item = item.get(key) if isinstance(item, dict) else None
    return item


def _resolve(row, status, final, timeline):
    """(verdict, next scorer, effective minute); None means insufficient evidence."""
    if status in VOID:
        return "void", None, None
    baseline = row["home_goals"], row["away_goals"]
    market, side = row["market"], row["side"]
    if final is None:
        return None
    # A corrected score can be lower than the display after VAR. For new
    # absolute outcomes the independently verified regulation result decides;
    # relative outcomes and historical receipts still require their baseline.
    if (any(f < b for f, b in zip(final, baseline))
            and (market in TIMELINE_MARKETS or row["policy_version"] not in COMPARISON_POLICIES)):
        return None
    scorer, goal_minute = None, None
    if market not in TIMELINE_MARKETS:
        from live_market_comparison import final_verdict
        won = final_verdict(market, side, *final)
        if type(won) is not bool:
            return None
    else:
        # A disallowed goal followed by a valid goal can leave the *same* final score.
        # Reconcile the entire goal timeline with this particular observation first.
        if timeline is None:
            return None
        remaining = evidence.remaining_goal_timeline(
            timeline, snapshot_order=evidence.period_clock(row["phase"], row["minute"], row["extra"]),
            baseline=baseline
        )
        if remaining is None:
            return None
        if market == "next_goal":
            won = bool(remaining)
        elif market == "team_scores":
            won = any(s == side for _, s in remaining)
        elif market in {"red_next", "next_scorer"}:
            result = evidence.first_scorer(remaining)
            if result is None:
                return None
            scorer, goal_minute = result
            won = side == ("none" if scorer == "no_goal" else scorer)
        else:
            return None
    return ("won" if won else "lost"), scorer, goal_minute


def settle_displayed_live_tips(api, *, max_fixtures=25, db_path=DB_PATH, now=None,
                              sleep_seconds=0.15) -> dict[str, int]:
    """Bound by distinct fixtures, not rows. Check the least-attempted fixtures first."""
    stats = dict(fixtures_checked=0, settled=0, void=0, still_running=0, unverified=0, provider_errors=0)
    path = Path(db_path)
    if not path.exists() or max_fixtures <= 0:
        return stats
    check_at = _now(now).isoformat()
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        queue = conn.execute(
            """SELECT fixture_id FROM live_tips WHERE status='open' AND shown_at<=?
               GROUP BY fixture_id ORDER BY MIN(checks),MIN(shown_at),fixture_id LIMIT ?""",
            (check_at, max_fixtures),
        ).fetchall()
        for (fixture_id,) in queue:
            rows = conn.execute("SELECT * FROM live_tips WHERE fixture_id=? AND status='open' AND shown_at<=?",
                                (fixture_id, check_at)).fetchall()
            if not rows:
                continue
            # Persist the attempt even on errors; no database write lock over any HTTP call.
            with conn:
                conn.executemany("UPDATE live_tips SET checks=checks+1 WHERE id=? AND status='open'",
                                 [(r["id"],) for r in rows])
            stats["fixtures_checked"] += 1
            payload = _response(api, "fixtures", {"id": fixture_id}, sleep_seconds)
            if payload is None:
                stats["provider_errors"] += 1
                continue
            fixture = payload[0] if len(payload) == 1 else None
            status = _nested(fixture, "fixture", "status", "short")
            native_id = _nested(fixture, "fixture", "id")
            home, away = (_nested(fixture, "teams", side, "id") for side in ("home", "away"))
            if (not _id(native_id) or native_id != fixture_id or not isinstance(status, str)
                    or not _id(home) or not _id(away) or home == away
                    or (home, away) != (rows[0]["home_id"], rows[0]["away_id"])):
                stats["unverified"] += len(rows)
                continue
            if status not in evidence.FINISHED_STATUSES and status not in VOID:
                stats["still_running"] += 1
                continue
            final = evidence.regulation_result(fixture)
            timeline = None
            if final is not None and any(r["market"] in TIMELINE_MARKETS for r in rows):
                events = _response(api, "fixtures/events", {"fixture": fixture_id}, sleep_seconds)
                if events is None:
                    stats["provider_errors"] += 1
                else:
                    timeline = evidence.verified_goal_timeline(fixture, events)
            with conn:
                for row in rows:
                    result = _resolve(row, status, final, timeline)
                    if result is None:
                        stats["unverified"] += 1
                        continue
                    verdict, scorer, goal_minute = result
                    cursor = conn.execute(
                        """UPDATE live_tips SET status=?,result_status=?,result_home=?,result_away=?,
                           result_next=?,result_minute=?,settled_at=? WHERE id=? AND status='open'""",
                        (verdict, status, *(final or (None, None)), scorer, goal_minute, check_at, row["id"]),
                    )
                    stats["void" if verdict == "void" else "settled"] += cursor.rowcount
    return stats
