"""Positive quote proof for public tips, never model/value qualification.

The existing 24-hour display lifetime is not an execution approval. Original
provider/fetch clocks remain unchanged and old offers must still be labelled old.
Callers apply this only after price-blind whole-event/market coherence.
"""
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from numbers import Integral
import json
from pathlib import Path
from statistics import median

from betting_math import MINIMUM_RECOMMENDED_DECIMAL_ODDS
from market_consensus import (
    MarketConsensus, QUOTE_DISPLAY_MAX_AGE, _parse_utc, _summary_prices,
    floor_only_pricing, observed_consensus, quote_matches_candidate, wettfinder_consensus,
)
from runtime_paths import RUNTIME_STATE_DIR

DEFAULT_QUOTE_STATE_PATH = RUNTIME_STATE_DIR / 'wettfinder_latest.json'
# Renderer receipt reads are bounded independently of the worker's model pool.
# Check before allocation and after a bounded read, including a file-size race.
MAX_QUOTE_STATE_BYTES = 64 * 1024 * 1024


def _value(candidate, name):
    return candidate.get(name) if isinstance(candidate, Mapping) else getattr(candidate, name, None)


def _observed_publication_quote(quote, *, candidate, now=None):
    """Normalize exact native proof without applying a price threshold.

    Unknown/foreign/expired evidence is not a cheap price, but cannot establish
    public-tip eligibility either. No clock is renewed by a later failed check.
    """
    current = now or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("publication requires an aware clock")
    current = current.astimezone(timezone.utc)
    start = next((_parse_utc(_value(candidate, name))
                  for name in ("scheduled_start", "kickoff", "starts_at")
                  if _value(candidate, name) is not None), None)
    if start is None or start <= current:
        return None  # Prematch offers never qualify an already started/live tip.
    observed = observed_consensus(quote, candidate=candidate, now=current)
    if observed is None:
        return None
    fetched = _parse_utc(observed.fetched_at)
    if fetched is None or not timedelta(0) <= current-fetched <= QUOTE_DISPLAY_MAX_AGE:
        return None
    # A stale high offer must not override a current low offer or disagree with
    # the common card display's established fresh-provider subset.
    normalized = wettfinder_consensus(observed, now=current) or observed
    points = tuple(point for point in normalized.points
                   if _parse_utc(point.observed_at) is not None
                   and _parse_utc(point.observed_at) <= fetched <= current
                   and timedelta(0) <= current-_parse_utc(point.observed_at) <= QUOTE_DISPLAY_MAX_AGE)
    if not points:
        return None
    lowest, conservative, consensus, best = _summary_prices(sorted(point.odds for point in points))
    return replace(normalized, points=points, bookmaker_count=len(points),
                   lowest_odds=lowest, conservative_odds=conservative,
                   consensus_odds=consensus, best_odds=best,
                   quoted_at=max(_parse_utc(point.observed_at) for point in points).isoformat())


def publication_quote(quote, *, candidate, now=None):
    """Apply admission only after the caller selected the newest exact receipt."""
    normalized = _observed_publication_quote(quote, candidate=candidate, now=now)
    if normalized is None:
        return None
    # Owner decision 25.10.2026 (docs/audits/2026-10-25-preispruefung-dreistufig.md):
    # under the floor policy the median price decides, as on the card; the old
    # contract keeps the best offer. The admitted points stay unchanged.
    prices = [point.odds for point in normalized.points]
    reference = float(median(prices)) if floor_only_pricing() else max(prices)
    if reference < MINIMUM_RECOMMENDED_DECIMAL_ODDS:
        return None
    return normalized


def publication_allowed(quote, *, candidate, now=None):
    return publication_quote(quote, candidate=candidate, now=now) is not None


def native_football_publication_offer(rows, *, fixture_id, scheduled_start,
                                      market_key, selection, home_team, away_team, now=None):
    """Reuse a cached native offer for another model, never its probability.

    The old BTTS view uses a different model/candidate ID. The provider fixture,
    start, participants, market and side must nevertheless be the same. Source
    candidate IDs stay attached to their original quote, never invented.
    """
    if isinstance(fixture_id, bool) or not isinstance(fixture_id, Integral) or fixture_id <= 0:
        return None, None
    start = _parse_utc(scheduled_start)
    if start is None:
        return None, None
    target = dict(fixture_id=int(fixture_id), scheduled_start=start.isoformat(),
        market_key=market_key, selection=selection, home_team=home_team, away_team=away_team,
        sport='Fußball', source='football_challenge')
    quote, binding = _latest_native_receipt(target, rows, now=now)
    if quote is None or publication_quote(quote, candidate=binding, now=now) is None:
        return None, None
    return quote, binding


def quote_receipt(candidate, quote):
    """Copy a quote's existing consumer binding; never mutate a model row."""
    row = dict(candidate) if isinstance(candidate, Mapping) else dict(vars(candidate))
    row['candidate_id'] = row.get('candidate_id') or row.get('key')
    row['reference_quote'] = quote
    return row


def _start(candidate):
    return next((_parse_utc(_value(candidate, name)) for name in ('scheduled_start', 'kickoff', 'starts_at')
                 if _value(candidate, name) is not None), None)


def _name(value):
    return ' '.join(str(value or '').casefold().split())


def _native_quote_identity(candidate):
    """Native IDs plus exact start/participants/market/side, never names alone."""
    start, market = _start(candidate), str(_value(candidate, 'market_key') or '').upper()
    if start is None or not market:
        return None
    fixture = _value(candidate, 'fixture_id')
    if isinstance(fixture, Integral) and not isinstance(fixture, bool) and fixture > 0:
        home, away = _name(_value(candidate, 'home_team')), _name(_value(candidate, 'away_team'))
        return ('football', int(fixture), start, market, home, away) if home and away and home != away else None
    if _name(_value(candidate, 'sport')) != 'tennis' or market != 'H2H':
        return None
    provider, event = _name(_value(candidate, 'fixture_source')), str(_value(candidate, 'provider_event_id') or '')
    a, b = _name(_value(candidate, 'competitor_a')), _name(_value(candidate, 'competitor_b'))
    selected = _name(_value(candidate, 'selected_competitor'))
    if not provider or not event or not a or not b or a == b or selected not in {a, b}:
        return None
    return ('tennis', provider, event, start, market, a, b, selected)


def _latest_native_receipt(candidate, rows, *, now=None):
    identity, matches = _native_quote_identity(candidate), []
    if identity is None:
        return None, None
    target = dict(candidate) if isinstance(candidate, Mapping) else dict(vars(candidate))
    for row in rows:
        if _native_quote_identity(row) != identity:
            continue
        raw = _value(row, 'reference_quote')
        quote = raw if isinstance(raw, MarketConsensus) else MarketConsensus.from_dict(raw)
        if quote is None or not quote_matches_candidate(quote, row):
            continue
        # Provider-event quote ID changes are not a license to move a receipt
        # to another event. Source and target independently pass exact binding.
        binding = dict(target, candidate_id=quote.candidate_id)
        if _parse_utc(quote.scheduled_start) != identity[2 if identity[0] == 'football' else 3]:
            continue
        normalized = _observed_publication_quote(quote, candidate=binding, now=now)
        if normalized is not None:
            matches.append((normalized, binding))
    if not matches:
        return None, None
    newest = max(_parse_utc(quote.fetched_at) for quote, _ in matches)
    latest = [(quote, binding) for quote, binding in matches if _parse_utc(quote.fetched_at) == newest]
    first = replace(latest[0][0], candidate_id='')
    if any(replace(quote, candidate_id='') != first for quote, _ in latest[1:]):
        return None, None
    return latest[0]


def latest_reference_quotes(candidates, current_quotes, *, shared_rows=(), now=None, blocked_at=None):
    """Adopt newest real exact receipts before admission; low prices participate.

    Only consumer copies of quote candidate IDs are adapted, after native event,
    start, participants, market and selected-side proof. Failed checks are not
    receipts and cannot renew an offer. Same-clock conflicting offers withhold.
    """
    candidates = tuple(candidates)
    wanted = {_native_quote_identity(candidate) for candidate in candidates} - {None}
    index = {}
    for row in shared_rows:
        identity = _native_quote_identity(row)
        if identity in wanted:
            index.setdefault(identity, []).append(row)
    result = {}
    for candidate in candidates:
        key = _value(candidate, 'candidate_id') or _value(candidate, 'key')
        rows = list(index.get(_native_quote_identity(candidate), ()))
        if key in current_quotes:
            rows.append(quote_receipt(candidate, current_quotes[key]))
        quote, _binding = _latest_native_receipt(candidate, rows, now=now)
        if quote is not None:
            blocked = _parse_utc(blocked_at.get(key)) if isinstance(blocked_at, Mapping) else None
            if blocked is not None and _parse_utc(quote.fetched_at) <= blocked:
                continue  # A same-clock conflict cannot revive after its quote was withheld.
            result[key] = replace(quote, candidate_id=key)
    return result


def read_shared_quote_rows(path=None):
    """Read bounded existing receipts only; no API, models, stores or rewrites."""
    from ev_signal_sources import MAX_AUTOMATED_MODEL_CANDIDATES
    try:
        source = Path(path or DEFAULT_QUOTE_STATE_PATH)
        if source.stat().st_size > MAX_QUOTE_STATE_BYTES:
            return []
        with source.open('rb') as stream:
            payload = stream.read(MAX_QUOTE_STATE_BYTES + 1)
        if len(payload) > MAX_QUOTE_STATE_BYTES:
            return []
        document = json.loads(payload.decode('utf-8'))
    except (OSError, TypeError, ValueError):
        return []
    if not isinstance(document, dict):
        return []
    result = []
    for name in ('model_candidates', 'riskobet_price_observations', 'tennis_price_observations'):
        rows = document.get(name, ())
        if not isinstance(rows, list) or len(rows) > MAX_AUTOMATED_MODEL_CANDIDATES:
            continue
        result.extend(row for row in rows if isinstance(row, dict) and row.get('reference_quote') is not None)
    return result
