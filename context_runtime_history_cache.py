"""Verification-local immutable encoding cache, never a decoded inventory.

Only completed owning-selector outputs are stored. Pressure evicts/bypasses;
it does not change input admission or permit an incomplete causal history.
"""
from collections import OrderedDict
import json
import sqlite3

from context_models.contracts import canonical_timestamp
from context_runtime_inventory import VerifiedReceiptMapping
from model_artifacts import canonical_bytes
from runtime_paths import RuntimeArtifactTrustError


MAX_ENCODED_HISTORY_BYTES = 64 * 1024 * 1024
_MAX_ENTRIES = 32  # Also bound metadata for zero-byte (empty) histories.


class EncodedHistoryCache:
    def __init__(self, receipts, *, max_bytes=MAX_ENCODED_HISTORY_BYTES):
        if not isinstance(receipts, VerifiedReceiptMapping):
            raise RuntimeArtifactTrustError("encoded history requires its verified receipt inventory")
        receipts._check_transaction()
        if type(max_bytes) is not int or max_bytes < 0:
            raise RuntimeArtifactTrustError("invalid encoded history cache budget")
        self._receipts = receipts
        self._generation = receipts._connection.transaction_generation
        self._changes = receipts._connection.total_changes
        self._schema = self._schema_versions()
        self._max_bytes = max_bytes
        self._invalid = False
        self._entries = OrderedDict()
        self._bytes = self._pending_bytes = 0
        self._counters = dict(hits=0, misses=0, stores=0, evictions=0, bypasses=0, peak_bytes=0)

    @property
    def stats(self):
        """Private diagnostic counters, never added to the public D4 report."""
        return {**self._counters, "bytes": self._bytes, "pending_bytes": self._pending_bytes,
                "entries": len(self._entries), "entry_bytes": tuple(size for _, size in self._entries.values()),
                "max_bytes": self._max_bytes}

    def _schema_versions(self):
        # DDL does not increment total_changes. Temp objects can shadow the
        # inventory's unqualified table names, so pin both visible schemas.
        connection = self._receipts._connection
        return (connection.execute("PRAGMA main.schema_version").fetchone()[0],
                connection.execute("PRAGMA temp.schema_version").fetchone()[0])

    def _check(self, receipts):
        try:
            receipts._check_transaction()
            if (self._invalid or receipts is not self._receipts
                    or receipts._connection.transaction_generation != self._generation
                    or receipts._connection.total_changes != self._changes
                    or self._schema_versions() != self._schema):
                raise RuntimeArtifactTrustError("encoded history inventory changed during verification")
        except (RuntimeArtifactTrustError, sqlite3.Error):
            self._invalid = True
            self._entries.clear()
            self._bytes = self._pending_bytes = 0
            raise

    def _lookup(self, receipts, *, cutoff, tour, max_bytes):
        self._check(receipts)
        key = canonical_timestamp(cutoff), tour
        stored = self._entries.get(key)
        if stored is None:
            self._counters["misses"] += 1
            return None
        self._counters["hits"] += 1
        encoded, size = stored
        if max_bytes is not None and size > max_bytes:
            raise RuntimeArtifactTrustError("complete Tennis history exceeds canonical input budget")
        self._entries.move_to_end(key)
        # These are our exact completed canonical outputs, not newly trusted
        # database bytes. Every consumer owns fresh nested dictionaries/lists.
        result = tuple(json.loads(row) for row in encoded)
        self._check(receipts)
        return result

    def _evict(self):
        _, (_, size) = self._entries.popitem(last=False)
        self._bytes -= size
        self._counters["evictions"] += 1

    def _store(self, receipts, history, *, cutoff, tour):
        self._check(receipts)
        if self._max_bytes == 0:
            self._counters["bypasses"] += 1
            return
        pending = []
        try:
            for row in history:
                self._check(receipts)
                encoded = canonical_bytes(row)  # One replay-row work buffer, not a giant tuple dump.
                needed = self._pending_bytes + len(encoded)
                if needed > self._max_bytes:
                    self._counters["bypasses"] += 1
                    return
                while self._bytes + needed > self._max_bytes:
                    self._evict()
                pending.append(encoded)
                self._pending_bytes = needed
                self._counters["peak_bytes"] = max(self._counters["peak_bytes"], self._bytes + needed)
            self._check(receipts)
            while len(self._entries) >= _MAX_ENTRIES:
                self._evict()
            key = canonical_timestamp(cutoff), tour
            self._entries[key] = (tuple(pending), self._pending_bytes)
            self._bytes += self._pending_bytes
            self._counters["stores"] += 1
        finally:
            self._pending_bytes = 0  # Failed/oversized builds never publish a partial entry.
