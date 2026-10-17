"""One additional runtime projection must preserve the owning v14 law."""
from copy import deepcopy
from dataclasses import asdict
import json
import math
import subprocess
import sys
from types import ModuleType

import pytest

import challenge_engine as engine
import football_joint_calibration as joint
from tests.test_football_original_capture import calibration, values


KEY = "TOTAL_RANGE_2_3"
PREVIOUS_CATALOG = "football-market-catalog:95-bounded-multigoal-v1"
CURRENT_CATALOG = "football-market-catalog:96-bounded-multigoal-v2"
PREVIOUS_REVISION = "6ff4d260a70365e11dc0c6caa7a8c56fe25b739a"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def test_two_to_three_is_one_additional_settleable_projection_not_a_new_fit_target():
    assert KEY in engine.MARKET_BY_KEY
    spec = engine.MARKET_BY_KEY[KEY]
    assert asdict(spec) == dict(key=KEY, market="Gesamttore", selection="2-3 Tore",
                               kind="total_range", side=None, threshold=None, low=2, high=3)
    assert len(engine.MARKET_SPECS) == len(engine.MARKET_BY_KEY) == 96
    assert len(engine.LEGACY_MARKET_SPECS) == len(engine.JOINT_FIT_MARKET_SPECS) == 90
    assert len(engine.GOAL_MARKET_SPECS) == 40
    assert len(engine.GOAL_PROJECTION_MARKET_SPECS) == 46
    assert KEY in engine.PROJECTION_ONLY_MARKET_KEYS
    assert not {"HOME_RANGE_2_3", "AWAY_RANGE_2_3"}.intersection(engine.MARKET_BY_KEY)
    assert engine.CHALLENGE_PREDICTION_VERSION == "challenge-engine:coherent-joint-calibration-v14"
    assert engine.CHALLENGE_MARKET_CATALOG_SIGNATURE == CURRENT_CATALOG


@pytest.mark.parametrize("score,want", [
    ((0, 0), False), ((1, 0), False), ((0, 1), False),
    ((2, 0), True), ((1, 1), True), ((0, 2), True),
    ((3, 0), True), ((2, 1), True), ((1, 2), True), ((0, 3), True),
    ((4, 0), False), ((3, 1), False), ((2, 2), False), ((1, 3), False),
    ((0, 4), False), ((2, 3), False), ((3, 2), False),
])
def test_two_to_three_settlement_uses_inclusive_match_total_not_either_team(score, want):
    assert KEY in engine.MARKET_BY_KEY
    assert engine.market_outcome(engine.MARKET_BY_KEY[KEY], *score) is want


def test_two_to_three_probability_is_hand_summed_joint_mass():
    assert KEY in engine.MARKET_BY_KEY
    raw = {(0, 0): .1, (1, 0): .15, (0, 2): .2, (2, 1): .25, (2, 2): .1, (5, 0): .2}
    assert engine.market_probability(raw, engine.MARKET_BY_KEY[KEY]) == pytest.approx(.45)


@pytest.mark.parametrize("law", [joint.LEGACY_LAW_VERSION, joint.LAW_VERSION])
def test_two_to_three_calibration_curve_never_refits_either_immutable_joint_law(law):
    assert KEY in engine.MARKET_BY_KEY
    raw = {(0, 0): .1, (1, 0): .3, (1, 1): .4, (2, 2): .2}
    curves = {"RESULT_HOME": lambda p: p + .1}
    before, diagnostics = joint.calibrate_joint_distribution(
        raw, engine.GOAL_MARKET_SPECS, curves, law_version=law)
    after, expanded_diagnostics = joint.calibrate_joint_distribution(
        raw, engine.GOAL_PROJECTION_MARKET_SPECS,
        {**curves, KEY: lambda p: .99}, law_version=law)
    assert after == before
    assert expanded_diagnostics == diagnostics
    assert KEY not in expanded_diagnostics["targets"]


def test_two_to_three_preserves_all_previous_95_probabilities_settlements_and_capture(monkeypatch):
    assert KEY in engine.MARKET_BY_KEY
    fixture, history = values()
    curves = calibration()
    originals = []
    current = engine.fixture_market_probabilities(
        fixture, history, curves, original_capture=originals.append)
    # Execute the actual immutable 95-market predecessor in this numerical
    # runtime. Its 90-market original and calibrated q are still the owners.
    sources = {name: subprocess.check_output(["git", "show", f"{PREVIOUS_REVISION}:{name}.py"])
               for name in ("challenge_engine", "football_joint_calibration")}
    with monkeypatch.context() as patch:
        modules = {name: ModuleType(name) for name in sources}
        for name, module in modules.items():
            module.__file__ = sys.modules[name].__file__
            patch.setitem(sys.modules, name, module)
        for name, module in modules.items():
            exec(compile(sources[name], f"<git:{PREVIOUS_REVISION}:{name}.py>", "exec"), module.__dict__)
        previous = modules["challenge_engine"]
        assert previous.CHALLENGE_MARKET_CATALOG_SIGNATURE == PREVIOUS_CATALOG
        assert len(previous.MARKET_SPECS) == 95
        old_curves = {spec.key: previous.MarketCalibration(curves[spec.key].points, curves[spec.key].samples)
                      for spec in previous.MARKET_SPECS if spec.key in curves}
        baseline = previous.fixture_market_probabilities(fixture, history, old_curves)
        old_specs = tuple(previous.MARKET_SPECS)
        old_outcomes = {spec.key: [previous.market_outcome(spec, h, a)
                                  for h in range(9) for a in range(9)] for spec in old_specs}
    assert canonical({key: triplet for key, triplet in current["probabilities"].items() if key != KEY}) == canonical(baseline["probabilities"])
    assert canonical({key: triplet for key, triplet in current["raw_probabilities"].items() if key != KEY}) == canonical(baseline["raw_probabilities"])
    assert canonical(current["distribution_capture"]) == canonical(baseline["distribution_capture"])
    assert [asdict(spec) for spec in engine.MARKET_SPECS if spec.key != KEY] == [asdict(spec) for spec in old_specs]
    assert {spec.key: [engine.market_outcome(spec, h, a) for h in range(9) for a in range(9)]
            for spec in engine.MARKET_SPECS if spec.key != KEY} == old_outcomes
    packet = originals[0].to_dict()
    assert len(packet["probabilities"]) == len(packet["market_specs"]) == 90
    assert KEY not in packet["probabilities"]
    for index, variant in enumerate(("active", "season", "form")):
        cells = current["distribution_capture"]["families"]["goals"][variant]["effective_cells"]
        expected = math.fsum(p for h, a, p in cells if h + a in (2, 3))
        actual = current["probabilities"][KEY][index]
        assert actual == pytest.approx(expected, abs=1e-14)
        assert actual <= current["probabilities"]["TOTAL_RANGE_1_3"][index]
        assert actual <= current["probabilities"]["TOTAL_RANGE_2_4"][index]


def test_two_to_three_walk_forward_owns_its_outcomes_and_has_no_future_label_leak():
    assert KEY in engine.MARKET_BY_KEY
    from tests.test_calibration import league_history
    rows = league_history(cycles=12)
    records = engine._walk_forward_market_records(rows)
    assert len(records) == 96
    record = records[KEY]
    assert record["outcomes"]
    assert record["outcomes"] != records["TOTAL_RANGE_1_3"]["outcomes"]
    assert record["outcomes"] != records["TOTAL_RANGE_2_4"]["outcomes"]
    changed = deepcopy(rows)
    changed[-1]["goals"] = {"home": 0, "away": 0}
    changed_records = engine._walk_forward_market_records(changed)
    assert record["outcomes"][-1] == 1
    assert changed_records[KEY]["outcomes"][-1] == 0
    assert changed_records[KEY]["probabilities"] == record["probabilities"]
    assert changed_records[KEY]["baselines"] == record["baselines"]
    metrics = engine._validation_metrics_from_records(records)
    assert metrics[KEY].observations == len(record["outcomes"])
    assert metrics[KEY].tested_hypotheses == 96


def test_two_to_three_candidate_does_not_borrow_previous_range_approval():
    assert KEY in engine.MARKET_BY_KEY
    fixture, history = values()
    old_metric = engine.ValidationMetrics(observations=300, brier_score=.1,
        baseline_brier_score=.2, relative_improvement=.5, expected_calibration_error=.01, passed=True)
    candidates = engine.build_fixture_candidates(fixture, history,
        {"TOTAL_RANGE_1_3": old_metric, "TOTAL_RANGE_2_4": old_metric},
        candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER)
    candidate = next(row for row in candidates if row.market_key == KEY)
    assert candidate.validation is None
    assert candidate.selection == "2-3 Tore"
    assert not engine.candidate_is_wettfinder_release_credible(candidate)


def test_old_95_validation_cache_is_retained_but_cannot_supply_new_96_coverage(tmp_path):
    from challenge_model_cache import load_model_artifact, save_model_artifact
    assert KEY in engine.MARKET_BY_KEY
    path = tmp_path / "range-2-3-cache.db"
    metric = engine.ValidationMetrics(300, .1, .2, .5, .01, True)
    previous = {spec.key: metric for spec in engine.MARKET_SPECS if spec.key != KEY}
    assert len(previous) == 95
    save_model_artifact(engine.CHALLENGE_PREDICTION_VERSION, 39, 2026, [], previous, {},
                        db_path=path, market_catalog_signature=PREVIOUS_CATALOG)
    assert load_model_artifact(engine.CHALLENGE_PREDICTION_VERSION, 39, 2026, [],
        db_path=path, market_catalog_signature=engine.CHALLENGE_MARKET_CATALOG_SIGNATURE,
        expected_market_keys=tuple(engine.MARKET_BY_KEY)) is None
    assert load_model_artifact(engine.CHALLENGE_PREDICTION_VERSION, 39, 2026, [],
        db_path=path, market_catalog_signature=PREVIOUS_CATALOG,
        expected_market_keys=tuple(previous)) == (previous, {})


def test_two_to_three_range_cannot_inherit_owning_joint_training_admission():
    from context_models.contracts import ContextContractError
    from context_models.training_contracts import validate_family_config
    from tests.test_multigoal_original_compatibility import joint_config
    assert KEY in engine.MARKET_BY_KEY
    with pytest.raises(ContextContractError, match="owning outcome/distribution catalog"):
        validate_family_config(joint_config(KEY))
