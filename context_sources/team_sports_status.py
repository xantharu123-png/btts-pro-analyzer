"""Owning price-free native schedule/status receipts, never player evidence.

These projections deliberately are NOT C2/C3 appearance/rotation/TOI records.
They retain the existing feed's native lifecycle and raw identity spellings.
Neither a current schedule nor a result proves a season's regulation rules,
an actual end instant, an injury, a confirmed starter or complete history.
"""
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
import math
import os
import re
from urllib.parse import parse_qsl, urlsplit

from context_models.contracts import (
    ContextContractError, ContextIntegrityError, OBSERVATION_FIELDS,
    canonical_timestamp, digest, normalize_observation, require_object,
)
from model_artifacts import canonical_bytes


STATUS_SCHEMA = "native-team-sport-status-v1"
_SOURCES = {"ESPN": ("espn", "basketball", "nba"),
            "EuroLeague": ("euroleague", "basketball", "euroleague"),
            "NHL": ("nhl", "ice_hockey", "nhl")}
_REQUEST_FIELDS = {"provider", "source", "sport", "competition", "phase", "endpoint", "params",
                   "request_key", "request_season", "request_window", "search_window"}
_PAYLOAD_FIELDS = {"request", "native", "projection"}
_SCALAR = object()
_SEASON = {"year": _SCALAR, "type": _SCALAR, "startDate": _SCALAR, "endDate": _SCALAR}
_ESPN_TEAM = {key: _SCALAR for key in ("id", "abbreviation", "displayName")}
_ESPN_TYPE = {key: _SCALAR for key in ("id", "name", "state", "completed", "description", "detail", "shortDetail")}
_ESPN_COMP = {"id": _SCALAR, "date": _SCALAR, "neutralSite": _SCALAR,
    "status": {"type": _ESPN_TYPE, "period": _SCALAR, "displayClock": _SCALAR},
    "competitors": [{"id": _SCALAR, "homeAway": _SCALAR, "type": _SCALAR,
                     "team": _ESPN_TEAM, "score": _SCALAR, "winner": _SCALAR}],
    "season": _SEASON}
_EURO_TEAM = {"club": {"code": _SCALAR, "abbreviatedName": _SCALAR, "name": _SCALAR}, "score": _SCALAR}
_EURO = {key: _SCALAR for key in ("id", "identifier", "gameCode", "played", "utcDate", "isNeutralVenue",
    "seasonCode", "status", "gameStatus", "cancelled", "canceled", "postponed")}
_EURO.update(local=_EURO_TEAM, road=_EURO_TEAM, winner={"code": _SCALAR})
_NHL_TEAM = {key: _SCALAR for key in ("id", "abbrev", "score")}
_NHL = {key: _SCALAR for key in ("id", "season", "gameType", "startTimeUTC", "gameState", "gameScheduleState", "neutralSite")}
_NHL.update(homeTeam=_NHL_TEAM, awayTeam=_NHL_TEAM,
    gameOutcome={"lastPeriodType": _SCALAR}, periodDescriptor={"number": _SCALAR, "periodType": _SCALAR},
    winningGoalie={"playerId": _SCALAR})


def _need(value, message):
    if not value:
        raise ContextContractError(message)


def _day(value):
    _need(type(value) is str, "native request day must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContextContractError("native request day is invalid") from exc
    _need(parsed.isoformat() == value, "native request day is noncanonical")
    return value


def _request(provider, url, params, *, phase, window, request_key):
    _need(type(provider) is str and provider in _SOURCES, "unsupported team-sport provider")
    _need(type(phase) is str and phase in {"schedule", "history"}, "unsupported response phase")
    _need(type(url) is str, "native endpoint must be explicit")
    query = {} if params is None else params
    _need(type(query) is dict, "native query must be explicit")
    source, sport, competition = _SOURCES[provider]
    season, requested = None, None
    if provider == "ESPN":
        _need(url == "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", "unreviewed ESPN endpoint")
        _need(set(query) == {"dates", "limit"} and type(query["limit"]) is int
              and query["limit"] == (100 if phase == "schedule" else 1000), "unreviewed ESPN request")
        dates = query["dates"]
        _need(type(dates) is str and re.fullmatch(r"[0-9]{8}(?:-[0-9]{8})?", dates), "invalid ESPN request window")
        pieces = dates.split("-")
        _need(len(pieces) == (1 if phase == "schedule" else 2), "ESPN phase/window mismatch")
        parsed = [_day(value[:4] + "-" + value[4:6] + "-" + value[6:]) for value in pieces]
        requested = {"start": parsed[0], "end": parsed[-1]}
        _need(parsed[0] <= parsed[-1], "reversed ESPN request window")
        if phase == "history":
            _need(request_key == "nba:" + parsed[0], "ESPN native request key differs")
    elif provider == "EuroLeague":
        matched = re.fullmatch(r"https://api-live\.euroleague\.net/v2/competitions/E/seasons/(E[0-9]{4})/games", url)
        _need(matched is not None and set(query) == {"limit"} and type(query["limit"]) is int
              and query["limit"] == 500, "unreviewed EuroLeague request")
        season = matched[1]
        if phase == "history":
            _need(request_key == season, "EuroLeague request season/key differs")
    else:
        matched = re.fullmatch(r"https://api-web\.nhle\.com/v1/schedule/([0-9]{4}-[0-9]{2}-[0-9]{2})", url)
        _need(matched is not None and not query, "unreviewed NHL request")
        cursor = _day(matched[1])
        # The actual requested cursor is known. Do not invent an end date or
        # season from its digits or from a nominal seven-day parser window.
        requested = {"start": cursor, "end": None}
        if phase == "history":
            _need(request_key == cursor, "NHL request cursor/key differs")
    search = None
    if phase == "schedule":
        _need(request_key is None and type(window) is tuple and len(window) == 2
              and all(type(value) is date for value in window), "schedule needs its actual search window")
        _need(0 <= (window[1] - window[0]).days <= 14, "unsupported schedule search window")
        search = {"start": window[0].isoformat(), "end": window[1].isoformat()}
    else:
        _need(window is None and type(request_key) is str, "history must retain its actual request key")
    return dict(provider=provider, source=source, sport=sport, competition=competition, phase=phase,
        endpoint=url, params=deepcopy(query), request_key=request_key, request_season=season,
        request_window=requested, search_window=search)


def response_request(provider, url, params, *, phase, window, request_key, response):
    """Only called by the four concrete existing response seams; never fetch."""
    result = _request(provider, url, params, phase=phase, window=window, request_key=request_key)
    _need(type(getattr(response, "status_code", None)) is int and response.status_code == 200,
          "incomplete native HTTP response")
    history = getattr(response, "history", None)
    _need(type(history) is list and not history, "redirected or unbound native response")
    actual = getattr(response, "url", None)
    _need(type(actual) is str, "native response URL is missing")
    try:
        parts, expected = urlsplit(actual), urlsplit(url)
    except ValueError as exc:
        raise ContextContractError("invalid native response URL") from exc
    _need((parts.scheme, parts.netloc, parts.path) == (expected.scheme, expected.netloc, expected.path)
          and not parts.fragment, "native response endpoint differs")
    try:
        pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise ContextContractError("invalid native response query") from exc
    _need(len(pairs) == len(result["params"]) and dict(pairs) == {key: str(value) for key, value in result["params"].items()},
          "native response query differs")
    return result


def validate_team_sport_request(value):
    require_object(value, _REQUEST_FIELDS, label="native team-sport request")
    window = value["search_window"]
    if window is not None:
        require_object(window, {"start", "end"}, label="native search window")
        window = tuple(date.fromisoformat(_day(window[name])) for name in ("start", "end"))
    expected = _request(value["provider"], value["endpoint"], value["params"], phase=value["phase"],
                        window=window, request_key=value["request_key"])
    _need(canonical_bytes(expected) == canonical_bytes(value), "native request scope binding differs")
    return expected


def _invalid(value):
    return {"invalid_shape": {type(None): "null", dict: "object", list: "array", bool: "boolean",
        str: "string", int: "integer", float: "number"}.get(type(value), "non-json")}


def _project(value, schema):
    """Explicit source fields only. Unknown field VALUES are retained, not guessed.

    Wrong-shaped fields have an explicit closed marker rather than being
    dropped like a successfully filtered event. Extra price/metadata keys do
    not become part of a context/model identity.
    """
    if type(value) is dict and set(value) == {"invalid_shape"} and type(value["invalid_shape"]) is str and value["invalid_shape"] in {
        "null", "object", "array", "boolean", "string", "integer", "number", "non-json"}:
        return dict(value)
    if schema is _SCALAR:
        if type(value) is str:
            try:
                value.encode("utf-8")
            except UnicodeError:
                return _invalid(value)
            return value
        if value is None or type(value) is bool:
            return value
        if type(value) in (int, float):
            try:
                if math.isfinite(value):
                    return value
            except OverflowError:
                pass
        return _invalid(value)
    if type(schema) is list:
        return [_project(item, schema[0]) for item in value] if type(value) is list else _invalid(value)
    return {key: _project(value[key], definition) for key, definition in schema.items() if key in value} if type(value) is dict else _invalid(value)


def _id(value, source):
    if type(value) not in (str, int):
        return None
    word = str(value)
    pattern = r"[A-Za-z0-9][A-Za-z0-9_-]*" if source == "euroleague" else r"[1-9][0-9]*"
    return word if re.fullmatch(pattern, word) else None


def _clock(value):
    try:
        return canonical_timestamp(value) if type(value) is str else None
    except ContextContractError:
        return None


def _dict(value):
    return value if type(value) is dict else {}


def _bool(value):
    return value if type(value) is bool else None


def _score(value):
    try:
        parsed = int(value) if type(value) is str and re.fullmatch(r"0|[1-9][0-9]*", value) else value
        if type(parsed) is int and parsed >= 0 and math.isfinite(parsed):
            return parsed
    except (ValueError, OverflowError):
        pass
    return None


def _projection(request, native):
    source, sport = request["source"], request["sport"]
    issues, aliases = set(), []
    if source == "espn":
        outer, game = _dict(native.get("event")), _dict(native.get("competition"))
        primary = _id(game.get("id"), source)
        outer_id = _id(outer.get("id"), source)
        if primary is None:
            # A real outer ID still preserves a correction, but is explicitly
            # event-only, never a guessed competition-id equivalence.
            primary = outer_id
            issues.add("competition-id-unavailable")
        for field, value in (("competition.id", game.get("id")), ("event.id", outer.get("id"))):
            if _id(value, source) is not None:
                aliases.append({"field": field, "value": value, "scope": "source"})
        status = _dict(_dict(game.get("status")).get("type"))
        state, name, completed = status.get("state"), status.get("name"), _bool(status.get("completed"))
        if type(name) is str and name in {"STATUS_CANCELED", "STATUS_CANCELLED"}:
            lifecycle = "cancelled"
        elif (state, name, completed) == ("post", "STATUS_FINAL", True):
            lifecycle = "completed"
        elif state == "pre" and completed is False and name == "STATUS_SCHEDULED":
            lifecycle = "scheduled"
        elif state == "in" and completed is False:
            lifecycle = "started"
        else:
            lifecycle = "unknown"
        participants = game.get("competitors")
        people = participants if type(participants) is list else []
        sides = {side: [p for p in people if type(p) is dict and p.get("homeAway") == side] for side in ("home", "away")}
        if len(people) != 2 or any(len(values) != 1 for values in sides.values()):
            issues.add("invalid-participants")
        home = sides["home"][0] if len(sides["home"]) == 1 else {}
        away = sides["away"][0] if len(sides["away"]) == 1 else {}
        ht, at = _dict(home.get("team")), _dict(away.get("team"))
        scheduled = _clock(game.get("date"))
        if scheduled is None:
            scheduled = _clock(outer.get("date"))
            issues.add("competition-schedule-unavailable")
        season = {key: deepcopy(value) for key, value in (("response", native.get("season")),
            ("event", outer.get("season")), ("competition", game.get("season"))) if value is not None}
        neutral, game_type = _bool(game.get("neutralSite")), None
        hi, ai = ht.get("id"), at.get("id")
    elif source == "euroleague":
        game = native
        primary = _id(game.get("id"), source) or _id(game.get("identifier"), source)
        for field in ("id", "identifier", "gameCode"):
            value = game.get(field)
            if _id(value, source) is not None:
                aliases.append({"field": field, "value": value,
                    "scope": "request-season" if field == "gameCode" else "source"})
        if primary is None and type(game.get("gameCode")) is int and game["gameCode"] > 0 and request["request_season"]:
            primary = f"season:{request['request_season']}:game:{game['gameCode']}"
            issues.add("season-composite-id-only")
        cancelled = game.get("cancelled") is True or game.get("canceled") is True
        lifecycle = "cancelled" if cancelled else "completed" if game.get("played") is True else "not_completed" if game.get("played") is False else "unknown"
        if game.get("postponed") is True or any(game.get(key) is not None for key in ("status", "gameStatus")):
            if not cancelled:
                lifecycle = "unknown"  # Preserve unknown native codes without guessing semantics.
        home, away = _dict(game.get("local")), _dict(game.get("road"))
        ht, at = _dict(home.get("club")), _dict(away.get("club"))
        hi, ai = ht.get("code"), at.get("code")
        scheduled, neutral, game_type = _clock(game.get("utcDate")), _bool(game.get("isNeutralVenue")), None
        season = {"request": request["request_season"]}
        if "seasonCode" in game:
            season["event"] = deepcopy(game["seasonCode"])
            if game["seasonCode"] != request["request_season"]:
                issues.add("native-season-conflict")
    else:
        game = native
        primary = _id(game.get("id"), source)
        if primary is not None:
            aliases.append({"field": "id", "value": game["id"], "scope": "source"})
        state = game.get("gameState")
        lifecycle = {"FUT": "scheduled", "PRE": "scheduled", "LIVE": "started", "CRIT": "started",
                     "FINAL": "completed", "OFF": "completed", "CANC": "cancelled"}.get(state, "unknown") if type(state) is str else "unknown"
        if game.get("gameScheduleState") not in (None, "OK"):
            lifecycle = "unknown"  # Unknown correction withdraws the old claim too.
        home, away = _dict(game.get("homeTeam")), _dict(game.get("awayTeam"))
        hi, ai = home.get("id"), away.get("id")
        scheduled, neutral = _clock(game.get("startTimeUTC")), _bool(game.get("neutralSite"))
        season, game_type = {"event": deepcopy(game.get("season"))}, deepcopy(game.get("gameType"))
    _need(primary is not None, "native-event-id-unavailable")
    event_key = f"{source}:{sport}:{primary}"
    home_id, away_id = _id(hi, source), _id(ai, source)
    if home_id is None or away_id is None or home_id == away_id:
        issues.add("invalid-participants")
    if scheduled is None:
        issues.add("invalid-schedule")
    if lifecycle == "unknown":
        issues.add("unknown-native-status")
    scores = {"home": _score(home.get("score")), "away": _score(away.get("score"))}
    if lifecycle == "completed" and (None in scores.values() or scores["home"] == scores["away"]):
        issues.add("invalid-terminal-score")
    if lifecycle == "completed" and None not in scores.values() and scores["home"] != scores["away"]:
        home_won = scores["home"] > scores["away"]
        if source == "espn":
            if any(type(person.get("winner")) is bool and person["winner"] != won
                   for person, won in ((home, home_won), (away, not home_won))):
                issues.add("native-winner-conflict")
        elif source == "euroleague":
            winner = _dict(game.get("winner")).get("code")
            if winner is not None and winner != (hi if home_won else ai):
                issues.add("native-winner-conflict")
    # Score/period evidence is not an actual end, minutes or player-exposure fact.
    return {"event_key": event_key, "aliases": aliases,
        "home_id": f"{source}:{sport}:team:{home_id}" if home_id is not None else None,
        "away_id": f"{source}:{sport}:team:{away_id}" if away_id is not None else None,
        "scheduled_start": scheduled, "status": lifecycle, "neutral_site": neutral,
        "season": season, "game_type": game_type, "scores": scores, "issues": sorted(issues)}


def _record(request, native, observed_at):
    projection = _projection(request, native)
    clock = canonical_timestamp(observed_at)
    start = projection["scheduled_start"]
    # A reported finish at/before the scheduled start cannot be used as a
    # causal result. The response itself still remains a receipt/correction.
    if start is not None and (projection["status"] == "completed" and start >= clock
                             or projection["status"] == "started" and start > clock):
        projection["issues"] = sorted(set(projection["issues"]) | {"native-status-time-conflict"})
    payload = {"request": request, "native": native, "projection": projection}
    event_key = projection["event_key"]
    return normalize_observation({"event_key": event_key, "sport": request["sport"],
        "competition": request["competition"], "format": "native_event_unqualified", "subject_id": event_key,
        "kind": "event_status", "source": request["source"], "source_schema": STATUS_SCHEMA,
        "source_revision": digest(payload),
        "schedule_revision": digest({"event_key": event_key, "scheduled_start": projection["scheduled_start"]}),
        "published_at": None, "publication_proof": None, "valid_from": clock, "valid_until": None,
        "complete": False, "payload": payload}, observed_at=observed_at)


def normalize_team_sport_response(request, payload, *, observed_at):
    request = validate_team_sport_request(request)
    _need(isinstance(observed_at, datetime), "status requires an actual receipt datetime")
    canonical_timestamp(observed_at)
    _need(type(payload) is dict, "native response envelope is unavailable")
    rows, issues = [], set()
    source = request["source"]
    if source == "espn":
        events = payload.get("events")
        _need(type(events) is list, "native ESPN events are unavailable")
        for event in events:
            if type(event) is not dict:
                issues.add("native-event-id-unavailable")
                continue
            competitions = event.get("competitions")
            if type(competitions) is not list or not competitions:
                # Retain a known event's withdrawal instead of silently losing it.
                competitions = [None]
            for comp in competitions:
                native = {"event": _project(event, {"id": _SCALAR, "date": _SCALAR, "season": _SEASON}),
                          "competition": _project(comp, _ESPN_COMP)}
                if "season" in payload:
                    native["season"] = _project(payload["season"], _SEASON)
                rows.append(native)
    elif source == "euroleague":
        _need(type(payload.get("data")) is list, "native EuroLeague rows are unavailable")
        rows = [_project(raw, _EURO) for raw in payload["data"]]
    else:
        _need(type(payload.get("gameWeek")) is list, "native NHL weeks are unavailable")
        for day in payload["gameWeek"]:
            if type(day) is not dict or type(day.get("games")) is not list:
                issues.add("native-collection-unavailable")
                continue
            rows.extend(_project(raw, _NHL) for raw in day["games"])
    result = []
    for native in rows:
        try:
            row = _record(request, native, observed_at)
        except (ContextContractError, TypeError, KeyError, ValueError, OverflowError):
            issues.add("native-event-id-unavailable")
            continue
        result.append(row)
        issues.update(row["payload"]["projection"]["issues"])
    return tuple(result), tuple(sorted(issues))


def validate_team_sport_status_record(row):
    """Rebuild all derived native identities; hashes alone are not source truth."""
    payload = require_object(row["payload"], _PAYLOAD_FIELDS, label="native team-sport status")
    request = validate_team_sport_request(payload["request"])
    native = payload["native"]
    schema = {"event": {"id": _SCALAR, "date": _SCALAR, "season": _SEASON},
              "competition": _ESPN_COMP, "season": _SEASON} if request["source"] == "espn" else _EURO if request["source"] == "euroleague" else _NHL
    _need(type(native) is dict and canonical_bytes(_project(native, schema)) == canonical_bytes(native), "native status fields differ")
    clock = canonical_timestamp(row["observed_at"])
    expected = _record(request, native, datetime.fromisoformat(clock))
    if canonical_bytes(expected) != canonical_bytes({key: row[key] for key in OBSERVATION_FIELDS}):
        raise ContextIntegrityError("native team-sport status envelope differs")
    return deepcopy(expected["payload"])


def _selected(row):
    try:
        return _checked_selected(row)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise ContextIntegrityError("invalid selected native team-sport receipt") from exc


def _checked_selected(row):
    fields = set(OBSERVATION_FIELDS) | {"digest", "content_digest", "observed_at", "evidence_class", "effective_at", "publication_resolution"}
    require_object(row, fields, label="selected native team-sport receipt")
    clock = canonical_timestamp(row["observed_at"])
    content = {key: row[key] for key in OBSERVATION_FIELDS}
    if (row["observed_at"] != clock or row["evidence_class"] != "prospective"
        or row["effective_at"] != clock or row["publication_resolution"] is not None
        or digest(content) != row["content_digest"]
        or digest({"content_digest": row["content_digest"], "observed_at": clock}) != row["digest"]):
        raise ContextIntegrityError("selected native team-sport receipt binding differs")
    validate_team_sport_status_record(row)
    return row


def team_sport_observations_as_of(path, *, cutoff):
    """Whole causal native lineage, no warm-cache import or latest pruning."""
    from context_models.dataset import _reader
    from context_observations import _SELECT, _decode_receipt
    decision = canonical_timestamp(cutoff)
    path = Path(path)
    if not os.path.lexists(path):
        return ()
    with _reader(path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('context_contents','context_observations')")}
        if not tables:
            return ()
        if tables != {"context_contents", "context_observations"}:
            raise ContextIntegrityError("incomplete native observation tables")
        decoded = [_decode_receipt(stored) for stored in connection.execute(_SELECT)]
    result = []
    for row in decoded:
        if row["source_schema"] != STATUS_SCHEMA:
            continue
        selected = {**row, "evidence_class": "prospective", "effective_at": row["observed_at"], "publication_resolution": None}
        _selected(selected)
        if row["observed_at"] <= decision:
            result.append(selected)
    return tuple(sorted(result, key=lambda row: (row["observed_at"], row["digest"])))


def select_team_sport_status(rows, *, cutoff, event_key):
    """Pure exact-ID status selection; NOT a legacy alias/source resolver."""
    decision = canonical_timestamp(cutoff)
    # Validate before filtering; a corrupt claimed known receipt is not missing.
    checked = [_selected(row) for row in rows]
    relevant = [row for row in checked if row["event_key"] == event_key and row["observed_at"] <= decision]
    if not relevant:
        return {"state": "missing", "rows": (), "receipt_refs": []}
    newest = max(row["observed_at"] for row in relevant)
    current = tuple(sorted((row for row in relevant if row["observed_at"] == newest), key=lambda row: row["digest"]))
    revisions = {digest({"native": row["payload"]["native"], "projection": row["payload"]["projection"]}) for row in current}
    state = "conflicting" if len(revisions) > 1 else "unknown" if current[0]["payload"]["projection"]["issues"] else "available"
    return {"state": state, "rows": deepcopy(current), "receipt_refs": sorted({row["digest"] for row in current})}
