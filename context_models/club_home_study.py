"""Offline-only home advantage research, with no collection, persistence or activation.

The caller must resolve native publication and source receipts, verify immutable
as-of availability and full eligible league coverage, and supply an independently
pinned digest of the normalized snapshot. A self-computed digest, a hand-entered
venue or a FootballOriginal alone is NOT source or publication evidence.
"""
from datetime import date
import hashlib
import math

import challenge_engine as engine
from context_models.contracts import (ContextContractError, canonical_timestamp, digest,
                                      require_digest, require_object)
from context_models.football_joint_effect import compare_joint_effect
from context_models.football_original_storage import MAX_ORIGINAL_BYTES
from football_original import FootballOriginal, original_goal_basis


LEAGUES = frozenset({39, 78, 135, 140, 61})
STUDY_LAW = "football-joint-settlement-projection-v1"  # Freeze at registration (20 Nov 2026).
STUDY_VERSION = "challenge-engine:legacy-form-strength-joint-calibration-v1"


def _need(ok, detail):
    if not ok:
        raise ContextContractError(detail)


def _event(value):
    _need(type(value) is list and len(value) == 5, "event binding missing")
    fid, lid, home, away, kickoff = value
    _need(all(type(i) is int and i > 0 for i in (fid, lid, home, away))
          and home != away and lid in LEAGUES, "ineligible event identity")
    return fid, lid, home, away, canonical_timestamp(kickoff)


def _venue(row, cutoff):
    require_object(row, {"event", "phase", "neutral", "ground_id", "registered_home_ground_id",
                         "registered_team_id", "observed_at", "source_digest"}, label="venue receipt")
    event = _event(row["event"])
    require_digest(row["source_digest"], "venue source")
    _need(row["phase"] == "regular-season", "regular league phase evidence required")
    _need(row["neutral"] is False and all(type(row[k]) is int and row[k] > 0 for k in
          ("ground_id", "registered_home_ground_id", "registered_team_id"))
          and row["ground_id"] == row["registered_home_ground_id"]
          and row["registered_team_id"] == event[2], "affirmative home venue required")
    observed = canonical_timestamp(row["observed_at"])
    _need(observed <= cutoff and observed < event[4], "late venue receipt")
    return event


def club_home_pair(original, snapshot, *, snapshot_digest):
    """Return all common active-market probabilities, including H/D/A, without settlement.

    Input history contains only eligible same-league FT rows since July 1 of
    the previous season; foreign, duplicate, late, or nonqualifying supplied
    rows invalidate the submitted evidence, rather than silently selecting a subset.
    Event layout: [native fixture ID, league ID, home ID, away ID, scheduled UTC instant].
    observed_at means *available to this system*, not event time or a backfill.
    """
    _need(type(original) is FootballOriginal and type(original._bytes) is bytes
          and len(original._bytes) <= MAX_ORIGINAL_BYTES, "owning bounded ORIGINAL required")
    require_object(snapshot, {"original_sha256", "target_venue", "history"}, label="study snapshot")
    rows = snapshot["history"]
    _need(type(rows) is list and 60 <= len(rows) <= 1000, "history outside admissible bounds")
    require_digest(snapshot_digest)
    _need(snapshot["original_sha256"] == hashlib.sha256(original._bytes).hexdigest(), "unbound ORIGINAL")
    p = original.to_dict()
    _need(p.get("schema") == 2 and original_goal_basis(p) == engine.GOAL_MODEL_FORM_STRENGTH
          and p.get("prediction_version") == STUDY_VERSION
          and p.get("distribution_capture", {}).get("law_version") == STUDY_LAW,
          "ineligible ORIGINAL basis or law")
    active = p["distribution_capture"]["families"]["goals"]["active"]["diagnostics"]
    _need(active["success"] is True and active["status"] in ("identity", "projected"),
          "unsuccessful active goal projection")
    f = p["fixture"]
    club = f["teams"]
    e = _event([f["fixture"]["id"], f["league"]["id"], club["home"]["id"], club["away"]["id"],
                f["fixture"]["date"]])
    _need(all(f.get(k, False) is False for k in
          ("challenge_senior_national_team", "challenge_neutral_venue", "challenge_venue_unknown"))
          and f.get("challenge_league_strength") is None and p["team_history"] is None,
          "not an eligible domestic fixture")
    _need((f["fixture"].get("status") or {}).get("short") in (None, "NS")
          and all(v is None for v in (f.get("goals") or {}).values()),
          "target fixture already carries match information")
    cutoff = canonical_timestamp(p["captured_at"])
    _need(cutoff < e[4] and _venue(snapshot["target_venue"], cutoff) == e,
          "target receipt must agree with prestart ORIGINAL")
    day = date.fromisoformat(e[4][:10])
    season_year = day.year - (day.month < 7)
    first = date(season_year - 1, 7, 1).isoformat()
    seen, h, a = {e[0]}, 0, 0
    for row in rows:
        require_object(row, {"venue", "result"}, label="historical evidence")
        past = _venue(row["venue"], cutoff)
        result = require_object(row["result"], {"event", "status", "goals", "observed_at",
                                                "source_digest"}, label="result receipt")
        require_digest(result["source_digest"], "result source")
        _need(past == _event(result["event"]) and past[1] == e[1] and past[0] not in seen,
              "unbound, duplicate, or foreign historical fixture")
        seen.add(past[0])
        _need(first <= past[4][:10] < e[4][:10]
              and past[4] < canonical_timestamp(result["observed_at"]) <= cutoff
              and result["status"] == "FT", "not a timely completed regulation result")
        goals = result["goals"]
        _need(type(goals) is list and len(goals) == 2 and
              all(type(x) is int and x >= 0 for x in goals), "invalid regulation score")
        h += goals[0]
        a += goals[1]
    _need(min(h, a) > 0, "undefined goal ratio")
    _need(digest(snapshot) == snapshot_digest, "unbound evidence snapshot")
    delta = .125 * math.log(h / a)
    changed = compare_joint_effect(original, home_delta=delta, away_delta=-delta)
    return {"history_n": len(rows), "delta": delta, "snapshot_digest": snapshot_digest,
            "baseline": {k: v[0] for k, v in p["probabilities"].items()},
            "candidate": {k: v[0] for k, v in changed["probabilities"].items()},
            "scope": "offline-research-only"}
