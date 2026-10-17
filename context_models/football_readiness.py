"""Bounded preparation of native football context cases in an offline store.

The input inventory is explicit. There is no provider call, global receipt scan,
source backdating, invented zero, or active-manifest publication here. Readiness
is an administrative source-availability result, not empirical qualification.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import re

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp, digest,
    event_in_population, require_digest, require_object,
)
from context_models.dataset import _artifact, _reader, validate_dataset
from context_models.football_joint_context import (
    BASE_VERSION, FEATURE_VERSION, POOLED_FEATURE_VERSION, PLAYER_LOAD_FEATURE_VERSION, VERSION, joint_features,
)
from context_models.football_original_publication import BINDING_KIND
from context_models.football_training import _load_publication, _original_envelope, build_joint_training_case, joint_base, joint_source_scope_kwargs
from context_models.replay import ReplayUnavailable
from context_models.training import fit_family, split_windows
from context_models.training_cases import assemble_training_cases
from context_models.training_contracts import validate_family_config, validate_identity_map
from context_observations import _SELECT, _decode_receipt
from football_joint_worker import _bounded_receipts, _native_binding
from model_artifacts import canonical_bytes, put_artifact
from runtime_paths import RUNTIME_STATE_DIR, _assert_no_symlink_components

MAX_EVENTS = 1024
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_BINDING_BYTES = 512 * 1024
MAX_OUTCOME_REVISIONS = 64
MAX_OUTCOME_BYTES = 64 * 1024
MAX_EVALUATION_RECEIPTS = 100000
MAX_EVALUATION_BYTES = 128 * 1024 * 1024
MAX_STREAM_TRAINING_BYTES = 128 * 1024 * 1024


class _PhysicalInputs:
    """One reader image; admission caches lengths, never decoded mutable data."""
    def __init__(self, connection, *, source_transport=None):
        self.connection, self.seen, self.size = connection, {}, 0
        self.limit = MAX_INPUT_BYTES
        if source_transport is not None:
            from context_models.football_source_stream import SOURCE_TRANSPORT, MAX_RAW_BYTES
            if source_transport != SOURCE_TRANSPORT:
                raise ContextContractError('unknown football preparation source transport')
            self.limit = MAX_RAW_BYTES

    def admit(self, table, ref):
        require_digest(ref)
        key_column = {'artifacts': 'digest', 'context_contents': 'content_digest'}[table]
        header = self.connection.execute(
            f'SELECT typeof(payload),length(CAST(payload AS BLOB)) FROM {table} WHERE {key_column}=?',
            (ref,)).fetchone()
        if header is None or header[0] != 'blob' or type(header[1]) is not int or header[1] <= 0:
            raise ContextIntegrityError('preparation input has missing or invalid physical content')
        key = (table, ref)
        if key not in self.seen:
            if self.size + header[1] > self.limit:
                raise ReplayUnavailable('preparation_total_byte_bound_exceeded')
            self.seen[key] = header[1]
            self.size += header[1]
        elif self.seen[key] != header[1]:
            raise ContextIntegrityError('preparation physical input changed within reader image')


def _inventory(requests):
    if type(requests) is not tuple or len(requests) > MAX_EVENTS:
        raise ContextContractError("football preparation needs a bounded explicit tuple of events")
    seen, result = set(), []
    for value in requests:
        require_object(value, {"binding_ref"}, optional={"decision_ref"}, label="football preparation input")
        ref = require_digest(value["binding_ref"], "original binding")
        if ref in seen:
            raise ContextContractError("duplicate original binding in preparation inventory")
        seen.add(ref)
        decision_ref = value.get("decision_ref")
        if decision_ref is not None:
            require_digest(decision_ref, "stored native context decision")
        result.append({"binding_ref": ref, "decision_ref": decision_ref})
    return tuple(result)


def _phase(decision, config, blocks):
    if decision < config["train_end"]:
        return "train"
    if decision < config["tune_end"]:
        return "tune"
    return next((f"test:{i}" for i, (start, end) in enumerate(blocks)
                 if start <= decision < end), "outside")


def _configuration(config, test_blocks, *, source_transport=None):
    config = validate_family_config(config)
    allowed_variant, allowed_base = {VERSION}, {BASE_VERSION}
    if source_transport is not None:
        from context_models.football_source_stream import SOURCE_TRANSPORT
        from context_models.football_joint_context import VERSIONS, BASE_VERSIONS
        if source_transport != SOURCE_TRANSPORT:
            raise ContextContractError('unknown football preparation source transport')
        allowed_variant, allowed_base = VERSIONS, BASE_VERSIONS
    if (config["sport"] != "football" or config["feature_version"] not in {FEATURE_VERSION, POOLED_FEATURE_VERSION, PLAYER_LOAD_FEATURE_VERSION}
            or config["model_variant"] not in allowed_variant or len(config["base_versions"]) != 1
            or config["base_versions"][0] not in allowed_base):
        raise ContextContractError("football preparation owns only the source-bound joint model")
    _, _, blocks = split_windows(train_end=datetime.fromisoformat(config["train_end"]),
        tune_end=datetime.fromisoformat(config["tune_end"]), test_blocks=test_blocks)
    return config, blocks


def _bounded_outcome(connection, event, *, latest, ledger=None):
    """Inspect only this native event's bounded final receipts, never a corpus."""
    headers = connection.execute(
        "SELECT r.digest,r.observed_at,typeof(c.payload),length(CAST(c.payload AS BLOB)) "
        "FROM context_observations r LEFT JOIN context_contents c ON c.content_digest=r.content_digest "
        "WHERE r.event_key=? AND r.kind='match_outcome' AND r.observed_at<=? "
        "ORDER BY r.observed_at,r.digest LIMIT ?", (event["event_key"], latest, MAX_OUTCOME_REVISIONS+1),
    ).fetchall()
    if len(headers) > MAX_OUTCOME_REVISIONS:
        raise ReplayUnavailable("outcome_revision_bound_exceeded")
    if not headers:
        return None, 0
    rows, size = [], 0
    for ref, _, storage_type, length in headers:
        if storage_type != "blob" or type(length) is not int or length <= 0:
            raise ContextIntegrityError("native outcome content is missing or not canonical bytes")
        size += length
        if size > MAX_OUTCOME_BYTES:
            raise ReplayUnavailable("outcome_byte_bound_exceeded")
        if ledger is not None:
            content_ref = connection.execute('SELECT content_digest FROM context_observations WHERE digest=?', (ref,)).fetchone()[0]
            ledger.admit('context_contents', content_ref)
        row = connection.execute(_SELECT+" WHERE r.digest=?", (ref,)).fetchone()
        if row is None or type(row[-1]) is not bytes or len(row[-1]) != length:
            raise ContextIntegrityError("native outcome differs from its physical header")
        decoded = _decode_receipt(row)
        decoded.update(evidence_class="prospective", effective_at=decoded["observed_at"], publication_resolution=None)
        rows.append(decoded)
    # Validate every selected receipt. An invalid old revision must not be
    # laundered by simply choosing a convenient newer hash.
    from context_sources.outcomes import validate_outcome_record
    for row in rows:
        validate_outcome_record(row, event=event)
    clock = max(row["observed_at"] for row in rows)
    candidates = [row for row in rows if row["observed_at"] == clock]
    if any(canonical_bytes(row["payload"]) != canonical_bytes(candidates[0]["payload"])
           for row in candidates):
        raise ContextIntegrityError("same-clock native outcomes contradict each other")
    return candidates[0], size


def _actual_decision(connection, request, binding, original, *, latest, ledger=None):
    """A later context decision needs an actual immutable worker reference."""
    decision = binding["decision_at"]
    if request["decision_ref"] is not None:
        from football_context_decisions import MAX_DECISION_BYTES, resolve_decision
        ref = request["decision_ref"]
        header = connection.execute("SELECT typeof(payload),length(CAST(payload AS BLOB)) FROM artifacts WHERE digest=?", (ref,)).fetchone()
        if header is None or header[0] != "blob" or type(header[1]) is not int or not 0 < header[1] <= MAX_DECISION_BYTES:
            raise ContextIntegrityError("native context decision is absent or exceeds its bounded envelope")
        if ledger is not None:
            ledger.admit('artifacts', ref)
        payload = resolve_decision(connection, ref, latest=latest)["payload"]
        if payload["binding_ref"] != request["binding_ref"] or payload["event_key"] != binding["native_event"]["event_key"]:
            raise ContextIntegrityError("native context decision belongs to another original")
        return payload["decision_at"], payload
    return decision, None


def _inspect(path, requests, config, blocks, *, as_of, source_transport=None):
    clock = canonical_timestamp(as_of)
    report = {"schema": 1, "scope": "football-native-context-readiness-v1", "evaluated_at": clock,
        "requested_events": len(requests), "inspected_events": 0, "input_payload_bytes": 0,
        "input_byte_accounting": "unique-physical-payload-v1", "retained_training_payload_bytes": 0,
        "events": [], "phase_counts": {key: 0 for key in ("train", "tune", "test:0", "test:1", "test:2", "outside")},
        "source_complete_events": 0, "feature_complete_events": 0, "outcome_events": 0,
        "test_events": 0, "minimum_test_events": 200, "empirical_qualification": "not_evaluated"}
    training_limit = MAX_INPUT_BYTES if source_transport is None else MAX_STREAM_TRAINING_BYTES
    if source_transport is not None:
        report.update(scope='football-native-context-readiness-v2', source_transport=source_transport,
                      retained_training_byte_limit=training_limit)
    entries, bindings, seen, retained = [], [], set(), []
    with _reader(Path(path)) as connection:
        ledger = _PhysicalInputs(connection, source_transport=source_transport)
        for request in requests:
            ref = request["binding_ref"]
            item = {"binding_ref": ref, "status": "source_unavailable", "reason": None}
            header = connection.execute("SELECT typeof(payload),length(CAST(payload AS BLOB)) FROM artifacts WHERE digest=?", (ref,)).fetchone()
            if header is None or header[0] != "blob" or type(header[1]) is not int or header[1] <= 0:
                raise ContextIntegrityError("requested original binding is missing or invalid")
            if header[1] > MAX_BINDING_BYTES:
                raise ContextIntegrityError("requested binding exceeds its owning payload bound")
            try:
                envelope, original, code = _load_publication(connection, ref, latest=clock, admit=ledger.admit)
                binding, packet = envelope["payload"], original.to_dict()
                decision, decision_proof = _actual_decision(connection, request, binding, original, latest=clock, ledger=ledger)
                base = joint_base(original, binding, decision_at=datetime.fromisoformat(decision))
                if config['feature_version'] == PLAYER_LOAD_FEATURE_VERSION and decision_proof is not None:
                    raise ReplayUnavailable("player_load_requires_original_decision")
                streamed = None
                if source_transport is None:
                    rows = _bounded_receipts(connection, packet, cutoff=decision,
                        **joint_source_scope_kwargs(config['feature_version']))
                else:
                    from context_models.football_source_stream import streamed_joint_sources
                    streamed = streamed_joint_sources(connection, packet, binding, base,
                        feature_version=config['feature_version'], ledger=ledger)
                    rows = streamed['observations']
                    item['source_processing'] = streamed['audit']
                # The owning source resolver admits its unchanged per-case pool
                # before decoding it. One bounded pool may exist transiently
                # before this cumulative physical-IO admission rejects it.
                for row in rows:
                    ledger.admit('context_contents', row['content_digest'])
                if decision_proof is not None:
                    if source_transport is not None:
                        raise ReplayUnavailable('stream_transport_requires_original_decision')
                    refs = sorted(row["digest"] for row in rows)
                    if (decision_proof["observation_refs_hash"] != digest(refs)
                            or decision_proof["observation_count"] != len(refs)):
                        raise ContextIntegrityError("native context decision differs from its actual predecision source pool")
                _native_binding(binding, original, rows)
                event = binding["native_event"]
                if event["event_key"] in seen:
                    raise ContextContractError("one native event cannot be selected through two original revisions")
                seen.add(event["event_key"])
                phase = _phase(decision, config, blocks)
                report["phase_counts"].setdefault(phase, 0)
                report["phase_counts"][phase] += 1
                features = joint_features(event, rows, base, cutoff=datetime.fromisoformat(decision),
                                          version=config['feature_version'])
                unavailable = [name for name in config["feature_names"]
                    if features["states"].get(name) != "available" or not features["refs"].get(name)]
                outcome, _ = _bounded_outcome(connection, event, latest=clock, ledger=ledger)
                if outcome is not None:
                    # Do not accept a foreign schedule, participant pair or
                    # outcome contract merely because its event_key matches.
                    from context_sources.outcomes import validate_outcome_record
                    validate_outcome_record(outcome, event=event)
                in_population = event_in_population(event, config["population"])
                item.update(event_key=event["event_key"], decision_at=decision, phase=phase,
                    status="ready" if in_population and outcome is not None else "outside_population" if not in_population else "outcome_unavailable",
                    source_complete=True, unavailable_features=unavailable, outcome_ref=None if outcome is None else outcome["digest"])
                report["source_complete_events"] += 1
                report["feature_complete_events"] += int(not unavailable)
                report["outcome_events"] += int(outcome is not None)
                if in_population and phase.startswith("test:"):
                    report["test_events"] += 1
                if in_population and phase != "outside":
                    target = binding["target_record"]
                    bindings.append({key: event[key] for key in ("event_key", "home_id", "away_id")} |
                                    {"source_refs": binding["consumed_receipts"][target]})
                    entries.append({"binding_ref": ref, "event": event, "decision_at": decision,
                        "phase": phase, "outcome_ref": item["outcome_ref"]})
                    if phase in {'train', 'tune'} and outcome is not None:
                        # Size-only detached projection; it cannot enter fitting.
                        payload = dict(schema=1, event=event, base=base, features=features, replay_ref=ref,
                            outcome_ref=outcome['digest'], event_identity_hash='0'*64,
                            family_config_hash=digest(config), preprocessing_refs=[])
                        if source_transport is not None:
                            payload.update(schema=2, source_transport=source_transport)
                        case = {'kind': 'context-training-case-v1', 'payload': payload}
                        artifacts = {obj['digest']: obj for obj in (envelope, _original_envelope(original), code)}
                        if decision_proof is not None:
                            from football_context_decisions import DECISION_KIND
                            artifacts[request['decision_ref']] = dict(digest=request['decision_ref'], kind=DECISION_KIND, payload=decision_proof)
                        retained_length = len(canonical_bytes(dict(case={'digest': digest(case), **case},
                            artifacts=artifacts, observations=rows+(outcome,))))
                        if streamed is not None:
                            # Preparation retains every causal row for detached
                            # D1/D2 checking, not the small feature projection.
                            retained_length += (streamed['audit']['expanded_observation_bytes']
                                                - len(canonical_bytes(rows)))
                        retained.append((item, retained_length))
            except ReplayUnavailable as exc:
                item["reason"] = str(exc)
            report["events"].append(item)
            report['input_payload_bytes'] = ledger.size
            report["inspected_events"] += 1
            if item["reason"] == "preparation_total_byte_bound_exceeded":
                break
    report["unprocessed_events"] = len(requests)-report["inspected_events"]
    identity = {"schema": 1, "policy": "native-source-only-v1",
                "bindings": sorted(bindings, key=lambda item: item["event_key"])}
    if bindings:
        validate_identity_map({"digest": digest({"kind": "context-native-identity-map-v1", "payload": identity}),
                               "kind": "context-native-identity-map-v1", "payload": identity})
    identity_envelope = {'digest': digest({'kind': 'context-native-identity-map-v1', 'payload': identity}),
                         'kind': 'context-native-identity-map-v1', 'payload': identity}
    # A nonempty artifacts mapping gains one comma and the global identity entry.
    identity_bytes = len(canonical_bytes({identity_envelope['digest']: identity_envelope}))-1
    for item, length in retained:
        report['retained_training_payload_bytes'] += length + identity_bytes
        if report['retained_training_payload_bytes'] > training_limit:
            item.update(status='source_unavailable', reason='training_retained_byte_bound_exceeded')
            break
    return report, tuple(entries), identity


def inspect_football_readiness(path, requests, config, *, test_blocks, as_of, source_transport=None):
    """Read only the explicit native inventory and return compact diagnostics."""
    config, blocks = _configuration(config, test_blocks, source_transport=source_transport)
    report, _, _ = _inspect(path, _inventory(requests), config, blocks, as_of=as_of, source_transport=source_transport)
    return report


def _offline_path(path):
    path = Path(path)
    if not path.is_absolute():
        raise ContextContractError("offline football store must be an explicit absolute path")
    path = _assert_no_symlink_components(path)
    production = RUNTIME_STATE_DIR.absolute()
    if path == production or production in path.parents:
        raise ContextContractError("football preparation cannot write configured production state")
    return path


def _evaluation_admission(path):
    """D2 audits its whole offline store; admit bounded headers before bodies."""
    count, size = 0, 0
    with _reader(path) as connection:
        rows = connection.execute("SELECT typeof(c.payload),length(CAST(c.payload AS BLOB)) "
            "FROM context_observations r LEFT JOIN context_contents c ON c.content_digest=r.content_digest "
            "LIMIT ?", (MAX_EVALUATION_RECEIPTS+1,))
        for storage_type, length in rows:
            count += 1
            if count > MAX_EVALUATION_RECEIPTS:
                raise ContextContractError("offline evaluation exceeds its bounded receipt inventory")
            if storage_type != "blob" or type(length) is not int or length <= 0:
                raise ContextIntegrityError("offline evaluation has missing or invalid physical content")
        # D2 also hashes orphan contents; all physical rows count exactly once.
        for storage_type, length in connection.execute('SELECT typeof(payload),length(CAST(payload AS BLOB)) FROM context_contents'):
            if storage_type != 'blob' or type(length) is not int or length <= 0:
                raise ContextIntegrityError('offline evaluation has invalid physical content')
            size += length
            if size > MAX_EVALUATION_BYTES:
                raise ContextContractError("offline evaluation exceeds its bounded physical content bytes")


def prepare_football_context(path, requests, config, *, test_blocks, code_revision, created_at,
                             evaluate=False, source_transport=None):
    """Prepare real cases/fit/dataset/experiment; never publish an active slot.

    Cases with missing selected features reach the owning resolver unchanged.
    Missing original sources or outcomes block preparation, not a smaller
    favorable final cohort. The existing evaluator alone may issue approval.
    """
    path = _offline_path(path)
    if type(evaluate) is not bool or type(code_revision) is not str or re.fullmatch(r"[0-9a-f]{40}", code_revision) is None:
        raise ContextContractError("preparation requires a full code revision and explicit evaluation flag")
    if evaluate:
        _evaluation_admission(path)
    config, blocks = _configuration(config, test_blocks, source_transport=source_transport)
    if canonical_timestamp(created_at) < config["tune_end"]:
        raise ContextContractError("preparation cannot predate completed tuning")
    requests = _inventory(requests)
    report, entries, identity = _inspect(path, requests, config, blocks, as_of=created_at, source_transport=source_transport)
    result = {"status": "not_ready", "readiness": report, "identity_ref": None, "case_refs": [],
        "fit_ref": None, "fit_status": None, "dataset_ref": None, "experiment_ref": None,
        "evaluation_ref": None, "approval_count": 0, "activated": False}
    if (not entries or not any(entry["phase"] in {"train", "tune"} for entry in entries)
            or report["unprocessed_events"] or any(item["status"] == "source_unavailable"
            for item in report["events"]) or any(entry["outcome_ref"] is None for entry in entries)):
        return result
    def store(kind, payload):
        return put_artifact(path, kind=kind, payload=payload, created_at=created_at)
    identity_ref = store("context-native-identity-map-v1", identity)
    training, training_members, final_members, case_refs, retained_bytes = [], [], [], [], 0
    for entry in sorted(entries, key=lambda entry: (entry['decision_at'], entry['event']['event_key'])):
        case = build_joint_training_case(path, binding_ref=entry['binding_ref'], outcome_ref=entry['outcome_ref'],
            identity_ref=identity_ref, config=config, as_of=created_at,
            decision_at=datetime.fromisoformat(entry['decision_at']), source_transport=source_transport)
        member = {'case_ref': case['case']['digest'], 'observation_refs': sorted(row['digest'] for row in case['observations'])}
        if entry['phase'] in {'train', 'tune'}:
            retained_bytes += len(canonical_bytes(case))
            if retained_bytes > (MAX_INPUT_BYTES if source_transport is None else MAX_STREAM_TRAINING_BYTES):
                raise ContextContractError('prepared train/tune exceeds its bounded retained expanded bytes')
            training.append(case)
            training_members.append(member)
        else:
            final_members.append(member)
        if store(case["case"]["kind"], case["case"]["payload"]) != case["case"]["digest"]:
            raise ContextIntegrityError("prepared native case identity differs")
        case_refs.append(member['case_ref'])
        del case
    training = tuple(training)
    assembly = assemble_training_cases(training, config)
    fit = fit_family(assembly["rows"], config, cases=training)
    for ref, artifact in fit["candidate_artifacts"].items():
        if store("context-effect-v1", artifact) != ref:
            raise ContextIntegrityError("prepared effect identity differs")
    fit_ref = store("context-fit-v1", fit)
    dataset = validate_dataset({"schema": 1, "event_identity_hash": identity_ref, "groups": [{
        "family_config_hash": digest(config), "training_cases": training_members,
        "final_cases": final_members,
        "unavailable_final": [], "fit_ref": fit_ref}]})
    dataset_ref = store("context-dataset-v1", dataset)
    definition = {"family_config_hash": digest(config), "ablation": "full", "target_markets": config["target_markets"],
                  "outcome_contract": config["outcome_contract"]}
    hypothesis = {**definition, "hypothesis_id": digest(definition), "candidate_artifact": fit["effect_hash"],
                  "pretest_status": "ready" if fit["status"] == "fitted" else fit["status"]}
    plan = {"schema": 1, "dataset_hash": dataset_ref, "event_identity_hash": identity_ref,
        "code_revision": code_revision, "base_versions": config["base_versions"], "family_configs": [config],
        "train_end": config["train_end"], "tune_end": config["tune_end"], "test_blocks": [list(block) for block in blocks],
        "target_markets": config["target_markets"], "outcome_contracts": [config["outcome_contract"]],
        "candidate_artifacts": [] if fit["effect_hash"] is None else [fit["effect_hash"]],
        "policy_version": "context-paired-hac-bh-v1", "availability_classes": ["prospective"],
        "created_at": canonical_timestamp(created_at), "hypotheses": [hypothesis],
        "test_inventory": sorted([{"event": entry["event"], "decision_at": entry["decision_at"], "block": entry["phase"]}
            for entry in entries if entry["phase"].startswith("test:")], key=lambda item: (item["decision_at"], item["event"]["event_key"]))}
    from context_models.experiments import freeze_experiment
    experiment_ref = freeze_experiment(path, plan, created_at=created_at)
    result.update(status="prepared_not_activated", identity_ref=identity_ref,
        case_refs=sorted(case_refs), fit_ref=fit_ref, fit_status=fit["status"],
        dataset_ref=dataset_ref, experiment_ref=experiment_ref)
    if evaluate:
        from context_models.evaluator import evaluate_experiment
        evaluation = evaluate_experiment(path, experiment_ref, evaluated_at=created_at)
        result.update(status="evaluated_not_activated", evaluation_ref=evaluation["digest"],
                      approval_count=len(evaluation["approvals"]))
    return deepcopy(result)
