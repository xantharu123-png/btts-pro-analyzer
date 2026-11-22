"""Read fixture rates from an old discovery edition only if its actual bytes predate kickoff.

The caller must compare path stat and open fstat before and after the read. POSIX
inode change time protects against a restored mtime; a quote rewrite after kickoff
therefore disables this bridge for that match, even when the pools look unchanged.
No API, replay, price input, stored snapshot, or reconstructed cutoff.
"""
from datetime import date, timedelta, timezone, datetime
import os
from zoneinfo import ZoneInfo

from challenge_engine import (CHALLENGE_MARKET_CATALOG_SIGNATURE, GOAL_PROJECTION_MARKET_SPECS,
                              MARKET_BY_KEY, MODEL_SCOPE_SAME_COMPETITION)
from ev_signal_sources import MAX_AUTOMATED_FOOTBALL_CANDIDATES
from forecast_analysis import _clock


_POSIX_CTIME = os.name == "posix"
_GOALS = frozenset(spec.key for spec in GOAL_PROJECTION_MARKET_SPECS)
# These three pre-context selection objections do not invalidate the goal distribution.
# A failed calibration, stale inputs, or a new/unknown reason cannot become a live basis.
_MARKET_ONLY_REASONS = {"Markt hat das Walk-forward-Gate nicht bestanden", "Evidenzscore unter 72",
                        "Saison- und Formmodell widersprechen sich"}
_ZURICH = ZoneInfo("Europe/Zurich")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _ns(t):
    return (t - _EPOCH) // timedelta(microseconds=1) * 1000


def _equal_typed(a, b):
    return type(a) is type(b) and a == b


def _raw_basis(row, recent, *, model, attempt, generated, day, file_ns, basis_factory):
    fid, league, home, away = (row.get(k) for k in ("fixture_id", "league_id", "home_team_id", "away_team_id"))
    names = row.get("home_team"), row.get("away_team")
    key, start = row.get("market_key"), row.get("kickoff")
    rates = row.get("expected_home_goals"), row.get("expected_away_goals")
    reasons = row.get("blocked_reasons")
    if (not isinstance(reasons, list) or not all(isinstance(r, str) and r in _MARKET_ONLY_REASONS for r in reasons)
            or not all(type(i) is int and i > 0 for i in (fid, league, home, away)) or home == away
            or not all(isinstance(n, str) and n.strip() == n and 0 < len(n) <= 200 for n in names)
            or names[0].casefold() == names[1].casefold() or row.get("candidate_id") != f"{fid}:{key}"
            or row.get("model_scope") != MODEL_SCOPE_SAME_COMPETITION or row.get("prediction_version") != model
            or row.get("expected_unit", "missing") is not None
            or not all(type(n) in (int, float) and 0 <= n <= 8 for n in rates)):
        return None
    comp, valid = row.get("market_comparison"), row.get("validation")
    if not all(isinstance(x, dict) for x in (recent, comp, valid)):
        return None
    ident = {"fixture_id": fid, "home_id": home, "away_id": away, "scheduled_start": start}
    if (recent.get("schema") != "football-recent-results-v1" or recent.get("model_scope") != MODEL_SCOPE_SAME_COMPETITION
            or any(not _equal_typed(recent.get(k), v) for k, v in ident.items())
            or comp.get("schema") != "league-market-comparison-v1" or valid.get("prediction_version") != model
            or any(not _equal_typed(comp.get(k), v) for k, v in
                   {**ident, "market_key": key, "league_id": league, "prediction_version": model,
                    "validation_prediction_version": model}.items())):
        return None
    kickoff, completion_bound, latest_history = map(_clock, (start, recent.get("as_of"), comp.get("latest_kickoff")))
    if (None in (kickoff, completion_bound, latest_history) or not latest_history < completion_bound
            or not attempt <= completion_bound <= generated or file_ns >= _ns(kickoff)):
        return None
    try:
        if kickoff.astimezone(_ZURICH).date() != day:
            return None
    except OverflowError:
        return None
    # Same scan creates recent.as_of just after build_fixture_candidates with the same fixture and history.
    # This is an upper bound on modeling, not an exact model/cutoff receipt; never re-publish this evidence.
    return basis_factory(league, home, away, *names, kickoff, None, completion_bound, rates)


def legacy_unpublished_priors(document, *, stat, basis_factory, model):
    """Initial same-day discovery only; the enclosing reader owns version, regular-file and race checks."""
    if not _POSIX_CTIME or stat is None or not isinstance(document, dict):
        return {}
    clocks = (stat.st_mtime_ns, stat.st_ctime_ns)
    if not all(type(n) is int and n > 0 for n in clocks):
        return {}
    s = document.get("football")
    if (not isinstance(s, dict) or s.get("discovery_model_version") != model
            or s.get("discovery_market_catalog_signature") != CHALLENGE_MARKET_CATALOG_SIGNATURE
            or s.get("status") not in ("completed", "degraded")
            or any(k in s for k in ("live_goal_priors", "model_checks", "last_context_at", "model_refresh_failed_fixture_ids"))
            or s.get("search_date") != document.get("target_search_date")):
        return {}
    try:
        day = date.fromisoformat(s["search_date"])
    except (KeyError, ValueError, TypeError):
        return {}
    attempt, generated = _clock(s.get("last_attempt_at")), _clock(document.get("generated_at"))
    recent = s.get("football_recent_results")
    pools = [s.get("discovery_candidates"), s.get("riskobet_source_candidates")]
    if (attempt is None or generated is None or not attempt <= generated or _ns(generated) > min(clocks)
            or attempt.astimezone(_ZURICH).date() != day or not isinstance(recent, dict)
            or not all(isinstance(p, list) for p in pools) or sum(map(len, pools)) > MAX_AUTOMATED_FOOTBALL_CANDIDATES
            or not all(_equal_typed(s.get(k), len(p)) for p, k in zip(pools, (
                "discovery_candidate_count", "riskobet_source_candidate_count")))):
        return {}
    index = {}
    for pool in pools:
        for row in pool:
            if not isinstance(row, dict) or type(fid := row.get("fixture_id")) is not int or fid <= 0:
                continue
            key = row.get("market_key")
            if isinstance(key, str) and key in MARKET_BY_KEY and key not in _GOALS:
                continue  # corner or card intensities cannot supply goals
            value = (_raw_basis(row, recent.get(str(fid)), model=model, attempt=attempt, generated=generated,
                                day=day, file_ns=max(clocks), basis_factory=basis_factory)
                     if isinstance(key, str) and key in _GOALS else None)
            index[fid] = value if fid not in index or index[fid] == value else None
    return {fid: v for fid, v in index.items() if v is not None}
