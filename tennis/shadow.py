"""Tennis shadow store — the same discipline as the football shadow bets.

Every daily prediction lands here BEFORE the match, with model
probabilities, gate results and (once entered) N1Bet prices.  After
the match we settle: result, RET flag, and CLV once the closing price
is known. Model outputs stay frozen; factual schedule metadata and
timestamped prices are appended to preserve the audit trail.

Settlement of retirements follows a configurable rule
(``RETIREMENT_RULE``): bookmakers differ ('ball served', '1 set',
'match completed').  We store the RET flag and settle under the
configured rule; the N1Bet T&Cs must be confirmed before real money.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent / "data" / "tennis_shadow.db"

# ASSUMPTION — verify against N1Bet T&Cs before real-money bets.
# Options: 'ball_served' | 'one_set' | 'match_completed'
RETIREMENT_RULE = "one_set"
CLOSING_WINDOW_SECONDS = 60 * 60
TENNIS_MODEL_VERSION = "elo-serve-platt-v2"
TENNIS_POLICY_VERSION = "risk-ev-haircut-v3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc REAL NOT NULL,
    match_date TEXT NOT NULL,
    provider_event_id TEXT,
    scheduled_start_utc TEXT,
    fixture_source TEXT,
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
    price_checked_utc REAL,
    settled INTEGER DEFAULT 0,
    actual_winner TEXT,
    ret_flag INTEGER DEFAULT 0,
    ret_set INTEGER,
    closing_odds_a REAL,
    closing_odds_b REAL,
    closing_checked_utc REAL,
    pnl REAL,
    model_version TEXT,
    policy_version TEXT
);
CREATE TABLE IF NOT EXISTS side_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc REAL NOT NULL,
    prediction_id INTEGER NOT NULL,
    market TEXT NOT NULL,          -- over_2_5_sets | under_2_5_sets | set_a_2_0 | set_b_2_0
    model_p REAL NOT NULL,
    odds REAL NOT NULL,
    edge REAL NOT NULL,
    closing_odds REAL,
    closing_checked_utc REAL,
    settled INTEGER DEFAULT 0,
    result TEXT,                   -- '2:0' | '2:1' | '1:2' | '0:2' | 'ret'
    won INTEGER,
    pnl REAL,
    policy_version TEXT
);
"""

_PREDICTION_MIGRATIONS = {
    "provider_event_id": "TEXT",
    "scheduled_start_utc": "TEXT",
    "fixture_source": "TEXT",
    "price_checked_utc": "REAL",
    "closing_checked_utc": "REAL",
    "model_version": "TEXT",
    "policy_version": "TEXT",
}
_SIDE_BET_MIGRATIONS = {
    "closing_odds": "REAL",
    "closing_checked_utc": "REAL",
    "policy_version": "TEXT",
}

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
            "INSERT INTO side_bets (created_utc, prediction_id, market, model_p, "
            "odds, edge, policy_version) VALUES (?,?,?,?,?,?,?)",
            (
                time.time(),
                prediction_id,
                market,
                model_p,
                odds,
                edge,
                TENNIS_POLICY_VERSION,
            ),
        )
        return int(cur.lastrowid)


def side_bets_for(prediction_ids: List[int]) -> List[Dict]:
    if not prediction_ids:
        return []
    marks = ",".join("?" * len(prediction_ids))
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM side_bets WHERE prediction_id IN ({marks}) "
            "AND policy_version=? ORDER BY id",
            [*prediction_ids, TENNIS_POLICY_VERSION],
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


def settle_side_bet(
    bet_id: int,
    result: str,
    closing_odds: Optional[float] = None,
) -> None:
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
        if closing_odds is not None and (
            not math.isfinite(closing_odds) or closing_odds <= 1.0
        ):
            raise ValueError("closing odds must be greater than 1.0")
        if result == "ret":
            won, pnl = None, 0.0
        else:
            won = 1 if result in SIDE_MARKETS[market]["wins_on"] else 0
            pnl = (odds - 1.0) if won else -1.0
        conn.execute(
            "UPDATE side_bets SET settled=1, result=?, won=?, pnl=?, "
            "closing_odds=COALESCE(?, closing_odds) WHERE id=?",
            (result, won, pnl, closing_odds, bet_id),
        )


def _scheduled_start_epoch(value: Optional[str]) -> float:
    if not value:
        raise ValueError("scheduled start is missing")
    try:
        start = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("scheduled start is invalid") from exc
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return start.astimezone(timezone.utc).timestamp()


def _validate_closing_capture(
    scheduled_start_utc: Optional[str],
    captured_utc: float,
) -> None:
    if not math.isfinite(captured_utc):
        raise ValueError("closing capture time must be finite")
    lead = _scheduled_start_epoch(scheduled_start_utc) - captured_utc
    if lead < 0:
        raise ValueError("closing price cannot be captured after scheduled start")
    if lead > CLOSING_WINDOW_SECONDS:
        raise ValueError("closing price may only be captured in the final 60 minutes")


def record_closing_prices(
    prediction_id: int,
    closing_a: float,
    closing_b: float,
    *,
    captured_utc: Optional[float] = None,
) -> None:
    """Freeze both N1Bet reference prices shortly before scheduled start."""
    if (
        not math.isfinite(closing_a)
        or not math.isfinite(closing_b)
        or closing_a <= 1.0
        or closing_b <= 1.0
    ):
        raise ValueError("closing odds must be greater than 1.0")
    captured = time.time() if captured_utc is None else float(captured_utc)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT scheduled_start_utc, settled, recommended_side
            FROM predictions WHERE id=?
            """,
            (prediction_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"prediction {prediction_id} not found")
        scheduled, settled, side = row
        if settled:
            raise ValueError("settled prediction cannot receive a closing price")
        if side not in ("A", "B"):
            raise ValueError("closing price requires a released shadow bet")
        _validate_closing_capture(scheduled, captured)
        conn.execute(
            """
            UPDATE predictions
            SET closing_odds_a=?, closing_odds_b=?, closing_checked_utc=?
            WHERE id=?
            """,
            (closing_a, closing_b, captured, prediction_id),
        )


def record_side_closing_price(
    bet_id: int,
    closing_odds: float,
    *,
    captured_utc: Optional[float] = None,
) -> None:
    """Freeze one side-market reference price shortly before start."""
    if not math.isfinite(closing_odds) or closing_odds <= 1.0:
        raise ValueError("closing odds must be greater than 1.0")
    captured = time.time() if captured_utc is None else float(captured_utc)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT p.scheduled_start_utc, s.settled
            FROM side_bets s
            JOIN predictions p ON p.id=s.prediction_id
            WHERE s.id=?
            """,
            (bet_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"side bet {bet_id} not found")
        scheduled, settled = row
        if settled:
            raise ValueError("settled side bet cannot receive a closing price")
        _validate_closing_capture(scheduled, captured)
        conn.execute(
            "UPDATE side_bets SET closing_odds=?, closing_checked_utc=? WHERE id=?",
            (closing_odds, captured, bet_id),
        )


def side_bet_summary() -> Dict:
    with _connect() as conn:
        total, settled = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(settled),0) FROM side_bets "
            "WHERE policy_version=?",
            (TENNIS_POLICY_VERSION,),
        ).fetchone()
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(pnl),0), AVG(pnl) FROM side_bets "
            "WHERE settled=1 AND won IS NOT NULL AND policy_version=?",
            (TENNIS_POLICY_VERSION,),
        ).fetchone()
        clv = conn.execute(
            "SELECT COUNT(*), AVG(odds / closing_odds - 1.0) FROM side_bets "
            "WHERE settled=1 AND odds>1.0 AND closing_odds>1.0 "
            "AND closing_checked_utc IS NOT NULL AND policy_version=?",
            (TENNIS_POLICY_VERSION,),
        ).fetchone()
    return {
        "side_bets": total,
        "open": total - settled,
        "settled": row[0],
        "units": round(row[1] or 0.0, 2),
        "roi": round(row[2] or 0.0, 4) if row[0] else None,
        "clv_samples": clv[0],
        "clv": round(clv[1], 4) if clv[0] else None,
    }


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(predictions)").fetchall()
    }
    for name, sql_type in _PREDICTION_MIGRATIONS.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE predictions ADD COLUMN {name} {sql_type}")
    side_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(side_bets)").fetchall()
    }
    for name, sql_type in _SIDE_BET_MIGRATIONS.items():
        if name not in side_columns:
            conn.execute(f"ALTER TABLE side_bets ADD COLUMN {name} {sql_type}")
    return conn


def ensure_schema() -> None:
    """Create or migrate the shadow schema before direct read/write access."""
    with _connect():
        pass


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
    *,
    provider_event_id: Optional[str] = None,
    scheduled_start_utc: Optional[str] = None,
    fixture_source: Optional[str] = None,
) -> int:
    """Persist a TennisPrediction.  Returns the row id (or -1 if duplicate)."""
    gates = {g.name: {"passed": g.passed, "detail": g.detail} for g in prediction.gates}
    with _connect() as conn:
        existing = None
        if provider_event_id:
            existing = conn.execute(
                """
                SELECT id FROM predictions
                WHERE provider_event_id=?
                  AND (fixture_source=? OR fixture_source IS NULL)
                """,
                (provider_event_id, fixture_source),
            ).fetchone()
        if existing is None:
            existing = conn.execute(
                "SELECT id FROM predictions "
                "WHERE match_date=? AND player_a=? AND player_b=?",
                (match_date, prediction.player_a, prediction.player_b),
            ).fetchone()
        if existing:
            # Schedules can move after the first scan. Model outputs stay frozen,
            # while factual fixture metadata may be refreshed.
            conn.execute(
                """
                UPDATE predictions
                SET match_date=?,
                    provider_event_id=COALESCE(?, provider_event_id),
                    scheduled_start_utc=COALESCE(?, scheduled_start_utc),
                    fixture_source=COALESCE(?, fixture_source)
                WHERE id=?
                """,
                (
                    match_date,
                    provider_event_id,
                    scheduled_start_utc,
                    fixture_source,
                    existing[0],
                ),
            )
            return -1
        cur = conn.execute(
            """
            INSERT INTO predictions (
                created_utc, match_date, provider_event_id, scheduled_start_utc,
                fixture_source, tour, tournament, surface, best_of,
                player_a, player_b, p_raw, p_cal, markets_json, gates_json,
                verdict, recommended_side, recommended_edge, odds_a, odds_b,
                model_version, policy_version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                time.time(),
                match_date,
                provider_event_id,
                scheduled_start_utc,
                fixture_source,
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
                TENNIS_MODEL_VERSION,
                TENNIS_POLICY_VERSION,
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
        if actual_winner not in (player_a, player_b):
            raise ValueError("actual_winner must match one of the stored players")
        for price in (closing_a, closing_b):
            if price is not None and (
                not math.isfinite(price) or price <= 1.0
            ):
                raise ValueError("closing odds must be greater than 1.0")

        pnl: Optional[float] = None
        if side:
            odds = odds_a if side == "A" else odds_b
            won = (side == "A" and actual_winner == player_a) or (
                side == "B" and actual_winner == player_b
            )
            if odds is None or odds <= 1.0:
                pnl = None
            elif ret and RETIREMENT_RULE == "match_completed":
                pnl = 0.0  # void
            elif ret and RETIREMENT_RULE == "one_set" and (ret_set or 0) < 1:
                pnl = 0.0  # void before set 1 completed
            else:
                pnl = (odds - 1.0) if won else -1.0

        conn.execute(
            """
            UPDATE predictions
            SET settled=1, actual_winner=?, ret_flag=?, ret_set=?,
                closing_odds_a=COALESCE(?, closing_odds_a),
                closing_odds_b=COALESCE(?, closing_odds_b), pnl=?
            WHERE id=?
            """,
            (actual_winner, 1 if ret else 0, ret_set, closing_a, closing_b, pnl, prediction_id),
        )


def summary() -> Dict:
    with _connect() as conn:
        total, settled = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(settled),0) FROM predictions"
        ).fetchone()
        recommended_total = conn.execute(
            "SELECT COUNT(*) FROM predictions "
            "WHERE recommended_side IN ('A', 'B') AND policy_version=?",
            (TENNIS_POLICY_VERSION,),
        ).fetchone()[0]
        reco = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(pnl),0), AVG(pnl) FROM predictions "
            "WHERE settled=1 AND recommended_side IS NOT NULL AND pnl IS NOT NULL "
            "AND policy_version=?",
            (TENNIS_POLICY_VERSION,),
        ).fetchone()
        clv = conn.execute(
            """
            SELECT COUNT(*), AVG(
                CASE recommended_side
                    WHEN 'A' THEN odds_a / closing_odds_a - 1.0
                    WHEN 'B' THEN odds_b / closing_odds_b - 1.0
                END
            )
            FROM predictions
            WHERE settled=1
              AND recommended_side IN ('A', 'B')
              AND policy_version=?
              AND closing_checked_utc IS NOT NULL
              AND (
                  (recommended_side='A' AND odds_a>1.0 AND closing_odds_a>1.0)
                  OR
                  (recommended_side='B' AND odds_b>1.0 AND closing_odds_b>1.0)
              )
            """,
            (TENNIS_POLICY_VERSION,),
        ).fetchone()
        brier = conn.execute(
            """
            SELECT COUNT(*), AVG(
                (p_cal - CASE WHEN actual_winner=player_a THEN 1.0 ELSE 0.0 END)
                * (p_cal - CASE WHEN actual_winner=player_a THEN 1.0 ELSE 0.0 END)
            )
            FROM predictions
            WHERE settled=1 AND actual_winner IN (player_a, player_b)
            """
        ).fetchone()
        benchmark = conn.execute(
            """
            SELECT COUNT(*),
                   AVG(
                       (p_cal - CASE WHEN actual_winner=player_a THEN 1.0 ELSE 0.0 END)
                       * (p_cal - CASE WHEN actual_winner=player_a THEN 1.0 ELSE 0.0 END)
                   ),
                   AVG(
                       (
                           closing_odds_b / (closing_odds_a + closing_odds_b)
                           - CASE WHEN actual_winner=player_a THEN 1.0 ELSE 0.0 END
                       )
                       * (
                           closing_odds_b / (closing_odds_a + closing_odds_b)
                           - CASE WHEN actual_winner=player_a THEN 1.0 ELSE 0.0 END
                       )
                   )
            FROM predictions
            WHERE settled=1
              AND actual_winner IN (player_a, player_b)
              AND closing_odds_a>1.0
              AND closing_odds_b>1.0
              AND closing_checked_utc IS NOT NULL
            """
        ).fetchone()
    return {
        "predictions": total,
        "settled": settled,
        "open": total - settled,
        "recommended_bets": recommended_total,
        "units": round(reco[1] or 0.0, 2),
        "roi": round(reco[2] or 0.0, 4) if reco[0] else None,
        "clv_samples": clv[0],
        "clv": round(clv[1], 4) if clv[0] else None,
        "brier_samples": brier[0],
        "brier": round(brier[1], 4) if brier[0] else None,
        "benchmark_samples": benchmark[0],
        "benchmark_model_brier": (
            round(benchmark[1], 4) if benchmark[0] else None
        ),
        "benchmark_market_brier": (
            round(benchmark[2], 4) if benchmark[0] else None
        ),
        "policy_version": TENNIS_POLICY_VERSION,
    }
