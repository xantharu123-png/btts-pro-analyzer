"""No-write D1/D2 evidence checks on D4's caller-held SQLite transaction.

This verifies stored workflow/calculation consistency, not provider truth, a
new empirical approval or activation. Unknown legacy transports and artifacts
whose original owning context is absent keep explicit incomplete boundaries.
"""
from collections import defaultdict

from context_models.contracts import (
    ContextIntegrityError, canonical_timestamp, digest,
    require_digest, require_list, require_number, require_object, require_text, validate_base_distribution,
    validate_event, validate_feature_vector,
)
from context_models.dataset import (
    CASE_KIND, DATASET_KIND, FIT_KIND, _artifact,
    _physical_receipt_preflight, _prepare, _receipt, resolve_case, validate_dataset,
)
from context_models.experiments import _load_experiment, _openings
from context_models.training_cases import CASE_FIELDS, case_header
from context_models.training_contracts import (
    resolve_identity_map, validate_fit_result, validate_identity_map,
    validate_resolved_case,
)
from model_artifacts import canonical_bytes


D2_KINDS = frozenset({
    "context-native-identity-map-v1", "context-base-replay-recipe-v1",
    "context-base-replay-v1", CASE_KIND, FIT_KIND, DATASET_KIND,
    "context-experiment-v1", "context-test-opening-v1", "context-evaluation-v1",
    "football-participation-v1",
})
_REPLAY_FIELDS = {"schema", "base", "event_hash", "recipe_hash", "input_refs_hash",
    "event_identity_hash", "logical_training_cutoff", "reconstructed_at", "evidence_class"}
_FIT_FIELDS = {"schema", "status", "reason", "family_config_hash", "event_identity_hash",
    "artifact", "effect_hash", "selected_alpha", "alpha_scores", "candidate_artifacts",
    "case_hashes", "rows_hash", "training_case_hashes", "tuning_case_hashes",
    "training_rows_hash", "tuning_rows_hash", "training_events", "tuning_events", "exclusions"}


def _same(left, right, label):
    if canonical_bytes(left) != canonical_bytes(right):
        raise ContextIntegrityError(label)


def _versioned(payload, kind):
    """Unknown versions are capability gaps; damaged known claims are errors.

    Old D4 fixtures deliberately stored opaque transports without ANY schema.
    Missing schema on an otherwise recognizable owning claim is not legacy.
    """
    if "schema" not in payload:
        identifying = {"family_configs", "evaluator_version", "groups", "case_hashes",
            "event_identity_hash", "replay_ref", "recipe_hash", "bindings", "input_refs",
            "opened_at", "training_refs_hash"}
        if identifying & set(payload):
            raise ContextIntegrityError("known D2 claim is missing its schema")
        return False
    if type(payload["schema"]) is not int or payload["schema"] < 1:
        raise ContextIntegrityError("D2 schema must be an actual positive integer")
    if payload["schema"] != 1:
        return False
    if kind == "context-evaluation-v1":
        from context_models.evaluator import EVALUATOR_VERSION
        if "evaluator_version" not in payload or type(payload["evaluator_version"]) is not str:
            raise ContextIntegrityError("known evaluation lacks its evaluator version")
        if payload["evaluator_version"] != EVALUATOR_VERSION:
            return False
    return True


def _clock(value, label):
    if type(value) is not str or canonical_timestamp(value) != value:
        raise ContextIntegrityError(label + " is not a canonical actual clock")
    return value


def _physical_ref(connection, ref, *, latest, kinds=None):
    """Outer index only: an opaque final label is never decoded here."""
    require_digest(ref, "physical receipt reference")
    row = connection.execute(
        "SELECT content_digest,event_key,observed_at,kind FROM context_observations WHERE digest=?", (ref,)).fetchone()
    if row is None:
        raise ContextIntegrityError("D2 artifact references a missing physical receipt")
    content, event_key, received, kind = row
    if (digest({"content_digest": require_digest(content), "observed_at": _clock(received, "receipt")}) != ref
            or received > latest or (kinds is not None and kind not in kinds)):
        raise ContextIntegrityError("D2 receipt has an impossible original clock or source kind")
    return event_key, received, kind


def _selected_receipt(connection, ref):
    row = _receipt(connection, ref)
    return {**row, "evidence_class": "prospective", "effective_at": row["observed_at"],
            "publication_resolution": None}


def _check_known_opening_claims(connection, known, clocks):
    """Reject damaged v1 claims even beside a future opening capability.

    This does not authorize reading labels: only the owning complete-inventory
    `_openings` pass can do that. A future opening keeps the overall inventory
    unresolved, but cannot conceal contradictions in a recognized v1 record.
    """
    seen_plans, seen_events = set(), set()
    for ref, envelope in known.items():
        if envelope["kind"] != "context-test-opening-v1":
            continue
        payload = require_object(envelope["payload"], {
            "schema", "experiment_hash", "event_identity_hash", "event_keys", "opened_at",
        }, label="known original final test opening")
        experiment_ref = require_digest(payload["experiment_hash"])
        plan = _load_experiment(connection, experiment_ref)
        expected = sorted(item["event"]["event_key"] for item in plan["test_inventory"])
        clock = _clock(payload["opened_at"], "opening")
        if (clock != clocks[ref] or clock < plan["created_at"]
                or payload["event_identity_hash"] != plan["event_identity_hash"]
                or payload["event_keys"] != expected):
            raise ContextIntegrityError("known opening contradicts its original whole inventory or actual clock")
        if experiment_ref in seen_plans or seen_events.intersection(expected):
            raise ContextIntegrityError("known original openings overlap")
        seen_plans.add(experiment_ref)
        seen_events.update(expected)


def _case_shape(connection, ref, payload, *, configs, actual):
    require_object(payload, CASE_FIELDS, label="stored D1 case")
    config = configs.get(require_digest(payload["family_config_hash"], "case configuration"))
    if config is not None:
        checked = case_header({"case": {"digest": ref, "kind": CASE_KIND, "payload": payload},
            "artifacts": {}, "observations": ()}, config=config)
        _same(checked, payload, "case does not retain canonical original inputs")
    else:
        # A pre-freeze case is valid storage, not an invented family config.
        for name, validator in (("event", validate_event), ("base", validate_base_distribution),
                                ("features", validate_feature_vector)):
            _same(validator(payload[name]), payload[name], "noncanonical standalone case input")
    event, base, features = (payload[name] for name in ("event", "base", "features"))
    if (event["event_key"] != base["event_key"] or event["event_key"] != features["event_key"]
            or base["cutoff"] != features["cutoff"] or base["cutoff"] >= event["scheduled_start"]
            or event["status"] != "scheduled"):
        raise ContextIntegrityError("standalone case has contradictory original identities")
    # Missing configuration does not make explicit prospective references
    # unknowable. Check every feature state against its original decision,
    # not the later case creation; this inspects no source/label body.
    for receipt in sorted({r for refs in features["refs"].values() for r in refs}):
        _physical_ref(connection, receipt, latest=features["cutoff"])
    replay = _artifact(connection, payload["replay_ref"], "context-base-replay-v1", latest=actual)["payload"]
    _artifact(connection, payload["event_identity_hash"], "context-native-identity-map-v1", latest=actual)
    if (replay.get("base") != base or replay.get("event_hash") != digest(event)
            or replay.get("event_identity_hash") != payload["event_identity_hash"]
            or replay.get("logical_training_cutoff") != base["cutoff"]):
        raise ContextIntegrityError("stored case and referenced original replay differ")
    refs = require_list(payload["preprocessing_refs"], "case preprocessing")
    if refs != sorted(set(require_digest(r) for r in refs)):
        raise ContextIntegrityError("case preprocessing references are not canonical")
    for preprocessing in refs:
        _artifact(connection, preprocessing, "football-participation-v1", latest=actual)
    event_key, _, _ = _physical_ref(connection, payload["outcome_ref"], latest=actual, kinds={"match_outcome"})
    if event_key != event["event_key"]:
        raise ContextIntegrityError("case outcome reference belongs to another native event")


def _fit_shape(connection, payload, *, configs, actual):
    require_object(payload, _FIT_FIELDS, label="stored D1 fit")
    config_ref = require_digest(payload["family_config_hash"], "fit configuration")
    config = configs.get(config_ref)
    if config is not None:
        _same(validate_fit_result(payload, config=config), payload, "noncanonical stored fit result")
    for field in ("case_hashes", "training_case_hashes", "tuning_case_hashes"):
        refs = require_list(payload[field], field)
        if refs != sorted(set(require_digest(ref) for ref in refs)):
            raise ContextIntegrityError("stored fit case inventory is not canonical")
        for ref in refs:
            case = _artifact(connection, ref, CASE_KIND, latest=actual)["payload"]
            if case.get("family_config_hash") != config_ref:
                raise ContextIntegrityError("fit references another family case")
    if payload["event_identity_hash"] is not None:
        _artifact(connection, payload["event_identity_hash"], "context-native-identity-map-v1", latest=actual)
    if type(payload["candidate_artifacts"]) is not dict:
        raise ContextIntegrityError("fit candidates must retain exact artifact bytes")
    for ref, candidate in payload["candidate_artifacts"].items():
        actual_candidate = _artifact(connection, ref, "context-effect-v1", latest=actual)["payload"]
        _same(candidate, actual_candidate, "fit candidate differs from actual A1 artifact")
    if config is None:
        _orphan_fit_header(payload)


def _orphan_fit_header(result):
    """Only v1 invariants independent of a missing original configuration.

    No feature scope, alpha grid or fitting source is guessed. These bounded
    header checks do NOT promote an orphan to an owning verified fit; they
    prevent its explicit capability limitation from hiding known type errors
    or internal contradictions. Full config-present checks remain with D1.
    """
    status = require_text(result["status"], "orphan fit status", code=True)
    if status not in {"fitted", "fit_failed", "unsupported", "insufficient_data"}:
        raise ContextIntegrityError("unknown stored fit status")
    for field in ("rows_hash", "training_rows_hash", "tuning_rows_hash"):
        require_digest(result[field], field)
    training, tuning, all_cases = (set(result[field]) for field in
                                  ("training_case_hashes", "tuning_case_hashes", "case_hashes"))
    if training & tuning or not training | tuning <= all_cases:
        raise ContextIntegrityError("stored fit train/tune partition contradicts itself")
    if all_cases and result["event_identity_hash"] is None:
        raise ContextIntegrityError("stored fit cases lack the global native map")
    for phase in ("training", "tuning"):
        count = result[phase + "_events"]
        if type(count) is not int or count < 0 or count != len(result[phase + "_case_hashes"]):
            raise ContextIntegrityError("stored fit count contradicts its actual case list")
    excluded, excluded_events = set(), set()
    for row in require_list(result["exclusions"], "orphan fit exclusions"):
        require_object(row, {"event_key", "case_hash", "status", "reason"}, label="stored case exclusion")
        for field in ("event_key", "status", "reason"):
            require_text(row[field], field, code=True)
        ref = require_digest(row["case_hash"])
        if (row["status"] not in {"unsupported", "insufficient_data", "excluded"}
                or ref in excluded or row["event_key"] in excluded_events):
            raise ContextIntegrityError("stored fit contains invalid or duplicate exclusions")
        excluded.add(ref)
        excluded_events.add(row["event_key"])
    if (training | tuning) & excluded or training | tuning | excluded != all_cases:
        raise ContextIntegrityError("stored fit cases lack their exact once-only partition")
    candidates, referenced, scored, alphas = result["candidate_artifacts"], set(), [], set()
    for row in require_list(result["alpha_scores"], "orphan alpha scores"):
        require_object(row, {"alpha", "status", "mean_brier", "effect_hash", "reason"}, label="stored alpha score")
        alpha = require_number(row["alpha"], "alpha", minimum=0)
        if alpha in alphas:
            raise ContextIntegrityError("stored alpha inventory duplicates one candidate")
        alphas.add(alpha)
        if row["status"] == "scored":
            require_number(row["mean_brier"], "Brier", minimum=0, maximum=1)
            ref = require_digest(row["effect_hash"])
            if (ref not in candidates or row["reason"] is not None
                    or any(head["alpha"] != alpha for head in candidates[ref]["heads"].values())):
                raise ContextIntegrityError("stored score contradicts its actual candidate")
            referenced.add(ref)
            scored.append(row)
        elif row["status"] == "fit_failed":
            require_text(row["reason"], "failed alpha reason")
            if row["mean_brier"] is not None or row["effect_hash"] is not None:
                raise ContextIntegrityError("failed stored alpha claims a fitted score")
        else:
            raise ContextIntegrityError("unknown stored alpha score status")
    if referenced != set(candidates):
        raise ContextIntegrityError("stored score and candidate inventories differ")
    if status == "fitted":
        require_number(result["selected_alpha"], "selected alpha", minimum=0)
        if not scored or result["reason"] is not None or len(training) < 2 or len(tuning) < 1:
            raise ContextIntegrityError("stored fitted header lacks complete train/tune claims")
        selected = min(scored, key=lambda row: (row["mean_brier"], -row["alpha"]))
        if (result["selected_alpha"] != selected["alpha"] or result["effect_hash"] != selected["effect_hash"]
                or canonical_bytes(result["artifact"]) != canonical_bytes(candidates[selected["effect_hash"]])):
            raise ContextIntegrityError("stored fit selection contradicts its reported alpha scores")
    else:
        require_text(result["reason"], "unavailable fit reason")
        if scored or any(result[field] is not None for field in ("artifact", "effect_hash", "selected_alpha")):
            raise ContextIntegrityError("unavailable stored fit claims a selected model")
        if status == "fit_failed" and not result["alpha_scores"]:
            raise ContextIntegrityError("stored fit failure lost all attempted alpha records")


def verify_d2_artifacts(connection, artifacts, created_at, limitations):
    """Verify every typed stored artifact, not only active manifest references.

    All connection operations are reads. In particular this never calls
    prepare_dataset's path wrapper, opening/persistence or active publication.
    """
    from context_models.activation import verify_approval
    from context_models.evaluator import verify_evaluation
    from context_models.replay import ReplayUnavailable, _recipe
    from context_models.training import fit_family
    from context_models.training_cases import assemble_training_cases

    verified = {name: [] for name in ("experiments", "datasets", "fits", "cases", "evaluations", "approvals")}
    known, unknown = {}, set()
    clocks = {ref: canonical_timestamp(clock) for ref, clock in created_at.items()}
    for ref, envelope in artifacts.items():
        if envelope["kind"] not in D2_KINDS:
            continue
        if _versioned(envelope["payload"], envelope["kind"]):
            known[ref] = envelope
        else:
            unknown.add(ref)
            limitations.add("d2-report-experiment-schema-unavailable" if envelope["kind"] in {
                "context-experiment-v1", "context-evaluation-v1"} else "d2-unrecognized-artifact-schema")
    if not known and not any(e["kind"] == "context-approval-v1" for e in artifacts.values()):
        return {"verified": verified, "protected_receipts": set()}

    # Hash/index checks precede every source decoder, including identity maps.
    _physical_receipt_preflight(connection)
    plans = {ref: _load_experiment(connection, ref) for ref, e in known.items()
             if e["kind"] == "context-experiment-v1"}
    configs = {digest(config): config for plan in plans.values() for config in plan["family_configs"]}
    unknown_opening = any(artifacts[r]["kind"] == "context-test-opening-v1" for r in unknown)
    if unknown_opening:
        _check_known_opening_claims(connection, known, clocks)
        openings = {}
        limitations.add("d2-opening-semantics-unavailable")
    else:
        # Owner checks all opening clocks, whole inventories, overlapping
        # native events and the complete A1 hash inventory before kind dispatch.
        openings, _ = _openings(connection)
    protected_events = {item["event"]["event_key"] for ref, plan in plans.items()
                        if ref not in openings for item in plan["test_inventory"]}
    protected = set()
    if protected_events:
        limitations.add("d2-final-source-replay-not-opened")
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name='context_observations'").fetchone():
            for ref, key, kind in connection.execute("SELECT digest,event_key,kind FROM context_observations"):
                if key in protected_events and kind == "match_outcome":
                    protected.add(ref)

    # All known reference shapes are inspected even if no dataset/experiment
    # owns them yet. Missing actual references are errors, not a legacy gap.
    for ref, envelope in known.items():
        kind, payload, actual = envelope["kind"], envelope["payload"], clocks[ref]
        if kind == "context-native-identity-map-v1":
            mapped = validate_identity_map({"digest": ref, **envelope})
            refs = sorted({r for b in mapped["payload"]["bindings"] for r in b["source_refs"]})
            for receipt in refs:
                _physical_ref(connection, receipt, latest=actual, kinds={"base_fixture", "performed_match"})
            resolve_identity_map(mapped, observations=tuple(_selected_receipt(connection, r) for r in refs))
        elif kind == "context-base-replay-recipe-v1":
            _recipe({"digest": ref, **envelope}, sport=payload.get("sport"))
            for receipt in payload["input_refs"]:
                _physical_ref(connection, receipt, latest=actual, kinds={"base_fixture"})
        elif kind == "context-base-replay-v1":
            require_object(payload, _REPLAY_FIELDS, label="stored base replay")
            base = validate_base_distribution(payload["base"])
            _same(base, payload["base"], "noncanonical original replay basis")
            for field in ("event_hash", "input_refs_hash"):
                require_digest(payload[field], field)
            recipe = _artifact(connection, payload["recipe_hash"], "context-base-replay-recipe-v1", latest=actual)["payload"]
            _artifact(connection, payload["event_identity_hash"], "context-native-identity-map-v1", latest=actual)
            if (_clock(payload["logical_training_cutoff"], "replay cutoff") != base["cutoff"]
                    or not base["cutoff"] <= _clock(payload["reconstructed_at"], "reconstruction") <= actual
                    or payload["input_refs_hash"] != digest(recipe.get("input_refs"))
                    or payload["evidence_class"] != "prospective"):
                raise ContextIntegrityError("stored replay has contradictory source or clock provenance")
        elif kind == CASE_KIND:
            _case_shape(connection, ref, payload, configs=configs, actual=actual)
        elif kind == FIT_KIND:
            _fit_shape(connection, payload, configs=configs, actual=actual)
        elif kind == DATASET_KIND:
            _same(validate_dataset(payload), payload, "noncanonical original dataset")
            _artifact(connection, payload["event_identity_hash"], "context-native-identity-map-v1", latest=actual)
            for group in payload["groups"]:
                if group["fit_ref"] is not None:
                    fit = _artifact(connection, group["fit_ref"], FIT_KIND, latest=actual)["payload"]
                    if fit.get("family_config_hash") != group["family_config_hash"]:
                        raise ContextIntegrityError("dataset fit has a different family configuration")
                for phase in ("training_cases", "final_cases"):
                    for item in group[phase]:
                        case = _artifact(connection, item["case_ref"], CASE_KIND, latest=actual)["payload"]
                        if (case.get("family_config_hash") != group["family_config_hash"]
                                or case.get("event_identity_hash") != payload["event_identity_hash"]):
                            raise ContextIntegrityError("dataset case configuration/native map differs")
                        for receipt in item["observation_refs"]:
                            _physical_ref(connection, receipt, latest=clocks[item["case_ref"]])
        elif kind == "football-participation-v1":
            from context_models.football import _participation_probability
            _participation_probability({"digest": ref, **envelope}, cutoff=actual, rows=())
            limitations.add("d1-participation-training-receipts-unresolved")
        elif kind == "context-evaluation-v1":
            from context_models.evaluator import REPORT_FIELDS, implementation_hashes
            require_object(payload, REPORT_FIELDS, label="stored source-resolved evaluation")
            if (payload["implementation_hashes"] != implementation_hashes()
                    or _clock(payload["evaluated_at"], "evaluation") != actual):
                raise ContextIntegrityError("evaluation implementation/actual creation claim differs")
            for name, expected_kind in (("experiment_hash", "context-experiment-v1"),
                    ("dataset_hash", DATASET_KIND), ("event_identity_hash", "context-native-identity-map-v1"),
                    ("opening_hash", "context-test-opening-v1")):
                _artifact(connection, payload[name], expected_kind, latest=actual)

    training_owners, case_owners = defaultdict(list), set()
    for ref, plan in plans.items():
        if plan["dataset_hash"] not in known:
            if plan["dataset_hash"] not in artifacts:
                raise ContextIntegrityError("experiment dataset is missing")
            limitations.add("d2-dataset-semantics-unavailable")
            continue
        checked = _prepare(connection, ref, evaluated_at=plan["created_at"])
        verified["experiments"].append(ref)
        verified["datasets"].append(plan["dataset_hash"])
        for group in checked["dataset"]["groups"]:
            config = configs[group["family_config_hash"]]
            if group["fit_ref"] is not None:
                verified["fits"].append(group["fit_ref"])
            for item in group["training_cases"]:
                training_owners[item["case_ref"]].append((plan, item))
                case_owners.add(item["case_ref"])
                verified["cases"].append(item["case_ref"])
            if ref not in openings:
                continue
            for item in group["final_cases"]:
                case_owners.add(item["case_ref"])
                try:
                    resolved = resolve_case(connection, item, config=config, plan=plan, latest=openings[ref][1]["opened_at"])
                    validate_resolved_case(resolved, config=config)
                except ReplayUnavailable:
                    limitations.add("d1-final-source-replay-unavailable")
                else:
                    verified["cases"].append(item["case_ref"])

    # A persisted, unselected fit is still a claim about exactly its own cases.
    # Reuse a uniquely known original receipt pool, never synthesize that pool.
    for ref, envelope in known.items():
        if envelope["kind"] != FIT_KIND or ref in verified["fits"]:
            continue
        payload = envelope["payload"]
        config = configs.get(payload["family_config_hash"])
        choices, resolvable = [], config is not None
        for case_ref in payload["case_hashes"]:
            owners = training_owners.get(case_ref, [])
            distinct = {digest(item) for _, item in owners}
            if len(distinct) != 1:
                resolvable = False
                break
            choices.append(owners[0])
        if not resolvable:
            limitations.add("d1-fit-owning-replay-unavailable")
            continue
        cases = tuple(resolve_case(connection, item, config=config, plan=plan, latest=clocks[ref])
                      for plan, item in choices)
        assembly = assemble_training_cases(cases, config)
        actual_fit = fit_family(assembly["rows"], config, cases=cases)
        _same(actual_fit, payload, "unselected fit does not reproduce its original cases and all alphas")
        verified["fits"].append(ref)

    for ref, envelope in known.items():
        kind = envelope["kind"]
        if kind == DATASET_KIND and ref not in verified["datasets"]:
            limitations.add("d2-dataset-owning-experiment-unavailable")
        elif kind == CASE_KIND and ref not in case_owners:
            # This includes unopened finals; headers/refs were checked above.
            limitations.add("d1-case-owning-replay-unavailable")
        elif kind in {"context-base-replay-v1", "context-base-replay-recipe-v1"}:
            linked = {known[c]["payload"]["replay_ref"] for c in case_owners}
            if kind == "context-base-replay-recipe-v1":
                linked = {artifacts[r]["payload"]["recipe_hash"] for r in linked}
            if ref not in linked:
                limitations.add("d1-original-replay-context-unavailable")
        elif kind == "context-evaluation-v1":
            if unknown_opening:
                limitations.add("d2-evaluation-opening-unavailable")
                continue
            verify_evaluation(connection, ref)
            verified["evaluations"].append(ref)

    for ref, envelope in artifacts.items():
        if envelope["kind"] != "context-approval-v1":
            continue
        payload = envelope["payload"]
        if payload["report_hash"] not in verified["evaluations"] or payload["experiment_hash"] not in plans:
            limitations.add("d2-approval-evidence-resolution-unavailable")
            continue
        verify_approval(connection, ref)
        verified["approvals"].append(ref)
    return {"verified": {key: sorted(set(values)) for key, values in verified.items()},
            "protected_receipts": protected}
