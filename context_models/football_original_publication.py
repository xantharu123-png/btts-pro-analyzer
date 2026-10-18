"""Opt-in same-call publication. Storage evidence is not model approval.

Only an explicit worker supplies finite budgets. No provider calls, inventory
searches, activation, source clock invention or ORIGINAL rewriting. A bounded
opponent comparison may reuse the frozen native inputs without changing them.
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
from football_original import FootballOriginal
from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest, require_object
from context_models.football_original_storage import prepare_original, publish_prepared, StorageBudgetExceeded, MAX_ORIGINAL_BYTES, _budget, _expand
from context_observations import freeze_named_receipts, _SELECT, _decode_receipt

CODE_KIND = "football-executed-code-v2"
BINDING_KIND = "football-original-b1-binding-v1"
MAX_PENDING_OPPONENT_COMPARISONS = 1200


def publication_for_worker(capture, limits, *, shared_budget=None):
    """Explicit configured opt-in; no environment switch or production default."""
    require_object(limits, {"max_publication_payload_bytes", "max_worker_payload_bytes",
        "max_source_payload_bytes"}, label="football original capture limits")
    from runtime_paths import CONTEXT_MODEL_DB_PATH
    return FootballOriginalPublication(capture.path if capture is not None else CONTEXT_MODEL_DB_PATH,
        capture, shared_budget=shared_budget, **limits)


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
                 "football_opponent_strength", "football_opponent_publication",
                 "challenge_15k", "football_model_refresh", "wettfinder_automation",
                 "context_models.football_original_publication", "context_sources.football_capture",
                 "context_sources.football_native", "context_sources.outcomes", "context_observations",
                 "football_context_inventory"):
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


class FootballOriginalBudget:
    """One in-process budget shared by every batch of a reserved worker run."""
    def __init__(self, *, max_worker_payload_bytes, max_source_payload_bytes, context_inventory_contract=None):
        for value in (max_worker_payload_bytes, max_source_payload_bytes):
            _budget(value)
        self.max_worker_payload_bytes = self.remaining_payload_bytes = max_worker_payload_bytes
        self.max_source_payload_bytes = self.remaining_source_bytes = max_source_payload_bytes
        self.lock = Lock()
        self._sealed = False
        self._optional = {}
        self._optional_bytes = 0
        self._decisions = {}
        self._decision_path = None
        self._decision_bytes = 0
        self._decision_unprocessed = 0
        self._decision_report = None
        self._decision_preparing = 0
        self._inventory_finalizing = self._inventory_failed = False
        self._inventory_budget = None
        if context_inventory_contract is not None:
            from football_context_inventory import HeaderBudget, KIND, MAX_EVENTS, MAX_HEADERS, MAX_HEADER_BYTES
            if context_inventory_contract != KIND:
                raise ContextContractError("unknown explicit postcapture inventory contract")
            self._inventory_budget = HeaderBudget(max_headers=3*MAX_EVENTS*MAX_HEADERS,
                max_bytes=3*MAX_EVENTS*MAX_HEADER_BYTES, seconds=4*MAX_EVENTS, phase_seconds=2)

    def defer_context_decisions(self, path, capture_report, *, decision_at):
        """Legacy default unchanged; explicit v2 prepares outside the worker mutex."""
        from football_context_decisions import prepare_capture_decisions
        if self._inventory_budget is not None:
            return self._defer_context_inventory(path, capture_report, decision_at=decision_at)
        with self.lock:
            if self._sealed:
                raise ContextContractError("reserved original worker is already finished")
            path = Path(path).resolve()
            if self._decision_path is not None and self._decision_path != path:
                raise ContextIntegrityError("one reserved worker cannot mix decision stores")
            prepared = prepare_capture_decisions(path, capture_report, decision_at=decision_at)
            self._decision_path = path
            self._admit_decisions_locked(prepared)

    def _admit_decisions_locked(self, prepared):
        from football_context_decisions import MAX_DECISION_BYTES, MAX_DECISION_EVENTS
        self._decision_unprocessed += prepared["unprocessed_events"]
        for row in prepared["events"]:
            key = row["binding_ref"]
            old = self._decisions.get(key)
            if old is not None and old["payload"] is not None and row["payload"] is None:
                continue  # An unavailable later attempt cannot erase genuine earlier evidence.
            if old is not None and old["payload"] is not None and row["payload"] is not None:
                revision = "header_hash" if self._inventory_budget is not None else "observation_refs_hash"
                if old["payload"][revision] == row["payload"][revision]:
                    if (self._inventory_budget is None
                            or old["payload"]["decision_at"] <= row["payload"]["decision_at"]):
                        continue  # Preserve the first actual clock, not completion order.
                elif (self._inventory_budget is not None
                        and row["payload"]["decision_at"] < old["payload"]["decision_at"]):
                    continue  # A slower older preparation cannot erase a newer revision.
                elif row["payload"]["decision_at"] <= old["payload"]["decision_at"]:
                    raise ContextIntegrityError("deferred source revisions have conflicting clocks")
            size = len(a1.canonical_bytes(row))
            old_size = 0 if old is None else len(a1.canonical_bytes(old))
            displaced = None
            if old is None and len(self._decisions) >= MAX_DECISION_EVENTS and row["payload"] is not None:
                displaced = next((item for item in self._decisions
                                  if self._decisions[item]["payload"] is None), None)
                if displaced is not None:
                    old_size = len(a1.canonical_bytes(self._decisions[displaced]))
            if ((old is None and len(self._decisions) >= MAX_DECISION_EVENTS)
                    and displaced is None
                    or self._decision_bytes-old_size+size > MAX_DECISION_BYTES*MAX_DECISION_EVENTS):
                self._decision_unprocessed += 1
                continue
            if displaced is not None:
                del self._decisions[displaced]
                self._decision_unprocessed += 1
            self._decisions[key] = deepcopy(row)
            self._decision_bytes += size-old_size

    def _defer_context_inventory(self, path, capture_report, *, decision_at):
        from football_context_inventory import prepare_capture_inventories
        with self.lock:
            if self._sealed:
                raise ContextContractError("reserved original worker is already finished")
            path = Path(path).resolve()
            if self._decision_path is not None and self._decision_path != path:
                raise ContextIntegrityError("one reserved worker cannot mix decision stores")
            self._decision_path = path
            self._decision_preparing += 1
        try:
            prepared = prepare_capture_inventories(path, capture_report,
                decision_at=decision_at, budget=self._inventory_budget)
        except BaseException:
            with self.lock:
                self._decision_preparing -= 1
            raise
        with self.lock:
            try:
                if self._sealed:
                    raise ContextIntegrityError("original worker sealed while an inventory was preparing")
                self._admit_decisions_locked(prepared)
            finally:
                self._decision_preparing -= 1

    def _defer_comparison(self, path, prepared, *, captured_at, scheduled_start):
        """Called under the shared lock; retain compact bytes, never history/owners."""
        if self._sealed:
            raise ContextContractError("reserved original worker is already finished")
        key = (str(Path(path).resolve()), prepared.digest)
        if key in self._optional:
            return
        size = len(prepared.payload_bytes)
        if (len(self._optional) >= MAX_PENDING_OPPONENT_COMPARISONS
                or self._optional_bytes + size > self.max_worker_payload_bytes):
            return  # Optional research cannot reserve or enlarge ORIGINAL bytes.
        self._optional[key] = (Path(path), prepared, captured_at, scheduled_start)
        self._optional_bytes += size

    def finish_optional_comparisons(self):
        """Seal ALL original batches, then spend only the existing leftover bytes.

        Idempotent and fail-closed. A failed optional transaction cannot roll
        back committed originals or regain the worker's payload/source budget.
        """
        if self._inventory_budget is not None:
            return self._finish_inventory_comparisons()
        with self.lock:
            if self._sealed:
                return deepcopy(self._decision_report)
            self._sealed = True
            # All owning ORIGINALs now have priority over compact decisions,
            # which in turn precede optional opponent research. One unchanged
            # worker envelope bounds every committed artifact.
            from football_context_decisions import MAX_DECISION_BYTES, MAX_DECISION_EVENTS, publish_deferred_decisions
            decisions, self._decisions = self._decisions, {}
            self._decision_bytes = 0
            if self._decision_path is not None:
                def debit(size):
                    if type(size) is not int or not 0 <= size <= self.remaining_payload_bytes:
                        raise ContextIntegrityError("invalid deferred decision byte accounting")
                    self.remaining_payload_bytes -= size
                self._decision_report = publish_deferred_decisions(self._decision_path,
                    {"events": list(decisions.values()), "unprocessed_events": self._decision_unprocessed},
                    max_run_bytes=min(self.remaining_payload_bytes, MAX_DECISION_BYTES*MAX_DECISION_EVENTS),
                    on_commit=debit)
            pending, self._optional = self._optional, {}
            self._optional_bytes = 0
            self._publish_optional_rows(pending)
            return deepcopy(self._decision_report)

    def _finish_inventory_comparisons(self):
        """Seal after joined ORIGINAL workers; perform no source IO under mutex."""
        from football_context_inventory import MAX_EVENTS, MAX_PAYLOAD_BYTES, publish_deferred_inventories
        with self.lock:
            if self._sealed:
                if self._inventory_finalizing or self._inventory_failed:
                    raise ContextContractError("unresolved inventory finalizer is active or previously failed")
                return deepcopy(self._decision_report)
            if self._decision_preparing:
                raise ContextContractError("join inventory preparation before sealing ORIGINALs")
            self._sealed = self._inventory_finalizing = True
            decisions, self._decisions = self._decisions, {}
            pending, self._optional = self._optional, {}
            self._decision_bytes = self._optional_bytes = 0
            remaining = self.remaining_payload_bytes
        def debit(size):
            with self.lock:
                if type(size) is not int or not 0 <= size <= self.remaining_payload_bytes:
                    raise ContextIntegrityError("invalid unresolved inventory byte debit")
                self.remaining_payload_bytes -= size
        try:
            report = None
            if self._decision_path is not None:
                report = publish_deferred_inventories(self._decision_path,
                    {"events": list(decisions.values()), "unprocessed_events": self._decision_unprocessed},
                    max_run_bytes=min(remaining, MAX_EVENTS*MAX_PAYLOAD_BYTES),
                    budget=self._inventory_budget, on_commit=debit)
            self._publish_optional_rows(pending)
        except BaseException:
            with self.lock:
                self._inventory_finalizing = False
                self._inventory_failed = True
            raise
        with self.lock:
            self._decision_report = report
            self._inventory_finalizing = False
            return deepcopy(report)

    def _publish_optional_rows(self, pending):
        from context_models.football_training import _load_publication
        for path, obj, captured_at, scheduled_start in pending.values():
            # This is the actual new physical publication clock, not the
            # earlier decision/capture clock carried by the original.
            created = canonical_timestamp(datetime.now(timezone.utc))
            if created < captured_at:
                raise ContextIntegrityError("optional publication precedes actual ORIGINAL capture")
            if created >= scheduled_start:
                continue  # A late batch is not prospective research evidence.
            if len(obj.payload_bytes) > self.remaining_payload_bytes:
                continue
            payload = a1._decode_object(obj.payload_bytes, label="opponent comparison")
            binding_ref = payload["original_binding_ref"]
            with closing(a1._connect(path)) as connection:
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    binding, _, _ = _load_publication(connection, binding_ref, latest=created)
                    value = binding["payload"]
                    if (value["captured_at"] != captured_at
                            or value["native_event"]["scheduled_start"] != scheduled_start
                            or value["original_manifest_digest"] != payload["original_manifest_ref"]
                            or value["code_digest"] != payload["original_code_ref"]):
                        raise ContextIntegrityError("deferred comparison differs from its stored original binding")
                    refs = tuple(sorted({ref for group in value["inspected_receipts"].values() for ref in group}))
                    def check_receipts():
                        for ref in refs:
                            raw = connection.execute(_SELECT + " WHERE r.digest=?", (ref,)).fetchone()
                            if raw is None or _decode_receipt(raw)["digest"] != ref:
                                raise ContextIntegrityError("deferred comparison source dependency changed")
                    check_receipts()
                    _, fresh = a1._insert_artifact(connection, obj, created)
                    inserted = len(obj.payload_bytes) if fresh else 0
                    if inserted > self.remaining_payload_bytes:
                        raise StorageBudgetExceeded("optional comparison leftover budget exhausted")
                    row = connection.execute("SELECT kind,payload,created_at FROM artifacts WHERE digest=?", (obj.digest,)).fetchone()
                    actual = a1._decode_artifact_row(obj.digest, row)
                    if (actual["kind"] != obj.kind or a1.canonical_bytes(actual["payload"]) != obj.payload_bytes
                            or row[2] < captured_at or row[2] >= scheduled_start or row[2] > created):
                        raise ContextIntegrityError("deferred comparison readback or publication clock differs")
                    # Trigger changes to existing dependencies are checked
                    # inside the same transaction before any budget debit.
                    _load_publication(connection, binding_ref, latest=created)
                    check_receipts()
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
            self.remaining_payload_bytes -= inserted

    def report(self):
        with self.lock:
            return {"inserted_payload_bytes": self.max_worker_payload_bytes - self.remaining_payload_bytes,
                "source_inserted_payload_bytes": self.max_source_payload_bytes - self.remaining_source_bytes}


class FootballOriginalPublication:
    def __init__(self, path, capture, *, max_publication_payload_bytes,
                 max_worker_payload_bytes, max_source_payload_bytes, shared_budget=None):
        for value in (max_publication_payload_bytes, max_worker_payload_bytes, max_source_payload_bytes):
            _budget(value)
        self.path, self.capture = path, capture
        self.max_publication_payload_bytes = max_publication_payload_bytes
        if shared_budget is None:
            shared_budget = FootballOriginalBudget(max_worker_payload_bytes=max_worker_payload_bytes,
                max_source_payload_bytes=max_source_payload_bytes)
        if (type(shared_budget) is not FootballOriginalBudget
                or shared_budget.max_worker_payload_bytes != max_worker_payload_bytes
                or shared_budget.max_source_payload_bytes != max_source_payload_bytes):
            raise ContextContractError("publication differs from the shared worker budget")
        self._budget = shared_budget
        if shared_budget._sealed:
            raise ContextContractError("reserved original worker is already finished")
        self.inserted_payload_bytes = 0
        self.source_inserted_bytes = 0
        self.events = []
        self._lock = shared_budget.lock
        self._rows = None
        self._associations = {}
        self._source_exhausted = False
        self._source_budget_excluded = frozenset()
        self._code = a1.prepare_artifact(kind=CODE_KIND, payload=executed_code_identity())

    @property
    def remaining_payload_bytes(self):
        return self._budget.remaining_payload_bytes

    @property
    def remaining_source_bytes(self):
        return self._budget.remaining_source_bytes

    def freeze(self, selected_input_scope):
        """Flush then freeze the exact independent source refs once per scan."""
        if self._rows is not None:
            raise ContextContractError("publication source set already frozen")
        if self._budget._sealed:
            raise ContextContractError("reserved original worker is already finished")
        if type(selected_input_scope) is not tuple:
            raise ContextContractError("publication input scope must be a tuple")
        if self.capture is not None:
            with self._lock:
                if self._budget._sealed:
                    raise ContextContractError("reserved original worker is already finished")
                before = self.capture.source_inserted_bytes
                try:
                    self._associations = self.capture.flush_baseline_receipts(selected_input_scope,
                        max_new_payload_bytes=self.remaining_source_bytes)
                except StorageBudgetExceeded:
                    self._source_exhausted = True
                    # Keep exact complete receipts only, never inventory fallback.
                    for ref, record in self.capture.baseline_scope_records.items():
                        self._associations[ref] = tuple(sorted(
                            self.capture.baseline_refs.get(record["fixture_id"], ()))) if record["source_marker"] in {
                                "unresolved", "api-football", "api-football-ft-tail"} else ()
                finally:
                    # A failed native append is not evidence that CSV rows or
                    # never-received fixtures were excluded by the byte budget.
                    # Freeze this flush's IDs before any later capture batch.
                    self._source_budget_excluded = frozenset(
                        getattr(self.capture, "baseline_budget_excluded_ids", ()))
                    # A later batch must not regain bytes committed before an
                    # error in this one. A process crash forfeits the whole permit.
                    inserted = self.capture.source_inserted_bytes - before
                    if type(inserted) is not int or not 0 <= inserted <= self.remaining_source_bytes:
                        self._budget.remaining_source_bytes = 0
                        raise ContextIntegrityError("invalid shared source byte accounting")
                    self._budget.remaining_source_bytes -= inserted
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
                    baseline = football_base_history_record(fixture)
                    budget_excluded = (baseline["source_marker"] in {
                        "unresolved", "api-football", "api-football-ft-tail"}
                        and baseline["fixture_id"] in self._source_budget_excluded)
                    unresolved[ref] = ("source-retention-budget-exhausted" if budget_excluded else
                        "native-receipt-reference-unavailable" if not self._associations.get(ref) else "native-revision-unresolved")
                else:
                    consumed[ref] = sorted(row["digest"] for row in source_rows
                        if row["digest"] in self._associations.get(ref, ())
                        and row["observed_at"] == evidence["payload"]["observed_at"])
            selected_state.update(records=records, provenance=provenance, consumed=consumed, unresolved=unresolved,
                inspected={ref: list(self._associations.get(ref, ())) for ref in records})
            return provenance

        def capture(original):
            # The storage protocol has a hard expanded-size cap. Recording is
            # optional: decline an over-limit owning record before decoding it,
            # without dropping the already calculated prediction. All other
            # integrity failures still propagate; no oversized bytes are saved.
            if (type(original) is FootballOriginal and type(original._bytes) is bytes
                    and len(original._bytes) > MAX_ORIGINAL_BYTES):
                with self._lock:
                    self.events.append({"target_record": None, "binding_ref": None, "status": "unavailable",
                        "inserted_payload_bytes": 0, "source_state": "partial",
                        "code_state": "execution-fingerprint-only", "empirical_state": "not-evaluated",
                        "unavailable_reason": "original-size-limit"})
                return
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
        # A distinct experimental recipe reuses this same input revision. It
        # stores only existing references and compact parameters/markets, never
        # the history or score cells again. Old probabilities remain untouched.
        from football_opponent_publication import prepare_opponent_comparison
        from football_opponent_strength import ComparisonUnavailable
        try:
            opponent = prepare_opponent_comparison(original,
                a1._decode_object(binding.payload_bytes, label="original binding"), dependencies)
        except ComparisonUnavailable:
            opponent = None
        with self._lock:
            if self._budget._sealed:
                raise ContextContractError("reserved original worker is already finished")
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
                self._budget.remaining_payload_bytes -= inserted
                self.inserted_payload_bytes += inserted
                if opponent is not None and len(opponent.payload_bytes) <= self.max_publication_payload_bytes - inserted:
                    self._budget._defer_comparison(self.path, opponent,
                        captured_at=packet["captured_at"], scheduled_start=native_event["scheduled_start"])
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
            if event["target_record"] is not None or event["unavailable_reason"] not in {
                    "selected-native-provenance-unavailable", "original-size-limit"}:
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
        expected_source_state = {"captured": "captured", "partial": "partial", "unavailable": "partial"}.get(event["status"])
        if expected_source_state is not None and event["source_state"] != expected_source_state:
            raise ContextContractError("inconsistent original source state")
        if event["status"] in {"budget-exhausted", "unavailable"} and event["inserted_payload_bytes"] != 0:
            raise ContextContractError("unpublished original cannot claim inserted bytes")
    if report["published_count"] != sum(event["binding_ref"] is not None for event in report["events"]) or report["inserted_payload_bytes"] != sum(event["inserted_payload_bytes"] for event in report["events"]):
        raise ContextContractError("inconsistent publication accounting")
    return {"football_original_capture": deepcopy(report)}

