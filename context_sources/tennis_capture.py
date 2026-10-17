"""Opt-in daily-worker observer of existing ESPN JSON replies; never a fetch."""
from contextlib import contextmanager
from contextvars import ContextVar
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

from context_models.contracts import ContextContractError, canonical_timestamp, digest
from context_observations import append_observation_batch
from context_sources.tennis_status import normalize_tennis_status


_CURRENT = ContextVar("tennis_existing_response_capture", default=None)


def _receipt_now():
    return datetime.now(timezone.utc)


def _terminal_revision(rows, competition):
    """Same terminal facts in one feed, not a new result reception.

    ESPN repeats a tournament's complete draw in replies for different dates.
    Only the reception-derived fields are removed from this comparison. All
    native identities, schedules, scores, missing fields and winner flags stay.
    Scheduled/in-progress receipts must remain separate timing observations.
    This fingerprint is neither stored evidence nor a freshness assertion.
    """
    status = rows[0]
    if status['payload']['native_status']['state'] != 'post':
        return None
    facts = []
    for row in rows:
        content = dict(row)
        content.pop('valid_from')
        content.pop('source_revision')
        payload = dict(content['payload'])
        if content['kind'] == 'event_status':
            payload.pop('competition_revision')
            payload.pop('workload_receipts')
        elif content['kind'] == 'workload':
            payload.pop('result_observed_at')
        else:
            return None
        content['payload'] = payload
        facts.append(content)
    players = competition.get('competitors')
    winner_flags = ([player.get('winner') if type(player) is dict else None for player in players]
                    if type(players) is list else None)
    if winner_flags is not None and any(
            flag is not None and type(flag) is not bool for flag in winner_flags):
        # Malformed native flags remain ambiguous to the outcome normalizer.
        # An optional echo optimisation must not reject their source receipt
        # or turn an arbitrary/nonfinite provider value into a winner.
        return None
    return digest({'rows': facts, 'native_winner_flags': winner_flags})


def _terminal_receipt_fingerprints(rows):
    """Exact completed native facts INCLUDING known winner outcomes.

    Winner flags are not retained in status-v1. Therefore a final without a
    validated outcome is deliberately not eligible for persistent suppression.
    No first clock, actual end, missing winner or injury is inferred here.
    """
    from context_models.contracts import OBSERVATION_FIELDS
    from context_sources.tennis import SOURCE_SCHEMA
    from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt
    from context_sources.outcomes import validate_outcome_record, TENNIS_WINNER_OUTCOME
    from context_models.tennis import _joint_match_identity
    statuses = [row for row in rows if row['kind'] == 'event_status']
    work = [row for row in rows if row['kind'] == 'workload']
    outcomes = [row for row in rows if row['kind'] == 'match_outcome']
    if len(statuses) != 1 or len(work) != 2 or not outcomes or len(rows) != 3+len(outcomes):
        return None
    status = statuses[0]
    p = status['payload']
    if (status['source_schema'] != STATUS_SCHEMA or status['sport'] != 'tennis'
            or status['format'] != 'singles' or p['status'] != 'completed' or p['issues']
            or any(p['native_status'][flag] for flag in ('retired', 'walkover', 'unsupported'))):
        return None
    for row in (status, *work):
        validate_selected_tennis_receipt({**row, 'evidence_class': 'prospective',
            'effective_at': row['observed_at'], 'publication_resolution': None})
    players = set(p['participant_ids'])
    if (set(p['workload_receipts']) != {row['digest'] for row in work}
            or {row['subject_id'] for row in work} != players
            or len({_joint_match_identity(row) for row in work}) != 1
            or any(row['source_schema'] != SOURCE_SCHEMA or row['payload']['status'] != 'completed'
                or row['competition'] != status['competition']
                or row['schedule_revision'] != status['schedule_revision']
                or row['observed_at'] != status['observed_at'] for row in work)):
        return None
    winners = set()
    for row in outcomes:
        result = row['payload']
        if (result.get('outcome_contract') != TENNIS_WINNER_OUTCOME
                or {result.get('home_id'), result.get('away_id')} != players
                or result.get('reported_scheduled_start', result.get('scheduled_start')) != p['scheduled_start']
                or row['observed_at'] != status['observed_at']):
            return None
        event = {'event_key': row['event_key'], 'sport': 'tennis', 'competition': row['competition'],
            'format': row['format'], 'home_id': result['home_id'], 'away_id': result['away_id'],
            'scheduled_start': result['scheduled_start'], 'schedule_revision': row['schedule_revision'],
            'status': 'scheduled', 'tour': p['tour'], 'surface': None, 'indoor': None}
        validate_outcome_record({**row, 'evidence_class': 'prospective',
            'effective_at': row['observed_at'], 'publication_resolution': None}, event=event)
        winners.add(result['result']['winner_id'])
    if len(winners) != 1:
        return None
    fingerprints = {}
    for row in rows:
        content = {key: row[key] for key in OBSERVATION_FIELDS}
        content.pop('valid_from')
        content.pop('source_revision')
        payload = dict(content['payload'])
        if row['kind'] == 'event_status':
            payload.pop('competition_revision')
            payload.pop('workload_receipts')
        elif row['kind'] == 'workload':
            payload.pop('result_observed_at')
        content['payload'] = payload
        key = digest(content)
        if key in fingerprints:
            return None
        fingerprints[key] = row['digest']
    return fingerprints


def _persisted_terminal_reuse(connection, prepared):
    """Bounded latest-whole-reception comparison under B1's writer lock."""
    from context_observations import _SELECT, _decode_receipt
    current = tuple({**row, 'observed_at': clock, 'content_digest': content_hash,
        'digest': receipt_hash} for row, clock, content_hash, receipt_hash, _ in prepared)
    desired = _terminal_receipt_fingerprints(current)
    if desired is None:
        return {}
    key, clock = current[0]['event_key'], current[0]['observed_at']
    latest = connection.execute('SELECT max(observed_at) FROM context_observations WHERE event_key=?',
        (key,)).fetchone()[0]
    if latest is None or latest > clock:
        return {}
    admission = connection.execute('''SELECT count(*),coalesce(sum(length(c.payload)),0)
        FROM context_observations r LEFT JOIN context_contents c ON c.content_digest=r.content_digest
        WHERE r.event_key=? AND r.observed_at=?''', (key, latest)).fetchone()
    if admission[0] > 64 or admission[1] > 128*1024:
        return {}  # Optional optimisation; never turn unbounded history into an empty match.
    stored = tuple(_decode_receipt(row) for row in connection.execute(_SELECT+
        ' WHERE r.event_key=? AND r.observed_at=?', (key, latest)))
    previous = _terminal_receipt_fingerprints(stored)
    return ({ref: previous[fact] for fact, ref in desired.items()}
        if previous is not None and previous.keys() == desired.keys() else {})


def _expected_exclusion(status, competition):
    """Classify known out-of-scope draws, never make their rows modelable.

    ESPN returns doubles and explicit TBD bracket slots alongside singles.
    Their unchanged native unknown/retraction rows must still be persisted.
    Missing identities in a played match or a named singles pair remain errors.
    """
    payload = status["payload"]
    issues = set(payload["issues"])
    if (status["format"] == "unsupported"
            and payload["grouping_slug"] in {"mens-singles", "womens-singles",
                "mens-doubles", "womens-doubles", "mixed-doubles"}
            and issues <= {"unsupported-format", "unsupported-terminal", "invalid-participants"}):
        return "outside-singles-scope"
    if (status["format"] != "singles" or payload["status"] not in {"scheduled", "cancelled"}
            or issues != {"invalid-participants"}):
        return None
    players = competition.get("competitors")
    if type(players) is not list or len(players) != 2:
        return None
    missing = False
    for native_id, player in zip(payload["participant_ids"], players):
        if native_id is not None:
            continue
        missing = True
        athlete = player.get("athlete") if type(player) is dict else None
        raw_id = player.get("id") if type(player) is dict else None
        if (type(athlete) is not dict or athlete.get("displayName") != "TBD"
                or not (raw_id is None or type(raw_id) is str and re.fullmatch(r"-[1-9][0-9]*", raw_id))):
            return None
    return "unresolved-draw-slot" if missing else None


class _Capture:
    def __init__(self):
        self.pending, self.issues, self.refs = [], set(), set()
        self.exclusions = Counter()
        self.coverage_gaps = set()
        self.retired_outcome_events = set()
        self.native_unavailable_outcome_events = set()
        self.unresolved_outcome_events = set()
        self.identity_conflict_outcome_events = set()
        self._outcome_sources = {}
        self._last_terminal = {}
        self.unchanged_terminal_receptions = 0

    def report(self):
        return {"schema": 1, "scope": "existing-espn-tennis-responses",
            "status": "partial" if self.issues or self.coverage_gaps or self.native_unavailable_outcome_events
                else "captured" if self.refs else "no_receipts",
            "receipt_refs": sorted(self.refs), "issues": sorted(self.issues),
            "coverage_gaps": sorted(self.coverage_gaps),
            "excluded_competitions": dict(sorted(self.exclusions.items())),
            "retired_outcome_events": sorted(self.retired_outcome_events),
            "native_unavailable_outcome_events": sorted(self.native_unavailable_outcome_events),
            "identity_conflict_outcome_events": sorted(self.identity_conflict_outcome_events),
            "unchanged_terminal_receptions": self.unchanged_terminal_receptions,
            "unresolved_outcome_events": sorted(self.unresolved_outcome_events)}

    def record(self, tour, payload, *, observed_at):
        if type(tour) is not str or tour not in {"atp", "wta"}:
            self.issues.add("native-tour-unavailable")
            return
        if type(payload) is not dict or type(payload.get("events")) is not list:
            self.issues.add("native-response-unavailable")
            return
        for event in payload["events"]:
            if type(event) is not dict or type(event.get("groupings")) is not list:
                self.issues.add("native-grouping-unavailable")
                continue
            for group in event["groupings"]:
                if type(group) is not dict or type(group.get("competitions")) is not list:
                    self.issues.add("native-grouping-unavailable")
                    continue
                grouping = group.get("grouping")
                slug = grouping.get("slug") if type(grouping) is dict else None
                for competition in group["competitions"]:
                    try:
                        rows = normalize_tennis_status(tour.upper(), event.get("id"), competition,
                            grouping_slug=slug, observed_at=observed_at)
                    except (ContextContractError, TypeError, ValueError, OverflowError, KeyError):
                        # Without a native match ID there is no honest event
                        # alias to append. A known ID with bad fields is instead
                        # preserved by the status normalizer as a withdrawal.
                        self.issues.add("native-competition-unavailable")
                        continue
                    key = rows[0]['event_key']
                    revision = _terminal_revision(rows, competition)
                    clock = canonical_timestamp(observed_at)
                    previous = self._last_terminal.get(key)
                    if (revision is not None and previous is not None
                            and previous[0] == revision and previous[1] <= clock):
                        # Keep the first genuine receipt, never move its clock
                        # forward or turn an old result into a fresh fact. A
                        # correction/retraction between replies resets this.
                        self.unchanged_terminal_receptions += 1
                        continue
                    self._last_terminal[key] = (revision, clock)
                    index = len(self.pending)
                    self.pending.append((observed_at, rows))
                    from context_sources.tennis_outcome_capture import source_for_normal_winner
                    eligible, source = source_for_normal_winner(rows[0], competition)
                    if eligible:
                        self._outcome_sources[index] = source
                    elif (rows[0]["format"] == "singles"
                            and rows[0]["payload"]["status"] == "completed"
                            and rows[0]["payload"]["issues"] == ["terminal-workload-unavailable"]
                            and not any(rows[0]["payload"]["native_status"][flag]
                                for flag in ("retired", "walkover", "unsupported"))):
                        # Keep a possible original outcome on the collector's
                        # watch list; missing workload must not hide its label.
                        self._outcome_sources[index] = None
                    exclusion = _expected_exclusion(rows[0], competition)
                    if exclusion is not None:
                        self.exclusions[exclusion] += 1
                    else:
                        for issue in rows[0]["payload"]["issues"]:
                            if issue == "terminal-workload-unavailable":
                                self.coverage_gaps.add(rows[0]["event_key"])
                            elif issue not in {"unsupported-format", "unsupported-terminal"}:
                                self.issues.add(issue)

    def persist(self, path):
        from context_sources.tennis_outcome_capture import collect_outcomes
        outcomes, issues = collect_outcomes(path, self.pending, self._outcome_sources,
            retired_events=self.retired_outcome_events,
            native_unavailable_events=self.native_unavailable_outcome_events,
            unresolved_events=self.unresolved_outcome_events,
            identity_conflict_events=self.identity_conflict_outcome_events)
        self.issues.update(issues)
        chunk = []
        def append_chunk():
            refs = append_observation_batch(path, tuple(chunk), deduplicate_tennis_terminals=True)
            self.refs.update(refs)
            actual = {digest({'content_digest': digest(row),
                'observed_at': canonical_timestamp(at)}) for row, at in chunk if row['kind'] == 'event_status'}
            self.unchanged_terminal_receptions += len(actual-set(refs))
        for index, (observed, rows) in enumerate(self.pending):
            if index in outcomes:
                rows = (*rows, *outcomes[index])
            if len(rows) > 512:
                raise ContextContractError("one native competition exceeds the atomic receipt batch limit")
            # Keep one competition's status/workload together. The whole feed
            # may remain partial on interruption, but a committed chunk is
            # atomic and retains every original reception clock.
            if len(chunk) + len(rows) > 512:
                append_chunk()
                chunk = []
            chunk.extend((row, observed) for row in rows)
        if chunk:
            append_chunk()
        # An explicit drain ends this reception batch. A later real reception
        # in the same owner is new evidence; no cache crosses persistence.
        self._last_terminal.clear()


def observe_espn_response(tour, payload):
    """Called exactly at the existing successful JSON response boundary.

    Default callers do not read a clock, normalize, persist or start a worker.
    The request's actual tour scope is used, never a name/tournament inference.
    """
    current = _CURRENT.get()
    if current is not None:
        current.record(tour, payload, observed_at=_receipt_now())


def observe_espn_failure(tour):
    """Record an existing failed request; never initiate a request or a write."""
    current = _CURRENT.get()
    if current is not None:
        current.issues.add(f"native-response-unavailable:{tour}")


@contextmanager
def capture_tennis_worker(*, path=None):
    """Explicit CLI batch ownership; always drain received facts/reset scope."""
    if _CURRENT.get() is not None:
        raise ContextContractError("tennis capture already belongs to an active worker")
    if path is None:
        from runtime_paths import CONTEXT_MODEL_DB_PATH
        path = CONTEXT_MODEL_DB_PATH
    current = _Capture()
    token = _CURRENT.set(current)
    try:
        yield current
    finally:
        _CURRENT.reset(token)
        # Storage integrity exceptions escape outside the provider's legacy
        # ValueError/network exception handling; never disguise them as no data.
        current.persist(Path(path))
