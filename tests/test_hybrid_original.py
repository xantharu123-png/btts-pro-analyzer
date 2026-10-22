"""ORIGINAL capture, storage, replay and identity for the coherent hybrid basis.

Plan: docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md. The legacy
capture must stay byte-identical; the hybrid packet names its basis, its fit
window and its own pins, replays exactly and is refused as a training case.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

import challenge_engine as engine
import football_original
from context_models import football_original_storage as storage
from context_models.contracts import ContextContractError, ContextIntegrityError
from context_models.football_joint_comparison import compare_captured_joint
from context_models.football_joint_effect import replay_joint_calculation
from context_models.football_original_publication import _code_identity_for_basis, executed_code_identity
from context_models.replay import ReplayUnavailable
from football_original import FootballOriginal, original_goal_basis
from tests.test_football_base_provenance import history, target
from tests.test_football_original_capture import calibration

NOW = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
HYBRID = engine.GOAL_MODEL_SHADOW_CANDIDATE


def capture(monkeypatch, *, goal_model=HYBRID, curves=None, at=NOW, law=None):
    monkeypatch.setattr(football_original, "_capture_now", lambda: at)
    saved = []
    model = engine.fixture_market_probabilities(
        target(), history(), calibration() if curves is None else curves,
        original_capture=saved.append, goal_model=goal_model,
        **({} if law is None else {"_joint_law_version": law}))
    assert model is not None and len(saved) == 1
    return saved[0]


def test_hybrid_capture_names_basis_pins_and_fit_window(monkeypatch):
    original = capture(monkeypatch)
    packet = original.to_dict()
    assert packet["schema"] == 2
    assert packet["prediction_version"] == engine.prediction_version_for_goal_model(HYBRID)
    assert packet["model_contract_signature"] == engine.model_contract_signature_for_goal_model(HYBRID)
    assert packet["prediction_version"] != engine.CHALLENGE_PREDICTION_VERSION
    goal = packet["goal_model"]
    assert original_goal_basis(packet) == HYBRID == goal["goal_model"]
    assert goal["dixon_coles"]["version"].startswith("dixon-coles-mle")
    assert len(goal["legacy_lambdas"]) == 2 and all(value > 0 for value in goal["legacy_lambdas"])
    weights = packet["goal_provenance"]["reference_weights"]
    assert weights["kind"] == "football-goals-hybrid-dc-v1"
    assert set(weights["heads"]) == {"home", "away"}
    window = weights["dixon_coles"]["window"]
    assert len(window) == goal["dixon_coles"]["matches"] == len(history())
    declared = {row["ref"] for row in packet["goal_provenance"]["history_refs"]}
    assert {row["ref"] for row in window} <= declared
    assert all(0 < row["weight"] <= 1 for row in window)
    assert weights["dixon_coles"]["legacy_lambdas"] == goal["legacy_lambdas"]
    assert weights["dixon_coles"]["effective_rho"] == goal["rho"]
    assert packet["limitations"] == []


def test_legacy_capture_bytes_carry_no_basis_fields(monkeypatch):
    original = capture(monkeypatch, goal_model=engine.GOAL_MODEL_LEGACY)
    packet = original.to_dict()
    assert original_goal_basis(packet) == engine.GOAL_MODEL_LEGACY
    assert not {"goal_model", "rho", "fitted_rho", "dixon_coles", "legacy_lambdas"} & set(packet["goal_model"])
    assert packet["prediction_version"] == engine.CHALLENGE_PREDICTION_VERSION
    assert packet["goal_provenance"]["reference_weights"]["kind"] == "football-goals-v1"
    assert compare_captured_joint(original)["law_version"]


def test_hybrid_capture_is_bound_to_the_active_joint_law(monkeypatch):
    from football_joint_calibration import LAW_VERSION
    with pytest.raises(ValueError):
        capture(monkeypatch, law=LAW_VERSION)


def test_hybrid_original_round_trips_through_storage_and_replays_exactly(monkeypatch, tmp_path):
    original = capture(monkeypatch)
    plan = storage.prepare_original(original)
    legacy_plan = storage.prepare_original(capture(monkeypatch, goal_model=engine.GOAL_MODEL_LEGACY))
    # The fit window is one more fixed array (chunk) than the legacy layout.
    assert len(plan.artifacts) == len(legacy_plan.artifacts) + 1
    result = storage.store_original(tmp_path / "o.db", original, created_at=NOW + timedelta(minutes=1),
                                    max_new_payload_bytes=plan.payload_bytes)
    loaded = storage.load_original(tmp_path / "o.db", result.manifest_digest)
    assert loaded._bytes == original._bytes
    comparison = replay_joint_calculation(loaded)
    assert comparison["original_logical_digest"] == hashlib.sha256(original._bytes).hexdigest()
    assert set(comparison["raw_probabilities"]) >= {"RESULT_HOME", "TOTAL_OVER_2_5"}


def test_tampered_hybrid_rho_or_basis_is_not_replayable(monkeypatch):
    packet = capture(monkeypatch).to_dict()
    tampered = json.loads(json.dumps(packet))
    tampered["goal_model"]["rho"] = packet["goal_model"]["rho"] + 0.01
    with pytest.raises(ContextIntegrityError):
        replay_joint_calculation(FootballOriginal(json.dumps(
            tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")))
    relabeled = json.loads(json.dumps(packet))
    relabeled["goal_model"]["goal_model"] = "dixon_coles"
    with pytest.raises((ContextContractError, ContextIntegrityError, ValueError)):
        compare_captured_joint(FootballOriginal(json.dumps(
            relabeled, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")))


def test_hybrid_window_outside_declared_history_fails_closed(monkeypatch):
    from context_models.contracts import validate_reference_weights
    packet = capture(monkeypatch).to_dict()
    weights = json.loads(json.dumps(packet["goal_provenance"]["reference_weights"]))
    refs = packet["goal_provenance"]["history_refs"]
    weights["dixon_coles"]["window"][0]["ref"] = "0" * 64
    with pytest.raises(ContextContractError):
        validate_reference_weights(weights, refs, family="football:goals:90min")
    weights = json.loads(json.dumps(packet["goal_provenance"]["reference_weights"]))
    weights["dixon_coles"]["window"] = []
    with pytest.raises(ContextContractError):
        validate_reference_weights(weights, refs, family="football:goals:90min")


def test_executed_code_declares_the_basis_pins_and_publication_resolves_them(monkeypatch):
    code = executed_code_identity()
    assert code["prediction_version"] == engine.CHALLENGE_PREDICTION_VERSION
    assert code["goal_basis_identities"][HYBRID] == {
        "prediction_version": engine.prediction_version_for_goal_model(HYBRID),
        "model_contract_signature": engine.model_contract_signature_for_goal_model(HYBRID),
    }
    hybrid_packet = capture(monkeypatch).to_dict()
    identity = _code_identity_for_basis(code, hybrid_packet)
    assert all(identity[name] == hybrid_packet[name]
               for name in ("prediction_version", "model_contract_signature"))
    legacy_packet = capture(monkeypatch, goal_model=engine.GOAL_MODEL_LEGACY).to_dict()
    assert _code_identity_for_basis(code, legacy_packet) is code
    unknown = json.loads(json.dumps(hybrid_packet))
    unknown["goal_model"]["goal_model"] = "not-a-basis"
    assert _code_identity_for_basis(code, unknown) is None


def test_hybrid_original_is_not_a_training_or_opponent_case(monkeypatch):
    from context_models.football_training import joint_base
    from football_opponent_publication import prepare_opponent_comparison
    from football_opponent_strength import ComparisonUnavailable
    original = capture(monkeypatch)
    with pytest.raises(ReplayUnavailable, match="original_basis_not_trainable"):
        joint_base(original, {})
    with pytest.raises(ComparisonUnavailable):
        prepare_opponent_comparison(original, {}, ())


def test_cold_start_fit_is_deterministic_and_independent_of_warm_history():
    from football_dixon_coles import _cold_fit, fit_for_fixture
    rows, current = history(), target()
    _cold_fit.cache_clear()
    first = fit_for_fixture(current, rows, half_life_days=365.0, cold_start=True)
    _cold_fit.cache_clear()
    second = fit_for_fixture(current, rows, half_life_days=365.0, cold_start=True)
    assert first == second
    warm = fit_for_fixture(current, rows, half_life_days=365.0)
    assert warm.matches == first.matches and abs(warm.rho - first.rho) < 1e-4
