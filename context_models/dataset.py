"""Offline A1/B1 dataset resolution; headers before labels, never free rows.

This establishes consistency of the stored local evidence, not that somebody
never inspected a provider result outside the process. No archive resolver is
invented here. Newly received historical inputs retain their actual clocks.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import hashlib
import os
import sqlite3

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, OBSERVATION_FIELDS, canonical_timestamp, digest,
    event_in_population, require_digest, require_list, require_object, require_text,
)
from context_models.experiments import _artifact_created_at, _load_experiment
from context_models.training_cases import assemble_training_cases, case_header
from context_models.training_contracts import validate_artifact_envelope, validate_fit_result, validate_identity_map
from context_observations import _SELECT, _check_selected_row, _decode_receipt
from model_artifacts import ArtifactIntegrityError, _load_artifact, canonical_bytes
from runtime_paths import (
    RuntimeArtifactTrustError,
    _assert_no_symlink_components, _validate_trusted_runtime_ancestor_chain,
    _validate_trusted_runtime_database_stat,
)

DATASET_KIND = "context-dataset-v1"
FIT_KIND = "context-fit-v1"
CASE_KIND = "context-training-case-v1"
UNAVAILABLE_REASONS = frozenset({"native_to_state_key_source_resolver_unavailable"})


def _reader_files(path, *, expected=None):
    """Inspect main and live SQLite companions without following any alias.

    SQLite can write synchronization metadata even through a mode=ro reader.
    Existing invalid files must therefore be rejected before SQLite opens.
    Checks bound observable identities, not a race-proof VFS: another process
    with the same trusted filesystem authority can still act between checks.
    """
    _validate_trusted_runtime_ancestor_chain(path.parent)
    identities = {}
    for suffix in ("", "-wal", "-shm", "-journal"):
        member = _assert_no_symlink_components(path.with_name(path.name + suffix))
        try:
            current = os.lstat(member)
        except FileNotFoundError:
            if not suffix:
                raise ContextIntegrityError("explicit context database does not exist")
            continue
        _validate_trusted_runtime_database_stat(member, current)
        if current.st_nlink != 1:
            raise RuntimeArtifactTrustError(f"context database and companions must be singly linked: {member}")
        identities[member] = (current.st_dev, current.st_ino)
    if expected is not None and any(identities.get(member) != identity for member, identity in expected.items()):
        raise ContextIntegrityError("context database path identity changed while opening or reading")
    return identities


@contextmanager
def _reader(path):
    """Live read transaction: no data/schema publication or implicit creation.

    Trusted SQLite WAL/SHM synchronization is allowed; committed WAL rows must
    remain visible. This is not an immutable main-file copy or a sealed audit.
    """
    path = _assert_no_symlink_components(Path(path))
    original = _reader_files(path)
    connection = None
    try:
        connection = sqlite3.connect(path.as_uri()+"?mode=ro", uri=True, timeout=5)
        opened = _reader_files(path, expected=original)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("BEGIN")
        yield connection
        _reader_files(path, expected=opened)
    except (ArtifactIntegrityError, sqlite3.DatabaseError, KeyError) as exc:
        raise ContextIntegrityError("context database references or stored bytes are invalid") from exc
    finally:
        if connection is not None:
            try:
                connection.rollback()
            finally:
                connection.close()


def _artifact(connection, ref, kind, *, latest):
    ref = require_digest(ref, "stored artifact reference")
    envelope = validate_artifact_envelope({"digest": ref, **_load_artifact(connection, ref)}, kind=kind)
    if _artifact_created_at(connection, ref) > latest:
        raise ContextIntegrityError("referenced artifact was actually inserted after its owning cutoff")
    return envelope


def _refs(value, label, *, nonempty=False):
    refs = require_list(value, label)
    for ref in refs:
        require_digest(ref, label)
    if refs != sorted(set(refs)) or (nonempty and not refs):
        raise ContextContractError(label+" must be sorted unique actual references")
    return list(refs)


def validate_dataset(value):
    require_object(value, {"schema", "event_identity_hash", "groups"}, label="context dataset")
    if type(value["schema"]) is not int or value["schema"] != 1:
        raise ContextContractError("unknown context dataset schema")
    require_digest(value["event_identity_hash"], "global identity map")
    groups = require_list(value["groups"], "dataset groups")
    config_refs = []
    for group in groups:
        require_object(group, {"family_config_hash", "training_cases", "final_cases", "unavailable_final", "fit_ref"},
                       label="dataset family group")
        config_refs.append(require_digest(group["family_config_hash"], "family config"))
        if group["fit_ref"] is not None:
            require_digest(group["fit_ref"], "stored fit")
        seen = set()
        for phase in ("training_cases", "final_cases"):
            for item in require_list(group[phase], phase):
                require_object(item, {"case_ref", "observation_refs"}, label="dataset case reference")
                ref = require_digest(item["case_ref"], "stored case")
                if ref in seen:
                    raise ContextIntegrityError("dataset case occurs more than once in a family")
                seen.add(ref)
                _refs(item["observation_refs"], "case receipt pool", nonempty=True)
        unavailable = require_list(group["unavailable_final"], "pretest unavailable events")
        for item in unavailable:
            require_object(item, {"event_key", "decision_at", "reason"}, label="pretest unavailable event")
            require_text(item["event_key"], "unavailable native event", code=True)
            if type(item["decision_at"]) is not str or canonical_timestamp(item["decision_at"]) != item["decision_at"]:
                raise ContextContractError("unavailable decision must retain its canonical clock")
            if require_text(item["reason"], "pretest unavailable reason", code=True) not in UNAVAILABLE_REASONS:
                raise ContextIntegrityError("unverified caller missing-data assertion is not a pretest exclusion")
        if unavailable != sorted(unavailable, key=lambda r: (r["decision_at"], r["event_key"])):
            raise ContextContractError("unavailable inventory must have canonical decision/event order")
    if not config_refs or config_refs != sorted(set(config_refs)):
        raise ContextContractError("dataset groups must be sorted unique config references")
    # Reject non-JSON values without coercion; caller flags have no side channel.
    canonical_bytes(value)
    return deepcopy(value)


def _physical_receipt_preflight(connection):
    """Hash opaque bytes; inspect only fixed OUTER B1 metadata, never labels.

    SQLite parses JSON to project those existing header fields. No Python JSON
    body decoder, payload.result projection, or owning outcome decoder runs.
    Canonical/semantic body verification remains the later B1 owner's task.
    """
    try:
        names = dict(connection.execute("SELECT name,type FROM sqlite_master WHERE name IN ('context_contents','context_observations')"))
        if not names:
            return  # A proved unavailable-only A1 dataset has no B1 inputs.
        if names != {"context_contents": "table", "context_observations": "table"}:
            raise ContextIntegrityError("physical B1 receipt tables are incomplete")
        capability = connection.execute("SELECT json_valid('{}'),json_type('{}'),json_extract('{\"source\":\"receipt\"}','$.source')").fetchone()
        if capability != (1, "object", "receipt"):
            raise ContextIntegrityError("fixed SQLite outer-JSON projection capability is unavailable")
        metadata = {}
        for content_ref, opaque in connection.execute("SELECT content_digest,payload FROM context_contents"):
            if type(opaque) is not bytes or hashlib.sha256(opaque).hexdigest() != require_digest(content_ref):
                raise ContextIntegrityError("opaque B1 content bytes lost their physical identity")
            outer = connection.execute("""SELECT json_type(CAST(?1 AS TEXT)),
                json_extract(CAST(?1 AS TEXT),'$.event_key'),
                json_extract(CAST(?1 AS TEXT),'$.schedule_revision'),
                json_extract(CAST(?1 AS TEXT),'$.source'),
                json_extract(CAST(?1 AS TEXT),'$.subject_id'),
                json_extract(CAST(?1 AS TEXT),'$.kind')""", (opaque,)).fetchone()
            keys = [row[0] for row in connection.execute("SELECT key FROM json_each(CAST(? AS TEXT))", (opaque,))]
            if outer[0] != "object" or len(keys) != len(OBSERVATION_FIELDS) or set(keys) != OBSERVATION_FIELDS:
                raise ContextIntegrityError("physical B1 content has an invalid closed outer header")
            if any(type(value) is not str or not value for value in outer[1:]):
                raise ContextIntegrityError("physical B1 index projection requires original text identities")
            metadata[content_ref] = outer[1:]
        for ref, content_ref, event_key, received, revision, source, subject, kind in connection.execute(
                "SELECT digest,content_digest,event_key,observed_at,schedule_revision,source,subject_id,kind FROM context_observations"):
            if (type(received) is not str or canonical_timestamp(received) != received
                    or digest({"content_digest": require_digest(content_ref), "observed_at": received}) != require_digest(ref)):
                raise ContextIntegrityError("physical B1 receipt lost its original content/clock identity")
            if metadata.get(content_ref) != (event_key, revision, source, subject, kind):
                raise ContextIntegrityError("physical B1 receipt index differs from its immutable outer header")
    except (ContextContractError, sqlite3.DatabaseError, TypeError, ValueError) as exc:
        if isinstance(exc, ContextIntegrityError):
            raise
        raise ContextIntegrityError("physical B1 outer-header verification failed") from exc


def _headers(connection, plan):
    """No label decoding; physical BLOB hashing is separate from body use."""
    frozen = plan["created_at"]
    envelope = _artifact(connection, plan["dataset_hash"], DATASET_KIND, latest=frozen)
    dataset = validate_dataset(envelope["payload"])
    dataset_clock = _artifact_created_at(connection, envelope["digest"])
    if dataset["event_identity_hash"] != plan["event_identity_hash"]:
        raise ContextIntegrityError("dataset and experiment global identities differ")
    identity = validate_identity_map(_artifact(connection, dataset["event_identity_hash"],
        "context-native-identity-map-v1", latest=dataset_clock))
    bindings = {row["event_key"]: row for row in identity["payload"]["bindings"]}
    configs = {digest(config): config for config in plan["family_configs"]}
    if [g["family_config_hash"] for g in dataset["groups"]] != list(configs):
        raise ContextIntegrityError("dataset must exactly cover every frozen family configuration")
    inventory = {r["event"]["event_key"]: r for r in plan["test_inventory"]}
    all_headers, final_headers, fits, phases = {}, {}, {}, {}
    for group in dataset["groups"]:
        config_ref = group["family_config_hash"]
        config = configs[config_ref]
        hypotheses = [h for h in plan["hypotheses"] if h["family_config_hash"] == config_ref]
        noncontrols = [h for h in hypotheses if h["pretest_status"] != "baseline_control"]
        if len(noncontrols) > 1:
            raise ContextIntegrityError("different ablations need their own actual feature configuration")
        if group["fit_ref"] is None:
            if noncontrols:
                raise ContextIntegrityError("non-control hypothesis has no stored D1 fit result")
            fits[config_ref] = None
        else:
            fit = validate_fit_result(_artifact(connection, group["fit_ref"], FIT_KIND, latest=dataset_clock)["payload"], config=config)
            fits[config_ref] = fit
            if fit["case_hashes"] != sorted(item["case_ref"] for item in group["training_cases"]):
                raise ContextIntegrityError("fit and dataset training inventories differ")
            if fit["case_hashes"] and fit["event_identity_hash"] != identity["digest"]:
                raise ContextIntegrityError("fit does not bind the same full global identity map")
            for h in noncontrols:
                expected_status = "ready" if fit["status"] == "fitted" else fit["status"]
                if h["pretest_status"] != expected_status or h["candidate_artifact"] != fit["effect_hash"]:
                    raise ContextIntegrityError("hypothesis changed the actual pretest fit status or chosen candidate")
            for ref, effect in fit["candidate_artifacts"].items():
                if _artifact(connection, ref, "context-effect-v1", latest=_artifact_created_at(connection, group["fit_ref"]))["payload"] != effect:
                    raise ContextIntegrityError("stored candidate differs from the exact D1 alpha inventory")
        seen, finals = set(), set()
        for phase in ("training_cases", "final_cases"):
            ordered = []
            for item in group[phase]:
                case = _artifact(connection, item["case_ref"], CASE_KIND, latest=dataset_clock)
                header = case_header({"case": case, "artifacts": {}, "observations": ()}, config=config)
                event, decision = header["event"], header["base"]["cutoff"]
                key = event["event_key"]
                if key in seen:
                    raise ContextIntegrityError("duplicate canonical native event within a family")
                seen.add(key)
                ordered.append((decision, key))
                if header["event_identity_hash"] != identity["digest"]:
                    raise ContextIntegrityError("case does not retain the global dataset map")
                if key not in bindings or any(bindings[key][name] != event[name] for name in ("home_id", "away_id")):
                    raise ContextIntegrityError("case participants differ from their frozen native map")
                if header["outcome_ref"] not in item["observation_refs"]:
                    raise ContextIntegrityError("owning opaque outcome reference is absent from its receipt pool")
                expected_phase = "train" if decision < config["train_end"] else "tune" if decision < config["tune_end"] else "final"
                if phase == "training_cases":
                    if expected_phase == "final" or key in inventory:
                        raise ContextIntegrityError("final event cannot enter fitting, even with another case hash")
                else:
                    expected = inventory.get(key)
                    if expected_phase != "final" or expected is None or (event, decision) != (expected["event"], expected["decision_at"]):
                        raise ContextIntegrityError("final case differs from its exact frozen Event/decision/block")
                    finals.add(key)
                    final_headers[item["case_ref"]] = header
                if key in phases and phases[key] != (expected_phase, decision):
                    raise ContextIntegrityError("native event crosses training/tuning/final families or decisions")
                phases[key] = expected_phase, decision
                all_headers[item["case_ref"]] = case
            if ordered != sorted(ordered):
                raise ContextContractError("case inventory must be in original decision/event order")
        for item in group["unavailable_final"]:
            key = item["event_key"]
            expected = inventory.get(key)
            if (key in finals or expected is None or item["decision_at"] != expected["decision_at"]
                    or config["sport"] != "tennis" or not event_in_population(expected["event"], config["population"])):
                raise ContextIntegrityError("unavailable native state-key capability is not derivable from this frozen scope")
            from context_models.replay import ReplayUnavailable, replay_code_hashes
            try:
                replay_code_hashes(config["sport"])
            except ReplayUnavailable as exc:
                if exc.reason != item["reason"]:
                    raise ContextIntegrityError("declared unavailable reason differs from owning replay capability") from exc
            else:
                raise ContextIntegrityError("declared missing replay capability is actually implemented")
            finals.add(key)
        matching = {key for key, row in inventory.items() if event_in_population(row["event"], config["population"])}
        if finals != matching:
            raise ContextIntegrityError("final cases and proven pretest gaps must partition the whole frozen population")
    _physical_receipt_preflight(connection)
    # An opaque reference must not launder a final label into a training pool.
    # Validate ALL training receipt indices before resolving ANY B1 body. The
    # actual bytes/indices are still fully cross-checked by B1 afterwards.
    final_outcomes = {header["outcome_ref"] for header in final_headers.values()}
    for group in dataset["groups"]:
        for item in group["training_cases"]:
            payload = all_headers[item["case_ref"]]["payload"]
            for ref in item["observation_refs"]:
                if ref in final_outcomes:
                    raise ContextIntegrityError("training pool attempts to open a frozen final outcome")
                index = connection.execute("SELECT event_key,kind,observed_at FROM context_observations WHERE digest=?", (ref,)).fetchone()
                if index is None:
                    raise ContextIntegrityError("training pool references a missing physical receipt")
                key, kind, received = index
                if canonical_timestamp(received) != received:
                    raise ContextIntegrityError("noncanonical original training receipt clock")
                if key in inventory:
                    raise ContextIntegrityError("training pool contains a frozen final native event receipt")
                if kind == "match_outcome":
                    if ref != payload["outcome_ref"] or key != payload["event"]["event_key"]:
                        raise ContextIntegrityError("training pool contains another event's outcome")
                elif received > payload["base"]["cutoff"]:
                    raise ContextIntegrityError("training pool contains a post-decision feature/source receipt")
    return {"plan": plan, "dataset": dataset, "headers": all_headers, "final_headers": final_headers, "fits": fits}


def _receipt(connection, ref):
    """Resolve actual B1 storage, never an external hash-shaped envelope."""
    row = connection.execute(_SELECT+" WHERE r.digest=?", (require_digest(ref),)).fetchone()
    if row is None:
        raise ContextIntegrityError("referenced physical B1 receipt is missing")
    return _decode_receipt(row)


def outcome_revisions(connection, frozen, *, event, through):
    """Audit original training phases or an already-opened final holdout.

    The caller establishes which labels are authorized and supplies that
    immutable phase/report boundary. Compare normalized terminal facts, not
    receipt metadata. Later receipts never rewrite a historical claim.
    """
    from context_sources.outcomes import validate_outcome_record
    frozen = validate_outcome_record(frozen, event=event)
    refs, conflicting = [], False
    for ref, content_ref, received in connection.execute(
            "SELECT digest,content_digest,observed_at FROM context_observations WHERE event_key=? ORDER BY observed_at,digest",
            (event["event_key"],)):
        if (canonical_timestamp(received) != received
                or digest({"content_digest": require_digest(content_ref), "observed_at": received}) != require_digest(ref)):
            raise ContextIntegrityError("outcome revision index lost its original physical receipt identity")
        if received > through:
            continue
        row = _receipt(connection, ref)
        if row["kind"] != "match_outcome" or (row["source"], row["source_schema"]) != (frozen["source"], frozen["source_schema"]):
            continue
        if any(row[field] != frozen[field] for field in ("sport", "competition", "format", "schedule_revision")):
            continue
        selected = {**row, "evidence_class": "prospective", "effective_at": row["observed_at"], "publication_resolution": None}
        selected = validate_outcome_record(selected, event=event)
        refs.append(ref)
        if received >= frozen["observed_at"] and selected["payload"] != frozen["payload"]:
            conflicting = True
    if frozen["digest"] not in refs:
        raise ContextIntegrityError("frozen owning outcome is absent from its actual native revision pool")
    return sorted(refs), conflicting


def resolve_case(connection, item, *, config, plan, latest):
    case = _artifact(connection, item["case_ref"], CASE_KIND, latest=plan["created_at"])
    payload = case_header({"case": case, "artifacts": {}, "observations": ()}, config=config)
    decision = payload["base"]["cutoff"]
    replay = _artifact(connection, payload["replay_ref"], "context-base-replay-v1", latest=_artifact_created_at(connection, case["digest"]))
    recipe_ref = require_digest(replay["payload"].get("recipe_hash"), "original replay recipe")
    refs = {payload["event_identity_hash"]: "context-native-identity-map-v1", recipe_ref: "context-base-replay-recipe-v1"}
    refs.update({ref: "football-participation-v1" for ref in payload["preprocessing_refs"]})
    artifacts = {ref: _artifact(connection, ref, kind, latest=_artifact_created_at(connection, case["digest"]))
                 for ref, kind in refs.items()}
    artifacts[replay["digest"]] = replay
    if replay["payload"].get("reconstructed_at", latest) > _artifact_created_at(connection, replay["digest"]):
        raise ContextIntegrityError("replay was stored before its claimed actual reconstruction")
    recipe = artifacts[recipe_ref]["payload"]
    if recipe.get("code_revision") != plan["code_revision"]:
        raise ContextIntegrityError("original source replay revision differs from frozen experiment code")
    observations = []
    for ref in item["observation_refs"]:
        row = _receipt(connection, ref)
        if row["observed_at"] > latest or row["observed_at"] > _artifact_created_at(connection, case["digest"]):
            raise ContextIntegrityError("case uses a source receipt from after its actual creation/evaluation")
        # No archive qualification is fabricated. D1 explicitly excludes late
        # feature receipts; the own target uses its actual result receipt.
        cutoff = latest if row["kind"] == "match_outcome" else decision
        selected = {**row, "effective_at": row["observed_at"], "publication_resolution": None,
                    "evidence_class": "prospective" if row["observed_at"] <= cutoff else "retrospective"}
        _check_selected_row(selected)
        observations.append(selected)
    # A declared causal native pool cannot suppress an already stored revision
    # for one of its own events. The recipe still owns which historical events
    # enter the original model; this does not invent a complete league corpus.
    own_refs = set(item["observation_refs"])
    event_keys = {r["event_key"] for r in observations if r["kind"] != "match_outcome"}
    for key in sorted(event_keys):
        for ref, content_ref, received, kind in connection.execute(
                "SELECT digest,content_digest,observed_at,kind FROM context_observations WHERE event_key=?", (key,)):
            if canonical_timestamp(received) != received:
                raise ContextIntegrityError("noncanonical receipt index clock")
            if digest({"content_digest": require_digest(content_ref), "observed_at": received}) != require_digest(ref):
                raise ContextIntegrityError("receipt index does not retain its original physical identity")
            if received <= decision and ref not in own_refs:
                if kind != "match_outcome":
                    raise ContextIntegrityError("declared causal native pool omits an already-known source revision")
                # Kind is merely an index, not an independently trusted proof.
                # A forged index cannot hide a base/context correction. These
                # are earlier history events; the global preflight prevented
                # final-event receipts from entering a training native pool.
                _receipt(connection, ref)
    return {"case": case, "artifacts": artifacts, "observations": tuple(observations)}


def _prepare(connection, experiment_hash, *, evaluated_at):
    from context_models.training import fit_family
    clock = canonical_timestamp(evaluated_at)
    plan = _load_experiment(connection, experiment_hash)
    if clock < plan["created_at"]:
        raise ContextIntegrityError("evaluation cannot precede actual experiment creation")
    checked = _headers(connection, plan)
    checked["training_outcome_revision_refs"] = {}
    configs = {digest(config): config for config in plan["family_configs"]}
    # ALL family train/final headers were checked above before the first label.
    for group in checked["dataset"]["groups"]:
        config_ref = group["family_config_hash"]
        config = configs[config_ref]
        cases = tuple(resolve_case(connection, item, config=config, plan=plan, latest=plan["created_at"])
                      for item in group["training_cases"])
        for case in cases:
            payload = case["case"]["payload"]
            boundary = config["train_end"] if payload["base"]["cutoff"] < config["train_end"] else config["tune_end"]
            outcome = next(row for row in case["observations"] if row["digest"] == payload["outcome_ref"])
            # D1 already excludes an original label first received after its
            # phase. Do not pretend it was eligible or silently substitute it.
            if outcome["observed_at"] <= boundary:
                refs, conflicting = outcome_revisions(connection, outcome, event=payload["event"], through=boundary)
                checked["training_outcome_revision_refs"][payload["outcome_ref"]] = refs
                if conflicting:
                    raise ContextIntegrityError("frozen label conflicts with an owning result within original train/tune phase")
        assembly = assemble_training_cases(cases, config)
        if group["fit_ref"] is not None:
            actual = fit_family(assembly["rows"], config, cases=cases)
            if canonical_bytes(actual) != canonical_bytes(checked["fits"][config_ref]):
                raise ContextIntegrityError("stored fit does not exactly reproduce every original train/tune candidate")
            fit_clock = _artifact_created_at(connection, group["fit_ref"])
            if any(_artifact_created_at(connection, c["case"]["digest"]) > fit_clock for c in cases):
                raise ContextIntegrityError("fit predates its actual source-resolved case inventory")
    return checked


def prepare_dataset(path: Path, experiment_hash: str, *, evaluated_at: datetime) -> dict:
    """Header/fit verification only; does not open final labels or approve."""
    with _reader(path) as connection:
        return _prepare(connection, experiment_hash, evaluated_at=evaluated_at)
