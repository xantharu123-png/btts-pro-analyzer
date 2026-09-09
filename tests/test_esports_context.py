"""C4 synthetic contract/mechanism tests; no claimed native feed coverage."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import runpy

import numpy as np
import pytest

from context_models.contracts import ContextContractError, digest

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def legacy_match():
    def history(team, opponent, first, wins):
        return [{"match_id": first + i, "begin_at": (NOW - timedelta(days=25-i, hours=2)).isoformat(),
                 "end_at": (NOW - timedelta(days=25-i)).isoformat(), "opponent_id": opponent,
                 "won": (i * wins) % 20 < wins, "number_of_games": 1 if i % 3 == 0 else 3}
                for i in range(20)]
    return {"id": 9000, "game": "CS2", "team1": "Alpha", "team2": "Beta", "team1_id": 7, "team2_id": 8,
            "status": "upcoming", "begin_at": (NOW + timedelta(hours=6)).isoformat(),
            "team1_score": 0, "team2_score": 0, "series_type": 3,
            "team1_stats": {"matches": 20, "wins": 15}, "team2_stats": {"matches": 20, "wins": 8},
            "team1_history": history(7, 100, 1000, 15), "team2_history": history(8, 100, 2000, 8)}


def test_series_offset_is_antisymmetric():
    from context_models.esports import series_probability
    p = series_probability(.6, -.3)
    assert p < .6
    assert p + series_probability(.4, .3) == pytest.approx(1.)


def native_event(identity=9000, a=7, b=8, *, best_of=3, start=None, status="scheduled"):
    return {"event_key": f"pandascore:esports:{identity}", "sport": "esports",
            "competition": "pandascore:title:1:competition:9", "format": f"series_best_of_{best_of}",
            "home_id": f"pandascore:esports:team:{a}", "away_id": f"pandascore:esports:team:{b}",
            "scheduled_start": (start or NOW + timedelta(hours=6)).isoformat(), "schedule_revision": "native-schedule-1", "status": status}


def scope(best_of=3):
    return {"title": "csgo", "title_id": 1, "competition_id": 9, "season_id": 2026,
            "rules": {"best_of": best_of, "starting_maps_a": 0, "starting_maps_b": 0, "forfeit": False}}


def source(kind, event, data):
    from context_sources.esports import SCHEMA
    return {"schema": 1, "source_schema": SCHEMA, "kind": kind, "event": deepcopy(event),
            "scope": scope(int(event["format"].rsplit("_", 1)[1])), "valid_until": None, "data": deepcopy(data)}


def lineup_data(event, *, status="observed", missing_player=False):
    teams = {}
    for side in ("home_id", "away_id"):
        key = event[side]
        team = int(key.rsplit(":", 1)[1])
        players = [{"player_id": f"pandascore:esports:player:{team * 100 + i}", "participated": True, "stand_in": False}
                   for i in range(1, 6)]
        if status != "observed" and team == 7:
            players[0]["participated"] = not missing_player
            players.append({"player_id": "pandascore:esports:player:706", "participated": missing_player, "stand_in": missing_player})
        teams[key] = {"complete": True, "players": players}
    return {"status": status, "teams": teams}


def ingest(path, target, records):
    from context_sources.esports import normalize_esports_context
    from context_observations import append_observation, observations_as_of
    keys = set()
    for raw, receipt in records:
        normalized = normalize_esports_context(target, (raw,), observed_at=receipt)
        for row in normalized:
            append_observation(path, row, observed_at=receipt)
            keys.add((row["event_key"], row["schedule_revision"]))
    return tuple(row for key, schedule in sorted(keys) for row in observations_as_of(
        path, key, cutoff=NOW, schedule_revision=schedule))


def make_case(path, *, missing_player=True, decision=NOW, identity=9000, best_of=3):
    from context_models.esports import esports_features
    from context_models.contracts import validate_event
    from multi_sport_recommendations import esports_match_winner_candidate
    match = legacy_match()
    match.update(id=identity, begin_at=(decision + timedelta(hours=6)).isoformat(), series_type=best_of)
    event = validate_event(native_event(identity, start=decision + timedelta(hours=6), best_of=best_of))
    records = []
    for side, team in (("team1_history", 7), ("team2_history", 8)):
        for row in match[side]:
            end = datetime.fromisoformat(row["end_at"])
            historic = native_event(row["match_id"], team, row["opponent_id"], best_of=row["number_of_games"],
                                    start=datetime.fromisoformat(row["begin_at"]), status="completed")
            needed = row["number_of_games"] // 2 + 1
            data = {"actual_start": row["begin_at"], "actual_end": row["end_at"],
                    "winner_id": historic["home_id" if row["won"] else "away_id"],
                    "score_a": needed if row["won"] else 0, "score_b": 0 if row["won"] else needed}
            records.append((source("series", historic, data), end + timedelta(minutes=1)))
            records.append((source("observed_lineup", historic, lineup_data(historic)), end + timedelta(minutes=2)))
    records.append((source("lineup", event, lineup_data(event, status="confirmed", missing_player=missing_player)), decision - timedelta(minutes=10)))
    observations = ingest(path, event, records)
    result = esports_match_winner_candidate(match, now=decision, base_request={"event": event, "observations": observations})
    base = result["base"]
    assert base["reference_weights"]["kind"] == "esports-observed-series-reference-v1"
    features = esports_features(event, observations, base, cutoff=decision)
    return {"path": path, "event": event, "match": match, "records": records, "observations": observations,
            "base": base, "features": features, "candidate": result["candidate"]}


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    return make_case(tmp_path_factory.mktemp("c4-native") / "context.sqlite")


def effect(case, *, names=None, coefficient=0.7):
    from context_models.esports import FAMILY, FEATURE_VERSION, MODEL_VARIANT
    names = names or ["participation_delta/1/2026/pandascore:esports:player:701"]
    event = case["event"]
    return {"schema": 1, "sport": "esports", "family": FAMILY, "feature_version": FEATURE_VERSION, "feature_names": names,
            "heads": {"winner": {"link": "logit", "scale": [1.] * len(names), "coef": [coefficient] * len(names), "alpha": .1, "n_rows": 20}},
            "preprocessing_artifacts": {}, "joint_calibration": {"kind": "identity"}, "training_end": (NOW - timedelta(days=1)).isoformat().replace("+00:00", ".000000Z"),
            "training_refs_hash": digest({"synthetic": "mechanism-only"}),
            "population": {"sport": "esports", "competitions": [event["competition"]], "formats": [event["format"]],
                           "tours": [None], "surfaces": [None], "indoor": [None]},
            "coverage": deepcopy(case["features"]["coverage"]), "model_variant": MODEL_VARIANT}


def test_frozen_full_legacy_and_cricket_parity():
    from multi_sport_recommendations import esports_match_winner_candidate, build_candidate
    import sports_prematch
    assert digest(asdict(esports_match_winner_candidate(legacy_match(), now=NOW))) == "7e61b58dab419b8f6dd66ec704ff6aca0a45aaf7567d514ae88b3d10832b947a"
    assert digest(asdict(build_candidate("Cricket", {"id": "c1", "team1": "A", "team2": "B"}))) == "4650ff4258dd94643ef03835540e406dc3153562444c5ee7fc822e0900fa2937"
    helpers = runpy.run_path(str(Path(__file__).with_name("test_sports_prematch.py")))
    cricket = sports_prematch.predict_prematch("cricket", helpers["event"]("cricket"), helpers["history"]("cricket"), helpers["NOW"])
    assert digest(cricket.to_dict()) == "f4e1dd2a3d5ed29c2c327fa5e782fabee3ca2afcd1df0d7c6a23fa99f069175f"


def test_native_sqlite_roster_features_reference_and_real_comparison(case):
    from context_models.esports import apply_esports_effect
    features, base = case["features"], case["base"]
    assert features["values"]["participation_delta/1/2026/pandascore:esports:player:701"] == -1
    assert features["values"]["participation_delta/1/2026/pandascore:esports:player:706"] == 1
    comparison = apply_esports_effect(base, features, effect(case), event=case["event"])
    assert comparison["params"]["p_a"] < base["params"]["p_a"]
    assert set(comparison["markets"]) == {"series_winner_a", "series_winner_b"}
    assert comparison["markets"]["series_winner_b"] == 1 - comparison["params"]["p_a"]
    assert features["values"]["history_complete_home"] == 0
    assert features["values"]["active_map_minutes_home"] is None
    assert features["values"]["medical_fatigue_home"] is None
    assert features["values"]["patch_reported"] is None


def test_neutral_effect_preserves_exact_original_parameter_and_market_bytes(case):
    from context_models.esports import apply_esports_effect
    from model_artifacts import canonical_bytes
    comparison = apply_esports_effect(case["base"], case["features"], effect(case, coefficient=0), event=case["event"])
    for key in ("params", "markets"):
        assert canonical_bytes(comparison[key]) == canonical_bytes(case["base"][key])


def test_source_sqlite_through_shared_b3_once_stays_experimental_without_approval(case, tmp_path):
    from context_models.esports import esports_context_result
    from context_snapshots import compute_once, snapshot_key
    from model_artifacts import put_artifact, load_artifact
    artifact = effect(case)
    artifact_path = tmp_path / "models.sqlite"
    effect_hash = put_artifact(artifact_path, kind="context-effect-v1", payload=artifact, created_at=NOW)
    envelope = load_artifact(artifact_path, effect_hash)
    refs = tuple(sorted({ref for values in case["features"]["refs"].values() for ref in values}))
    key = snapshot_key(case["event"], base_hash=digest(case["base"]), context_refs=refs, feature_version=case["features"]["version"],
                       feature_hash=digest(case["features"]), effect_hash=effect_hash, decision_at=NOW, approval_hash=None)
    called = []
    def calculate():
        called.append(True)
        return esports_context_result(case["base"], case["features"], envelope, event=case["event"], effect_hash=effect_hash)
    first = compute_once(artifact_path, key, calculate)
    second = compute_once(artifact_path, key, calculate)
    assert first == second and len(called) == 1
    assert first["role"] == "experimental"
    assert first["used_params"] == case["base"]["params"]
    assert first["approval_hash"] is None and first["certified_markets"] == []


@pytest.mark.parametrize("best_of", [1, 3, 5])
def test_each_explicit_native_series_format_exports_exact_original_bytes(best_of, tmp_path):
    from context_models.esports import apply_esports_effect, _replay
    data = make_case(tmp_path / "format.sqlite", best_of=best_of)
    original = data["base"]
    replayed, _, _ = _replay(original["reference_weights"]["windows"], data["event"])
    assert original["params"]["p_a"].hex() == replayed.hex()
    assert original["reference_weights"]["scope"]["rules"]["best_of"] == best_of
    assert apply_esports_effect(original, data["features"], effect(data, coefficient=0), event=data["event"])["markets"] == original["markets"]


@pytest.mark.parametrize("changes", [{"team1_history": []}, {"team1_score": 2, "status": "running"}])
def test_optional_export_has_an_explicit_absent_base_when_original_model_is_unavailable(changes):
    from multi_sport_recommendations import esports_match_winner_candidate
    match = {**legacy_match(), **changes}
    original = esports_match_winner_candidate(match, now=NOW)
    result = esports_match_winner_candidate(match, now=NOW, base_request={"event": native_event(), "observations": ()})
    assert result == {"candidate": original, "base": None}


def test_unsupported_context_bo7_does_not_change_the_legacy_candidate_path():
    from multi_sport_recommendations import esports_match_winner_candidate
    match = {**legacy_match(), "series_type": 7}
    original = esports_match_winner_candidate(match, now=NOW)
    assert original.model_probability is not None
    with pytest.raises(ContextContractError):
        esports_match_winner_candidate(match, now=NOW, base_request={"event": native_event(best_of=7), "observations": ()})
