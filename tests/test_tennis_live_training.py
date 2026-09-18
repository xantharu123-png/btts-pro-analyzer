"""Synthetic sources through the real original -> D1 -> D2 path, not quality proof."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp, digest
from context_models.tennis_live import CODE_PATHS, ORIGIN_KIND, ORIGINAL_ARTIFACT_KIND, original_base
from context_models.tennis_v3 import tennis_features_v3
from context_models.training_cases import assemble_training_cases
from context_models.training_contracts import validate_family_config
from context_observations import _SELECT, _decode_receipt, append_observation
from context_sources.tennis_status import normalize_tennis_status, select_tennis_observations
from context_sources.outcomes import normalize_tennis_outcome
from model_artifacts import load_artifact, put_artifact
from test_tennis_live_worker import NOW, competition, publish_state
from test_context_tennis_outcome_capture import completed
from context_training_helpers import envelope
from test_context_runtime_tennis_live import (
    _REVIEWED_DURATION_SOURCE_MANIFEST,
    _REVIEWED_PRIOR_SOURCE_MANIFESTS,
)


_FROZEN_HISTORICAL_TRAINING_ORIGINALS = (
    {
        "source_commit": "185812e0846c7821a46673c9267abfe838d89f4b",
        "artifact_digest": "2504aaff4d5c48c6db53ba50f485d5ab21ab69489fa06e238317fdcbd82fed69",
        "origin": json.loads(r'''{"code_hashes":{"tennis/data_loader.py":"59ac32fcadc1d963ff981bbc0f6533c36579ea78f46ffe807349bc8a840ba937","tennis/elo.py":"cc7e6d4e249087aa5a1490b3e32c59dfced5f7b0ad32564ff2b028c72be48f35","tennis/model_state.py":"654a75872a2114f3125ee77fac4efa06376e8c47791ed5f76a562d9cc8456563","tennis/predict.py":"df806e19414e3a304068be0b5e322b8bdd996ce9252762676711906fe5bdab80","tennis/serve_model.py":"b32a0805b9c810d40ed52be7c8be8905330ecea876ae4aabd3ef7b6bd7635715","tennis/simulator.py":"82a9489bc4fd8d4c581ac7c133eec82f0ccc696f5c012362cc43f79ef4e044d3"},"competition_revision":"db0e73748c261977ab8d6b3affa5f1041b24effba97c09a9b6465f44500e238c","cutoff":"2026-09-09T12:00:00.000000Z","event":{"away_id":"espn:tennis:ATP:player:101","competition":"espn:ATP:tournament:189-2026","event_key":"espn:tennis:ATP:match:200","format":"singles","home_id":"espn:tennis:ATP:player:100","indoor":null,"schedule_revision":"6142277bc837799d2eeae193c170131f1eea85490ed440849dc1c549cc5025d8","scheduled_start":"2026-09-09T17:00:00.000000Z","sport":"tennis","status":"scheduled","surface":null,"tour":"ATP"},"inputs":{"best_of":3,"indoor":false,"player_a":"Alpha A","player_b":"Beta B","state_key_a":"alpha a","state_key_b":"beta b","surface":"Hard","tour":"ATP"},"kind":"tennis-live-winner-origin-v1","native_observed_at":"2026-09-09T11:59:50.000000Z","native_receipt":"d5e876fafde50ee2b602fab7cde73ae5c1a1afb242d629a566a2703d865c007b","native_state_identity":"unresolved","schema":1,"state_hash":"0d015d4c789a89f9b53e6705df7d39a04e7b004c670d0c0ead5e53ff22300aba","values":{"p_a_cal":0.875497705719586,"p_a_raw":0.8716369103008822,"p_b_cal":0.12450229428041404}}'''),
    },
    {
        "source_commit": "b342b02ac9c52b559152d7dd91d08c049e131611",
        "artifact_digest": "d8bc7fa2b1eb31e2d16fb4faccf83d774424bb746bcbf484f3a5b07824ac47c1",
        "origin": json.loads(r'''{"code_hashes":{"tennis/data_loader.py":"063c782b99fe876b2da5f4b5a6dec284fb1ae39b92aac5d9b42889acb392358c","tennis/elo.py":"cc7e6d4e249087aa5a1490b3e32c59dfced5f7b0ad32564ff2b028c72be48f35","tennis/model_state.py":"654a75872a2114f3125ee77fac4efa06376e8c47791ed5f76a562d9cc8456563","tennis/predict.py":"df806e19414e3a304068be0b5e322b8bdd996ce9252762676711906fe5bdab80","tennis/serve_model.py":"b32a0805b9c810d40ed52be7c8be8905330ecea876ae4aabd3ef7b6bd7635715","tennis/simulator.py":"82a9489bc4fd8d4c581ac7c133eec82f0ccc696f5c012362cc43f79ef4e044d3"},"competition_revision":"db0e73748c261977ab8d6b3affa5f1041b24effba97c09a9b6465f44500e238c","cutoff":"2026-09-09T12:00:00.000000Z","event":{"away_id":"espn:tennis:ATP:player:101","competition":"espn:ATP:tournament:189-2026","event_key":"espn:tennis:ATP:match:200","format":"singles","home_id":"espn:tennis:ATP:player:100","indoor":null,"schedule_revision":"6142277bc837799d2eeae193c170131f1eea85490ed440849dc1c549cc5025d8","scheduled_start":"2026-09-09T17:00:00.000000Z","sport":"tennis","status":"scheduled","surface":null,"tour":"ATP"},"inputs":{"best_of":3,"indoor":false,"player_a":"Alpha A","player_b":"Beta B","state_key_a":"alpha a","state_key_b":"beta b","surface":"Hard","tour":"ATP"},"kind":"tennis-live-winner-origin-v1","native_observed_at":"2026-09-09T11:59:50.000000Z","native_receipt":"d5e876fafde50ee2b602fab7cde73ae5c1a1afb242d629a566a2703d865c007b","native_state_identity":"unresolved","schema":1,"state_hash":"0d015d4c789a89f9b53e6705df7d39a04e7b004c670d0c0ead5e53ff22300aba","values":{"p_a_cal":0.875497705719586,"p_a_raw":0.8716369103008822,"p_b_cal":0.12450229428041404}}'''),
    },
)


def live_config(tour="ATP"):
    return {"schema": 1, "sport": "tennis", "family": "tennis:winner",
        "feature_version": "tennis-performed-load-v3",
        "feature_names": ["observed_recovery_minimum_hours_delta"],
        "population": {"sport": "tennis", "competitions": [f"espn:{tour}:tournament:189-2026"],
            "formats": ["singles"], "tours": [tour], "surfaces": [None], "indoor": [None]},
        "coverage": {"version": "tennis-performed-load-coverage-v2",
            "case": "status-paired.observed-only.receipt-bound-observed.missing-end-times"},
        "model_variant": "tennis-live-winner-status-load-antisymmetric-v1",
        "base_versions": ["tennis-live-calibrated-winner-v1"], "head_links": {"winner": "logit"},
        "reference_version": "tennis-context-reference-v3", "preprocessing_artifacts": {},
        "groups": {"recovery": ["observed_recovery_minimum_hours_delta"]},
        "joint_calibration": {"kind": "identity"}, "target_markets": ["winner_a", "winner_b"],
        "outcome_contract": "tennis-completed-winner-v1",
        "train_end": canonical_timestamp(NOW+timedelta(days=2)),
        "tune_end": canonical_timestamp(NOW+timedelta(days=4)),
        "alpha_grid": [.01, .1, 1., 10., 100.]}


def packet(tmp_path, tour="ATP"):
    from context_runtime_tennis import _native_event
    from tennis.predict import predict_match
    from tennis.tour_state import _decode_wrapper
    db = tmp_path / "live-training.db"
    state_ref = publish_state(db, tour=tour)
    state = _decode_wrapper(load_artifact(db, state_ref)["payload"], tour)
    grouping = "mens-singles" if tour == "ATP" else "womens-singles"
    root = Path(__file__).resolve().parents[1]
    hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in CODE_PATHS}
    originals, outcomes, bindings = [], [], []
    for index, day in enumerate((0, 1, 2, 3, 5, 7, 9)):
        decision = NOW+timedelta(days=day)
        native = competition(id=str(200+index), date=canonical_timestamp(decision+timedelta(hours=5)))
        for side, player in enumerate(native["competitors"]):
            player["id"] = str(100+index*10+side)
        for side in (0, 1):
            prior = completed(event_id=str(1000+index*10+side))
            received = decision-timedelta(hours=(24 if (index+side) % 2 else 48))
            prior["date"] = canonical_timestamp(received-timedelta(hours=4))
            prior["competitors"][0]["id"] = native["competitors"][side]["id"]
            prior["competitors"][1]["id"] = str(5000+index*10+side)
            for record in normalize_tennis_status(tour, "189-2026", prior,
                    grouping_slug=grouping, observed_at=received):
                append_observation(db, record, observed_at=received)
        received = decision-timedelta(seconds=10)
        status, = normalize_tennis_status(tour, "189-2026", native,
            grouping_slug=grouping, observed_at=received)
        native_ref = append_observation(db, status, observed_at=received)
        event = _native_event(status)
        captured = []
        predict_match(state, "Alpha A", "Beta B", surface="Hard", best_of=3, tour=tour,
            indoor=False, as_of=decision, workload_history=(), original_capture=captured.append)
        origin = {"schema": 1, "kind": ORIGIN_KIND, "event": event, "cutoff": canonical_timestamp(decision),
            "state_hash": state_ref, "native_receipt": native_ref, "native_observed_at": canonical_timestamp(received),
            "competition_revision": status["payload"]["competition_revision"], "native_state_identity": "unresolved",
            "code_hashes": hashes, **captured[0]}
        originals.append(put_artifact(db, kind=ORIGINAL_ARTIFACT_KIND,
            payload={"schema": 1, "origin": origin}, created_at=decision+timedelta(seconds=1)))
        bindings.append({"event_key": event["event_key"], "home_id": event["home_id"],
            "away_id": event["away_id"], "source_refs": [native_ref]})
        result = completed(event_id=native["id"], winner=index % 2)
        result["date"] = native["date"]
        for side in (0, 1):
            result["competitors"][side]["id"] = native["competitors"][side]["id"]
        at = decision+timedelta(hours=8)
        record = normalize_tennis_outcome(event, {"source_schema": "espn-scoreboard-v1", "tour": tour,
            "tournament_id": "189-2026", "competition": result}, observed_at=at)
        outcomes.append(append_observation(db, record, observed_at=at))
    built = NOW+timedelta(days=10)
    identity = put_artifact(db, kind="context-native-identity-map-v1", payload={"schema": 1,
        "policy": "native-source-only-v1", "bindings": bindings}, created_at=built)
    return db, originals, outcomes, identity, built


def cases_for(tmp_path, tour="ATP"):
    from context_models.tennis_training import build_live_training_case
    db, originals, outcomes, identity, built = packet(tmp_path, tour=tour)
    config = live_config(tour)
    cases = [build_live_training_case(db, original_ref=original, outcome_ref=outcome,
        identity_ref=identity, config=config, as_of=built) for original, outcome in zip(originals, outcomes)]
    return db, cases, config, built


def with_source_manifest(case, source_manifest, newline="LF"):
    from context_models.tennis_v3 import tennis_reference_hash_v3
    changed = deepcopy(case)
    payload = changed["case"]["payload"]
    old_ref = payload["replay_ref"]
    origin = payload["base"]["reference_weights"]
    origin["code_hashes"] = {
        name: variants[newline] for name, variants in source_manifest.items()
    }
    payload["base"] = original_base(origin)
    publication = envelope(ORIGINAL_ARTIFACT_KIND, {"schema": 1, "origin": origin})
    payload["replay_ref"] = publication["digest"]
    del changed["artifacts"][old_ref]
    changed["artifacts"][publication["digest"]] = publication
    payload["features"]["reference_hash"] = tennis_reference_hash_v3(
        payload["base"], payload["event"])
    changed["case"] = envelope("context-training-case-v1", payload)
    return changed


def with_frozen_original(case, fixture):
    from context_models.tennis_v3 import tennis_reference_hash_v3
    changed = deepcopy(case)
    payload = changed["case"]["payload"]
    old_ref = payload["replay_ref"]
    origin = deepcopy(fixture["origin"])
    payload["base"] = original_base(origin)
    publication = envelope(ORIGINAL_ARTIFACT_KIND, {"schema": 1, "origin": origin})
    assert publication["digest"] == fixture["artifact_digest"]
    payload["replay_ref"] = publication["digest"]
    del changed["artifacts"][old_ref]
    changed["artifacts"][publication["digest"]] = publication
    payload["features"]["reference_hash"] = tennis_reference_hash_v3(
        payload["base"], payload["event"])
    changed["case"] = envelope("context-training-case-v1", payload)
    return changed


def test_live_cohort_is_distinct_from_legacy_and_does_not_invent_environment():
    config = live_config()
    assert validate_family_config(config) == config
    for change in ({"base_versions": ["tennis-winner-predecision-tour-state-v1"]},
                   {"feature_version": "tennis-performed-load-v2"},
                   {"model_variant": "tennis-winner-status-load-antisymmetric-v1"}):
        with pytest.raises(ContextContractError):
            validate_family_config({**deepcopy(config), **change})
    for field, value in (("surfaces", ["Hard"]), ("indoor", [False]), ("tours", ["ATP", "WTA"])):
        bad = deepcopy(config)
        bad["population"][field] = value
        with pytest.raises(ContextContractError):
            validate_family_config(bad)


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_real_stored_originals_can_train_and_change_complementary_winner_probabilities(tmp_path, tour):
    from context_models.training import fit_family
    from context_models.tennis_effect import apply_tennis_effect, tennis_context_result
    db, cases, config, _ = cases_for(tmp_path, tour=tour)
    assembly = assemble_training_cases(tuple(cases[:4]), config)
    assert assembly["canonical_events"] == 4 and not assembly["excluded"]
    fit = fit_family(assembly["rows"], config, cases=tuple(cases[:4]))
    assert fit["status"] == "fitted" and fit["training_events"] == fit["tuning_events"] == 2
    source = deepcopy(cases[-1]["case"]["payload"])
    before = deepcopy(source)
    changed = apply_tennis_effect(source["base"], source["features"], fit["artifact"], event=source["event"])
    assert changed["markets"]["winner_a"] != source["base"]["markets"]["winner_a"]
    assert changed["markets"]["winner_a"] + changed["markets"]["winner_b"] == pytest.approx(1.)
    assert source == before
    result = tennis_context_result(source["base"], source["features"],
        {"kind": "context-effect-v1", "payload": fit["artifact"]}, event=source["event"], effect_hash=fit["effect_hash"])
    assert result["used_markets"] == source["base"]["markets"] and result["role"] != "applied"
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE kind='context-approval-v1'").fetchone()[0] == 0


def test_builder_is_read_only_and_uses_complete_relevant_revisions(tmp_path):
    db, cases, _, _ = cases_for(tmp_path)
    first = cases[0]
    assert len(first["observations"]) == 8  # target + two status/workload triples + result
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE kind='context-training-case-v1'").fetchone()[0] == 0
        all_rows = tuple(_decode_receipt(row) for row in connection.execute(_SELECT))
    payload = first["case"]["payload"]
    from datetime import datetime
    full = select_tennis_observations(all_rows, cutoff=datetime.fromisoformat(payload["base"]["cutoff"]), tour="ATP")
    assert tennis_features_v3(payload["event"], full, payload["base"],
        cutoff=datetime.fromisoformat(payload["base"]["cutoff"])) == payload["features"]


@pytest.mark.parametrize("source_manifest", _REVIEWED_PRIOR_SOURCE_MANIFESTS,
                         ids=("locator", "pre-duration"))
@pytest.mark.parametrize("newline", ["LF", "CRLF"])
def test_exact_historical_original_replays_through_training_verifier(
        tmp_path, source_manifest, newline):
    from context_models.training_contracts import validate_resolved_case
    _, cases, config, _ = cases_for(tmp_path)
    historical = with_source_manifest(cases[0], source_manifest, newline)

    assert validate_resolved_case(historical, config=config) == historical


@pytest.mark.parametrize("fixture", _FROZEN_HISTORICAL_TRAINING_ORIGINALS,
                         ids=("locator-original", "pre-duration-original"))
def test_canonical_predecessor_original_replays_through_training_verifier(
        tmp_path, fixture):
    from context_models.training_contracts import validate_resolved_case
    _, cases, config, _ = cases_for(tmp_path)
    historical = with_frozen_original(cases[0], fixture)

    assert validate_resolved_case(historical, config=config) == historical
    base = historical["case"]["payload"]["base"]
    assert base["params"] == {"p_a": 0.875497705719586}
    assert base["markets"] == {
        "winner_a": 0.875497705719586,
        "winner_b": 0.12450229428041404,
    }


def test_prior_reviewed_duration_manifest_remains_training_compatible(tmp_path):
    from context_models.training_contracts import validate_resolved_case
    _, cases, config, _ = cases_for(tmp_path)
    historical = with_source_manifest(
        cases[0], _REVIEWED_DURATION_SOURCE_MANIFEST, "LF")

    assert validate_resolved_case(historical, config=config) == historical


@pytest.mark.parametrize("source_manifest", _REVIEWED_PRIOR_SOURCE_MANIFESTS,
                         ids=("locator", "pre-duration"))
def test_historical_training_replay_rejects_another_owner_change(tmp_path, source_manifest):
    from context_models.training_contracts import validate_resolved_case
    _, cases, config, _ = cases_for(tmp_path)
    changed = deepcopy(source_manifest)
    changed["tennis/predict.py"] = {"LF": "f" * 64, "CRLF": "f" * 64}
    historical = with_source_manifest(cases[0], changed)

    with pytest.raises(ContextContractError):
        validate_resolved_case(historical, config=config)


@pytest.mark.parametrize("change", ["probability", "state", "code", "feature", "outcome", "missing_source"])
def test_changed_original_or_source_cannot_enter_training(tmp_path, change):
    from context_models.training_contracts import validate_resolved_case
    _, cases, config, _ = cases_for(tmp_path)
    bad = deepcopy(cases[0])
    payload = bad["case"]["payload"]
    if change == "probability":
        payload["base"]["params"]["p_a"] = .99
        payload["base"]["markets"] = {"winner_a": .99, "winner_b": 1-.99}
    elif change == "state":
        bad["artifacts"].pop(payload["base"]["model_hash"])
    elif change == "code":
        payload["base"]["reference_weights"]["code_hashes"][CODE_PATHS[0]] = "f"*64
    elif change == "feature":
        payload["features"]["values"]["observed_recovery_minimum_hours_delta"] += 1
    elif change == "outcome":
        payload["outcome_ref"] = cases[1]["case"]["payload"]["outcome_ref"]
    else:
        bad["observations"] = tuple(row for row in bad["observations"] if row["kind"] != "workload")
    bad["case"] = envelope("context-training-case-v1", payload)
    with pytest.raises(ContextContractError):
        validate_resolved_case(bad, config=config)


def frozen_packet(tmp_path):
    from context_models.experiments import freeze_experiment
    from context_models.training import fit_family
    db, cases, config, built = cases_for(tmp_path)
    def store(kind, value):
        return put_artifact(db, kind=kind, payload=value, created_at=built)
    for case in cases:
        assert store(case["case"]["kind"], case["case"]["payload"]) == case["case"]["digest"]
    training = tuple(cases[:4])
    fit = fit_family(assemble_training_cases(training, config)["rows"], config, cases=training)
    for ref, effect in fit["candidate_artifacts"].items():
        assert store("context-effect-v1", effect) == ref
    fit_ref = store("context-fit-v1", fit)
    member = lambda case: {"case_ref": case["case"]["digest"],
        "observation_refs": sorted(row["digest"] for row in case["observations"])}
    identity = cases[0]["case"]["payload"]["event_identity_hash"]
    dataset = {"schema": 1, "event_identity_hash": identity, "groups": [{
        "family_config_hash": digest(config), "training_cases": [member(c) for c in cases[:4]],
        "final_cases": [member(c) for c in cases[4:]], "unavailable_final": [], "fit_ref": fit_ref}]}
    dataset_ref = store("context-dataset-v1", dataset)
    definition = {"family_config_hash": digest(config), "ablation": "full", "target_markets": config["target_markets"],
        "outcome_contract": config["outcome_contract"]}
    hypothesis = {**definition, "hypothesis_id": digest(definition), "candidate_artifact": fit["effect_hash"],
        "pretest_status": "ready"}
    frozen = built+timedelta(minutes=1)
    plan = {"schema": 1, "dataset_hash": dataset_ref, "event_identity_hash": identity,
        "code_revision": "a"*40, "base_versions": config["base_versions"], "family_configs": [config],
        "train_end": config["train_end"], "tune_end": config["tune_end"],
        "test_blocks": [[canonical_timestamp(NOW+timedelta(days=d)), canonical_timestamp(NOW+timedelta(days=d+2))]
            for d in (4, 6, 8)], "target_markets": config["target_markets"],
        "outcome_contracts": [config["outcome_contract"]], "candidate_artifacts": [fit["effect_hash"]],
        "policy_version": "context-paired-hac-bh-v1", "availability_classes": ["prospective"],
        "created_at": canonical_timestamp(frozen), "hypotheses": [hypothesis],
        "test_inventory": [{"event": c["case"]["payload"]["event"], "decision_at": c["case"]["payload"]["base"]["cutoff"],
            "block": f"test:{index}"} for index, c in enumerate(cases[4:])]}
    plan_ref = freeze_experiment(db, plan, created_at=frozen)
    return db, cases, plan, plan_ref, built+timedelta(hours=1)


def test_live_dataset_reaches_real_evaluation_but_small_synthetic_corpus_never_approves(tmp_path):
    from context_models.evaluator import evaluate_experiment, verify_evaluation
    from context_models.dataset import _reader, prepare_dataset
    from context_runtime import verify_context_database
    db, cases, plan, ref, evaluated = frozen_packet(tmp_path)
    assert prepare_dataset(db, ref, evaluated_at=evaluated)["plan"] == plan
    result = evaluate_experiment(db, ref, evaluated_at=evaluated)
    key = plan["hypotheses"][0]["hypothesis_id"]
    assert len(result["payload"]["results"][key]) == 6
    assert len(result["payload"]["distribution_losses"][key]) == 3
    assert result["payload"]["statistics"]["hypotheses"][key]["metrics"]["event_count"] == 3
    assert result["approvals"] == [] and result["payload"]["ready_failures"][key] == []
    with _reader(db) as connection:
        assert verify_evaluation(connection, result["digest"])["payload"] == result["payload"]
    report = verify_context_database(db)
    assert report["empirical_approval_verified"] is False


def test_stored_dataset_rejects_omitted_or_added_history_before_fitting(tmp_path):
    from context_models.dataset import _reader, resolve_case
    db, _, plan, _, _ = frozen_packet(tmp_path)
    dataset = load_artifact(db, plan["dataset_hash"])["payload"]
    member = deepcopy(dataset["groups"][0]["training_cases"][0])
    member["observation_refs"].pop(0)
    with _reader(db) as connection, pytest.raises(ContextIntegrityError, match="causal participant/source"):
        resolve_case(connection, member, config=plan["family_configs"][0], plan=plan, latest=plan["created_at"])


@pytest.mark.parametrize("field", ["original", "state"])
def test_actual_publication_clocks_cannot_be_laundered_by_valid_payloads(tmp_path, field):
    from context_models.tennis_training import build_live_training_case
    db, originals, outcomes, identity, built = packet(tmp_path)
    publication = load_artifact(db, originals[0])["payload"]
    origin = publication["origin"]
    ref = originals[0] if field == "original" else origin["state_hash"]
    wrong_clock = origin["event"]["scheduled_start"] if field == "original" else canonical_timestamp(NOW+timedelta(seconds=1))
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?", (wrong_clock, ref))
    with pytest.raises(ContextIntegrityError):
        build_live_training_case(db, original_ref=originals[0], outcome_ref=outcomes[0],
            identity_ref=identity, config=live_config(), as_of=built)


def test_publicly_rehashed_fake_original_still_fails_actual_model_replay(tmp_path):
    from context_models.training_contracts import validate_resolved_case
    from context_models.tennis_v3 import tennis_reference_hash_v3
    _, cases, config, _ = cases_for(tmp_path)
    bad = deepcopy(cases[0])
    payload = bad["case"]["payload"]
    old_ref = payload["replay_ref"]
    origin = payload["base"]["reference_weights"]
    origin["values"].update(p_a_cal=.99, p_b_cal=1-.99)
    payload["base"] = original_base(origin)
    publication = envelope(ORIGINAL_ARTIFACT_KIND, {"schema": 1, "origin": origin})
    payload["replay_ref"] = publication["digest"]
    del bad["artifacts"][old_ref]
    bad["artifacts"][publication["digest"]] = publication
    payload["features"]["reference_hash"] = tennis_reference_hash_v3(payload["base"], payload["event"])
    bad["case"] = envelope("context-training-case-v1", payload)
    with pytest.raises(ContextIntegrityError, match="actual tour model"):
        validate_resolved_case(bad, config=config)


def test_later_revision_removing_player_is_kept_and_future_revision_is_not(tmp_path):
    from context_models.dataset import _reader
    from context_models.tennis_training import relevant_receipts
    db, cases, _, _ = cases_for(tmp_path)
    payload = cases[0]["case"]["payload"]
    before = tuple(row for row in cases[0]["observations"] if row["kind"] != "match_outcome")
    for hours, participants in ((-1, (9001, 9002)), (1, (100, 9002))):
        raw = completed(event_id="1000")
        raw["date"] = canonical_timestamp(NOW-timedelta(hours=52))
        for side, player in enumerate(raw["competitors"]):
            player["id"] = str(participants[side])
        received = NOW+timedelta(hours=hours)
        for record in normalize_tennis_status("ATP", "189-2026", raw,
                grouping_slug="mens-singles", observed_at=received):
            append_observation(db, record, observed_at=received)
    with _reader(db) as connection:
        rows = relevant_receipts(connection, payload["event"], payload["base"]["cutoff"])
    assert len(rows) == len(before)+3
    assert max(row["observed_at"] for row in rows) <= payload["base"]["cutoff"]
    features = tennis_features_v3(payload["event"], rows, payload["base"], cutoff=NOW)
    assert features["states"]["observed_recovery_minimum_hours_a"] == "missing"


def test_d2_does_not_open_final_labels_before_the_registered_inventory(tmp_path, monkeypatch):
    import context_models.dataset as dataset
    from context_models.evaluator import evaluate_experiment
    from context_models.experiments import _openings
    db, cases, plan, ref, evaluated = frozen_packet(tmp_path)
    final_refs = {case["case"]["payload"]["outcome_ref"] for case in cases[4:]}
    original = dataset._receipt
    def guarded(connection, receipt):
        if receipt in final_refs:
            openings, _ = _openings(connection)
            assert openings[ref][1]["event_keys"] == sorted(row["event"]["event_key"] for row in plan["test_inventory"])
        return original(connection, receipt)
    monkeypatch.setattr(dataset, "_receipt", guarded)
    assert evaluate_experiment(db, ref, evaluated_at=evaluated)["approvals"] == []


def test_mixed_football_and_live_tennis_inventory_keeps_replay_owners_separate(tmp_path):
    from context_dataset_helpers import stored_packet
    from context_runtime import verify_context_database
    directory = tmp_path / "football"
    directory.mkdir()
    football = stored_packet(directory)
    db, _, _, _, _ = frozen_packet(tmp_path)
    # Merge only these synthetic, schema-identical immutable inventories.
    with sqlite3.connect(football["path"]) as source, sqlite3.connect(db) as target:
        for table in ("context_contents", "context_observations", "artifacts"):
            rows = source.execute(f"SELECT * FROM {table}").fetchall()
            slots = ",".join("?" for _ in rows[0])
            target.executemany(f"INSERT INTO {table} VALUES ({slots})", rows)
    result = verify_context_database(db)
    assert result["empirical_approval_verified"] is False


def test_unavailable_context_is_preserved_as_an_explicit_training_exclusion(tmp_path):
    from context_models.tennis_training import build_live_training_case
    db, originals, outcomes, identity, built = packet(tmp_path)
    raw = competition(id="1000", date=canonical_timestamp(NOW-timedelta(hours=52)))
    raw["competitors"][0]["id"], raw["competitors"][1]["id"] = "100", "5000"
    raw["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS", completed=False)
    received = NOW-timedelta(hours=1)
    for record in normalize_tennis_status("ATP", "189-2026", raw,
            grouping_slug="mens-singles", observed_at=received):
        append_observation(db, record, observed_at=received)
    config = live_config()
    case = build_live_training_case(db, original_ref=originals[0], outcome_ref=outcomes[0],
        identity_ref=identity, config=config, as_of=built)
    assembly = assemble_training_cases((case,), config)
    assert assembly["canonical_events"] == 0 and len(assembly["excluded"]) == 1
    assert assembly["excluded"][0]["case_hash"] == case["case"]["digest"]
    assert assembly["excluded"][0]["reason"] == "feature_coverage_outside_frozen_cohort"
