"""Synthetic native publication mechanics, not prediction-quality evidence."""
from copy import deepcopy
from datetime import timedelta
import json
import sqlite3

import pytest

import challenge_engine as engine
import football_opponent_publication as comparison
from context_models.contracts import ContextContractError, ContextIntegrityError, digest
from context_training_helpers import NOW, detail


def publication(tmp_path, monkeypatch, *, count=48, payload_limit=4_000_000, finalize=True):
    from context_models.football_original_publication import FootballOriginalPublication
    from context_sources.football_capture import _Capture
    import football_original
    path = tmp_path / "native-opponent.db"
    observer = _Capture(path, baseline_enabled=True)
    past = []
    for index in range(count):
        start = NOW - timedelta(days=count - index)
        raw = detail(1000 + index, start, goals=(1 + index % 3, index % 3))
        observer.record("fixtures", {"id": raw["fixture"]["id"]},
            {"response": [raw], "errors": [], "results": 1, "paging": {"current": 1, "total": 1}},
            observed_at=start + timedelta(hours=3), status=200)
        past.append(raw)
    target = detail(9000, NOW + timedelta(hours=2), terminal="NS")
    observer.record("fixtures", {"id": 9000},
        {"response": [target], "errors": [], "results": 1, "paging": {"current": 1, "total": 1}},
        observed_at=NOW - timedelta(minutes=30), status=200)
    class Clock:
        @staticmethod
        def now(tz=None):
            return NOW + timedelta(seconds=1)
    monkeypatch.setattr("context_models.football_original_publication.datetime", Clock)
    monkeypatch.setattr(football_original, "_capture_now", lambda: NOW)
    owner = FootballOriginalPublication(path, observer,
        max_publication_payload_bytes=payload_limit, max_worker_payload_bytes=payload_limit,
        max_source_payload_bytes=4_000_000)
    owner.freeze(tuple([target, *past]))
    baseline = engine.fixture_market_probabilities(target, past)
    actual = engine.fixture_market_probabilities(target, past, **owner.model_kwargs(decision_at=NOW))
    assert actual == baseline
    if finalize:
        owner._budget.finish_optional_comparisons()
    return path, owner, target, past


@pytest.fixture
def native(tmp_path, monkeypatch):
    return publication(tmp_path, monkeypatch)


def objects(path):
    with sqlite3.connect(path) as connection:
        return {ref: {"kind": kind, "payload": json.loads(payload), "bytes": payload}
                for ref, kind, payload in connection.execute("SELECT digest,kind,payload FROM artifacts")}


def material(native):
    from context_models.football_original_storage import load_original
    from context_observations import freeze_named_receipts
    path, owner, _, _ = native
    ref = owner.report()["events"][0]["binding_ref"]
    binding = objects(path)[ref]["payload"]
    original = load_original(path, binding["original_manifest_digest"])
    refs = sorted({key for values in binding["inspected_receipts"].values() for key in values})
    receipts = freeze_named_receipts(path, tuple(refs))
    return original, binding, receipts


def test_actual_native_publication_collects_a_distinct_compact_comparison(native):
    path, owner, _, _ = native
    candidates = [obj for obj in objects(path).values() if obj["kind"] == comparison.KIND]
    assert len(candidates) == 1
    value = candidates[0]["payload"]
    assert value["model_version"] == comparison.VERSION
    assert value["role"] == "experimental-not-applied" and value["empirically_qualified"] is False
    assert value["training_matches"] == value["receipt_clock_matches"] == 48
    assert value["original_binding_ref"] == owner.report()["events"][0]["binding_ref"]
    assert len(candidates[0]["bytes"]) < comparison.MAX_PAYLOAD_BYTES
    assert not any(key in value for key in ("league_history", "joint_cells", "coefficients", "goal_provenance"))
    assert value["recipe"]["calibration"] == "identity-new-recipe-no-inherited-market-calibrators"
    assert not any(obj["kind"] in {"context-effect-v1", "context-approval-v1"} for obj in objects(path).values())


def test_every_goal_market_uses_one_joint_law_and_counts_are_not_relabelled(native):
    value = next(obj["payload"] for obj in objects(native[0]).values() if obj["kind"] == comparison.KIND)
    law = engine.score_matrix(value["params"]["home_lambda"], value["params"]["away_lambda"])
    assert value["markets"] == {spec.key: engine.market_probability(law, spec) for spec in engine.GOAL_MARKET_SPECS}
    assert set(value["markets"]) == {spec.key for spec in engine.GOAL_MARKET_SPECS}
    assert sum(value["markets"][key] for key in ("RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY")) == pytest.approx(1)
    assert value["markets"]["BTTS_YES"] + value["markets"]["BTTS_NO"] == pytest.approx(1)


def test_reconstruction_is_read_only_and_exactly_reproduces_stored_bytes(native):
    path, owner, _, _ = native
    before = path.read_bytes()
    with sqlite3.connect(path) as connection:
        rebuilt = comparison.reconstruct_opponent_comparison(connection,
            owner.report()["events"][0]["binding_ref"], latest=NOW + timedelta(seconds=2))
    saved = objects(path)[rebuilt.digest]
    assert saved["bytes"] == rebuilt.payload_bytes
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["swap", "missing", "after_decision", "foreign", "content", "logical_hash", "target"])
def test_invalid_source_or_original_is_not_silently_skipped(native, change):
    original, binding, receipts = material(native)
    receipts = list(deepcopy(receipts))
    if change == "swap":
        refs = binding["consumed_receipts"]
        first, second = list(refs)[:2]
        refs[first], refs[second] = refs[second], refs[first]
    elif change == "missing":
        receipts.pop()
    elif change == "after_decision":
        from context_sources.outcomes import normalize_football_base_input
        from context_models.contracts import canonical_timestamp
        raw = deepcopy(receipts[0])
        observed = NOW + timedelta(minutes=1)
        normalized = normalize_football_base_input(raw["payload"]["detail"], observed_at=observed)
        raw.update(normalized, observed_at=canonical_timestamp(observed), content_digest=digest(normalized))
        raw["digest"] = digest({"content_digest": raw["content_digest"], "observed_at": raw["observed_at"]})
        receipts[0] = raw
    elif change == "foreign":
        receipts[0]["event_key"] = "api-football:football:5555"
    elif change == "content":
        receipts[0]["payload"]["detail"]["goals"]["home"] = 9
    elif change == "logical_hash":
        binding["original_logical_digest"] = "a" * 64
    else:
        binding["native_event"]["away_id"] = "api-football:team:3"
    with pytest.raises(ContextContractError):
        comparison.prepare_opponent_comparison(original, binding, tuple(receipts))


def test_uncaptured_sources_and_insufficient_history_are_not_false_activation(native, tmp_path, monkeypatch):
    import football_opponent_strength as strength
    original, binding, receipts = material(native)
    binding["source_state"] = "partial"
    binding["unresolved"] = {binding["target_record"]: "native-receipt-unavailable"}
    with pytest.raises(strength.ComparisonUnavailable):
        comparison.prepare_opponent_comparison(original, binding, receipts)
    small_dir = tmp_path / "small"
    small_dir.mkdir()
    small, owner, _, _ = publication(small_dir, monkeypatch, count=26)
    assert owner.report()["events"][0]["source_state"] == "captured"
    assert not any(obj["kind"] == comparison.KIND for obj in objects(small).values())


def test_repeated_identical_original_does_not_duplicate_or_refit_per_market(tmp_path, monkeypatch):
    path, owner, target, past = publication(tmp_path, monkeypatch, finalize=False)
    before = objects(path)
    budget = owner.remaining_payload_bytes
    import football_opponent_strength as strength
    fitted = strength._fit.cache_info().hits
    engine.fixture_market_probabilities(target, past, **owner.model_kwargs(decision_at=NOW))
    assert owner.remaining_payload_bytes == budget
    assert objects(path) == before
    assert strength._fit.cache_info().hits > fitted
    owner._budget.finish_optional_comparisons()
    assert sum(obj['kind'] == comparison.KIND for obj in objects(path).values()) == 1


def test_late_original_cannot_be_promoted_to_prematch_comparison(native):
    original, binding, receipts = material(native)
    binding["decision_at"] = binding["native_event"]["scheduled_start"]
    with pytest.raises(ContextIntegrityError, match="prematch"):
        comparison.prepare_opponent_comparison(original, binding, receipts)


def test_retroactive_receipt_class_is_not_rewritten_as_prospective(native):
    original, binding, receipts = material(native)
    changed = list(deepcopy(receipts))
    changed[0]["evidence_class"] = "retrospective"
    with pytest.raises(ContextIntegrityError, match="prospective"):
        comparison.prepare_opponent_comparison(original, binding, tuple(changed))


def test_optional_comparison_cannot_consume_the_existing_original_budget(native, tmp_path, monkeypatch):
    path, owner, _, _ = native
    comparison_bytes = sum(len(obj["bytes"]) for obj in objects(path).values() if obj["kind"] == comparison.KIND)
    # Original reports do not change after the worker's optional finalizer;
    # only its shared all-in budget accounts for compact research bytes.
    original_bytes = owner.report()["inserted_payload_bytes"]
    assert comparison_bytes > 0
    limited_dir = tmp_path / "limited"
    limited_dir.mkdir()
    limited, publication_owner, _, _ = publication(limited_dir, monkeypatch, payload_limit=original_bytes)
    assert publication_owner.report()["events"][0]["source_state"] == "captured"
    assert publication_owner.report()["inserted_payload_bytes"] == original_bytes
    assert not any(obj["kind"] == comparison.KIND for obj in objects(limited).values())


def test_legitimate_slow_original_is_unavailable_not_an_optional_adapter_crash(native):
    import hashlib
    import football_opponent_strength as strength
    from football_original import FootballOriginal
    from model_artifacts import canonical_bytes
    original, binding, receipts = material(native)
    packet = original.to_dict()
    packet["captured_at"] = binding["native_event"]["scheduled_start"]
    delayed = FootballOriginal(canonical_bytes(packet))
    binding["captured_at"] = packet["captured_at"]
    binding["original_logical_digest"] = hashlib.sha256(delayed._bytes).hexdigest()
    with pytest.raises(strength.ComparisonUnavailable, match="after-kickoff"):
        comparison.prepare_opponent_comparison(delayed, binding, receipts)


def test_slow_real_owner_publishes_original_without_optional_comparison(tmp_path, monkeypatch):
    import football_original
    path, owner, target, past = publication(tmp_path, monkeypatch, finalize=False)
    monkeypatch.setattr(football_original, "_capture_now", lambda: NOW + timedelta(hours=3))
    class LateClock:
        @staticmethod
        def now(tz=None):
            return NOW + timedelta(hours=3, seconds=1)
    monkeypatch.setattr("context_models.football_original_publication.datetime", LateClock)
    baseline = engine.fixture_market_probabilities(target, past)
    actual = engine.fixture_market_probabilities(target, past, **owner.model_kwargs(decision_at=NOW))
    assert actual == baseline
    assert owner.report()["events"][-1]["binding_ref"] is not None
    owner._budget.finish_optional_comparisons()
    assert not any(obj['kind'] == comparison.KIND for obj in objects(path).values())


def two_event_worker(tmp_path, monkeypatch, *, payload_limit=4_000_000, separate_batches=False,
                     finalize=True):
    from context_models.football_original_publication import FootballOriginalBudget, FootballOriginalPublication
    from context_sources.football_capture import _Capture
    import football_original
    path = tmp_path / "two-events.db"
    observer = _Capture(path, baseline_enabled=True)
    past = []
    for index in range(48):
        start = NOW - timedelta(days=48-index)
        raw = detail(1000+index, start, goals=(1+index%3, index%3))
        observer.record("fixtures", {"id": raw["fixture"]["id"]},
            {"response": [raw], "errors": [], "results": 1, "paging": {"current": 1, "total": 1}},
            observed_at=start+timedelta(hours=3), status=200)
        past.append(raw)
    targets = [detail(9000+i, NOW+timedelta(hours=2+i), terminal="NS") for i in range(2)]
    for target in targets:
        observer.record("fixtures", {"id": target["fixture"]["id"]},
            {"response": [target], "errors": [], "results": 1, "paging": {"current": 1, "total": 1}},
            observed_at=NOW-timedelta(minutes=30), status=200)
    class Clock:
        @staticmethod
        def now(tz=None):
            return NOW+timedelta(seconds=1)
    monkeypatch.setattr("context_models.football_original_publication.datetime", Clock)
    monkeypatch.setattr(football_original, "_capture_now", lambda: NOW)
    budget = FootballOriginalBudget(max_worker_payload_bytes=payload_limit,
        max_source_payload_bytes=4_000_000)
    owners = []
    for selected in ([targets] if not separate_batches else [[target] for target in targets]):
        owner = FootballOriginalPublication(path, observer,
            max_publication_payload_bytes=payload_limit, max_worker_payload_bytes=payload_limit,
            max_source_payload_bytes=4_000_000, shared_budget=budget)
        owner.freeze(tuple([*selected, *past]))
        owners.append(owner)
        for target in selected:
            baseline = engine.fixture_market_probabilities(target, past)
            actual = engine.fixture_market_probabilities(target, past, **owner.model_kwargs(decision_at=NOW))
            assert actual == baseline
    if finalize and hasattr(budget, "finish_optional_comparisons"):
        budget.finish_optional_comparisons()
    return path, budget, owners, targets, past


@pytest.mark.parametrize("separate_batches", [False, True])
def test_optional_comparisons_never_displace_later_originals_in_reserved_worker(
        tmp_path, monkeypatch, separate_batches):
    large_dir = tmp_path / "large"
    large_dir.mkdir()
    large, _, _, _, _ = two_event_worker(large_dir, monkeypatch, separate_batches=separate_batches)
    original_budget = sum(len(obj["bytes"]) for obj in objects(large).values() if obj["kind"] != comparison.KIND)
    limited_dir = tmp_path / "tight"
    limited_dir.mkdir()
    path, budget, owners, _, _ = two_event_worker(limited_dir, monkeypatch,
        payload_limit=original_budget, separate_batches=separate_batches)
    assert sum(owner.report()["published_count"] for owner in owners) == 2
    assert all(event["source_state"] == "captured" and event["binding_ref"] is not None
               for owner in owners for event in owner.report()["events"])
    assert budget.remaining_payload_bytes == 0
    assert not any(obj["kind"] == comparison.KIND for obj in objects(path).values())


def test_optional_comparisons_are_deferred_until_worker_is_finished(tmp_path, monkeypatch):
    path, budget, owners, _, _ = two_event_worker(tmp_path, monkeypatch,
        separate_batches=True, finalize=False)
    assert sum(owner.report()["published_count"] for owner in owners) == 2
    assert not any(obj["kind"] == comparison.KIND for obj in objects(path).values())
    budget.finish_optional_comparisons()
    assert sum(obj["kind"] == comparison.KIND for obj in objects(path).values()) == 2


def test_finished_worker_is_idempotent_and_cannot_accept_later_originals(tmp_path, monkeypatch):
    from context_models.football_original_publication import FootballOriginalPublication
    path, budget, owners, targets, past = two_event_worker(tmp_path, monkeypatch, separate_batches=True)
    before, reports, usage = objects(path), [owner.report() for owner in owners], budget.report()
    budget.finish_optional_comparisons()
    assert objects(path) == before and [owner.report() for owner in owners] == reports
    assert budget.report() == usage
    assert usage['inserted_payload_bytes'] == sum(len(obj['bytes']) for obj in before.values())
    assert sum(report['inserted_payload_bytes'] for report in reports) < usage['inserted_payload_bytes']
    with pytest.raises(ContextContractError, match='already finished'):
        engine.fixture_market_probabilities(targets[0], past, **owners[0].model_kwargs(decision_at=NOW))
    with pytest.raises(ContextContractError, match='already finished'):
        FootballOriginalPublication(path, None, max_publication_payload_bytes=4_000_000,
            max_worker_payload_bytes=4_000_000, max_source_payload_bytes=4_000_000, shared_budget=budget)
    assert objects(path) == before and budget.report() == usage


@pytest.mark.parametrize('hours, expected', [(2, 1), (4, 0)])
def test_deferred_comparison_uses_actual_final_clock_and_declines_at_kickoff(tmp_path, monkeypatch, hours, expected):
    path, budget, owners, _, _ = two_event_worker(tmp_path, monkeypatch, finalize=False)
    originals, before_reports = objects(path), [owner.report() for owner in owners]
    class Clock:
        @staticmethod
        def now(tz=None):
            return NOW+timedelta(hours=hours)
    monkeypatch.setattr('context_models.football_original_publication.datetime', Clock)
    budget.finish_optional_comparisons()
    after = objects(path)
    assert all(after[key] == value for key, value in originals.items())
    assert [owner.report() for owner in owners] == before_reports
    assert sum(obj['kind'] == comparison.KIND for obj in after.values()) == expected
    with sqlite3.connect(path) as connection:
        clocks = connection.execute('SELECT created_at FROM artifacts WHERE kind=?', (comparison.KIND,)).fetchall()
    from context_models.contracts import canonical_timestamp
    assert clocks == [(canonical_timestamp(NOW+timedelta(hours=hours)),)] * expected


def test_deferred_clock_reversal_is_rejected_without_spending_or_regaining_budget(tmp_path, monkeypatch):
    path, budget, owners, _, _ = two_event_worker(tmp_path, monkeypatch, finalize=False)
    before, usage = objects(path), budget.report()
    class Clock:
        @staticmethod
        def now(tz=None):
            return NOW-timedelta(seconds=1)
    monkeypatch.setattr('context_models.football_original_publication.datetime', Clock)
    with pytest.raises(ContextIntegrityError, match='precedes actual ORIGINAL'):
        budget.finish_optional_comparisons()
    assert objects(path) == before and budget.report() == usage
    budget.finish_optional_comparisons()
    assert objects(path) == before and budget.report() == usage
    assert budget._sealed


@pytest.mark.parametrize('change', ['binding', 'receipt', 'original', 'trigger_binding', 'trigger_receipt'])
def test_deferred_dependencies_are_rechecked_and_optional_failure_rolls_back(tmp_path, monkeypatch, change):
    path, budget, owners, _, _ = two_event_worker(tmp_path, monkeypatch, finalize=False)
    binding_ref = owners[0].report()['events'][0]['binding_ref']
    binding = objects(path)[binding_ref]['payload']
    with sqlite3.connect(path) as connection:
        if change == 'binding':
            connection.execute('UPDATE artifacts SET payload=? WHERE digest=?', (b'{}', binding_ref))
        elif change == 'receipt':
            connection.execute("UPDATE context_observations SET event_key='foreign' WHERE digest=?",
                (next(iter(binding['inspected_receipts'].values()))[0],))
        elif change == 'original':
            connection.execute('DELETE FROM artifacts WHERE digest=?', (binding['original_manifest_digest'],))
        elif change == 'trigger_binding':
            connection.execute("CREATE TRIGGER mutate_original AFTER INSERT ON artifacts WHEN NEW.kind='"+comparison.KIND+
                "' BEGIN UPDATE artifacts SET payload=x'7b7d' WHERE digest='"+binding_ref+"'; END")
        else:
            receipt = next(iter(binding['inspected_receipts'].values()))[0]
            connection.execute("CREATE TRIGGER mutate_source AFTER INSERT ON artifacts WHEN NEW.kind='"+comparison.KIND+
                "' BEGIN UPDATE context_observations SET event_key='foreign' WHERE digest='"+receipt+"'; END")
    before, reports, usage = objects(path), [owner.report() for owner in owners], budget.report()
    with sqlite3.connect(path) as connection:
        before_receipts = connection.execute('SELECT * FROM context_observations ORDER BY digest').fetchall()
    with pytest.raises((ContextContractError, ValueError, KeyError)):
        budget.finish_optional_comparisons()
    assert objects(path) == before and [owner.report() for owner in owners] == reports
    assert budget.report() == usage
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT * FROM context_observations ORDER BY digest').fetchall() == before_receipts
    assert not any(obj['kind'] == comparison.KIND for obj in objects(path).values())
    assert budget._sealed


def test_pending_optional_memory_and_count_do_not_multiply_worker_limit(native, monkeypatch, tmp_path):
    import context_models.football_original_publication as publication_owner
    from model_artifacts import prepare_artifact
    saved = next(obj for obj in objects(native[0]).values() if obj['kind'] == comparison.KIND)
    prepared = prepare_artifact(kind=comparison.KIND, payload=saved['payload'])
    size = len(prepared.payload_bytes)
    # Different database destinations distinguish queue keys without copying
    # histories or introducing another payload/source reservation.
    bounded = publication_owner.FootballOriginalBudget(max_worker_payload_bytes=size+size//2,
        max_source_payload_bytes=0)
    with bounded.lock:
        for index in range(10):
            bounded._defer_comparison(tmp_path/f'{index}.db', prepared,
                captured_at=saved['payload']['decision_at'], scheduled_start=NOW.isoformat())
    assert len(bounded._optional) == 1 and bounded._optional_bytes == size
    assert bounded.remaining_payload_bytes == size+size//2
    assert all(len(task) == 4 and task[1] is prepared for task in bounded._optional.values())
    monkeypatch.setattr(publication_owner, 'MAX_PENDING_OPPONENT_COMPARISONS', 1)
    counted = publication_owner.FootballOriginalBudget(max_worker_payload_bytes=size*10,
        max_source_payload_bytes=0)
    with counted.lock:
        for index in range(10):
            counted._defer_comparison(tmp_path/f'{index}.db', prepared,
                captured_at=saved['payload']['decision_at'], scheduled_start=NOW.isoformat())
    assert len(counted._optional) == 1 and counted._optional_bytes == size
    assert counted.remaining_payload_bytes == size*10


def test_finalizer_seals_a_source_freeze_waiting_for_the_shared_lock(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from context_models.football_original_publication import FootballOriginalBudget, FootballOriginalPublication
    arrived, resume = threading.Event(), threading.Event()
    class Gate:
        def __init__(self):
            self.actual = threading.Lock()
        def __enter__(self):
            if threading.current_thread() is not threading.main_thread():
                arrived.set()
                assert resume.wait(10), 'source-freeze test was not resumed'
            self.actual.acquire()
        def __exit__(self, *_):
            self.actual.release()
    class Capture:
        source_inserted_bytes = 0
        baseline_scope_records = {}
        baseline_refs = {}
        calls = 0
        def flush_baseline_receipts(self, scope, *, max_new_payload_bytes):
            self.calls += 1
            self.source_inserted_bytes += 1
            return {}
    budget = FootballOriginalBudget(max_worker_payload_bytes=4_000_000, max_source_payload_bytes=100)
    budget.lock = Gate()
    capture = Capture()
    owner = FootballOriginalPublication(tmp_path/'waiting-freeze.db', capture,
        max_publication_payload_bytes=4_000_000, max_worker_payload_bytes=4_000_000,
        max_source_payload_bytes=100, shared_budget=budget)
    with ThreadPoolExecutor(max_workers=1) as worker:
        pending = worker.submit(owner.freeze, ())
        try:
            assert arrived.wait(10), 'source-freeze did not reach its lock'
            budget.finish_optional_comparisons()
        finally:
            resume.set()
        with pytest.raises(ContextContractError, match='already finished'):
            pending.result(timeout=10)
    assert capture.calls == 0 and budget.remaining_source_bytes == 100
    assert budget.report()['source_inserted_payload_bytes'] == 0
