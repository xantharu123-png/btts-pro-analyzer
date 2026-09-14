"""Operational, read-only release check, explicitly NOT a historical audit.

Check SQLite storage and the active model objects the new application must
load. Historical feature construction, fits and evaluation replay remain in
context_runtime.verify_context_database and the unchanged activation checks.
Neither this report nor a successful deployment grants a model approval.
"""
from datetime import datetime
import sqlite3

from context_models.contracts import (
    require_digest, validate_context_approval, validate_effect_artifact,
)
from context_runtime import _manifest_rows, _open_database, _verify_schema, _verify_slots
from context_runtime_inventory import VerifiedArtifactMapping
from model_artifacts import ArtifactIntegrityError, _validate_stored_timestamp, canonical_bytes
from runtime_paths import RuntimeArtifactTrustError


# Streamed file input: this is a disk envelope, not an in-memory allocation.
MAX_DEPLOYMENT_CONTEXT_BYTES = 4 * 1024 * 1024 * 1024
DEPLOYMENT_CHECKS = ["active_models", "manifest_chain", "sqlite_integrity",
                     "sqlite_references", "sqlite_schema"]


def _active_models(slots, artifacts, created_at):
    from tennis.tour_state import _check_predictions, _decode_wrapper

    def resolve(ref, kind=None):
        envelope = artifacts[require_digest(ref, "active artifact reference")]
        if kind is not None and envelope["kind"] != kind:
            raise ArtifactIntegrityError("active reference has the wrong artifact kind")
        return envelope["payload"]

    for ref in set(slots.values()):
        envelope = artifacts[ref]  # Hash, canonical JSON and stored timestamp.
        kind, payload = envelope["kind"], envelope["payload"]
        if kind == "tennis-tour-state":
            tour = payload.get("state", {}).get("tour")
            if tour not in ("ATP", "WTA"):
                raise ArtifactIntegrityError("active model has an unknown tour")
            _check_predictions(_decode_wrapper(payload, tour,
                decision_cutoff=created_at[ref].timestamp()))
        elif kind == "context-effect-v1":
            if canonical_bytes(validate_effect_artifact(payload)) != canonical_bytes(payload):
                raise ArtifactIntegrityError("noncanonical active effect")
            if datetime.fromisoformat(payload["training_end"]) > created_at[ref]:
                raise ArtifactIntegrityError("active effect predates its training")
            for dependency in payload["preprocessing_artifacts"].values():
                resolve(dependency)
        elif kind == "context-approval-v1":
            if canonical_bytes(validate_context_approval(payload)) != canonical_bytes(payload):
                raise ArtifactIntegrityError("noncanonical active approval")
            effect = validate_effect_artifact(resolve(payload["effect_hash"], "context-effect-v1"))
            if any(payload[name] != effect[name] for name in
                   ("sport", "family", "feature_version", "population", "coverage", "model_variant")):
                raise ArtifactIntegrityError("active approval and effect scope differ")
            evaluated = datetime.fromisoformat(payload["evaluated_at"])
            if not datetime.fromisoformat(effect["training_end"]) <= evaluated <= created_at[ref]:
                raise ArtifactIntegrityError("active approval chronology differs")
            resolve(payload["report_hash"], "context-evaluation-v1")
            resolve(payload["experiment_hash"], "context-experiment-v1")
    _verify_slots(slots, artifacts)


def verify_context_deployment(path, *, input_mode="memory"):
    """Check an explicit private image; never repair or open a live WAL DB.

    The small memory mode is retained for portable/offline fixtures. Production
    must explicitly use sealed_file, including its Linux ownership, descriptor,
    no-companion, query-only and streamed before/after identity checks.
    """
    if input_mode == "memory":
        reader = _open_database(path)
    elif input_mode == "sealed_file":
        from context_runtime_input import open_sealed_connection
        reader = open_sealed_connection(path, max_bytes=MAX_DEPLOYMENT_CONTEXT_BYTES)
    else:
        raise RuntimeArtifactTrustError("unsupported deployment input mode")
    with reader as connection:
        if not connection.in_transaction:
            connection.execute("BEGIN")
        try:
            tables = _verify_schema(connection)
            artifacts = VerifiedArtifactMapping(connection)
            created_at = {require_digest(ref, "artifact identity"): datetime.fromisoformat(
                _validate_stored_timestamp(created, label="artifact creation time"))
                for ref, created in connection.execute("SELECT digest,created_at FROM artifacts")}
            manifests, current, _ = _manifest_rows(connection, artifacts, created_at)
            slots = manifests[current]["slots"] if current is not None else {}
            _active_models(slots, artifacts, created_at)
            counts = {label: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                      if table in tables else 0 for label, table in {
                          "artifacts": "artifacts", "manifests": "manifests",
                          "contents": "context_contents", "observations": "context_observations",
                          "snapshots": "context_snapshots", "rollbacks": "context_model_rollbacks"}.items()}
            return {"schema": 2, "verification_level": "deployment",
                    "historical_analysis_verified": False, "empirical_approval_verified": False,
                    "checks": list(DEPLOYMENT_CHECKS), "counts": counts,
                    "active_manifest": current, "active_slots": dict(slots),
                    "tour_states": {tour: slots[f"tennis:{tour}"] for tour in ("ATP", "WTA")
                                    if f"tennis:{tour}" in slots}}
        except (ValueError, TypeError, KeyError, AttributeError, sqlite3.Error,
                ArithmeticError, RecursionError, MemoryError) as exc:
            raise ArtifactIntegrityError("context deployment verification failed") from exc
        finally:
            connection.rollback()
