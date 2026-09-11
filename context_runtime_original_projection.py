"""Bounded scalar folds, never source selection, decoding or retained payloads."""
from dataclasses import dataclass

from model_artifacts import canonical_bytes


@dataclass(slots=True)
class _OriginalQuery:
    key: tuple
    charge: int
    prefix_bytes: int = 0
    latest: str | None = None
    count: int = 0
    ordinal: int | None = None
    basis: tuple | None = None
    serial: int | None = None

    @staticmethod
    def reservation(key, byte_limit, serial):
        # Two byte-bounded counters, clock plus basis clock/tour, saturated
        # count, serial and JSON punctuation. No duplicate encoded key kept.
        return len(canonical_bytes(key)) + 192 + 2 * len(str(byte_limit)) + len(str(serial))

    def fold(self, row, size, ordinal):
        event, cutoff, _ = self.key
        clock = row["observed_at"]
        if clock > cutoff:
            return
        self.prefix_bytes += size
        if row["event_key"] != event:
            return
        if self.latest is None or clock > self.latest:
            self.latest, self.count, self.ordinal = clock, 1, ordinal
        elif clock == self.latest:
            self.count, self.ordinal = 2, None
