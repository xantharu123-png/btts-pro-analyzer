"""Verifier-owned SQLite lifecycle tracking without callbacks or SQL rewriting.

The normal Connection/Cursor APIs retain SQLite's transaction semantics. A
monotonic generation additionally invalidates views when a transaction ends,
including automatic rollback on statement failure and script end/restart.
"""
from contextlib import contextmanager
import sqlite3

from runtime_paths import RuntimeArtifactTrustError


class TrackedCursor(sqlite3.Cursor):
    def execute(self, *args, **kwargs):
        with self.connection._observe_transaction():
            return super().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        with self.connection._observe_transaction():
            return super().executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        # A single call can commit the old transaction AND begin another,
        # leaving in_transaction unchanged. Never treat scripts as one epoch.
        with self.connection._observe_transaction(invalidate=True):
            return super().executescript(*args, **kwargs)


class TrackedConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transaction_generation = 0

    @property
    def transaction_generation(self):
        return self._transaction_generation

    @contextmanager
    def _observe_transaction(self, *, invalidate=False):
        before = self.in_transaction
        if invalidate:
            self._transaction_generation += 1
        try:
            yield
        finally:
            if before != self.in_transaction:
                self._transaction_generation += 1

    def cursor(self, factory=TrackedCursor):
        if not isinstance(factory, type) or not issubclass(factory, TrackedCursor):
            raise RuntimeArtifactTrustError("context connection requires a tracked cursor")
        return super().cursor(factory)

    def execute(self, *args, **kwargs):
        return self.cursor().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self.cursor().executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self.cursor().executescript(*args, **kwargs)

    def commit(self):
        # autocommit=False may end and restart in one C API call.
        with self._observe_transaction(invalidate=self.in_transaction):
            return super().commit()

    def rollback(self):
        with self._observe_transaction(invalidate=self.in_transaction):
            return super().rollback()

    def __exit__(self, *args):
        with self._observe_transaction(invalidate=self.in_transaction):
            return super().__exit__(*args)

    def close(self):
        self._transaction_generation += 1
        return super().close()

    def deserialize(self, *args, **kwargs):
        with self._observe_transaction(invalidate=True):
            return super().deserialize(*args, **kwargs)

    def __setattr__(self, name, value):
        if name in {"isolation_level", "autocommit"} and "_transaction_generation" in self.__dict__:
            # These setters can commit/restart without invoking our commit().
            with self._observe_transaction(invalidate=True):
                super().__setattr__(name, value)
        else:
            super().__setattr__(name, value)
