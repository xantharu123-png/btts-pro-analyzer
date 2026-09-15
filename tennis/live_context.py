"""Daily worker ownership of same-call live winner originals and context refs.

This module does IO outside the CPU-only B3 callback. It consumes existing
ESPN receptions only, never fetches, joins historical native names, or fits.
Missing context/approval leaves the existing prediction unchanged.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from context_models.activation import verify_approval
from context_models.contracts import (ContextContractError, ContextIntegrityError,
    canonical_timestamp, digest, event_in_population, require_digest, validate_effect_artifact)
from context_models.dataset import _artifact, _reader
from context_models.experiments import _artifact_created_at
from context_models.tennis_live import (CODE_PATHS, MARKETS, ORIGIN_KIND,
    ORIGINAL_ARTIFACT_KIND, SIDECAR_KIND, live_event, original_base,
    validate_context_model, validate_original_publication)
from context_models.tennis_v3 import tennis_features_v3
from context_sources.tennis_status import (STATUS_SCHEMA, normalize_tennis_status,
    tennis_observations_as_of)
from context_snapshots import _decode_snapshot, compute_once
from context_transport import (KIND, calculate_context_payload, context_consumer_reference,
    context_payload_key)
from model_artifacts import _load_active, _load_artifact, put_artifact
from context_json import canonical_context_bytes as canonical_bytes


_CURRENT = ContextVar("tennis_live_original_worker", default=None)


def _now():
    return datetime.now(timezone.utc)


def active_worker():
    return _CURRENT.get()


def has_stored_context(row):
    try:
        context = json.loads(row.get("context_json") or "{}")
    except (TypeError, ValueError):
        return False  # Does not turn an old opaque legacy row into native proof.
    return type(context) is dict and "context_model" in context


def _equal(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


def _receipt(row, observed):
    return digest({"content_digest": digest(row), "observed_at": canonical_timestamp(observed)})


def _event(row):
    data = row["payload"]
    return live_event({"event_key": row["event_key"], "sport": "tennis", "competition": row["competition"],
        "format": "singles", "home_id": data["participant_ids"][0], "away_id": data["participant_ids"][1],
        "scheduled_start": data["scheduled_start"], "schedule_revision": row["schedule_revision"],
        "status": "scheduled", "tour": data["tour"], "surface": None, "indoor": None})


class _Inventory:
    """One prepared immutable A1/D2 inventory per worker, not per-card replay."""
    def __init__(self, connection):
        self.effects, self.approvals = {}, {}
        manifest, slots = _load_active(connection)
        self.publication = (canonical_timestamp(connection.execute(
            "SELECT published_at FROM manifests WHERE digest=?", (manifest,)).fetchone()[0]) if manifest else None)
        for ref in set(slots.values()):
            artifact = _load_artifact(connection, ref)
            if artifact["kind"] == "context-effect-v1":
                checked = validate_effect_artifact(artifact["payload"])
                if not _equal(checked, artifact["payload"]):
                    raise ContextIntegrityError("active fitted context effect is not canonical")
                self.effects[ref] = (artifact, _artifact_created_at(connection, ref))
        for slot, ref in slots.items():
            if slot.startswith("context-approval:"):
                effect_hash = require_digest(slot[len("context-approval:"):], "approval slot effect")
                envelope = verify_approval(connection, ref)
                if envelope["payload"]["effect_hash"] != effect_hash or effect_hash not in self.effects:
                    raise ContextIntegrityError("active approval is not coupled to the actual effect")
                self.approvals[effect_hash] = envelope

    def select(self, event, base, features):
        from context_models.tennis_effect import STATUS_WINNER_VARIANT, _prepare
        cutoff = base["cutoff"]
        if self.publication is None or self.publication > cutoff:
            return None, None, None, "no-predecision-effect-manifest"
        matches = []
        for ref, (envelope, created) in self.effects.items():
            effect = envelope["payload"]
            if (created <= cutoff and effect["training_end"] <= cutoff
                    and effect["family"] == base["family"] and effect["sport"] == "tennis"
                    and effect["feature_version"] == features["version"]
                    and effect["coverage"] == features["coverage"]
                    and effect["model_variant"] == STATUS_WINNER_VARIANT
                    and event_in_population(event, effect["population"])):
                matches.append((ref, envelope))
        if len(matches) != 1:
            return None, None, None, "effect-unavailable" if not matches else "effect-ambiguous"
        ref, envelope = matches[0]
        approval = self.approvals.get(ref)
        if approval is not None:
            claim = approval["payload"]
            if (claim["evaluated_at"] > cutoff or base["version"] not in claim["base_versions"]
                    or any(features["states"].get(name) != "available" or not features["refs"].get(name)
                           for name in envelope["payload"]["feature_names"])):
                approval = None
            else:
                if not set(claim["target_markets"]) <= set(base["markets"]):
                    raise ContextIntegrityError("approval targets differ from the original winner catalog")
                _prepare(base, features, envelope["payload"], event)
        return envelope, ref, approval, "approved" if approval is not None else "no-owning-approval"


class LiveWorker:
    def __init__(self, path, *, progress=None):
        self.path = Path(path)
        self.capture = None
        self.bindings, self.pending = {}, []
        self._pending_histories = {}
        self.finished = False
        self.reasons = []
        self._progress = progress

    def _report(self, phase, **details):
        if self._progress is not None:
            self._progress({"phase": phase, **details})

    def attach_capture(self, capture):
        if self.capture is not None or self.finished:
            raise ContextContractError("live worker already owns a capture")
        self.capture = capture

    def bind_fixture(self, fixture, *, tour, tournament_id, competition, grouping_slug):
        """Retain the SAME response's native current identity before formatting.

        No receipt clock is synthesized here. A fake/unobserved fixture is not
        upgraded by finding old players with matching display names.
        """
        if self.capture is None:
            return
        candidates = {}
        for observed, rows in self.capture.pending:
            row = rows[0]
            if row["payload"]["tour"] != tour or row["event_key"].rsplit(":", 1)[-1] != str(competition.get("id")):
                continue
            projected = normalize_tennis_status(tour, tournament_id, competition,
                grouping_slug=grouping_slug, observed_at=observed)[0]
            if _equal(projected, row) and row["payload"]["status"] == "scheduled" and not row["payload"]["issues"]:
                candidates[_receipt(row, observed)] = (row, canonical_timestamp(observed))
        if not candidates:
            return
        newest = max(clock for _, clock in candidates.values())
        selected = [(ref, row, clock) for ref, (row, clock) in candidates.items() if clock == newest]
        if len(selected) != 1:
            return
        ref, row, clock = selected[0]
        self.bindings[id(fixture)] = {"fixture": deepcopy(fixture), "row": deepcopy(row),
            "receipt": ref, "observed_at": clock}

    def wants_original(self, fixture, state):
        return id(fixture) in self.bindings and getattr(state, "artifact_hash", None) is not None

    def bind_pending(self, row, *, decision_at):
        """Reuse ONLY a verified stored native origin, without fetching.

        A new current status may refresh the receipt but may not substitute
        participants, tour, schedule, or a guessed link from display names.
        """
        sidecar = validate_context_model(json.loads(row["context_json"])["context_model"])
        event, ref = sidecar["event"], sidecar["reference"]
        if (row["fixture_source"] != "ESPN" or event["event_key"] != f"espn:tennis:{row['tour']}:match:{row['provider_event_id']}"
                or canonical_timestamp(row["scheduled_start_utc"]) != event["scheduled_start"]
                or canonical_timestamp(datetime.fromtimestamp(row["created_utc"], timezone.utc)) != sidecar["cutoff"]):
            raise ContextIntegrityError("pending native identity differs from its immutable context")
        with _reader(self.path) as connection:
            publication = _load_artifact(connection, sidecar["original_artifact_hash"])
            created_at = _artifact_created_at(connection, sidecar["original_artifact_hash"])
            saved = connection.execute("SELECT payload,payload_digest FROM context_snapshots WHERE key=?", (ref["key"],)).fetchone()
            from context_snapshot_storage import freeze_reference_bytes
            reference_data = None if saved is None else freeze_reference_bytes(saved[0], connection)
        if publication["kind"] != ORIGINAL_ARTIFACT_KIND:
            raise ContextIntegrityError("pending context has no owning original publication")
        validate_original_publication(publication["payload"], created_at=created_at)
        if saved is None:
            raise ContextIntegrityError("pending context snapshot is absent")
        payload = _decode_snapshot(ref["key"], *saved, reference_data=reference_data)
        origin = publication["payload"]["origin"]
        if (not _equal(context_consumer_reference(ref["key"], payload), ref)
                or not _equal(payload["base"], original_base(origin))
                or not _equal(payload["event"], event) or payload["base"]["cutoff"] != sidecar["cutoff"]
                or any(origin["inputs"][name] != row[name] for name in ("player_a", "player_b", "tour"))
                or round(origin["values"]["p_a_cal"], 4) != row["p_cal"]):
            raise ContextIntegrityError("pending original/forecast/context bytes differ")
        history_key = (row["tour"], canonical_timestamp(decision_at))
        if history_key not in self._pending_histories:
            self._pending_histories[history_key] = tennis_observations_as_of(
                self.path, cutoff=decision_at, tour=row["tour"], prepared=True)
        observations = self._pending_histories[history_key].for_event(event)
        history = [record for record in observations if record["event_key"] == event["event_key"]]
        newest = max((record["observed_at"] for record in history), default=None)
        latest = [record for record in history if record["observed_at"] == newest]
        if (len(latest) != 1 or latest[0]["source_schema"] != STATUS_SCHEMA
                or latest[0]["payload"]["issues"] or latest[0]["payload"]["status"] != "scheduled"
                or not _equal(_event(latest[0]), event)):
            raise ContextIntegrityError("pending native fixture has been withdrawn, changed or is unverified")
        actual = latest[0]
        self.bindings[id(row)] = {"fixture": deepcopy(row), "row": deepcopy(actual),
            "receipt": actual["digest"], "observed_at": actual["observed_at"]}

    def enqueue(self, fixture, state, prediction, originals, *, decision_at, kwargs, result, success_counter="stored"):
        if self.finished:
            raise ContextContractError("live batch is already finished")
        binding = self.bindings.get(id(fixture)) if originals else None
        if binding is not None and not _equal(binding["fixture"], fixture):
            raise ContextIntegrityError("formatted fixture changed after its actual native reception")
        if binding is not None and len(originals) != 1:
            raise ContextIntegrityError("same-call original was not captured exactly once")
        self.pending.append({"fixture": deepcopy(fixture), "state": state, "prediction": deepcopy(prediction),
            "original": deepcopy(originals[0]) if binding else None, "binding": deepcopy(binding),
            "decision": decision_at, "kwargs": dict(kwargs), "result": result, "success_counter": success_counter})
        result["prepared"] = result.get("prepared", 0)+1

    def _verify_states(self, qualified):
        """Validate each actual in-memory tour model once in this batch.

        Group by object identity AND tour, never by a caller-supplied hash
        alone. The earliest decision checks every item's causal constraint.
        No cache survives a finish call or authorizes a later changed state.
        """
        from tennis.state_codec import encode_state
        from tennis.tour_state import _decode_wrapper
        groups, refs = {}, {}
        for item in qualified:
            groups.setdefault((id(item["state"]), item["fixture"]["tour"]), []).append(item)
        for (_, tour), items in groups.items():
            state = items[0]["state"]
            decision = min(item["decision"] for item in items)
            ref = require_digest(state.artifact_hash, "actually loaded tour model")
            with _reader(self.path) as connection:
                envelope = _artifact(connection, ref, "tennis-tour-state", latest=canonical_timestamp(decision))
            _decode_wrapper(envelope["payload"], tour, decision_cutoff=decision.timestamp())
            if (not _equal(envelope["payload"]["state"], encode_state(state, tour=tour))
                    or state.training_cutoff != envelope["payload"]["training_cutoff"]):
                raise ContextIntegrityError("actually used model differs from its immutable A1 tour state")
            refs.update((id(item), ref) for item in items)
        return refs

    def _original(self, item, ref, observations, code_hashes):
        binding = item["binding"]
        cutoff = canonical_timestamp(item["decision"])
        event = _event(binding["row"])
        if binding["observed_at"] > cutoff:
            raise ContextIntegrityError("native receipt follows original prediction cutoff")
        history = [row for row in observations if row["event_key"] == event["event_key"]]
        newest = max((row["observed_at"] for row in history), default=None)
        latest = [row for row in history if row["observed_at"] == newest]
        if (len(latest) != 1 or latest[0]["source_schema"] != STATUS_SCHEMA
                or latest[0]["digest"] != binding["receipt"]):
            raise ContextIntegrityError("current native event was revised or conflicts with the original fixture")
        actual = latest[0]
        if (actual["payload"]["issues"] or actual["payload"]["status"] != "scheduled"
                or not _equal(_event(actual), event)):
            raise ContextIntegrityError("current native event is not the original scheduled singles pair")
        origin = {"schema": 1, "kind": ORIGIN_KIND, "event": event, "cutoff": cutoff,
            "state_hash": ref, "native_receipt": binding["receipt"], "native_observed_at": binding["observed_at"],
            "competition_revision": actual["payload"]["competition_revision"], "native_state_identity": "unresolved",
            "code_hashes": code_hashes, **item["original"]}
        base = original_base(origin)
        features = tennis_features_v3(event, observations, base, cutoff=item["decision"])
        return origin, event, base, features

    def finish(self):
        from context_sources.tennis_capture import _CURRENT as current_capture
        from tennis import shadow
        if current_capture.get() is not None:
            raise ContextContractError("capture must commit before live context input resolution")
        if self.finished:
            raise ContextContractError("live batch cannot be appended twice")
        qualified = [item for item in self.pending if item["binding"] is not None]
        self._report("history", total=len(self.pending), native=len(qualified))
        # Pending prechecks share a tour image, but final publication still
        # resolves a fresh complete inventory and detects intervening revisions.
        self._pending_histories.clear()
        prepared = {}
        if qualified:
            root = Path(__file__).resolve().parents[1]
            code_hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in CODE_PATHS}
            histories = {}
            for item in qualified:
                key = (item["fixture"]["tour"], canonical_timestamp(item["decision"]))
                if key not in histories:
                    histories[key] = tennis_observations_as_of(
                        self.path, cutoff=item["decision"], tour=key[0], prepared=True)
                    self._report("history_ready", tour=key[0], references=len(histories[key].observation_refs))
            with _reader(self.path) as connection:
                inventory = _Inventory(connection)
            state_refs = self._verify_states(qualified)
            self._report("prepare", total=len(qualified))
            for item in qualified:
                history = histories[item["fixture"]["tour"], canonical_timestamp(item["decision"])]
                observations = history.for_event(_event(item["binding"]["row"]))
                origin, event, base, features = self._original(item, state_refs[id(item)], observations, code_hashes)
                effect, effect_hash, approval, reason = inventory.select(event, base, features)
                inputs = {"event": event, "base": base, "features": features,
                    "observation_refs": history.observation_refs, "preprocessing_refs": [],
                    "effect_artifact": effect, "effect_hash": effect_hash, "approval": approval}
                descriptor = {"schema": 1, "kind": KIND, **inputs,
                    "approval_hash": approval["digest"] if approval is not None else None}
                key = context_payload_key(descriptor)
                prepared[id(item)] = (origin, inputs, key)
                self.reasons.append(reason)
            self._report("prepared", total=len(prepared))
        # B1/A1/D2 resolution is complete before any CPU-only compute callback.
        # Cross-database publication is intentionally not claimed atomic: an
        # orphan immutable original/snapshot is safe; a dangling Shadow ref is not.
        for ordinal, item in enumerate(self.pending, 1):
            kwargs = item["kwargs"]
            if id(item) in prepared:
                origin, inputs, key = prepared[id(item)]
                published_at = _now()
                publication = validate_original_publication({"schema": 1, "origin": origin}, created_at=published_at)
                original_hash = put_artifact(self.path, kind=ORIGINAL_ARTIFACT_KIND,
                    payload=publication, created_at=published_at)
                with _reader(self.path) as connection:
                    stored_original = _load_artifact(connection, original_hash)
                    if not _equal(stored_original, {"kind": ORIGINAL_ARTIFACT_KIND, "payload": publication}):
                        raise ContextIntegrityError("original publication differs from its actual stored bytes")
                    original_published_at = _artifact_created_at(connection, original_hash)
                    validate_original_publication(stored_original["payload"],
                        created_at=original_published_at)
                payload = compute_once(self.path, key, lambda inputs=inputs: calculate_context_payload(**inputs))
                # Existing same-key bytes must match our actual resolved inputs,
                # not merely be self-hashed valid JSON from another producer.
                expected = {"schema": 1, "kind": KIND, **inputs,
                    "approval_hash": inputs["approval"]["digest"] if inputs["approval"] is not None else None}
                if not _equal({name: payload.get(name) for name in expected}, expected):
                    raise ContextIntegrityError("stored context snapshot differs from resolved original inputs")
                reference = context_consumer_reference(key, payload)
                kwargs = {**kwargs, "context_model": validate_context_model({"schema": 1, "kind": SIDECAR_KIND,
                    "reference": reference, "event": inputs["event"], "cutoff": origin["cutoff"],
                    "markets": MARKETS, "original_artifact_hash": original_hash}), "context_original": origin,
                    "context_original_published_at": original_published_at}
            try:
                fx = item["fixture"]
                row_id = shadow.store_prediction(fx["match_date"], fx["tour"], fx["tournament"], item["prediction"], **kwargs)
                if row_id > 0 or item["success_counter"] == "refreshed":
                    item["result"][item["success_counter"]] += 1
            except shadow.FixtureIdentityConflict as exc:
                # A replaced opponent invalidates only this immutable event
                # lineage. Retain the error and original rows, but finish the
                # independent fixtures. Other integrity failures still raise.
                item["result"]["skipped"] += 1
                item["result"]["errors"].append({
                    "tour": fx.get("tour"),
                    "provider_event_id": fx.get("provider_event_id"),
                    "reason": "fixture_identity_conflict",
                    "error_type": type(exc).__name__,
                })
                item["result"]["status"] = "partial"
            except shadow.FixtureNotRefreshable:
                item["result"]["skipped"] += 1
            if ordinal == 1 or ordinal % 10 == 0 or ordinal == len(self.pending):
                self._report("published", processed=ordinal, total=len(self.pending))
        self.finished = True
        self._report("complete", total=len(self.pending))


@contextmanager
def live_worker(*, path=None, progress=None):
    if _CURRENT.get() is not None:
        raise ContextContractError("live tennis worker is already owned")
    if path is None:
        from runtime_paths import CONTEXT_MODEL_DB_PATH
        path = CONTEXT_MODEL_DB_PATH
    batch = LiveWorker(path, progress=progress)
    token = _CURRENT.set(batch)
    try:
        yield batch
    finally:
        _CURRENT.reset(token)
