"""Persistent cross-sport records for price-approved betting candidates."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
import sqlite3
from typing import Optional

from multi_sport_recommendations import PriceDecision


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "saved_tips.db"
SETTLEMENT_RESULTS = frozenset({"WON", "LOST", "VOID"})
SAVEABLE_DECISION_STATUSES = frozenset({"BET", "SHADOW"})


@dataclass(frozen=True)
class SavedTip:
    id: int
    created_at: str
    updated_at: str
    sport: str
    event_key: str
    event_label: str
    market: str
    selection: str
    model_probability: float
    risk_adjusted_probability: float
    minimum_odds: float
    quoted_odds: float
    decision_status: str
    evidence_stage: str
    stake_amount: float
    source: str
    result: Optional[str]
    settled_at: Optional[str]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_tips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_id TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sport TEXT NOT NULL,
    event_key TEXT NOT NULL,
    event_label TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    model_probability REAL NOT NULL,
    risk_adjusted_probability REAL NOT NULL,
    minimum_odds REAL NOT NULL,
    quoted_odds REAL NOT NULL,
    decision_status TEXT NOT NULL,
    evidence_stage TEXT NOT NULL,
    stake_amount REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    result TEXT CHECK (result IS NULL OR result IN ('WON', 'LOST', 'VOID')),
    settled_at TEXT,
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    UNIQUE(scope_id, identity_key)
);

CREATE INDEX IF NOT EXISTS idx_saved_tips_state
ON saved_tips(scope_id, archived, result, updated_at DESC);
"""


def _text(value, field: str, maximum: int = 300) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{field} muss 1 bis {maximum} Zeichen enthalten")
    return normalized


def _positive_number(value, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} muss numerisch sein")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} muss numerisch sein") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field} muss positiv und endlich sein")
    return number


class TipStore:
    """Small SQLite store shared by football, live and multi-sport finders."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        *,
        scope_id: str = "default",
    ):
        self.db_path = Path(db_path)
        self.scope_id = _text(scope_id, "Sitzung", 120)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @staticmethod
    def _identity(
        sport: str,
        event_key: str,
        market: str,
        selection: str,
    ) -> str:
        payload = "\x1f".join((sport, event_key, market, selection)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def save_decision(
        self,
        decision: PriceDecision,
        *,
        source: str,
        now: Optional[datetime] = None,
    ) -> SavedTip:
        """Upsert one confirmed, price-approved decision."""
        if (
            not isinstance(decision, PriceDecision)
            or decision.status not in SAVEABLE_DECISION_STATUSES
        ):
            raise ValueError("Nur freigegebene oder Shadow-Tipps können gespeichert werden")
        candidate = decision.candidate
        if decision.quoted_odds is None:
            raise ValueError("Eine bestätigte Quote fehlt")
        timestamp = now or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("Zeitstempel benötigt eine Zeitzone")
        timestamp_text = timestamp.astimezone(timezone.utc).isoformat()
        sport = _text(candidate.sport, "Sport", 60)
        event_key = _text(candidate.event_key, "Ereignis-ID", 220)
        event_label = _text(candidate.event_label, "Ereignis", 300)
        market = _text(candidate.market, "Markt", 240)
        selection = _text(candidate.selection, "Auswahl", 240)
        model_probability = _positive_number(
            candidate.model_probability,
            "Modellwahrscheinlichkeit",
        )
        adjusted_probability = _positive_number(
            candidate.risk_adjusted_probability,
            "Konservative Wahrscheinlichkeit",
        )
        minimum_odds = _positive_number(candidate.minimum_odds, "Mindestquote")
        quoted_odds = _positive_number(decision.quoted_odds, "Quote")
        source_text = _text(source, "Quelle", 120)
        identity = self._identity(sport, event_key, market, selection)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO saved_tips (
                    scope_id, identity_key, created_at, updated_at, sport, event_key,
                    event_label, market, selection, model_probability,
                    risk_adjusted_probability, minimum_odds, quoted_odds,
                    decision_status, evidence_stage, stake_amount, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_id, identity_key) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    event_label=excluded.event_label,
                    model_probability=excluded.model_probability,
                    risk_adjusted_probability=excluded.risk_adjusted_probability,
                    minimum_odds=excluded.minimum_odds,
                    quoted_odds=excluded.quoted_odds,
                    decision_status=excluded.decision_status,
                    evidence_stage=excluded.evidence_stage,
                    stake_amount=excluded.stake_amount,
                    source=excluded.source,
                    archived=0
                """,
                (
                    self.scope_id,
                    identity,
                    timestamp_text,
                    timestamp_text,
                    sport,
                    event_key,
                    event_label,
                    market,
                    selection,
                    model_probability,
                    adjusted_probability,
                    minimum_odds,
                    quoted_odds,
                    _text(decision.status, "Status", 30),
                    _text(candidate.evidence_stage, "Evidenzstufe", 40),
                    max(0.0, float(decision.stake_amount or 0.0)),
                    source_text,
                ),
            )
            row = connection.execute(
                "SELECT * FROM saved_tips WHERE scope_id=? AND identity_key=?",
                (self.scope_id, identity),
            ).fetchone()
            connection.commit()
        return self._saved_tip(row)

    def list_tips(
        self,
        *,
        active: Optional[bool] = None,
        include_archived: bool = False,
    ) -> list[SavedTip]:
        clauses = ["scope_id=?"]
        params: list[object] = [self.scope_id]
        if not include_archived:
            clauses.append("archived=0")
        if active is True:
            clauses.append("result IS NULL")
        elif active is False:
            clauses.append("result IS NOT NULL")
        query = "SELECT * FROM saved_tips"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY COALESCE(settled_at, updated_at) DESC, id DESC"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._saved_tip(row) for row in rows]

    def settle(
        self,
        tip_id: int,
        result: str,
        *,
        now: Optional[datetime] = None,
    ) -> None:
        normalized = str(result).strip().upper()
        if normalized not in SETTLEMENT_RESULTS:
            raise ValueError("Ergebnis muss WON, LOST oder VOID sein")
        timestamp = now or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("Zeitstempel benötigt eine Zeitzone")
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE saved_tips
                SET result=?, settled_at=?, updated_at=?
                WHERE id=? AND scope_id=? AND archived=0 AND result IS NULL
                """,
                (
                    normalized,
                    timestamp.astimezone(timezone.utc).isoformat(),
                    timestamp.astimezone(timezone.utc).isoformat(),
                    int(tip_id),
                    self.scope_id,
                ),
            )
            connection.commit()
        if cursor.rowcount != 1:
            raise ValueError("Aktiver Tipp wurde nicht gefunden")

    def archive(self, tip_id: int) -> None:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE saved_tips SET archived=1 WHERE id=? AND scope_id=? AND archived=0",
                (int(tip_id), self.scope_id),
            )
            connection.commit()
        if cursor.rowcount != 1:
            raise ValueError("Tipp wurde nicht gefunden")

    def archive_candidate(
        self,
        *,
        sport: str,
        event_key: str,
        market: str,
        selection: str,
    ) -> None:
        """Remove a previously approved pick when a fresh price check fails."""
        identity = self._identity(
            _text(sport, "Sport", 60),
            _text(event_key, "Ereignis-ID", 220),
            _text(market, "Markt", 240),
            _text(selection, "Auswahl", 240),
        )
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE saved_tips SET archived=1
                WHERE scope_id=? AND identity_key=? AND result IS NULL
                """,
                (self.scope_id, identity),
            )
            connection.commit()

    @staticmethod
    def _saved_tip(row: sqlite3.Row) -> SavedTip:
        return SavedTip(
            id=int(row["id"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            sport=row["sport"],
            event_key=row["event_key"],
            event_label=row["event_label"],
            market=row["market"],
            selection=row["selection"],
            model_probability=float(row["model_probability"]),
            risk_adjusted_probability=float(row["risk_adjusted_probability"]),
            minimum_odds=float(row["minimum_odds"]),
            quoted_odds=float(row["quoted_odds"]),
            decision_status=row["decision_status"],
            evidence_stage=row["evidence_stage"],
            stake_amount=float(row["stake_amount"]),
            source=row["source"],
            result=row["result"],
            settled_at=row["settled_at"],
        )


__all__ = ["DEFAULT_DB_PATH", "SavedTip", "TipStore"]
