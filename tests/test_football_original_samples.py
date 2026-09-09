"""Ancillary sample metadata must not gate the actual legacy calculation."""
import sys

import pytest

import challenge_engine as engine
import football_original
from tests.test_football_original_capture import canonical, values


def curve_with_samples(samples, container):
    source = engine.MarketCalibration(((0.0, .1), (1.0, .9)), samples)
    curve = source if container == "direct" else engine.ConservativeMarketCalibration((source,))
    return source, curve


def source_recipe(packet, container):
    recipe = packet["calibration_recipes"]["RESULT_HOME"]
    return recipe if container == "direct" else recipe["source_curves"][0]


@pytest.mark.parametrize("container", ["direct", "conservative"])
@pytest.mark.parametrize("sign", [1, -1])
def test_unrepresentable_samples_keep_original_and_mark_only_recipe(container, sign, monkeypatch):
    fixture, history = values()
    samples = sign * 10**5000
    source, curve = curve_with_samples(samples, container)
    expected = engine.fixture_market_probabilities(fixture, history, {"RESULT_HOME": curve})
    before_limit = sys.get_int_max_str_digits()
    monkeypatch.setattr(sys, "set_int_max_str_digits", lambda *a: pytest.fail("digit-limit bypass"))
    captured = []
    actual = engine.fixture_market_probabilities(fixture, history, {"RESULT_HOME": curve},
                                                 original_capture=captured.append)
    assert canonical(actual) == canonical(expected)
    assert len(captured) == 1
    assert source.samples is samples  # no clamp, rewritten count, or mutation
    assert sys.get_int_max_str_digits() == before_limit
    packet = captured[0].to_dict()
    assert source_recipe(packet, container) == {"kind": "unsupported-callable"}
    assert "calibration-recipe-unavailable" in packet["limitations"]
    assert packet["probabilities"]["RESULT_HOME"] == list(expected["probabilities"]["RESULT_HOME"])


@pytest.mark.parametrize("container", ["direct", "conservative"])
@pytest.mark.parametrize("samples", [0, -1, 1, -(10**300), 10**300, 10**308])
def test_representable_integer_sample_metadata_is_retained_exactly(container, samples):
    fixture, history = values()
    source, curve = curve_with_samples(samples, container)
    before = source.samples
    captured = []
    expected = engine.fixture_market_probabilities(fixture, history, {"RESULT_HOME": curve})
    actual = engine.fixture_market_probabilities(fixture, history, {"RESULT_HOME": curve},
                                                 original_capture=captured.append)
    assert canonical(actual) == canonical(expected)
    assert len(captured) == 1 and source.samples is before
    packet = captured[0].to_dict()
    assert source_recipe(packet, container) == {
        "kind": "legacy-market-calibration-v1", "points": [[0.0, .1], [1.0, .9]], "samples": samples}
    assert type(source_recipe(packet, container)["samples"]) is int
    assert "calibration-recipe-unavailable" not in packet["limitations"]


@pytest.mark.parametrize("samples", [None, True, False, 3.0, "123", {"secret": "not capture data"}])
@pytest.mark.parametrize("container", ["direct", "conservative"])
def test_samples_still_require_exact_owning_integer_type(samples, container):
    fixture, history = values()
    _, curve = curve_with_samples(samples, container)
    expected = engine.fixture_market_probabilities(fixture, history, {"RESULT_HOME": curve})
    captured = []
    actual = engine.fixture_market_probabilities(fixture, history, {"RESULT_HOME": curve},
                                                 original_capture=captured.append)
    assert canonical(actual) == canonical(expected)
    packet = captured[0].to_dict()
    assert source_recipe(packet, container) == {"kind": "unsupported-callable"}
    assert "not capture data" not in captured[0]._bytes.decode("utf-8")


@pytest.mark.parametrize("sign", [1, -1])
def test_sample_numeric_range_matches_existing_point_scalar_range(sign):
    source, _ = curve_with_samples(sign * 10**309, "direct")
    assert football_original.calibration_recipe(source) == {"kind": "unsupported-callable"}
