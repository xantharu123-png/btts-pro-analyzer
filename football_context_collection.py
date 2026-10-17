"""Bounded admission for existing same-call football ORIGINAL collection.

This records evidence, not a new prediction or an approved effect. Reserve
before work; do not refund failed/crashed attempts. Limits count new JSON
payload bytes, not total SQLite size. Only the canonical worker calls this.
"""
from datetime import date, datetime, timezone
from pathlib import Path
import shutil
import hashlib
import sqlite3
from uuid import uuid4

from context_models.contracts import ContextIntegrityError
from context_snapshots import _compute_lock
from model_artifacts import _decode_object, canonical_bytes
from runtime_paths import atomic_write_bytes, open_trusted_pickle

SCHEMA = 'football-original-admission-v1'
SESSION_BYTES = 4 * 1024 * 1024
DAILY_BYTES = 8 * 1024 * 1024
TOTAL_BYTES = 128 * 1024 * 1024
MIN_FREE_BYTES = 512 * 1024 * 1024
LIMITS = {'max_publication_payload_bytes': 1024 * 1024,
          'max_worker_payload_bytes': 3 * 1024 * 1024,
          'max_source_payload_bytes': 1024 * 1024}


def reserve_original_capture(path: Path, *, now: datetime) -> dict:
    """One finite worker permit, no quota reset on crashes or clock reversal."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('original collection requires an aware clock')
    today = now.astimezone(timezone.utc).date().isoformat()
    with _compute_lock(Path(path)) as (target, check):
        if target.exists():
            with open_trusted_pickle(target) as stream:
                raw = stream.read(4097)
            if len(raw) > 4096:
                raise ContextIntegrityError('original collection admission state is oversized')
            state = _decode_object(raw, label='original collection admission')
            if (set(state) != {'schema', 'day', 'daily_reserved', 'total_reserved'}
                    or state['schema'] != SCHEMA or type(state['day']) is not str):
                raise ContextIntegrityError('invalid original collection admission state')
            try:
                if date.fromisoformat(state['day']).isoformat() != state['day']:
                    raise ValueError('noncanonical date')
            except ValueError as exc:
                raise ContextIntegrityError('invalid original collection admission date') from exc
            for key, maximum in (('daily_reserved', DAILY_BYTES), ('total_reserved', TOTAL_BYTES)):
                value = state[key]
                if type(value) is not int or not 0 <= value <= maximum or value % SESSION_BYTES:
                    raise ContextIntegrityError('invalid original collection admission counter')
            if state['daily_reserved'] > state['total_reserved']:
                raise ContextIntegrityError('inconsistent original collection admission counters')
        else:
            state = dict(schema=SCHEMA, day=today, daily_reserved=0, total_reserved=0)
        status = None
        if today < state['day']:
            status = 'clock_before_reservation'
        elif state['total_reserved'] + SESSION_BYTES > TOTAL_BYTES:
            status = 'total_limit'
        elif today == state['day'] and state['daily_reserved'] + SESSION_BYTES > DAILY_BYTES:
            status = 'daily_limit'
        elif shutil.disk_usage(target.parent).free < MIN_FREE_BYTES:
            status = 'storage_reserve'
        if status:
            return {'schema': SCHEMA, 'status': status, 'limits': None}
        if today != state['day']:
            state.update(day=today, daily_reserved=0)
        state['daily_reserved'] += SESSION_BYTES
        state['total_reserved'] += SESSION_BYTES
        check()
        atomic_write_bytes(target, canonical_bytes(state))
        return {'schema': SCHEMA, 'status': 'reserved', 'limits': dict(LIMITS)}


# A different, explicit accounting contract, NOT a refund/reset of v1. Counts
# existing football artifacts plus new committed artifact/source payloads from
# this owner. Pre-existing generic source history and total SQLite file size
# are outside these units. Outstanding/crashed attempts still cost all 4 MiB.
METERED_SCHEMA = 'football-original-committed-admission-v2'
METERED_STATE_BYTES = 64 * 1024
COMPLETED_RECEIPTS = 128


def _day(value):
    if type(value) is not str or date.fromisoformat(value).isoformat() != value:
        raise ContextIntegrityError('invalid metered capture date')
    return value


def _today(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('original collection requires an aware clock')
    return now.astimezone(timezone.utc).date().isoformat()


def _token(value):
    if type(value) is not str or len(value) != 32 or any(x not in '0123456789abcdef' for x in value):
        raise ContextIntegrityError('invalid metered capture reservation')


def _legacy_link(path):
    if not Path(path).exists():
        return None, None
    with open_trusted_pickle(Path(path)) as stream:
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise ContextIntegrityError('legacy capture ledger is oversized')
    obj = _decode_object(raw, label='legacy capture ledger')
    if (set(obj) != {'schema', 'day', 'daily_reserved', 'total_reserved'}
            or obj['schema'] != SCHEMA):
        raise ContextIntegrityError('invalid legacy capture ledger')
    _day(obj['day'])
    for key, cap in (('daily_reserved', DAILY_BYTES), ('total_reserved', TOTAL_BYTES)):
        if type(obj[key]) is not int or not 0 <= obj[key] <= cap or obj[key] % SESSION_BYTES:
            raise ContextIntegrityError('invalid legacy capture counter')
    if obj['daily_reserved'] > obj['total_reserved']:
        raise ContextIntegrityError('inconsistent legacy capture counters')
    return hashlib.sha256(raw).hexdigest(), obj['day']


def _owned_payload_bytes(path):
    """Scalar read only: never load/copy blobs or initialize a runtime store."""
    path = Path(path)
    if not path.exists():
        return 0
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='artifacts'").fetchone():
            return 0
        return int(connection.execute(
            "SELECT COALESCE(SUM(length(payload)), 0) FROM artifacts WHERE substr(kind,1,9)='football-'"
        ).fetchone()[0])
    finally:
        connection.close()


def _read_metered(target):
    with open_trusted_pickle(target) as stream:
        raw = stream.read(METERED_STATE_BYTES + 1)
    if len(raw) > METERED_STATE_BYTES:
        raise ContextIntegrityError('metered capture ledger is oversized')
    state = _decode_object(raw, label='metered capture ledger')
    if (set(state) != {'schema', 'legacy_digest', 'day', 'total_committed',
                       'daily_committed', 'pending', 'completed'}
            or state['schema'] != METERED_SCHEMA):
        raise ContextIntegrityError('invalid metered capture ledger')
    link = state['legacy_digest']
    if link is not None and (type(link) is not str or len(link) != 64
                            or any(x not in '0123456789abcdef' for x in link)):
        raise ContextIntegrityError('invalid legacy capture linkage')
    _day(state['day'])
    for key, cap in (('total_committed', TOTAL_BYTES), ('daily_committed', DAILY_BYTES)):
        if type(state[key]) is not int or not 0 <= state[key] <= cap:
            raise ContextIntegrityError('invalid metered capture counter')
    if type(state['pending']) is not dict or type(state['completed']) is not dict:
        raise ContextIntegrityError('invalid metered capture receipts')
    if len(state['pending']) > TOTAL_BYTES // SESSION_BYTES or len(state['completed']) > COMPLETED_RECEIPTS:
        raise ContextIntegrityError('too many metered capture receipts')
    if set(state['pending']) & set(state['completed']):
        raise ContextIntegrityError('duplicate metered capture receipt')
    for token, day in state['pending'].items():
        _token(token)
        if _day(day) > state['day']:
            raise ContextIntegrityError('future metered capture reservation')
    for token, usage in state['completed'].items():
        _token(token)
        if type(usage) is not list or len(usage) != 2:
            raise ContextIntegrityError('invalid completed capture receipt')
        _usage(dict(zip(('inserted_payload_bytes', 'source_inserted_payload_bytes'), usage)))
    if (state['total_committed'] + SESSION_BYTES * len(state['pending']) > TOTAL_BYTES
            or state['daily_committed'] > state['total_committed']
            or state['daily_committed'] + SESSION_BYTES * sum(
                day == state['day'] for day in state['pending'].values()) > DAILY_BYTES):
        raise ContextIntegrityError('inconsistent metered capture totals')
    return state


def _usage(usage):
    keys = ('inserted_payload_bytes', 'source_inserted_payload_bytes')
    if type(usage) is not dict or set(usage) != set(keys):
        raise ContextIntegrityError('invalid committed capture usage')
    result = [usage[key] for key in keys]
    for value, cap in zip(result, (LIMITS['max_worker_payload_bytes'], LIMITS['max_source_payload_bytes'])):
        if type(value) is not int or not 0 <= value <= cap:
            raise ContextIntegrityError('invalid committed capture bytes')
    return result


def reserve_metered_capture(path, *, model_path, legacy_path, now):
    """v2 permit: completed actual usage, full conservative crash reservations."""
    today = _today(now)
    with _compute_lock(Path(path)) as (target, check):
        link, legacy_day = _legacy_link(legacy_path)
        state = (_read_metered(target) if target.exists() else dict(
            schema=METERED_SCHEMA, legacy_digest=link, day=today,
            total_committed=0, daily_committed=0, pending={}, completed={}))
        if state['legacy_digest'] != link:
            raise ContextIntegrityError('legacy capture ledger changed after v2 admission')
        owned_bytes = _owned_payload_bytes(model_path)
        # The floor cannot shrink after external deletion. Concurrent physical
        # writes can only overcharge this conservative reconciliation.
        committed = max(state['total_committed'], owned_bytes)
        daily = state['daily_committed'] if today == state['day'] else 0
        status = None
        if today < state['day'] or legacy_day is not None and today < legacy_day:
            status = 'clock_before_reservation'
        elif committed + SESSION_BYTES * (len(state['pending']) + 1) > TOTAL_BYTES:
            status = 'total_limit'
        elif daily + SESSION_BYTES * (1 + sum(day == today for day in state['pending'].values())) > DAILY_BYTES:
            status = 'daily_limit'
        elif shutil.disk_usage(target.parent).free < MIN_FREE_BYTES:
            status = 'storage_reserve'
        if status:
            return dict(schema=METERED_SCHEMA, status=status, limits=None)
        token = uuid4().hex
        state.update(day=today, daily_committed=daily, total_committed=committed)
        state['pending'][token] = today
        check()
        atomic_write_bytes(target, canonical_bytes(state))
        return dict(schema=METERED_SCHEMA, status='reserved', limits=dict(LIMITS), reservation_id=token)


def finish_metered_capture(path, reservation_id, *, usage, now):
    """Only a known successful invocation can release its unused reservation."""
    today, pair = _today(now), _usage(usage)
    _token(reservation_id)
    with _compute_lock(Path(path)) as (target, check):
        if not target.exists():
            raise ContextIntegrityError('missing metered capture ledger')
        state = _read_metered(target)
        previous = state['completed'].get(reservation_id)
        if previous is not None:
            if previous != pair:
                raise ContextIntegrityError('conflicting completed capture usage')
            return dict(schema=METERED_SCHEMA, status='completed', charged_bytes=sum(pair))
        admitted = state['pending'].get(reservation_id)
        if admitted is None or today < max(admitted, state['day']):
            raise ContextIntegrityError('unknown or future metered capture reservation')
        del state['pending'][reservation_id]
        state['total_committed'] += sum(pair)
        if admitted == state['day']:
            state['daily_committed'] += sum(pair)
        state['completed'][reservation_id] = pair
        # Canonical serialization sorts keys; bounded history need not be LRU.
        while len(state['completed']) > COMPLETED_RECEIPTS:
            del state['completed'][next(key for key in state['completed'] if key != reservation_id)]
        check()
        atomic_write_bytes(target, canonical_bytes(state))
        return dict(schema=METERED_SCHEMA, status='completed', charged_bytes=sum(pair))
