"""One governed native football request per call; live model work is entirely offline."""
from collections import Counter
from dataclasses import asdict
from math import isfinite

import api_budget
from api_football import APIFootball
from league_catalog import LEAGUE_BY_ID
from red_card_impact_predictor import RED_CARD_MODEL_VERSION, RedCardImpactPredictor
from redcard_events import period_clock, regulation_clock, score_pair, scoring_goal
from scanners.ultra_live_scanner_v3 import UltraLiveScanner


class LiveSourceError(RuntimeError):
    """Report a failed refresh without disclosing a provider response or a credential."""


def _positive(n):
    return type(n) is int and n > 0


def _mapping(value):
    return value if isinstance(value, dict) else {}


class LiveFootballSource:
    def __init__(self, api_key, *, ready=None):
        self._api_key = api_key
        self._ready = ready

    def discover(self):
        return self._fixtures({"live": "all"}, "discover")

    def details(self, ids):
        if (not isinstance(ids, (tuple, list)) or not 1 <= len(ids) <= 20
                or not all(_positive(n) for n in ids) or len(set(ids)) != len(ids)):
            raise ValueError("invalid detail group")
        return self._fixtures({"ids": "-".join(map(str, ids))}, "details", set(ids))

    def _fixtures(self, params, label, requested=None):
        try:
            ready = self._ready
            if ready is None:
                from live_football_readiness import jobs_idle as ready
            if not self._api_key or ready() is not True:
                raise LiveSourceError("live request deferred")
            response = api_budget.api_football_get(
                "https://v3.football.api-sports.io/fixtures", headers={"x-apisports-key": self._api_key},
                params=params, priority=api_budget.APIBudgetPriority.BACKGROUND,
                label=f"live-ticker:{label}", allow_redirects=False, timeout=10)
            if response.status_code != 200:
                raise LiveSourceError("live request unavailable")
            data = response.json()
        except LiveSourceError:
            raise
        except Exception:
            raise LiveSourceError("live request unavailable") from None
        data = _mapping(data)
        rows = data.get("response")
        paging = _mapping(data.get("paging"))
        if (data.get("get") != "fixtures" or data.get("parameters") != params
                or data.get("errors") not in ([], {}) or not isinstance(rows, list)
                or type(data.get("results")) is not int or data["results"] != len(rows)
                or type(paging.get("current")) is not int or paging["current"] != 1
                or type(paging.get("total")) is not int or paging["total"] not in ((1,) if rows else (0, 1))):
            raise LiveSourceError("invalid live response envelope")
        grouped = {}
        for row in rows:
            fixture_id = _mapping(_mapping(row).get("fixture")).get("id")
            if not _positive(fixture_id) or requested is not None and fixture_id not in requested:
                raise LiveSourceError("unattributable live response")
            if requested is None and (fixture_id in grouped or not _positive(_mapping(row.get("league")).get("id"))):
                # A complete discovery replaces the previous list. Withhold the
                # refresh, don't turn corrupt identity into a confirmed removal.
                raise LiveSourceError("ambiguous discovery")
            # Duplicate IDs are ambiguous, but do not discard other valid fixtures.
            grouped[fixture_id] = None if fixture_id in grouped else row
        return [row for row in grouped.values() if row is not None
                and _positive(league_id := _mapping(row.get("league")).get("id")) and league_id in LEAGUE_BY_ID]


class _FixtureObservations:
    """Only these two already-received observations are accessible to the scanner."""
    def __init__(self, ids, stats, events):
        self.ids, self.stats, self.events = ids, stats, events

    def get_match_statistics(self, fixture_id, home_id, away_id):
        return self.stats if (fixture_id, home_id, away_id) == self.ids else None

    def get_fixture_events(self, fixture_id):
        return self.events if fixture_id == self.ids[0] else []


def _valid_child(row, fixture_id, names):
    if not isinstance(row, dict):
        return False
    for key in ("fixture", "fixture_id"):
        if key in row:
            identifier = _mapping(row[key]).get("id") if key == "fixture" else row[key]
            if not _positive(identifier) or identifier != fixture_id:
                return False
    team = _mapping(row.get("team"))
    identifier = team.get("id")
    return (_positive(identifier) and identifier in names and
            (team.get("name") is None or team["name"] == names[identifier]))


def _validate_stats(rows, fixture_id, names):
    if not isinstance(rows, list) or len(rows) != 2:
        return None
    seen = set()
    for row in rows:
        if not _valid_child(row, fixture_id, names):
            return None
        team = _mapping(_mapping(row).get("team")).get("id")
        fields = _mapping(row).get("statistics")
        if team in seen or not isinstance(fields, list):
            return None
        seen.add(team)
        stat_names = set()
        for entry in fields:
            name = _mapping(entry).get("type")
            if not isinstance(name, str) or name in stat_names or "value" not in entry:
                return None
            stat_names.add(name)
            if name == "expected_goals":
                raw = entry["value"]
                if (not isinstance(raw, (float, int, str)) or isinstance(raw, bool)
                        or isinstance(raw, str) and "%" in raw):
                    return None
                try:
                    value = float(raw)
                except (OverflowError, ValueError):
                    return None
                if not isfinite(value) or not 0 <= value <= 20:
                    return None
        if not {"expected_goals", "Red Cards"} <= stat_names:
            return None
    return APIFootball.parse_match_statistics(rows, *names)


def _corroborate(match, teams, snapshot_clock, stats):
    events = match.get("events")
    if not isinstance(events, list):
        return False, None
    goals, first, reds = Counter(), Counter(), Counter()
    dismissal = None
    findings, confirmations = [], []
    scored_events = set()
    for event in events:
        if not _valid_child(event, match["fixture"]["id"], teams):
            return False, None
        typ = _mapping(event).get("type")
        detail = _mapping(event).get("detail")
        if not isinstance(typ, str) or not isinstance(detail, str):
            return False, None
        if typ not in {"Goal", "Card", "subst", "Subst", "Var"}:
            return False, None
        desc = (detail + " " + str(event.get("comments") or "")).casefold()
        if any(word in desc for word in ("cancel", "disallow", "overturn", "no goal", "review", "var check")):
            return False, None
        team = _mapping(event.get("team")).get("id")
        try:
            clock = regulation_clock(event, match["fixture"]["status"]["short"])
            if clock is None or clock > snapshot_clock:
                return False, None
            if typ == "Var":
                verdict = {"goal confirmed": "Goal", "red card confirmed": "Red"}.get(detail.strip().casefold())
                if verdict is None:
                    return False, None
                confirmations.append((verdict, team, clock))
            if typ == "Goal":
                if not detail.strip():
                    return False, None
                if scoring_goal(event):
                    player = _mapping(event.get("player")).get("id")
                    if player is not None and not _positive(player):
                        return False, None
                    signature = (team, clock, player)
                    if signature in scored_events:
                        return False, None
                    scored_events.add(signature)
                    goals[team] += 1
                    first[team] += clock[0] == 1
                    findings.append(("Goal", team, clock))
        except ValueError:
            return False, None
        if typ == "Card":
            if detail in ("Red Card", "Second Yellow card"):
                if not _positive(_mapping(event.get("player")).get("id")) or clock[2] > 30:
                    return False, None
                reds[team] += 1
                dismissal = event
                findings.append(("Red", team, clock))
            elif detail != "Yellow Card":
                return False, None
    if any(not any(kind == observed and side == t and when <= checked
                   for observed, t, when in findings) for kind, side, checked in confirmations):
        return False, None
    if tuple(goals[t] for t in teams) != score_pair(match.get("goals")):
        return False, None
    if (sum(reds.values()) > 1 or (stats["red_cards_home"], stats["red_cards_away"])
            != tuple(reds[t] for t in teams)):
        return False, None
    score = match.get("score")
    if score is not None and not isinstance(score, dict):
        return False, None
    halftime = _mapping(score).get("halftime")
    if halftime is not None and halftime != {"home": None, "away": None}:
        if score_pair(halftime) != tuple(first[t] for t in teams):
            return False, None
    for key in ("fulltime", "extratime", "penalty"):
        pair = _mapping(score).get(key)
        if pair is not None and pair != {"home": None, "away": None}:
            return False, None
    return True, dismissal


def _red_result(match, event, stats, priors):
    time, player, team = event["time"], event["player"], event["team"]["id"]
    teams, score = match["teams"], match["goals"]
    side, other = ("home", "away") if team == teams["home"]["id"] else ("away", "home")
    fid, minute = match["fixture"]["id"], match["fixture"]["status"]["elapsed"]
    extra = time.get("extra") or 0
    # Keep the legacy presentation names. The predictor uses only bilateral xG.
    live = {f"{out}_{s}": stats[f"{key}_{s}"] for s in ("home", "away") for out, key in (
        ("xg", "xg"), ("shots_on_goal", "shots_on_target"), ("possession", "possession"),
        ("total_attacks", "attacks"), ("dangerous_attacks", "dangerous_attacks"),
        ("corners", "corners"), ("total_shots", "shots"))}
    prediction = RedCardImpactPredictor().predict(
        minute, score["home"], score["away"], side, live, *priors, red_card_minute=time["elapsed"])
    return {"card": {"card_id": f"{fid}_{team}_{player['id']}_{time['elapsed']}_{extra}",
                     "minute": time["elapsed"], "extra_minute": extra, "detail": event["detail"],
                     "player": player.get("name") or "Unknown", "team": teams[side]["name"], "team_id": team,
                     "source_dismissal_count": 1,
                     "match": {k: match[k] for k in ("fixture", "teams", "league", "goals")}},
            "home": teams["home"]["name"], "away": teams["away"]["name"],
            "score": f"{score['home']}-{score['away']}", "opponent": teams[other]["name"], "red_side": side,
            "fixture_red_card_count": 1, "error": None, "live_stats": live, "prediction_minute": minute,
            "prediction": asdict(prediction), "model_version": RED_CARD_MODEL_VERSION}


def analyze_detail(fixture, analyzer=None):
    """Return model rows only for an independently corroborated, supported grouping."""
    match = _mapping(fixture)
    native, league, teams = (_mapping(match.get(k)) for k in ("fixture", "league", "teams"))
    status = _mapping(native.get("status"))
    sides = [_mapping(teams.get(s)) for s in ("home", "away")]
    ids = tuple(side.get("id") for side in sides)
    if (not _positive(native.get("id")) or not _positive(league.get("id")) or league["id"] not in LEAGUE_BY_ID
            or not all(_positive(t) for t in ids) or ids[0] == ids[1]
            or not all(isinstance(s.get("name"), str) and s["name"].strip() for s in sides)):
        return None, None
    extra = status.get("extra")
    clock = period_clock(status.get("short"), status.get("elapsed"), 0 if extra is None else extra)
    if clock is None or status.get("short") == "2H" and status["elapsed"] >= 90:
        return None, None
    names = {side["id"]: side["name"] for side in sides}
    stats = _validate_stats(match.get("statistics"), native["id"], names)
    if stats is None:
        return None, None
    consistent, card = _corroborate(match, names, clock, stats)
    if not consistent:
        return None, None
    priors = (None, None)
    if analyzer is not None:
        from advanced_analyzer import AdvancedBTTSAnalyzer
        if isinstance(analyzer, AdvancedBTTSAnalyzer):
            priors = AdvancedBTTSAnalyzer.cached_live_goal_priors(
                analyzer, *ids, league["id"], league.get("season"), native.get("date"))
    local = _FixtureObservations((native["id"], *ids), stats, match["events"])
    ordinary = UltraLiveScanner(None, local).analyze_live_match_ultra(match, prematch_priors=priors)
    if ordinary:
        ordinary["scheduled_start"] = native.get("date")
    return ordinary, _red_result(match, card, stats, priors) if card else None
