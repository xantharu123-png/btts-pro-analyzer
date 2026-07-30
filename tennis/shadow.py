"""Tennis shadow store — the same discipline as the football shadow bets.

Every daily prediction lands here BEFORE the match, with model
probabilities, gate results and (once entered) N1Bet prices.  After
the match we settle: result, RET flag, and CLV once the closing price
is known.  No prediction is ever edited after creation — the audit
trail is the whole point.

Settlement of retirements follows a configurable rule
(``RETIREMENT_RULE``): bookmakers differ ('ball served', '1 set',
'match completed').  We store the RET flag and settle under the
configured rule; the N1Bet T&Cs must be confirmed before real money.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent / "data" / "tennis_shadow.db"

# ASSUMPTION — verify against N1Bet T&Cs before real-money bets.
# Options: 'ball_served' | 'one_set' | 'match_completed'
RETIREMENT_RULE = "one_set"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc REAL NOT NULL,
    match_date TEXT NOT NULL,
    tour TEXT NOT NULL,
    tournament TEXT,
    surface TEXT,
    best_of INTEGER,
    player_a TEXT NOT NULL,
    player_b TEXT NOT NULL,
    p_raw REAL,
    p_cal REAL,
    markets_json TEXT,
    gates_json TEXT,
    verdict TEXT,
    recommended_side TEXT,
    recommended_edge REAL,
    odds_a REAL,
    odds_b REAL,
    settled INTEGER DEFAULT 0,
    actual_winner TEXT,
    ret_flag INTEGER DEFAULT 0,
    ret_set INTEGER,
    closing_odds_a REAL,
    closing_odds_b REAL,
    pnl REAL
);
CREATE TABLE IF NOT EXISTS side_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc REAL NOT NULL,
    prediction_id INTEGER NOT NULL,
    market TEXT NOT NULL,          -- over_2_5_sets | under_2_5_sets | set_a_2_0 | set_b_2_0
    model_p REAL NOT NULL,
    odds REAL NOT NULL,
    edge REAL NOT NULL,
    settled INTEGER DEFAULT 0,
    result TEXT,                   -- '2:0' | '2:1' | '1:2' | '0:2' | 'ret'
    won INTEGER,
    pnl REAL
);
"""

# set markets offered in the UI; distributions calibration-tested on
# 9.6k ATP matches (RMS 3.7-4.7% in the betting region).  Game totals
# and game handicaps are NOT offered: the calibration test shows a
# systematic 5-10pp bias that bookmaker lines exploit.
SIDE_MARKETS = {
    "over_2_5_sets": {
        "label": "Über 2,5 Sätze",
        "wins_on": ("2:1", "1:2"),
    },
    "under_2_5_sets": {
        "label": "Unter 2,5 Sätze",
        "wins_on": ("2:0", "0:2"),
    },
    "set_a_2_0": {
        "label": "Satz-Handicap A −1,5 (2:0)",
        "wins_on": ("2:0",),
    },
    "set_b_2_0": {
        "label": "Satz-Handicap B −1,5 (0:2)",
        "wins_on": ("0:2",),
    },
}


def store_side_bet(prediction_id: int, market: str, model_p: float,
                   odds: float, edge: float) -> int:
    """Track one side-market bet (price checked in the UI)."""
    if market not in SIDE_MARKETS:
        raise ValueError(f"unknown side market {market!r}")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO side_bets (created_utc, prediction_id, market, model_p, odds, edge)"
            " VALUES (?,?,?,?,?,?)",
            (time.time(), prediction_id, market, model_p, odds, edge),
        )
        return int(cur.lastrowid)


def side_bets_for(prediction_ids: List[int]) -> List[Dict]:
    if not prediction_ids:
        return []
    marks = ",".join("?" * len(prediction_ids))
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM side_bets WHERE prediction_id IN ({marks}) ORDER BY id",
            prediction_ids,
        ).fetchall()
    return [dict(r) for r in rows]


def open_side_bets() -> List[Dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT s.*, p.player_a, p.player_b, p.match_date, p.tournament, p.tour
            FROM side_bets s JOIN predictions p ON p.id = s.prediction_id
            WHERE s.settled = 0
            ORDER BY p.match_date
            """
        ).fetchall()
    return [dict(r) for r in rows]


def settle_side_bet(bet_id: int, result: str) -> None:
    """Settle from the set score ('2:0'/'2:1'/'1:2'/'0:2') or 'ret'.

    Conservative rule: ANY retirement voids set markets (bookmaker rules
    differ; void can never cost us a fake win or a fake loss).
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT market, odds FROM side_bets WHERE id=?", (bet_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"side bet {bet_id} not found")
        market, odds = row
        if result == "ret":
            won, pnl = None, 0.0
        else:
            won = 1 if result in SIDE_MARKETS[market]["wins_on"] else 0
            pnl = (odds - 1.0) if won else -1.0
        conn.execute(
            "UPDATE side_bets SET settled=1, result=?, won=?, pnl=? WHERE id=?",
            (result, won, pnl, bet_id),
        )


def side_bet_summary() -> Dict:
    with _connect() as conn:
        total, settled = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(settled),0) FROM side_bets"
        ).fetchone()
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(pnl),0), AVG(pnl) FROM side_bets "
            "WHERE settled=1 AND won IS NOT NULL"
        ).fetchone()
    return {
        "side_bets": total,
        "open": total - settled,
        "settled": row[0],
        "units": round(row[1] or 0.0, 2),
        "roi": round(row[2] or 0.0, 4) if row[0] else None,
    }


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def already_stored(match_date: str, player_a: str, player_b: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM predictions WHERE match_date=? AND player_a=? AND player_b=?",
            (match_date, player_a, player_b),
        ).fetchone()
    return row is not None


def store_prediction(
    match_date: str,
    tour: str,
    tournament: Optional[str],
    prediction,
    odds_a: Optional[float] = None,
    odds_b: Optional[float] = None,
) -> int:
    """Persist a TennisPrediction.  Returns the row id (or -1 if duplicate)."""
    if already_stored(match_date, prediction.player_a, prediction.player_b):
        return -1
    gates = {g.name: {"passed": g.passed, "detail": g.detail} for g in prediction.gates}
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO predictions (
                created_utc, match_date, tour, tournament, surface, best_of,
                player_a, player_b, p_raw, p_cal, markets_json, gates_json,
                verdict, recommended_side, recommended_edge, odds_a, odds_b
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                time.time(),
                match_date,
                tour,
                tournament,
                prediction.surface,
                prediction.best_of,
                prediction.player_a,
                prediction.player_b,
                prediction.p_a_raw,
                prediction.p_a_cal,
                json.dumps(prediction.market_summary()),
                json.dumps(gates, ensure_ascii=False),
                prediction.verdict,
                prediction.recommended_side,
                prediction.recommended_edge,
                odds_a,
                odds_b,
            ),
        )
        return int(cur.lastrowid)


def pending_predictions() -> List[Dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM predictions WHERE settled=0 ORDER BY match_date"
        ).fetchall()
    return [dict(r) for r in rows]


def settle(prediction_id: int, actual_winner: str, ret: bool = False,
           ret_set: Optional[int] = None,
           closing_a: Optional[float] = None, closing_b: Optional[float] = None) -> None:
    """Settle one prediction.  ``actual_winner`` must equal player_a or player_b."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT player_a, player_b, recommended_side, odds_a, odds_b FROM predictions WHERE id=?",
            (prediction_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"prediction {prediction_id} not found")
        player_a, player_b, side, odds_a, odds_b = row

        pnl: Optional[float] = None
        if side:
            odds = odds_a if side == "A" else odds_b
            won = (side == "A" and actual_winner == player_a) or (
                side == "B" and actual_winner == player_b
            )
            if ret and RETIREMENT_RULE == "match_completed":
                pnl = 0.0  # void
            elif ret and RETIREMENT_RULE == "one_set" and (ret_set or 0) < 1:
                pnl = 0.0  # void before set 1 completed
            else:
                pnl = (odds - 1.0) if won else -1.0

        conn.execute(
            """
            UPDATE predictions
            SET settled=1, actual_winner=?, ret_flag=?, ret_set=?,
                closing_odds_a=?, closing_odds_b=?, pnl=?
            WHERE id=?
            """,
            (actual_winner, 1 if ret else 0, ret_set, closing_a, closing_b, pnl, prediction_id),
        )


def summary() -> Dict:
    with _connect() as conn:
        total, settled = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(settled),0) FROM predictions"
        ).fetchone()
        reco = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(pnl),0), AVG(pnl) FROM predictions "
            "WHERE settled=1 AND recommended_side IS NOT NULL AND pnl IS NOT NULL"
        ).fetchone()
    return {
        "predictions": total,
        "settled": settled,
        "open": total - settled,
        "recommended_bets": reco[0],
        "units": round(reco[1] or 0.0, 2),
        "roi": round(reco[2] or 0.0, 4) if reco[0] else None,
    }
