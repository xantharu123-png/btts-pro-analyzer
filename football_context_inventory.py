"""DRAFT: freeze unresolved native headers; never certify bodies or effects.

Separate immutable kind. A later consumer MUST physically rebuild every source
body and the exact header inventory before deriving features. Capture writes
never perform that expensive source-body audit. No providers or activation.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
import struct
from threading import Lock
from time import monotonic

import challenge_engine as engine
from context_models.contracts import (ContextContractError, ContextIntegrityError,
    canonical_timestamp, digest, require_digest, require_object)
from context_models.dataset import _reader, _reader_files
from context_models.football_training import _load_publication, joint_base
from context_models.replay import ReplayUnavailable
from model_artifacts import _insert_artifact, canonical_bytes, prepare_artifact
from runtime_paths import _assert_no_symlink_components

KIND = 'football-native-context-inventory-v2'
STATE = 'frozen-unresolved'
SOURCE_TRANSPORT = 'football-native-source-stream-v2'
SOURCE_SCOPE = 'native-base-roster-weather-all-revisions-v1'
HEADER_LAW = 'football-header-inventory-lp8-v1'
FIELDS = ('digest', 'content_digest', 'event_key', 'observed_at',
          'schedule_revision', 'source', 'subject_id', 'kind')
MAX_EVENTS, MAX_PAYLOAD_BYTES = 32, 1024
MAX_HEADERS, MAX_HEADER_BYTES, MAX_FIELD_BYTES = 100000, 32*1024**2, 1024


def _now():
    return datetime.now(timezone.utc)


class HeaderBudget:
    """Explicit new cumulative contract. No implicit operational defaults.

    Counts actual metadata work, including failed reads and both writer
    rechecks. Concurrent phases debit elapsed processing time cumulatively.
    Required limits must be selected only after native read measurement.
    """
    def __init__(self, *, max_headers, max_bytes, seconds, phase_seconds):
        if (type(max_headers) is not int or not 1 <= max_headers <= 3*MAX_EVENTS*MAX_HEADERS
                or type(max_bytes) is not int or not 1 <= max_bytes <= 3*MAX_EVENTS*MAX_HEADER_BYTES
                or type(seconds) not in (int, float) or not 0 < seconds <= 4*MAX_EVENTS
                or type(phase_seconds) not in (int, float) or not 0 < phase_seconds <= 2):
            raise ContextContractError('explicit bounded unresolved-header budget required')
        self.max_headers, self.max_bytes = max_headers, max_bytes
        self.seconds, self.phase_seconds = seconds, phase_seconds
        self.headers = self.bytes = 0
        self.spent = self.max_phase_seconds = 0.0
        self.max_writer_seconds = 0.0
        self.active, self.lock, self.serial = {}, Lock(), 0

    def over_time(self):
        with self.lock:
            now = monotonic()
            return (self.spent+sum(now-start for start in self.active.values()) > self.seconds
                    or any(now-start > self.phase_seconds for start in self.active.values()))

    @contextmanager
    def phase(self, label='prepare'):
        if label not in {'prepare', 'writer'}:
            raise ContextContractError('unknown unresolved header phase')
        with self.lock:
            self.serial += 1
            token = self.serial
            self.active[token] = monotonic()
        def check(rows=0, size=0):
            with self.lock:
                now = monotonic()
                elapsed = now-self.active[token]
                if elapsed < 0:
                    raise ContextIntegrityError('unresolved header monotonic clock reversed')
                total = self.spent+sum(now-start for start in self.active.values())
                if (elapsed > self.phase_seconds or total > self.seconds
                        or self.headers+rows > self.max_headers or self.bytes+size > self.max_bytes):
                    raise ReplayUnavailable('unresolved_header_budget_exhausted')
                self.headers += rows
                self.bytes += size
        check.started_at = self.active[token]
        failed = False
        try:
            check()
            yield check
        except BaseException:
            failed = True
            raise
        finally:
            with self.lock:
                elapsed = monotonic()-self.active.pop(token)
                self.spent += elapsed
                self.max_phase_seconds = max(self.max_phase_seconds, elapsed)
                if label == 'writer':
                    self.max_writer_seconds = max(self.max_writer_seconds, elapsed)
            if label == 'prepare' and elapsed > self.phase_seconds and not failed:
                raise ReplayUnavailable('unresolved_header_prepare_time_overrun')


class _HeaderHash:
    def __init__(self):
        self.hash = hashlib.sha256(HEADER_LAW.encode('ascii')+b'\x00')
        self.count = self.bytes = 0
        self.refs = []

    def add(self, header, check):
        if (type(header) is not tuple or len(header) != len(FIELDS)
                or any(type(value) is not str for value in header)):
            raise ContextIntegrityError('unresolved inventory has untyped header fields')
        values = tuple(value.encode('utf8') for value in header)
        if any(len(value) > MAX_FIELD_BYTES for value in values):
            raise ContextIntegrityError('unresolved inventory header field is oversized')
        encoded = struct.pack('!8I', *(len(value) for value in values))+b''.join(values)
        if self.count >= MAX_HEADERS or self.bytes+len(encoded) > MAX_HEADER_BYTES:
            raise ReplayUnavailable('unresolved_inventory_header_bound_exceeded')
        check(1, len(encoded))
        self.hash.update(encoded)
        self.count += 1
        self.bytes += len(encoded)
        self.refs.append(header[0])

    def finish(self):
        if not self.count or len(set(self.refs)) != self.count:
            raise ContextIntegrityError('unresolved inventory is empty or repeats receipt identities')
        return {'header_hash': self.hash.hexdigest(), 'header_bytes': self.bytes,
                'observation_refs_hash': digest(sorted(self.refs)), 'observation_count': self.count}


def _keys(packet):
    ids = {engine.football_base_history_record(row)['fixture_id'] for row in
           [packet['fixture'], *packet['league_history'], *(packet['team_history'] or [])]}
    if len(ids) > 4096:
        raise ReplayUnavailable('unresolved_inventory_event_bound_exceeded')
    return tuple(sorted('api-football:football:'+str(native_id) for native_id in ids))


@contextmanager
def _sql_deadline(connection, check):
    """Only on this capture owner's fresh connection, never replace a caller guard."""
    cancelled = []
    def progress():
        try:
            check()
        except ReplayUnavailable as exc:
            cancelled.append(exc)
            return 1
        return 0
    connection.set_progress_handler(progress, 1000)
    try:
        yield
    except sqlite3.OperationalError as exc:
        if cancelled:
            raise cancelled[0] from exc
        if getattr(exc, 'sqlite_errorcode', None) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            raise ReplayUnavailable('unresolved_inventory_writer_busy') from exc
        raise
    finally:
        connection.set_progress_handler(None, 0)


def _headers(connection, packet, cutoff, check):
    """Only scalar metadata. This intentionally makes no canonical-body claim."""
    if not connection.in_transaction:
        raise ContextContractError('unresolved header inventory requires one held image')
    result = _HeaderHash()
    cols = ','.join('r.'+name for name in FIELDS)
    bad = ' OR '.join("typeof(r."+name+")!='text' OR length(CAST(r."+name+
        " AS BLOB))>1024" for name in FIELDS)
    for key in _keys(packet):
        check()
        condition = " WHERE r.event_key=? AND r.observed_at<=? AND r.kind!='match_outcome'"
        if connection.execute('SELECT 1 FROM context_observations r'+condition+
                ' AND ('+bad+') LIMIT 1', (key, cutoff)).fetchone():
            raise ContextIntegrityError('unresolved inventory has invalid scalar metadata')
        for header in connection.execute('SELECT '+cols+' FROM context_observations r'+condition+
                ' ORDER BY r.observed_at,r.digest LIMIT ?', (key, cutoff, MAX_HEADERS-result.count+1)):
            result.add(tuple(header), check)
    return result.finish()


def validate_inventory(payload):
    fields = {'schema', 'state', 'source_transport', 'source_scope', 'header_law',
        'binding_ref', 'event_key', 'decision_at', 'scheduled_start', 'header_hash', 'header_bytes',
        'observation_refs_hash', 'observation_count'}
    require_object(payload, fields, label='unresolved football header inventory')
    if (type(payload['schema']) is not int or payload['schema'] != 2
            or payload['state'] != STATE or payload['source_transport'] != SOURCE_TRANSPORT
            or payload['source_scope'] != SOURCE_SCOPE or payload['header_law'] != HEADER_LAW):
        raise ContextContractError('unknown unresolved football inventory contract')
    for name in ('binding_ref', 'header_hash', 'observation_refs_hash'):
        require_digest(payload[name], name)
    key, prefix = payload['event_key'], 'api-football:football:'
    if (type(key) is not str or not key.startswith(prefix) or not key[len(prefix):].isascii()
            or not key[len(prefix):].isdecimal() or str(int(key[len(prefix):])) != key[len(prefix):]
            or int(key[len(prefix):]) <= 0):
        raise ContextContractError('inventory event is not an exact native football key')
    if (type(payload['decision_at']) is not str
            or canonical_timestamp(payload['decision_at']) != payload['decision_at']):
        raise ContextContractError('inventory needs an actual canonical decision clock')
    if (type(payload['scheduled_start']) is not str
            or canonical_timestamp(payload['scheduled_start']) != payload['scheduled_start']
            or payload['decision_at'] >= payload['scheduled_start']):
        raise ContextContractError('inventory cutoff must precede its frozen original kickoff')
    for name, maximum in (('header_bytes', MAX_HEADER_BYTES), ('observation_count', MAX_HEADERS)):
        if type(payload[name]) is not int or not 1 <= payload[name] <= maximum:
            raise ContextContractError('inventory metadata count or bytes are unbounded')
    if len(canonical_bytes(payload)) > MAX_PAYLOAD_BYTES:
        raise ContextContractError('unresolved inventory exceeds compact artifact envelope')
    return dict(payload)


def prepare_inventory(path, binding_ref, *, decision_at, budget):
    if type(budget) is not HeaderBudget or not isinstance(decision_at, datetime) or decision_at.utcoffset() is None:
        raise ContextContractError('inventory preparation needs explicit budget and actual aware clock')
    clock = canonical_timestamp(decision_at)
    with budget.phase() as check, _reader(Path(path)) as connection, _sql_deadline(connection, check):
        connection.execute('PRAGMA busy_timeout=0')
        binding, original, _ = _load_publication(connection, binding_ref, latest=clock)
        event = binding['payload']['native_event']
        if not binding['payload']['decision_at'] <= clock < event['scheduled_start']:
            raise ReplayUnavailable('unresolved_inventory_not_prematch')
        proof = _headers(connection, original.to_dict(), clock, check)
        check()
    return validate_inventory({'schema': 2, 'state': STATE, 'source_transport': SOURCE_TRANSPORT,
        'source_scope': SOURCE_SCOPE, 'header_law': HEADER_LAW, 'binding_ref': binding_ref,
        'event_key': event['event_key'], 'decision_at': clock,
        'scheduled_start': event['scheduled_start'], **proof})


def _same_inventory(connection, original, payload, check):
    actual = _headers(connection, original.to_dict(), payload['decision_at'], check)
    if any(actual[name] != payload[name] for name in actual):
        raise ContextIntegrityError('frozen unresolved source headers changed before publication')


def _bounded_artifact(connection, ref, *, latest):
    from context_models.dataset import _artifact
    header = connection.execute('SELECT kind,typeof(payload),length(CAST(payload AS BLOB)) '
                                'FROM artifacts WHERE digest=?', (ref,)).fetchone()
    if (header is None or header[:2] != (KIND, 'blob') or type(header[2]) is not int
            or not 0 < header[2] <= MAX_PAYLOAD_BYTES):
        raise ContextIntegrityError('unresolved inventory artifact is absent or physically unbounded')
    return _artifact(connection, ref, KIND, latest=latest)


@contextmanager
def _existing_writer(path):
    """No implicit DB/schema creation or unmetered autoinit writer transaction."""
    path = _assert_no_symlink_components(Path(path))
    before = _reader_files(path)
    connection = sqlite3.connect(path.as_uri()+'?mode=rw', uri=True, timeout=0)
    try:
        opened = _reader_files(path, expected=before)
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=0')
        connection.execute('PRAGMA trusted_schema=OFF')
        def check_file():
            _reader_files(path, expected=opened)
        yield connection, check_file
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()


def publish_inventory(path, payload, *, remaining, budget):
    """Short metadata-only writer. Never call the physical body resolver here."""
    payload = validate_inventory(payload)
    if type(budget) is not HeaderBudget or type(remaining) is not int or remaining < 0:
        raise ContextContractError('inventory publication needs explicit remaining bytes and budget')
    with budget.phase('writer') as check, _existing_writer(path) as (connection, check_file), _sql_deadline(connection, check):
        try:
            connection.execute('PRAGMA busy_timeout=0')
            connection.execute('BEGIN IMMEDIATE')
            read_at = canonical_timestamp(_now())
            binding, original, _ = _load_publication(connection, payload['binding_ref'], latest=read_at)
            event = binding['payload']['native_event']
            if (payload['event_key'] != event['event_key']
                    or payload['scheduled_start'] != event['scheduled_start'] or not
                    binding['payload']['decision_at'] <= payload['decision_at'] <= read_at < event['scheduled_start']):
                raise ReplayUnavailable('unresolved_inventory_publication_not_prematch')
            _same_inventory(connection, original, payload, check)
            if connection.execute('SELECT 1 FROM artifacts WHERE kind=? AND '
                    "(typeof(payload)!='blob' OR length(CAST(payload AS BLOB))>? OR length(payload)=0) LIMIT 1",
                    (KIND, MAX_PAYLOAD_BYTES)).fetchone():
                raise ContextIntegrityError('invalid physical unresolved inventory metadata')
            rows = connection.execute("SELECT digest FROM artifacts WHERE kind=? "
                "AND json_extract(CAST(payload AS TEXT),'$.binding_ref')=? "
                "AND json_extract(CAST(payload AS TEXT),'$.header_hash')=? LIMIT 2",
                (KIND, payload['binding_ref'], payload['header_hash'])).fetchall()
            if len(rows) > 1:
                raise ContextIntegrityError('duplicate first unresolved inventory for one source revision')
            if rows:
                previous = load_inventory(connection, rows[0][0], latest=read_at)[0]['payload']
                if (any(previous[name] != payload[name] for name in previous if name != 'decision_at')
                        or previous['decision_at'] > payload['decision_at']):
                    raise ContextIntegrityError('previous unresolved inventory changes source scope or first clock')
                check()
                connection.rollback()
                return rows[0][0], 'reused-unresolved', 0
            prepared = prepare_artifact(kind=KIND, payload=payload)
            if len(prepared.payload_bytes) > remaining:
                connection.rollback()
                return None, 'budget-exhausted', 0
            created = canonical_timestamp(_now())
            if not payload['decision_at'] <= created < event['scheduled_start']:
                raise ReplayUnavailable('unresolved_inventory_missed_prematch')
            actual_created, inserted = _insert_artifact(connection, prepared, created)
            if not inserted or actual_created != created:
                raise ContextIntegrityError('unresolved inventory physical insert clock differs from actual writer clock')
            # Header-level recheck only. Body alterations cannot gain a source
            # approval: the offline owner below must re-read those real bodies.
            _same_inventory(connection, original, payload, check)
            load_inventory(connection, prepared.digest, latest=created)
            finished = canonical_timestamp(_now())
            if not created <= finished < event['scheduled_start']:
                raise ReplayUnavailable('unresolved_inventory_readback_missed_prematch')
            check_file()
            check()
            connection.commit()
            # Commit latency cannot be rolled back after success. Preserve its
            # byte debit and real receipt, but NEVER relabel an overrun PASS.
            status = ('captured-unresolved-time-overrun' if budget.over_time()
                      else 'captured-unresolved')
            return prepared.digest, status, len(prepared.payload_bytes)
        except BaseException:
            connection.rollback()
            raise


def load_inventory(connection, inventory_ref, *, latest):
    """Load only unresolved ownership metadata; this is NOT source approval."""
    from context_models.experiments import _artifact_created_at
    if not connection.in_transaction:
        raise ContextContractError('inventory source proof requires one held physical reader')
    envelope = _bounded_artifact(connection, inventory_ref, latest=canonical_timestamp(latest))
    payload = validate_inventory(envelope['payload'])
    binding, original, _ = _load_publication(connection, payload['binding_ref'], latest=canonical_timestamp(latest))
    event = binding['payload']['native_event']
    if (_artifact_created_at(connection, payload['binding_ref']) > payload['decision_at']
            or payload['event_key'] != event['event_key'] or payload['scheduled_start'] != event['scheduled_start'] or not
            binding['payload']['decision_at'] <= payload['decision_at'] <=
            _artifact_created_at(connection, inventory_ref) < event['scheduled_start']):
        raise ContextIntegrityError('unresolved inventory is not a real prematch owner of this original')
    return envelope, binding, original


def resolve_inventory_sources(connection, inventory_ref, *, latest, feature_version, retain_full=False, ledger=None):
    """Actual physical source proof, required before ANY training/feature use."""
    from context_models.football_joint_context import FEATURE_VERSION, POOLED_FEATURE_VERSION, PLAYER_LOAD_FEATURE_VERSION
    from context_models.football_source_stream import _stream_joint_sources_at_cutoff
    from football_joint_worker import _native_binding
    if feature_version == PLAYER_LOAD_FEATURE_VERSION:
        raise ReplayUnavailable('player_load_requires_original_decision')
    if feature_version not in {FEATURE_VERSION, POOLED_FEATURE_VERSION}:
        raise ContextContractError('unknown postcapture inventory feature version')
    envelope, binding, original = load_inventory(connection, inventory_ref, latest=latest)
    payload = envelope['payload']
    base = joint_base(original, binding['payload'], decision_at=payload['decision_at'])
    # Always retain the explicit bounded full tuple here, even if the caller
    # ultimately needs only features: header equality cannot bypass physical
    # canonical body validation or the 128MiB expanded-source admission.
    sources = _stream_joint_sources_at_cutoff(connection, original.to_dict(), binding['payload'], base,
        feature_version=feature_version, retain_full=True, ledger=ledger)
    # The closed stream owner just decoded every physical canonical body;
    # bind its exact scalar inventory without repeating a second body audit.
    _bind_resolved_headers(payload, sources['observations'])
    _native_binding(binding['payload'], original, sources['observations'])
    if not retain_full:
        sources['observations'] = sources['feature_observations']
    return envelope, sources


def validate_resolved_inventory(payload, observations):
    """Bind complete canonical body rows to headers, never accept a bare hash."""
    from context_observations import _check_selected_row
    payload = validate_inventory(payload)
    for row in observations:
        _check_selected_row(row)
    _bind_resolved_headers(payload, observations)


def _bind_resolved_headers(payload, observations):
    proof = _HeaderHash()
    for row in sorted(observations, key=lambda row: (row['event_key'], row['observed_at'], row['digest'])):
        if row['kind'] == 'match_outcome' or row['observed_at'] > payload['decision_at']:
            raise ContextIntegrityError('resolved inventory includes outcome or late source bytes')
        proof.add(tuple(row[name] for name in FIELDS), lambda *_: None)
    actual = proof.finish()
    if any(actual[name] != payload[name] for name in actual):
        raise ContextIntegrityError('physical source rebuild differs from frozen unresolved headers')


def find_inventory_ref(connection, binding_ref, decision_at, *, latest):
    if connection.execute('SELECT 1 FROM artifacts WHERE kind=? AND '
            "(typeof(payload)!='blob' OR length(CAST(payload AS BLOB))>? OR length(payload)=0) LIMIT 1",
            (KIND, MAX_PAYLOAD_BYTES)).fetchone():
        raise ContextIntegrityError('invalid physical unresolved inventory metadata')
    refs = connection.execute("SELECT digest FROM artifacts WHERE kind=? "
        "AND json_extract(CAST(payload AS TEXT),'$.binding_ref')=? "
        "AND json_extract(CAST(payload AS TEXT),'$.decision_at')=? LIMIT 2",
        (KIND, binding_ref, decision_at)).fetchall()
    if not refs:
        raise ReplayUnavailable('later_unresolved_inventory_unpublished')
    if len(refs) != 1:
        raise ContextIntegrityError('duplicate actual unresolved inventory decision')
    validate_inventory(_bounded_artifact(connection, refs[0][0], latest=canonical_timestamp(latest))['payload'])
    return refs[0][0]


def rebuild_later_sources(connection, packet, binding, base, *, latest, feature_version, ledger=None, retain_full=False):
    """A free cutoff cannot select a pool: require its real stored inventory."""
    from context_models.football_original_publication import BINDING_KIND
    if latest is None:
        raise ContextContractError('later source rebuild requires its owning actual as-of clock')
    binding_ref = digest({'kind': BINDING_KIND, 'payload': binding})
    ref = find_inventory_ref(connection, binding_ref, base['cutoff'], latest=latest)
    _, sources = resolve_inventory_sources(connection, ref, latest=latest,
        feature_version=feature_version, ledger=ledger, retain_full=retain_full)
    physical, original, _ = _load_publication(connection, binding_ref, latest=canonical_timestamp(latest))
    if (canonical_bytes(physical['payload']) != canonical_bytes(binding)
            or hashlib.sha256(canonical_bytes(packet)).hexdigest() != binding['original_logical_digest']
            or canonical_bytes(joint_base(original, binding, decision_at=base['cutoff'])) != canonical_bytes(base)):
        raise ContextIntegrityError('later source view differs from actual stored original')
    return sources


def prepare_capture_inventories(path, capture_report, *, decision_at, budget):
    """Prepare outside the shared ORIGINAL mutex, under one cumulative ledger."""
    from context_models.football_original_publication import original_capture_report_fields
    checked = original_capture_report_fields({'football_original_capture': capture_report})['football_original_capture']
    candidates = [row for row in checked['events'] if row['status'] == 'captured']
    rows = []
    for row in candidates[:MAX_EVENTS]:
        try:
            payload = prepare_inventory(path, row['binding_ref'], decision_at=decision_at, budget=budget)
            rows.append({'binding_ref': row['binding_ref'], 'payload': payload,
                         'scheduled_start': payload['scheduled_start']})
        except ReplayUnavailable as exc:
            rows.append({'binding_ref': row['binding_ref'], 'payload': None,
                         'scheduled_start': None, 'reason': str(exc)})
    return {'events': rows, 'unprocessed_events': len(candidates)-len(rows)}


def publish_deferred_inventories(path, prepared, *, max_run_bytes, budget, on_commit=None):
    require_object(prepared, {'events', 'unprocessed_events'}, label='deferred unresolved inventory')
    from challenge_15k import MAX_SCAN_FIXTURES
    if (type(budget) is not HeaderBudget
            or type(prepared['events']) is not list or len(prepared['events']) > MAX_EVENTS
            or type(prepared['unprocessed_events']) is not int or prepared['unprocessed_events'] < 0
            or prepared['unprocessed_events'] > MAX_SCAN_FIXTURES
            or type(max_run_bytes) is not int or not 0 <= max_run_bytes <= MAX_EVENTS*MAX_PAYLOAD_BYTES):
        raise ContextContractError('unresolved deferred inventory must remain bounded')
    if on_commit is not None and not callable(on_commit):
        raise ContextContractError('unresolved inventory accounting callback must be callable')
    seen, events, inserted = set(), [], 0
    for row in prepared['events']:
        require_object(row, {'binding_ref', 'payload', 'scheduled_start'}, optional={'reason'}, label='unresolved inventory event')
        require_digest(row['binding_ref'], 'original binding')
        if row['binding_ref'] in seen:
            raise ContextContractError('duplicate deferred unresolved original')
        seen.add(row['binding_ref'])
        if row['payload'] is None:
            if row['scheduled_start'] is not None or type(row.get('reason')) is not str or not 1 <= len(row['reason']) <= 256:
                raise ContextContractError('unavailable unresolved inventory lacks actual reason')
            events.append({'binding_ref': row['binding_ref'], 'status': 'unavailable',
                           'decision_ref': None, 'reason': row['reason']})
            continue
        payload = validate_inventory(row['payload'])
        if (payload['binding_ref'] != row['binding_ref'] or 'reason' in row
                or payload['scheduled_start'] != row['scheduled_start']):
            raise ContextIntegrityError('deferred inventory differs from its actual original')
        try:
            ref, status, size = publish_inventory(path, payload, remaining=max_run_bytes-inserted, budget=budget)
            inserted += size
            if size and on_commit is not None:
                on_commit(size)
            events.append({'binding_ref': row['binding_ref'], 'status': status, 'decision_ref': ref})
        except ReplayUnavailable as exc:
            events.append({'binding_ref': row['binding_ref'], 'status': 'unavailable',
                           'decision_ref': None, 'reason': str(exc)})
    return {'schema': 2, 'scope': 'football-postcapture-unresolved-header-inventory-v2',
            'state': STATE, 'events': events, 'unprocessed_events': prepared['unprocessed_events'],
            'inserted_payload_bytes': inserted, 'header_rows_processed': budget.headers,
            'header_bytes_processed': budget.bytes, 'header_processing_seconds': round(budget.spent, 6),
            'max_writer_seconds': round(budget.max_writer_seconds, 6)}


def inventory_report_fields(snapshot):
    """Closed admin diagnostics, explicitly not source readiness or a tip."""
    from copy import deepcopy
    import math
    from challenge_15k import MAX_SCAN_FIXTURES
    report = snapshot['football_context_decisions']
    require_object(report, {'schema', 'scope', 'state', 'events', 'unprocessed_events',
        'inserted_payload_bytes', 'header_rows_processed', 'header_bytes_processed',
        'header_processing_seconds', 'max_writer_seconds'}, label='unresolved inventory admin report')
    if (type(report['schema']) is not int or report['schema'] != 2
            or report['scope'] != 'football-postcapture-unresolved-header-inventory-v2'
            or report['state'] != STATE or type(report['events']) is not list or len(report['events']) > MAX_EVENTS):
        raise ContextContractError('unknown unresolved inventory report')
    for name, bound in (('unprocessed_events', MAX_SCAN_FIXTURES),
            ('inserted_payload_bytes', MAX_EVENTS*MAX_PAYLOAD_BYTES),
            ('header_rows_processed', 3*MAX_EVENTS*MAX_HEADERS),
            ('header_bytes_processed', 3*MAX_EVENTS*MAX_HEADER_BYTES)):
        if type(report[name]) is not int or not 0 <= report[name] <= bound:
            raise ContextContractError('unresolved inventory report counter is unbounded')
    for name in ('header_processing_seconds', 'max_writer_seconds'):
        if type(report[name]) not in (int, float) or not math.isfinite(report[name]) or report[name] < 0:
            raise ContextContractError('unresolved inventory timings must be actual finite measurements')
    seen, captured = set(), 0
    for row in report['events']:
        require_object(row, {'binding_ref', 'status', 'decision_ref'}, optional={'reason'}, label='unresolved report event')
        require_digest(row['binding_ref'], 'unresolved report original')
        if row['binding_ref'] in seen:
            raise ContextContractError('unresolved report repeats an original')
        seen.add(row['binding_ref'])
        if row['status'] in {'captured-unresolved', 'captured-unresolved-time-overrun', 'reused-unresolved'}:
            require_digest(row['decision_ref'], 'actual frozen unresolved inventory')
            if 'reason' in row:
                raise ContextContractError('stored unresolved inventory cannot claim missing publication')
            captured += row['status'].startswith('captured-')
        elif row['status'] not in {'unavailable', 'budget-exhausted'} or row['decision_ref'] is not None:
            raise ContextContractError('unknown unresolved inventory status')
        if 'reason' in row and (row['status'] != 'unavailable' or type(row['reason']) is not str or not 1 <= len(row['reason']) <= 256):
            raise ContextContractError('unresolved inventory reason is unbounded')
    if report['inserted_payload_bytes'] > captured*MAX_PAYLOAD_BYTES:
        raise ContextContractError('unresolved inventory report debits absent artifacts')
    return {'football_context_decisions': deepcopy(report)}
