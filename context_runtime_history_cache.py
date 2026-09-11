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
from context_runtime_original_projection import _OriginalQuery
from model_artifacts import canonical_bytes
from runtime_paths import RuntimeArtifactTrustError


MAX_ENCODED_HISTORY_BYTES = 64 * 1024 * 1024
_MAX_ENTRIES = 32  # Also bound metadata for zero-byte (empty) histories.
_MAX_ORIGINAL_QUERIES = 30  # Reserve the two possible tour entries.
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
        self._owned = {}  # key -> (completed entry serial, charged marker bytes)
        self._queries = OrderedDict()
        self._original_cutoffs = {}
        self._planning_bytes = self._metadata_bytes = 0
        self._building = self._build_cancelled = False
        self._serial = 0
        self._bytes = self._pending_bytes = 0
        self._counters = dict(hits=0, covering_hits=0, misses=0, stores=0, evictions=0, bypasses=0, peak_bytes=0)

    @property
    def stats(self):
        """Private diagnostic counters, never added to the public D4 report."""
        return {**self._counters, "bytes": self._bytes, "pending_bytes": self._pending_bytes,
                "entries": len(self._entries), "entry_bytes": tuple(size for _, size in self._entries.values()),
                "metadata_slots": len(self._entries) + len(self._queries),
                "metadata_bytes": self._metadata_bytes,
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
            self._clear_original_metadata()
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
            self._clear_original_metadata()
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

    def _clear_original_metadata(self):
        self._owned.clear()
        self._queries.clear()
        self._original_cutoffs.clear()
        self._basis_cutoffs = None
        self._metadata_bytes = self._planning_bytes = 0

    def _charge_metadata(self, size):
        self._metadata_bytes += size
        self._bytes += size
        self._counters["peak_bytes"] = max(self._counters["peak_bytes"], self._bytes + self._pending_bytes)

    def _drop_query(self, key):
        self._charge_metadata(-self._queries.pop(key).charge)

    def _drop_planning(self):
        self._original_cutoffs.clear()
        self._basis_cutoffs = None
        self._charge_metadata(-self._planning_bytes)
        self._planning_bytes = 0

    def _drop_owned(self, key):
        marker = self._owned.pop(key, None)
        if marker is not None:
            self._charge_metadata(-marker[1])
        for query_key in tuple(self._queries):
            if self._queries[query_key].basis == key:
                self._drop_query(query_key)

    def _make_room(self, needed):
        # Optional queries lose to an otherwise fitting history. Planning is
        # also optional; dropping it cancels any remaining tour preparation.
        while self._bytes + needed > self._max_bytes and self._queries:
            self._drop_query(next(reversed(self._queries)))
        if self._bytes + needed > self._max_bytes and self._planning_bytes:
            self._drop_planning()
        while self._bytes + needed > self._max_bytes and self._entries:
            self._evict()
        return self._bytes + needed <= self._max_bytes

    def _plan_original_publications(self, artifacts, created_at):
        """Keep publication/key work locals out of the subsequent basis frame."""
        from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, validate_original_publication
        for ref, envelope in artifacts.items():
            if envelope["kind"] != ORIGINAL_ARTIFACT_KIND:
                continue
            publication = validate_original_publication(envelope["payload"], created_at=created_at[ref])
            origin = publication["origin"]
            tour, cutoff = origin["event"]["tour"], origin["cutoff"]
            # Both maxima are discovered even after optional query space
            # is exhausted. There are only two validated tour names.
            if tour not in self._original_cutoffs:
                charge = 128  # Two canonical fixed-width tour/cutoff maps.
                while self._bytes + charge > self._max_bytes and self._queries:
                    self._drop_query(next(reversed(self._queries)))
                if self._bytes + charge <= self._max_bytes:
                    self._original_cutoffs[tour] = cutoff
                    self._planning_bytes += charge
                    self._charge_metadata(charge)
            elif cutoff > self._original_cutoffs[tour]:
                self._original_cutoffs[tour] = cutoff
            key = origin["event"]["event_key"], cutoff, tour
            if key in self._queries:
                continue
            charge = _OriginalQuery.reservation(key, self._max_bytes, self._serial + 1)
            if (len(self._queries) < min(_MAX_ORIGINAL_QUERIES, _MAX_ENTRIES - max(2, len(self._entries)))
                    and self._bytes + charge <= self._max_bytes):
                self._queries[key] = _OriginalQuery(key, charge)
                self._charge_metadata(charge)

    def _prepare_originals(self, receipts, artifacts, created_at):
        """Own publication planning; callers provide neither keys nor proof."""
        from datetime import datetime
        self._check_selected_proof(receipts)
        if self._proof is None:
            return
        try:
            self._plan_original_publications(artifacts, created_at)
            self._check_selected_proof(receipts)
            self._basis_cutoffs = dict(self._original_cutoffs)
            # The second dictionary contains the same bounded scalar cutoffs;
            # the planning reservation includes its representation too.
            while self._original_cutoffs:
                tour = next(iter(self._original_cutoffs))
                cutoff = self._original_cutoffs[tour]
                self._prepare_original_basis(receipts, cutoff=datetime.fromisoformat(cutoff), tour=tour)
                self._original_cutoffs.pop(tour, None)
        except BaseException:
            # Failed planning/preparation publishes no original authority.
            for key in tuple(self._owned):
                self._drop_owned(key)
            for key in tuple(self._queries):
                self._drop_query(key)
            self._drop_planning()
            raise

    def _prepare_original_basis(self, receipts, *, cutoff, tour):
        """Only this fixed cold-owner + whole-seal operation grants completeness."""
        from context_runtime_tennis import _cold_replay_history, _HistoryBasisOverflow
        self._check_selected_proof(receipts)
        key = canonical_timestamp(cutoff), tour
        if self._proof is None or self._original_cutoffs.get(tour) != key[0]:
            return
        try:
            try:
                history = _cold_replay_history(receipts, cutoff=cutoff, tour=tour,
                    max_bytes=None, basis_max_bytes=self._max_bytes)
            except _HistoryBasisOverflow:
                self._check_selected_proof(receipts)
                self._counters["bypasses"] += 1
                return
            serial = self._store_encoded(receipts, history, cutoff=cutoff, tour=tour)
            del history
            self._check_selected_proof(receipts)
            if serial is None or self._seals.get(key) != serial or key not in self._entries:
                return
            charge = len(canonical_bytes((key, serial))) + 32
            # No history eviction to buy a marker. If even the small marker
            # cannot fit, keep the row seal only and cold-replay originals.
            while self._bytes + charge > self._max_bytes and self._queries:
                self._drop_query(next(reversed(self._queries)))
            if self._bytes + charge > self._max_bytes:
                return
            self._check_selected_proof(receipts)
            if self._seals.get(key) != serial or key not in self._entries:
                return
            self._owned[key] = serial, charge
            self._charge_metadata(charge)
            for query_key in tuple(self._queries):
                query = self._queries[query_key]
                if query_key[2] != tour:
                    continue
                needed = _OriginalQuery.reservation(query_key, self._max_bytes, serial)
                if self._bytes + max(0, needed-query.charge) > self._max_bytes:
                    self._drop_query(query_key)
                    continue
                self._charge_metadata(needed-query.charge)
                query.charge = needed
                query.basis, query.serial = key, serial
            self._check_selected_proof(receipts)
            if self._seals.get(key) != serial or key not in self._entries:
                self._drop_owned(key)
        except BaseException:
            self._drop_owned(key)
            raise
        finally:
            # A draft never survives an unsuccessful or interrupted seal.
            for query_key in tuple(self._queries):
                if query_key[2] == tour and self._queries[query_key].serial is None:
                    self._drop_query(query_key)

    def _owned_current(self, receipts, key, serial):
        self._check_selected_proof(receipts)
        marker = self._owned.get(key)
        return (serial is not None and key in self._entries and marker is not None
                and marker[0] == serial and self._seals.get(key) == serial)

    def _lookup_original_native(self, receipts, *, event_key, cutoff, tour, max_bytes):
        self._check_selected_proof(receipts)
        from context_sources.tennis_status import select_tennis_observations
        select_tennis_observations((), cutoff=cutoff, tour=tour)
        query = self._queries.get((event_key, canonical_timestamp(cutoff), tour))
        if query is None or not self._owned_current(receipts, query.basis, query.serial):
            return None
        key, serial = query.basis, query.serial
        if max_bytes is not None and query.prefix_bytes > max_bytes:
            raise RuntimeArtifactTrustError("complete Tennis history exceeds canonical input budget")
        count, ordinal, latest = query.count, query.ordinal, query.latest
        candidate = None
        if count == 1:
            if type(ordinal) is not int or not 0 <= ordinal < len(self._entries[key][0]):
                raise RuntimeArtifactTrustError("invalid original projection ordinal")
            candidate = json.loads(self._entries[key][0][ordinal])
            if not self._owned_current(receipts, key, serial):
                return None
            if candidate["event_key"] != event_key or candidate["observed_at"] != latest:
                raise RuntimeArtifactTrustError("invalid original projection candidate")
        elif count not in (0, 2):
            raise RuntimeArtifactTrustError("invalid original projection multiplicity")
        if not self._owned_current(receipts, key, serial):
            return None
        return count, candidate

    def _lookup_owned_original_history(self, receipts, *, cutoff, tour, max_bytes):
        """Pin the actual owned entry; an unowned exact key cannot shadow it."""
        self._check_selected_proof(receipts)
        from context_sources.tennis_status import select_tennis_observations
        select_tennis_observations((), cutoff=cutoff, tour=tour)
        decision = canonical_timestamp(cutoff)
        key = min((key for key in self._owned if key[1] == tour and key[0] >= decision), default=None)
        serial = self._owned[key][0] if key is not None else None
        if not self._owned_current(receipts, key, serial):
            return None
        history, used, ordinal = [], 0, 0
        while self._owned_current(receipts, key, serial):
            if ordinal == len(self._entries[key][0]):
                break
            # No whole-entry alias or iterator survives deserialization.
            raw = self._entries[key][0][ordinal]
            row = json.loads(raw)
            size = len(raw)
            del raw
            if not self._owned_current(receipts, key, serial):
                return None
            if row["observed_at"] > decision:
                break
            used += size
            if max_bytes is not None and used > max_bytes:
                raise RuntimeArtifactTrustError("complete Tennis history exceeds canonical input budget")
            history.append(row)
            ordinal += 1
        if not self._owned_current(receipts, key, serial):
            return None
        self._entries.move_to_end(key)
        return tuple(history)

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
        self._drop_owned(key)
        self._bytes -= size
        self._counters["evictions"] += 1

    def _drop_original_tour_queries(self, tour):
        """Release dropped key locals before another encoded build can start."""
        for query_key in tuple(self._queries):
            if query_key[2] == tour:
                self._drop_query(query_key)

    def _store(self, receipts, history, *, cutoff, tour):
        # A caller's valid rows cannot establish aggregate completeness.
        self._drop_original_tour_queries(tour)
        self._store_encoded(receipts, history, cutoff=cutoff, tour=tour)

    def _fold_original_queries(self, row, *, tour, size, ordinal):
        """Release loop-local drafts before the next pressure/accounting step."""
        for query in self._queries.values():
            if query.key[2] == tour:
                query.fold(row, size, ordinal)

    def _store_encoded(self, receipts, history, *, cutoff, tour):
        self._check(receipts)
        if self._building:
            # A reentrant replacement cannot share/reset the outer pending
            # byte pool. Cancel optional retention; owners still cold-fallback.
            self._build_cancelled = True
            return
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
        self._drop_owned(key)
        del previous
        pending = []
        sealable = True
        from context_sources.tennis_status import _validate_selected_tennis_receipt_cold
        self._building, self._build_cancelled = True, False
        try:
            for row in history:
                self._check(receipts)
                if self._build_cancelled:
                    return
                try:
                    plain = _plain_json(row)
                except RecursionError:
                    plain = False
                if not plain:
                    _validate_selected_tennis_receipt_cold(row)
                    sealable = False
                encoded = canonical_bytes(row)  # One replay-row work buffer, not a giant tuple dump.
                self._check(receipts)  # Also guard the final/oversized row before bypass.
                if self._build_cancelled:
                    return
                needed = self._pending_bytes + len(encoded)
                if needed > self._max_bytes:
                    self._counters["bypasses"] += 1
                    return
                self._make_room(needed)
                if plain:
                    validated = json.loads(encoded)
                    _validate_selected_tennis_receipt_cold(validated)
                    self._fold_original_queries(validated, tour=tour,
                        size=len(encoded), ordinal=len(pending))
                    del validated
                self._check(receipts)
                if self._build_cancelled:
                    return
                pending.append(encoded)
                self._pending_bytes = needed
                self._counters["peak_bytes"] = max(self._counters["peak_bytes"], self._bytes + needed)
            self._check(receipts)
            if self._build_cancelled:
                return
            while len(self._entries) + len(self._queries) >= _MAX_ENTRIES:
                self._evict()
            self._entries[key] = (tuple(pending), self._pending_bytes)
            self._serial += 1
            if sealable and self._proof is not None:
                self._seals[key] = self._serial
            self._bytes += self._pending_bytes
            self._counters["stores"] += 1
            return self._serial if sealable and self._proof is not None else None
        finally:
            self._pending_bytes = 0  # Failed/oversized builds never publish a partial entry.
            self._building = self._build_cancelled = False
