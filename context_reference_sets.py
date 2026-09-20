"""Bounded reuse of exact immutable reference values, not supplied proof.

No schema/source/model decision is cached. A changed value changes the key;
mutable objects and str subclasses always reach the ordinary validator.
Two whole-value entries per operation bound small-history metadata. Larger
histories reuse bounded chunks; no count threshold disables all reuse and no
input is silently truncated. Mutable leaves still use the ordinary validator.
"""
from functools import lru_cache

from context_models.contracts import ContextContractError, require_digest


_CHUNK_SIZE = 8192


@lru_cache(maxsize=256)
def _validated_reference_chunk(values):
    # Actual immutable values, never a supplied digest/identity. Each retained
    # entry is bounded even when the whole history exceeds 500,000 receipts.
    for value in values:
        require_digest(value, "references")


def _large_reference_values(values):
    return (len(values) > 500_000
            and all(type(value) is str and len(value) == 64 for value in values))


def _check_large_digests(values, label):
    try:
        for start in range(0, len(values), _CHUNK_SIZE):
            _validated_reference_chunk(tuple(values[start:start + _CHUNK_SIZE]))
    except ContextContractError:
        # Preserve the public validator's field-specific error.
        for value in values:
            require_digest(value, label)
        raise


def _cacheable(values):
    return 128 <= len(values) <= 500_000 and all(type(value) is str for value in values)


def _check_sorted(values, label):
    for value in values:
        require_digest(value, label)
    if any(left >= right for left, right in zip(values, values[1:])):
        raise ContextContractError(f"{label} must be sorted and unique")
    return frozenset(values)


@lru_cache(maxsize=2)
def _sorted_reference_values(values):
    return _check_sorted(values, "references")


def sorted_reference_set(values, label):
    if _large_reference_values(values):
        _check_large_digests(values, label)
        if any(left >= right for left, right in zip(values, values[1:])):
            raise ContextContractError(f"{label} must be sorted and unique")
        return frozenset(values)
    if _cacheable(values):
        try:
            return _sorted_reference_values(tuple(values))
        except ContextContractError:
            pass  # Preserve the caller's exact cold error and field label.
    return _check_sorted(values, label)


def _check_unique(values):
    for value in values:
        require_digest(value, "context reference")
    if len(set(values)) != len(values):
        raise ContextContractError("context refs must be an explicit unique tuple")
    return tuple(sorted(values))


@lru_cache(maxsize=2)
def _unique_reference_values(values):
    return _check_unique(values)


def unique_reference_tuple(values):
    if _large_reference_values(values):
        _check_large_digests(values, "context reference")
        if all(left < right for left, right in zip(values, values[1:])):
            return tuple(values)
        if len(set(values)) != len(values):
            raise ContextContractError("context refs must be an explicit unique tuple")
        return tuple(sorted(values))
    if _cacheable(values):
        return _unique_reference_values(tuple(values))
    return _check_unique(values)
