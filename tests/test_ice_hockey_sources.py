"""Synthetic NHL internal envelopes: no real TOI/goalie source qualification."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from test_ice_hockey_context import NOW, event, scope


def source():
    from context_sources import ice_hockey
    return ice_hockey


def team(team_id, *, measured=True):
    first = int(team_id.rsplit(":", 1)[1])*1000
    skaters = [f"nhl:ice_hockey:player:{first+i}" for i in range(1, 7)]
    goalie = f"nhl:ice_hockey:player:{first+101}"
    players = [{"player_id": player, "role": "skater", "regulation_seconds": 3600 if i < 5 else 100,
                "overtime_seconds": (300 if i < 3 else 0) if measured else None} for i, player in enumerate(skaters)]
    players.append({"player_id": goalie, "role": "goalie", "regulation_seconds": 3500,
                    "overtime_seconds": 300 if measured else None})
    return {"complete": True, "players": players, "regulation_intervals": [
        {"start": 0, "end": 3500, "skaters": skaters[:5], "goalie": goalie},
        {"start": 3500, "end": 3600, "skaters": skaters, "goalie": None}],
        "overtime_intervals": [{"start": 0, "end": 300, "skaters": skaters[:3], "goalie": goalie}] if measured else None}


def raw(kind="appearance", *, ev=None):
    ev = deepcopy(ev or event())
    if kind == "appearance":
        ev.update(event_key="nhl:ice_hockey:2025021888", status="completed",
                  scheduled_start=canonical_timestamp(NOW-timedelta(hours=32)))
        data = {"actual_start": ev["scheduled_start"], "actual_end": canonical_timestamp(NOW-timedelta(hours=30)),
                "result_observed_at": canonical_timestamp(NOW-timedelta(hours=29)), "regulation_seconds": 3600,
                "overtime_seconds": 300, "terminal_phase": "OT",
                "teams": {ev[side]: team(ev[side]) for side in ("home_id", "away_id")}}
    elif kind == "projection":
        data = {"scenarios": [{"scenario_id": "candidate-a", "teams": {
            ev[side]: team(ev[side], measured=False) for side in ("home_id", "away_id")}}]}
    elif kind == "starter":
        data = {"teams": {ev[side]: {"status": "confirmed", "player_id": f"nhl:ice_hockey:player:{int(ev[side].rsplit(':',1)[1])*1000+101}"}
                          for side in ("home_id", "away_id")}}
    else:
        data = {"teams": {ev[side]: {"complete": True, "players": [
            {"player_id": item["player_id"], "status": "available"} for item in team(ev[side])["players"]]}
            for side in ("home_id", "away_id")}}
    return {"schema": 1, "source_schema": "hockey-internal-context-v1", "kind": kind, "event": ev,
            "scope": scope(), "valid_from": canonical_timestamp(NOW-timedelta(hours=1)), "valid_until": None, "data": data}


def normalized(item, observed=NOW):
    return source().normalize_ice_hockey_context(item["event"], (item,), observed_at=observed)[0]


@pytest.mark.parametrize("mutation", ["sort-null", "sort-list", "skater-object", "starter-status", "availability-status"])
def test_malformed_nested_shapes_have_typed_errors(mutation):
    item = raw("starter" if mutation == "starter-status" else "availability" if mutation == "availability-status" else "appearance")
    if mutation.startswith("sort-"):
        item["data"]["teams"][event()["home_id"]]["regulation_intervals"][0]["start"] = None if mutation == "sort-null" else []
    elif mutation == "skater-object": item["data"]["teams"][event()["home_id"]]["regulation_intervals"][0]["skaters"][0] = {}
    elif mutation == "starter-status": item["data"]["teams"][event()["home_id"]]["status"] = []
    else: item["data"]["teams"][event()["home_id"]]["players"][0]["status"] = []
    with pytest.raises(ContextContractError): normalized(item)


@pytest.mark.parametrize("kind", ["appearance", "projection", "starter", "availability"])
def test_closed_whole_event_source_roundtrip_preserves_declared_fact_kind(kind):
    item = raw(kind)
    before = deepcopy(item)
    row = normalized(item)
    assert row["complete"] is True
    assert row["payload"]["kind"] == kind
    assert source().validate_hockey_receipt({**row, "observed_at": canonical_timestamp(NOW)}) == row["payload"]
    assert item == before


def test_actual_empty_net_and_ot_exposure_are_separate_not_five_times_sixty():
    row = normalized(raw())
    players = row["payload"]["data"]["teams"][event()["home_id"]]["players"]
    assert sum(p["regulation_seconds"] for p in players if p["role"] == "skater") == 18100
    assert sum(p["regulation_seconds"] for p in players if p["role"] == "goalie") == 3500
    assert sum(p["overtime_seconds"] for p in players if p["role"] == "skater") == 900
    assert sum(p["overtime_seconds"] for p in players if p["role"] == "goalie") == 300


@pytest.mark.parametrize("mutation", ["gap", "overlap", "toi", "goalie-toi", "duplicate", "foreign-player", "role", "negative",
    "boolean", "so-playoff", "reg-ot", "future", "same-teams", "price", "unknown-season", "unknown-rule"])
def test_native_source_rejects_inconsistent_collection_and_phase(mutation):
    item = raw()
    data = item["data"]
    usage = data["teams"][event()["home_id"]]
    if mutation == "gap": usage["regulation_intervals"][1]["start"] += 1
    elif mutation == "overlap": usage["regulation_intervals"][1]["start"] -= 1
    elif mutation == "toi": usage["players"][0]["regulation_seconds"] -= 1
    elif mutation == "goalie-toi": usage["players"][-1]["regulation_seconds"] = 3600
    elif mutation == "duplicate": usage["players"].append(deepcopy(usage["players"][0]))
    elif mutation == "foreign-player": usage["regulation_intervals"][0]["skaters"][0] = "nhl:ice_hockey:player:999999"
    elif mutation == "role": usage["players"][0]["role"] = "goalie"
    elif mutation == "negative": usage["players"][0]["overtime_seconds"] = -1
    elif mutation == "boolean": data["overtime_seconds"] = True
    elif mutation == "so-playoff":
        item["event"]["format"] = "nhl_reg60_playoff_ot"
        item["scope"]["game_type"] = 3
        data["terminal_phase"] = "SO"
    elif mutation == "reg-ot": data["terminal_phase"] = "REG"
    elif mutation == "future": data["result_observed_at"] = canonical_timestamp(NOW+timedelta(microseconds=1))
    elif mutation == "same-teams": item["event"]["away_id"] = item["event"]["home_id"]
    elif mutation == "price": data["odds"] = 1.3
    elif mutation == "unknown-season": item["scope"]["season"] = 20262027
    else: item["scope"]["rule_version"] = "unreviewed"
    with pytest.raises(ContextContractError): normalized(item)


@pytest.mark.parametrize("missing", ["regulation_seconds", "overtime_seconds", "regulation_intervals", "overtime_intervals"])
def test_missing_usage_is_unknown_not_silent_zero_or_full_exposure(missing):
    item = raw()
    usage = item["data"]["teams"][event()["home_id"]]
    if missing.endswith("intervals"): usage[missing] = None
    else: usage["players"][0][missing] = None
    row = normalized(item)
    assert row["complete"] is False
    stored = row["payload"]["data"]["teams"][event()["home_id"]]
    assert (stored[missing] if missing.endswith("intervals") else stored["players"][0][missing]) is None


def test_reported_candidates_are_neither_starter_confirmation_nor_probability_weights():
    item = raw("starter")
    item["data"]["teams"][event()["home_id"]]["status"] = "unconfirmed"
    row = normalized(item)
    assert row["complete"] is False
    assert row["payload"]["data"]["teams"][event()["home_id"]]["status"] == "unconfirmed"
    scenario = raw("projection")
    scenario["data"]["scenarios"][0]["weight"] = .5
    with pytest.raises(ContextContractError): normalized(scenario)
