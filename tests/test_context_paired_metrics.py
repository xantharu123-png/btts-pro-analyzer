"""Numerical D2 policy mechanics, not a real opened experiment or approval."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import importlib
import math

import pytest

from context_models.contracts import ContextContractError


START = datetime(2026, 9, 1, tzinfo=timezone.utc)
BLOCKS = tuple(((START+timedelta(days=i)).isoformat(), (START+timedelta(days=i+1)).isoformat())
               for i in range(3))


def sample(n=300, *, markets=("winner_a",), one_block=False):
    rows, distributions = [], []
    for i in range(n):
        # Deliberately synthetic calibrated bins, with a worse constant baseline.
        p = (.2, .4, .6, .8, .9)[(i//20) % 5]
        y = int(i % 20 < round(20*p))
        block = 0 if one_block else i % 3
        decision = (START+timedelta(days=block, seconds=i+1)).isoformat()
        identity = {"event_key": f"espn:tennis:ATP:match:{i}", "decision_at": decision, "block": f"test:{block}"}
        rows.extend({**identity, "market_key": m, "p_base": .5, "p_context": p, "outcome": y} for m in markets)
        distributions.append({**identity, "outcome_contract": "tennis-completed-winner-v1",
                              "base_logloss": -math.log(.5), "context_logloss": -math.log(p if y else 1-p),
                              "tail_policy": "bernoulli-exact-v1"})
    return tuple(rows), tuple(distributions)


def metric(rows=None, dist=None, **kw):
    if rows is None:
        rows, dist = sample()
    return importlib.import_module("context_models.validation").paired_cohort_metrics(
        rows, dist, target_markets=kw.pop("targets", ("winner_a",)), test_blocks=kw.pop("blocks", BLOCKS),
        outcome_contract=kw.pop("outcome_contract", "tennis-completed-winner-v1"),
        tail_policy=kw.pop("tail_policy", "bernoulli-exact-v1"), **kw)


def test_reports_one_chronological_sample_and_explicit_checks_without_approval():
    report = metric()
    assert report["event_count"] == 300
    assert report["base_brier"] == .25
    assert report["relative_improvement"] >= .02
    assert report["hac_lower"] > 0
    assert report["p_value"] <= .05
    assert report["context_logloss"] < report["base_logloss"]
    assert report["pre_multiplicity_failures"] == []
    assert "approved" not in report and "passed" not in report and "q_value" not in report
    assert all(item["event_count"] == 100 for item in report["blocks"])
    assert report["event_inventory"] == sorted(report["event_inventory"], key=lambda r: (r["decision_at"], r["event_key"]))


def test_199_events_with_900_markets_still_fails_event_minimum():
    markets = tuple(f"market{i:03}" for i in range(900))
    rows, dist = sample(199, markets=markets)
    report = metric(rows, dist, targets=markets)
    assert report["event_count"] == 199
    assert "insufficient-events" in report["pre_multiplicity_failures"]


def test_200_events_in_one_block_do_not_supply_three_blocks():
    report = metric(*sample(200, one_block=True))
    assert "unrepresented-test-block" in report["pre_multiplicity_failures"]


def test_worse_distribution_fails_on_the_same_events():
    rows, dist = sample()
    report = metric(rows, tuple({**r, "context_logloss": r["base_logloss"]+.001} for r in dist))
    assert "worse-distribution-logloss" in report["pre_multiplicity_failures"]


def test_equal_distribution_is_not_invented_improvement_or_a_failure():
    rows, dist = sample()
    report = metric(rows, tuple({**r, "context_logloss": r["base_logloss"]} for r in dist))
    assert report["distribution_delta"] == 0
    assert "worse-distribution-logloss" not in report["pre_multiplicity_failures"]


def test_log_density_may_be_negative():
    rows, dist = sample()
    report = metric(rows, tuple({**r, "base_logloss": -1., "context_logloss": -2.} for r in dist))
    assert report["base_logloss"] == -1. and report["context_logloss"] == -2.


def test_missing_distribution_cannot_select_a_second_better_subset():
    rows, dist = sample()
    with pytest.raises(ContextContractError, match="same exact events"):
        metric(rows, dist[:-1])


def test_missing_target_must_be_intersected_before_calling_final_cohort_metrics():
    rows, dist = sample(markets=("a", "b"))
    with pytest.raises(ContextContractError, match="incomplete target"):
        metric(rows[:-1], dist, targets=("a", "b"))


@pytest.mark.parametrize("field,value", [("decision_at", "2026-09-01T00:02:00Z"), ("block", "test:1"),
    ("outcome_contract", "different-v1"), ("tail_policy", "epsilon-v1"), ("base_logloss", float("inf")),
    ("context_logloss", True), ("context_logloss", "0.5"), ("extra", "odds")])
def test_distribution_mismatch_and_malformed_values_fail_not_excluded(field, value):
    rows, dist = sample()
    with pytest.raises(ContextContractError):
        metric(rows, ({**dist[0], field: value},)+dist[1:])


def test_duplicate_distribution_row_fails_even_if_identical():
    rows, dist = sample()
    with pytest.raises(ContextContractError, match="duplicate"):
        metric(rows, dist+(dist[0],))


@pytest.mark.parametrize("blocks", [BLOCKS[:2], BLOCKS[::-1], (BLOCKS[0], BLOCKS[0], BLOCKS[2]),
    ((BLOCKS[0][0], BLOCKS[0][1]), (BLOCKS[2][0], BLOCKS[2][1]), ("2026-09-04T00:00:00Z", "2026-09-05T00:00:00Z"))])
def test_invalid_frozen_block_inventory_is_an_error_even_with_no_events(blocks):
    with pytest.raises(ContextContractError):
        metric((), (), blocks=blocks)


def test_block_label_is_recomputed_from_actual_decision():
    rows, dist = sample()
    rows = ({**rows[0], "block": "test:2"},)+rows[1:]
    dist = ({**dist[0], "block": "test:2"},)+dist[1:]
    with pytest.raises(ContextContractError, match="decision"):
        metric(rows, dist)


def test_empty_cohort_reports_insufficient_data_without_fake_zero_losses():
    report = metric((), ())
    assert report["event_count"] == 0
    assert report["p_value"] == 1.
    assert report["base_brier"] is report["relative_improvement"] is report["context_logloss"] is None
    assert "insufficient-events" in report["pre_multiplicity_failures"]


def test_sparse_constant_calibration_cannot_certify_a_market():
    rows, dist = sample()
    rows = tuple({**r, "p_context": .5} for r in rows)
    report = metric(rows, dist)
    assert "market-calibration:winner_a" in report["pre_multiplicity_failures"]
    assert report["calibration"]["winner_a"]["supported_bins"] == 1


def test_metrics_order_and_output_mutation_do_not_change_input():
    rows, dist = sample()
    old = deepcopy((rows, dist))
    report = metric(rows, dist)
    assert report == metric(tuple(reversed(rows)), tuple(reversed(dist)))
    report["event_inventory"][0]["block"] = "changed"
    assert old == (rows, dist)


def test_zero_baseline_loss_has_no_relative_improvement_denominator():
    rows, dist = sample()
    report = metric(tuple({**r, "p_base": r["outcome"]} for r in rows), dist)
    assert report["base_brier"] == 0
    assert report["relative_improvement"] is None
    assert "insufficient-relative-improvement" in report["pre_multiplicity_failures"]


def test_1_99_percent_is_not_rounded_up_to_the_two_percent_requirement():
    rows, dist = sample()
    distance = math.sqrt(.25*(1-.0199))
    report = metric(tuple({**r, "p_context": 1-distance if r["outcome"] else distance} for r in rows), dist)
    assert report["relative_improvement"] == pytest.approx(.0199)
    assert "insufficient-relative-improvement" in report["pre_multiplicity_failures"]


def test_invalid_clock_representation_is_not_a_source_receipt():
    rows, dist = sample()
    with pytest.raises(ContextContractError):
        metric(rows, ({**dist[0], "decision_at": START},)+dist[1:])


def test_calibration_is_exact_existing_diagnostic_and_threshold():
    from challenge_engine import _calibration_diagnostics, adaptive_bin_threshold
    rows, dist = sample()
    report = metric(rows, dist)
    diag = _calibration_diagnostics([r["p_context"] for r in rows], [r["outcome"] for r in rows])
    result = report["calibration"]["winner_a"]
    assert (result["ece"], result["supported_bins"], result["min_bin_size"], result["worst_deviation"],
            result["worst_bin_size"], result["worst_mean"]) == pytest.approx(diag)
    assert result["adaptive_threshold"] == adaptive_bin_threshold(diag[5], diag[4])


@pytest.mark.parametrize("base,context", [(2**53, 2**53+1), (2**53, 2**53-1),
                                           (float(2**53), 2**53+1), (2**53+1, float(2**53))])
def test_paired_logloss_preserves_exact_json_integer_and_float_difference(base, context):
    rows, dist = sample()
    report = metric(rows, tuple({**d, "base_logloss": base, "context_logloss": context} for d in dist))
    expected = float(Fraction(context)-Fraction(base))
    assert report["distribution_delta"] == expected
    assert all(b["distribution_delta"] == expected for b in report["blocks"])
    assert ("worse-distribution-logloss" in report["pre_multiplicity_failures"]) is (expected > 0)


def test_large_absolute_losses_cannot_round_away_a_real_paired_worsening():
    rows, dist = sample()
    dist = tuple({**d, "base_logloss": 1e16, "context_logloss": 1e16+(2. if i < 150 else 0.)}
                 for i, d in enumerate(dist))
    report = metric(rows, dist)
    assert report["distribution_delta"] == 1.
    assert all(b["distribution_delta"] == 1. for b in report["blocks"])
    assert "worse-distribution-logloss" in report["pre_multiplicity_failures"]


@pytest.mark.parametrize("direction", [-1, 1])
def test_nonzero_paired_difference_below_float_range_is_not_equal_quality(direction):
    rows, dist = sample()
    dist = tuple({**d, "base_logloss": 0., "context_logloss": direction*math.ulp(0.) if i == 0 else 0.}
                 for i, d in enumerate(dist))
    with pytest.raises(ContextContractError, match="representable"):
        metric(rows, dist)


def test_identical_subnormal_loss_means_do_not_underflow_before_summing():
    rows, dist = sample()
    report = metric(rows, tuple({**d, "base_logloss": math.ulp(0.), "context_logloss": math.ulp(0.)} for d in dist))
    assert report["base_logloss"] == report["context_logloss"] == math.ulp(0.)
    assert report["distribution_delta"] == 0.
