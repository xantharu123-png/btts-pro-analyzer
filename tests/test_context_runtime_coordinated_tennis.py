"""Fixed physical/source ownership on real persisted inventories."""
from collections import Counter
from contextlib import closing, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
import sqlite3
import sys
import weakref

import pytest

import context_observations
import context_runtime
import context_runtime_tennis as replay
import context_sources.tennis_status as status
import tennis.predict
import context_transport
import context_runtime_history_cache as cache_module
from context_models.contracts import ContextContractError, canonical_timestamp
from context_runtime_inventory import VerifiedArtifactMapping, VerifiedReceiptMapping
from context_runtime_transaction import TrackedConnection
from model_artifacts import ArtifactIntegrityError, canonical_bytes, put_artifact
from runtime_paths import RuntimeArtifactTrustError
from test_context_runtime_shared_history import five_groups
from test_context_runtime_tennis_live import _stored
from test_tennis_live_worker import NOW, competition


@contextmanager
def inventory(db, *, protected=()):
    with closing(sqlite3.connect(db, factory=TrackedConnection)) as conn:
        conn.execute("BEGIN")
        receipts = VerifiedReceiptMapping(conn, protected_receipts=protected)
        artifacts = VerifiedArtifactMapping(conn)
        created = {ref: datetime.fromisoformat(clock) for ref, clock in
                   conn.execute("SELECT digest,created_at FROM artifacts")}
        yield conn, receipts, artifacts, created


def append_status(db, *, tour="ATP", clock=NOW, change=None, number="999"):
    row = status.normalize_tennis_status(tour, "189-2026", competition(id=number),
        grouping_slug="mens-singles" if tour == "ATP" else "womens-singles", observed_at=clock)[0]
    if change is not None:
        change(row)
    return context_observations.append_observation(db, row, observed_at=clock)


def test_full_verification_decodes_physical_once_and_keeps_independent_seal(five_groups, monkeypatch):
    db, _, _, _, _, order = five_groups
    calls = Counter()
    def spy(module, name, label):
        owner = getattr(module, name)
        def observed(*args, **kwargs):
            calls[label] += 1
            return owner(*args, **kwargs)
        monkeypatch.setattr(module, name, observed)
    spy(context_observations, "_decode_receipt", "physical")
    spy(context_observations, "normalize_observation", "physical_generic")
    spy(status, "_validate_selected_tennis_receipt_cold", "cold")
    spy(status, "normalize_observation", "selected_generic")
    spy(tennis.predict, "predict_match", "predictor")
    spy(context_transport, "replay_context_payload", "transport")
    owner, histories = replay.tennis_features_v3, []
    def features(event, history, base, **kwargs):
        assert type(history) is tuple and len(history) == 10
        histories.append(tuple(row["digest"] for row in history))
        return owner(event, history, base, **kwargs)
    monkeypatch.setattr(replay, "tennis_features_v3", features)
    report = context_runtime.verify_context_database(db)
    assert report["counts"]["observations"] == len(order) == 10
    assert calls["physical"] == 10
    assert calls["cold"] == 10  # Full cold seal of ten independently decoded encodings.
    assert calls["physical_generic"] == calls["selected_generic"] == 10
    assert calls["predictor"] == calls["transport"] == len(histories) == 10
    assert all(history == histories[0] for history in histories)
    assert not report["empirical_approval_verified"]


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
@pytest.mark.parametrize("fault", ["reception", "envelope", "participants", "native_flag", "source"])
def test_source_failure_defers_only_until_real_postphysical_cold_rejection(tmp_path, monkeypatch, tour, fault):
    db, _ = _stored(monkeypatch, tmp_path)
    def damage(row):
        if fault == "reception": row["payload"]["competition_revision"] = "0"*64
        elif fault == "envelope": row["competition"] = "espn:ATP:tournament:1"
        elif fault == "participants": row["payload"]["participant_ids"][0] = "espn:tennis:WTA:player:88" if tour == "ATP" else "espn:tennis:ATP:player:88"
        elif fault == "native_flag": row["payload"]["native_status"]["cancelled"] = True
        else: row["source"] = "other"
    append_status(db, tour=tour, clock=NOW-timedelta(seconds=5), change=damage)
    with inventory(db) as (_, receipts, artifacts, created):
        count, cache = receipts._validate_all_with_tennis(artifacts)
        assert count == 2 and cache is None and receipts._validation_stamp is not None
        cold, calls = replay._cold_replay_history, []
        def observed(*args, **kwargs):
            calls.append(1)
            return cold(*args, **kwargs)
        monkeypatch.setattr(replay, "_cold_replay_history", observed)
        with pytest.raises(ContextContractError) as ordinary:
            replay.verify_live_originals(artifacts, created, receipts, set())
        assert calls == [1]
        # Public selector remains independently authoritative for arbitrary rows.
        with pytest.raises(type(ordinary.value)) as selected:
            status.select_tennis_observations(tuple(receipts.values()), cutoff=NOW, tour="ATP")
        assert str(selected.value) == str(ordinary.value)


@pytest.mark.parametrize("early", ["source", "publication"])
@pytest.mark.parametrize("later", ["receipt", "orphan"])
def test_deferred_domain_failure_cannot_hide_later_physical_corruption(tmp_path, monkeypatch, early, later):
    db, _ = _stored(monkeypatch, tmp_path)
    if early == "source":
        append_status(db, clock=NOW-timedelta(seconds=5), change=lambda row: row["payload"].update(competition_revision="0"*64))
    else:
        put_artifact(db, kind=replay.ORIGINAL_ARTIFACT_KIND, payload={"schema":999}, created_at=NOW)
    ref = append_status(db, clock=NOW+timedelta(seconds=5), number="998")
    with closing(sqlite3.connect(db)) as conn, conn:
        if later == "receipt": conn.execute("UPDATE context_observations SET source='broken' WHERE digest=?", (ref,))
        else: conn.execute("DELETE FROM context_observations WHERE digest=?", (ref,))
    with inventory(db) as (_, receipts, artifacts, _):
        with pytest.raises((ContextContractError, ArtifactIntegrityError), match="persisted context receipt|no validated receipt"):
            receipts._validate_all_with_tennis(artifacts)
        assert receipts._validation_stamp is None and receipts._validation_failed


def test_both_tour_union_source_checks_and_own_cutoffs_use_complete_order(tmp_path, monkeypatch):
    db, _ = _stored(monkeypatch, tmp_path, tours=("ATP", "WTA"))
    # A valid, unreferenced original publication still extends its tour maximum.
    with inventory(db) as (_, _, artifacts, _):
        publication = deepcopy(next(row["payload"] for row in artifacts.values()
            if row["kind"] == replay.ORIGINAL_ARTIFACT_KIND and row["payload"]["origin"]["event"]["tour"] == "WTA"))
    publication["origin"]["cutoff"] = canonical_timestamp(NOW+timedelta(seconds=20))
    put_artifact(db, kind=replay.ORIGINAL_ARTIFACT_KIND, payload=publication, created_at=NOW+timedelta(seconds=21))
    for tour in ("ATP", "WTA"):
        append_status(db, tour=tour, clock=NOW+timedelta(seconds=10))
        append_status(db, tour=tour, clock=NOW+timedelta(seconds=30), number="998")
    calls = Counter()
    decode, tail, cold = context_observations._decode_receipt, status._validate_tennis_source_tail, status._validate_selected_tennis_receipt_cold
    def physical(raw):
        calls["physical"] += 1
        return decode(raw)
    def source(row, raw):
        calls["source"] += 1
        return tail(row, raw)
    def seal(row):
        calls["seal"] += 1
        return cold(row)
    monkeypatch.setattr(context_observations, "_decode_receipt", physical)
    monkeypatch.setattr(status, "_validate_tennis_source_tail", source)
    monkeypatch.setattr(status, "_validate_selected_tennis_receipt_cold", seal)
    with inventory(db) as (_, receipts, artifacts, _):
        _, cache = receipts._validate_all_with_tennis(artifacts)
        assert calls == {"physical":6, "source":7, "seal":3}  # Four union tails plus three independent full seals.
        assert cache.stats["entries"] == 2 and cache.stats["metadata_slots"] == 5
        for tour, count in (("ATP",1), ("WTA",2)):
            cutoff = NOW if tour == "ATP" else NOW+timedelta(seconds=20)
            history = cache._lookup_owned_original_history(receipts, cutoff=cutoff, tour=tour, max_bytes=None)
            assert len(history) == count
            assert [(r["observed_at"],r["digest"]) for r in history] == sorted((r["observed_at"],r["digest"]) for r in history)
        assert cache.stats["bytes"] == sum(cache.stats["entry_bytes"])+cache.stats["metadata_bytes"]
        assert cache.stats["pending_bytes"] == 0


@pytest.mark.parametrize("kind", ["dict", "subclass", "foreign", "already_validated"])
def test_wrong_or_prior_physical_provenance_never_mints_source_authority(tmp_path, monkeypatch, kind):
    db, _ = _stored(monkeypatch, tmp_path)
    with inventory(db) as (_, receipts, artifacts, created), inventory(db) as (_, _, foreign, _):
        if kind == "dict": artifacts = dict(artifacts)
        elif kind == "subclass":
            class Alias(VerifiedArtifactMapping): pass
            artifacts = Alias(receipts._connection)
        elif kind == "foreign": artifacts = foreign
        else: receipts.validate_all()
        _, cache = receipts._validate_all_with_tennis(artifacts)
        assert cache is None
        public = cache_module.EncodedHistoryCache(receipts)
        public._store(receipts, (), cutoff=NOW, tour="ATP")
        checked = replay.verify_live_originals(artifacts, created, receipts, set(), history_cache=public)
        assert len(checked) == 1 and next(iter(checked.values())).history_cache is not public


@pytest.mark.parametrize("phase", ["source", "encode", "seal", "fold"])
@pytest.mark.parametrize("mutation", ["write", "main_ddl", "temp_ddl", "commit", "rollback", "close", "interrupt", "memory"])
def test_each_coordinated_boundary_is_fail_closed_and_releases_pool(tmp_path, monkeypatch, phase, mutation):
    db, _ = _stored(monkeypatch, tmp_path)
    with inventory(db) as (conn, receipts, artifacts, _):
        caches, owner_init = [], cache_module.EncodedHistoryCache.__init__
        def constructed(self, *args, **kwargs):
            owner_init(self, *args, **kwargs)
            caches.append(self)
        monkeypatch.setattr(cache_module.EncodedHistoryCache, "__init__", constructed)
        if phase == "source": module, name = status, "_validate_tennis_source_tail"
        elif phase == "encode": module, name = cache_module, "canonical_bytes"
        elif phase == "seal": module, name = status, "_validate_selected_tennis_receipt_cold"
        else: module, name = cache_module.EncodedHistoryCache, "_fold_original_queries"
        owner, touched = getattr(module, name), []
        def changed(*args, **kwargs):
            result = owner(*args, **kwargs)
            # Encoding's other callers reserve scalar metadata during planning.
            eligible = phase != "encode" or type(args[0]) is dict and "evidence_class" in args[0]
            if eligible and not touched:
                touched.append(1)
                if mutation == "write": conn.execute("UPDATE context_observations SET source=source")
                elif mutation == "main_ddl": conn.execute("CREATE TABLE changed (id INTEGER)")
                elif mutation == "temp_ddl": conn.execute("CREATE TEMP TABLE changed (id INTEGER)")
                elif mutation == "close": conn.close()
                elif mutation == "interrupt": raise KeyboardInterrupt()
                elif mutation == "memory": raise MemoryError()
                else:
                    getattr(conn, mutation)()
                    conn.execute("BEGIN")
            return result
        monkeypatch.setattr(module, name, changed)
        with pytest.raises((RuntimeArtifactTrustError, sqlite3.ProgrammingError, KeyboardInterrupt, MemoryError)):
            receipts._validate_all_with_tennis(artifacts)
        assert touched and len(caches) == 1
        cache = caches[0]
        assert cache.stats["bytes"] == cache.stats["pending_bytes"] == cache.stats["metadata_bytes"] == 0
        assert not cache._owned and not cache._queries and cache._coordinated_pending is None


def test_reentrant_store_cancels_optional_pool_without_adopting_subset(tmp_path, monkeypatch):
    db, _ = _stored(monkeypatch, tmp_path)
    caches, owner = [], cache_module.EncodedHistoryCache._begin_coordinated
    def begin(self, *args):
        caches.append(self)
        return owner(self, *args)
    monkeypatch.setattr(cache_module.EncodedHistoryCache, "_begin_coordinated", begin)
    tail = status._validate_tennis_source_tail
    with inventory(db) as (_, receipts, artifacts, created):
        def source(*args):
            result = tail(*args)
            caches[0]._store(receipts, (), cutoff=NOW, tour="ATP")
            return result
        monkeypatch.setattr(status, "_validate_tennis_source_tail", source)
        _, cache = receipts._validate_all_with_tennis(artifacts)
        assert cache is None and caches[0].stats["bytes"] == caches[0].stats["pending_bytes"] == 0
        monkeypatch.setattr(status, "_validate_tennis_source_tail", tail)
        assert len(replay.verify_live_originals(artifacts, created, receipts, set())) == 1


@pytest.mark.parametrize("budget", [0, 1, 512, 2500, 64*1024*1024])
def test_pressure_is_optional_and_canonical_full_report_is_unchanged(tmp_path, monkeypatch, budget):
    db, _ = _stored(monkeypatch, tmp_path, tours=("ATP", "WTA"))
    expected = canonical_bytes(context_runtime.verify_context_database(db))
    monkeypatch.setattr(cache_module, "MAX_ENCODED_HISTORY_BYTES", budget)
    assert canonical_bytes(context_runtime.verify_context_database(db)) == expected


def test_decoded_rows_and_pending_encodings_have_real_single_owner_lifetimes(tmp_path, monkeypatch):
    db, _ = _stored(monkeypatch, tmp_path)
    references, probe, boundaries = [], [None], []
    physical = context_observations._decode_receipt
    class ObservedRow(dict):
        __slots__ = ("__weakref__",)
    def decode(raw):
        result = ObservedRow(physical(raw))
        references.append(weakref.ref(result))
        return result
    monkeypatch.setattr(context_observations, "_decode_receipt", decode)
    seal = cache_module.EncodedHistoryCache._seal_coordinated
    def sealing(self):
        assert all(ref() is None for ref in references)
        probe[0] = self._coordinated_pending["ATP"][0]
        count = sys.getrefcount(probe[0])
        assert count == 3  # Probe, sole pending list, call argument.
        assert self._pending_bytes == len(probe[0])
        boundaries.append("pending")
        return seal(self)
    monkeypatch.setattr(cache_module.EncodedHistoryCache, "_seal_coordinated", sealing)
    with inventory(db) as (_, receipts, artifacts, _):
        _, cache = receipts._validate_all_with_tennis(artifacts)
        count = sys.getrefcount(probe[0])
        assert count == 3  # The same bytes now have one retained owner.
        assert cache.stats["pending_bytes"] == 0
        cache._evict()
        count = sys.getrefcount(probe[0])
        assert count == 2
        assert boundaries == ["pending"]


def test_long_dropped_query_and_iterator_die_before_metadata_uncharge(tmp_path, monkeypatch):
    from context_models.contracts import digest
    db, _ = _stored(monkeypatch, tmp_path)
    with inventory(db) as (_, _, artifacts, _):
        publication = deepcopy(next(row["payload"] for row in artifacts.values()
                                    if row["kind"] == replay.ORIGINAL_ARTIFACT_KIND))
    event = publication["origin"]["event"]
    event["event_key"] = "espn:tennis:ATP:match:" + "9"*4096
    event["schedule_revision"] = digest({"event_key":event["event_key"], "scheduled_start":event["scheduled_start"]})
    put_artifact(db, kind=replay.ORIGINAL_ARTIFACT_KIND, payload=publication, created_at=NOW+timedelta(seconds=1))
    refs, probes, boundaries = [], [], []
    original_query = cache_module._OriginalQuery
    class ObservedQuery(original_query):
        __slots__ = ("__weakref__",)
        def __init__(self, *args):
            super().__init__(*args)
            refs.append(weakref.ref(self))
            probes.append(self.key)
    monkeypatch.setattr(cache_module, "_OriginalQuery", ObservedQuery)
    begin, seal, charge = cache_module.EncodedHistoryCache._begin_coordinated, cache_module.EncodedHistoryCache._seal_coordinated, cache_module.EncodedHistoryCache._charge_metadata
    def started(self, *args):
        self._serial = 9  # Planning must reserve the actual upcoming serial width.
        result = begin(self, *args)
        self._serial = 10**100  # Exercise a later owning-entry serial-width transition.
        return result
    def sealed(self):
        result = seal(self)
        key = next(iter(self._entries))
        # Exact marker fit leaves no byte for the increased query serial.
        self._max_bytes = self._bytes + len(canonical_bytes((key, self._seals[key]))) + 32
        return result
    def charged(self, size):
        if size < 0 and not self._queries:
            counts = [sys.getrefcount(probes[index]) for index in range(len(probes))]
            assert counts == [2,2]
            assert all(ref() is None for ref in refs)
            boundaries.append(size)
        return charge(self, size)
    monkeypatch.setattr(cache_module.EncodedHistoryCache, "_begin_coordinated", started)
    monkeypatch.setattr(cache_module.EncodedHistoryCache, "_seal_coordinated", sealed)
    monkeypatch.setattr(cache_module.EncodedHistoryCache, "_charge_metadata", charged)
    with inventory(db) as (_, receipts, artifacts, _):
        _, cache = receipts._validate_all_with_tennis(artifacts)
        assert cache is not None and not cache._queries and len(cache._owned) == 1
        assert len(boundaries) == 1 and cache.stats["bytes"] <= cache.stats["max_bytes"]


@pytest.mark.parametrize("no_originals", [False, True])
def test_empty_physical_and_no_original_routes_remain_cold_without_fabricated_evidence(tmp_path, monkeypatch, no_originals):
    db, _ = _stored(monkeypatch, tmp_path)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DELETE FROM context_observations")
        conn.execute("DELETE FROM context_contents")
        if no_originals:
            conn.execute("DELETE FROM artifacts WHERE kind=?", (replay.ORIGINAL_ARTIFACT_KIND,))
    with inventory(db) as (_, receipts, artifacts, created):
        count, cache = receipts._validate_all_with_tennis(artifacts)
        assert count == 0
        if no_originals:
            assert cache is None and replay.verify_live_originals(artifacts, created, receipts, set()) == {}
        else:
            assert cache.stats["entries"] == 1 and cache.stats["entry_bytes"] == (0,)
            with pytest.raises(ArtifactIntegrityError, match="native current"):
                replay.verify_live_originals(artifacts, created, receipts, set(), history_cache=cache)


def test_unknown_future_and_protected_receipts_are_never_source_inputs(tmp_path, monkeypatch):
    db, _ = _stored(monkeypatch, tmp_path)
    append_status(db, clock=NOW-timedelta(seconds=5), change=lambda row: row.update(source_schema="unknown-v1"))
    append_status(db, clock=NOW+timedelta(seconds=5), change=lambda row: row["payload"].update(competition_revision="0"*64), number="998")
    protected = append_status(db, clock=NOW-timedelta(seconds=4), change=lambda row: row["payload"].update(competition_revision="0"*64), number="997")
    decode, tail, calls = context_observations._decode_receipt, status._validate_tennis_source_tail, Counter()
    def physical(raw):
        assert raw[0] != protected
        calls["physical"] += 1
        return decode(raw)
    def source(*args):
        calls["source"] += 1
        return tail(*args)
    monkeypatch.setattr(context_observations, "_decode_receipt", physical)
    monkeypatch.setattr(status, "_validate_tennis_source_tail", source)
    with inventory(db, protected=(protected,)) as (_, receipts, artifacts, _):
        count, cache = receipts._validate_all_with_tennis(artifacts)
        assert count == 4 and calls == {"physical":3,"source":2}
        assert len(cache._entries[next(iter(cache._entries))][0]) == 1


@pytest.mark.parametrize("mutation", ["revoke", "ddl", "commit", "interrupt"])
@pytest.mark.parametrize("empty", [False, True])
def test_final_and_empty_seal_proof_boundaries_cannot_publish(tmp_path, monkeypatch, mutation, empty):
    db, _ = _stored(monkeypatch, tmp_path)
    if empty:
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("DELETE FROM context_observations")
            conn.execute("DELETE FROM context_contents")
    owner = cache_module.EncodedHistoryCache._seal_coordinated
    with inventory(db) as (conn, receipts, artifacts, _):
        def changed(self):
            result = owner(self)
            if mutation == "revoke": receipts._validation_stamp = None
            elif mutation == "ddl": conn.execute("CREATE TEMP TABLE late (id INTEGER)")
            elif mutation == "interrupt": raise KeyboardInterrupt()
            else:
                conn.commit()
                conn.execute("BEGIN")
            return result
        monkeypatch.setattr(cache_module.EncodedHistoryCache, "_seal_coordinated", changed)
        with pytest.raises((RuntimeArtifactTrustError, KeyboardInterrupt)):
            receipts._validate_all_with_tennis(artifacts)
        assert receipts._validation_stamp is None


def test_recursive_physical_owner_cannot_construct_a_second_pending_pool(tmp_path, monkeypatch):
    db, _ = _stored(monkeypatch, tmp_path)
    tail = status._validate_tennis_source_tail
    with inventory(db) as (_, receipts, artifacts, _):
        def recursive(*args):
            result = tail(*args)
            receipts._validate_all_with_tennis(artifacts)
            return result
        monkeypatch.setattr(status, "_validate_tennis_source_tail", recursive)
        with pytest.raises(RuntimeArtifactTrustError, match="already active"):
            receipts._validate_all_with_tennis(artifacts)
        assert receipts._validation_stamp is None and not receipts._validating


def test_exact_marker_fit_and_one_byte_below_use_the_same_budget(tmp_path, monkeypatch):
    db, _ = _stored(monkeypatch, tmp_path)
    monkeypatch.setattr(cache_module, "_MAX_ORIGINAL_QUERIES", 0)
    with inventory(db) as (_, receipts, artifacts, _):
        _, cache = receipts._validate_all_with_tennis(artifacts)
        exact = cache.stats["bytes"]
    for budget, fits in ((exact, True), (exact-1, False)):
        monkeypatch.setattr(cache_module, "MAX_ENCODED_HISTORY_BYTES", budget)
        with inventory(db) as (_, receipts, artifacts, created):
            _, cache = receipts._validate_all_with_tennis(artifacts)
            assert (cache is not None) is fits
            if fits:
                assert cache.stats["bytes"] == exact and cache.stats["pending_bytes"] == 0
            assert len(replay.verify_live_originals(artifacts, created, receipts, set(), history_cache=cache)) == 1


def test_all_excess_persisted_originals_are_planned_and_both_pending_slots_are_visible(tmp_path, monkeypatch):
    db, _ = _stored(monkeypatch, tmp_path, tours=("ATP", "WTA"))
    with inventory(db) as (_, _, artifacts, _):
        publication = deepcopy(next(row["payload"] for row in artifacts.values()
            if row["kind"] == replay.ORIGINAL_ARTIFACT_KIND and row["payload"]["origin"]["event"]["tour"] == "ATP"))
    for index in range(35):
        publication["origin"]["cutoff"] = canonical_timestamp(NOW+timedelta(seconds=index+1))
        put_artifact(db, kind=replay.ORIGINAL_ARTIFACT_KIND, payload=publication, created_at=NOW+timedelta(seconds=40))
    observations, owner = [], cache_module.EncodedHistoryCache._seal_coordinated
    def seal(self):
        observations.append(self.stats["metadata_slots"])
        assert len(self._queries) == 30 and len(self._coordinated_pending) == 2
        assert self._original_cutoffs["ATP"] == canonical_timestamp(NOW+timedelta(seconds=35))
        return owner(self)
    monkeypatch.setattr(cache_module.EncodedHistoryCache, "_seal_coordinated", seal)
    predict, calls = tennis.predict.predict_match, []
    def predicted(*args, **kwargs):
        calls.append(1)
        return predict(*args, **kwargs)
    monkeypatch.setattr(tennis.predict, "predict_match", predicted)
    with inventory(db) as (_, receipts, artifacts, created):
        _, cache = receipts._validate_all_with_tennis(artifacts)
        assert observations == [32] and cache.stats["metadata_slots"] == 32
        assert len(replay.verify_live_originals(artifacts, created, receipts, set(), history_cache=cache)) == len(calls) == 37


def test_source_cancellation_has_no_row_traceback_or_other_tour_encoding_alias(tmp_path, monkeypatch):
    db, _ = _stored(monkeypatch, tmp_path, tours=("ATP", "WTA"))
    append_status(db, tour="WTA", clock=NOW-timedelta(seconds=5),
                  change=lambda row: row["payload"].update(competition_revision="0"*64))
    rows, probe, boundaries = [], [None], []
    physical, cancel = context_observations._decode_receipt, cache_module.EncodedHistoryCache._cancel_coordinated
    class ObservedRow(dict):
        __slots__ = ("__weakref__",)
    def decode(raw):
        result = ObservedRow(physical(raw))
        rows.append(weakref.ref(result))
        return result
    def cancelled(self):
        assert all(ref() is None for ref in rows)
        assert self._pending_bytes > 0 and set(self._coordinated_pending) == {"ATP", "WTA"}
        probe[0] = self._coordinated_pending["ATP"][0]
        result = cancel(self)
        count = sys.getrefcount(probe[0])
        assert count == 2  # Observer only; no cancelled list or traceback owns bytes.
        assert self.stats["bytes"] == self.stats["pending_bytes"] == 0
        boundaries.append(1)
        return result
    monkeypatch.setattr(context_observations, "_decode_receipt", decode)
    monkeypatch.setattr(cache_module.EncodedHistoryCache, "_cancel_coordinated", cancelled)
    with inventory(db) as (_, receipts, artifacts, _):
        _, cache = receipts._validate_all_with_tennis(artifacts)
        assert cache is None and boundaries == [1] and len(rows) == 3
