"""D2 paired-loss mechanics, not an empirical evaluation or activation."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib

import pytest

from context_models.contracts import ContextContractError


def module():
    return importlib.import_module("context_models.validation")


def row(key="m1", **changes):
    return {"event_key": "api-football:football:1", "market_key": key,
            "decision_at": "2026-09-01T12:00:00.000000Z", "block": "test:0",
            "p_base": .5, "p_context": .1, "outcome": 0, **changes}


def aggregate(rows, targets=("m1", "m2")):
    return module().aggregate_event_losses(rows, target_markets=targets)


def test_event_loss_is_not_the_loss_of_mean_probability():
    events = aggregate((row(), row("m2", p_context=.9)))
    assert len(events) == 1
    assert events[0] == {"event_key": "api-football:football:1", "block": "test:0",
                         "decision_at": "2026-09-01T12:00:00.000000Z",
                         "base_brier": .25, "context_brier": pytest.approx(.41), "advantage": pytest.approx(-.16)}


def test_missing_target_is_excluded_and_diagnosed_not_an_easier_paired_set():
    values = (row(),)
    assert aggregate(values) == ()
    report = module().event_loss_coverage(values, target_markets=("m1", "m2"))
    assert report["events"] == ()
    assert report["excluded"] == ({"event_key": row()["event_key"], "reason": "missing-target-markets",
                                     "missing": ["m2"]},)


@pytest.mark.parametrize("changes", [{}, {"outcome": 1}, {"p_context": .8}])
def test_duplicate_market_rows_are_rejected_before_any_exclusion(changes):
    with pytest.raises(ContextContractError, match="duplicate"):
        aggregate((row(), row(**changes)))


@pytest.mark.parametrize("changes", [{"decision_at": "2026-09-01T13:00:00Z"}, {"block": "test:1"}])
def test_one_native_event_cannot_cross_decisions_or_blocks(changes):
    with pytest.raises(ContextContractError):
        aggregate((row(), row("m2", **changes)))


@pytest.mark.parametrize("field,value", [("outcome", True), ("outcome", 0.0), ("outcome", -1), ("outcome", 2),
    ("p_base", True), ("p_base", "0.5"), ("p_base", float("nan")), ("p_base", 1.01),
    ("p_context", float("inf")), ("p_context", -.1), ("decision_at", "2026-09-01T12:00:00"),
    ("event_key", "same name"), ("odds", 1.9), ("provider_flag", True)])
def test_bad_rows_are_errors_not_dropped_to_improve_the_model(field, value):
    with pytest.raises(ContextContractError):
        aggregate((row(**{field: value}), row("m2")))


@pytest.mark.parametrize("targets", [(), ("m1", "m1"), ("m2", "m1"), ["m1", "m2"], ("odds",)])
def test_frozen_targets_require_canonical_unique_price_free_names(targets):
    with pytest.raises(ContextContractError):
        aggregate((), targets)


def test_unregistered_market_cannot_expand_or_shrink_the_frozen_policy():
    with pytest.raises(ContextContractError):
        aggregate((row(), row("m2"), row("m3")))


def test_market_count_does_not_multiply_independent_event_count():
    targets = tuple(f"m{i}" for i in range(9))
    values = tuple(row(market, event_key=f"api-football:football:{event}")
                   for event in range(1, 200) for market in targets)
    assert len(aggregate(values, targets)) == 199


def test_order_is_chronological_then_native_identity_and_market_reordering_is_inert():
    values = (row("m2", event_key="api-football:football:2"), row("m2"),
              row(event_key="api-football:football:2"), row())
    frozen = deepcopy(values)
    result = aggregate(values)
    assert result == aggregate(tuple(reversed(values)))
    assert result[0]["event_key"] == "api-football:football:1"
    assert values == frozen
    result[0]["advantage"] = 999
    assert values == frozen


def test_complete_binary_endpoint_predictions_are_valid_not_clipped():
    values = (row(p_base=0, p_context=1, outcome=1), row("m2", p_base=1, p_context=0, outcome=0))
    assert aggregate(values)[0]["advantage"] == 1.


def test_aware_timezone_representations_are_same_decision_instant():
    values = (row(), row("m2", decision_at="2026-09-01T14:00:00+02:00"))
    assert len(aggregate(values)) == 1


def test_unknown_native_aliases_are_not_falsely_resolved_by_this_cpu_layer():
    # D1 identity assembly must supply its frozen, verified native mapping.
    values = (row(), row("m2"), row(event_key="another:football:1"), row("m2", event_key="another:football:1"))
    assert len(aggregate(values)) == 2


@pytest.mark.parametrize("changes", [{"decision_at": datetime(2026, 9, 1, 12, tzinfo=timezone.utc)},
                                      {"event_key": "native:cricket:1"}, {"event_key": "native:unknown:1"}])
def test_closed_context_transport_does_not_expand_sport_or_json_contract(changes):
    with pytest.raises(ContextContractError):
        aggregate((row(**changes), row("m2", **changes)))
