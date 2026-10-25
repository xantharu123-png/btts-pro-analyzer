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
from dataclasses import asdict, dataclass, replace
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from statistics import median
from time import monotonic
from typing import Any, Iterable, Mapping, MutableMapping, Optional
import unicodedata

import requests

from api_budget import (
    APIBudgetError, APIBudgetExceeded, APIBudgetPriority, APIBudgetUnavailable,
    api_football_get,
)
from odds_api_client import odds_api_get
from betting_math import (
    MINIMUM_RECOMMENDED_DECIMAL_ODDS,
    BettingMathError,
    validate_decimal_odds,
)


REFERENCE_SOURCE = "API-Football Mehrbuchmacher"
ODDS_API_REFERENCE_SOURCE = "The Odds API Mehrbuchmacher"
TEAM_PRICE_SOURCES = {
    "basketball": "API-Basketball Abrufbeobachtung",
    "ice_hockey": "API-Hockey Abrufbeobachtung",
}
ESPORTS_PRICE_SOURCE = "OddsPapi E-Sport Abrufbeobachtung"
OBSERVATION_SOURCES = frozenset((*TEAM_PRICE_SOURCES.values(), ESPORTS_PRICE_SOURCE))


def esports_discipline(value: object) -> Optional[int]:
    """Verified native sport IDs; no generic esports/name-only cross-game join."""
    return {"cs2": 17, "csgo": 17, "counter-strike": 17,
            "lol": 18, "league of legends": 18,
            "dota2": 16, "dota 2": 16, "valorant": 61}.get(str(value or "").strip().casefold())


ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
ODDS_API_EVENT_TOLERANCE = timedelta(hours=2)
FOOTBALL_QUOTE_START_TOLERANCE = timedelta(minutes=5)
TENNIS_QUOTE_START_TOLERANCE = timedelta(minutes=30)
MAX_TENNIS_EVENT_DISCOVERY_KEYS = 8
TENNIS_EVENT_DISCOVERY_TIMEOUT = 5
# Match the existing bounded daily tennis model catalog. Both delivered winner
# sides must survive a later favorite change without an additional API request.
TENNIS_PRICE_MAX_EVENTS = 1_200
TENNIS_PRICE_MAX_SIDES = 2 * TENNIS_PRICE_MAX_EVENTS
TENNIS_PRICE_MAX_BYTES = 8 * 1024 * 1024
# Both Echtgeld consumers require a realistically executable quote when the
# user sees it.  Keeping a wider 15K window made a recently fetched aggregate
# appear current even when one or more contributing offers were many hours old.
# Use the same strict retrieval and per-offer clocks for both workflows.
REFERENCE_FETCH_MAX_AGE = timedelta(minutes=35)
REFERENCE_QUOTE_MAX_AGE = timedelta(minutes=45)
WETTFINDER_FETCH_MAX_AGE = timedelta(minutes=35)
WETTFINDER_QUOTE_MAX_AGE = timedelta(minutes=45)
# Presentation only. API-Football updates pre-match odds about every 3 hours;
# retaining the last observation must never extend the execution window above.
QUOTE_DISPLAY_MAX_AGE = timedelta(hours=24)
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
    origin_provider: Optional[str] = None
    origin_event_id: Optional[str] = None
    event_discipline: Optional[int] = None
    # Optional measurement sidecar. Never used in probabilities or admission.
    native_market_partitions: tuple[dict, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.event_discipline is None:
            # Keep legacy quote serialization unchanged (including financial history).
            payload.pop('event_discipline')
        if not self.native_market_partitions:
            payload.pop('native_market_partitions')
        else:
            # The live document and its stored JSON must expose the same
            # container type, just as the existing points field does.
            payload['native_market_partitions'] = list(payload['native_market_partitions'])
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
                origin_provider=payload.get("origin_provider"),
                origin_event_id=payload.get("origin_event_id"),
                event_discipline=payload.get("event_discipline"),
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
                *OBSERVATION_SOURCES,
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
        if quote.source in OBSERVATION_SOURCES and (
            quote.fixture_id is not None or not quote.provider_event_id
            or not isinstance(quote.origin_provider, str) or not quote.origin_provider.strip()
            or not isinstance(quote.origin_event_id, str) or not quote.origin_event_id.strip()
            or any(point.observed_at != quote.fetched_at for point in quote.points)
        ):
            return None
        if quote.source == ESPORTS_PRICE_SOURCE and (
            type(quote.event_discipline) is not int
            or quote.event_discipline not in {16, 17, 18, 61}
            or quote.origin_provider != "pandascore"
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
        return replace(quote, native_market_partitions=validated_native_partitions(
            payload.get('native_market_partitions', ()), quote))

    def is_fresh(self, now: Optional[datetime] = None) -> bool:
        """Require the fetch and every contributing offer to be current.

        ``quoted_at`` is an aggregate (the newest point), so checking only that
        clock can hide stale contributors. Legacy snapshots without individual
        point timestamps remain readable but are deliberately not actionable.
        """

        if self.source in OBSERVATION_SOURCES:
            return False  # These APIs expose retrieval time, not the bookmaker's update time.
        quoted = _parse_utc(self.quoted_at)
        fetched = _parse_utc(self.fetched_at)
        point_times = [_parse_utc(point.observed_at) for point in self.points]
        if (
            quoted is None
            or fetched is None
            or not point_times
            or any(observed is None for observed in point_times)
        ):
            return False
        current = _as_utc(now or datetime.now(timezone.utc))
        quote_age = current - quoted
        fetch_age = current - fetched
        return (
            timedelta(minutes=-1) <= quote_age <= REFERENCE_QUOTE_MAX_AGE
            and timedelta(minutes=-1) <= fetch_age <= REFERENCE_FETCH_MAX_AGE
            and all(
                timedelta(minutes=-1)
                <= current - observed
                <= REFERENCE_QUOTE_MAX_AGE
                for observed in point_times
                if observed is not None
            )
            and all(
                timedelta(minutes=-1)
                <= fetched - observed
                <= REFERENCE_QUOTE_MAX_AGE
                for observed in point_times
                if observed is not None
            )
        )

    def is_wettfinder_fresh(self, now: Optional[datetime] = None) -> bool:
        """Require every contributing offer to satisfy the normal live window."""

        if self.source in OBSERVATION_SOURCES:
            return False
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


def native_partition(market_key, period, bookmaker_id, observed_at, fetched_at, outcomes):
    """Small actual-price partition; never synthesize an opposing offer."""
    return dict(market_key=market_key, period=period, bookmaker_id=bookmaker_id,
        observed_at=observed_at, fetched_at=fetched_at,
        outcomes=[dict(selection=selection, odds=odds) for selection, odds in outcomes])


def validated_native_partitions(raw, quote):
    """Optional malformed evidence is dropped without changing a valid offer."""
    if not isinstance(raw, (list, tuple)) or len(raw) > 100:
        return ()
    contract = native_partition_contract(quote)
    if contract is None:
        return ()
    family, period, expected, selected = contract
    name_key = _tennis_identity_name if period == 'tennis_match' else lambda value: value
    valid, conflicts = {}, set()
    for part in raw:
        try:
            if not isinstance(part, Mapping) or set(part) != {
                    'market_key', 'period', 'bookmaker_id', 'observed_at', 'fetched_at', 'outcomes'}:
                continue
            if not all(isinstance(part[key], str) and 0 < len(part[key]) <= 300
                       for key in ('market_key', 'period', 'bookmaker_id')):
                continue
            observed, fetched = _parse_utc(part['observed_at']), _parse_utc(part['fetched_at'])
            if (observed is None or fetched is None or not observed <= fetched == _parse_utc(quote.fetched_at)
                    or part['market_key'] != family or part['period'] != period
                    or not any(point.bookmaker_id == part['bookmaker_id']
                               and _parse_utc(point.observed_at) == observed for point in quote.points)):
                continue
            outcomes = part['outcomes']
            if (not isinstance(outcomes, (list, tuple)) or not 2 <= len(outcomes) <= 16
                    or any(not isinstance(item, Mapping) or set(item) != {'selection', 'odds'}
                           or not isinstance(item['selection'], str) or not 0 < len(item['selection']) <= 300
                           for item in outcomes)):
                continue
            names = [item['selection'] for item in outcomes]
            if len(names) != len(set(map(name_key, names))) or set(map(name_key, names)) != set(map(name_key, expected)):
                continue
            canonical = native_partition(part['market_key'], part['period'], part['bookmaker_id'],
                observed.isoformat(), fetched.isoformat(),
                [(item['selection'], validate_decimal_odds(item['odds'])) for item in outcomes])
            if selected is not None and not any(
                    point.bookmaker_id == part['bookmaker_id'] and _parse_utc(point.observed_at) == observed
                    and next(item['odds'] for item in canonical['outcomes']
                             if name_key(item['selection']) == name_key(selected)) == point.odds
                    for point in quote.points):
                continue
            identity = tuple(canonical[key] for key in ('market_key', 'period', 'bookmaker_id', 'observed_at', 'fetched_at'))
            if identity in valid and valid[identity] != canonical:
                conflicts.add(identity)
            valid[identity] = canonical
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
    return tuple(part for key, part in sorted(valid.items()) if key not in conflicts)


def native_partition_contract(quote):
    """Exact exhaustive price contract; overlapping DC is derived from 1X2."""
    if quote.source == REFERENCE_SOURCE:
        wanted = _football_partition_targets(quote.market_key)
        if wanted is None:
            return None
        family, targets = wanted
        selected = (None if quote.market_key.startswith('DC_') else
                    quote.market_key.removeprefix('RESULT_') if family == 'RESULT' else
                    quote.market_key.removeprefix('BTTS_') if family == 'BTTS' else
                    'OVER' if '_OVER_' in quote.market_key else 'UNDER')
        return family, 'football_90_minutes', tuple(side for side, _ in targets), selected
    periods = {ODDS_API_REFERENCE_SOURCE: 'tennis_match', ESPORTS_PRICE_SOURCE: 'esports_series',
               TEAM_PRICE_SOURCES['basketball']: 'including_overtime',
               TEAM_PRICE_SOURCES['ice_hockey']: 'including_overtime_shootout'}
    name_key = _tennis_identity_name if quote.source == ODDS_API_REFERENCE_SOURCE else lambda value: value
    if (quote.market_key == 'H2H' and quote.source in periods and quote.event_home and quote.event_away
            and name_key(quote.event_home) != name_key(quote.event_away)
            and name_key(quote.value_name) in (name_key(quote.event_home), name_key(quote.event_away))):
        return 'H2H', periods[quote.source], (quote.event_home, quote.event_away), quote.value_name
    return None


def _football_partition_targets(market_key):
    if market_key.startswith('RESULT_') or market_key in {'DC_1X', 'DC_X2', 'DC_12'}:
        return 'RESULT', [(side, exact_market_target('RESULT_'+side)) for side in ('HOME', 'DRAW', 'AWAY')]
    if market_key in {'BTTS_YES', 'BTTS_NO'}:
        return 'BTTS', [(side, exact_market_target('BTTS_'+side)) for side in ('YES', 'NO')]
    match = re.fullmatch(r'(TOTAL|HOME|AWAY|CORNERS|HOME_CORNERS|AWAY_CORNERS|YELLOW|HOME_YELLOW|AWAY_YELLOW)_(OVER|UNDER)_(\d+)_5', market_key)
    if match:
        prefix, _, line = match.groups()
        return f'{prefix}_{line}_5', [(side, exact_market_target(f'{prefix}_{side}_{line}_5')) for side in ('OVER', 'UNDER')]
    return None


def _football_native_partitions(market_key, fixture_id, points, quotes):
    wanted = _football_partition_targets(market_key)
    if wanted is None:
        return ()
    family, targets = wanted
    result = []
    for point in points:
        members = []
        for side, target in targets:
            if target is None:
                break
            found = [item for item in quotes.get((fixture_id, _normalize(target[0]), _normalize(target[1])), {}).values()
                     if item[0].bookmaker_id == point.bookmaker_id and item[0].observed_at == point.observed_at]
            if len(found) != 1:
                break
            members.append((side, found[0]))
        if len(members) == len(targets) and len({item[1][2] for item in members}) == 1:
            result.append(native_partition(family, 'football_90_minutes', point.bookmaker_id,
                point.observed_at, members[0][1][2].isoformat(), [(side, item[0].odds) for side, item in members]))
    return tuple(result)


_DOUBLE_CHANCE_SIDES = {'DC_1X': ('HOME', 'DRAW'), 'DC_X2': ('DRAW', 'AWAY'), 'DC_12': ('HOME', 'AWAY')}


def no_vig_market_probability(quote: "MarketConsensus") -> Optional[float]:
    """Median no-vig probability of the quote's selected side across bookmaker partitions.

    Each ``native_market_partitions`` entry holds one bookmaker's complete,
    exhaustive market (all sides, same observation). Shin removes the margin
    for three or more outcomes, Power for two (betting_math). Double chance is
    the sum of its two 1X2 sides. ``None`` without complete partitions: the
    caller must then fall back explicitly, never to a one-sided implied price.
    This is a market benchmark; it never changes a model probability.
    """
    from statistics import median
    from betting_math import no_vig_market
    contract = native_partition_contract(quote)
    if contract is None or not quote.native_market_partitions:
        return None
    family, period, expected, selected = contract
    name_key = _tennis_identity_name if period == 'tennis_match' else (lambda value: value)
    if selected is None:
        sides = _DOUBLE_CHANCE_SIDES.get(quote.market_key)
        if sides is None:
            return None
        wanted = [name_key(side) for side in sides]
    else:
        wanted = [name_key(selected)]
    values = []
    for part in quote.native_market_partitions:
        outcomes = part.get('outcomes') if isinstance(part, Mapping) else None
        if not isinstance(outcomes, (list, tuple)) or len(outcomes) < 2:
            continue
        try:
            law = no_vig_market([item['odds'] for item in outcomes], 'shin' if len(outcomes) >= 3 else 'power')
        except (BettingMathError, KeyError, TypeError):
            continue
        by_name = {name_key(item['selection']): probability
                   for item, probability in zip(outcomes, law.no_vig_probabilities)}
        if not all(name in by_name for name in wanted):
            continue
        values.append(sum(by_name[name] for name in wanted))
    if not values:
        return None
    return float(median(values))


@dataclass(frozen=True)
class ReferencePriceStatus:
    code: str
    label: str
    usable_odds: Optional[float]
    bookmaker: Optional[str] = None
    bookmaker_id: Optional[str] = None
    observed_at: Optional[str] = None
    # Transparency for the edge cap: which market probability was compared.
    market_probability: Optional[float] = None
    market_basis: Optional[str] = None


EDGE_CAP_FLAG = "BETBOY_EDGE_CAP_PP"
# Owner decision 23.10.2026 (docs/audits/2026-10-23-preisregel-1-20.md): the
# bookmaker feed is no longer a release gate and is not shown in the app. Public
# tips follow the model and the context gates; the only price rule is the 1.20
# floor, checked in the background against the last observed market quote.
# ``BETBOY_PRICE_POLICY=gate`` restores the previous execution contract
# (freshness windows, lower quartile, model minimum odds, execution proof).
PRICE_POLICY_FLAG = "BETBOY_PRICE_POLICY"
PRICE_POLICY_FLOOR = "floor"
PRICE_POLICY_GATE = "gate"
FLOOR_PRICE_MAX_AGE = QUOTE_DISPLAY_MAX_AGE
# Owner decision 25.10.2026 (docs/audits/2026-10-25-preispruefung-dreistufig.md):
# the 1.20 floor is a three-stage check. (1) A direct quote: the median of the
# bookmaker prices observed within 24 hours must reach 1.20 (the user's book
# rarely pays the best price). (2) A goal range without a direct quote: a bound
# derived from the over/under lines of the same team or match decides, with a
# typical bookmaker margin. (3) Without any price evidence the model guard
# decides: from 65 % model probability a price of 1.20 is not plausible.
FLOOR_UNPRICED_MAX_PROBABILITY = 0.65
FLOOR_DERIVED_MARGIN = 0.06
FLOOR_BASIS_DERIVED = "derived-range-bound"
FLOOR_BASIS_MODEL = "model-guard"
FLOOR_BOUND_BASES = frozenset({"upper_bound", "line_difference"})
_RANGE_MARKET_KEY = re.compile(r"(HOME|AWAY|TOTAL)_RANGE_(\d+)_(\d+)")


def price_policy() -> str:
    import os
    raw = os.environ.get(PRICE_POLICY_FLAG, PRICE_POLICY_FLOOR).strip().lower()
    return PRICE_POLICY_GATE if raw == PRICE_POLICY_GATE else PRICE_POLICY_FLOOR


def floor_only_pricing() -> bool:
    """True when price is only the 1.20 floor (default since 23.10.2026)."""
    return price_policy() == PRICE_POLICY_FLOOR


def floor_price_status(
    quote: Optional[MarketConsensus],
    *,
    now: Optional[datetime] = None,
) -> ReferencePriceStatus:
    """1.20 floor against the last observed market quote; never a release gate.

    ``UNPRICED`` (no quote, or none observed within 24 hours) keeps the tip
    visible: the user checks the 1.20 floor at the bookmaker. ``BELOW_FLOOR``
    means no bookmaker offered 1.20 or more, so the tip is withheld.
    """
    if quote is None or not quote.points:
        return ReferencePriceStatus(
            "UNPRICED", "Keine Marktquote beobachtet; Mindestquote 1,20 beim Buchmacher pruefen", None)
    current = _as_utc(now or datetime.now(timezone.utc))
    observed = []
    for point in quote.points:
        stamp = _point_observed_at(point, quote.quoted_at)
        if stamp is not None and timedelta(minutes=-1) <= current - stamp <= FLOOR_PRICE_MAX_AGE:
            observed.append(point)
    if not observed:
        return ReferencePriceStatus(
            "UNPRICED", "Letzte Marktquote ist aelter als 24 Stunden; Mindestquote 1,20 beim Buchmacher pruefen", None)
    # Owner decision 25.10.2026: the floor is checked against the median price;
    # the best price of up to nine books overstates what the user's book pays.
    if float(median(point.odds for point in observed)) + 1e-9 < MINIMUM_RECOMMENDED_DECIMAL_ODDS:
        return ReferencePriceStatus("BELOW_FLOOR", "Mittlere Marktquote liegt unter 1,20; kein Tipp", None)
    best = max(observed, key=lambda point: point.odds)
    return ReferencePriceStatus(
        "PLAYABLE", "Mittlere Marktquote ab 1,20 beobachtet; Preis beim Buchmacher pruefen", best.odds,
        bookmaker=best.bookmaker, bookmaker_id=best.bookmaker_id, observed_at=best.observed_at,
    )


def _fractional_probability(value: object) -> Optional[float]:
    """A model probability as a fraction; candidates in percent (e.g. 79.7) are scaled."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    probability = float(value)
    if not math.isfinite(probability) or probability <= 0.0 or probability > 100.0:
        return None
    return probability / 100.0 if probability > 1.0 else probability


def valid_price_bound(value: object, market_key: object) -> Optional[dict]:
    """A stored stage-2 bound for exactly this range market, normalised, or ``None``."""
    if not isinstance(value, Mapping):
        return None
    key = str(value.get("market_key") or "").strip().upper()
    if _RANGE_MARKET_KEY.fullmatch(key) is None or key != str(market_key or "").strip().upper():
        return None
    probability = value.get("probability")
    if (isinstance(probability, bool) or not isinstance(probability, (int, float))
            or not math.isfinite(float(probability)) or not 0.0 < float(probability) <= 1.0):
        return None
    basis = value.get("basis")
    observed = _parse_utc(value.get("observed_at"))
    sources = value.get("sources")
    if (basis not in FLOOR_BOUND_BASES or observed is None or not isinstance(sources, (list, tuple))
            or not sources or not all(isinstance(item, str) and item.strip() for item in sources)):
        return None
    return {"market_key": key, "probability": float(probability), "basis": basis,
            "sources": [str(item).strip() for item in sources], "observed_at": observed.isoformat()}


def _line_over_probability(siblings: Mapping[str, object], prefix: str, line: int,
                           current: datetime) -> Optional[tuple[float, datetime, str]]:
    """No-vig P(more than ``line`` goals) from a priced over or under sibling row."""
    for side in ("OVER", "UNDER"):
        key = f"{prefix}_{side}_{line}_5"
        row = siblings.get(key)
        if row is None:
            continue
        quote = MarketConsensus.from_dict(_candidate_value(row, "reference_quote"))
        if quote is None or not quote.points or not quote_matches_candidate(quote, row):
            continue
        stamps = [_point_observed_at(point, quote.quoted_at) for point in quote.points]
        if any(stamp is None for stamp in stamps):
            continue
        oldest = min(stamps)
        if current - oldest > FLOOR_PRICE_MAX_AGE or max(stamps) - current > timedelta(minutes=1):
            continue
        probability = no_vig_market_probability(quote)
        if probability is None or not 0.0 < probability < 1.0:
            continue
        return (probability if side == "OVER" else 1.0 - probability), oldest, key
    return None


def derive_range_price_bound(candidate: object, siblings: Mapping[str, object], *,
                             now: datetime) -> Optional[dict]:
    """Stage 2 of the floor: market probability of a goal range from its over/under lines.

    ``a-b`` goals is ``P(>= a) - P(>= b+1)``. With only the lower line the
    result is an upper bound (``P(a-b) <= P(>= a)``), so the derived price is
    a lower bound and the check stays on the safe side. ``siblings`` maps the
    market keys of the same fixture to rows carrying their own exact quote.
    """
    key = str(_candidate_value(candidate, "market_key") or "").strip().upper()
    match = _RANGE_MARKET_KEY.fullmatch(key)
    if match is None:
        return None
    prefix, low, high = match[1], int(match[2]), int(match[3])
    if low > high:
        return None
    current = _as_utc(now)
    upper = _line_over_probability(siblings, prefix, high, current)
    if low == 0:
        if upper is None:
            return None
        lower: tuple[float, Optional[datetime], Optional[str]] = (1.0, None, None)
    else:
        found = _line_over_probability(siblings, prefix, low - 1, current)
        if found is None:
            return None
        lower = found
    probability = lower[0] - (upper[0] if upper is not None else 0.0)
    if not math.isfinite(probability) or probability <= 0.0:
        return None  # inconsistent lines: no bound, the model guard decides
    parts = [part for part in (lower, upper) if part is not None and part[1] is not None]
    return {
        "market_key": key,
        "probability": round(min(probability, 1.0), 6),
        "basis": "line_difference" if upper is not None else "upper_bound",
        "sources": [part[2] for part in parts],
        "observed_at": min(part[1] for part in parts).isoformat(),
    }


def _unpriced_floor_status(
    status: ReferencePriceStatus,
    candidate: object,
    *,
    now: Optional[datetime],
    model_probability: Optional[float] = None,
) -> ReferencePriceStatus:
    """Stages 2 and 3 for a candidate without a current direct quote."""
    current = _as_utc(now or datetime.now(timezone.utc))
    bound = valid_price_bound(_candidate_value(candidate, "reference_price_bound"),
                              _candidate_value(candidate, "market_key"))
    if bound is not None and current - _parse_utc(bound["observed_at"]) <= FLOOR_PRICE_MAX_AGE:
        derived_odds = 1.0 / (bound["probability"] * (1.0 + FLOOR_DERIVED_MARGIN))
        if derived_odds + 1e-9 < MINIMUM_RECOMMENDED_DECIMAL_ODDS:
            return ReferencePriceStatus(
                "BELOW_FLOOR", "Keine direkte Marktquote; aus den Torlinien abgeleiteter Preis liegt unter 1,20; kein Tipp",
                None, market_probability=bound["probability"], market_basis=FLOOR_BASIS_DERIVED)
        return ReferencePriceStatus(
            "UNPRICED", "Keine direkte Marktquote; die Torlinien belegen einen Preis ab 1,20",
            None, market_probability=bound["probability"], market_basis=FLOOR_BASIS_DERIVED)
    probability = _fractional_probability(
        model_probability if model_probability is not None else _candidate_value(candidate, "probability"))
    if probability is not None and probability >= FLOOR_UNPRICED_MAX_PROBABILITY:
        return ReferencePriceStatus(
            "BELOW_FLOOR", "Keine Marktquote; ab 65 % Modellwahrscheinlichkeit ist ein Preis ab 1,20 nicht belegbar; kein Tipp",
            None, market_basis=FLOOR_BASIS_MODEL)
    return status


def edge_cap_pp() -> Optional[float]:
    """Optional cap on the admissible model-minus-market edge in percentage points.

    Audit 2026-10-16 K3 and the benchmark replay of 2026-10-20: the price gate
    selects the fixtures where the model deviates most from the market; a cap
    of 8 pp lifted the replayed policy from -5.5 % to +0.8 % ROI (interval
    contains zero, in-sample). Off unless ``BETBOY_EDGE_CAP_PP`` holds a
    positive number; pre-registered in docs/superpowers/plans/2026-10-21-edge-cap.md.
    """
    import os
    raw = os.environ.get(EDGE_CAP_FLAG, "").strip()
    if not raw:
        return None
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return None
    return value if math.isfinite(value) and value > 0.0 else None


def _edge_cap_status(quote: MarketConsensus, model_probability: Optional[float]) -> Optional[ReferencePriceStatus]:
    """Demote a playable price when the model sits too far above the market consensus."""
    cap = edge_cap_pp()
    if cap is None or model_probability is None:
        return None
    try:
        probability = float(model_probability)
    except (TypeError, ValueError):
        return None
    if isinstance(model_probability, bool) or not math.isfinite(probability) or not 0.0 < probability < 1.0:
        return None
    market_probability = no_vig_market_probability(quote)
    basis = "no-vig"
    if market_probability is None:
        consensus = quote.consensus_odds
        if consensus is None or not math.isfinite(consensus) or consensus <= 1.0:
            return None
        # Fallback: the consensus implied probability still contains the margin,
        # so it overstates the market probability and makes the cap stricter.
        market_probability, basis = 1.0 / consensus, "consensus-implied"
    edge = 100.0 * (probability - market_probability)
    if edge <= cap:
        return None
    return ReferencePriceStatus(
        "EDGE_CAP",
        f"Modell liegt {edge:.1f} Prozentpunkte ueber dem Markt ({basis}); Kappung bei {cap:.0f}",
        None,
        market_probability=market_probability,
        market_basis=basis,
    )


def reference_price_status(
    quote: Optional[MarketConsensus],
    minimum_odds: Optional[float],
    *,
    now: Optional[datetime] = None,
    model_probability: Optional[float] = None,
) -> ReferencePriceStatus:
    """Classify a reference price without changing the model forecast."""
    if floor_only_pricing():
        return floor_price_status(quote, now=now)
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
    executable = quote.executable_point
    if quote.conservative_odds + 1e-9 >= threshold and executable is not None:
        capped = _edge_cap_status(quote, model_probability)
        if capped is not None:
            return capped
        return ReferencePriceStatus(
            "PLAYABLE",
            "Marktpreis liegt konservativ ueber der Mindestquote",
            executable.odds,
            bookmaker=executable.bookmaker,
            bookmaker_id=executable.bookmaker_id,
            observed_at=executable.observed_at,
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
    if quote.source == ESPORTS_PRICE_SOURCE:
        return "oddspapi:"
    for sport, source in TEAM_PRICE_SOURCES.items():
        if quote.source == source:
            return f"api-sports-{sport}:"
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

    One old or unidentified point must not poison an otherwise valid normal
    three-book market, so Q25, median, best and the executable offer are
    recomputed only from the current provider-native subset.
    """

    if not isinstance(quote, MarketConsensus) or quote.source in OBSERVATION_SOURCES:
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


def quote_below_publication_floor(quote: object, *, candidate: object, now: Optional[datetime] = None) -> bool:
    """Exclude an exact observed best offer below the user floor.

    This is a downstream display rule, not a probability/value calculation.
    This preference uses the last known price (up to the display TTL), not
    the stricter executable-price clock. Missing/foreign/malformed evidence
    never implies short odds. Old prices remain labelled old in the UI.
    """
    try:
        quote = MarketConsensus.from_dict(quote.to_dict() if isinstance(quote, MarketConsensus) else quote)
    except (TypeError, ValueError, AttributeError):
        return False
    if quote is None or not quote_matches_candidate(quote, candidate):
        return False
    current = wettfinder_consensus(quote, now=now) or observed_consensus(quote, candidate=candidate, now=now)
    # Compare unrounded native offers, not the six-decimal display aggregate.
    if current is None:
        return False
    # Owner decision 25.10.2026: under the floor policy the median price decides.
    reference = (float(median(p.odds for p in current.points)) if floor_only_pricing()
                 else max(p.odds for p in current.points))
    return reference < MINIMUM_RECOMMENDED_DECIMAL_ODDS


def observed_consensus(quote: object, *, candidate: object, now: Optional[datetime] = None) -> Optional[MarketConsensus]:
    """Last exact provider observation for display, never execution approval."""
    try:
        parsed = MarketConsensus.from_dict(quote.to_dict() if isinstance(quote, MarketConsensus) else quote)
    except (TypeError, ValueError, AttributeError):
        return None
    if parsed is None or not quote_matches_candidate(parsed, candidate):
        return None
    current = _as_utc(now or datetime.now(timezone.utc))
    fetched = _parse_utc(parsed.fetched_at)
    if parsed.source in OBSERVATION_SOURCES:
        start = _parse_utc(parsed.scheduled_start)
        if start is None or start <= current:
            return None
    if fetched is None or not timedelta(minutes=-1) <= current - fetched <= QUOTE_DISPLAY_MAX_AGE:
        return None
    points = tuple(p for p in _wettfinder_identified_points(parsed)
                   if timedelta(minutes=-1) <= current - _parse_utc(p.observed_at) <= QUOTE_DISPLAY_MAX_AGE
                   and _parse_utc(p.observed_at) <= fetched + timedelta(minutes=1))
    if not points:
        return None
    from dataclasses import replace
    lowest, conservative, consensus, best = _summary_prices(sorted(point.odds for point in points))
    return replace(parsed, points=points, bookmaker_count=len(points),
                   consensus_odds=consensus, conservative_odds=conservative,
                   lowest_odds=lowest, best_odds=best,
                   quoted_at=max(_parse_utc(p.observed_at) for p in points).isoformat())


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
    model_probability: Optional[float] = None,
) -> ReferencePriceStatus:
    """Classify a quote under the normal Wettfinder execution contract.

    Normal Wettfinder callers add provider-native identity proof: an otherwise
    playable price is actionable only when
    the event/selection is exactly bound (when a candidate is supplied), the
    event start is present, and every contributing bookmaker has a stable
    provider ID plus its own parseable observation timestamp.
    """

    if floor_only_pricing():
        if quote is not None and candidate is not None and not quote_matches_candidate(quote, candidate):
            quote = None
        status = floor_price_status(quote, now=now)
        if status.code != "UNPRICED" or candidate is None:
            return status
        return _unpriced_floor_status(status, candidate, now=now, model_probability=model_probability)
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
    if quote.source in OBSERVATION_SOURCES:
        observed = observed_consensus(quote, candidate=candidate, now=now)
        return ReferencePriceStatus(
            "OBSERVED" if observed is not None else "UNAVAILABLE",
            "Quote abgerufen; Anbieterzeit unbekannt" if observed is not None else "Quote fehlt",
            None,
        )
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
    if model_probability is None and candidate is not None:
        model_probability = _candidate_value(candidate, "probability")
    status = reference_price_status(effective_quote, minimum_odds, now=now, model_probability=model_probability)
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
    # readable for audit/history; actionable freshness deliberately requires
    # the provider clock carried by every newly fetched point.
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


def _tennis_identity_name(value: object) -> str:
    """Match complete tennis names despite provider given/family-name order.

    Sorting keeps every normalized word, including repeated words. It never
    expands initials or accepts partial names, spelling similarities or extras.
    Other sports retain their existing order-sensitive identity contract.
    """
    return " ".join(sorted(_identity_name(value).split()))


def _line_from_key(market_key: str) -> Optional[str]:
    match = re.search(r"_(\d+)_(\d+)$", market_key)
    if not match:
        return None
    return f"{int(match.group(1))}.{int(match.group(2))}"


_RANGE_BET_NAMES = {
    "total goals number by ranges": (186, "Total Goals Number By Ranges"),
    "number of goals in match (range)": (223, "Total Goals Number By Ranges"),
    "number of goals in match": (349, "Total Goals Number By Ranges"),
    "home team exact goals number": (40, "Home Team Exact Goals Number"),
    "away team exact goals number": (41, "Away Team Exact Goals Number"),
}


def _literal_goal_range(value: object, *, candidate_selection: bool = False) -> Optional[str]:
    """Inclusive endpoints or an adjacent native pair; never disjoint sets/O-U."""
    suffix = r"(?:\s+Tore)?" if candidate_selection else ""
    match = re.fullmatch(r"\s*(\d+)\s*[-–]\s*(\d+)" + suffix + r"\s*", str(value or ""))
    if match is not None and int(match[1]) <= int(match[2]):
        return f"{int(match[1])}-{int(match[2])}"
    if not candidate_selection:
        adjacent = re.fullmatch(r"\s*(\d+)\s+or\s+(\d+)\s+goals\s*",
                                str(value or ""), flags=re.IGNORECASE)
        if adjacent is not None and int(adjacent[2]) == int(adjacent[1]) + 1:
            return f"{int(adjacent[1])}-{int(adjacent[2])}"
    return None


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
        "TOTAL_RANGE_2_3": ("Total Goals Number By Ranges", "2-3"),
    }
    if key in fixed:
        return fixed[key]
    ranged = re.fullmatch(r"(TOTAL|HOME|AWAY)_RANGE_(1_3|1_4|2_4)", key)
    if ranged:
        bet = {"TOTAL": "Total Goals Number By Ranges", "HOME": "Home Team Exact Goals Number",
               "AWAY": "Away Team Exact Goals Number"}[ranged[1]]
        return bet, ranged[2].replace("_", "-")
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
        if "_RANGE_" in market_key:
            return False
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

    if "_RANGE_" in market_key:
        target = exact_market_target(market_key)
        return target is not None and _literal_goal_range(raw, candidate_selection=True) == target[1]

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
    team_sport = {"basketball": "basketball", "eishockey": "ice_hockey", "ice_hockey": "ice_hockey"}.get(sport)
    if sport in {"e-sport", "esports", "e sport"} and not fixture_is_valid:
        a = _identity_name(_candidate_value(candidate, "competitor_a"))
        b = _identity_name(_candidate_value(candidate, "competitor_b"))
        selected = _identity_name(_candidate_value(candidate, "selected_competitor"))
        return (
            source in {"", "esports_shadow", "automated_wettfinder_forecast"} and market_key == "H2H"
            and quote.source == ESPORTS_PRICE_SOURCE and quote.fixture_id is None
            and type(quote.event_discipline) is int
            and quote.event_discipline == esports_discipline(_candidate_value(candidate, "competition"))
            and quote.origin_provider == _candidate_value(candidate, "fixture_source") == "pandascore"
            and bool(quote.origin_event_id) and bool(quote.provider_event_id)
            and quote.origin_event_id == str(_candidate_value(candidate, "provider_event_id") or "")
            and quote.bet_name == "Series Winner" and bool(a) and bool(b) and a != b
            and _identity_name(quote.event_home) == a and _identity_name(quote.event_away) == b
            and selected in {a, b} and _identity_name(quote.value_name) == selected
            and _event_start_matches(quote, candidate, timedelta(minutes=5))
        )
    if team_sport and not fixture_is_valid:
        return (
            market_key == "H2H" and quote.fixture_id is None
            and quote.source == TEAM_PRICE_SOURCES[team_sport]
            and quote.origin_provider == _candidate_value(candidate, "fixture_source")
            and quote.origin_event_id == str(_candidate_value(candidate, "provider_event_id") or "")
            and bool(quote.provider_event_id)
            and quote.bet_name == "Home/Away including overtime"
            and _identity_name(quote.event_home) == _identity_name(_candidate_value(candidate, "competitor_a"))
            and _identity_name(quote.event_away) == _identity_name(_candidate_value(candidate, "competitor_b"))
            and bool(_identity_name(quote.event_home)) and bool(_identity_name(quote.event_away))
            and _identity_name(quote.event_home) != _identity_name(quote.event_away)
            and _identity_name(quote.value_name) == _identity_name(_candidate_value(candidate, "selected_competitor"))
            and _identity_name(quote.value_name) in {_identity_name(quote.event_home), _identity_name(quote.event_away)}
            and _event_start_matches(quote, candidate, timedelta(seconds=1))
        )
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
            and _normalize(_RANGE_BET_NAMES.get(_normalize(quote.bet_name), (None, quote.bet_name))[1]) == _normalize(bet_name)
            and (_literal_goal_range(quote.value_name) == value_name if "_RANGE_" in market_key
                 else _normalize(quote.value_name) == _normalize(value_name))
            and _football_candidate_selection_matches(
                candidate,
                market_key,
            )
        )
    if is_tennis:
        selected = _tennis_identity_name(
            _candidate_value(candidate, "selected_competitor")
        )
        competitors = {
            _tennis_identity_name(_candidate_value(candidate, "competitor_a")),
            _tennis_identity_name(_candidate_value(candidate, "competitor_b")),
        }
        quoted_competitors = {
            _tennis_identity_name(quote.event_home),
            _tennis_identity_name(quote.event_away),
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
            and _tennis_identity_name(quote.value_name) == selected
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


def _quote_diagnostic(
    diagnostics: Optional[MutableMapping[str, dict[str, Any]]],
    candidates: Iterable[object],
    reason_code: str,
    *,
    fetched_at: Optional[datetime] = None,
    checked_at: Optional[datetime] = None,
    provider_updated_at: Optional[datetime] = None,
    bookmaker_count: Optional[int] = None,
    error_type: Optional[str] = None,
    http_status: Optional[int] = None,
) -> None:
    """Write only bounded receipt facts, never provider text or payloads."""
    if diagnostics is None:
        return
    record: dict[str, Any] = {"reason_code": reason_code}
    for field, moment in (("fetched_at", fetched_at), ("checked_at", checked_at),
                          ("provider_updated_at", provider_updated_at)):
        if moment is not None:
            record[field] = _as_utc(moment).isoformat()
    if bookmaker_count is not None:
        record["bookmaker_count"] = bookmaker_count
    if error_type in {
        "MISSING_CREDENTIAL", "BUDGET_EXHAUSTED", "BUDGET_UNAVAILABLE", "BUDGET_ERROR",
        "HTTP_ERROR", "TIMEOUT", "REQUEST_ERROR", "INVALID_RESPONSE", "PROVIDER_ERROR",
        "INCOMPLETE_PAGINATION",
    }:
        record["error_type"] = error_type
    if type(http_status) is int and 100 <= http_status <= 599:
        record["http_status"] = http_status
    for candidate in candidates:
        candidate_id = str(_candidate_value(candidate, "candidate_id") or "").strip()
        if candidate_id:
            diagnostics[candidate_id] = dict(record)


def _request_error_facts(error: BaseException) -> dict[str, Any]:
    """Classify actual exception/status facts without serializing its text."""
    if isinstance(error, APIBudgetExceeded):
        return {"error_type": "BUDGET_EXHAUSTED"}
    if isinstance(error, APIBudgetUnavailable):
        transport_error_type = getattr(error, "transport_error_type", None)
        if transport_error_type in {"TIMEOUT", "REQUEST_ERROR"}:
            return {"error_type": transport_error_type}
        return {"error_type": "BUDGET_UNAVAILABLE"}
    if isinstance(error, APIBudgetError):
        return {"error_type": "BUDGET_ERROR"}
    if isinstance(error, requests.Timeout):
        return {"error_type": "TIMEOUT"}
    if isinstance(error, requests.HTTPError):
        facts: dict[str, Any] = {"error_type": "HTTP_ERROR"}
        status = getattr(error.response, "status_code", None)
        if type(status) is int and 100 <= status <= 599:
            facts["http_status"] = status
        return facts
    return {"error_type": "INVALID_RESPONSE" if isinstance(error, ValueError) else "REQUEST_ERROR"}


def _quote_clock_reason(observed: Optional[datetime], fetched: datetime) -> str:
    if observed is None or fetched - observed < timedelta(minutes=-1):
        return "BAD_CLOCK"
    if fetched - observed > REFERENCE_QUOTE_MAX_AGE:
        return "STALE_CLOCK"
    return "OBSERVED"


def _missing_quote_reason(reasons: Iterable[str]) -> str:
    # A valid but expired/undated offer proves more than a malformed price.
    for reason in ("STALE_CLOCK", "BAD_CLOCK", "INVALID_QUOTE"):
        if reason in reasons:
            return reason
    return "UNKNOWN_NOT_RECEIVED"


def parse_fixture_consensus(
    payload: object,
    candidates: Iterable[object],
    *,
    fetched_at: Optional[datetime] = None,
    retain_observations: bool = False,
    diagnostics: Optional[MutableMapping[str, dict[str, Any]]] = None,
    entry_received_at: Optional[Iterable[datetime]] = None,
) -> dict[str, MarketConsensus]:
    """Parse exact prices, preserving each native page's actual receipt clock."""
    candidate_list = list(candidates)
    fetched = _as_utc(fetched_at or datetime.now(timezone.utc))
    _quote_diagnostic(diagnostics, candidate_list, "UNKNOWN_NOT_RECEIVED", fetched_at=fetched)
    if not isinstance(payload, Mapping) or payload.get("errors"):
        if isinstance(payload, Mapping) and payload.get("errors"):
            _quote_diagnostic(diagnostics, candidate_list, "REQUEST_FAILED", fetched_at=fetched,
                              error_type="PROVIDER_ERROR")
        return {}
    response = payload.get("response")
    if not isinstance(response, list):
        return {}
    receipts = ([fetched] * len(response) if entry_received_at is None
                else [_as_utc(moment) for moment in entry_received_at])
    if len(receipts) != len(response):
        raise ValueError("entry receipt clocks must match odds response entries")
    quotes: dict[
        tuple[int, str, str],
        dict[str, tuple[QuotePoint, datetime, datetime]],
    ] = {}
    fixture_ids: set[int] = set()
    fixture_starts: dict[int, Optional[datetime]] = {}
    requested_targets = {
        (_candidate_value(candidate, "fixture_id"), _normalize(target[0]), _normalize(target[1]))
        for candidate in candidate_list
        if (target := exact_market_target(_candidate_value(candidate, "market_key"))) is not None
        and type(_candidate_value(candidate, "fixture_id")) is int
    } if diagnostics is not None else set()
    received_markets: set[tuple[int, str]] = set()
    received_selections: dict[tuple[int, str, str], set[str]] = {}
    received_updates: dict[tuple[int, str, str], datetime] = {}
    received_receipts: dict[tuple[int, str, str], datetime] = {}
    for entry, entry_fetched in zip(response, receipts):
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
                range_source = _RANGE_BET_NAMES.get(bet_name)
                if range_source is not None:
                    expected_id, canonical_name = range_source
                    # An explicit contradictory source ID invalidates the
                    # range contract. Missing IDs retain exact-name binding.
                    if "id" in bet and (type(bet["id"]) is not int or bet["id"] != expected_id):
                        continue
                    bet_name = _normalize(canonical_name)
                if diagnostics is not None and bet_name:
                    received_markets.add((fixture_id, bet_name))
                values = bet.get("values")
                if not bet_name or not isinstance(values, list):
                    continue
                for value in values:
                    if not isinstance(value, Mapping):
                        continue
                    value_name = _normalize(value.get("value"))
                    if range_source is not None:
                        # Do not sum exact-count prices or infer a range price
                        # from open-ended/exact-goal/O-U selections.
                        value_name = _literal_goal_range(value.get("value"))
                        if value_name is None:
                            continue
                    if bet_name == "double chance":
                        # API-Football uses both token and spelled-out outcomes.
                        # Canonicalize only this exact full-time market; retain
                        # the existing side/fixture/start binding afterwards.
                        value_name = {"1x": "home/draw", "x2": "draw/away",
                                      "12": "home/away"}.get(value_name, value_name)
                    receipt_key = (fixture_id, bet_name, value_name)
                    reasons = None
                    if receipt_key in requested_targets:
                        reasons = received_selections.setdefault(receipt_key, set())
                        received_receipts[receipt_key] = max(
                            entry_fetched, received_receipts.get(receipt_key, entry_fetched))
                        if update is not None:
                            received_updates[receipt_key] = max(update, received_updates.get(receipt_key, update))
                    try:
                        odds = validate_decimal_odds(value.get("odd"))
                    except BettingMathError:
                        if reasons is not None:
                            reasons.add("INVALID_QUOTE")
                        continue
                    if reasons is not None:
                        reasons.add(_quote_clock_reason(update, entry_fetched))
                    if not (_observation_is_current(update, entry_fetched) or (
                        retain_observations and update is not None
                        and timedelta(minutes=-1) <= entry_fetched - update <= QUOTE_DISPLAY_MAX_AGE
                    )):
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
                            entry_fetched,
                        )

    result: dict[str, MarketConsensus] = {}
    for candidate in candidate_list:
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
        ):
            _quote_diagnostic(diagnostics, [candidate], "UNSUPPORTED", fetched_at=fetched)
            continue
        if fixture_id not in fixture_ids:
            _quote_diagnostic(diagnostics, [candidate],
                              "IDENTITY_MISMATCH" if fixture_ids else "FIXTURE_ABSENT",
                              fetched_at=fetched)
            continue
        bet_name, value_name = target
        receipt_key = (fixture_id, _normalize(bet_name), _normalize(value_name))
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
            if (fixture_id, _normalize(bet_name)) not in received_markets:
                reason = "MARKET_ABSENT"
            elif receipt_key not in received_selections:
                reason = "SELECTION_ABSENT"
            else:
                reason = _missing_quote_reason(received_selections[receipt_key])
            _quote_diagnostic(diagnostics, [candidate], reason,
                              fetched_at=received_receipts.get(receipt_key, fetched),
                              provider_updated_at=received_updates.get(receipt_key))
            continue
        lowest, conservative, consensus, best = summary
        observed_at = [observed[1] for observed in raw.values()]
        quote_fetched = max(observed[2] for observed in raw.values())
        quoted_at = max(observed_at).isoformat() if observed_at else None
        _quote_diagnostic(diagnostics, [candidate],
                          "OBSERVED" if all(_observation_is_current(observed[1], observed[2])
                                            for observed in raw.values())
                          else "STALE_CLOCK", fetched_at=quote_fetched,
                          provider_updated_at=max(observed_at), bookmaker_count=len(points))
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
            fetched_at=quote_fetched.isoformat(),
            source=REFERENCE_SOURCE,
            points=points,
            scheduled_start=(
                fixture_starts[fixture_id].isoformat()
                if fixture_starts.get(fixture_id) is not None
                else None
            ),
            native_market_partitions=_football_native_partitions(market_key, fixture_id, points, quotes),
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
        _tennis_identity_name(value)
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
        _tennis_identity_name(event.get("home_team")),
        _tennis_identity_name(event.get("away_team")),
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
    diagnostics: Optional[MutableMapping[str, dict[str, Any]]] = None,
) -> dict[str, MarketConsensus]:
    """Parse exact match-winner prices for one identified provider event.

    Participant names must contain the exact same complete words after case,
    accent and punctuation normalization; only word order may differ. The
    scheduled times must be close, and the selected
    participant must be one of the two modeled competitors. No market or
    price is inferred when any identity field is missing or ambiguous.
    """
    current = _as_utc(fetched_at or datetime.now(timezone.utc))
    requested_candidates = list(candidates)
    _quote_diagnostic(diagnostics, requested_candidates, "UNKNOWN_NOT_RECEIVED", fetched_at=current)
    if not isinstance(payload, Mapping):
        return {}
    provider_event_id = str(payload.get("id") or "").strip()
    if not provider_event_id:
        _quote_diagnostic(diagnostics, requested_candidates, "IDENTITY_MISMATCH", fetched_at=current)
        return {}
    _quote_diagnostic(diagnostics, requested_candidates, "IDENTITY_MISMATCH", fetched_at=current)
    candidate_list = [
        candidate
        for candidate in requested_candidates
        if _h2h_event_matches(payload, candidate)
    ]
    if not candidate_list:
        return {}

    quotes: dict[str, dict[str, tuple[QuotePoint, datetime]]] = {}
    received_market = False
    received_selections: dict[str, set[str]] = {}
    received_updates: dict[str, datetime] = {}
    selected_names = {identity[2] for candidate in candidate_list
                      if (identity := _h2h_candidate_identity(candidate)) is not None}
    bookmakers = payload.get("bookmakers")
    if not isinstance(bookmakers, list):
        _quote_diagnostic(diagnostics, candidate_list, "MARKET_ABSENT", fetched_at=current)
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
            received_market = True
            market_update = _parse_utc(market.get("last_update"))
            observed_at = market_update or bookmaker_update
            outcomes = market.get("outcomes")
            if not isinstance(outcomes, list):
                continue
            for outcome in outcomes:
                if not isinstance(outcome, Mapping):
                    continue
                outcome_name = _tennis_identity_name(outcome.get("name"))
                if not outcome_name:
                    continue
                reasons = None
                if diagnostics is not None and outcome_name in selected_names:
                    reasons = received_selections.setdefault(outcome_name, set())
                    if observed_at is not None:
                        received_updates[outcome_name] = max(observed_at, received_updates.get(outcome_name, observed_at))
                try:
                    odds = validate_decimal_odds(outcome.get("price"))
                except BettingMathError:
                    if reasons is not None:
                        reasons.add("INVALID_QUOTE")
                    continue
                if reasons is not None:
                    reasons.add(_quote_clock_reason(observed_at, current))
                if not _observation_is_current(observed_at, current):
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
            reason = ("MARKET_ABSENT" if not received_market else
                      "SELECTION_ABSENT" if selected not in received_selections else
                      _missing_quote_reason(received_selections[selected]))
            _quote_diagnostic(diagnostics, [candidate], reason, fetched_at=current,
                              provider_updated_at=received_updates.get(selected))
            continue
        lowest, conservative, consensus, best = summary
        observed = [entry[1] for entry in raw_points.values()]
        partitions = []
        native_names = [str(_candidate_value(candidate, field)).strip() for field in ('competitor_a', 'competitor_b')]
        for point in points:
            pair = []
            for normalized, name in zip(identity[:2], native_names):
                found = [item[0] for item in quotes.get(normalized, {}).values()
                         if item[0].bookmaker_id == point.bookmaker_id
                         and item[0].observed_at == point.observed_at]
                if len(found) != 1:
                    break
                pair.append((name, found[0].odds))
            if len(pair) == 2:
                partitions.append(native_partition('H2H', 'tennis_match', point.bookmaker_id,
                    point.observed_at, current.isoformat(), pair))
        _quote_diagnostic(diagnostics, [candidate], "OBSERVED", fetched_at=current,
                          provider_updated_at=max(observed), bookmaker_count=len(points))
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
            native_market_partitions=tuple(partitions),
        )
    return result


def _odds_api_json(
    path: str,
    api_key: str,
    *,
    params: Optional[Mapping[str, object]] = None,
    timeout: int = 20,
    request_diagnostic: Optional[MutableMapping[str, Any]] = None,
) -> tuple[object, Optional[str]]:
    try:
        response = odds_api_get(
            path,
            api_key=api_key,
            params=params,
            timeout=timeout,
        )
        if 300 <= response.status_code < 400:
            if request_diagnostic is not None:
                request_diagnostic.update(error_type="HTTP_ERROR", http_status=response.status_code)
            return None, "unerwartete Weiterleitung"
        response.raise_for_status()
        return response.json(), None
    except APIBudgetError as exc:
        if request_diagnostic is not None:
            request_diagnostic.update(_request_error_facts(exc))
        return None, type(exc).__name__
    except requests.RequestException as exc:
        # Do not include the exception text: requests may embed the request URL
        # and therefore the API key in it.
        if request_diagnostic is not None:
            request_diagnostic.update(_request_error_facts(exc))
        return None, f"{type(exc).__name__}"
    except ValueError:
        if request_diagnostic is not None:
            request_diagnostic["error_type"] = "INVALID_RESPONSE"
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


def _tennis_observation_identity(row: object) -> Optional[tuple[str, str, str, str, str, str]]:
    """Native event identity, separate from the odds provider's event ID."""
    if not isinstance(row, Mapping) or row.get("fixture_id") is not None:
        return None
    fields = ("fixture_source", "provider_event_id", "competitor_a", "competitor_b", "selected_competitor")
    values = tuple(row.get(field) for field in fields)
    if (not all(isinstance(value, str) and value.strip() and len(value) <= 300 for value in values)
            or _normalize(row.get("sport")) != "tennis" or row.get("market_key") != "H2H"
            or values[2] == values[3] or values[4] not in values[2:4]):
        return None
    try:
        for value in values:
            value.encode("utf-8")
    except UnicodeError:
        # Optional collection must not turn a valid ordinary quote response
        # into a loader failure while hashing malformed native metadata.
        return None
    try:
        start = _parse_utc(row.get("scheduled_start"))
    except (ValueError, OverflowError):
        return None
    if start is None:
        return None
    return values[0], values[1], start.isoformat(), values[2], values[3], values[4]


def bounded_tennis_price_observations(rows: object, *, now: datetime) -> list[dict[str, Any]]:
    """Validate a small current-price artifact; never retain a price history."""
    if not isinstance(rows, (list, tuple)) or len(rows) > TENNIS_PRICE_MAX_SIDES:
        return []
    try:
        if len(json.dumps(rows, ensure_ascii=False, allow_nan=False).encode("utf-8")) > TENNIS_PRICE_MAX_BYTES:
            return []
    except (TypeError, ValueError, RecursionError):
        return []
    result, events = [], set()
    for row in rows:
        identity = _tennis_observation_identity(row)
        if identity is None or _parse_utc(identity[2]) <= _as_utc(now):
            continue
        try:
            quote = MarketConsensus.from_dict(row.get("reference_quote"))
            observed = observed_consensus(quote, candidate=row, now=now)
        except (ValueError, TypeError, OverflowError, RecursionError):
            continue
        if (quote is None or not isinstance(row.get("quote_provider_event_id"), str)
                or row["quote_provider_event_id"] != quote.provider_event_id
                or observed is None):
            continue
        events.add(identity[:2])
        if len(events) > TENNIS_PRICE_MAX_EVENTS:
            return []
        # Persist only identity and actual price facts, never model/statistics payloads.
        result.append({field: deepcopy(row[field]) for field in (
            "sport", "fixture_id", "fixture_source", "provider_event_id", "competitor_a",
            "competitor_b", "selected_competitor", "scheduled_start", "market_key",
            "candidate_id", "quote_provider_event_id", "reference_quote",
        ) if field in row})
    return result


def merge_tennis_price_observations(previous: object, fresh: object, checked_rows: Iterable[object],
                                    *, now: datetime) -> list[dict[str, Any]]:
    """Replace checked events within the bounded current daily price catalog."""
    incoming = bounded_tennis_price_observations(fresh, now=now)
    checked = {identity[:2] for row in checked_rows
               if (identity := _tennis_observation_identity(row)) is not None}
    retained = [row for row in bounded_tennis_price_observations(previous, now=now)
                if _tennis_observation_identity(row)[:2] not in checked]
    merged, events = list(incoming), {_tennis_observation_identity(row)[:2] for row in incoming}
    for row in retained:
        event = _tennis_observation_identity(row)[:2]
        if len(merged) >= TENNIS_PRICE_MAX_SIDES or (event not in events and len(events) >= TENNIS_PRICE_MAX_EVENTS):
            continue
        events.add(event)
        merged.append(row)
    return bounded_tennis_price_observations(merged, now=now)


def _collect_tennis_event_prices(event: Mapping[str, object], candidates: Iterable[object], *,
                                 now: datetime) -> list[dict[str, Any]]:
    """Both actual H2H outcomes from the already received exact event response."""
    rows = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        for selected in (candidate.get("competitor_a"), candidate.get("competitor_b")):
            row = {field: candidate.get(field) for field in (
                "fixture_source", "provider_event_id", "competitor_a", "competitor_b", "scheduled_start",
            )}
            row.update(sport="Tennis", fixture_id=None, market_key="H2H", selected_competitor=selected)
            identity = _tennis_observation_identity(row)
            if identity is None:
                continue
            digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()
            row["candidate_id"] = f"tennis-price:{digest}"
            row["quote_provider_event_id"] = str(event.get("id") or "")
            rows.setdefault(identity, row)
    parsed = parse_h2h_event_consensus(event, rows.values(), fetched_at=now)
    return bounded_tennis_price_observations([
        {**row, "reference_quote": parsed[row["candidate_id"]].to_dict()}
        for row in rows.values() if row["candidate_id"] in parsed
    ], now=now)


def fetch_tennis_h2h_consensus(
    api_key: str,
    candidates: Iterable[object],
    *,
    timeout: int = 20,
    now: Optional[datetime] = None,
    price_observations: Optional[list[dict[str, Any]]] = None,
    diagnostics: Optional[MutableMapping[str, dict[str, Any]]] = None,
) -> tuple[dict[str, MarketConsensus], list[str]]:
    """Fetch exact current H2H prices for persisted tennis model rows.

    The free sports/events discovery endpoints identify one provider event
    first. Only then is its real H2H market requested. Ambiguous or unmatched
    events remain unpriced instead of being guessed from similar names.
    """
    current = _as_utc(now or datetime.now(timezone.utc))
    key = str(api_key or "").strip()
    requested_candidates = list(candidates)
    _quote_diagnostic(diagnostics, requested_candidates, "UNSUPPORTED")
    candidate_list = [
        candidate
        for candidate in requested_candidates
        if _normalize(_candidate_value(candidate, "sport")) == "tennis"
        and _h2h_candidate_identity(candidate) is not None
        and str(_candidate_value(candidate, "candidate_id") or "").strip()
    ]
    _quote_diagnostic(diagnostics, candidate_list, "UNKNOWN_NOT_RECEIVED")
    if not key:
        _quote_diagnostic(diagnostics, candidate_list, "REQUEST_FAILED", checked_at=current,
                          error_type="MISSING_CREDENTIAL")
        return {}, ["The-Odds-API-Key fuer Tennisquoten fehlt"]
    if not candidate_list:
        return {}, []

    # The paired-price artifact must cover the requested pool, not silently
    # evict earlier events after successfully requesting them. This is the
    # same bound as the automatic model catalog, including manual windows.
    event_identities = set()
    for candidate in candidate_list:
        native = tuple(_candidate_value(candidate, field)
                       for field in ("fixture_source", "provider_event_id"))
        if all(isinstance(value, str) and value.strip() for value in native):
            event_identities.add(("native", *native))
        else:
            identity = _h2h_candidate_identity(candidate)
            event_identities.add(("legacy", identity[0], identity[1], identity[3]))
    event_count = len(event_identities)
    if event_count > TENNIS_PRICE_MAX_EVENTS:
        _quote_diagnostic(diagnostics, candidate_list, "UNSUPPORTED")
        return {}, [f"Tennis-Quotenumfang überschreitet {TENNIS_PRICE_MAX_EVENTS} Ereignisse"]

    sports_request_diagnostic: dict[str, Any] = {}
    sports_payload, sports_error = _odds_api_json(
        "sports/",
        key,
        timeout=timeout,
        request_diagnostic=sports_request_diagnostic,
    )
    sports_completed_at = current if now is not None else _as_utc(datetime.now(timezone.utc))
    if sports_error is not None or not isinstance(sports_payload, list):
        _quote_diagnostic(diagnostics, candidate_list,
                          "REQUEST_FAILED" if sports_error is not None else "UNKNOWN_NOT_RECEIVED",
                          checked_at=sports_completed_at if sports_error is not None else None,
                          fetched_at=sports_completed_at if sports_error is None else None,
                          **sports_request_diagnostic)
        return {}, [
            f"Tennis-Sportliste: {sports_error or 'ungueltige Antwort'}"
        ]
    sport_keys, sport_key_error = _bounded_tennis_sport_keys(
        sports_payload,
        candidate_list,
    )
    if sport_key_error is not None:
        _quote_diagnostic(diagnostics, candidate_list, "UNSUPPORTED", fetched_at=sports_completed_at)
        return {}, [sport_key_error]
    if not sport_keys:
        _quote_diagnostic(diagnostics, candidate_list, "UNSUPPORTED", fetched_at=sports_completed_at)
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
    event_request_diagnostics: dict[str, dict[str, Any]] = {sport_key: {} for sport_key in sport_keys}
    event_completed_at = sports_completed_at
    with ThreadPoolExecutor(max_workers=min(4, len(sport_keys))) as executor:
        futures = {
            executor.submit(
                _odds_api_json,
                f"sports/{sport_key}/events",
                key,
                params=event_params,
                timeout=min(timeout, TENNIS_EVENT_DISCOVERY_TIMEOUT),
                request_diagnostic=event_request_diagnostics[sport_key],
            ): sport_key
            for sport_key in sport_keys
        }
        for future in as_completed(futures):
            sport_key = futures[future]
            try:
                event_results[sport_key] = future.result()
            except Exception as exc:
                event_request_diagnostics[sport_key].update(_request_error_facts(exc))
                event_results[sport_key] = (
                    None,
                    f"{type(exc).__name__}",
                )
            event_completed_at = current if now is not None else _as_utc(datetime.now(timezone.utc))

    discovery_failed = False
    discovery_failure_facts: dict[str, Any] = {}
    received_events = False
    for sport_key in sport_keys:
        events_payload, event_error = event_results.get(
            sport_key,
            (None, "keine Antwort"),
        )
        if event_error is not None:
            discovery_failed = True
            # Report one actual failure; never concatenate arbitrary provider data.
            if not discovery_failure_facts:
                discovery_failure_facts = event_request_diagnostics[sport_key]
            errors.append(f"Tennis-Events {sport_key}: {event_error}")
            continue
        if not isinstance(events_payload, list):
            discovery_failed = True
            if not discovery_failure_facts:
                discovery_failure_facts = {"error_type": "INVALID_RESPONSE"}
            errors.append(f"Tennis-Events {sport_key}: ungueltige Antwort")
            continue
        for event in events_payload:
            if not isinstance(event, Mapping):
                continue
            event_id = str(event.get("id") or "").strip()
            if not event_id:
                continue
            received_events = True
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
            reason = ("IDENTITY_MISMATCH" if len(candidate_matches) > 1 else
                      "REQUEST_FAILED" if discovery_failed else
                      "IDENTITY_MISMATCH" if received_events else "FIXTURE_ABSENT")
            _quote_diagnostic(diagnostics, [candidate], reason,
                              checked_at=event_completed_at if reason == "REQUEST_FAILED" else None,
                              fetched_at=event_completed_at if reason != "REQUEST_FAILED" else None,
                              **(discovery_failure_facts if reason == "REQUEST_FAILED" else {}))
            continue
        event_key = next(iter(candidate_matches))
        grouped_events.setdefault(event_key, []).append(candidate)

    result: dict[str, MarketConsensus] = {}
    by_sport: dict[str, dict[str, list[object]]] = {}
    for (sport_key, event_id), event_candidates in grouped_events.items():
        by_sport.setdefault(sport_key, {})[event_id] = event_candidates
    collected_prices, collected_checks = [], []
    completed_at = current
    for sport_key, requested_events in by_sport.items():
        odds_request_diagnostic: dict[str, Any] = {}
        odds_payload, odds_error = _odds_api_json(
            f"sports/{sport_key}/odds",
            key,
            params={
                "regions": "eu",
                "markets": "h2h",
                "eventIds": ",".join(sorted(requested_events)),
                "dateFormat": "iso",
                "oddsFormat": "decimal",
            },
            timeout=timeout,
            request_diagnostic=odds_request_diagnostic,
        )
        fetched_at = current if now is not None else _as_utc(datetime.now(timezone.utc))
        if odds_error is not None:
            errors.append(f"Tennisquote {sport_key}: {odds_error}")
            for event_candidates in requested_events.values():
                _quote_diagnostic(diagnostics, event_candidates, "REQUEST_FAILED", checked_at=fetched_at,
                                  **odds_request_diagnostic)
            continue
        if not isinstance(odds_payload, list):
            errors.append(f"Tennisquote {sport_key}: ungueltige Antwort")
            for event_candidates in requested_events.values():
                _quote_diagnostic(diagnostics, event_candidates, "UNKNOWN_NOT_RECEIVED", fetched_at=fetched_at)
            continue
        # Each completed sport response owns its actual retrieval clock; a
        # provider update made during the batch must not look future-dated.
        completed_at = fetched_at
        returned = {}
        duplicate_ids = set()
        for event in odds_payload:
            if not isinstance(event, Mapping):
                continue
            event_id = str(event.get("id") or "")
            if event_id in returned:
                duplicate_ids.add(event_id)
            returned[event_id] = event
        for event_id, event_candidates in requested_events.items():
            if event_id not in returned or event_id in duplicate_ids:
                _quote_diagnostic(diagnostics, event_candidates,
                                  "IDENTITY_MISMATCH" if event_id in duplicate_ids else "FIXTURE_ABSENT",
                                  fetched_at=fetched_at)
                continue
            result.update(
                parse_h2h_event_consensus(
                    returned[event_id], event_candidates, fetched_at=fetched_at,
                    diagnostics=diagnostics,
                )
            )
            if price_observations is not None:
                collected_prices.extend(_collect_tennis_event_prices(
                    returned[event_id], event_candidates, now=fetched_at))
                collected_checks.extend(event_candidates)
    if price_observations is not None and collected_checks:
        # Validate/copy the bounded catalog once, not after every received
        # event. Individual quotes retain their actual response timestamps.
        price_observations[:] = merge_tennis_price_observations(
            price_observations, collected_prices, collected_checks, now=completed_at)
    return result, errors


_FOOTBALL_ODDS_MAX_PAGES = 20


def _football_odds_entry_has_shape(entry: object) -> bool:
    """A broken native container cannot prove a market or selection absent."""
    if not isinstance(entry, Mapping):
        return False
    fixture, bookmakers = entry.get("fixture"), entry.get("bookmakers")
    if (not isinstance(fixture, Mapping) or type(fixture.get("id")) is not int
            or fixture["id"] <= 0 or not isinstance(bookmakers, list)):
        return False
    for bookmaker in bookmakers:
        if not isinstance(bookmaker, Mapping) or not isinstance(bookmaker.get("bets"), list):
            return False
        for bet in bookmaker["bets"]:
            if not isinstance(bet, Mapping) or not isinstance(bet.get("values"), list):
                return False
            if not all(isinstance(value, Mapping) for value in bet["values"]):
                return False
    return True


def fetch_football_consensus(
    api_key: str,
    candidates: Iterable[object],
    *,
    timeout: int = 20,
    now: Optional[datetime] = None,
    diagnostics: Optional[MutableMapping[str, dict[str, Any]]] = None,
    deadline: Optional[float] = None,
) -> tuple[dict[str, MarketConsensus], list[str]]:
    """Fetch and merge bounded native pages before calculating exact prices.

    A deadline defers only requests not yet started; the existing per-request
    timeout still bounds any in-flight call. Entirely deferred fixtures have no receipt clock.
    Partial pages can prove received offers, never an absent market/selection.
    """
    current = _as_utc(now or datetime.now(timezone.utc))
    candidate_list = list(candidates)
    _quote_diagnostic(diagnostics, candidate_list, "UNSUPPORTED")
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
            _quote_diagnostic(diagnostics, [candidate], "UNKNOWN_NOT_RECEIVED")
    quotes: dict[str, MarketConsensus] = {}
    errors: list[str] = []
    headers = {"x-apisports-key": str(api_key or "").strip()}
    if not headers["x-apisports-key"]:
        for fixture_candidates in grouped.values():
            _quote_diagnostic(diagnostics, fixture_candidates, "REQUEST_FAILED", checked_at=current,
                              error_type="MISSING_CREDENTIAL")
        return {}, ["API-Football-Key fuer Marktquoten fehlt"]
    for fixture_id, fixture_candidates in grouped.items():
        if deadline is not None and monotonic() >= deadline:
            _quote_diagnostic(diagnostics, fixture_candidates, "DEFERRED")
            continue
        entries: list[object] = []
        entry_receipts: list[datetime] = []
        received_pages: list[list[object]] = []
        fetched_at: Optional[datetime] = None
        checked_at: Optional[datetime] = None
        total_pages: Optional[int] = None
        page_number = 1
        failure: Optional[str] = None
        failure_error: Optional[str] = None
        failure_facts: dict[str, Any] = {}
        while True:
            if page_number > 1 and deadline is not None and monotonic() >= deadline:
                failure = "DEADLINE"
                break
            params = {"fixture": fixture_id}
            if page_number > 1:
                params["page"] = page_number
            try:
                response = api_football_get(
                    "https://v3.football.api-sports.io/odds",
                    headers=headers,
                    params=params,
                    timeout=timeout,
                    priority=APIBudgetPriority.RECOMMENDATION,
                    label=f"odds consensus fixture {fixture_id}",
                )
                response.raise_for_status()
                payload = response.json()
            except (APIBudgetError, requests.RequestException, ValueError) as exc:
                failure = "REQUEST_FAILED"
                failure_error = f"Marktquoten Spiel {fixture_id}: {type(exc).__name__}"
                failure_facts = _request_error_facts(exc)
                checked_at = current if now is not None else _as_utc(datetime.now(timezone.utc))
                break
            # Each actual response owns its clock. A failed later request must
            # not renew the retrieval clock of an earlier received offer.
            received_at = current if now is not None else _as_utc(datetime.now(timezone.utc))
            checked_at = received_at
            if not isinstance(payload, Mapping):
                failure = "INVALID_RESPONSE"
                failure_facts = {"error_type": "INVALID_RESPONSE"}
                break
            if payload.get("errors"):
                failure = "PROVIDER_ERROR"
                failure_error = f"Marktquoten Spiel {fixture_id}: Providerfehler"
                failure_facts = {"error_type": "PROVIDER_ERROR"}
                break
            if not isinstance(payload.get("response"), list):
                failure = "INVALID_RESPONSE"
                failure_facts = {"error_type": "INVALID_RESPONSE"}
                break
            page_entries = payload["response"]
            # Preserve genuinely received prices even if page metadata is bad.
            entries.extend(page_entries)
            entry_receipts.extend([received_at] * len(page_entries))
            fetched_at = received_at
            repeated_body = page_entries in received_pages
            received_pages.append(page_entries)
            if not all(_football_odds_entry_has_shape(entry) for entry in page_entries):
                failure = "INVALID_RESPONSE"
                failure_facts = {"error_type": "INVALID_RESPONSE"}
                break
            paging = payload.get("paging")
            if not isinstance(paging, Mapping):
                failure = "MISSING_PAGING" if "paging" not in payload else "INVALID_PAGING"
                break
            reported_page, reported_total = paging.get("current"), paging.get("total")
            if (type(reported_page) is not int or type(reported_total) is not int
                    or reported_page < 1 or reported_total < reported_page):
                failure = "INVALID_PAGING"
                break
            if reported_page != page_number:
                failure = "REPEATED_PAGE" if reported_page < page_number else "INVALID_PAGING"
                break
            if total_pages is None:
                total_pages = reported_total
            elif reported_total != total_pages:
                failure = "INVALID_PAGING"
                break
            if repeated_body:
                failure = "REPEATED_PAGE"
                break
            if page_number == total_pages:
                break
            if page_number >= _FOOTBALL_ODDS_MAX_PAGES:
                failure = "PAGE_LIMIT"
                break
            page_number += 1
        fixture_quotes = (
            parse_fixture_consensus(
                {"errors": [], "response": entries},
                fixture_candidates,
                fetched_at=fetched_at,
                retain_observations=True,
                diagnostics=diagnostics,
                entry_received_at=entry_receipts,
            )
            if fetched_at is not None else {}
        )
        quotes.update(fixture_quotes)
        if failure is not None:
            deferred = failure == "DEADLINE"
            if not deferred:
                errors.append(failure_error or f"Marktquoten Spiel {fixture_id}: unvollstaendige Paginierung")
                failure_facts.setdefault("error_type", "INCOMPLETE_PAGINATION")
            missing = [candidate for candidate in fixture_candidates
                       if str(_candidate_value(candidate, "candidate_id") or "").strip() not in fixture_quotes]
            for candidate in missing:
                candidate_id = str(_candidate_value(candidate, "candidate_id") or "").strip()
                previous = diagnostics.get(candidate_id, {}) if diagnostics is not None else {}
                _quote_diagnostic(diagnostics, [candidate], "DEFERRED" if deferred else "REQUEST_FAILED",
                                  fetched_at=_parse_utc(previous.get("fetched_at")) or fetched_at,
                                  checked_at=checked_at,
                                  provider_updated_at=_parse_utc(previous.get("provider_updated_at")),
                                  **failure_facts)
            if diagnostics is not None:
                for candidate in fixture_candidates:
                    candidate_id = str(_candidate_value(candidate, "candidate_id") or "").strip()
                    if candidate_id and candidate_id in diagnostics:
                        diagnostics[candidate_id].update(
                            pagination_complete=False,
                            pagination_pages_received=len(received_pages),
                            pagination_failure=failure,
                        )
                        if total_pages is not None:
                            diagnostics[candidate_id]["pagination_total_pages"] = total_pages
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
    "PRICE_POLICY_FLAG",
    "floor_only_pricing",
    "floor_price_status",
    "price_policy",
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
    "quote_below_publication_floor",
    "reference_price_status",
    "serialize_consensus_map",
    "wettfinder_consensus",
    "wettfinder_reference_price_status",
]
