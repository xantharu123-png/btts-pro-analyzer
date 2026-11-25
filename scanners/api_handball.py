"""Exact, budgeted API-Handball Bundesliga inputs for the private 1X2 pilot.

Coverage: https://api-sports.io/sports/handball. The response contract is
covered offline; confirm it with the actual account before enabling the pilot.
"""
from __future__ import annotations

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
_GERMAN_CLOCK = ZoneInfo('Europe/Berlin')
_SIDES = ('Home', 'Draw', 'Away')


class HandballSourceError(RuntimeError):
    """An allowlisted local diagnosis, never a provider reply or URL."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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


def _bundesliga(league, country) -> bool:
    return (isinstance(league, dict) and type(league.get('id')) is int and league['id'] == BUNDESLIGA_ID
            and league.get('name') == 'Bundesliga' and league.get('type') == 'League'
            and isinstance(country, dict) and type(country.get('id')) is int and country['id'] == 13
            and country.get('name') == 'Germany' and country.get('code') == 'DE')


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


def _game(row, *, season: int, season_start: date, season_end: date) -> HandballGame:
    league, country = row.get('league'), row.get('country')
    if (not _bundesliga(league, country) or type(league.get('season')) is not int or league['season'] != season
            or not _positive_id(row.get('id'))):
        raise HandballSourceError('handball_invalid_game')
    start = _clock(row.get('date'))
    if (start is None or not season_start <= start.astimezone(_GERMAN_CLOCK).date() <= season_end
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
    return HandballGame(row['id'], BUNDESLIGA_ID, season, start, home['id'], away['id'], home['name'],
                        away['name'], code, h_score, a_score)


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


def _prices(row, game: HandballGame, now: datetime) -> dict[str, tuple[float, float, float]]:
    league = row.get('league')
    if (type(row.get('game_id')) is not int or row['game_id'] != game.game_id
            or not _bundesliga(league, row.get('country'))
            or type(league.get('season')) is not int or league['season'] != game.season
            or not _matches_kickoff(row, game.starts_at)):
        return {}
    if 'teams' in row:
        teams = row['teams']
        if not isinstance(teams, dict) or not all(
            isinstance(team, dict) and _positive_id(team.get('id')) and team['id'] == expected
            for team, expected in ((teams.get('home'), game.home_id), (teams.get('away'), game.away_id))
        ):
            return {}
    updated, books = _clock(row.get('updated')), row.get('bookmakers')
    if updated is None or not now - MAX_PRICE_AGE <= updated <= now or not isinstance(books, list):
        return {}
    known = [book for book in books if isinstance(book, dict)
             and _positive_id(book.get('id')) and _name(book.get('name'))]
    seen_ids = {book['id'] for book in known}
    seen_names = {book['name'].casefold() for book in known}
    if len(known) != len(seen_ids) or len(known) != len(seen_names):
        return {}  # Ambiguous bookmaker identities cannot supply a benchmark.
    return {book['name']: odds for book in known if (odds := _triplet(book)) is not None}


class APIHandballClient:
    def __init__(self, key: str, *, governor=None, get=requests.get):
        self._key = key
        self._governor = governor
        self._get = get

    def _request(self, endpoint: str, params: dict) -> list[dict]:
        try:
            if self._governor is None:
                self._governor = APIBudgetGovernor(DEFAULT_DB_PATH, daily_limit=100, critical_floor=5,
                                                    recommendation_reserve=10, background_reserve=15)
            if self._governor.recent_request_count(api_key=self._key, provider=PROVIDER, seconds=60) >= 9:
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

    def bundesliga_games(self, season: int) -> list[HandballGame]:
        if type(season) is not int or not 1900 <= season <= 2100:
            raise HandballSourceError('handball_league_unconfirmed')
        rows = self._request('leagues', {'id': BUNDESLIGA_ID})
        if len(rows) != 1 or not _bundesliga(rows[0], rows[0].get('country')):
            raise HandballSourceError('handball_league_unconfirmed')
        first, last = _season(rows[0], season)
        games = [_game(row, season=season, season_start=first, season_end=last)
                 for row in self._request('games', {'league': BUNDESLIGA_ID, 'season': season})]
        if len({row.game_id for row in games}) != len(games):
            raise HandballSourceError('handball_duplicate_game')
        return sorted(games, key=lambda row: (row.starts_at, row.game_id))

    def prices(self, game: HandballGame, *, now: datetime) -> dict[str, tuple[float, float, float]]:
        """Return complete per-book regulation 1X2 observations, not offers."""
        if (now.utcoffset() is None or game.status != 'NS' or game.league_id != BUNDESLIGA_ID
                or now >= game.starts_at or not _positive_id(game.game_id)):
            return {}
        rows = self._request('odds', {'game': game.game_id, 'bet': REGULATION_1X2_ID})
        return _prices(rows[0], game, now.astimezone(timezone.utc)) if len(rows) == 1 else {}
