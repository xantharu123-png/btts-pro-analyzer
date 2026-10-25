"""Explicit v4 live source ownership; never activation.

The caller opts in explicitly and preserves its original feature/publication
owners. This is a new live contract,
not an enlargement or renaming of the four-case offline training admission.
2 GiB limits cumulative read work, not retained memory or a newly created file.
"""
from contextlib import contextmanager
from datetime import datetime
import sys
from time import monotonic, process_time

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp
from context_models.tennis_live import live_event
from context_models.tennis_training import _TennisBatchDiscovery, _batch_reader
from context_models.tennis_stream import _case_selection, _physical_rows
from tennis.history_projection import PreparedTennisHistory


def _heap(value):
    """Conservative owned-container accounting; shared children count twice."""
    result = sys.getsizeof(value)
    if type(value) is dict:
        result += sum(_heap(key)+_heap(item) for key, item in value.items())
    elif type(value) in (tuple, list, set, frozenset):
        result += sum(_heap(item) for item in value)
    return result


class LiveTennisReadBudget:
    contract = 'tennis-live-indexed-source-v1'

    def __init__(self):
        self.started, self.cpu_started = monotonic(), process_time()
        # New explicit live limits. None is a claimed measured daily PASS.
        self.seconds, self.cpu_seconds = 1200, 1200
        self.case_limit, self.raw_row_limit, self.raw_byte_limit = 400, 2_000_000, 2*1024**3
        self.output_limit = 128*1024**2
        self.admitted_rows = self.admitted_bytes = self.actual_rows = self.actual_bytes = 0
        self.plan_bytes = self.prepared_bytes = self.completed_cases = 0
        self.sql_cancelled = False

    def check(self):
        for name, maximum in (('seconds', 1200), ('cpu_seconds', 1200), ('case_limit', 400),
                ('raw_row_limit', 2_000_000), ('raw_byte_limit', 2*1024**3), ('output_limit', 128*1024**2)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError('live source limits may only tighten the named contract')
        if monotonic()-self.started > self.seconds or process_time()-self.cpu_started > self.cpu_seconds:
            raise TimeoutError('live tennis source time budget exhausted')
        if self.plan_bytes+self.prepared_bytes > self.output_limit:
            raise ValueError('live tennis output/reference retention exceeded')

    def admit(self, rows, size):
        self.check()
        if self.admitted_rows+rows > self.raw_row_limit or self.admitted_bytes+size > self.raw_byte_limit:
            raise ValueError('live tennis cumulative raw admission exceeded')
        self.admitted_rows += rows
        self.admitted_bytes += size

    def keep_prepared(self, value):
        """Call before retaining each actual unpublished prepared payload."""
        self.prepared_bytes += _heap(value)
        self.check()

    def sql_progress(self):
        self.sql_cancelled = (monotonic()-self.started > self.seconds
            or process_time()-self.cpu_started > self.cpu_seconds)
        return int(self.sql_cancelled)


class _LiveCaseBudget:
    """One physical owner under the SAME non-resetting live read deadline."""
    def __init__(self, daily):
        self.daily = daily
        self.metadata_bytes = self.selected_bytes = self.output_bytes = 0
        self.chunk_rows, self.chunk_bytes = 512, 2*1024**2
        self.max_chunk_rows = self.max_chunk_payload_bytes = 0
        self.raw_receipts_total = self.raw_payload_bytes_total = 0

    def check(self):
        self.daily.check()
        for name, maximum in (('chunk_rows', 512), ('chunk_bytes', 2*1024**2)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError('live source chunk limits may only tighten the named contract')
        if self.metadata_bytes+self.selected_bytes > 256*1024**2:
            raise ValueError('live tennis physical-owner retention exceeded')

    def charge_metadata(self, amount):
        self.metadata_bytes += amount
        self.check()

    def admit_raw(self, rows, size, maximum, missing):
        self.check()
        if missing or maximum > self.chunk_bytes or rows > 32768 or size > 32*1024**2:
            raise LiveCaseAdmissionExceeded(rows, size, maximum, missing)
        self.daily.admit(rows, size)
        self.raw_receipts_total, self.raw_payload_bytes_total = rows, size
        self.selected_bytes = 3*size+rows*4096
        self.check()

    def retain_case(self, encoded_bytes, rows):
        self.selected_bytes = 3*encoded_bytes+rows*4096
        self.check()


class LiveCaseAdmissionExceeded(ValueError):
    """One case exceeds its own raw admission (rows, bytes, chunk or missing payloads).

    Owner 25.10.2026 (Gesamtaudit D3): such a case is excluded from the live
    batch with these numbers as diagnosis; the cumulative, chunk and deadline
    limits of the whole batch stay fail-closed.
    """

    def __init__(self, rows, size, maximum, missing):
        super().__init__('live tennis per-case raw admission exceeded')
        self.rows, self.size, self.maximum, self.missing = rows, size, maximum, missing


class _LiveSources:
    def __init__(self, connection, cases, budget):
        if type(budget) is not LiveTennisReadBudget:
            raise TypeError('explicit live tennis source budget required')
        budget.check()
        if type(cases) is not tuple or not 1 <= len(cases) <= budget.case_limit:
            raise ValueError('live tennis forecast count admission exceeded')
        if not connection.in_transaction:
            raise ContextContractError('live source needs one owning physical reader image')
        self.connection, self.budget, self.plans = connection, budget, []
        self.admitted, self.excluded = [], []
        self.consumed = False
        # ALL case SQL metadata and total raw work are admitted BEFORE the
        # first body, including a failing final case. No successful prefix.
        for index, (event, cutoff) in enumerate(cases):
            event, clock = live_event(event), canonical_timestamp(cutoff)
            unit = _LiveCaseBudget(budget)
            discovery = _TennisBatchDiscovery(connection, ((event, clock),), unit, 'indexed')
            try:
                keys, members = _case_selection(discovery, event, clock)
            except LiveCaseAdmissionExceeded as exc:
                # Owner 25.10.2026 (Gesamtaudit D3): one case over its own raw
                # limit is excluded with a diagnosis instead of losing the day;
                # nothing of it was admitted to the shared daily budget.
                self.excluded.append({
                    'case': index, 'event_key': event['event_key'], 'tour': event.get('tour'), 'cutoff': clock,
                    'reason': 'live_case_raw_admission_exceeded', 'rows': exc.rows, 'bytes': exc.size,
                    'max_chunk_bytes': exc.maximum, 'missing_payloads': exc.missing,
                })
                continue
            charge = _heap((event, clock, keys, members))
            budget.plan_bytes += charge
            budget.check()
            self.plans.append((event, clock, keys, members, unit, charge))
            self.admitted.append(index)

    def histories(self):
        if self.consumed:
            raise ContextContractError('live physical source owner cannot be reused')
        self.consumed = True
        for index in range(len(self.plans)):
            event, clock, keys, members, unit, charge = self.plans[index]
            count = size = 0
            def actual_rows():
                nonlocal count, size
                for raw in _physical_rows(self.connection, keys, clock, unit):
                    count += 1
                    size += len(raw[8])
                    self.budget.actual_rows += 1
                    self.budget.actual_bytes += len(raw[8])
                    if (count > unit.raw_receipts_total or size > unit.raw_payload_bytes_total):
                        raise ContextIntegrityError('live source exceeds its frozen raw admission')
                    yield raw
            owner = PreparedTennisHistory._from_case_physical_rows(actual_rows(),
                cutoff=datetime.fromisoformat(clock), tour=event['tour'], memberships=members, budget=unit)
            if count != unit.raw_receipts_total or size != unit.raw_payload_bytes_total:
                raise ContextIntegrityError('live physical source differs from its admitted inventory')
            yield owner
            del owner
            self.plans[index] = None
            self.budget.plan_bytes -= charge
            self.budget.completed_cases += 1
            self.budget.check()

    def require_complete(self):
        if (self.budget.completed_cases != len(self.plans)
                or self.budget.actual_rows != self.budget.admitted_rows
                or self.budget.actual_bytes != self.budget.admitted_bytes):
            raise ContextIntegrityError('live source read did not complete its whole admitted batch')


@contextmanager
def open_live_sources(path, cases, budget):
    """No network/writes/fallback. Reader closes BEFORE existing publication."""
    with _batch_reader(path, budget) as connection:
        sources = _LiveSources(connection, cases, budget)
        yield connection, sources
        sources.require_complete()


def prepare_live_v4(batch, qualified, state_refs, code_hashes, budget):
    """Exact v4 preparation seam; no writes or prediction changes.

    The owning caller must have run its unchanged A1 _verify_states exactly
    once. The unchanged _original performs real target-receipt and feature
    checks, not a seed presented as validated. Only final prepared inputs
    survive a case. The v3/default legacy path must never call this helper.
    """
    if batch.feature_version != 'tennis-performed-load-v4':
        raise ContextContractError('indexed live source contract is v4 only')
    from tennis.live_context import _event, _Inventory
    from tennis.simulator import POINT_MODEL_VERSION
    from context_transport import KIND, context_payload_key
    cases = tuple((_event(item['binding']['row']), item['decision']) for item in qualified)
    prepared, reasons = {}, []
    with open_live_sources(batch.path, cases, budget) as (connection, sources):
        inventory = _Inventory(connection)
        ordinal = 0
        # zip/enumerate retain their last yielded result tuple while fetching
        # the next source owner. Use the source iterator DIRECTLY, not either
        # wrapper, otherwise even del(owner) would leave a hidden raw alias.
        for owner in sources.histories():
            ordinal += 1
            item = qualified[sources.admitted[ordinal-1]]
            feature_start = monotonic()
            with owner.feature_scope(_event(item['binding']['row'])) as observations:
                origin, event, base, features = batch._original(
                    item, state_refs[id(item)], observations, code_hashes)
                observation_refs = sorted({row['digest'] for row in observations})
            # A for-loop normally retains its previous target until AFTER the
            # next owner is constructed. Delete BOTH actual source aliases
            # explicitly; a real weak-reference test proves this lifetime.
            del observations, owner
            feature_seconds = monotonic()-feature_start
            if item['state'].market_model_version == POINT_MODEL_VERSION:
                effect, effect_hash, approval = None, None, None
                reason = 'point-winner-law-needs-own-effect-contract'
            else:
                effect, effect_hash, approval, reason = inventory.select(event, base, features)
            inputs = {'event': event, 'base': base, 'features': features,
                'observation_refs': observation_refs, 'preprocessing_refs': [],
                'effect_artifact': effect, 'effect_hash': effect_hash, 'approval': approval}
            descriptor = {'schema': 1, 'kind': KIND, **inputs,
                'approval_hash': approval['digest'] if approval is not None else None}
            key_start = monotonic()
            key = context_payload_key(descriptor)
            value = (origin, inputs, key)
            budget.keep_prepared(value)
            prepared[id(item)] = value
            reasons.append(reason)
            if ordinal == 1 or ordinal % 10 == 0 or ordinal == len(qualified):
                batch._report('prepare_progress', processed=ordinal, total=len(qualified),
                    feature_seconds=round(feature_seconds, 3), key_seconds=round(monotonic()-key_start, 3))
        for diagnosis in sources.excluded:
            # The excluded forecast is stored without context evidence; the
            # numbers reach the journal and the item's result (owner 25.10.2026).
            item = qualified[diagnosis['case']]
            batch._report('prepare_excluded', **diagnosis)
            item['result']['errors'].append({'tour': diagnosis['tour'], 'event_key': diagnosis['event_key'],
                'reason': diagnosis['reason'], 'rows': diagnosis['rows'], 'bytes': diagnosis['bytes'],
                'max_chunk_bytes': diagnosis['max_chunk_bytes'], 'missing_payloads': diagnosis['missing_payloads']})
            item['result']['status'] = 'partial'
            reasons.append('live-case-excluded:' + diagnosis['reason'])
    return prepared, reasons
