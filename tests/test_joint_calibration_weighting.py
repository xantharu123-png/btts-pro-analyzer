"""Per-market projection weight and immutable previous-law compatibility."""
import pytest

import challenge_engine as engine
import football_joint_calibration as joint


def test_full_goal_catalog_keeps_each_calibration_target_unit_weight():
    # Between 0:0 and 1:0, exactly these eleven catalog events change.
    # A coherent target shifts the home-win atom from .4 to .5. With unit
    # weight per event and two prior atoms, the optimum is (11*.5+2*.4)/13.
    increasing = {
        "RESULT_HOME", "DC_12", "TOTAL_OVER_0_5", "HOME_OVER_0_5",
        "HOME_RANGE_1_3", "MIXED_HOME_OR_OVER_2_5",
    }
    decreasing = {
        "RESULT_DRAW", "DC_X2", "TOTAL_UNDER_0_5", "HOME_UNDER_0_5",
        "RESULT_TOTAL_X2_UNDER_3_5",
    }
    curves = {key: lambda p: p + .1 for key in increasing}
    curves.update({key: lambda p: p - .1 for key in decreasing})
    fitted, diagnostics = joint.calibrate_joint_distribution(
        {(0, 0): .6, (1, 0): .4}, engine.GOAL_MARKET_SPECS, curves,
        law_version=joint.LAW_VERSION,
    )
    assert fitted[1, 0] == pytest.approx(6.3 / 13, abs=1e-8)
    assert fitted[0, 0] == pytest.approx(6.7 / 13, abs=1e-8)
    assert diagnostics["success"] is True


def test_legacy_joint_projection_reproduces_previous_atom_weights():
    raw = {(0, 0): .6, (1, 0): .4}
    curves = {"RESULT_HOME": lambda p: p + .1}
    fitted, diagnostic = joint.calibrate_joint_distribution(
        raw, engine.GOAL_MARKET_SPECS, curves,
        law_version="football-joint-settlement-projection-v1",
    )
    # There are eleven nonconstant event targets in this two-atom law.
    # Only the home-win target moves. Previous mean objective /40 gives
    # (11*.4 + .1 + 80*.4) /91 = 36.5/91.
    assert fitted[1, 0] == pytest.approx(36.5 / 91, abs=1e-8)
    assert diagnostic["law_version"] == "football-joint-settlement-projection-v1"


def test_unknown_projection_version_is_not_relabelled_current():
    with pytest.raises(ValueError, match="law"):
        joint.calibrate_joint_distribution(
            {(0, 0): 1.0}, engine.GOAL_MARKET_SPECS, {}, law_version="invented-law",
        )


def test_default_projection_does_not_activate_unqualified_candidate():
    fitted, diagnostic = joint.calibrate_joint_distribution(
        {(0, 0): .6, (1, 0): .4}, engine.GOAL_MARKET_SPECS,
        {"RESULT_HOME": lambda p: p + .1},
    )
    assert fitted[1, 0] == pytest.approx(36.5 / 91, abs=1e-8)
    assert diagnostic["law_version"] == "football-joint-settlement-projection-v1"


def test_both_captured_laws_roundtrip_and_replay_without_rewriting(monkeypatch, tmp_path):
    from context_models.football_original_storage import load_original, store_original
    from context_models.football_joint_effect import replay_joint_calculation
    from tests.test_football_original_capture import calibration, values
    from tests.test_football_original_storage import NOW
    from football_original import FootballOriginal
    import model_artifacts

    fixture, history = values()
    monkeypatch.setattr("football_original._capture_now", lambda: NOW)
    versions = ["football-joint-settlement-projection-v1", joint.LAW_VERSION]
    snapshots = []
    for version in versions:
        originals = []
        engine.fixture_market_probabilities(
            fixture, history, calibration(), original_capture=originals.append,
            _joint_law_version=version,
        )
        original = originals[0]
        snapshots.append(original)
        stored = store_original(tmp_path / "both-laws.db", original, created_at=NOW,
                                max_new_payload_bytes=4_000_000)
        restored = load_original(tmp_path / "both-laws.db", stored.manifest_digest)
        assert restored._bytes == original._bytes
        assert replay_joint_calculation(restored)["law_version"] == version
    assert snapshots[0].to_dict()["prediction_version"] != snapshots[1].to_dict()["prediction_version"]
    assert snapshots[0].to_dict()["probabilities"] != snapshots[1].to_dict()["probabilities"]

    # The two known signatures may not be mixed to relabel previous outputs.
    packet = snapshots[0].to_dict()
    packet["prediction_version"] = snapshots[1].to_dict()["prediction_version"]
    with pytest.raises(model_artifacts.ArtifactIntegrityError):
        store_original(tmp_path / "both-laws.db", FootballOriginal(model_artifacts.canonical_bytes(packet)),
                       created_at=NOW, max_new_payload_bytes=4_000_000)
