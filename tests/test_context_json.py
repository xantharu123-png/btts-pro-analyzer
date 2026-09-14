"""Serialization memoization cannot change identities or authorize inputs."""
from copy import deepcopy
import hashlib
import random

import pytest

from context_json import _encoded_references, canonical_context_bytes, context_digest
from model_artifacts import canonical_bytes


def refs(n=160):
    return [f"{i:064x}" for i in range(n)]


@pytest.mark.parametrize("field", ["observation_refs", "context_refs"])
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("extra", [None, -0.0, 1e-250, {"ä": [True, None, "\"\\\n"]}, [1, 2.5]])
def test_cached_json_is_byte_identical(field, wrapped, extra):
    payload = {field: refs(), "z": extra, "a": "Ö🎾"}
    if wrapped:
        payload = {"payload": payload, "key": "d" * 64}
    assert canonical_context_bytes(payload) == canonical_bytes(payload)
    assert context_digest(payload) == hashlib.sha256(canonical_bytes(payload)).hexdigest()


def test_cache_owns_full_immutable_values_and_never_list_identity():
    _encoded_references.cache_clear()
    payload = {"observation_refs": refs(), "x": 1}
    before = canonical_context_bytes(payload)
    assert _encoded_references.cache_info().misses == 1
    assert canonical_context_bytes(deepcopy(payload)) == before
    assert _encoded_references.cache_info().hits == 1
    payload["observation_refs"][-1] = "f" * 64
    after = canonical_context_bytes(payload)
    assert before != after == canonical_bytes(payload)
    payload["x"] = 2
    assert canonical_context_bytes(payload) == canonical_bytes(payload) != after
    for i in range(8):
        payload["observation_refs"][-1] = f"{1000 + i:064x}"
        canonical_context_bytes(payload)
    assert _encoded_references.cache_info().currsize <= 2


@pytest.mark.parametrize("value", ["é" * 64, "a" * 65, 1, None, True, [], "\"" * 64, "\\" * 64])
def test_nonstandard_reference_bytes_use_exact_standard_semantics(value):
    payload = {"observation_refs": refs() + [value], "x": 1}
    assert canonical_context_bytes(payload) == canonical_bytes(payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), object()])
def test_cached_reference_encoding_does_not_hide_invalid_other_values(value):
    payload = {"observation_refs": refs(), "invalid": value}
    with pytest.raises((TypeError, ValueError)):
        canonical_context_bytes(payload)


def test_random_reference_unions_preserve_old_snapshot_identity():
    from context_transport import _merged_refs
    rng = random.Random(2718)
    universe = refs(200)
    for _ in range(100):
        left = sorted(rng.sample(universe, rng.randint(0, 200)))
        right = sorted(rng.sample(universe, rng.randint(0, 200)))
        descriptor = rng.choice(universe)
        assert _merged_refs(left, right, descriptor) == tuple(sorted(set(left + right + [descriptor])))


@pytest.mark.parametrize("change", ["duplicate", "reverse", "bad_digest", "foreign_type"])
def test_reused_serialization_never_skips_reference_validation(change):
    import context_transport as transport
    from context_models.contracts import ContextContractError
    from test_context_transport import inputs
    args = inputs()
    args["observation_refs"] = sorted(set(args["observation_refs"] + refs()))
    payload = transport.calculate_context_payload(**args)
    canonical_context_bytes(payload)  # populate serialization only
    if change == "duplicate":
        payload["observation_refs"].append(payload["observation_refs"][-1])
    elif change == "reverse":
        payload["observation_refs"].reverse()
    elif change == "bad_digest":
        payload["observation_refs"][-1] = "Z" * 64
    else:
        payload["observation_refs"][-1] = 42
    with pytest.raises(ContextContractError):
        transport.context_payload_key(payload)
