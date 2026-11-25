"""Internal European handball 1X2 pilot; default CLI is read-only."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from math import isclose, isfinite
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from config_loader import load_handball_api_key
from handball_market_review import review_handball_market
from handball_pilot_model import predict_1x2
from handball_publication import build_handball_publication
from runtime_paths import PROJECT_ROOT, RUNTIME_STATE_DIR, atomic_write_text, prepare_trusted_runtime_database_path
from scanners.api_handball import APIHandballClient, HANDBALL_LEAGUES, MAX_PRICE_AGE, HandballSourceError


_ZONE = ZoneInfo('Europe/Zurich')
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


def _finite_float(raw):
    value = float(raw)
    if not isfinite(value):
        raise ValueError('nonfinite_handball_state')
    return value


def _aware_clock(raw):
    if not isinstance(raw, str):
        raise ValueError('invalid_handball_clock')
    value = datetime.fromisoformat(raw)
    if value.utcoffset() is None:
        raise ValueError('invalid_handball_clock')
    return value


def _load(path):
    if not path.exists():
        return {'version': 2, 'forecasts': {}, 'run': {}}
    data = json.loads(path.read_text(encoding='utf-8'), parse_float=_finite_float, parse_constant=_finite_float)
    if (not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] not in {1, 2, 3}
            or not isinstance(data.get('forecasts'), dict) or not isinstance(data.get('run'), dict)):
        raise ValueError('unknown_handball_pilot_state')
    run = data['run']
    if (('status' in run and not isinstance(run['status'], str))
            or ('day' in run and (not isinstance(run['day'], str)
                                 or date.fromisoformat(run['day']).isoformat() != run['day']))
            or ('diagnostics' in run and not isinstance(run['diagnostics'], dict))):
        raise ValueError('invalid_handball_run')
    for row in data['forecasts'].values():
        if not isinstance(row, dict):
            raise ValueError('invalid_handball_forecast')
        fixture = row.get('fixture')
        p = row.get('p')
        if (not isinstance(fixture, list) or len(fixture) != 5
                or any(type(value) is not int or not 0 < value < 2**63 for value in fixture[:4])
                or fixture[2] == fixture[3] or not isinstance(p, dict) or p.keys() != {'home', 'draw', 'away'}
                or any(type(v) not in (int, float) or not 0 <= v <= 1 for v in p.values())
                or not isclose(sum(p.values()), 1., rel_tol=0., abs_tol=1e-6)):
            raise ValueError('invalid_handball_forecast')
        decided = _aware_clock(row.get('decided_at'))
        if decided >= _aware_clock(fixture[4]):
            raise ValueError('invalid_handball_decision_clock')
        if 'price_source_at' in row:
            source = _aware_clock(row['price_source_at'])
            observed = _aware_clock(row.get('price_observed_at'))
            if source > observed:
                raise ValueError('invalid_handball_price_clock')
        if 'revision_confirmed_at' in row and _aware_clock(row['revision_confirmed_at']) > decided:
            raise ValueError('invalid_handball_revision_clock')
    if 'fixture_revisions' in data:
        archive = data['fixture_revisions']
        if (not isinstance(archive, dict) or type(archive.get('version')) is not int or archive['version'] != 1
                or not isinstance(archive.get('history'), dict)
                or not isinstance(archive.get('schedule', {}), dict)
                or any(not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                       for rows in archive['history'].values())):
            raise ValueError('invalid_handball_fixture_revisions')
        for change in archive.get('schedule', {}).values():
            if (not isinstance(change, dict) or not isinstance(change.get('fixture'), list)
                    or len(change['fixture']) != 5):
                raise ValueError('invalid_handball_revision_schedule')
            _aware_clock(change.get('confirmed_at'))
    return data


def _write(path, data):
    data['version'] = 3 if 'publication' in data else 2
    atomic_write_text(path, json.dumps(data, allow_nan=False, sort_keys=True))


def _identity(game):
    return [game.league_id, game.season, game.home_id, game.away_id, game.starts_at.isoformat()]


def _note_revised_schedule(data, game, observed):
    if game.status != 'NS':
        return
    archive = data.get('fixture_revisions', {})
    key = str(game.game_id)
    if key not in archive.get('history', {}):
        return
    schedule = archive.setdefault('schedule', {})
    revised = _identity(game)
    if schedule.get(key, {}).get('fixture') != revised:
        schedule[key] = {'fixture': revised, 'confirmed_at': observed.isoformat()}


def _report(data):
    forecasts = data['forecasts'].values()
    return {
        'status': 'not_run', **data['run'],
        'modelled': len(forecasts), 'priced': sum(bool(row.get('odds')) for row in forecasts),
        'superseded': sum(map(len, data.get('fixture_revisions', {}).get('history', {}).values())),
        'settled': sum('result' in row for row in forecasts),
        **review_handball_market(forecasts),
    }


def read_report(path=None):
    """Read paired scores and the last attempt; never open the provider."""
    return _report(_load(Path(path) if path is not None else _path(_utcnow())))


def _collect_league_prices(client, league, season, *, games, forecasts, pending, run, clock):
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
               and fetched - MAX_PRICE_AGE < offer.updated_at <= fetched and offer.bookmakers}
    before_revision = set()
    for game_id, offer in matched.items():
        confirmed = forecasts.get(str(game_id), {}).get('revision_confirmed_at')
        if confirmed is not None and offer.updated_at < datetime.fromisoformat(confirmed):
            before_revision.add(game_id)
    for game_id in before_revision:
        matched.pop(game_id)
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
        if before_revision:
            diagnostics['price_predates_revision'] = len(before_revision)
        return diagnostics, matched, fetched
    if before_revision:
        return {'price_predates_revision': len(before_revision)}, {}, fetched
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
    if league is not None:
        # Store a compact, replaceable input from this existing request, not whole provider replies.
        data['study_input'] = {'version': 1, 'observed_at': now.isoformat(), 'games': [
            [game.game_id, game.starts_at.isoformat(), game.home_id, game.away_id, game.home_score, game.away_score]
            for game in completed
        ]}
    forecasts = data['forecasts']
    for game in games:
        key = str(game.game_id)
        row = forecasts.get(key)
        if row is None:
            _note_revised_schedule(data, game, now)
            continue
        previous = row.get('result')
        if row['fixture'] != _identity(game):
            archive = data.setdefault('fixture_revisions', {'version': 1, 'history': {}})['history']
            archive.setdefault(key, []).append(forecasts.pop(key))
            _note_revised_schedule(data, game, now)
            run['changed_fixture'] += 1
            run['result_revisions'] += int(previous is not None)
            continue
        if game.game_id in final_ids:
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
            changed = data.get('fixture_revisions', {}).get('schedule', {}).get(key, {})
            if changed.get('fixture') == _identity(game):
                forecasts[key]['revision_confirmed_at'] = changed['confirmed_at']
        row = forecasts[key]
        if row['fixture'] == _identity(game) and 'result' not in row and not row.get('odds'):
            pending.append((game, row))
    # Persist the independent prediction before any offered price is known.
    _write(path, data)

    if league is not None:
        diagnostics, matches, fetched = _collect_league_prices(
            client, league, season, games=games, forecasts=forecasts, pending=pending, run=run, clock=clock,
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
        if 'revision_confirmed_at' in row:
            continue  # Legacy offers have no provider clock to bind to the new schedule.
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
    leagues = {}
    for league in HANDBALL_LEAGUES:
        try:
            leagues[league.code] = read_report(_path(now, league.code, directory))
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            leagues[league.code] = {'status': 'local_state_invalid', 'diagnostics': {'local_state_invalid': 1}}
    today = [r['status'] for r in leagues.values() if r.get('day') == day]
    invalid = sum(r['status'] == 'local_state_invalid' for r in leagues.values())
    if invalid:
        status = 'unavailable' if invalid == len(leagues) else 'partial'
    elif not today:
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
        if existing['leagues'][league.code]['status'] == 'local_state_invalid':
            continue  # Never reconstruct or overwrite a damaged league ledger.
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
        return run_europe(APIHandballClient(key, clock=_utcnow), started=now)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scheduled', action='store_true', help=argparse.SUPPRESS)
    print(json.dumps(_scheduled_worker() if parser.parse_args().scheduled else read_europe_report(), ensure_ascii=True))
