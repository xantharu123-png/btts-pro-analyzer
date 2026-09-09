"""Opt-in observations of existing NBA/EuroLeague/NHL JSON reads; no fetch."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from context_models.contracts import ContextContractError
from context_observations import append_observation
from context_sources.team_sports_status import normalize_team_sport_response, response_request


_CURRENT = ContextVar("existing_team_sports_response_capture", default=None)


def _receipt_now():
    return datetime.now(timezone.utc)


class _Capture:
    def __init__(self):
        self.pending, self.issues, self.refs = [], set(), set()

    def report(self):
        return {"schema": 1, "scope": "existing-team-sport-responses",
            "status": "partial" if self.issues else "captured" if self.refs else "no_receipts",
            "receipt_refs": sorted(self.refs), "issues": sorted(self.issues)}

    def record(self, provider, url, params, phase, window, key, payload, response):
        observed = _receipt_now()
        try:
            request = response_request(provider, url, params, phase=phase, window=window,
                                       request_key=key, response=response)
            rows, issues = normalize_team_sport_response(request, payload, observed_at=observed)
        except (ContextContractError, KeyError, TypeError, OverflowError):
            self.issues.add("native-response-unavailable")
            return
        self.issues.update(issues)
        self.pending.extend((observed, row) for row in rows)

    def persist(self, path):
        for observed, row in self.pending:
            self.refs.add(append_observation(path, row, observed_at=observed))


def observe_espn_basketball_schedule(url, league, day, start, end, payload, response):
    current = _CURRENT.get()
    if current is not None:
        if league != "NBA":
            current.issues.add("native-request-unavailable")
            return
        current.record("ESPN", url, {"dates": day.strftime("%Y%m%d"), "limit": 100},
                       "schedule", (start, end), None, payload, response)


def observe_euroleague_schedule(base_url, season, start, end, payload, response):
    current = _CURRENT.get()
    if current is not None:
        current.record("EuroLeague", f"{base_url}/competitions/E/seasons/{season}/games",
                       {"limit": 500}, "schedule", (start, end), None, payload, response)


def observe_nhl_schedule(base_url, cursor, start, end, payload, response):
    current = _CURRENT.get()
    if current is not None:
        current.record("NHL", f"{base_url}/{cursor}", None, "schedule", (start, end),
                       None, payload, response)


def observe_completed_team_sports_response(provider, key, url, params, payload, response):
    # Cricket never enters the observer, even with an active team-sport scope.
    if provider not in {"ESPN", "EuroLeague", "NHL"}:
        return
    current = _CURRENT.get()
    if current is not None:
        current.record(provider, url, params, "history", None, key, payload, response)


@contextmanager
def capture_team_sports_worker(*, path=None):
    """Drain actual received observations, never manufacture warm-cache facts."""
    if _CURRENT.get() is not None:
        raise ContextContractError("team-sport capture already has an owner")
    if path is None:
        from runtime_paths import CONTEXT_MODEL_DB_PATH
        path = CONTEXT_MODEL_DB_PATH
    current = _Capture()
    token = _CURRENT.set(current)
    try:
        yield current
    finally:
        _CURRENT.reset(token)
        # Storage errors propagate outside legacy network/parser catches.
        current.persist(Path(path))
