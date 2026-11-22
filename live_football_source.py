"""One governed native football request per call; live model work is entirely offline."""
from collections import Counter
from dataclasses import asdict
from math import isfinite

import api_budget
import redcard_events
from api_football import APIFootball
from league_catalog import LEAGUE_BY_ID
from live_football_feed import LiveRefreshIssue, LiveSourceError
from red_card_impact_predictor import RED_CARD_MODEL_VERSION, RedCardImpactPredictor
from redcard_events import period_clock, regulation_clock, score_pair, scoring_goal
from scanners.ultra_live_scanner_v3 import UltraLiveScanner


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
            if not self._api_key:
                raise LiveSourceError(LiveRefreshIssue.TEMPORARY_ERROR)
            if ready() is not True:
                raise LiveSourceError(LiveRefreshIssue.JOBS_DEFERRED)
            response = api_budget.api_football_get(
                "https://v3.football.api-sports.io/fixtures", headers={"x-apisports-key": self._api_key},
                params=params, priority=api_budget.APIBudgetPriority.BACKGROUND,
                label=f"live-ticker:{label}", allow_redirects=False, timeout=10)
            if response.status_code != 200:
                raise LiveSourceError(LiveRefreshIssue.PROVIDER_ERROR)
        except api_budget.APIBudgetExceeded as error:
            issue = {
                "protected_reserve": LiveRefreshIssue.PROTECTED_RESERVE,
                "ticker_limit": LiveRefreshIssue.TICKER_LIMIT,
            }.get(getattr(error, "reason", None), LiveRefreshIssue.BUDGET_BLOCKED)
            raise LiveSourceError(issue) from None
        except api_budget.APIBudgetError:
            raise LiveSourceError(LiveRefreshIssue.BUDGET_UNAVAILABLE) from None
        except LiveSourceError:
            raise
        except Exception:
            raise LiveSourceError(LiveRefreshIssue.TEMPORARY_ERROR) from None
        try:
            data = _mapping(response.json())
        except Exception:
            raise LiveSourceError(LiveRefreshIssue.PROVIDER_ERROR) from None
        rows = data.get("response")
        paging = _mapping(data.get("paging"))
        if (data.get("get") != "fixtures" or data.get("parameters") != params
                or data.get("errors") not in ([], {}) or not isinstance(rows, list)
                or type(data.get("results")) is not int or data["results"] != len(rows)
                or type(paging.get("current")) is not int or paging["current"] != 1
                or type(paging.get("total")) is not int or paging["total"] not in ((1,) if rows else (0, 1))):
            raise LiveSourceError(LiveRefreshIssue.PROVIDER_ERROR)
        grouped = {}
        for row in rows:
            fixture_id = _mapping(_mapping(row).get("fixture")).get("id")
            if not _positive(fixture_id) or requested is not None and fixture_id not in requested:
                if requested is not None:
                    # The envelope is bound to this exact group. An extra
                    # or unidentified row says nothing about its siblings.
                    continue
                raise LiveSourceError(LiveRefreshIssue.PROVIDER_ERROR)
            if requested is None and (fixture_id in grouped or not _positive(_mapping(row.get("league")).get("id"))):
                # A complete discovery replaces the previous list. Withhold the
                # refresh, don't turn corrupt identity into a confirmed removal.
                raise LiveSourceError(LiveRefreshIssue.PROVIDER_ERROR)
            # Duplicate IDs are ambiguous, but do not discard other valid fixtures.
            grouped[fixture_id] = None if fixture_id in grouped else row
        if requested is not None and rows and not grouped:
            raise LiveSourceError(LiveRefreshIssue.PROVIDER_ERROR)
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


def _card_counts(rows, fixture_id, names):
    """Only the native Red Cards field is relevant; explicit null means zero."""
    counts = {}
    if rows is None:
        return counts
    if not isinstance(rows, list):
        return None
    for row in rows:
        fields = _mapping(row).get("statistics")
        if not _valid_child(row, fixture_id, names) or not isinstance(fields, list):
            return None
        team = row["team"]["id"]
        for field in fields:
            if _mapping(field).get("type") == "Red Cards":
                value = field.get("value")
                if team in counts or "value" not in field or not (value is None or type(value) is int and value >= 0):
                    return None
                counts[team] = 0 if value is None else value
    return counts


def _card_clock(phase, timing, event=None):
    """Extend the regulation clock for display only; ET stoppage precedes the next period."""
    minute, extra = timing.get("elapsed"), timing.get("extra")
    extra = 0 if extra is None else extra
    if phase not in ("ET", "BT", "P"):
        return (period_clock(phase, minute, extra) if event is None else regulation_clock(event, phase))
    if type(minute) is not int or type(extra) is not int or not 0 <= extra <= 30:
        return None
    if event is None and phase in ("BT", "P"):
        # Some competitions go directly from 90 minutes to the shootout.
        periods = {90: 2, 105: 3} if phase == "BT" else {90: 2, 120: 4}
        return (periods[minute], minute, 30) if minute in periods else None
    period = timing.get("period")
    if event is not None:
        other = event.get("period")
        if period is not None and other is not None and period != other:
            return None
        period = other if period is None else period
        if period in ("1H", "2H") or period is None and minute <= 90:
            return regulation_clock(event, phase)
    if not 90 <= minute <= 120:
        return None
    if period == "ET1" or period in ("ET", None) and minute <= 105:
        return (3, minute, extra) if minute <= 105 and (not extra or minute == 105) else None
    if period in ("ET", "ET2", None):
        return (4, minute, extra) if minute >= 105 and (not extra or minute == 120) else None
    return None


def confirmed_live_dismissals(fixture):
    """Return (side, minute, extra, explicitly off-field) facts, never an on-field count or a pick."""
    match = _mapping(fixture)
    native, teams = _mapping(match.get("fixture")), _mapping(match.get("teams"))
    fixture_id, status = native.get("id"), _mapping(native.get("status"))
    sides = {}
    names = {}
    for side in ("home", "away"):
        team = _mapping(teams.get(side))
        team_id, name = team.get("id"), team.get("name")
        if not _positive(team_id) or team_id in sides or not isinstance(name, str) or not name.strip():
            return ()
        sides[team_id], names[team_id] = side, name
    phase = status.get("short")
    snapshot = _card_clock(phase, status)
    events = match.get("events")
    if not _positive(fixture_id) or snapshot is None or not isinstance(events, list):
        return ()
    counts = _card_counts(match.get("statistics"), fixture_id, names)
    if counts is None:
        return ()

    cards, reviews, confirmations = {}, [], {}
    for event in events:
        kind, detail = _mapping(event).get("type"), _mapping(event).get("detail")
        if not isinstance(kind, str) or kind.strip().casefold() not in ("card", "var") or not isinstance(detail, str):
            continue
        var = kind.strip().casefold() == "var"
        label = detail.strip().casefold()
        text = (label + " " + str(event.get("comments") or "")).casefold()
        reversed_card = any(word in text for word in (
            "cancel", "overturn", "disallow", "rescind", "withdraw", "no card", "no red card", "not a red card"))
        reversed_or_open = reversed_card or redcard_events.denied_or_pending_dismissal(event) or "review" in text
        review = (var and "card" in text
                  or reversed_or_open and ("red card" in text or "second yellow" in text))
        if not review and (var or label not in ("red card", "second yellow card")):
            continue
        if not _valid_child(event, fixture_id, names):
            if review:
                return ()  # An unbound card review cannot safely be attributed.
            continue
        team, player = event["team"]["id"], _mapping(event.get("player")).get("id")
        try:
            clock = _card_clock(phase, _mapping(event.get("time")), event)
        except ValueError:
            clock = None
        if clock is None or clock[2] > 30:
            if review:
                return ()
            continue
        if clock > snapshot:
            continue
        if review:
            recipient = player if _positive(player) else None
            # An upgrade isn't a dismissal by itself. It is compatible with a separate
            # red event when the native side count can corroborate the resulting list.
            if var and label == "red card confirmed" and not reversed_or_open and recipient is not None:
                key = team, recipient
                confirmations[key] = max(clock, confirmations.get(key, clock))
            elif reversed_or_open or label not in ("red card confirmed", "card upgrade") or (
                    label == "card upgrade" and team not in counts):
                reviews.append((team, recipient, clock, reversed_card))
        if not var and label in ("red card", "second yellow card") and _positive(player):
            off_field = redcard_events.explicit_off_field_dismissal(event)
            if player not in cards:
                cards[player] = (clock, team, off_field)
            elif (prior := cards[player]) is not None:
                # Second yellow + red can describe one event. No guess between
                # conflicting timestamps or teams; retain explicit bench evidence.
                cards[player] = (clock, team, prior[2] or off_field) if prior[:2] == (clock, team) else None

    # VAR need not carry a player id: withhold ambiguous earlier cards on that side.
    # Only a strictly later confirmation of the same recipient resolves an open review.
    unresolved = [(t, p, when) for t, p, when, cancelled in reviews
                  if cancelled or confirmations.get((t, p), when) <= when]
    confirmed = sorted(card for player, card in cards.items() if card is not None and
                       not any(t == card[1] and p in (None, player) and card[0] <= when for t, p, when in unresolved))
    totals = Counter(team for _, team, _ in confirmed)
    return tuple((sides[t], minute, extra, off) for (_, minute, extra), t, off in confirmed
                 if t not in counts or counts[t] == totals[t])


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
    from redcard_events import denied_or_pending_dismissal, explicit_off_field_dismissal

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
                if explicit_off_field_dismissal(event) or denied_or_pending_dismissal(event):
                    return False, None  # A team card statistic does not prove missing manpower.
                if not _positive(_mapping(event.get("player")).get("id")) or clock[2] > 30:
                    return False, None
                reds[team] += 1
                dismissal = event, clock
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


def _red_result(match, event, card_clock, stats, priors):
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
        minute, score["home"], score["away"], side, live, *priors, red_card_minute=card_clock[1])
    version = (RED_CARD_MODEL_VERSION + ":grouped-first-half-added-v1"
               if card_clock[0] == 1 and card_clock[2] else RED_CARD_MODEL_VERSION)
    return {"card": {"card_id": f"{fid}_{team}_{player['id']}_{time['elapsed']}_{extra}",
                     "minute": time["elapsed"], "extra_minute": extra, "detail": event["detail"],
                     "player": player.get("name") or "Unknown", "team": teams[side]["name"], "team_id": team,
                     "source_dismissal_count": 1,
                     "match": {k: match[k] for k in ("fixture", "teams", "league", "goals")}},
            "home": teams["home"]["name"], "away": teams["away"]["name"],
            "score": f"{score['home']}-{score['away']}", "opponent": teams[other]["name"], "red_side": side,
            "fixture_red_card_count": 1, "error": None, "live_stats": live, "prediction_minute": minute,
            "prediction": asdict(prediction), "model_version": version}


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
    consistent, dismissal = _corroborate(match, names, clock, stats)
    if not consistent:
        return None, None
    priors = (None, None)
    if analyzer is not None:
        from advanced_analyzer import AdvancedBTTSAnalyzer
        if isinstance(analyzer, AdvancedBTTSAnalyzer):
            priors = AdvancedBTTSAnalyzer.cached_live_goal_priors(
                analyzer, *ids, league["id"], league.get("season"), native.get("date"))
    local = _FixtureObservations((native["id"], *ids), stats, match["events"])
    card, card_clock = dismissal if dismissal else (None, None)
    # The scalar models run on regulation minutes. 1H 48 and 45+3 both have
    # base minute 45; an unqualified 48 remains 2H. Keep the raw receipt clock.
    ordinary = UltraLiveScanner(None, local).analyze_live_match_ultra(
        match, prematch_priors=priors, corroborated_red_card_minute=card_clock[1] if card_clock else None)
    if ordinary:
        ordinary["scheduled_start"] = native.get("date")
    return ordinary, _red_result(match, card, card_clock, stats, priors) if card else None
