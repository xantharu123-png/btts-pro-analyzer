"""Observed live-winner residual training, not a native historical state join.

The baseline is the actual pre-match, stored, reproducible app forecast. Native
status receipts bind today's players; they do NOT prove the legacy name-keyed
model's historical identities. Unknown environment is a separate population,
never a surface claim. D2 still has to qualify every effect on held-out events.
No network, database mutation, invented durations or automatic activation.
"""
from copy import deepcopy
from datetime import datetime
from contextlib import contextmanager
import math
import json
import sqlite3
from time import monotonic

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, original_base, validate_original_publication
from context_models.tennis_v3 import tennis_features_v3
from context_models.training_contracts import resolve_identity_map, validate_artifact_envelope
from context_models.replay import ReplayUnavailable
from context_observations import _SELECT, _check_selected_row, _decode_receipt
from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt
from model_artifacts import canonical_bytes


class _TennisBatchBudget:
    """One call's admission accounting, not a total-process RSS guarantee.

    Metadata charges include conservative Python container/index overhead;
    encoded history and unpublished output share the unchanged runtime cap.
    Optional diagnostic limits may only tighten that cap.
    """
    def __init__(self, seconds=45, *, started=None, selected_count=None,
                 selected_bytes_per_case=None, selected_bytes_total=None):
        from context_runtime import MAX_TENNIS_HISTORY_BYTES
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 1 <= seconds <= 600:
            raise ValueError('seconds must be between 1 and 600')
        for value in (selected_count, selected_bytes_per_case, selected_bytes_total):
            if value is not None and (type(value) is not int or not 1 <= value <= MAX_TENNIS_HISTORY_BYTES):
                raise ValueError('diagnostic batch limits must be positive lower-only integers')
        if started is not None and (type(started) not in (int, float) or not math.isfinite(started)
                                    or started > monotonic()):
            raise ValueError('batch start must be a prior finite monotonic clock')
        self.started = monotonic() if started is None else started
        self.seconds, self.limit = seconds, MAX_TENNIS_HISTORY_BYTES
        self.metadata_bytes = self.selected_bytes = self.output_bytes = 0
        self.selected_payload_bytes = self.selected_payload_bytes_total = 0
        self.selected_count = selected_count
        self.selected_bytes_per_case = selected_bytes_per_case
        self.selected_bytes_total = selected_bytes_total
        self.sql_cancelled = False

    def check(self):
        if monotonic()-self.started > self.seconds:
            raise TimeoutError('native tennis batch time budget exhausted')
        if self.metadata_bytes+self.selected_bytes+self.output_bytes > self.limit:
            raise ValueError('native tennis batch retention byte budget exhausted')

    def charge_metadata(self, amount):
        self.metadata_bytes += amount
        self.check()

    def admit_selected(self, count, payload_bytes):
        self.selected_payload_bytes = payload_bytes
        self.selected_payload_bytes_total += payload_bytes
        if ((self.selected_count is not None and count > self.selected_count)
                or (self.selected_bytes_per_case is not None and payload_bytes > self.selected_bytes_per_case)
                or (self.selected_bytes_total is not None and self.selected_payload_bytes_total > self.selected_bytes_total)):
            raise ValueError('native tennis batch selected byte/count budget exhausted')
        # Reserve encoded receipt envelopes and indexes before fetching bodies.
        self.selected_bytes = payload_bytes+count*2048
        self.check()

    def sql_progress(self):
        self.sql_cancelled = monotonic()-self.started > self.seconds
        return int(self.sql_cancelled)


@contextmanager
def _batch_reader(path, budget):
    from context_models.dataset import _reader
    try:
        with _reader(path) as connection:
            connection.set_progress_handler(budget.sql_progress, 10000)
            try:
                budget.check()
                yield connection
                budget.check()
            finally:
                connection.set_progress_handler(None, 0)
    except ContextIntegrityError as exc:
        cause = exc.__cause__
        if (budget.sql_cancelled and isinstance(cause, sqlite3.OperationalError)
                and getattr(cause, 'sqlite_errorcode', None) == sqlite3.SQLITE_INTERRUPT):
            raise TimeoutError('native tennis batch time budget exhausted') from exc
        raise


class _TennisBatchDiscovery:
    """Transaction-local small membership index, never a receipt validation flag."""
    def __init__(self, connection, cases, budget, membership_mode):
        self.connection, self.budget = connection, budget
        self.membership_mode = membership_mode
        self.membership = {}
        if membership_mode == 'indexed':
            from context_tennis_index import _verified_index_state
            _verified_index_state(connection)
            return
        players = sorted({(event['tour'], player) for event, _ in cases
                          for player in (event['home_id'], event['away_id'])})
        clock = max(cutoff for _, cutoff in cases)
        requested = set(players)
        tours = {tour for tour, _ in players}
        # Restrict physical receipt candidates BEFORE touching source JSON.
        # Only small SQL metadata are grouped; source bodies are never spooled.
        query = """WITH receipt_candidates AS MATERIALIZED (
            SELECT content_digest,event_key,MIN(observed_at) AS first_seen
            FROM context_observations
            WHERE source='espn' AND kind IN ('event_status','workload') AND observed_at<=?
            GROUP BY content_digest,event_key)
            SELECT r.event_key,r.first_seen,
                json_extract(CAST(c.payload AS TEXT),'$.payload.tour','$.payload.player_id',
                             '$.payload.opponent_id','$.payload.participant_ids')
            FROM receipt_candidates r JOIN context_contents c ON c.content_digest=r.content_digest"""
        budget.charge_metadata(1024+sum(512+sum(len(v.encode('utf8')) for v in pair) for pair in players))
        for key, first_seen, projection in connection.execute(query, (clock,)):
            budget.check()
            # One small projection per candidate content, not one JSON pass per
            # requested player. Unmatched projections are immediately discarded.
            projected_bytes = sum(len(value.encode('utf8')) for value in (key, first_seen, projection))
            if budget.metadata_bytes+budget.output_bytes+projected_bytes+2048 > budget.limit:
                raise ValueError('native tennis batch lookup byte budget exhausted')
            tour, player, opponent, participants = json.loads(projection)
            if type(tour) is not str or tour not in tours:
                continue
            participants = (participants.values() if type(participants) is dict else participants
                            if type(participants) is list else (participants,))
            matching = {value for group in ((player, opponent), participants) for value in group
                        if type(value) is str and (tour, value) in requested}
            for player in matching:
                identity = (tour, player, key)
                previous = self.membership.get(identity)
                if previous is None:
                    budget.charge_metadata(1024+sum(len(value.encode('utf8')) for value in (*identity, first_seen)))
                if previous is None or first_seen < previous:
                    self.membership[identity] = first_seen

    def prepare(self, event, cutoff):
        from tennis.history_projection import PreparedTennisHistory
        budget = self.budget
        keys = {event['event_key']}
        if self.membership_mode == 'indexed':
            from context_tennis_index import _player_membership_candidates, player_event_keys
            selection = dict(tour=event['tour'], player_ids=(event['home_id'], event['away_id']), cutoff=cutoff)
            budget.charge_metadata(1536+len(event['event_key'].encode('utf8')))
            for member in _player_membership_candidates(self.connection, **selection):
                budget.check()
                if member[2] not in keys:
                    budget.charge_metadata(512+len(member[2].encode('utf8')))
                    keys.add(member[2])
        else:
            keys.update(key for (tour, player, key), first in self.membership.items()
                        if tour == event['tour'] and player in (event['home_id'], event['away_id']) and first <= cutoff)
        budget.check()
        count = payload_bytes = 0
        for key in sorted(keys):
            budget.check()
            row = self.connection.execute("""SELECT COUNT(*),COALESCE(SUM(LENGTH(c.payload)),0)
                FROM context_observations r LEFT JOIN context_contents c ON c.content_digest=r.content_digest
                WHERE r.event_key=? AND r.observed_at<=? AND r.source='espn'
                AND r.kind IN ('event_status','workload')""", (key, cutoff)).fetchone()
            count += row[0]
            payload_bytes += row[1]
        budget.admit_selected(count, payload_bytes)
        if self.membership_mode == 'indexed':
            # Only metadata was touched above. Admit the complete history before
            # the public owner opens even the first native membership proof.
            proved = set(player_event_keys(self.connection, **selection)) | {event['event_key']}
            if proved != keys:
                raise ContextIntegrityError('indexed membership changed within its held snapshot')
            budget.check()
        encoded = 0
        def rows():
            nonlocal encoded
            for key in sorted(keys):
                for raw in self.connection.execute(_SELECT+" WHERE r.event_key=? AND r.observed_at<=?"
                        " AND r.source='espn' AND r.kind IN ('event_status','workload') ORDER BY r.observed_at,r.digest",
                        (key, cutoff)):
                    budget.check()
                    row = _decode_receipt(raw)
                    row.update(evidence_class='prospective', effective_at=row['observed_at'], publication_resolution=None)
                    if row['payload']['tour'] != event['tour']:
                        raise ContextIntegrityError('native match revision crosses tennis tours')
                    encoded += len(canonical_bytes(row))+2048
                    if encoded > budget.selected_bytes:
                        budget.selected_bytes = encoded
                        budget.check()
                    yield row
        owner = PreparedTennisHistory.from_selected_rows(rows())
        budget.check()
        return owner


def iter_live_tennis_features(connection, origins, *, budget, feature_version='tennis-performed-load-v4',
                              membership_mode='indexed'):
    """Actual readiness/training feature consumer in its caller's read transaction.

    Yields one validated history owner at a time. No outcome is read, no mutable
    owner is reused between cases, and no validation scope escapes a feature call.
    """
    _validate_membership_mode(membership_mode)
    if type(origins) is not tuple or not 1 <= len(origins) <= 100:
        raise ValueError('feature batch requires 1 to 100 explicit frozen origins')
    if not connection.in_transaction:
        raise ContextContractError('tennis feature batch requires its owning read transaction')
    from context_models.tennis_v4 import live_tennis_features
    cases = tuple((origin['event'], canonical_timestamp(origin['cutoff'])) for origin in origins)
    discovery = _TennisBatchDiscovery(connection, cases, budget, membership_mode)
    for origin, (event, cutoff) in zip(origins, cases):
        budget.check()
        owner = discovery.prepare(event, cutoff)
        with owner.feature_scope(event) as history:
            features = live_tennis_features(feature_version, event, history, original_base(origin),
                                           cutoff=datetime.fromisoformat(cutoff))
            budget.check()
        yield owner, history, features
        del owner, history, features
        budget.selected_bytes = 0
    budget.check()


def _validate_membership_mode(mode):
    if type(mode) is not str or mode not in {'indexed', 'legacy'}:
        raise ValueError('membership_mode must be indexed or legacy')


def build_live_training_cases(path, requests, *, config, as_of, seconds=45, membership_mode='indexed'):
    """Build an unpublished bounded case tuple with one actual B1 transaction."""
    started = monotonic()
    _validate_membership_mode(membership_mode)
    budget = _TennisBatchBudget(seconds, started=started)
    from context_models.dataset import _artifact, _receipt
    from context_models.training_contracts import validate_family_config, validate_resolved_case
    from context_models.contracts import require_digest
    if type(requests) not in (list, tuple) or not 1 <= len(requests) <= 100:
        raise ValueError('training batch requires 1 to 100 explicit requests')
    frozen = []
    for request in requests:
        if type(request) is not dict or set(request) != {'original_ref', 'outcome_ref', 'identity_ref'}:
            raise ValueError('training batch requires exact original/outcome/identity requests')
        for ref in request.values():
            require_digest(ref)
        frozen.append(deepcopy(request))
    frozen = tuple(frozen)
    config, clock = validate_family_config(config), canonical_timestamp(as_of)
    budget.charge_metadata(len(canonical_bytes(frozen))+len(canonical_bytes(config))+4096)
    with _batch_reader(path, budget) as connection:
        origins = []
        for request in frozen:
            budget.check()
            original = _artifact(connection, request['original_ref'], ORIGINAL_ARTIFACT_KIND, latest=clock)
            origin = original['payload']['origin']
            original_base(origin)
            budget.charge_metadata(len(canonical_bytes(origin))+2048)
            origins.append(origin)
        results = []
        for _, history, features in iter_live_tennis_features(connection, tuple(origins), budget=budget,
                                                              feature_version=config['feature_version'],
                                                              membership_mode=membership_mode):
            request, origin = frozen[len(results)], origins[len(results)]
            budget.check()
            payload = {'schema': 1, 'event': origin['event'], 'base': original_base(origin), 'features': features,
                'replay_ref': request['original_ref'], 'outcome_ref': request['outcome_ref'],
                'event_identity_hash': request['identity_ref'], 'family_config_hash': digest(config), 'preprocessing_refs': []}
            artifacts = live_case_artifacts(connection, payload, latest=clock)
            outcome = _receipt(connection, request['outcome_ref'])
            if outcome['observed_at'] > clock:
                raise ContextIntegrityError('outcome was received after case construction')
            outcome.update(effective_at=outcome['observed_at'], evidence_class='prospective', publication_resolution=None)
            case = {'kind': 'context-training-case-v1', 'payload': payload}
            resolved = {'case': {'digest': digest(case), **case}, 'artifacts': artifacts, 'observations': history+(outcome,)}
            try:
                result = validate_resolved_case(resolved, config=config)
            except ReplayUnavailable:
                result = deepcopy(resolved)
            budget.output_bytes += len(canonical_bytes(result))+4096
            budget.check()
            results.append(result)
            # Do not keep the yielded encoded owner alive while the generator
            # prepares the next case. Required resolved output remains owned.
            del _, history, features
        budget.check()
        return tuple(results)


def _same(actual, expected, message):
    if canonical_bytes(actual) != canonical_bytes(expected):
        raise ContextIntegrityError(message)


def relevant_receipts(connection, event, cutoff):
    """All revisions of any native match ever associated with either player.

    This is equivalent to v3's participant filter, not 'take latest wins'. A
    correction removing a participant stays included. Only context bodies are
    opened; match-outcome labels and other sports are never selected here.
    """
    clock = canonical_timestamp(cutoff)
    keys = {event["event_key"]}
    params = {"cutoff": clock, "tour": event["tour"], "home": event["home_id"], "away": event["away_id"]}
    query = """SELECT DISTINCT r.event_key FROM context_observations r
        JOIN context_contents c ON c.content_digest=r.content_digest
        WHERE r.source='espn' AND r.kind IN ('event_status','workload') AND r.observed_at<=:cutoff
        AND json_extract(CAST(c.payload AS TEXT),'$.payload.tour')=:tour
        AND (json_extract(CAST(c.payload AS TEXT),'$.payload.player_id') IN (:home,:away)
          OR json_extract(CAST(c.payload AS TEXT),'$.payload.opponent_id') IN (:home,:away)
          OR EXISTS (SELECT 1 FROM json_each(CAST(c.payload AS TEXT),'$.payload.participant_ids')
                     WHERE value IN (:home,:away)))"""
    keys.update(row[0] for row in connection.execute(query, params))
    selected = []
    for key in sorted(keys):
        for raw in connection.execute(_SELECT + " WHERE r.event_key=? AND r.observed_at<=?"
                " AND r.source='espn' AND r.kind IN ('event_status','workload') ORDER BY r.observed_at,r.digest",
                (key, clock)):
            row = _decode_receipt(raw)
            row.update(evidence_class="prospective", effective_at=row["observed_at"], publication_resolution=None)
            validate_selected_tennis_receipt(row)
            if row["payload"]["tour"] != event["tour"]:
                raise ContextIntegrityError("native match revision crosses tennis tours")
            selected.append(row)
    return tuple(sorted(selected, key=lambda row: (row["observed_at"], row["digest"])))


def live_case_artifacts(connection, payload, *, latest):
    """Resolve physical publication clocks, not just hash-shaped metadata."""
    from context_models.dataset import _artifact, _receipt
    from context_models.experiments import _artifact_created_at
    original = _artifact(connection, payload["replay_ref"], ORIGINAL_ARTIFACT_KIND, latest=latest)
    created = _artifact_created_at(connection, original["digest"])
    publication = validate_original_publication(original["payload"], created_at=created)
    base = original_base(publication["origin"])
    _same(base, payload["base"], "case differs from actual published original")
    _same(publication["origin"]["event"], payload["event"], "case differs from original event")
    if created >= payload["event"]["scheduled_start"]:
        raise ContextIntegrityError("training original was not stored before scheduled start")
    from context_sources.outcomes import validate_outcome_record
    outcome = _receipt(connection, payload["outcome_ref"])
    outcome.update(effective_at=outcome["observed_at"], evidence_class="prospective", publication_resolution=None)
    outcome = validate_outcome_record(outcome, event=payload["event"])
    reported = outcome["payload"].get("reported_scheduled_start", payload["event"]["scheduled_start"])
    if created >= reported:
        raise ContextIntegrityError("training original was not stored before reported native start")
    state = _artifact(connection, base["model_hash"], "tennis-tour-state", latest=base["cutoff"])
    identity = _artifact(connection, payload["event_identity_hash"], "context-native-identity-map-v1", latest=latest)
    return {item["digest"]: item for item in (original, state, identity)}


def validate_live_training_case(resolved, *, config, payload):
    from context_models.tennis_effect import _feature_input
    from context_models.offset import ContextModelError
    from context_sources.outcomes import validate_outcome_record
    from context_runtime_tennis import (
        _code_manifest_supported, _code_variants, _native_event, _state_code_manifest_supported,
    )
    from tennis.predict import predict_match
    from tennis.tour_state import _decode_wrapper
    event, base, features = (payload[name] for name in ("event", "base", "features"))
    decision = base["cutoff"]
    artifacts = resolved["artifacts"]
    expected = {payload["replay_ref"], base["model_hash"], payload["event_identity_hash"]}
    if type(artifacts) is not dict or set(artifacts) != expected:
        raise ContextIntegrityError("live case lacks its exact original, tour state or native map")
    original = validate_artifact_envelope(artifacts[payload["replay_ref"]], kind=ORIGINAL_ARTIFACT_KIND)
    origin = original["payload"]["origin"]
    _same(original["payload"], {"schema": 1, "origin": origin}, "unknown original publication fields")
    _same(original_base(origin), base, "case substituted its original live forecast")
    _same(origin["event"], event, "live case changed the original native event")
    for ref, artifact in artifacts.items():
        if artifact.get("digest") != ref:
            raise ContextIntegrityError("miskeyed original artifact")
    state_envelope = validate_artifact_envelope(artifacts[base["model_hash"]], kind="tennis-tour-state")
    state = _decode_wrapper(state_envelope["payload"], event["tour"])
    if state.built_at > datetime.fromisoformat(decision).timestamp():
        raise ContextIntegrityError("original tour state was built after the decision")
    variants = _code_variants()
    if not _code_manifest_supported(origin["code_hashes"], variants):
        raise ContextIntegrityError("original calculation has no supported exact source replay")
    if not _state_code_manifest_supported(origin["code_hashes"], state):
        raise ContextIntegrityError("point joint Tennis state lacks its reviewed versioned code identity")
    if type(resolved["observations"]) is not tuple:
        raise ContextContractError("live training requires immutable source receipts")
    by_ref, history, outcomes = {}, [], []
    for row in resolved["observations"]:
        _check_selected_row(row)
        if row["digest"] in by_ref:
            raise ContextIntegrityError("duplicate physical live training receipt")
        by_ref[row["digest"]] = row
        if row["kind"] == "match_outcome":
            outcomes.append(row)
            continue
        if row["observed_at"] > decision or row["effective_at"] > decision or row["evidence_class"] != "prospective":
            raise ReplayUnavailable("late_feature_receipt_is_not_predecision_evidence")
        validate_selected_tennis_receipt(row)
        if row["payload"]["tour"] != event["tour"]:
            raise ContextIntegrityError("live training includes another tour")
        history.append(row)
    if len(outcomes) != 1 or outcomes[0]["digest"] != payload["outcome_ref"]:
        raise ContextIntegrityError("live case must resolve exactly its own frozen outcome")
    outcome = validate_outcome_record(outcomes[0], event=event)
    if decision >= outcome["payload"].get("reported_scheduled_start", event["scheduled_start"]):
        raise ContextIntegrityError("original decision follows the later reported native start")
    if outcome["observed_at"] <= decision or outcome["payload"]["outcome_contract"] != config["outcome_contract"]:
        raise ContextIntegrityError("live outcome is not a later normal winner of this contract")
    identity = resolve_identity_map(artifacts[payload["event_identity_hash"]],
        observations=tuple(history), event_keys=(event["event_key"],))
    binding = next(row for row in identity["payload"]["bindings"] if row["event_key"] == event["event_key"])
    _same(binding, {"event_key": event["event_key"], "home_id": event["home_id"], "away_id": event["away_id"],
        "source_refs": [origin["native_receipt"]]}, "live identity map differs from original source binding")
    target = [row for row in history if row["event_key"] == event["event_key"]]
    newest = max((row["observed_at"] for row in target), default=None)
    latest = [row for row in target if row["observed_at"] == newest]
    if (len(latest) != 1 or latest[0]["digest"] != origin["native_receipt"]
            or latest[0]["source_schema"] != STATUS_SCHEMA
            or latest[0]["observed_at"] != origin["native_observed_at"]
            or latest[0]["payload"]["competition_revision"] != origin["competition_revision"]
            or latest[0]["payload"]["status"] != "scheduled" or latest[0]["payload"]["issues"]):
        raise ContextIntegrityError("original native target was missing, conflicting or superseded")
    _same(_native_event(latest[0]), event, "original native target differs from case")
    captures = []
    predict_match(state, **{key: origin["inputs"][key] for key in (
        "player_a", "player_b", "surface", "best_of", "tour", "indoor")},
        as_of=datetime.fromisoformat(decision), workload_history=(), original_capture=captures.append)
    _same(captures, [{"inputs": origin["inputs"], "values": origin["values"]}],
        "stored original does not reproduce from the actual tour model")
    from context_models.tennis_v4 import live_tennis_features
    rebuilt = live_tennis_features(config["feature_version"], event, tuple(history), base, cutoff=datetime.fromisoformat(decision))
    _same(rebuilt, features, "live feature vector differs from causal source receipts")
    if features["coverage"] != config["coverage"]:
        raise ReplayUnavailable("feature_coverage_outside_frozen_cohort")
    try:
        _feature_input(features, config["feature_names"], family="tennis:winner")
    except ContextModelError as exc:
        raise ReplayUnavailable("consumed_feature_unavailable") from exc
    return deepcopy(resolved)


def build_live_training_case(path, *, original_ref, outcome_ref, identity_ref, config, as_of):
    """Build, do not publish, a case from existing immutable app receipts.

    Caller freezes one native event/decision per cohort before evaluation.
    This function never picks profitable results or an alpha, and cannot
    manufacture an original for a match which was not actually predicted.
    """
    from context_models.dataset import _artifact, _reader, _receipt
    from context_models.training_contracts import validate_family_config, validate_resolved_case
    config = validate_family_config(config)
    clock = canonical_timestamp(as_of)
    with _reader(path) as connection:
        original = _artifact(connection, original_ref, ORIGINAL_ARTIFACT_KIND, latest=clock)
        origin = original["payload"]["origin"]
        base, event = original_base(origin), origin["event"]
        history = relevant_receipts(connection, event, base["cutoff"])
        from context_models.tennis_v4 import live_tennis_features
        features = live_tennis_features(config["feature_version"], event, history, base, cutoff=datetime.fromisoformat(base["cutoff"]))
        payload = {"schema": 1, "event": event, "base": base, "features": features, "replay_ref": original_ref,
            "outcome_ref": outcome_ref, "event_identity_hash": identity_ref, "family_config_hash": digest(config),
            "preprocessing_refs": []}
        artifacts = live_case_artifacts(connection, payload, latest=clock)
        outcome = _receipt(connection, outcome_ref)
        if outcome["observed_at"] > clock:
            raise ContextIntegrityError("outcome was received after case construction")
        outcome.update(effective_at=outcome["observed_at"], evidence_class="prospective", publication_resolution=None)
        case = {"kind": "context-training-case-v1", "payload": payload}
        resolved = {"case": {"digest": digest(case), **case}, "artifacts": artifacts, "observations": history+(outcome,)}
        try:
            return validate_resolved_case(resolved, config=config)
        except ReplayUnavailable:
            # Keep a structurally verified original with insufficient context
            # in the requested inventory. D1 records the explicit exclusion;
            # D2 treats an unavailable ready case as a failure, not a favorable
            # silently smaller holdout. Integrity errors are never swallowed.
            return deepcopy(resolved)
