"""Explicitly synthetic D1 mechanics with genuine isolated B1 receipt storage."""
from datetime import datetime, timedelta, timezone

from context_models.contracts import canonical_timestamp, digest
from context_observations import append_observation, observations_as_of
from context_sources.football import _detail_event, normalize_football_context
from context_sources.outcomes import normalize_football_base_input

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def envelope(kind, payload):
    value = {"kind": kind, "payload": payload}
    return {"digest": digest(value), **value}


def detail(native_id, scheduled, *, terminal="FT", goals=(2, 1), minutes=60):
    lineups, players = [], []
    for team, start in ((1, 1), (2, 12)):
        lineup = [{"player": {"id": p, "pos": "D"}} for p in range(start, start + 11)]
        lineups.append({"team": {"id": team}, "startXI": lineup, "substitutes": []})
        players.append({"team": {"id": team}, "players": [{"player": {"id": p}, "statistics": [
            {"games": {"minutes": minutes if p == 1 else 80, "substitute": False, "position": "D"}}]}
            for p in range(start, start + 11)]})
    return {"fixture": {"id": native_id, "date": canonical_timestamp(scheduled), "status": {"short": terminal}},
        "league": {"id": 39, "season": 2026}, "teams": {"home": {"id": 1}, "away": {"id": 2}},
        "goals": {"home": goals[0] if terminal == "FT" else None, "away": goals[1] if terminal == "FT" else None},
        "lineups": lineups, "players": players if terminal == "FT" else []}


def football_inventory(tmp_path, *, decision=NOW, count=26, event_id=9000, minute_shift=0, omit_base_target_lineups=False):
    path = tmp_path / f"synthetic-football-{event_id}.db"
    raw_inputs = []
    for index in range(count):
        kickoff = decision - timedelta(days=count-index)
        raw = detail(1000+index, kickoff, goals=(1 + index % 3, 1 + index % 2), minutes=50+10*((index+minute_shift) % 4))
        raw_inputs.append((raw, kickoff + timedelta(hours=3)))
    target = detail(event_id, decision + timedelta(hours=2), terminal="NS")
    raw_inputs.append((target, decision - timedelta(minutes=30)))
    base_rows, all_rows = [], []
    for raw, received in raw_inputs:
        ev = _detail_event(raw)
        base_raw = dict(raw)
        if raw is target and omit_base_target_lineups:
            base_raw.pop("lineups")
        records = (normalize_football_base_input(base_raw, observed_at=received),) + normalize_football_context(
            ev, injuries=[], lineups=[raw] if raw is target else [],
            appearances=[raw] if raw is not target else [], observed_at=received)
        for record in records:
            append_observation(path, record, observed_at=received)
        rows = observations_as_of(path, ev["event_key"], cutoff=decision, schedule_revision=ev["schedule_revision"])
        all_rows.extend(rows)
        base_rows.extend(row for row in rows if row["kind"] == "base_fixture")
    event = _detail_event(target)
    source_ref = next(row["digest"] for row in base_rows if row["event_key"] == event["event_key"])
    identities = envelope("context-native-identity-map-v1", {"schema": 1, "policy": "native-source-only-v1",
        "bindings": [{"event_key": event["event_key"], "home_id": event["home_id"], "away_id": event["away_id"],
                      "source_refs": [source_ref]}]})
    return event, tuple(base_rows), tuple(all_rows), identities


def football_recipe(history, *, markets=None):
    from context_models.replay import replay_code_hashes
    return envelope("context-base-replay-recipe-v1", {"schema": 1, "sport": "football", "family": "football:goals:90min",
        "base_version": "football-goals-raw-reference-v1", "code_revision": "a" * 40,
        "code_hashes": replay_code_hashes("football"), "input_refs": sorted(row["digest"] for row in history),
        "target_markets": sorted(markets or ["RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY", "BTTS_YES", "BTTS_NO"]),
        "state_ref": None, "calibrator_ref": None})
