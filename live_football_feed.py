"""Shared, viewer-driven football scoreboard. No scheduler, HTTP client or disk state."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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
        self._discovery_failed = self._details_failed = False

    @property
    def unavailable(self):
        """A failed or deferred fetch is not evidence that there are no live games."""
        return self._discovery_failed or self._details_failed

    def _publish(self, rows):
        with self._publication:
            self._rows = rows

    @contextmanager
    def current_detail(self, number, stamp, fixture):
        """Pin only the final local display, never HTTP, analysis, account or ledger I/O."""
        with self._publication:
            row = self._rows.get(number)
            yield (row is not None and stamp is not None and row["detailed_at"] == stamp
                   and row["fixture"] == fixture)

    def _invalidate(self, ids):
        rows = self._rows.copy()
        for number in ids:
            if number in rows:
                rows[number] = {**rows[number], "detailed_at": None}
        self._publish(rows)

    def _eligible(self, ids, now):
        return [i for i in ids if i not in self._details_due or now >= self._details_due[i]]

    def _snapshot(self, now):
        result = deepcopy(self._rows)
        for entry in result.values():
            stamp = entry["detailed_at"]
            if stamp is not None and not timedelta(0) <= now - stamp <= MAX_DETAIL_AGE:
                entry["detailed_at"] = None
        return result

    def _discover(self, source, now):
        indexed = _indexed(source.discover())
        rows = {}
        for number, row in indexed.items():
            if (row and _phase(row) in LIVE and _sides(row) and _scored(row)
                    and (number not in self._rows or _not_older(row, self._rows[number]["fixture"]))):
                rows[number] = {"fixture": row, "observed_at": now, "detailed_at": None}
            elif number in self._rows and (not row or _phase(row) not in FINISHED):
                rows[number] = {**self._rows[number], "detailed_at": None}
        self._publish(rows)

    def _details(self, source, ids, now):
        indexed = _indexed(source.details(ids))
        rows = self._rows.copy()
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
                    continue
            rows[number] = {**old, "detailed_at": None}
        self._publish(rows)

    def tick(self, source, *, now: datetime, viewer_active=lambda: True):
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("Live tick requires an aware clock")
        now = now.astimezone(timezone.utc)
        if not viewer_active():
            return {}
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
                try:
                    self._discover(source, now)
                except Exception:
                    self._discovery_failed = True
                    self._invalidate(self._rows)
                    self._retry_after = current() + ERROR_BACKOFF
                    return self._snapshot(now)
                self._discovery_failed = False
                if not self._rows:
                    self._details_failed = False
                self._details_due = {i: due for i, due in self._details_due.items() if i in self._rows}
            ids = sorted(self._rows)
            refreshed = False
            for offset in range(0, len(ids), BATCH_SIZE):
                stamp = current()
                group = self._eligible(ids[offset:offset + BATCH_SIZE], stamp)
                if not group:
                    continue
                if not viewer_active():
                    return {}
                self._details_due.update(dict.fromkeys(group, stamp + DETAIL_INTERVAL))
                try:
                    self._details(source, group, stamp)
                    refreshed = True
                except Exception:
                    self._details_failed = True
                    self._invalidate(ids[offset:])
                    self._retry_after = current() + ERROR_BACKOFF
                    break
            else:
                if refreshed:
                    self._details_failed = False
            return self._snapshot(current()) if viewer_active() else {}
        finally:
            self._writer.release()
