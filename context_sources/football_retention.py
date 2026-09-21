"""Reuse complete, unchanged FT bundles without inventing a fresh receipt.

Only already received native fixtures in this worker's explicit input scope
may name stored evidence. Scheduled inputs, injuries and lineups are never
reused here. Old clocks stay old; a correction or incomplete bundle requires
an ordinary new, budgeted append. No provider call or inventory fallback.
"""
from datetime import datetime
import os

from context_models.contracts import ContextIntegrityError, canonical_timestamp, digest
from context_observations import _SELECT, _decode_receipt
from context_sources.football import _detail_event, normalize_football_context
from context_sources.outcomes import normalize_football_base_input, normalize_football_outcome
from model_artifacts import canonical_bytes


def fixture_bundle(raw, observed):
    event = _detail_event(raw)
    additions = [row for row in normalize_football_context(event, injuries=[],
        lineups=[raw] if "lineups" in raw and event["status"] == "scheduled" else [],
        appearances=[raw] if "players" in raw and event["status"] == "completed" else [],
        observed_at=observed) if row["kind"] != "availability"]
    additions.append(normalize_football_base_input(raw, observed_at=observed))
    base_index = len(additions) - 1
    outcome = normalize_football_outcome(event, raw, observed_at=observed)
    if outcome is not None:
        additions.append(outcome)
    return additions, base_index


class RetainedFinals:
    def __init__(self, path, received):
        self.rows, self.bases, self.live = {}, {}, {}
        for raw, clock in received:
            event_key = _detail_event(raw)["event_key"]
            self.live.setdefault(event_key, []).append((clock, canonical_bytes(raw)))
        keys = tuple(sorted(self.live))
        if not keys or not os.path.lexists(path):
            return
        from context_models.dataset import _reader
        frozen = []
        with _reader(path) as connection:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('context_observations','context_contents')")}
            if not tables:
                return
            if tables != {"context_observations", "context_contents"}:
                raise ContextIntegrityError("incomplete stored context observation tables")
            for start in range(0, len(keys), 128):
                part = keys[start:start+128]
                marks = ','.join('?' for _ in part)
                # Do not filter by mutable source/kind index columns: validate
                # every named event row, including a damaged indexed field.
                frozen.extend(connection.execute(_SELECT +
                    f" WHERE r.event_key IN ({marks})", part).fetchall())
        for stored in frozen:
            row = _decode_receipt(stored)
            self.rows[row["digest"]] = row
            if row["source"] == "api-football" and row["kind"] == "base_fixture":
                self.bases.setdefault(row["event_key"], []).append(row)

    def reuse(self, raw, *, observed):
        if raw["fixture"]["status"]["short"] != "FT":
            return None
        event_key = _detail_event(raw)["event_key"]
        clock = canonical_timestamp(observed)
        previous = [row for row in self.bases.get(event_key, ()) if row["observed_at"] <= clock]
        if not previous:
            return None
        latest = max(row["observed_at"] for row in previous)
        latest_rows = [row for row in previous if row["observed_at"] == latest]
        if len(latest_rows) != 1:
            return None  # Simultaneous revisions have no arbitrary winner.
        base = latest_rows[0]
        if (base["source_schema"] != "native-football-base-detail-v1"
                or base["payload"].get("schema") != 1
                or canonical_bytes(base["payload"].get("detail")) != canonical_bytes(raw)):
            return None
        raw_bytes = canonical_bytes(raw)
        if any(latest <= at <= clock and payload != raw_bytes
               for at, payload in self.live[event_key]):
            return None  # Never collapse A -> B -> A into the old A receipt.
        additions, base_index = fixture_bundle(raw, datetime.fromisoformat(latest))
        refs = []
        for content in additions:
            content_hash = digest(content)
            ref = digest({"content_digest": content_hash, "observed_at": latest})
            existing = self.rows.get(ref)
            if existing is None:
                return None  # A standalone old base row is not a whole bundle.
            if existing != {**content, "digest": ref, "content_digest": content_hash, "observed_at": latest}:
                raise ContextIntegrityError("retained football bundle identity mismatch")
            refs.append(ref)
        return tuple(refs), base_index
