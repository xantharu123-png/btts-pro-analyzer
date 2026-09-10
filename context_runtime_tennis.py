"""Owning live Tennis replay on D4's transaction-bound lazy inventory.

Known v1 original code, actual predecision tour state, current native B1 event,
full causal tour inventory and v3 features are replayed. Historical native
player/state aliases and an empirical effect improvement remain unproved.
No source request, fit, activation, live SQLite path or old-row rewrite.
"""
from datetime import datetime
from dataclasses import dataclass
import hashlib
from pathlib import Path

from context_models.contracts import canonical_timestamp, digest
from context_models.tennis_live import (
    BASE_VERSION, CODE_PATHS, ORIGIN_KIND, ORIGINAL_ARTIFACT_KIND, live_event,
    original_base, validate_live_winner_origin, validate_original_publication,
)
from context_models.tennis_v3 import FEATURE_VERSION, tennis_features_v3
from context_sources.tennis_status import STATUS_SCHEMA, select_tennis_observations
from model_artifacts import ArtifactIntegrityError, canonical_bytes
from runtime_paths import RuntimeArtifactTrustError


def _same(actual, expected, label):
    if canonical_bytes(actual) != canonical_bytes(expected):
        raise ArtifactIntegrityError(label)


def _code_variants():
    # Only line-terminator equivalence, not source normalization or guessed
    # recipe compatibility. A changed owning implementation requires a new
    # explicitly supported replay before historical originals can be released.
    root = Path(__file__).resolve().parent
    result = {}
    for name in CODE_PATHS:
        raw = (root/name).read_bytes()
        lf = raw.replace(b"\r\n", b"\n")
        result[name] = {hashlib.sha256(body).hexdigest()
                       for body in (raw, lf, lf.replace(b"\n", b"\r\n"))}
    return result


def _native_event(row):
    data = row["payload"]
    return live_event({"event_key": row["event_key"], "sport": "tennis", "competition": row["competition"],
        "format": "singles", "home_id": data["participant_ids"][0], "away_id": data["participant_ids"][1],
        "scheduled_start": data["scheduled_start"], "schedule_revision": row["schedule_revision"],
        "status": "scheduled", "tour": data["tour"], "surface": None, "indoor": None})


@dataclass(frozen=True)
class LiveReplayDescriptor:
    artifact_ref: str
    artifacts: object
    receipts: object
    history_max_bytes: int | None
    history_cache: object = None


def _cold_replay_history(receipts, *, cutoff, tour, max_bytes):
    """One complete causal tuple; owning selection/validation stays exact.

    Select each fully decoded receipt with the unchanged owning tuple API,
    then sort the complete result using its original total order. Nothing is
    latest-only or participant-pruned. No full decoded input inventory exists.
    """
    from context_runtime_inventory import VerifiedReceiptMapping
    history, used = [], 0
    rows = (receipts.values_at_or_before(cutoff) if isinstance(receipts, VerifiedReceiptMapping)
            else receipts.values())
    for row in rows:
        if "source_schema" not in row:  # Opaque unopened D2 final.
            continue
        selected = select_tennis_observations((row,), cutoff=cutoff, tour=tour)
        for candidate in selected:
            if max_bytes is not None:
                used += len(canonical_bytes(candidate))
                if used > max_bytes:
                    raise RuntimeArtifactTrustError("complete Tennis history exceeds canonical input budget")
            history.append(candidate)
    history.sort(key=lambda row: (row["observed_at"], row["digest"]))
    return tuple(history)


def _replay_history(receipts, *, cutoff, tour, max_bytes, cache=None):
    # Cache keys must not broaden the owning tuple selector's typed API.
    select_tennis_observations((), cutoff=cutoff, tour=tour)
    if cache is not None:
        cached = cache._lookup(receipts, cutoff=cutoff, tour=tour, max_bytes=max_bytes)
        if cached is not None:
            return cached
    history = _cold_replay_history(receipts, cutoff=cutoff, tour=tour, max_bytes=max_bytes)
    if cache is not None:
        cache._store(receipts, history, cutoff=cutoff, tour=tour)
    return history


def _verify_live_original(ref, publication, artifacts, created_at, receipts, variants, history_max_bytes, history_cache):
    """Own all decoded state/history in this one call, never in descriptors."""
    from tennis.predict import predict_match
    from tennis.tour_state import _decode_wrapper
    validate_original_publication(publication, created_at=created_at[ref])
    origin = publication["origin"]
    original_base(origin)  # Preserve the original's owning distribution check.
    cutoff, event = origin["cutoff"], origin["event"]
    decision = datetime.fromisoformat(cutoff)
    for name, code_hash in origin["code_hashes"].items():
        if code_hash not in variants[name]:
            raise ArtifactIntegrityError("original Tennis code has no supported exact replay")
    state_ref = origin["state_hash"]
    envelope = artifacts.get(state_ref)
    if (envelope is None or envelope["kind"] != "tennis-tour-state"
            or canonical_timestamp(created_at[state_ref]) > cutoff):
        raise ArtifactIntegrityError("live original lacks its actual predecision tour state")
    state = _decode_wrapper(envelope["payload"], event["tour"])
    if state.built_at > decision.timestamp():
        raise ArtifactIntegrityError("live original state was built after its decision")
    history = _replay_history(receipts, cutoff=decision, tour=event["tour"], max_bytes=history_max_bytes,
                              cache=history_cache)
    target = [row for row in history if row["event_key"] == event["event_key"]]
    newest = max((row["observed_at"] for row in target), default=None)
    latest = [row for row in target if row["observed_at"] == newest]
    if (len(latest) != 1 or latest[0]["source_schema"] != STATUS_SCHEMA
            or latest[0]["digest"] != origin["native_receipt"]
            or latest[0]["observed_at"] != origin["native_observed_at"]
            or latest[0]["payload"]["competition_revision"] != origin["competition_revision"]
            or latest[0]["payload"]["status"] != "scheduled" or latest[0]["payload"]["issues"]):
        raise ArtifactIntegrityError("live original native current input was absent or revised")
    _same(_native_event(latest[0]), event, "live original differs from its native event")
    recorded = []
    args = {name: origin["inputs"][name] for name in (
        "player_a", "player_b", "surface", "best_of", "tour", "indoor")}
    predict_match(state, **args, as_of=decision, workload_history=(), original_capture=recorded.append)
    _same(recorded, [{"inputs": origin["inputs"], "values": origin["values"]}],
          "live original differs from its actual tour model calculation")


def verify_live_originals(artifacts, created_at, receipts, limitations, *, history_max_bytes=None):
    """Verify every original, including an unreferenced safe orphan publication."""
    from context_runtime_history_cache import EncodedHistoryCache, MAX_ENCODED_HISTORY_BYTES
    from context_runtime_inventory import VerifiedReceiptMapping
    variants, checked, history_cache = None, {}, None
    # Opaque unopened D2 final receipts are never decoded here or promoted into
    # source inputs. A live original requiring such a receipt will lack its
    # verified native target and fail below, not silently use an older alias.
    for ref, envelope in artifacts.items():
        if envelope["kind"] != ORIGINAL_ARTIFACT_KIND:
            continue
        if variants is None:
            variants = _code_variants()
            if isinstance(receipts, VerifiedReceiptMapping):
                history_cache = EncodedHistoryCache(receipts, max_bytes=MAX_ENCODED_HISTORY_BYTES)
        _verify_live_original(ref, envelope["payload"], artifacts, created_at, receipts, variants, history_max_bytes, history_cache)
        checked[ref] = LiveReplayDescriptor(ref, artifacts, receipts, history_max_bytes, history_cache)
    # Replaying a recorded name-based model input does NOT prove the native
    # historical player/state association needed by D1 or a passed D2 corpus.
    if checked:
        limitations.add("d1-original-replay-context-unavailable")
    return checked


def verify_live_snapshot(payload, key, originals, *, effect, approval, limitations):
    """Return False only for an actually different producer/version."""
    from context_transport import replay_context_payload
    base = payload["base"]
    reference = base.get("reference_weights")
    if (base.get("version") != BASE_VERSION
            and not (type(reference) is dict and reference.get("kind") == ORIGIN_KIND)):
        return False
    validate_live_winner_origin(base, payload["event"])
    ref = digest({"kind": ORIGINAL_ARTIFACT_KIND, "payload": {"schema": 1, "origin": reference}})
    if ref not in originals:
        raise ArtifactIntegrityError("live worker lacks its exact original publication")
    descriptor = originals[ref]
    original = original_base(descriptor.artifacts[ref]["payload"]["origin"])
    history = _replay_history(descriptor.receipts, cutoff=datetime.fromisoformat(original["cutoff"]),
        tour=original["reference_weights"]["event"]["tour"], max_bytes=descriptor.history_max_bytes,
        cache=descriptor.history_cache)
    _same(base, original, "live worker substituted its published original")
    if payload["features"]["version"] != FEATURE_VERSION:
        raise ArtifactIntegrityError("live winner v1 has no owning feature version of this kind")
    _same(payload["observation_refs"], sorted(row["digest"] for row in history),
          "live worker omitted or added causal tour observations")
    features = tennis_features_v3(payload["event"], history, original,
                                 cutoff=datetime.fromisoformat(original["cutoff"]))
    _same(payload["features"], features, "live worker features differ from actual source replay")
    replay_context_payload(payload, key=key, effect_artifact=effect, approval=approval)
    # Actual native source completeness and historical state joins remain
    # outside these mechanical checks. Do not upgrade the global D3/D2 status.
    limitations.add("d3-owning-source-feature-replay-unavailable")
    return True
