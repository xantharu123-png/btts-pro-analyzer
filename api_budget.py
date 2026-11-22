"""Process-wide API-Football quota protection with workload priorities."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Optional
from urllib.parse import urlparse

import requests


DEFAULT_DAILY_LIMIT = 7_500
DEFAULT_CRITICAL_FLOOR = 50
DEFAULT_RECOMMENDATION_RESERVE = 750
DEFAULT_BACKGROUND_RESERVE = 2_500
LIVE_TICKER_DAILY_CAP = 500
LIVE_TICKER_PREFIX = "live-ticker:"
FOOTBALL_ROLLOVER_STATUS_LABEL = "account rollover check"
_FOOTBALL_STATUS_URL = "https://v3.football.api-sports.io/status"
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "runtime_state" / "api_budget.db"


class APIBudgetPriority(str, Enum):
    """Quota classes in descending operational importance."""

    CRITICAL = "critical"
    RECOMMENDATION = "recommendation"
    BACKGROUND = "background"


class APIBudgetError(RuntimeError):
    """Base class for quota-governor failures."""


class APIBudgetExceeded(APIBudgetError):
    """Raised before a request that would consume protected quota."""

    def __init__(self, message: str, *, reason: str = "unknown"):
        super().__init__(message)
        self.reason = reason


class APIBudgetUnavailable(APIBudgetError):
    """Raised when the shared quota ledger cannot be used safely."""


@dataclass(frozen=True)
class APIBudgetReservation:
    event_id: int
    provider: str
    account_hash: str
    quota_day: str
    priority: APIBudgetPriority
    endpoint: str
    remaining_before: int
    remaining_after: int


@dataclass(frozen=True)
class APIBudgetSnapshot:
    quota_day: str
    daily_limit: int
    remaining_estimate: int
    observed_remaining: Optional[int]
    critical_floor: int
    recommendation_reserve: int
    background_reserve: int


_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_budget_state (
    provider TEXT NOT NULL,
    account_hash TEXT NOT NULL,
    quota_day TEXT NOT NULL,
    daily_limit INTEGER NOT NULL CHECK (daily_limit > 0),
    remaining_estimate INTEGER NOT NULL CHECK (remaining_estimate >= 0),
    observed_remaining INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (provider, account_hash, quota_day)
);

CREATE TABLE IF NOT EXISTS api_budget_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    account_hash TEXT NOT NULL,
    quota_day TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    priority TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    decision TEXT NOT NULL,
    remaining_before INTEGER NOT NULL,
    remaining_after INTEGER NOT NULL,
    provider_remaining INTEGER,
    http_status INTEGER,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_api_budget_events_day
ON api_budget_events(provider, account_hash, quota_day, id);
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _positive_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise APIBudgetUnavailable(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise APIBudgetUnavailable(f"{name} must be a positive integer")
    return value


def _priority(value: APIBudgetPriority | str) -> APIBudgetPriority:
    if isinstance(value, APIBudgetPriority):
        return value
    try:
        return APIBudgetPriority(str(value).strip().lower())
    except ValueError as exc:
        raise ValueError(f"Unknown API budget priority: {value!r}") from exc


def _header_int(headers: Any, name: str) -> Optional[int]:
    if not isinstance(headers, Mapping):
        return None
    raw = headers.get(name)
    if raw is None:
        raw = headers.get(name.lower())
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _account_hash(api_key: str) -> str:
    value = str(api_key or "").strip()
    if not value:
        raise APIBudgetUnavailable("API-Football key is missing")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


class APIBudgetGovernor:
    """Reserve API calls atomically across Streamlit and systemd processes."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        *,
        daily_limit: Optional[int] = None,
        critical_floor: Optional[int] = None,
        recommendation_reserve: Optional[int] = None,
        background_reserve: Optional[int] = None,
        quota_period: str = "day",
    ):
        self.db_path = Path(db_path)
        if quota_period not in {"day", "month"}:
            raise APIBudgetUnavailable("Unknown quota period")
        self.quota_period = quota_period
        self.daily_limit = daily_limit or _positive_env_int(
            "BETBOY_API_DAILY_LIMIT",
            DEFAULT_DAILY_LIMIT,
        )
        self.critical_floor = critical_floor or _positive_env_int(
            "BETBOY_API_CRITICAL_FLOOR",
            DEFAULT_CRITICAL_FLOOR,
        )
        self.recommendation_reserve = recommendation_reserve or _positive_env_int(
            "BETBOY_API_RECOMMENDATION_RESERVE",
            DEFAULT_RECOMMENDATION_RESERVE,
        )
        self.background_reserve = background_reserve or _positive_env_int(
            "BETBOY_API_BACKGROUND_RESERVE",
            DEFAULT_BACKGROUND_RESERVE,
        )
        if not (
            0
            < self.critical_floor
            < self.recommendation_reserve
            < self.background_reserve
            < self.daily_limit
        ):
            raise APIBudgetUnavailable(
                "API budget floors must be ordered below the daily limit"
            )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection:
                journal_mode = connection.execute(
                    "PRAGMA journal_mode = WAL"
                ).fetchone()
                if (
                    journal_mode is None
                    or len(journal_mode) != 1
                    or str(journal_mode[0]).casefold() != "wal"
                ):
                    raise sqlite3.OperationalError(
                        "API budget database requires WAL journal mode"
                    )
                connection.executescript(_SCHEMA)
        except (OSError, sqlite3.Error) as exc:
            raise APIBudgetUnavailable(
                f"Shared API budget ledger is unavailable: {type(exc).__name__}"
            ) from exc

    def _floor(self, priority: APIBudgetPriority) -> int:
        return {
            APIBudgetPriority.CRITICAL: self.critical_floor,
            APIBudgetPriority.RECOMMENDATION: self.recommendation_reserve,
            APIBudgetPriority.BACKGROUND: self.background_reserve,
        }[priority]

    def _quota_day(self, current: datetime) -> str:
        """Existing ledger key: the first UTC day of the configured period."""
        day = current.astimezone(timezone.utc).date()
        return (day.replace(day=1) if self.quota_period == "month" else day).isoformat()

    def recent_request_count(
        self,
        *,
        api_key: str,
        provider: str,
        seconds: float,
        now: Optional[datetime] = None,
    ) -> int:
        """Requests of one provider and account started within the last ``seconds`` (owner 18.11.2026).

        Read only, across every process that shares the ledger. A blocked reservation was never sent and does
        not count. Callers use it to stay below a provider's limit per minute, which the daily quota cannot see.
        """
        account = _account_hash(api_key)
        current = (now or _utc_now()).astimezone(timezone.utc)
        since = current - timedelta(seconds=seconds)
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT COUNT(*) FROM api_budget_events WHERE provider = ? AND account_hash = ? "
                    "AND started_at >= ? AND started_at <= ? AND decision != 'BLOCKED'",
                    (provider, account, since.isoformat(), current.isoformat()),
                ).fetchone()
        except sqlite3.Error as exc:
            raise APIBudgetUnavailable(
                f"Shared API budget ledger is unavailable: {type(exc).__name__}"
            ) from exc
        return int(row[0]) if row else 0

    def reserve(
        self,
        *,
        api_key: str,
        endpoint: str,
        priority: APIBudgetPriority | str,
        provider: str = "api-football",
        now: Optional[datetime] = None,
        cost: int = 1,
    ) -> APIBudgetReservation:
        if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
            raise APIBudgetUnavailable("Request cost must be a positive integer")
        live_ticker = endpoint.startswith(LIVE_TICKER_PREFIX)
        selected_priority = APIBudgetPriority.BACKGROUND if live_ticker else _priority(priority)
        account = _account_hash(api_key)
        current = (now or _utc_now()).astimezone(timezone.utc)
        day = self._quota_day(current)
        started_at = current.isoformat()
        floor = self._floor(selected_priority)

        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT daily_limit, remaining_estimate, observed_remaining
                    FROM api_budget_state
                    WHERE provider=? AND account_hash=? AND quota_day=?
                    """,
                    (provider, account, day),
                ).fetchone()
                if row is None:
                    remaining = self.daily_limit
                    connection.execute(
                        """
                        INSERT INTO api_budget_state (
                            provider, account_hash, quota_day, daily_limit,
                            remaining_estimate, observed_remaining, updated_at
                        ) VALUES (?, ?, ?, ?, ?, NULL, ?)
                        """,
                        (
                            provider,
                            account,
                            day,
                            self.daily_limit,
                            remaining,
                            started_at,
                        ),
                    )
                else:
                    remaining = min(
                        int(row["remaining_estimate"]),
                        int(row["daily_limit"]),
                    )

                if endpoint == FOOTBALL_ROLLOVER_STATUS_LABEL:
                    # The ordinary Shadow run checks cheaply before calling; repeat
                    # admission under the write lock shared by every worker.
                    if provider != "api-football" or self.quota_period != "day":
                        raise APIBudgetExceeded("Kein Fußball-Tageskonto.", reason="not_needed")
                    prior_check = connection.execute(
                        "SELECT 1 FROM api_budget_events WHERE provider=? AND account_hash=? "
                        "AND quota_day=? AND endpoint=? AND decision!='BLOCKED' LIMIT 1",
                        (provider, account, day, endpoint),
                    ).fetchone()
                    if prior_check:
                        raise APIBudgetExceeded("Kontostand heute bereits geprüft.", reason="already_checked")
                    if (row is None or row["observed_remaining"] is None or
                            not remaining <= self.background_reserve < row["observed_remaining"]):
                        raise APIBudgetExceeded("Kein widersprüchlicher Kontostand.", reason="not_needed")

                blocked_reason = None
                if remaining - cost < floor:
                    blocked_reason = f"protected floor {floor}"
                elif live_ticker:
                    # Count spent and in-flight units together, under the same write lock as
                    # this reservation. A failed request costs quota; a refused one does not.
                    spent = connection.execute(
                        "SELECT COALESCE(SUM(remaining_before - remaining_after), 0) "
                        "FROM api_budget_events WHERE provider=? AND account_hash=? AND quota_day=? "
                        "AND started_at >= ? AND started_at < ? AND endpoint GLOB ? AND decision != 'BLOCKED'",
                        (provider, account, day, current.date().isoformat(),
                         (current + timedelta(days=1)).date().isoformat(), LIVE_TICKER_PREFIX + "*"),
                    ).fetchone()[0]
                    if spent + cost > LIVE_TICKER_DAILY_CAP:
                        blocked_reason = f"live ticker daily cap {LIVE_TICKER_DAILY_CAP}"

                if blocked_reason:
                    connection.execute(
                        """
                        INSERT INTO api_budget_events (
                            provider, account_hash, quota_day, started_at,
                            completed_at, priority, endpoint, decision,
                            remaining_before, remaining_after, error
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'BLOCKED', ?, ?, ?)
                        """,
                        (
                            provider,
                            account,
                            day,
                            started_at,
                            started_at,
                            selected_priority.value,
                            str(endpoint)[:200],
                            remaining,
                            remaining,
                            blocked_reason,
                        ),
                    )
                    connection.commit()
                    if blocked_reason.startswith("live ticker"):
                        raise APIBudgetExceeded("Live-Tageskontingent ausgeschöpft.", reason="ticker_limit")
                    raise APIBudgetExceeded(
                        "API-Budget geschützt: "
                        f"{selected_priority.value} wurde bei geschätzten "
                        f"{remaining} Rest-Calls vor dem Reservebereich {floor} blockiert.",
                        reason="protected_reserve",
                    )

                after = remaining - cost
                connection.execute(
                    """
                    UPDATE api_budget_state
                    SET remaining_estimate=?, updated_at=?
                    WHERE provider=? AND account_hash=? AND quota_day=?
                    """,
                    (after, started_at, provider, account, day),
                )
                cursor = connection.execute(
                    """
                    INSERT INTO api_budget_events (
                        provider, account_hash, quota_day, started_at,
                        priority, endpoint, decision,
                        remaining_before, remaining_after
                    ) VALUES (?, ?, ?, ?, ?, ?, 'RESERVED', ?, ?)
                    """,
                    (
                        provider,
                        account,
                        day,
                        started_at,
                        selected_priority.value,
                        str(endpoint)[:200],
                        remaining,
                        after,
                    ),
                )
                cutoff = (current - timedelta(days=21)).date().isoformat()
                connection.execute(
                    "DELETE FROM api_budget_events WHERE started_at < ?",
                    (cutoff,),
                )
                connection.commit()
                return APIBudgetReservation(
                    event_id=int(cursor.lastrowid),
                    provider=provider,
                    account_hash=account,
                    quota_day=day,
                    priority=selected_priority,
                    endpoint=str(endpoint),
                    remaining_before=remaining,
                    remaining_after=after,
                )
        except APIBudgetExceeded:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise APIBudgetUnavailable(
                f"API request blocked because the shared budget ledger failed: "
                f"{type(exc).__name__}"
            ) from exc

    def complete(
        self,
        reservation: APIBudgetReservation,
        *,
        response_headers: Any = None,
        http_status: Optional[int] = None,
        error: Optional[str] = None,
        now: Optional[datetime] = None,
        account_status_response: Any = None,
    ) -> None:
        completed = (now or _utc_now()).astimezone(timezone.utc).isoformat()
        provider_remaining = _header_int(
            response_headers,
            "x-ratelimit-requests-remaining",
        )
        provider_limit = _header_int(
            response_headers,
            "x-ratelimit-requests-limit",
        )
        usage = active_football_account_usage(account_status_response) if account_status_response is not None else None
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT daily_limit, remaining_estimate, observed_remaining, updated_at
                    FROM api_budget_state
                    WHERE provider=? AND account_hash=? AND quota_day=?
                    """,
                    (
                        reservation.provider,
                        reservation.account_hash,
                        reservation.quota_day,
                    ),
                ).fetchone()
                if row is not None:
                    current_remaining = int(row["remaining_estimate"])
                    stored_limit = int(row["daily_limit"])
                    current_limit = provider_limit or stored_limit
                    observed = provider_remaining
                    if account_status_response is not None:
                        bound = None
                        if (usage is not None and reservation.provider == "api-football"
                                and self.quota_period == "day" and completed[:10] == reservation.quota_day
                                and http_status == 200 and not error):
                            used, limit = usage
                            observed = min(limit - used, observed if observed is not None else limit)
                            current_limit = min(limit, provider_limit if provider_limit is not None else limit)
                            if provider_limit in (None, limit):
                                bound = self._status_bound(connection, reservation, row["updated_at"], limit, observed)
                        if bound is not None:
                            current_remaining = bound
                        else:
                            # Conflicting plans, malformed status or overlapping state
                            # changes: tighten only. Keep the stored plan so a later
                            # normal header cannot look like a plan upgrade.
                            current_remaining = min(current_remaining, current_limit)
                            current_limit = stored_limit
                            if observed is not None and row["observed_remaining"] is not None:
                                observed = min(observed, row["observed_remaining"])
                    elif reservation.provider == "api-football" and (
                            error or http_status is None or not 200 <= http_status < 300):
                        # Failed responses can tighten but cannot redefine the tariff.
                        current_remaining = min(current_remaining, current_limit)
                        current_limit = stored_limit
                        if observed is not None and row["observed_remaining"] is not None:
                            observed = min(observed, row["observed_remaining"])
                    elif current_limit > stored_limit and observed is not None:
                        # Existing plan-upgrade contract on a successful response.
                        current_remaining = observed
                    current_remaining = min(current_remaining, current_limit)
                    if observed is not None:
                        current_remaining = min(current_remaining, observed)
                    connection.execute(
                        """
                        UPDATE api_budget_state
                        SET daily_limit=?, remaining_estimate=?,
                            observed_remaining=COALESCE(?, observed_remaining),
                            updated_at=?
                        WHERE provider=? AND account_hash=? AND quota_day=?
                        """,
                        (
                            current_limit,
                            current_remaining,
                            observed,
                            completed,
                            reservation.provider,
                            reservation.account_hash,
                            reservation.quota_day,
                        ),
                    )
                connection.execute(
                    """
                    UPDATE api_budget_events
                    SET completed_at=?, decision=?, provider_remaining=?,
                        http_status=?, error=?
                    WHERE id=?
                    """,
                    (
                        completed,
                        "FAILED" if error else "COMPLETED",
                        provider_remaining,
                        http_status,
                        str(error)[:300] if error else None,
                        reservation.event_id,
                    ),
                )
                connection.commit()
        except (OSError, sqlite3.Error) as exc:
            raise APIBudgetUnavailable(
                f"API budget completion could not be recorded: {type(exc).__name__}"
            ) from exc

    @staticmethod
    def _status_bound(connection, reservation, updated_at, limit, observed) -> Optional[int]:
        """A confirmed account snapshot covers only calls settled before it began."""
        key = (reservation.provider, reservation.account_hash, reservation.quota_day)
        started = connection.execute(
            "SELECT started_at FROM api_budget_events WHERE provider=? AND account_hash=? "
            "AND quota_day=? AND id=? AND decision='RESERVED'", (*key, reservation.event_id),
        ).fetchone()
        if started is None or started[0] != updated_at:
            return None  # Another reservation/completion/reconciliation changed state in flight.
        spent, uncertain, overlap = connection.execute(
            """SELECT SUM(remaining_before-remaining_after),
                      SUM(remaining_before-remaining_after -
                          CASE WHEN decision='COMPLETED' AND http_status BETWEEN 200 AND 299
                               THEN 1 ELSE 0 END),
                      MAX(id > ? OR (id != ? AND completed_at >= ?))
               FROM api_budget_events WHERE provider=? AND account_hash=? AND quota_day=?
               AND decision!='BLOCKED'""",
            (reservation.event_id, reservation.event_id, started[0], *key),
        ).fetchone()
        if overlap:
            return None
        # Hold all local units, including failed/uncertain and weighted costs.
        # The status request itself is still RESERVED and may be unbilled.
        return max(0, min(limit - spent, observed - uncertain))

    def snapshot(
        self,
        *,
        api_key: str,
        provider: str = "api-football",
        now: Optional[datetime] = None,
    ) -> APIBudgetSnapshot:
        account = _account_hash(api_key)
        day = self._quota_day(now or _utc_now())
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT daily_limit, remaining_estimate, observed_remaining
                    FROM api_budget_state
                    WHERE provider=? AND account_hash=? AND quota_day=?
                    """,
                    (provider, account, day),
                ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise APIBudgetUnavailable(
                f"API budget snapshot failed: {type(exc).__name__}"
            ) from exc
        return APIBudgetSnapshot(
            quota_day=day,
            daily_limit=int(row["daily_limit"]) if row else self.daily_limit,
            remaining_estimate=(
                int(row["remaining_estimate"]) if row else self.daily_limit
            ),
            observed_remaining=(
                int(row["observed_remaining"])
                if row and row["observed_remaining"] is not None
                else None
            ),
            critical_floor=self.critical_floor,
            recommendation_reserve=self.recommendation_reserve,
            background_reserve=self.background_reserve,
        )

    def reconcile_usage(
        self,
        *,
        api_key: str,
        used: int,
        daily_limit: int,
        provider: str = "api-football",
        now: Optional[datetime] = None,
    ) -> APIBudgetSnapshot:
        if (
            isinstance(used, bool)
            or isinstance(daily_limit, bool)
            or not isinstance(used, int)
            or not isinstance(daily_limit, int)
            or used < 0
            or daily_limit <= 0
            or used > daily_limit
        ):
            raise ValueError("Provider usage must be valid daily integer counts")
        current = (now or _utc_now()).astimezone(timezone.utc)
        day = self._quota_day(current)
        account = _account_hash(api_key)
        provider_remaining = daily_limit - used
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT remaining_estimate, daily_limit
                    FROM api_budget_state
                    WHERE provider=? AND account_hash=? AND quota_day=?
                    """,
                    (provider, account, day),
                ).fetchone()
                if row is None or daily_limit > int(row["daily_limit"]):
                    # No estimate yet, or the plan grew during the day: the
                    # provider's account status is the only truthful count.
                    remaining = provider_remaining
                else:
                    remaining = min(int(row["remaining_estimate"]), provider_remaining)
                connection.execute(
                    """
                    INSERT INTO api_budget_state (
                        provider, account_hash, quota_day, daily_limit,
                        remaining_estimate, observed_remaining, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(provider, account_hash, quota_day)
                    DO UPDATE SET
                        daily_limit=excluded.daily_limit,
                        remaining_estimate=excluded.remaining_estimate,
                        observed_remaining=excluded.observed_remaining,
                        updated_at=excluded.updated_at
                    """,
                    (
                        provider,
                        account,
                        day,
                        daily_limit,
                        remaining,
                        provider_remaining,
                        current.isoformat(),
                    ),
                )
                connection.commit()
        except (OSError, sqlite3.Error) as exc:
            raise APIBudgetUnavailable(
                f"API usage reconciliation failed: {type(exc).__name__}"
            ) from exc
        return self.snapshot(api_key=api_key, provider=provider, now=current)


_GOVERNORS: dict[str, APIBudgetGovernor] = {}
_GOVERNOR_LOCK = threading.Lock()


def get_api_budget_governor() -> APIBudgetGovernor:
    path = Path(os.environ.get("BETBOY_API_BUDGET_DB") or DEFAULT_DB_PATH)
    cache_key = str(path.resolve())
    with _GOVERNOR_LOCK:
        governor = _GOVERNORS.get(cache_key)
        if governor is None:
            governor = APIBudgetGovernor(path)
            _GOVERNORS[cache_key] = governor
    return governor


def reset_api_budget_governor_cache() -> None:
    """Clear cached instances after changing test or deployment configuration."""
    with _GOVERNOR_LOCK:
        _GOVERNORS.clear()


TIMEOUT_ATTEMPTS = 2
TIMEOUT_RETRY_DELAY_SECONDS = 3.0


def active_football_account_usage(response: Any) -> Optional[tuple[int, int]]:
    """Validated (used, daily limit) from an active API-Football account response."""
    if response.status_code != 200:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict) or body.get("errors") not in ([], {}):
        return None
    account = body.get("response")
    if not isinstance(account, dict):
        return None
    subscription, usage = account.get("subscription"), account.get("requests")
    if not isinstance(subscription, dict) or subscription.get("active") is not True or not isinstance(usage, dict):
        return None
    used, limit = usage.get("current"), usage.get("limit_day")
    if type(used) is not int or type(limit) is not int or not 0 <= used <= limit or limit <= 0:
        return None
    return used, limit


def api_football_get(
    url: str,
    *,
    priority: APIBudgetPriority | str = APIBudgetPriority.RECOMMENDATION,
    label: Optional[str] = None,
    **request_kwargs: Any,
):
    """Perform one API-Football GET after an atomic quota reservation."""
    headers = request_kwargs.get("headers")
    api_key = headers.get("x-apisports-key") if isinstance(headers, Mapping) else None
    endpoint = label or urlparse(str(url)).path.strip("/") or "unknown"
    governor = get_api_budget_governor()
    # One retry after a connect/read timeout (06./07.11.2026: single provider timeouts failed
    # whole nightly runs). Each attempt holds its own quota reservation; any other error and a
    # second timeout are raised unchanged.
    live_ticker = endpoint.startswith(LIVE_TICKER_PREFIX)
    status_call = str(url) == _FOOTBALL_STATUS_URL
    auto_check = endpoint == FOOTBALL_ROLLOVER_STATUS_LABEL
    if auto_check and not status_call:
        raise APIBudgetUnavailable("Rollover check requires the API-Football account endpoint")
    attempts = 1 if live_ticker or auto_check else TIMEOUT_ATTEMPTS
    if live_ticker or status_call:
        request_kwargs["allow_redirects"] = False
    for attempt in range(1, attempts + 1):
        reservation = governor.reserve(
            api_key=str(api_key or ""),
            endpoint=endpoint,
            priority=priority,
        )
        try:
            response = requests.get(url, **request_kwargs)
        except requests.Timeout as exc:
            governor.complete(reservation, error=type(exc).__name__)
            if attempt == attempts:
                raise
            time.sleep(TIMEOUT_RETRY_DELAY_SECONDS)
            continue
        except Exception as exc:
            governor.complete(
                reservation,
                error=type(exc).__name__,
            )
            raise
        break
    governor.complete(
        reservation,
        account_status_response=response if status_call else None,
        response_headers=getattr(response, "headers", None),
        http_status=(
            int(response.status_code)
            if isinstance(getattr(response, "status_code", None), int)
            and not isinstance(response.status_code, bool)
            else None
        ),
    )
    return response


__all__ = [
    "APIBudgetError",
    "APIBudgetExceeded",
    "APIBudgetGovernor",
    "APIBudgetPriority",
    "APIBudgetReservation",
    "APIBudgetSnapshot",
    "APIBudgetUnavailable",
    "FOOTBALL_ROLLOVER_STATUS_LABEL",
    "active_football_account_usage",
    "api_football_get",
    "get_api_budget_governor",
    "reset_api_budget_governor_cache",
]
