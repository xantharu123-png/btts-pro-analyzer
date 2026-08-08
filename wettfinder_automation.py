"""Daily discovery plus fixture-only context refresh for BetBoy.

One broad football discovery scans every configured league once per target
date. Later timer wake-ups never repeat that league scan: they refresh only
persisted candidate fixtures inside the pre-match context window. Tennis and
E-sport reuse their own daily persisted model runs as internal evidence. The
public artifact keeps at most three recommendations for exactly one local
match day, and only after an exact multi-bookmaker price passes the final
price gate.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from zoneinfo import ZoneInfo

from betting_math import BETTING_POLICY_VERSION, minimum_acceptable_odds
from challenge_15k import (
    MAX_SCAN_FIXTURES,
    ChallengeDataProvider,
    refresh_discovered_candidates,
    scan_daily_challenge,
)
from challenge_engine import (
    ChallengeCandidate,
    ValidationMetrics,
    candidate_is_credible,
)
from config_loader import AppConfig, load_app_config
from ev_signal_sources import (
    AUTOMATED_SELECTION_POLICY_VERSION,
    AUTOMATED_WETTFINDER_VERSION,
    ModelSignal,
    esports_signals,
    tennis_model_signals,
)
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from market_consensus import (
    MarketConsensus,
    fetch_football_consensus,
    reference_price_status,
)


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "runtime_state" / "wettfinder_latest.json"
ZURICH_TZ = ZoneInfo("Europe/Zurich")
AUTOMATION_VERSION = AUTOMATED_WETTFINDER_VERSION
SELECTION_POLICY_VERSION = AUTOMATED_SELECTION_POLICY_VERSION
MAX_AUTOMATIC_CANDIDATES = 3
MAX_AUTOMATIC_PRICE_FIXTURES = 10
MAX_AUTOMATIC_MARKETS_PER_FIXTURE = 8
TOMORROW_SCAN_HOUR = 23
ERROR_RETRY = timedelta(hours=2)
FOOTBALL_CONTEXT_WINDOW = timedelta(hours=2)
FOOTBALL_CONTEXT_MIN_GAP = timedelta(minutes=25)
FOOTBALL_CONTEXT_MAX_AGE = timedelta(minutes=75)


@dataclass(frozen=True)
class FootballDueDecision:
    due: bool
    reason: str
    next_kickoff: Optional[datetime] = None
    minimum_gap: Optional[timedelta] = None


def _utc(value: Optional[datetime] = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _parse_iso(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def target_search_date(now: Optional[datetime] = None) -> date:
    """Use today's events until 23:00 Zurich, then prepare tomorrow."""
    local = _utc(now).astimezone(ZURICH_TZ)
    return local.date() + timedelta(days=local.hour >= TOMORROW_SCAN_HOUR)


def football_due(
    previous: object,
    *,
    now: Optional[datetime] = None,
    search_date: Optional[date] = None,
) -> FootballDueDecision:
    """Decide whether the once-per-target-date league discovery is due."""
    current = _utc(now)
    target = search_date or target_search_date(current)
    if not isinstance(previous, dict):
        return FootballDueDecision(True, "no_previous_scan")
    if previous.get("search_date") != target.isoformat():
        return FootballDueDecision(True, "new_search_date")

    attempted = _parse_iso(
        previous.get("last_attempt_at") or previous.get("last_success_at")
    )
    if attempted is None:
        return FootballDueDecision(True, "invalid_previous_timestamp")
    age = current - attempted
    if age.total_seconds() < 0:
        return FootballDueDecision(True, "future_previous_timestamp")

    status = str(previous.get("status") or "")
    if status != "completed":
        return FootballDueDecision(
            age >= ERROR_RETRY,
            "retry_degraded_scan" if age >= ERROR_RETRY else "degraded_backoff",
            minimum_gap=ERROR_RETRY,
        )

    return FootballDueDecision(
        False,
        "daily_discovery_current",
    )


def _value(candidate: object, name: str, default: Any = None) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(name, default)
    return getattr(candidate, name, default)


def _finite_probability(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or not 0.0 < number < 1.0:
        return None
    return number


def _minimum_price(probability: float, haircut: float) -> Optional[float]:
    try:
        return minimum_acceptable_odds(
            probability * 100.0,
            probability_haircut=haircut * 100.0,
        )
    except (TypeError, ValueError):
        return None


_CHALLENGE_CANDIDATE_FIELDS = {
    field.name for field in fields(ChallengeCandidate)
}
_VALIDATION_FIELDS = {field.name for field in fields(ValidationMetrics)}


def _challenge_candidate_payload(
    candidate: object,
    *,
    keep_context: bool = False,
) -> Optional[dict[str, Any]]:
    """Serialize a model candidate without trusting derived properties."""
    if not isinstance(candidate, ChallengeCandidate) or not candidate.base_eligible:
        return None
    payload = candidate.to_dict()
    payload.pop("base_eligible", None)
    payload.pop("eligible", None)
    if not keep_context:
        payload["context"] = {}
    return payload


def _challenge_candidate_from_payload(
    payload: object,
) -> Optional[ChallengeCandidate]:
    """Strictly rebuild a persisted daily candidate for a fresh context pass."""
    if not isinstance(payload, dict):
        return None
    raw = {
        name: payload.get(name)
        for name in _CHALLENGE_CANDIDATE_FIELDS
    }
    validation_payload = raw.get("validation")
    if not isinstance(validation_payload, dict):
        return None
    if set(validation_payload) - _VALIDATION_FIELDS:
        return None
    try:
        raw["validation"] = ValidationMetrics(**validation_payload)
        raw["venue_samples"] = tuple(raw.get("venue_samples") or ())
        raw["form_samples"] = tuple(raw.get("form_samples") or ())
        raw["reasons"] = list(raw.get("reasons") or [])
        raw["blocked_reasons"] = list(raw.get("blocked_reasons") or [])
        raw["context"] = {}
        candidate = ChallengeCandidate(**raw)
    except (TypeError, ValueError):
        return None
    if not candidate.base_eligible:
        return None
    return candidate


def _football_candidate_record(
    candidate: object,
    *,
    context_checked_at: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    if not isinstance(candidate, ChallengeCandidate):
        return None
    if not candidate_is_credible(candidate):
        return None
    probability = _finite_probability(_value(candidate, "probability"))
    conservative = _finite_probability(
        _value(candidate, "conservative_probability")
    )
    if probability is None or conservative is None or conservative > probability:
        return None
    haircut = probability - conservative
    minimum_odds = _minimum_price(probability, haircut)
    kickoff = _parse_iso(_value(candidate, "kickoff"))
    candidate_id = str(_value(candidate, "candidate_id") or "").strip()
    home = str(_value(candidate, "home_team") or "").strip()
    away = str(_value(candidate, "away_team") or "").strip()
    market = str(_value(candidate, "market") or "").strip()
    selection = str(_value(candidate, "selection") or "").strip()
    if (
        minimum_odds is None
        or kickoff is None
        or not candidate_id
        or not all((home, away, market, selection))
    ):
        return None
    event = f"{home} vs {away}"
    league = str(_value(candidate, "league_name") or "Liga").strip()
    evidence_score = _value(candidate, "evidence_score")
    spread = _value(candidate, "model_spread_pp")
    detail_parts = [f"15K-Fussballmodell", league]
    if isinstance(evidence_score, (int, float)) and math.isfinite(
        float(evidence_score)
    ):
        detail_parts.append(f"Evidenz {float(evidence_score):.0f}/100")
    if isinstance(spread, (int, float)) and math.isfinite(float(spread)):
        detail_parts.append(f"Modellstreuung {float(spread):.1f} PP")
    return {
        "key": f"wettfinder-football-{candidate_id}",
        "candidate_id": candidate_id,
        "fixture_id": _value(candidate, "fixture_id"),
        "league_id": _value(candidate, "league_id"),
        "market_key": _value(candidate, "market_key"),
        "sport": "Fussball",
        "event": event,
        "event_identity": f"football:{_value(candidate, 'fixture_id')}",
        "label": f"Fussball - {event} - {market}: {selection}",
        "market": market,
        "selection": selection,
        "probability": probability,
        "probability_haircut": haircut,
        "conservative_probability": conservative,
        "minimum_odds": minimum_odds,
        "evidence_stage": "SHADOW",
        "policy_version": BETTING_POLICY_VERSION,
        "scheduled_start": kickoff.isoformat(),
        "status": "PRICE_REQUIRED",
        "source": "football_challenge",
        "detail": " - ".join(detail_parts),
        "context_checked_at": (
            _utc(context_checked_at).isoformat()
            if context_checked_at is not None
            else None
        ),
    }


def _signal_record(signal: ModelSignal) -> Optional[dict[str, Any]]:
    probability = _finite_probability(signal.probability)
    if probability is None:
        return None
    haircut = float(signal.probability_haircut)
    conservative = probability - haircut
    if conservative <= 0.0:
        return None
    minimum_odds = _minimum_price(probability, haircut)
    if minimum_odds is None:
        return None
    if signal.sport:
        sport = signal.sport
    elif signal.key.startswith("tennis-"):
        sport = "Tennis"
    elif signal.key.startswith("esports-"):
        sport = "E-Sport"
    else:
        sport = "Modell"
    event_label = signal.event_label or signal.label
    market = signal.market or "Match Winner"
    selection = signal.selection or signal.label
    scheduled = _parse_iso(signal.scheduled_start)
    if signal.scheduled_start is not None and scheduled is None:
        return None
    return {
        "key": signal.key,
        "sport": sport,
        "event": event_label,
        "event_identity": f"{sport.lower()}:{signal.key}",
        "label": signal.label,
        "market": market,
        "selection": selection,
        "probability": probability,
        "probability_haircut": haircut,
        "conservative_probability": conservative,
        "minimum_odds": minimum_odds,
        "evidence_stage": signal.evidence_stage,
        "policy_version": signal.policy_version,
        "scheduled_start": scheduled.isoformat() if scheduled else None,
        "status": "PRICE_REQUIRED",
        "source": "tennis_shadow" if sport == "Tennis" else "esports_shadow",
        "detail": signal.detail,
    }


def _ranked_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
) -> list[dict[str, Any]]:
    """Validate and rank candidates for exactly one Zurich match day."""
    current = _utc(now)
    target = target_date or target_search_date(current)
    stage_rank = {"RELEASED": 2, "SHADOW": 1, "RESEARCH": 0}
    valid: list[dict[str, Any]] = []
    for row in candidates:
        if not isinstance(row, dict) or row.get("status") != "PRICE_REQUIRED":
            continue
        evidence_stage = str(row.get("evidence_stage") or "")
        if evidence_stage not in stage_rank:
            continue
        probability = _finite_probability(row.get("probability"))
        conservative = _finite_probability(row.get("conservative_probability"))
        haircut = row.get("probability_haircut")
        if (
            probability is None
            or conservative is None
            or conservative > probability
            or isinstance(haircut, bool)
            or not isinstance(haircut, (int, float))
            or not math.isfinite(float(haircut))
            or abs((probability - conservative) - float(haircut)) > 1e-8
        ):
            continue
        kickoff = _parse_iso(row.get("scheduled_start"))
        if row.get("scheduled_start") is not None and kickoff is None:
            continue
        if (
            kickoff is None
            or kickoff <= current
            or kickoff.astimezone(ZURICH_TZ).date() != target
        ):
            continue
        valid.append(dict(row))

    valid.sort(
        key=lambda row: (
            -stage_rank.get(str(row.get("evidence_stage")), -1),
            -float(row["conservative_probability"]),
            float(row["probability_haircut"]),
            str(row.get("key") or ""),
        )
    )
    return valid


def select_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
    limit: int = MAX_AUTOMATIC_CANDIDATES,
) -> list[dict[str, Any]]:
    """Select one probability-first market per event after the price gate."""
    valid = _ranked_candidates(
        candidates,
        now=now,
        target_date=target_date,
    )
    selected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_events: set[str] = set()
    for row in valid:
        key = str(row.get("key") or "").strip()
        event = str(row.get("event_identity") or key).strip()
        if not key or key in seen_keys or event in seen_events:
            continue
        seen_keys.add(key)
        seen_events.add(event)
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def select_price_check_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
    max_fixtures: int = MAX_AUTOMATIC_PRICE_FIXTURES,
    max_markets_per_fixture: int = MAX_AUTOMATIC_MARKETS_PER_FIXTURE,
) -> list[dict[str, Any]]:
    """Keep several valid markets per fixture until exact prices are known."""
    for value, label in (
        (max_fixtures, "max_fixtures"),
        (max_markets_per_fixture, "max_markets_per_fixture"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{label} must be a positive integer")

    valid = _ranked_candidates(
        candidates,
        now=now,
        target_date=target_date,
    )
    selected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    fixture_counts: dict[str, int] = {}
    for row in valid:
        key = str(row.get("key") or "").strip()
        fixture = str(row.get("event_identity") or key).strip()
        if not key or not fixture or key in seen_keys:
            continue
        if fixture not in fixture_counts:
            if len(fixture_counts) >= max_fixtures:
                continue
            fixture_counts[fixture] = 0
        if fixture_counts[fixture] >= max_markets_per_fixture:
            continue
        seen_keys.add(key)
        fixture_counts[fixture] += 1
        selected.append(row)
    return selected


def _fixture_kickoffs(snapshot: dict[str, Any]) -> list[str]:
    values: list[object] = list(snapshot.get("fixture_kickoffs") or [])
    if not values:
        values = [
            _value(candidate, "kickoff")
            for candidate in (snapshot.get("base_shortlist") or [])
        ]
    parsed = sorted(
        item
        for item in (_parse_iso(value) for value in values)
        if item is not None
    )
    return [item.isoformat() for item in parsed]


def _football_state_from_snapshot(
    snapshot: dict[str, Any],
    *,
    attempted_at: datetime,
    search_date: date,
) -> dict[str, Any]:
    scanned_at = _parse_iso(snapshot.get("scanned_at")) or attempted_at
    discovery_values = (
        snapshot.get("discovery_candidates")
        or snapshot.get("base_shortlist")
        or []
    )
    discovery_payloads = [
        payload
        for payload in (
            _challenge_candidate_payload(candidate)
            for candidate in discovery_values
        )
        if payload is not None
    ]
    records = [
        record
        for record in (
            _football_candidate_record(
                candidate,
                context_checked_at=scanned_at,
            )
            for candidate in (
                snapshot.get("price_candidates")
                or snapshot.get("shortlist")
                or []
            )
        )
        if record is not None
    ]
    errors = [
        str(error)
        for error in (snapshot.get("errors") or [])
        if str(error).strip()
    ][:20]
    fixtures_found = int(snapshot.get("fixtures_found") or 0)
    degraded = fixtures_found == 0 and bool(errors)
    context_checks = {
        str(payload["fixture_id"]): scanned_at.isoformat()
        for payload in discovery_payloads
        if isinstance(payload.get("fixture_id"), int)
    }
    return {
        "status": "degraded" if degraded else "completed",
        "search_date": search_date.isoformat(),
        "last_attempt_at": attempted_at.isoformat(),
        "last_discovery_at": scanned_at.isoformat() if not degraded else None,
        "last_success_at": scanned_at.isoformat() if not degraded else None,
        "fixture_kickoffs": _fixture_kickoffs(snapshot),
        "fixtures_found": fixtures_found,
        "fixtures_modeled": int(snapshot.get("fixtures_modeled") or 0),
        "base_candidates": int(snapshot.get("base_candidates") or 0),
        "blocked_counts": {
            str(reason): int(count)
            for reason, count in (snapshot.get("blocked_counts") or {}).items()
            if str(reason).strip()
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count > 0
        },
        "continental_fixtures_found": int(
            snapshot.get("continental_fixtures_found") or 0
        ),
        "continental_fallback_modeled": int(
            snapshot.get("continental_fallback_modeled") or 0
        ),
        "continental_fallback_failed": int(
            snapshot.get("continental_fallback_failed") or 0
        ),
        "discovery_candidates": discovery_payloads,
        "discovery_candidate_count": len(discovery_payloads),
        "context_checks": context_checks,
        "approved_candidates": len(records),
        "candidates": records,
        "errors": errors,
    }


def _failed_football_state(
    previous: object,
    *,
    attempted_at: datetime,
    search_date: date,
    error: str,
) -> dict[str, Any]:
    same_day = (
        isinstance(previous, dict)
        and previous.get("search_date") == search_date.isoformat()
    )
    state = dict(previous) if same_day else {}
    state.update(
        {
            "status": "degraded",
            "search_date": search_date.isoformat(),
            "last_attempt_at": attempted_at.isoformat(),
            "errors": [str(error)[:500]],
        }
    )
    state.setdefault("fixture_kickoffs", [])
    state.setdefault("discovery_candidates", [])
    state.setdefault("discovery_candidate_count", 0)
    state.setdefault("context_checks", {})
    state.setdefault("candidates", [])
    state.setdefault("fixtures_found", 0)
    state.setdefault("fixtures_modeled", 0)
    state.setdefault("approved_candidates", 0)
    return state


def football_context_due_fixture_ids(
    state: object,
    *,
    now: Optional[datetime] = None,
) -> list[int]:
    """Return only persisted shortlist fixtures needing fresh pre-match context."""
    if not isinstance(state, dict):
        return []
    current = _utc(now)
    checks = state.get("context_checks")
    checks = checks if isinstance(checks, dict) else {}
    due: dict[int, datetime] = {}
    for payload in state.get("discovery_candidates") or []:
        if not isinstance(payload, dict):
            continue
        fixture_id = payload.get("fixture_id")
        kickoff = _parse_iso(payload.get("kickoff"))
        if (
            isinstance(fixture_id, bool)
            or not isinstance(fixture_id, int)
            or fixture_id <= 0
            or kickoff is None
            or not current < kickoff <= current + FOOTBALL_CONTEXT_WINDOW
        ):
            continue
        last_check = _parse_iso(checks.get(str(fixture_id)))
        if (
            last_check is not None
            and timedelta(0) <= current - last_check < FOOTBALL_CONTEXT_MIN_GAP
        ):
            continue
        due[fixture_id] = kickoff
    return [
        fixture_id
        for fixture_id, _kickoff in sorted(
            due.items(),
            key=lambda item: (item[1], item[0]),
        )[:20]
    ]


def _discovered_candidates_for_fixtures(
    state: object,
    fixture_ids: list[int],
) -> list[ChallengeCandidate]:
    if not isinstance(state, dict):
        return []
    allowed = set(fixture_ids)
    candidates: list[ChallengeCandidate] = []
    for payload in state.get("discovery_candidates") or []:
        if not isinstance(payload, dict) or payload.get("fixture_id") not in allowed:
            continue
        candidate = _challenge_candidate_from_payload(payload)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _merge_context_refresh(
    state: dict[str, Any],
    result: dict[str, Any],
    *,
    fixture_ids: list[int],
    checked_at: datetime,
) -> dict[str, Any]:
    refreshed = dict(state)
    allowed = set(fixture_ids)
    retained = [
        row
        for row in (state.get("candidates") or [])
        if isinstance(row, dict) and row.get("fixture_id") not in allowed
    ]
    new_records = [
        record
        for record in (
            _football_candidate_record(
                candidate,
                context_checked_at=checked_at,
            )
            for candidate in (
                result.get("price_candidates")
                or result.get("candidates")
                or result.get("shortlist")
                or []
            )
        )
        if record is not None
    ]
    checks = dict(state.get("context_checks") or {})
    for fixture_id in fixture_ids:
        checks[str(fixture_id)] = checked_at.isoformat()
    errors = [
        str(error)
        for error in (
            list(state.get("errors") or [])
            + list(result.get("errors") or [])
        )
        if str(error).strip()
    ]
    refreshed.update(
        {
            "last_context_at": checked_at.isoformat(),
            "context_checks": checks,
            "candidates": retained + new_records,
            "approved_candidates": len(retained) + len(new_records),
            "last_blocked_counts": dict(result.get("blocked_counts") or {}),
            "errors": list(dict.fromkeys(errors))[-20:],
        }
    )
    return refreshed


def _active_football_candidates(
    state: object,
    *,
    now: datetime,
    target_date: date,
) -> list[dict[str, Any]]:
    if not isinstance(state, dict):
        return []
    current = _utc(now)
    fresh = []
    for row in state.get("candidates") or []:
        if not isinstance(row, dict):
            continue
        checked = _parse_iso(row.get("context_checked_at"))
        if (
            checked is None
            or current - checked < timedelta(0)
            or current - checked > FOOTBALL_CONTEXT_MAX_AGE
        ):
            continue
        fresh.append(row)
    return select_price_check_candidates(
        fresh,
        now=current,
        target_date=target_date,
    )


def load_state(path: str | Path = STATE_PATH) -> dict[str, Any]:
    state_path = Path(path)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(payload, dict) or payload.get("version") != AUTOMATION_VERSION:
        return {}
    return payload


def write_state(document: dict[str, Any], path: str | Path = STATE_PATH) -> None:
    """Atomically replace the public runtime artifact."""
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_name(
        f".{state_path.name}.{os.getpid()}.tmp"
    )
    serialized = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, state_path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _default_football_scan(
    search_date: date,
    config: AppConfig,
) -> dict[str, Any]:
    if not config.api_football_key:
        raise RuntimeError("API_FOOTBALL_KEY is not configured")
    provider = ChallengeDataProvider(
        config.api_football_key,
        config.weather_key,
    )
    return scan_daily_challenge(
        provider,
        list(ALTERNATIVE_MARKET_LEAGUES),
        search_date,
        MAX_SCAN_FIXTURES,
    )


def _default_football_context_refresh(
    candidates: list[ChallengeCandidate],
    search_date: date,
    current: datetime,
    config: AppConfig,
) -> dict[str, Any]:
    if not config.api_football_key:
        raise RuntimeError("API_FOOTBALL_KEY is not configured")
    provider = ChallengeDataProvider(
        config.api_football_key,
        config.weather_key,
    )
    return refresh_discovered_candidates(
        provider,
        candidates,
        search_date,
        now=current,
        max_candidates=6,
    )


def run_wettfinder(
    *,
    now: Optional[datetime] = None,
    state_path: str | Path = STATE_PATH,
    config: Optional[AppConfig] = None,
    football_scanner: Optional[Callable[[date], dict[str, Any]]] = None,
    football_context_refresher: Optional[
        Callable[
            [list[ChallengeCandidate], date, datetime],
            dict[str, Any],
        ]
    ] = None,
    football_quote_loader: Optional[
        Callable[
            [list[dict[str, Any]]],
            tuple[dict[str, MarketConsensus], list[str]],
        ]
    ] = None,
    tennis_loader: Callable[..., list[ModelSignal]] = tennis_model_signals,
    esports_loader: Callable[..., list[ModelSignal]] = esports_signals,
    force_football: bool = False,
    clock: Optional[Callable[[], datetime]] = None,
) -> dict[str, Any]:
    """Run daily discovery if due, then refresh only near candidate fixtures."""
    runtime_clock = clock or (lambda: datetime.now(timezone.utc))
    fixed_now = now is not None
    current = _utc(now if fixed_now else runtime_clock())
    target = target_search_date(current)
    previous = load_state(state_path)
    previous_football = previous.get("football")
    due = football_due(previous_football, now=current, search_date=target)
    football_state = (
        dict(previous_football) if isinstance(previous_football, dict) else {}
    )

    if force_football or due.due:
        try:
            app_config = config or load_app_config()
            scanner = football_scanner or (
                lambda scan_date: _default_football_scan(scan_date, app_config)
            )
            snapshot = scanner(target)
            if not isinstance(snapshot, dict):
                raise RuntimeError("football scanner returned no document")
            football_state = _football_state_from_snapshot(
                snapshot,
                attempted_at=current,
                search_date=target,
            )
        except Exception as exc:
            football_state = _failed_football_state(
                previous_football,
                attempted_at=current,
                search_date=target,
                error=f"{type(exc).__name__}: {exc}",
            )

    if not fixed_now:
        current = _utc(runtime_clock())

    context_fixture_ids = football_context_due_fixture_ids(
        football_state,
        now=current,
    )
    context_status = "not_due"
    if context_fixture_ids:
        context_candidates = _discovered_candidates_for_fixtures(
            football_state,
            context_fixture_ids,
        )
        if not context_candidates:
            context_status = "invalid_daily_pool"
            football_state = dict(football_state)
            football_state["status"] = "degraded"
            football_state["errors"] = list(
                dict.fromkeys(
                    list(football_state.get("errors") or [])
                    + ["Persistierter Fußball-Tagespool ist ungültig"]
                )
            )[-20:]
        else:
            try:
                app_config = config or load_app_config()
                refresher = football_context_refresher or (
                    lambda pool, scan_date, checked_at: (
                        _default_football_context_refresh(
                            pool,
                            scan_date,
                            checked_at,
                            app_config,
                        )
                    )
                )
                refresh_result = refresher(
                    context_candidates,
                    target,
                    current,
                )
                if not isinstance(refresh_result, dict):
                    raise RuntimeError("football context refresher returned no document")
                football_state = _merge_context_refresh(
                    football_state,
                    refresh_result,
                    fixture_ids=context_fixture_ids,
                    checked_at=current,
                )
                context_status = "refreshed"
            except Exception as exc:
                context_status = "degraded"
                football_state = dict(football_state)
                football_state["errors"] = list(
                    dict.fromkeys(
                        list(football_state.get("errors") or [])
                        + [f"Context {type(exc).__name__}: {exc}"[:500]]
                    )
                )[-20:]

    if not fixed_now:
        current = _utc(runtime_clock())

    source_rows: list[dict[str, Any]] = _active_football_candidates(
        football_state,
        now=current,
        target_date=target,
    )
    source_status: dict[str, dict[str, Any]] = {
        "football": {
            "status": football_state.get("status", "idle"),
            "due_reason": "forced" if force_football else due.reason,
            "discovery_scope": len(ALTERNATIVE_MARKET_LEAGUES),
            "context_status": context_status,
            "context_fixture_count": len(context_fixture_ids),
            "candidate_count": len(source_rows),
            "search_date": target.isoformat(),
        }
    }

    for source_name, loader, kwargs in (
        (
            "tennis",
            tennis_loader,
            {"now": current, "today": target.isoformat()},
        ),
        (
            "esports",
            esports_loader,
            {"now": current, "require_released": True},
        ),
    ):
        try:
            signals = loader(**kwargs)
            rows = [
                row
                for row in (_signal_record(signal) for signal in signals)
                if row is not None
            ]
            source_rows.extend(rows)
            source_status[source_name] = {
                "status": "reused_persisted_model",
                "candidate_count": len(rows),
            }
        except Exception as exc:
            source_status[source_name] = {
                "status": "degraded",
                "candidate_count": 0,
                "error": f"{type(exc).__name__}: {exc}"[:500],
            }

    source_status["basketball"] = {
        "status": "live_only_no_prematch_model",
        "candidate_count": 0,
    }
    source_status["ice_hockey"] = {
        "status": "live_only_no_prematch_model",
        "candidate_count": 0,
    }
    source_status["cricket"] = {
        "status": "blocked_no_validated_model",
        "candidate_count": 0,
    }

    football_price_rows = select_price_check_candidates(
        (
            row
            for row in source_rows
            if row.get("source") == "football_challenge"
            and isinstance(row.get("fixture_id"), int)
            and not isinstance(row.get("fixture_id"), bool)
            and row["fixture_id"] > 0
            and str(row.get("market_key") or "").strip()
        ),
        now=current,
        target_date=target,
    )
    quote_errors: list[str] = []
    reference_quotes: dict[str, MarketConsensus] = {}
    if football_price_rows:
        try:
            if football_quote_loader is not None:
                reference_quotes, quote_errors = football_quote_loader(
                    football_price_rows
                )
            elif football_scanner is None and football_context_refresher is None:
                app_config = config or load_app_config()
                reference_quotes, quote_errors = fetch_football_consensus(
                    app_config.api_football_key or "",
                    football_price_rows,
                    now=current,
                )
        except Exception as exc:
            quote_errors = [f"{type(exc).__name__}: {exc}"[:500]]
    if not fixed_now:
        current = _utc(runtime_clock())
    price_status_counts: dict[str, int] = {}
    playable_rows: list[dict[str, Any]] = []
    for row in football_price_rows:
        candidate_id = str(row.get("candidate_id") or "")
        quote = reference_quotes.get(candidate_id)
        if quote is None:
            status_code = "UNAVAILABLE"
            row["reference_price_status"] = status_code
            price_status_counts[status_code] = (
                price_status_counts.get(status_code, 0) + 1
            )
            continue
        row["reference_quote"] = quote.to_dict()
        status_code = reference_price_status(
            quote,
            row.get("minimum_odds"),
            now=current,
        ).code
        row["reference_price_status"] = status_code
        price_status_counts[status_code] = (
            price_status_counts.get(status_code, 0) + 1
        )
        if status_code == "PLAYABLE":
            playable_rows.append(row)

    candidates = select_candidates(
        playable_rows,
        now=current,
        target_date=target,
        limit=MAX_AUTOMATIC_CANDIDATES,
    )
    for row in candidates:
        row["status"] = "RECOMMENDED"
    if isinstance(source_status.get("football"), dict):
        source_status["football"]["reference_quote_count"] = len(
            reference_quotes
        )
        source_status["football"]["price_checked_count"] = len(
            football_price_rows
        )
        source_status["football"]["price_fixture_count"] = len(
            {row["fixture_id"] for row in football_price_rows}
        )
        source_status["football"]["price_status_counts"] = price_status_counts
        source_status["football"]["published_recommendation_count"] = len(
            candidates
        )
        source_status["football"]["quote_errors"] = quote_errors[:10]
    document = {
        "version": AUTOMATION_VERSION,
        "generated_at": current.isoformat(),
        "betting_policy_version": BETTING_POLICY_VERSION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        # A quote can be genuinely used to reject every candidate. Keep price
        # evidence separate from the number of published recommendations.
        "bookmaker_data_used": bool(reference_quotes),
        "quote_required": True,
        "target_search_date": target.isoformat(),
        "football": football_state,
        "sources": source_status,
        "candidates": candidates,
    }
    write_state(document, state_path)
    return document


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-football", action="store_true")
    parser.add_argument("--state-path", default=str(STATE_PATH))
    args = parser.parse_args(argv)
    try:
        document = run_wettfinder(
            state_path=args.state_path,
            force_football=args.force_football,
        )
    except Exception as exc:
        print(
            json.dumps(
                {"status": "error", "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "ok",
                "generated_at": document["generated_at"],
                "candidate_count": len(document["candidates"]),
                "football_status": document["sources"]["football"]["status"],
                "football_due_reason": document["sources"]["football"]["due_reason"],
                "football_context_status": document["sources"]["football"][
                    "context_status"
                ],
                "football_discovery_scope": document["sources"]["football"][
                    "discovery_scope"
                ],
                "bookmaker_data_used": document["bookmaker_data_used"],
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
