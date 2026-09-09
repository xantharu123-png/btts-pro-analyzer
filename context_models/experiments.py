"""Frozen context hypotheses and append-only local final-test opening history.

This module does not fit/score models, authenticate historical source truth or
issue approval. The D1/D2 resolver must verify actual case/receipt provenance.
Opening is a local workflow guard; it cannot prove that nobody inspected an
external match result. All writes use the existing trusted A1 model database.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import re

from model_artifacts import _connect, _load_artifact, canonical_bytes
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, EVIDENCE_CLASSES, _names,
    _sport_json, canonical_timestamp, digest, event_in_population, require_digest,
    require_list, require_object, require_text, validate_effect_artifact, validate_event,
)
from context_models.training import split_windows
from context_models.training_contracts import validate_family_config

EXPERIMENT_KIND = "context-experiment-v1"
OPENING_KIND = "context-test-opening-v1"
POLICY_VERSION = "context-paired-hac-bh-v1"
_PLAN_FIELDS = {
    "schema", "dataset_hash", "event_identity_hash", "code_revision", "base_versions",
    "family_configs", "train_end", "tune_end", "test_blocks", "target_markets",
    "outcome_contracts", "candidate_artifacts", "policy_version", "availability_classes",
    "created_at", "hypotheses", "test_inventory",
}
_DEFINITION_FIELDS = {"family_config_hash", "ablation", "target_markets", "outcome_contract"}


def _iso(value, name):
    if type(value) is not str:
        raise ContextContractError(f"{name} must be an aware JSON timestamp")
    return canonical_timestamp(value)


def _sorted_names(value, name, *, empty=False):
    result = _names(value, name, allow_empty=empty)
    if result != sorted(result):
        raise ContextContractError(f"{name} must be canonical sorted unique names")
    return result


def _artifact_created_at(connection, ref):
    """Normalize A1's first-insertion clock after its owning artifact check.

    A1 intentionally keeps this metadata outside the kind/payload digest.
    Registry time semantics therefore require a separate comparison; they
    cannot be inferred from a valid public content hash alone.
    """
    row = connection.execute("SELECT created_at FROM artifacts WHERE digest=?", (ref,)).fetchone()
    if row is None:
        raise ContextIntegrityError("referenced artifact has no creation metadata")
    return _iso(row[0], "artifact creation")


def validate_hypothesis(value):
    require_object(value, _DEFINITION_FIELDS | {"hypothesis_id", "candidate_artifact", "pretest_status"},
                   label="frozen hypothesis")
    row = _sport_json(value, label="hypothesis")
    require_digest(row["family_config_hash"])
    require_digest(row["hypothesis_id"])
    for name in ("ablation", "outcome_contract"):
        _names([row[name]], name)
    row["target_markets"] = _sorted_names(row["target_markets"], "hypothesis targets")
    if digest({name: row[name] for name in _DEFINITION_FIELDS}) != row["hypothesis_id"]:
        raise ContextIntegrityError("hypothesis definition hash differs")
    status = require_text(row["pretest_status"], "pretest status", code=True)
    if status not in {"ready", "fit_failed", "insufficient_data", "unsupported", "baseline_control"}:
        raise ContextContractError("unknown pretest status")
    if status == "ready":
        require_digest(row["candidate_artifact"], "ready candidate artifact")
    elif row["candidate_artifact"] is not None:
        raise ContextContractError("unevaluable/control hypothesis must not have a fitted candidate")
    return row


def validate_experiment(value):
    """Validate the closed frozen definition; no source/label I/O or approval."""
    require_object(value, _PLAN_FIELDS, label="frozen experiment")
    row = _sport_json(value, label="experiment")
    if type(row["schema"]) is not int or row["schema"] != 1:
        raise ContextContractError("unknown experiment schema")
    for name in ("dataset_hash", "event_identity_hash"):
        require_digest(row[name], name)
    if type(row["code_revision"]) is not str or re.fullmatch(r"[0-9a-f]{40}", row["code_revision"]) is None:
        raise ContextContractError("experiment must freeze the complete code revision")
    if row["policy_version"] != POLICY_VERSION:
        raise ContextContractError("unsupported context evaluation policy")
    for name in ("train_end", "tune_end", "created_at"):
        row[name] = _iso(row[name], name)
    raw_blocks = require_list(row["test_blocks"], "test blocks")
    if any(type(pair) is not list or len(pair) != 2 or any(type(v) is not str for v in pair) for pair in raw_blocks):
        raise ContextContractError("test blocks must be closed timestamp pairs")
    _, _, blocks = split_windows(train_end=row["train_end"], tune_end=row["tune_end"],
                                test_blocks=tuple(tuple(p) for p in raw_blocks))
    row["test_blocks"] = [list(p) for p in blocks]
    if row["created_at"] < row["tune_end"]:
        raise ContextContractError("experiment cannot predate its completed tuning cutoff")
    configs = require_list(row["family_configs"], "family configs")
    if not configs:
        raise ContextContractError("experiment requires explicit family configurations")
    row["family_configs"] = [validate_family_config(config) for config in configs]
    hashes = [digest(config) for config in row["family_configs"]]
    if hashes != sorted(set(hashes)):
        raise ContextContractError("family configs must be sorted by unique canonical payload hashes")
    configs = dict(zip(hashes, row["family_configs"]))
    for config in configs.values():
        if (config["train_end"], config["tune_end"]) != (row["train_end"], row["tune_end"]):
            raise ContextContractError("family split differs from its frozen experiment")
    for name, source in (("base_versions", "base_versions"), ("target_markets", "target_markets")):
        row[name] = _sorted_names(row[name], name)
        if row[name] != sorted({v for c in configs.values() for v in c[source]}):
            raise ContextContractError(f"experiment {name} must equal its exact config union")
    row["outcome_contracts"] = _sorted_names(row["outcome_contracts"], "outcome contracts")
    if row["outcome_contracts"] != sorted({c["outcome_contract"] for c in configs.values()}):
        raise ContextContractError("outcome contracts must equal the config union")
    row["availability_classes"] = _sorted_names(row["availability_classes"], "availability classes")
    if not set(row["availability_classes"]) <= EVIDENCE_CLASSES:
        raise ContextContractError("unknown context evidence class")
    raw_hypotheses = require_list(row["hypotheses"], "hypotheses")
    if not raw_hypotheses:
        raise ContextContractError("all hypotheses require an explicit nonempty registry")
    row["hypotheses"] = [validate_hypothesis(h) for h in raw_hypotheses]
    ids = [h["hypothesis_id"] for h in row["hypotheses"]]
    if ids != sorted(set(ids)):
        raise ContextContractError("hypotheses require sorted unique definitions")
    for hypothesis in row["hypotheses"]:
        config = configs.get(hypothesis["family_config_hash"])
        if config is None or any(hypothesis[k] != config[k] for k in ("target_markets", "outcome_contract")):
            raise ContextContractError("hypothesis does not bind the exact frozen family configuration")
    if set(configs) != {h["family_config_hash"] for h in row["hypotheses"]}:
        raise ContextContractError("a configured family is absent from the hypothesis registry")
    row["candidate_artifacts"] = _sorted_names(row["candidate_artifacts"], "candidate artifacts", empty=True)
    expected = sorted({h["candidate_artifact"] for h in row["hypotheses"] if h["candidate_artifact"] is not None})
    if row["candidate_artifacts"] != expected:
        raise ContextContractError("candidate artifacts must equal the registered candidate set")
    inventory = []
    seen = set()
    for value in require_list(row["test_inventory"], "unlabeled test inventory"):
        require_object(value, {"event", "decision_at", "block"}, label="unlabeled test inventory entry")
        event = validate_event(value["event"])
        decision = _iso(value["decision_at"], "test decision")
        expected_block = next((f"test:{i}" for i, (start, end) in enumerate(blocks) if start <= decision < end), None)
        if expected_block is None or value["block"] != expected_block:
            raise ContextContractError("inventory decision differs from its fixed test block")
        if decision >= event["scheduled_start"] or event["status"] != "scheduled":
            raise ContextContractError("test inventory must freeze actual pre-start decisions")
        if event["event_key"] in seen:
            raise ContextContractError("one native event can occur only once in the final inventory")
        if not any(event_in_population(event, c["population"]) for c in configs.values()):
            raise ContextContractError("test event is outside the frozen populations")
        seen.add(event["event_key"])
        inventory.append({"event": event, "decision_at": decision, "block": expected_block})
    if inventory != sorted(inventory, key=lambda r: (r["decision_at"], r["event"]["event_key"])):
        raise ContextContractError("test inventory must be in canonical decision/event order")
    row["test_inventory"] = inventory
    return row


def _checked_references(connection, plan):
    # Owning validation here is structural. Full receipt resolution is an
    # additional mandatory step when constructing/evaluating real D1 cases.
    from context_models.training_contracts import validate_identity_map

    ref = plan["event_identity_hash"]
    identity = validate_identity_map({"digest": ref, **_load_artifact(connection, ref)})
    if _artifact_created_at(connection, ref) > plan["created_at"]:
        raise ContextIntegrityError("native identity map was created after the frozen experiment")
    bindings = {r["event_key"]: r for r in identity["payload"]["bindings"]}
    for item in plan["test_inventory"]:
        event = item["event"]
        known = bindings.get(event["event_key"])
        if known is None or any(known[name] != event[name] for name in ("home_id", "away_id")):
            raise ContextIntegrityError("test inventory does not bind the whole native identity map")
    configs = {digest(c): c for c in plan["family_configs"]}
    for hypothesis in plan["hypotheses"]:
        if hypothesis["candidate_artifact"] is None:
            continue
        config = configs[hypothesis["family_config_hash"]]
        ref = hypothesis["candidate_artifact"]
        record = _load_artifact(connection, ref)
        if record["kind"] != "context-effect-v1":
            raise ContextIntegrityError("registered candidate is not a context effect")
        effect = validate_effect_artifact(record["payload"])
        keys = ("sport", "family", "feature_version", "feature_names", "preprocessing_artifacts",
                "joint_calibration", "population", "coverage", "model_variant")
        if any(effect[k] != config[k] for k in keys) or effect["training_end"] != config["train_end"]:
            raise ContextIntegrityError("candidate scope/training differs from the frozen hypothesis")
        if {key: head["link"] for key, head in effect["heads"].items()} != config["head_links"]:
            raise ContextIntegrityError("candidate does not have the registered fitting law")
        if any(head["alpha"] not in config["alpha_grid"] for head in effect["heads"].values()):
            raise ContextIntegrityError("candidate alpha was not in the declared search")
        actual = _artifact_created_at(connection, ref)
        if actual < effect["training_end"]:
            raise ContextIntegrityError("candidate creation precedes its own training cutoff")
        if actual > plan["created_at"]:
            raise ContextIntegrityError("candidate was produced after the experiment was frozen")


def _load_experiment(connection, ref):
    record = _load_artifact(connection, require_digest(ref, "experiment hash"))
    if record["kind"] != EXPERIMENT_KIND:
        raise ContextIntegrityError("reference is not a frozen context experiment")
    plan = validate_experiment(record["payload"])
    if plan != record["payload"]:
        raise ContextIntegrityError("stored experiment is not canonical")
    if _artifact_created_at(connection, ref) != plan["created_at"]:
        raise ContextIntegrityError("actual experiment creation differs from its frozen clock")
    _checked_references(connection, plan)
    return plan


def _persist(connection, *, kind, payload, created_at):
    """Append within the caller's A1 transaction and verify exact stored bytes."""
    ref = digest({"kind": kind, "payload": payload})
    connection.execute("INSERT OR IGNORE INTO artifacts(digest,kind,payload,created_at) VALUES(?,?,?,?)",
                       (ref, kind, canonical_bytes(payload), canonical_timestamp(created_at)))
    if _load_artifact(connection, ref) != {"kind": kind, "payload": payload}:
        raise ContextIntegrityError("immutable experiment artifact identity collision")
    if _artifact_created_at(connection, ref) != canonical_timestamp(created_at):
        raise ContextIntegrityError("existing artifact creation differs from the bound registry clock")
    return ref


def _openings(connection):
    openings, reserved = {}, {}
    # Validate the complete A1 byte/type/hash inventory before kind dispatch.
    # Otherwise one corrupted kind column can hide an existing opening. This
    # does not fit/score/interpret case labels or authenticate a rebuilt DB.
    for (ref,) in connection.execute("SELECT digest FROM artifacts ORDER BY digest"):
        record = _load_artifact(connection, ref)
        if record["kind"] != OPENING_KIND:
            continue
        payload = record["payload"]
        require_object(payload, {"schema", "experiment_hash", "event_identity_hash", "event_keys", "opened_at"},
                       label="final test opening")
        if type(payload["schema"]) is not int or payload["schema"] != 1:
            raise ContextIntegrityError("invalid final test opening schema")
        experiment_ref = require_digest(payload["experiment_hash"])
        plan = _load_experiment(connection, experiment_ref)
        expected = sorted(r["event"]["event_key"] for r in plan["test_inventory"])
        clock = _iso(payload["opened_at"], "opening time")
        if _artifact_created_at(connection, ref) != clock:
            raise ContextIntegrityError("actual opening creation differs from its original opening clock")
        if (payload["event_identity_hash"] != plan["event_identity_hash"] or payload["event_keys"] != expected
                or clock != payload["opened_at"] or clock < plan["created_at"]):
            raise ContextIntegrityError("opening does not bind the original whole inventory")
        if experiment_ref in openings:
            raise ContextIntegrityError("experiment has more than one original opening")
        for event in expected:
            if event in reserved:
                raise ContextIntegrityError("persisted experiments have overlapping opened events")
            reserved[event] = experiment_ref
        openings[experiment_ref] = (ref, payload)
    return openings, reserved


def freeze_experiment(path: Path, plan: dict, *, created_at: datetime) -> str:
    """Freeze all intended hypotheses before labels; preserve previous openings."""
    canonical = validate_experiment(plan)
    if canonical_timestamp(created_at) != canonical["created_at"]:
        raise ContextContractError("actual freeze clock differs from the frozen creation time")
    ref = digest({"kind": EXPERIMENT_KIND, "payload": canonical})
    with closing(_connect(path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            _checked_references(connection, canonical)
            _, reserved = _openings(connection)
            if any(reserved.get(r["event"]["event_key"], ref) != ref for r in canonical["test_inventory"]):
                raise ContextContractError("changed experiment reuses already opened final test events")
            result = _persist(connection, kind=EXPERIMENT_KIND, payload=canonical, created_at=created_at)
            connection.commit()
            return result
        except BaseException:
            connection.rollback()
            raise


def open_test_inventory(path: Path, experiment_hash: str, *, opened_at: datetime) -> str:
    """Reserve the whole frozen test before the caller consumes any label.

    Failed downstream evaluation never deletes this opening. Exact reruns keep
    its original clock. There is deliberately no event-subset or force option.
    """
    clock = canonical_timestamp(opened_at)
    with closing(_connect(path)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            plan = _load_experiment(connection, experiment_hash)
            if clock < plan["created_at"]:
                raise ContextContractError("opening cannot precede the frozen experiment")
            openings, reserved = _openings(connection)
            if experiment_hash in openings:
                original = openings[experiment_hash]
                if clock < original[1]["opened_at"]:
                    raise ContextContractError("exact rerun cannot backdate its original opening")
                connection.commit()
                return original[0]
            events = sorted(r["event"]["event_key"] for r in plan["test_inventory"])
            if any(event in reserved for event in events):
                raise ContextContractError("another experiment already opened these final test events")
            payload = {"schema": 1, "experiment_hash": experiment_hash, "event_identity_hash": plan["event_identity_hash"],
                       "event_keys": events, "opened_at": clock}
            result = _persist(connection, kind=OPENING_KIND, payload=payload, created_at=opened_at)
            connection.commit()
            return result
        except BaseException:
            connection.rollback()
            raise
