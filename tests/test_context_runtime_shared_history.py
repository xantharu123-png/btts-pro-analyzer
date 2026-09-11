"""Shared-basis behavior on real owning publications and receipt selectors."""
from contextlib import closing
from datetime import datetime, timedelta
import sqlite3
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest

import context_runtime_tennis as tennis_runtime
import context_runtime_history_cache as history_cache
from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
from context_runtime_transaction import TrackedConnection
from context_models.contracts import canonical_timestamp
from context_sources.tennis_status import select_tennis_observations, normalize_tennis_status
from context_observations import append_observation
from model_artifacts import canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_context_runtime_capacity import encoded_history_fixture
from test_tennis_live_worker import NOW, competition, configure, run_batch, context_rows


@pytest.fixture
def five_groups(tmp_path, monkeypatch):
    comp = competition(date="2026-09-11T23:00Z")
    db, predictions, _, _ = configure(monkeypatch, tmp_path, comp=comp)
    day = NOW + timedelta(days=1)
    monkeypatch.setattr("test_tennis_live_worker.NOW", day.replace(hour=20))
    # Exact observed ordering; duplicate cutoffs belong to distinct events.
    clocks = [(12, 7), (16, 37), (19, 7), (14, 7), (10, 0),
              (12, 7), (14, 7), (19, 7), (10, 0), (16, 37)]
    # All equal-time source receipts physically exist before any snapshot.
    # Later production must never invent backdated source rows into old views.
    for index in range(10):
        comp["id"] = str(300 + index)
        clock = day.replace(hour=9, minute=59)
        for row in normalize_tennis_status("ATP", "189-2026", comp, grouping_slug="mens-singles", observed_at=clock):
            append_observation(db, row, observed_at=clock)
    order = []
    for index, (hour, minute) in enumerate(clocks):
        cutoff = day.replace(hour=hour, minute=minute)
        comp["id"] = str(300 + index)
        monkeypatch.setattr("context_sources.tennis_capture._receipt_now", lambda: day.replace(hour=9, minute=59))
        monkeypatch.setattr("tennis.live_context._now", lambda: day.replace(hour=20))
        run_batch(db, predictions, decision=cutoff)
        order.append((canonical_timestamp(cutoff), "espn:tennis:ATP:match:" + comp["id"]))
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        artifacts = dict(VerifiedArtifactMapping(conn).items())
        originals = {ref: row for ref, row in artifacts.items() if row["kind"] == tennis_runtime.ORIGINAL_ARTIFACT_KIND}
        ordered = {ref: row for clock, event in order for ref, row in originals.items()
                   if row["payload"]["origin"]["cutoff"] == clock
                   and row["payload"]["origin"]["event"]["event_key"] == event}
        ordered.update({ref: row for ref, row in artifacts.items() if ref not in originals})
        assert len(originals) == len(ordered) - 1 == 10
        receipts = VerifiedReceiptMapping(conn)
        receipts.validate_all()
        created = {ref: datetime.fromisoformat(clock) for ref, clock in conn.execute("SELECT digest,created_at FROM artifacts")}
        yield db, conn, ordered, created, receipts, order


def test_five_interleaved_groups_share_one_completed_basis(five_groups, monkeypatch):
    # Break caught: per-cutoff storage evicts the maximum and rebuilds cold.
    db, _, artifacts, created, receipts, order = five_groups
    baseline = tuple(receipts.values())
    expected = {clock: select_tennis_observations(baseline, cutoff=datetime.fromisoformat(clock), tour="ATP")
                for clock, _ in order}
    maximum = max(expected)
    budget = 2 * sum(len(canonical_bytes(row)) for row in expected[maximum])
    monkeypatch.setattr(history_cache, "MAX_ENCODED_HISTORY_BYTES", budget)
    cold, calls = tennis_runtime._cold_replay_history, []
    def observed(*args, **kwargs):
        calls.append(canonical_timestamp(kwargs["cutoff"]))
        return cold(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", observed)
    checked = tennis_runtime.verify_live_originals(artifacts, created, receipts, set())
    cache = next(iter(checked.values())).history_cache
    for clock, _ in order:
        result = tennis_runtime._replay_history(receipts, cutoff=datetime.fromisoformat(clock), tour="ATP",
                                               max_bytes=None, cache=cache)
        assert type(result) is tuple and canonical_bytes(result) == canonical_bytes(expected[clock])
        result[0]["payload"]["participant_ids"].append("poison")
    assert calls == [maximum]
    assert cache.stats["entries"] == 1 and cache.stats["stores"] == 1
    assert cache.stats["bytes"] == budget // 2 + cache.stats["metadata_bytes"]
    assert cache.stats["peak_bytes"] <= budget and cache.stats["pending_bytes"] == 0


def _prepared(receipts, cutoff, *, budget=1024**2, tours=("ATP",)):
    cache = history_cache.EncodedHistoryCache(receipts, max_bytes=budget)
    assert cache._plan_bases(receipts, {tour: cutoff for tour in tours})
    for tour in tours:
        rows = tennis_runtime._cold_replay_history(receipts, cutoff=cutoff, tour=tour, max_bytes=None)
        cache._store(receipts, rows, cutoff=cutoff, tour=tour)
    return cache


def test_shared_basis_preserves_all_ten_owner_calls_and_exact_report(five_groups, monkeypatch):
    import context_runtime
    import tennis.predict
    db, _, artifacts, created, receipts, order = five_groups
    originals, snapshots = [], []
    owner_original, owner_features = tennis.predict.predict_match, tennis_runtime.tennis_features_v3
    def original(*args, **kwargs):
        originals.append(canonical_timestamp(kwargs["as_of"]))
        return owner_original(*args, **kwargs)
    def features(event, history, base, **kwargs):
        snapshots.append((base["cutoff"], event["event_key"]))
        assert type(history) is tuple
        return owner_features(event, history, base, **kwargs)
    monkeypatch.setattr(tennis.predict, "predict_match", original)
    monkeypatch.setattr(tennis_runtime, "tennis_features_v3", features)
    checked = tennis_runtime.verify_live_originals(artifacts, created, receipts, set())
    for key, payload in context_rows(db):
        assert tennis_runtime.verify_live_snapshot(payload, key, checked, effect=None, approval=None, limitations=set())
    assert originals == [clock for clock, _ in order]
    assert snapshots == order
    actual = context_runtime.verify_context_database(db)
    replay = tennis_runtime._replay_history
    def uncached(receipts, **kwargs):
        return replay(receipts, **{**kwargs, "cache": None})
    monkeypatch.setattr(tennis_runtime, "_replay_history", uncached)
    assert context_runtime.verify_context_database(db) == actual
    assert actual["counts"]["snapshots"] == 10 and not actual["empirical_approval_verified"]


@pytest.mark.parametrize("field", ["schema", "cutoff", "tour"])
def test_planning_rejects_malformed_last_publication_before_history(five_groups, monkeypatch, field):
    _, _, artifacts, created, receipts, _ = five_groups
    artifacts = deepcopy(artifacts)
    publication = list(artifacts.values())[-2]["payload"]
    if field == "schema": publication["schema"] = 2
    elif field == "cutoff": publication["origin"]["cutoff"] = "invalid-clock"
    else: publication["origin"]["event"]["tour"] = "unknown-tour"
    def no_history(*args, **kwargs):
        pytest.fail("malformed planning metadata reached history preparation")
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", no_history)
    with pytest.raises(ValueError):
        tennis_runtime.verify_live_originals(artifacts, created, receipts, set())


def test_shared_planning_keeps_unreferenced_original_model_replay(five_groups, monkeypatch):
    import context_runtime
    import tennis.predict
    db, conn, _, _, _, _ = five_groups
    conn.execute("DELETE FROM context_snapshots WHERE key=(SELECT key FROM context_snapshots LIMIT 1)")
    conn.commit()
    owner, calls = tennis.predict.predict_match, []
    def observed(*args, **kwargs):
        calls.append(kwargs["as_of"])
        return owner(*args, **kwargs)
    monkeypatch.setattr(tennis.predict, "predict_match", observed)
    result = context_runtime.verify_context_database(db)
    assert len(calls) == 10 and result["counts"]["snapshots"] == 9


def test_shared_basis_prefix_boundaries_and_eviction_release(encoded_history_fixture):
    from datetime import timezone
    _, receipts, now = encoded_history_fixture
    baseline = tuple(receipts.values())
    receipts.validate_all()
    later = now + timedelta(seconds=2)
    atp = select_tennis_observations(baseline, cutoff=later, tour="ATP")
    size = sum(len(canonical_bytes(row)) for row in atp)
    cache = _prepared(receipts, later, budget=size, tours=("ATP", "WTA"))
    # WTA evicts ATP under the same global cap, not a separate per-tour cap.
    assert cache.stats["evictions"] == 1 and cache.stats["entries"] == 1
    raw = next(iter(cache._entries.values()))[0][0]
    descriptor = tennis_runtime.LiveReplayDescriptor("unused", {}, receipts, None, cache)
    cache._evict()
    assert descriptor.history_cache.stats["bytes"] == 0
    assert sys.getrefcount(raw) == 2  # No descriptor/cache metadata owns evicted bytes.
    for tour in ("ATP", "WTA"):
        for cutoff in (now-timedelta(microseconds=1), now, later, now,
                       now.astimezone(timezone(timedelta(hours=5, minutes=30)))):
            expected = select_tennis_observations(baseline, cutoff=cutoff, tour=tour)
            actual = tennis_runtime._replay_history(receipts, cutoff=cutoff, tour=tour, max_bytes=None, cache=cache)
            assert type(actual) is tuple and canonical_bytes(actual) == canonical_bytes(expected)
            assert cache.stats["peak_bytes"] <= size


def test_shared_oversize_maximum_does_not_reject_valid_smaller_prefix(encoded_history_fixture, monkeypatch):
    _, receipts, now = encoded_history_fixture
    receipts.validate_all()
    expected = tennis_runtime._cold_replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None)
    size = len(canonical_bytes(expected[0]))
    cache = _prepared(receipts, now+timedelta(seconds=2), budget=size)
    assert cache.stats["bypasses"] == 1 and cache.stats["entries"] == 0
    cold, calls = tennis_runtime._cold_replay_history, []
    def observed(*args, **kwargs):
        calls.append(kwargs["cutoff"])
        return cold(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", observed)
    assert tennis_runtime._replay_history(receipts, cutoff=now, tour="ATP", max_bytes=size, cache=cache) == expected
    assert calls == [now] and cache.stats["entries"] == 0
    with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
        tennis_runtime._replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=size, cache=cache)
    assert cache.stats["pending_bytes"] == 0


@pytest.mark.parametrize("mutation", ["write", "ddl", "temp", "commit", "rollback", "close"])
@pytest.mark.parametrize("empty", [False, True])
def test_shared_basis_last_decode_and_empty_prefix_revoke(encoded_history_fixture, monkeypatch, mutation, empty):
    conn, receipts, now = encoded_history_fixture
    receipts.validate_all()
    cache = _prepared(receipts, now+timedelta(seconds=2))
    decode, calls = history_cache.json.loads, []
    def changed(raw):
        row = decode(raw)
        calls.append(1)
        if len(calls) == (1 if empty else 2):
            if mutation == "write": conn.execute("UPDATE context_observations SET source=source")
            elif mutation == "ddl": conn.execute("CREATE TABLE basis_mutation (id INTEGER)")
            elif mutation == "temp": conn.execute("CREATE TEMP TABLE context_observations (digest TEXT)")
            elif mutation == "close": conn.close()
            else:
                getattr(conn, mutation)()
                conn.execute("BEGIN")
        return row
    monkeypatch.setattr(history_cache, "json", SimpleNamespace(loads=changed))
    cutoff = now-timedelta(days=1) if empty else now+timedelta(seconds=2)
    for _ in range(2):
        with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
            tennis_runtime._replay_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=None, cache=cache)
    assert cache.stats["bytes"] == 0 and cache.stats["entries"] == 0


@pytest.mark.parametrize("proof", ["never", "interrupted", "failed"])
def test_shared_basis_cannot_plan_without_completed_proof(encoded_history_fixture, monkeypatch, proof):
    import context_observations
    conn, receipts, now = encoded_history_fixture
    if proof != "never":
        if proof == "failed":
            conn.execute("UPDATE context_contents SET payload=?", (b"{}",))
        else:
            def interrupted(raw):
                raise KeyboardInterrupt("physical proof interrupted")
            monkeypatch.setattr(context_observations, "_decode_receipt", interrupted)
        with pytest.raises((KeyboardInterrupt, ValueError)):
            receipts.validate_all()
        with pytest.raises(RuntimeArtifactTrustError):
            history_cache.EncodedHistoryCache(receipts)
    else:
        cache = history_cache.EncodedHistoryCache(receipts)
        assert cache._plan_bases(receipts, {"ATP": now}) is False
        assert cache._basis_cutoffs is None
        assert tennis_runtime._replay_history(receipts, cutoff=now, tour="ATP", max_bytes=None, cache=cache)


def test_shared_oversize_bypass_cannot_hide_last_encoding_mutation(encoded_history_fixture, monkeypatch):
    conn, receipts, now = encoded_history_fixture
    receipts.validate_all()
    rows = tennis_runtime._cold_replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=None)
    cache = history_cache.EncodedHistoryCache(receipts, max_bytes=len(canonical_bytes(rows[0])))
    assert cache._plan_bases(receipts, {"ATP": now+timedelta(seconds=2)})
    encode, calls = history_cache.canonical_bytes, []
    def mutated(row):
        raw = encode(row)
        calls.append(1)
        if len(calls) == 2:
            conn.execute("UPDATE context_observations SET source=source")
        return raw
    monkeypatch.setattr(history_cache, "canonical_bytes", mutated)
    with pytest.raises(RuntimeArtifactTrustError):
        cache._store(receipts, rows, cutoff=now+timedelta(seconds=2), tour="ATP")
    assert cache.stats["pending_bytes"] == 0 and cache.stats["entries"] == 0


def test_maximum_preparation_keeps_eligible_opposite_tour_owner_validation(encoded_history_fixture, monkeypatch):
    import json
    from context_models.contracts import ContextIntegrityError, digest
    conn, _, _ = encoded_history_fixture
    for ref, raw in conn.execute("SELECT content_digest,payload FROM context_contents"):
        content = json.loads(raw)
        if content["payload"]["tour"] == "WTA":
            content["payload"]["competition_revision"] = "0" * 64
            replacement = digest(content)
            clock = conn.execute("SELECT observed_at FROM context_observations WHERE content_digest=?", (ref,)).fetchone()[0]
            conn.execute("UPDATE context_contents SET content_digest=?,payload=? WHERE content_digest=?",
                         (replacement, canonical_bytes(content), ref))
            conn.execute("UPDATE context_observations SET content_digest=?,digest=? WHERE content_digest=?",
                         (replacement, digest({"content_digest": replacement, "observed_at": clock}), ref))
            break
    else:
        pytest.fail("missing opposite-tour native receipt")
    receipts = VerifiedReceiptMapping(conn)
    receipts.validate_all()  # Fully B1-valid; owning Tennis selection must still reject it.
    artifacts = dict(VerifiedArtifactMapping(conn).items())
    # Only ATP consumers: the malformed eligible WTA row is still validated.
    artifacts = {ref: row for ref, row in artifacts.items()
                 if row["kind"] != tennis_runtime.ORIGINAL_ARTIFACT_KIND
                 or row["payload"]["origin"]["event"]["tour"] == "ATP"}
    created = {ref: datetime.fromisoformat(clock) for ref, clock in conn.execute("SELECT digest,created_at FROM artifacts")}
    cold, calls = tennis_runtime._cold_replay_history, []
    def observed(*args, **kwargs):
        calls.append(kwargs["tour"])
        return cold(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", observed)
    with pytest.raises(ContextIntegrityError):
        tennis_runtime.verify_live_originals(artifacts, created, receipts, set())
    assert calls == ["ATP"]  # Error propagates, never becomes a cache-miss retry.


@pytest.mark.parametrize("admit", [True, False])
def test_optional_maximum_preparation_stops_at_size_only_overflow(five_groups, monkeypatch, admit):
    import context_observations
    _, _, artifacts, created, receipts, order = five_groups
    selected = select_tennis_observations(tuple(receipts.values()),
                cutoff=datetime.fromisoformat(max(clock for clock, _ in order)), tour="ATP")
    assert len(selected) == 10
    budget = len(canonical_bytes(selected[0]))
    assert all(len(canonical_bytes(row)) == budget for row in selected)
    monkeypatch.setattr(history_cache, "MAX_ENCODED_HISTORY_BYTES", budget)
    decode, decoded = context_observations._decode_receipt, []
    def observed(raw):
        decoded.append(raw[0])
        return decode(raw)
    monkeypatch.setattr(context_observations, "_decode_receipt", observed)
    verify, consumers = tennis_runtime._verify_live_original, []
    def complete_consumer(*args, **kwargs):
        if not consumers:
            assert len(decoded) == 2  # Stop optional preparation, not full consumer validation.
        consumers.append(1)
        return verify(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_verify_live_original", complete_consumer)
    if admit:
        checked = tennis_runtime.verify_live_originals(artifacts, created, receipts, set(), history_max_bytes=10*budget)
        assert len(checked) == len(consumers) == 10
        assert len(decoded) == 2 + 10*10  # All actual consumers still validate complete histories.
        cache = next(iter(checked.values())).history_cache
        assert cache.stats["entries"] == 0 and cache.stats["pending_bytes"] == 0
    else:
        with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
            tennis_runtime.verify_live_originals(artifacts, created, receipts, set(), history_max_bytes=9*budget)
        assert len(consumers) == 1 and len(decoded) == 2 + 10


def test_optional_overflow_fallback_still_rejects_later_malformed_receipt(five_groups, monkeypatch):
    import json
    from context_models.contracts import ContextIntegrityError, digest
    _, conn, artifacts, created, _, order = five_groups
    ref, raw = conn.execute("SELECT content_digest,payload FROM context_contents ORDER BY rowid DESC LIMIT 1").fetchone()
    content = json.loads(raw)
    content["payload"]["competition_revision"] = "0" * 64
    replacement = digest(content)
    clock = conn.execute("SELECT observed_at FROM context_observations WHERE content_digest=?", (ref,)).fetchone()[0]
    conn.execute("UPDATE context_contents SET content_digest=?,payload=? WHERE content_digest=?",
                 (replacement, canonical_bytes(content), ref))
    conn.execute("UPDATE context_observations SET content_digest=?,digest=? WHERE content_digest=?",
                 (replacement, digest({"content_digest": replacement, "observed_at": clock}), ref))
    receipts = VerifiedReceiptMapping(conn)
    receipts.validate_all()
    monkeypatch.setattr(history_cache, "MAX_ENCODED_HISTORY_BYTES", 256)
    cold, calls = tennis_runtime._cold_replay_history, []
    def observed(*args, **kwargs):
        calls.append(canonical_timestamp(kwargs["cutoff"]))
        return cold(*args, **kwargs)
    monkeypatch.setattr(tennis_runtime, "_cold_replay_history", observed)
    with pytest.raises(ContextIntegrityError):
        tennis_runtime.verify_live_originals(artifacts, created, receipts, set())
    assert calls == [max(clock for clock, _ in order), order[0][0]]


def test_optional_overflow_does_not_swallow_simultaneous_proof_mutation(five_groups, monkeypatch):
    _, conn, artifacts, created, receipts, _ = five_groups
    monkeypatch.setattr(history_cache, "MAX_ENCODED_HISTORY_BYTES", 256)
    encode = tennis_runtime.canonical_bytes
    def changed(row):
        raw = encode(row)
        conn.execute("UPDATE context_observations SET source=source")
        return raw
    monkeypatch.setattr(tennis_runtime, "canonical_bytes", changed)
    def no_consumer(*args, **kwargs):
        pytest.fail("revoked preparation fell through to consumer replay")
    monkeypatch.setattr(tennis_runtime, "_verify_live_original", no_consumer)
    with pytest.raises(RuntimeArtifactTrustError):
        tennis_runtime.verify_live_originals(artifacts, created, receipts, set())
