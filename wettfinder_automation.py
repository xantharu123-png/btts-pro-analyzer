"""Event-driven, bookmaker-independent candidate selection for BetBoy.

The hourly systemd timer calls this module, but an hourly wake-up is not an
hourly full scan. Football is recalculated only when its event window is due.
Tennis and E-sport reuse their existing persisted model runs. The resulting
artifact contains at most three probability-ranked, price-pending candidates;
it never fetches or invents a bookmaker quote.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from zoneinfo import ZoneInfo

from betting_math import BETTING_POLICY_VERSION, minimum_acceptable_odds
from challenge_15k import (
    DEFAULT_CHALLENGE_LEAGUES,
    MAX_SCAN_FIXTURES,
    ChallengeDataProvider,
    scan_daily_challenge,
)
from config_loader import AppConfig, load_app_config
from ev_signal_sources import (
    ModelSignal,
    esports_signals,
    tennis_model_signals,
)


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "runtime_state" / "wettfinder_latest.json"
ZURICH_TZ = ZoneInfo("Europe/Zurich")
AUTOMATION_VERSION = 1
SELECTION_POLICY_VERSION = "probability-first-v1"
MAX_AUTOMATIC_CANDIDATES = 3
TOMORROW_SCAN_HOUR = 23
ERROR_RETRY = timedelta(hours=2)
EMPTY_RETRY = timedelta(hours=12)
FAR_EVENT_RETRY = timedelta(hours=12)
MEDIUM_EVENT_RETRY = timedelta(hours=2)
NEAR_EVENT_RETRY = timedelta(minutes=45)
NEAR_EVENT_WINDOW = timedelta(hours=2)
MEDIUM_EVENT_WINDOW = timedelta(hours=6)
FOOTBALL_CANDIDATE_MAX_AGE = timedelta(hours=2)


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
    """Decide whether the expensive football context scan is actually due."""
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

    parsed_kickoffs = [
        parsed
        for parsed in (
            _parse_iso(item) for item in (previous.get("fixture_kickoffs") or [])
        )
        if parsed is not None
    ]
    future_kickoffs = sorted(item for item in parsed_kickoffs if item > current)
    if parsed_kickoffs and not future_kickoffs:
        return FootballDueDecision(False, "all_known_events_started")
    if not future_kickoffs:
        return FootballDueDecision(
            age >= EMPTY_RETRY,
            "retry_empty_schedule" if age >= EMPTY_RETRY else "empty_backoff",
            minimum_gap=EMPTY_RETRY,
        )

    next_kickoff = future_kickoffs[0]
    until_kickoff = next_kickoff - current
    if until_kickoff <= NEAR_EVENT_WINDOW:
        gap = NEAR_EVENT_RETRY
    elif until_kickoff <= MEDIUM_EVENT_WINDOW:
        gap = MEDIUM_EVENT_RETRY
    else:
        gap = FAR_EVENT_RETRY
    due = age >= gap
    return FootballDueDecision(
        due,
        "event_window_due" if due else "event_window_not_due",
        next_kickoff=next_kickoff,
        minimum_gap=gap,
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


def _football_candidate_record(candidate: object) -> Optional[dict[str, Any]]:
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
    if signal.key.startswith("tennis-"):
        sport = "Tennis"
    elif signal.key.startswith("esports-"):
        sport = "E-Sport"
    else:
        sport = "Modell"
    scheduled = _parse_iso(signal.scheduled_start)
    if signal.scheduled_start is not None and scheduled is None:
        return None
    return {
        "key": signal.key,
        "sport": sport,
        "event": signal.label,
        "event_identity": f"{sport.lower()}:{signal.key}",
        "label": signal.label,
        "market": "Match Winner",
        "selection": signal.label,
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


def select_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    limit: int = MAX_AUTOMATIC_CANDIDATES,
) -> list[dict[str, Any]]:
    """Select probability-first candidates without offered-odds input."""
    current = _utc(now)
    valid: list[dict[str, Any]] = []
    for row in candidates:
        if not isinstance(row, dict) or row.get("status") != "PRICE_REQUIRED":
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
        if kickoff is not None and kickoff <= current:
            continue
        valid.append(dict(row))

    stage_rank = {"RELEASED": 2, "SHADOW": 1, "RESEARCH": 0}
    valid.sort(
        key=lambda row: (
            -stage_rank.get(str(row.get("evidence_stage")), -1),
            -float(row["conservative_probability"]),
            float(row["probability_haircut"]),
            str(row.get("key") or ""),
        )
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
    records = [
        record
        for record in (
            _football_candidate_record(candidate)
            for candidate in (snapshot.get("shortlist") or [])
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
    scanned_at = _parse_iso(snapshot.get("scanned_at")) or attempted_at
    return {
        "status": "degraded" if degraded else "completed",
        "search_date": search_date.isoformat(),
        "last_attempt_at": attempted_at.isoformat(),
        "last_success_at": scanned_at.isoformat() if not degraded else None,
        "fixture_kickoffs": _fixture_kickoffs(snapshot),
        "fixtures_found": fixtures_found,
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
    state.setdefault("candidates", [])
    state.setdefault("fixtures_found", 0)
    state.setdefault("approved_candidates", 0)
    return state


def _active_football_candidates(
    state: object,
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    if not isinstance(state, dict):
        return []
    scanned = _parse_iso(state.get("last_success_at"))
    if scanned is None or now - scanned > FOOTBALL_CANDIDATE_MAX_AGE:
        return []
    return select_candidates(state.get("candidates") or [], now=now, limit=10)


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
        list(DEFAULT_CHALLENGE_LEAGUES),
        search_date,
        MAX_SCAN_FIXTURES,
    )


def run_wettfinder(
    *,
    now: Optional[datetime] = None,
    state_path: str | Path = STATE_PATH,
    config: Optional[AppConfig] = None,
    football_scanner: Optional[Callable[[date], dict[str, Any]]] = None,
    tennis_loader: Callable[..., list[ModelSignal]] = tennis_model_signals,
    esports_loader: Callable[..., list[ModelSignal]] = esports_signals,
    force_football: bool = False,
) -> dict[str, Any]:
    """Run one due check and persist the maximum-three candidate artifact."""
    current = _utc(now)
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

    source_rows: list[dict[str, Any]] = _active_football_candidates(
        football_state,
        now=current,
    )
    source_status: dict[str, dict[str, Any]] = {
        "football": {
            "status": football_state.get("status", "idle"),
            "due_reason": "forced" if force_football else due.reason,
            "candidate_count": len(source_rows),
            "search_date": target.isoformat(),
        }
    }

    for source_name, loader, kwargs in (
        ("tennis", tennis_loader, {"now": current}),
        (
            "esports",
            esports_loader,
            {"now": current, "require_released": False},
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

    for unsupported in ("basketball", "ice_hockey", "cricket"):
        source_status[unsupported] = {
            "status": "blocked_no_validated_model",
            "candidate_count": 0,
        }

    candidates = select_candidates(source_rows, now=current)
    document = {
        "version": AUTOMATION_VERSION,
        "generated_at": current.isoformat(),
        "betting_policy_version": BETTING_POLICY_VERSION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "bookmaker_data_used": False,
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
                "bookmaker_data_used": False,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
