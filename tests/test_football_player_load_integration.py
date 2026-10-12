"""Real isolated storage/transport, with synthetic events and fitted effects."""
from copy import deepcopy
from datetime import timedelta
import shutil

import pytest

from context_models.contracts import ContextContractError, canonical_timestamp
from context_models.dataset import _reader
from context_models.football_joint_context import PLAYER_LOAD_FEATURE_VERSION, feature_coverage, joint_features
from context_models.football_training import _load_publication, relevant_receipts, build_joint_training_case
from context_observations import append_observation
from context_sources.football import _detail_event, normalize_football_context
from context_sources.outcomes import normalize_football_base_input
from context_training_helpers import NOW, detail
from test_football_joint_training import source_case
from test_football_joint_worker import fitted, snapshots


@pytest.fixture
def native_case(tmp_path_factory):
    # A full 22-player cohort and 24 fixtures meet the real baseline's league
    # minimum. Whole-event storage and the 512KiB transport cap still apply.
    import test_football_joint_training as helpers
    original_inventory = helpers.football_inventory
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(helpers, "football_inventory", lambda *args, **kwargs:
            original_inventory(*args, **{**kwargs, "count": 24}))
        return source_case(tmp_path_factory.mktemp("load-native"), patch)


@pytest.fixture
def isolated(native_case, tmp_path):
    source, case, config = deepcopy(native_case)
    path = tmp_path / "load.db"
    shutil.copyfile(source, path)
    return path, case, config


def national(path, *, observed=None):
    raw = detail(777001, NOW - timedelta(days=2), minutes=90)
    raw["league"]["id"] = 5
    raw["teams"]["home"]["id"] = 100
    raw["teams"]["away"]["id"] = 200
    for field in ("players", "lineups"):
        for block, team in zip(raw[field], (100, 200)):
            block["team"]["id"] = team
    received = observed or NOW - timedelta(days=2) + timedelta(hours=3)
    ev = _detail_event(raw)
    records = (normalize_football_base_input(raw, observed_at=received),) + normalize_football_context(
        ev, injuries=[], lineups=[], appearances=[raw], observed_at=received)
    return tuple(append_observation(path, row, observed_at=received) for row in records)


def load_config(config):
    config = deepcopy(config)
    config["feature_version"] = PLAYER_LOAD_FEATURE_VERSION
    config["coverage"] = feature_coverage(PLAYER_LOAD_FEATURE_VERSION)
    config["feature_names"] = ["load.home.reported_minutes_schedule_7d"]
    config["groups"] = {"load": config["feature_names"]}
    return config


def test_live_and_training_read_same_whole_national_pool_without_rewriting_baseline(isolated):
    import football_joint_worker as worker
    path, case, _ = isolated
    payload = case["case"]["payload"]
    added = national(path)
    with _reader(path) as connection:
        _, original, _ = _load_publication(connection, payload["replay_ref"], latest=canonical_timestamp(NOW + timedelta(hours=6)))
        packet = original.to_dict()
        old = worker._bounded_receipts(connection, packet, cutoff=canonical_timestamp(NOW))
        live = worker._bounded_receipts(connection, packet, cutoff=canonical_timestamp(NOW), include_player_load=True)
        train = relevant_receipts(connection, packet, cutoff=canonical_timestamp(NOW), include_player_load=True)
    assert live == train
    assert not set(added) & {row["digest"] for row in old}
    assert set(added) <= {row["digest"] for row in live}
    # Old source/pointer identities and club form stay untouched.
    before = joint_features(payload["event"], old, payload["base"], cutoff=NOW)
    after = joint_features(payload["event"], live, payload["base"], cutoff=NOW, version=PLAYER_LOAD_FEATURE_VERSION)
    for field in ("values", "states", "refs"):
        assert {k: v for k, v in after[field].items() if not k.startswith("load.")} == {
            k: v for k, v in before[field].items() if not k.startswith("roster.")}
    assert after["states"]["load.home.reported_minutes_schedule_7d"] == "available"
    player = [r["digest"] for r in live if r["kind"] == "appearance"
              and r["event_key"] == "api-football:football:777001" and r["subject_id"] == "api-football:player:1"]
    assert len(player) == 1 and player[0] in after["refs"]["load.home.reported_minutes_schedule_7d"]
    assert original.to_dict() == packet


def test_source_bound_rejects_whole_extra_pool_not_a_convenient_subset(isolated, monkeypatch):
    import football_joint_worker as worker
    from context_models.replay import ReplayUnavailable
    path, case, _ = isolated
    national(path)
    with _reader(path) as connection:
        _, original, _ = _load_publication(connection, case["case"]["payload"]["replay_ref"],
                                          latest=canonical_timestamp(NOW + timedelta(hours=6)))
        old = worker._bounded_receipts(connection, original.to_dict(), cutoff=canonical_timestamp(NOW))
        monkeypatch.setattr(worker, "MAX_SOURCE_RECEIPTS", len(old) + 2)
        with pytest.raises(ReplayUnavailable, match="joint_source_receipt_bound_exceeded"):
            worker._bounded_receipts(connection, original.to_dict(), cutoff=canonical_timestamp(NOW), include_player_load=True)


def test_load_training_case_resolves_real_source_and_is_read_only(isolated):
    from context_models.training_cases import assemble_training_cases
    path, case, config = isolated
    national(path)
    config = load_config(config)
    payload = case["case"]["payload"]
    before = path.read_bytes()
    built = build_joint_training_case(path, binding_ref=payload["replay_ref"], outcome_ref=payload["outcome_ref"],
        identity_ref=payload["event_identity_hash"], config=config, as_of=NOW + timedelta(hours=6))
    prepared = assemble_training_cases((built,), config)
    assert prepared["canonical_events"] == 1 and not prepared["excluded"]
    assert len(prepared["rows"]) == 2
    assert path.read_bytes() == before


def test_v3_fit_can_compute_internal_distribution_but_never_changes_public_baseline(isolated):
    import football_joint_worker as worker
    from context_snapshots import _decode_snapshot
    from context_snapshot_storage import freeze_reference_bytes
    path, case, config = isolated
    national(path)
    fitted((path, case, load_config(config)), names=["load.home.reported_minutes_schedule_7d"])
    got = worker.publish_joint_comparison(path, case["case"]["payload"]["replay_ref"], decision_at=NOW + timedelta(minutes=2))
    assert got["status"] == "comparison-stored" and got["role"] == "experimental"
    key = got["reference"]["key"]
    with _reader(path) as connection:
        raw = connection.execute("SELECT payload,payload_digest FROM context_snapshots WHERE key=?", (key,)).fetchone()
        saved = _decode_snapshot(key, *raw, reference_data=freeze_reference_bytes(raw[0], connection))
    result = saved["result"]
    assert result["comparison_markets"] != result["base_markets"]
    assert result["used_params"] == result["base_params"]
    assert result["used_markets"] == result["base_markets"] == case["case"]["payload"]["base"]["markets"]
    assert not result["certified_markets"] and result["approval_hash"] is None


def test_legacy_version_cannot_claim_new_player_load_vocabulary(isolated):
    from context_models.training_contracts import validate_family_config
    _, _, config = isolated
    config["feature_names"] = ["load.home.reported_minutes_schedule_7d"]
    config["groups"] = {"load": config["feature_names"]}
    with pytest.raises(ContextContractError, match="separate v3"):
        validate_family_config(config)
