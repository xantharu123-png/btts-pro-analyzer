"""C2 CPU mechanics on synthetic source-resolved data; no empirical approval."""
from copy import deepcopy
import ast
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from context_models.contracts import ContextContractError, canonical_bytes, canonical_timestamp, digest
from context_models.offset import fit_offset
from test_sports_prematch import NOW, event as old_event, history as old_history


def implementation():
    from context_models import team_sports
    return team_sports


def event():
    return dict(event_key="espn:basketball:401999999", sport="basketball", competition="nba",
        format="nba_reg48_including_ot", home_id="espn:basketball:team:1", away_id="espn:basketball:team:8",
        scheduled_start=canonical_timestamp(NOW + timedelta(hours=6)), schedule_revision="schedule-1", status="scheduled")


def rules():
    return dict(regulation_minutes=48, regulation_periods=4, overtime_period_minutes=5)


def inputs():
    target = old_event(provider_event_id="401999999")
    rows = [{**row, "provider_event_id": str(401800000 + i), "season": "2026", "context_rules": rules()}
            for i, row in enumerate(old_history())]
    return target, rows


def base():
    import sports_prematch
    target, rows = inputs()
    return sports_prematch.basketball_base_distribution(target, rows, NOW,
        context_event=event(), scope={"season": "2026", "rules": rules()})


@pytest.mark.parametrize("mean", [-12., -3., 0., 3., 12.])
def test_shared_margin_law_and_side_complement(mean):
    result = implementation().margin_distribution(mean, 12.)
    reverse = implementation().margin_distribution(-mean, 12.)
    assert result["home_win"] + result["away_win"] == 1.
    assert result["home_win"] == pytest.approx(reverse["away_win"], abs=1e-15)
    assert result["expected_margin"] == mean and result["residual_scale"] == 12.


@pytest.mark.parametrize("mean,scale", [(True, 12), ("3", 12), (3, False), (float("inf"), 12),
    (3, float("nan")), (3, 0), (3, -1)])
def test_margin_parameters_are_strict(mean, scale):
    with pytest.raises(ContextContractError):
        implementation().margin_distribution(mean, scale)


def test_original_unrounded_ridge_provenance_is_signed_and_replayable():
    from context_models.contracts import validate_base_distribution
    original = base()
    assert original["family"] == "basketball:margin:including_ot"
    assert original["params"]["expected_margin"] == 20.89527458469624
    assert original["params"]["residual_scale"] == 3.7478553605050626
    assert min(original["reference_weights"]["influences"]) < 0
    assert len(original["history_refs"]) == 84
    assert validate_base_distribution(original) == original
    changed = deepcopy(original)
    changed["reference_weights"]["influences"][0] += .01
    with pytest.raises(ContextContractError):
        validate_base_distribution(changed)


def test_missing_season_rules_keeps_valid_original_base_without_roster_claim():
    import sports_prematch
    target, rows = inputs()
    original = sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=event())
    assert original["reference_weights"]["kind"] == "unavailable"
    assert original["params"] == base()["params"]
    assert original["markets"] == base()["markets"]


def test_frozen_default_cricket_matches_before_change_on_same_cpu():
    import sports_prematch
    path = Path(__file__).parent / "fixtures/context/basketball/sports_prematch_legacy_0d000f6.py"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "b4e44d03d09a6c8f22ce52568ea36f9af1c7e563d094af98c135703a0a204677"
    # The verified original Git blob be3d56fc... is captured before any product
    # edit; compare both numerical backends on this CPU, without tolerances.
    spec = importlib.util.spec_from_file_location("c2_legacy_sports_prematch", path)
    legacy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = legacy
    spec.loader.exec_module(legacy)
    cases = [(old_event("cricket"), old_history("cricket")),
        (old_event("cricket", format="odi"), [{**row, "format": "odi"} for row in old_history("cricket")]),
        (old_event("cricket"), old_history("cricket", newly_imported=True)),
        (old_event("cricket"), []), (old_event("cricket", format="test"), old_history("cricket"))]
    for target, rows in cases:
        frozen = deepcopy((target, rows))
        a = legacy.predict_prematch("cricket", target, rows, NOW).to_dict()
        b = sports_prematch.predict_prematch("cricket", target, rows, NOW).to_dict()
        assert canonical_bytes(a) == canonical_bytes(b)
        assert (target, rows) == frozen
    # The additive same-call collector intentionally changes this source file.
    # Keep the old functions/math frozen, not an obsolete whole-file prefix.
    old_functions = {n.name: n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}
    new_functions = {n.name: n for n in ast.parse(Path(sports_prematch.__file__).read_bytes()).body
                     if isinstance(n, ast.FunctionDef)}
    for name, before in old_functions.items():
        after = deepcopy(new_functions[name])
        if name == "predict_prematch":
            assert len(after.args.kwonlyargs) == 1
            assert after.args.kwonlyargs[0].arg == "original_capture"
            assert ast.dump(after.args.kw_defaults[0]) == "Constant(value=None)"
            after.args.kwonlyargs = []
            after.args.kw_defaults = []
            conditional = ast.dump(ast.parse("original_capture is not None", mode="eval").body)
            guards = [n for n in after.body if isinstance(n, ast.If) and ast.dump(n.test) == conditional]
            assert len(guards) == 2 and all(not n.orelse for n in guards)
            after.body = [n for n in after.body if n not in guards]
            assignment, returned = after.body[-2:]
            assert isinstance(assignment, ast.Assign) and len(assignment.targets) == 1
            assert isinstance(assignment.targets[0], ast.Name) and assignment.targets[0].id == "result"
            assert isinstance(returned, ast.Return) and isinstance(returned.value, ast.Name)
            assert returned.value.id == "result"
            after.body[-2:] = [ast.Return(value=assignment.value)]
        assert ast.dump(before) == ast.dump(after), name


def rotation_team(team_id, *, load=False):
    start = int(team_id.rsplit(":", 1)[1]) * 100
    return {"complete": True, "collection": "full_rotation", "players": [
        {"player_id": f"espn:basketball:player:{start+i}", "regulation_minutes": 24.,
         **({"inclusive_minutes": 26.5} if load else {"availability": "available"})} for i in range(1, 11)]}


def transport(*, kind="rotation", ev=None):
    ev = deepcopy(ev or event())
    appearance = kind == "appearance"
    if appearance:
        ev.update(event_key="espn:basketball:401800500", status="completed",
            scheduled_start=canonical_timestamp(NOW - timedelta(hours=32)))
    teams = {ev[side]: rotation_team(ev[side], load=appearance) for side in ("home_id", "away_id")}
    if kind == "availability":
        for team in teams.values():
            team["collection"] = "full_roster"
            for player in team["players"]:
                player.pop("regulation_minutes")
    data = {"teams": teams}
    if appearance:
        data.update(actual_start=canonical_timestamp(NOW - timedelta(hours=32)),
            actual_end=canonical_timestamp(NOW - timedelta(hours=30)),
            result_observed_at=canonical_timestamp(NOW - timedelta(hours=29)), overtime_periods=1)
    elif kind == "rotation":
        data["status"] = "expected"
    return {"schema": 1, "source_schema": "basketball-internal-context-v1", "kind": kind,
        "event": ev, "season": "2026", "rules": rules(),
        "valid_from": canonical_timestamp(NOW - timedelta(hours=1)), "valid_until": None, "data": data}


def normalized(raw, observed=NOW):
    from context_sources.basketball import normalize_basketball_context
    return normalize_basketball_context(raw["event"], (raw,), observed_at=observed)


@pytest.mark.parametrize("kind", ["rotation", "appearance", "availability"])
def test_whole_native_event_transport_retains_explicit_scope(kind):
    raw = transport(kind=kind)
    original = deepcopy(raw)
    records = normalized(raw)
    assert len(records) == 1
    assert records[0]["subject_id"] == raw["event"]["event_key"] + ":participants:" + digest(
        {key: raw["event"][key] for key in ("home_id", "away_id")})
    assert records[0]["payload"]["event"] == raw["event"]
    assert records[0]["payload"]["season"] == "2026"
    assert raw == original


@pytest.mark.parametrize("mutation", ["no-season", "unknown-rules", "no-team", "duplicate-player", "missing-native",
    "minute-string", "minute-bool", "negative", "too-many", "five-starters", "not-full", "wrong-total",
    "questionable-half", "out-nonzero", "nonfinite", "quote", "wrong-format", "wrong-source"])
def test_internal_rotation_rejects_guesses_and_partial_identity(mutation):
    raw = transport()
    home = raw["data"]["teams"][event()["home_id"]]
    if mutation == "no-season": raw["season"] = None
    elif mutation == "unknown-rules": raw["rules"]["overtime_period_minutes"] = None
    elif mutation == "no-team": raw["data"]["teams"].pop(event()["away_id"])
    elif mutation == "duplicate-player": home["players"][1]["player_id"] = home["players"][0]["player_id"]
    elif mutation == "missing-native": home["players"][0]["player_id"] = "unknown"
    elif mutation == "minute-string": home["players"][0]["regulation_minutes"] = "24"
    elif mutation == "minute-bool": home["players"][0]["regulation_minutes"] = True
    elif mutation == "negative": home["players"][0]["regulation_minutes"] = -1
    elif mutation == "too-many": home["players"][0]["regulation_minutes"] = 49
    elif mutation == "five-starters": home["collection"] = "starting_five"
    elif mutation == "not-full": home["collection"] = "partial"
    elif mutation == "wrong-total": home["players"][0]["regulation_minutes"] = 23
    elif mutation == "questionable-half": home["players"][0]["availability"] = "questionable"
    elif mutation == "out-nonzero": home["players"][0]["availability"] = "out"
    elif mutation == "nonfinite": home["players"][0]["regulation_minutes"] = float("nan")
    elif mutation == "quote": raw["data"]["odds"] = 2.
    elif mutation == "wrong-format": raw["event"]["format"] = "including_ot"
    elif mutation == "wrong-source": raw["event"]["event_key"] = "other:basketball:1"
    with pytest.raises(ContextContractError): normalized(raw)


@pytest.mark.parametrize("mutation", ["guessed-total", "before-start", "after-receipt", "future-receipt", "bool-ot", "fraction-ot", "negative-ot", "bad-inclusive", "native-other-team"])
def test_appearance_cannot_reconstruct_overnight_or_overtime_load(mutation):
    raw = transport(kind="appearance")
    data = raw["data"]
    home = data["teams"][event()["home_id"]]
    if mutation == "guessed-total": home["players"][0]["inclusive_minutes"] = 25
    elif mutation == "before-start": data["actual_end"] = canonical_timestamp(NOW - timedelta(hours=33))
    elif mutation == "after-receipt": data["actual_end"] = canonical_timestamp(NOW - timedelta(hours=28))
    elif mutation == "future-receipt": data["result_observed_at"] = canonical_timestamp(NOW + timedelta(seconds=1))
    elif mutation == "bool-ot": data["overtime_periods"] = True
    elif mutation == "fraction-ot": data["overtime_periods"] = .5
    elif mutation == "negative-ot": data["overtime_periods"] = -1
    elif mutation == "bad-inclusive": home["players"][0]["inclusive_minutes"] = 23
    elif mutation == "native-other-team": data["teams"][event()["away_id"]]["players"][0]["player_id"] = home["players"][0]["player_id"]
    with pytest.raises(ContextContractError): normalized(raw)


def test_unknown_minutes_and_end_survive_as_unknown_not_zero():
    raw = transport(kind="appearance")
    raw["data"]["actual_end"] = raw["data"]["actual_start"] = raw["data"]["overtime_periods"] = None
    team = raw["data"]["teams"][event()["home_id"]]
    team["players"][0]["inclusive_minutes"] = team["players"][0]["regulation_minutes"] = None
    result = normalized(raw)[0]
    assert result["payload"]["data"]["teams"][event()["home_id"]]["players"][0]["inclusive_minutes"] is None
    assert result["payload"]["data"]["actual_end"] is None
    assert result["complete"] is False


def receipt(raw, observed=NOW, *, evidence="prospective"):
    content = normalized(raw, observed)[0]
    content_hash, stamp = digest(content), canonical_timestamp(observed)
    return {**content, "content_digest": content_hash, "observed_at": stamp,
        "digest": digest({"content_digest": content_hash, "observed_at": stamp}),
        "effective_at": stamp, "evidence_class": evidence, "publication_resolution": None}


@lru_cache()
def _packet():
    original = base()
    raw_rows = [transport()]
    for ref in original["reference_weights"]["rows"]:
        ev = {**event(), "event_key": ref["event_key"], "home_id": ref["home_id"], "away_id": ref["away_id"],
            "scheduled_start": ref["start"], "schedule_revision": "history-1", "status": "completed"}
        raw = transport(kind="appearance")
        raw["event"] = ev
        raw["season"], raw["rules"] = ref["season"], deepcopy(ref["rules"])
        raw["data"].update(actual_start=ref["start"], actual_end=canonical_timestamp(datetime.fromisoformat(ref["start"]) + timedelta(hours=2)),
            result_observed_at=ref["observed"], teams={ev[side]: rotation_team(ev[side], load=True) for side in ("home_id", "away_id")})
        raw_rows.append(raw)
    return original, raw_rows


def packet():
    original, raws = deepcopy(_packet())
    return original, raws, tuple(receipt(row, NOW - timedelta(minutes=30)) for row in raws)


def feature_packet(original=None, rows=None, ev=None, cutoff=NOW):
    if original is None or rows is None:
        initial, _, observed = packet()
        original = initial if original is None else original
        rows = observed if rows is None else rows
    return implementation().team_sport_features("basketball", ev or event(), rows, original, cutoff=cutoff)


def artifact(original, feats, *, name="rotation_delta/espn:basketball:player:101", beta=-2., ev=None):
    from context_models.contracts import normalize_population
    ev = ev or event()
    x = np.array([[-1.], [0.], [1.]] * 20)
    offset = np.full(60, 3.)
    head = fit_offset(x, offset, offset + beta * x[:, 0], link="identity", alpha=.1)
    return {"schema": 1, "sport": "basketball", "family": implementation().FAMILY,
        "feature_version": implementation().FEATURE_VERSION, "feature_names": [name], "heads": {"margin": head},
        "preprocessing_artifacts": {}, "joint_calibration": {"kind": "identity"},
        "training_end": canonical_timestamp(NOW - timedelta(days=1)), "training_refs_hash": "a" * 64,
        "population": normalize_population({"sport": "basketball", "competitions": [ev["competition"]], "formats": [ev["format"]],
            "tours": [None], "surfaces": [None], "indoor": [None]}), "coverage": deepcopy(feats["coverage"]),
        "model_variant": implementation().MODEL_VARIANT}


def test_measured_rotation_uses_signed_original_prediction_influences():
    original, _, observations = packet()
    feats = feature_packet(original, observations)
    player = "espn:basketball:player:101"
    refs = original["reference_weights"]
    expected = sum(weight * .5 * (int(row["home_id"] == event()["home_id"]) - int(row["away_id"] == event()["home_id"]))
        for weight, row in zip(refs["influences"], refs["rows"]))
    assert feats["values"]["rotation_reference/" + player] == pytest.approx(expected, abs=1e-15)
    assert feats["values"]["rotation_delta/" + player] == .5 - feats["values"]["rotation_reference/" + player]
    assert feats["coverage"]["case"].startswith("rotation-expected.complete-reference.")
    assert len(feats["refs"]["rotation_delta/" + player]) == 85


def test_actual_fitted_margin_effect_changes_mean_not_scale_and_never_in_place():
    original, _, observed = packet()
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats)
    old = deepcopy((original, feats, fitted))
    comparison = implementation().apply_team_sport_effect("basketball", original, feats, fitted, event=event())
    assert comparison["params"]["expected_margin"] < original["params"]["expected_margin"]
    assert comparison["params"]["residual_scale"] == original["params"]["residual_scale"]
    assert comparison["markets"]["home_win"] < original["markets"]["home_win"]
    assert comparison["markets"]["home_win"] + comparison["markets"]["away_win"] == 1.
    assert (original, feats, fitted) == old


@pytest.mark.parametrize("mutation", ["missing-cell", "partial-roster", "missing-event", "later-import", "stale-rotation", "wrong-season", "wrong-rules", "wrong-history-start", "empty-current"])
def test_incomplete_provenance_does_not_turn_into_a_player_penalty(mutation):
    original, raws, observed = packet()
    if mutation == "missing-cell": raws[1]["data"]["teams"][raws[1]["event"]["home_id"]]["players"][0]["regulation_minutes"] = None
    elif mutation == "partial-roster": raws[1]["data"]["teams"][raws[1]["event"]["home_id"]].update(complete=False, collection="partial")
    elif mutation == "missing-event": raws.pop(1)
    elif mutation == "wrong-season": raws[1]["season"] = "2025"
    elif mutation == "wrong-rules": raws[1]["rules"]["overtime_period_minutes"] = 6
    elif mutation == "wrong-history-start": raws[1]["event"]["scheduled_start"] = canonical_timestamp(NOW - timedelta(days=400))
    elif mutation == "empty-current":
        for team in raws[0]["data"]["teams"].values(): team.update(complete=False, collection="partial", players=[])
    if mutation == "wrong-rules":
        for team in raws[1]["data"]["teams"].values():
            for player in team["players"]: player["inclusive_minutes"] = 27.
    if mutation == "stale-rotation":
        raws[0]["valid_from"] = canonical_timestamp(NOW - timedelta(days=2))
    observed = tuple(receipt(raw, NOW - timedelta(days=1) if mutation == "stale-rotation" and i == 0 else NOW - timedelta(minutes=30))
        for i, raw in enumerate(raws))
    if mutation == "later-import": observed = (observed[0], receipt(raws[1], NOW + timedelta(hours=1), evidence="retrospective"), *observed[2:])
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats)
    with pytest.raises(ContextContractError):
        implementation().apply_team_sport_effect("basketball", original, feats, fitted, event=event())
    assert original["params"] == base()["params"]


@pytest.mark.parametrize("field", ["scheduled_start", "schedule_revision", "home_id", "away_id", "competition", "format", "status"])
def test_old_features_cannot_cross_an_event_revision(field):
    original, _, observed = packet()
    feats = feature_packet(original, observed)
    ev = event()
    ev[field] = {"scheduled_start": canonical_timestamp(NOW + timedelta(hours=8)), "schedule_revision": "s2",
        "home_id": "espn:basketball:team:2", "away_id": "espn:basketball:team:3", "competition": "other",
        "format": "regulation", "status": "cancelled"}[field]
    with pytest.raises(ContextContractError):
        implementation().apply_team_sport_effect("basketball", original, feats, artifact(original, feats), event=ev)


def test_observed_inclusive_workload_and_receipt_rest_are_not_regulation_rotation():
    original, _, observed = packet()
    recent = transport(kind="appearance")
    row = receipt(recent, NOW - timedelta(minutes=20))
    feats = feature_packet(original, (*observed, row))
    assert feats["values"]["observed_inclusive_minutes_3d_home"] == 265.
    assert feats["values"]["observed_inclusive_minutes_complete_3d_home"] == 1
    assert feats["values"]["observed_recovery_exact_hours_home"] == 36.
    assert feats["values"]["history_complete_3d_home"] == 0
    recent["data"]["actual_end"] = None
    feats = feature_packet(original, (*observed, receipt(recent)))
    assert feats["values"]["observed_recovery_exact_hours_home"] is None
    assert feats["values"]["observed_recovery_minimum_hours_home"] == 35.
    assert feats["values"]["observed_inclusive_minutes_complete_3d_home"] == 0


@pytest.mark.parametrize("mutation", ["mean", "scale", "market", "model-hash", "event", "history", "source-influence", "feature", "coefficient", "label-only", "original-scale", "nested-comparison"])
def test_comparison_requires_owning_full_replay_not_a_free_label(mutation):
    from context_models.contracts import validate_base_distribution
    original, _, observed = packet()
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats)
    comparison = implementation().apply_team_sport_effect("basketball", original, feats, fitted, event=event())
    changed = deepcopy(comparison)
    ref = changed["reference_weights"]
    if mutation == "mean": changed["params"]["expected_margin"] += 1
    elif mutation == "scale": changed["params"]["residual_scale"] += 1
    elif mutation == "market": changed["markets"]["home_win"] -= .01; changed["markets"]["away_win"] += .01
    elif mutation == "model-hash": changed["model_hash"] = "f" * 64
    elif mutation == "event": ref["event"]["schedule_revision"] = "s2"
    elif mutation == "history": changed["history_refs"].pop()
    elif mutation == "source-influence": ref["original"]["reference_weights"]["influences"][0] += .1
    elif mutation == "feature": ref["features"]["values"][fitted["feature_names"][0]] += 1
    elif mutation == "coefficient": ref["effect"]["heads"]["margin"]["coef"][0] += 1
    elif mutation == "label-only": changed["reference_weights"] = deepcopy(original["reference_weights"])
    elif mutation == "original-scale": ref["original"]["params"]["residual_scale"] += 1
    elif mutation == "nested-comparison": ref["original"] = deepcopy(comparison)
    with pytest.raises(ContextContractError): validate_base_distribution(changed)


def test_zero_fit_preserves_allowed_original_market_last_bit_exactly():
    original, _, observed = packet()
    original["markets"]["home_win"] = float(np.nextafter(original["markets"]["home_win"], 1.))
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats, beta=0.)
    assert fitted["heads"]["margin"]["coef"] == [0.]
    comparison = implementation().apply_team_sport_effect("basketball", original, feats, fitted, event=event())
    assert canonical_bytes(comparison["params"]) == canonical_bytes(original["params"])
    assert canonical_bytes(comparison["markets"]) == canonical_bytes(original["markets"])
    assert comparison["markets"] is not original["markets"]


def test_longstanding_explicit_absence_is_not_deducted_twice():
    original, raws, _ = packet()
    for raw in raws:
        team = raw["data"]["teams"].get(event()["home_id"])
        if team:
            team["players"][0]["regulation_minutes"] = 0.
            team["players"][1]["regulation_minutes"] = 48.
            if raw["kind"] == "appearance":
                team["players"][0]["inclusive_minutes"] = 0.
                team["players"][1]["inclusive_minutes"] = 53.
            else: team["players"][0]["availability"] = "out"
    observed = tuple(receipt(raw) for raw in raws)
    feats = feature_packet(original, observed)
    name = "rotation_delta/espn:basketball:player:101"
    assert feats["values"][name] == 0
    comparison = implementation().apply_team_sport_effect("basketball", original, feats, artifact(original, feats), event=event())
    assert comparison["params"] == original["params"]
    assert comparison["markets"] == original["markets"]


def test_removed_current_member_is_only_expected_zero_not_injury_or_health():
    original, raws, _ = packet()
    home = raws[0]["data"]["teams"][event()["home_id"]]
    home["players"].pop(0)
    home["players"][0]["regulation_minutes"] = 48.
    feats = feature_packet(original, tuple(receipt(raw) for raw in raws))
    assert feats["values"]["rotation_current/espn:basketball:player:101"] == 0
    assert feats["values"]["reported_out_count_home"] is None
    assert feats["values"]["medical_fatigue_home"] is None
    expected_case = feats["coverage"]
    raws[0]["data"]["status"] = "confirmed"
    confirmed = feature_packet(original, tuple(receipt(raw) for raw in raws))
    assert confirmed["coverage"] != expected_case
    with pytest.raises(ContextContractError):
        implementation().apply_team_sport_effect("basketball", original, confirmed, artifact(original, feats), event=event())


@pytest.mark.parametrize("mutation", ["new-player", "partial", "new-participants", "late-expired"])
def test_latest_joint_roster_revision_never_borrows_old_members(mutation):
    original, raws, observed = packet()
    new = deepcopy(raws[1])
    team = new["data"]["teams"][new["event"]["home_id"]]
    if mutation == "new-player": team["players"][0]["player_id"] = "espn:basketball:player:999999"
    elif mutation == "partial": team.update(complete=False, collection="partial", players=team["players"][:4])
    elif mutation == "new-participants":
        old = new["event"]["home_id"]
        new["event"]["home_id"] = "espn:basketball:team:99"
        new["data"]["teams"][new["event"]["home_id"]] = new["data"]["teams"].pop(old)
    elif mutation == "late-expired": new["valid_until"] = canonical_timestamp(NOW - timedelta(minutes=1))
    after = feature_packet(original, (*observed, receipt(new)))
    if mutation == "new-player":
        assert "rotation_delta/espn:basketball:player:999999" in after["values"]
        assert after["refs"]["rotation_reference/espn:basketball:player:999999"] != []
    else:
        assert after["values"]["rotation_complete"] == 0
    before = feature_packet(original, observed)
    assert before["values"]["rotation_complete"] == 1


def test_same_instant_conflict_blocks_both_sides_and_genuine_duplicate_counts_once():
    original, raws, observed = packet()
    recent = transport(kind="appearance")
    a = receipt(recent)
    duplicate = feature_packet(original, (*observed, a, a))
    assert duplicate["values"]["observed_inclusive_minutes_3d_home"] == 265.
    recent["data"]["teams"][event()["home_id"]]["players"][0]["inclusive_minutes"] = None
    conflict = feature_packet(original, (*observed, a, receipt(recent)))
    assert conflict["states"]["observed_inclusive_minutes_3d_home"] == "conflicting"
    assert conflict["states"]["observed_inclusive_minutes_3d_away"] == "conflicting"


@pytest.mark.parametrize("days", [1, 3, 7])
@pytest.mark.parametrize("side", ["home", "away"])
def test_unknown_end_receipt_bound_is_strict_at_each_window(days, side):
    original, _, observed = packet()
    recent = transport(kind="appearance")
    recent["data"]["actual_end"] = canonical_timestamp(NOW - timedelta(hours=12))
    recent["data"]["result_observed_at"] = canonical_timestamp(NOW - timedelta(hours=11))
    recent["data"]["actual_start"] = canonical_timestamp(NOW - timedelta(hours=14))
    bounded = deepcopy(recent)
    bounded["event"]["event_key"] = "espn:basketball:401800501"
    bounded["data"]["actual_start"] = bounded["data"]["actual_end"] = None
    bounded["data"]["result_observed_at"] = canonical_timestamp(NOW - timedelta(days=days))
    name = f"observed_inclusive_minutes_complete_{days}d_{side}"
    at_boundary = feature_packet(original, (*observed, receipt(recent), receipt(bounded)))
    assert at_boundary["values"][name] == 0
    bounded["data"]["result_observed_at"] = canonical_timestamp(NOW - timedelta(days=days, microseconds=1))
    excluded = feature_packet(original, (*observed, receipt(recent), receipt(bounded)))
    assert excluded["values"][name] == 1
    assert excluded["values"][f"observed_recovery_exact_hours_{side}"] == 18.
    assert receipt(bounded)["digest"] in excluded["refs"][name]


def test_real_b1_sqlite_round_trip_and_cutoff_replay(tmp_path):
    from context_observations import append_observation, observations_as_of
    original, raws, synthetic = packet()
    path = tmp_path / "basketball-context.db"
    for raw in raws:
        record = normalized(raw, NOW - timedelta(minutes=30))[0]
        append_observation(path, record, observed_at=NOW - timedelta(minutes=30))
    retrieved = tuple(row for raw in raws for row in observations_as_of(path, raw["event"]["event_key"], cutoff=NOW,
        schedule_revision=raw["event"]["schedule_revision"]))
    assert feature_packet(original, retrieved) == feature_packet(original, synthetic)
    changed = deepcopy(raws[0])
    changed["data"]["teams"][event()["home_id"]]["players"][0]["regulation_minutes"] = None
    later = NOW + timedelta(minutes=5)
    append_observation(path, normalized(changed, later)[0], observed_at=later)
    earlier = observations_as_of(path, event()["event_key"], cutoff=NOW, schedule_revision=event()["schedule_revision"])
    assert earlier == (synthetic[0],)


@pytest.mark.parametrize("unknown", [{"season": None, "rules": rules()}, {"season": "2026", "rules": None},
    {"season": "2026", "rules": {"regulation_minutes": 48, "regulation_periods": 4, "overtime_period_minutes": None}}])
def test_unknown_current_scope_preserves_original_forecast(unknown):
    import sports_prematch
    target, rows = inputs()
    result = sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=event(), scope=unknown)
    assert result["reference_weights"]["kind"] == "unavailable"
    assert result["params"] == base()["params"]


@pytest.mark.parametrize("mutation", ["team-list-type", "unhashable-team", "duplicate-event", "target-event", "missing-history", "unknown-season", "missing-rules",
    "reverse-input-order", "renormalized-influences", "rounded-mean", "coefficient", "penalty-bool", "penalty", "row-score", "wrong-roster-join", "extra-market"])
def test_base_recipe_cannot_be_replaced_by_an_unproven_mean(mutation):
    from context_models.contracts import validate_base_distribution
    original = base()
    recipe = original["reference_weights"]
    if mutation == "team-list-type": recipe["teams"] = {}
    elif mutation == "unhashable-team": recipe["teams"][0] = []
    elif mutation == "duplicate-event": recipe["rows"][1] = deepcopy(recipe["rows"][0])
    elif mutation == "target-event": recipe["rows"][0]["event_key"] = event()["event_key"]
    elif mutation == "missing-history": original["history_refs"].pop()
    elif mutation == "unknown-season": recipe["rows"][0]["season"] = None
    elif mutation == "missing-rules": recipe["rows"][0]["rules"] = None
    elif mutation == "reverse-input-order": recipe["rows"].reverse()
    elif mutation == "renormalized-influences": recipe["influences"] = [abs(value) / sum(abs(v) for v in recipe["influences"]) for value in recipe["influences"]]
    elif mutation == "rounded-mean": original["params"]["expected_margin"] = round(original["params"]["expected_margin"], 2)
    elif mutation == "coefficient": recipe["coefficients"][0] += .001
    elif mutation == "penalty-bool": recipe["penalty"][-1] = True
    elif mutation == "penalty": recipe["penalty"][0] = 0.
    elif mutation == "row-score": recipe["rows"][0]["home_score"] += 1
    elif mutation == "wrong-roster-join": original["history_refs"][0]["roster_join"] = "verified_native"
    elif mutation == "extra-market": original["markets"]["total_over_220_5"] = .5
    with pytest.raises(ContextContractError): validate_base_distribution(original)


@pytest.mark.parametrize("mutation", ["boolean", "string", "nan", "inf", "inexact-int", "missing-ref", "audit-ref-in-delta", "missing-state", "different-base", "different-cutoff", "different-preprocessing", "unreviewed-input", "future-fit", "different-population", "different-family", "overflow"])
def test_offset_does_not_accept_noncausal_or_unmeasured_columns(mutation):
    original, _, observed = packet()
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats)
    name = fitted["feature_names"][0]
    if mutation == "boolean": feats["values"][name] = True
    elif mutation == "string": feats["values"][name] = "0.5"
    elif mutation == "nan": feats["values"][name] = float("nan")
    elif mutation == "inf": feats["values"][name] = float("inf")
    elif mutation == "inexact-int": feats["values"][name] = 2**60 + 1
    elif mutation == "missing-ref": feats["refs"][name] = []
    elif mutation == "audit-ref-in-delta": feats["refs"][name] = sorted(feats["refs"][name] + ["f" * 64])
    elif mutation == "missing-state": feats["states"][name] = "missing"; feats["values"][name] = None
    elif mutation == "different-base": original["model_hash"] = "e" * 64
    elif mutation == "different-cutoff": feats["cutoff"] = canonical_timestamp(NOW - timedelta(seconds=1))
    elif mutation == "different-preprocessing": fitted["preprocessing_artifacts"] = {"participation": "f" * 64}
    elif mutation == "unreviewed-input": fitted["feature_names"] = ["reported_out_count_home"]
    elif mutation == "future-fit": fitted["training_end"] = canonical_timestamp(NOW + timedelta(seconds=1))
    elif mutation == "different-population": fitted["population"]["competitions"] = ["euroleague"]
    elif mutation == "different-family": fitted["family"] = "basketball:margin:regulation"
    elif mutation == "overflow": fitted["heads"]["margin"].update(coef=[1e308], scale=[1e-8])
    with pytest.raises(ContextContractError):
        implementation().apply_team_sport_effect("basketball", original, feats, fitted, event=event())


@pytest.mark.parametrize("season", ["2025", "2026"])
def test_new_unknown_minutes_never_reuse_old_complete_receipt(season):
    original, raws, observed = packet()
    later = deepcopy(raws[1])
    later["season"] = season
    later["data"]["teams"][later["event"]["home_id"]]["players"][0]["regulation_minutes"] = None
    feats = feature_packet(original, (*observed, receipt(later)))
    assert feats["values"]["rotation_complete"] == 0


def test_unknown_overtime_count_does_not_certify_complete_inclusive_load():
    original, _, observed = packet()
    raw = transport(kind="appearance")
    raw["data"]["overtime_periods"] = None
    feats = feature_packet(original, (*observed, receipt(raw)))
    assert feats["values"]["observed_inclusive_minutes_complete_3d_home"] == 0
    assert feats["values"]["observed_inclusive_minutes_3d_home"] is None


def test_actual_regulation_and_inclusive_minutes_are_never_subtracted_or_assumed():
    raw = transport(kind="appearance")
    player = raw["data"]["teams"][event()["home_id"]]["players"][0]
    player["regulation_minutes"] = None
    record = normalized(raw)[0]
    assert record["payload"]["data"]["teams"][event()["home_id"]]["players"][0]["regulation_minutes"] is None
    assert player["inclusive_minutes"] == 26.5


@pytest.mark.parametrize("target,trials,valid", [(-3., None, True), (3, None, True), (3.5, None, False),
    (-3.5, None, False), (True, None, False), (float("inf"), None, False), (-3., 1, False)])
def test_b1_margin_training_shape_is_signed_integral_and_nonbinomial(target, trials, valid):
    from context_models.contracts import validate_training_row
    original, _, observed = packet()
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats)
    name = fitted["feature_names"][0]
    row = {"event_key": event()["event_key"], "decision_at": canonical_timestamp(NOW - timedelta(days=2)),
        "result_observed_at": canonical_timestamp(NOW - timedelta(days=1)), "block": "synthetic-block-1",
        "population": fitted["population"], "coverage": feats["coverage"], "feature_names": [name], "x": [.1],
        "offset": 2., "target": target, "trials": trials, "base_hash": digest(original), "feature_refs": {name: ["a" * 64]},
        "evidence_class": "prospective", "family": implementation().FAMILY, "head": "margin"}
    if valid: assert validate_training_row(row, effect_artifact=fitted) == row
    else:
        with pytest.raises(ContextContractError): validate_training_row(row, effect_artifact=fitted)


def select_result(original, feats, fitted, comparison, ev=None):
    from context_snapshots import select_context_result
    envelope = {"kind": "context-effect-v1", "payload": fitted}
    return select_context_result(original, comparison, event=ev or event(), features=feats,
        effect_artifact=envelope, effect_hash=digest(envelope), approval=None,
        factor_roles={name: "applied" if name in fitted["feature_names"] else "not_applied" for name in feats["values"]},
        factor_states=feats["states"], limitations=[])


@pytest.mark.parametrize("beta", [-2., 0.])
def test_b3_c2_comparison_without_approval_remains_experimental_with_original_used(beta):
    original, _, observed = packet()
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats, beta=beta)
    comparison = implementation().apply_team_sport_effect("basketball", original, feats, fitted, event=event())
    result = select_result(original, feats, fitted, comparison)
    assert result["role"] == "experimental"
    assert result["used_params"] == original["params"]
    assert result["used_markets"] == original["markets"]
    assert result["comparison_params"] == comparison["params"]
    assert result["approval_hash"] is None and result["certified_markets"] == []


@pytest.mark.parametrize("mutation", ["external-base", "external-event", "external-feature", "external-effect", "external-trainingrefs", "external-same-value-different-type"])
def test_b3_internally_valid_foreign_comparison_is_not_this_request(mutation):
    original, _, observed = packet()
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats)
    comparison = implementation().apply_team_sport_effect("basketball", original, feats, fitted, event=event())
    ev = event()
    if mutation == "external-base": original["model_hash"] = "f" * 64
    elif mutation == "external-event": ev["scheduled_start"] = canonical_timestamp(NOW + timedelta(hours=7))
    elif mutation == "external-feature": feats["values"]["reported_out_count_home"] = 1.; feats["states"]["reported_out_count_home"] = "available"; feats["refs"]["reported_out_count_home"] = ["f" * 64]
    elif mutation == "external-effect": fitted["heads"]["margin"]["coef"][0] *= 2
    elif mutation == "external-trainingrefs": fitted["training_refs_hash"] = "f" * 64
    elif mutation == "external-same-value-different-type": feats["values"]["rotation_complete"] = 1.
    with pytest.raises(ContextContractError): select_result(original, feats, fitted, comparison, ev)


def test_euroleague_native_case_and_40minute_scope_are_not_legacy_aliases():
    import sports_prematch
    target, rows = inputs()
    target.update(provider="euroleague", competition="Euroleague", provider_event_id="E2026_999", home_team_id="AAA", away_team_id="ZZZ")
    teams = {str(index): code for index, code in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "ZZZ"), 1)}
    rule40 = {**rules(), "regulation_minutes": 40}
    for i, row in enumerate(rows):
        row.update(provider="euroleague", competition="Euroleague", provider_event_id=f"E2026_{i+1}", context_rules=rule40,
            home_team_id=teams[row["home_team_id"]], away_team_id=teams[row["away_team_id"]])
    ev = {**event(), "event_key": "euroleague:basketball:E2026_999", "competition": "euroleague", "format": "euroleague_reg40_including_ot",
        "home_id": "euroleague:basketball:team:AAA", "away_id": "euroleague:basketball:team:ZZZ"}
    original = sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=ev, scope={"season": "2026", "rules": rule40})
    assert original["reference_weights"]["kind"] == implementation().REFERENCE_KIND
    assert original["history_refs"][0]["source_event_id"].startswith("E2026_")
    assert original["reference_weights"]["teams"][0] == "euroleague:basketball:team:AAA"
    assert original["params"] == base()["params"]
    raw = transport()
    raw["event"], raw["rules"] = ev, rule40
    groups = {}
    for side in ("home_id", "away_id"):
        team = rotation_team(event()[side])
        for player in team["players"]:
            player["player_id"] = "euroleague:basketball:player:P" + player["player_id"].rsplit(":", 1)[1]
            player["regulation_minutes"] = 20.
        groups[ev[side]] = team
    raw["data"]["teams"] = groups
    assert normalized(raw)[0]["complete"] is True


def test_typed_numerical_failure_uses_unchanged_base_not_fake_neutral_effect():
    original, _, observed = packet()
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats)
    fitted["heads"]["margin"].update(coef=[1e308], scale=[1e-8])
    envelope = {"kind": "context-effect-v1", "payload": fitted}
    result = implementation().team_sport_context_result("basketball", original, feats, envelope, event=event(), effect_hash=digest(envelope))
    assert result["role"] == "not_applied"
    assert result["comparison_params"] is None
    assert result["used_params"] == original["params"] and result["used_markets"] == original["markets"]
    assert all(value == "not_applied" for value in result["factor_roles"].values())


@pytest.mark.parametrize("field", ["kind", "schema", "source_schema", "complete", "collection", "availability", "player_id", "event_key", "format", "rules"])
def test_json_container_type_errors_are_typed_at_source_boundary(field):
    raw = transport()
    if field in {"kind", "schema", "source_schema"}: raw[field] = []
    elif field in {"complete", "collection"}: raw["data"]["teams"][event()["home_id"]][field] = []
    elif field in {"availability", "player_id"}: raw["data"]["teams"][event()["home_id"]]["players"][0][field] = []
    elif field in {"event_key", "format"}: raw["event"][field] = []
    elif field == "rules": raw["rules"] = []
    with pytest.raises(ContextContractError): normalized(raw)


def test_ordinary_price_and_tab_are_not_original_model_or_feature_inputs():
    import sports_prematch
    target, rows = inputs()
    target.update(bookmaker_odds=100., tab="Riskobet")
    for row in rows: row.update(bookmaker_odds=1.01, quote_status="missing")
    original = sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=event(), scope={"season": "2026", "rules": rules()})
    assert canonical_bytes(original) == canonical_bytes(base())


def test_neutral_court_orientation_mirrors_fitted_signed_effect_not_home_advantage():
    import sports_prematch
    target, rows = inputs()
    target["neutral_site"] = True
    original = sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=event(), scope={"season": "2026", "rules": rules()})
    _, raws, observed = packet()
    feats = feature_packet(original, observed)
    fitted = artifact(original, feats)
    forward = implementation().apply_team_sport_effect("basketball", original, feats, fitted, event=event())
    target["home_team_id"], target["away_team_id"] = target["away_team_id"], target["home_team_id"]
    ev = {**event(), "home_id": event()["away_id"], "away_id": event()["home_id"]}
    reverse = sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=ev, scope={"season": "2026", "rules": rules()})
    raws[0]["event"] = ev
    reversed_features = feature_packet(reverse, tuple(receipt(raw, NOW - timedelta(minutes=30)) for raw in raws), ev)
    backward = implementation().apply_team_sport_effect("basketball", reverse, reversed_features, artifact(reverse, reversed_features, ev=ev), event=ev)
    assert backward["params"]["expected_margin"] == -forward["params"]["expected_margin"]
    assert backward["markets"]["away_win"] == pytest.approx(forward["markets"]["home_win"], abs=1e-15)


@pytest.mark.parametrize("mutation", ["native-case-collision", "native-event-case-collision", "no-ids", "missing-season", "late-result", "confirmed-projection"])
def test_provenance_negative_paths_are_causal_or_explicitly_different(mutation):
    original, raws, observed = packet()
    if mutation == "confirmed-projection":
        raws[0]["data"]["status"] = "confirmed"
        newer = feature_packet(original, (*observed, receipt(raws[0])))
        assert newer["coverage"] != feature_packet(original, observed)["coverage"]
        assert newer["values"]["rotation_complete"] == 1
        return
    import sports_prematch
    target, rows = inputs()
    if mutation == "missing-season": rows[0].pop("season")
    elif mutation == "no-ids":
        for row in rows: row.pop("home_team_id"); row.pop("away_team_id")
        target.pop("home_team_id"); target.pop("away_team_id")
    elif mutation == "late-result":
        for row in rows: row["result_observed_at"] = canonical_timestamp(NOW + timedelta(days=1))
        with pytest.raises(ContextContractError):
            sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=event(), scope={"season": "2026", "rules": rules()})
        return
    else:
        # Numeric ESPN IDs have no lettercase aliases; retain the literal
        # provider text rather than silently interpreting leading zeros.
        if mutation == "native-case-collision": rows[0]["home_team_id"] = "01"
        else: rows[0]["provider_event_id"] = "0401800000"
    result = sports_prematch.basketball_base_distribution(target, rows, NOW, context_event=event(), scope={"season": "2026", "rules": rules()})
    assert result["reference_weights"]["kind"] == "unavailable"
