"""Read-only Wettfinder bridge for exact, current handball model selections."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from math import isclose, isfinite
import os
from statistics import median

from betting_math import BettingMathError, MINIMUM_RECOMMENDED_DECIMAL_ODDS, validate_decimal_odds
from scanners.api_handball import HANDBALL_LEAGUES, MAX_PRICE_AGE


_OUTCOMES = ('home', 'draw', 'away')
_HORIZON = timedelta(hours=36)
_STATE_SIZE = 1024 * 1024


@dataclass(frozen=True)
class HandballSelection:
    event_id: str
    league: str
    home: str
    away: str
    starts_at: datetime
    side: str
    probability: float
    expires_at: datetime


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _id(value):
    return type(value) is int and 0 < value < 2**63


def _name(value):
    return (isinstance(value, str) and 0 < len(value) <= 160 and value.strip() == value
            and value.isprintable())


def _modal_side(probability):
    if (not isinstance(probability, dict) or set(probability) != set(_OUTCOMES)
            or any(type(p) not in (float, int) or not 0 <= p <= 1 for p in probability.values())
            or not isclose(sum(probability.values()), 1., rel_tol=0., abs_tol=1e-6)):
        return None
    side = max(_OUTCOMES, key=probability.__getitem__)
    if sum(isclose(p, probability[side], rel_tol=0., abs_tol=1e-12) for p in probability.values()) > 1:
        return None
    return side


def _passes_floor(value):
    if type(value) not in (float, int):
        return False
    try:
        return isfinite(value) and value >= MINIMUM_RECOMMENDED_DECIMAL_ODDS
    except OverflowError:
        return False


def build_handball_publication(league, *, games, forecasts, markets, observed_at):
    """Build current receipts; neither update first odds nor choose a side by price."""
    rows = {}
    ids = {game.league_id for game in games}
    league_id = next(iter(ids)) if len(ids) == 1 else None
    envelope = {'league_code': league.code, 'league_id': league_id, 'rows': rows}
    if not _id(league_id):
        return envelope
    for game in games:
        key = str(game.game_id)
        row = forecasts.get(key)
        market = markets.get(game.game_id)
        fixture = [game.league_id, game.season, game.home_id, game.away_id, game.starts_at.isoformat()]
        if (row is None or market is None or row['fixture'] != fixture or 'result' in row
                or game.status != 'NS' or not _name(game.home) or not _name(game.away)
                or not observed_at < game.starts_at <= observed_at + _HORIZON
                or not observed_at - MAX_PRICE_AGE < market.updated_at <= observed_at):
            continue
        decided = _time(row.get('decided_at'))
        side = _modal_side(row.get('p'))
        if side is None or decided is None or decided > observed_at or game.starts_at - decided > _HORIZON:
            continue
        quotes = []
        for triplet in market.bookmakers.values():
            if not isinstance(triplet, (tuple, list)) or len(triplet) != 3:
                continue
            try:
                prices = tuple(validate_decimal_odds(value) for value in triplet)
            except (BettingMathError, OverflowError):
                continue
            quotes.append(prices[_OUTCOMES.index(side)])
        if quotes and _passes_floor(consensus := median(quotes)):
            rows[key] = {'fixture': fixture, 'home': game.home, 'away': game.away, 'side': side,
                         'median': consensus, 'source_at': market.updated_at.isoformat(),
                         'observed_at': observed_at.isoformat()}
    return envelope


def _display_row(profile, league_id, season, game_id, forecast, receipt, now):
    if not isinstance(forecast, dict) or not isinstance(receipt, dict) or 'result' in forecast:
        return None
    fixture = receipt.get('fixture')
    if (not isinstance(fixture, list) or len(fixture) != 5 or fixture != forecast.get('fixture')
            or not all(_id(value) for value in fixture[:4]) or fixture[:2] != [league_id, season]
            or fixture[2] == fixture[3] or (profile.pinned_id is not None and fixture[0] != profile.pinned_id)
            or not _name(receipt.get('home')) or not _name(receipt.get('away'))):
        return None
    source = _time(receipt.get('source_at'))
    observed = _time(receipt.get('observed_at'))
    decided = _time(forecast.get('decided_at'))
    start = _time(fixture[4])
    if (None in (source, observed, decided, start) or not decided <= observed <= now < start
            or not now - MAX_PRICE_AGE < source <= observed or start - decided > _HORIZON):
        return None
    consensus = receipt.get('median')
    side = _modal_side(forecast.get('p'))
    if side is None or receipt.get('side') != side or not _passes_floor(consensus):
        return None
    return HandballSelection(
        f'{profile.code}:{fixture[0]}:{season}:{game_id}', profile.name, receipt['home'], receipt['away'],
        start, side, forecast['p'][side], min(start, source + MAX_PRICE_AGE),
    )


def read_handball_selections(*, now, directory=None) -> tuple[HandballSelection, ...]:
    """Read current league snapshots without modifying files or opening a provider."""
    if os.getenv('BETBOY_HANDBALL_PILOT') != '1' or now.utcoffset() is None:
        return ()
    from handball_pilot import _path, _season

    picks = []
    season = _season(now)
    for profile in HANDBALL_LEAGUES:
        path = _path(now, profile.code, directory)
        try:
            if not path.is_file() or path.is_symlink():
                continue
            with path.open(encoding='utf-8') as handle:
                raw = handle.read(_STATE_SIZE + 1)
            if len(raw) > _STATE_SIZE:
                continue
            data = json.loads(raw)
        except (OSError, ValueError, RecursionError):
            continue
        if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 3:
            continue
        forecasts, publication = data.get('forecasts'), data.get('publication')
        if (not isinstance(forecasts, dict) or not isinstance(publication, dict)
                or publication.get('league_code') != profile.code or not isinstance(publication.get('rows'), dict)
                or not _id(league_id := publication.get('league_id'))):
            continue
        for key, receipt in publication['rows'].items():
            if (len(key) > 19 or not key.isascii() or not key.isdecimal()
                    or not _id(game_id := int(key)) or key != str(game_id)):
                continue
            pick = _display_row(profile, league_id, season, game_id, forecasts.get(key), receipt, now)
            if pick is not None:
                picks.append(pick)
    return tuple(sorted(picks, key=lambda pick: (pick.starts_at, pick.event_id)))
