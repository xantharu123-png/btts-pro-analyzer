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
            from scanners.api_hockey import APIHockeyScanner, DEFAULT_CANDIDATES
            api = APIHockeyScanner(load_app_config().api_football_key, candidates=DEFAULT_CANDIDATES)
        self.nhl, self.api = nhl, api
        self.errors, self.history_coverage = {}, {}

    def get_upcoming_games(self, start: date, end: date, *, nhl_end: date | None = None):
        history_window(start, end)
        if (end - start).days > 14:
            raise ValueError("Schedule window must span zero to fourteen days")
        native_end = end if nhl_end is None else nhl_end
        history_window(start, native_end)
        if (native_end - start).days > 14:
            raise ValueError("Schedule window must span zero to fourteen days")
        self.errors, rows = {}, []
        for provider, scanner, method in (
            ("NHL", self.nhl, self.nhl.get_upcoming_nhl_games),
            ("API-Hockey", self.api, self.api.get_upcoming_games),
        ):
            try:
                extra = list(method(start, native_end if provider == "NHL" else end))
                # NHL stays on its existing free native source. Never count a
                # second provider's copy as independent evidence.
                rows.extend(row for row in extra if provider == "NHL"
                            or str(row.get("competition", "")).casefold() != "nhl")
                self.errors.update(getattr(scanner, "errors", {}))
            except Exception as exc:
                self.errors[f"{provider}:schedule"] = type(exc).__name__
        return sorted(rows, key=lambda row: (row.get("start_time", ""), row.get("provider", ""), row.get("provider_event_id", "")))

    def get_completed_games(self, start: date, end: date, *, as_of=None, events=None):
        history_window(start, end)
        if as_of is not None and utc_time(as_of) is None:
            raise ValueError("History as_of must be timezone-aware")
        # Only providers needed by this batch load history. Old results become
        # available at their real first receipt, never at a guessed finish.
        if events is not None and (type(events) not in (list, tuple)
                                  or any(type(row) is not dict for row in events)):
            raise ValueError("Invalid hockey event scope")
        self.errors, rows, coverage = {}, [], []
        provider_events = {"NHL": [], "API-Hockey": []}
        for row in events or ():
            provider = row.get("provider") or row.get("source")
            if (type(provider) is not str or provider not in provider_events
                    or any(row.get(key) not in (None, provider) for key in ("provider", "source"))
                    or row.get("sport") not in (None, "ice_hockey")
                    or provider == "NHL" and row.get("source_contract") is not None):
                self.errors["scope"] = "invalid_history_scope"
                continue
            provider_events[provider].append(row)
        if self.errors:
            coverage.append({"status": "partial"})
        for provider, scanner, method in (
            ("NHL", self.nhl, self.nhl.get_completed_nhl_games),
            ("API-Hockey", self.api, self.api.get_completed_games),
        ):
            if events is not None and not provider_events[provider]:
                continue
            try:
                kwargs = {"as_of": as_of}
                if provider == "API-Hockey":
                    kwargs["events"] = None if events is None else provider_events[provider]
                rows.extend(list(method(start, end, **kwargs)))
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


def completed_hockey_loader(scanner, target_date, *, collector=None):
    def load(*, as_of, events=None, **_kwargs):
        rows = scanner.get_completed_games(target_date - timedelta(days=365), target_date,
                                           as_of=as_of, events=events)
        load.coverage = scanner.history_coverage
        if collector is not None:
            try:
                collector(events=events, completed_rows=rows)
            except Exception:
                # Optional source intake never erases valid baseline results or
                # changes their result-status coverage. Admin reporting is owned
                # by the collector closure, not public forecast prose.
                pass
        return rows
    return load
