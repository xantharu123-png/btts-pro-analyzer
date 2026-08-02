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
from typing import Any, Optional
from urllib.parse import urlparse

import requests


DEFAULT_DAILY_LIMIT = 7_500
DEFAULT_CRITICAL_FLOOR = 50
DEFAULT_RECOMMENDATION_RESERVE = 750
DEFAULT_BACKGROUND_RESERVE = 2_500
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
    ):
        self.db_path = Path(db_path)
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
                connection.execute("PRAGMA journal_mode = WAL")
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

    def reserve(
        self,
        *,
        api_key: str,
        endpoint: str,
        priority: APIBudgetPriority | str,
        provider: str = "api-football",
        now: Optional[datetime] = None,
    ) -> APIBudgetReservation:
        selected_priority = _priority(priority)
        account = _account_hash(api_key)
        current = (now or _utc_now()).astimezone(timezone.utc)
        day = current.date().isoformat()
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

                if remaining <= floor:
                    cursor = connection.execute(
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
                            f"protected floor {floor}",
                        ),
                    )
                    connection.commit()
                    raise APIBudgetExceeded(
                        "API-Budget geschützt: "
                        f"{selected_priority.value} wurde bei geschätzten "
                        f"{remaining} Rest-Calls vor dem Reservebereich {floor} blockiert."
                    )

                after = remaining - 1
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
                    "DELETE FROM api_budget_events WHERE quota_day < ?",
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
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT daily_limit, remaining_estimate
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
                    current_limit = int(row["daily_limit"])
                    if provider_limit is not None and provider_limit > 0:
                        current_limit = provider_limit
                    if provider_remaining is not None:
                        current_remaining = min(
                            current_remaining,
                            provider_remaining,
                            current_limit,
                        )
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
                            provider_remaining,
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

    def snapshot(
        self,
        *,
        api_key: str,
        provider: str = "api-football",
        now: Optional[datetime] = None,
    ) -> APIBudgetSnapshot:
        account = _account_hash(api_key)
        day = (now or _utc_now()).astimezone(timezone.utc).date().isoformat()
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
        day = current.date().isoformat()
        account = _account_hash(api_key)
        provider_remaining = daily_limit - used
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT remaining_estimate
                    FROM api_budget_state
                    WHERE provider=? AND account_hash=? AND quota_day=?
                    """,
                    (provider, account, day),
                ).fetchone()
                remaining = (
                    min(int(row["remaining_estimate"]), provider_remaining)
                    if row is not None
                    else provider_remaining
                )
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
    reservation = governor.reserve(
        api_key=str(api_key or ""),
        endpoint=endpoint,
        priority=priority,
    )
    try:
        response = requests.get(url, **request_kwargs)
    except Exception as exc:
        governor.complete(
            reservation,
            error=type(exc).__name__,
        )
        raise
    governor.complete(
        reservation,
        response_headers=getattr(response, "headers", None),
        http_status=(
            int(response.status_code)
            if isinstance(getattr(response, "status_code", None), int)
            and not isinstance(response.status_code, bool)
            else None
        ),
    )
    if urlparse(str(url)).path.rstrip("/").endswith("/status"):
        try:
            payload = response.json()
            provider_response = (
                payload.get("response") if isinstance(payload, dict) else None
            )
            usage = (
                provider_response.get("requests")
                if isinstance(provider_response, dict)
                else None
            )
            used = usage.get("current") if isinstance(usage, dict) else None
            daily_limit = (
                usage.get("limit_day") if isinstance(usage, dict) else None
            )
            if (
                isinstance(used, int)
                and not isinstance(used, bool)
                and isinstance(daily_limit, int)
                and not isinstance(daily_limit, bool)
            ):
                governor.reconcile_usage(
                    api_key=str(api_key),
                    used=used,
                    daily_limit=daily_limit,
                )
        except (APIBudgetError, ValueError):
            pass
    return response


__all__ = [
    "APIBudgetError",
    "APIBudgetExceeded",
    "APIBudgetGovernor",
    "APIBudgetPriority",
    "APIBudgetReservation",
    "APIBudgetSnapshot",
    "APIBudgetUnavailable",
    "api_football_get",
    "get_api_budget_governor",
    "reset_api_budget_governor_cache",
]
