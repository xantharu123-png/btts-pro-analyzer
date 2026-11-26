"""Bounded, prospective football form-blend pairs from existing model and result calls.

Research only: neither arm changes served probabilities, and this module never
requests fixtures or changes the native settlement queue.
"""

from contextlib import closing
from datetime import datetime, timezone
from itertools import chain
from math import isclose
from pathlib import Path
import os
import sqlite3

from runtime_paths import (
    RuntimeArtifactTrustError,
    _assert_no_symlink_components,
    _validate_trusted_runtime_ancestor_chain,
    _validate_trusted_runtime_database_stat,
    prepare_trusted_runtime_database_path,
)


MAX_PAIRS = 65_536
_VERSION = 1
_APPLICATION_ID = 0x42424643
_SCOPES = frozenset({'same_competition', 'cross_competition_provisional_forecast',
                     'cross_competition_unvalidated'})
_MARKETS = {'1': (0,), 'X': (1,), '2': (2,), '1X': (0, 1), 'X2': (1, 2), '12': (0, 2)}
_IDENTITY_FIELDS = ('fixture_id', 'league_id', 'home_id', 'away_id', 'kickoff', 'captured_at',
                    'model_version', 'model_scope')
_FIELDS = {*_IDENTITY_FIELDS, 'with_form', 'without_form'}
_DDL = """
CREATE TABLE form_pairs (
    fixture_id INTEGER NOT NULL,
    league_id INTEGER NOT NULL,
    home_id INTEGER NOT NULL,
    away_id INTEGER NOT NULL,
    kickoff TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    model_version TEXT NOT NULL,
    model_scope TEXT NOT NULL,
    with_home REAL NOT NULL,
    with_draw REAL NOT NULL,
    with_away REAL NOT NULL,
    without_home REAL NOT NULL,
    without_draw REAL NOT NULL,
    without_away REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    goals_home INTEGER,
    goals_away INTEGER,
    observed_at TEXT,
    CHECK ((goals_home IS NULL AND goals_away IS NULL AND observed_at IS NULL) OR
           (goals_home IS NOT NULL AND goals_away IS NOT NULL AND observed_at IS NOT NULL)),
    PRIMARY KEY(fixture_id, kickoff, model_version, model_scope)
) WITHOUT ROWID
"""


def _clock(value):
    if isinstance(value, str) and 0 < len(value) <= 40:
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError('comparison needs an aware clock')
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')


def _integer(value, minimum=1):
    if type(value) is not int or not minimum <= value < 2**63:
        raise ValueError('invalid comparison identity or score')
    return value


def _probabilities(vector):
    if (not isinstance(vector, (tuple, list)) or len(vector) != 3
            or any(type(p) not in (int, float) or not 0 <= p <= 1 for p in vector)
            or not isclose(sum(vector), 1.0, rel_tol=0.0, abs_tol=1e-6)):
        raise ValueError('invalid comparison probabilities')
    return tuple(float(p) for p in vector)


def _pair(row, recorded_at):
    if not isinstance(row, dict) or set(row) != _FIELDS:
        raise ValueError('invalid comparison fields')
    fixture, league, home, away = (_integer(row[key]) for key in ('fixture_id', 'league_id', 'home_id', 'away_id'))
    kickoff, captured = _clock(row['kickoff']), _clock(row['captured_at'])
    version, scope = row['model_version'], row['model_scope']
    if (home == away or not captured <= recorded_at < kickoff
            or not isinstance(version, str) or not 0 < len(version) <= 160
            or not version.isascii() or not version.isprintable() or version.strip() != version
            or not isinstance(scope, str) or scope not in _SCOPES):
        raise ValueError('invalid comparison binding')
    return (fixture, league, home, away, kickoff, captured, version, scope,
            *_probabilities(row['with_form']), *_probabilities(row['without_form']), recorded_at)


def _path(path, *, create=False):
    path = (prepare_trusted_runtime_database_path(Path(path)) if create else
            _assert_no_symlink_components(Path(path)))
    _validate_trusted_runtime_ancestor_chain(path.parent)
    for suffix in ('', '-journal', '-wal', '-shm'):
        member = _assert_no_symlink_components(path.with_name(path.name + suffix))
        try:
            info = os.lstat(member)
        except FileNotFoundError:
            if not suffix and not create:
                return None
            continue
        _validate_trusted_runtime_database_stat(member, info)
        if info.st_nlink != 1:
            raise RuntimeArtifactTrustError('comparison database must be singly linked')
    return path


def _open(path, mode, *, timeout=2):
    conn = sqlite3.connect(f'{path.as_uri()}?mode={mode}', uri=True, timeout=timeout)
    try:
        conn.execute('PRAGMA trusted_schema=OFF')
        if mode == 'ro':
            conn.execute('PRAGMA query_only=ON')
        return conn
    except BaseException:
        conn.close()
        raise


def _check_schema(conn, *, create=False):
    version = conn.execute('PRAGMA user_version').fetchone()[0]
    application = conn.execute('PRAGMA application_id').fetchone()[0]
    if (version, application) == (_VERSION, _APPLICATION_ID):
        rows = conn.execute('SELECT type,name,sql FROM sqlite_master LIMIT 2').fetchall()
        if (len(rows) == 1 and rows[0][:2] == ('table', 'form_pairs')
                and isinstance(rows[0][2], str) and rows[0][2].split() == _DDL.split()):
            return
    if create and version == application == 0 and conn.execute('SELECT 1 FROM sqlite_master LIMIT 1').fetchone() is None:
        conn.execute(_DDL)
        conn.execute(f'PRAGMA application_id={_APPLICATION_ID}')
        conn.execute(f'PRAGMA user_version={_VERSION}')
        return
    raise ValueError('unrecognized football form comparison schema')


def append_pairs(path, pairs, *, recorded_at):
    """Record the first valid pair per fixture, kickoff, model version and scope."""
    report = dict(inserted=0, duplicates=0, conflicts=0, rejected=0, capacity_skipped=0)
    clock = _clock(recorded_at)

    def checked():
        for row in pairs:
            try:
                yield _pair(row, clock)
            except (ValueError, OverflowError):
                report['rejected'] += 1

    rows = checked()
    first = next(rows, None)
    if first is None:
        return report
    with closing(_open(_path(path, create=True), 'rwc')) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        _check_schema(conn, create=True)
        stored = conn.execute('SELECT count(*) FROM form_pairs').fetchone()[0]
        for row in chain((first,), rows):
            previous = conn.execute('SELECT * FROM form_pairs WHERE fixture_id=? AND kickoff=?',
                                    (row[0], row[4])).fetchall()
            if any(old[1:4] != row[1:4] for old in previous):
                report['conflicts'] += 1
                continue
            old = next((old for old in previous if old[6:8] == row[6:8]), None)
            if old is not None:
                report['duplicates' if old[:14] == row[:14] else 'conflicts'] += 1
            elif stored >= MAX_PAIRS:
                report['capacity_skipped'] += 1
            else:
                conn.execute('INSERT INTO form_pairs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)', row)
                stored += 1
                report['inserted'] += 1
    return report


def _goals(value):
    return _integer(value['home'], 0), _integer(value['away'], 0)


def _final(fixture, observed_at):
    native = fixture['fixture']
    kickoff, observed = _clock(native['date']), _clock(observed_at)
    if 'timestamp' in native and _clock(datetime.fromtimestamp(_integer(native['timestamp']), timezone.utc)) != kickoff:
        raise ValueError('conflicting native result kickoff')
    teams = fixture['teams']
    home, away = _integer(teams['home']['id']), _integer(teams['away']['id'])
    if native['status']['short'] != 'FT' or kickoff >= observed or home == away:
        raise ValueError('invalid regulation result')
    goals = _goals(fixture['goals'])
    score = fixture.get('score', {})
    if not isinstance(score, dict) or ('fulltime' in score and _goals(score['fulltime']) != goals):
        raise ValueError('conflicting regulation score')
    for phase in ('extratime', 'penalty'):
        counts = score.get(phase)
        if counts is not None and (not isinstance(counts, dict)
                                   or any(counts.get(side) is not None for side in ('home', 'away'))):
            raise ValueError('nonregulation scores on FT result')
    return (*goals, observed, _integer(native['id']), kickoff, _integer(fixture['league']['id']), home, away)


def settle_pairs(path, fixture, *, observed_at):
    """Reuse the native FT envelope; never start, expand or retry a result fetch."""
    path = _path(path)
    if path is None:
        return {'status': 'missing', 'settled': 0}
    try:
        values = _final(fixture, observed_at)
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, OSError):
        return {'status': 'invalid_result', 'settled': 0}
    where = 'fixture_id=? AND kickoff=? AND league_id=? AND home_id=? AND away_id=?'
    # Do not wait on a diagnostic lock inside the primary settlement loop.
    with closing(_open(path, 'rw', timeout=0)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        _check_schema(conn)
        previous = conn.execute(f'SELECT goals_home, goals_away FROM form_pairs WHERE {where}', values[3:]).fetchall()
        if not previous:
            return {'status': 'unmatched', 'settled': 0}
        if any(goals != (None, None) and goals != values[:2] for goals in previous):
            return {'status': 'conflict', 'settled': 0}
        updated = conn.execute(f'UPDATE form_pairs SET goals_home=?, goals_away=?, observed_at=? '
                               f'WHERE {where} AND observed_at IS NULL', values).rowcount
        return {'status': 'settled' if updated else 'unchanged', 'settled': updated}


def _group(league, version, scope):
    return dict(league_id=league, model_version=version, model_scope=scope, stored=0, settled=0, open=0,
                brier_1x2={'with_form': 0.0, 'without_form': 0.0},
                markets={name: dict(hits=0, with_form_expected=0.0, without_form_expected=0.0,
                                    with_form_brier=0.0, without_form_brier=0.0) for name in _MARKETS})


def _verify_stored_row(row):
    pair = dict(zip(_IDENTITY_FIELDS, row[:8]), with_form=row[8:11], without_form=row[11:14])
    if _pair(pair, _clock(row[14])) != row[:15]:
        raise ValueError('noncanonical stored football form comparison')
    home, away, observed = row[15:18]
    if observed is not None:
        if _clock(observed) != observed or observed <= row[4]:
            raise ValueError('invalid comparison result clock')
        _integer(home, 0)
        _integer(away, 0)
    elif home is not None or away is not None:
        raise ValueError('comparison result clock is missing')


def _score_group(group, with_form, without_form, result):
    group['settled'] += 1
    for arm, probabilities in (('with_form', with_form), ('without_form', without_form)):
        group['brier_1x2'][arm] += sum((p - (side == result)) ** 2 for side, p in enumerate(probabilities))
        for name, sides in _MARKETS.items():
            market = group['markets'][name]
            predicted = sum(probabilities[i] for i in sides)
            hit = result in sides
            market[f'{arm}_expected'] += predicted
            market[f'{arm}_brier'] += (predicted - hit) ** 2
            if arm == 'with_form':
                market['hits'] += hit


def league_report(path):
    """Score the same completed games on both arms; open games enter neither score."""
    report = dict(status='missing', stored=0, settled=0, open=0, groups=[])
    path = _path(path)
    if path is None:
        return report
    report['status'] = 'present'
    groups = {}
    with closing(_open(path, 'ro')) as conn:
        conn.execute('BEGIN')
        _check_schema(conn)
        for row in conn.execute('SELECT * FROM form_pairs ORDER BY fixture_id,kickoff,model_version,model_scope '
                                'LIMIT ?', (MAX_PAIRS + 1,)):
            report['stored'] += 1
            if report['stored'] > MAX_PAIRS:
                raise ValueError('football form comparison exceeds row limit')
            _verify_stored_row(row)
            group_key = row[1], row[6], row[7]
            if group_key not in groups:
                groups[group_key] = _group(*group_key)
            group = groups[group_key]
            group['stored'] += 1
            if row[17] is None:
                group['open'] += 1
                report['open'] += 1
                continue
            home, away = row[15:17]
            result = 0 if home > away else 1 if home == away else 2
            _score_group(group, row[8:11], row[11:14], result)
            report['settled'] += 1
    for group_key in sorted(groups):
        group = groups[group_key]
        n = group['settled']
        for arm in ('with_form', 'without_form'):
            group['brier_1x2'][arm] = group['brier_1x2'][arm] / n if n else None
            for market in group['markets'].values():
                key = f'{arm}_brier'
                market[key] = market[key] / n if n else None
        report['groups'].append(group)
    return report
