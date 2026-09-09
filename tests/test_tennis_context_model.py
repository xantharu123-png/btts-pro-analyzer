"""Synthetic B7 numerical checks; none establishes a real fatigue effect."""

from copy import deepcopy

import numpy as np
import pytest
from scipy.special import logit

from context_models.contracts import (
    ContextContractError, digest, normalize_population,
    validate_base_distribution, validate_event,
)
from context_models.offset import ContextModelError, fit_offset
from context_models.tennis import FEATURE_VERSION
from context_models.tennis_effect import (
    SERVE_BASE_VERSION, SERVE_VARIANT, WINNER_VARIANT,
    apply_tennis_effect, tennis_context_result, tennis_factor_comparisons,
    tennis_serve_markets,
)
from tennis.simulator import simulate_match


STAMP = "2026-09-09T12:00:00.000000Z"
REF = "a" * 64


def event(*, best_of=3, **changes):
    return {"event_key": "espn:tennis:ATP:match:999", "sport": "tennis",
            "competition": "espn:ATP:tournament:189-2026", "format": f"singles_best_of_{best_of}",
            "home_id": "espn:tennis:ATP:player:1", "away_id": "espn:tennis:ATP:player:2",
            "scheduled_start": "2026-09-09T18:00:00.000000Z", "schedule_revision": "s1",
            "status": "scheduled", "tour": "ATP", "surface": "Hard", "indoor": False, **changes}


def base(*, family="tennis:winner", best_of=3, p=.6, hold_a=.78, hold_b=.74):
    params = {"p_a": p} if family == "tennis:winner" else {"hold_a": hold_a, "hold_b": hold_b, "best_of": best_of}
    markets = {"winner_a": p, "winner_b": 1-p} if family == "tennis:winner" else tennis_serve_markets(params)
    return {"version": "synthetic-original-winner-v1" if family == "tennis:winner" else SERVE_BASE_VERSION,
            "model_hash": "b" * 64, "event_key": event()["event_key"], "cutoff": STAMP,
            "family": family, "params": params, "markets": markets, "history_refs": [],
            "reference_weights": {"schema": 1, "kind": "unavailable", "reason": "synthetic-no-roster"}}


def features(original=None, *, ev=None, load_a=5., load_b=2., rest_a=20., rest_b=36.):
    original = original or base()
    ev = ev or event(best_of=original["params"].get("best_of", 3))
    values = {"observed_sets_1d_a": load_a, "observed_sets_1d_b": load_b,
              "observed_sets_1d_delta": load_a-load_b,
              "observed_sets_complete_1d_a": 1, "observed_sets_complete_1d_b": 1,
              "observed_recovery_exact_hours_a": rest_a, "observed_recovery_exact_hours_b": rest_b,
              "observed_recovery_exact_hours_delta": rest_a-rest_b,
              "availability_delta": None}
    return {"version": FEATURE_VERSION, "event_key": original["event_key"], "cutoff": STAMP,
            "values": values, "states": {name: "missing" if value is None else "available" for name, value in values.items()},
            "refs": {name: [] if value is None else [REF] for name, value in values.items()},
            "coverage": {"version": "tennis-performed-load-coverage-v1", "case": "observed-only.exact-observed.known-end-times"},
            "reference_hash": digest({"version": "tennis-context-reference-v2",
                "base_hash": digest(validate_base_distribution(original)), "event_hash": digest(validate_event(ev))})}


def artifact(original=None, feats=None, ev=None):
    original = original or base()
    ev = ev or event(best_of=original["params"].get("best_of", 3))
    feats = feats or features(original, ev=ev)
    # Actual B2 optimization of artificial, mirrored Bernoulli observations.
    x = np.array([[-1.], [0.], [1.]] * 40)
    winner = fit_offset(x, np.zeros(120), np.array([1., 0., 0.] * 40), link="logit", alpha=.1)
    if original["family"] == "tennis:serve":
        # Identified service successes/trials, not match-winner targets.
        head = fit_offset(x, np.full(120, logit(.75)), np.array([9., 8., 5.] * 40),
                          trials=np.full(120, 10.), link="logit", alpha=.1)
        heads = {"hold_a": head, "hold_b": {**deepcopy(head), "coef": [-c for c in head["coef"]]}}
        variant = SERVE_VARIANT
    else:
        heads, variant = {"winner": winner}, WINNER_VARIANT
    return {"schema": 1, "sport": "tennis", "family": original["family"], "feature_version": FEATURE_VERSION,
            "feature_names": ["observed_sets_1d_delta"], "heads": heads,
            "preprocessing_artifacts": {}, "joint_calibration": {"kind": "identity"},
            "training_end": "2026-09-01T12:00:00.000000Z", "training_refs_hash": REF,
            "population": normalize_population({"sport": "tennis", "competitions": [ev["competition"]],
                "formats": [ev["format"]], "tours": [ev["tour"]], "surfaces": [ev["surface"]], "indoor": [ev["indoor"]]}),
            "coverage": deepcopy(feats["coverage"]), "model_variant": variant}


def test_winner_basis_cannot_acquire_serve_effect_or_side_markets():
    with pytest.raises(ContextModelError, match="family"):
        apply_tennis_effect(base(), features(), artifact(base(family="tennis:serve")), event=event())


def test_learned_winner_effect_changes_probability_and_keeps_original_inputs():
    original, feats = base(), features()
    fitted = artifact(original, feats)
    before = deepcopy((original, feats, fitted))
    comparison = apply_tennis_effect(original, feats, fitted, event=event())
    assert 0 < comparison["markets"]["winner_a"] < original["markets"]["winner_a"]
    assert set(comparison["markets"]) == {"winner_a", "winner_b"}
    assert sum(comparison["markets"].values()) == pytest.approx(1., abs=1e-15)
    assert (original, feats, fitted) == before


def test_missing_load_is_not_zero_or_a_healthy_player():
    feats = features()
    feats["values"]["observed_sets_1d_delta"] = None
    feats["states"]["observed_sets_1d_delta"] = "missing"
    with pytest.raises(ContextModelError, match="feature"):
        apply_tennis_effect(base(), feats, artifact(), event=event())


def test_strict_simulator_does_not_round_away_a_small_hold_change():
    first = simulate_match(.770001, .74, best_of=3, strict=True)
    changed = simulate_match(.770009, .74, best_of=3, strict=True)
    assert changed.p_a_win > first.p_a_win
    assert simulate_match(.770001, .74).p_a_win == simulate_match(.770009, .74).p_a_win


def result(original=None, feats=None, fitted=None, ev=None, **changes):
    original = original or base()
    ev = ev or event(best_of=original["params"].get("best_of", 3))
    feats = feats or features(original, ev=ev)
    fitted = fitted or artifact(original, feats, ev)
    envelope = {"kind": "context-effect-v1", "payload": fitted}
    return tennis_context_result(original, feats, envelope, event=ev, effect_hash=digest(envelope), **changes)


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
@pytest.mark.parametrize("best_of", [3, 5])
def test_real_fitted_heads_are_internal_until_d2_and_a1_hash_binds_kind_payload(family, best_of):
    original = base(family=family, best_of=best_of)
    ev = event(best_of=best_of)
    feats = features(original, ev=ev)
    fitted = artifact(original, feats, ev)
    answer = result(original, feats, fitted, ev)
    assert answer["role"] == "experimental"
    assert answer["base_hash"] == digest(original)
    assert answer["effect_hash"] == digest({"kind": "context-effect-v1", "payload": fitted})
    assert answer["effect_hash"] != digest(fitted)
    assert answer["used_params"] == original["params"]
    assert answer["used_markets"] == original["markets"]
    assert all(value == 0 for value in answer["delta_pp"].values())
    assert answer["comparison_markets"]["winner_a"] < original["markets"]["winner_a"]
    assert answer["certified_markets"] == []
    assert answer["factor_roles"]["availability_delta"] == "not_applied"


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
@pytest.mark.parametrize("best_of", [3, 5])
@pytest.mark.parametrize("loads", [(1., 5.), (2., 2.), (5., 1.)])
def test_side_swap_with_same_artifact_complements_winner_and_shared_markets(family, best_of, loads):
    original = base(family=family, best_of=best_of)
    ev = event(best_of=best_of)
    feats = features(original, ev=ev, load_a=loads[0], load_b=loads[1])
    fitted = artifact(original, feats, ev)
    first = apply_tennis_effect(original, feats, fitted, event=ev)
    reverse = base(family=family, best_of=best_of, p=.4, hold_a=.74, hold_b=.78)
    reverse_ev = {**ev, "home_id": ev["away_id"], "away_id": ev["home_id"]}
    reverse_feats = features(reverse, ev=reverse_ev, load_a=loads[1], load_b=loads[0], rest_a=36., rest_b=20.)
    second = apply_tennis_effect(reverse, reverse_feats, fitted, event=reverse_ev)
    assert first["markets"]["winner_a"] + second["markets"]["winner_a"] == pytest.approx(1., abs=1e-12)
    if family == "tennis:serve":
        assert first["params"]["hold_a"] == second["params"]["hold_b"]
        assert first["params"]["hold_b"] == second["params"]["hold_a"]
        for name in first["markets"]:
            if name.startswith(("over_", "under_", "exact_", "tiebreak_")):
                assert first["markets"][name] == pytest.approx(second["markets"][name], abs=1e-12)
        assert first["markets"]["game_handicap_a_minus_3_5"] == pytest.approx(second["markets"]["game_handicap_b_minus_3_5"], abs=1e-12)


@pytest.mark.parametrize("best_of", [3, 5])
def test_serve_catalog_probability_sums_and_nested_lines(best_of):
    original = base(family="tennis:serve", best_of=best_of)
    comparison = apply_tennis_effect(original, features(original), artifact(original), event=event(best_of=best_of))
    m = comparison["markets"]
    assert all(0 <= probability <= 1 for probability in m.values())
    assert sum(p for name, p in m.items() if name.startswith("correct_score_")) == pytest.approx(1., abs=1e-12)
    assert sum(p for name, p in m.items() if name.startswith("exact_")) == pytest.approx(1., abs=1e-12)
    assert m["tiebreak_yes"] + m["tiebreak_no"] == pytest.approx(1., abs=1e-15)
    totals = sorted((int(name.split("_")[1].split(".")[0]), p) for name, p in m.items() if name.startswith("over_") and name.endswith("games"))
    assert all(a[1] >= b[1] for a, b in zip(totals, totals[1:]))
    for lower, probability in totals:
        assert probability + m[f"under_{lower}.5_games"] == pytest.approx(1., abs=1e-12)
    assert m["game_handicap_a_minus_2_5"] >= m["game_handicap_a_minus_3_5"] >= m["game_handicap_a_minus_4_5"]
    if best_of == 5:
        assert m["over_3_5_sets"] >= m["over_4_5_sets"]


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
def test_zero_fitted_effect_keeps_exact_original_probability_bytes(family):
    original = base(family=family)
    fitted = artifact(original)
    # This head is also actually fitted, with an unidentifiable all-zero column.
    zero = fit_offset(np.zeros((20, 1)), np.zeros(20), np.array([0., 1.] * 10), link="logit", alpha=.1)
    for head in fitted["heads"]:
        fitted["heads"][head] = deepcopy(zero)
    comparison = apply_tennis_effect(original, features(original), fitted, event=event())
    assert comparison["params"] == original["params"]
    assert comparison["markets"] == original["markets"]
    assert result(original, fitted=fitted)["role"] == "experimental"


@pytest.mark.parametrize("state", ["missing", "stale", "conflicting", "not_applicable"])
def test_unavailable_feature_retains_basis_without_numeric_zero_substitution(state):
    feats = features()
    feats["states"]["observed_sets_1d_delta"] = state
    if state in {"missing", "not_applicable"}:
        feats["values"]["observed_sets_1d_delta"] = None
    answer = result(feats=feats)
    assert answer["role"] == "not_applied"
    assert answer["comparison_params"] is None
    assert answer["used_markets"] == base()["markets"]
    assert answer["factor_states"]["observed_sets_1d_delta"] == state


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
@pytest.mark.parametrize("value", [1e308, -1e308])
def test_offset_overflow_is_typed_and_b3_preserves_baseline(family, value):
    original = base(family=family)
    fitted = artifact(original)
    for index, head in enumerate(fitted["heads"].values()):
        head["coef"] = [value if index == 0 else -value]
    with pytest.raises(ContextModelError):
        apply_tennis_effect(original, features(original), fitted, event=event())
    answer = result(original, fitted=fitted)
    assert answer["role"] == "not_applied"
    assert answer["comparison_markets"] is None
    assert answer["used_markets"] == original["markets"]


@pytest.mark.parametrize("p", [0., 1.])
def test_valid_endpoint_winner_base_remains_visible_when_logit_is_unavailable(p):
    original = base(p=p)
    answer = result(original)
    assert answer["role"] == "not_applied"
    assert answer["used_markets"] == original["markets"]


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
def test_prior_comparison_cannot_be_adjusted_a_second_time(family):
    original = base(family=family)
    fitted = artifact(original)
    comparison = apply_tennis_effect(original, features(original), fitted, event=event())
    with pytest.raises(ContextModelError, match="original"):
        apply_tennis_effect(comparison, features(original), fitted, event=event())
    with pytest.raises(ContextContractError):
        apply_tennis_effect(result(original), features(original), fitted, event=event())
    assert apply_tennis_effect(original, features(original), fitted, event=event()) == comparison


@pytest.mark.parametrize("fmt", ["singles", "doubles", "best_of_3", "best_of_5", "doubles_best_of_3", "singles_best_of_5"])
def test_serve_does_not_infer_or_change_actual_single_format(fmt):
    original = base(family="tennis:serve")
    ev = event(format=fmt)
    fitted = artifact(original, ev=ev)
    with pytest.raises(ContextModelError, match="format|best_of"):
        apply_tennis_effect(original, features(original, ev=ev), fitted, event=ev)
    assert result(original, fitted=fitted, ev=ev)["used_params"] == original["params"]


def test_winner_only_unknown_single_format_is_explicit_scope_not_serve_permission():
    ev = event(format="singles")
    answer = result(ev=ev)
    assert answer["role"] == "experimental"
    assert set(answer["comparison_markets"]) == {"winner_a", "winner_b"}
    assert result(ev=event(), fitted=artifact(ev=ev))["role"] == "not_applied"


@pytest.mark.parametrize("changes", [{"tour": "WTA"}, {"surface": "Clay"}, {"surface": None},
    {"indoor": True}, {"indoor": None}, {"competition": "other:tournament"}, {"status": "cancelled"},
    {"status": "started"}, {"status": "completed"}, {"scheduled_start": STAMP}])
def test_wrong_population_or_current_event_state_cannot_use_fitted_effect(changes):
    answer = result(ev=event(**changes), fitted=artifact())
    assert answer["role"] == "not_applied"
    assert answer["used_markets"] == base()["markets"]


@pytest.mark.parametrize("field,values", [("tours", ["ATP", "WTA"]), ("surfaces", ["Clay", "Hard"]), ("indoor", [False, True])])
def test_first_variant_does_not_pool_tour_surface_or_environment(field, values):
    fitted = artifact()
    fitted["population"][field] = values
    assert result(fitted=fitted)["role"] == "not_applied"


@pytest.mark.parametrize("change", ["reference", "event", "cutoff"])
def test_input_identity_mismatch_is_integrity_error_not_a_missing_feature(change):
    from context_models.contracts import ContextIntegrityError
    feats = features()
    if change == "reference": feats["reference_hash"] = "d" * 64
    if change == "event": feats["event_key"] = "espn:tennis:ATP:match:123"
    if change == "cutoff": feats["cutoff"] = "2026-09-09T12:00:01.000000Z"
    with pytest.raises(ContextIntegrityError):
        result(feats=feats)


def test_changed_quote_or_injected_model_price_is_not_an_input_to_numerical_api():
    import inspect
    for function in (apply_tennis_effect, tennis_factor_comparisons, tennis_context_result):
        assert not any(word in name for name in inspect.signature(function).parameters for word in ("odds", "price", "quote"))
    first = result()
    separate_display_price = {"odds": 1.12}
    separate_display_price["odds"] = 3.4
    assert result() == first
    contaminated = base()
    contaminated["odds"] = 3.4
    with pytest.raises(ContextContractError):
        apply_tennis_effect(contaminated, features(), artifact(), event=event())


@pytest.mark.parametrize("feature", ["surface_hard", "indoor", "retired_injured", "availability_delta", "travel_hours_delta", "observed_sets_1d_a"])
def test_winner_rejects_unowned_or_nonantisymmetric_features(feature):
    feats, fitted = features(), artifact()
    feats["values"][feature], feats["states"][feature], feats["refs"][feature] = 1., "available", [REF]
    fitted["feature_names"] = [feature]
    assert result(feats=feats, fitted=fitted)["role"] == "not_applied"


@pytest.mark.parametrize("change", ["wrong_delta", "empty_ref", "wrong_union", "negative_load", "inexact_int"])
def test_cannot_forge_measurement_differences_or_unproven_numeric_values(change):
    feats = features()
    if change == "wrong_delta": feats["values"]["observed_sets_1d_delta"] += 1
    if change == "empty_ref": feats["refs"]["observed_sets_1d_delta"] = []
    if change == "wrong_union": feats["refs"]["observed_sets_1d_delta"] = ["d" * 64]
    if change == "negative_load": feats["values"]["observed_sets_1d_a"] = -1.
    if change == "inexact_int":
        feats["values"].update(observed_sets_1d_a=2**53+1, observed_sets_1d_b=0, observed_sets_1d_delta=2**53+1)
    assert result(feats=feats)["role"] == "not_applied"


@pytest.mark.parametrize("change", ["coefficient", "scale", "n_rows", "alpha"])
def test_separately_fitted_unconstrained_serve_heads_are_not_silently_symmetrized(change):
    original = base(family="tennis:serve")
    fitted = artifact(original)
    key = {"coefficient": "coef", "scale": "scale", "n_rows": "n_rows", "alpha": "alpha"}[change]
    if key in {"coef", "scale"}: fitted["heads"]["hold_b"][key][0] += .01
    else: fitted["heads"]["hold_b"][key] += 1
    with pytest.raises(ContextModelError, match="mirror"):
        apply_tennis_effect(original, features(original), fitted, event=event())
    assert result(original, fitted=fitted)["role"] == "not_applied"


@pytest.mark.parametrize("change", ["legacy_version", "mixed_winner", "rounded", "unsupported_market", "expected_games"])
def test_serve_basis_must_be_the_same_coherent_distribution(change):
    original = base(family="tennis:serve")
    if change == "legacy_version": original["version"] = "legacy-elo-serve-blend"
    if change == "mixed_winner": original["markets"]["winner_a"] += .01
    if change == "rounded": original["markets"] = {name: round(p, 4) for name, p in original["markets"].items()}
    if change == "unsupported_market": original["markets"]["unknown_outcome"] = .3
    if change == "expected_games": original["markets"]["expected_games"] = .3
    with pytest.raises(ContextModelError, match="basis"):
        apply_tennis_effect(original, features(original), artifact(original), event=event())
    assert result(original)["used_markets"] == original["markets"]


def test_subset_of_supported_serve_markets_preserves_exact_catalog_and_has_no_added_markets():
    original = base(family="tennis:serve")
    original["markets"] = {name: original["markets"][name] for name in ("winner_a", "winner_b", "over_22.5_games")}
    comparison = apply_tennis_effect(original, features(original), artifact(original), event=event())
    assert set(comparison["markets"]) == set(original["markets"])


@pytest.mark.parametrize("change", ["coverage_version", "coverage_case", "feature_version", "trained_later", "preprocessing", "variant"])
def test_effect_model_and_feature_coverage_versions_are_exact(change):
    fitted = artifact()
    if change == "coverage_version": fitted["coverage"]["version"] = "another-coverage-v1"
    if change == "coverage_case": fitted["coverage"]["case"] = "observed-only.receipt-bound-observed.known-end-times"
    if change == "feature_version": fitted["feature_version"] = "another-feature-v1"
    if change == "trained_later": fitted["training_end"] = "2026-09-10T12:00:00.000000Z"
    if change == "preprocessing": fitted["preprocessing_artifacts"]["unresolved-transform"] = REF
    if change == "variant": fitted["model_variant"] = "legacy-calibrated-winner"
    assert result(fitted=fitted)["role"] == "not_applied"


def test_owning_simulator_failure_does_not_publish_changed_values(monkeypatch):
    import context_models.tennis_effect as module
    original, fitted = base(family="tennis:serve"), artifact(base(family="tennis:serve"))
    def invalid(*args, **kwargs):
        raise ValueError("invalid probability mass")
    monkeypatch.setattr(module, "simulate_match", invalid)
    answer = result(original, fitted=fitted)
    assert answer["role"] == "not_applied"
    assert answer["used_markets"] == original["markets"]


@pytest.mark.parametrize("value", [True, False, "0.7", None, 0., 1., -.1, 1.1, float("nan"), float("inf")])
def test_strict_simulator_rejects_invalid_holds_without_clamps(value):
    with pytest.raises(ValueError):
        simulate_match(value, .7, 3, strict=True)
    with pytest.raises(ValueError):
        simulate_match(.7, value, 3, strict=True)


@pytest.mark.parametrize("value", [True, False, 3., 5., "3", None, 1, 7])
def test_strict_simulator_requires_actual_integer_match_format(value):
    with pytest.raises(ValueError):
        simulate_match(.7, .7, value, strict=True)


def test_strict_simulator_reports_broken_mass_without_renormalization(monkeypatch):
    import tennis.simulator as module
    monkeypatch.setattr(module, "_set_distribution_cached", lambda *args: (("A", 6, 0, False, .2),))
    with pytest.raises(ValueError, match="mass"):
        module.simulate_match(.7, .7, 3, strict=True)


@pytest.mark.parametrize("side", ["a", "b"])
@pytest.mark.parametrize("value", [0, None])
def test_observed_subset_completeness_is_required_for_each_consumed_side(side, value):
    feats = features()
    name = f"observed_sets_complete_1d_{side}"
    feats["values"][name] = value
    if value is None:
        feats["states"][name] = "missing"
    answer = result(feats=feats)
    assert answer["role"] == "not_applied"
    assert answer["used_markets"] == base()["markets"]


def test_complete_observed_subset_does_not_require_or_claim_complete_player_history():
    feats = features()
    for side in ("a", "b"):
        name = f"history_complete_1d_{side}"
        feats["values"][name], feats["states"][name], feats["refs"][name] = 0, "available", [REF]
    answer = result(feats=feats)
    assert answer["role"] == "experimental"
    for side in ("a", "b"):
        assert answer["factor_roles"][f"history_complete_1d_{side}"] == "not_applied"


@pytest.mark.parametrize("fmt,available", [("singles", True), ("singles_best_of_3", True), ("singles_best_of_5", True),
    ("best_of_3", False), ("best_of_5", False), ("doubles", False), ("doubles_best_of_3", False)])
def test_b6_only_explicit_single_formats_reach_existing_load_features(tmp_path, fmt, available):
    from test_tennis_context_features import features as b6_features, native_row, event as b6_event
    feats = b6_features(tmp_path, [native_row(sets=(3, 2)), native_row("2", "2", sets=(2, 0))], ev=b6_event(format=fmt))
    assert (feats["states"]["observed_sets_1d_delta"] == "available") is available
    if available:
        assert feats["values"]["observed_sets_1d_delta"] == 3
    else:
        assert feats["values"]["observed_sets_1d_delta"] is None


def test_append_only_b6_receipts_feed_fitted_b7_without_inventing_an_injury(tmp_path):
    from test_tennis_context_features import native_row, stored, NOW
    from context_models.tennis import tennis_features
    ev, original = event(), base()
    rows = stored(tmp_path, [native_row(sets=(3, 2), termination="retirement"), native_row("2", "2", sets=(2, 0))])
    feats = tennis_features(ev, rows, original, cutoff=NOW)
    assert feats["values"]["availability_a"] is None
    assert feats["states"]["observed_sets_1d_delta"] == "available"
    answer = result(original, feats)
    assert answer["role"] == "experimental"
    assert answer["comparison_markets"]["winner_a"] < original["markets"]["winner_a"]
    assert answer["factor_roles"]["availability_a"] == "not_applied"
    assert answer["feature_refs"]["observed_sets_1d_delta"] == feats["refs"]["observed_sets_1d_delta"]
    assert tennis_features(ev, rows + rows, original, cutoff=NOW) == feats


def test_missing_actual_end_does_not_turn_receipt_time_into_completed_load(tmp_path):
    from test_tennis_context_features import native_row, stored, NOW
    from context_models.tennis import tennis_features
    original, ev = base(), event()
    rows = stored(tmp_path, [native_row(actual_end_utc=None), native_row("2", "2", actual_end_utc=None)])
    feats = tennis_features(ev, rows, original, cutoff=NOW)
    assert feats["values"]["observed_sets_1d_delta"] is None
    assert feats["values"]["observed_recovery_minimum_hours_delta"] is not None
    answer = result(original, feats)
    assert answer["role"] == "not_applied"
    assert answer["used_markets"] == original["markets"]


def two_group_fit(original):
    fitted = artifact(original)
    fitted["feature_names"] = ["observed_sets_1d_delta", "observed_recovery_exact_hours_delta"]
    x = np.array([[-1., -1.], [-1., 1.], [1., -1.], [1., 1.]] * 30)
    targets = np.array([1., 1., 0., 1.] * 30)
    head = fit_offset(x, np.full(120, logit(.6)), targets, link="logit", alpha=.2)
    assert all(abs(value) > .01 for value in head["coef"])
    fitted["heads"] = {"winner": head}
    return fitted


def test_leave_group_out_contrasts_are_original_based_and_not_additive_explanations():
    original = base()
    feats = features(original, load_a=3., load_b=2., rest_a=35., rest_b=36.)
    fitted = two_group_fit(original)
    snapshot = deepcopy((original, feats, fitted))
    full = apply_tennis_effect(original, feats, fitted, event=event())
    contrasts = tennis_factor_comparisons(original, feats, fitted, event=event())
    assert set(contrasts) == {"workload", "recovery"}
    for group, contrast in contrasts.items():
        assert contrast["kind"] == "tennis-group-counterfactual-v1"
        assert contrast["additive"] is False
        assert contrast["base_hash"] == digest(original)
        assert contrast["comparison"]["model_hash"] != full["model_hash"]
        assert contrast["delta_pp_vs_full"]["winner_a"] == 100 * (contrast["comparison"]["markets"]["winner_a"] - full["markets"]["winner_a"])
        # A contrast is explicitly wrapped, not a replacement model input.
        with pytest.raises(ContextContractError):
            apply_tennis_effect(contrast, feats, fitted, event=event())
    removed_sum = sum(contrast["delta_pp_vs_full"]["winner_a"] for contrast in contrasts.values())
    joint_removal = 100 * (original["markets"]["winner_a"] - full["markets"]["winner_a"])
    assert abs(removed_sum - joint_removal) > .01
    assert (original, feats, fitted) == snapshot


def test_serve_mirrored_individual_features_and_stored_scale_route_to_correct_heads():
    original = base(family="tennis:serve")
    fitted = artifact(original)
    fitted["feature_names"] = ["observed_sets_1d_a", "observed_sets_1d_b"]
    x = np.array([[1., 2.], [2., 1.], [4., 2.], [2., 4.]] * 30)
    head = fit_offset(x, np.full(120, logit(.75)), np.array([9., 6., 4., 8.] * 30),
                      trials=np.full(120, 10.), link="logit", alpha=.2)
    # The counterpart is the exact same fitted law under the A/B permutation.
    fitted["heads"] = {"hold_a": head, "hold_b": {**deepcopy(head), "coef": head["coef"][::-1], "scale": head["scale"][::-1]}}
    first = apply_tennis_effect(original, features(original), fitted, event=event())
    reverse = base(family="tennis:serve", hold_a=.74, hold_b=.78)
    reverse_ev = event(home_id=event()["away_id"], away_id=event()["home_id"])
    second = apply_tennis_effect(reverse, features(reverse, ev=reverse_ev, load_a=2., load_b=5.), fitted, event=reverse_ev)
    assert first["params"]["hold_a"] == second["params"]["hold_b"]
    assert first["params"]["hold_b"] == second["params"]["hold_a"]
    assert first["markets"]["winner_a"] + second["markets"]["winner_a"] == pytest.approx(1., abs=1e-12)
    fitted["feature_names"] = ["observed_sets_1d_a", "observed_recovery_exact_hours_b"]
    with pytest.raises(ContextModelError, match="counterpart"):
        apply_tennis_effect(original, features(original), fitted, event=event())


def test_equivalent_utc_inputs_and_pure_reloads_preserve_comparison_identity():
    original, feats = base(), features()
    fitted, ev = artifact(), event()
    first = apply_tennis_effect(original, feats, fitted, event=ev)
    original["cutoff"] = feats["cutoff"] = "2026-09-09T14:00:00+02:00"
    ev["scheduled_start"] = "2026-09-09T20:00:00+02:00"
    assert apply_tennis_effect(original, feats, fitted, event=ev) == first
    changed = base(p=.61)
    assert apply_tennis_effect(changed, features(changed), fitted, event=event())["model_hash"] != first["model_hash"]
    assert base()["model_hash"] == changed["model_hash"]


@pytest.mark.parametrize("changes", [{"digest_only": True}, {"wrong_kind": True}, {"changed_payload": True}])
def test_a1_effect_envelope_cannot_be_aliased_or_tampered(changes):
    from context_models.contracts import ContextIntegrityError
    fitted = artifact()
    envelope = {"kind": "context-effect-v1", "payload": fitted}
    bound = digest(envelope)
    if changes.get("digest_only"): bound = digest(fitted)
    if changes.get("wrong_kind"): envelope["kind"] = "other-effect-v1"
    if changes.get("changed_payload"): fitted["heads"]["winner"]["coef"][0] += .1
    with pytest.raises(ContextIntegrityError):
        tennis_context_result(base(), features(), envelope, event=event(), effect_hash=bound)


@pytest.mark.parametrize("case", [(.78, .74, 3), (.78, .74, 5), (.770001, .74, 3),
    (.770009, .74, 3), (.00001, .7, 3), (.999999, .75, 5), (.9, .6, 3), (.7, .7, 5)])
def test_legacy_simulator_full_distributions_retain_frozen_original_bytes(case, monkeypatch):
    """Hash-verified original Git blob; exact same-CPU comparison, not a tolerance."""
    import hashlib
    import sys
    import types
    from dataclasses import asdict
    from pathlib import Path
    source = (Path(__file__).parent / "fixtures/tennis_simulator_legacy_dd6fd38.py").read_bytes()
    assert hashlib.sha256(source).hexdigest() == "c0f6a751b09c59c3bb547d13703eb854094c0b6b5527f2bc27358086b3da3734"
    legacy = types.ModuleType("_b7_frozen_legacy_simulator")
    monkeypatch.setitem(sys.modules, legacy.__name__, legacy)
    exec(compile(source, "frozen_legacy_simulator", "exec"), legacy.__dict__)
    assert repr(asdict(simulate_match(*case))).encode() == repr(asdict(legacy.simulate_match(*case))).encode()
    assert simulate_match(*case) == simulate_match(*case, strict=False)


def test_strict_mode_preserves_valid_sub_clamp_hold_differences():
    assert simulate_match(.0003, .7, strict=True).p_a_win != simulate_match(.0008, .7, strict=True).p_a_win
    assert simulate_match(.0003, .7).p_a_win == simulate_match(.0008, .7).p_a_win


def test_unfitted_legacy_calibrator_is_not_appended_to_the_new_joint_distribution():
    fitted = artifact(base(family="tennis:serve"))
    fitted["joint_calibration"] = {"kind": "platt", "coef": [1., 0.]}
    with pytest.raises(ContextContractError):
        result(base(family="tennis:serve"), fitted=fitted)


def synthetic_resolved_approval(original, fitted):
    """Only a B3 transport fixture, not a genuine D2 evaluation/approval."""
    payload = {"schema": 1, "decision": "approved", "hypothesis_id": "1" * 64,
        "experiment_hash": "2" * 64, "report_hash": "3" * 64,
        "effect_hash": digest({"kind": "context-effect-v1", "payload": fitted}),
        "dataset_hash": "4" * 64, "event_identity_hash": "5" * 64, "code_revision": "6" * 40,
        "policy_version": "synthetic-test-v1", "base_versions": [original["version"]],
        "sport": "tennis", "family": original["family"], "feature_version": FEATURE_VERSION,
        "population": deepcopy(fitted["population"]), "coverage": deepcopy(fitted["coverage"]),
        "model_variant": fitted["model_variant"], "target_markets": sorted(original["markets"]),
        "outcome_contract": "synthetic-tennis-result-v1", "test_events_hash": "7" * 64,
        "evaluated_at": "2026-09-08T12:00:00.000000Z"}
    envelope = {"kind": "context-approval-v1", "payload": payload}
    return {"digest": digest(envelope), **envelope}


@pytest.mark.parametrize("family", ["tennis:winner", "tennis:serve"])
@pytest.mark.parametrize("zero", [False, True])
def test_b3_resolved_approval_uses_one_version_and_distinguishes_zero_from_not_applied(family, zero):
    original = base(family=family)
    feats = features(original, load_a=2., load_b=2.) if zero else features(original)
    fitted = artifact(original, feats)
    answer = result(original, feats, fitted, approval=synthetic_resolved_approval(original, fitted))
    assert answer["role"] == "applied"
    assert answer["factor_roles"]["observed_sets_1d_delta"] == "applied"
    assert answer["used_params"] == answer["comparison_params"]
    assert answer["used_markets"] == answer["comparison_markets"]
    assert answer["used_markets"]["winner_a"] + answer["used_markets"]["winner_b"] == pytest.approx(1., abs=1e-12)
    if zero:
        assert answer["used_markets"] == original["markets"]
        assert all(value == 0 for value in answer["delta_pp"].values())
    else:
        assert answer["delta_pp"]["winner_a"] < 0
    # This is isolated transport mechanics; no runtime model or ticket exists.
    assert original == base(family=family)


def test_matching_unknown_coverage_does_not_create_an_undeclared_variant():
    feats, fitted = features(), artifact()
    feats["coverage"]["case"] = fitted["coverage"]["case"] = "complete-full-career"
    assert result(feats=feats, fitted=fitted)["role"] == "not_applied"


@pytest.mark.parametrize("side", ["a", "b"])
def test_partly_missing_observed_minutes_cannot_reuse_full_subset_coefficients(side):
    feats, fitted = features(), artifact()
    fitted["feature_names"] = ["observed_minutes_1d_delta"]
    for name, value in {"observed_minutes_1d_a": 200., "observed_minutes_1d_b": 100.,
                        "observed_minutes_1d_delta": 100., "observed_minutes_complete_1d_a": 1,
                        "observed_minutes_complete_1d_b": 1}.items():
        feats["values"][name], feats["states"][name], feats["refs"][name] = value, "available", [REF]
    feats["values"][f"observed_minutes_complete_1d_{side}"] = 0
    assert result(feats=feats, fitted=fitted)["role"] == "not_applied"


@pytest.mark.parametrize("change", ["kickoff", "revision", "tour", "surface", "indoor", "participants", "format", "competition", "status", "base_params", "base_model", "base_version"])
def test_old_features_cannot_cross_a_changed_complete_event_or_baseline(change):
    from context_models.contracts import ContextIntegrityError
    original, ev = base(), event()
    frozen = features(original)
    fitted = artifact(original, frozen, ev)
    if change == "kickoff": ev["scheduled_start"] = "2026-09-09T22:00:00.000000Z"
    if change == "revision": ev["schedule_revision"] = "s2"
    if change == "tour": ev["tour"] = "WTA"
    if change == "surface": ev["surface"] = "Clay"
    if change == "indoor": ev["indoor"] = True
    if change == "participants": ev["home_id"], ev["away_id"] = ev["away_id"], ev["home_id"]
    if change == "format": ev["format"] = "singles_best_of_5"
    if change == "competition": ev["competition"] = "espn:ATP:tournament:other"
    if change == "status": ev["status"] = "cancelled"
    if change == "base_params": original.update(params={"p_a": .55}, markets={"winner_a": .55, "winner_b": .45})
    if change == "base_model": original["model_hash"] = "e" * 64
    if change == "base_version": original["version"] = "different-base-v2"
    # Same native event key, same cutoff and same stored feature values are not
    # permission to reuse a different scheduled/metadata/base revision.
    assert original["event_key"] == frozen["event_key"] == ev["event_key"]
    assert original["cutoff"] == frozen["cutoff"]
    with pytest.raises(ContextIntegrityError, match="reference"):
        apply_tennis_effect(original, frozen, fitted, event=ev)


def test_b6_reference_v2_binds_complete_canonical_event_and_base(tmp_path):
    from test_tennis_context_features import native_row, stored, NOW
    from context_models.contracts import validate_base_distribution, validate_event
    from context_models.tennis import tennis_features
    original, ev = base(), event()
    observations = stored(tmp_path, [native_row(sets=(3, 2)), native_row("2", "2")])
    feats = tennis_features(ev, observations, original, cutoff=NOW)
    assert feats["version"] == "tennis-performed-load-v2"
    assert feats["reference_hash"] == digest({"version": "tennis-context-reference-v2",
        "base_hash": digest(validate_base_distribution(original)), "event_hash": digest(validate_event(ev))})


def test_v1_history_only_reference_cannot_be_relabelled_as_v2():
    from context_models.contracts import ContextIntegrityError
    original, feats = base(), features()
    feats["reference_hash"] = digest({name: original[name] for name in ("history_refs", "reference_weights")})
    with pytest.raises(ContextIntegrityError, match="reference"):
        result(original, feats)


@pytest.mark.parametrize("old", ["features", "effect", "both"])
def test_v1_feature_or_effect_version_is_never_silently_migrated(old):
    feats, fitted = features(), artifact()
    if old in {"features", "both"}: feats["version"] = "tennis-performed-load-v1"
    if old in {"effect", "both"}: fitted["feature_version"] = "tennis-performed-load-v1"
    answer = result(feats=feats, fitted=fitted)
    assert answer["role"] == "not_applied"
    assert answer["used_markets"] == base()["markets"]
    assert answer["comparison_markets"] is None


def test_b6_rebuild_after_schedule_revision_updates_recovery_and_binding(tmp_path):
    from copy import deepcopy
    from context_models.contracts import ContextIntegrityError
    from context_models.tennis import tennis_features
    from test_tennis_context_features import native_row, stored, NOW
    original, ev = base(), event()
    observations = stored(tmp_path, [native_row(sets=(3, 2)), native_row("2", "2", hours=12)])
    before = tennis_features(ev, observations, original, cutoff=NOW)
    saved = deepcopy((observations, original, ev, before))
    fitted = artifact(original, before, ev)
    first = apply_tennis_effect(original, before, fitted, event=ev)
    revised = {**ev, "scheduled_start": "2026-09-09T22:00:00.000000Z", "schedule_revision": "s2"}
    with pytest.raises(ContextIntegrityError):
        apply_tennis_effect(original, before, fitted, event=revised)
    after = tennis_features(revised, observations, original, cutoff=NOW)
    assert after["reference_hash"] != before["reference_hash"]
    for side in ("a", "b"):
        assert after["values"][f"observed_recovery_exact_hours_{side}"] == before["values"][f"observed_recovery_exact_hours_{side}"] + 4
        assert after["values"][f"observed_recovery_minimum_hours_{side}"] == before["values"][f"observed_recovery_minimum_hours_{side}"] + 4
    rebuilt = apply_tennis_effect(original, after, fitted, event=revised)
    assert rebuilt["model_hash"] != first["model_hash"]
    assert result(original, after, fitted, revised)["role"] == "experimental"
    assert apply_tennis_effect(original, before, fitted, event=ev) == first
    assert (observations, original, ev, before) == saved


@pytest.mark.parametrize("part", ["params", "markets"])
def test_serve_baseline_changed_under_same_model_hash_needs_new_features(part):
    from context_models.contracts import ContextIntegrityError
    original = base(family="tennis:serve")
    frozen, fitted = features(original), artifact(original)
    changed = deepcopy(original)
    if part == "params":
        changed["params"]["hold_a"] = .81
        changed["markets"] = tennis_serve_markets(changed["params"])
    else:
        changed["markets"]["over_22.5_games"] += .001
    assert changed["model_hash"] == original["model_hash"]
    with pytest.raises(ContextIntegrityError, match="reference"):
        apply_tennis_effect(changed, frozen, fitted, event=event())
