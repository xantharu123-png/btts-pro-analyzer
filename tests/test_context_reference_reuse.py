"""Exact immutable values may reuse work, never caller identity or a hash claim."""
from copy import deepcopy
import pytest

from context_models.contracts import ContextContractError
from model_artifacts import canonical_bytes


def refs(n=256):
    return [f"{i:064x}" for i in range(n)]


def test_equal_values_reuse_validation_but_mutations_are_checked(monkeypatch):
    import context_reference_sets as module
    module._sorted_reference_values.cache_clear()
    calls = []
    real = module.require_digest
    def counted(value, label="digest"):
        calls.append(value)
        return real(value, label)
    monkeypatch.setattr(module, "require_digest", counted)
    original = refs()
    expected = frozenset(original)
    assert module.sorted_reference_set(original, "refs") == expected
    assert module.sorted_reference_set(deepcopy(original), "refs") == expected
    assert len(calls) == len(original)
    for replacement in ("Z" * 64, [], 12, True):
        changed = original.copy()
        changed[-1] = replacement
        with pytest.raises(ContextContractError):
            module.sorted_reference_set(changed, "refs")
    for changed in (original[::-1], original + [original[-1]]):
        with pytest.raises(ContextContractError):
            module.sorted_reference_set(changed, "refs")
    assert module.sorted_reference_set(original, "refs") == expected


def test_snapshot_ref_order_is_canonical_and_cache_is_bounded():
    import context_reference_sets as module
    module._unique_reference_values.cache_clear()
    for i in range(7):
        values = tuple(refs() + [f"{1000+i:064x}"])
        assert module.unique_reference_tuple(values[::-1]) == tuple(sorted(values))
    assert module._unique_reference_values.cache_info().currsize <= 2
    with pytest.raises(ContextContractError):
        module.unique_reference_tuple(tuple(refs() + [refs()[-1]]))


def test_string_subclasses_do_not_borrow_cached_plain_string_validation():
    from context_reference_sets import sorted_reference_set
    class Alias(str): pass
    values = refs()
    sorted_reference_set(values, "refs")
    values[-1] = Alias(values[-1])
    with pytest.raises(ContextContractError):
        sorted_reference_set(values, "refs")


def test_fast_payload_copy_is_deep_except_for_immutable_string_leaves():
    from context_json import copy_context_payload
    original = {"observation_refs": refs(), "nested": {"list": [1, {"x": 2}]}}
    result = copy_context_payload(original)
    assert canonical_bytes(result) == canonical_bytes(deepcopy(original))
    result["observation_refs"].clear()
    result["nested"]["list"][1]["x"] = 3
    assert original["observation_refs"] == refs()
    assert original["nested"]["list"][1]["x"] == 2


def test_payload_bytes_key_and_reference_equal_uncached_oracle(monkeypatch):
    import context_reference_sets as module
    import context_transport as transport
    from test_context_transport import inputs
    args = inputs()
    args["observation_refs"] = sorted(set(args["observation_refs"] + refs()))
    fast = transport.calculate_context_payload(**args)
    key = transport.context_payload_key(fast)
    reference = transport.context_consumer_reference(key, fast)
    monkeypatch.setattr(module, "_cacheable", lambda value: False)
    cold = transport.calculate_context_payload(**args)
    assert canonical_bytes(fast) == canonical_bytes(cold)
    assert transport.context_payload_key(cold) == key
    assert transport.context_consumer_reference(key, cold) == reference


def test_above_old_ceiling_keeps_complete_payload_key_and_reference_identical(monkeypatch):
    import context_json
    import context_reference_sets as module
    import context_transport as transport
    from test_context_transport import inputs
    args = inputs()
    args["observation_refs"] = sorted(set(args["observation_refs"] + refs(500_001)))
    fast = transport.calculate_context_payload(**args)
    key = transport.context_payload_key(fast)
    reference = transport.context_consumer_reference(key, fast)
    monkeypatch.setattr(module, "_large_reference_values", lambda value: False)
    monkeypatch.setattr(module, "_cacheable", lambda value: False)
    monkeypatch.setattr(context_json, "canonical_context_bytes", canonical_bytes)
    cold = transport.calculate_context_payload(**args)
    assert canonical_bytes(fast) == canonical_bytes(cold)
    assert transport.context_payload_key(cold) == key
    assert transport.context_consumer_reference(key, cold) == reference
