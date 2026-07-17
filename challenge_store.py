"""Persistent cent-accurate bankroll ledger for the 15K challenge."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Optional

from challenge_engine import (
    CROSS_LEG_MODEL_FACTOR,
    MAX_STAKE_FRACTION,
    QuotedTicket,
    TARGET_BALANCE,
    TARGET_ODDS_MAX,
    TARGET_ODDS_MIN,
    candidate_is_credible,
)
from betting_math import BettingMathError, evaluate_market_price, validate_decimal_odds


DEFAULT_CHALLENGE_DB = Path(__file__).with_name("challenge_15k.db")
VALID_STATUSES = {"PENDING", "WON", "LOST", "VOID"}
MAX_QUOTE_AGE_SECONDS = 10 * 60


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


def _utc_datetime(value: Any, label: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return timestamp.astimezone(timezone.utc)


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


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
        try:
            analysis_day = datetime.fromisoformat(str(analysis_date)).date()
        except (TypeError, ValueError) as exc:
            raise ValueError("analysis_date must be an ISO calendar date") from exc
        if str(analysis_day) != str(analysis_date):
            raise ValueError("analysis_date must be an ISO calendar date")

        now_dt = datetime.now(timezone.utc)
        quote_time = _utc_datetime(quote_verified_at, "quote_verified_at")
        quote_age = (now_dt - quote_time).total_seconds()
        if quote_age < -60 or quote_age > MAX_QUOTE_AGE_SECONDS:
            raise ValueError("The verified quote is stale or from the future")
        if any(not candidate_is_credible(leg.candidate) for leg in ticket.legs):
            raise ValueError("Ticket contains an unverified candidate")

        try:
            leg_odds = [validate_decimal_odds(leg.odds) for leg in ticket.legs]
        except BettingMathError as exc:
            raise ValueError("Ticket contains invalid decimal odds") from exc
        derived_total_odds = math.prod(leg_odds)
        dependency_factor = CROSS_LEG_MODEL_FACTOR ** max(0, len(ticket.legs) - 1)
        derived_joint_probability = (
            math.prod(leg.candidate.conservative_probability for leg in ticket.legs)
            * dependency_factor
        )
        derived_expected_roi = derived_joint_probability * derived_total_odds - 1.0
        derived_leg_rois = [
            leg.candidate.conservative_probability * odds - 1.0
            for leg, odds in zip(ticket.legs, leg_odds)
        ]
        if any(value < 0.02 for value in derived_leg_rois):
            raise ValueError("Every ticket leg must clear the value gate")
        try:
            leg_roi_consistent = all(
                math.isclose(float(leg.expected_roi), value, abs_tol=5e-7)
                for leg, value in zip(ticket.legs, derived_leg_rois)
            )
        except (TypeError, ValueError):
            leg_roi_consistent = False
        if not leg_roi_consistent:
            raise ValueError("Ticket leg ROI does not match its probability and odds")
        try:
            derived_metrics = evaluate_market_price(
                derived_joint_probability * 100.0,
                derived_total_odds,
                probability_haircut=0.0,
                kelly_fraction=0.25,
                kelly_cap=MAX_STAKE_FRACTION,
            )
        except BettingMathError as exc:
            raise ValueError("Ticket mathematics are invalid") from exc
        try:
            ticket_fields = (
                ticket.total_odds,
                ticket.joint_probability,
                ticket.expected_roi,
                ticket.model_dependency_factor,
                ticket.stake_fraction,
            )
            if any(isinstance(value, bool) for value in ticket_fields):
                raise ValueError
            consistency_checks = (
                math.isclose(float(ticket.total_odds), derived_total_odds, abs_tol=5e-5),
                math.isclose(
                    float(ticket.joint_probability),
                    derived_joint_probability,
                    abs_tol=5e-7,
                ),
                math.isclose(
                    float(ticket.expected_roi),
                    derived_expected_roi,
                    abs_tol=5e-7,
                ),
                math.isclose(
                    float(ticket.model_dependency_factor),
                    dependency_factor,
                    abs_tol=5e-7,
                ),
                math.isclose(
                    float(ticket.stake_fraction),
                    derived_metrics.kelly_fraction,
                    abs_tol=5e-7,
                ),
            )
        except (TypeError, ValueError, OverflowError):
            consistency_checks = (False,)
        if not all(consistency_checks):
            raise ValueError("Ticket fields do not match the underlying legs")
        if not TARGET_ODDS_MIN <= derived_total_odds <= TARGET_ODDS_MAX:
            raise ValueError("Ticket odds are outside the challenge corridor")
        if derived_expected_roi < 0.03:
            raise ValueError("Ticket expected ROI is below the challenge gate")

        fixture_ids = [leg.candidate.fixture_id for leg in ticket.legs]
        if len(set(fixture_ids)) != len(fixture_ids):
            raise ValueError("Ticket legs must use different fixtures")
        team_ids = [
            team_id
            for leg in ticket.legs
            for team_id in (
                leg.candidate.home_team_id,
                leg.candidate.away_team_id,
            )
        ]
        if len(set(team_ids)) != len(team_ids):
            raise ValueError("Ticket legs must not reuse a team")
        if any(
            _utc_datetime(leg.candidate.kickoff, "kickoff") <= now_dt
            for leg in ticket.legs
        ):
            raise ValueError("Every ticket leg must still be pre-match")

        legs_json = json.dumps(self._ticket_legs(ticket), ensure_ascii=False, separators=(",", ":"))
        now = now_dt.isoformat()

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT current_balance_cents FROM challenge_settings WHERE id = 1"
                ).fetchone()
                if row is None or stake_cents > row[0]:
                    raise ValueError("Stake exceeds the available balance")
                allowed_fraction = min(
                    MAX_STAKE_FRACTION,
                    derived_metrics.kelly_fraction,
                )
                max_stake_cents = int(
                    (Decimal(row[0]) * Decimal(str(allowed_fraction))).quantize(
                        Decimal("1"),
                        rounding=ROUND_HALF_UP,
                    )
                )
                if stake_cents > max_stake_cents:
                    raise ValueError("Stake exceeds the ticket's Kelly cap")
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
        ticket_id = _positive_integer(ticket_id, "ticket_id")
        normalized = str(status).upper()
        if normalized not in {"WON", "LOST", "VOID"}:
            raise ValueError("Settlement status must be WON, LOST, or VOID")
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status, stake_cents, total_odds FROM challenge_tickets WHERE id = ?",
                (ticket_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ValueError("Ticket does not exist")
            if row["status"] != "PENDING":
                connection.rollback()
                raise ValueError("Ticket has already been settled")

            if normalized == "WON":
                payout_cents = int(
                    (
                        Decimal(row["stake_cents"])
                        * Decimal(str(row["total_odds"]))
                    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
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
                (normalized, payout_cents, now, ticket_id),
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
        ticket_id = _positive_integer(ticket_id, "ticket_id")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM challenge_tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Ticket does not exist")
        return self._row_to_ticket(row)

    def tickets(self, limit: int = 100) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM challenge_tickets ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def pending_tickets(self) -> list[dict[str, Any]]:
        return [ticket for ticket in self.tickets() if ticket["status"] == "PENDING"]


__all__ = ["ChallengeLedger", "DEFAULT_CHALLENGE_DB"]
