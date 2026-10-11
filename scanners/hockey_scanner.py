"""One hockey entry point: existing NHL plus reviewed API-Hockey leagues.

The daily owner retains its schedule. No additional timer or API call occurs
on import, rendering, price lookup, or settlement. Source identities are never
merged by team names, and a missing paid-provider entitlement leaves NHL intact.
"""
from datetime import date, timedelta

from scanners.completed_history import history_window, utc_time


class HockeyScanner:
    def __init__(self, *, nhl=None, api=None):
        if nhl is None:
            from scanners.basketball_scanner import BasketballScanner
            nhl = BasketballScanner()
        if api is None:
            from config_loader import load_app_config
            from scanners.api_hockey import APIHockeyScanner
            api = APIHockeyScanner(load_app_config().api_football_key)
        self.nhl, self.api = nhl, api
        self.errors, self.history_coverage = {}, {}

    def get_upcoming_games(self, start: date, end: date):
        history_window(start, end)
        if (end - start).days > 14:
            raise ValueError("Schedule window must span zero to fourteen days")
        self.errors, rows = {}, []
        for provider, scanner, method in (
            ("NHL", self.nhl, self.nhl.get_upcoming_nhl_games),
            ("API-Hockey", self.api, self.api.get_upcoming_games),
        ):
            try:
                extra = list(method(start, end))
                # NHL stays on its existing free native source. Never count a
                # second provider's copy as independent evidence.
                rows.extend(row for row in extra if provider == "NHL"
                            or str(row.get("competition", "")).casefold() != "nhl")
                self.errors.update(getattr(scanner, "errors", {}))
            except Exception as exc:
                self.errors[f"{provider}:schedule"] = type(exc).__name__
        return sorted(rows, key=lambda row: (row.get("start_time", ""), row.get("provider", ""), row.get("provider_event_id", "")))

    def get_completed_games(self, start: date, end: date, *, as_of=None, events=()):
        history_window(start, end)
        if as_of is not None and utc_time(as_of) is None:
            raise ValueError("History as_of must be timezone-aware")
        # Only providers needed by this batch load history. Old results become
        # available at their real first receipt, never at a guessed finish.
        providers = {row.get("provider") or row.get("source") for row in events}
        self.errors, rows, coverage = {}, [], []
        for provider, scanner, method in (
            ("NHL", self.nhl, self.nhl.get_completed_nhl_games),
            ("API-Hockey", self.api, self.api.get_completed_games),
        ):
            if providers and provider not in providers:
                continue
            try:
                rows.extend(list(method(start, end, as_of=as_of)))
                coverage.append(getattr(scanner, "history_coverage", {}))
                self.errors.update(getattr(scanner, "errors", {}))
            except Exception as exc:
                self.errors[f"{provider}:history"] = type(exc).__name__
                coverage.append({"status": "partial"})
        self.history_coverage = {
            "status": "partial" if any(c.get("status") not in (None, "complete") for c in coverage) else "complete",
            "pending_observations": sum(c.get("pending_observations", 0) for c in coverage),
        }
        return rows


def completed_hockey_loader(scanner, target_date):
    def load(*, as_of, events=(), **_kwargs):
        rows = scanner.get_completed_games(target_date - timedelta(days=365), target_date,
                                           as_of=as_of, events=events)
        load.coverage = scanner.history_coverage
        return rows
    return load
