"""D2 extraction parity, including the unchanged legacy policy edge cases."""
import importlib
import importlib.util
import math
from pathlib import Path
import random

import pytest

import challenge_engine as engine


def legacy():
    location = Path(__file__).parent / "fixtures/context_statistics_legacy_3e9ce2c.py"
    spec = importlib.util.spec_from_file_location("context_statistics_legacy", location)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def implementation():
    return importlib.import_module("model_loss_statistics")


@pytest.mark.parametrize("count", [0, 1, 2, 3, 10, 100, 200, 1000])
@pytest.mark.parametrize("shape", ["random", "identical", "better", "worse", "alternating"])
def test_hac_matches_exact_legacy_arithmetic_on_ordered_paired_event_losses(count, shape):
    rng = random.Random(7901+count)
    outcomes = [rng.randrange(2) for _ in range(count)]
    bases = [rng.random() for _ in range(count)]
    models = {"random": lambda i: rng.random(), "identical": lambda i: bases[i],
              "better": lambda i: outcomes[i], "worse": lambda i: 1-outcomes[i],
              "alternating": lambda i: .1 if i % 2 else .9}
    probabilities = [models[shape](i) for i in range(count)]
    advantages = [(b-y)**2-(p-y)**2 for p, b, y in zip(probabilities, bases, outcomes)]
    expected = legacy()._paired_loss_statistics(probabilities, bases, outcomes)
    assert implementation().paired_advantage_statistics(advantages) == expected
    assert engine._paired_loss_statistics(probabilities, bases, outcomes) == expected


@pytest.mark.parametrize("advantages", [[float("nan")], [float("inf")], [float("-inf")]])
def test_nonfinite_advantage_is_unevaluable_not_success(advantages):
    assert implementation().paired_advantage_statistics(advantages) == (None,)*4


@pytest.mark.parametrize("probabilities,baselines,outcomes", [([], [], []), ([.2], [], [1]),
    (["bad"], [.5], [0]), ([float("nan")], [.5], [0]), ([1e300], [.5], [0]),
    ([.2], [.5], [True]), ([.2], [.5], [1.9]), ([".2"], [.5], ["1"])])
def test_legacy_wrapper_invalid_input_behavior_is_preserved(probabilities, baselines, outcomes):
    assert engine._paired_loss_statistics(probabilities, baselines, outcomes) == legacy()._paired_loss_statistics(
        probabilities, baselines, outcomes)


@pytest.mark.parametrize("values", [{}, {"a": .01}, {"a": .01, "b": .02, "c": 1.},
    {"z": .05, "a": .05, "c": .03, "q": 0.}, {f"h{i}": i/99 for i in range(100)}])
def test_bh_exact_arithmetic_includes_loser_entries_and_deterministic_ties(values):
    expected = legacy()._benjamini_hochberg_q_values(values)
    assert implementation().benjamini_hochberg_q_values(values) == expected
    assert engine._benjamini_hochberg_q_values(values) == expected
    assert implementation().benjamini_hochberg_q_values(dict(reversed(tuple(values.items())))) == expected


@pytest.mark.parametrize("value", [True, False, -1, 1.01, "0.1", None, float("nan"), float("inf")])
def test_bh_rejects_same_invalid_values_as_legacy(value):
    for method in (legacy()._benjamini_hochberg_q_values, engine._benjamini_hochberg_q_values,
                   implementation().benjamini_hochberg_q_values):
        with pytest.raises(ValueError):
            method({"hypothesis": value})


def test_existing_confidence_constant_is_not_a_new_relaxed_gate():
    assert implementation().PAIRED_LOSS_CONFIDENCE_Z == engine.PAIRED_LOSS_CONFIDENCE_Z == 1.6448536269514722


def test_event_order_matters_and_is_not_sorted_by_outcome_inside_statistics():
    module = implementation()
    chronological = [.08]*30 + [-.04]*30
    alternating = [.08, -.04]*30
    assert not math.isclose(module.paired_advantage_statistics(chronological)[1],
                            module.paired_advantage_statistics(alternating)[1])


def test_existing_engine_wrappers_really_delegate_the_unchanged_advantages(monkeypatch):
    module = implementation()
    captured = []
    def paired(values):
        captured.append(values)
        return (11., 12., 13., 14.)
    monkeypatch.setattr(module, "paired_advantage_statistics", paired)
    assert engine._paired_loss_statistics([.2, .4], [.5, .5], [0, 1]) == (11., 12., 13., 14.)
    assert captured == [[(.5-0)**2-(.2-0)**2, (.5-1)**2-(.4-1)**2]]
    monkeypatch.setattr(module, "benjamini_hochberg_q_values", lambda values: {"delegated": 1.})
    assert engine._benjamini_hochberg_q_values({"registered": .1}) == {"delegated": 1.}
