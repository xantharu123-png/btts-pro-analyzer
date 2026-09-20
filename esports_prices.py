"""Shared, bounded prematch series-winner observations. Never a model input.

Native sport/market/outcome IDs verified against the real catalog on 2026-09-20.
Only full-series two-way winner markets; no map, draw or prediction-market proxy.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re

from api_budget import DEFAULT_DB_PATH
from betting_math import validate_decimal_odds
from market_consensus import (MarketConsensus, QuotePoint, ESPORTS_PRICE_SOURCE,
    esports_discipline, _identity_name, _parse_utc, _summary_prices,
    observed_consensus, quote_matches_candidate)
from oddspapi_client import OddsPapiClient
from runtime_paths import atomic_write_text
from team_sport_prices import _writer_lock

CACHE_PATH = Path(__file__).resolve().parent / 'runtime_state' / 'esports_quotes.json'
MAX_CACHE_BYTES = 2_000_000
BOOKMAKERS = ('pinnacle', '1xbet')
MARKETS = {16: (161, 161, 162), 17: (171, 171, 172),
           18: (181, 181, 182), 61: (611, 611, 612)}
REFRESH_AFTER = timedelta(hours=12)


def _read(path):
    try:
        if path.is_symlink() or path.stat().st_size > MAX_CACHE_BYTES:
            return {}
        doc = json.loads(path.read_text(encoding='utf-8'))
        return doc if doc.get('schema') == 'esports-prices-v1' and isinstance(doc.get('events'), list) else {}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def _event(event, now):
    if not isinstance(event, dict):
        return False
    start = _parse_utc(event.get('startTime'))
    a, b = event.get('participant1Name'), event.get('participant2Name')
    return (type(event.get('sportId')) is int and event['sportId'] in MARKETS
        and all(type(event.get(k)) is int and event[k] > 0 for k in ('participant1Id', 'participant2Id'))
        and event['participant1Id'] != event['participant2Id']
        and type(event.get('statusId')) is int and event['statusId'] == 0
        and event.get('hasOdds') is True and event.get('trueStartTime') is None
        and event.get('trueEndTime') is None and start is not None and start > now
        and isinstance(event.get('fixtureId'), str)
        and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', event['fixtureId']) is not None
        and all(isinstance(n, str) and 0 < len(n.strip()) <= 200 for n in (a, b))
        and _identity_name(a) != _identity_name(b))


def _pairs(event, now):
    """Validate both sides, not merely a convenient selected price."""
    if not _event(event, now) or not isinstance(event.get('bookmakerOdds'), dict):
        return {}
    market_id, first, second = MARKETS[event['sportId']]
    pairs = {}
    for slug, book in event['bookmakerOdds'].items():
        try:
            if slug not in BOOKMAKERS or book['bookmakerIsActive'] is not True or book['suspended'] is not False:
                continue
            if not isinstance(book.get('bookmakerFixtureId'), str) or not book['bookmakerFixtureId']:
                continue
            market = book['markets'][str(market_id)]
            if market['marketActive'] is not True or set(market['outcomes']) != {str(first), str(second)}:
                continue
            pair = []
            for outcome in (first, second):
                players = market['outcomes'][str(outcome)]['players']
                if set(players) != {'0'}:
                    raise ValueError('not a whole-team winner')
                point = players['0']
                changed = _parse_utc(point.get('changedAt'))
                if (point['active'] is not True or point.get('playerName') is not None
                        or point.get('exchangeMeta') not in (None, {}) or changed is None
                        or changed > now + timedelta(minutes=1)):
                    raise ValueError('inactive or malformed point')
                pair.append(validate_decimal_odds(point['price']))
            pairs[slug] = pair
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return pairs


def _binding(row):
    if not isinstance(row, dict) or str(row.get('sport') or '').casefold() not in {'e-sport', 'esports', 'e sport'}:
        return None
    discipline = esports_discipline(row.get('competition'))
    start = _parse_utc(row.get('scheduled_start'))
    a, b, selected = (row.get(k) for k in ('competitor_a', 'competitor_b', 'selected_competitor'))
    event = row.get('provider_event_id')
    if (discipline is None or start is None or row.get('market_key') != 'H2H'
            or row.get('fixture_source') != 'pandascore' or not isinstance(event, str)
            or not re.fullmatch(r'[1-9][0-9]{0,19}', event)
            or not all(isinstance(n, str) and n.strip() for n in (a, b, selected))
            or _identity_name(a) == _identity_name(b) or selected not in (a, b)):
        return None
    return discipline, start, a, b, selected


def load_cached_quote(row, *, now=None, path=CACHE_PATH, document=None):
    current = now or datetime.now(timezone.utc)
    binding = _binding(row)
    if binding is None:
        return None
    discipline, start, a, b, selected = binding
    doc = document if document is not None else _read(Path(path))
    fetched = _parse_utc(doc.get('fetched_at'))
    if (fetched is None or not timedelta(minutes=-1) <= current-fetched <= timedelta(hours=24)
            or start <= current):
        return None
    matches = [e for e in doc.get('events', ()) if _event(e, current)
        and e['sportId'] == discipline
        and abs(_parse_utc(e['startTime'])-start) <= timedelta(minutes=5)
        and {_identity_name(e['participant1Name']), _identity_name(e['participant2Name'])}
            == {_identity_name(a), _identity_name(b)}]
    if len(matches) != 1:
        return None
    event = matches[0]
    position = 0 if _identity_name(selected) == _identity_name(event['participant1Name']) else 1
    points = tuple(QuotePoint(slug, pair[position], 'oddspapi:'+slug, fetched.isoformat())
                   for slug, pair in sorted(_pairs(event, fetched).items()))
    if not points:
        return None
    lowest, conservative, median, best = _summary_prices(sorted(p.odds for p in points))
    quote = MarketConsensus(None, str(row.get('candidate_id') or row.get('key') or ''),
        'H2H', 'Series Winner', selected, median, conservative, lowest, best, len(points),
        fetched.isoformat(), fetched.isoformat(), ESPORTS_PRICE_SOURCE, points,
        event['fixtureId'], event['startTime'], a, b, 'pandascore', row['provider_event_id'], discipline)
    return observed_consensus(quote, candidate=row, now=current)


def attach_cached_esports_prices(rows, *, now=None, path=CACHE_PATH):
    doc = _read(Path(path))
    rows = list(rows)
    origins = {}
    for row in rows:
        binding = _binding(row)
        if binding is not None:
            game, start, a, b, _ = binding
            origins.setdefault((game, tuple(sorted((_identity_name(a), _identity_name(b))))), []).append((start, row['provider_event_id']))
    output = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get('sport') or '').casefold() not in {'e-sport', 'esports', 'e sport'}:
            output.append(row)
            continue
        quote = load_cached_quote(row, now=now, document=doc)
        binding = _binding(row)
        if binding is not None:
            game, start, a, b, _ = binding
            peers = origins[game, tuple(sorted((_identity_name(a), _identity_name(b))))]
            if any(ident != row['provider_event_id'] and abs(stamp-start) <= timedelta(minutes=10)
                   for stamp, ident in peers):
                quote = None
        output.append(dict(row, reference_quote=quote.to_dict() if quote is not None else None,
                           reference_price_status='OBSERVED' if quote is not None else 'UNAVAILABLE'))
    return output


def refresh_esports_prices(*, api_key, now=None, path=CACHE_PATH, client=None):
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError('aware clock required')
    if not api_key:
        return {'status': 'missing_key', 'quotes': 0}
    target = Path(path)
    try:
        with _writer_lock(target):
            doc = _read(target)
            attempted = _parse_utc(doc.get('attempted_at'))
            wait = (timedelta(hours=24) if doc.get('refresh_calls', 3) > 3 else REFRESH_AFTER) if doc.get('status') == 'complete' else timedelta(hours=1)
            if attempted and timedelta(0) <= current-attempted < wait:
                return {'status': 'cached', 'events': len(doc['events'])}
            doc = doc or {'schema': 'esports-prices-v1', 'events': []}
            doc['attempted_at'] = current.isoformat()
            # Persist the attempt before HTTP so a crashed worker cannot spin.
            doc['status'] = 'pending'
            atomic_write_text(target, json.dumps(doc, separators=(',', ':')))
            errors, events = [], {}
            try:
                client = client or OddsPapiClient(api_key,
                    db_path=os.environ.get('BETBOY_API_BUDGET_DB') or DEFAULT_DB_PATH)
                quota = client.authorize()
                client.ensure_refresh_budget()
                fixtures = client.get('fixtures', {'from': current.isoformat(),
                    'to': (current+timedelta(hours=47)).isoformat(), 'statusId': 0, 'language': 'en'})
                if not isinstance(fixtures, list) or len(fixtures) > 10000:
                    raise ValueError('unexpected fixture response')
                native = [e for e in fixtures if _event(e, current)]
                ids = [e['fixtureId'] for e in native]
                unique = {e['fixtureId']: e for e in native if ids.count(e['fixtureId']) == 1}
                tournaments = sorted({e.get('tournamentId') for e in native
                                      if type(e.get('tournamentId')) is int and e['tournamentId'] > 0})
                if len(tournaments) > 40:
                    raise ValueError('too many esports tournaments')
                batches = [tournaments[i:i+5] for i in range(0, len(tournaments), 5)]
                required = len(batches) * len(BOOKMAKERS)
                if required:
                    client.ensure_refresh_budget(required_calls=required)
                doc['refresh_calls'] = 1 + required
                successful_books = 0
                for slug in BOOKMAKERS if tournaments else ():
                    try:
                        # Native API: singular bookmaker and at most five tournaments.
                        payload = []
                        for batch in batches:
                            part = client.get('odds-by-tournaments', {'tournamentIds': ','.join(map(str, batch)),
                                'bookmaker': slug, 'verbosity': 3, 'language': 'en'})
                            if not isinstance(part, list) or len(part) > 2000:
                                raise ValueError('unexpected odds response')
                            payload.extend(e for e in part if isinstance(e, dict) and e.get('tournamentId') in batch)
                        if len(payload) > 2000:
                            raise ValueError('too many odds events')
                        seen = set()
                        for event in payload:
                            if not _event(event, current):
                                continue
                            ident = event['fixtureId']
                            origin = unique.get(ident)
                            if ident in seen:
                                raise ValueError('duplicate odds event')
                            seen.add(ident)
                            fields = ('sportId', 'participant1Id', 'participant2Id', 'participant1Name',
                                      'participant2Name', 'startTime', 'tournamentId')
                            if not origin or any(event.get(k) != origin.get(k) for k in fields):
                                continue
                            if slug not in _pairs(event, current):
                                continue
                            minimal = {k: event.get(k) for k in (*fields, 'fixtureId', 'statusId', 'hasOdds', 'trueStartTime', 'trueEndTime')}
                            minimal['bookmakerOdds'] = {}
                            entry = events.setdefault(ident, minimal)
                            book = event['bookmakerOdds'][slug]
                            market_id = str(MARKETS[event['sportId']][0])
                            entry['bookmakerOdds'][slug] = {
                                'bookmakerIsActive': True, 'suspended': False,
                                'bookmakerFixtureId': book['bookmakerFixtureId'],
                                'markets': {market_id: book['markets'][market_id]}}
                        successful_books += 1
                    except Exception as exc:
                        # Drop this book's entire partial response on conflicting duplicates.
                        for event in events.values():
                            event['bookmakerOdds'].pop(slug, None)
                        errors.append(type(exc).__name__)
                fetched = current if now is not None else datetime.now(timezone.utc)
                if successful_books or not errors:
                    doc.update(events=[e for e in events.values() if e['bookmakerOdds']],
                               fetched_at=fetched.isoformat())
                doc.update(status='partial' if errors else 'complete', errors=errors, quota_before=quota)
            except Exception as exc:
                doc.update(status='failed', errors=[type(exc).__name__])
            text = json.dumps(doc, ensure_ascii=False, separators=(',', ':'))
            if len(text.encode()) > MAX_CACHE_BYTES:
                raise ValueError('bounded esports price cache exceeded')
            atomic_write_text(target, text)
            return {k: doc[k] for k in ('status', 'errors')} | {'events': len(doc['events'])}
    except (OSError, ValueError) as exc:
        return {'status': 'unavailable', 'error_type': type(exc).__name__, 'events': 0}


def snapshot_price_rows(snapshots):
    from riskobet_domain import stable_event_key
    rows = []
    for snapshot in snapshots:
        if snapshot.sport != 'esports' or esports_discipline(snapshot.competition) is None:
            continue
        identities = [f.factor_key.split(':', 1)[1] for f in snapshot.factors
                      if f.factor_key.startswith('esports_match_id:')]
        names = snapshot.event_label.split(' vs ')
        if len(identities) != 1 or len(names) != 2 or snapshot.event_key != stable_event_key('esports', 'pandascore', identities[0]):
            continue
        for side, selected in zip(('home', 'away'), names):
            rows.append(dict(candidate_id=f'price:{snapshot.event_key}:{side}', sport='E-Sport',
                market_key='H2H', selection=selected, selected_competitor=selected,
                competitor_a=names[0], competitor_b=names[1], competition=snapshot.competition,
                fixture_source='pandascore', provider_event_id=identities[0], scheduled_start=snapshot.starts_at.isoformat()))
    return rows
