"""Read-only, uncached views of a caller-held verification transaction.

Only identities are retained. Values are fresh owning-decoder results on each
lookup. A view is permanently invalid after its original transaction ends.
"""
from collections.abc import Mapping
import hashlib
import sqlite3

import context_observations
from context_models.contracts import canonical_timestamp, digest, require_digest
from model_artifacts import ArtifactIntegrityError, _decode_object, _load_artifact
from runtime_paths import RuntimeArtifactTrustError
from context_runtime_transaction import TrackedConnection


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

    def _check_transaction(self):
        super()._check_transaction()
        if self._validation_failed:
            raise RuntimeArtifactTrustError("receipt inventory validation permanently failed")

    def _inventory_stamp(self):
        self._check_transaction()
        connection = self._connection
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
        try:
            self._check_validation()
            if self._validation_stamp is not None:
                return self._validated_content_count
            stamp = self._inventory_stamp()
            connection = self._connection
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
            for ref in self:
                self[ref]  # Every receipt, including inactive/unreferenced/future rows.
            if connection.execute("""SELECT 1 FROM context_contents AS c
                    LEFT JOIN context_observations AS r ON r.content_digest=c.content_digest
                    WHERE r.digest IS NULL LIMIT 1""").fetchone():
                raise ArtifactIntegrityError("observation content has no validated receipt")
            if self._inventory_stamp() != stamp:
                raise RuntimeArtifactTrustError("receipt inventory changed during complete validation")
            self._validated_content_count = content_count
            self._validation_stamp = stamp  # Publish only after all checks succeed.
            return content_count
        except BaseException:
            # An interrupt must not leave a partial proof available for reuse.
            self._validation_failed = True
            self._validation_stamp = None
            raise

    def values_at_or_before(self, cutoff):
        """Skip future decoding only under this mapping's completed proof."""
        self._check_validation()
        if self._validation_stamp is None:
            yield from self.values()  # Never validated: preserve the full cold path.
            return
        decision = canonical_timestamp(cutoff)
        for ref, clock in self._connection.execute("SELECT digest,observed_at FROM context_observations"):
            self._check_validation()
            if ref in self._protected or clock <= decision:
                row = self[ref]
                self._check_validation()
                yield row
                self._check_validation()  # Also guards resumption after the final yield.
        self._check_validation()

    def __getitem__(self, key):
        self._check_transaction()
        row = self._connection.execute(context_observations._SELECT + " WHERE r.digest=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        if key in self._protected:
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
