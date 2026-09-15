"""Bounded reuse of exact immutable reference values, not supplied proof.

No schema/source/model decision is cached. A changed value changes the key;
mutable objects and str subclasses always reach the ordinary validator.
Two entries per operation bound retained metadata. Larger inputs remain
validatable through the original uncached path, never silently truncated.
"""
from functools import lru_cache

from context_models.contracts import ContextContractError, require_digest


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
    if _cacheable(values):
        return _unique_reference_values(tuple(values))
    return _check_unique(values)
