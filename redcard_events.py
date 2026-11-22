"""Pure checks for native football events and completed regulation timelines."""

import re

FINISHED_STATUSES = {"FT", "AET", "PEN"}
HISTORY_POLICY = "regulation-goals-score-verified-v2"


_OFF_FIELD_RECIPIENT = re.compile(
    r"(?:(?:red card|second yellow card|card)(?: (?:shown to|for|to) (?:the |a )?|\s*[:(–-]\s*))?"
    r"(?:bench(?: player)?|(?:player )?on (?:the )?bench|(?:unused )?substitute|"
    r"(?:player )?(?:already )?substituted(?: off| player)?|(?:head |assistant )?coach|manager|"
    r"(?:(?:technical|coaching|team) )?staff(?: member)?|team official)\s*(?:$|[,;():.!–-])"
)
_CARD_NOT_FINAL = re.compile(
    r"\b(?:no (?:red )?card|not a red card|(?:cancelled|canceled|rescinded|overturned|"
    r"disallowed|withdrawn)|under review|var check)\b"
)


def explicit_off_field_dismissal(event):
    """Native recipient label, not an inference from the player's name or a roster."""
    # An offence involving a bench player is not itself a card *for* that player.
    comment = str(event.get("comments") or "").casefold().strip()
    return bool(_OFF_FIELD_RECIPIENT.match(comment))


def denied_or_pending_dismissal(event):
    """A negated/reviewed card is no evidence for the numerical advantage model."""
    return bool(_CARD_NOT_FINAL.search(_event_description(event)))


def response_rows(response, api):
    """Distinguish a successful empty response from a provider/HTTP failure."""
    if (not isinstance(response, dict) or getattr(api, "last_error", None)
            or response.get("errors") or not isinstance(response.get("response"), list)):
        return None
    return response["response"]


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def score_pair(value):
    if not isinstance(value, dict):
        return None
    pair = value.get("home"), value.get("away")
    return pair if all(_integer(n, 0, 30) for n in pair) else None


def period_clock(phase, elapsed, extra=0):
    """1H 45+4 precedes both HT and 2H 46. No guessed stoppage horizon."""
    if not isinstance(phase, str) or not _integer(elapsed, 0, 130) or not _integer(extra, 0, 40):
        return None
    if phase == "HT":
        return (1, 91, 0) if 45 <= elapsed <= 60 else None
    if phase not in {"1H", "2H"}:
        return None
    boundary, period = (45, 1) if phase == "1H" else (90, 2)
    if (phase == "1H" and elapsed > 60) or (phase == "2H" and elapsed < 45):
        return None
    if elapsed > boundary:
        if extra not in {0, elapsed - boundary}:
            return None
        return period, boundary, elapsed - boundary
    if extra and elapsed != boundary:
        return None
    return period, elapsed, extra


def regulation_clock(event, status):
    """Return ordered clock, None for confirmed ET/shootout, raise for ambiguity."""
    timing = event.get("time")
    if not isinstance(timing, dict):
        raise ValueError("missing event clock")
    elapsed, extra = timing.get("elapsed"), timing.get("extra")
    extra = 0 if extra is None else extra
    if not _integer(elapsed, 0, 130) or not _integer(extra, 0, 40):
        raise ValueError("invalid event time")
    phase = timing.get("period")
    if phase is not None and event.get("period") is not None and phase != event["period"]:
        raise ValueError("contradictory event periods")
    if phase is None:
        phase = event.get("period")
    if phase is None:
        if status in {"AET", "PEN"} and elapsed > 90:
            return None
        phase = "1H" if elapsed <= 45 else "2H"
    if phase in ("ET", "ET1", "ET2", "P", "PEN") and status in {"AET", "PEN"}:
        return None
    if phase not in ("1H", "2H"):
        raise ValueError("event outside a playing period")
    # A packed native event with added minutes given twice is ambiguous.
    if extra and elapsed not in {45, 90}:
        raise ValueError("ambiguous added time")
    clock = period_clock(phase, elapsed, extra)
    if clock is None:
        raise ValueError("invalid event phase")
    return clock


def _event_description(event):
    return " ".join(str(event.get(k) or "").casefold() for k in ("detail", "comments"))


def _reversed(text):
    return any(word in text for word in ("cancel", "disallow", "overturn", "no goal"))


def scoring_goal(event):
    if event.get("type") != "Goal":
        return False
    text = _event_description(event)
    if _reversed(text) or any(word in text for word in ("missed", "shootout", "shoot-out", "shoot out")):
        return False
    if str(event.get("detail") or "").strip().casefold() not in ("", "normal goal", "goal", "penalty", "own goal"):
        raise ValueError("unknown goal verdict")
    return True


def regulation_result(fixture):
    """FT may use the final goals. AET/PEN need the explicit regulation score."""
    if not isinstance(fixture, dict):
        return None
    native = fixture.get("fixture")
    status = native.get("status") if isinstance(native, dict) else None
    status = status.get("short") if isinstance(status, dict) else None
    if status not in ("FT", "AET", "PEN"):
        return None
    score = fixture.get("score")
    if score is not None and not isinstance(score, dict):
        return None
    fulltime = (score or {}).get("fulltime")
    final = score_pair(fulltime)
    if status == "FT":
        raw_goals = fixture.get("goals")
        goals = score_pair(raw_goals)
        if (raw_goals is not None and goals is None) or (fulltime is not None and final is None):
            return None
        if final is not None and goals is not None and final != goals:
            return None
        final = final if final is not None else goals
    return final


def verified_goal_timeline(fixture, events):
    """List of (ordered clock, home/away), or None if the native score is not proved."""
    final = regulation_result(fixture)
    if final is None or not isinstance(events, list):
        return None
    teams = fixture.get("teams")
    if not isinstance(teams, dict) or not all(isinstance(teams.get(s), dict) for s in ("home", "away")):
        return None
    home, away = teams["home"].get("id"), teams["away"].get("id")
    if not all(type(n) is int and n > 0 for n in (home, away)) or home == away:
        return None
    sides = {home: "home", away: "away"}
    totals = {"home": 0, "away": 0}
    goals = []
    reversals = []
    for event in events:
        if not isinstance(event, dict):
            return None
        try:
            text = _event_description(event)
            reversal = str(event.get("type") or "").casefold() == "var" and "goal" in text and _reversed(text)
            if not reversal and not scoring_goal(event):
                continue
            clock = regulation_clock(event, fixture["fixture"]["status"]["short"])
        except ValueError:
            return None
        if clock is None:
            continue
        team = event.get("team")
        team_id = team.get("id") if isinstance(team, dict) else None
        if type(team_id) is not int or team_id not in sides:
            return None
        side = sides[team_id]
        if reversal:
            reversals.append((clock, side))
            continue
        totals[side] += 1
        goals.append((clock, side))
    if (totals["home"], totals["away"]) != final:
        return None
    halftime = (fixture.get("score") or {}).get("halftime")
    if halftime is not None and halftime != {"home": None, "away": None}:
        first_half = tuple(sum(1 for clock, s in goals if s == side and clock[0] == 1)
                           for side in ("home", "away"))
        if score_pair(halftime) != first_half:
            return None
    # Separate VAR rows carry no stable original-goal reference. A retained
    # preceding goal for that side could be the cancelled one: never guess.
    if any(s == side and time <= clock for clock, side in reversals for time, s in goals):
        return None
    return sorted(goals)


def remaining_goal_timeline(goals, *, snapshot_order, baseline):
    """Subtract only score-proved past goals from an already verified timeline."""
    if (goals is None or not isinstance(snapshot_order, tuple) or len(snapshot_order) != 3
            or any(type(n) is not int for n in snapshot_order)
            or snapshot_order[0] not in (1, 2)
            or not isinstance(baseline, tuple) or len(baseline) != 2
            or not all(_integer(n, 0, 30) for n in baseline)):
        return None
    period, elapsed, extra = snapshot_order
    if (snapshot_order != (1, 91, 0)
            and period_clock("1H" if period == 1 else "2H", elapsed, extra) != snapshot_order):
        return None
    remaining = []
    for side, score in zip(("home", "away"), baseline):
        before = sum(1 for clock, s in goals if s == side and clock < snapshot_order)
        same = sum(1 for clock, s in goals if s == side and clock == snapshot_order)
        if not before <= score <= before + same:
            return None
        remaining.extend([(snapshot_order, side)] * (before + same - score))
    remaining.extend((clock, side) for clock, side in goals if clock > snapshot_order)
    return sorted(remaining)


def first_scorer(remaining):
    """Both sides in the first clock bucket: no proved first scorer."""
    if remaining is None:
        return None
    if not remaining:
        return "no_goal", None
    first = remaining[0][0]
    sides = {side for clock, side in remaining if clock == first}
    return (sides.pop(), sum(first[1:])) if len(sides) == 1 else None


def verified_next_goal(fixture, events, *, snapshot_order, baseline):
    """Return (side, minute), ('no_goal', None), or None = insufficient evidence."""
    goals = verified_goal_timeline(fixture, events)
    return first_scorer(remaining_goal_timeline(goals, snapshot_order=snapshot_order, baseline=baseline))
