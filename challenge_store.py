"""Persistent cent-accurate bankroll ledger for the 15K challenge."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import sqlite3
from typing import Any, Optional

from challenge_engine import QuotedTicket, TARGET_BALANCE


DEFAULT_CHALLENGE_DB = Path(__file__).with_name("challenge_15k.db")
VALID_STATUSES = {"PENDING", "WON", "LOST", "VOID"}


def _money_to_cents(value: Any, *, allow_zero: bool = True) -> int:
    if isinstance(value, bool):
        raise ValueError("Money must be numeric, not boolean")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Money must be numeric") from exc
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        raise ValueError("Money must be finite and non-negative")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cents_to_money(value: int) -> float:
    return float(Decimal(int(value)) / Decimal(100))


class ChallengeLedger:
    """Store challenge settings and settle one ticket per calendar day."""

    def __init__(self, db_path: str | Path = DEFAULT_CHALLENGE_DB):
        self.db_path = str(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    starting_balance_cents INTEGER NOT NULL CHECK (starting_balance_cents >= 0),
                    current_balance_cents INTEGER NOT NULL CHECK (current_balance_cents >= 0),
                    target_balance_cents INTEGER NOT NULL CHECK (target_balance_cents > 0),
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_date TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    quote_verified_at TEXT NOT NULL,
                    settled_at TEXT,
                    status TEXT NOT NULL CHECK (status IN ('PENDING', 'WON', 'LOST', 'VOID')),
                    stake_cents INTEGER NOT NULL CHECK (stake_cents > 0),
                    payout_cents INTEGER NOT NULL DEFAULT 0 CHECK (payout_cents >= 0),
                    total_odds REAL NOT NULL CHECK (total_odds > 1),
                    joint_probability REAL NOT NULL CHECK (joint_probability >= 0 AND joint_probability <= 1),
                    expected_roi REAL NOT NULL,
                    legs_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_challenge_daily_ticket
                ON challenge_tickets(analysis_date)
                WHERE status != 'VOID'
                """
            )
            now = datetime.now(timezone.utc).isoformat()
            default_cents = _money_to_cents(100.0)
            target_cents = _money_to_cents(TARGET_BALANCE, allow_zero=False)
            connection.execute(
                """
                INSERT OR IGNORE INTO challenge_settings (
                    id, starting_balance_cents, current_balance_cents,
                    target_balance_cents, updated_at
                ) VALUES (1, ?, ?, ?, ?)
                """,
                (default_cents, default_cents, target_cents, now),
            )
            connection.commit()

    def settings(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM challenge_settings WHERE id = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("Challenge settings are missing")
        return {
            "starting_balance": _cents_to_money(row["starting_balance_cents"]),
            "current_balance": _cents_to_money(row["current_balance_cents"]),
            "target_balance": _cents_to_money(row["target_balance_cents"]),
            "updated_at": row["updated_at"],
        }

    def set_balance(self, balance: Any, *, reset_start: bool = False) -> dict[str, Any]:
        cents = _money_to_cents(balance)
        with closing(self._connect()) as connection:
            pending = connection.execute(
                "SELECT COUNT(*) FROM challenge_tickets WHERE status = 'PENDING'"
            ).fetchone()[0]
            if pending:
                raise ValueError("Open tickets must be settled before correcting the balance")
            now = datetime.now(timezone.utc).isoformat()
            if reset_start:
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET starting_balance_cents = ?, current_balance_cents = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (cents, cents, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (cents, now),
                )
            connection.commit()
        return self.settings()

    @staticmethod
    def _ticket_legs(ticket: QuotedTicket) -> list[dict[str, Any]]:
        return [
            {
                "candidate_id": leg.candidate.candidate_id,
                "fixture_id": leg.candidate.fixture_id,
                "kickoff": leg.candidate.kickoff,
                "match": f"{leg.candidate.home_team} vs {leg.candidate.away_team}",
                "market": leg.candidate.market,
                "selection": leg.candidate.selection,
                "model_probability": leg.candidate.probability,
                "conservative_probability": leg.candidate.conservative_probability,
                "evidence_score": leg.candidate.evidence_score,
                "odds": leg.odds,
                "expected_roi": leg.expected_roi,
            }
            for leg in ticket.legs
        ]

    def place_ticket(
        self,
        analysis_date: str,
        ticket: QuotedTicket,
        stake: Any,
        quote_verified_at: str,
    ) -> int:
        stake_cents = _money_to_cents(stake, allow_zero=False)
        if not ticket.legs or len(ticket.legs) > 3:
            raise ValueError("A challenge ticket must contain one to three legs")
        legs_json = json.dumps(self._ticket_legs(ticket), ensure_ascii=False, separators=(",", ":"))
        now = datetime.now(timezone.utc).isoformat()

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT current_balance_cents FROM challenge_settings WHERE id = 1"
                ).fetchone()
                if row is None or stake_cents > row[0]:
                    raise ValueError("Stake exceeds the available balance")
                cursor = connection.execute(
                    """
                    INSERT INTO challenge_tickets (
                        analysis_date, created_at, quote_verified_at, status,
                        stake_cents, total_odds, joint_probability,
                        expected_roi, legs_json
                    ) VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_date,
                        now,
                        quote_verified_at,
                        stake_cents,
                        ticket.total_odds,
                        ticket.joint_probability,
                        ticket.expected_roi,
                        legs_json,
                    ),
                )
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents = current_balance_cents - ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (stake_cents, now),
                )
                connection.commit()
                return int(cursor.lastrowid)
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("For this date, a challenge ticket already exists") from exc
            except Exception:
                connection.rollback()
                raise

    def settle_ticket(self, ticket_id: int, status: str) -> dict[str, Any]:
        normalized = str(status).upper()
        if normalized not in {"WON", "LOST", "VOID"}:
            raise ValueError("Settlement status must be WON, LOST, or VOID")
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status, stake_cents, total_odds FROM challenge_tickets WHERE id = ?",
                (int(ticket_id),),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ValueError("Ticket does not exist")
            if row["status"] != "PENDING":
                connection.rollback()
                raise ValueError("Ticket has already been settled")

            if normalized == "WON":
                payout_cents = _money_to_cents(
                    _cents_to_money(row["stake_cents"]) * float(row["total_odds"])
                )
            elif normalized == "VOID":
                payout_cents = int(row["stake_cents"])
            else:
                payout_cents = 0
            connection.execute(
                """
                UPDATE challenge_tickets
                SET status = ?, payout_cents = ?, settled_at = ?
                WHERE id = ?
                """,
                (normalized, payout_cents, now, int(ticket_id)),
            )
            connection.execute(
                """
                UPDATE challenge_settings
                SET current_balance_cents = current_balance_cents + ?, updated_at = ?
                WHERE id = 1
                """,
                (payout_cents, now),
            )
            connection.commit()
        return self.get_ticket(ticket_id)

    @staticmethod
    def _row_to_ticket(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "analysis_date": row["analysis_date"],
            "created_at": row["created_at"],
            "quote_verified_at": row["quote_verified_at"],
            "settled_at": row["settled_at"],
            "status": row["status"],
            "stake": _cents_to_money(row["stake_cents"]),
            "payout": _cents_to_money(row["payout_cents"]),
            "total_odds": float(row["total_odds"]),
            "joint_probability": float(row["joint_probability"]),
            "expected_roi": float(row["expected_roi"]),
            "legs": json.loads(row["legs_json"]),
        }

    def get_ticket(self, ticket_id: int) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM challenge_tickets WHERE id = ?", (int(ticket_id),)
            ).fetchone()
        if row is None:
            raise ValueError("Ticket does not exist")
        return self._row_to_ticket(row)

    def tickets(self, limit: int = 100) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM challenge_tickets ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def pending_tickets(self) -> list[dict[str, Any]]:
        return [ticket for ticket in self.tickets() if ticket["status"] == "PENDING"]


__all__ = ["ChallengeLedger", "DEFAULT_CHALLENGE_DB"]
