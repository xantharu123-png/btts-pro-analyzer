"""Opt-in same-call publication. Storage evidence is not model approval.

Only an explicit worker supplies finite budgets. No provider calls, fitting,
inventory searches, activation, source clock invention or ORIGINAL rewriting.
"""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import marshal
import platform
from threading import Lock
import types
from pathlib import Path
from dataclasses import asdict, is_dataclass
import inspect

import model_artifacts as a1
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest, require_object
from context_models.football_original_storage import prepare_original, publish_prepared, StorageBudgetExceeded, _budget, _expand
from context_observations import freeze_named_receipts, _SELECT, _decode_receipt

CODE_KIND = "football-executed-code-v2"
BINDING_KIND = "football-original-b1-binding-v1"


def publication_for_worker(capture, limits):
    """Explicit configured opt-in; no environment switch or production default."""
    require_object(limits, {"max_publication_payload_bytes", "max_worker_payload_bytes",
        "max_source_payload_bytes"}, label="football original capture limits")
    from runtime_paths import CONTEXT_MODEL_DB_PATH
    return FootballOriginalPublication(capture.path if capture is not None else CONTEXT_MODEL_DB_PATH,
        capture, **limits)


def executed_code_identity():
    """Hash actual loaded Python code, not a guessed git revision or disk file.

    This names the executed closure/runtime; it is not an empirical certificate.
    Module-owned class methods are included along with module functions.
    """
    modules, sources, bindings = {}, {}, {}
    def value_identity(value):
        if value is None or type(value) in (str, bool, int, float):
            return value
        if type(value) in (tuple, list):
            return [value_identity(item) for item in value]
        if type(value) in (set, frozenset):
            return sorted((value_identity(item) for item in value), key=a1.canonical_bytes)
        if type(value) is dict:
            return {str(key): value_identity(item) for key, item in value.items()}
        if is_dataclass(value) and not isinstance(value, type):
            return value_identity(asdict(value))
        return {"type": type(value).__module__ + "." + type(value).__qualname__}
    for name in ("challenge_engine", "football_original", "football_joint_calibration",
                 "challenge_15k", "football_model_refresh", "wettfinder_automation",
                 "context_models.football_original_publication", "context_sources.football_capture",
                 "context_sources.football_native", "context_sources.outcomes", "context_observations"):
        module = importlib.import_module(name)
        sources[name] = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        bindings[name] = {key: value_identity(value) for key, value in vars(module).items()
                          if key.isupper() and not key.startswith("__")}
        functions = {}
        for key, value in vars(module).items():
            if callable(value) and not isinstance(value, type):
                value = inspect.unwrap(value)
            if isinstance(value, types.FunctionType) and value.__module__ == name:
                functions[key] = {"code": hashlib.sha256(marshal.dumps(value.__code__)).hexdigest(),
                    "defaults": value_identity(value.__defaults__), "kwdefaults": value_identity(value.__kwdefaults__)}
            elif isinstance(value, type) and value.__module__ == name:
                for method, function in vars(value).items():
                    if isinstance(function, (staticmethod, classmethod)):
                        function = function.__func__
                    if isinstance(function, types.FunctionType):
                        functions[key + "." + method] = {"code": hashlib.sha256(marshal.dumps(function.__code__)).hexdigest(),
                            "defaults": value_identity(function.__defaults__), "kwdefaults": value_identity(function.__kwdefaults__)}
        modules[name] = digest(functions)
    import challenge_engine as engine
    import scipy
    import numpy
    return {"schema": 2, "kind": CODE_KIND, "modules": modules, "source_files": sources,
        "runtime_bindings": bindings, "authority": "execution-fingerprint-not-replay-qualification",
        "python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__,
        "prediction_version": engine.CHALLENGE_PREDICTION_VERSION,
        "model_contract_signature": engine.CHALLENGE_MODEL_CONTRACT_SIGNATURE}


class FootballOriginalPublication:
    def __init__(self, path, capture, *, max_publication_payload_bytes,
                 max_worker_payload_bytes, max_source_payload_bytes):
        for value in (max_publication_payload_bytes, max_worker_payload_bytes, max_source_payload_bytes):
            _budget(value)
        self.path, self.capture = path, capture
        self.max_publication_payload_bytes = max_publication_payload_bytes
        self.remaining_payload_bytes = max_worker_payload_bytes
        self.remaining_source_bytes = max_source_payload_bytes
        self.inserted_payload_bytes = 0
        self.source_inserted_bytes = 0
        self.events = []
        self._lock = Lock()
        self._rows = None
        self._associations = {}
        self._source_exhausted = False
        self._code = a1.prepare_artifact(kind=CODE_KIND, payload=executed_code_identity())

    def freeze(self, selected_input_scope):
        """Flush then freeze the exact independent source refs once per scan."""
        if self._rows is not None:
            raise ContextContractError("publication source set already frozen")
        if type(selected_input_scope) is not tuple:
            raise ContextContractError("publication input scope must be a tuple")
        if self.capture is not None:
            before = self.capture.source_inserted_bytes
            try:
                self._associations = self.capture.flush_baseline_receipts(selected_input_scope,
                    max_new_payload_bytes=self.remaining_source_bytes)
            except StorageBudgetExceeded:
                self._source_exhausted = True
                # The flush committed complete single-receipt units only. Keep
                # those exact refs; never fall back to a database inventory.
                for ref, record in self.capture.baseline_scope_records.items():
                    self._associations[ref] = tuple(sorted(
                        self.capture.baseline_refs.get(record["fixture_id"], ()))) if record["source_marker"] in {
                            "unresolved", "api-football", "api-football-ft-tail"} else ()
            inserted = self.capture.source_inserted_bytes - before
            self.remaining_source_bytes -= inserted
            self.source_inserted_bytes += inserted
        refs = tuple(sorted({ref for values in self._associations.values() for ref in values}))
        self._rows = freeze_named_receipts(self.path, refs)

    def model_kwargs(self, *, decision_at):
        """Create the selected-input resolver and callback for ONE final call."""
        if self._rows is None:
            raise ContextContractError("freeze native receipts before decision")
        decision = canonical_timestamp(decision_at)
        selected_state = {}

        def resolve(fixtures):
            from challenge_engine import football_base_history_record
            from context_sources.football_native import football_native_provenance
            from context_sources.outcomes import validate_football_base_input
            records = {digest(football_base_history_record(row)): row for row in fixtures}
            named = {ref for record in records for ref in self._associations.get(record, ())}
            receipts, source_rows = [], []
            for row in self._rows:
                if row["digest"] not in named:
                    continue
                if row["source"] != "api-football" or row["kind"] != "base_fixture":
                    raise ContextIntegrityError("named baseline receipt has wrong source or kind")
                selected = {**row, "evidence_class": "prospective", "effective_at": row["observed_at"], "publication_resolution": None}
                validate_football_base_input(selected)
                source_rows.append(row)
                receipts.append({"detail": row["payload"]["detail"], "observed_at": row["observed_at"]})
            provenance = football_native_provenance(tuple(records.values()), tuple(receipts), decision_at=decision_at)
            consumed, unresolved = {}, {}
            for ref, fixture in records.items():
                evidence = provenance["records"].get(ref)
                if evidence is None:
                    unresolved[ref] = ("source-retention-budget-exhausted" if self._source_exhausted else
                        "native-receipt-reference-unavailable" if not self._associations.get(ref) else "native-revision-unresolved")
                else:
                    consumed[ref] = sorted(row["digest"] for row in source_rows
                        if row["digest"] in self._associations.get(ref, ())
                        and row["observed_at"] == evidence["payload"]["observed_at"])
            selected_state.update(records=records, provenance=provenance, consumed=consumed, unresolved=unresolved,
                inspected={ref: list(self._associations.get(ref, ())) for ref in records})
            return provenance

        def capture(original):
            if not selected_state:
                with self._lock:
                    self.events.append({"target_record": None, "binding_ref": None, "status": "unavailable",
                        "inserted_payload_bytes": 0, "source_state": "partial",
                        "code_state": "execution-fingerprint-only", "empirical_state": "not-evaluated",
                        "unavailable_reason": "selected-native-provenance-unavailable"})
                return
            self._publish(original, decision, selected_state)
        return {"native_resolver": resolve, "original_capture": capture}

    def _publish(self, original, decision, selected):
        from challenge_engine import football_base_history_record
        from context_sources.football import _detail_event
        prepared = prepare_original(original)
        packet = original.to_dict()
        code = a1._decode_object(self._code.payload_bytes, label="executed code")
        if any(packet[name] != code[name] for name in ("prediction_version", "model_contract_signature")):
            raise ContextIntegrityError("ORIGINAL differs from executed code/model identity")
        if decision > packet["captured_at"]:
            raise ContextIntegrityError("decision follows actual ORIGINAL capture")
        target_ref = digest(football_base_history_record(packet["fixture"]))
        selected = dict(selected)
        unavailable = packet["goal_provenance"]["reference_weights"].get("kind") == "unavailable"
        if unavailable:
            original_refs = {digest(football_base_history_record(row)) for row in
                [packet["fixture"], *packet["league_history"], *(packet["team_history"] or [])]}
            selected["consumed"] = {}
            selected["unresolved"] = {ref: "football-source-provenance-invalid" for ref in selected["records"]}
        else:
            original_refs = {row["ref"] for row in packet["goal_provenance"]["history_refs"]} | {target_ref}
        mismatched = not set(selected["records"]) <= original_refs if unavailable else original_refs != set(selected["records"])
        if target_ref not in selected["records"] or mismatched:
            raise ContextIntegrityError("ORIGINAL differs from same-call selected baseline union")
        native_event = None
        target_refs = selected["consumed"].get(target_ref, ())
        if target_refs:
            row = next(row for row in self._rows if row["digest"] == target_refs[0])
            native_event = _detail_event(row["payload"]["detail"])
        binding = a1.prepare_artifact(kind=BINDING_KIND, payload={"schema": 1,
            "source_state": "partial" if selected["unresolved"] else "captured",
            "code_state": "execution-fingerprint-only", "empirical_state": "not-evaluated",
            "native_event": native_event, "decision_at": decision, "captured_at": packet["captured_at"],
            "original_manifest_digest": prepared.manifest_digest, "original_logical_digest": prepared.logical_digest,
            "code_digest": self._code.digest, "prediction_version": packet["prediction_version"],
            "model_contract_signature": packet["model_contract_signature"], "target_record": target_ref,
            "consumed_receipts": selected["consumed"], "inspected_receipts": selected["inspected"],
            "unresolved": selected["unresolved"]})
        dependency_refs = {ref for refs in selected["inspected"].values() for ref in refs}
        dependencies = tuple(row for row in self._rows if row["digest"] in dependency_refs)
        with self._lock:
            created_at = datetime.now(timezone.utc)
            created = canonical_timestamp(created_at)
            limit = min(self.max_publication_payload_bytes, self.remaining_payload_bytes)
            try:
                with closing(a1._connect(self.path)) as connection:
                    try:
                        connection.execute("BEGIN IMMEDIATE")
                        # Reverify every named dependency in the writer image.
                        # A concurrently changed B1 row cannot orphan an ORIGINAL.
                        for row in dependencies:
                            stored = connection.execute(_SELECT + " WHERE r.digest=?", (row["digest"],)).fetchone()
                            if stored is None or _decode_receipt(stored) != row:
                                raise ContextIntegrityError("named receipt changed after freeze")
                        result = publish_prepared(connection, prepared, created_at=created_at,
                            max_new_payload_bytes=limit)
                        inserted = result.inserted_payload_bytes
                        for obj in (self._code, binding):
                            _, fresh = a1._insert_artifact(connection, obj, created)
                            inserted += len(obj.payload_bytes) if fresh else 0
                        if inserted > limit:
                            raise StorageBudgetExceeded("code/binding publication budget exhausted")
                        # Verify final actual readback, including trigger effects.
                        final_original_rows = {}
                        for obj in (*prepared.artifacts, self._code, binding):
                            row = connection.execute("SELECT kind,payload,created_at FROM artifacts WHERE digest=?", (obj.digest,)).fetchone()
                            actual = a1._decode_artifact_row(obj.digest, row)
                            if actual["kind"] != obj.kind or a1.canonical_bytes(actual["payload"]) != obj.payload_bytes:
                                raise ContextIntegrityError("publication dependency readback mismatch")
                            if obj in prepared.artifacts:
                                final_original_rows[obj.digest] = row
                            elif row[2] > created:
                                raise ContextIntegrityError("publication dependency created after binding")
                        _expand(final_original_rows, prepared.manifest_digest)
                        for row in dependencies:
                            stored = connection.execute(_SELECT + " WHERE r.digest=?", (row["digest"],)).fetchone()
                            if stored is None or _decode_receipt(stored) != row:
                                raise ContextIntegrityError("binding dependency changed during publication")
                        connection.commit()
                    except BaseException:
                        connection.rollback()
                        raise
                self.remaining_payload_bytes -= inserted
                self.inserted_payload_bytes += inserted
                status = "partial" if selected["unresolved"] else "captured"
                ref = binding.digest
            except StorageBudgetExceeded:
                inserted, ref, status = 0, None, "budget-exhausted"
            self.events.append({"target_record": target_ref, "binding_ref": ref,
                "status": status, "inserted_payload_bytes": inserted,
                "source_state": "partial" if selected["unresolved"] else "captured",
                "code_state": "execution-fingerprint-only", "empirical_state": "not-evaluated",
                "unavailable_reason": None})

    def report(self):
        return {"schema": 1, "scope": "football-final-same-call-originals",
            "published_count": sum(row["binding_ref"] is not None for row in self.events),
            "inserted_payload_bytes": self.inserted_payload_bytes,
            "source_inserted_payload_bytes": self.source_inserted_bytes,
            "events": deepcopy(self.events)}


def original_capture_report_fields(snapshot):
    if "football_original_capture" not in snapshot:
        return {}
    report = require_object(snapshot["football_original_capture"], {"schema", "scope", "published_count",
        "inserted_payload_bytes", "source_inserted_payload_bytes", "events"}, label="football original capture report")
    if report["schema"] != 1 or type(report["schema"]) is not int or report["scope"] != "football-final-same-call-originals":
        raise ContextContractError("invalid original capture report version")
    for field in ("published_count", "inserted_payload_bytes", "source_inserted_payload_bytes"):
        _budget(report[field])
    from challenge_15k import MAX_SCAN_FIXTURES
    if type(report["events"]) is not list or len(report["events"]) > MAX_SCAN_FIXTURES:
        raise ContextContractError("invalid original capture event list")
    for event in report["events"]:
        require_object(event, {"target_record", "binding_ref", "status", "inserted_payload_bytes",
            "source_state", "code_state", "empirical_state", "unavailable_reason"}, label="original capture event")
        if (event["source_state"] not in {"partial", "captured"} or event["code_state"] != "execution-fingerprint-only"
                or event["empirical_state"] != "not-evaluated"):
            raise ContextContractError("invalid original qualification state")
        if event["status"] == "unavailable":
            if event["target_record"] is not None or event["unavailable_reason"] != "selected-native-provenance-unavailable":
                raise ContextContractError("unavailable capture cannot claim a selected record")
        else:
            a1._validate_digest(event["target_record"])
            if event["unavailable_reason"] is not None:
                raise ContextContractError("unexpected unavailable reason")
        if event["binding_ref"] is not None:
            a1._validate_digest(event["binding_ref"])
        if event["status"] not in {"captured", "partial", "budget-exhausted", "unavailable"} or (event["binding_ref"] is None) != (event["status"] in {"budget-exhausted", "unavailable"}):
            raise ContextContractError("inconsistent original event status")
        _budget(event["inserted_payload_bytes"])
    if report["published_count"] != sum(event["binding_ref"] is not None for event in report["events"]) or report["inserted_payload_bytes"] != sum(event["inserted_payload_bytes"] for event in report["events"]):
        raise ContextContractError("inconsistent publication accounting")
    return {"football_original_capture": deepcopy(report)}
