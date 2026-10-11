"""Native API-Hockey schedules/results, not an NHL adapter or model approval.

Schema: https://api-sports.io/documentation/hockey/v1 (reviewed 2026-10-11).
League IDs come from the account's actual catalogue, never this name list.
The three regulation periods, final scores and native terminal phase remain
separate. Unknown rules/lineups/neutral venues are not invented here.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import re

import requests

from api_budget import APIBudgetGovernor, DEFAULT_DB_PATH
from scanners.completed_history import CompletedHistoryStore, history_window, utc_time
from team_sport_prices import _json_get

PROVIDER = "API-Hockey"
SCHEMA = "api-hockey-native-periods-v1"
SOURCE_CONTRACT = "api-hockey-games-v1"
MAX_ROWS = 2500
MAX_CACHE_BYTES = 2_000_000
TERMINAL = {"FT": "REG", "AOT": "OT", "AP": "SO"}
STATUSES = frozenset((*TERMINAL, "NS", "P1", "P2", "P3", "OT", "PT", "BT", "AW", "POST", "CANC", "INTR", "ABD"))
HISTORY_TTL = timedelta(hours=20)


@dataclass(frozen=True)
class LeagueCandidate:
    name: str
    country: str


# Candidate coverage, NOT twenty configured/validated leagues. The official
# coverage page uses these names; a renamed/missing league requires review.
CANDIDATES = tuple(LeagueCandidate(name, country) for name, country in (
    ("National League", "Switzerland"), ("Swiss League", "Switzerland"),
    ("NHL", "USA"), ("AHL", "USA"), ("ECHL", "USA"),
    ("SHL", "Sweden"), ("Hockey Allsvenskan", "Sweden"),
    ("Liiga", "Finland"), ("Mestis", "Finland"),
    ("DEL", "Germany"), ("DEL 2", "Germany"),
    ("Extraliga", "Czech-Republic"), ("Extraliga", "Slovakia"),
    ("ICE Hockey League", "Austria"), ("Metal Ligaen", "Denmark"),
    ("Fjordkraft-ligaen", "Norway"), ("Ligue Magnus", "France"),
    ("Elite League", "United-Kingdom"), ("KHL", "Russia"), ("VHL", "Russia"),
))


def supported_competition(name):
    """Exact reviewed names only; event/team/league IDs must still be bound."""
    return type(name) is str and any(name == row.name for row in CANDIDATES)


@dataclass(frozen=True)
class LeagueSeason:
    league_id: int
    name: str
    country: str
    country_id: int
    season: int
    start: date
    end: date

    def __post_init__(self):
        _positive(self.league_id)
        _positive(self.country_id)
        _text(self.name)
        _text(self.country)
        if type(self.season) is not int or not 1000 <= self.season <= 9999:
            raise ValueError("invalid native season")
        history_window(self.start, self.end)


def _positive(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("invalid native integer")
    return value


def _text(value):
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError("invalid native name")
    return value


def _day(value):
    if type(value) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise ValueError("invalid native day")
    return date.fromisoformat(value)


def _clock(value):
    parsed = utc_time(value)
    if parsed is None:
        raise ValueError("aware clock required")
    return parsed


def _rows(value):
    if type(value) is not list or len(value) > MAX_ROWS or any(type(row) is not dict for row in value):
        raise ValueError("invalid or oversized native response")
    return value


def _catalogue(catalogue, start, end, candidates):
    history_window(start, end)
    wanted = {(c.name, c.country): index for index, c in enumerate(candidates)}
    found, identities, names = {}, {}, {}
    for row in _rows(catalogue):
        country = row.get("country")
        if type(country) is not dict or (row.get("name"), country.get("name")) not in wanted:
            continue
        if row.get("type") != "League":
            continue
        pair = (_text(row["name"]), _text(country["name"]))
        identity, country_id = _positive(row.get("id")), _positive(country.get("id"))
        if identity in identities and identities[identity] != pair:
            raise ValueError("conflicting native league ID")
        if pair in names and names[pair] != identity:
            raise ValueError("native league ID changed across seasons")
        identities[identity] = pair
        names[pair] = identity
        seasons = _rows(row.get("seasons"))
        for item in seasons:
            season = _positive(item.get("season"))
            first, last = _day(item.get("start")), _day(item.get("end"))
            if not 1000 <= season <= 9999 or first > last or type(item.get("current")) is not bool:
                raise ValueError("invalid native season")
            if first > end or last < start:
                continue
            definition = LeagueSeason(identity, *pair, country_id, season, first, last)
            key = (pair, season)
            if key in found and found[key] != definition:
                raise ValueError("ambiguous native league/season")
            found[key] = definition
    return tuple(sorted(found.values(), key=lambda row: (wanted[row.name, row.country], -row.season)))


def resolve_leagues(catalogue, *, on: date, candidates=CANDIDATES):
    """Resolve exact reviewed name/country pairs in actual season date bounds."""
    definitions = _catalogue(catalogue, on, on, candidates)
    if len({(row.name, row.country) for row in definitions}) != len(definitions):
        raise ValueError("overlapping native seasons")
    return definitions


def _game(row, leagues):
    native, country = row.get("league"), row.get("country")
    if type(native) is not dict or type(country) is not dict:
        raise ValueError("native competition identity missing")
    matches = [league for league in leagues if native.get("id") == league.league_id
               and native.get("season") == league.season]
    if not matches:
        return None
    if len(set(matches)) != 1:
        raise ValueError("ambiguous native competition")
    league = matches[0]
    if (type(native.get("id")) is not int or type(native.get("season")) is not int
            or native.get("name") != league.name or native.get("type") != "League"
            or type(country.get("id")) is not int or country.get("id") != league.country_id
            or country.get("name") != league.country):
        raise ValueError("native competition binding differs")
    identity = _positive(row.get("id"))
    start = _clock(row.get("date"))
    if not league.start <= start.date() <= league.end:
        raise ValueError("game outside actual native season")
    teams = row.get("teams")
    if type(teams) is not dict or any(type(teams.get(side)) is not dict for side in ("home", "away")):
        raise ValueError("native participants missing")
    home, away = teams["home"], teams["away"]
    home_id, away_id = _positive(home.get("id")), _positive(away.get("id"))
    home_name, away_name = _text(home.get("name")), _text(away.get("name"))
    if home_id == away_id or home_name == away_name:
        raise ValueError("native participants coincide")
    status = row.get("status")
    if type(status) is not dict or status.get("short") not in STATUSES:
        raise ValueError("native status missing")
    return {
        "provider": PROVIDER, "source": PROVIDER, "sport": "ice_hockey",
        "provider_event_id": str(identity), "event_id": str(identity), "game_id": identity,
        "competition_id": str(league.league_id), "league_id": league.league_id,
        "competition": league.name, "league": league.name, "country": league.country,
        "season": league.season, "start_time": start.isoformat(),
        "home_team": home_name, "away_team": away_name,
        "home_team_id": str(home_id), "away_team_id": str(away_id),
        "native_status": status["short"], "source_schema": SCHEMA,
        "source_contract": SOURCE_CONTRACT,
        "neutral_site": None, "phase": None,
    }


def _score_pair(value):
    if type(value) is not str or re.fullmatch(r"\d{1,3}-\d{1,3}", value) is None:
        raise ValueError("invalid native period score")
    return tuple(int(part) for part in value.split("-"))


def _final(row, base):
    periods, final = row.get("periods"), row.get("scores")
    if (type(periods) is not dict or type(final) is not dict
            or any(key not in periods for key in ("first", "second", "third", "overtime", "penalties"))):
        raise ValueError("native final/period scores missing")
    regulation = tuple(_score_pair(periods.get(key)) for key in ("first", "second", "third"))
    h, a = (sum(pair[side] for pair in regulation) for side in (0, 1))
    fh, fa = final.get("home"), final.get("away")
    if any(type(value) is not int or not 0 <= value <= 999 for value in (fh, fa)) or fh == fa:
        raise ValueError("native final winner missing")
    code = base["native_status"]
    overtime = None if periods.get("overtime") is None else _score_pair(periods["overtime"])
    penalties = None if periods.get("penalties") is None else _score_pair(periods["penalties"])
    if code == "FT":
        if (fh, fa) != (h, a) or overtime is not None or penalties is not None:
            raise ValueError("native regulation final contradicts periods")
    elif code == "AOT":
        if h != a or overtime is None or penalties is not None or sum(overtime) != 1:
            raise ValueError("native overtime final contradicts periods")
        if (fh, fa) != (h + overtime[0], a + overtime[1]):
            raise ValueError("native overtime final score differs")
    else:  # AP: the period feed and native final identify the winner separately.
        if h != a or overtime is not None and overtime[0] != overtime[1]:
            raise ValueError("native shootout followed a non-tied game")
        before = (h + (overtime or (0, 0))[0], a + (overtime or (0, 0))[1])
        if min(fh, fa) != before[0] or max(fh, fa) <= before[0]:
            raise ValueError("native shootout final contradicts regulation")
        if penalties is not None and (penalties[0] == penalties[1] or (penalties[0] > penalties[1]) != (fh > fa)):
            raise ValueError("native penalties contradict the final winner")
    return dict(base, status="completed", result_scope="including_overtime_shootout",
                home_score=fh, away_score=fa, home_score_final=fh, away_score_final=fa,
                home_score_regulation=h, away_score_regulation=a,
                regulation_home_score=h, regulation_away_score=a,
                winner_side="home" if fh > fa else "away", last_period_type=TERMINAL[code],
                regulation_periods=[list(pair) for pair in regulation],
                overtime_score=list(overtime) if overtime is not None else None,
                penalty_score=list(penalties) if penalties is not None else None)


def _unique(rows):
    by_id = {}
    for row in rows:
        key = row["provider_event_id"]
        if key in by_id and by_id[key] != row:
            raise ValueError("conflicting native event revisions in one response")
        by_id[key] = row
    return sorted(by_id.values(), key=lambda row: (row["start_time"], row["provider_event_id"]))


def parse_upcoming_games(rows, leagues, *, observed_at, start: date, end: date):
    from scanners.completed_history import SEARCH_TIMEZONE
    cutoff = _clock(observed_at)
    history_window(start, end)
    if (end - start).days > 14:
        raise ValueError("invalid schedule window")
    parsed = []
    for row in _rows(rows):
        base = _game(row, leagues)
        if base is None or base["native_status"] != "NS":
            continue
        kickoff = _clock(base["start_time"])
        if kickoff <= cutoff or not start <= kickoff.astimezone(SEARCH_TIMEZONE).date() <= end:
            continue
        if (type(row.get("scores")) is not dict or any(side not in row["scores"] or row["scores"][side] is not None for side in ("home", "away"))
                or type(row.get("periods")) is not dict
                or any(key not in row["periods"] or row["periods"][key] is not None for key in ("first", "second", "third", "overtime", "penalties"))):
            raise ValueError("scheduled game contains terminal scores")
        parsed.append(dict(base, status="upcoming", source_observed_at=cutoff.isoformat()))
    return _unique(parsed)


def parse_completed_games(rows, leagues, *, observed_at):
    cutoff = _clock(observed_at)
    parsed = []
    for row in _rows(rows):
        base = _game(row, leagues)
        if base is None or base["native_status"] not in TERMINAL:
            continue
        if _clock(base["start_time"]) >= cutoff:
            raise ValueError("terminal result precedes kickoff")
        parsed.append(_final(row, base))
    return _unique(parsed)


def _native_retractions(rows, league, observed_at):
    """Known native IDs cannot retain an old final after withdrawal/conflict.

    Unknown/malformed identities never overwrite an unrelated cached event.
    Bad scores withdraw only that ID; absence from a season response does not.
    """
    removed, seen = {}, {}
    cutoff = _clock(observed_at)
    for raw in rows:
        try:
            base = _game(raw, (league,))
        except (ValueError, TypeError):
            native, country = raw.get("league"), raw.get("country")
            if (type(native) is dict and type(country) is dict
                    and type(native.get("id")) is int and native["id"] == league.league_id
                    and type(native.get("season")) is int and native["season"] == league.season
                    and native.get("name") == league.name and native.get("type") == "League"
                    and type(country.get("id")) is int and country["id"] == league.country_id
                    and country.get("name") == league.country):
                try:
                    key = str(_positive(raw.get("id")))
                except ValueError:
                    continue
                # record() only withdraws an existing result for this canonical
                # provider ID. Bad participants/status never qualify a final,
                # and cannot resurrect the earlier final after a later refresh.
                removed[key] = dict(provider=PROVIDER, event_id=key,
                    status="retracted", retraction_reason="unusable_native_identity")
            continue
        if base is None:
            continue
        key, reason = base["event_id"], None
        if base["native_status"] not in TERMINAL:
            reason = "native_status=" + base["native_status"]
        else:
            try:
                current = _final(raw, base)
                if _clock(base["start_time"]) >= cutoff:
                    raise ValueError("terminal before kickoff")
                if key in seen and seen[key] != current:
                    reason = "ambiguous_native_terminal"
                seen[key] = current
            except (ValueError, TypeError):
                reason = "unusable_native_terminal"
        if reason:
            removed[key] = dict(base, status="retracted", retraction_reason=reason)
    return list(removed.values())


class APIHockeyScanner:
    """Bounded native adapter; construction/import makes no request or writes."""

    def __init__(self, api_key=None, *, governor=None, history_store=None, get=requests.get,
                 clock=None, candidates=CANDIDATES, max_history_requests=8, include_nhl=False):
        if type(max_history_requests) is not int or not 1 <= max_history_requests <= 48:
            raise ValueError("invalid history request bound")
        if type(include_nhl) is not bool:
            raise ValueError("invalid native NHL inclusion")
        self.api_key, self.governor, self.history_store = api_key, governor, history_store
        self.get, self.clock = get, clock or (lambda: datetime.now(timezone.utc))
        self.candidates = tuple(row for row in candidates if include_nhl or (row.name, row.country) != ("NHL", "USA"))
        self.max_history_requests = max_history_requests
        self.errors, self.last_history_report = {}, {}
        self._catalogue_rows, self._catalogue_day = None, None

    def _request(self, endpoint, params):
        if self.api_key is None:
            from config_loader import load_app_config
            self.api_key = load_app_config().api_football_key
        if not self.api_key:
            raise ValueError("API-Hockey key unavailable")
        if self.governor is None:
            self.governor = APIBudgetGovernor(DEFAULT_DB_PATH, daily_limit=100,
                critical_floor=5, recommendation_reserve=10, background_reserve=15)
        return _rows(_json_get("ice_hockey", endpoint, params, self.api_key,
                               governor=self.governor, get=self.get))

    def _store(self):
        if self.history_store is None:
            self.history_store = CompletedHistoryStore(clock=self.clock)
        return self.history_store

    def _cached_request(self, endpoint, params, *, ttl):
        """Small raw catalogue/date cache in the existing result DB, no archive."""
        store, now = self._store(), _clock(self.clock())
        key = endpoint + ":" + json.dumps(params, sort_keys=True, separators=(",", ":"))
        with closing(store._connect()) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS api_hockey_response_cache (cache_key TEXT PRIMARY KEY, observed_at TEXT NOT NULL, expires_at TEXT NOT NULL, payload TEXT NOT NULL)")
            cached = connection.execute("SELECT observed_at,expires_at,payload FROM api_hockey_response_cache WHERE cache_key=?", (key,)).fetchone()
        if cached and len(cached[2].encode()) <= MAX_CACHE_BYTES:
            try:
                observed, expires = _clock(cached[0]), _clock(cached[1])
                if observed <= now < expires and expires - observed <= ttl:
                    return _rows(json.loads(cached[2])), observed
            except (ValueError, TypeError):
                pass
        rows = self._request(endpoint, params)
        observed = _clock(self.clock())
        payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(payload.encode()) > MAX_CACHE_BYTES:
            raise ValueError("oversized native response cache")
        with closing(store._connect()) as connection, connection:
            connection.execute("DELETE FROM api_hockey_response_cache WHERE expires_at<=?", (observed.isoformat(),))
            connection.execute("INSERT OR REPLACE INTO api_hockey_response_cache VALUES(?,?,?,?)", (key, observed.isoformat(), (observed + ttl).isoformat(), payload))
            connection.execute("DELETE FROM api_hockey_response_cache WHERE cache_key IN (SELECT cache_key FROM api_hockey_response_cache ORDER BY observed_at DESC,cache_key LIMIT -1 OFFSET 16)")
        return rows, observed

    def _catalogue(self):
        today = _clock(self.clock()).date()
        if self._catalogue_rows is None or self._catalogue_day != today:
            rows, _ = self._cached_request("leagues", {}, ttl=timedelta(days=1))
            self._catalogue_rows, self._catalogue_day = rows, today
        return self._catalogue_rows

    def resolve_leagues(self, on):
        return resolve_leagues(self._catalogue(), on=on, candidates=self.candidates)

    @staticmethod
    def _history_order(store, leagues):
        # Missing batches first, then least recently attempted. Stable catalogue
        # order alone would starve league9+ under the daily eight-request bound.
        with closing(store._connect()) as connection:
            attempts = dict(connection.execute("SELECT cache_key,attempted_at FROM history_requests WHERE provider=?", (PROVIDER,)))
        return sorted(leagues, key=lambda row: attempts.get(f"{PROVIDER}:league:{row.league_id}:season:{row.season}", ""))

    def get_upcoming_games(self, start, end):
        self.errors.pop("schedule", None)
        history_window(start, end)
        if (end - start).days > 14:
            raise ValueError("invalid schedule window")
        try:
            leagues = _catalogue(self._catalogue(), start, end, self.candidates)
            if not leagues:
                return []
            output = []
            for offset in range((end - start).days + 1):
                day = start + timedelta(days=offset)
                rows, observed = self._cached_request("games", {"date": day.isoformat(), "timezone": "Europe/Zurich"}, ttl=timedelta(hours=3))
                output.extend(parse_upcoming_games(rows, leagues, observed_at=observed, start=start, end=end))
            return [row for row in _unique(output) if _clock(row["start_time"]) > _clock(self.clock())]
        except Exception as exc:
            self.errors["schedule"] = type(exc).__name__
            return []

    def get_completed_games(self, start, end, *, as_of=None):
        history_window(start, end)
        self.errors.pop("history", None)
        store = self._store()
        store.validate_asof(as_of)
        calls, errors, complete, blocked, leagues, pending = 0, [], True, set(), (), 0
        try:
            leagues = _catalogue(self._catalogue(), start, end, self.candidates)
            for league in self._history_order(store, leagues):
                key = f"league:{league.league_id}:season:{league.season}"
                if store.due(PROVIDER, key, ttl=HISTORY_TTL):
                    if calls >= self.max_history_requests:
                        complete = False
                        continue
                    if not store.reserve(PROVIDER, key, ttl=HISTORY_TTL, daily_limit=48):
                        errors.append("history_budget_exhausted")
                        complete = False
                        continue
                    calls += 1
                    withdrawn = []
                    try:
                        rows = self._request("games", {"league": league.league_id, "season": league.season})
                        withdrawn = _native_retractions(rows, league, store.clock())
                        finals = parse_completed_games(rows, (league,), observed_at=store.clock())
                        withdrawn_ids = {row["event_id"] for row in withdrawn}
                        store.record(PROVIDER, key, [row for row in finals if row["event_id"] not in withdrawn_ids] + withdrawn)
                    except Exception as exc:
                        error = type(exc).__name__
                        store.record(PROVIDER, key, withdrawn, error=error)
                        errors.append(error)
                        complete = False
                        blocked.add((league.league_id, league.season))
                elif store.request_error(PROVIDER, key):
                    errors.append(store.request_error(PROVIDER, key))
                    complete = False
                    blocked.add((league.league_id, league.season))
            rows = store.read((PROVIDER,), start, end, as_of=as_of)
            allowed = {(row.league_id, row.season) for row in leagues}
            rows = [row for row in rows if (row.get("league_id"), row.get("season")) in allowed - blocked]
            if as_of is not None:
                current_rows = store.read((PROVIDER,), start, end)
                pending = sum((row.get("league_id"), row.get("season")) in allowed - blocked
                              and _clock(row["result_observed_at"]) >= _clock(as_of) for row in current_rows)
        except Exception as exc:
            errors.append(type(exc).__name__)
            rows, complete = [], False
        if errors:
            self.errors["history"] = ";".join(errors)
        self.last_history_report = {"status": "complete" if complete else "partial",
                                    "windows_complete": complete, "requests": calls,
                                    "returned_results": len(rows), "errors": tuple(errors),
                                    "pending_observations": pending,
                                    "resolved_league_seasons": len(leagues),
                                    "reviewed_candidates": len(self.candidates)}
        return rows

    @property
    def history_coverage(self):
        return dict(self.last_history_report)
