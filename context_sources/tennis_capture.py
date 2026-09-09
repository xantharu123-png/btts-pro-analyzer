"""Opt-in daily-worker observer of existing ESPN JSON replies; never a fetch."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from context_models.contracts import ContextContractError
from context_observations import append_observation
from context_sources.tennis_status import normalize_tennis_status


_CURRENT = ContextVar("tennis_existing_response_capture", default=None)


def _receipt_now():
    return datetime.now(timezone.utc)


class _Capture:
    def __init__(self):
        self.pending, self.issues, self.refs = [], set(), set()

    def report(self):
        return {"schema": 1, "scope": "existing-espn-tennis-responses",
            "status": "partial" if self.issues else "captured" if self.refs else "no_receipts",
            "receipt_refs": sorted(self.refs), "issues": sorted(self.issues)}

    def record(self, tour, payload, *, observed_at):
        if type(tour) is not str or tour not in {"atp", "wta"}:
            self.issues.add("native-tour-unavailable")
            return
        if type(payload) is not dict or type(payload.get("events")) is not list:
            self.issues.add("native-response-unavailable")
            return
        for event in payload["events"]:
            if type(event) is not dict or type(event.get("groupings")) is not list:
                self.issues.add("native-grouping-unavailable")
                continue
            for group in event["groupings"]:
                if type(group) is not dict or type(group.get("competitions")) is not list:
                    self.issues.add("native-grouping-unavailable")
                    continue
                grouping = group.get("grouping")
                slug = grouping.get("slug") if type(grouping) is dict else None
                for competition in group["competitions"]:
                    try:
                        rows = normalize_tennis_status(tour.upper(), event.get("id"), competition,
                            grouping_slug=slug, observed_at=observed_at)
                    except (ContextContractError, TypeError, ValueError, OverflowError, KeyError):
                        # Without a native match ID there is no honest event
                        # alias to append. A known ID with bad fields is instead
                        # preserved by the status normalizer as a withdrawal.
                        self.issues.add("native-competition-unavailable")
                        continue
                    self.pending.append((observed_at, rows))
                    for issue in rows[0]["payload"]["issues"]:
                        if issue not in {"unsupported-format", "unsupported-terminal"}:
                            self.issues.add(issue)

    def persist(self, path):
        for observed, rows in self.pending:
            # Publish status first: an interruption can leave an explicitly
            # incomplete new pair, never apparently valid orphan workload.
            # B1 is append-only/idempotent; this is NOT a multi-row transaction.
            for row in rows:
                self.refs.add(append_observation(path, row, observed_at=observed))


def observe_espn_response(tour, payload):
    """Called exactly at the existing successful JSON response boundary.

    Default callers do not read a clock, normalize, persist or start a worker.
    The request's actual tour scope is used, never a name/tournament inference.
    """
    current = _CURRENT.get()
    if current is not None:
        current.record(tour, payload, observed_at=_receipt_now())


@contextmanager
def capture_tennis_worker(*, path=None):
    """Explicit CLI batch ownership; always drain received facts/reset scope."""
    if _CURRENT.get() is not None:
        raise ContextContractError("tennis capture already belongs to an active worker")
    if path is None:
        from runtime_paths import CONTEXT_MODEL_DB_PATH
        path = CONTEXT_MODEL_DB_PATH
    current = _Capture()
    token = _CURRENT.set(current)
    try:
        yield current
    finally:
        _CURRENT.reset(token)
        # Storage integrity exceptions escape outside the provider's legacy
        # ValueError/network exception handling; never disguise them as no data.
        current.persist(Path(path))
