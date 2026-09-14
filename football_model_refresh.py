"""Recompute a bounded, already discovered fixture batch with the normal model.

This is not another league discovery or a timestamp refresh. Native event
details, completed history, validation and calibration feed the SAME scan core
as daily discovery. Failed inputs leave the previously recorded model alone.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from challenge_15k import (
    CHALLENGE_TIMEZONE, _fixture_kickoff, _reconcile_candidate_fixture,
    _valid_upcoming_fixture, scan_daily_challenge,
)

MODEL_REFRESH_VERSION = "football-fixture-model-refresh-v1"


class _FixtureBatchProvider:
    """Delegate budgeted history/context calls, never rediscover a league."""

    def __init__(self, provider, fixtures, details):
        self._provider = provider
        self._fixtures = fixtures
        self._details = details

    def __getattr__(self, name):
        return getattr(self._provider, name)

    def upcoming_fixtures(self, league_id, season, search_date):
        return self.upcoming_fixtures_range(league_id, season, search_date, search_date)

    def upcoming_fixtures_range(self, league_id, season, start, end):
        return [row for row in self._fixtures
                if row["league"]["id"] == league_id
                and start <= _fixture_kickoff(row).astimezone(CHALLENGE_TIMEZONE).date() <= end]

    def details_by_fixture(self, fixture_ids):
        if not set(fixture_ids) <= set(self._details):
            raise ValueError("model refresh attempted an undiscovered fixture")
        return {key: self._details[key] for key in fixture_ids}


def refresh_fixture_models(provider, candidates, search_date, *, now):
    """Rebuild all supported markets, not just the formerly selected market.

    Shared immutable prediction/evidence logs remain untouched. The caller
    publishes a new latest-catalog revision only after this function succeeds.
    """
    by_fixture = {}
    for candidate in candidates:
        prior = by_fixture.setdefault(candidate.fixture_id, candidate)
        if (prior.league_id, prior.home_team_id, prior.away_team_id) != (
                candidate.league_id, candidate.home_team_id, candidate.away_team_id):
            raise ValueError("model refresh has conflicting persisted event identities")
    if not 0 < len(by_fixture) <= 20:
        raise ValueError("model refresh needs one bounded batch of 1 to 20 fixtures")
    details = provider.details_by_fixture(sorted(by_fixture))
    fixtures, invalidated = [], []
    for fixture_id, candidate in by_fixture.items():
        row = details.get(fixture_id)
        if (not _valid_upcoming_fixture(row, candidate.league_id)
                or row["fixture"]["id"] != fixture_id
                or row["teams"]["home"]["id"] != candidate.home_team_id
                or row["teams"]["away"]["id"] != candidate.away_team_id):
            raise RuntimeError("model refresh source identity/details unavailable")
        status = row["fixture"].get("status")
        if not isinstance(status, dict) or not isinstance(status.get("short"), str) or not status["short"]:
            raise RuntimeError("model refresh fixture status unavailable")
        if _reconcile_candidate_fixture(deepcopy(candidate), row, now=now, search_date=search_date):
            fixtures.append(row)
        else:
            invalidated.append(fixture_id)
    result = {"candidates": [], "wettfinder_candidates": [], "basis_forecasts": [],
              "riskobet_source_candidates": [], "riskobet_context_checked_fixture_ids": [],
              "context_fixture_statuses": {}, "errors": [], "modeled_fixture_ids": []}
    if fixtures:
        result = scan_daily_challenge(
            _FixtureBatchProvider(provider, fixtures, details),
            sorted({row["league"]["id"] for row in fixtures}), search_date, len(fixtures),
            allow_above_challenge_probability=True, candidate_profile="wettfinder",
            # Reuse stored xG observations; background refresh cannot multiply
            # the discovery worker's optional xG acquisition budget.
            max_new_xg_calls=0,
        )
        if result.get("operational_errors"):
            raise RuntimeError("model refresh inputs incomplete; prior model retained")
        modeled_ids = set(result["modeled_fixture_ids"])
        if modeled_ids != {row["fixture"]["id"] for row in fixtures}:
            raise RuntimeError("model refresh could not recompute every requested fixture")
        result["candidates"] = list({candidate.candidate_id: candidate
            for field in ("discovery_candidates", "wettfinder_candidates", "basis_forecasts")
            for candidate in result.get(field, ())}.values())
    finished = datetime.now(timezone.utc).isoformat()
    result["fixture_ids"] = sorted(by_fixture)
    result["invalidated_fixture_ids"] = sorted(set(invalidated) | set(result.get("invalidated_fixture_ids", ())))
    result["checked_at"] = finished
    result["model_refresh"] = {
        "version": MODEL_REFRESH_VERSION,
        "fixture_ids": result["modeled_fixture_ids"],
        "modeled_at": finished, "input_cutoff_at": finished,
    }
    return result
