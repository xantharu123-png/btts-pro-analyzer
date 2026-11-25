"""Internal European handball 1X2 pilot; default CLI is read-only."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from config_loader import load_handball_api_key
from handball_pilot_model import predict_1x2
from handball_publication import build_handball_publication
from runtime_paths import PROJECT_ROOT, RUNTIME_STATE_DIR, atomic_write_text, prepare_trusted_runtime_database_path
from scanners.api_handball import APIHandballClient, HANDBALL_LEAGUES, HandballSourceError


_ZONE = ZoneInfo('Europe/Zurich')
_OUTCOMES = ('home', 'draw', 'away')
_MAX_PRICE_CALLS = 4
_PROVIDER_STOP = {'api_rate_limit', 'api_rate_limit_deferred', 'api_budget_unavailable', 'api_access_denied'}
_HORIZON = timedelta(hours=36)
_ODDS_HORIZON = timedelta(days=7)


def _utcnow():
    return datetime.now(timezone.utc)


def _season(now):
    local = now.astimezone(_ZONE)
    return local.year - int(local.month < 7)


def _path(now, country='DE', directory=None):
    # Keep the existing German receipt path; other leagues cannot share it.
    suffix = '' if country == 'DE' else f'_{country.lower()}'
    directory = Path(directory) if directory is not None else RUNTIME_STATE_DIR
    return directory / f'handball_pilot{suffix}_{_season(now)}.json'


def _load(path):
    if not path.exists():
        return {'version': 2, 'forecasts': {}, 'run': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] not in {1, 2, 3}
            or not isinstance(data.get('forecasts'), dict) or not isinstance(data.get('run'), dict)):
        raise ValueError('unknown_handball_pilot_state')
    for row in data['forecasts'].values():
        if not isinstance(row, dict):
            raise ValueError('invalid_handball_forecast')
        if 'price_source_at' in row:
            source = datetime.fromisoformat(row['price_source_at'])
            observed = datetime.fromisoformat(row['price_observed_at'])
            if source.utcoffset() is None or observed.utcoffset() is None or source > observed:
                raise ValueError('invalid_handball_price_clock')
    return data


def _write(path, data):
    data['version'] = 3 if 'publication' in data else 2
    atomic_write_text(path, json.dumps(data, allow_nan=False, sort_keys=True))


def _identity(game):
    return [game.league_id, game.season, game.home_id, game.away_id, game.starts_at.isoformat()]


def _market_probability(books):
    shares = []
    for odds in books.values():
        inverse = [1 / price for price in odds]
        total = sum(inverse)
        shares.append([value / total for value in inverse])
    return [sum(side) / len(shares) for side in zip(*shares)]


def _report(data):
    forecasts = data['forecasts'].values()
    settled = [row for row in forecasts if 'result' in row]
    paired = [row for row in settled if row.get('odds')]
    starts = sorted(row['fixture'][-1] for row in paired)
    model_brier = market_brier = 0.
    for row in paired:
        outcome = row['result']
        market = _market_probability(row['odds'])
        model_brier += sum((row['p'][side] - (side == outcome)) ** 2 for side in _OUTCOMES)
        market_brier += sum((probability - (side == outcome)) ** 2
                            for side, probability in zip(_OUTCOMES, market))
    return {
        'status': 'not_run', **data['run'],
        'modelled': len(forecasts), 'priced': sum(bool(row.get('odds')) for row in forecasts),
        'settled': len(settled), 'paired': len(paired),
        'first_paired_kickoff': starts[0] if starts else None,
        'last_paired_kickoff': starts[-1] if starts else None,
        'model_brier': model_brier / len(paired) if paired else None,
        'market_brier': market_brier / len(paired) if paired else None,
    }


def read_report(path=None):
    """Read paired scores and the last attempt; never open the provider."""
    return _report(_load(Path(path) if path is not None else _path(_utcnow())))


def _collect_league_prices(client, league, season, *, games, pending, run, clock):
    requested = clock()
    run['unpriced_pending'] = len(pending)
    eligible = {game.game_id: game for game in games
                if game.status == 'NS' and requested < game.starts_at <= requested + _ODDS_HORIZON}
    if not eligible:
        return {}, {}, requested

    run['price_checks'] = 1
    try:
        offers = client.league_prices(league, season, now=requested)
    except HandballSourceError as exc:
        return {exc.code: 1}, {}, requested
    fetched = clock()
    matched = {game_id: offer for game_id, offer in offers.items()
               if game_id in eligible and requested <= fetched < eligible[game_id].starts_at
               and offer.updated_at <= fetched and offer.bookmakers}
    run['quote_fixtures'] = len(matched)
    for game, row in pending:
        offer = matched.get(game.game_id)
        if offer is not None:
            row.update(odds=offer.bookmakers, price_source_at=offer.updated_at.isoformat(),
                       price_observed_at=fetched.isoformat())
            run['newly_priced'] += 1
            run['unpriced_pending'] -= 1
    if matched:
        diagnostics = ({'no_complete_1x2_for_pending': run['unpriced_pending']}
                       if run['unpriced_pending'] else {})
        return diagnostics, matched, fetched
    if fetched < requested or any(game_id in eligible and fetched >= eligible[game_id].starts_at
                                    for game_id in offers):
        return {'outside_prematch_window': 1}, {}, fetched
    return {'no_complete_1x2': 1}, {}, fetched


def run_pilot(client, *, path=None, clock=_utcnow, league=None, started=None):
    """One attempted collection per Zurich day; the worker owns a separate lock."""
    started = clock() if started is None else started
    path = prepare_trusted_runtime_database_path(Path(path) if path is not None else
                                                 _path(started, league.code if league else 'DE'))
    data = _load(path)
    day = started.astimezone(_ZONE).date().isoformat()
    if data['run'].get('day') == day:
        return _report(data)

    run = {'day': day, 'status': 'started', 'scheduled': 0, 'training_games': 0,
           'unconfirmed_finals': 0, 'changed_fixture': 0, 'result_revisions': 0,
           'price_checks': 0, 'quote_fixtures': 0, 'newly_priced': 0,
           'unpriced_pending': 0, 'diagnostics': {}}
    data['run'] = run
    if league is not None:
        data['publication'] = {'league_code': league.code, 'rows': {}}
    # A failed or interrupted run also spends part of the request budget.
    _write(path, data)
    try:
        season = _season(started)
        games = client.league_games(league, season) if league else client.bundesliga_games(season)
    except HandballSourceError as exc:
        run.update(status='unavailable', diagnostics={exc.code: 1})
        _write(path, data)
        return _report(data)

    now = clock()
    completed = [game for game in games if game.status == 'FT' and game.starts_at < now
                 and game.home_score is not None and game.away_score is not None]
    completed.sort(key=lambda game: (game.starts_at, game.game_id))
    final_ids = {game.game_id for game in completed}
    run['unconfirmed_finals'] = sum(game.status == 'FT' and game.game_id not in final_ids for game in games)
    history = [(game.home_id, game.away_id, game.home_score, game.away_score) for game in completed]
    forecasts = data['forecasts']
    for game in games:
        row = forecasts.get(str(game.game_id))
        if row is None:
            continue
        previous = row.get('result')
        same_fixture = row['fixture'] == _identity(game)
        if not same_fixture:
            run['changed_fixture'] += 1
        if same_fixture and game.game_id in final_ids:
            row['result'] = ('home' if game.home_score > game.away_score else
                             'away' if game.home_score < game.away_score else 'draw')
        else:
            row.pop('result', None)
        if previous is not None and previous != row.get('result'):
            run['result_revisions'] += 1

    upcoming = sorted((game for game in games if game.status == 'NS' and now < game.starts_at <= now + _HORIZON),
                      key=lambda game: (game.starts_at, game.game_id))
    run.update(scheduled=len(upcoming), training_games=len(history))
    pending = []
    for game in upcoming:
        key = str(game.game_id)
        if key not in forecasts:
            probability = predict_1x2(history, home_id=game.home_id, away_id=game.away_id)
            if probability is None:
                continue
            decided = clock()
            if not now <= decided < game.starts_at:
                continue
            forecasts[key] = {'fixture': _identity(game), 'p': probability, 'decided_at': decided.isoformat()}
        row = forecasts[key]
        if row['fixture'] == _identity(game) and 'result' not in row and not row.get('odds'):
            pending.append((game, row))
    # Persist the independent prediction before any offered price is known.
    _write(path, data)

    if league is not None:
        diagnostics, matches, fetched = _collect_league_prices(
            client, league, season, games=games, pending=pending, run=run, clock=clock,
        )
        data['publication'] = build_handball_publication(
            league, games=upcoming, forecasts=forecasts, markets=matches, observed_at=fetched,
        )
        run.update(status=('partial_prices' if diagnostics else 'completed') if games else 'empty_schedule',
                   diagnostics=diagnostics)
        _write(path, data)
        return _report(data)

    diagnostics = Counter()
    pending.sort(key=lambda pair: (bool(pair[1].get('last_price_attempt')), pair[0].starts_at))
    for game, row in pending[:_MAX_PRICE_CALLS]:
        requested = clock()
        if requested >= game.starts_at:
            continue
        row['last_price_attempt'] = requested.isoformat()
        run['price_checks'] += 1
        try:
            books = client.prices(game, now=requested)
        except HandballSourceError as exc:
            diagnostics[exc.code] += 1
            break  # provider failures should not consume the remaining allowance
        fetched = clock()
        if fetched >= game.starts_at or fetched < requested:
            diagnostics['outside_prematch_window'] += 1
        elif books:
            row.update(odds=books, price_observed_at=fetched.isoformat())
        else:
            diagnostics['no_complete_1x2'] += 1
    run.update(status=('partial_prices' if diagnostics else 'completed') if games else 'empty_schedule',
               diagnostics=dict(diagnostics))
    _write(path, data)
    return _report(data)


def read_europe_report(*, directory=None, now=None):
    """Read independent league evidence without API requests or file writes."""
    now = _utcnow() if now is None else now
    day = now.astimezone(_ZONE).date().isoformat()
    leagues = {league.code: read_report(_path(now, league.code, directory)) for league in HANDBALL_LEAGUES}
    today = [r['status'] for r in leagues.values() if r.get('day') == day]
    if not today:
        status = 'stale' if any(r.get('day') for r in leagues.values()) else 'not_run'
    elif len(today) == len(leagues) and len(set(today)) == 1 and today[0] in {'completed', 'unavailable'}:
        status = today[0]
    else:
        status = 'partial'
    return {'status': status, 'day': day, 'leagues': leagues}


def run_europe(client, *, directory=None, clock=_utcnow, started=None):
    """One catalogue, one schedule and at most one odds batch per league/day."""
    started = clock() if started is None else started
    existing = read_europe_report(directory=directory, now=started)
    # Each league stamps the date before its first provider request. Any current
    # stamp also guards the shared catalogue and all leagues after interruption.
    if any(r.get('day') == existing['day'] for r in existing['leagues'].values()):
        return existing
    # Rotate processing order so a provider-wide interruption cannot always
    # cost the same league its first daily attempt.
    offset = started.astimezone(_ZONE).date().toordinal() % len(HANDBALL_LEAGUES)
    rotation = HANDBALL_LEAGUES[offset:] + HANDBALL_LEAGUES[:offset]
    for league in rotation:
        report = run_pilot(client, league=league, path=_path(started, league.code, directory), clock=clock,
                           started=started)
        if _PROVIDER_STOP.intersection(report.get('diagnostics', {})):
            break
    return read_europe_report(directory=directory, now=started)


def scheduled_handball_pilot(*, canonical, forced):
    if not canonical or forced or os.getenv('BETBOY_HANDBALL_PILOT') != '1':
        return None
    if not load_handball_api_key():
        return {'status': 'missing_api_key'}
    try:
        worker = subprocess.run([sys.executable, '-m', 'handball_pilot', '--scheduled'], cwd=PROJECT_ROOT,
                                timeout=75, check=True, capture_output=True)
        return json.loads(worker.stdout)
    except subprocess.TimeoutExpired:
        return {'status': 'timed_out'}


def _scheduled_worker():
    if os.getenv('BETBOY_HANDBALL_PILOT') != '1':
        return {'status': 'disabled'}
    key = load_handball_api_key()
    if not key:
        return {'status': 'missing_api_key'}
    # Independent ownership: the core publication lock is already released.
    from wettfinder_automation import _quote_publication_lock

    now = _utcnow()
    path = prepare_trusted_runtime_database_path(_path(now))
    with _quote_publication_lock(path):
        return run_europe(APIHandballClient(key), started=now)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scheduled', action='store_true', help=argparse.SUPPRESS)
    print(json.dumps(_scheduled_worker() if parser.parse_args().scheduled else read_europe_report(), ensure_ascii=True))
