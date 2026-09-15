"""Byte-identical JSON encoding of repeated large context reference lists.

This caches serialization only, never schema validation, source evidence or
approval. The cache key contains every actual immutable string, not a claimed
digest or mutable list identity. Public canonical JSON remains the oracle.
"""
from functools import lru_cache
from copy import deepcopy
import hashlib

from model_artifacts import canonical_bytes as _canonical_bytes


@lru_cache(maxsize=2)
def _encoded_references(values: tuple[str, ...]) -> bytes:
    return _canonical_bytes(values)


def canonical_context_bytes(value: object) -> bytes:
    if type(value) is not dict or any(type(key) is not str for key in value):
        return _canonical_bytes(value)
    cached = {}
    for name in ("observation_refs", "context_refs"):
        refs = value.get(name)
        # Bound both entry count and individual bytes. Arbitrary strings or
        # non-reference JSON always use the original encoder unchanged.
        if (type(refs) is list and 128 <= len(refs) <= 500_000
                and all(type(ref) is str and len(ref) == 64 and ref.isascii() for ref in refs)):
            cached[name] = _encoded_references(tuple(refs))
    if not cached:
        if set(value) == {"key", "payload"} and type(value["payload"]) is dict:
            return (b'{"key":' + _canonical_bytes(value["key"]) + b',"payload":'
                    + canonical_context_bytes(value["payload"]) + b'}')
        return _canonical_bytes(value)
    # Same sorted keys, escaping, separators, finite-number behavior and UTF-8
    # as canonical_bytes. No raw external JSON is accepted or substituted.
    return b'{' + b','.join(
        _canonical_bytes(key) + b':' + (cached[key] if key in cached else _canonical_bytes(value[key]))
        for key in sorted(value)
    ) + b'}'


def context_digest(value: object) -> str:
    return hashlib.sha256(canonical_context_bytes(value)).hexdigest()


def copy_context_payload(value):
    """Detach a payload without visiting each immutable reference leaf twice."""
    if type(value) is not dict:
        return deepcopy(value)
    refs = value.get("observation_refs")
    if type(refs) is not list or not all(type(ref) is str for ref in refs):
        return deepcopy(value)
    # Only the list is mutable. Every other field still receives a deep copy.
    copied = deepcopy({key: item for key, item in value.items() if key != "observation_refs"})
    copied["observation_refs"] = refs.copy()
    return copied
