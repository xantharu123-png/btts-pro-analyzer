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
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .prediction_revisions import (
    REVISION_SCHEMA, append_revision, freeze_legacy_baseline, read_latest_predictions, utc_epoch,
)

from price_ledger import (
    PriceLedger,
    PriceLedgerError,
    PriceLedgerIntegrityError,
    PriceQuote,
)

DB_PATH = Path(__file__).resolve().parent / "data" / "tennis_shadow.db"

# ASSUMPTION — verify against N1Bet T&Cs before real-money bets.
# Options: 'ball_served' | 'one_set' | 'match_completed'
RETIREMENT_RULE = "one_set"
CLOSING_WINDOW_SECONDS = 60 * 60
TENNIS_MODEL_VERSION = "elo-serve-platt-v3"
TENNIS_POLICY_VERSION = "risk-ev-haircut-min-odds-v4"

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
    entry_quote_id_a INTEGER,
    entry_quote_id_b INTEGER,
    settled INTEGER DEFAULT 0,
    actual_winner TEXT,
    ret_flag INTEGER DEFAULT 0,
    ret_set INTEGER,
    termination TEXT,
    result_observed_at TEXT,
    player_a_sets INTEGER,
    player_b_sets INTEGER,
    closing_odds_a REAL,
    closing_odds_b REAL,
    closing_checked_utc REAL,
    closing_quote_id_a INTEGER,
    closing_quote_id_b INTEGER,
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
    entry_quote_id INTEGER,
    closing_odds REAL,
    closing_checked_utc REAL,
    closing_quote_id INTEGER,
    settled INTEGER DEFAULT 0,
    result TEXT,                   -- '2:0' | '2:1' | '1:2' | '0:2' | 'ret'
    won INTEGER,
    pnl REAL,
    policy_version TEXT
);
"""

_CLOSING_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS tennis_closing_prices_frozen
BEFORE UPDATE OF closing_odds_a, closing_odds_b, closing_checked_utc,
                 closing_quote_id_a, closing_quote_id_b
ON predictions
WHEN OLD.closing_quote_id_a IS NOT NULL OR OLD.closing_quote_id_b IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'tennis closing prices are frozen');
END;
CREATE TRIGGER IF NOT EXISTS tennis_side_closing_price_frozen
BEFORE UPDATE OF closing_odds, closing_checked_utc, closing_quote_id
ON side_bets
WHEN OLD.closing_quote_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'tennis side closing price is frozen');
END;
"""

_PREDICTION_MIGRATIONS = {
    "provider_event_id": "TEXT",
    "scheduled_start_utc": "TEXT",
    "fixture_source": "TEXT",
    "price_checked_utc": "REAL",
    "entry_quote_id_a": "INTEGER",
    "entry_quote_id_b": "INTEGER",
    "closing_checked_utc": "REAL",
    "closing_quote_id_a": "INTEGER",
    "closing_quote_id_b": "INTEGER",
    "termination": "TEXT",
    "result_observed_at": "TEXT",
    "player_a_sets": "INTEGER",
    "player_b_sets": "INTEGER",
    "model_version": "TEXT",
    "policy_version": "TEXT",
    "match_duration_minutes": "INTEGER",
}
_SIDE_BET_MIGRATIONS = {
    "closing_odds": "REAL",
    "closing_checked_utc": "REAL",
    "entry_quote_id": "INTEGER",
    "closing_quote_id": "INTEGER",
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


def _capture_datetime(value: Optional[float]) -> datetime:
    captured = time.time() if value is None else float(value)
    if not math.isfinite(captured):
        raise ValueError("price capture time must be finite")
    return datetime.fromtimestamp(captured, timezone.utc)


def _prediction_price_context(
    prediction_id: int,
) -> dict[str, str]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT provider_event_id, scheduled_start_utc, fixture_source,
                   tour, tournament, player_a, player_b, settled
            FROM predictions WHERE id=?
            """,
            (prediction_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"prediction {prediction_id} not found")
    if row["settled"]:
        raise ValueError("settled prediction cannot receive a price")
    if not row["scheduled_start_utc"]:
        raise ValueError("verified scheduled start is required for price evidence")
    return {
        "event_id": str(
            row["provider_event_id"] or f"tennis-prediction-{prediction_id}"
        ),
        "event_name": f"{row['player_a']} vs {row['player_b']}",
        "scheduled_start": str(row["scheduled_start_utc"]),
        "tour": str(row["tour"] or ""),
        "tournament": str(row["tournament"] or ""),
        "fixture_source": str(row["fixture_source"] or ""),
        "player_a": str(row["player_a"]),
        "player_b": str(row["player_b"]),
    }


def _append_price_quotes(
    quotes: list[PriceQuote],
    *,
    recorded_at: datetime,
) -> list[int]:
    try:
        observations = PriceLedger(DB_PATH).append_many(
            quotes,
            now=recorded_at,
        )
    except (PriceLedgerError, PriceLedgerIntegrityError) as exc:
        raise ValueError(str(exc)) from exc
    return [observation.id for observation in observations]


def record_entry_prices(
    prediction_id: int,
    odds_a: float,
    odds_b: float,
    *,
    captured_utc: Optional[float] = None,
) -> tuple[int, int]:
    """Append both N1Bet match-winner prices before updating the current pointer."""
    if (
        not math.isfinite(odds_a)
        or not math.isfinite(odds_b)
        or odds_a <= 1.0
        or odds_b <= 1.0
    ):
        raise ValueError("entry odds must be greater than 1.0")
    captured = _capture_datetime(captured_utc)
    context = _prediction_price_context(prediction_id)
    start = _scheduled_start_epoch(context["scheduled_start"])
    if captured.timestamp() > start:
        raise ValueError("entry price cannot be captured after scheduled start")
    common = {
        "sport": "TENNIS",
        "event_id": context["event_id"],
        "event_name": context["event_name"],
        "scheduled_start": context["scheduled_start"],
        "market_key": "MATCH_WINNER",
        "market_name": "Match winner",
        "phase": "ENTRY",
        "source": "MANUAL",
        "captured_at": captured,
        "model_ref": TENNIS_POLICY_VERSION,
        "metadata": {
            "prediction_id": prediction_id,
            "tour": context["tour"],
            "tournament": context["tournament"],
            "fixture_source": context["fixture_source"],
        },
    }
    observation_ids = _append_price_quotes(
        [
            PriceQuote(
                **common,
                selection_key="A",
                selection_name=context["player_a"],
                decimal_odds=odds_a,
            ),
            PriceQuote(
                **common,
                selection_key="B",
                selection_name=context["player_b"],
                decimal_odds=odds_b,
            ),
        ],
        recorded_at=datetime.now(timezone.utc),
    )
    with _connect() as conn:
        conn.execute(
            """
            UPDATE predictions
            SET odds_a=?, odds_b=?, price_checked_utc=?,
                entry_quote_id_a=?, entry_quote_id_b=?
            WHERE id=?
            """,
            (
                odds_a,
                odds_b,
                captured.timestamp(),
                observation_ids[0],
                observation_ids[1],
                prediction_id,
            ),
        )
    return observation_ids[0], observation_ids[1]


def store_side_bet(prediction_id: int, market: str, model_p: float,
                   odds: float, edge: float) -> int:
    """Track one side-market bet (price checked in the UI)."""
    if market not in SIDE_MARKETS:
        raise ValueError(f"unknown side market {market!r}")
    if not math.isfinite(odds) or odds <= 1.0:
        raise ValueError("entry odds must be greater than 1.0")
    captured = datetime.now(timezone.utc)
    context = _prediction_price_context(prediction_id)
    observation_id = _append_price_quotes(
        [
            PriceQuote(
                sport="TENNIS",
                event_id=context["event_id"],
                event_name=context["event_name"],
                scheduled_start=context["scheduled_start"],
                market_key=market,
                market_name=SIDE_MARKETS[market]["label"],
                selection_key=market,
                selection_name=SIDE_MARKETS[market]["label"],
                decimal_odds=odds,
                phase="ENTRY",
                source="MANUAL",
                captured_at=captured,
                model_ref=TENNIS_POLICY_VERSION,
                metadata={
                    "prediction_id": prediction_id,
                    "tour": context["tour"],
                    "tournament": context["tournament"],
                },
            )
        ],
        recorded_at=captured,
    )[0]
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO side_bets (created_utc, prediction_id, market, model_p, "
            "odds, edge, entry_quote_id, policy_version) VALUES (?,?,?,?,?,?,?,?)",
            (
                captured.timestamp(),
                prediction_id,
                market,
                model_p,
                odds,
                edge,
                observation_id,
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
        if closing_odds is not None:
            raise ValueError(
                "record closing odds before settlement with "
                "record_side_closing_price"
            )
        if result == "ret":
            won, pnl = None, 0.0
        else:
            won = 1 if result in SIDE_MARKETS[market]["wins_on"] else 0
            pnl = (odds - 1.0) if won else -1.0
        conn.execute(
            "UPDATE side_bets SET settled=1, result=?, won=?, pnl=? WHERE id=?",
            (result, won, pnl, bet_id),
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
    captured_dt = _capture_datetime(captured_utc)
    captured = captured_dt.timestamp()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT scheduled_start_utc, settled, recommended_side,
                   closing_quote_id_a, closing_quote_id_b
            FROM predictions WHERE id=?
            """,
            (prediction_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"prediction {prediction_id} not found")
        scheduled, settled, side, quote_id_a, quote_id_b = row
        if settled:
            raise ValueError("settled prediction cannot receive a closing price")
        if side not in ("A", "B"):
            raise ValueError("closing price requires a released shadow bet")
        if quote_id_a is not None or quote_id_b is not None:
            raise ValueError("closing prices are already frozen")
        _validate_closing_capture(scheduled, captured)
    context = _prediction_price_context(prediction_id)
    common = {
        "sport": "TENNIS",
        "event_id": context["event_id"],
        "event_name": context["event_name"],
        "scheduled_start": context["scheduled_start"],
        "market_key": "MATCH_WINNER",
        "market_name": "Match winner",
        "phase": "CLOSING",
        "source": "MANUAL",
        "captured_at": captured_dt,
        "model_ref": TENNIS_POLICY_VERSION,
        "metadata": {
            "prediction_id": prediction_id,
            "tour": context["tour"],
            "tournament": context["tournament"],
        },
    }
    observation_ids = _append_price_quotes(
        [
            PriceQuote(
                **common,
                selection_key="A",
                selection_name=context["player_a"],
                decimal_odds=closing_a,
            ),
            PriceQuote(
                **common,
                selection_key="B",
                selection_name=context["player_b"],
                decimal_odds=closing_b,
            ),
        ],
        recorded_at=datetime.now(timezone.utc),
    )
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                UPDATE predictions SET
                    closing_odds_a=?, closing_odds_b=?, closing_checked_utc=?,
                    closing_quote_id_a=?, closing_quote_id_b=?
                WHERE id=?
                  AND closing_quote_id_a IS NULL
                  AND closing_quote_id_b IS NULL
                """,
                (
                    closing_a,
                    closing_b,
                    captured,
                    observation_ids[0],
                    observation_ids[1],
                    prediction_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("closing prices are already frozen")
    except sqlite3.IntegrityError as exc:
        raise ValueError("closing prices are already frozen") from exc


def record_side_closing_price(
    bet_id: int,
    closing_odds: float,
    *,
    captured_utc: Optional[float] = None,
) -> None:
    """Freeze one side-market reference price shortly before start."""
    if not math.isfinite(closing_odds) or closing_odds <= 1.0:
        raise ValueError("closing odds must be greater than 1.0")
    captured_dt = _capture_datetime(captured_utc)
    captured = captured_dt.timestamp()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT p.scheduled_start_utc, s.settled, s.prediction_id,
                   s.market, s.closing_quote_id
            FROM side_bets s
            JOIN predictions p ON p.id=s.prediction_id
            WHERE s.id=?
            """,
            (bet_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"side bet {bet_id} not found")
        scheduled, settled, prediction_id, market, quote_id = row
        if settled:
            raise ValueError("settled side bet cannot receive a closing price")
        if quote_id is not None:
            raise ValueError("closing price is already frozen")
        _validate_closing_capture(scheduled, captured)
    context = _prediction_price_context(prediction_id)
    observation_id = _append_price_quotes(
        [
            PriceQuote(
                sport="TENNIS",
                event_id=context["event_id"],
                event_name=context["event_name"],
                scheduled_start=context["scheduled_start"],
                market_key=market,
                market_name=SIDE_MARKETS[market]["label"],
                selection_key=market,
                selection_name=SIDE_MARKETS[market]["label"],
                decimal_odds=closing_odds,
                phase="CLOSING",
                source="MANUAL",
                captured_at=captured_dt,
                model_ref=TENNIS_POLICY_VERSION,
                metadata={
                    "prediction_id": prediction_id,
                    "side_bet_id": bet_id,
                    "tour": context["tour"],
                    "tournament": context["tournament"],
                },
            )
        ],
        recorded_at=datetime.now(timezone.utc),
    )[0]
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                UPDATE side_bets
                SET closing_odds=?, closing_checked_utc=?, closing_quote_id=?
                WHERE id=? AND closing_quote_id IS NULL
                """,
                (closing_odds, captured, observation_id, bet_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("closing price is already frozen")
    except sqlite3.IntegrityError as exc:
        raise ValueError("closing price is already frozen") from exc


def side_bet_summary() -> Dict:
    with _connect() as conn:
        total, settled = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(s.settled),0) FROM side_bets s "
            "JOIN predictions p ON p.id=s.prediction_id "
            "WHERE s.policy_version=? AND p.model_version=?",
            (TENNIS_POLICY_VERSION, TENNIS_MODEL_VERSION),
        ).fetchone()
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(s.pnl),0), AVG(s.pnl) "
            "FROM side_bets s JOIN predictions p ON p.id=s.prediction_id "
            "WHERE s.settled=1 AND s.won IS NOT NULL "
            "AND s.entry_quote_id IS NOT NULL "
            "AND s.policy_version=? AND p.model_version=?",
            (TENNIS_POLICY_VERSION, TENNIS_MODEL_VERSION),
        ).fetchone()
        clv = conn.execute(
            "SELECT COUNT(*), AVG(s.odds / s.closing_odds - 1.0) "
            "FROM side_bets s JOIN predictions p ON p.id=s.prediction_id "
            "WHERE s.settled=1 AND s.odds>1.0 AND s.closing_odds>1.0 "
            "AND s.entry_quote_id IS NOT NULL AND s.closing_quote_id IS NOT NULL "
            "AND s.closing_checked_utc IS NOT NULL "
            "AND s.policy_version=? AND p.model_version=?",
            (TENNIS_POLICY_VERSION, TENNIS_MODEL_VERSION),
        ).fetchone()
    return {
        "side_bets": total,
        "open": total - settled,
        "settled": row[0],
        "units": round(row[1] or 0.0, 2),
        "roi": round(row[2] or 0.0, 4) if row[0] else None,
        "clv_samples": clv[0],
        "clv": round(clv[1], 4) if clv[0] else None,
        "policy_version": TENNIS_POLICY_VERSION,
        "model_version": TENNIS_MODEL_VERSION,
    }


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path if db_path is not None else DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
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
    conn.executescript(_CLOSING_TRIGGERS + REVISION_SCHEMA)
    return conn


def ensure_schema() -> None:
    """Create or migrate the shadow schema before direct read/write access."""
    with _connect():
        pass


def already_stored(match_date: str, player_a: str, player_b: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM predictions "
            "WHERE match_date=? AND player_a=? AND player_b=? "
            "AND model_version=? AND policy_version=?",
            (
                match_date,
                player_a,
                player_b,
                TENNIS_MODEL_VERSION,
                TENNIS_POLICY_VERSION,
            ),
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
    modeled_at: datetime | str | float | None = None,
    db_path: str | Path | None = None,
) -> int:
    """Freeze the initial prediction and append every later model observation.

    The original id/return convention is preserved for ledger callers: a
    subsequent observation returns -1, but is available via latest_predictions.
    """
    gates = {g.name: {"passed": g.passed, "detail": g.detail} for g in prediction.gates}
    observed = utc_epoch(
        modeled_at if modeled_at is not None
        else getattr(prediction, "modeled_at", None) or time.time()
    )
    revision = {
        "created_utc": observed,
        "match_date": match_date,
        "provider_event_id": provider_event_id,
        "scheduled_start_utc": scheduled_start_utc,
        "fixture_source": fixture_source,
        "tour": tour,
        "tournament": tournament,
        "surface": prediction.surface,
        "best_of": prediction.best_of,
        "player_a": prediction.player_a,
        "player_b": prediction.player_b,
        "p_raw": prediction.p_a_raw,
        "p_cal": prediction.p_a_cal,
        "markets_json": json.dumps(prediction.market_summary(), allow_nan=False),
        "gates_json": json.dumps(gates, ensure_ascii=False, allow_nan=False),
        "context_json": json.dumps(getattr(prediction, "context_evidence", {}), ensure_ascii=False, allow_nan=False),
        "verdict": prediction.verdict,
        "recommended_side": prediction.recommended_side,
        "recommended_edge": prediction.recommended_edge,
        "model_version": TENNIS_MODEL_VERSION,
        "policy_version": TENNIS_POLICY_VERSION,
    }
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = None
        if provider_event_id:
            existing = conn.execute(
                """
                SELECT id FROM predictions
                WHERE provider_event_id=?
                  AND (fixture_source=? OR fixture_source IS NULL)
                  AND model_version=? AND policy_version=?
                """,
                (
                    provider_event_id,
                    fixture_source,
                    TENNIS_MODEL_VERSION,
                    TENNIS_POLICY_VERSION,
                ),
            ).fetchone()
        if existing is None:
            # Pair/date matching only upgrades compatible legacy identities.
            # A known native event must not absorb another event's forecast,
            # even when the same players meet on the same calendar day.
            existing = conn.execute(
                "SELECT id FROM predictions "
                "WHERE match_date=? AND player_a=? AND player_b=? "
                "AND model_version=? AND policy_version=? "
                "AND (provider_event_id IS NULL OR fixture_source IS NULL) "
                "AND (provider_event_id IS NULL OR provider_event_id=?) "
                "AND (fixture_source IS NULL OR fixture_source=?)",
                (
                    match_date,
                    prediction.player_a,
                    prediction.player_b,
                    TENNIS_MODEL_VERSION,
                    TENNIS_POLICY_VERSION,
                    provider_event_id,
                    fixture_source,
                ),
            ).fetchone()
        if existing:
            stored = conn.execute(
                "SELECT player_a,player_b,settled FROM predictions WHERE id=?", (existing[0],)
            ).fetchone()
            if tuple(stored[:2]) != (prediction.player_a, prediction.player_b):
                raise ValueError("tennis revision cannot change player identity or orientation")
            if stored[2]:
                raise ValueError("cannot append a model revision after settlement")
            freeze_legacy_baseline(conn, int(existing[0]))
            # Schedules can move after the first scan. Model outputs stay frozen,
            # while factual fixture metadata may be refreshed.
            conn.execute(
                """
                UPDATE predictions
                SET match_date=?,
                    provider_event_id=COALESCE(provider_event_id, ?),
                    scheduled_start_utc=COALESCE(?, scheduled_start_utc),
                    fixture_source=COALESCE(fixture_source, ?)
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
            identity = conn.execute(
                "SELECT provider_event_id,fixture_source,scheduled_start_utc FROM predictions WHERE id=?",
                (existing[0],),
            ).fetchone()
            revision.update(zip(("provider_event_id", "fixture_source", "scheduled_start_utc"), identity))
            append_revision(conn, int(existing[0]), revision)
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
                observed,
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
        append_revision(conn, int(cur.lastrowid), revision)
        return int(cur.lastrowid)


def latest_predictions(
    db_path: str | Path | None = None, *, pending_only: bool = True,
    as_of: datetime | str | float | None = None,
) -> List[Dict]:
    """Read current immutable model observations; original rows remain auditable."""
    return read_latest_predictions(
        db_path if db_path is not None else DB_PATH,
        pending_only=pending_only, as_of=as_of,
    )


def workload_history(db_path: str | Path | None = None) -> List[Dict]:
    """Read observed completed facts without model/price fields or DB writes."""
    path = Path(db_path if db_path is not None else DB_PATH)
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        columns = {row[1] for row in conn.execute("PRAGMA table_info(predictions)")}
        required = {"settled", "player_a", "player_b", "provider_event_id", "fixture_source", "scheduled_start_utc", "result_observed_at", "termination", "player_a_sets", "player_b_sets"}
        if not required.issubset(columns):
            return []
        selected = sorted(required | ({"match_duration_minutes"} & columns))
        return [dict(row) for row in conn.execute(
            f"SELECT {','.join(selected)} FROM predictions WHERE settled=1 AND result_observed_at IS NOT NULL"
        )]


def pending_predictions() -> List[Dict]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM predictions WHERE settled=0 ORDER BY match_date"
        ).fetchall()
    return [dict(r) for r in rows]


def _result_observation_iso(value: datetime | str | None) -> str:
    """Return one timezone-aware observation timestamp in canonical UTC ISO form."""
    if value is None:
        observed = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        observed = value
    elif isinstance(value, str) and value.strip():
        try:
            observed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("result_observed_at must be a valid ISO timestamp") from exc
    else:
        raise TypeError("result_observed_at must be a datetime or ISO timestamp")
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("result_observed_at must include a timezone")
    return observed.astimezone(timezone.utc).isoformat()


def _validated_set_score(
    player_a_sets: Optional[int],
    player_b_sets: Optional[int],
    *,
    best_of: object,
    player_a: str,
    player_b: str,
    actual_winner: Optional[str],
    retired: bool,
) -> tuple[Optional[int], Optional[int]]:
    if player_a_sets is None and player_b_sets is None:
        return None, None
    if player_a_sets is None or player_b_sets is None:
        raise ValueError("player_a_sets and player_b_sets must be provided together")
    for field, value in (
        ("player_a_sets", player_a_sets),
        ("player_b_sets", player_b_sets),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if isinstance(best_of, bool) or not isinstance(best_of, int) or best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5 when a set score is recorded")
    sets_to_win = best_of // 2 + 1
    if player_a_sets > sets_to_win or player_b_sets > sets_to_win:
        raise ValueError("set score exceeds the stored best-of format")
    if not retired:
        winner_sets = player_a_sets if actual_winner == player_a else player_b_sets
        loser_sets = player_b_sets if actual_winner == player_a else player_a_sets
        if winner_sets != sets_to_win or loser_sets >= sets_to_win:
            raise ValueError("set score does not prove the stored winner")
    return player_a_sets, player_b_sets


def settle(prediction_id: int, actual_winner: Optional[str], ret: bool = False,
           ret_set: Optional[int] = None,
           closing_a: Optional[float] = None, closing_b: Optional[float] = None,
           *, termination: Optional[str] = None,
           result_observed_at: datetime | str | None = None,
           player_a_sets: Optional[int] = None,
           player_b_sets: Optional[int] = None,
           match_duration_minutes: Optional[int] = None) -> None:
    """Settle one prediction and persist auditable result evidence.

    Existing callers remain valid: when no observation time is supplied, the
    current UTC instant is recorded.  Set scores are optional, but must be a
    complete, winner-consistent A/B pair when supplied for a normal final.
    """
    if closing_a is not None or closing_b is not None:
        raise ValueError(
            "record closing odds before settlement with record_closing_prices"
        )
    if not isinstance(ret, bool):
        raise TypeError("ret must be a boolean")
    if termination is None:
        clean_termination = "retirement" if ret else "normal"
    elif isinstance(termination, str) and termination in {
        "normal",
        "retirement",
        "walkover",
    }:
        clean_termination = termination
    else:
        raise ValueError("termination must be normal, retirement, or walkover")
    if ret and clean_termination != "retirement":
        raise ValueError("ret=True requires retirement termination")
    retired = clean_termination == "retirement"
    if ret_set is not None and (
        isinstance(ret_set, bool) or not isinstance(ret_set, int) or ret_set < 0
    ):
        raise ValueError("ret_set must be a non-negative integer")
    if not retired and ret_set is not None:
        raise ValueError("ret_set requires retirement termination")
    if clean_termination == "walkover" and (
        actual_winner is not None
        or player_a_sets is not None
        or player_b_sets is not None
    ):
        raise ValueError("walkover cannot include a winner or set score")
    observed_iso = _result_observation_iso(result_observed_at)
    if match_duration_minutes is not None and (
        isinstance(match_duration_minutes, bool)
        or not isinstance(match_duration_minutes, int)
        or not 1 <= match_duration_minutes <= 1500
        or clean_termination == "walkover"
    ):
        raise ValueError("match duration must be observed playing minutes for a played match")
    with _connect() as conn:
        row = conn.execute(
            "SELECT player_a, player_b, recommended_side, odds_a, odds_b, "
            "best_of, settled FROM predictions WHERE id=?",
            (prediction_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"prediction {prediction_id} not found")
        player_a, player_b, side, odds_a, odds_b, best_of, settled = row
        if settled:
            raise ValueError("prediction is already settled")
        if actual_winner is not None and actual_winner not in (player_a, player_b):
            raise ValueError("actual_winner must match one of the stored players")
        if clean_termination == "normal" and actual_winner is None:
            raise ValueError("normal settlement requires an actual_winner")
        player_a_sets, player_b_sets = _validated_set_score(
            player_a_sets,
            player_b_sets,
            best_of=best_of,
            player_a=player_a,
            player_b=player_b,
            actual_winner=actual_winner,
            retired=retired,
        )
        pnl: Optional[float] = None
        if side:
            if clean_termination == "walkover" or actual_winner is None:
                pnl = 0.0
            else:
                odds = odds_a if side == "A" else odds_b
                won = (side == "A" and actual_winner == player_a) or (
                    side == "B" and actual_winner == player_b
                )
                if odds is None or odds <= 1.0:
                    pnl = None
                elif retired and RETIREMENT_RULE == "match_completed":
                    pnl = 0.0  # void
                elif retired and RETIREMENT_RULE == "one_set" and (ret_set or 0) < 1:
                    pnl = 0.0  # void before set 1 completed
                else:
                    pnl = (odds - 1.0) if won else -1.0

        cursor = conn.execute(
            """
            UPDATE predictions
            SET settled=1, actual_winner=?, ret_flag=?, ret_set=?,
                termination=?, result_observed_at=?,
                player_a_sets=?, player_b_sets=?, pnl=?, match_duration_minutes=?
            WHERE id=? AND settled=0
            """,
            (
                actual_winner,
                1 if retired else 0,
                ret_set,
                clean_termination,
                observed_iso,
                player_a_sets,
                player_b_sets,
                pnl,
                match_duration_minutes,
                prediction_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("prediction is already settled")


def summary() -> Dict:
    with _connect() as conn:
        total, settled = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(settled),0) FROM predictions "
            "WHERE model_version=?",
            (TENNIS_MODEL_VERSION,),
        ).fetchone()
        recommended_total = conn.execute(
            "SELECT COUNT(*) FROM predictions "
            "WHERE recommended_side IN ('A', 'B') "
            "AND entry_quote_id_a IS NOT NULL AND entry_quote_id_b IS NOT NULL "
            "AND model_version=? AND policy_version=?",
            (TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION),
        ).fetchone()[0]
        reco = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(pnl),0), AVG(pnl) FROM predictions "
            "WHERE settled=1 AND recommended_side IS NOT NULL AND pnl IS NOT NULL "
            "AND entry_quote_id_a IS NOT NULL AND entry_quote_id_b IS NOT NULL "
            "AND model_version=? AND policy_version=?",
            (TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION),
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
              AND model_version=? AND policy_version=?
              AND closing_checked_utc IS NOT NULL
              AND entry_quote_id_a IS NOT NULL
              AND entry_quote_id_b IS NOT NULL
              AND closing_quote_id_a IS NOT NULL
              AND closing_quote_id_b IS NOT NULL
              AND (
                  (recommended_side='A' AND odds_a>1.0 AND closing_odds_a>1.0)
                  OR
                  (recommended_side='B' AND odds_b>1.0 AND closing_odds_b>1.0)
              )
            """,
            (TENNIS_MODEL_VERSION, TENNIS_POLICY_VERSION),
        ).fetchone()
        brier = conn.execute(
            """
            SELECT COUNT(*), AVG(
                (p_cal - CASE WHEN actual_winner=player_a THEN 1.0 ELSE 0.0 END)
                * (p_cal - CASE WHEN actual_winner=player_a THEN 1.0 ELSE 0.0 END)
            )
            FROM predictions
            WHERE settled=1 AND actual_winner IN (player_a, player_b)
              AND model_version=?
            """,
            (TENNIS_MODEL_VERSION,),
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
              AND entry_quote_id_a IS NOT NULL
              AND entry_quote_id_b IS NOT NULL
              AND closing_quote_id_a IS NOT NULL
              AND closing_quote_id_b IS NOT NULL
              AND model_version=?
            """,
            (TENNIS_MODEL_VERSION,),
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
        "model_version": TENNIS_MODEL_VERSION,
    }
