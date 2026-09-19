"""Bounded admission for existing same-call football ORIGINAL collection.

This records evidence, not a new prediction or an approved effect. Reserve
before work; do not refund failed/crashed attempts. Limits count new JSON
payload bytes, not total SQLite size. Only the canonical worker calls this.
"""
from datetime import date, datetime, timezone
from pathlib import Path
import shutil

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
