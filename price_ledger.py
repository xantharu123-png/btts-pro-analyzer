"""Append-only, tamper-evident bookmaker price observations."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Optional

from betting_math import BettingMathError, validate_decimal_odds


BOOKMAKER = "N1Bet"
ALLOWED_SPORTS = {
    "BASKETBALL",
    "CRICKET",
    "ESPORTS",
    "FOOTBALL",
    "ICE_HOCKEY",
    "TENNIS",
}
ALLOWED_PHASES = {"ENTRY", "OPENING", "CLOSING", "REFERENCE", "LIVE"}
ALLOWED_SOURCES = {"MANUAL", "BOOKMAKER_EXPORT", "API", "PERMITTED_CAPTURE"}
MANUAL_CAPTURE_MAX_AGE_SECONDS = 5 * 60
ZERO_HASH = "0" * 64
ODDS_SCALE = Decimal("1000000")
LINE_SCALE = Decimal("1000000")


class PriceLedgerError(ValueError):
    """Raised when a quote cannot be admitted to the evidence ledger."""


class PriceLedgerIntegrityError(RuntimeError):
    """Raised when the append-only hash chain no longer verifies."""


@dataclass(frozen=True)
class PriceQuote:
    sport: str
    event_id: str
    event_name: str
    scheduled_start: datetime | str
    market_key: str
    market_name: str
    selection_key: str
    selection_name: str
    decimal_odds: float
    phase: str = "ENTRY"
    source: str = "MANUAL"
    captured_at: datetime | str | float | int | None = None
    line: Optional[float] = None
    model_ref: Optional[str] = None
    supersedes_id: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class PriceObservation:
    id: int
    recorded_at: str
    captured_at: str
    bookmaker: str
    sport: str
    event_id: str
    event_name: str
    scheduled_start: str
    market_key: str
    market_name: str
    selection_key: str
    selection_name: str
    decimal_odds: float
    phase: str
    source: str
    line: Optional[float]
    model_ref: Optional[str]
    supersedes_id: Optional[int]
    metadata: dict[str, Any]
    previous_hash: str
    record_hash: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    bookmaker TEXT NOT NULL CHECK (bookmaker = 'N1Bet'),
    sport TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    scheduled_start TEXT NOT NULL,
    market_key TEXT NOT NULL,
    market_name TEXT NOT NULL,
    selection_key TEXT NOT NULL,
    selection_name TEXT NOT NULL,
    line_micros INTEGER,
    odds_micros INTEGER NOT NULL CHECK (odds_micros > 1000000),
    phase TEXT NOT NULL,
    source TEXT NOT NULL,
    model_ref TEXT,
    supersedes_id INTEGER,
    metadata_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL UNIQUE,
    FOREIGN KEY (supersedes_id) REFERENCES price_observations(id)
);

CREATE INDEX IF NOT EXISTS idx_price_observation_event
ON price_observations(sport, event_id, market_key, selection_key, id);

CREATE TRIGGER IF NOT EXISTS price_observations_no_update
BEFORE UPDATE ON price_observations
BEGIN
    SELECT RAISE(ABORT, 'price observations are append-only');
END;

CREATE TRIGGER IF NOT EXISTS price_observations_no_delete
BEFORE DELETE ON price_observations
BEGIN
    SELECT RAISE(ABORT, 'price observations are append-only');
END;
"""


def _utc_datetime(value: datetime | str | float | int, field: str) -> datetime:
    if isinstance(value, bool):
        raise PriceLedgerError(f"{field} must be a timestamp")
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise PriceLedgerError(f"{field} must be finite")
        parsed = datetime.fromtimestamp(float(value), timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise PriceLedgerError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise PriceLedgerError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _text(value: Any, field: str, *, maximum: int = 300) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum:
        raise PriceLedgerError(f"{field} must contain 1-{maximum} characters")
    return text


def _scaled_decimal(
    value: Any,
    field: str,
    scale: Decimal,
    *,
    maximum: float,
) -> int:
    if isinstance(value, bool):
        raise PriceLedgerError(f"{field} must be numeric")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PriceLedgerError(f"{field} must be numeric") from exc
    if not number.is_finite() or abs(number) > Decimal(str(maximum)):
        raise PriceLedgerError(f"{field} is outside the supported range")
    return int((number * scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _normalize_metadata(value: Optional[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    metadata = value or {}
    if not isinstance(metadata, dict):
        raise PriceLedgerError("metadata must be an object")
    try:
        encoded = json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise PriceLedgerError("metadata must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > 16_384:
        raise PriceLedgerError("metadata is too large")
    return metadata, encoded


def _row_payload(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "recorded_at": row["recorded_at"],
        "captured_at": row["captured_at"],
        "bookmaker": row["bookmaker"],
        "sport": row["sport"],
        "event_id": row["event_id"],
        "event_name": row["event_name"],
        "scheduled_start": row["scheduled_start"],
        "market_key": row["market_key"],
        "market_name": row["market_name"],
        "selection_key": row["selection_key"],
        "selection_name": row["selection_name"],
        "line_micros": row["line_micros"],
        "odds_micros": row["odds_micros"],
        "phase": row["phase"],
        "source": row["source"],
        "model_ref": row["model_ref"],
        "supersedes_id": row["supersedes_id"],
        "metadata_json": row["metadata_json"],
        "previous_hash": row["previous_hash"],
    }


def _record_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PriceLedger:
    """Write-once price evidence that can share an existing SQLite database."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(_SCHEMA)

    @staticmethod
    def _verify_rows(connection: sqlite3.Connection) -> tuple[bool, Optional[int]]:
        expected_previous = ZERO_HASH
        rows = connection.execute(
            "SELECT * FROM price_observations ORDER BY id"
        ).fetchall()
        for row in rows:
            if row["previous_hash"] != expected_previous:
                return False, int(row["id"])
            if _record_hash(_row_payload(row)) != row["record_hash"]:
                return False, int(row["id"])
            expected_previous = row["record_hash"]
        return True, None

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        with closing(self._connect()) as connection:
            return self._verify_rows(connection)

    @staticmethod
    def _validated_quote(
        quote: PriceQuote,
        *,
        recorded_at: datetime,
    ) -> dict[str, Any]:
        if not isinstance(quote, PriceQuote):
            raise PriceLedgerError("quote must be a PriceQuote")
        sport = _text(quote.sport, "sport", maximum=40).upper()
        if sport not in ALLOWED_SPORTS:
            raise PriceLedgerError(f"unsupported sport: {sport}")
        phase = _text(quote.phase, "phase", maximum=20).upper()
        if phase not in ALLOWED_PHASES:
            raise PriceLedgerError(f"unsupported quote phase: {phase}")
        source = _text(quote.source, "source", maximum=30).upper()
        if source not in ALLOWED_SOURCES:
            raise PriceLedgerError(f"unsupported quote source: {source}")
        scheduled = _utc_datetime(quote.scheduled_start, "scheduled_start")
        captured = _utc_datetime(
            quote.captured_at if quote.captured_at is not None else recorded_at,
            "captured_at",
        )
        if captured > recorded_at + timedelta(seconds=60):
            raise PriceLedgerError("captured_at cannot be in the future")
        if (
            source in {"MANUAL", "PERMITTED_CAPTURE"}
            and abs((recorded_at - captured).total_seconds())
            > MANUAL_CAPTURE_MAX_AGE_SECONDS
        ):
            raise PriceLedgerError(
                "manual price observations cannot be entered retroactively"
            )
        if phase != "LIVE" and captured > scheduled:
            raise PriceLedgerError("pre-match price cannot be captured after start")
        try:
            odds = validate_decimal_odds(quote.decimal_odds)
        except BettingMathError as exc:
            raise PriceLedgerError(str(exc)) from exc
        if odds > 1_000:
            raise PriceLedgerError("decimal odds are implausibly large")
        odds_micros = _scaled_decimal(
            odds,
            "decimal_odds",
            ODDS_SCALE,
            maximum=1_000,
        )
        line_micros = (
            _scaled_decimal(
                quote.line,
                "line",
                LINE_SCALE,
                maximum=10_000,
            )
            if quote.line is not None
            else None
        )
        metadata, metadata_json = _normalize_metadata(quote.metadata)
        supersedes_id = quote.supersedes_id
        if supersedes_id is not None and (
            isinstance(supersedes_id, bool)
            or not isinstance(supersedes_id, int)
            or supersedes_id <= 0
        ):
            raise PriceLedgerError("supersedes_id must be a positive integer")
        model_ref = (
            _text(quote.model_ref, "model_ref", maximum=200)
            if quote.model_ref is not None
            else None
        )
        return {
            "recorded_at": recorded_at.isoformat(),
            "captured_at": captured.isoformat(),
            "bookmaker": BOOKMAKER,
            "sport": sport,
            "event_id": _text(quote.event_id, "event_id", maximum=200),
            "event_name": _text(quote.event_name, "event_name", maximum=300),
            "scheduled_start": scheduled.isoformat(),
            "market_key": _text(quote.market_key, "market_key", maximum=200),
            "market_name": _text(quote.market_name, "market_name", maximum=300),
            "selection_key": _text(
                quote.selection_key,
                "selection_key",
                maximum=200,
            ),
            "selection_name": _text(
                quote.selection_name,
                "selection_name",
                maximum=300,
            ),
            "line_micros": line_micros,
            "odds_micros": odds_micros,
            "phase": phase,
            "source": source,
            "model_ref": model_ref,
            "supersedes_id": supersedes_id,
            "metadata": metadata,
            "metadata_json": metadata_json,
        }

    def append(
        self,
        quote: PriceQuote,
        *,
        now: Optional[datetime] = None,
    ) -> PriceObservation:
        return self.append_many((quote,), now=now)[0]

    def append_many(
        self,
        quotes: Iterable[PriceQuote],
        *,
        now: Optional[datetime] = None,
    ) -> list[PriceObservation]:
        recorded_at = (
            _utc_datetime(now, "now")
            if now is not None
            else datetime.now(timezone.utc)
        )
        items = [
            self._validated_quote(quote, recorded_at=recorded_at)
            for quote in quotes
        ]
        if not items:
            return []
        observations: list[PriceObservation] = []
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            valid, bad_id = self._verify_rows(connection)
            if not valid:
                connection.rollback()
                raise PriceLedgerIntegrityError(
                    f"price hash chain is invalid at observation {bad_id}"
                )
            previous_row = connection.execute(
                "SELECT record_hash FROM price_observations ORDER BY id DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous_row["record_hash"] if previous_row else ZERO_HASH
            for item in items:
                if item["supersedes_id"] is not None:
                    superseded = connection.execute(
                        "SELECT * FROM price_observations WHERE id=?",
                        (item["supersedes_id"],),
                    ).fetchone()
                    identity = (
                        "sport",
                        "event_id",
                        "market_key",
                        "selection_key",
                    )
                    if superseded is None or any(
                        superseded[field] != item[field] for field in identity
                    ):
                        connection.rollback()
                        raise PriceLedgerError(
                            "a correction must supersede the same event and selection"
                        )
                payload = {
                    key: value
                    for key, value in item.items()
                    if key != "metadata"
                }
                payload["previous_hash"] = previous_hash
                digest = _record_hash(payload)
                cursor = connection.execute(
                    """
                    INSERT INTO price_observations (
                        recorded_at, captured_at, bookmaker, sport, event_id,
                        event_name, scheduled_start, market_key, market_name,
                        selection_key, selection_name, line_micros, odds_micros,
                        phase, source, model_ref, supersedes_id, metadata_json,
                        previous_hash, record_hash
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?
                    )
                    """,
                    (
                        item["recorded_at"],
                        item["captured_at"],
                        item["bookmaker"],
                        item["sport"],
                        item["event_id"],
                        item["event_name"],
                        item["scheduled_start"],
                        item["market_key"],
                        item["market_name"],
                        item["selection_key"],
                        item["selection_name"],
                        item["line_micros"],
                        item["odds_micros"],
                        item["phase"],
                        item["source"],
                        item["model_ref"],
                        item["supersedes_id"],
                        item["metadata_json"],
                        previous_hash,
                        digest,
                    ),
                )
                observations.append(
                    PriceObservation(
                        id=int(cursor.lastrowid),
                        recorded_at=item["recorded_at"],
                        captured_at=item["captured_at"],
                        bookmaker=item["bookmaker"],
                        sport=item["sport"],
                        event_id=item["event_id"],
                        event_name=item["event_name"],
                        scheduled_start=item["scheduled_start"],
                        market_key=item["market_key"],
                        market_name=item["market_name"],
                        selection_key=item["selection_key"],
                        selection_name=item["selection_name"],
                        decimal_odds=float(
                            Decimal(item["odds_micros"]) / ODDS_SCALE
                        ),
                        phase=item["phase"],
                        source=item["source"],
                        line=(
                            float(Decimal(item["line_micros"]) / LINE_SCALE)
                            if item["line_micros"] is not None
                            else None
                        ),
                        model_ref=item["model_ref"],
                        supersedes_id=item["supersedes_id"],
                        metadata=item["metadata"],
                        previous_hash=previous_hash,
                        record_hash=digest,
                    )
                )
                previous_hash = digest
            connection.commit()
        return observations

    @staticmethod
    def _observation(row: sqlite3.Row) -> PriceObservation:
        return PriceObservation(
            id=int(row["id"]),
            recorded_at=row["recorded_at"],
            captured_at=row["captured_at"],
            bookmaker=row["bookmaker"],
            sport=row["sport"],
            event_id=row["event_id"],
            event_name=row["event_name"],
            scheduled_start=row["scheduled_start"],
            market_key=row["market_key"],
            market_name=row["market_name"],
            selection_key=row["selection_key"],
            selection_name=row["selection_name"],
            decimal_odds=float(Decimal(row["odds_micros"]) / ODDS_SCALE),
            phase=row["phase"],
            source=row["source"],
            line=(
                float(Decimal(row["line_micros"]) / LINE_SCALE)
                if row["line_micros"] is not None
                else None
            ),
            model_ref=row["model_ref"],
            supersedes_id=row["supersedes_id"],
            metadata=json.loads(row["metadata_json"]),
            previous_hash=row["previous_hash"],
            record_hash=row["record_hash"],
        )

    def get(self, observation_id: int) -> PriceObservation:
        if (
            isinstance(observation_id, bool)
            or not isinstance(observation_id, int)
            or observation_id <= 0
        ):
            raise PriceLedgerError("observation_id must be a positive integer")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM price_observations WHERE id=?",
                (observation_id,),
            ).fetchone()
        if row is None:
            raise PriceLedgerError("price observation does not exist")
        return self._observation(row)

    def for_event(self, sport: str, event_id: str) -> list[PriceObservation]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM price_observations
                WHERE sport=? AND event_id=?
                ORDER BY id
                """,
                (str(sport).strip().upper(), str(event_id).strip()),
            ).fetchall()
        return [self._observation(row) for row in rows]


__all__ = [
    "BOOKMAKER",
    "PriceLedger",
    "PriceLedgerError",
    "PriceLedgerIntegrityError",
    "PriceObservation",
    "PriceQuote",
]
