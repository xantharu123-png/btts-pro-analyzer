"""One bounded detail batch for observed completed games missing player data.

The ordinary league result list has no player minutes. Waiting for unsettled
recommendations to request details misses most of that history. This worker
reuses its secured native result archive to select at most twenty IDs, makes
one BACKGROUND request, and preserves the actual new reception. It neither
backdates training evidence nor estimates or activates a player effect.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest, require_digest
from context_models.dataset import _reader
from context_observations import _SELECT, _decode_receipt
from context_sources.football_capture import capture_football_worker
from context_sources.outcomes import validate_football_base_input
from runtime_paths import atomic_write_bytes


MAX_FIXTURES = 20
DETAIL_RECHECK = timedelta(days=1)
ROTATION_SECONDS = 30 * 60


def _identity(detail):
    """Bind an enrichment attempt to the exact native result revision."""
    return (detail['fixture']['id'], canonical_timestamp(detail['fixture']['date']),
        detail['league']['id'], detail['league']['season'],
        detail['teams']['home']['id'], detail['teams']['away']['id'],
        detail['fixture']['status']['short'], detail['goals']['home'], detail['goals']['away'])


def _pending_identities(path: Path, *, now: datetime):
    """Selected source rows are fully validated; this is not a full DB audit.

    Missing/altered lookup indexes cannot certify coverage or a model here.
    Every actual request still needs an owning, hash-validated native receipt.
    The read transaction closes BEFORE any network request or publication.
    """
    decision = canonical_timestamp(now)
    path = Path(path)
    if not os.path.lexists(path):
        return ()
    latest, details = {}, {}
    with _reader(path) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('context_observations','context_contents')")}
        if not tables:
            return ()
        if tables != {'context_observations', 'context_contents'}:
            raise ContextIntegrityError('incomplete context observation tables')
        for stored in connection.execute(_SELECT +
                " WHERE r.source='api-football' AND r.kind='base_fixture'"):
            row = _decode_receipt(stored)
            if row['observed_at'] > decision:
                continue
            row.update(evidence_class='prospective', effective_at=row['observed_at'], publication_resolution=None)
            try:
                validate_football_base_input(row)
            except ContextContractError as exc:
                raise ContextIntegrityError('invalid native appearance source receipt') from exc
            raw = row['payload']['detail']
            key, clock = row['event_key'], row['observed_at']
            identity = _identity(raw)
            previous = latest.get(key)
            if previous is None or clock > previous[0]:
                latest[key] = (clock, {identity})
            elif clock == previous[0]:
                previous[1].add(identity)
            if 'players' in raw:
                details[identity] = max(details.get(identity, clock), clock)
    cutoff = canonical_timestamp(datetime.fromisoformat(decision) - DETAIL_RECHECK)
    pending = []
    for _, identities in latest.values():
        if len(identities) != 1:
            continue  # Unresolved concurrent native identities are not a fetch plan.
        identity = next(iter(identities))
        if identity[6] != 'FT' or identity[1] >= decision:
            continue
        if details.get(identity, '') > cutoff:
            continue  # Empty supplied players are a checked gap, not a healthy squad.
        pending.append(identity)
    pending.sort(key=lambda item: (item[1], item[0]))
    return pending


def _attempt_state_path(path):
    return Path(path).with_name(Path(path).name + '.football-appearance-attempts.json')


def _attempt_key(identity):
    return digest(list(identity))


def _recent_attempts(path, *, now):
    """Internal scheduling only: never a source receipt or coverage claim."""
    if not os.path.lexists(path):
        return {}
    from runtime_paths import open_trusted_pickle
    # The existing regular-file/owner/no-symlink reader is format independent;
    # JSON bytes below are never deserialized as executable pickle input.
    with open_trusted_pickle(path) as stream:
        raw = stream.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ContextIntegrityError('appearance attempt state exceeds its bound')
    try:
        state = json.loads(raw)
        if (type(state) is not dict or set(state) != {'schema', 'purpose', 'reservations'}
                or type(state['schema']) is not int or state['schema'] != 1
                or state['purpose'] != 'football-appearance-request-reservations'
                or type(state['reservations']) is not dict):
            raise ValueError('invalid attempt state')
        cutoff = canonical_timestamp(now - DETAIL_RECHECK)
        recent = {}
        for key, clock in state['reservations'].items():
            require_digest(key, 'attempt identity')
            if type(clock) is not str or canonical_timestamp(clock) != clock:
                raise ValueError('invalid attempt clock')
            # A worker with an older entry clock may reach the lock after a
            # newer worker. Its reservation is not expired (nor source data).
            if cutoff < clock:
                recent[key] = clock
        return recent
    except (ValueError, TypeError, OverflowError, KeyError) as exc:
        raise ContextIntegrityError('invalid appearance request reservation state') from exc


def _choose(pending, attempts, *, now, limit):
    if type(limit) is not int or not 1 <= limit <= MAX_FIXTURES:
        raise ValueError('appearance batch limit must be an integer from 1 to 20')
    pending = [item for item in pending if _attempt_key(item) not in attempts]
    if len(pending) > limit:
        offset = (int(now.timestamp()) // ROTATION_SECONDS * limit) % len(pending)
        pending = [pending[(offset + index) % len(pending)] for index in range(limit)]
    return pending


def pending_appearance_ids(path: Path, *, now: datetime, limit: int = MAX_FIXTURES) -> tuple[int, ...]:
    _choose([], {}, now=now, limit=limit)
    pending = _pending_identities(path, now=now)
    chosen = _choose(pending, _recent_attempts(_attempt_state_path(path), now=now), now=now, limit=limit)
    return tuple(sorted(item[0] for item in chosen))


def refresh_football_appearances(provider, *, path: Path | None = None,
                               now: datetime | None = None, limit: int = MAX_FIXTURES) -> dict:
    """No fallback fan-out, no extra timer, no database read during the GET."""
    if path is None:
        from runtime_paths import CONTEXT_MODEL_DB_PATH
        path = CONTEXT_MODEL_DB_PATH
    now = now or datetime.now(timezone.utc)
    _choose([], {}, now=now, limit=limit)
    pending = _pending_identities(path, now=now)
    report = {'schema': 1, 'scope': 'observed-football-result-player-details',
              'status': 'no_request_due', 'requested_count': 0, 'capture': None,
              'player_fixture_count': 0, 'player_record_count': 0}
    if not pending:
        return report
    from context_snapshots import _compute_lock
    # Reserve BEFORE networking, while holding only a short local file lock.
    # A crash, empty reply, malformed body or HTTP error still backs off; no
    # fake provider receipt is appended, and concurrent workers cannot retry.
    with _compute_lock(_attempt_state_path(path)) as (attempt_path, check):
        attempts = _recent_attempts(attempt_path, now=now)
        chosen = _choose(pending, attempts, now=now, limit=limit)
        if not chosen:
            return report
        for item in chosen:
            attempts[_attempt_key(item)] = canonical_timestamp(now)
        check()
        atomic_write_bytes(attempt_path, json.dumps({'schema': 1,
            'purpose': 'football-appearance-request-reservations',
            'reservations': attempts}, sort_keys=True).encode('utf-8'))
    ids = tuple(sorted(item[0] for item in chosen))
    report['requested_count'] = len(ids)
    with capture_football_worker(provider, path=path) as capture:
        response = provider._background_football_get('fixtures',
            {'ids': '-'.join(str(value) for value in ids)}, 'Kontext Einsatzhistorie')
    report['capture'] = capture.report()
    if report['capture']['status'] == 'captured':
        from context_sources.football import _detail_event, normalize_football_context
        with_minutes = set()
        for receipt in capture.receipts:
            for raw in receipt['rows']:
                rows = normalize_football_context(_detail_event(raw), injuries=[], lineups=[],
                    appearances=[raw], observed_at=datetime.fromisoformat(receipt['observed_at']))
                players = [row for row in rows if row['kind'] == 'appearance'
                    and row['subject_id'].startswith('api-football:player:')]
                report['player_record_count'] += len(players)
                if any(row['payload']['minutes'] is not None for row in players):
                    with_minutes.add(raw['fixture']['id'])
        report['player_fixture_count'] = len(with_minutes)
    report['status'] = ('unavailable' if response is None else
        'player_data_captured' if report['player_fixture_count'] == len(ids) else 'partial')
    return report
