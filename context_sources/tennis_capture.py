"""Opt-in daily-worker observer of existing ESPN JSON replies; never a fetch."""
from contextlib import contextmanager
from contextvars import ContextVar
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

from context_models.contracts import ContextContractError
from context_observations import append_observation_batch
from context_sources.tennis_status import normalize_tennis_status


_CURRENT = ContextVar("tennis_existing_response_capture", default=None)


def _receipt_now():
    return datetime.now(timezone.utc)


def _expected_exclusion(status, competition):
    """Classify known out-of-scope draws, never make their rows modelable.

    ESPN returns doubles and explicit TBD bracket slots alongside singles.
    Their unchanged native unknown/retraction rows must still be persisted.
    Missing identities in a played match or a named singles pair remain errors.
    """
    payload = status["payload"]
    issues = set(payload["issues"])
    if (status["format"] == "unsupported"
            and payload["grouping_slug"] in {"mens-singles", "womens-singles",
                "mens-doubles", "womens-doubles", "mixed-doubles"}
            and issues <= {"unsupported-format", "unsupported-terminal", "invalid-participants"}):
        return "outside-singles-scope"
    if (status["format"] != "singles" or payload["status"] not in {"scheduled", "cancelled"}
            or issues != {"invalid-participants"}):
        return None
    players = competition.get("competitors")
    if type(players) is not list or len(players) != 2:
        return None
    missing = False
    for native_id, player in zip(payload["participant_ids"], players):
        if native_id is not None:
            continue
        missing = True
        athlete = player.get("athlete") if type(player) is dict else None
        raw_id = player.get("id") if type(player) is dict else None
        if (type(athlete) is not dict or athlete.get("displayName") != "TBD"
                or not (raw_id is None or type(raw_id) is str and re.fullmatch(r"-[1-9][0-9]*", raw_id))):
            return None
    return "unresolved-draw-slot" if missing else None


class _Capture:
    def __init__(self):
        self.pending, self.issues, self.refs = [], set(), set()
        self.exclusions = Counter()
        self.retired_outcome_events = set()
        self._outcome_sources = {}

    def report(self):
        return {"schema": 1, "scope": "existing-espn-tennis-responses",
            "status": "partial" if self.issues else "captured" if self.refs else "no_receipts",
            "receipt_refs": sorted(self.refs), "issues": sorted(self.issues),
            "excluded_competitions": dict(sorted(self.exclusions.items())),
            "retired_outcome_events": sorted(self.retired_outcome_events)}

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
                    index = len(self.pending)
                    self.pending.append((observed_at, rows))
                    from context_sources.tennis_outcome_capture import source_for_normal_winner
                    eligible, source = source_for_normal_winner(rows[0], competition)
                    if eligible:
                        self._outcome_sources[index] = source
                    exclusion = _expected_exclusion(rows[0], competition)
                    if exclusion is not None:
                        self.exclusions[exclusion] += 1
                    else:
                        for issue in rows[0]["payload"]["issues"]:
                            if issue not in {"unsupported-format", "unsupported-terminal"}:
                                self.issues.add(issue)

    def persist(self, path):
        from context_sources.tennis_outcome_capture import collect_outcomes
        outcomes, issues = collect_outcomes(path, self.pending, self._outcome_sources,
            retired_events=self.retired_outcome_events)
        self.issues.update(issues)
        chunk = []
        for index, (observed, rows) in enumerate(self.pending):
            if index in outcomes:
                rows = (*rows, *outcomes[index])
            if len(rows) > 512:
                raise ContextContractError("one native competition exceeds the atomic receipt batch limit")
            # Keep one competition's status/workload together. The whole feed
            # may remain partial on interruption, but a committed chunk is
            # atomic and retains every original reception clock.
            if len(chunk) + len(rows) > 512:
                self.refs.update(append_observation_batch(path, tuple(chunk)))
                chunk = []
            chunk.extend((row, observed) for row in rows)
        if chunk:
            self.refs.update(append_observation_batch(path, tuple(chunk)))


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
