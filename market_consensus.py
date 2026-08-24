"""Conservative multi-bookmaker reference prices for exact football markets.

Model probabilities remain independent from bookmaker prices. This module is
only the downstream price layer: it accepts a quote when a provider exposes
the exact same event, market and selection.  The lower quartile is a trust
gate, while any price handed to a betting decision is one actually observed
bookmaker offer near that gate. Unsupported combinations and prices are never
synthesized.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from statistics import median
from typing import Any, Iterable, Mapping, Optional
import unicodedata

import requests

from api_budget import APIBudgetError, APIBudgetPriority, api_football_get
from betting_math import (
    MINIMUM_RECOMMENDED_DECIMAL_ODDS,
    BettingMathError,
    validate_decimal_odds,
)


REFERENCE_SOURCE = "API-Football Mehrbuchmacher"
ODDS_API_REFERENCE_SOURCE = "The Odds API Mehrbuchmacher"
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
ODDS_API_EVENT_TOLERANCE = timedelta(hours=2)
FOOTBALL_QUOTE_START_TOLERANCE = timedelta(minutes=5)
TENNIS_QUOTE_START_TOLERANCE = timedelta(minutes=30)
MAX_TENNIS_EVENT_DISCOVERY_KEYS = 8
TENNIS_EVENT_DISCOVERY_TIMEOUT = 5
# The established reference window belongs to the separate 15K workflow and
# is also enforced by its append-only ledger. Keep that contract unchanged.
REFERENCE_FETCH_MAX_AGE = timedelta(minutes=90)
REFERENCE_QUOTE_MAX_AGE = timedelta(hours=24)
# A normal Wettfinder recommendation must be realistically executable when the
# user sees it. Its retrieval and point clocks are deliberately much shorter;
# they must not silently tighten the independent 15K challenge contract.
WETTFINDER_FETCH_MAX_AGE = timedelta(minutes=35)
WETTFINDER_QUOTE_MAX_AGE = timedelta(minutes=45)
MIN_REFERENCE_BOOKMAKERS = 3

# Keep obvious placeholder entries and accidental feed labels out of the
# consensus. Every other named API-Football bookmaker contributes at most one
# exact quote per selection.
EXCLUDED_BOOKMAKERS = frozenset({"", "none", "null", "n/a"})


@dataclass(frozen=True)
class QuotePoint:
    bookmaker: str
    odds: float
    bookmaker_id: Optional[str] = None
    observed_at: Optional[str] = None


@dataclass(frozen=True)
class MarketConsensus:
    fixture_id: Optional[int]
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
    provider_event_id: Optional[str] = None
    scheduled_start: Optional[str] = None
    event_home: Optional[str] = None
    event_away: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["points"] = [asdict(point) for point in self.points]
        executable = self.executable_point
        payload["executable_quote"] = (
            asdict(executable) if executable is not None else None
        )
        return payload

    @classmethod
    def from_dict(cls, payload: object) -> Optional["MarketConsensus"]:
        if not isinstance(payload, Mapping):
            return None
        try:
            legacy_quoted_at = (
                _utc_iso(payload.get("quoted_at"))
                if payload.get("quoted_at")
                else None
            )
            points = tuple(
                _quote_point_from_payload(
                    point,
                )
                for point in payload.get("points", ())
                if isinstance(point, Mapping)
            )
            raw_fixture_id = payload.get("fixture_id")
            quote = cls(
                fixture_id=(
                    _positive_int(raw_fixture_id)
                    if raw_fixture_id is not None
                    else None
                ),
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
                quoted_at=legacy_quoted_at,
                fetched_at=_utc_iso(payload.get("fetched_at")),
                source=_required_text(payload.get("source")),
                points=points,
                provider_event_id=(
                    _required_text(payload.get("provider_event_id"))
                    if payload.get("provider_event_id") is not None
                    else None
                ),
                scheduled_start=(
                    _utc_iso(payload.get("scheduled_start"))
                    if payload.get("scheduled_start") is not None
                    else None
                ),
                event_home=(
                    _required_text(payload.get("event_home"))
                    if payload.get("event_home") is not None
                    else None
                ),
                event_away=(
                    _required_text(payload.get("event_away"))
                    if payload.get("event_away") is not None
                    else None
                ),
            )
        except (BettingMathError, TypeError, ValueError):
            return None
        if (
            quote.source not in {
                REFERENCE_SOURCE,
                ODDS_API_REFERENCE_SOURCE,
            }
            or (
                quote.source == REFERENCE_SOURCE
                and quote.fixture_id is None
            )
            or (
                quote.source == ODDS_API_REFERENCE_SOURCE
                and quote.provider_event_id is None
            )
            or quote.bookmaker_count != len(quote.points)
            or len({_quote_point_identity(point) for point in quote.points})
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
        point_times = [
            _point_observed_at(point, quote.quoted_at)
            for point in quote.points
        ]
        if any(observed is None for observed in point_times):
            return None
        latest = max(
            observed for observed in point_times if observed is not None
        )
        quoted = _parse_utc(quote.quoted_at)
        if quoted is None or not _same_moment(quoted, latest):
            return None
        serialized_executable = payload.get("executable_quote")
        if serialized_executable is not None:
            if not isinstance(serialized_executable, Mapping):
                return None
            loaded_executable = _quote_point_from_payload(
                serialized_executable,
            )
            if loaded_executable != quote.executable_point:
                return None
        return quote

    def is_fresh(self, now: Optional[datetime] = None) -> bool:
        """Apply the established 15K aggregate quote/fetch window."""

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

    def is_wettfinder_fresh(self, now: Optional[datetime] = None) -> bool:
        """Require every contributing offer to satisfy the normal live window."""

        fetched = _parse_utc(self.fetched_at)
        point_times = [
            _point_observed_at(point, self.quoted_at)
            for point in self.points
        ]
        if fetched is None or not point_times or any(
            observed is None for observed in point_times
        ):
            return False
        current = _as_utc(now or datetime.now(timezone.utc))
        fetch_age = current - fetched
        return (
            timedelta(minutes=-1) <= fetch_age <= WETTFINDER_FETCH_MAX_AGE
            and all(
                timedelta(minutes=-1)
                <= current - observed
                <= WETTFINDER_QUOTE_MAX_AGE
                for observed in point_times
                if observed is not None
            )
            and all(
                timedelta(minutes=-1)
                <= fetched - observed
                <= WETTFINDER_QUOTE_MAX_AGE
                for observed in point_times
                if observed is not None
            )
        )

    @property
    def has_consensus(self) -> bool:
        return self.bookmaker_count >= MIN_REFERENCE_BOOKMAKERS

    @property
    def executable_point(self) -> Optional[QuotePoint]:
        """Return the real offer closest at/above the conservative Q25 gate."""

        eligible = [
            point
            for point in self.points
            if point.odds + 1e-9 >= self.conservative_odds
        ]
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda point: (
                point.odds,
                _quote_point_identity(point),
            ),
        )


@dataclass(frozen=True)
class ReferencePriceStatus:
    code: str
    label: str
    usable_odds: Optional[float]
    bookmaker: Optional[str] = None
    bookmaker_id: Optional[str] = None
    observed_at: Optional[str] = None


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


def _wettfinder_provider_prefix(quote: MarketConsensus) -> Optional[str]:
    """Return the stable ID namespace required for a normal finder quote."""

    if quote.source == REFERENCE_SOURCE:
        return "api-football:"
    if quote.source == ODDS_API_REFERENCE_SOURCE:
        return "odds-api:"
    return None


def _wettfinder_fetch_is_fresh(
    quote: MarketConsensus,
    now: Optional[datetime] = None,
) -> bool:
    fetched = _parse_utc(quote.fetched_at)
    if fetched is None:
        return False
    current = _as_utc(now or datetime.now(timezone.utc))
    age = current - fetched
    return timedelta(minutes=-1) <= age <= WETTFINDER_FETCH_MAX_AGE


def _wettfinder_identified_points(
    quote: MarketConsensus,
) -> tuple[QuotePoint, ...]:
    provider_prefix = _wettfinder_provider_prefix(quote)
    if provider_prefix is None:
        return ()
    return tuple(
        point
        for point in quote.points
        if (
            _normalize(point.bookmaker_id).startswith(provider_prefix)
            and _normalize(point.bookmaker_id)
            .removeprefix(provider_prefix)
            .strip()
            and _parse_utc(point.observed_at) is not None
        )
    )


def wettfinder_consensus(
    quote: Optional[MarketConsensus],
    *,
    now: Optional[datetime] = None,
) -> Optional[MarketConsensus]:
    """Rebuild the normal consensus from current, provider-bound offers.

    The shared parser deliberately retains the wider 15K observation window.
    One old or unidentified point must not poison an otherwise valid normal
    three-book market, so Q25, median, best and the executable offer are
    recomputed only from the current provider-native subset.
    """

    if not isinstance(quote, MarketConsensus):
        return None
    fetched = _parse_utc(quote.fetched_at)
    if fetched is None:
        return None
    current = _as_utc(now or datetime.now(timezone.utc))
    points = tuple(
        point
        for point in _wettfinder_identified_points(quote)
        if (
            timedelta(minutes=-1)
            <= current - _parse_utc(point.observed_at)
            <= WETTFINDER_QUOTE_MAX_AGE
            and timedelta(minutes=-1)
            <= fetched - _parse_utc(point.observed_at)
            <= WETTFINDER_QUOTE_MAX_AGE
        )
    )
    summary = _summary_prices(sorted(point.odds for point in points))
    if summary is None:
        return None
    lowest, conservative, consensus, best = summary
    observed = [
        _parse_utc(point.observed_at)
        for point in points
        if _parse_utc(point.observed_at) is not None
    ]
    return MarketConsensus(
        fixture_id=quote.fixture_id,
        candidate_id=quote.candidate_id,
        market_key=quote.market_key,
        bet_name=quote.bet_name,
        value_name=quote.value_name,
        consensus_odds=consensus,
        conservative_odds=conservative,
        lowest_odds=lowest,
        best_odds=best,
        bookmaker_count=len(points),
        quoted_at=max(observed).isoformat() if observed else None,
        fetched_at=quote.fetched_at,
        source=quote.source,
        points=points,
        provider_event_id=quote.provider_event_id,
        scheduled_start=quote.scheduled_start,
        event_home=quote.event_home,
        event_away=quote.event_away,
    )


def _wettfinder_quote_has_execution_proof(
    quote: MarketConsensus,
) -> bool:
    """Require provider-native identity and clocks for every consensus point.

    Legacy snapshots intentionally remain deserializable through ``from_dict``.
    They can still explain an observed price, but aggregate timestamps and
    bookmaker names are not enough evidence for an actionable normal
    Wettfinder decision.
    """

    provider_prefix = _wettfinder_provider_prefix(quote)
    if provider_prefix is None or _parse_utc(quote.scheduled_start) is None:
        return False
    stable_ids: set[str] = set()
    for point in quote.points:
        bookmaker_id = _normalize(point.bookmaker_id)
        if (
            not bookmaker_id.startswith(provider_prefix)
            or not bookmaker_id.removeprefix(provider_prefix).strip()
            or _parse_utc(point.observed_at) is None
        ):
            return False
        stable_ids.add(bookmaker_id)
    executable = quote.executable_point
    return (
        len(stable_ids) >= MIN_REFERENCE_BOOKMAKERS
        and executable is not None
        and _normalize(executable.bookmaker_id) in stable_ids
        and _parse_utc(executable.observed_at) is not None
    )


def wettfinder_reference_price_status(
    quote: Optional[MarketConsensus],
    minimum_odds: Optional[float],
    *,
    candidate: object = None,
    now: Optional[datetime] = None,
) -> ReferencePriceStatus:
    """Classify a quote under the normal Wettfinder execution contract.

    The established ``reference_price_status`` API deliberately remains
    unchanged for the separate 15K workflow. Normal Wettfinder callers use
    this stricter layer: an otherwise playable price is actionable only when
    the event/selection is exactly bound (when a candidate is supplied), the
    event start is present, and every contributing bookmaker has a stable
    provider ID plus its own parseable observation timestamp.
    """

    if quote is not None and candidate is not None:
        modeled_selection = str(
            _candidate_value(candidate, "selection") or ""
        ).strip()
        if not modeled_selection or not quote_matches_candidate(
            quote,
            candidate,
        ):
            return ReferencePriceStatus(
                "UNAVAILABLE",
                "Marktquote ist nicht exakt an diese Auswahl gebunden",
                None,
            )
    if quote is None:
        return reference_price_status(None, minimum_odds, now=now)
    if not _wettfinder_fetch_is_fresh(quote, now):
        return ReferencePriceStatus(
            "STALE",
            "Marktvergleich ist nicht mehr aktuell",
            None,
        )
    identified_points = _wettfinder_identified_points(quote)
    effective_quote = wettfinder_consensus(quote, now=now)
    if effective_quote is None:
        if identified_points:
            return ReferencePriceStatus(
                "STALE",
                "Marktvergleich ist nicht mehr aktuell",
                None,
            )
        return ReferencePriceStatus(
            "UNAVAILABLE",
            "Quotenstand hat keinen vollstaendigen Anbieter- und Zeitbeleg",
            None,
        )
    status = reference_price_status(effective_quote, minimum_odds, now=now)
    if status.code != "PLAYABLE":
        return status
    if not _wettfinder_quote_has_execution_proof(effective_quote):
        return ReferencePriceStatus(
            "UNAVAILABLE",
            "Quotenstand hat keinen vollstaendigen Anbieter- und Zeitbeleg",
            None,
        )
    executable = effective_quote.executable_point
    if executable is None:
        return ReferencePriceStatus(
            "UNAVAILABLE",
            "Es liegt kein konkret ausfuehrbares Anbieterangebot vor",
            None,
        )
    return ReferencePriceStatus(
        "PLAYABLE",
        status.label,
        executable.odds,
        bookmaker=executable.bookmaker,
        bookmaker_id=executable.bookmaker_id,
        observed_at=executable.observed_at or quote.quoted_at,
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


def _same_moment(left: datetime, right: datetime) -> bool:
    return abs((left - right).total_seconds()) <= 1e-6


def _quote_point_from_payload(
    payload: Mapping[str, object],
) -> QuotePoint:
    bookmaker = _required_text(payload.get("bookmaker"))
    bookmaker_id = (
        _required_text(payload.get("bookmaker_id"))
        if payload.get("bookmaker_id") is not None
        else None
    )
    # Old saved snapshots did not contain point-level timestamps. Keep them
    # readable and use their aggregate quoted_at only during freshness checks;
    # newly fetched points always carry their own provider observation clock.
    raw_observed = payload.get("observed_at")
    observed_at = (
        _utc_iso(raw_observed)
        if raw_observed is not None
        else None
    )
    return QuotePoint(
        bookmaker=bookmaker,
        odds=validate_decimal_odds(payload.get("odds")),
        bookmaker_id=bookmaker_id,
        observed_at=observed_at,
    )


def _quote_point_identity(point: QuotePoint) -> str:
    stable = _normalize(point.bookmaker_id)
    if stable:
        return f"id:{stable}"
    return f"name:{_normalize(point.bookmaker)}"


def _point_observed_at(
    point: QuotePoint,
    legacy_quoted_at: Optional[str],
) -> Optional[datetime]:
    return _parse_utc(point.observed_at) or _parse_utc(legacy_quoted_at)


def _provider_bookmaker_id(
    provider: Mapping[str, object],
    *,
    source_prefix: str,
    fields: tuple[str, ...],
) -> Optional[str]:
    for field in fields:
        raw = provider.get(field)
        if isinstance(raw, bool) or raw is None:
            continue
        text = str(raw).strip()
        if text:
            return f"{source_prefix}:{text.casefold()}"
    return None


def _provider_fixture_start(fixture: Mapping[str, object]) -> Optional[datetime]:
    parsed = _parse_utc(fixture.get("date"))
    if parsed is not None:
        return parsed
    timestamp = fixture.get("timestamp")
    if isinstance(timestamp, bool):
        return None
    try:
        number = int(timestamp)
    except (TypeError, ValueError, OverflowError):
        return None
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _identity_name(value: object) -> str:
    """Normalize participant names without introducing fuzzy matching."""
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    separated = "".join(
        character
        if character.isalnum()
        else " "
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(separated.split())


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


def _candidate_start(candidate: object) -> Optional[datetime]:
    for field in ("scheduled_start", "kickoff", "start_time"):
        value = _candidate_value(candidate, field)
        if value is not None:
            return _parse_utc(value)
    return None


def _candidate_quote_provider_event_id(candidate: object) -> Optional[str]:
    """Return only an ID explicitly belonging to the quote provider.

    Generic fixture/provider IDs can come from a different data source and
    must not be compared with The Odds API event IDs. The automation persists
    this dedicated field after its initial exact team/start discovery match.
    """

    for field in ("quote_provider_event_id", "odds_provider_event_id"):
        text = str(_candidate_value(candidate, field) or "").strip()
        if text:
            return text
    return None


def _selection_has_exact_line(selection: str, expected_line: str) -> bool:
    values = re.findall(r"\d+(?:[.,]\d+)?", selection)
    normalized = {value.replace(",", ".") for value in values}
    return normalized == {expected_line}


def _football_candidate_selection_matches(
    candidate: object,
    market_key: str,
) -> bool:
    raw = _candidate_value(candidate, "selection")
    if raw is None:
        # Legacy in-memory callers used only candidate_id/fixture_id/key. New
        # production rows always include the modeled selection and are checked.
        return True
    selected = _identity_name(raw)
    if not selected:
        return False
    aliases = {
        "RESULT_HOME": {"home", "heimsieg", "1"},
        "RESULT_DRAW": {"draw", "unentschieden", "x"},
        "RESULT_AWAY": {"away", "auswartssieg", "2"},
        "DC_1X": {"1x", "home draw", "heim unentschieden"},
        "DC_X2": {"x2", "draw away", "unentschieden auswarts"},
        "DC_12": {"12", "home away", "heim auswarts"},
        "BTTS_YES": {"yes", "ja", "btts ja"},
        "BTTS_NO": {"no", "nein", "btts nein"},
    }
    if market_key in aliases:
        if selected in aliases[market_key]:
            return True
        home = _identity_name(_candidate_value(candidate, "home_team"))
        away = _identity_name(_candidate_value(candidate, "away_team"))
        if market_key == "RESULT_HOME" and home:
            return selected in {home, f"sieg {home}"}
        if market_key == "RESULT_AWAY" and away:
            return selected in {away, f"sieg {away}"}
        return False

    expected_line = _line_from_key(market_key)
    if expected_line is None:
        return False
    wants_over = "_OVER_" in market_key
    wants_under = "_UNDER_" in market_key
    if wants_over == wants_under:
        return False
    words = set(selected.split())
    direction_matches = (
        bool(words & {"over", "uber"})
        if wants_over
        else bool(words & {"under", "unter"})
    )
    return direction_matches and _selection_has_exact_line(
        str(raw),
        expected_line,
    )


def _event_start_matches(
    quote: MarketConsensus,
    candidate: object,
    tolerance: timedelta,
) -> bool:
    quote_start = _parse_utc(quote.scheduled_start)
    candidate_start = _candidate_start(candidate)
    if quote_start is None and candidate_start is None:
        # Backwards-compatible path for old saved snapshots. Newly fetched
        # provider quotes always contain a provider event start.
        return True
    if quote_start is None and all(
        point.observed_at is None for point in quote.points
    ):
        # Legacy serialized/manual consensus objects predate event starts and
        # point clocks. They remain readable during migration; every newly
        # parsed provider quote has both and therefore cannot use this path.
        return True
    return (
        quote_start is not None
        and candidate_start is not None
        and abs(quote_start - candidate_start) <= tolerance
    )


def quote_matches_candidate(
    quote: object,
    candidate: object,
) -> bool:
    """Bind one real provider quote to exactly one modeled market.

    The common candidate/market identity is mandatory for every sport.
    Football additionally requires the same fixture and API-Football source;
    Tennis accepts only an event-backed The Odds API H2H quote with exact
    participants and start binding. Unknown sports never inherit a quote merely
    because a candidate ID happens to match.
    """
    if not isinstance(quote, MarketConsensus):
        return False
    candidate_id = str(
        _candidate_value(candidate, "candidate_id") or ""
    ).strip()
    market_key = str(
        _candidate_value(candidate, "market_key") or ""
    ).strip().upper()
    if (
        not candidate_id
        or not market_key
        or quote.candidate_id != candidate_id
        or quote.market_key.strip().upper() != market_key
    ):
        return False

    sport = _normalize(_candidate_value(candidate, "sport"))
    source = _normalize(_candidate_value(candidate, "source"))
    fixture_id = _candidate_value(candidate, "fixture_id")
    fixture_is_valid = (
        isinstance(fixture_id, int)
        and not isinstance(fixture_id, bool)
        and fixture_id > 0
    )
    is_football = (
        source == "football_challenge"
        or sport.replace("ß", "ss") == "fussball"
        or fixture_is_valid
    )
    is_tennis = source == "tennis_shadow" or sport == "tennis"
    if is_football and is_tennis:
        return False
    if is_football:
        target = exact_market_target(market_key)
        if target is None:
            return False
        bet_name, value_name = target
        return (
            fixture_is_valid
            and quote.fixture_id == fixture_id
            and quote.source == REFERENCE_SOURCE
            and sport in {"", "fussball", "fußball", "football"}
            and _event_start_matches(
                quote,
                candidate,
                FOOTBALL_QUOTE_START_TOLERANCE,
            )
            and _normalize(quote.bet_name) == _normalize(bet_name)
            and _normalize(quote.value_name) == _normalize(value_name)
            and _football_candidate_selection_matches(
                candidate,
                market_key,
            )
        )
    if is_tennis:
        selected = _identity_name(
            _candidate_value(candidate, "selected_competitor")
        )
        competitors = {
            _identity_name(_candidate_value(candidate, "competitor_a")),
            _identity_name(_candidate_value(candidate, "competitor_b")),
        }
        quoted_competitors = {
            _identity_name(quote.event_home),
            _identity_name(quote.event_away),
        }
        expected_provider_event_id = _candidate_quote_provider_event_id(
            candidate
        )
        return (
            market_key == "H2H"
            and quote.fixture_id is None
            and quote.source == ODDS_API_REFERENCE_SOURCE
            and sport == "tennis"
            and isinstance(quote.provider_event_id, str)
            and bool(quote.provider_event_id.strip())
            and (
                expected_provider_event_id is None
                or quote.provider_event_id == expected_provider_event_id
            )
            and _normalize(quote.bet_name) == "h2h"
            and bool(selected)
            and len(competitors) == 2
            and selected in competitors
            and quoted_competitors == competitors
            and _event_start_matches(
                quote,
                candidate,
                TENNIS_QUOTE_START_TOLERANCE,
            )
            and _identity_name(quote.value_name) == selected
        )
    return False


def challenge_quote_matches_candidate(
    quote: object,
    candidate: object,
) -> bool:
    """Apply the established fixture/market binding used by the 15K mode.

    The normal Wettfinder intentionally adds selection, event-start and
    provider-execution proof. Those new release conditions must not
    retroactively alter the separate 15K challenge contract.
    """

    if not isinstance(quote, MarketConsensus):
        return False
    candidate_id = str(
        _candidate_value(candidate, "candidate_id") or ""
    ).strip()
    market_key = str(
        _candidate_value(candidate, "market_key") or ""
    ).strip().upper()
    fixture_id = _candidate_value(candidate, "fixture_id")
    target = exact_market_target(market_key)
    if (
        not candidate_id
        or target is None
        or isinstance(fixture_id, bool)
        or not isinstance(fixture_id, int)
        or fixture_id <= 0
        or quote.candidate_id != candidate_id
        or quote.market_key.strip().upper() != market_key
    ):
        return False
    bet_name, value_name = target
    return (
        quote.fixture_id == fixture_id
        and quote.source == REFERENCE_SOURCE
        and _normalize(quote.bet_name) == _normalize(bet_name)
        and _normalize(quote.value_name) == _normalize(value_name)
    )


def _observation_is_current(
    observed_at: Optional[datetime],
    fetched_at: datetime,
) -> bool:
    if observed_at is None:
        return False
    age = fetched_at - observed_at
    return timedelta(minutes=-1) <= age <= REFERENCE_QUOTE_MAX_AGE


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
    quotes: dict[
        tuple[int, str, str],
        dict[str, tuple[QuotePoint, datetime]],
    ] = {}
    fixture_ids: set[int] = set()
    fixture_starts: dict[int, Optional[datetime]] = {}
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
        fixture_start = _provider_fixture_start(fixture)
        if fixture_id not in fixture_starts:
            fixture_starts[fixture_id] = fixture_start
        else:
            previous_start = fixture_starts[fixture_id]
            if (
                previous_start is None
                or fixture_start is None
                or abs(previous_start - fixture_start)
                > FOOTBALL_QUOTE_START_TOLERANCE
            ):
                # Preserve the legacy fixture-ID quote for 15K, but remove the
                # start proof so the normal Wettfinder remains fail-closed.
                fixture_starts[fixture_id] = None
        fixture_ids.add(fixture_id)
        update = _parse_utc(entry.get("update"))
        bookmakers = entry.get("bookmakers")
        if not isinstance(bookmakers, list):
            continue
        for bookmaker in bookmakers:
            if not isinstance(bookmaker, Mapping):
                continue
            bookmaker_name = str(bookmaker.get("name") or "").strip()
            bookmaker_id = _provider_bookmaker_id(
                bookmaker,
                source_prefix="api-football",
                fields=("id",),
            )
            bookmaker_key = (
                f"id:{_normalize(bookmaker_id)}"
                if bookmaker_id
                else f"name:{_normalize(bookmaker_name)}"
            )
            if _normalize(bookmaker_name) in EXCLUDED_BOOKMAKERS:
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
                    if not _observation_is_current(update, fetched):
                        continue
                    market_quotes = quotes.setdefault(
                        (fixture_id, bet_name, value_name),
                        {},
                    )
                    current = market_quotes.get(bookmaker_key)
                    # Stable provider IDs deduplicate renamed books. Prefer the
                    # newest observation; at an identical timestamp retain the
                    # lower price so duplicates cannot inflate the consensus.
                    if (
                        current is None
                        or update > current[1]
                        or (
                            _same_moment(update, current[1])
                            and odds < current[0].odds
                        )
                    ):
                        market_quotes[bookmaker_key] = (
                            QuotePoint(
                                bookmaker=bookmaker_name,
                                odds=odds,
                                bookmaker_id=bookmaker_id,
                                observed_at=update.isoformat(),
                            ),
                            update,
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
            observed[0]
            for _, observed in sorted(raw.items(), key=lambda item: item[0])
        )
        summary = _summary_prices(sorted(point.odds for point in points))
        if summary is None:
            continue
        lowest, conservative, consensus, best = summary
        observed_at = [observed[1] for observed in raw.values()]
        quoted_at = max(observed_at).isoformat() if observed_at else None
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
            scheduled_start=(
                fixture_starts[fixture_id].isoformat()
                if fixture_starts.get(fixture_id) is not None
                else None
            ),
        )
    return result


def _h2h_candidate_identity(
    candidate: object,
) -> Optional[tuple[str, str, str, datetime]]:
    competitor_a = str(
        _candidate_value(candidate, "competitor_a") or ""
    ).strip()
    competitor_b = str(
        _candidate_value(candidate, "competitor_b") or ""
    ).strip()
    selected = str(
        _candidate_value(candidate, "selected_competitor") or ""
    ).strip()
    scheduled = _parse_utc(_candidate_value(candidate, "scheduled_start"))
    normalized = tuple(
        _identity_name(value)
        for value in (competitor_a, competitor_b, selected)
    )
    if (
        not all(normalized)
        or normalized[0] == normalized[1]
        or normalized[2] not in normalized[:2]
        or scheduled is None
    ):
        return None
    return normalized[0], normalized[1], normalized[2], scheduled


def _h2h_event_matches(
    event: object,
    candidate: object,
) -> bool:
    if not isinstance(event, Mapping):
        return False
    identity = _h2h_candidate_identity(candidate)
    commence = _parse_utc(event.get("commence_time"))
    if identity is None or commence is None:
        return False
    competitor_a, competitor_b, _selected, scheduled = identity
    event_participants = {
        _identity_name(event.get("home_team")),
        _identity_name(event.get("away_team")),
    }
    return (
        event_participants == {competitor_a, competitor_b}
        and abs(commence - scheduled) <= ODDS_API_EVENT_TOLERANCE
    )


def parse_h2h_event_consensus(
    payload: object,
    candidates: Iterable[object],
    *,
    fetched_at: Optional[datetime] = None,
) -> dict[str, MarketConsensus]:
    """Parse exact match-winner prices for one identified provider event.

    Participant names must match exactly after case, accent and punctuation
    normalization, the scheduled times must be close, and the selected
    participant must be one of the two modeled competitors. No market or
    price is inferred when any identity field is missing or ambiguous.
    """
    if not isinstance(payload, Mapping):
        return {}
    provider_event_id = str(payload.get("id") or "").strip()
    if not provider_event_id:
        return {}
    current = _as_utc(fetched_at or datetime.now(timezone.utc))
    candidate_list = [
        candidate
        for candidate in candidates
        if _h2h_event_matches(payload, candidate)
    ]
    if not candidate_list:
        return {}

    quotes: dict[str, dict[str, tuple[QuotePoint, datetime]]] = {}
    bookmakers = payload.get("bookmakers")
    if not isinstance(bookmakers, list):
        return {}
    for bookmaker in bookmakers:
        if not isinstance(bookmaker, Mapping):
            continue
        bookmaker_name = str(
            bookmaker.get("title") or bookmaker.get("key") or ""
        ).strip()
        bookmaker_id = _provider_bookmaker_id(
            bookmaker,
            source_prefix="odds-api",
            fields=("key",),
        )
        bookmaker_key = (
            f"id:{_normalize(bookmaker_id)}"
            if bookmaker_id
            else f"name:{_normalize(bookmaker_name)}"
        )
        if _normalize(bookmaker_name) in EXCLUDED_BOOKMAKERS:
            continue
        bookmaker_update = _parse_utc(bookmaker.get("last_update"))
        markets = bookmaker.get("markets")
        if not isinstance(markets, list):
            continue
        for market in markets:
            if (
                not isinstance(market, Mapping)
                or _normalize(market.get("key")) != "h2h"
            ):
                continue
            market_update = _parse_utc(market.get("last_update"))
            observed_at = market_update or bookmaker_update
            if not _observation_is_current(observed_at, current):
                continue
            outcomes = market.get("outcomes")
            if not isinstance(outcomes, list):
                continue
            for outcome in outcomes:
                if not isinstance(outcome, Mapping):
                    continue
                outcome_name = _identity_name(outcome.get("name"))
                if not outcome_name:
                    continue
                try:
                    odds = validate_decimal_odds(outcome.get("price"))
                except BettingMathError:
                    continue
                by_bookmaker = quotes.setdefault(outcome_name, {})
                existing = by_bookmaker.get(bookmaker_key)
                if (
                    existing is None
                    or observed_at > existing[1]
                    or (
                        _same_moment(observed_at, existing[1])
                        and odds < existing[0].odds
                    )
                ):
                    by_bookmaker[bookmaker_key] = (
                        QuotePoint(
                            bookmaker=bookmaker_name,
                            odds=odds,
                            bookmaker_id=bookmaker_id,
                            observed_at=observed_at.isoformat(),
                        ),
                        observed_at,
                    )

    result: dict[str, MarketConsensus] = {}
    for candidate in candidate_list:
        identity = _h2h_candidate_identity(candidate)
        candidate_id = str(
            _candidate_value(candidate, "candidate_id") or ""
        ).strip()
        if identity is None or not candidate_id:
            continue
        selected = identity[2]
        raw_points = quotes.get(selected, {})
        points = tuple(
            observed[0]
            for _, observed in sorted(
                raw_points.items(),
                key=lambda item: item[0],
            )
        )
        summary = _summary_prices(sorted(point.odds for point in points))
        if summary is None:
            continue
        lowest, conservative, consensus, best = summary
        observed = [entry[1] for entry in raw_points.values()]
        result[candidate_id] = MarketConsensus(
            fixture_id=None,
            candidate_id=candidate_id,
            market_key="H2H",
            bet_name="h2h",
            value_name=str(
                _candidate_value(candidate, "selected_competitor")
            ).strip(),
            consensus_odds=consensus,
            conservative_odds=conservative,
            lowest_odds=lowest,
            best_odds=best,
            bookmaker_count=len(points),
            quoted_at=max(observed).isoformat() if observed else None,
            fetched_at=current.isoformat(),
            source=ODDS_API_REFERENCE_SOURCE,
            points=points,
            provider_event_id=provider_event_id,
            scheduled_start=_utc_iso(payload.get("commence_time")),
            event_home=_required_text(payload.get("home_team")),
            event_away=_required_text(payload.get("away_team")),
        )
    return result


def _odds_api_json(
    path: str,
    api_key: str,
    *,
    params: Optional[Mapping[str, object]] = None,
    timeout: int = 20,
) -> tuple[object, Optional[str]]:
    query = {"apiKey": api_key, **dict(params or {})}
    try:
        response = requests.get(
            f"{ODDS_API_BASE_URL}/{path.lstrip('/')}",
            params=query,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        # Do not include the exception text: requests may embed the request URL
        # and therefore the API key in it.
        return None, f"{type(exc).__name__}"
    except ValueError:
        return None, "ungueltige JSON-Antwort"


_GENERIC_TENNIS_COMPETITION_TOKENS = frozenset(
    {
        "tennis",
        "singles",
        "single",
        "open",
        "championship",
        "championships",
        "masters",
        "men",
        "women",
    }
)


def _competition_tokens(value: object) -> set[str]:
    return {
        token
        for token in _identity_name(value).split()
        if token not in _GENERIC_TENNIS_COMPETITION_TOKENS
    }


def _bounded_tennis_sport_keys(
    sports: Iterable[object],
    candidates: Iterable[object],
) -> tuple[list[str], Optional[str]]:
    tennis_rows = [
        row
        for row in sports
        if isinstance(row, Mapping)
        and row.get("active") is not False
        and (
            _normalize(row.get("group")) == "tennis"
            or str(row.get("key") or "").strip().startswith("tennis_")
        )
        and str(row.get("key") or "").strip()
    ]
    all_keys = sorted(
        {str(row.get("key") or "").strip() for row in tennis_rows}
    )
    if len(all_keys) <= MAX_TENNIS_EVENT_DISCOVERY_KEYS:
        return all_keys, None

    selected: set[str] = set()
    for candidate in candidates:
        wanted = _competition_tokens(
            _candidate_value(candidate, "competition")
        )
        if not wanted:
            return [], (
                "Zu viele aktive Tennis-Konkurrenzen und keine eindeutige "
                "Turnierzuordnung"
            )
        matches: set[str] = set()
        for row in tennis_rows:
            offered = _competition_tokens(
                f"{row.get('title') or ''} {row.get('description') or ''}"
            )
            if wanted and offered and (
                wanted <= offered or offered <= wanted
            ):
                matches.add(str(row.get("key") or "").strip())
        if not matches:
            return [], (
                "Tennis-Turnier konnte keinem aktiven Provider-Sportkey "
                "eindeutig zugeordnet werden"
            )
        selected.update(matches)
    if len(selected) > MAX_TENNIS_EVENT_DISCOVERY_KEYS:
        return [], (
            "Tennis-Turnierzuordnung ueberschreitet das sichere "
            "Requestlimit"
        )
    return sorted(selected), None


def fetch_tennis_h2h_consensus(
    api_key: str,
    candidates: Iterable[object],
    *,
    timeout: int = 20,
    now: Optional[datetime] = None,
) -> tuple[dict[str, MarketConsensus], list[str]]:
    """Fetch exact current H2H prices for persisted tennis model rows.

    The free sports/events discovery endpoints identify one provider event
    first. Only then is its real H2H market requested. Ambiguous or unmatched
    events remain unpriced instead of being guessed from similar names.
    """
    current = _as_utc(now or datetime.now(timezone.utc))
    key = str(api_key or "").strip()
    if not key:
        return {}, ["The-Odds-API-Key fuer Tennisquoten fehlt"]
    candidate_list = [
        candidate
        for candidate in candidates
        if _normalize(_candidate_value(candidate, "sport")) == "tennis"
        and _h2h_candidate_identity(candidate) is not None
        and str(_candidate_value(candidate, "candidate_id") or "").strip()
    ]
    if not candidate_list:
        return {}, []

    sports_payload, sports_error = _odds_api_json(
        "sports/",
        key,
        timeout=timeout,
    )
    if sports_error is not None or not isinstance(sports_payload, list):
        return {}, [
            f"Tennis-Sportliste: {sports_error or 'ungueltige Antwort'}"
        ]
    sport_keys, sport_key_error = _bounded_tennis_sport_keys(
        sports_payload,
        candidate_list,
    )
    if sport_key_error is not None:
        return {}, [sport_key_error]
    if not sport_keys:
        return {}, ["The Odds API meldet keine aktive Tennis-Konkurrenz"]

    scheduled_values = [
        identity[3]
        for identity in (
            _h2h_candidate_identity(candidate)
            for candidate in candidate_list
        )
        if identity is not None
    ]
    time_from = min(scheduled_values) - ODDS_API_EVENT_TOLERANCE
    time_to = max(scheduled_values) + ODDS_API_EVENT_TOLERANCE
    matches: dict[str, dict[tuple[str, str], Mapping[str, object]]] = {
        str(_candidate_value(candidate, "candidate_id")): {}
        for candidate in candidate_list
    }
    errors: list[str] = []
    event_params = {
        "dateFormat": "iso",
        "commenceTimeFrom": time_from.isoformat().replace("+00:00", "Z"),
        "commenceTimeTo": time_to.isoformat().replace("+00:00", "Z"),
    }
    event_results: dict[str, tuple[object, Optional[str]]] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(sport_keys))) as executor:
        futures = {
            executor.submit(
                _odds_api_json,
                f"sports/{sport_key}/events",
                key,
                params=event_params,
                timeout=min(timeout, TENNIS_EVENT_DISCOVERY_TIMEOUT),
            ): sport_key
            for sport_key in sport_keys
        }
        for future in as_completed(futures):
            sport_key = futures[future]
            try:
                event_results[sport_key] = future.result()
            except Exception as exc:
                event_results[sport_key] = (
                    None,
                    f"{type(exc).__name__}",
                )

    for sport_key in sport_keys:
        events_payload, event_error = event_results.get(
            sport_key,
            (None, "keine Antwort"),
        )
        if event_error is not None:
            errors.append(f"Tennis-Events {sport_key}: {event_error}")
            continue
        if not isinstance(events_payload, list):
            errors.append(f"Tennis-Events {sport_key}: ungueltige Antwort")
            continue
        for event in events_payload:
            if not isinstance(event, Mapping):
                continue
            event_id = str(event.get("id") or "").strip()
            if not event_id:
                continue
            for candidate in candidate_list:
                if _h2h_event_matches(event, candidate):
                    candidate_id = str(
                        _candidate_value(candidate, "candidate_id")
                    )
                    matches[candidate_id][(sport_key, event_id)] = event

    grouped_events: dict[tuple[str, str], list[object]] = {}
    for candidate in candidate_list:
        candidate_id = str(_candidate_value(candidate, "candidate_id"))
        candidate_matches = matches.get(candidate_id, {})
        if len(candidate_matches) != 1:
            if len(candidate_matches) > 1:
                errors.append(
                    f"Tennisquote {candidate_id}: Ereignis nicht eindeutig"
                )
            continue
        event_key = next(iter(candidate_matches))
        grouped_events.setdefault(event_key, []).append(candidate)

    result: dict[str, MarketConsensus] = {}
    for (sport_key, event_id), event_candidates in grouped_events.items():
        odds_payload, odds_error = _odds_api_json(
            f"sports/{sport_key}/events/{event_id}/odds",
            key,
            params={
                "regions": "eu",
                "markets": "h2h",
                "dateFormat": "iso",
                "oddsFormat": "decimal",
            },
            timeout=timeout,
        )
        if odds_error is not None:
            errors.append(f"Tennisquote {event_id}: {odds_error}")
            continue
        result.update(
            parse_h2h_event_consensus(
                odds_payload,
                event_candidates,
                fetched_at=current,
            )
        )
    return result, errors


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
    "ODDS_API_REFERENCE_SOURCE",
    "QuotePoint",
    "REFERENCE_FETCH_MAX_AGE",
    "REFERENCE_QUOTE_MAX_AGE",
    "REFERENCE_SOURCE",
    "ReferencePriceStatus",
    "challenge_quote_matches_candidate",
    "deserialize_consensus_map",
    "exact_market_target",
    "fetch_football_consensus",
    "fetch_tennis_h2h_consensus",
    "parse_h2h_event_consensus",
    "parse_fixture_consensus",
    "quote_matches_candidate",
    "reference_price_status",
    "serialize_consensus_map",
    "wettfinder_consensus",
    "wettfinder_reference_price_status",
]
