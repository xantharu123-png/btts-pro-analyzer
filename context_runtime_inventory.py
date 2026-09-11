"""Read-only, uncached views of a caller-held verification transaction.

Only identities are retained. Values are fresh owning-decoder results on each
lookup. A view is permanently invalid after its original transaction ends.
"""
from collections.abc import Mapping
import hashlib
import sqlite3

import context_observations
from context_models.contracts import ContextContractError, canonical_timestamp, digest, require_digest
from model_artifacts import ArtifactIntegrityError, _decode_object, _load_artifact, canonical_bytes
from runtime_paths import RuntimeArtifactTrustError
from context_runtime_transaction import TrackedConnection


# Capture only the internal methods, never an overridden instance callback.
_TRACKED_EXECUTE = TrackedConnection.execute
_TRACKED_CURSOR = TrackedConnection.cursor


class _TransactionMapping(Mapping):
    def __init__(self, connection):
        if not isinstance(connection, TrackedConnection):
            raise RuntimeArtifactTrustError("context inventory requires a tracked connection")
        self._connection = connection
        self._generation = connection.transaction_generation
        self._check_transaction()

    def _check_transaction(self):
        if (self._connection.transaction_generation != self._generation
                or not self._connection.in_transaction):
            raise RuntimeArtifactTrustError("context inventory requires its held transaction")

    def __iter__(self):
        self._check_transaction()
        for (key,) in self._connection.execute(self._keys_sql):
            self._check_transaction()
            yield key

    def __len__(self):
        self._check_transaction()
        return self._connection.execute(self._count_sql).fetchone()[0]

    def __contains__(self, key):
        self._check_transaction()
        return self._connection.execute(self._contains_sql, (key,)).fetchone() is not None


class VerifiedArtifactMapping(_TransactionMapping):
    _keys_sql = "SELECT digest FROM artifacts"
    _count_sql = "SELECT count(*) FROM artifacts"
    _contains_sql = "SELECT 1 FROM artifacts WHERE digest=?"

    def __getitem__(self, key):
        if key not in self:
            raise KeyError(key)
        return _load_artifact(self._connection, key)


class VerifiedReceiptMapping(_TransactionMapping):
    _keys_sql = "SELECT digest FROM context_observations"
    _count_sql = "SELECT count(*) FROM context_observations"
    _contains_sql = "SELECT 1 FROM context_observations WHERE digest=?"

    def __init__(self, connection, *, protected_receipts=()):
        self._validation_failed = False
        super().__init__(connection)
        self._protected = frozenset(protected_receipts)
        self._validation_stamp = None
        self._validating = False

    def _check_transaction(self):
        super()._check_transaction()
        if self._validation_failed:
            raise RuntimeArtifactTrustError("receipt inventory validation permanently failed")

    def _inventory_stamp(self):
        self._check_transaction()
        connection = self._connection
        if (type(self) is VerifiedReceiptMapping and type(connection) is TrackedConnection
                and TrackedConnection.execute is _TRACKED_EXECUTE
                and TrackedConnection.cursor is _TRACKED_CURSOR
                and "execute" not in connection.__dict__ and "cursor" not in connection.__dict__
                and connection.row_factory is None):
            # Keep the original value-evaluation order before allocating.
            generation, changes = connection.transaction_generation, connection.total_changes
            cursor = connection.cursor()
            try:
                main = cursor.execute("PRAGMA main.schema_version").fetchone()[0]
                if (type(connection) is TrackedConnection
                        and TrackedConnection.execute is _TRACKED_EXECUTE
                        and TrackedConnection.cursor is _TRACKED_CURSOR
                        and "execute" not in connection.__dict__ and "cursor" not in connection.__dict__
                        and connection.row_factory is None):
                    temp = cursor.execute("PRAGMA temp.schema_version").fetchone()[0]
                else:
                    temp = connection.execute("PRAGMA temp.schema_version").fetchone()[0]
            except BaseException as error:
                try:
                    cursor.close()
                except BaseException as cleanup:
                    # A closed database must not replace a primary interrupt.
                    raise error from cleanup
                raise
            else:
                cursor.close()
            return generation, changes, main, temp
        return (connection.transaction_generation, connection.total_changes,
                connection.execute("PRAGMA main.schema_version").fetchone()[0],
                connection.execute("PRAGMA temp.schema_version").fetchone()[0])

    def _check_validation(self):
        try:
            if (self._validation_failed or (self._validation_stamp is not None
                    and self._inventory_stamp() != self._validation_stamp)):
                raise RuntimeArtifactTrustError("completed receipt inventory changed or validation failed")
        except (RuntimeArtifactTrustError, sqlite3.Error):
            self._validation_failed = True
            self._validation_stamp = None
            raise

    def validate_all(self):
        """Own the complete physical pass; no caller can grant completion."""
        return self._validate_complete()[0]

    def _validate_all_with_tennis(self, artifacts):
        """Fixed same-transaction co-owner, not a callback or supplied-row API."""
        return self._validate_complete(artifacts)

    def _try_plan_tennis(self, cache, artifacts):
        try:
            return cache._begin_coordinated(artifacts)
        except (ContextContractError, ArtifactIntegrityError):
            # Leave this frame/exception context before releasing metadata.
            # Existing postphysical planning will reproduce the real error.
            return False

    def _decode_row_with_tennis(self, raw, cache):
        from context_sources.tennis_status import (
            STATUS_SCHEMA, SOURCE_SCHEMA, _validate_tennis_source_tail,
        )
        row = None
        try:
            self._check_transaction()
            if raw[0] in self._protected:
                self._decode_row(raw)
                return True
            # Real, unchanged physical owner immediately precedes the complete
            # shared source tail in this non-yielding frame. Nothing receives
            # the decoded object between these checks. Raw[8] is the canonical
            # content just checked by that exact physical decoder invocation.
            row = context_observations._decode_receipt(raw)
            if (row["source_schema"] not in (STATUS_SCHEMA, SOURCE_SCHEMA)
                    or row["observed_at"] > max(cache._original_cutoffs.values())):
                return True
            try:
                _validate_tennis_source_tail(row, raw[8])
            except ContextContractError:
                return False  # Never catch physical, resource or lifetime errors.
            row.update(evidence_class="prospective", effective_at=row["observed_at"],
                       publication_resolution=None)
            return cache._append_coordinated(row)
        finally:
            row = raw = None

    def _validate_complete(self, artifacts=None):
        if self._validating:
            raise RuntimeArtifactTrustError("receipt inventory validation is already active")
        self._validating = True
        cache = None
        try:
            self._check_validation()
            if self._validation_stamp is not None:
                return self._validated_content_count, None
            stamp = self._inventory_stamp()
            connection = self._connection
            if (type(self) is VerifiedReceiptMapping and type(artifacts) is VerifiedArtifactMapping
                    and artifacts._connection is connection and artifacts._generation == self._generation):
                from context_runtime_history_cache import EncodedHistoryCache, MAX_ENCODED_HISTORY_BYTES
                artifacts._check_transaction()
                cache = EncodedHistoryCache(self, max_bytes=MAX_ENCODED_HISTORY_BYTES)
                if not self._try_plan_tennis(cache, artifacts):
                    cache._cancel_coordinated()
                    cache = None
            protected_contents = {content for ref, content in connection.execute(
                "SELECT digest,content_digest FROM context_observations") if ref in self._protected}
            content_count = 0
            for key, raw in connection.execute("SELECT content_digest,payload FROM context_contents"):
                content_count += 1
                require_digest(key, "observation content identity")
                if key in protected_contents:
                    # D2 already owns opaque physical bytes and outer indices.
                    # An unopened final body is never decoded in this pass.
                    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != key:
                        raise ArtifactIntegrityError("unopened observation content hash mismatch")
                    continue
                content = _decode_object(raw, label="observation content")
                if digest(content) != key:
                    raise ArtifactIntegrityError("observation content hash mismatch")
            content = raw = key = None  # End content-phase work before pending rows accumulate.
            query = context_observations._SELECT
            if cache is not None:
                query += " ORDER BY r.observed_at,r.digest"
            for row in connection.execute(query):
                if cache is None:
                    self._decode_row(row)  # Every inactive/unreferenced/future receipt.
                else:
                    keep = self._decode_row_with_tennis(row, cache)
                    cache._check(self)
                    if not keep or cache._build_cancelled:
                        cache._cancel_coordinated()  # Row/helper/exception frames ended.
                        cache = None
            row = None
            if connection.execute("""SELECT 1 FROM context_contents AS c
                    LEFT JOIN context_observations AS r ON r.content_digest=c.content_digest
                    WHERE r.digest IS NULL LIMIT 1""").fetchone():
                raise ArtifactIntegrityError("observation content has no validated receipt")
            if self._inventory_stamp() != stamp:
                raise RuntimeArtifactTrustError("receipt inventory changed during complete validation")
            self._validated_content_count = content_count
            self._validation_stamp = stamp  # Publish only after all checks succeed.
            if cache is not None:
                cache._check(self)
                # The sole preproof transition is inside this actual completed
                # physical/source owner. Direct stores and ordinary validation
                # never execute this branch or acquire source completeness.
                cache._proof = stamp
                if not cache._seal_coordinated():
                    cache._cancel_coordinated()
                    cache = None
                else:
                    # A row seal alone still proves no completeness. Only this
                    # finished operation can bind each exact entry serial.
                    for key in cache._entries:
                        serial = cache._seals[key]
                        charge = len(canonical_bytes((key, serial))) + 32
                        while cache._bytes + charge > cache._max_bytes and cache._queries:
                            cache._drop_query(next(reversed(cache._queries)))
                        if cache._bytes + charge > cache._max_bytes:
                            break
                        cache._check_selected_proof(self)
                        cache._owned[key] = serial, charge
                        cache._charge_metadata(charge)
                        released = cache._bind_coordinated_queries(key, serial)
                        cache._charge_metadata(-released)
                        cache._check_selected_proof(self)
                    # No planning/query-key locals survive optional cancellation.
                    key = None
                    if cache._build_cancelled or len(cache._owned) != len(cache._entries):
                        cache._cancel_coordinated()
                        cache = None
                    else:
                        cache._coordinated_artifacts = artifacts
                        cache._building = False
                        cache._check_selected_proof(self)
            return content_count, cache
        except BaseException:
            # An interrupt must not leave a partial proof available for reuse.
            self._validation_failed = True
            self._validation_stamp = None
            if cache is not None:
                cache._cancel_coordinated()
            raise
        finally:
            self._validating = False

    def values_at_or_before(self, cutoff):
        """Skip future decoding only under this mapping's completed proof."""
        self._check_validation()
        if self._validation_stamp is None:
            yield from self.values()  # Never validated: preserve the full cold path.
            return
        decision = canonical_timestamp(cutoff)
        remaining_protected = set(self._protected)
        for raw in self._connection.execute(context_observations._SELECT + " WHERE r.observed_at<=?", (decision,)):
            self._check_validation()
            row = self._decode_row(raw)
            remaining_protected.discard(raw[0])
            self._check_validation()
            yield row
            self._check_validation()
        # Protected clocks are not eligibility evidence. Keep their opaque
        # rows even when SQL did not select them, without an unbounded IN list.
        for ref in remaining_protected:
            self._check_validation()
            try:
                row = self[ref]
            except KeyError:
                self._check_validation()
                continue  # A protected identity may genuinely be absent.
            self._check_validation()
            yield row
            self._check_validation()  # Also guards resumption after the final yield.
        self._check_validation()

    def __getitem__(self, key):
        self._check_transaction()
        row = self._connection.execute(context_observations._SELECT + " WHERE r.digest=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return self._decode_row(row)

    def _decode_row(self, row):
        self._check_transaction()
        if row[0] in self._protected:
            require_digest(row[0], "protected observation receipt identity")
            # D2's physical preflight owns outer validation; never body-decode
            # an unopened final even when a consumer explicitly requests it.
            return {"digest": row[0], "content_digest": row[1], "event_key": row[2],
                    "observed_at": row[3], "kind": row[7]}
        return context_observations._decode_receipt(row)


class ArtifactSubsetMapping(Mapping):
    """Identity-only subset; D2 must not recreate a decoded inventory cache."""
    def __init__(self, artifacts, keys):
        artifacts._check_transaction()
        self._artifacts, self._keys = artifacts, frozenset(keys)

    def __getitem__(self, key):
        self._artifacts._check_transaction()
        if key not in self._keys:
            raise KeyError(key)
        return self._artifacts[key]

    def __iter__(self):
        self._artifacts._check_transaction()
        for key in self._keys:
            self._artifacts._check_transaction()
            yield key

    def __len__(self):
        self._artifacts._check_transaction()
        return len(self._keys)

    def __contains__(self, key):
        self._artifacts._check_transaction()
        return key in self._keys
