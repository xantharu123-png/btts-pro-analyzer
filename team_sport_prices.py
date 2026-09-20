"""Bounded, shared pre-match odds from the existing API-Sports account.

Home/Away is the full-game two-way winner, including overtime/shootout.
Neither a regulation 3-way market nor a half/period market can substitute it.
The provider does not expose bookmaker update times here: these are retrieval
observations only, never automatic execution evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping

import requests

from api_budget import APIBudgetGovernor, APIBudgetPriority, DEFAULT_DB_PATH
from market_consensus import (
    MarketConsensus, QuotePoint, TEAM_PRICE_SOURCES, _identity_name,
    _parse_utc, _summary_prices, observed_consensus, quote_matches_candidate,
)
from betting_math import validate_decimal_odds
from runtime_paths import atomic_write_text, prepare_trusted_runtime_database_path

CACHE_PATH = Path(__file__).resolve().parent / 'runtime_state' / 'team_sport_quotes.json'
REFRESH_AFTER = timedelta(hours=3)
MAX_EVENTS_PER_SPORT = 8
MAX_CACHE_BYTES = 2_000_000
SPORTS = {'basketball': 'basketball', 'eishockey': 'ice_hockey', 'ice_hockey': 'ice_hockey'}
HOSTS = {'basketball': 'https://v1.basketball.api-sports.io', 'ice_hockey': 'https://v1.hockey.api-sports.io'}
LEAGUES = {'basketball': {'nba': 'nba', 'euroleague': 'euroleague'}, 'ice_hockey': {'nhl': 'nhl'}}


def _sport(row):
    return SPORTS.get(str(row.get('sport') or '').casefold())


def _binding(row):
    sport = _sport(row)
    start = _parse_utc(row.get('scheduled_start'))
    a, b, selected = (str(row.get(k) or '').strip() for k in ('competitor_a', 'competitor_b', 'selected_competitor'))
    origin, event = str(row.get('fixture_source') or '').strip(), str(row.get('provider_event_id') or '').strip()
    if (sport is None or start is None or row.get('market_key') != 'H2H'
            or not origin or not event or not a or not b or _identity_name(a) == _identity_name(b)
            or selected not in (a, b) or _identity_name(row.get('competition')) not in LEAGUES[sport]):
        return None
    return sport, origin, event, start.isoformat(), a, b, selected


def _key(row):
    binding = _binding(row)
    return hashlib.sha256(json.dumps(binding, ensure_ascii=True).encode()).hexdigest() if binding else None


def snapshot_price_rows(snapshots):
    """Price existing event identities, even while the sporting model is incomplete."""
    result = []
    for snapshot in snapshots:
        forecast = snapshot.team_sport_forecast
        if forecast is None or forecast.sport not in HOSTS:
            continue
        for side, selected in (('home', forecast.home), ('away', forecast.away)):
            key = f'price:{snapshot.event_key}:{side}'
            result.append(dict(candidate_id=key,key=key,sport=forecast.sport,
                fixture_source=forecast.provider,provider_event_id=forecast.provider_event_id,
                scheduled_start=snapshot.starts_at.isoformat(),competition=snapshot.competition,
                competitor_a=forecast.home,competitor_b=forecast.away,selected_competitor=selected,
                market_key='H2H',selection=selected))
    return result


def _read(path):
    try:
        if path.is_symlink() or path.stat().st_size > MAX_CACHE_BYTES:
            return {}
        doc = json.loads(path.read_text(encoding='utf-8'))
        if doc.get('schema') != 1 or not isinstance(doc.get('quotes'), dict) or not isinstance(doc.get('attempts'), dict):
            return {}
        return doc
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


@contextmanager
def _writer_lock(path):
    target = prepare_trusted_runtime_database_path(path)
    lock = prepare_trusted_runtime_database_path(target.with_suffix('.lock'))
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def load_cached_quote(row, *, now=None, path=CACHE_PATH, document=None):
    """Read-only exact origin/start/side lookup; no provider request on page load."""
    current = now or datetime.now(timezone.utc)
    if not isinstance(row, Mapping) or _binding(row) is None:
        return None
    doc = document if document is not None else _read(Path(path))
    entry = doc.get('quotes', {}).get(_key(row))
    if not isinstance(entry, dict) or entry.get('binding') != list(_binding(row)):
        return None
    quote = MarketConsensus.from_dict(entry.get('quote'))
    if quote is None or quote.candidate_id != _key(row):
        return None
    quote = replace(quote, candidate_id=str(row.get('candidate_id') or row.get('key') or ''))
    # Pre-match observations are not live prices and disappear at kickoff.
    start = _parse_utc(row.get('scheduled_start'))
    if start is None or start <= current or not quote_matches_candidate(quote, row):
        return None
    return observed_consensus(quote, candidate=row, now=current)


def _json_get(sport, endpoint, params, api_key, *, governor, get=requests.get):
    reservation = governor.reserve(api_key=api_key, provider=f'api-sports-{sport}',
        endpoint=endpoint, priority=APIBudgetPriority.BACKGROUND)
    response = None
    error = None
    try:
        response = get(HOSTS[sport] + '/' + endpoint, params=params,
            headers={'x-apisports-key': api_key}, timeout=10, allow_redirects=False)
        if response.status_code != 200:
            raise ValueError(f'HTTP_{response.status_code}')
        payload = response.json()
        if not isinstance(payload, dict) or payload.get('errors') or not isinstance(payload.get('response'), list):
            raise ValueError('provider_payload')
        paging = payload.get('paging') or {}
        if paging.get('total', 1) != 1:
            raise ValueError('incomplete_provider_page')
        return payload['response']
    except Exception as exc:
        error = type(exc).__name__  # Never include credential-bearing request URLs.
        raise
    finally:
        governor.complete(reservation, response_headers=getattr(response, 'headers', None),
            http_status=getattr(response, 'status_code', None), error=error)


def _nhl_names(row, payload):
    """Resolve abbreviations using the original NHL event, not fuzzy names."""
    found = []
    for day in payload.get('gameWeek', []):
        for game in day.get('games', []):
            if str(game.get('id')) != row['provider_event_id']:
                continue
            if _parse_utc(game.get('startTimeUTC')) != _parse_utc(row['scheduled_start']):
                continue
            home, away = game.get('homeTeam', {}), game.get('awayTeam', {})
            if home.get('abbrev') != row['competitor_a'] or away.get('abbrev') != row['competitor_b']:
                continue
            names = []
            for team in (home, away):
                place, club = team.get('placeName', {}).get('default'), team.get('commonName', {}).get('default')
                if not isinstance(place, str) or not isinstance(club, str):
                    break
                names.append(place + ' ' + club)
            if len(names) == 2:
                found.append(tuple(names))
    return found[0] if len(found) == 1 else None


def match_game(row, games, names):
    sport = _sport(row)
    found = []
    for game in games:
        if not isinstance(game, dict) or type(game.get('id')) is not int or game['id'] <= 0:
            continue
        if game.get('status', {}).get('short') != 'NS':
            continue
        if _identity_name(game.get('league', {}).get('name')) != LEAGUES[sport].get(_identity_name(row.get('competition'))):
            continue
        if _parse_utc(game.get('date')) != _parse_utc(row.get('scheduled_start')):
            continue
        teams = game.get('teams', {})
        pair = tuple(_identity_name(teams.get(side, {}).get('name')) for side in ('home', 'away'))
        if pair == tuple(_identity_name(n) for n in names):
            found.append(game)
    return found[0] if len(found) == 1 else None


def parse_game_quotes(entries, rows, game, *, fetched_at, names=None):
    """Exact game/side/market parsing of original API-Sports responses."""
    output = {}
    matching = [e for e in entries if isinstance(e, dict) and e.get('game') == game]
    if len(matching) != 1 or game.get('status', {}).get('short') != 'NS':
        return output
    for row in rows:
        if _binding(row) is None or _parse_utc(row['scheduled_start']) <= fetched_at:
            continue
        native_names = names or (row['competitor_a'], row['competitor_b'])
        if match_game(row, [game], native_names) is None:
            continue
        selected_side = 'Home' if row['selected_competitor'] == row['competitor_a'] else 'Away'
        points, conflicts = {}, set()
        for book in matching[0].get('bookmakers', []):
            if not isinstance(book, dict) or type(book.get('id')) is not int or book['id'] <= 0 or not str(book.get('name') or '').strip():
                continue
            book_id = f"api-sports-{_sport(row)}:{book['id']}"
            for market in book.get('bets', []):
                if not isinstance(market, dict) or type(market.get('id')) is not int or market['id'] != 2 or market.get('name') != 'Home/Away':
                    continue
                values = market.get('values', [])
                if not isinstance(values, list) or len(values) != 2 or {v.get('value') for v in values if isinstance(v, dict)} != {'Home', 'Away'}:
                    continue
                try:
                    # Invalid opposing odds reject a malformed two-way market, too.
                    pair = {v['value']: validate_decimal_odds(v['odd']) for v in values}
                except (TypeError, ValueError, KeyError):
                    continue
                point = QuotePoint(book['name'], pair[selected_side], book_id, fetched_at.isoformat())
                if book_id in points and points[book_id] != point:
                    conflicts.add(book_id)
                points[book_id] = point
        points = tuple(p for key, p in sorted(points.items()) if key not in conflicts)
        if not points:
            continue
        lowest, conservative, median, best = _summary_prices(sorted(p.odds for p in points))
        quote = MarketConsensus(None, str(row.get('candidate_id') or row.get('key')), 'H2H',
            'Home/Away including overtime', row['selected_competitor'], median, conservative,
            lowest, best, len(points), fetched_at.isoformat(), fetched_at.isoformat(),
            TEAM_PRICE_SOURCES[_sport(row)], points, str(game['id']), row['scheduled_start'],
            row['competitor_a'], row['competitor_b'], row['fixture_source'], row['provider_event_id'])
        if quote_matches_candidate(quote, row):
            output[quote.candidate_id] = quote
    return output


def refresh_team_sport_prices(rows, *, api_key, now=None, path=CACHE_PATH, governor=None, get=requests.get):
    """One bounded refresh in the existing worker; no new scheduler or database."""
    current = now or datetime.now(timezone.utc)
    if not api_key:
        return {'status': 'missing_key', 'quotes': 0}
    if current.tzinfo is None:
        raise ValueError('aware clock required')
    current = current.astimezone(timezone.utc)
    grouped = {}
    for row in rows:
        binding = _binding(row)
        if binding is not None and current < _parse_utc(binding[3]) <= current + timedelta(days=3):
            grouped.setdefault(binding[:4], []).append(row)
    if not grouped:
        return {'status': 'no_events', 'quotes': 0}
    identities = {}
    for group_id, group in grouped.items():
        row = group[0]
        identity = (_sport(row), row['scheduled_start'], _identity_name(row['competitor_a']),
                    _identity_name(row['competitor_b']), _identity_name(row['competition']))
        identities.setdefault(identity, set()).add(group_id)
    ambiguous = {key for keys in identities.values() if len(keys) > 1 for key in keys}
    target = Path(path)
    errors, checked, matched = [], 0, 0
    from time import monotonic
    deadline = monotonic() + 35
    try:
        with _writer_lock(target):
            doc = _read(target) or {'schema': 1, 'quotes': {}, 'attempts': {}}
            # Current events only, one price per event/side; no accumulating history.
            wanted = {_key(r) for group in grouped.values() for r in group}
            doc['quotes'] = {k: v for k, v in doc['quotes'].items() if k in wanted}
            governor = governor or APIBudgetGovernor(DEFAULT_DB_PATH, daily_limit=100,
                critical_floor=5, recommendation_reserve=10, background_reserve=15)
            games_cache, nhl_cache, used = {}, {}, {}
            attempts = {}
            for group_id, group in sorted(grouped.items(), key=lambda item: item[0][3]):
                if monotonic() >= deadline:
                    break
                sport, origin, event, start = group_id
                attempt_key = '|'.join(group_id)
                last = _parse_utc(doc['attempts'].get(attempt_key))
                if last is not None and timedelta(0) <= current - last < REFRESH_AFTER:
                    attempts[attempt_key] = last.isoformat()
                    continue
                if used.get(sport, 0) >= MAX_EVENTS_PER_SPORT:
                    continue
                used[sport] = used.get(sport, 0) + 1
                date = _parse_utc(start).date().isoformat()
                try:
                    if group_id in ambiguous:
                        for r in group:
                            doc['quotes'].pop(_key(r), None)
                        raise ValueError('ambiguous_origin_events')
                    if len({(_binding(r)[4], _binding(r)[5], r.get('competition')) for r in group}) != 1:
                        raise ValueError('conflicting_origin_identity')
                    names = (group[0]['competitor_a'], group[0]['competitor_b'])
                    if sport == 'ice_hockey' and origin == 'NHL':
                        if date not in nhl_cache:
                            native = get('https://api-web.nhle.com/v1/schedule/' + date, timeout=10, allow_redirects=False)
                            if native.status_code != 200:
                                raise ValueError('native_identity_unavailable')
                            nhl_cache[date] = native.json()
                        names = _nhl_names(group[0], nhl_cache[date])
                    if names is None:
                        for r in group:
                            doc['quotes'].pop(_key(r), None)
                        raise ValueError('native_identity_unbound')
                    if (sport, date) not in games_cache:
                        games_cache[sport, date] = _json_get(sport, 'games', {'date': date}, api_key, governor=governor, get=get)
                    game = match_game(group[0], games_cache[sport, date], names)
                    if game is not None:
                        matched += 1
                        entries = _json_get(sport, 'odds', {'game': game['id']}, api_key, governor=governor, get=get)
                        for r in group:
                            doc['quotes'].pop(_key(r), None)
                        # The recorded retrieval clock belongs to the actual completed call.
                        fetched = current if now is not None else datetime.now(timezone.utc)
                        for quote in parse_game_quotes(entries, group, game, fetched_at=fetched, names=names).values():
                            row = next(r for r in group if str(r.get('candidate_id') or r.get('key')) == quote.candidate_id)
                            key = _key(row)
                            doc['quotes'][key] = {'binding': list(_binding(row)), 'quote': replace(quote, candidate_id=key).to_dict()}
                    else:
                        for r in group:
                            doc['quotes'].pop(_key(r), None)
                    checked += 1
                except Exception as exc:
                    errors.append(f'{sport}:{type(exc).__name__}')
                attempts[attempt_key] = current.isoformat()
            doc.update(attempts=attempts, updated_at=current.isoformat(), errors=errors)
            text = json.dumps(doc, ensure_ascii=False, separators=(',', ':'))
            if len(text.encode('utf-8')) > MAX_CACHE_BYTES:
                raise ValueError('bounded_quote_cache_exceeded')
            atomic_write_text(target, text)
            return {'status': 'partial' if errors else 'complete', 'checked': checked,
                    'matched_games': matched, 'quotes': len(doc['quotes']), 'errors': errors}
    except OSError as exc:
        return {'status': 'unavailable', 'error_type': type(exc).__name__, 'quotes': 0}


def attach_cached_team_prices(rows, *, now=None, path=CACHE_PATH):
    doc = _read(Path(path))
    result = []
    for row in rows:
        quote = load_cached_quote(row, now=now, document=doc)
        result.append(dict(row, reference_quote=quote.to_dict()) if quote is not None else row)
    return result


if __name__ == '__main__':
    from config_loader import load_app_config
    from riskobet_ui import load_riskobet_view
    rows = snapshot_price_rows(load_riskobet_view().snapshots.values())
    print(json.dumps(refresh_team_sport_prices(rows, api_key=load_app_config().api_football_key)))
