"""Exact event ambiguity guard for a Daily3 slot, not a fuzzy fixture merge."""
import hashlib
import json
import re

from daily3_math import Daily3Error
from selection_coherence import consumer_event_identity, _exact_event_signatures

_HASH = re.compile(r'[0-9a-f]{64}\Z', re.ASCII)


def event_guard(signal):
    # Use the same role/time/name normalization as the ordinary coherent view.
    # Keep all exact aliases in the immutable receipt so a later native-ID or
    # provider upgrade cannot offer that already occupied event as a new slot.
    aliases = sorted({hashlib.sha256(json.dumps(signature, ensure_ascii=True,
        separators=(',', ':')).encode('ascii')).hexdigest()
        for signature in _exact_event_signatures(signal)})
    return {'identity': consumer_event_identity(signal), 'aliases': aliases}


def validate_guard(guard, identity):
    if (type(guard) is not dict or set(guard) != {'identity', 'aliases'}
            or guard['identity'] != identity or type(guard['aliases']) is not list
            or len(guard['aliases']) > 3
            or any(type(alias) is not str or not _HASH.fullmatch(alias) for alias in guard['aliases'])
            or guard['aliases'] != sorted(set(guard['aliases']))):
        raise Daily3Error('Die gespeicherte Spielzuordnung ist nicht eindeutig.')


def events_overlap(left, right):
    # Distinct native IDs remain distinct in the models/catalog. For another
    # real-stake slot, an exact same-time participant/label collision is still
    # insufficient proof of a DIFFERENT event, even across equal-tier sources.
    return (left['identity'] == right['identity']
            or bool(set(left['aliases']).intersection(right['aliases'])))
