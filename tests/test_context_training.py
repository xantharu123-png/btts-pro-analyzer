"""D1 split mechanics only; synthetic rows cannot certify source availability."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from test_context_contracts import training_row


def date(day, hour=0):
    return datetime(2026, 9, day, hour, tzinfo=timezone.utc)


def row(number=1, decision=None, result=None, **changes):
    return {**training_row(), "event_key": f"espn:tennis:{number}",
            "decision_at": canonical_timestamp(decision or date(1)),
            "result_observed_at": canonical_timestamp(result or date(1, 12)), **changes}


def split(rows, **changes):
    kwargs = {"train_end": date(2), "tune_end": date(5),
              "test_blocks": ((date(5), date(6)), (date(6), date(7)), (date(7), date(8))), **changes}
    return importlib.import_module("context_models.training").split_rows(rows, **kwargs)


def test_late_result_never_moves_an_early_event_into_tuning():
    value = row(result=date(4))
    result = split((value,))
    assert result["train"] == result["tune"] == ()
    assert result["late_results"] == (value,)


def test_all_boundaries_use_the_same_half_open_decision_contract():
    values = tuple(row(index, decision=start, result=start+timedelta(hours=1)) for index, start in enumerate(
        (date(1), date(2), date(5), date(6), date(7), date(8)), 1))
    result = split(values)
    for name, expected in zip(("train", "tune", "test:0", "test:1", "test:2", "outside"), values):
        assert result[name] == (expected,)
    assert result["late_results"] == result["retrospective"] == ()


@pytest.mark.parametrize("boundary,decision,expected", [(2, 1, "train"), (5, 2, "tune")])
def test_result_at_fitting_boundary_is_allowed_but_one_microsecond_later_is_not(boundary, decision, expected):
    assert split((row(decision=date(decision), result=date(boundary)),))[expected]
    assert split((row(decision=date(decision), result=date(boundary)+timedelta(microseconds=1)),))["late_results"]


@pytest.mark.parametrize("blocks", [(), ((date(5), date(6)),),
    ((date(5), date(7)), (date(6), date(8)), (date(8), date(9))),
    ((date(5), date(6)), (date(7), date(8)), (date(8), date(9))),
    ((date(5), date(5)), (date(5), date(6)), (date(6), date(7))),
    ((date(4), date(5)), (date(5), date(6)), (date(6), date(7))),
    [[date(5), date(6)], [date(6), date(7)], [date(7), date(8)]],
    ((date(5), date(6)), (date(6), date(7)), (date(7), datetime(2026, 9, 8)))])
def test_invalid_or_noncontiguous_final_blocks_are_rejected_even_for_empty_data(blocks):
    with pytest.raises(ContextContractError):
        split((), test_blocks=blocks)


@pytest.mark.parametrize("train_end,tune_end", [(date(5), date(2)), (date(2), date(2)),
    (datetime(2026, 9, 2), date(5)), (True, date(5))])
def test_cutoffs_are_valid_aware_and_strictly_ordered(train_end, tune_end):
    with pytest.raises(ContextContractError):
        split((), train_end=train_end, tune_end=tune_end)


def test_known_gap_before_final_window_is_outside_not_tuning():
    blocks = ((date(6), date(7)), (date(7), date(8)), (date(8), date(9)))
    value = row(decision=date(5), result=date(5, 12))
    assert split((value,), test_blocks=blocks)["outside"] == (value,)


def test_a_second_decision_revision_cannot_put_one_native_event_in_two_splits():
    with pytest.raises(ContextContractError, match="decision"):
        split((row(), row(decision=date(3), result=date(4))))


@pytest.mark.parametrize("mutation", [{}, {"target": 0}, {"base_hash": "e"*64}, {"offset": .6}])
def test_duplicate_or_contradictory_head_is_not_extra_training_evidence(mutation):
    with pytest.raises(ContextContractError, match="duplicate"):
        split((row(), row(**mutation)))


def test_all_heads_of_event_share_late_outcome_exclusion():
    values = (row(family="tennis:serve", head="hold_a", trials=2, target=1),
              row(family="tennis:serve", head="hold_b", trials=2, target=0, result=date(4)))
    result = split(values)
    assert len(result["late_results"]) == 2 and not result["train"]


@pytest.mark.parametrize("evidence,expected", [("prospective", "train"), ("archival_verified", "train"),
                                             ("retrospective", "retrospective")])
def test_evidence_class_is_never_inferred_from_nonempty_values(evidence, expected):
    value = row(evidence_class=evidence)
    assert split((value,))[expected] == (value,)


def test_one_retrospective_head_does_not_lend_a_causal_partial_training_event():
    values = (row(family="tennis:serve", head="hold_a", trials=2, target=1),
              row(family="tennis:serve", head="hold_b", trials=2, target=0, evidence_class="retrospective"))
    result = split(values)
    assert len(result["retrospective"]) == 2 and not result["train"]


@pytest.mark.parametrize("field", ["odds", "bookmaker", "minimumPrice", "unknown_column"])
def test_unknown_price_or_provider_columns_do_not_enter_normalized_rows(field):
    with pytest.raises(ContextContractError):
        split((row(**{field: .1}),))


def test_output_is_order_independent_and_detached_from_input():
    values = (row(2), row(1))
    frozen = deepcopy(values)
    output = split(values)
    assert output == split(tuple(reversed(values)))
    assert values == frozen
    output["train"][0]["x"][0] = 99
    assert values == frozen


def test_splitting_does_not_fake_cross_provider_alias_proof():
    # Canonical identity assembly is a separate mandatory D1 input boundary.
    # No name/kickoff guess or de-duplication under one provider is claimed here.
    values = (row(), row(event_key="second:tennis:1"))
    assert len(split(values)["train"]) == 2


def test_mutable_iterable_is_not_a_frozen_training_inventory():
    with pytest.raises(ContextContractError):
        split([row()])
