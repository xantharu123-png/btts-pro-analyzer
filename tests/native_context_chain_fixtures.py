"""Historical native protocol DATA; never executed or a current-source approval.

These two verbatim Git blobs preserve the owners pinned by the frozen native
catalogues. Portable manifest/launcher tests do not qualify today's sources.
No Git lookup, source rewriting or production-admission override occurs here.
"""
import hashlib
from pathlib import Path


ROOT = Path(__file__).absolute().parents[1]
HISTORICAL = {
    # cac8db725b4c9ffac6bbcb4f81817d90da2823c9, before f3a0ebc lock slots.
    "tests/test_context_storage_corpus_consumer.py": (
        "native_context_chain_task54_cac8db7.py",
        "5a59f75d0a3093238031159a813ce81b6c633c63105cab0338ed376a7bac7649",
    ),
    # c5912a7, before bf22681 added the snapshot-reference tables.
    "context_storage_v2/inventory.py": (
        "native_context_inventory_c5912a7.py",
        "7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b",
    ),
}


def historical_source(name):
    """Return exact historical bytes only for the two reviewed fixture owners."""
    if name not in HISTORICAL:
        return (ROOT / name).read_bytes()
    filename, expected = HISTORICAL[name]
    raw = (ROOT / "tests" / "fixtures" / filename).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, "historical QA fixture changed"
    return raw
