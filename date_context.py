"""Shared Zurich calendar labels for scans and stored results."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo


ZURICH_TIMEZONE = ZoneInfo("Europe/Zurich")


def format_zurich_time(value: Any, *, seconds: bool = False, unknown: str = "n/a") -> str:
    """Display an explicit instant, never a server-local or unknown timezone."""
    try:
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if moment.tzinfo is None or moment.utcoffset() is None:
            return unknown
        return moment.astimezone(ZURICH_TIMEZONE).strftime(
            "%d.%m.%Y %H:%M:%S" if seconds else "%d.%m.%Y %H:%M"
        )
    except (TypeError, ValueError, OverflowError):
        return unknown


def zurich_today(now: Optional[datetime] = None) -> date:
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return reference.astimezone(ZURICH_TIMEZONE).date()


def calendar_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def german_day_label(
    value: Any,
    *,
    today: Optional[date] = None,
) -> str:
    target = calendar_date(value)
    if target is None:
        return "Für den gewählten Spieltag"
    reference = today or zurich_today()
    if target == reference:
        return "Heute"
    if target == reference + timedelta(days=1):
        return "Morgen"
    return f"Am {target.strftime('%d.%m.%Y')}"


def german_date_window(
    start_value: Any,
    days_ahead: int,
    *,
    today: Optional[date] = None,
) -> str:
    start = calendar_date(start_value)
    if (
        start is None
        or isinstance(days_ahead, bool)
        or not isinstance(days_ahead, int)
        or days_ahead < 1
    ):
        return "unbekannt"
    end = start + timedelta(days=days_ahead)
    start_label = german_day_label(start, today=today)
    return (
        f"{start_label} ({start.strftime('%d.%m.%Y')}) bis "
        f"{end.strftime('%d.%m.%Y')}"
    )


__all__ = [
    "ZURICH_TIMEZONE",
    "calendar_date",
    "format_zurich_time",
    "german_date_window",
    "german_day_label",
    "zurich_today",
]
