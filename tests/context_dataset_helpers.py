"""Synthetic offline D2 mechanics, never a real empirical acceptance corpus."""
from copy import deepcopy
from datetime import timedelta
import sqlite3

from context_models.contracts import OBSERVATION_FIELDS, canonical_timestamp, digest
from context_models.experiments import freeze_experiment
from context_models.football import football_features
from context_models.replay import replay_base_distribution
from context_models.training import fit_family
from context_models.training_cases import assemble_training_cases
from context_models.training_contracts import validate_family_config
from context_observations import append_observation, observations_as_of
from context_sources.football import _detail_event, normalize_football_context
from context_sources.outcomes import normalize_football_base_input, normalize_football_outcome
from model_artifacts import put_artifact
from context_training_helpers import NOW, detail, envelope, football_recipe

BUILT = NOW + timedelta(days=8)
FROZEN = BUILT + timedelta(minutes=1)
EVALUATED = BUILT + timedelta(hours=1)
_PACKET = None


def cached_packet(factory):
    global _PACKET
    if _PACKET is None:
        _PACKET = stored_packet(factory.mktemp("source-d2"))
    return _PACKET


def stored_packet(directory, *, control=False):
    """Seven native-shaped events with disjoint historical fixture identities."""
    path = directory / "mechanics.db"
    prepared = []
    for index, day in enumerate((-9, -8, -5, -4, 1, 3, 5)):
        decision, event_id = NOW + timedelta(days=day), 9000 + index
        raw = []
        for sample in range(26):
            kickoff = decision - timedelta(days=26-sample)
            raw.append((detail(event_id*100+sample, kickoff,
                goals=(1+sample % 3, 1+sample % 2), minutes=50+10*((sample+index) % 4)),
                kickoff+timedelta(hours=3)))
        target = detail(event_id, decision+timedelta(hours=2), terminal="NS")
        raw.append((target, decision-timedelta(minutes=30)))
        rows = []
        for native, received in raw:
            event = _detail_event(native)
            records = (normalize_football_base_input(native, observed_at=received),) + normalize_football_context(
                event, injuries=[], lineups=[native] if native is target else [],
                appearances=[] if native is target else [native], observed_at=received)
            for record in records:
                append_observation(path, record, observed_at=received)
            rows.extend(observations_as_of(path, event["event_key"], cutoff=decision,
                                          schedule_revision=event["schedule_revision"]))
        event = _detail_event(target)
        history = tuple(row for row in rows if row["kind"] == "base_fixture")
        prepared.append((event, decision, history, tuple(rows)))
    identities = envelope("context-native-identity-map-v1", {"schema": 1, "policy": "native-source-only-v1",
        "bindings": [{"event_key": event["event_key"], "home_id": event["home_id"], "away_id": event["away_id"],
            "source_refs": [next(row["digest"] for row in history if row["event_key"] == event["event_key"])]}
            for event, _, history, _ in prepared]})
    def store(value):
        assert put_artifact(path, kind=value["kind"], payload=value["payload"], created_at=BUILT) == value["digest"]
        return value["digest"]
    store(identities)
    cases, config = [], None
    for index, (event, decision, history, rows) in enumerate(prepared):
        recipe = football_recipe(history)
        replay = replay_base_distribution("football", event, history, decision_at=decision,
            reconstructed_at=BUILT, recipe=recipe, identity_map=identities)
        base = replay["payload"]["base"]
        features = football_features(event, rows, base, cutoff=decision)
        name = "home.venue_attack.goals.api-football:player:1"
        if config is None:
            config = validate_family_config({"schema": 1, "sport": "football", "family": "football:goals:90min",
                "feature_version": features["version"], "feature_names": [name],
                "population": {"sport": "football", "competitions": ["39"], "formats": ["90min"],
                               "tours": [None], "surfaces": [None], "indoor": [None]},
                "coverage": features["coverage"], "model_variant": "football-roster-two-head-log-rate-v1",
                "base_versions": [base["version"]], "head_links": {"home": "log_rate", "away": "log_rate"},
                "reference_version": "football-context-reference-v2", "preprocessing_artifacts": {},
                "groups": {"roster": [name]}, "joint_calibration": {"kind": "identity"},
                "target_markets": ["RESULT_AWAY", "RESULT_DRAW", "RESULT_HOME"],
                "outcome_contract": "football-regulation-ft-v1", "train_end": canonical_timestamp(NOW-timedelta(days=7)),
                "tune_end": canonical_timestamp(NOW), "alpha_grid": [.01, .1, 1., 10., 100.]})
        result_time = decision + timedelta(hours=4)
        raw_result = detail(9000+index, decision+timedelta(hours=2), goals=((0, 1), (4, 0), (2, 2), (1, 0))[index % 4])
        result_ref = append_observation(path, normalize_football_outcome(event, raw_result, observed_at=result_time),
                                        observed_at=result_time)
        result = next(row for row in observations_as_of(path, event["event_key"], cutoff=BUILT,
                      schedule_revision=event["schedule_revision"]) if row["digest"] == result_ref)
        case = envelope("context-training-case-v1", {"schema": 1, "event": event, "base": base, "features": features,
            "replay_ref": store(replay), "outcome_ref": result_ref, "event_identity_hash": identities["digest"],
            "family_config_hash": digest(config), "preprocessing_refs": []})
        store(recipe)
        store(case)
        cases.append({"case": case, "artifacts": {o["digest"]: o for o in (recipe, replay, identities)},
                      "observations": rows+(result,)})
    assembly = assemble_training_cases(tuple(cases[:4]), config)
    fit = fit_family(assembly["rows"], config, cases=tuple(cases[:4]))
    assert fit["status"] == "fitted"
    for ref, effect in fit["candidate_artifacts"].items():
        assert store(envelope("context-effect-v1", effect)) == ref
    fit_ref = store(envelope("context-fit-v1", fit))
    member = lambda case: {"case_ref": case["case"]["digest"],
                           "observation_refs": sorted(row["digest"] for row in case["observations"])}
    dataset = {"schema": 1, "event_identity_hash": identities["digest"], "groups": [{
        "family_config_hash": digest(config), "training_cases": [member(c) for c in cases[:4]],
        "final_cases": [member(c) for c in cases[4:]], "unavailable_final": [], "fit_ref": None if control else fit_ref}]}
    dataset_ref = store(envelope("context-dataset-v1", dataset))
    definition = {"family_config_hash": digest(config), "ablation": "full", "target_markets": config["target_markets"],
                  "outcome_contract": config["outcome_contract"]}
    hypothesis = {**definition, "hypothesis_id": digest(definition),
                  "candidate_artifact": None if control else fit["effect_hash"],
                  "pretest_status": "baseline_control" if control else "ready"}
    plan = {"schema": 1, "dataset_hash": dataset_ref, "event_identity_hash": identities["digest"],
        "code_revision": "a"*40, "base_versions": config["base_versions"], "family_configs": [config],
        "train_end": config["train_end"], "tune_end": config["tune_end"],
        "test_blocks": [[canonical_timestamp(NOW+timedelta(days=d)), canonical_timestamp(NOW+timedelta(days=d+2))]
                        for d in (0, 2, 4)], "target_markets": config["target_markets"],
        "outcome_contracts": [config["outcome_contract"]], "candidate_artifacts": [] if control else [fit["effect_hash"]],
        "policy_version": "context-paired-hac-bh-v1", "availability_classes": ["prospective"],
        "created_at": canonical_timestamp(FROZEN), "hypotheses": [hypothesis],
        "test_inventory": [{"event": c["case"]["payload"]["event"], "decision_at": c["case"]["payload"]["base"]["cutoff"],
                           "block": f"test:{i}"} for i, c in enumerate(cases[4:])]}
    experiment_ref = freeze_experiment(path, plan, created_at=FROZEN)
    return {"path": path, "plan": plan, "experiment_ref": experiment_ref, "dataset": dataset,
            "cases": cases, "fit": fit, "hypothesis_id": hypothesis["hypothesis_id"]}


def copy_packet(original, directory):
    result = deepcopy(original)
    result["path"] = directory / "copy.db"
    with sqlite3.connect(original["path"]) as source, sqlite3.connect(result["path"]) as target:
        source.backup(target)
    return result
