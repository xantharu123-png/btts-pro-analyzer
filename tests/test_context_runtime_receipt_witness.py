"""Exact-value receipt proofs; spies always delegate to the real owner."""
from contextlib import closing
from contextvars import copy_context
from copy import deepcopy
from datetime import datetime, timedelta
import sqlite3
import sys

import pytest

import context_runtime_history_cache as hc
import context_runtime_tennis as rt
import context_sources.tennis_status as status
from context_models.contracts import OBSERVATION_FIELDS, digest
from context_runtime_inventory import VerifiedReceiptMapping
from model_artifacts import canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_context_runtime_capacity import encoded_history_fixture
from test_context_runtime_shared_history import five_groups
from test_tennis_live_worker import context_rows
from context_runtime_transaction import TrackedConnection
from context_models.tennis_v3 import tennis_features_v3
from test_context_tennis_capture import NOW, competition, persist, records
from test_tennis_context_features import base, event
from test_tennis_status_v3 import legacy


def prepared(fixture, *, proof=True, budget=1024**2):
    conn, receipts, now = fixture
    if proof:
        receipts.validate_all()
    cutoff = now + timedelta(seconds=2)
    rows = rt._cold_replay_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=None)
    cache = hc.EncodedHistoryCache(receipts, max_bytes=budget)
    cache._store(receipts, rows, cutoff=cutoff, tour="ATP")
    return conn, receipts, cutoff, rows, cache


def spy_cold(monkeypatch):
    owner, calls = status._validate_selected_tennis_receipt_cold, []
    def counted(row):
        calls.append(1)
        return owner(row)
    monkeypatch.setattr(status, "_validate_selected_tennis_receipt_cold", counted)
    return calls


def rehash(row):
    row["content_digest"] = digest({key: row[key] for key in OBSERVATION_FIELDS})
    row["digest"] = digest({"content_digest": row["content_digest"], "observed_at": row["observed_at"]})
    return row


def test_repeated_full_snapshots_replace_only_cold_receipt_derivation(five_groups, monkeypatch):
    db, _, artifacts, created, receipts, order = five_groups
    owner, calls = status.validate_tennis_status_record, []
    def counted(row):
        calls.append(1)
        return owner(row)
    monkeypatch.setattr(status, "validate_tennis_status_record", counted)
    checked = rt.verify_live_originals(artifacts, created, receipts, set())
    assert len(calls) == 20  # Ten selected rows, then one independent owning seal.
    calls.clear()
    for _ in range(3):
        for key, payload in context_rows(db):
            assert rt.verify_live_snapshot(payload, key, checked, effect=None, approval=None, limitations=set())
    assert len(order) == 10 and calls == []


@pytest.mark.parametrize("poison", ["source", "tuple"])
def test_store_cannot_launder_source_invalid_or_type_aliased_rows(encoded_history_fixture, poison):
    _, receipts, now = encoded_history_fixture
    receipts.validate_all()
    rows = list(rt._cold_replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=None))
    if poison == "source":
        rows[-1]["payload"]["competition_revision"] = "0" * 64
        rehash(rows[-1])  # Valid B1 hashes alone do not prove native Tennis.
    else:
        rows[-1]["payload"]["participant_ids"] = tuple(rows[-1]["payload"]["participant_ids"])
    with pytest.raises(ValueError):
        status.validate_selected_tennis_receipt(rows[-1])
    cache = hc.EncodedHistoryCache(receipts)
    with pytest.raises(ValueError):
        cache._store(receipts, rows, cutoff=now, tour="ATP")
    assert cache.stats["entries"] == cache.stats["bytes"] == cache.stats["pending_bytes"] == 0


def test_final_row_interrupted_owner_seal_publishes_nothing(encoded_history_fixture, monkeypatch):
    _, receipts, now = encoded_history_fixture
    receipts.validate_all()
    rows = rt._cold_replay_history(receipts, cutoff=now+timedelta(seconds=2), tour="ATP", max_bytes=None)
    owner, calls = status.validate_tennis_status_record, []
    def interrupted(row):
        result = owner(row)
        calls.append(1)
        if len(calls) == len(rows):
            raise KeyboardInterrupt("last owning seal interrupted")
        return result
    monkeypatch.setattr(status, "validate_tennis_status_record", interrupted)
    cache = hc.EncodedHistoryCache(receipts)
    with pytest.raises(KeyboardInterrupt):
        cache._store(receipts, rows, cutoff=now, tour="ATP")
    assert cache.stats["entries"] == cache.stats["pending_bytes"] == cache.stats["bytes"] == 0


class DictAlias(dict): pass
class ListAlias(list): pass
class StrAlias(str): pass
class IntAlias(int): pass
class FloatAlias(float): pass


@pytest.mark.parametrize("change", [
    "participants-tuple", "workload-tuple", "issues-tuple", "dict", "list", "str", "key",
    "int", "float", "bool", "nan", "missing", "extra", "body", "rehashed", "metadata",
    "accepted-alias", "accepted-key",
])
def test_current_value_and_type_match_cold_acceptance(encoded_history_fixture, monkeypatch, change):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    row = deepcopy(rows[0])
    payload = row["payload"]
    if change.endswith("-tuple"):
        key = {"participants-tuple": "participant_ids", "workload-tuple": "workload_receipts", "issues-tuple": "issues"}[change]
        payload[key] = tuple(payload[key])
    elif change == "dict": row["payload"] = DictAlias(payload)
    elif change == "list": payload["participant_ids"] = ListAlias(payload["participant_ids"])
    elif change == "str": payload["tour"] = StrAlias(payload["tour"])
    elif change == "key":
        value = payload.pop("tour")
        payload[StrAlias("tour")] = value
    elif change == "int": payload["native_status"]["completed"] = IntAlias(0)
    elif change == "float": payload["native_status"]["completed"] = FloatAlias(0.0)
    elif change == "bool": payload["tournament_id"] = True
    elif change == "nan": payload["tournament_id"] = float("nan")
    elif change == "missing": del row["effective_at"]
    elif change == "extra": row["unexpected"] = None
    elif change in {"body", "rehashed"}:
        payload["competition_revision"] = "0"*64
        if change == "rehashed": rehash(row)
    elif change == "metadata": row["evidence_class"] = "archive"
    elif change == "accepted-alias": row["evidence_class"] = StrAlias("prospective")
    else:
        value = row.pop("evidence_class")
        row[StrAlias("evidence_class")] = value
    try:
        expected = status._validate_selected_tennis_receipt_cold(row)
    except Exception as exc:
        outcome = type(exc)
    else:
        outcome = None
        assert expected is row
        assert change in {"accepted-alias", "accepted-key"}
    calls = spy_cold(monkeypatch)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        if outcome:
            with pytest.raises(outcome): status.validate_selected_tennis_receipt(row)
        else:
            assert status.validate_selected_tennis_receipt(row) is row
    assert calls == [1]  # Never launder types, even when canonical bytes alias.


@pytest.mark.parametrize("kind", ["reverse", "duplicate", "changed", "evict", "replace", "never", "zero"])
def test_valid_misses_still_validate_and_accept(encoded_history_fixture, monkeypatch, kind):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture, proof=kind != "never", budget=0 if kind == "zero" else 1024**2)
    candidates = deepcopy(rows)
    if kind == "reverse": candidates = tuple(reversed(candidates))
    elif kind == "duplicate": candidates = (candidates[0], candidates[0])
    elif kind == "changed": candidates = (deepcopy(rows[1]),)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        if kind in {"evict", "replace"}:
            cache._evict()
            if kind == "replace": cache._store(receipts, rows, cutoff=cutoff, tour="ATP")
        calls = spy_cold(monkeypatch)
        for row in candidates:
            assert status.validate_selected_tennis_receipt(row) is row
    assert len(calls) == (1 if kind in {"changed", "duplicate"} else len(candidates))


@pytest.mark.parametrize("kind", ["write", "ddl", "temp", "commit", "rollback", "close", "revoke"])
@pytest.mark.parametrize("when", ["entry", "comparison", "exit", "empty"])
def test_active_lifetime_corruption_is_never_a_miss(encoded_history_fixture, monkeypatch, kind, when):
    conn, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    def mutate():
        if kind == "write": conn.execute("UPDATE context_observations SET source=source")
        elif kind == "ddl": conn.execute("CREATE TABLE witness_change (id INTEGER)")
        elif kind == "temp": conn.execute("CREATE TEMP TABLE witness_change (id INTEGER)")
        elif kind == "close": conn.close()
        elif kind == "revoke": receipts._validation_stamp = None
        else:
            getattr(conn, kind)()
            conn.execute("BEGIN")
    encode = hc.canonical_bytes
    def changed(row):
        raw = encode(row)
        mutate()
        return raw
    if when == "entry": mutate()
    with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
        with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
            if when == "comparison": monkeypatch.setattr(hc, "canonical_bytes", changed)
            if when != "empty":
                for row in rows: status.validate_selected_tennis_receipt(row)
            if when in {"exit", "empty"}: mutate()
    assert hc._selected_receipt_witness.get() is None
    assert cache.stats["entries"] == cache.stats["bytes"] == 0


def test_nested_exception_copied_and_unrelated_contexts_do_not_leak_authority(encoded_history_fixture, monkeypatch):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    calls = spy_cold(monkeypatch)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP") as outer:
        status.validate_selected_tennis_receipt(rows[0])
        with pytest.raises(LookupError):
            with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP") as inner:
                copied = copy_context()
                status.validate_selected_tennis_receipt(rows[0])
                raise LookupError("consumer failed")
        assert hc._selected_receipt_witness.get() is outer and not inner._active
        copied.run(status.validate_selected_tennis_receipt, rows[0])
        status.validate_selected_tennis_receipt(rows[1])
    assert calls == [1] and not outer._active
    class Unrelated:
        def _matches(self, row): pytest.fail("arbitrary callback invoked")
    token = hc._selected_receipt_witness.set(Unrelated())
    try: assert status.validate_selected_tennis_receipt(rows[0]) is rows[0]
    finally: hc._selected_receipt_witness.reset(token)
    assert calls == [1, 1]


def test_store_accepted_nonplain_metadata_does_not_seal(encoded_history_fixture, monkeypatch):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    changed = deepcopy(rows)
    changed[0]["evidence_class"] = StrAlias("prospective")
    assert status._validate_selected_tennis_receipt_cold(changed[0]) is changed[0]
    cache._store(receipts, changed, cutoff=cutoff, tour="ATP")
    calls = spy_cold(monkeypatch)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        for row in rows: status.validate_selected_tennis_receipt(row)
    assert len(calls) == len(rows)
    assert cache.stats["bytes"] == sum(len(canonical_bytes(row)) for row in rows)


def test_evicted_scope_holds_no_entry_bytes_and_replacement_accounts_exactly(encoded_history_fixture, monkeypatch):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    size = cache.stats["bytes"]
    for _ in range(3):
        cache._store(receipts, rows, cutoff=cutoff, tour="ATP")
        assert cache.stats["bytes"] == size and cache.stats["entries"] == 1
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP") as witness:
        raw = next(iter(cache._entries.values()))[0][0]
        cache._evict()
        assert sys.getrefcount(raw) == 2
        assert not any(isinstance(getattr(witness, name), (bytes, list, dict, type(iter(())))) for name in witness.__slots__)
        assert cache.stats["bytes"] == 0 and not cache._seals
        calls = spy_cold(monkeypatch)
        assert status.validate_selected_tennis_receipt(rows[0]) is rows[0]
        assert calls == [1]


def test_fresh_materialization_does_not_share_mutable_bodies(encoded_history_fixture, monkeypatch):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    a = cache._lookup(receipts, cutoff=cutoff, tour="ATP", max_bytes=None)
    a[0]["payload"]["participant_ids"].append("invalid")
    b = cache._lookup(receipts, cutoff=cutoff, tour="ATP", max_bytes=None)
    assert type(b) is tuple and canonical_bytes(b) == canonical_bytes(rows)
    calls = spy_cold(monkeypatch)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        with pytest.raises(ValueError): status.validate_selected_tennis_receipt(a[0])
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        for row in b: status.validate_selected_tennis_receipt(row)
    assert calls == [1]


@pytest.mark.parametrize("case,mode", [
    ("paired", "status-paired"), ("legacy", "legacy-only"), ("mixed", "mixed-status-legacy"),
    ("unavailable", "unavailable-status"), ("conflict", "unavailable-status"),
    ("revised-players", "status-paired"), ("revised-schedule", "status-paired"),
    ("target-started", "unavailable-status"), ("target-cancelled", "unavailable-status"),
    ("target-players", "unavailable-status"), ("target-schedule", "unavailable-status"),
    ("target-defective", "unavailable-status"), ("target-matching", "legacy-only"),
])
def test_complete_status_feature_parity(tmp_path, monkeypatch, case, mode):
    db = tmp_path / "parity.db"
    clock = NOW-timedelta(hours=1)
    if case in {"legacy", "mixed"} or case.startswith("target-"):
        legacy(db, match="102")
    if not case.startswith("target-") and case != "legacy":
        persist(db, records(), clock=clock)
    if case in {"unavailable", "revised-players", "revised-schedule"}:
        raw = competition()
        if case == "unavailable": raw["competitors"] = []
        elif case == "revised-players": raw["competitors"][0]["id"] = "3"
        else: raw["date"] = "2026-09-08T20:00Z"
        persist(db, records(raw, clock=clock+timedelta(minutes=1)), clock=clock+timedelta(minutes=1))
    if case == "conflict":
        raw = competition()
        raw["competitors"][0]["linescores"][0]["value"] = 7
        persist(db, records(raw), clock=clock)
    if case.startswith("target-"):
        raw = competition(id="999", date=event()["scheduled_start"],
            status={"type": {"state": "pre", "completed": False, "name": "STATUS_SCHEDULED"}})
        if case == "target-started": raw["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS")
        elif case == "target-cancelled": raw["status"]["type"]["name"] = "STATUS_CANCELLED"
        elif case == "target-players": raw["competitors"][0]["id"] = "3"
        elif case == "target-schedule": raw["date"] = "2026-09-09T19:00Z"
        elif case == "target-defective": raw["competitors"] = []
        persist(db, records(raw), clock=clock)
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        receipts.validate_all()
        cache = hc.EncodedHistoryCache(receipts)
        complete = rt._replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None, cache=cache)
        for cutoff in (NOW, clock-timedelta(microseconds=1), clock, clock+timedelta(microseconds=1)):
            history = status.select_tennis_observations(tuple(receipts.values()), cutoff=cutoff, tour="ATP")
            expected = tennis_features_v3(event(), history, base(cutoff=cutoff), cutoff=cutoff)
            if cutoff == NOW: assert expected["coverage"]["case"].startswith(mode+".")
            with monkeypatch.context() as local:
                calls = spy_cold(local)
                with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
                    actual = tennis_features_v3(event(), history, base(cutoff=cutoff), cutoff=cutoff)
                assert canonical_bytes(actual) == canonical_bytes(expected)
                assert calls == []
        assert complete


@pytest.mark.parametrize("kind", ["future", "unrelated", "opposite"])
def test_unproved_bad_row_is_checked_before_feature_projection(encoded_history_fixture, monkeypatch, kind):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    row = deepcopy(rows[0])
    if kind == "future": row["observed_at"] = "2030-01-01T00:00:00.000000Z"
    elif kind == "unrelated": row["event_key"] = "espn:tennis:ATP:match:8888"
    else: row["payload"]["tour"] = "WTA"
    with pytest.raises(ValueError): tennis_features_v3(event(), (row,), base(cutoff=cutoff), cutoff=cutoff)
    calls = spy_cold(monkeypatch)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        with pytest.raises(ValueError): tennis_features_v3(event(), (row,), base(cutoff=cutoff), cutoff=cutoff)
    assert calls == [1]


@pytest.mark.parametrize("alias", ["tuple", "list", "dict", "score-dict", "score-int", "int", "float", "bool", "nonfinite"])
def test_workload_nested_types_cannot_alias_the_seal(tmp_path, monkeypatch, alias):
    db = tmp_path / "workload.db"
    persist(db, records(), clock=NOW-timedelta(hours=1))
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        receipts.validate_all()
        cache = hc.EncodedHistoryCache(receipts)
        rows = rt._replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None, cache=cache)
        index = next(i for i, row in enumerate(rows) if row["kind"] == "workload")
        candidate = deepcopy(rows[index])
        scores = candidate["payload"]["set_scores"]
        if alias == "tuple": candidate["payload"]["set_scores"] = tuple(scores)
        elif alias == "list": candidate["payload"]["set_scores"] = ListAlias(scores)
        elif alias == "dict": candidate["payload"] = DictAlias(candidate["payload"])
        elif alias == "score-dict": scores[0] = DictAlias(scores[0])
        elif alias == "score-int": scores[0]["a"] = IntAlias(scores[0]["a"])
        else:
            candidate["payload"]["games"] = {"int": IntAlias(candidate["payload"]["games"]), "float": FloatAlias(18),
                "bool": True, "nonfinite": float("inf")}[alias]
        with pytest.raises(ValueError): status._validate_selected_tennis_receipt_cold(candidate)
        calls = spy_cold(monkeypatch)
        with cache._selected_receipt_scope(receipts, cutoff=NOW, tour="ATP"):
            for row in rows[:index]: status.validate_selected_tennis_receipt(row)
            with pytest.raises(ValueError): status.validate_selected_tennis_receipt(candidate)
        assert calls == [1]


def test_same_entry_replacement_during_comparison_cannot_hit(encoded_history_fixture, monkeypatch):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    encode = hc.canonical_bytes
    calls = spy_cold(monkeypatch)
    def replace(row):
        result = encode(row)
        with monkeypatch.context() as local:
            local.setattr(hc, "canonical_bytes", encode)
            cache._store(receipts, rows, cutoff=cutoff, tour="ATP")
        return result
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        monkeypatch.setattr(hc, "canonical_bytes", replace)
        assert status.validate_selected_tennis_receipt(rows[0]) is rows[0]
    assert len(calls) == len(rows)+1  # Independent new seal PLUS cold miss on stale serial.


def test_encoding_failure_uses_owner_not_optimization_rejection(encoded_history_fixture, monkeypatch):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    def unavailable(row): raise ValueError("optional comparison encoding unavailable")
    monkeypatch.setattr(hc, "canonical_bytes", unavailable)
    calls = spy_cold(monkeypatch)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        assert status.validate_selected_tennis_receipt(rows[0]) is rows[0]
    assert calls == [1]


def test_final_seal_mutation_and_distinct_mapping_reject(encoded_history_fixture, monkeypatch):
    conn, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    with pytest.raises(RuntimeArtifactTrustError):
        with cache._selected_receipt_scope(VerifiedReceiptMapping(conn), cutoff=cutoff, tour="ATP"):
            pytest.fail("different inventory entered")
    cache = hc.EncodedHistoryCache(receipts)
    owner, calls = status._validate_selected_tennis_receipt_cold, []
    def changed(row):
        result = owner(row)
        calls.append(1)
        if len(calls) == len(rows): conn.execute("UPDATE context_observations SET source=source")
        return result
    monkeypatch.setattr(status, "_validate_selected_tennis_receipt_cold", changed)
    with pytest.raises(RuntimeArtifactTrustError): cache._store(receipts, rows, cutoff=cutoff, tour="ATP")
    assert not cache._seals and cache.stats["pending_bytes"] == cache.stats["bytes"] == cache.stats["entries"] == 0


def test_two_tours_and_empty_entries_share_byte_and_metadata_limits(encoded_history_fixture):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    cache = hc.EncodedHistoryCache(receipts, max_bytes=sum(len(canonical_bytes(row)) for row in rows))
    cache._store(receipts, rows, cutoff=cutoff, tour="ATP")
    other = rt._cold_replay_history(receipts, cutoff=cutoff, tour="WTA", max_bytes=None)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        cache._store(receipts, other, cutoff=cutoff, tour="WTA")
        assert cache.stats["evictions"] == 1
        assert cache.stats["bytes"] == sum(len(canonical_bytes(row)) for row in other)
        assert cache.stats["peak_bytes"] <= cache.stats["max_bytes"]
    for i in range(40): cache._store(receipts, (), cutoff=cutoff+timedelta(seconds=i), tour="ATP")
    assert cache.stats["entries"] == len(cache._seals) == 32
    assert cache.stats["bytes"] == 0


@pytest.mark.parametrize("container", [list, lambda rows: iter(rows), type("TupleAlias", (tuple,), {})])
def test_scope_preserves_feature_tuple_container_contract(encoded_history_fixture, container):
    _, receipts, cutoff, rows, cache = prepared(encoded_history_fixture)
    with cache._selected_receipt_scope(receipts, cutoff=cutoff, tour="ATP"):
        with pytest.raises(ValueError, match="complete owning B1 tuple"):
            tennis_features_v3(event(), container(rows), base(cutoff=cutoff), cutoff=cutoff)
