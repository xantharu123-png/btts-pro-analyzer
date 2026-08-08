"""Persistent cent-accurate bankroll ledger for the 15K challenge."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import math
from pathlib import Path
import sqlite3
from typing import Any

from challenge_engine import (
    DEFAULT_CHALLENGE_STAKE_FRACTION,
    KELLY_REFERENCE_CAP,
    MARKET_BY_KEY,
    MAX_CHALLENGE_STAKE_FRACTION,
    MIN_CHALLENGE_STAKE_FRACTION,
    MIN_LEG_EXPECTED_ROI,
    QuotedTicket,
    TARGET_BALANCE,
    TARGET_ODDS_MAX,
    TARGET_ODDS_MIN,
    candidate_is_credible,
    dependence_floor_probability,
    ticket_dependency_factor,
)
from betting_math import BettingMathError, evaluate_market_price, validate_decimal_odds
from price_ledger import (
    BOOKMAKER,
    PriceLedger,
    PriceLedgerError,
    PriceLedgerIntegrityError,
    PriceQuote,
)
from market_consensus import (
    MIN_REFERENCE_BOOKMAKERS,
    REFERENCE_FETCH_MAX_AGE,
    REFERENCE_QUOTE_MAX_AGE,
    REFERENCE_SOURCE,
)


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
                    stake_fraction_bps INTEGER NOT NULL DEFAULT 2500
                        CHECK (stake_fraction_bps BETWEEN 500 AND 2500),
                    updated_at TEXT NOT NULL
                )
                """
            )
            setting_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(challenge_settings)")
            }
            if "stake_fraction_bps" not in setting_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_settings
                    ADD COLUMN stake_fraction_bps INTEGER NOT NULL DEFAULT 2500
                        CHECK (stake_fraction_bps BETWEEN 500 AND 10000)
                    """
                )
            connection.execute(
                """
                UPDATE challenge_settings
                SET stake_fraction_bps=?
                WHERE stake_fraction_bps>?
                """,
                (
                    int(MAX_CHALLENGE_STAKE_FRACTION * 10_000),
                    int(MAX_CHALLENGE_STAKE_FRACTION * 10_000),
                ),
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
                    played_odds REAL CHECK (played_odds IS NULL OR played_odds > 1),
                    joint_probability REAL NOT NULL CHECK (joint_probability >= 0 AND joint_probability <= 1),
                    expected_roi REAL NOT NULL,
                    legs_json TEXT NOT NULL,
                    entry_source TEXT NOT NULL DEFAULT 'MODEL'
                )
                """
            )
            ticket_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(challenge_tickets)")
            }
            if "played_odds" not in ticket_columns:
                connection.execute(
                    "ALTER TABLE challenge_tickets ADD COLUMN played_odds REAL"
                )
            if "entry_source" not in ticket_columns:
                connection.execute(
                    """
                    ALTER TABLE challenge_tickets
                    ADD COLUMN entry_source TEXT NOT NULL DEFAULT 'MODEL'
                    """
                )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_challenge_daily_ticket
                ON challenge_tickets(analysis_date)
                WHERE status != 'VOID'
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    balance_after_cents INTEGER NOT NULL
                        CHECK (balance_after_cents >= 0),
                    ticket_id INTEGER,
                    note TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES challenge_tickets(id)
                )
                """
            )
            now = datetime.now(timezone.utc).isoformat()
            default_cents = _money_to_cents(100.0)
            target_cents = _money_to_cents(TARGET_BALANCE, allow_zero=False)
            connection.execute(
                """
                INSERT OR IGNORE INTO challenge_settings (
                    id, starting_balance_cents, current_balance_cents,
                    target_balance_cents, stake_fraction_bps, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?)
                """,
                (
                    default_cents,
                    default_cents,
                    target_cents,
                    int(DEFAULT_CHALLENGE_STAKE_FRACTION * 10_000),
                    now,
                ),
            )
            transaction_count = connection.execute(
                "SELECT COUNT(*) FROM challenge_transactions"
            ).fetchone()[0]
            if transaction_count == 0:
                settings_row = connection.execute(
                    """
                    SELECT current_balance_cents
                    FROM challenge_settings WHERE id = 1
                    """
                ).fetchone()
                ticket_count = connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets"
                ).fetchone()[0]
                current_cents = int(settings_row["current_balance_cents"])
                if ticket_count:
                    kind = "MIGRATION_SNAPSHOT"
                    amount_cents = 0
                    note = "Legacy balance captured during ledger migration"
                else:
                    kind = "OPENING_BALANCE"
                    amount_cents = current_cents
                    note = "Challenge opening balance"
                connection.execute(
                    """
                    INSERT INTO challenge_transactions (
                        created_at, kind, amount_cents,
                        balance_after_cents, note
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (now, kind, amount_cents, current_cents, note),
                )
            connection.commit()
        PriceLedger(self.db_path)

    def settings(self) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM challenge_settings WHERE id = 1"
            ).fetchone()
            external_funding_cents = connection.execute(
                """
                SELECT COALESCE(SUM(amount_cents), 0)
                FROM challenge_transactions
                WHERE kind IN (
                    'OPENING_BALANCE',
                    'BALANCE_ADJUSTMENT',
                    'CHALLENGE_RESET'
                )
                """
            ).fetchone()[0]
        if row is None:
            raise RuntimeError("Challenge settings are missing")
        return {
            "starting_balance": _cents_to_money(row["starting_balance_cents"]),
            "current_balance": _cents_to_money(row["current_balance_cents"]),
            "target_balance": _cents_to_money(row["target_balance_cents"]),
            "stake_fraction": row["stake_fraction_bps"] / 10_000.0,
            "net_external_funding": _cents_to_money(external_funding_cents),
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _record_transaction(
        connection: sqlite3.Connection,
        *,
        created_at: str,
        kind: str,
        amount_cents: int,
        balance_after_cents: int,
        ticket_id: int | None = None,
        note: str | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO challenge_transactions (
                created_at, kind, amount_cents, balance_after_cents,
                ticket_id, note
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                str(kind),
                int(amount_cents),
                int(balance_after_cents),
                ticket_id,
                note,
            ),
        )

    def set_balance(self, balance: Any, *, reset_start: bool = False) -> dict[str, Any]:
        cents = _money_to_cents(balance)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            pending = connection.execute(
                "SELECT COUNT(*) FROM challenge_tickets WHERE status = 'PENDING'"
            ).fetchone()[0]
            if pending:
                connection.rollback()
                raise ValueError("Open tickets must be settled before correcting the balance")
            current_row = connection.execute(
                """
                SELECT current_balance_cents
                FROM challenge_settings WHERE id = 1
                """
            ).fetchone()
            if current_row is None:
                connection.rollback()
                raise RuntimeError("Challenge settings are missing")
            previous_cents = int(current_row["current_balance_cents"])
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
            self._record_transaction(
                connection,
                created_at=now,
                kind="CHALLENGE_RESET" if reset_start else "BALANCE_ADJUSTMENT",
                amount_cents=cents - previous_cents,
                balance_after_cents=cents,
                note=(
                    "Explicit challenge restart"
                    if reset_start
                    else "Manual balance correction"
                ),
            )
            connection.commit()
        return self.settings()

    def set_stake_fraction(self, stake_fraction: Any) -> dict[str, Any]:
        if isinstance(stake_fraction, bool):
            raise ValueError("Stake fraction must be numeric")
        try:
            fraction = Decimal(str(stake_fraction))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Stake fraction must be numeric") from exc
        if (
            not fraction.is_finite()
            or fraction < Decimal(str(MIN_CHALLENGE_STAKE_FRACTION))
            or fraction > Decimal(str(MAX_CHALLENGE_STAKE_FRACTION))
        ):
            raise ValueError("Stake fraction must be between 5% and 25%")
        basis_points = int(
            (fraction * Decimal("10000")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE challenge_settings
                SET stake_fraction_bps = ?, updated_at = ?
                WHERE id = 1
                """,
                (basis_points, now),
            )
            connection.commit()
        return self.settings()

    @staticmethod
    def _ticket_legs(
        ticket: QuotedTicket,
        quote_observation_ids: list[int | None],
    ) -> list[dict[str, Any]]:
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
                "quote_observation_id": quote_observation_ids[index],
                "quote_source": leg.quote_source,
                "quoted_at": leg.quoted_at,
                "fetched_at": leg.fetched_at,
                "bookmaker_count": leg.bookmaker_count,
                "reference_odds": leg.quote_low,
                "best_observed_odds": leg.quote_high,
            }
            for index, leg in enumerate(ticket.legs)
        ]

    def _verified_quote_observation_ids(
        self,
        ticket: QuotedTicket,
        *,
        quote_time: datetime,
        now: datetime,
    ) -> list[int | None]:
        has_n1_price = any(leg.quote_source == BOOKMAKER for leg in ticket.legs)
        ledger = PriceLedger(self.db_path) if has_n1_price else None
        if ledger is not None:
            chain_valid, bad_id = ledger.verify_chain()
            if not chain_valid:
                raise PriceLedgerIntegrityError(
                    f"price hash chain is invalid at observation {bad_id}"
                )
        observation_ids: list[int | None] = []
        for leg in ticket.legs:
            candidate = leg.candidate
            if leg.quote_source != BOOKMAKER:
                if (
                    leg.quote_source != REFERENCE_SOURCE
                    or leg.quote_observation_id is not None
                    or leg.bookmaker_count < MIN_REFERENCE_BOOKMAKERS
                    or leg.quoted_at is None
                    or leg.fetched_at is None
                    or leg.quote_low is None
                    or leg.quote_high is None
                    or leg.quote_low > leg.quote_high
                    or not math.isclose(
                        leg.odds,
                        leg.quote_low,
                        rel_tol=0.0,
                        abs_tol=5e-7,
                    )
                ):
                    raise ValueError("Ticket reference price evidence is invalid")
                reference_time = _utc_datetime(leg.quoted_at, "quoted_at")
                fetched_time = _utc_datetime(leg.fetched_at, "fetched_at")
                reference_age = now - reference_time
                fetch_age = now - fetched_time
                if (
                    reference_age.total_seconds() < -60
                    or reference_age > REFERENCE_QUOTE_MAX_AGE
                    or fetch_age.total_seconds() < -60
                    or fetch_age > REFERENCE_FETCH_MAX_AGE
                ):
                    raise ValueError("Ticket reference price is stale or from the future")
                observation_ids.append(None)
                continue
            if ledger is None:
                raise ValueError("N1Bet price ledger is unavailable")
            observation_id = leg.quote_observation_id
            if observation_id is None:
                spec = MARKET_BY_KEY.get(candidate.market_key)
                observation = ledger.append(
                    PriceQuote(
                        sport="FOOTBALL",
                        event_id=str(candidate.fixture_id),
                        event_name=(
                            f"{candidate.home_team} vs {candidate.away_team}"
                        ),
                        scheduled_start=candidate.kickoff,
                        market_key=candidate.market_key,
                        market_name=candidate.market,
                        selection_key=candidate.candidate_id,
                        selection_name=candidate.selection,
                        decimal_odds=leg.odds,
                        phase="ENTRY",
                        source="MANUAL",
                        captured_at=quote_time,
                        line=spec.threshold if spec is not None else None,
                        model_ref="challenge-engine-v5",
                        metadata={
                            "candidate_id": candidate.candidate_id,
                            "league_id": candidate.league_id,
                        },
                    ),
                    now=now,
                )
                observation_id = observation.id
            observation = ledger.get(observation_id)
            expected_start = _utc_datetime(candidate.kickoff, "kickoff")
            observed_start = _utc_datetime(
                observation.scheduled_start,
                "scheduled_start",
            )
            observed_capture = _utc_datetime(
                observation.captured_at,
                "captured_at",
            )
            if (
                observation.bookmaker != BOOKMAKER
                or observation.sport != "FOOTBALL"
                or observation.event_id != str(candidate.fixture_id)
                or observation.event_name
                != f"{candidate.home_team} vs {candidate.away_team}"
                or observation.market_key != candidate.market_key
                or observation.selection_key != candidate.candidate_id
                or observation.phase != "ENTRY"
                or not math.isclose(
                    observation.decimal_odds,
                    leg.odds,
                    rel_tol=0.0,
                    abs_tol=5e-7,
                )
                or observed_start != expected_start
                or abs((observed_capture - quote_time).total_seconds()) > 1.0
            ):
                raise ValueError(
                    "Ticket price does not match its append-only N1Bet observation"
                )
            observation_ids.append(observation_id)
        return observation_ids

    def place_ticket(
        self,
        analysis_date: str,
        ticket: QuotedTicket,
        stake: Any,
        quote_verified_at: str,
        *,
        played_odds: Any | None = None,
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
        quote_age_limit = (
            int(REFERENCE_FETCH_MAX_AGE.total_seconds())
            if any(leg.quote_source == REFERENCE_SOURCE for leg in ticket.legs)
            else MAX_QUOTE_AGE_SECONDS
        )
        if quote_age < -60 or quote_age > quote_age_limit:
            raise ValueError("The verified quote is stale or from the future")
        if any(not candidate_is_credible(leg.candidate) for leg in ticket.legs):
            raise ValueError("Ticket contains an unverified candidate")

        try:
            leg_odds = [validate_decimal_odds(leg.odds) for leg in ticket.legs]
        except BettingMathError as exc:
            raise ValueError("Ticket contains invalid decimal odds") from exc
        derived_total_odds = math.prod(leg_odds)
        dependency_factor = ticket_dependency_factor(
            leg.candidate for leg in ticket.legs
        )
        derived_joint_probability = (
            math.prod(leg.candidate.conservative_probability for leg in ticket.legs)
            * dependency_factor
        )
        derived_dependence_floor = dependence_floor_probability(
            leg.candidate for leg in ticket.legs
        )
        derived_expected_roi = derived_joint_probability * derived_total_odds - 1.0
        derived_leg_rois = [
            leg.candidate.conservative_probability * odds - 1.0
            for leg, odds in zip(ticket.legs, leg_odds)
        ]
        if any(value < MIN_LEG_EXPECTED_ROI for value in derived_leg_rois):
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
                kelly_cap=KELLY_REFERENCE_CAP,
            )
        except BettingMathError as exc:
            raise ValueError("Ticket mathematics are invalid") from exc
        try:
            ticket_fields = (
                ticket.total_odds,
                ticket.joint_probability,
                ticket.expected_roi,
                ticket.model_dependency_factor,
                ticket.dependence_floor_probability,
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
                    float(ticket.dependence_floor_probability),
                    derived_dependence_floor,
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
        if derived_expected_roi < MIN_LEG_EXPECTED_ROI:
            raise ValueError("Ticket expected ROI is below the challenge gate")

        try:
            actual_total_odds = validate_decimal_odds(
                derived_total_odds if played_odds is None else played_odds
            )
        except BettingMathError as exc:
            raise ValueError("The played ticket odds are invalid") from exc
        actual_expected_roi = derived_joint_probability * actual_total_odds - 1.0
        if not TARGET_ODDS_MIN <= actual_total_odds <= TARGET_ODDS_MAX:
            raise ValueError("The played ticket odds are outside the challenge corridor")
        if actual_expected_roi < MIN_LEG_EXPECTED_ROI:
            raise ValueError("The played ticket odds do not clear the value gate")

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

        try:
            quote_observation_ids = self._verified_quote_observation_ids(
                ticket,
                quote_time=quote_time,
                now=now_dt,
            )
        except (PriceLedgerError, PriceLedgerIntegrityError) as exc:
            raise ValueError(str(exc)) from exc
        legs_json = json.dumps(
            self._ticket_legs(ticket, quote_observation_ids),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        now = now_dt.isoformat()

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                pending_count = connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets WHERE status = 'PENDING'"
                ).fetchone()[0]
                if pending_count:
                    # Challenge sizing assumes sequential roll-over tickets;
                    # concurrent tickets would silently stack bankroll exposure.
                    raise ValueError(
                        "An open ticket must be settled before a new ticket can be placed"
                    )
                row = connection.execute(
                    """
                    SELECT current_balance_cents, stake_fraction_bps
                    FROM challenge_settings WHERE id = 1
                    """
                ).fetchone()
                if row is None or stake_cents > row[0]:
                    raise ValueError("Stake exceeds the available balance")
                max_stake_cents = row[0] * row[1] // 10_000
                if stake_cents > max_stake_cents:
                    raise ValueError("Stake exceeds the configured challenge limit")
                cursor = connection.execute(
                    """
                    INSERT INTO challenge_tickets (
                        analysis_date, created_at, quote_verified_at, status,
                        stake_cents, total_odds, played_odds, joint_probability,
                        expected_roi, legs_json, entry_source
                    ) VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, 'MODEL')
                    """,
                    (
                        analysis_date,
                        now,
                        quote_verified_at,
                        stake_cents,
                        ticket.total_odds,
                        actual_total_odds,
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
                balance_after_cents = int(row[0]) - stake_cents
                self._record_transaction(
                    connection,
                    created_at=now,
                    kind="STAKE",
                    amount_cents=-stake_cents,
                    balance_after_cents=balance_after_cents,
                    ticket_id=int(cursor.lastrowid),
                    note=f"Ticket #{int(cursor.lastrowid)} placed",
                )
                connection.commit()
                return int(cursor.lastrowid)
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("For this date, a challenge ticket already exists") from exc
            except Exception:
                connection.rollback()
                raise

    def record_manual_result(
        self,
        analysis_date: str,
        description: str,
        stake: Any,
        total_odds: Any,
        status: str,
    ) -> int:
        """Record a real past bet that was not saved before kickoff."""
        stake_cents = _money_to_cents(stake, allow_zero=False)
        normalized = str(status).upper()
        if normalized not in {"WON", "LOST", "VOID"}:
            raise ValueError("Settlement status must be WON, LOST, or VOID")
        label = str(description or "").strip()
        if not label or len(label) > 300:
            raise ValueError("Description must contain 1 to 300 characters")
        try:
            analysis_day = datetime.fromisoformat(str(analysis_date)).date()
        except (TypeError, ValueError) as exc:
            raise ValueError("analysis_date must be an ISO calendar date") from exc
        if str(analysis_day) != str(analysis_date):
            raise ValueError("analysis_date must be an ISO calendar date")
        if analysis_day > datetime.now(timezone.utc).date() + timedelta(days=1):
            raise ValueError("A settled ticket cannot be recorded for a future date")
        try:
            actual_total_odds = validate_decimal_odds(total_odds)
        except BettingMathError as exc:
            raise ValueError("The played ticket odds are invalid") from exc

        if normalized == "WON":
            payout_cents = int(
                (
                    Decimal(stake_cents) * Decimal(str(actual_total_odds))
                ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        elif normalized == "VOID":
            payout_cents = stake_cents
        else:
            payout_cents = 0

        now = datetime.now(timezone.utc).isoformat()
        legs_json = json.dumps(
            [{"manual": True, "label": label}],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                pending_count = connection.execute(
                    "SELECT COUNT(*) FROM challenge_tickets WHERE status = 'PENDING'"
                ).fetchone()[0]
                if pending_count:
                    raise ValueError(
                        "An open ticket must be settled before a past ticket can be recorded"
                    )
                row = connection.execute(
                    """
                    SELECT current_balance_cents, stake_fraction_bps
                    FROM challenge_settings WHERE id = 1
                    """
                ).fetchone()
                if row is None or stake_cents > row["current_balance_cents"]:
                    raise ValueError("Stake exceeds the available balance")
                max_stake_cents = (
                    int(row["current_balance_cents"])
                    * int(row["stake_fraction_bps"])
                    // 10_000
                )
                if stake_cents > max_stake_cents:
                    raise ValueError("Stake exceeds the configured challenge limit")

                cursor = connection.execute(
                    """
                    INSERT INTO challenge_tickets (
                        analysis_date, created_at, quote_verified_at, settled_at,
                        status, stake_cents, payout_cents, total_odds,
                        played_odds, joint_probability, expected_roi, legs_json,
                        entry_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, 'MANUAL')
                    """,
                    (
                        analysis_date,
                        now,
                        now,
                        now,
                        normalized,
                        stake_cents,
                        payout_cents,
                        actual_total_odds,
                        actual_total_odds,
                        legs_json,
                    ),
                )
                ticket_id = int(cursor.lastrowid)
                balance_after_stake = int(row["current_balance_cents"]) - stake_cents
                self._record_transaction(
                    connection,
                    created_at=now,
                    kind="STAKE",
                    amount_cents=-stake_cents,
                    balance_after_cents=balance_after_stake,
                    ticket_id=ticket_id,
                    note=f"Manual ticket #{ticket_id} recorded",
                )
                final_balance = balance_after_stake + payout_cents
                self._record_transaction(
                    connection,
                    created_at=now,
                    kind={
                        "WON": "PAYOUT",
                        "LOST": "LOSS_SETTLED",
                        "VOID": "VOID_REFUND",
                    }[normalized],
                    amount_cents=payout_cents,
                    balance_after_cents=final_balance,
                    ticket_id=ticket_id,
                    note=f"Manual ticket #{ticket_id} settled {normalized}",
                )
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (final_balance, now),
                )
                connection.commit()
                return ticket_id
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError(
                    "For this date, a challenge ticket already exists"
                ) from exc
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
                """
                SELECT status, stake_cents, total_odds, played_odds
                FROM challenge_tickets WHERE id = ?
                """,
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
                        * Decimal(str(row["played_odds"] or row["total_odds"]))
                    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                )
            elif normalized == "VOID":
                payout_cents = int(row["stake_cents"])
            else:
                payout_cents = 0
            settings_row = connection.execute(
                """
                SELECT current_balance_cents
                FROM challenge_settings WHERE id = 1
                """
            ).fetchone()
            if settings_row is None:
                connection.rollback()
                raise RuntimeError("Challenge settings are missing")
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
            balance_after_cents = (
                int(settings_row["current_balance_cents"]) + payout_cents
            )
            transaction_kind = {
                "WON": "PAYOUT",
                "LOST": "LOSS_SETTLED",
                "VOID": "VOID_REFUND",
            }[normalized]
            self._record_transaction(
                connection,
                created_at=now,
                kind=transaction_kind,
                amount_cents=payout_cents,
                balance_after_cents=balance_after_cents,
                ticket_id=ticket_id,
                note=f"Ticket #{ticket_id} settled {normalized}",
            )
            connection.commit()
        return self.get_ticket(ticket_id)

    @staticmethod
    def _row_to_ticket(row: sqlite3.Row) -> dict[str, Any]:
        reference_odds = float(row["total_odds"])
        played_odds = float(row["played_odds"] or reference_odds)
        return {
            "id": row["id"],
            "analysis_date": row["analysis_date"],
            "created_at": row["created_at"],
            "quote_verified_at": row["quote_verified_at"],
            "settled_at": row["settled_at"],
            "status": row["status"],
            "stake": _cents_to_money(row["stake_cents"]),
            "payout": _cents_to_money(row["payout_cents"]),
            "total_odds": played_odds,
            "reference_total_odds": reference_odds,
            "joint_probability": float(row["joint_probability"]),
            "expected_roi": float(row["expected_roi"]),
            "legs": json.loads(row["legs_json"]),
            "entry_source": row["entry_source"],
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

    def transactions(self, limit: int = 500) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM challenge_transactions
                ORDER BY id ASC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "kind": row["kind"],
                "amount": _cents_to_money(row["amount_cents"]),
                "balance_after": _cents_to_money(row["balance_after_cents"]),
                "ticket_id": row["ticket_id"],
                "note": row["note"],
            }
            for row in rows
        ]


__all__ = ["ChallengeLedger", "DEFAULT_CHALLENGE_DB"]
