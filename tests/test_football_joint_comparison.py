"""Synthetic, read-only settlement checks; never source or quality approval."""
import hashlib

import pytest

import challenge_engine as engine
from context_models.contracts import ContextContractError, ContextIntegrityError
from context_models.football_joint_comparison import COMPARISON_VERSION, compare_captured_joint
from context_models.football_original_storage import MAX_ORIGINAL_BYTES, load_original, store_original
from football_original import FootballOriginal
from model_artifacts import ArtifactIntegrityError, canonical_bytes
from tests.test_football_original_capture import calibration, values
from tests.test_football_original_storage import NOW, capture


@pytest.mark.parametrize("curves", [None, calibration()])
def test_stored_v2_exactly_compares_captured_joint_markets_and_means(monkeypatch, tmp_path, curves):
    current, rows = values()
    original = capture(monkeypatch, curves=curves, current=current, rows=rows)
    result = store_original(tmp_path / "original.db", original, created_at=NOW,
                            max_new_payload_bytes=4_000_000)
    restored = load_original(tmp_path / "original.db", result.manifest_digest)
    comparison = compare_captured_joint(restored)
    packet = original.to_dict()
    assert comparison["version"] == COMPARISON_VERSION
    assert comparison["scope"] == "captured-settlement-only"
    assert comparison["original_logical_digest"] == hashlib.sha256(original._bytes).hexdigest()
    assert comparison["raw_probabilities"] == packet["raw_probabilities"]
    assert comparison["probabilities"] == packet["probabilities"]
    for family, model in (("goals", packet["goal_model"]), *packet["count_models"].items()):
        for variant in ("active", "season", "form"):
            key = variant + ("_lambdas" if family == "goals" else "_counts")
            assert comparison["effective_means"][family][variant] == model[key]
    assert set(comparison) == {"version", "scope", "original_logical_digest", "law_version",
                               "raw_probabilities", "probabilities", "delta_pp", "effective_means"}


def test_comparison_does_not_recalculate_model_or_joint_projection(monkeypatch):
    original = capture(monkeypatch, curves=calibration())
    def forbidden(*args, **kwargs):
        raise AssertionError("comparison must not re-run a model or solver")
    monkeypatch.setattr(engine, "_fixture_model", forbidden)
    import football_joint_calibration as joint
    monkeypatch.setattr(joint, "calibrate_joint_distribution", forbidden)
    assert compare_captured_joint(original)["scope"] == "captured-settlement-only"


@pytest.mark.parametrize("family", ["goals", "corners", "yellow"])
def test_comparison_rejects_raw_parameters_that_do_not_generate_the_cells(monkeypatch, family):
    current, rows = values()
    packet = capture(monkeypatch, current=current, rows=rows).to_dict()
    packet["distribution_capture"]["families"][family]["active"]["raw_means"][0] += .01
    with pytest.raises(ContextIntegrityError, match="raw cells/means"):
        compare_captured_joint(FootballOriginal(canonical_bytes(packet)))


@pytest.mark.parametrize("mutation", ["published-market", "effective-cell", "raw-cell",
                                      "catalog", "target-keys", "fallback", "cell-order",
                                      "malformed-triplet", "altered-means"])
def test_comparison_rejects_inconsistent_v2_capture(monkeypatch, mutation):
    packet = capture(monkeypatch, curves=calibration()).to_dict()
    record = packet["distribution_capture"]["families"]["goals"]["active"]
    if mutation == "published-market":
        packet["probabilities"]["RESULT_HOME"][0] += .01
    elif mutation in {"effective-cell", "raw-cell"}:
        cells = record["effective_cells" if mutation == "effective-cell" else "raw_cells"]
        ranked = sorted(range(len(cells)), key=lambda index: cells[index][2], reverse=True)
        cells[ranked[0]][2] += .0001
        cells[ranked[1]][2] -= .0001
    elif mutation == "catalog":
        packet["market_specs"][0]["selection"] = "different"
    elif mutation == "target-keys":
        record["diagnostics"]["targets"].pop("RESULT_HOME")
    elif mutation == "fallback":
        record["diagnostics"]["status"] = "raw-fallback"
        record["diagnostics"]["success"] = False
    elif mutation == "cell-order":
        record["effective_cells"][:2] = reversed(record["effective_cells"][:2])
    elif mutation == "malformed-triplet":
        packet["probabilities"]["RESULT_HOME"] = [True, .2, .3]
    elif mutation == "altered-means":
        packet["goal_model"]["active_lambdas"][0] += .01
    with pytest.raises(ContextIntegrityError):
        compare_captured_joint(FootballOriginal(canonical_bytes(packet)))


def test_v1_and_unversioned_laws_cannot_enter_comparison(monkeypatch):
    packet = capture(monkeypatch).to_dict()
    packet["schema"] = 1
    packet["kind"] = "football-original-market-calculation-v1"
    packet.pop("distribution_capture")
    with pytest.raises(ContextContractError, match="v2"):
        compare_captured_joint(FootballOriginal(canonical_bytes(packet)))
    packet = capture(monkeypatch).to_dict()
    packet["prediction_version"] = "old-or-unknown"
    with pytest.raises(ContextContractError, match="matching installed law"):
        compare_captured_joint(FootballOriginal(canonical_bytes(packet)))


def test_comparison_rejects_noncanonical_original_bytes(monkeypatch):
    raw = capture(monkeypatch)._bytes
    assert raw.startswith(b"{")
    with pytest.raises(ArtifactIntegrityError, match="canonical"):
        compare_captured_joint(FootballOriginal(raw.replace(b'"schema":2', b'"schema": 2', 1)))


def test_comparison_keeps_original_size_bound_before_decoding():
    with pytest.raises(ContextContractError, match="byte bound"):
        compare_captured_joint(FootballOriginal(b" " * (MAX_ORIGINAL_BYTES + 1)))
