"""Synthetic proofs only; no network, store, published matches or scores."""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import importlib
import importlib.util
import math

import pytest

import challenge_engine as ce
import football_original
from context_models.contracts import ContextContractError, digest
from tests.test_football_base_provenance import history, target
from tests.test_football_original_capture import calibration


def study():
    name = "context_models.club_home_study"
    assert importlib.util.find_spec(name), "offline club/home comparison is missing"
    return importlib.import_module(name).club_home_pair


def instant(dt):
    return dt.isoformat()


def proof(event):
    return {"event": event, "phase": "regular-season", "neutral": False, "ground_id": 9,
            "registered_home_ground_id": 9, "registered_team_id": event[2],
            "observed_at": instant(datetime.fromisoformat(event[4]) - timedelta(hours=12)),
            "source_digest": "f"*64}


@pytest.fixture(scope="module")
def originals():
    current, rows = target(), history()
    ko = datetime.fromisoformat(current["fixture"]["date"])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(football_original, "_capture_now", lambda: ko - timedelta(hours=3))
        out = []
        for basis in (ce.GOAL_MODEL_FORM_STRENGTH, ce.GOAL_MODEL_LEGACY):
            ce.fixture_market_probabilities(current, rows, calibration(), original_capture=out.append,
                                            goal_model=basis)
    return out


def snapshot(original, home_goals=1):
    f = original.to_dict()["fixture"]
    ko = datetime.fromisoformat(f["fixture"]["date"])
    e = [f["fixture"]["id"], f["league"]["id"], f["teams"]["home"]["id"],
         f["teams"]["away"]["id"], instant(ko)]
    rows = []
    for i in range(60):
        dt = ko - timedelta(days=i+1)
        ev = [i+301, 39, 1, 2, instant(dt)]
        rows.append({"venue": proof(ev), "result": {"event": ev.copy(), "status": "FT",
                     "goals": [home_goals, 1], "observed_at": instant(dt + timedelta(hours=2)),
                     "source_digest": "e"*64}})
    return {"original_sha256": hashlib.sha256(original._bytes).hexdigest(),
            "target_venue": proof(e), "history": rows}


def pair(original, snap):
    return study()(original, snap, snapshot_digest=digest(snap))


def test_neutral_effect_exactly_preserves_original_active_probabilities(originals):
    orig = originals[0]
    p = pair(orig, snapshot(orig))
    assert p["history_n"] == 60 and p["delta"] == 0
    assert p["baseline"] == p["candidate"] == {k: v[0] for k,v in orig.to_dict()["probabilities"].items()}


def test_tilts_effective_cells_once_and_projects_active_1x2(originals):
    orig = originals[0]
    out = pair(orig, snapshot(orig, 2))
    assert out["delta"] == pytest.approx(math.log(2)/8)
    cells = orig.to_dict()["distribution_capture"]["families"]["goals"]["active"]["effective_cells"]
    w = [(h, a, p*2**((h-a)/8)) for h,a,p in cells]
    denom = sum(p for _,_,p in w)
    assert [out["candidate"][k] for k in ("RESULT_HOME","RESULT_DRAW","RESULT_AWAY")] == pytest.approx(
        [sum(p for h,a,p in w if cmp(h,a))/denom for cmp in (int.__gt__, int.__eq__, int.__lt__)])


@pytest.mark.parametrize("bad", ["bare","neutral","unknown","ground","team","other_target","late_venue",
    "unbound_result","future_result","other_league","duplicate","small","not_ft","same_day","old",
    "legacy","unsealed","target_playoff","prior_playoff","unbounded"])
def test_ineligible_or_unbound_rows_cannot_create_pair(originals, bad):
    orig = originals[bad == "legacy"]
    snap = snapshot(orig)
    v = snap["target_venue"]
    r = snap["history"][0]
    if bad == "bare": snap["target_venue"] = True
    elif bad == "neutral": v["neutral"] = True
    elif bad == "unknown": del v["neutral"]
    elif bad == "ground": v["ground_id"] += 1
    elif bad == "team": v["registered_team_id"] += 1
    elif bad == "other_target": v["event"][0] += 1
    elif bad == "late_venue": v["observed_at"] = v["event"][4]
    elif bad == "unbound_result": r["result"]["event"][2] += 1
    elif bad == "future_result": r["result"]["observed_at"] = v["event"][4]
    elif bad == "other_league":
        for k in ("result","venue"): r[k]["event"][1] = 61
    elif bad == "duplicate": snap["history"].append(deepcopy(r))
    elif bad == "small": snap["history"].pop()
    elif bad == "not_ft": r["result"]["status"] = "AET"
    elif bad == "target_playoff": v["phase"] = "relegation"
    elif bad == "prior_playoff": r["venue"]["phase"] = "relegation"
    elif bad == "unbounded": snap["history"] = [r] * 1001
    elif bad in ("same_day","old"):
        dt = datetime.fromisoformat(v["event"][4]) - (timedelta(hours=8) if bad == "same_day" else timedelta(days=790))
        for k in ("result","venue"): r[k]["event"][4] = instant(dt)
        r["venue"]["observed_at"] = instant(dt-timedelta(hours=2))
        r["result"]["observed_at"] = instant(dt+timedelta(hours=2))
    with pytest.raises(ContextContractError):
        study()(orig, snap, snapshot_digest="a"*64 if bad == "unsealed" else digest(snap))


def test_failed_calibration_is_not_a_study_baseline(originals):
    from football_original import FootballOriginal
    from model_artifacts import canonical_bytes
    p = originals[0].to_dict()
    p["distribution_capture"]["families"]["goals"]["active"]["diagnostics"]["success"] = False
    orig = FootballOriginal(canonical_bytes(p))
    with pytest.raises(ContextContractError, match="goal projection"):
        pair(orig, snapshot(orig))
