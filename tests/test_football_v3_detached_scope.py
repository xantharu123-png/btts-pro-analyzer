"""Actual expanded native-player sources at the owning detached/D4 boundary.

Baseline-control fixtures contain no fitted effect and confer no empirical
quality. The hand-checked event inventory catches missing national event scope.
"""
from copy import deepcopy
from datetime import timedelta
import sqlite3
import shutil

import pytest

from context_models.contracts import canonical_timestamp, digest, ContextContractError, ContextIntegrityError
from context_models.dataset import _reader, resolve_case
from context_models.experiments import freeze_experiment
from context_models.football_training import build_joint_training_case
from context_runtime import verify_context_database
from model_artifacts import ArtifactIntegrityError, put_artifact
from test_football_player_load_integration import isolated, national, load_config
from test_football_joint_training import source_case
from context_training_helpers import NOW


BUILT = NOW+timedelta(hours=6)
FROZEN = NOW+timedelta(days=4)
BLOCKS = [[canonical_timestamp(NOW+timedelta(days=day)),
           canonical_timestamp(NOW+timedelta(days=day+2))] for day in (4, 6, 8)]
NATIONAL_KEY = "api-football:football:777001"
ORIGINAL_KEYS = {"api-football:football:9000", *{
    "api-football:football:"+str(901000+i) for i in range(24)}}


@pytest.fixture(scope="module")
def joint_sources(tmp_path_factory):
    import test_football_joint_training as helpers
    inventory = helpers.football_inventory
    sources = {}
    for law in ("football-joint-settlement-projection-v1", "football-joint-settlement-projection-v2"):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(helpers, "football_inventory", lambda *a, **kw: inventory(*a, **{**kw, "count": 24}))
            if law == "football-joint-settlement-projection-v2":
                # Same real offline candidate execution contract as the owning
                # variant-binding tests: captured runtime fingerprint is v15,
                # never an arbitrary code envelope or default-law activation.
                import challenge_engine as engine
                patch.setattr(engine, "CHALLENGE_PREDICTION_VERSION", "challenge-engine:coherent-joint-calibration-v15")
            sources[law] = source_case(tmp_path_factory.mktemp("native-"+law[-2:]), patch, law_version=law)
    return sources


@pytest.fixture(scope="module")
def native_case(joint_sources):
    return joint_sources["football-joint-settlement-projection-v1"]


def persist_case_plan(path, case, config, *, observation_refs=None):
    """Freeze only a baseline-control source case, not a numerical fit."""
    payload = case["case"]["payload"]
    case_ref = put_artifact(path, kind=case["case"]["kind"], payload=payload, created_at=BUILT)
    member = {"case_ref": case_ref, "observation_refs": sorted(
        row["digest"] for row in case["observations"]) if observation_refs is None else observation_refs}
    dataset = {"schema": 1, "event_identity_hash": payload["event_identity_hash"], "groups": [{
        "family_config_hash": digest(config), "training_cases": [member], "final_cases": [],
        "unavailable_final": [], "fit_ref": None}]}
    dataset_ref = put_artifact(path, kind="context-dataset-v1", payload=dataset, created_at=BUILT)
    definition = {"family_config_hash": digest(config), "ablation": "baseline_control",
        "target_markets": config["target_markets"], "outcome_contract": config["outcome_contract"]}
    plan = {"schema": 1, "dataset_hash": dataset_ref, "event_identity_hash": payload["event_identity_hash"],
        "code_revision": "242093feda28a31bb8729e31529032ee059b570a", "base_versions": config["base_versions"],
        "family_configs": [config], "train_end": config["train_end"], "tune_end": config["tune_end"],
        "test_blocks": BLOCKS, "target_markets": config["target_markets"],
        "outcome_contracts": [config["outcome_contract"]], "candidate_artifacts": [],
        "policy_version": "context-paired-hac-bh-v1", "availability_classes": ["prospective"],
        "created_at": canonical_timestamp(FROZEN), "hypotheses": [{**definition,
            "hypothesis_id": digest(definition), "candidate_artifact": None, "pretest_status": "baseline_control"}],
        "test_inventory": []}
    ref = freeze_experiment(path, plan, created_at=FROZEN)
    return member, plan, ref


def expanded_case(isolated):
    path, case, config = isolated
    added = national(path)
    config = load_config(config)
    payload = case["case"]["payload"]
    built = build_joint_training_case(path, binding_ref=payload["replay_ref"], outcome_ref=payload["outcome_ref"],
        identity_ref=payload["event_identity_hash"], config=config, as_of=BUILT)
    source = tuple(row for row in built["observations"] if row["kind"] != "match_outcome")
    assert {row["event_key"] for row in source} == ORIGINAL_KEYS | {NATIONAL_KEY}
    assert set(added) <= {row["digest"] for row in source}
    player = [row for row in source if row["event_key"] == NATIONAL_KEY
              and row["kind"] == "appearance" and row["subject_id"] == "api-football:player:1"]
    assert len(player) == 1
    assert player[0]["digest"] in built["case"]["payload"]["features"]["refs"]["load.home.reported_minutes_schedule_7d"]
    return path, built, config, added


def test_v3_national_event_resolves_through_actual_detached_owner(isolated):
    from context_models.training_contracts import validate_resolved_case
    path, built, config, _ = expanded_case(isolated)
    item, plan, _ = persist_case_plan(path, built, config)
    before = path.read_bytes()
    with _reader(path) as connection:
        resolved = resolve_case(connection, item, config=config, plan=plan, latest=canonical_timestamp(FROZEN))
    checked = validate_resolved_case(resolved, config=config)
    assert checked["case"] == built["case"] and checked["artifacts"] == built["artifacts"]
    assert {row["digest"]: row for row in checked["observations"]} == {
        row["digest"]: row for row in built["observations"]}
    assert path.read_bytes() == before


def test_v3_national_event_passes_full_d4_without_an_effect_or_fit(isolated):
    path, built, config, _ = expanded_case(isolated)
    _, _, ref = persist_case_plan(path, built, config)
    before = path.read_bytes()
    report = verify_context_database(path)
    assert ref in report["d2_verified"]["experiments"]
    assert built["case"]["digest"] in report["d2_verified"]["cases"]
    assert not report["empirical_approval_verified"]
    assert path.read_bytes() == before
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM artifacts WHERE kind IN ('context-effect-v1','context-fit-v1','context-approval-v1')").fetchone()[0] == 0


@pytest.mark.parametrize("version", ["football-native-context-v1", "football-native-context-exposure-v2"])
@pytest.mark.parametrize("law", ["football-joint-settlement-projection-v1", "football-joint-settlement-projection-v2"])
def test_legacy_source_scope_and_both_known_joint_laws_pass_d4_without_expansion(joint_sources, tmp_path, law, version):
    from context_models.football_joint_context import feature_coverage
    source, old, config = deepcopy(joint_sources[law])
    path = tmp_path/"legacy.db"
    shutil.copyfile(source, path)
    added = national(path)
    config.update(feature_version=version, coverage=feature_coverage(version),
        feature_names=["schedule.gap_hours_home"], groups={"schedule": ["schedule.gap_hours_home"]})
    payload = old["case"]["payload"]
    built = build_joint_training_case(path, binding_ref=payload["replay_ref"], outcome_ref=payload["outcome_ref"],
        identity_ref=payload["event_identity_hash"], config=config, as_of=BUILT)
    assert not set(added) & {row["digest"] for row in built["observations"]}
    assert {row["event_key"] for row in built["observations"]} == ORIGINAL_KEYS
    assert built["case"]["payload"]["base"] == payload["base"]
    item, plan, ref = persist_case_plan(path, built, config)
    before = path.read_bytes()
    with _reader(path) as connection:
        resolved = resolve_case(connection, item, config=config, plan=plan, latest=canonical_timestamp(FROZEN))
    assert {row["digest"] for row in resolved["observations"]} == set(item["observation_refs"])
    assert ref in verify_context_database(path)["d2_verified"]["experiments"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("version", [None, True, 3, "unknown-v4", [], {}])
def test_source_scope_dispatch_rejects_unknown_versions_without_a_default_scope(version):
    from context_models.football_training import joint_source_scope_kwargs
    with pytest.raises(ContextContractError, match="unknown.*source-scope"):
        joint_source_scope_kwargs(version)


@pytest.mark.parametrize("change", ["omit_negative", "omit_whole_event", "add_unrelated"])
def test_complete_d4_rejects_forged_added_or_omitted_national_source_pools(isolated, change):
    from context_observations import append_observation
    from context_sources.outcomes import normalize_football_base_input
    from context_training_helpers import detail
    path, built, config, added = expanded_case(isolated)
    refs = {row["digest"] for row in built["observations"]}
    if change == "omit_negative":
        negative = next(row["digest"] for row in built["observations"]
            if row["event_key"] == NATIONAL_KEY and row["kind"] == "availability")
        refs.remove(negative)  # No convenient omission of nonpositive evidence.
    elif change == "omit_whole_event": refs.difference_update(added)
    else:
        raw = detail(888888, NOW-timedelta(days=2))
        row = normalize_football_base_input(raw, observed_at=NOW-timedelta(days=1))
        refs.add(append_observation(path, row, observed_at=NOW-timedelta(days=1)))
    persist_case_plan(path, built, config, observation_refs=sorted(refs))
    before = path.read_bytes()
    with pytest.raises(ArtifactIntegrityError) as caught:
        verify_context_database(path)
    assert "joint case omits or adds a causal native revision" in str(caught.value.__cause__)
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["wrong_binding_kind", "binding_event", "case_before_binding", "foreign_outcome"])
def test_full_d4_joint_dispatch_preserves_original_binding_clock_and_outcome_ownership(isolated, change):
    from context_observations import append_observation
    from context_sources.football import _detail_event
    from context_sources.outcomes import normalize_football_outcome
    from context_training_helpers import detail
    path, built, config, _ = expanded_case(isolated)
    payload = built["case"]["payload"]
    if change == "wrong_binding_kind":
        payload["replay_ref"] = payload["event_identity_hash"]
    elif change == "binding_event":
        envelope = built["artifacts"][payload["replay_ref"]]
        binding = deepcopy(envelope["payload"])
        binding["native_event"]["home_id"] = "api-football:team:777"
        payload["replay_ref"] = put_artifact(path, kind=envelope["kind"], payload=binding,
            created_at=NOW+timedelta(seconds=1))
    elif change == "foreign_outcome":
        raw = detail(888888, NOW+timedelta(hours=2))
        event = {**_detail_event(raw), "status": "scheduled"}
        row = normalize_football_outcome(event, raw, observed_at=NOW+timedelta(hours=4))
        payload["outcome_ref"] = append_observation(path, row, observed_at=NOW+timedelta(hours=4))
    item, _, _ = persist_case_plan(path, built, config)
    if change == "case_before_binding":
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE artifacts SET created_at=? WHERE digest=?",
                (canonical_timestamp(NOW), item["case_ref"]))
    before = path.read_bytes()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)
    assert path.read_bytes() == before


def test_unknown_base_keeps_the_prior_strict_replay_path(isolated):
    path, old, _ = isolated
    payload = deepcopy(old["case"]["payload"])
    payload["base"]["version"] = "football-unknown-baseline-v99"
    payload["base"]["params"].pop("joint_cells")
    put_artifact(path, kind="context-training-case-v1", payload=payload, created_at=BUILT)
    with pytest.raises(ArtifactIntegrityError) as caught:
        verify_context_database(path)
    assert "resolved artifact has a different kind" in str(caught.value.__cause__)


def test_orphan_joint_case_keeps_its_explicit_uncertified_owning_boundary(isolated):
    path, built, _, _ = expanded_case(isolated)
    ref = put_artifact(path, kind=built["case"]["kind"], payload=built["case"]["payload"], created_at=BUILT)
    report = verify_context_database(path)
    assert ref not in report["d2_verified"]["cases"]
    assert "d1-case-owning-replay-unavailable" in report["limitations"]
    assert not report["empirical_approval_verified"]


def test_v3_detached_scope_excludes_late_outcome_and_unrelated_player_receipts(isolated):
    from context_observations import append_observation
    from context_sources.football import _detail_event, normalize_football_context
    from context_sources.outcomes import normalize_football_base_input, normalize_football_outcome
    from context_training_helpers import detail
    path, old, config = isolated
    early = national(path)
    late = national(path, observed=NOW+timedelta(minutes=1))
    raw = detail(888002, NOW-timedelta(days=2))
    for block in raw["players"]:
        for item in block["players"]: item["player"]["id"] += 10000
    event = _detail_event(raw)
    received = NOW-timedelta(days=1)
    records = (normalize_football_base_input(raw, observed_at=received),) + normalize_football_context(
        event, injuries=[], lineups=[], appearances=[raw], observed_at=received)
    unrelated = tuple(append_observation(path, row, observed_at=received) for row in records)
    result_raw = detail(777001, NOW-timedelta(days=2))
    result_raw["league"]["id"] = 5
    result_raw["teams"]["home"]["id"], result_raw["teams"]["away"]["id"] = 100, 200
    result_event = {**_detail_event(result_raw), "status": "scheduled"}
    outcome = normalize_football_outcome(result_event, result_raw, observed_at=received)
    other_outcome = append_observation(path, outcome, observed_at=received)
    config = load_config(config)
    p = old["case"]["payload"]
    built = build_joint_training_case(path, binding_ref=p["replay_ref"], outcome_ref=p["outcome_ref"],
        identity_ref=p["event_identity_hash"], config=config, as_of=BUILT)
    refs = {row["digest"] for row in built["observations"]}
    assert set(early) <= refs and not (set(late) | set(unrelated) | {other_outcome}) & refs
    assert {row["event_key"] for row in built["observations"]} == ORIGINAL_KEYS | {NATIONAL_KEY}
    item, plan, _ = persist_case_plan(path, built, config)
    with _reader(path) as connection:
        resolved = resolve_case(connection, item, config=config, plan=plan, latest=canonical_timestamp(FROZEN))
    assert {row["digest"] for row in resolved["observations"]} == refs
    assert built["case"]["digest"] in verify_context_database(path)["d2_verified"]["cases"]


@pytest.mark.parametrize("bound,reason", [("MAX_SOURCE_RECEIPTS", "joint_source_receipt_bound_exceeded"),
    ("MAX_SOURCE_BYTES", "joint_source_byte_bound_exceeded")])
def test_detached_v3_rejects_the_entire_expanded_pool_at_the_existing_bounds(isolated, monkeypatch, bound, reason):
    import football_joint_worker as worker
    path, built, config, _ = expanded_case(isolated)
    source = [row for row in built["observations"] if row["kind"] != "match_outcome"]
    if bound == "MAX_SOURCE_RECEIPTS": maximum = len(source)-1
    else:
        with sqlite3.connect(path) as connection:
            maximum = sum(connection.execute("SELECT length(payload) FROM context_contents WHERE content_digest=?",
                (row["content_digest"],)).fetchone()[0] for row in source)-1
    persist_case_plan(path, built, config)
    monkeypatch.setattr(worker, bound, maximum)
    with pytest.raises(ArtifactIntegrityError) as caught:
        verify_context_database(path)
    assert reason in str(caught.value.__cause__)


def test_later_v3_guard_survives_a_genuine_old_nonexpanded_decision_proof(isolated, monkeypatch):
    import football_context_decisions as decisions
    from context_models.football_readiness import inspect_football_readiness
    from context_models.replay import ReplayUnavailable
    from test_football_joint_worker import capture_report
    path, old, config = isolated
    national(path)
    later = NOW+timedelta(minutes=2)
    monkeypatch.setattr(decisions, "_now", lambda: later+timedelta(seconds=1))
    ref = old["case"]["payload"]["replay_ref"]
    proof = decisions.publish_capture_decisions(path, capture_report([ref]), decision_at=later)
    assert proof["events"][0]["status"] == "captured"
    config = load_config(config)
    p = old["case"]["payload"]
    with pytest.raises(ReplayUnavailable, match="player_load_requires_original_decision"):
        build_joint_training_case(path, binding_ref=ref, outcome_ref=p["outcome_ref"],
            identity_ref=p["event_identity_hash"], config=config, as_of=BUILT, decision_at=later)
    report = inspect_football_readiness(path, ({"binding_ref": ref, "decision_ref": proof["events"][0]["decision_ref"]},),
        config, test_blocks=tuple((NOW+timedelta(days=d), NOW+timedelta(days=d+2)) for d in (4, 6, 8)), as_of=FROZEN)
    assert report["source_complete_events"] == 0
    assert report["events"][0]["reason"] == "player_load_requires_original_decision"


def test_d1_readiness_uses_the_same_expanded_native_pool_without_qualification(isolated):
    from context_models.football_readiness import inspect_football_readiness
    path, built, config, _ = expanded_case(isolated)
    report = inspect_football_readiness(path, ({"binding_ref": built["case"]["payload"]["replay_ref"]},), config,
        test_blocks=tuple((NOW+timedelta(days=d), NOW+timedelta(days=d+2)) for d in (4, 6, 8)), as_of=FROZEN)
    assert report["source_complete_events"] == report["feature_complete_events"] == 1
    assert report["events"][0]["unavailable_features"] == []
    assert report["input_byte_accounting"] == "unique-physical-payload-v1"
    assert report["minimum_test_events"] == 200 and report["test_events"] == 0
    assert report["empirical_qualification"] == "not_evaluated"
