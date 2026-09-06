"""Causal, observed tennis workload evidence; no invented fitness coefficients.

An observed terminal timestamp is not an actual end time. We therefore expose
only the minimum elapsed recovery since that observation. Missing match or
duration coverage is explicit, and is never interpreted as zero workload.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping

from .data_loader import normalize_player_name


def _instant(value: object) -> datetime | None:
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _whole(value: object, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or int(value) != value or not minimum <= value <= maximum:
        return None
    return int(value)


def observed_workload_context(
    player_a: str, player_b: str, history: Iterable[Mapping[str, object]], *,
    as_of: datetime,
) -> dict:
    """Extract identifiable completed facts known at the model cutoff.

    Only exact normalized names match. No fuzzy name, tournament-date or
    match-order inference is used to fabricate a previous match or rest time.
    """
    cutoff = _instant(as_of)
    if cutoff is None:
        raise ValueError("workload cutoff must be timezone-aware")
    rows = tuple(history)
    result = {
        "schema_version": 1,
        "observed_at": cutoff.isoformat(),
        "source": "tennis_shadow.completed_results",
        "probability_adjustment_applied": False,
        "adjustment_pp": 0.0,
        "coverage": "observed_matches_only",
        "limitations": [
            "Belastungsdaten decken nur zuvor beobachtete Matches ab.",
            "Aktuelle Verletzungen und Reisebelastung sind nicht verifiziert.",
            "Ein numerischer Belastungseffekt ist noch nicht historisch validiert.",
        ],
        "players": {},
    }
    for side, player in (("a", player_a), ("b", player_b)):
        key = normalize_player_name(player)
        observed = []
        seen = set()
        for row in rows:
            if not isinstance(row, Mapping) or row.get("settled") != 1:
                continue
            names = (normalize_player_name(str(row.get("player_a") or "")), normalize_player_name(str(row.get("player_b") or "")))
            if not key or names.count(key) != 1:
                continue
            recorded = _instant(row.get("result_observed_at"))
            start = _instant(row.get("scheduled_start_utc"))
            if recorded is None or start is None or recorded > cutoff or start >= recorded:
                continue
            if row.get("termination") not in ("normal", "retirement"):
                continue
            identity = (str(row.get("fixture_source") or ""), str(row.get("provider_event_id") or ""))
            if not all(identity):
                continue
            if identity in seen:
                continue
            seen.add(identity)
            a_sets = _whole(row.get("player_a_sets"), 0, 3)
            b_sets = _whole(row.get("player_b_sets"), 0, 3)
            total_sets = a_sets + b_sets if a_sets is not None and b_sets is not None else None
            if total_sets is not None and not 0 <= total_sets <= 5:
                total_sets = None
            duration = _whole(row.get("match_duration_minutes"), 1, 1500)
            observed.append({
                "event_id": identity[1], "source": identity[0],
                "started_at": start.isoformat(), "result_observed_at": recorded.isoformat(),
                "sets": total_sets, "duration_minutes": duration,
                "termination": row.get("termination"),
            })
        observed.sort(key=lambda item: (item["started_at"], item["result_observed_at"], item["source"], item["event_id"]), reverse=True)
        recent = [item for item in observed if _instant(item["started_at"]) >= cutoff - timedelta(days=7)]
        previous = observed[0] if observed else None
        recovery = (cutoff - _instant(previous["result_observed_at"])).total_seconds() / 3600 if previous else None
        evidence = {
            "player": player,
            "observed_matches_7d": len(recent),
            "observed_sets_7d": sum(item["sets"] for item in recent if item["sets"] is not None),
            "sets_coverage_7d": sum(item["sets"] is not None for item in recent),
            "observed_minutes_7d": sum(item["duration_minutes"] for item in recent if item["duration_minutes"] is not None) if any(item["duration_minutes"] is not None for item in recent) else None,
            "duration_coverage_7d": sum(item["duration_minutes"] is not None for item in recent),
            "previous_match": previous,
            "minimum_recovery_hours": round(recovery, 2) if recovery is not None else None,
            "previous_five_sets": previous["sets"] == 5 if previous and previous["sets"] is not None else None,
            "facts": [],
        }
        if previous:
            if previous["sets"] is not None:
                evidence["facts"].append(f"{player}: zuletzt {previous['sets']} beobachtete Sätze.")
            if previous["duration_minutes"] is not None:
                evidence["facts"].append(f"{player}: letztes Match {previous['duration_minutes']} Minuten laut Ergebnisquelle.")
            evidence["facts"].append(f"{player}: Ergebnis seit {recovery:.1f} Stunden bestätigt; tatsächliche Erholung mindestens so lang.")
            if previous["termination"] == "retirement":
                evidence["facts"].append(f"{player}: vorheriges Match endete mit Aufgabe; verletzter Spieler und Ursache nicht belegt.")
        else:
            evidence["facts"].append(f"{player}: keine zeitlich belegte vorherige Matchbelastung verfügbar.")
        result["players"][side] = evidence
    return result
