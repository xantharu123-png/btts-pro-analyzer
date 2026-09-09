"""Read an existing worker revision without calculating or publishing anything.

The producer owns source/approval verification. This read boundary binds the
stored transport to the consumer's exact native event and original decision;
it does not certify source truth, calibration or an empirical improvement.
No missing/corrupt reference is silently converted to a new prediction.
"""
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path

from context_copy import public_context_summary
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, canonical_timestamp,
    require_digest, require_object, validate_event,
)
from context_models.dataset import _reader
from context_snapshots import _decode_snapshot
from context_transport import project_context_market
from model_artifacts import canonical_bytes


def validate_context_reference(reference: dict) -> dict:
    """Validate only the closed transport identity; no source/IO authority."""
    require_object(reference, {"schema", "kind", "key", "payload_digest"},
                   label="stored context consumer reference")
    if (type(reference["schema"]) is not int or reference["schema"] != 1
            or reference["kind"] != "context-consumer-reference-v1"):
        raise ContextContractError("unknown context consumer reference version")
    require_digest(reference["key"], "worker input key")
    require_digest(reference["payload_digest"], "worker payload digest")
    return deepcopy(reference)


@contextmanager
def _read_context_snapshot(path: Path, reference: dict, *, expected_event: dict,
        expected_cutoff: str):
    """Hold one bound read transaction, including an owning adapter's checks.

    This internal seam returns stored bytes, not model/source approval. A caller
    must project its actual market before using a probability. The original
    reader's final path/companion checks still execute before any result escapes.
    """
    reference = validate_context_reference(reference)
    event = validate_event(expected_event)
    if (type(expected_cutoff) is not str
            or canonical_timestamp(expected_cutoff) != expected_cutoff):
        raise ContextContractError("consumer requires its canonical stored decision")
    with _reader(Path(path)) as connection:
        schema = connection.execute(
            "SELECT type FROM sqlite_master WHERE name='context_snapshots'",
        ).fetchall()
        if schema != [("table",)]:
            raise ContextIntegrityError("referenced context snapshot table is unavailable")
        columns = connection.execute("PRAGMA table_xinfo(context_snapshots)").fetchall()
        expected_columns = [(0, "key", "TEXT", 1, None, 1, 0),
                            (1, "payload", "BLOB", 1, None, 0, 0),
                            (2, "payload_digest", "TEXT", 1, None, 0, 0)]
        if columns != expected_columns:
            raise ContextIntegrityError("referenced context snapshot schema is invalid")
        row = connection.execute(
            "SELECT key,payload,payload_digest FROM context_snapshots WHERE key=?",
            (reference["key"],),
        ).fetchone()
        if row is None:
            raise ContextIntegrityError("referenced worker context snapshot is missing")
        if row[0] != reference["key"] or row[2] != reference["payload_digest"]:
            raise ContextIntegrityError("stored context reference and payload identity differ")
        payload = _decode_snapshot(*row)
        base = payload.get("base")
        if type(base) is not dict:
            raise ContextIntegrityError("context snapshot base must be an object")
        if (canonical_bytes(payload.get("event")) != canonical_bytes(event)
                or base.get("cutoff") != expected_cutoff):
            raise ContextIntegrityError("context snapshot belongs to another consumer event or decision")
        yield connection, payload


def load_context_market(path: Path, reference: dict, selected_market: str, *,
        expected_event: dict, expected_cutoff: str, factor_groups: dict | None = None) -> dict:
    """Project the exact stored revision without a provider, fit or prediction.

    Schedule invalidation remains the caller's existing live-state responsibility.
    Groups, when supplied, are the owning adapter's explicit feature map.
    """
    with _read_context_snapshot(path, reference, expected_event=expected_event,
            expected_cutoff=expected_cutoff) as (_, payload):
        projection = project_context_market(payload, reference, selected_market)
        display_input = {**payload["result"], "selected_market": selected_market}
        if factor_groups is not None:
            display_input["factor_groups"] = factor_groups
        public = public_context_summary(display_input)
    return {"projection": projection, "public_summary": public}
