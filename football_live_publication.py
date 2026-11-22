"""Freeze the first pre-match goal pair per fixture, separate from public market cards."""
from datetime import datetime, timedelta

from live_football_priors import (
    PRIOR_MODEL, LIVE_GOAL_PRIORS_VERSION, MAX_LIVE_GOAL_PRIORS, compact_goal_rows,
)
from ev_signal_sources import AUTOMATED_WETTFINDER_VERSION


class _Fresh(dict):
    """In-process receipt from the fixture scanner; JSON reload loses this marker."""


class _FirstEdition(dict):
    """Only newly issued rows need the atomic writer's first-write deadline check."""


def check_write_deadlines(document, now):
    """The temporary file is flushed; drop first-time pairs if kickoff has arrived."""
    changed = False
    for key in ("football", "football_next_day"):
        state = document.get(key)
        section = state.get("live_goal_priors") if isinstance(state, dict) else None
        if not isinstance(section, _FirstEdition):
            continue
        late = {fid for fid, kickoff in section.deadlines.items() if kickoff <= now}
        if late:
            section["rows"] = [r for r in section["rows"] if r["fixture_id"] not in late]
            for fid in late:
                del section.deadlines[fid]
            changed = True
    return changed


def confirm_write(document):
    for key in ("football", "football_next_day"):
        state = document.get(key)
        section = state.get("live_goal_priors") if isinstance(state, dict) else None
        if isinstance(section, _FirstEdition):
            section.deadlines.clear()


def capture_section(snapshot):
    if "live_goal_priors" not in snapshot:
        return {}
    source = snapshot["live_goal_priors"]
    rows = (source.get("rows") if isinstance(source, dict)
            and type(source.get("version")) is int and source["version"] == LIVE_GOAL_PRIORS_VERSION else None)
    # Only this writer supplies the issue clock, never the raw input or a price refresh.
    rows = [{k: v for k, v in row.items() if k != "published_at"}
            for row in rows if isinstance(row, dict)] if isinstance(rows, list) and len(rows) <= MAX_LIVE_GOAL_PRIORS else []
    return {"live_goal_priors": _Fresh(version=LIVE_GOAL_PRIORS_VERSION, rows=rows)}


def previous_section(previous, day):
    if not isinstance(previous, dict) or previous.get("version") != AUTOMATED_WETTFINDER_VERSION:
        return None
    for key, anchor in (("football", day), ("football_next_day", day - timedelta(days=1))):
        state = previous.get(key)
        if (previous.get("target_search_date") == anchor.isoformat() and isinstance(state, dict)
                and state.get("search_date") == day.isoformat() and state.get("discovery_model_version") == PRIOR_MODEL
                and (key == "football" or previous.get("next_day_search_date", day.isoformat()) == day.isoformat())):
            return state.get("live_goal_priors")
    return None


def publish_live_bases(state, previous, *, day, now):
    if state.get("search_date") != day.isoformat():
        return
    current = state.get("live_goal_priors")
    prior = previous_section(previous, day)
    if "live_goal_priors" not in state and prior is None:
        return  # retain the legacy file contract until real fixture capture is available
    frozen = compact_goal_rows(prior, day)
    if state.get("discovery_model_version") != PRIOR_MODEL:
        # A failed first run of a new day has no discovery rows/revision of its
        # own. Preserve only real overnight evidence, never any public market.
        if ("discovery_model_version" in state or state.get("status") != "degraded"
                or state.get("candidates") or current is not None or not frozen):
            return
        state["discovery_model_version"] = PRIOR_MODEL
    stamp = now.isoformat()
    fresh = isinstance(current, _Fresh)
    section = {**current, "published_at": stamp} if fresh else current
    current_rows = compact_goal_rows(section, day)
    # Keep the original pair on rediscovery, but never carry it across reschedules,
    # changed sides or an ambiguous/malformed replacement sharing the provider ID.
    identity = ("league_id", "home_id", "away_id", "scheduled_start", "home_team", "away_team")
    if fresh:
        for raw in current["rows"]:
            fid = raw.get("fixture_id")
            if type(fid) is not int or fid not in frozen:
                continue
            canonical = current_rows.get(fid)
            if canonical is None or any(canonical[k] != frozen[fid][k] for k in identity):
                del frozen[fid]
    deadlines = {}
    for fid, row in current_rows.items():
        if fresh and fid not in frozen:
            deadlines[fid] = datetime.fromisoformat(row["scheduled_start"])
        frozen.setdefault(fid, row)
    issued = _FirstEdition(version=LIVE_GOAL_PRIORS_VERSION, published_at=stamp,
                           rows=[frozen[k] for k in sorted(frozen)] if len(frozen) <= MAX_LIVE_GOAL_PRIORS else [])
    issued.deadlines = deadlines
    state["live_goal_priors"] = issued
