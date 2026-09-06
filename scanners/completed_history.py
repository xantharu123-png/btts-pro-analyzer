"""Bounded, observed-at result history for the scanners' existing providers.

Provider scoreboards usually expose a kickoff, not the time a result became
known. Results therefore become usable at their first real retrieval. They are
never backdated to kickoff (nor to a guessed game duration). Corrections retain
their own observation time so historical as-of reads cannot see the correction.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

import requests

from runtime_paths import RUNTIME_STATE_DIR

UTC = timezone.utc
SEARCH_TIMEZONE = ZoneInfo("Europe/Zurich")
DEFAULT_HISTORY_PATH = RUNTIME_STATE_DIR / "sports_completed_history.db"


def utc_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def history_window(start: date, end: date) -> tuple[date, date]:
    if (
        isinstance(start, datetime) or not isinstance(start, date)
        or isinstance(end, datetime) or not isinstance(end, date)
        or not 0 <= (end - start).days <= 366
    ):
        raise ValueError("History window must span zero to 366 days")
    return start, end


def text(value: object) -> str:
    return str(value).strip() if isinstance(value, (str, int)) and not isinstance(value, bool) else ""


def whole(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None


def result_row(
    *, provider: str, event_id: object, start: object, home: object, away: object,
    home_id: object = None, away_id: object = None, home_score: object = None,
    away_score: object = None, winner: str | None = None, **features: object,
) -> dict | None:
    played = utc_time(start)
    home_name, away_name, identity = text(home), text(away), text(event_id)
    if (
        played is None or not identity or not home_name or not away_name
        or home_name.casefold() == away_name.casefold()
        or (text(home_id) and text(home_id) == text(away_id))
    ):
        return None
    hs, aws = whole(home_score), whole(away_score)
    if winner is None and hs is not None and aws is not None and hs != aws:
        winner = "home" if hs > aws else "away"
    if winner not in {"home", "away"}:
        return None
    return {
        "provider": provider, "source": provider, "provider_event_id": identity,
        "event_id": identity, "start_time": played.isoformat(), "status": "completed",
        "home_team": home_name, "away_team": away_name,
        "home_team_id": text(home_id), "away_team_id": text(away_id),
        "home_score": hs, "away_score": aws, "winner_side": winner, **features,
    }


class CompletedHistoryStore:
    """Cross-process cache plus per-provider daily request reservations.

    The request key never contains authentication values. A reservation is
    committed before network I/O; failed requests consume budget and cool down.
    No credentials or raw provider error messages are persisted.
    """

    def __init__(self, path: Path | str = DEFAULT_HISTORY_PATH, *, clock=None):
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS history_requests (
                    cache_key TEXT PRIMARY KEY, provider TEXT NOT NULL,
                    attempted_at TEXT NOT NULL, success_at TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS history_budget (
                    provider TEXT NOT NULL, day TEXT NOT NULL, requests INTEGER NOT NULL,
                    PRIMARY KEY(provider, day)
                );
                CREATE TABLE IF NOT EXISTS history_result_revisions (
                    provider TEXT NOT NULL, event_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(provider, event_id, observed_at)
                );
                CREATE INDEX IF NOT EXISTS history_results_asof
                    ON history_result_revisions(provider, observed_at);
            """)

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    def due(self, provider: str, key: str, *, ttl: timedelta) -> bool:
        now = self.clock()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT attempted_at, success_at FROM history_requests WHERE cache_key=?",
                (f"{provider}:{key}",),
            ).fetchone()
        if row is None:
            return True
        attempted, success = utc_time(row[0]), utc_time(row[1])
        return bool(
            attempted is not None and now - attempted >= timedelta(minutes=30)
            and (success is None or now - success >= ttl)
        )

    def reserve(self, provider: str, key: str, *, ttl: timedelta, daily_limit: int) -> bool:
        now = self.clock()
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT attempted_at,success_at FROM history_requests WHERE cache_key=?",
                (f"{provider}:{key}",),
            ).fetchone()
            if row:
                attempted, success = utc_time(row[0]), utc_time(row[1])
                if (
                    attempted is None or now - attempted < timedelta(minutes=30)
                    or (success is not None and now - success < ttl)
                ):
                    return False
            count = connection.execute(
                "SELECT requests FROM history_budget WHERE provider=? AND day=?",
                (provider, now.date().isoformat()),
            ).fetchone()
            if count and count[0] >= daily_limit:
                return False
            connection.execute(
                "INSERT INTO history_budget VALUES(?,?,1) ON CONFLICT(provider,day) "
                "DO UPDATE SET requests=requests+1", (provider, now.date().isoformat()),
            )
            connection.execute(
                "INSERT INTO history_requests VALUES(?,?,?,NULL,NULL) "
                "ON CONFLICT(cache_key) DO UPDATE SET attempted_at=excluded.attempted_at,error=NULL",
                (f"{provider}:{key}", provider, now.isoformat()),
            )
        return True

    def record(self, provider: str, key: str, rows: Iterable[dict], *, error: str | None = None):
        observed = self.clock()
        with closing(self._connect()) as connection, connection:
            for row in rows:
                played = utc_time(row.get("start_time"))
                if row.get("provider") != provider or played is None or played >= observed:
                    continue
                payload = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
                digest = hashlib.sha256(payload.encode()).hexdigest()
                previous = connection.execute(
                    "SELECT digest FROM history_result_revisions WHERE provider=? AND event_id=? "
                    "ORDER BY observed_at DESC LIMIT 1", (provider, row["event_id"]),
                ).fetchone()
                if previous and previous[0] == digest:
                    continue
                connection.execute(
                    "INSERT OR IGNORE INTO history_result_revisions VALUES(?,?,?,?,?)",
                    (provider, row["event_id"], observed.isoformat(), digest, payload),
                )
            connection.execute(
                "UPDATE history_requests SET success_at=CASE WHEN ? IS NULL THEN ? ELSE success_at END, "
                "error=? WHERE cache_key=?",
                (error, observed.isoformat(), error, f"{provider}:{key}"),
            )

    def read(self, providers: Iterable[str], start: date, end: date, *, as_of=None) -> list[dict]:
        history_window(start, end)
        cutoff = self.clock() if as_of is None else utc_time(as_of)
        if cutoff is None or cutoff > self.clock():
            raise ValueError("History as_of must be an aware time no later than now")
        names = tuple(providers)
        if not names:
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT provider,event_id,observed_at,payload FROM history_result_revisions "
                f"WHERE provider IN ({','.join('?' for _ in names)}) AND observed_at<=? "
                "ORDER BY observed_at", (*names, cutoff.isoformat()),
            ).fetchall()
        latest = {}
        for provider, event_id, observed, payload in rows:
            latest[(provider, event_id)] = (observed, json.loads(payload))
        accepted = []
        for observed, row in latest.values():
            played = utc_time(row["start_time"])
            if played is not None and played < cutoff and start <= played.astimezone(SEARCH_TIMEZONE).date() <= end:
                accepted.append({**row, "result_observed_at": observed, "fetched_at": observed})
        return sorted(accepted, key=lambda row: (row["start_time"], row["provider"], row["event_id"]))

    def request_error(self, provider: str, key: str) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT error,success_at,attempted_at FROM history_requests WHERE cache_key=?",
                (f"{provider}:{key}",),
            ).fetchone()
        if row is None:
            return "Daily history request budget reached"
        if row[0]:
            return row[0]
        if row[1] is None or row[2] > row[1]:
            return "History request pending"
        return None

    def validate_asof(self, as_of):
        if as_of is not None and (utc_time(as_of) is None or utc_time(as_of) > self.clock()):
            raise ValueError("History as_of must be an aware time no later than now")


def fetch_page(store, provider, key, url, parser, *, params=None, headers=None, ttl=timedelta(hours=12), daily_limit=48):
    if not store.reserve(provider, key, ttl=ttl, daily_limit=daily_limit):
        return False, store.request_error(provider, key)
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")
        rows = parser(response.json())
        store.record(provider, key, rows)
        return True, None
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        # Deliberately omit exception bodies; request URLs may contain API keys.
        error = str(exc) if isinstance(exc, ValueError) and str(exc).startswith("HTTP ") else type(exc).__name__
        store.record(provider, key, (), error=error)
        return True, error


def parse_espn_results(payload) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("Invalid ESPN result payload")
    results = []
    for event in payload["events"]:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions", [])
        if not isinstance(competitions, list):
            continue
        for game in competitions:
            if not isinstance(game, dict):
                continue
            status = game.get("status", {})
            kind = status.get("type", {}) if isinstance(status, dict) else {}
            if not isinstance(kind, dict) or kind.get("completed") is not True or kind.get("state") != "post":
                continue
            competitors = game.get("competitors", [])
            if not isinstance(competitors, list) or len(competitors) != 2:
                continue
            sides = {x.get("homeAway"): x for x in competitors if isinstance(x, dict)}
            h, a = sides.get("home", {}), sides.get("away", {})
            ht, at = h.get("team", {}), a.get("team", {})
            if not isinstance(ht, dict) or not isinstance(at, dict):
                continue
            hs, aws = whole(h.get("score")), whole(a.get("score"))
            if hs is None or aws is None or hs == aws:
                continue
            expected = "home" if hs > aws else "away"
            if any(
                isinstance(side.get("winner"), bool) and side["winner"] != (label == expected)
                for label, side in (("home", h), ("away", a))
            ):
                continue
            row = result_row(
                provider="ESPN", event_id=game.get("id") or event.get("id"),
                start=game.get("date") or event.get("date"),
                home=ht.get("abbreviation") or ht.get("displayName"),
                away=at.get("abbreviation") or at.get("displayName"),
                home_id=ht.get("id"), away_id=at.get("id"), home_score=hs, away_score=aws,
                sport="basketball", league="NBA", competition="NBA",
                neutral_site=game.get("neutralSite") if isinstance(game.get("neutralSite"), bool) else None,
                periods=whole(status.get("period")), result_scope="including_overtime",
            )
            if row:
                results.append(row)
    return results


def parse_euroleague_results(payload) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Invalid EuroLeague result payload")
    results = []
    for game in payload["data"]:
        if not isinstance(game, dict) or game.get("played") is not True:
            continue
        h, a = game.get("local", {}), game.get("road", {})
        if not isinstance(h, dict) or not isinstance(a, dict):
            continue
        ht, at = h.get("club", {}), a.get("club", {})
        if not isinstance(ht, dict) or not isinstance(at, dict):
            continue
        hs, aws = whole(h.get("score")), whole(a.get("score"))
        if hs is None or aws is None or hs == aws:
            continue
        winner = game.get("winner", {})
        expected = text(ht.get("code") if hs > aws else at.get("code"))
        if isinstance(winner, dict) and text(winner.get("code")) and text(winner["code"]) != expected:
            continue
        row = result_row(
            provider="EuroLeague", event_id=game.get("id") or game.get("identifier"),
            start=game.get("utcDate"), home=ht.get("code"), away=at.get("code"),
            home_id=ht.get("code"), away_id=at.get("code"), home_score=hs, away_score=aws,
            sport="basketball", league="Euroleague", competition="Euroleague",
            neutral_site=game.get("isNeutralVenue") if isinstance(game.get("isNeutralVenue"), bool) else None,
            result_scope="including_overtime",
        )
        if row:
            results.append(row)
    return results


def parse_nhl_results(payload) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("gameWeek"), list):
        raise ValueError("Invalid NHL result payload")
    results = []
    for day in payload["gameWeek"]:
        games = day.get("games", []) if isinstance(day, dict) else []
        if not isinstance(games, list):
            continue
        for game in games:
            if not isinstance(game, dict) or game.get("gameState") not in {"FINAL", "OFF"}:
                continue
            h, a = game.get("homeTeam", {}), game.get("awayTeam", {})
            if not isinstance(h, dict) or not isinstance(a, dict):
                continue
            hs, aws = whole(h.get("score")), whole(a.get("score"))
            if hs is None or aws is None or hs == aws:
                continue
            outcome = game.get("gameOutcome", {})
            row = result_row(
                provider="NHL", event_id=game.get("id"), start=game.get("startTimeUTC"),
                home=h.get("abbrev"), away=a.get("abbrev"),
                home_id=h.get("id"), away_id=a.get("id"), home_score=hs, away_score=aws,
                sport="ice_hockey", league="NHL", competition="NHL",
                season=text(game.get("season")), game_type=whole(game.get("gameType")),
                neutral_site=game.get("neutralSite") if isinstance(game.get("neutralSite"), bool) else None,
                last_period_type=text(outcome.get("lastPeriodType")) if isinstance(outcome, dict) else "",
                result_scope="including_overtime_shootout",
            )
            if row:
                results.append(row)
    return results


def completed_basketball(scanner, league, start, end, *, as_of=None, store=None):
    history_window(start, end)
    if league not in {"NBA", "Euroleague", "All"}:
        raise ValueError("Unknown basketball league")
    store = store or CompletedHistoryStore()
    store.validate_asof(as_of)
    errors = []
    providers = []
    windows_complete = True
    if league in {"NBA", "All"}:
        providers.append("ESPN")
        # Month buckets let cold history fill gradually, then remain cached.
        cursor, calls = min(end, store.clock().date()).replace(day=1), 0
        while calls < 4:
            next_month = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            last = next_month - timedelta(days=1)
            if last < start:
                break
            key = f"nba:{cursor.isoformat()}"
            ttl = timedelta(hours=6) if last >= store.clock().date() - timedelta(days=14) else timedelta(days=7)
            if store.due("ESPN", key, ttl=ttl):
                attempted, error = fetch_page(
                    store, "ESPN", key, scanner.espn_nba_url, parse_espn_results,
                    params={"dates": f"{cursor:%Y%m%d}-{last:%Y%m%d}", "limit": 1000},
                    headers={"User-Agent": scanner.nba_headers["User-Agent"], "Accept": "application/json"}, ttl=ttl,
                )
                calls += int(attempted)
                if error:
                    errors.append(f"NBA history: {error}")
                    break
            else:
                cached_error = store.request_error("ESPN", key)
                if cached_error:
                    errors.append(f"NBA history: {cached_error}")
                    break
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        cursor_end = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        windows_complete = cursor_end < start and not errors
    if league in {"Euroleague", "All"}:
        providers.append("EuroLeague")
        for year in range(start.year - 1, end.year + 1):
            season_start, season_end = date(year, 7, 1), date(year + 1, 6, 30)
            if season_end < start or season_start > end:
                continue
            season = f"E{year}"
            ttl = timedelta(hours=6) if season_end >= store.clock().date() else timedelta(days=7)
            _, error = fetch_page(
                store, "EuroLeague", season,
                f"{scanner.euroleague_games_base}/competitions/E/seasons/{season}/games",
                parse_euroleague_results, params={"limit": 500}, ttl=ttl,
            )
            if error:
                errors.append(f"EuroLeague history: {error}")
    if errors:
        scanner.errors["basketball_history"] = "; ".join(errors)
    else:
        scanner.errors.pop("basketball_history", None)
    rows = store.read(providers, start, end, as_of=as_of)
    scanner.history_coverage = {
        "sport": "basketball", "requested_start": start.isoformat(), "requested_end": end.isoformat(),
        "status": "complete" if windows_complete and not errors else "partial",
        "returned_results": len(rows), "errors": tuple(errors),
        "pending_observations": max(0, len(store.read(providers, start, end)) - len(rows)),
    }
    return rows


def completed_nhl(scanner, start, end, *, as_of=None, store=None):
    history_window(start, end)
    store = store or CompletedHistoryStore()
    store.validate_asof(as_of)
    errors, calls = [], 0
    # Monday anchors are disjoint seven-day schedule windows.
    last_day = min(end, store.clock().date())
    cursor = last_day - timedelta(days=last_day.weekday())
    while cursor + timedelta(days=6) >= start and calls < 8:
        key = cursor.isoformat()
        ttl = timedelta(hours=6) if cursor >= store.clock().date() - timedelta(days=14) else timedelta(days=7)
        if store.due("NHL", key, ttl=ttl):
            attempted, error = fetch_page(
                store, "NHL", key, f"{scanner.nhl_schedule_base}/{key}", parse_nhl_results,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, ttl=ttl,
            )
            calls += int(attempted)
            if error:
                errors.append(f"NHL history: {error}")
                break
        else:
            cached_error = store.request_error("NHL", key)
            if cached_error:
                errors.append(f"NHL history: {cached_error}")
                break
        cursor -= timedelta(days=7)
    if errors:
        scanner.errors["nhl_history"] = "; ".join(errors)
    else:
        scanner.errors.pop("nhl_history", None)
    rows = store.read(("NHL",), start, end, as_of=as_of)
    scanner.history_coverage = {
        "sport": "ice_hockey", "requested_start": start.isoformat(), "requested_end": end.isoformat(),
        "status": "complete" if cursor + timedelta(days=6) < start and not errors else "partial",
        "returned_results": len(rows), "errors": tuple(errors),
        "pending_observations": max(0, len(store.read(("NHL",), start, end)) - len(rows)),
    }
    return rows


def cricket_winner(info, home, away):
    """Use explicit winner identity/result text, never compare innings runs.

    Run totals cannot establish the winner under DLS or differing innings.
    Draws, ties, abandonments and no-results have no binary winner history.
    """
    status = text(info.get("status")).casefold()
    if any(token in status for token in ("no result", "abandon", "cancel", "match drawn", "match tied")):
        return None
    winner = text(info.get("matchWinner") or info.get("winner"))
    if winner.casefold() in {text(home).casefold(), text(away).casefold()}:
        return "home" if winner.casefold() == text(home).casefold() else "away"
    matches = [side for side, name in (("home", home), ("away", away)) if status.startswith(text(name).casefold() + " won by ")]
    return matches[0] if len(matches) == 1 else None


def parse_cricbuzz_results(payload) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("typeMatches"), list):
        raise ValueError("Invalid Cricbuzz result payload")
    results = []
    for group in payload["typeMatches"]:
        series = group.get("seriesMatches", []) if isinstance(group, dict) else []
        if not isinstance(series, list):
            continue
        for item in series:
            wrapper = item.get("seriesAdWrapper", {}) if isinstance(item, dict) else {}
            games = wrapper.get("matches", []) if isinstance(wrapper, dict) else []
            if not isinstance(games, list):
                continue
            for game in games:
                info = game.get("matchInfo", {}) if isinstance(game, dict) else {}
                if not isinstance(info, dict) or text(info.get("state")).casefold() != "complete":
                    continue
                h, a = info.get("team1", {}), info.get("team2", {})
                if not isinstance(h, dict) or not isinstance(a, dict):
                    continue
                start_value = info.get("startDate")
                try:
                    if isinstance(start_value, bool):
                        continue
                    start = datetime.fromtimestamp(float(start_value) / 1000.0, UTC)
                except (ValueError, TypeError, OSError, OverflowError):
                    continue
                winner = cricket_winner(info, h.get("teamName"), a.get("teamName"))
                row = result_row(
                    provider="Cricbuzz", event_id=info.get("matchId"), start=start,
                    home=h.get("teamName"), away=a.get("teamName"),
                    home_id=h.get("teamId"), away_id=a.get("teamId"), winner=winner,
                    sport="cricket", competition=text(info.get("seriesName")),
                    format=text(info.get("matchFormat")).casefold(), result_scope="match_winner",
                )
                if row:
                    results.append(row)
    return results


def parse_cricketdata_results(payload) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("status") != "success" or not isinstance(payload.get("data"), list):
        raise ValueError("Invalid CricketData result payload")
    results = []
    for game in payload["data"]:
        if not isinstance(game, dict) or game.get("matchEnded") is not True:
            continue
        teams = game.get("teams")
        if not isinstance(teams, list) or len(teams) != 2:
            continue
        start = game.get("dateTimeGMT")
        # This provider explicitly labels a naive dateTimeGMT as GMT.
        if isinstance(start, str) and utc_time(start) is None:
            try:
                parsed = datetime.fromisoformat(start)
                start = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
            except ValueError:
                continue
        row = result_row(
            provider="CricketData", event_id=game.get("id"), start=start,
            home=teams[0], away=teams[1], winner=cricket_winner(game, *teams),
            sport="cricket", competition=text(game.get("name")),
            format=text(game.get("matchType")).casefold(), result_scope="match_winner",
        )
        if row:
            results.append(row)
    return results


def completed_cricket(scanner, start, end, *, as_of=None, store=None):
    history_window(start, end)
    if not scanner.rapidapi_key and not scanner.cricket_api_key:
        scanner.last_error = "Cricket API key missing"
        scanner.history_coverage = {"sport": "cricket", "status": "unavailable", "returned_results": 0, "errors": (scanner.last_error,)}
        return []
    store = store or CompletedHistoryStore()
    store.validate_asof(as_of)
    providers, errors = [], []
    if scanner.rapidapi_key:
        providers.append("Cricbuzz")
        _, error = fetch_page(
            store, "Cricbuzz", "recent", f"{scanner.cricbuzz_base}/matches/v1/recent",
            parse_cricbuzz_results, headers=scanner.headers, daily_limit=4,
        )
        if error:
            errors.append(f"Cricbuzz history: {error}")
    if scanner.cricket_api_key:
        providers.append("CricketData")
        _, error = fetch_page(
            store, "CricketData", "current-completed", f"{scanner.public_api}/currentMatches",
            parse_cricketdata_results, params={"apikey": scanner.cricket_api_key, "offset": 0}, daily_limit=4,
        )
        if error:
            errors.append(f"CricketData history: {error}")
    scanner.last_error = "; ".join(errors) if errors else None
    rows = store.read(providers, start, end, as_of=as_of)
    scanner.history_coverage = {
        "sport": "cricket", "requested_start": start.isoformat(), "requested_end": end.isoformat(),
        "status": "partial", "returned_results": len(rows), "errors": tuple(errors),
        "coverage_note": "Recent-result feeds accumulate history; full requested-range coverage is not asserted.",
        "pending_observations": max(0, len(store.read(providers, start, end)) - len(rows)),
    }
    return rows
