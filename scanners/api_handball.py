"""Exact, budgeted API-Handball league inputs for the private 1X2 pilot.

Coverage: https://api-sports.io/sports/handball. League odds use the provider's
native game ID and update timestamp, bound to a previously verified schedule.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo

import requests

from api_budget import APIBudgetError, APIBudgetGovernor, APIBudgetPriority, DEFAULT_DB_PATH
from betting_math import BettingMathError, validate_decimal_odds

HOST = 'https://v1.handball.api-sports.io'
PROVIDER = 'api-sports-handball'
BUNDESLIGA_ID = 39
REGULATION_1X2_ID = 1
MAX_PRICE_AGE = timedelta(hours=36)
DEFAULT_REQUESTS_PER_MINUTE = 9
PAID_REQUESTS_PER_MINUTE = 11
_SIDES = ('Home', 'Draw', 'Away')


class HandballSourceError(RuntimeError):
    """An allowlisted local diagnosis, never a provider reply or URL."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class HandballLeague:
    code: str
    name: str
    country: str
    clock: ZoneInfo
    pinned_id: int | None = None
    pinned_country_id: int | None = None


_BUNDESLIGA = HandballLeague('DE', 'Bundesliga', 'Germany', ZoneInfo('Europe/Berlin'), BUNDESLIGA_ID, 13)
HANDBALL_LEAGUES = (
    HandballLeague('ES', 'Liga ASOBAL', 'Spain', ZoneInfo('Europe/Madrid')),
    _BUNDESLIGA,
    HandballLeague('DK', 'Herre Handbold Ligaen', 'Denmark', ZoneInfo('Europe/Copenhagen')),
    HandballLeague('FR', 'Starligue', 'France', ZoneInfo('Europe/Paris')),
    HandballLeague('HU', 'NB I', 'Hungary', ZoneInfo('Europe/Budapest')),
)


@dataclass(frozen=True)
class _LeagueSeason:
    profile: HandballLeague
    league_id: int
    country_id: int
    season: int
    first: date
    last: date

    def matches(self, league, country) -> bool:
        return (_matches_profile(self.profile, league, country)
                and _positive_id(league.get('id')) and league['id'] == self.league_id
                and _positive_id(country.get('id')) and country['id'] == self.country_id
                and type(league.get('season')) is int and league['season'] == self.season)


@dataclass(frozen=True)
class HandballGame:
    game_id: int
    league_id: int
    season: int
    starts_at: datetime
    home_id: int
    away_id: int
    home: str
    away: str
    status: str
    home_score: int | None
    away_score: int | None


@dataclass(frozen=True)
class HandballMarket:
    updated_at: datetime
    bookmakers: dict[str, tuple[float, float, float]]


def _positive_id(value) -> bool:
    return type(value) is int and 0 < value < 2**63


def _name(value) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 160 and value.strip() == value


def _clock(value) -> datetime | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(timezone.utc) if parsed.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _day(value) -> date | None:
    if not isinstance(value, str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _matches_kickoff(row, start: datetime) -> bool:
    return (('date' not in row or _clock(row['date']) == start)
            and ('timestamp' not in row or (type(row['timestamp']) is int and row['timestamp'] == start.timestamp())))


def _matches_profile(profile: HandballLeague, league, country) -> bool:
    return (isinstance(league, dict) and league.get('name') == profile.name and league.get('type') == 'League'
            and isinstance(country, dict) and country.get('name') == profile.country
            and country.get('code') == profile.code)


def _season(row, season: int) -> tuple[date, date]:
    seasons = row.get('seasons')
    matches = [item for item in seasons if isinstance(item, dict) and type(item.get('season')) is int
               and item['season'] == season] if isinstance(seasons, list) else []
    if len(matches) != 1:
        raise HandballSourceError('handball_league_unconfirmed')
    first, last = _day(matches[0].get('start')), _day(matches[0].get('end'))
    if first is None or last is None or first.year != season or not 0 < (last - first).days <= 366:
        raise HandballSourceError('handball_league_unconfirmed')
    return first, last


def _resolve_league(rows: list[dict], profile: HandballLeague, season: int) -> _LeagueSeason:
    matches = [row for row in rows if _matches_profile(profile, row, row.get('country'))]
    if len(matches) != 1:
        raise HandballSourceError('handball_league_unconfirmed')
    row = matches[0]
    native_id, country_id = row.get('id'), row['country'].get('id')
    if (not _positive_id(native_id) or not _positive_id(country_id)
            or (profile.pinned_id is not None and native_id != profile.pinned_id)
            or (profile.pinned_country_id is not None and country_id != profile.pinned_country_id)
            or (native_id == BUNDESLIGA_ID and profile != _BUNDESLIGA)
            or sum(item.get('id') == native_id for item in rows) != 1):
        raise HandballSourceError('handball_league_unconfirmed')
    first, last = _season(row, season)
    return _LeagueSeason(profile, native_id, country_id, season, first, last)


def _score(record) -> tuple[int, int] | None:
    if not isinstance(record, dict):
        return None
    home, away = record.get('home'), record.get('away')
    if type(home) is int and type(away) is int and 0 <= home <= 999 and 0 <= away <= 999:
        return home, away
    return None


def _regulation_score(row) -> tuple[int | None, int | None]:
    periods = row.get('periods')
    scores = _score(row.get('scores'))
    first, second = (_score(periods.get('first')), _score(periods.get('second'))) if isinstance(periods, dict) else (None, None)
    if first is None or second is None or scores != (first[0] + second[0], first[1] + second[1]):
        return None, None  # Keep the event identity, not an unverified result.
    return scores


def _game(row, league: _LeagueSeason) -> HandballGame:
    if not league.matches(row.get('league'), row.get('country')) or not _positive_id(row.get('id')):
        raise HandballSourceError('handball_invalid_game')
    start = _clock(row.get('date'))
    if (start is None or not league.first <= start.astimezone(league.profile.clock).date() <= league.last
            or not _matches_kickoff(row, start)):
        raise HandballSourceError('handball_invalid_game')
    teams, status = row.get('teams'), row.get('status')
    home, away = (teams.get('home'), teams.get('away')) if isinstance(teams, dict) else (None, None)
    code = status.get('short') if isinstance(status, dict) else None
    if (not isinstance(code, str) or re.fullmatch(r'[A-Z0-9]{1,12}', code) is None
            or not all(isinstance(team, dict) and _positive_id(team.get('id')) and _name(team.get('name'))
                       for team in (home, away))
            or home['id'] == away['id'] or home['name'].casefold() == away['name'].casefold()):
        raise HandballSourceError('handball_invalid_game')
    if code == 'NS' and isinstance(row.get('scores'), dict) and any(
        row['scores'].get(side) is not None for side in ('home', 'away')
    ):
        raise HandballSourceError('handball_invalid_game')
    h_score, a_score = _regulation_score(row) if code == 'FT' else (None, None)
    return HandballGame(row['id'], league.league_id, league.season, start, home['id'], away['id'],
                        home['name'], away['name'], code, h_score, a_score)


def _triplet(book) -> tuple[float, float, float] | None:
    bets = book.get('bets')
    if not isinstance(bets, list):
        return None
    matches = [bet for bet in bets if isinstance(bet, dict)
               and type(bet.get('id')) is int and bet['id'] == REGULATION_1X2_ID]
    if len(matches) != 1 or matches[0].get('name') != '3Way Result':
        return None
    values = matches[0].get('values')
    if not isinstance(values, list) or len(values) != 3:
        return None
    odds = {}
    for entry in values:
        side = entry.get('value') if isinstance(entry, dict) else None
        if not isinstance(side, str) or side not in _SIDES or side in odds:
            return None
        try:
            odds[side] = validate_decimal_odds(entry.get('odd'))
        except (BettingMathError, OverflowError):
            return None
    return odds['Home'], odds['Draw'], odds['Away']


def _odds_game_ids(row) -> list:
    ids = [row['game_id']] if 'game_id' in row else []
    if 'game' in row:
        native = row['game']
        ids.append(native.get('id') if isinstance(native, dict) else None)
    return ids


def _odds_game_details(row, game: HandballGame) -> bool:
    if not _matches_kickoff(row, game.starts_at):
        return False
    if 'teams' not in row:
        return True
    teams = row['teams']
    return isinstance(teams, dict) and all(
        isinstance(team, dict) and _positive_id(team.get('id')) and team['id'] == expected
        for team, expected in ((teams.get('home'), game.home_id), (teams.get('away'), game.away_id))
    )


def _market(row, game: HandballGame, observed: datetime, league: _LeagueSeason) -> HandballMarket | None:
    ids = _odds_game_ids(row)
    if (observed >= game.starts_at or not ids or any(not _positive_id(value) or value != game.game_id for value in ids)
            or not league.matches(row.get('league'), row.get('country'))
            or not _odds_game_details(row, game) or not _odds_game_details(row.get('game', {}), game)):
        return None
    times = [_clock(row[key]) for key in ('update', 'updated') if key in row]
    updated = times[0] if times else None
    books = row.get('bookmakers')
    if (updated is None or any(value != updated for value in times)
            or not observed - MAX_PRICE_AGE <= updated <= observed
            or not isinstance(books, list)):
        return None
    known = [book for book in books if isinstance(book, dict)
             and _positive_id(book.get('id')) and _name(book.get('name'))]
    seen_ids = {book['id'] for book in known}
    seen_names = {book['name'].casefold() for book in known}
    if len(known) != len(seen_ids) or len(known) != len(seen_names):
        return None  # Ambiguous bookmaker identities cannot supply a benchmark.
    bookmakers = {book['name']: odds for book in known if (odds := _triplet(book)) is not None}
    return HandballMarket(updated, bookmakers) if bookmakers else None


def _paid_rate_confirmed(headers) -> bool:
    normalized = {str(name).casefold(): str(value).strip() for name, value in (headers or {}).items()}
    day_limit = normalized.get('x-ratelimit-requests-limit', '')
    minute_limit = normalized.get('x-ratelimit-limit', '')
    return (re.fullmatch(r'[0-9]{1,9}', day_limit) is not None and int(day_limit) >= 7500
            and re.fullmatch(r'[0-9]{1,9}', minute_limit) is not None and int(minute_limit) >= 60)


class APIHandballClient:
    def __init__(self, key: str, *, governor=None, get=requests.get, clock: Callable[[], datetime] | None = None):
        self._key = key
        self._governor = governor
        self._get = get
        self._clock = clock
        self._catalogue: list[dict] | None = None
        self._catalogue_error: str | None = None
        self._confirmed: dict[tuple[int, int], tuple[_LeagueSeason, dict[int, HandballGame]]] = {}
        self._minute_limit = DEFAULT_REQUESTS_PER_MINUTE

    def _request(self, endpoint: str, params: dict) -> list[dict]:
        try:
            if self._governor is None:
                self._governor = APIBudgetGovernor(DEFAULT_DB_PATH, daily_limit=100, critical_floor=5,
                                                    recommendation_reserve=10, background_reserve=15)
            if self._governor.recent_request_count(api_key=self._key, provider=PROVIDER, seconds=60) >= self._minute_limit:
                raise HandballSourceError('api_rate_limit_deferred')
            reservation = self._governor.reserve(api_key=self._key, provider=PROVIDER, endpoint=endpoint,
                                                 priority=APIBudgetPriority.BACKGROUND)
        except APIBudgetError:
            raise HandballSourceError('api_budget_unavailable') from None
        response = error = None
        try:
            try:
                response = self._get(f'{HOST}/{endpoint}', params=params, headers={'x-apisports-key': self._key},
                                     timeout=10, allow_redirects=False)
            except requests.RequestException:
                raise HandballSourceError('api_transport_error') from None
            if response.status_code != 200:
                code = {429: 'api_rate_limit', 401: 'api_access_denied', 403: 'api_access_denied'}
                raise HandballSourceError(code.get(response.status_code, 'api_http_error'))
            try:
                payload = response.json()
            except ValueError:
                raise HandballSourceError('api_invalid_json') from None
            if not isinstance(payload, dict) or payload.get('get', endpoint) != endpoint:
                raise HandballSourceError('api_invalid_envelope')
            if errors := payload.get('errors'):
                code = 'api_plan_error' if isinstance(errors, dict) and 'plan' in errors else 'api_reported_error'
                raise HandballSourceError(code)
            rows, paging = payload.get('response'), payload.get('paging', {'current': 1, 'total': 1})
            if (not isinstance(rows, list) or len(rows) > 512 or any(not isinstance(row, dict) for row in rows)
                    or type(payload.get('results', len(rows))) is not int or payload.get('results', len(rows)) != len(rows)):
                raise HandballSourceError('api_invalid_response_list')
            if (not isinstance(paging, dict) or type(paging.get('total')) is not int or paging['total'] != 1
                    or type(paging.get('current', 1)) is not int or paging.get('current', 1) != 1):
                raise HandballSourceError('api_incomplete_page')
            self._minute_limit = (PAID_REQUESTS_PER_MINUTE if _paid_rate_confirmed(getattr(response, 'headers', None))
                                  else DEFAULT_REQUESTS_PER_MINUTE)
            return rows
        except HandballSourceError as exc:
            error = exc.code
            raise
        finally:
            try:
                self._governor.complete(reservation, response_headers=getattr(response, 'headers', None),
                                        http_status=getattr(response, 'status_code', None), error=error)
            except APIBudgetError:
                raise HandballSourceError('api_budget_unavailable') from None

    def league_games(self, league: HandballLeague, season: int) -> list[HandballGame]:
        if league not in HANDBALL_LEAGUES or type(season) is not int or not 1900 <= season <= 2100:
            raise HandballSourceError('handball_league_unconfirmed')
        if self._catalogue_error is not None:
            raise HandballSourceError(self._catalogue_error)
        if self._catalogue is None:
            try:
                self._catalogue = self._request('leagues', {})
            except HandballSourceError as exc:
                self._catalogue_error = exc.code
                raise
        return self._league_games(_resolve_league(self._catalogue, league, season))

    def bundesliga_games(self, season: int) -> list[HandballGame]:
        """Retain the pilot's pinned request for callers loading Germany only."""
        if type(season) is not int or not 1900 <= season <= 2100:
            raise HandballSourceError('handball_league_unconfirmed')
        if self._catalogue is not None or self._catalogue_error is not None:
            return self.league_games(_BUNDESLIGA, season)
        rows = self._request('leagues', {'id': BUNDESLIGA_ID})
        if len(rows) != 1:
            raise HandballSourceError('handball_league_unconfirmed')
        return self._league_games(_resolve_league(rows, _BUNDESLIGA, season))

    def _league_games(self, league: _LeagueSeason) -> list[HandballGame]:
        key = (league.league_id, league.season)
        self._confirmed.pop(key, None)
        games = [_game(row, league) for row in self._request('games', {'league': key[0], 'season': key[1]})]
        if len({row.game_id for row in games}) != len(games):
            raise HandballSourceError('handball_duplicate_game')
        self._confirmed[key] = (league, {row.game_id: row for row in games if row.status == 'NS'})
        return sorted(games, key=lambda row: (row.starts_at, row.game_id))

    def _odds_observed_at(self, requested: datetime) -> datetime | None:
        # Frozen-time callers can supply just `now`; collectors inject a live clock.
        observed = self._clock() if self._clock is not None else requested
        if not isinstance(observed, datetime) or observed.utcoffset() is None:
            return None
        observed = observed.astimezone(timezone.utc)
        return observed if observed >= requested.astimezone(timezone.utc) else None

    def league_prices(self, league: HandballLeague, season: int, *, now: datetime) -> dict[int, HandballMarket]:
        """Read one league odds page and retain only exact upcoming game markets."""
        if now.utcoffset() is None or league not in HANDBALL_LEAGUES or type(season) is not int:
            return {}
        context = next((item for item in self._confirmed.values()
                        if item[0].profile == league and item[0].season == season), None)
        if context is None:
            return {}
        confirmed, games = context
        now = now.astimezone(timezone.utc)
        upcoming = {game_id: game for game_id, game in games.items() if now < game.starts_at}
        if not upcoming:
            return {}
        rows = self._request('odds', {'league': confirmed.league_id, 'season': season, 'bet': REGULATION_1X2_ID})
        observed = self._odds_observed_at(now)
        if observed is None:
            return {}
        candidates: dict[int, dict | None] = {}
        for row in rows:
            for game_id in {value for value in _odds_game_ids(row) if _positive_id(value)} & upcoming.keys():
                # Only identical rows can repeat; compare before reducing payloads to bookmaker names.
                candidates[game_id] = None if game_id in candidates and candidates[game_id] != row else row
        return {game_id: market for game_id, row in candidates.items() if row is not None
                and (market := _market(row, upcoming[game_id], observed, confirmed)) is not None}

    def prices(self, game: HandballGame, *, now: datetime) -> dict[str, tuple[float, float, float]]:
        """Return complete per-book regulation 1X2 observations, not offers."""
        if (now.utcoffset() is None or game.status != 'NS' or now >= game.starts_at
                or not _positive_id(game.game_id) or not _positive_id(game.league_id) or type(game.season) is not int):
            return {}
        context = self._confirmed.get((game.league_id, game.season))
        if context is None:
            return {}
        league, games = context
        if games.get(game.game_id) != game:
            return {}
        rows = self._request('odds', {'game': game.game_id, 'bet': REGULATION_1X2_ID})
        observed = self._odds_observed_at(now)
        market = _market(rows[0], game, observed, league) if observed is not None and len(rows) == 1 else None
        return market.bookmakers if market is not None else {}
