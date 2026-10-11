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


def publication(tmp_path, monkeypatch, *, count=48, payload_limit=4_000_000):
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


def test_repeated_identical_original_does_not_duplicate_or_refit_per_market(native, monkeypatch):
    path, owner, target, past = native
    before = objects(path)
    budget = owner.remaining_payload_bytes
    import football_opponent_strength as strength
    fitted = strength._fit.cache_info().hits
    engine.fixture_market_probabilities(target, past, **owner.model_kwargs(decision_at=NOW))
    assert owner.remaining_payload_bytes == budget
    assert objects(path) == before
    assert strength._fit.cache_info().hits > fitted


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
    original_bytes = owner.report()["inserted_payload_bytes"] - comparison_bytes
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


def test_slow_real_owner_publishes_original_without_optional_comparison(native, monkeypatch):
    import football_original
    path, owner, target, past = native
    previous = {obj["payload"]["original_binding_ref"] for obj in objects(path).values()
                if obj["kind"] == comparison.KIND}
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
    assert owner.report()["events"][-1]["binding_ref"] not in previous
    assert {obj["payload"]["original_binding_ref"] for obj in objects(path).values()
            if obj["kind"] == comparison.KIND} == previous
