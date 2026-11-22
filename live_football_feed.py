"""Shared, viewer-driven football scoreboard. No scheduler, HTTP client or disk state."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import Lock
from time import monotonic as monotonic_clock

from live_tip_ledger import MAX_SNAPSHOT_AGE_SECONDS
from redcard_events import period_clock


DISCOVERY_INTERVAL = timedelta(minutes=5)
DETAIL_INTERVAL = timedelta(minutes=1)
ERROR_BACKOFF = timedelta(minutes=2)
MAX_DETAIL_AGE = timedelta(seconds=MAX_SNAPSHOT_AGE_SECONDS)
BATCH_SIZE = 20
LIVE = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "INT", "SUSP", "LIVE"})
FINISHED = frozenset({"FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO", "NS", "TBD"})


class LiveRefreshIssue(str, Enum):
    """Safe display codes, in descending priority when more than one applies."""

    TICKER_LIMIT = "ticker_limit"
    PROTECTED_RESERVE = "protected_reserve"
    BUDGET_BLOCKED = "budget_blocked"
    BUDGET_UNAVAILABLE = "budget_unavailable"
    JOBS_DEFERRED = "jobs_deferred"
    PROVIDER_ERROR = "provider_error"
    TEMPORARY_ERROR = "temporary_error"
    PARTIAL_DATA = "partial_data"


@dataclass(frozen=True)
class LiveFeedView:
    rows: dict
    issue: LiveRefreshIssue | None
    loading: bool


class LiveSourceError(RuntimeError):
    """The source may pass only a safe code, never provider or governor text."""

    def __init__(self, issue: LiveRefreshIssue):
        super().__init__(issue.value)
        self.issue = issue


def _refresh_issue(error):
    return error.issue if isinstance(error, LiveSourceError) else LiveRefreshIssue.TEMPORARY_ERROR


def _positive(value):
    return type(value) is int and value > 0


def _indexed(rows):
    """Keep only uniquely attributed rows. An unidentifiable envelope is not an empty list."""
    if not isinstance(rows, list):
        raise ValueError("Invalid fixture list")
    index = {}
    for row in rows:
        fixture = row.get("fixture") if isinstance(row, dict) else None
        number = fixture.get("id") if isinstance(fixture, dict) else None
        if not _positive(number):
            raise ValueError("Unidentifiable fixture")
        index[number] = None if number in index else row
    return index


def _sides(row):
    teams = row.get("teams")
    if isinstance(teams, dict):
        sides = tuple(teams[s].get("id") if isinstance(teams.get(s), dict) else None
                      for s in ("home", "away"))
        if all(_positive(s) for s in sides) and sides[0] != sides[1]:
            return sides
    return None


def _phase(row):
    status = row["fixture"].get("status")
    return status.get("short") if isinstance(status, dict) and isinstance(status.get("short"), str) else None


def _scored(row):
    goals = row.get("goals")
    return isinstance(goals, dict) and all(type(goals.get(s)) is int and goals[s] >= 0
                                           for s in ("home", "away"))


def _clock(row):
    status = row["fixture"]["status"]
    phase, minute, extra = _phase(row), status.get("elapsed"), status.get("extra")
    extra = 0 if extra is None else extra
    if phase in {"ET", "BT", "P"} and type(minute) is int and 0 <= minute <= 130 and type(extra) is int and 0 <= extra <= 40:
        # BT is the break within extra time; do not order it after the entire ET period.
        return (4 if phase == "P" else 3, minute, extra)
    return period_clock(phase, minute, extra)


def _not_older(row, previous):
    before = _clock(previous)
    current = _clock(row)
    return before is None or (current is not None and current >= before)


def _without_detail(row):
    invalid = {**row, "detailed_at": None}
    invalid.pop("stats_at", None)
    return invalid


class LiveFootballFeed:
    """One instance per credential/provider, shared by the authorized UI sessions.

    One tick owns the network pass; other callers see each completed batch without
    waiting on a provider. Published dictionaries are replaced, never edited in place.
    """

    def __init__(self, *, monotonic=monotonic_clock):
        self._monotonic = monotonic
        self._writer = Lock()
        self._publication = Lock()
        self._rows = {}
        self._details_due = {}
        self._discover_due = self._retry_after = None
        self._discovery_valid_until = None  # None until this attempt publishes a result or an error.
        self._discovery_issue = None
        self._detail_issues = {}

    @property
    def unavailable(self):
        """A failed or deferred fetch is not evidence that there are no live games."""
        return self.refresh_issue is not None

    @property
    def refresh_issue(self):
        with self._publication:
            return self._issue()

    def _issue(self):
        issues = {self._discovery_issue, *self._detail_issues.values()}
        return next((issue for issue in LiveRefreshIssue if issue in issues), None)

    def _awaiting_discovery(self, now):
        return not self._rows and (self._discovery_valid_until is None or now >= self._discovery_valid_until)

    def awaiting_discovery(self, now):
        """Only for the immediate loading indicator, before blocking on provider I/O."""
        with self._publication:
            return self._awaiting_discovery(now)

    @contextmanager
    def current_detail(self, number, stamp, fixture):
        """Pin only the final local display, never HTTP, analysis, account or ledger I/O."""
        with self._publication:
            row = self._rows.get(number)
            yield (row is not None and stamp is not None and row["detailed_at"] == stamp
                   and row["fixture"] == fixture)

    def _invalidate(self, ids, issue, *, discovery_retry_at=None):
        rows = self._rows.copy()
        for number in ids:
            if number in rows:
                rows[number] = _without_detail(rows[number])
        with self._publication:
            self._rows = rows
            if discovery_retry_at is not None:
                self._discovery_issue = issue
                self._discovery_valid_until = discovery_retry_at
            else:
                self._detail_issues.update(dict.fromkeys(ids, issue))

    def _eligible(self, ids, now):
        return [i for i in ids if i not in self._details_due or now >= self._details_due[i]]

    def _snapshot(self, now):
        # Rows are replaced, never modified in place. Capture their status before
        # releasing the publication lock; another viewer may publish before rendering.
        with self._publication:
            rows, issue = self._rows, self._issue()
            loading = self._awaiting_discovery(now)
        result = deepcopy(rows)
        for entry in result.values():
            stamp = entry["detailed_at"]
            if stamp is not None and not timedelta(0) <= now - stamp <= MAX_DETAIL_AGE:
                entry["detailed_at"] = None
        return LiveFeedView(result, None if loading else issue, loading)

    def _discover(self, source, now):
        indexed = _indexed(source.discover())
        rows = {}
        incomplete = False
        for number, row in indexed.items():
            if (row and _phase(row) in LIVE and _sides(row) and _scored(row)
                    and (number not in self._rows or _not_older(row, self._rows[number]["fixture"]))):
                rows[number] = {"fixture": row, "observed_at": now, "detailed_at": None}
            elif not row or _phase(row) not in FINISHED:
                incomplete = True
                if number in self._rows:
                    rows[number] = _without_detail(self._rows[number])
        with self._publication:
            self._rows = rows
            self._discovery_valid_until = now + DISCOVERY_INTERVAL
            self._discovery_issue = LiveRefreshIssue.PARTIAL_DATA if incomplete else None
            self._detail_issues = {i: issue for i, issue in self._detail_issues.items() if i in rows}

    def _details(self, source, ids, now):
        indexed = _indexed(source.details(ids))
        rows = self._rows.copy()
        incomplete = set()
        for number in ids:
            old, row = rows[number], indexed.get(number)
            if row and _sides(row) == _sides(old["fixture"]):
                phase = _phase(row)
                if phase in FINISHED:
                    del rows[number]
                    continue
                if phase in LIVE and _scored(row) and _not_older(row, old["fixture"]):
                    arrays = all(isinstance(row.get(k), list) for k in ("events", "statistics"))
                    rows[number] = {"fixture": row, "observed_at": now, "detailed_at": now if arrays else None}
                    if not arrays:
                        incomplete.add(number)
                        # A current stats packet may arrive without events. Its counts
                        # can be displayed but must never unlock a model prediction.
                        if isinstance(row.get("statistics"), list) and row["statistics"]:
                            rows[number]["stats_at"] = now
                    continue
            rows[number] = _without_detail(old)
            incomplete.add(number)
        with self._publication:
            self._rows = rows
            for number in ids:
                self._detail_issues.pop(number, None)
            self._detail_issues.update(dict.fromkeys(incomplete, LiveRefreshIssue.PARTIAL_DATA))

    def tick(self, source, *, now: datetime, viewer_active=lambda: True):
        return self.tick_view(source, now=now, viewer_active=viewer_active).rows

    def tick_view(self, source, *, now: datetime, viewer_active=lambda: True):
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("Live tick requires an aware clock")
        now = now.astimezone(timezone.utc)
        if not viewer_active():
            return LiveFeedView({}, None, True)
        if not self._writer.acquire(blocking=False):
            return self._snapshot(now)
        started = self._monotonic()

        def current():
            return now + timedelta(seconds=self._monotonic() - started)

        try:
            if self._retry_after is not None and now < self._retry_after:
                return self._snapshot(now)
            if self._discover_due is None or now >= self._discover_due:
                self._discover_due = now + DISCOVERY_INTERVAL
                # Even a viewer whose clock was sampled just before expiry must
                # no longer present the previous empty result during this fetch.
                with self._publication:
                    self._discovery_valid_until = None
                try:
                    self._discover(source, now)
                except Exception as error:
                    self._retry_after = current() + ERROR_BACKOFF
                    self._invalidate(self._rows, _refresh_issue(error),
                                     discovery_retry_at=max(self._retry_after, self._discover_due))
                    return self._snapshot(now)
                self._details_due = {i: due for i, due in self._details_due.items() if i in self._rows}
            ids = sorted(self._rows)
            for offset in range(0, len(ids), BATCH_SIZE):
                stamp = current()
                group = self._eligible(ids[offset:offset + BATCH_SIZE], stamp)
                if not group:
                    continue
                if not viewer_active():
                    return LiveFeedView({}, None, True)
                self._details_due.update(dict.fromkeys(group, stamp + DETAIL_INTERVAL))
                try:
                    self._details(source, group, stamp)
                except Exception as error:
                    self._invalidate(ids[offset:], _refresh_issue(error))
                    self._retry_after = current() + ERROR_BACKOFF
                    break
            return self._snapshot(current()) if viewer_active() else LiveFeedView({}, None, True)
        finally:
            self._writer.release()
