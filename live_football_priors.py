"""Read-only fixture index of pre-kickoff, production football goal intensities.

The Wettfinder writer owns the artifact. No prices, current games or outcomes
are used to reconstruct missing priors. Retain just one compact edition, not the
document and not one copy per viewer or live fixture.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from stat import S_ISREG
from threading import Lock
from zoneinfo import ZoneInfo

from challenge_engine import (
    CHALLENGE_PREDICTION_VERSION, FORM_STRENGTH_PREDICTION_VERSION, MARKET_BY_KEY, MODEL_SCOPE_SAME_COMPETITION,
)
from ev_signal_sources import AUTOMATED_WETTFINDER_VERSION, MAX_AUTOMATED_FOOTBALL_CANDIDATES
from forecast_analysis import _clock, read_football_analysis
from season_utils import current_season_start_year_for_id


# A different production basis requires explicit review, not an implicit live revision.
PRIOR_MODEL = FORM_STRENGTH_PREDICTION_VERSION
PRIOR_REVISION = ":wettfinder-goal-prior-v1:" + PRIOR_MODEL
LIVE_GOAL_PRIORS_VERSION = 1
MAX_LIVE_GOAL_PRIORS = 1_200  # daily discovery fixture bound; independent of public market shortlists
_GOAL_KINDS = {"result", "double_chance", "btts", "total", "total_range", "team_total", "team_range",
               "result_total", "mixed_or"}
_MAX_BYTES = 64 * 1024 * 1024
_ZURICH = ZoneInfo("Europe/Zurich")
_lock = Lock()
_cached_edition = None
_cached_index = {}


@dataclass(frozen=True)
class _GoalBasis:
    league: int
    home: int
    away: int
    home_name: str
    away_name: str
    kickoff: datetime
    cutoff: datetime | None  # only the legacy market evidence contains a separate input-cutoff clock
    modeled: datetime
    rates: tuple[float, float]
    first_published: datetime | None = None  # compact, fixture-level evidence only


def _basis(row, day, published):
    key = row.get("market_key")
    spec = MARKET_BY_KEY.get(key) if isinstance(key, str) else None
    if (not spec or spec.kind not in _GOAL_KINDS or row.get("market_kind") != spec.kind
            or row.get("sport") != "Fußball" or row.get("source") != "football_challenge"
            or row.get("event_identity") != f"football:{row['fixture_id']}"
            or row.get("candidate_id") != f"{row['fixture_id']}:{key}"
            or type(row.get("league_id")) is not int or row["league_id"] <= 0
            or row.get("model_scope") != MODEL_SCOPE_SAME_COMPETITION
            or any(row.get(k) != PRIOR_MODEL for k in ("prediction_version", "model_version",
                                                        "validation_prediction_version"))):
        return None
    evidence = read_football_analysis(row, now=published)
    if not evidence:
        return None
    identity, basis = evidence["identity"], evidence["basis"]
    kickoff, cutoff, modeled = (_clock(identity[k]) for k in ("scheduled_start", "input_cutoff_at", "modeled_at"))
    rates = tuple(basis.get(k) for k in ("expected_home_goals", "expected_away_goals"))
    if (None in (kickoff, cutoff, modeled) or not cutoff <= modeled <= published < kickoff
            or kickoff.astimezone(_ZURICH).date() != day
            or not all(type(n) in (int, float) and 0 <= n <= 8 for n in rates)):
        return None
    return _GoalBasis(row["league_id"], identity["home_id"], identity["away_id"],
                      identity["home_team"], identity["away_team"], kickoff, cutoff, modeled, rates)


def _compact_basis(row, day, publication):
    if (row.get("model_version") != PRIOR_MODEL or row.get("model_scope") != MODEL_SCOPE_SAME_COMPETITION
            or not all(type(row.get(k)) is int and row[k] > 0 for k in ("league_id", "home_id", "away_id"))
            or row["home_id"] == row["away_id"]):
        return None
    names = row.get("home_team"), row.get("away_team")
    if (not all(isinstance(n, str) and n.strip() and len(n) <= 200 for n in names)
            or names[0].strip().casefold() == names[1].strip().casefold()):
        return None
    kickoff = _clock(row.get("scheduled_start"))
    modeled = _clock(row.get("modeled_at"))
    first_published = _clock(row["published_at"]) if "published_at" in row else publication
    rates = row.get("expected_home_goals"), row.get("expected_away_goals")
    if (None in (kickoff, modeled, first_published) or not modeled <= first_published <= publication
            or first_published >= kickoff or kickoff.astimezone(_ZURICH).date() != day
            or not all(type(n) in (int, float) and 0 <= n <= 8 for n in rates)):
        return None
    return _GoalBasis(row["league_id"], row["home_id"], row["away_id"], *names, kickoff, None,
                      modeled, rates, first_published)


def _compact_index(section, day):
    if (not isinstance(section, dict) or type(section.get("version")) is not int
            or section["version"] != LIVE_GOAL_PRIORS_VERSION
            or not isinstance(rows := section.get("rows"), list) or len(rows) > MAX_LIVE_GOAL_PRIORS
            or (publication := _clock(section.get("published_at"))) is None):
        return {}
    index = {}
    for row in rows:
        if not isinstance(row, dict) or type(fid := row.get("fixture_id")) is not int or fid <= 0:
            continue
        if fid in index:
            index[fid] = None  # unlike old per-market rows, this contract publishes one row per fixture
            continue
        try:
            index[fid] = _compact_basis(row, day, publication)
        except (ValueError, OverflowError):
            index[fid] = None
    return index


def compact_goal_rows(envelope, day: date) -> dict[int, dict]:
    """Project validated published priors for carry-forward; never carry arbitrary payload or reset first clocks."""
    return {
        fid: {
            "fixture_id": fid, "league_id": value.league, "home_id": value.home, "away_id": value.away,
            "home_team": value.home_name, "away_team": value.away_name,
            "scheduled_start": value.kickoff.isoformat(), "modeled_at": value.modeled.isoformat(),
            "published_at": value.first_published.isoformat(),
            "model_version": PRIOR_MODEL, "model_scope": MODEL_SCOPE_SAME_COMPETITION,
            "expected_home_goals": value.rates[0], "expected_away_goals": value.rates[1],
        }
        for fid, value in _compact_index(envelope, day).items() if value is not None
    }


def _project_index(document, *, stat=None):
    if (not isinstance(document, dict) or type(document.get("version")) is not int
            or document["version"] != AUTOMATED_WETTFINDER_VERSION or CHALLENGE_PREDICTION_VERSION != PRIOR_MODEL):
        return {}
    generated = _clock(document.get("generated_at"))
    if generated is None:
        return {}
    try:
        today = date.fromisoformat(document["target_search_date"])
    except (KeyError, TypeError, ValueError):
        return {}
    index = {}
    compact_present = False
    for group, field in (("football", "target_search_date"), ("football_next_day", "next_day_search_date")):
        state = document.get(group)
        compact_present |= isinstance(state, dict) and "live_goal_priors" in state
        if not isinstance(state, dict) or state.get("discovery_model_version") != PRIOR_MODEL:
            continue
        day = today + timedelta(days=1) if group == "football_next_day" else today
        if day.isoformat() != state.get("search_date"):
            continue
        if "live_goal_priors" in state:
            # A tomorrow search may have priors but no publishable market preview.
            # A present but broken section must never fall through to that market catalog.
            if field not in document or document[field] == day.isoformat():
                for fid, basis in _compact_index(state["live_goal_priors"], day).items():
                    index[fid] = basis if fid not in index else None
            continue
        published = _clock(document.get("decision_at")) if group == "football_next_day" else generated
        pools = [state.get(k) for k in ("candidates", "basis_candidates")]
        if (day.isoformat() != document.get(field) or not published or published < generated
                or not all(isinstance(pool, list) for pool in pools)
                or sum(map(len, pools)) > MAX_AUTOMATED_FOOTBALL_CANDIDATES):
            continue
        for pool in pools:
            for row in pool:
                if not isinstance(row, dict) or type(fid := row.get("fixture_id")) is not int or fid <= 0:
                    continue
                key = row.get("market_key")
                spec = MARKET_BY_KEY.get(key) if isinstance(key, str) else None
                if spec is not None and spec.kind not in _GOAL_KINDS:
                    continue  # No corner/card counts, even if goal numbers are attached.
                try:
                    candidate = _basis(row, day, published)
                except (KeyError, ValueError, TypeError, OverflowError, RecursionError):
                    candidate = None
                # Each goal market of a fixture should repeat the same model facts.
                # Conflicting or broken target evidence is sticky for this edition.
                index[fid] = candidate if fid not in index or index[fid] == candidate else None
    if stat is not None and not compact_present:
        from live_football_legacy_priors import legacy_unpublished_priors
        for fid, basis in legacy_unpublished_priors(document, stat=stat, basis_factory=_GoalBasis,
                                                    model=PRIOR_MODEL).items():
            index.setdefault(fid, basis)  # Never revive a conflicting or malformed legacy goal record.
    return {fid: value for fid, value in index.items() if value is not None}


def _edition(path, stat):
    # Windows path.stat and fstat can disagree on ctime (creation vs.
    # metadata-change time). The file ID changes on atomic replacement.
    return (path, stat.st_dev, stat.st_ino, stat.st_mtime_ns,
            stat.st_ctime_ns if os.name != "nt" else None, stat.st_size)


def _index(path):
    global _cached_edition, _cached_index
    try:
        with _lock:
            info = path.stat()
            if not S_ISREG(info.st_mode) or not 0 < info.st_size <= _MAX_BYTES:
                return {}
            edition = _edition(path, info)
            if edition != _cached_edition:
                with path.open("rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if _edition(path, opened) != edition:
                        return {}
                    data = stream.read(info.st_size + 1)
                    if _edition(path, os.fstat(stream.fileno())) != edition:
                        return {}
                if len(data) != info.st_size:
                    return {}
                try:
                    index = _project_index(json.loads(data), stat=opened)
                except (TypeError, ValueError, RecursionError, OverflowError):
                    index = {}
                if _edition(path, path.stat()) != edition:
                    return {}
                _cached_edition, _cached_index = edition, index
            return _cached_index
    except OSError:
        return {}


def stored_goal_priors(match):
    """Return this exact live fixture's bilateral pair, or no prior. Never fetch."""
    from ev_signal_sources import AUTOMATED_WETTFINDER_PATH
    if not isinstance(match, dict):
        return None
    native, teams, league = (match.get(k) for k in ("fixture", "teams", "league"))
    if not all(isinstance(value, dict) for value in (native, teams, league)):
        return None
    kickoff = _clock(native.get("date"))
    now = datetime.now(timezone.utc)
    if (kickoff is None or kickoff > now or type(native.get("id")) is not int
            or (now.astimezone(_ZURICH).date() - kickoff.astimezone(_ZURICH).date()).days > 1):
        return None
    if "timestamp" in native and (type(native["timestamp"]) is not int or native["timestamp"] != kickoff.timestamp()):
        return None
    basis = _index(Path(AUTOMATED_WETTFINDER_PATH)).get(native["id"])
    if (basis is None or kickoff != basis.kickoff or type(league.get("id")) is not int or league["id"] != basis.league):
        return None
    if ("season" in league and (type(league["season"]) is not int
            or league["season"] != current_season_start_year_for_id(basis.league, when=kickoff.astimezone(_ZURICH)))):
        return None
    for side, identifier, name in (("home", basis.home, basis.home_name), ("away", basis.away, basis.away_name)):
        team = teams.get(side)
        if (not isinstance(team, dict) or type(team.get("id")) is not int or team["id"] != identifier
                or team.get("name") != name):
            return None
    return basis.rates
