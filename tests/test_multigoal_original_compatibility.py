"""New range projections must not redefine an owning historical/context law."""
from copy import deepcopy
from dataclasses import asdict

import pytest

import challenge_engine as engine
from context_models.contracts import ContextContractError, ContextIntegrityError
from football_original import FootballOriginal
from model_artifacts import canonical_bytes
from tests.test_football_original_capture import calibration, values
from tests.test_football_original_storage import NOW


NEW_RANGES = {
    "TOTAL_RANGE_1_3", "TOTAL_RANGE_1_4", "TOTAL_RANGE_2_4",
    "HOME_RANGE_1_4", "AWAY_RANGE_1_4",
}


def legacy_original(monkeypatch):
    """Execute the real model with its historical catalog, before expansion."""
    fixture, history = values()
    originals = []
    with monkeypatch.context() as patch:
        patch.setattr(engine, "MARKET_SPECS", engine.JOINT_FIT_MARKET_SPECS)
        patch.setattr(engine, "GOAL_MARKET_SPECS", tuple(
            spec for spec in engine.JOINT_FIT_MARKET_SPECS
            if spec.kind not in engine.COUNT_MARKET_KINDS))
        patch.setattr("football_original._capture_now", lambda: NOW)
        engine.fixture_market_probabilities(
            fixture, history, calibration(), original_capture=originals.append)
    return originals[0]


def joint_config(target):
    return dict(
        schema=1, sport="football", family="football:goals:90min",
        feature_version="football-native-context-v1",
        feature_names=["roster.home.venue_attack.goals.api-football:player:1"],
        population=dict(sport="football", competitions=["39"], formats=["90min"],
                        tours=[None], surfaces=[None], indoor=[None]),
        coverage=dict(version="football-native-context-v1.coverage", case="source-bound"),
        model_variant="football-joint-log-tilt-v1",
        base_versions=["football-goals-captured-joint-v1"],
        head_links={"home": "log_joint_tilt", "away": "log_joint_tilt"},
        reference_version="football-context-reference-v2", preprocessing_artifacts={},
        groups={"roster": ["roster.home.venue_attack.goals.api-football:player:1"]},
        joint_calibration={"kind": "identity"}, target_markets=[target],
        outcome_contract="football-regulation-ft-v1",
        train_end="2026-09-20T00:00:00.000000Z",
        tune_end="2026-09-22T00:00:00.000000Z", alpha_grid=[.01, .1, 1., 10., 100.])


def test_historical_catalog_still_compares_after_runtime_expansion(monkeypatch):
    # Reading the global expanded registry instead of the owning fit catalog
    # must not invalidate a genuine previously captured calculation.
    from context_models.football_joint_comparison import compare_captured_joint
    original = legacy_original(monkeypatch)
    assert len(original.to_dict()["market_specs"]) == 90
    comparison = compare_captured_joint(original)
    assert comparison["probabilities"] == original.to_dict()["probabilities"]
    assert not NEW_RANGES.intersection(comparison["probabilities"])


@pytest.mark.parametrize("target", sorted(NEW_RANGES))
def test_runtime_range_does_not_inherit_existing_joint_training_admission(target):
    # An expanded runtime registry is not an approved context/training catalog.
    from context_models.training_contracts import validate_family_config
    assert target in engine.MARKET_BY_KEY
    with pytest.raises(ContextContractError, match="owning outcome/distribution catalog"):
        validate_family_config(joint_config(target))


def test_existing_range_retains_joint_training_admission():
    from context_models.training_contracts import validate_family_config
    config = joint_config("HOME_RANGE_1_3")
    assert validate_family_config(config) == config


@pytest.mark.parametrize("schema", [1, 2])
def test_historical_original_roundtrip_is_byte_preserving(monkeypatch, tmp_path, schema):
    from context_models.football_original_storage import load_original, store_original
    original = legacy_original(monkeypatch)
    if schema == 1:
        packet = original.to_dict()
        packet.update(schema=1, kind="football-original-market-calculation-v1")
        packet.pop("distribution_capture")
        original = FootballOriginal(canonical_bytes(packet))
    stored = store_original(tmp_path / "original.db", original, created_at=NOW,
                            max_new_payload_bytes=4_000_000)
    restored = load_original(tmp_path / "original.db", stored.manifest_digest)
    assert restored._bytes == original._bytes
    assert len(restored.to_dict()["probabilities"]) == 90


def test_historical_joint_replay_remains_exact(monkeypatch):
    from context_models.football_joint_effect import replay_joint_calculation
    original = legacy_original(monkeypatch)
    assert replay_joint_calculation(original)["probabilities"] == original.to_dict()["probabilities"]


@pytest.mark.parametrize("mutation", ["triplet", "catalog", "targets"])
def test_projected_range_cannot_be_forged_into_legacy_capture(monkeypatch, mutation):
    from context_models.football_joint_comparison import compare_captured_joint
    packet = legacy_original(monkeypatch).to_dict()
    key = "HOME_RANGE_1_4"
    if mutation == "triplet":
        packet["probabilities"][key] = [.5, .5, .5]
        packet["raw_probabilities"][key] = [.5, .5, .5]
    elif mutation == "catalog":
        packet["market_specs"].append(asdict(engine.MARKET_BY_KEY[key]))
    else:
        packet["distribution_capture"]["families"]["goals"]["active"]["diagnostics"]["targets"][key] = .5
    with pytest.raises(ContextIntegrityError):
        compare_captured_joint(FootballOriginal(canonical_bytes(packet)))


def test_fresh_runtime_projects_ranges_without_expanding_owning_original(monkeypatch):
    fixture, history = values()
    originals = []
    monkeypatch.setattr("football_original._capture_now", lambda: NOW)
    model = engine.fixture_market_probabilities(
        fixture, history, calibration(), original_capture=originals.append)
    packet = originals[0].to_dict()
    assert len(model["probabilities"]) == 95
    assert NEW_RANGES <= set(model["probabilities"])
    for field in ("probabilities", "raw_probabilities", "calibration_recipes"):
        assert len(packet[field]) == 90
        assert not NEW_RANGES.intersection(packet[field])
    assert len(packet["market_specs"]) == 90
    assert packet["prediction_version"] == "challenge-engine:coherent-joint-calibration-v14"


def test_native_reconstruction_keeps_legacy_original_and_joint_baseline(monkeypatch, tmp_path):
    # This real publication->native receipt reconstruction->case admission path
    # catches whole-map drift, not just detached comparison compatibility.
    from tests.test_football_joint_training import source_case
    from context_models.training_cases import assemble_training_cases
    _, case, config = source_case(tmp_path, monkeypatch)
    before = deepcopy(case)
    result = assemble_training_cases((case,), config)
    assert result["canonical_events"] == 1
    assert not result["excluded"]
    assert len(result["rows"]) == 2
    assert case == before
    assert not NEW_RANGES.intersection(case["case"]["payload"]["base"]["markets"])
