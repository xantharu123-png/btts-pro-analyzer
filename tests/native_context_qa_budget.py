"""One aggregate, non-refundable QA package; never production proof authority.

The native coordinator owns namespace custody, process limits and measurements.
This closed protocol durably reserves A/B/C together before the first scan. It
does not reset or modify the older preparation/admission journals. Replay is
read-only: there is deliberately no resume, repair, refund or retry operation.
"""
import json
import os
import threading

import context_preparation_budget as legacy

NS = 10**9
FORMAT = 'betboy-context-qa-budget-v2'
AUTHORIZATION = '2026-09-13-coordination-qualification-01'
AUTHORIZATION_02 = '2026-09-13-coordination-qualification-02'
STEPS = ('A1', 'A2', 'A3', 'B', 'C')
LIMITS = {'A': 300*NS, 'B': 300*NS, 'C': 300*NS}
PROFILES = {AUTHORIZATION: LIMITS, AUTHORIZATION_02: {'A': 400*NS, 'B': 300*NS, 'C': 200*NS}}
CHARGE = sum(LIMITS.values())
WALL = 900*NS
PARENT = 60*NS
WORKER = 240*NS
ZERO = '0'*64


class QaBudgetError(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise QaBudgetError(message)


def integer(value, maximum=2**63-1):
    return legacy._integer(value, 'QA counter', maximum=maximum)


def clone(value):
    return json.loads(legacy._canonical(value))


class _State:
    def __init__(self):
        self.head, self.count = ZERO, 0
        self.binding, self.clock, self.pending = None, None, None
        self.offset_low = self.offset_high = None
        self.steps = []
        self.child_cpu = dict.fromkeys(LIMITS, 0)
        self.parent_cpu = 0
        self.status = 'unreserved'

    def observe(self, value, parent_cpu):
        sample = legacy._clock_from_dict(value)
        integer(parent_cpu, PARENT)
        need(parent_cpu >= self.parent_cpu, 'parent CPU moved backwards')
        need(sample.boot_id == self.binding['boot_id'], 'boot changed')
        need(self.binding['start_boot_ns'] <= sample.boot_before_ns and
             sample.boot_after_ns < self.binding['deadline_boot_ns'], 'original QA deadline expired')
        low = sample.realtime_ns - sample.boot_after_ns
        high = sample.realtime_ns - sample.boot_before_ns
        if self.clock is not None:
            need(sample.boot_before_ns >= self.clock.boot_after_ns and
                 sample.realtime_ns >= self.clock.realtime_ns, 'clock moved backwards')
            low, high = max(low, self.offset_low), min(high, self.offset_high)
        need(low <= high, 'clock discontinuity')
        self.clock, self.offset_low, self.offset_high = sample, low, high
        self.parent_cpu = parent_cpu

    def apply(self, record):
        legacy._closed(record, 'format sequence previous event body'.split(), 'QA record')
        need(record['format'] == FORMAT and type(record['sequence']) is int and
             record['sequence'] == self.count and record['previous'] == self.head,
             'foreign, reordered or truncated QA record')
        body, event = record['body'], record['event']
        need(self.status not in ('complete', 'stopped'), 'terminal package cannot be reused')
        if event == 'reserve':
            legacy._closed(body, 'authorization identity history_digest start_boot_ns deadline_boot_ns boot_id limits charge_cpu_ns clock parent_cpu_ns'.split(), 'QA reservation')
            need(self.count == 0 and body['authorization'] in PROFILES, 'one explicit package only')
            limits = PROFILES[body['authorization']]
            legacy._identity(legacy.BudgetIdentity(**body['identity']))
            legacy._digest(body['history_digest'], 'declared historical workload')
            integer(body['start_boot_ns']); integer(body['deadline_boot_ns'])
            need(body['deadline_boot_ns'] == body['start_boot_ns'] + WALL, 'deadline was renewed')
            legacy._closed(body['limits'], LIMITS, 'aggregate phase limits')
            for key in LIMITS:
                integer(body['limits'][key], limits[key])
            integer(body['charge_cpu_ns'], CHARGE)
            need(body['limits'] == limits and body['charge_cpu_ns'] == CHARGE, 'partial or altered reservation')
            self.binding = clone(body)
            self.observe(body['clock'], body['parent_cpu_ns'])
            self.status = 'reserved'
        else:
            need(self.binding is not None, 'package is not reserved')
            if event == 'begin':
                legacy._closed(body, 'step allowance_cpu_ns clock parent_cpu_ns'.split(), 'QA step start')
                self.observe(body['clock'], body['parent_cpu_ns'])
                need(self.pending is None and len(self.steps) < len(STEPS) and
                     body['step'] == STEPS[len(self.steps)], 'missing, repeated or concurrent QA step')
                phase = body['step'][0]
                remaining = (WORKER if phase == 'B' else self.binding['limits'][phase]) - self.child_cpu[phase]
                integer(body['allowance_cpu_ns'], remaining)
                need(body['allowance_cpu_ns'] == remaining // NS * NS and remaining >= NS,
                     'child must receive only the whole-second remaining phase allowance')
                # Keep postscan wall time reserved before admitting the data worker.
                if phase == 'B':
                    need(self.binding['deadline_boot_ns'] - self.clock.boot_after_ns > WORKER + self.binding['limits']['C'],
                         'insufficient time for worker and required postscan')
                self.pending = clone(body)
                self.status = 'running'
            elif event == 'finish':
                legacy._closed(body, 'step child_cpu_ns child_peak_rss_bytes child_exit_code evidence_digest clock parent_cpu_ns'.split(), 'QA step finish')
                self.observe(body['clock'], body['parent_cpu_ns'])
                need(self.pending is not None and body['step'] == self.pending['step'], 'no matching actual child')
                integer(body['child_cpu_ns'], self.pending['allowance_cpu_ns'])
                integer(body['child_peak_rss_bytes'], 1024**3-1)
                need(type(body['child_exit_code']) is int and body['child_exit_code'] == 0,
                     'child did not actually finish successfully')
                legacy._digest(body['evidence_digest'], 'held complete child evidence')
                phase = body['step'][0]
                self.child_cpu[phase] += body['child_cpu_ns']
                need(self.child_cpu[phase] <= (WORKER if phase == 'B' else self.binding['limits'][phase]),
                     'cumulative phase CPU exceeded')
                self.steps.append(body['step'])
                self.pending = None
                self.status = 'reserved'
            elif event == 'complete':
                legacy._closed(body, 'clock parent_cpu_ns result_digest'.split(), 'QA completion')
                self.observe(body['clock'], body['parent_cpu_ns'])
                legacy._digest(body['result_digest'], 'complete result')
                need(self.pending is None and tuple(self.steps) == STEPS, 'incomplete package')
                self.status = 'complete'
            elif event == 'stop':
                # Stop is also allowed after timeout; never releases the charge.
                legacy._closed(body, 'reason'.split(), 'QA stop')
                need(type(body['reason']) is str and 0 < len(body['reason']) <= 200, 'bounded stop reason required')
                self.status = 'stopped'
            else:
                raise QaBudgetError('unknown QA event')
        self.head = legacy._hash(record)
        self.count += 1
        need(self.count <= 32, 'QA journal record bound')

    def snapshot(self):
        return dict(status=self.status, head=self.head, count=self.count,
                    charged_cpu_ns=0 if self.binding is None else CHARGE,
                    measured_child_cpu_ns=dict(self.child_cpu), measured_parent_cpu_ns=self.parent_cpu,
                    pending=clone(self.pending), completed_steps=list(self.steps), binding=clone(self.binding),
                    external_terminal_observation_required=True, native_pass=False)


def replay(raw):
    need(type(raw) is bytes and 0 < len(raw) <= 32*legacy.MAX_RECORD_BYTES and raw.endswith(b'\n'),
         'missing, partial or oversized QA journal')
    state = _State()
    lines = raw.splitlines(keepends=True)
    need(len(lines) <= 32, 'too many QA records')
    for line in lines:
        need(len(line) <= legacy.MAX_RECORD_BYTES, 'QA record is oversized')
        value = json.loads(line, object_pairs_hook=legacy._pairs,
                           parse_float=legacy._forbidden_number, parse_constant=legacy._forbidden_number,
                           parse_int=legacy._json_integer)
        need(legacy._canonical(value)+b'\n' == line, 'QA record is not canonical')
        state.apply(value)
    return state


class QaBudget:
    """Single-process protocol handle over a separately held durable journal."""
    def __init__(self, store, *, identity, history_digest, process_start_boot_ns, clock, parent_cpu,
                 authorization=AUTHORIZATION):
        self.store, self.clock, self.parent_cpu = store, clock, parent_cpu
        self.pid, self.failed, self.closed = os.getpid(), False, False
        self.lock = threading.Lock()
        self.state = _State()
        need(authorization in PROFILES, 'explicit authorized QA profile required')
        need(store.read() == b'', 'existing package cannot be restarted')
        sample = clock()
        binding = dict(authorization=authorization, identity=legacy._identity(identity),
                       history_digest=history_digest, start_boot_ns=process_start_boot_ns,
                       deadline_boot_ns=process_start_boot_ns+WALL, boot_id=sample.boot_id,
                       limits=dict(PROFILES[authorization]), charge_cpu_ns=CHARGE,
                       clock=legacy._clock(sample), parent_cpu_ns=parent_cpu())
        self._append('reserve', binding)

    def _check(self):
        need(not self.closed and not self.failed and self.pid == os.getpid(), 'lost original QA owner')
        actual = replay(self.store.read())
        need(actual.snapshot() == self.state.snapshot(), 'held QA journal changed')

    def _append(self, event, body):
        need(not self.closed and not self.failed and self.pid == os.getpid(), 'lost original QA owner')
        need(self.lock.acquire(blocking=False), 'concurrent QA accounting operation')
        try:
            if self.state.count:
                self._check()
            candidate = _State() if not self.state.count else replay(self.store.read())
            record = dict(format=FORMAT, sequence=candidate.count, previous=candidate.head, event=event, body=body)
            candidate.apply(record)
            self.store.append(legacy._canonical(record)+b'\n')
            # No admission until append, file+directory fsync and readback succeeded.
            actual = replay(self.store.read())
            need(actual.snapshot() == candidate.snapshot(), 'durable QA reservation differs')
            self.state = actual
        except BaseException:
            self.failed = True
            raise
        finally:
            self.lock.release()

    def _measurement(self):
        return dict(clock=legacy._clock(self.clock()), parent_cpu_ns=self.parent_cpu())

    def begin(self, step):
        self._check()
        need(type(step) is str and step in STEPS, 'unknown step')
        phase = step[0]
        limit = WORKER if phase == 'B' else self.state.binding['limits'][phase]
        allowance = (limit-self.state.child_cpu[phase]) // NS * NS
        self._append('begin', dict(step=step, allowance_cpu_ns=allowance, **self._measurement()))
        return allowance // NS

    def finish(self, step, *, child_cpu_ns, child_peak_rss_bytes, child_exit_code, evidence_digest):
        self._append('finish', dict(step=step, child_cpu_ns=child_cpu_ns,
            child_peak_rss_bytes=child_peak_rss_bytes, child_exit_code=child_exit_code,
            evidence_digest=evidence_digest, **self._measurement()))

    def complete(self, result_digest):
        self._append('complete', dict(result_digest=result_digest, **self._measurement()))

    def stop(self, reason):
        self._append('stop', dict(reason=reason))

    def snapshot(self):
        self._check()
        return self.state.snapshot()

    def close(self):
        if not self.closed:
            self.closed = True
            self.store.close()
