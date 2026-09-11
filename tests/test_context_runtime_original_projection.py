"""Original-only complete-basis proofs; fixtures persist real source/native data."""
from contextlib import closing, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
import sqlite3
from types import SimpleNamespace

import pytest

import context_runtime_history_cache as cache_module
import context_runtime_tennis as replay
from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
from context_runtime_transaction import TrackedConnection
from context_models.contracts import canonical_timestamp
from context_observations import append_observation
from context_sources.tennis_status import normalize_tennis_status
from model_artifacts import ArtifactIntegrityError, canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from test_context_runtime_shared_history import five_groups
from test_context_runtime_tennis_live import _stored
from test_tennis_live_worker import NOW, competition, context_rows


def test_originals_decode_only_candidates_but_snapshots_keep_full_tuples(five_groups, monkeypatch):
    # Removing projection recreates ten complete ten-row materializations.
    db, _, artifacts, created, receipts, order = five_groups
    decode, decoded = cache_module.json.loads, []
    def observed(raw):
        decoded.append(1)
        return decode(raw)
    monkeypatch.setattr(cache_module, "json", SimpleNamespace(loads=observed))
    checked = replay.verify_live_originals(artifacts, created, receipts, set())
    assert len(checked) == 10
    assert len(decoded) == 20  # Ten independent seal rows + ten fresh candidates.
    owner, calls = replay.tennis_features_v3, []
    def features(event, history, base, **kwargs):
        assert type(history) is tuple and len(history) == 10
        calls.append(event["event_key"])
        return owner(event, history, base, **kwargs)
    monkeypatch.setattr(replay, "tennis_features_v3", features)
    for key, payload in context_rows(db):
        assert replay.verify_live_snapshot(payload, key, checked, effect=None, approval=None, limitations=set())
    assert sorted(calls) == sorted(event for _, event in order)
    assert len(decoded) == 120


@pytest.mark.parametrize("poison", ["older", "empty"])
@pytest.mark.parametrize("equal_time", [False, True])
def test_direct_store_cannot_forge_complete_original_history(tmp_path, monkeypatch, poison, equal_time):
    # A real valid row seal must not prove absence of another actual target.
    db, _ = _stored(monkeypatch, tmp_path)
    native = competition()
    native["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS")
    with closing(sqlite3.connect(db)) as conn:
        original_clock = datetime.fromisoformat(conn.execute("SELECT observed_at FROM context_observations").fetchone()[0])
    clock = original_clock if equal_time else NOW-timedelta(seconds=5)
    for row in normalize_tennis_status("ATP", "189-2026", native, grouping_slug="mens-singles", observed_at=clock):
        append_observation(db, row, observed_at=clock)
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        receipts.validate_all()
        artifacts = dict(VerifiedArtifactMapping(conn).items())
        created = {ref: datetime.fromisoformat(clock) for ref, clock in conn.execute("SELECT digest,created_at FROM artifacts")}
        ref, envelope = next((ref, row) for ref, row in artifacts.items() if row["kind"] == replay.ORIGINAL_ARTIFACT_KIND)
        origin = envelope["payload"]["origin"]
        history = replay._cold_replay_history(receipts, cutoff=NOW, tour="ATP", max_bytes=None)
        subset = tuple(row for row in history if row["digest"] == origin["native_receipt"]) if poison == "older" else ()
        cache = cache_module.EncodedHistoryCache(receipts)
        cache._store(receipts, subset, cutoff=NOW, tour="ATP")
        cold, calls = replay._cold_replay_history, []
        def observed(*args, **kwargs):
            calls.append(1)
            return cold(*args, **kwargs)
        monkeypatch.setattr(replay, "_cold_replay_history", observed)
        with pytest.raises(ArtifactIntegrityError, match="native current"):
            replay._verify_live_original(ref, envelope["payload"], artifacts, created, receipts,
                                        replay._code_variants(), None, cache)
        assert calls == [1]


def test_query_reservations_are_visible_inside_the_global_budget(five_groups):
    # Dropping accounting must not hide query keys beside the encoded pool.
    _, _, artifacts, created, receipts, _ = five_groups
    checked = replay.verify_live_originals(artifacts, created, receipts, set())
    cache = next(iter(checked.values())).history_cache
    stats = cache.stats
    assert stats["metadata_slots"] == 11
    assert stats["metadata_bytes"] > 0
    assert stats["bytes"] == sum(stats["entry_bytes"]) + stats["metadata_bytes"]
    assert stats["bytes"] + stats["pending_bytes"] <= stats["max_bytes"]


def _owner_cache(fixture, *, budget=1024**2):
    _, _, artifacts, created, receipts, _ = fixture
    cache = cache_module.EncodedHistoryCache(receipts, max_bytes=budget)
    cache._prepare_originals(receipts, artifacts, created)
    return cache


def _query(fixture, index=0):
    clock, event = fixture[-1][index]
    return dict(event_key=event, cutoff=datetime.fromisoformat(clock), tour="ATP", max_bytes=None)


def test_zero_queries_keep_owned_full_fallback_and_ignore_unowned_exact(five_groups, monkeypatch):
    # A pre-existing exact-key subset cannot borrow covering completeness.
    monkeypatch.setattr(cache_module, "_MAX_ORIGINAL_QUERIES", 0)
    _, _, artifacts, created, receipts, _ = five_groups
    query = _query(five_groups)
    cache = cache_module.EncodedHistoryCache(receipts)
    cache._store(receipts, (), cutoff=query["cutoff"], tour="ATP")
    cache._prepare_originals(receipts, artifacts, created)
    assert cache._lookup_original_native(receipts, **query) is None
    result = cache._lookup_owned_original_history(receipts, **{k:v for k,v in query.items() if k != "event_key"})
    assert type(result) is tuple and len(result) == 10
    assert cache.stats["metadata_slots"] == 2
    assert cache.stats["metadata_bytes"] > 0
    # Same-key replacement cannot preserve completeness, even identical bytes.
    maximum = max(clock for clock, _ in five_groups[-1])
    cache._store(receipts, result, cutoff=datetime.fromisoformat(maximum), tour="ATP")
    assert cache._lookup_owned_original_history(receipts, **{k:v for k,v in query.items() if k != "event_key"}) is None


@pytest.mark.parametrize("mode", ["projection", "full"])
@pytest.mark.parametrize("action", ["evict", "replace"])
def test_lookup_discards_decoded_result_after_pure_entry_change(five_groups, monkeypatch, mode, action):
    cache = _owner_cache(five_groups)
    receipts, query = five_groups[4], _query(five_groups)
    decode, calls = cache_module.json.loads, []
    maximum = max(clock for clock, _ in five_groups[-1])
    def changed(raw):
        result = decode(raw)
        if not calls:
            calls.append(1)
            if action == "evict": cache._evict()
            else: cache._store(receipts, (), cutoff=datetime.fromisoformat(maximum), tour="ATP")
        return result
    monkeypatch.setattr(cache_module, "json", SimpleNamespace(loads=changed))
    if mode == "projection":
        assert cache._lookup_original_native(receipts, **query) is None
    else:
        assert cache._lookup_owned_original_history(receipts, **{k:v for k,v in query.items() if k != "event_key"}) is None
    assert not cache._owned


@pytest.mark.parametrize("mutation", ["write", "ddl", "temp", "commit", "rollback", "revoke", "close"])
@pytest.mark.parametrize("mode", ["projection", "full"])
def test_lookup_mutation_is_hard_failure_not_cache_miss(five_groups, monkeypatch, mutation, mode):
    cache = _owner_cache(five_groups)
    conn, receipts, query = five_groups[1], five_groups[4], _query(five_groups)
    decode, called = cache_module.json.loads, []
    def changed(raw):
        result = decode(raw)
        if not called:
            called.append(1)
            _mutate(conn, receipts, mutation)
        return result
    monkeypatch.setattr(cache_module, "json", SimpleNamespace(loads=changed))
    for _ in range(2):
        with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
            if mode == "projection": cache._lookup_original_native(receipts, **query)
            else: cache._lookup_owned_original_history(receipts, **{k:v for k,v in query.items() if k != "event_key"})
    assert cache.stats["bytes"] == cache.stats["pending_bytes"] == 0


def _mutate(conn, receipts, mutation):
    if mutation == "write": conn.execute("UPDATE context_observations SET source=source")
    elif mutation == "ddl": conn.execute("CREATE TABLE projection_mutation (id INTEGER)")
    elif mutation == "temp": conn.execute("CREATE TEMP TABLE projection_mutation (id INTEGER)")
    elif mutation == "revoke": receipts._validation_stamp = None
    elif mutation == "close": conn.close()
    else:
        getattr(conn, mutation)()
        conn.execute("BEGIN")


@pytest.mark.parametrize("phase", ["cold", "seal", "publish"])
@pytest.mark.parametrize("mutation", ["interrupt", "write", "ddl", "revoke", "commit", "close"])
def test_preparation_cannot_publish_partial_authority(five_groups, monkeypatch, phase, mutation):
    import context_sources.tennis_status as status
    _, conn, artifacts, created, receipts, _ = five_groups
    cache = cache_module.EncodedHistoryCache(receipts)
    calls = []
    if phase == "cold": module, name = replay, "_cold_replay_history"
    elif phase == "seal": module, name = status, "_validate_selected_tennis_receipt_cold"
    else: module, name = cache, "_store_encoded"
    owner = getattr(module, name)
    def changed(*args, **kwargs):
        result = owner(*args, **kwargs)
        calls.append(1)
        if len(calls) == (20 if phase == "seal" else 1):
            if mutation == "interrupt": raise KeyboardInterrupt("interrupted actual owner")
            _mutate(conn, receipts, mutation)
        return result
    monkeypatch.setattr(module, name, changed)
    with pytest.raises((KeyboardInterrupt, RuntimeArtifactTrustError, sqlite3.ProgrammingError)):
        cache._prepare_originals(receipts, artifacts, created)
    assert not cache._owned and not cache._queries
    assert cache.stats["pending_bytes"] == cache.stats["metadata_bytes"] == 0


def test_complete_prefix_budget_and_fresh_candidate(five_groups):
    cache = _owner_cache(five_groups)
    receipts, query = five_groups[4], _query(five_groups)
    total = sum(cache.stats["entry_bytes"])
    count, first = cache._lookup_original_native(receipts, **{**query, "max_bytes":total})
    assert count == 1 and first["event_key"] == query["event_key"]
    assert len(canonical_bytes(first)) < total
    first["payload"]["participant_ids"].append("poison")
    assert "poison" not in cache._lookup_original_native(receipts, **query)[1]["payload"]["participant_ids"]
    for budget in (0, total-1):
        with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
            cache._lookup_original_native(receipts, **{**query, "max_bytes":budget})


def test_caller_cutoffs_do_not_grant_owned_preparation(five_groups):
    _, _, _, _, receipts, order = five_groups
    cutoff = datetime.fromisoformat(max(clock for clock, _ in order))
    cache = cache_module.EncodedHistoryCache(receipts)
    assert cache._plan_bases(receipts, {"ATP":cutoff})
    cache._prepare_original_basis(receipts, cutoff=cutoff, tour="ATP")
    assert not cache._owned and cache.stats["entries"] == 0


@pytest.mark.parametrize("budget_kind", ["zero", "tiny", "exact", "metadata", "full"])
def test_pressure_drops_optional_proof_without_truncating_history(five_groups, budget_kind):
    _, _, artifacts, created, receipts, order = five_groups
    maximum = datetime.fromisoformat(max(clock for clock, _ in order))
    complete = replay._cold_replay_history(receipts, cutoff=maximum, tour="ATP", max_bytes=None)
    total = sum(len(canonical_bytes(row)) for row in complete)
    budget = {"zero":0, "tiny":1, "exact":total, "metadata":total+256, "full":total*2}[budget_kind]
    cache = _owner_cache(five_groups, budget=budget)
    query = _query(five_groups)
    count, candidate = replay._original_native_candidate(receipts,
        {"event_key":query["event_key"], "tour":"ATP"}, query["cutoff"], total, cache)
    assert count == 1 and candidate["event_key"] == query["event_key"]
    assert cache.stats["peak_bytes"] <= budget
    assert cache.stats["pending_bytes"] == 0
    assert cache.stats["bytes"] == sum(cache.stats["entry_bytes"]) + cache.stats["metadata_bytes"]
    if budget_kind == "exact":
        assert cache.stats["entry_bytes"] == (total,)
        assert not cache._owned and not cache._queries


def _with_long_last_query(artifacts):
    from context_models.contracts import digest
    artifacts = deepcopy(artifacts)
    publication = next(row["payload"] for row in reversed(artifacts.values())
                       if row["kind"] == replay.ORIGINAL_ARTIFACT_KIND)
    event = publication["origin"]["event"]
    event["event_key"] = "espn:tennis:ATP:match:" + "9"*4096
    event["schedule_revision"] = digest({"event_key":event["event_key"], "scheduled_start":event["scheduled_start"]})
    return artifacts  # Planning-only fixture; no claim of native acceptance.


@pytest.mark.parametrize("long_key", [False, True])
def test_dropped_query_records_die_before_pending_history_fills_budget(five_groups, monkeypatch, long_key):
    # A loop-local draft must not keep an uncharged query alive after pressure.
    import sys
    import weakref
    _, _, artifacts, created, receipts, order = five_groups
    if long_key:
        artifacts = _with_long_last_query(artifacts)
    maximum = datetime.fromisoformat(max(clock for clock, _ in order))
    history = replay._cold_replay_history(receipts, cutoff=maximum, tour="ATP", max_bytes=None)
    total = sum(len(canonical_bytes(row)) for row in history)
    del history
    references, inspections, last_key = [], [], [None]
    original_query = cache_module._OriginalQuery
    class ObservedQuery(original_query):
        __slots__ = ("__weakref__",)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            references.append(weakref.ref(self))  # The observer owns no draft.
            last_key[0] = self.key  # One explicit probe reference, not cache ownership.
    monkeypatch.setattr(cache_module, "_OriginalQuery", ObservedQuery)
    cache = cache_module.EncodedHistoryCache(receipts, max_bytes=total)
    check = cache._check
    def observed(receipts):
        check(receipts)
        if cache._building and cache._pending_bytes == total:
            assert not cache._queries and cache.stats["metadata_bytes"] == 0
            live = sum(reference() is not None for reference in references)
            inspections.append((cache._pending_bytes, live))
            assert live == 0, "dropped query record outlived its metadata charge"
            key_references = sys.getrefcount(last_key[0])
            assert key_references == 2  # Probe + getrefcount argument only.
    monkeypatch.setattr(cache, "_check", observed)
    cache._prepare_originals(receipts, artifacts, created)
    assert len(references) == 10 and inspections == [(total, 0)]
    assert cache.stats["entry_bytes"] == (total,)
    assert cache.stats["pending_bytes"] == 0


@pytest.mark.parametrize("long_key", [False, True])
def test_direct_store_releases_dropped_query_key_before_encoding(five_groups, monkeypatch, long_key):
    import sys
    _, _, artifacts, created, receipts, order = five_groups
    if long_key:
        artifacts = _with_long_last_query(artifacts)
    cache = cache_module.EncodedHistoryCache(receipts)
    cache._prepare_originals(receipts, artifacts, created)
    maximum = datetime.fromisoformat(max(clock for clock, _ in order))
    key_probe = next(reversed(cache._queries))  # One known observer-owned reference.
    store, observations = cache._store_encoded, []
    def observed(*args, **kwargs):
        assert not cache._queries
        references = sys.getrefcount(key_probe)
        observations.append(references)
        assert references == 2  # Probe + getrefcount argument only.
        return store(*args, **kwargs)
    monkeypatch.setattr(cache, "_store_encoded", observed)
    cache._store(receipts, (), cutoff=maximum, tour="ATP")
    assert observations == [2]


def test_planning_releases_validated_publication_temporaries_before_cold_basis(five_groups, monkeypatch):
    import weakref
    import context_models.tennis_live as live
    _, _, artifacts, created, receipts, _ = five_groups
    validate, references = live.validate_original_publication, []
    class ObservedObject(dict):
        __slots__ = ("__weakref__",)
    def observed_publication(*args, **kwargs):
        publication = validate(*args, **kwargs)  # Keep the complete real owner check.
        publication["origin"] = ObservedObject(publication["origin"])
        publication = ObservedObject(publication)
        references.extend((weakref.ref(publication), weakref.ref(publication["origin"])))
        return publication
    monkeypatch.setattr(live, "validate_original_publication", observed_publication)
    cache = cache_module.EncodedHistoryCache(receipts)
    prepare, boundaries = cache._prepare_original_basis, []
    def observed_basis(*args, **kwargs):
        alive = sum(reference() is not None for reference in references)
        boundaries.append(alive)
        assert alive == 0, "planning payload temporary survived into basis preparation"
        return prepare(*args, **kwargs)
    monkeypatch.setattr(cache, "_prepare_original_basis", observed_basis)
    cache._prepare_originals(receipts, artifacts, created)
    assert len(references) == 20 and boundaries == [0]


def test_maximum_slot_pressure_deduplicates_but_validates_excess_publications(five_groups, monkeypatch):
    _, _, artifacts, created, receipts, _ = five_groups
    originals = [item for item in artifacts.items() if item[1]["kind"] == replay.ORIGINAL_ARTIFACT_KIND]
    artifacts, created = deepcopy(artifacts), dict(created)
    original_ref, envelope = originals[0]
    for number in range(40):
        ref = "extra-" + str(number)
        copied = deepcopy(envelope)
        copied["payload"]["origin"]["cutoff"] = canonical_timestamp(
            datetime.fromisoformat(copied["payload"]["origin"]["cutoff"])+timedelta(seconds=number+1))
        artifacts[ref], created[ref] = copied, created[original_ref]
    artifacts["duplicate"] = deepcopy(envelope)
    created["duplicate"] = created[original_ref]
    cache = cache_module.EncodedHistoryCache(receipts)
    cache._prepare_originals(receipts, artifacts, created)
    assert len(cache._queries) == 30 and cache.stats["metadata_slots"] == 31
    artifacts["duplicate"]["payload"]["schema"] = 999
    with pytest.raises(ValueError):
        cache_module.EncodedHistoryCache(receipts)._prepare_originals(receipts, artifacts, created)


def test_large_serial_and_keys_have_explicit_reservations(five_groups):
    from context_runtime_original_projection import _OriginalQuery
    key = ("event-" + "9"*100000, "9999-12-31T23:59:59.999999Z", "ATP")
    serial = 10**200
    charge = _OriginalQuery.reservation(key, 64*1024**2, serial)
    encoded_summary = canonical_bytes((key, 64*1024**2, key[1], 2, 64*1024**2,
                                      (key[1], "ATP"), serial))
    assert charge >= len(encoded_summary) > 100000
    _, _, artifacts, created, receipts, _ = five_groups
    cache = cache_module.EncodedHistoryCache(receipts)
    cache._serial = serial
    cache._prepare_originals(receipts, artifacts, created)
    for query in cache._queries.values():
        actual = canonical_bytes((query.key, query.prefix_bytes, query.latest, query.count,
                                  query.ordinal, query.basis, query.serial))
        assert len(actual) <= query.charge
    for key, (serial, charge) in cache._owned.items():
        assert len(canonical_bytes((key, serial))) <= charge
    assert cache.stats["bytes"] == sum(cache.stats["entry_bytes"])+cache.stats["metadata_bytes"]


@pytest.mark.parametrize("corruption", ["ordinal", "candidate", "count"])
def test_corrupt_claimed_projection_cannot_authorize_wrong_candidate(five_groups, corruption):
    cache = _owner_cache(five_groups)
    query = _query(five_groups)
    record = cache._queries[(query["event_key"], canonical_timestamp(query["cutoff"]), "ATP")]
    if corruption == "ordinal": record.ordinal = 1000000
    elif corruption == "count": record.count = 3
    else: record.latest = "0001-01-01T00:00:00.000000Z"
    with pytest.raises(RuntimeArtifactTrustError, match="projection"):
        cache._lookup_original_native(five_groups[4], **query)


@pytest.mark.parametrize("mode", ["disabled", "zero_queries", "evicted", "bypassed"])
def test_canonical_report_parity_with_all_original_and_snapshot_calls(five_groups, monkeypatch, mode):
    import context_runtime
    import tennis.predict
    db = five_groups[0]
    expected = context_runtime.verify_context_database(db)
    if mode == "disabled":
        monkeypatch.setattr(cache_module.EncodedHistoryCache, "_lookup_original_native", lambda *a, **k: None)
    elif mode == "zero_queries": monkeypatch.setattr(cache_module, "_MAX_ORIGINAL_QUERIES", 0)
    elif mode == "bypassed": monkeypatch.setattr(cache_module, "MAX_ENCODED_HISTORY_BYTES", 0)
    else:
        prepare = cache_module.EncodedHistoryCache._prepare_originals
        def evicted(self, *args):
            prepare(self, *args)
            while self._entries: self._evict()
        monkeypatch.setattr(cache_module.EncodedHistoryCache, "_prepare_originals", evicted)
    predict, features = tennis.predict.predict_match, replay.tennis_features_v3
    calls, histories = [], []
    def predicted(*args, **kwargs):
        calls.append(1)
        return predict(*args, **kwargs)
    def featured(event, history, *args, **kwargs):
        assert type(history) is tuple and len(history) == 10
        histories.append(1)
        return features(event, history, *args, **kwargs)
    monkeypatch.setattr(tennis.predict, "predict_match", predicted)
    monkeypatch.setattr(replay, "tennis_features_v3", featured)
    assert canonical_bytes(context_runtime.verify_context_database(db)) == canonical_bytes(expected)
    assert len(calls) == len(histories) == 10


@contextmanager
def _inventory(db):
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn)
        receipts.validate_all()
        artifacts = dict(VerifiedArtifactMapping(conn).items())
        created = {ref: datetime.fromisoformat(clock) for ref, clock in conn.execute("SELECT digest,created_at FROM artifacts")}
        yield conn, receipts, artifacts, created


@pytest.mark.parametrize("case,count,accepted", [
    ("scheduled",1,True), ("workload",1,False), ("equal_workload",2,False),
    ("equal_status",2,False), ("cancelled",1,False), ("started",1,False),
    ("defective",1,False), ("participants",1,False), ("schedule",1,False),
    ("absent",0,False), ("empty",0,False), ("future",1,True),
])
def test_every_target_row_and_native_error_matches_complete_owner(tmp_path, monkeypatch, case, count, accepted):
    from context_sources.tennis import normalize_tennis_workload
    from test_tennis_context_features import native_row
    import tennis.predict
    db, _ = _stored(monkeypatch, tmp_path)
    clock = NOW-timedelta(seconds=10 if case.startswith("equal_") else 5)
    rows = ()
    if case in {"workload", "equal_workload"}:
        rows = normalize_tennis_workload((native_row("201", "1", "2"),), observed_at=clock)[:1]
    elif case in {"absent", "empty"}:
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("DELETE FROM context_observations")
            conn.execute("DELETE FROM context_contents")
        if case == "absent":
            rows = normalize_tennis_status("ATP", "189-2026", competition(id="999"),
                grouping_slug="mens-singles", observed_at=clock)
    elif case != "scheduled":
        native = competition()
        if case in {"started", "equal_status", "future"}:
            native["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS")
        elif case == "cancelled":
            native["status"]["type"].update(state="post", name="STATUS_CANCELED", completed=True)
        elif case == "defective": native["competitors"] = []
        elif case == "participants": native["competitors"][0]["id"] = "123"
        elif case == "schedule": native["date"] = "2026-09-09T18:00Z"
        if case == "future": clock = NOW+timedelta(microseconds=1)
        rows = normalize_tennis_status("ATP", "189-2026", native,
            grouping_slug="mens-singles", observed_at=clock)
    for row in rows:
        append_observation(db, row, observed_at=clock)
    with _inventory(db) as (_, receipts, artifacts, created):
        cache = cache_module.EncodedHistoryCache(receipts)
        cache._prepare_originals(receipts, artifacts, created)
        ref, envelope = next((ref,row) for ref,row in artifacts.items() if row["kind"] == replay.ORIGINAL_ARTIFACT_KIND)
        origin = envelope["payload"]["origin"]
        query = dict(event_key=origin["event"]["event_key"], cutoff=NOW, tour="ATP", max_bytes=None)
        result = cache._lookup_original_native(receipts, **query)
        assert result is not None and result[0] == count
        if case in {"absent", "empty", "equal_status", "equal_workload"}:
            total = sum(cache.stats["entry_bytes"])
            if total:
                with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
                    cache._lookup_original_native(receipts, **{**query, "max_bytes":total-1})
            assert cache._lookup_original_native(receipts, **{**query, "max_bytes":total})[0] == count
        owner, calls, outcomes = tennis.predict.predict_match, [], []
        def predicted(*args, **kwargs):
            calls.append(1)
            return owner(*args, **kwargs)
        monkeypatch.setattr(tennis.predict, "predict_match", predicted)
        for optimization in (cache, None):
            try:
                replay._verify_live_original(ref, envelope["payload"], artifacts, created, receipts,
                    replay._code_variants(), None, optimization)
                outcomes.append("accepted")
            except ArtifactIntegrityError as exc:
                outcomes.append((type(exc).__name__, str(exc)))
        assert outcomes[0] == outcomes[1]
        assert (outcomes[0] == "accepted") is accepted
        assert len(calls) == (2 if accepted else 0)


@pytest.mark.parametrize("count", [0,2])
def test_non_candidate_lookup_checks_final_lifetime(five_groups, monkeypatch, count):
    cache = _owner_cache(five_groups)
    conn, receipts, query = five_groups[1], five_groups[4], _query(five_groups)
    record = cache._queries[(query["event_key"], canonical_timestamp(query["cutoff"]), "ATP")]
    # Exercise the no-deserializer final boundary, not native acceptance.
    record.count, record.ordinal = count, None
    owner, calls = cache._owned_current, []
    def changed(*args):
        calls.append(1)
        if len(calls) == 2: _mutate(conn, receipts, "ddl")
        return owner(*args)
    monkeypatch.setattr(cache, "_owned_current", changed)
    with pytest.raises(RuntimeArtifactTrustError):
        cache._lookup_original_native(receipts, **query)


def test_owned_full_prefix_empty_timezone_and_budget_boundaries(five_groups):
    from datetime import timezone
    cache = _owner_cache(five_groups)
    receipts, query = five_groups[4], _query(five_groups)
    early = query["cutoff"].replace(hour=9, minute=58)
    at = early.replace(minute=59)
    total = sum(cache.stats["entry_bytes"])
    for cutoff, size in ((early,0), (at-timedelta(microseconds=1),0),
                         (at,total), (at+timedelta(microseconds=1),total),
                         (at.astimezone(timezone(timedelta(hours=5, minutes=30))),total)):
        rows = cache._lookup_owned_original_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=size)
        assert type(rows) is tuple and len(rows) == (10 if size else 0)
        if size:
            with pytest.raises(RuntimeArtifactTrustError, match="history.*budget"):
                cache._lookup_owned_original_history(receipts, cutoff=cutoff, tour="ATP", max_bytes=size-1)


def test_planning_charge_covers_both_live_cutoff_maps(five_groups, monkeypatch):
    _, _, artifacts, created, receipts, _ = five_groups
    cache = cache_module.EncodedHistoryCache(receipts)
    prepare, reservations = cache._prepare_original_basis, []
    def observed(*args, **kwargs):
        size = len(canonical_bytes((cache._original_cutoffs, cache._basis_cutoffs)))
        reservations.append(size)
        assert cache._planning_bytes >= size
        return prepare(*args, **kwargs)
    monkeypatch.setattr(cache, "_prepare_original_basis", observed)
    cache._prepare_originals(receipts, artifacts, created)
    assert reservations


def test_interrupted_marker_publication_is_clean_before_returning_to_planner(five_groups, monkeypatch):
    _, _, artifacts, created, receipts, _ = five_groups
    cache = cache_module.EncodedHistoryCache(receipts)
    charge, prepare = cache._charge_metadata, cache._prepare_original_basis
    def interrupted(size):
        charge(size)
        if size > 0 and cache._owned:
            raise KeyboardInterrupt("marker publication interrupted")
    def observed(*args, **kwargs):
        try:
            return prepare(*args, **kwargs)
        except KeyboardInterrupt:
            assert not cache._owned
            raise
    monkeypatch.setattr(cache, "_charge_metadata", interrupted)
    monkeypatch.setattr(cache, "_prepare_original_basis", observed)
    with pytest.raises(KeyboardInterrupt):
        cache._prepare_originals(receipts, artifacts, created)
    assert cache.stats["metadata_bytes"] == 0


@pytest.mark.parametrize("budget_kind", ["one_tour", "both_tours", "zero_queries"])
def test_both_tour_bases_share_charges_without_losing_complete_fallback(tmp_path, monkeypatch, budget_kind):
    db, _ = _stored(monkeypatch, tmp_path, tours=("ATP","WTA"))
    if budget_kind == "zero_queries": monkeypatch.setattr(cache_module, "_MAX_ORIGINAL_QUERIES", 0)
    with _inventory(db) as (_, receipts, artifacts, created):
        histories = {tour:replay._cold_replay_history(receipts, cutoff=NOW, tour=tour, max_bytes=None)
                     for tour in ("ATP","WTA")}
        assert [len(rows) for rows in histories.values()] == [1,1]
        sizes = [sum(len(canonical_bytes(row)) for row in rows) for rows in histories.values()]
        budget = max(sizes)+512 if budget_kind == "one_tour" else sum(sizes)+512
        cache = cache_module.EncodedHistoryCache(receipts, max_bytes=budget)
        cache._prepare_originals(receipts, artifacts, created)
        assert cache.stats["entries"] == (1 if budget_kind == "one_tour" else 2)
        assert cache.stats["peak_bytes"] <= budget and cache.stats["metadata_slots"] <= 32
        for ref, envelope in artifacts.items():
            if envelope["kind"] != replay.ORIGINAL_ARTIFACT_KIND: continue
            origin = envelope["payload"]["origin"]
            count, row = replay._original_native_candidate(receipts, origin["event"], NOW, None, cache)
            assert count == 1 and row["digest"] == origin["native_receipt"]


def test_all_excess_and_duplicate_originals_still_execute_predictor(five_groups, monkeypatch):
    import tennis.predict
    _, _, artifacts, created, receipts, _ = five_groups
    artifacts, created = dict(artifacts), dict(created)
    first_ref, first = next((ref,row) for ref,row in artifacts.items() if row["kind"] == replay.ORIGINAL_ARTIFACT_KIND)
    for number in range(35):
        ref = "orphan-" + str(number)
        artifacts[ref], created[ref] = deepcopy(first), created[first_ref]
        artifacts[ref]["payload"]["origin"]["cutoff"] = canonical_timestamp(
            datetime.fromisoformat(first["payload"]["origin"]["cutoff"])+timedelta(seconds=number))
    predict, calls = tennis.predict.predict_match, []
    def observed(*args, **kwargs):
        calls.append(1)
        return predict(*args, **kwargs)
    monkeypatch.setattr(tennis.predict, "predict_match", observed)
    checked = replay.verify_live_originals(artifacts, created, receipts, set())
    assert len(checked) == len(calls) == 45
    assert len(next(iter(checked.values())).history_cache._queries) == 30


def test_reentrant_replacement_during_last_seal_cancels_pending_proof(five_groups, monkeypatch):
    import context_sources.tennis_status as status
    _, _, artifacts, created, receipts, order = five_groups
    cache = cache_module.EncodedHistoryCache(receipts)
    validate, calls = status._validate_selected_tennis_receipt_cold, []
    def changed(row):
        result = validate(row)
        calls.append(1)
        if len(calls) == 20:
            cache._store(receipts, (), cutoff=datetime.fromisoformat(max(clock for clock,_ in order)), tour="ATP")
        return result
    monkeypatch.setattr(status, "_validate_selected_tennis_receipt_cold", changed)
    cache._prepare_originals(receipts, artifacts, created)
    assert not cache._owned and not cache._queries
    assert cache.stats["pending_bytes"] == 0
    assert cache.stats["bytes"] == sum(cache.stats["entry_bytes"])+cache.stats["metadata_bytes"]


def test_long_actual_publication_query_is_charged_or_dropped(five_groups):
    from context_models.contracts import digest
    _, _, artifacts, created, receipts, _ = five_groups
    artifacts = deepcopy(artifacts)
    first = next(row for row in artifacts.values() if row["kind"] == replay.ORIGINAL_ARTIFACT_KIND)
    event = first["payload"]["origin"]["event"]
    event["event_key"] = "espn:tennis:ATP:match:" + "9"*100000
    event["schedule_revision"] = digest({"event_key":event["event_key"], "scheduled_start":event["scheduled_start"]})
    cache = cache_module.EncodedHistoryCache(receipts, max_bytes=32768)
    cache._prepare_originals(receipts, artifacts, created)
    assert all(len(key[0]) < 100000 for key in cache._queries)
    assert cache.stats["peak_bytes"] <= 32768
    # Capacity never suppresses validation of that same actual publication.
    first["payload"]["schema"] = 2
    with pytest.raises(ValueError):
        cache_module.EncodedHistoryCache(receipts, max_bytes=0)._prepare_originals(receipts, artifacts, created)


def test_cold_original_fallback_rechecks_lifetime_after_complete_owner(five_groups, monkeypatch):
    _, conn, _, _, receipts, _ = five_groups
    cache = cache_module.EncodedHistoryCache(receipts)
    query = _query(five_groups)
    owner = replay._cold_replay_history
    def changed(*args, **kwargs):
        result = owner(*args, **kwargs)
        _mutate(conn, receipts, "ddl")
        return result
    monkeypatch.setattr(replay, "_cold_replay_history", changed)
    with pytest.raises(RuntimeArtifactTrustError):
        replay._original_native_candidate(receipts, {"event_key":query["event_key"], "tour":"ATP"},
                                          query["cutoff"], None, cache)
