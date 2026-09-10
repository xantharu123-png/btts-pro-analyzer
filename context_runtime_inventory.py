"""Read-only, uncached views of a caller-held verification transaction.

Only identities are retained. Values are fresh owning-decoder results on each
lookup. A view is permanently invalid after its original transaction ends.
"""
from collections.abc import Mapping

import context_observations
from model_artifacts import _load_artifact
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
        super().__init__(connection)
        self._protected = frozenset(protected_receipts)

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
