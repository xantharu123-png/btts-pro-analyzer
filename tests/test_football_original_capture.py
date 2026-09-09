"""Same-call original math capture, not native/context model qualification."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

import challenge_engine as engine
from tests.test_football_base_provenance import history, target


def values():
    rows, upcoming = history(), target()
    for index, row in enumerate(rows):
        row["fixture"]["referee"] = "Referee Alpha, Country"
        row["challenge_stats"].update(corners_home=3 + index % 7, corners_away=2 + index % 4,
            yellow_cards_home=1 + index % 4, yellow_cards_away=index % 3)
    upcoming["fixture"]["referee"] = "Referee Alpha, Country"
    return upcoming, rows


def calibration():
    return {spec.key: engine.MarketCalibration(((0.0, .01234567890123), (1.0, .91234567890123)), 234)
            for spec in engine.MARKET_SPECS if spec.key != "RESULT_AWAY"}


def canonical(value):
    def plain(item):
        if isinstance(item, dict):
            return [[plain(key), plain(val)] for key, val in sorted(item.items(), key=lambda pair: repr(pair[0]))]
        if isinstance(item, (tuple, list)):
            return [plain(child) for child in item]
        if type(item) is float:
            return {"float_hex": item.hex()}
        return item
    return json.dumps(plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def test_new_same_call_api_retains_final_triplets_before_candidate_rounding():
    fixture, raw = values()
    curves = calibration()
    raw_model = engine.fixture_market_probabilities(fixture, raw)
    expected = engine.fixture_market_probabilities(fixture, raw, curves)
    originals = []
    actual = engine.build_fixture_candidates(fixture, raw, {}, curves,
        candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER, original_capture=originals.append)
    assert len(originals) == 1
    packet = originals[0].to_dict()
    assert packet["kind"] == "football-original-market-calculation-v1"
    assert packet["prediction_version"] == engine.CHALLENGE_PREDICTION_VERSION
    assert packet["probabilities"] == {key: list(val) for key, val in expected["probabilities"].items()}
    assert packet["raw_probabilities"] == {key: list(val) for key, val in raw_model["probabilities"].items()}
    assert packet["goal_model"]["active_lambdas"] == list(expected["active_lambdas"])
    assert packet["count_models"]["corners"]["active_counts"] == list(expected["count_models"]["corners"]["active_counts"])
    assert packet["count_models"]["yellow"]["dispersion"] == list(expected["count_models"]["yellow"]["dispersion"])
    assert len(packet["probabilities"]) == len(engine.MARKET_SPECS)
    assert any(item.probability != packet["probabilities"][item.market_key][0] for item in actual)
    assert any(item.expected_home_goals != packet["goal_model"]["active_lambdas"][0] for item in actual)
    assert all(item.probability == round(packet["probabilities"][item.market_key][0], 6) for item in actual)
    assert canonical([item.to_dict() for item in actual]) == canonical([item.to_dict() for item in
        engine.build_fixture_candidates(fixture, raw, {}, curves, candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER)])


def test_same_call_capture_adds_no_second_fit_matrix_or_calibration_call(monkeypatch):
    fixture, raw = values()
    counts = {}
    for name in ("_fixture_model", "_fixture_count_model", "score_matrix", "_market_probabilities"):
        original = getattr(engine, name)
        def counted(*args, _name=name, _original=original, **kwargs):
            counts[_name] = counts.get(_name, 0) + 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(engine, name, counted)
    original_curve = engine.MarketCalibration.__call__
    def curve(self, probability):
        counts["curve"] = counts.get("curve", 0) + 1
        return original_curve(self, probability)
    monkeypatch.setattr(engine.MarketCalibration, "__call__", curve)
    expected = engine.fixture_market_probabilities(fixture, raw, calibration())
    ordinary_counts = dict(counts)
    counts.clear()
    captured = []
    actual = engine.fixture_market_probabilities(fixture, raw, calibration(), original_capture=captured.append)
    assert counts == ordinary_counts
    assert len(captured) == 1 and canonical(actual) == canonical(expected)


def test_disabled_capture_has_no_new_clock_provenance_or_capture_constructor(monkeypatch):
    import football_original
    fixture, raw = values()
    def forbidden(*args, **kwargs):
        pytest.fail("the unchanged default invoked optional capture machinery")
    monkeypatch.setattr(football_original, "_capture_now", forbidden)
    monkeypatch.setattr(football_original, "capture_football_original", forbidden)
    monkeypatch.setattr(engine, "_football_reference_provenance", forbidden)
    assert engine.fixture_market_probabilities(fixture, raw, calibration()) is not None
    assert engine.build_fixture_candidates(fixture, raw, {}, calibration())


def test_capture_clock_is_actual_and_not_the_logical_historical_kickoff(monkeypatch):
    import football_original
    fixture, raw = values()
    actual = datetime(2026, 9, 9, 12, 34, 56, 123456, tzinfo=timezone.utc)
    clocks = []
    monkeypatch.setattr(football_original, "_capture_now", lambda: clocks.append(actual) or actual)
    captured = []
    engine.fixture_market_probabilities(fixture, raw, original_capture=captured.append)
    packet = captured[0].to_dict()
    assert clocks == [actual]
    assert packet["captured_at"] == "2026-09-09T12:34:56.123456Z"
    assert packet["logical_history_cutoff"] == "2026-08-06T12:00:00.000000Z"
    assert packet["captured_at"] > packet["logical_history_cutoff"]


def test_capture_is_detached_price_free_and_unknown_metadata_does_not_gate_basis():
    fixture, raw = values()
    fixture["league"].pop("season")
    fixture["fixture"].update(odds=1.0, bookmaker="secret price label")
    fixture.update(minimum_odds=99, context={"verified": True, "api_key": "not captured"})
    for row in raw:
        row.update(bookmaker="not captured", price=999, context={"verified": True})
    expected = engine.fixture_market_probabilities(fixture, raw)
    saved = []
    def callback(original):
        saved.append(original)
        projection = original.to_dict()
        projection["probabilities"]["RESULT_HOME"][0] = .123
        projection["fixture"].clear()
    actual = engine.fixture_market_probabilities(fixture, raw, original_capture=callback)
    assert canonical(actual) == canonical(expected)
    frozen = saved[0].to_dict()
    text = canonical(frozen)
    assert all(word not in text for word in ("bookmaker", "minimum_odds", "api_key", "not captured"))
    assert frozen["probabilities"]["RESULT_HOME"] == list(expected["probabilities"]["RESULT_HOME"])
    fixture.clear()
    raw.clear()
    assert saved[0].to_dict() == frozen


def test_existing_arbitrary_callable_is_used_once_per_original_probability_but_not_certified():
    fixture, raw = values()
    calls = []
    def custom(value):
        calls.append(value)
        return value * .923456789
    captured = []
    model = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": custom}, original_capture=captured.append)
    assert len(calls) == 3
    packet = captured[0].to_dict()
    assert packet["probabilities"]["RESULT_HOME"] == list(model["probabilities"]["RESULT_HOME"])
    assert packet["calibration_recipes"]["RESULT_HOME"] == {"kind": "unsupported-callable"}
    assert "calibration-recipe-unavailable" in packet["limitations"]


def test_missing_computable_model_does_not_manufacture_an_original():
    captured = []
    assert engine.fixture_market_probabilities(target(), [], original_capture=captured.append) is None
    assert engine.build_fixture_candidates(target(), [], {}, original_capture=captured.append) == []
    assert captured == []


def test_calibration_mapping_is_not_looked_up_an_extra_time_for_capture():
    fixture, raw = values()
    class ChangingMap(dict):
        def __init__(self):
            super().__init__({"RESULT_HOME": True})
            self.calls = []
        def get(self, key, default=None):
            self.calls.append(key)
            if key == "RESULT_HOME":
                factor = .5 if self.calls.count(key) == 1 else .25
                return lambda probability: probability * factor
            return default
    before, after = ChangingMap(), ChangingMap()
    expected = engine.fixture_market_probabilities(fixture, raw, before)
    captured = []
    actual = engine.fixture_market_probabilities(fixture, raw, after, original_capture=captured.append)
    assert after.calls == before.calls
    assert canonical(actual) == canonical(expected)


def test_later_calibrator_side_effect_does_not_rewrite_already_consumed_inputs():
    fixture, raw = values()
    original_id = fixture["fixture"]["id"]
    original_goals = deepcopy(raw[0]["goals"])
    def mutator(probability):
        fixture["fixture"]["id"] = 888888
        raw[0]["goals"]["home"] = 987654
        return probability
    captured = []
    engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": mutator}, original_capture=captured.append)
    packet = captured[0].to_dict()
    assert packet["fixture"]["fixture"]["id"] == original_id
    assert packet["league_history"][0]["goals"] == original_goals


def test_one_shot_league_and_distinct_team_iterators_are_consumed_once_and_retained_in_order():
    fixture, raw = values()
    separate = list(reversed(raw))
    class Once:
        def __init__(self, rows):
            self.rows, self.calls = rows, 0
        def __iter__(self):
            self.calls += 1
            assert self.calls == 1
            yield from self.rows
    league, teams = Once(raw), Once(separate)
    captured = []
    result = engine.fixture_market_probabilities(fixture, league, team_history=teams, original_capture=captured.append)
    assert result is not None and league.calls == teams.calls == 1
    packet = captured[0].to_dict()
    assert [r["fixture"]["id"] for r in packet["league_history"]] == [r["fixture"]["id"] for r in raw]
    assert [r["fixture"]["id"] for r in packet["team_history"]] == [r["fixture"]["id"] for r in separate]


def test_price_and_names_do_not_change_any_capture_byte_with_the_same_actual_clock(monkeypatch):
    import football_original
    fixture, raw = values()
    monkeypatch.setattr(football_original, "_capture_now", lambda: datetime(2026, 9, 9, tzinfo=timezone.utc))
    first, second = [], []
    engine.fixture_market_probabilities(fixture, raw, calibration(), original_capture=first.append)
    fixture.update(odds=1.01, minimum_price=99, bookmaker="anything", context={"verified": True})
    fixture["teams"]["home"]["name"] = "Completely different label"
    for row in raw:
        row.update(odds=99.99, bookmaker="anything", context={"verified": False})
        row["teams"]["home"]["name"] = "Another label"
    engine.fixture_market_probabilities(fixture, raw, calibration(), original_capture=second.append)
    assert first[0]._bytes == second[0]._bytes


@pytest.mark.parametrize("metadata", ["missing_ids", "naive_date", "nonfinite_unused_xg", "malformed_source_marker"])
def test_legacy_computable_ancillary_metadata_remains_original_not_a_capture_gate(metadata):
    fixture, raw = values()
    if metadata == "missing_ids":
        fixture["fixture"].pop("id")
        fixture["league"].clear()
    elif metadata == "naive_date":
        fixture["fixture"]["date"] = fixture["fixture"]["date"].replace("+00:00", "")
    elif metadata == "nonfinite_unused_xg":
        # A row not in any selected target team series can carry bad optional xG.
        next(r for r in raw if r["teams"]["home"]["id"] == 5)["challenge_stats"]["xg_home"] = float("inf")
    else:
        fixture["challenge_source"] = {"unexpected": "object"}
    expected = engine.fixture_market_probabilities(fixture, raw)
    assert expected is not None
    captured = []
    actual = engine.fixture_market_probabilities(fixture, raw, original_capture=captured.append)
    assert canonical(actual) == canonical(expected)
    packet = captured[0].to_dict()
    if metadata == "naive_date":
        assert "aware-native-schedule-unavailable" in packet["limitations"]
        assert packet["logical_history_cutoff"] == "2026-08-06T12:00:00.000000Z"
    assert packet["source_evidence"] == "unresolved-receipts-not-in-this-capture"


@pytest.mark.parametrize("result", [True, False, float("nan"), float("inf"), -float("inf")])
def test_accepted_legacy_callable_values_remain_unchanged_and_no_finite_number_is_fabricated(result):
    fixture, raw = values()
    expected = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": lambda p: result})
    captured = []
    actual = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": lambda p: result}, original_capture=captured.append)
    assert canonical(actual) == canonical(expected)
    packet = captured[0].to_dict()
    assert packet["calibration_recipes"]["RESULT_HOME"] == {"kind": "unsupported-callable"}
    if type(result) is bool:
        assert packet["probabilities"]["RESULT_HOME"] == [result, result, result]
    else:
        assert packet["probabilities"]["RESULT_HOME"] == [{"unavailable_value": "nonfinite-number"}] * 3
        assert "input-or-result-not-json-representable" in packet["limitations"]


def test_callback_failure_is_explicit_and_never_swallowed_as_an_unavailable_model():
    def broken(original):
        raise RuntimeError("observer persistence failed")
    fixture, raw = values()
    with pytest.raises(RuntimeError, match="observer persistence failed"):
        engine.fixture_market_probabilities(fixture, raw, original_capture=broken)


@pytest.mark.parametrize("invalid", [False, 0, {}, [], "callback"])
def test_explicit_noncallable_capture_is_a_typed_option_error(invalid):
    fixture, raw = values()
    with pytest.raises(ValueError, match="original_capture"):
        engine.fixture_market_probabilities(fixture, raw, original_capture=invalid)


@pytest.mark.parametrize("malformed", [{"bookmaker": "secret", "odds": 99}, "secret price payload", ["secret"]])
def test_custom_nonnumeric_market_result_cannot_smuggle_unallowlisted_payload(malformed):
    fixture, raw = values()
    curve = lambda probability: deepcopy(malformed)
    expected = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": curve})
    captured = []
    actual = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": curve}, original_capture=captured.append)
    assert canonical(actual) == canonical(expected)
    packet = captured[0].to_dict()
    assert "secret" not in json.dumps(packet)
    assert packet["probabilities"]["RESULT_HOME"] == [{"unavailable_value": "non-numeric-market-value"}] * 3


def test_nonstandard_conservative_iterator_is_not_consumed_by_recipe_description():
    fixture, raw = values()
    def curves():
        yield lambda probability: probability * .5
    old_curve = engine.ConservativeMarketCalibration(curves())
    new_curve = engine.ConservativeMarketCalibration(curves())
    expected = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": old_curve})
    captured = []
    actual = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": new_curve}, original_capture=captured.append)
    assert canonical(actual) == canonical(expected)
    assert captured[0].to_dict()["calibration_recipes"]["RESULT_HOME"] == {"kind": "unsupported-callable"}


def test_malformed_owning_curve_is_not_a_loophole_for_free_recipe_text():
    fixture, raw = values()
    curve = engine.MarketCalibration(((0., "secret price payload"),), 120)
    expected = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": curve})
    captured = []
    actual = engine.fixture_market_probabilities(fixture, raw, {"RESULT_HOME": curve}, original_capture=captured.append)
    assert canonical(actual) == canonical(expected)
    packet = captured[0].to_dict()
    assert "secret" not in json.dumps(packet)
    assert packet["calibration_recipes"]["RESULT_HOME"] == {"kind": "unsupported-callable"}
