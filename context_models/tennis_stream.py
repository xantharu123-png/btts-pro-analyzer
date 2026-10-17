"""Explicit bounded all-revision tennis source transport; never activation.

The old diagnostic 512-row/2-MiB admission remains unchanged. This separate
contract admits physical payload metadata before bodies and validates each
actual revision. The indexed path retains one encoded owner; the explicit
global fallback retains at most four encoded owners and decodes one feature
case at a time under one shared memory budget. It does not build, renew, or
trust an invalid membership index, read outcomes, fit effects, or change the
six frozen prediction owners.
"""
from datetime import datetime
import math
from time import monotonic

from context_models.contracts import ContextContractError, canonical_timestamp
from context_models.tennis_training import _TennisBatchDiscovery, _validate_membership_mode
from context_observations import _SELECT


class TennisSourceStreamBudget:
    contract = 'tennis-source-stream-v1'

    def __init__(self, seconds=120, *, started=None):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 1 <= seconds <= 600:
            raise ValueError('stream seconds must be between 1 and 600')
        if started is not None and (type(started) not in (int, float) or not math.isfinite(started)
                                    or started > monotonic()):
            raise ValueError('stream start must be a prior finite monotonic clock')
        self.started = monotonic() if started is None else started
        self.seconds, self.limit = seconds, 256*1024**2
        self.raw_case_rows, self.raw_case_bytes = 32768, 32*1024**2
        self.raw_total_rows, self.raw_total_bytes = 131072, 128*1024**2
        self.chunk_rows, self.chunk_bytes = 512, 2*1024**2
        self.raw_receipts_total = self.raw_payload_bytes_total = 0
        self.global_raw_rows = self.global_raw_payload_bytes = 0
        self.case_raw_rows = [0]*4
        self.case_raw_bytes = [0]*4
        self.metadata_bytes = self.selected_bytes = self.output_bytes = 0
        self.max_chunk_rows = self.max_chunk_payload_bytes = 0
        self.sql_cancelled = False

    def check(self):
        for name, maximum in (('limit', 256*1024**2), ('raw_case_rows', 32768),
                ('raw_case_bytes', 32*1024**2), ('raw_total_rows', 131072),
                ('raw_total_bytes', 128*1024**2), ('chunk_rows', 512), ('chunk_bytes', 2*1024**2)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError('tennis source stream limits may only tighten the frozen contract')
        if monotonic()-self.started > self.seconds:
            raise TimeoutError('tennis source stream time budget exhausted')
        if self.metadata_bytes+self.selected_bytes+self.output_bytes > self.limit:
            raise ValueError('tennis source stream retained byte budget exhausted')

    def charge_metadata(self, amount):
        self.metadata_bytes += amount
        self.check()

    def retain_case(self, encoded_bytes, rows):
        self.selected_bytes = 3*encoded_bytes+rows*4096
        self.check()

    def admit_case_raw(self, index, rows, payload_bytes):
        """Selected cases, separate from the complete global negative proof."""
        self.check()
        if (self.case_raw_rows[index]+rows > self.raw_case_rows
                or self.case_raw_bytes[index]+payload_bytes > self.raw_case_bytes
                or self.raw_receipts_total+rows > self.raw_total_rows
                or self.raw_payload_bytes_total+payload_bytes > self.raw_total_bytes):
            raise ValueError('tennis source stream raw admission exceeded')
        self.case_raw_rows[index] += rows
        self.case_raw_bytes[index] += payload_bytes
        self.raw_receipts_total += rows
        self.raw_payload_bytes_total += payload_bytes

    def admit_raw(self, rows, payload_bytes, max_payload, missing):
        self.check()
        if (missing or max_payload > self.chunk_bytes or rows > self.raw_case_rows
                or payload_bytes > self.raw_case_bytes
                or self.raw_receipts_total+rows > self.raw_total_rows
                or self.raw_payload_bytes_total+payload_bytes > self.raw_total_bytes):
            raise ValueError('tennis source stream raw admission exceeded')
        self.raw_receipts_total += rows
        self.raw_payload_bytes_total += payload_bytes
        self.selected_bytes = 3*payload_bytes+rows*4096
        self.check()

    def sql_progress(self):
        self.sql_cancelled = monotonic()-self.started > self.seconds
        return int(self.sql_cancelled)


def _case_selection(discovery, event, cutoff):
    budget, connection = discovery.budget, discovery.connection
    keys, members = {event['event_key']}, ()
    if discovery.membership_mode == 'indexed':
        from context_tennis_index import _player_membership_candidates
        members = tuple(_player_membership_candidates(connection, tour=event['tour'],
            player_ids=(event['home_id'], event['away_id']), cutoff=cutoff))
        for member in members:
            budget.charge_metadata(1024+sum(len(value.encode('utf8')) for value in member))
            keys.add(member[2])
    else:
        keys.update(key for (tour, player, key), first in discovery.membership.items()
                    if tour == event['tour'] and player in (event['home_id'], event['away_id']) and first <= cutoff)
    ordered = tuple(sorted(keys))
    rows = payload_bytes = maximum = missing = 0
    for key in ordered:
        budget.check()
        count, amount, peak, invalid = connection.execute("""SELECT COUNT(*),
            COALESCE(SUM(LENGTH(c.payload)),0),COALESCE(MAX(LENGTH(c.payload)),0),
            COALESCE(SUM(c.payload IS NULL OR typeof(c.payload)!='blob'),0)
            FROM context_observations r LEFT JOIN context_contents c ON c.content_digest=r.content_digest
            WHERE r.event_key=? AND r.observed_at<=? AND r.source='espn'
            AND r.kind IN ('event_status','workload')""", (key, cutoff)).fetchone()
        rows += count
        payload_bytes += amount
        maximum, missing = max(maximum, peak), missing+invalid
    budget.admit_raw(rows, payload_bytes, maximum, missing)
    return ordered, members


def _physical_rows(connection, keys, cutoff, budget):
    chunk_rows = chunk_bytes = 0
    for key in keys:
        cursor = connection.execute(_SELECT+" WHERE r.event_key=? AND r.observed_at<=?"
            " AND r.source='espn' AND r.kind IN ('event_status','workload') ORDER BY r.observed_at,r.digest",
            (key, cutoff))
        for stored in cursor:
            budget.check()
            size = len(stored[8])
            if chunk_rows == budget.chunk_rows or chunk_bytes+size > budget.chunk_bytes:
                chunk_rows = chunk_bytes = 0
            chunk_rows += 1
            chunk_bytes += size
            budget.max_chunk_rows = max(budget.max_chunk_rows, chunk_rows)
            budget.max_chunk_payload_bytes = max(budget.max_chunk_payload_bytes, chunk_bytes)
            yield stored


def iter_streamed_tennis_features(connection, origins, *, budget, feature_version='tennis-performed-load-v4',
                                   membership_mode='indexed'):
    """Explicit opt-in reader; every raw revision and causal correction survives."""
    from context_models.tennis_live import original_base
    from context_models.tennis_v4 import live_tennis_features
    from tennis.history_projection import PreparedTennisHistory
    _validate_membership_mode(membership_mode)
    if type(budget) is not TennisSourceStreamBudget:
        raise TypeError('explicit tennis-source-stream-v1 budget required')
    if type(origins) is not tuple or not 1 <= len(origins) <= 4:
        raise ValueError('source stream requires 1 to 4 explicit frozen origins')
    if not connection.in_transaction:
        raise ContextContractError('tennis source stream requires its owning read transaction')
    cases = tuple((origin['event'], canonical_timestamp(origin['cutoff'])) for origin in origins)
    if membership_mode == 'legacy':
        clock = max(cutoff for _, cutoff in cases)
        # Metadata rejects oversize physical work rows before the SQL cursor
        # returns a body. Global scan counts are not the selected-case limits.
        maximum, invalid = connection.execute("""SELECT COALESCE(MAX(LENGTH(CAST(c.payload AS BLOB))),0),
            COALESCE(SUM(c.payload IS NULL OR typeof(c.payload)!='blob'),0)
            FROM context_observations r LEFT JOIN context_contents c ON c.content_digest=r.content_digest
            WHERE r.source='espn' AND r.kind IN ('event_status','workload') AND r.observed_at<=?
            AND r.event_key>='espn:tennis:' AND r.event_key<'espn:tennis;'""", (clock,)).fetchone()
        if invalid or maximum > budget.chunk_bytes:
            raise ValueError('global tennis source work row exceeds chunk admission')
        raw = connection.execute(_SELECT+" WHERE r.source='espn' AND r.kind IN ('event_status','workload')"
            " AND r.observed_at<=? AND r.event_key>='espn:tennis:' AND r.event_key<'espn:tennis;'"
            " ORDER BY r.event_key,r.observed_at,r.digest", (clock,))
        try:
            owners = PreparedTennisHistory._from_physical_case_batch(raw, cases=cases, budget=budget)
        finally:
            raw.close()
        for index, (origin, (event, cutoff)) in enumerate(zip(origins, cases)):
            owner = owners[index]
            with owner._stream_feature_scope(event, budget) as history:
                features = live_tennis_features(feature_version, event, history, original_base(origin),
                                               cutoff=datetime.fromisoformat(cutoff))
                budget.check()
            yield owner, history, features
            budget.metadata_bytes -= owner._stream_charge
            owners[index] = None
            del owner, history, features
        budget.check()
        return
    discovery = _TennisBatchDiscovery(connection, cases, budget, membership_mode)
    for origin, (event, cutoff) in zip(origins, cases):
        keys, memberships = _case_selection(discovery, event, cutoff)
        owner = PreparedTennisHistory._from_case_physical_rows(
            _physical_rows(connection, keys, cutoff, budget), cutoff=cutoff, tour=event['tour'],
            memberships=memberships, budget=budget)
        with owner.feature_scope(event) as history:
            features = live_tennis_features(feature_version, event, history, original_base(origin),
                                           cutoff=datetime.fromisoformat(cutoff))
            budget.check()
        yield owner, history, features
        del owner, history, features
        budget.selected_bytes = 0
    budget.check()
