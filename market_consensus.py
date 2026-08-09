"""Conservative multi-bookmaker reference prices for exact football markets.

Model probabilities remain independent from bookmaker prices. This module is
only the downstream price layer: it accepts a quote when API-Football exposes
the exact same market and selection, then uses a lower-quartile price instead
of the best available price. Unsupported combinations are never synthesized.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from statistics import median
from typing import Any, Iterable, Mapping, Optional

import requests

from api_budget import APIBudgetError, APIBudgetPriority, api_football_get
from betting_math import (
    MINIMUM_RECOMMENDED_DECIMAL_ODDS,
    BettingMathError,
    validate_decimal_odds,
)


REFERENCE_SOURCE = "API-Football Mehrbuchmacher"
# A current retrieval can legitimately contain a provider price whose source
# timestamp did not change for several hours. Both clocks matter: the app must
# have fetched the market recently, while the provider observation itself may
# be older but never older than one day.
REFERENCE_FETCH_MAX_AGE = timedelta(minutes=90)
REFERENCE_QUOTE_MAX_AGE = timedelta(hours=24)
MIN_REFERENCE_BOOKMAKERS = 3

# Keep obvious placeholder entries and accidental feed labels out of the
# consensus. Every other named API-Football bookmaker contributes at most one
# exact quote per selection.
EXCLUDED_BOOKMAKERS = frozenset({"", "none", "null", "n/a"})


@dataclass(frozen=True)
class QuotePoint:
    bookmaker: str
    odds: float


@dataclass(frozen=True)
class MarketConsensus:
    fixture_id: int
    candidate_id: str
    market_key: str
    bet_name: str
    value_name: str
    consensus_odds: float
    conservative_odds: float
    lowest_odds: float
    best_odds: float
    bookmaker_count: int
    quoted_at: Optional[str]
    fetched_at: str
    source: str
    points: tuple[QuotePoint, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["points"] = [asdict(point) for point in self.points]
        return payload

    @classmethod
    def from_dict(cls, payload: object) -> Optional["MarketConsensus"]:
        if not isinstance(payload, Mapping):
            return None
        try:
            points = tuple(
                QuotePoint(
                    bookmaker=str(point["bookmaker"]).strip(),
                    odds=validate_decimal_odds(point["odds"]),
                )
                for point in payload.get("points", ())
                if isinstance(point, Mapping)
            )
            quote = cls(
                fixture_id=_positive_int(payload.get("fixture_id")),
                candidate_id=_required_text(payload.get("candidate_id")),
                market_key=_required_text(payload.get("market_key")),
                bet_name=_required_text(payload.get("bet_name")),
                value_name=_required_text(payload.get("value_name")),
                consensus_odds=validate_decimal_odds(
                    payload.get("consensus_odds")
                ),
                conservative_odds=validate_decimal_odds(
                    payload.get("conservative_odds")
                ),
                lowest_odds=validate_decimal_odds(payload.get("lowest_odds")),
                best_odds=validate_decimal_odds(payload.get("best_odds")),
                bookmaker_count=_positive_int(payload.get("bookmaker_count")),
                quoted_at=(
                    _utc_iso(payload.get("quoted_at"))
                    if payload.get("quoted_at")
                    else None
                ),
                fetched_at=_utc_iso(payload.get("fetched_at")),
                source=_required_text(payload.get("source")),
                points=points,
            )
        except (BettingMathError, TypeError, ValueError):
            return None
        if (
            quote.source != REFERENCE_SOURCE
            or quote.bookmaker_count != len(quote.points)
            or len({_normalize(point.bookmaker) for point in quote.points})
            != len(quote.points)
            or not quote.points
        ):
            return None
        ordered = sorted(point.odds for point in quote.points)
        expected = _summary_prices(ordered)
        if expected is None:
            return None
        values = (
            quote.lowest_odds,
            quote.conservative_odds,
            quote.consensus_odds,
            quote.best_odds,
        )
        if any(
            not math.isclose(actual, calculated, rel_tol=0.0, abs_tol=5e-6)
            for actual, calculated in zip(values, expected)
        ):
            return None
        return quote

    def is_fresh(self, now: Optional[datetime] = None) -> bool:
        quoted = _parse_utc(self.quoted_at)
        fetched = _parse_utc(self.fetched_at)
        if quoted is None or fetched is None:
            return False
        current = _as_utc(now or datetime.now(timezone.utc))
        quote_age = current - quoted
        fetch_age = current - fetched
        return (
            timedelta(minutes=-1) <= quote_age <= REFERENCE_QUOTE_MAX_AGE
            and timedelta(minutes=-1) <= fetch_age <= REFERENCE_FETCH_MAX_AGE
        )

    @property
    def has_consensus(self) -> bool:
        return self.bookmaker_count >= MIN_REFERENCE_BOOKMAKERS


@dataclass(frozen=True)
class ReferencePriceStatus:
    code: str
    label: str
    usable_odds: Optional[float]


def reference_price_status(
    quote: Optional[MarketConsensus],
    minimum_odds: Optional[float],
    *,
    now: Optional[datetime] = None,
) -> ReferencePriceStatus:
    """Classify a reference price without changing the model forecast."""
    if quote is None:
        return ReferencePriceStatus(
            "UNAVAILABLE",
            "Keine exakt passende Marktquote verfuegbar",
            None,
        )
    if not quote.has_consensus:
        return ReferencePriceStatus(
            "THIN",
            f"Nur {quote.bookmaker_count} Buchmacher im Vergleich",
            None,
        )
    if not quote.is_fresh(now):
        return ReferencePriceStatus(
            "STALE",
            "Marktvergleich ist nicht mehr aktuell",
            None,
        )
    try:
        threshold = max(
            validate_decimal_odds(minimum_odds),
            MINIMUM_RECOMMENDED_DECIMAL_ODDS,
        )
    except BettingMathError:
        return ReferencePriceStatus(
            "INVALID_MINIMUM",
            "Mindestquote ist nicht belastbar",
            None,
        )
    if quote.conservative_odds + 1e-9 >= threshold:
        return ReferencePriceStatus(
            "PLAYABLE",
            "Marktpreis liegt konservativ ueber der Mindestquote",
            quote.conservative_odds,
        )
    if quote.best_odds + 1e-9 >= threshold:
        return ReferencePriceStatus(
            "BORDERLINE",
            "Nur einzelne Anbieter erreichen die Mindestquote",
            None,
        )
    return ReferencePriceStatus(
        "TOO_LOW",
        "Marktpreis liegt unter der Mindestquote",
        None,
    )


def _required_text(value: object) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 300:
        raise ValueError("text value is missing or too long")
    return text


def _positive_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("positive integer required")
    number = int(value)
    if number <= 0:
        raise ValueError("positive integer required")
    return number


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _parse_utc(value: object) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: object) -> str:
    parsed = _parse_utc(value)
    if parsed is None:
        raise ValueError("valid timezone-aware timestamp required")
    return parsed.isoformat()


def _normalize(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _line_from_key(market_key: str) -> Optional[str]:
    match = re.search(r"_(\d+)_(\d+)$", market_key)
    if not match:
        return None
    return f"{int(match.group(1))}.{int(match.group(2))}"


def exact_market_target(market_key: object) -> Optional[tuple[str, str]]:
    """Return the exact API-Football bet/value pair for one model market."""
    key = str(market_key or "").strip().upper()
    fixed = {
        "RESULT_HOME": ("Match Winner", "Home"),
        "RESULT_DRAW": ("Match Winner", "Draw"),
        "RESULT_AWAY": ("Match Winner", "Away"),
        "DC_1X": ("Double Chance", "Home/Draw"),
        "DC_X2": ("Double Chance", "Draw/Away"),
        "DC_12": ("Double Chance", "Home/Away"),
        "BTTS_YES": ("Both Teams Score", "Yes"),
        "BTTS_NO": ("Both Teams Score", "No"),
    }
    if key in fixed:
        return fixed[key]
    line = _line_from_key(key)
    if line is None:
        return None
    side = "Over" if "_OVER_" in key else "Under" if "_UNDER_" in key else None
    if side is None:
        return None
    if key.startswith("TOTAL_"):
        return "Goals Over/Under", f"{side} {line}"
    if key.startswith("HOME_CORNERS_"):
        return "Home Corners Over/Under", f"{side} {line}"
    if key.startswith("AWAY_CORNERS_"):
        return "Away Corners Over/Under", f"{side} {line}"
    if key.startswith("CORNERS_"):
        return "Corners Over Under", f"{side} {line}"
    if key.startswith("HOME_YELLOW_"):
        return "Home Team Yellow Cards", f"{side} {line}"
    if key.startswith("AWAY_YELLOW_"):
        return "Away Team Yellow Cards", f"{side} {line}"
    if key.startswith("YELLOW_"):
        return "Yellow Over/Under", f"{side} {line}"
    if key.startswith("HOME_"):
        return "Total - Home", f"{side} {line}"
    if key.startswith("AWAY_"):
        return "Total - Away", f"{side} {line}"
    return None


def _percentile(values: list[float], fraction: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _summary_prices(
    ordered: list[float],
) -> Optional[tuple[float, float, float, float]]:
    if not ordered:
        return None
    return (
        round(ordered[0], 6),
        round(_percentile(ordered, 0.25), 6),
        round(float(median(ordered)), 6),
        round(ordered[-1], 6),
    )


def _candidate_value(candidate: object, field: str) -> object:
    if isinstance(candidate, Mapping):
        return candidate.get(field)
    return getattr(candidate, field, None)


def parse_fixture_consensus(
    payload: object,
    candidates: Iterable[object],
    *,
    fetched_at: Optional[datetime] = None,
) -> dict[str, MarketConsensus]:
    """Parse exact candidate prices from one API-Football odds response."""
    if not isinstance(payload, Mapping) or payload.get("errors"):
        return {}
    response = payload.get("response")
    if not isinstance(response, list):
        return {}
    fetched = _as_utc(fetched_at or datetime.now(timezone.utc))
    quotes: dict[tuple[int, str, str], dict[str, QuotePoint]] = {}
    updates: dict[int, list[datetime]] = {}
    fixture_ids: set[int] = set()
    for entry in response:
        if not isinstance(entry, Mapping):
            continue
        fixture = entry.get("fixture")
        fixture = fixture if isinstance(fixture, Mapping) else {}
        fixture_id = fixture.get("id")
        if (
            not isinstance(fixture_id, int)
            or isinstance(fixture_id, bool)
            or fixture_id <= 0
        ):
            continue
        fixture_ids.add(fixture_id)
        update = _parse_utc(entry.get("update"))
        if update is not None:
            updates.setdefault(fixture_id, []).append(update)
        bookmakers = entry.get("bookmakers")
        if not isinstance(bookmakers, list):
            continue
        for bookmaker in bookmakers:
            if not isinstance(bookmaker, Mapping):
                continue
            bookmaker_name = str(bookmaker.get("name") or "").strip()
            bookmaker_key = _normalize(bookmaker_name)
            if bookmaker_key in EXCLUDED_BOOKMAKERS:
                continue
            bets = bookmaker.get("bets")
            if not isinstance(bets, list):
                continue
            for bet in bets:
                if not isinstance(bet, Mapping):
                    continue
                bet_name = _normalize(bet.get("name"))
                values = bet.get("values")
                if not bet_name or not isinstance(values, list):
                    continue
                for value in values:
                    if not isinstance(value, Mapping):
                        continue
                    value_name = _normalize(value.get("value"))
                    try:
                        odds = validate_decimal_odds(value.get("odd"))
                    except BettingMathError:
                        continue
                    market_quotes = quotes.setdefault(
                        (fixture_id, bet_name, value_name),
                        {},
                    )
                    current = market_quotes.get(bookmaker_key)
                    # A provider sometimes emits casing variants of the same
                    # bookmaker. Count it once and retain the lower price so a
                    # duplicate can never make the consensus more optimistic.
                    if current is None or odds < current.odds:
                        market_quotes[bookmaker_key] = QuotePoint(
                            bookmaker=bookmaker_name,
                            odds=odds,
                        )

    result: dict[str, MarketConsensus] = {}
    for candidate in candidates:
        candidate_id = str(_candidate_value(candidate, "candidate_id") or "").strip()
        market_key = str(_candidate_value(candidate, "market_key") or "").strip()
        fixture_id = _candidate_value(candidate, "fixture_id")
        target = exact_market_target(market_key)
        if (
            not candidate_id
            or target is None
            or isinstance(fixture_id, bool)
            or not isinstance(fixture_id, int)
            or fixture_id <= 0
            or (fixture_ids and fixture_id not in fixture_ids)
        ):
            continue
        bet_name, value_name = target
        raw = quotes.get(
            (fixture_id, _normalize(bet_name), _normalize(value_name)),
            {},
        )
        points = tuple(
            point
            for _, point in sorted(raw.items(), key=lambda item: item[0])
        )
        summary = _summary_prices(sorted(point.odds for point in points))
        if summary is None:
            continue
        lowest, conservative, consensus, best = summary
        fixture_updates = updates.get(fixture_id, [])
        quoted_at = max(fixture_updates).isoformat() if fixture_updates else None
        result[candidate_id] = MarketConsensus(
            fixture_id=fixture_id,
            candidate_id=candidate_id,
            market_key=market_key,
            bet_name=bet_name,
            value_name=value_name,
            consensus_odds=consensus,
            conservative_odds=conservative,
            lowest_odds=lowest,
            best_odds=best,
            bookmaker_count=len(points),
            quoted_at=quoted_at,
            fetched_at=fetched.isoformat(),
            source=REFERENCE_SOURCE,
            points=points,
        )
    return result


def fetch_football_consensus(
    api_key: str,
    candidates: Iterable[object],
    *,
    timeout: int = 20,
    now: Optional[datetime] = None,
) -> tuple[dict[str, MarketConsensus], list[str]]:
    """Fetch one exact multi-bookmaker quote set per shortlisted fixture."""
    current = _as_utc(now or datetime.now(timezone.utc))
    candidate_list = list(candidates)
    grouped: dict[int, list[object]] = {}
    for candidate in candidate_list:
        fixture_id = _candidate_value(candidate, "fixture_id")
        if (
            isinstance(fixture_id, int)
            and not isinstance(fixture_id, bool)
            and fixture_id > 0
            and exact_market_target(_candidate_value(candidate, "market_key"))
            is not None
        ):
            grouped.setdefault(fixture_id, []).append(candidate)
    quotes: dict[str, MarketConsensus] = {}
    errors: list[str] = []
    headers = {"x-apisports-key": str(api_key or "").strip()}
    if not headers["x-apisports-key"]:
        return {}, ["API-Football-Key fuer Marktquoten fehlt"]
    for fixture_id, fixture_candidates in grouped.items():
        try:
            response = api_football_get(
                "https://v3.football.api-sports.io/odds",
                headers=headers,
                params={"fixture": fixture_id},
                timeout=timeout,
                priority=APIBudgetPriority.RECOMMENDATION,
                label=f"odds consensus fixture {fixture_id}",
            )
            response.raise_for_status()
            payload = response.json()
        except (APIBudgetError, requests.RequestException, ValueError) as exc:
            errors.append(f"Marktquoten Spiel {fixture_id}: {exc}")
            continue
        if not isinstance(payload, Mapping):
            errors.append(f"Marktquoten Spiel {fixture_id}: ungueltige Antwort")
            continue
        provider_errors = payload.get("errors")
        if provider_errors:
            errors.append(f"Marktquoten Spiel {fixture_id}: {provider_errors}")
            continue
        quotes.update(
            parse_fixture_consensus(
                payload,
                fixture_candidates,
                fetched_at=current,
            )
        )
    return quotes, errors


def serialize_consensus_map(
    quotes: Mapping[str, MarketConsensus],
) -> dict[str, dict[str, Any]]:
    return {key: quote.to_dict() for key, quote in quotes.items()}


def deserialize_consensus_map(
    payload: object,
) -> dict[str, MarketConsensus]:
    if not isinstance(payload, Mapping):
        return {}
    result: dict[str, MarketConsensus] = {}
    for key, value in payload.items():
        quote = MarketConsensus.from_dict(value)
        if quote is not None and quote.candidate_id == str(key):
            result[str(key)] = quote
    return result


__all__ = [
    "MIN_REFERENCE_BOOKMAKERS",
    "MarketConsensus",
    "QuotePoint",
    "REFERENCE_FETCH_MAX_AGE",
    "REFERENCE_QUOTE_MAX_AGE",
    "REFERENCE_SOURCE",
    "ReferencePriceStatus",
    "deserialize_consensus_map",
    "exact_market_target",
    "fetch_football_consensus",
    "parse_fixture_consensus",
    "reference_price_status",
    "serialize_consensus_map",
]
