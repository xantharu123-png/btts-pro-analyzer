"""Daily discovery plus fixture-only context refresh for BetBoy.

One broad football discovery scans every configured league once per target
date. Later timer wake-ups never repeat that league scan: they refresh only
persisted candidate fixtures inside the pre-match context window. Tennis and
E-sport reuse their own daily persisted model runs as internal evidence. The
public artifact keeps a bounded model catalog for exactly one local match day
independently of price. The first three remain the compact featured block;
additional model selections stay available below it. A second, strict list
contains at most three selections whose exact multi-bookmaker price passes
the final price gate. A price can reject playability, never erase or reorder
the forecast catalog.
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
import unicodedata
from zoneinfo import ZoneInfo

from betting_math import BETTING_POLICY_VERSION, minimum_recommendation_odds
from challenge_15k import (
    MAX_SCAN_FIXTURES,
    ChallengeDataProvider,
    refresh_discovered_candidates,
    scan_daily_challenge,
)
from challenge_engine import (
    MARKET_BY_KEY,
    MARKET_SPECS,
    MODEL_SCOPE_SAME_COMPETITION,
    VALIDATION_FDR_ALPHA,
    ChallengeCandidate,
    ValidationMetrics,
    candidate_context_summary,
    candidate_is_forecast_credible,
    candidate_selection_rank,
    market_is_basic_forecast,
    select_wettfinder_catalog,
)
from config_loader import AppConfig, load_app_config
from ev_signal_sources import (
    AUTOMATED_SELECTION_POLICY_VERSION,
    AUTOMATED_WETTFINDER_VERSION,
    MAX_AUTOMATED_FOOTBALL_CANDIDATES,
    MAX_AUTOMATED_MODEL_CANDIDATES,
    MAX_AUTOMATED_OTHER_CANDIDATES_PER_SPORT,
    MAX_AUTOMATED_RECOMMENDATIONS,
    ModelSignal,
    _validated_football_context_statuses,
    esports_signals,
    tennis_model_signals,
)
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from market_consensus import (
    MarketConsensus,
    exact_market_target,
    fetch_football_consensus,
    fetch_tennis_h2h_consensus,
    quote_matches_candidate,
    wettfinder_consensus,
    wettfinder_reference_price_status,
)


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "runtime_state" / "wettfinder_latest.json"
ZURICH_TZ = ZoneInfo("Europe/Zurich")
AUTOMATION_VERSION = AUTOMATED_WETTFINDER_VERSION
SELECTION_POLICY_VERSION = AUTOMATED_SELECTION_POLICY_VERSION
MAX_AUTOMATIC_FOOTBALL_CANDIDATES = MAX_AUTOMATED_FOOTBALL_CANDIDATES
MAX_AUTOMATIC_OTHER_CANDIDATES_PER_SPORT = (
    MAX_AUTOMATED_OTHER_CANDIDATES_PER_SPORT
)
MAX_AUTOMATIC_CANDIDATES = MAX_AUTOMATED_MODEL_CANDIDATES
MAX_AUTOMATIC_RECOMMENDATIONS = MAX_AUTOMATED_RECOMMENDATIONS
MAX_AUTOMATIC_PRICE_FIXTURES = 10
MAX_AUTOMATIC_MARKETS_PER_FIXTURE = 8
MAX_AUTOMATIC_BASIC_FORECASTS = 10
# The persisted artifact represents the currently active Zurich match day.
# Switching to tomorrow before midnight used to discard still-upcoming late
# fixtures.  A new local day is picked up naturally after midnight.
ERROR_RETRY = timedelta(minutes=25)
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


def _event_identity_name(value: object) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join(
        "".join(
            character
            if character.isalnum() and not unicodedata.combining(character)
            else " "
            for character in decomposed
        ).split()
    )


def _signal_event_identity(
    sport: str,
    signal_key: str,
    competitor_a: Optional[str],
    competitor_b: Optional[str],
    scheduled: Optional[datetime],
) -> str:
    """Stable real-event identity for persisted tennis model variants."""

    normalized_sport = _event_identity_name(sport)
    participants = sorted(
        _event_identity_name(value)
        for value in (competitor_a, competitor_b)
        if _event_identity_name(value)
    )
    if (
        normalized_sport == "tennis"
        and scheduled is not None
        and len(participants) == 2
        and participants[0] != participants[1]
    ):
        match_day = scheduled.astimezone(ZURICH_TZ).date().isoformat()
        return (
            f"tennis:{participants[0]}|{participants[1]}:"
            f"{match_day}"
        )
    return f"{str(sport or '').lower()}:{signal_key}"


def target_search_date(now: Optional[datetime] = None) -> date:
    """Return the active Zurich match day without dropping late fixtures."""
    local = _utc(now).astimezone(ZURICH_TZ)
    return local.date()


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
        return minimum_recommendation_odds(
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
    payload.pop("forecast_eligible", None)
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
    allow_basic: bool = False,
) -> Optional[dict[str, Any]]:
    if not isinstance(candidate, ChallengeCandidate):
        return None
    if not candidate_is_forecast_credible(candidate):
        return None
    is_basic_forecast = market_is_basic_forecast(candidate.market_key)
    # ``allow_basic`` remains in the call contract for older persisted
    # snapshots. The normal Wettfinder never excludes a credible forecast by
    # market name; usefulness is decided later by ranking and presentation.
    del allow_basic
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
    detail_parts = ["Fußball-Marktmodell", league]
    if isinstance(evidence_score, (int, float)) and math.isfinite(
        float(evidence_score)
    ):
        detail_parts.append(f"Evidenz {float(evidence_score):.0f}/100")
    if isinstance(spread, (int, float)) and math.isfinite(float(spread)):
        detail_parts.append(f"Modellstreuung {float(spread):.1f} PP")
    model_scope = str(_value(candidate, "model_scope") or "")
    if model_scope == "cross_competition_provisional_forecast":
        detail_parts.append("UEFA-Heimatliga-Modell in Transfer-Prüfphase")
    market_spec = MARKET_BY_KEY.get(str(_value(candidate, "market_key") or ""))
    validation = candidate.validation
    return {
        "key": f"wettfinder-football-{candidate_id}",
        "candidate_id": candidate_id,
        "fixture_id": _value(candidate, "fixture_id"),
        "league_id": _value(candidate, "league_id"),
        "home_team": home,
        "away_team": away,
        "market_key": _value(candidate, "market_key"),
        "sport": "Fußball",
        "event": event,
        "event_identity": f"football:{_value(candidate, 'fixture_id')}",
        "label": f"Fußball - {event} - {market}: {selection}",
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
        "model_scope": model_scope,
        "market_kind": market_spec.kind if market_spec is not None else "other",
        "is_basic_forecast": is_basic_forecast,
        "selection_rank": list(candidate_selection_rank(candidate)),
        "statistical_release_passed": (
            validation.statistical_release_passed is True
        ),
        "paired_loss_mean": validation.paired_loss_mean,
        "paired_loss_hac_standard_error": (
            validation.paired_loss_hac_standard_error
        ),
        "paired_loss_lower_confidence_bound": (
            validation.paired_loss_lower_confidence_bound
        ),
        "paired_loss_p_value": validation.paired_loss_p_value,
        "fdr_q_value": validation.fdr_q_value,
        "tested_hypotheses": validation.tested_hypotheses,
        "context_summary": candidate_context_summary(candidate),
        "context": dict(candidate.context),
        "context_checked_at": (
            _utc(context_checked_at).isoformat()
            if context_checked_at is not None
            else None
        ),
    }


def _first_present_candidate_list(
    payload: object,
    *field_names: str,
) -> list:
    """Use the first present schema field; an explicit empty list is final."""

    if not isinstance(payload, dict):
        return []
    for field_name in field_names:
        if field_name not in payload:
            continue
        value = payload.get(field_name)
        return list(value) if isinstance(value, (list, tuple)) else []
    return []


def _merged_candidate_lists(
    payload: object,
    *field_names: str,
) -> list:
    """Merge compatible candidate pools without losing later alternatives.

    The engine exposes a compact forecast shortlist as well as a richer price
    pool.  Persisting only the first field made other credible markets from
    the same fixture disappear before the quote provider could inspect them.
    """

    if not isinstance(payload, dict):
        return []
    merged: list = []
    seen: set[str] = set()
    for field_name in field_names:
        values = payload.get(field_name)
        if not isinstance(values, (list, tuple)):
            continue
        for candidate in values:
            identity = str(
                _value(candidate, "candidate_id")
                or _value(candidate, "key")
                or ""
            ).strip()
            if not identity or identity in seen:
                continue
            seen.add(identity)
            merged.append(candidate)
    return merged


def _wettfinder_candidates_from_snapshot(payload: object) -> list[ChallengeCandidate]:
    """Recover the richest normal-Wettfinder pool from scan schemas."""

    raw_candidates = _merged_candidate_lists(
        payload,
        "wettfinder_candidates",
        "candidates",
        "forecast_shortlist",
        "model_shortlist",
        "basis_forecasts",
        "price_candidates",
        "shortlist",
        "base_shortlist",
    )
    return select_wettfinder_catalog(
        (
            candidate
            for candidate in raw_candidates
            if isinstance(candidate, ChallengeCandidate)
        ),
        max_candidates=None,
    )


def _football_record_selection_rank(row: object) -> Optional[tuple[float, ...]]:
    if not isinstance(row, dict):
        return None
    raw = row.get("selection_rank")
    if not isinstance(raw, (list, tuple)) or len(raw) != 6:
        return None
    values: list[float] = []
    for value in raw:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            return None
        values.append(float(value))
    return tuple(values)


def _select_football_record_catalog(
    rows: Iterable[dict[str, Any]],
    *,
    limit: int = MAX_AUTOMATIC_FOOTBALL_CANDIDATES,
) -> list[dict[str, Any]]:
    """Rebuild the soft-diverse catalog after a context refresh."""

    records = [dict(row) for row in rows if isinstance(row, dict)]
    if not records:
        return []
    ranked_rows = [
        (rank, row)
        for row in records
        if (rank := _football_record_selection_rank(row)) is not None
    ]
    # Old in-memory records are never mixed into the new schema in
    # production, but preserving their order keeps the helper fail-safe.
    if len(ranked_rows) != len(records):
        return records[:limit]
    ranked_rows.sort(
        key=lambda item: (
            *(-value for value in item[0]),
            str(item[1].get("key") or ""),
        )
    )
    ranked = [row for _rank, row in ranked_rows]
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    fixture_counts: dict[str, int] = {}

    def add(row: dict[str, Any]) -> bool:
        key = str(row.get("key") or "").strip()
        event = str(row.get("event_identity") or key).strip()
        if not key or key in selected_keys or not event:
            return False
        if fixture_counts.get(event, 0) >= MAX_AUTOMATIC_MARKETS_PER_FIXTURE:
            return False
        selected.append(row)
        selected_keys.add(key)
        fixture_counts[event] = fixture_counts.get(event, 0) + 1
        return True

    for row in ranked:
        add(row)
        if len(selected) >= limit:
            break
    return selected


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
    competitor_a = str(
        getattr(signal, "competitor_a", None) or ""
    ).strip() or None
    competitor_b = str(
        getattr(signal, "competitor_b", None) or ""
    ).strip() or None
    selected_competitor = str(
        getattr(signal, "selected_competitor", None) or ""
    ).strip() or None
    competition = str(
        getattr(signal, "competition", None) or ""
    ).strip() or None
    return {
        "key": signal.key,
        "candidate_id": signal.key,
        "sport": sport,
        "event": event_label,
        "event_identity": _signal_event_identity(
            sport,
            signal.key,
            competitor_a,
            competitor_b,
            scheduled,
        ),
        "label": signal.label,
        "market": market,
        "market_key": (
            "H2H"
            if all((competitor_a, competitor_b, selected_competitor))
            else None
        ),
        "selection": selection,
        "competitor_a": competitor_a,
        "competitor_b": competitor_b,
        "selected_competitor": selected_competitor,
        "competition": competition,
        "probability": probability,
        "probability_haircut": haircut,
        "conservative_probability": conservative,
        "minimum_odds": minimum_odds,
        "evidence_stage": signal.evidence_stage,
        "policy_version": signal.policy_version,
        "scheduled_start": scheduled.isoformat() if scheduled else None,
        "status": "PRICE_REQUIRED",
        "reference_price_status": "UNAVAILABLE",
        "source": "tennis_shadow" if sport == "Tennis" else "esports_shadow",
        "detail": signal.detail,
        "context_summary": signal.context_summary,
    }


def _ranked_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
    preserve_order: bool = False,
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

    if not preserve_order:
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
    limit: int = MAX_AUTOMATIC_RECOMMENDATIONS,
    preserve_order: bool = False,
) -> list[dict[str, Any]]:
    """Select one validated market per event, optionally preserving order."""
    valid = _ranked_candidates(
        candidates,
        now=now,
        target_date=target_date,
        preserve_order=preserve_order,
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


def select_catalog_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
    limit: int = MAX_AUTOMATIC_CANDIDATES,
    preserve_order: bool = False,
) -> list[dict[str, Any]]:
    """Keep distinct credible markets; fixture deduplication is UI-only.

    Variants that describe the exact same market and selection are collapsed,
    while a second genuinely different market from one fixture remains in the
    forecast catalog for price checking and the secondary UI section.
    """

    valid = _ranked_candidates(
        candidates,
        now=now,
        target_date=target_date,
        preserve_order=preserve_order,
    )
    selected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_markets: set[tuple[str, str, str]] = set()
    fixture_counts: dict[str, int] = {}
    for row in valid:
        key = str(row.get("key") or "").strip()
        event = str(row.get("event_identity") or key).strip()
        market = str(row.get("market_key") or row.get("market") or "").strip()
        selection = str(row.get("selection") or "").strip().casefold()
        market_identity = (event, market.casefold(), selection)
        if (
            not key
            or not event
            or key in seen_keys
            or market_identity in seen_markets
            or fixture_counts.get(event, 0)
            >= MAX_AUTOMATIC_MARKETS_PER_FIXTURE
        ):
            continue
        seen_keys.add(key)
        seen_markets.add(market_identity)
        fixture_counts[event] = fixture_counts.get(event, 0) + 1
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def build_model_selection_ledger(
    strict_rows: Iterable[dict[str, Any]],
    forecast_rows: Iterable[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
    limit: int = MAX_AUTOMATIC_CANDIDATES,
) -> list[dict[str, Any]]:
    """Build the maximum-N display ledger independently of bookmaker price.

    Strict rows are accepted for the existing call contract, but cannot affect
    model ranking. A weaker PLAYABLE price must never hide a stronger forecast
    whose quote is missing or below the price threshold.
    """

    del strict_rows
    forecast_list = [
        dict(row) for row in forecast_rows if isinstance(row, dict)
    ]
    ledger = [
        dict(row)
        for row in select_catalog_candidates(
            forecast_list,
            now=now,
            target_date=target_date,
            limit=limit,
            preserve_order=True,
        )
    ]
    for row in ledger:
        row["status"] = "MODEL_SELECTION"
    return ledger


def build_daily_forecast_catalog(
    football_rows: Iterable[dict[str, Any]],
    other_rows: Iterable[dict[str, Any]],
    *,
    football_basis_rows: Iterable[dict[str, Any]] = (),
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
) -> list[dict[str, Any]]:
    """Reserve catalog space for football and each validated other sport."""

    football_catalog = select_catalog_candidates(
        football_rows,
        now=now,
        target_date=target_date,
        limit=MAX_AUTOMATIC_FOOTBALL_CANDIDATES,
        preserve_order=True,
    )
    football_keys = {
        str(row.get("key") or "").strip()
        for row in football_catalog
        if str(row.get("key") or "").strip()
    }
    basis_catalog: list[dict[str, Any]] = []
    for row in _ranked_candidates(
        football_basis_rows,
        now=now,
        target_date=target_date,
        preserve_order=True,
    ):
        key = str(row.get("key") or "").strip()
        if (
            not key
            or key in football_keys
            or row.get("is_basic_forecast") is not True
        ):
            continue
        football_keys.add(key)
        basis_catalog.append(row)
        if (
            len(football_catalog) + len(basis_catalog)
            >= MAX_AUTOMATIC_FOOTBALL_CANDIDATES
        ):
            break
    grouped_other: dict[str, list[dict[str, Any]]] = {}
    for row in other_rows:
        if not isinstance(row, dict):
            continue
        sport = str(row.get("sport") or "").strip()
        if not sport:
            continue
        grouped_other.setdefault(sport, []).append(row)
    other_catalog: list[dict[str, Any]] = []
    for rows in grouped_other.values():
        other_catalog.extend(
            select_catalog_candidates(
                rows,
                now=now,
                target_date=target_date,
                limit=MAX_AUTOMATIC_OTHER_CANDIDATES_PER_SPORT,
                preserve_order=True,
            )
        )
    return [*football_catalog, *basis_catalog, *other_catalog]


def select_price_check_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
    max_fixtures: int = MAX_AUTOMATIC_PRICE_FIXTURES,
    max_markets_per_fixture: int = MAX_AUTOMATIC_MARKETS_PER_FIXTURE,
    preserve_order: bool = False,
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
        preserve_order=preserve_order,
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
    discovery_values = _first_present_candidate_list(
        snapshot,
        "discovery_candidates",
        "base_shortlist",
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
            for candidate in _wettfinder_candidates_from_snapshot(snapshot)
        )
        if record is not None
    ]
    records = _select_football_record_catalog(records)
    record_ids = {
        str(record.get("candidate_id") or "").strip()
        for record in records
        if str(record.get("candidate_id") or "").strip()
    }
    basis_records = [
        record
        for record in (
            _football_candidate_record(
                candidate,
                context_checked_at=scanned_at,
                allow_basic=True,
            )
            for candidate in _first_present_candidate_list(
                snapshot,
                "basis_forecasts",
            )
        )
        if record is not None
        and record.get("is_basic_forecast") is True
        and str(record.get("candidate_id") or "").strip() not in record_ids
    ]
    basis_records = _select_football_record_catalog(
        basis_records,
        limit=MAX_AUTOMATIC_BASIC_FORECASTS,
    )
    errors = [
        str(error)
        for error in (snapshot.get("errors") or [])
        if str(error).strip()
    ][:20]
    fixtures_found = int(snapshot.get("fixtures_found") or 0)
    operational_values = snapshot.get("operational_errors")
    if isinstance(operational_values, list):
        operational_errors = [
            str(error) for error in operational_values if str(error).strip()
        ]
    else:
        operational_errors = [
            error
            for error in errors
            if not (
                error.startswith("xG Liga ")
                and "Tormodell dominant" in error
            )
        ]
    degraded = bool(operational_errors) or (fixtures_found == 0 and bool(errors))
    context_fixture_statuses = snapshot.get("context_fixture_statuses")
    context_accounting_available = isinstance(
        context_fixture_statuses,
        dict,
    ) and all(
        key in snapshot
        for key in (
            "base_fixture_count",
            "context_verified_fixtures",
            "context_data_incomplete_fixtures",
            "context_unchecked_fixtures",
            "deferred_context_fixtures",
            "context_scope_complete",
        )
    )
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
        "base_fixture_count": int(snapshot.get("base_fixture_count") or 0),
        "context_fixtures": int(snapshot.get("context_fixtures") or 0),
        "context_verified_fixtures": int(
            snapshot.get("context_verified_fixtures") or 0
        ),
        "context_data_incomplete_fixtures": int(
            snapshot.get("context_data_incomplete_fixtures") or 0
        ),
        "context_unchecked_fixtures": int(
            snapshot.get("context_unchecked_fixtures") or 0
        ),
        "deferred_context_fixtures": int(
            snapshot.get("deferred_context_fixtures") or 0
        ),
        "context_scope_complete": snapshot.get("context_scope_complete") is True,
        "context_fixture_statuses": (
            dict(context_fixture_statuses)
            if context_accounting_available
            else {}
        ),
        "context_accounting_available": context_accounting_available,
        "discovery_operational_error_count": len(operational_errors),
        "context_operational_error_count": 0,
        "operational_error_count": len(operational_errors),
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
        "basis_candidates": basis_records,
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
    discovery_error_count = max(
        int(state.get("discovery_operational_error_count") or 0),
        1,
    )
    context_error_count = int(state.get("context_operational_error_count") or 0)
    state["discovery_operational_error_count"] = discovery_error_count
    state["context_operational_error_count"] = context_error_count
    state["operational_error_count"] = discovery_error_count + context_error_count
    state.setdefault("fixture_kickoffs", [])
    state.setdefault("discovery_candidates", [])
    state.setdefault("discovery_candidate_count", 0)
    state.setdefault("context_checks", {})
    state.setdefault("candidates", [])
    state.setdefault("basis_candidates", [])
    state.setdefault("fixtures_found", 0)
    state.setdefault("fixtures_modeled", 0)
    state.setdefault("base_candidates", 0)
    state.setdefault("base_fixture_count", 0)
    state.setdefault("context_fixtures", 0)
    state.setdefault("context_verified_fixtures", 0)
    state.setdefault("context_data_incomplete_fixtures", 0)
    state.setdefault("context_unchecked_fixtures", 0)
    state.setdefault("deferred_context_fixtures", 0)
    state.setdefault("context_scope_complete", False)
    state.setdefault("context_fixture_statuses", {})
    state.setdefault("context_accounting_available", False)
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
    existing_records = [
        row for row in (state.get("candidates") or []) if isinstance(row, dict)
    ]
    refreshed_candidates = _wettfinder_candidates_from_snapshot(result)
    new_records = [
        record
        for record in (
            _football_candidate_record(
                candidate,
                context_checked_at=checked_at,
            )
            for candidate in refreshed_candidates
        )
        if record is not None
    ]
    existing_basis_records = [
        row
        for row in (state.get("basis_candidates") or [])
        if isinstance(row, dict)
    ]
    refreshed_basis_candidates = _first_present_candidate_list(
        result,
        "basis_forecasts",
    )
    new_basis_records = [
        record
        for record in (
            _football_candidate_record(
                candidate,
                context_checked_at=checked_at,
                allow_basic=True,
            )
            for candidate in refreshed_basis_candidates
        )
        if record is not None and record.get("is_basic_forecast") is True
    ]
    new_by_fixture: dict[int, list[dict[str, Any]]] = {}
    for record in new_records:
        fixture_id = record.get("fixture_id")
        if isinstance(fixture_id, int) and not isinstance(fixture_id, bool):
            new_by_fixture.setdefault(fixture_id, []).append(record)
    merged_records: list[dict[str, Any]] = []
    replaced_fixtures: set[int] = set()
    for record in existing_records:
        fixture_id = record.get("fixture_id")
        if fixture_id not in allowed:
            merged_records.append(record)
            continue
        if (
            isinstance(fixture_id, int)
            and fixture_id not in replaced_fixtures
        ):
            merged_records.extend(new_by_fixture.get(fixture_id, []))
            replaced_fixtures.add(fixture_id)
    for fixture_id in fixture_ids:
        if fixture_id not in replaced_fixtures:
            merged_records.extend(new_by_fixture.get(fixture_id, []))
            replaced_fixtures.add(fixture_id)
    merged_records = _select_football_record_catalog(merged_records)
    new_basis_by_fixture: dict[int, list[dict[str, Any]]] = {}
    for record in new_basis_records:
        fixture_id = record.get("fixture_id")
        if isinstance(fixture_id, int) and not isinstance(fixture_id, bool):
            new_basis_by_fixture.setdefault(fixture_id, []).append(record)
    merged_basis_records: list[dict[str, Any]] = []
    replaced_basis_fixtures: set[int] = set()
    for record in existing_basis_records:
        fixture_id = record.get("fixture_id")
        if fixture_id not in allowed:
            merged_basis_records.append(record)
            continue
        if (
            isinstance(fixture_id, int)
            and fixture_id not in replaced_basis_fixtures
        ):
            merged_basis_records.extend(
                new_basis_by_fixture.get(fixture_id, [])
            )
            replaced_basis_fixtures.add(fixture_id)
    for fixture_id in fixture_ids:
        if fixture_id not in replaced_basis_fixtures:
            merged_basis_records.extend(
                new_basis_by_fixture.get(fixture_id, [])
            )
            replaced_basis_fixtures.add(fixture_id)
    merged_basis_records = _select_football_record_catalog(
        merged_basis_records,
        limit=MAX_AUTOMATIC_BASIC_FORECASTS,
    )
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
    previous_statuses = state.get("context_fixture_statuses")
    result_statuses = result.get("context_fixture_statuses")
    accounting_available = (
        state.get("context_accounting_available") is True
        and isinstance(previous_statuses, dict)
        and isinstance(result_statuses, dict)
    )
    if accounting_available:
        merged_statuses = dict(previous_statuses)
        merged_statuses.update(
            {
                str(fixture_id): status
                for fixture_id, status in result_statuses.items()
                if str(fixture_id).isdigit()
                and status
                in {"verified", "data_incomplete", "unchecked", "deferred"}
            }
        )
        context_verified = sum(
            status == "verified" for status in merged_statuses.values()
        )
        context_incomplete = sum(
            status == "data_incomplete" for status in merged_statuses.values()
        )
        context_unchecked = sum(
            status == "unchecked" for status in merged_statuses.values()
        )
        context_deferred = sum(
            status == "deferred" for status in merged_statuses.values()
        )
        context_scope_complete = bool(merged_statuses) and all(
            status == "verified" for status in merged_statuses.values()
        )
    else:
        merged_statuses = {}
        context_verified = 0
        context_incomplete = 0
        context_unchecked = 0
        context_deferred = 0
        context_scope_complete = False

    refresh_operational_errors = result.get("operational_errors")
    refresh_operational_error_count = (
        len(refresh_operational_errors)
        if isinstance(refresh_operational_errors, list)
        else 0
    )
    previous_total_errors = int(state.get("operational_error_count") or 0)
    discovery_operational_error_count = int(
        state.get("discovery_operational_error_count")
        or (
            previous_total_errors
            if state.get("status") == "degraded"
            and not state.get("last_discovery_at")
            else 0
        )
    )
    total_operational_error_count = (
        discovery_operational_error_count + refresh_operational_error_count
    )
    refreshed.update(
        {
            "last_context_at": checked_at.isoformat(),
            "context_checks": checks,
            "candidates": merged_records,
            "basis_candidates": merged_basis_records,
            "approved_candidates": len(merged_records),
            "last_blocked_counts": dict(result.get("blocked_counts") or {}),
            "errors": list(dict.fromkeys(errors))[-20:],
            "base_fixture_count": len(merged_statuses),
            "context_fixtures": context_verified + context_incomplete,
            "context_verified_fixtures": context_verified,
            "context_data_incomplete_fixtures": context_incomplete,
            "context_unchecked_fixtures": context_unchecked,
            "deferred_context_fixtures": context_deferred,
            "context_scope_complete": context_scope_complete,
            "context_fixture_statuses": merged_statuses,
            "context_accounting_available": accounting_available,
            "discovery_operational_error_count": (
                discovery_operational_error_count
            ),
            "context_operational_error_count": refresh_operational_error_count,
            "operational_error_count": total_operational_error_count,
            "status": (
                "completed"
                if accounting_available
                and context_scope_complete
                and total_operational_error_count == 0
                else "degraded"
                if total_operational_error_count > 0
                else state.get("status", "completed")
            ),
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
    valid = _ranked_candidates(
        fresh,
        now=current,
        target_date=target_date,
        preserve_order=True,
    )
    return _select_football_record_catalog(valid)


def _active_football_basis_candidates(
    state: object,
    *,
    now: datetime,
    target_date: date,
) -> list[dict[str, Any]]:
    if not isinstance(state, dict):
        return []
    current = _utc(now)
    fresh: list[dict[str, Any]] = []
    for row in state.get("basis_candidates") or []:
        if not isinstance(row, dict) or row.get("is_basic_forecast") is not True:
            continue
        checked = _parse_iso(row.get("context_checked_at"))
        if (
            checked is None
            or current - checked < timedelta(0)
            or current - checked > FOOTBALL_CONTEXT_MAX_AGE
        ):
            continue
        fresh.append(row)
    valid = _ranked_candidates(
        fresh,
        now=current,
        target_date=target_date,
        preserve_order=True,
    )
    return _select_football_record_catalog(
        valid,
        limit=MAX_AUTOMATIC_BASIC_FORECASTS,
    )


def _persisted_football_records(
    state: object,
    *,
    field_name: str,
    now: datetime,
    target_date: date,
    limit: int,
    basic_only: bool,
) -> list[dict[str, Any]]:
    """Keep valid future same-day models visible beyond the context TTL."""
    if (
        not isinstance(state, dict)
        or state.get("search_date") != target_date.isoformat()
    ):
        return []
    current = _utc(now)
    valid = _ranked_candidates(
        (
            row
            for row in (state.get(field_name) or [])
            if isinstance(row, dict)
            and (
                row.get("is_basic_forecast") is True
                if basic_only
                else True
            )
        ),
        now=current,
        target_date=target_date,
        preserve_order=True,
    )
    selected = _select_football_record_catalog(valid, limit=limit)
    result: list[dict[str, Any]] = []
    for raw in selected:
        row = dict(raw)
        checked = _parse_iso(row.get("context_checked_at"))
        context_fresh = (
            checked is not None
            and timedelta(0) <= current - checked <= FOOTBALL_CONTEXT_MAX_AGE
        )
        context = row.get("context")
        context = context if isinstance(context, dict) else {}
        release_complete = context.get("release_context_complete")
        row["context_complete"] = context_fresh and (
            release_complete is True
            if isinstance(release_complete, bool)
            else True
        )
        row["context_stale"] = not context_fresh
        if not context_fresh:
            existing_summary = str(row.get("context_summary") or "").strip()
            stale_note = (
                "Kontextprüfung veraltet; vor einer Freigabe ist eine "
                "Aktualisierung nötig."
            )
            row["context_summary"] = " - ".join(
                part for part in (existing_summary, stale_note) if part
            )[:300]
        result.append(row)
    return result


def _football_record_release_eligible(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    context = row.get("context")
    evidence_values = tuple(
        row.get(field)
        for field in (
            "paired_loss_mean",
            "paired_loss_hac_standard_error",
            "paired_loss_lower_confidence_bound",
            "paired_loss_p_value",
            "fdr_q_value",
        )
    )
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in evidence_values
    ):
        return False
    mean_advantage, standard_error, lower_bound, p_value, q_value = (
        float(value) for value in evidence_values
    )
    return (
        isinstance(context, dict)
        and context.get("release_context_complete") is True
        and context.get("release_eligible") is True
        and row.get("model_scope") == MODEL_SCOPE_SAME_COMPETITION
        and row.get("context_stale") is not True
        and row.get("statistical_release_passed") is True
        and row.get("tested_hypotheses") == len(MARKET_SPECS)
        and -1.0 <= mean_advantage <= 1.0
        and 0.0 <= standard_error <= 1.0
        and 0.0 < lower_bound <= mean_advantage + 1e-9
        and 0.0 <= p_value <= q_value + 1e-9
        and q_value <= VALIDATION_FDR_ALPHA
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
        allow_above_challenge_probability=True,
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
        max_candidates=15,
    )


def _apply_reference_quotes(
    model_rows: list[dict[str, Any]],
    price_rows: list[dict[str, Any]],
    quotes: dict[str, MarketConsensus],
    *,
    now: datetime,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Attach only freshly fetched exact prices without altering forecasts."""
    execution_fields = (
        "reference_quote_source",
        "reference_quote_executable_odds",
        "reference_quote_bookmaker",
        "reference_quote_bookmaker_id",
        "reference_quote_observed_at",
    )

    def clear_execution(target: dict[str, Any]) -> None:
        for field in execution_fields:
            target.pop(field, None)

    def persist_execution(
        target: dict[str, Any],
        quote: MarketConsensus,
        status,
    ) -> None:
        target["reference_quote_source"] = quote.source
        target["reference_quote_executable_odds"] = status.usable_odds
        target["reference_quote_bookmaker"] = status.bookmaker
        target["reference_quote_bookmaker_id"] = status.bookmaker_id
        target["reference_quote_observed_at"] = status.observed_at

    model_by_id = {
        str(row.get("candidate_id") or "").strip(): row
        for row in model_rows
        if str(row.get("candidate_id") or "").strip()
    }
    for row in model_rows:
        row.pop("reference_quote", None)
        row.pop("quote_provider_event_id", None)
        clear_execution(row)
        row["reference_price_status"] = "UNAVAILABLE"

    status_counts: dict[str, int] = {}
    playable: list[dict[str, Any]] = []
    for row in price_rows:
        clear_execution(row)
        candidate_id = str(row.get("candidate_id") or "").strip()
        model_row = model_by_id.get(candidate_id)
        raw_quote = quotes.get(candidate_id)
        if not quote_matches_candidate(raw_quote, row):
            status_code = "UNAVAILABLE"
            row.pop("reference_quote", None)
        else:
            quote = wettfinder_consensus(raw_quote, now=now) or raw_quote
            quotes[candidate_id] = quote
            row["reference_quote"] = quote.to_dict()
            if quote.provider_event_id:
                row["quote_provider_event_id"] = quote.provider_event_id
            if model_row is not None:
                model_row["reference_quote"] = row["reference_quote"]
                if quote.provider_event_id:
                    model_row["quote_provider_event_id"] = (
                        quote.provider_event_id
                    )
            status = wettfinder_reference_price_status(
                quote,
                row.get("minimum_odds"),
                candidate=row,
                now=now,
            )
            status_code = status.code
            if status_code == "PLAYABLE":
                persist_execution(row, quote, status)
                if model_row is not None:
                    persist_execution(model_row, quote, status)
        row["reference_price_status"] = status_code
        if model_row is not None:
            model_row["reference_price_status"] = status_code
        status_counts[status_code] = status_counts.get(status_code, 0) + 1
        if status_code == "PLAYABLE":
            playable.append(row)
    return status_counts, playable


def _safe_quote_loader_error(exc: Exception) -> list[str]:
    """Return a persistable provider error without exception details."""
    return [f"Quotenabruf fehlgeschlagen ({type(exc).__name__})"]


def _operational_quote_errors(errors: Iterable[object]) -> list[str]:
    """Separate provider failures from normal market/coverage absence."""

    unavailable_markers = (
        "keine aktive tennis-konkurrenz",
        "zu viele aktive tennis-konkurrenzen",
        "keine eindeutige turnierzuordnung",
        "keinem aktiven provider-sportkey eindeutig zugeordnet",
        "turnierzuordnung ueberschreitet das sichere requestlimit",
        "ereignis nicht eindeutig",
    )
    operational: list[str] = []
    for raw in errors:
        message = str(raw).strip()
        if not message:
            continue
        normalized = message.casefold()
        if any(marker in normalized for marker in unavailable_markers):
            continue
        operational.append(message)
    return list(dict.fromkeys(operational))


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
    tennis_quote_loader: Optional[
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
    if previous and (
        previous.get("version") != AUTOMATION_VERSION
        or previous.get("betting_policy_version") != BETTING_POLICY_VERSION
        or previous.get("selection_policy_version") != SELECTION_POLICY_VERSION
    ):
        due = FootballDueDecision(True, "recommendation_policy_changed")
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
            discovery_error_count = int(
                football_state.get("discovery_operational_error_count") or 0
            )
            context_error_count = int(
                football_state.get("context_operational_error_count") or 0
            ) + 1
            football_state["discovery_operational_error_count"] = (
                discovery_error_count
            )
            football_state["context_operational_error_count"] = (
                context_error_count
            )
            football_state["operational_error_count"] = (
                discovery_error_count + context_error_count
            )
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
                football_state["status"] = "degraded"
                discovery_error_count = int(
                    football_state.get("discovery_operational_error_count") or 0
                )
                context_error_count = int(
                    football_state.get("context_operational_error_count") or 0
                ) + 1
                football_state["discovery_operational_error_count"] = (
                    discovery_error_count
                )
                football_state["context_operational_error_count"] = (
                    context_error_count
                )
                football_state["operational_error_count"] = (
                    discovery_error_count + context_error_count
                )
                football_state["errors"] = list(
                    dict.fromkeys(
                        list(football_state.get("errors") or [])
                        + [f"Context {type(exc).__name__}: {exc}"[:500]]
                    )
                )[-20:]

    if not fixed_now:
        current = _utc(runtime_clock())

    active_football_rows: list[dict[str, Any]] = _active_football_candidates(
        football_state,
        now=current,
        target_date=target,
    )
    active_football_basis_rows = _active_football_basis_candidates(
        football_state,
        now=current,
        target_date=target,
    )
    persisted_football_rows = _persisted_football_records(
        football_state,
        field_name="candidates",
        now=current,
        target_date=target,
        limit=MAX_AUTOMATIC_FOOTBALL_CANDIDATES,
        basic_only=False,
    )
    persisted_football_basis_rows = _persisted_football_records(
        football_state,
        field_name="basis_candidates",
        now=current,
        target_date=target,
        limit=MAX_AUTOMATIC_BASIC_FORECASTS,
        basic_only=True,
    )
    context_statuses = _validated_football_context_statuses(football_state)
    # A partial league scan must not erase a candidate whose own model and
    # context record are complete.  Such rows remain model selections only;
    # the strict priced-signal reader still blocks a degraded football run.
    football_forecast_rows = (
        []
        if context_statuses is None
        else [
            row
            for row in persisted_football_rows
            if context_statuses.get(str(row.get("fixture_id"))) == "verified"
        ]
    )
    football_basis_forecast_rows = (
        []
        if context_statuses is None
        else [
            row
            for row in persisted_football_basis_rows
            if context_statuses.get(str(row.get("fixture_id"))) == "verified"
        ]
    )
    source_rows: list[dict[str, Any]] = [
        *football_forecast_rows,
        *football_basis_forecast_rows,
    ]
    source_status: dict[str, dict[str, Any]] = {
        "football": {
            "status": football_state.get("status", "idle"),
            "due_reason": "forced" if force_football else due.reason,
            "discovery_scope": len(ALTERNATIVE_MARKET_LEAGUES),
            "context_status": context_status,
            "context_fixture_count": len(context_fixture_ids),
            "candidate_count": (
                len(football_forecast_rows)
                + len(football_basis_forecast_rows)
            ),
            "basis_candidate_count": len(football_basis_forecast_rows),
            "stale_context_candidate_count": sum(
                row.get("context_stale") is True
                for row in (
                    *football_forecast_rows,
                    *football_basis_forecast_rows,
                )
            ),
            "search_date": target.isoformat(),
            "operational_error_count": int(
                football_state.get("operational_error_count") or 0
            ),
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
                "operational_error_count": 0,
            }
        except Exception as exc:
            source_status[source_name] = {
                "status": "degraded",
                "candidate_count": 0,
                "operational_error_count": 1,
                "error": f"{type(exc).__name__}: {exc}"[:500],
            }

    source_status["basketball"] = {
        "status": "live_only_no_prematch_model",
        "candidate_count": 0,
        "operational_error_count": 0,
    }
    source_status["ice_hockey"] = {
        "status": "live_only_no_prematch_model",
        "candidate_count": 0,
        "operational_error_count": 0,
    }
    source_status["cricket"] = {
        "status": "blocked_no_validated_model",
        "candidate_count": 0,
        "operational_error_count": 0,
    }

    football_model_rows = [
        row
        for row in source_rows
        if row.get("source") == "football_challenge"
        and isinstance(row.get("fixture_id"), int)
        and not isinstance(row.get("fixture_id"), bool)
        and row["fixture_id"] > 0
        and str(row.get("market_key") or "").strip()
    ]
    # Every valid model row stays visible even when its exact bookmaker market
    # cannot be mapped. Only the separate quote pools may reach providers.
    football_price_rows = select_price_check_candidates(
        (
            row
            for row in football_model_rows
            if exact_market_target(row.get("market_key")) is not None
        ),
        now=current,
        target_date=target,
        preserve_order=True,
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
            quote_errors = _safe_quote_loader_error(exc)
    if not fixed_now:
        current = _utc(runtime_clock())
    football_price_by_id = {
        str(row.get("candidate_id") or "").strip(): row
        for row in football_price_rows
        if str(row.get("candidate_id") or "").strip()
    }
    reference_quotes = {
        candidate_id: quote
        for candidate_id, quote in reference_quotes.items()
        if quote_matches_candidate(
            quote,
            football_price_by_id.get(candidate_id),
        )
    }
    football_price_status_counts, football_playable_rows = (
        _apply_reference_quotes(
            football_model_rows,
            football_price_rows,
            reference_quotes,
            now=current,
        )
    )

    tennis_model_rows = [
        row for row in source_rows if row.get("source") == "tennis_shadow"
    ]
    tennis_price_rows = select_price_check_candidates(
        (
            row
            for row in tennis_model_rows
            if row.get("market_key") == "H2H"
            and all(
                str(row.get(field) or "").strip()
                for field in (
                    "competitor_a",
                    "competitor_b",
                    "selected_competitor",
                )
            )
        ),
        now=current,
        target_date=target,
        preserve_order=True,
    )
    tennis_quote_errors: list[str] = []
    tennis_reference_quotes: dict[str, MarketConsensus] = {}
    if tennis_price_rows:
        try:
            if tennis_quote_loader is not None:
                tennis_reference_quotes, tennis_quote_errors = (
                    tennis_quote_loader(tennis_price_rows)
                )
            else:
                app_config = config or load_app_config()
                if app_config.odds_api_key:
                    tennis_reference_quotes, tennis_quote_errors = (
                        fetch_tennis_h2h_consensus(
                            app_config.odds_api_key,
                            tennis_price_rows,
                            now=current,
                        )
                    )
        except Exception as exc:
            tennis_quote_errors = _safe_quote_loader_error(exc)
    if tennis_price_rows and not fixed_now:
        current = _utc(runtime_clock())
    tennis_price_by_id = {
        str(row.get("candidate_id") or "").strip(): row
        for row in tennis_price_rows
        if str(row.get("candidate_id") or "").strip()
    }
    tennis_reference_quotes = {
        candidate_id: quote
        for candidate_id, quote in tennis_reference_quotes.items()
        if quote_matches_candidate(
            quote,
            tennis_price_by_id.get(candidate_id),
        )
    }
    tennis_price_status_counts, tennis_playable_rows = (
        _apply_reference_quotes(
            tennis_model_rows,
            tennis_price_rows,
            tennis_reference_quotes,
            now=current,
        )
    )

    esports_model_rows = [
        row for row in source_rows if row.get("source") == "esports_shadow"
    ]
    for row in esports_model_rows:
        row.pop("reference_quote", None)
        row["reference_price_status"] = "UNAVAILABLE"

    # Preserve every model result independently of bookmaker price. A missing
    # football, tennis or E-sport quote only prevents strict playability; it
    # never removes or reorders the forecast.
    non_football_rows = [
        row
        for row in source_rows
        if row.get("source") != "football_challenge"
    ]
    football_run_publishable = (
        football_state.get("status") == "completed"
        and int(football_state.get("operational_error_count") or 0) == 0
        and context_statuses is not None
    )
    football_release_candidate_ids = {
        str(row.get("candidate_id") or "").strip()
        for row in active_football_rows
        if str(row.get("candidate_id") or "").strip()
        and context_statuses is not None
        and context_statuses.get(str(row.get("fixture_id"))) == "verified"
        and _football_record_release_eligible(row)
    }
    # The model catalog is independent of bookmaker price. The first three
    # remain the compact featured block; additional eligible forecasts stay
    # available instead of being discarded.
    forecast_catalog = build_daily_forecast_catalog(
        football_model_rows,
        non_football_rows,
        now=current,
        target_date=target,
    )
    playable_rows = [
        *(
            [
                row
                for row in football_playable_rows
                if str(row.get("candidate_id") or "").strip()
                in football_release_candidate_ids
            ]
            if football_run_publishable
            else []
        ),
        *tennis_playable_rows,
    ]
    model_candidates = build_model_selection_ledger(
        playable_rows,
        forecast_catalog,
        now=current,
        target_date=target,
        limit=MAX_AUTOMATIC_CANDIDATES,
    )
    visible_keys = {
        str(row.get("key") or "").strip()
        for row in model_candidates
        if str(row.get("key") or "").strip()
    }
    # A strict signal may only annotate one of those visible forecasts. Price
    # can enable an action or stake, but never change the displayed catalog.
    playable_by_key = {
        str(row.get("key") or "").strip(): row
        for row in playable_rows
        if str(row.get("key") or "").strip()
    }
    candidates = select_candidates(
        (
            playable_by_key[key]
            for key in (
                str(row.get("key") or "").strip()
                for row in model_candidates
            )
            if key in visible_keys
            and key in playable_by_key
            and (
                playable_by_key[key].get("source") != "football_challenge"
                or football_run_publishable
            )
        ),
        now=current,
        target_date=target,
        limit=MAX_AUTOMATIC_RECOMMENDATIONS,
        preserve_order=True,
    )
    for row in candidates:
        row["status"] = "RECOMMENDED"
    if isinstance(source_status.get("football"), dict):
        football_quote_error_count = len(_operational_quote_errors(quote_errors))
        source_status["football"]["quote_operational_error_count"] = (
            football_quote_error_count
        )
        source_status["football"]["operational_error_count"] = int(
            source_status["football"].get("operational_error_count") or 0
        ) + football_quote_error_count
        source_status["football"]["reference_quote_count"] = len(
            reference_quotes
        )
        source_status["football"]["price_checked_count"] = len(
            football_price_rows
        )
        source_status["football"]["price_fixture_count"] = len(
            {row["fixture_id"] for row in football_price_rows}
        )
        source_status["football"]["price_status_counts"] = (
            football_price_status_counts
        )
        source_status["football"]["published_recommendation_count"] = len(
            [
                row
                for row in candidates
                if row.get("source") == "football_challenge"
            ]
        )
        source_status["football"]["published_model_selection_count"] = sum(
            row.get("source") == "football_challenge"
            for row in model_candidates
        )
        source_status["football"]["quote_errors"] = quote_errors[:10]
    if isinstance(source_status.get("tennis"), dict):
        source_status["tennis"]["price_provider_status"] = (
            "configured"
            if (config or load_app_config()).odds_api_key
            or tennis_quote_loader is not None
            else "missing_api_key"
        )
        source_status["tennis"]["reference_quote_count"] = len(
            tennis_reference_quotes
        )
        source_status["tennis"]["price_checked_count"] = len(
            tennis_price_rows
        )
        source_status["tennis"]["price_status_counts"] = (
            tennis_price_status_counts
        )
        source_status["tennis"]["published_recommendation_count"] = sum(
            row.get("source") == "tennis_shadow" for row in candidates
        )
        source_status["tennis"]["quote_errors"] = tennis_quote_errors[:10]
        tennis_quote_error_count = len(
            _operational_quote_errors(tennis_quote_errors)
        )
        source_status["tennis"]["quote_operational_error_count"] = (
            tennis_quote_error_count
        )
        source_status["tennis"]["operational_error_count"] = int(
            source_status["tennis"].get("operational_error_count") or 0
        ) + tennis_quote_error_count
    if isinstance(source_status.get("esports"), dict):
        source_status["esports"]["price_provider_status"] = (
            "unsupported_no_verified_odds_provider"
        )
        source_status["esports"]["reference_quote_count"] = 0
        source_status["esports"]["price_checked_count"] = 0
        source_status["esports"]["price_status_counts"] = (
            {"UNAVAILABLE": len(esports_model_rows)}
            if esports_model_rows
            else {}
        )
        source_status["esports"]["published_recommendation_count"] = 0
    operational_error_count = sum(
        int(source.get("operational_error_count") or 0)
        for source in source_status.values()
        if isinstance(source, dict)
    )
    failed_sources = {
        source_name
        for source_name, source in source_status.items()
        if isinstance(source, dict)
        and int(source.get("operational_error_count") or 0) > 0
    }
    source_for_row = {
        "football_challenge": "football",
        "tennis_shadow": "tennis",
        "esports_shadow": "esports",
    }
    if failed_sources:
        # Fail closed only for the affected provider/model. A Tennis timeout,
        # for example, must not erase an independently verified football tip.
        candidates = [
            row
            for row in candidates
            if source_for_row.get(str(row.get("source") or ""))
            not in failed_sources
        ]
        if isinstance(source_status.get("football"), dict):
            source_status["football"]["published_recommendation_count"] = sum(
                row.get("source") == "football_challenge" for row in candidates
            )
        if isinstance(source_status.get("tennis"), dict):
            source_status["tennis"]["published_recommendation_count"] = sum(
                row.get("source") == "tennis_shadow" for row in candidates
            )
    document = {
        "version": AUTOMATION_VERSION,
        "generated_at": current.isoformat(),
        "betting_policy_version": BETTING_POLICY_VERSION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        # A quote can be genuinely used to reject every candidate. Keep price
        # evidence separate from the number of published recommendations.
        "bookmaker_data_used": bool(
            reference_quotes or tennis_reference_quotes
        ),
        "quote_required": True,
        "run_status": (
            "completed" if operational_error_count == 0 else "degraded"
        ),
        "operational_error_count": operational_error_count,
        "target_search_date": target.isoformat(),
        "football": football_state,
        "sources": source_status,
        "model_candidates": model_candidates,
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
                "status": document.get("run_status", "degraded"),
                "generated_at": document["generated_at"],
                "candidate_count": len(document["candidates"]),
                "model_candidate_count": len(document["model_candidates"]),
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
    return 0 if int(document.get("operational_error_count") or 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
