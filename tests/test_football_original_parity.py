"""Frozen real-parent default and conservative calibration law comparisons."""
import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError
import math
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest

import challenge_engine as engine
from tests.test_football_original_capture import canonical, values

BASE = "bb297bbd34ca80eb83129e87cf1559cc44ae20df"
ROOT = Path(__file__).resolve().parents[1]


def old_blob(path):
    return subprocess.run(["git", "show", BASE + ":" + path], cwd=ROOT,
                          check=True, capture_output=True).stdout


def old_engine():
    name = "_p5a_frozen_challenge_engine"
    if name not in sys.modules:
        module = ModuleType(name)
        sys.modules[name] = module
        exec(compile(old_blob("challenge_engine.py"), BASE + ":challenge_engine.py", "exec"), module.__dict__)
    return sys.modules[name]


def actual_old_conservative_factory():
    # Execute the exact original function AST, not a manually reconstructed law.
    module = ast.parse(old_blob("challenge_15k.py"))
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef)
                    and node.name == "_conservative_calibration_map")
    namespace = {"Any": object, "market_specs": old_engine().market_specs}
    exec(compile(ast.Module(body=[function], type_ignores=[]), BASE + ":conservative-map", "exec"), namespace)
    return namespace["_conservative_calibration_map"]


class RemoveOnlyCaptureAdditions(ast.NodeTransformer):
    def visit_ClassDef(self, node):
        return None if node.name == "ConservativeMarketCalibration" else self.generic_visit(node)

    def visit_If(self, node):
        if ast.unparse(node.test) == "original_capture is not None":
            assert len(node.body) == 1
            assert ast.unparse(node.body[0]) == "original_calibration_recipes[market_key] = calibration_recipe(curve)"
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if node.name not in {"fixture_market_probabilities", "build_fixture_candidates"}:
            return self.generic_visit(node)
        assert node.args.kwonlyargs[-1].arg == "original_capture"
        node.args.kwonlyargs.pop()
        node.args.kw_defaults.pop()
        rebuilt = []
        for statement in node.body:
            if isinstance(statement, ast.If) and "original_capture" in ast.unparse(statement.test):
                if node.name == "build_fixture_candidates":
                    assert ast.unparse(statement.test) == "original_capture is None"
                    rebuilt.extend(statement.body)
                else:
                    assert ast.unparse(statement.test) in {"original_capture is not None", "original_capture is not None and (not callable(original_capture))"}
                continue
            if (isinstance(statement, ast.Assign) and isinstance(statement.value, ast.IfExp)
                    and "original_capture" in ast.unparse(statement.value.test)):
                assert node.name == "fixture_market_probabilities"
                assert ast.unparse(statement.value.test) == "original_capture is None"
                statement.value = statement.value.body
            rebuilt.append(statement)
        node.body = rebuilt
        return self.generic_visit(node)


def test_whole_engine_parent_ast_unchanged_outside_explicit_observing_seams():
    actual = RemoveOnlyCaptureAdditions().visit(ast.parse((ROOT / "challenge_engine.py").read_text(encoding="utf-8")))
    expected = ast.parse(old_blob("challenge_engine.py"))
    assert ast.dump(actual, include_attributes=False) == ast.dump(expected, include_attributes=False)


def test_whole_challenge_module_has_only_the_authorized_closure_type_replacement():
    from tests.test_football_final_original_a0 import strip_exact_a0_additions
    expected = ast.parse(old_blob("challenge_15k.py"))
    outer = next(node for node in expected.body if isinstance(node, ast.FunctionDef) and node.name == "_conservative_calibration_map")
    loop = next(node for node in outer.body if isinstance(node, ast.For))
    assert isinstance(loop.body[-2], ast.FunctionDef) and loop.body[-2].name == "conservative_curve"
    assert ast.unparse(loop.body[-1]) == "combined[spec.key] = conservative_curve"
    loop.body[-2:] = ast.parse("from challenge_engine import ConservativeMarketCalibration\ncombined[spec.key] = ConservativeMarketCalibration(tuple(curves))").body
    actual = ast.parse((ROOT / "challenge_15k.py").read_text(encoding="utf-8"))
    scanner = next(node for node in actual.body if isinstance(node, ast.FunctionDef)
                   and node.name == "scan_daily_challenge")
    strip_exact_a0_additions(scanner, "scanner")
    assert ast.dump(actual, include_attributes=False) == ast.dump(expected, include_attributes=False)


@pytest.mark.parametrize("profile", [engine.CANDIDATE_PROFILE_CHALLENGE, engine.CANDIDATE_PROFILE_WETTFINDER])
@pytest.mark.parametrize("scope", [engine.MODEL_SCOPE_SAME_COMPETITION, engine.MODEL_SCOPE_CROSS_COMPETITION_UNVALIDATED,
                                  engine.MODEL_SCOPE_CROSS_COMPETITION_PROVISIONAL_FORECAST])
@pytest.mark.parametrize("capture", [False, True])
def test_actual_parent_full_candidates_ids_release_fields_order_and_numbers_unchanged(profile, scope, capture):
    fixture, history = values()
    old = old_engine()
    def maps(module):
        return {spec.key: module.MarketCalibration(((0.0, .01356789), (1.0, .91864321)), 234)
                for spec in module.MARKET_SPECS}
    expected = old.build_fixture_candidates(deepcopy(fixture), deepcopy(history), {}, maps(old),
        candidate_profile=profile, model_scope=scope)
    original = []
    kwargs = {"original_capture": original.append} if capture else {}
    actual = engine.build_fixture_candidates(fixture, history, {}, maps(engine),
        candidate_profile=profile, model_scope=scope, **kwargs)
    assert canonical([row.to_dict() for row in actual]) == canonical([row.to_dict() for row in expected])
    assert len(original) == int(capture)


@pytest.mark.parametrize("probability", [0.0, 1.0, .431234567891, True, False, float("nan"), float("inf"), -float("inf")])
def test_conservative_law_keeps_actual_parent_float_and_nan_behavior(probability):
    def make_calls():
        calls = []
        def one(value):
            calls.append(("one", type(value).__name__, canonical(value)))
            return value * .8123456789
        def two(value):
            calls.append(("two", type(value).__name__, canonical(value)))
            return True
        return (one, two), calls
    old_curves, old_calls = make_calls()
    new_curves, new_calls = make_calls()
    expected = actual_old_conservative_factory()([{"RESULT_HOME": old_curves[0]}, {"RESULT_HOME": old_curves[1]}])["RESULT_HOME"](probability)
    actual = engine.ConservativeMarketCalibration(new_curves)(probability)
    assert canonical(actual) == canonical(expected)
    assert new_calls == old_calls


@pytest.mark.parametrize("bad_index", [0, 1])
def test_conservative_original_exception_and_short_circuit_order_preserved(bad_index):
    def case():
        calls = []
        def one(value):
            calls.append("one")
            if bad_index == 0:
                raise RuntimeError("source failed")
            return value
        def two(value):
            calls.append("two")
            raise RuntimeError("source failed")
        return (one, two), calls
    before, old_calls = case()
    after, new_calls = case()
    old = actual_old_conservative_factory()([{"RESULT_HOME": before[0]}, {"RESULT_HOME": before[1]}])["RESULT_HOME"]
    with pytest.raises(RuntimeError, match="source failed"):
        old(.37)
    with pytest.raises(RuntimeError, match="source failed"):
        engine.ConservativeMarketCalibration(after)(.37)
    assert new_calls == old_calls


def test_same_call_uefa_recipe_retains_unrounded_minimum_of_actual_parent_sources():
    fixture, raw = values()
    first = engine.MarketCalibration(((0., .123456789), (1., .923456789)), 101)
    second = engine.MarketCalibration(((0., .031415926), (1., .731415926)), 204)
    expected_curve = actual_old_conservative_factory()([{"RESULT_HOME": first}, {"RESULT_HOME": second}])
    expected = old_engine().fixture_market_probabilities(fixture, raw, expected_curve)
    originals = []
    actual = engine.fixture_market_probabilities(fixture, raw,
        {"RESULT_HOME": engine.ConservativeMarketCalibration((first, second))}, original_capture=originals.append)
    assert canonical(actual) == canonical(expected)
    packet = originals[0].to_dict()
    recipe = packet["calibration_recipes"]["RESULT_HOME"]
    assert recipe["kind"] == "legacy-minimum-source-calibration-v1"
    assert recipe["source_curves"] == [
        {"kind": "legacy-market-calibration-v1", "points": [[0., .123456789], [1., .923456789]], "samples": 101},
        {"kind": "legacy-market-calibration-v1", "points": [[0., .031415926], [1., .731415926]], "samples": 204}]
    assert packet["probabilities"]["RESULT_HOME"] == list(expected["probabilities"]["RESULT_HOME"])


def test_capture_bytes_and_declared_calibrator_container_are_frozen():
    fixture, history = values()
    captured = []
    engine.fixture_market_probabilities(fixture, history, original_capture=captured.append)
    with pytest.raises(FrozenInstanceError):
        captured[0]._bytes = b"{}"
    curve = engine.ConservativeMarketCalibration(())
    with pytest.raises(FrozenInstanceError):
        curve.source_curves = ()
