"""Verification-local immutable encoding cache, never a decoded inventory.

Only completed owning-selector outputs are stored. Pressure evicts/bypasses;
it does not change input admission or permit an incomplete causal history.
"""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
import json
import sqlite3

from context_models.contracts import canonical_timestamp
from context_runtime_inventory import VerifiedReceiptMapping
from model_artifacts import canonical_bytes
from runtime_paths import RuntimeArtifactTrustError


MAX_ENCODED_HISTORY_BYTES = 64 * 1024 * 1024
_MAX_ENTRIES = 32  # Also bound metadata for zero-byte (empty) histories.
_selected_receipt_witness = ContextVar("_selected_receipt_witness", default=None)


def _plain_json(value):
    """Eligibility, not schema acceptance: aliases must go to the cold owner."""
    kind = type(value)
    if kind is dict:
        return all(type(key) is str and _plain_json(item) for key, item in value.items())
    if kind is list:
        return all(_plain_json(item) for item in value)
    return kind in (str, int, float, bool, type(None))


class _SelectedReceiptScope:
    """Non-owning cursor. No entry, bytes, decoded rows or iterators survive."""
    __slots__ = ("_cache", "_receipts", "_key", "_serial", "_ordinal", "_active")

    def __init__(self, cache, receipts, key, serial):
        self._cache, self._receipts = cache, receipts
        self._key, self._serial = key, serial
        self._ordinal, self._active = 0, True

    def _matches(self, row):
        if not self._active:
            return False
        cache = self._cache
        cache._check_selected_proof(self._receipts)
        raw = None
        if self._serial is not None and cache._seals.get(self._key) == self._serial:
            # Only one row reference, never a whole-entry local alias across
            # canonicalization (which may evict/replace the current entry).
            if self._key in cache._entries and self._ordinal < len(cache._entries[self._key][0]):
                raw = cache._entries[self._key][0][self._ordinal]
                self._ordinal += 1
        matched = False
        if raw is not None:
            try:
                matched = _plain_json(row) and canonical_bytes(row) == raw
            except (TypeError, ValueError, OverflowError, RecursionError):
                pass  # The unchanged owner decides acceptance of every miss.
        cache._check_selected_proof(self._receipts)
        return (matched and self._key in cache._entries
                and cache._seals.get(self._key) == self._serial)


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
        self._proof = receipts._validation_stamp
        self._basis_cutoffs = None
        self._max_bytes = max_bytes
        self._invalid = False
        self._entries = OrderedDict()
        self._seals = {}
        self._serial = 0
        self._bytes = self._pending_bytes = 0
        self._counters = dict(hits=0, covering_hits=0, misses=0, stores=0, evictions=0, bypasses=0, peak_bytes=0)

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
                    or (self._proof is not None and receipts._validation_stamp != self._proof)
                    or self._schema_versions() != self._schema):
                raise RuntimeArtifactTrustError("encoded history inventory changed during verification")
        except (RuntimeArtifactTrustError, sqlite3.Error):
            self._invalid = True
            self._entries.clear()
            self._seals.clear()
            self._bytes = self._pending_bytes = 0
            raise

    def _check_selected_proof(self, receipts):
        try:
            if self._proof is None or receipts._validation_stamp is None:
                # A missing/unfinished proof does not check fresh schemas.
                self._check(receipts)
                receipts._check_validation()
                if receipts._validation_stamp != self._proof:
                    raise RuntimeArtifactTrustError("encoded history inventory changed during verification")
            else:
                # The completed inventory owns the fresh generation, write
                # and main/temp schema check. Never authorize from a stored
                # tuple without first asking that exact proof's owner.
                receipts._check_validation()
                if (self._invalid or receipts is not self._receipts
                        or receipts._validation_stamp != self._proof
                        or self._proof != (self._generation, self._changes, *self._schema)
                        or receipts._connection.total_changes != self._changes):
                    raise RuntimeArtifactTrustError("encoded history inventory changed during verification")
                receipts._check_transaction()
        except (RuntimeArtifactTrustError, sqlite3.Error):
            self._invalid = True
            self._entries.clear()
            self._seals.clear()
            self._bytes = self._pending_bytes = 0
            raise

    @contextmanager
    def _selected_receipt_scope(self, receipts, *, cutoff, tour):
        self._check_selected_proof(receipts)
        from context_sources.tennis_status import select_tennis_observations
        select_tennis_observations((), cutoff=cutoff, tour=tour)
        decision = canonical_timestamp(cutoff)
        key = (decision, tour)
        if key not in self._entries:
            key = min((key for key in self._entries if key[1] == tour and key[0] > decision), default=None)
        serial = self._seals.get(key) if self._proof is not None else None
        witness = _SelectedReceiptScope(self, receipts, key, serial)
        token = _selected_receipt_witness.set(witness)
        try:
            yield witness
        finally:
            witness._active = False
            _selected_receipt_witness.reset(token)
            self._check_selected_proof(receipts)  # Also empty histories / final row / exceptions.

    def _plan_bases(self, receipts, cutoffs):
        """Keep only bounded cutoff metadata, never caller-granted proof/data."""
        self._check(receipts)
        receipts._check_validation()
        if receipts._validation_stamp is None:
            return False
        from context_sources.tennis_status import select_tennis_observations
        planned = {}
        for tour, cutoff in cutoffs.items():
            select_tennis_observations((), cutoff=cutoff, tour=tour)
            planned[tour] = canonical_timestamp(cutoff)
        self._proof = receipts._validation_stamp
        self._basis_cutoffs = planned
        return True

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

    def _lookup_covering(self, receipts, *, cutoff, tour, max_bytes):
        """Derive an earlier prefix only from a completed, still-proved pool."""
        self._check(receipts)
        receipts._check_validation()
        if receipts._validation_stamp is None:
            return None  # Never validated: only the full cold path is permitted.
        decision = canonical_timestamp(cutoff)
        key = min((key for key in self._entries if key[1] == tour and key[0] > decision), default=None)
        if key is None:
            return None
        encoded, _ = self._entries[key]
        self._entries.move_to_end(key)
        history, used = [], 0
        for raw in encoded:
            self._check(receipts)
            row = json.loads(raw)
            self._check(receipts)
            # Completed owning outputs are sorted by (observed_at, digest),
            # and their evidence fields depend on receipt clocks, not cutoff.
            if row["observed_at"] > decision:
                break
            used += len(raw)  # Admit only the complete retained earlier history.
            if max_bytes is not None and used > max_bytes:
                raise RuntimeArtifactTrustError("complete Tennis history exceeds canonical input budget")
            history.append(row)
        self._check(receipts)  # Required even for an empty covering entry/result.
        self._counters["covering_hits"] += 1
        return tuple(history)

    def _evict(self):
        key, (_, size) = self._entries.popitem(last=False)
        self._seals.pop(key, None)
        self._bytes -= size
        self._counters["evictions"] += 1

    def _store(self, receipts, history, *, cutoff, tour):
        self._check(receipts)
        key = canonical_timestamp(cutoff), tour
        if self._basis_cutoffs is not None and self._basis_cutoffs.get(tour) != key[0]:
            # A missing/evicted/oversized maximum falls back to complete cold
            # selection. Retaining its prefixes would recreate the old thrash.
            return
        if self._max_bytes == 0:
            self._counters["bypasses"] += 1
            return
        # Replacement must remove both the former bytes and their proof.
        previous = self._entries.pop(key, None)
        if previous is not None:
            self._bytes -= previous[1]
        self._seals.pop(key, None)
        del previous
        pending = []
        sealable = True
        from context_sources.tennis_status import _validate_selected_tennis_receipt_cold
        try:
            for row in history:
                self._check(receipts)
                try:
                    plain = _plain_json(row)
                except RecursionError:
                    plain = False
                if not plain:
                    _validate_selected_tennis_receipt_cold(row)
                    sealable = False
                encoded = canonical_bytes(row)  # One replay-row work buffer, not a giant tuple dump.
                self._check(receipts)  # Also guard the final/oversized row before bypass.
                needed = self._pending_bytes + len(encoded)
                if needed > self._max_bytes:
                    self._counters["bypasses"] += 1
                    return
                while self._bytes + needed > self._max_bytes:
                    self._evict()
                if plain:
                    _validate_selected_tennis_receipt_cold(json.loads(encoded))
                self._check(receipts)
                pending.append(encoded)
                self._pending_bytes = needed
                self._counters["peak_bytes"] = max(self._counters["peak_bytes"], self._bytes + needed)
            self._check(receipts)
            while len(self._entries) >= _MAX_ENTRIES:
                self._evict()
            self._entries[key] = (tuple(pending), self._pending_bytes)
            self._serial += 1
            if sealable and self._proof is not None:
                self._seals[key] = self._serial
            self._bytes += self._pending_bytes
            self._counters["stores"] += 1
        finally:
            self._pending_bytes = 0  # Failed/oversized builds never publish a partial entry.
