"""Source transport mechanics; synthetic fixtures are not effect validation."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError
from context_models.dataset import _reader
from context_models.football_joint_context import (
    FEATURE_VERSION, POOLED_FEATURE_VERSION, PLAYER_LOAD_FEATURE_VERSION, joint_features,
)
from context_models.football_source_stream import SOURCE_TRANSPORT, streamed_joint_sources
from context_models.football_training import _load_publication, joint_base, relevant_receipts
from context_models.replay import ReplayUnavailable
from context_training_helpers import NOW
from test_football_joint_training import native_case, source_case, joint_cohort


def _resolve(path, ref, *, version=FEATURE_VERSION):
    with _reader(path) as con:
        binding, original, _ = _load_publication(con, ref, latest=(NOW+timedelta(hours=6)).isoformat())
        base = joint_base(original, binding["payload"])
        return streamed_joint_sources(con, original.to_dict(), binding["payload"], base, feature_version=version)


@pytest.mark.parametrize("version", [FEATURE_VERSION, POOLED_FEATURE_VERSION, PLAYER_LOAD_FEATURE_VERSION])
def test_stream_features_are_byte_identical_to_complete_physical_oracle(native_case, version):
    path, case, _ = native_case
    with _reader(path) as con:
        binding, original, _ = _load_publication(con, case["case"]["payload"]["replay_ref"], latest=(NOW+timedelta(hours=6)).isoformat())
        base = joint_base(original, binding["payload"])
        rows = relevant_receipts(con, original.to_dict(), cutoff=base["cutoff"],
                                 include_player_load=version == PLAYER_LOAD_FEATURE_VERSION)
        projected = streamed_joint_sources(con, original.to_dict(), binding["payload"], base, feature_version=version)
        assert projected["source_transport"] == SOURCE_TRANSPORT
        assert projected["audit"]["receipt_count"] == len(rows)
        assert joint_features(binding["payload"]["native_event"], projected["observations"], base, cutoff=NOW, version=version) == joint_features(
            binding["payload"]["native_event"], rows, base, cutoff=NOW, version=version)


def test_stream_retains_frozen_consumed_and_inspected_rows(native_case):
    path, case, _ = native_case
    ref = case["case"]["payload"]["replay_ref"]
    projected = _resolve(path, ref)
    binding = case["artifacts"][ref]["payload"]
    expected = {row for field in ("consumed_receipts", "inspected_receipts") for group in binding[field].values() for row in group}
    assert expected <= {row["digest"] for row in projected["branches"]["binding"]}


def test_stream_raw_bound_does_not_change_legacy_admission(native_case, monkeypatch):
    import football_joint_worker as worker
    path, case, _ = native_case
    ref = case["case"]["payload"]["replay_ref"]
    monkeypatch.setattr(worker, "MAX_SOURCE_BYTES", 1)
    with _reader(path) as con:
        binding, original, _ = _load_publication(con, ref, latest=(NOW+timedelta(hours=6)).isoformat())
        base = joint_base(original, binding["payload"])
        with pytest.raises(ReplayUnavailable, match="joint_source_byte_bound_exceeded"):
            worker._bounded_receipts(con, original.to_dict(), cutoff=base["cutoff"])
        assert streamed_joint_sources(con, original.to_dict(), binding["payload"], base,
                                      feature_version=FEATURE_VERSION)["audit"]["receipt_count"] > 0


@pytest.mark.parametrize("bound, reason", [("MAX_RAW_BYTES", "physical_byte"), ("MAX_RAW_RECEIPTS", "receipt_bound"), ("MAX_BRANCH_RECEIPTS", "branch_bound|branch_receipt")])
def test_explicit_stream_limits_reject_the_whole_input(native_case, monkeypatch, bound, reason):
    import context_models.football_source_stream as stream
    path, case, _ = native_case
    monkeypatch.setattr(stream, bound, 1)
    with pytest.raises(ReplayUnavailable, match=reason):
        _resolve(path, case["case"]["payload"]["replay_ref"])


def test_unknown_stream_feature_contract_is_not_silently_accepted(native_case):
    path, case, _ = native_case
    with pytest.raises(ContextContractError, match="unknown"):
        _resolve(path, case["case"]["payload"]["replay_ref"], version="future-feature")


def test_stream_cannot_mix_independent_sqlite_reader_images(native_case):
    import sqlite3
    path, case, _ = native_case
    payload = case['case']['payload']
    binding = case['artifacts'][payload['replay_ref']]['payload']
    with sqlite3.connect(path) as con:
        assert not con.in_transaction
        with pytest.raises(ContextContractError, match='held physical reader transaction'):
            streamed_joint_sources(con, {}, binding, payload['base'], feature_version=FEATURE_VERSION)


def test_stream_training_case_keeps_all_physical_rows_not_a_hash_only_projection(native_case):
    from context_models.football_training import build_joint_training_case
    from context_models.training_contracts import validate_resolved_case
    path, original, config = native_case
    payload = original['case']['payload']
    actual = build_joint_training_case(path, binding_ref=payload['replay_ref'], outcome_ref=payload['outcome_ref'],
        identity_ref=payload['event_identity_hash'], config=config, as_of=NOW+timedelta(hours=6),
        source_transport=SOURCE_TRANSPORT)
    assert actual['case']['payload']['schema'] == 2
    assert actual['case']['payload']['source_transport'] == SOURCE_TRANSPORT
    assert actual['observations'] == original['observations']
    assert actual['case']['payload']['features'] == payload['features']
    assert validate_resolved_case(actual, config=config) == actual


def test_stream_case_cannot_be_mislabeled_as_legacy(native_case):
    from context_models.training_cases import case_header
    from context_training_helpers import envelope
    _, original, config = native_case
    changed = deepcopy(original)
    changed['case']['payload']['source_transport'] = SOURCE_TRANSPORT
    changed['case'] = envelope('context-training-case-v1', changed['case']['payload'])
    with pytest.raises(ContextContractError):
        case_header(changed, config=config)


def test_detached_versioned_case_cannot_bypass_expanded_materialization_bound(native_case, monkeypatch):
    import context_models.football_source_stream as stream
    from context_models.training_contracts import validate_resolved_case
    from context_training_helpers import envelope
    _, original, config = native_case
    changed = deepcopy(original)
    changed['case']['payload'].update(schema=2, source_transport=SOURCE_TRANSPORT)
    changed['case'] = envelope('context-training-case-v1', changed['case']['payload'])
    monkeypatch.setattr(stream, 'MAX_EXPANDED_SOURCE_BYTES', 1)
    with pytest.raises(ContextContractError, match='expanded source byte bound'):
        validate_resolved_case(changed, config=config)


@pytest.mark.parametrize('bad', ['text', [], None])
def test_stream_case_rejects_malformed_base_with_contract_error(native_case, bad):
    from context_models.training_cases import case_header
    from context_training_helpers import envelope
    _, original, config = native_case
    changed = deepcopy(original)
    changed['case']['payload'].update(schema=2, source_transport=SOURCE_TRANSPORT, base=bad)
    changed['case'] = envelope('context-training-case-v1', changed['case']['payload'])
    with pytest.raises(ContextContractError):
        case_header(changed, config=config)


def test_readiness_stream_is_explicit_and_retains_empirical_policy(native_case):
    from context_models.football_readiness import inspect_football_readiness
    path, original, config = native_case
    blocks = tuple((NOW+timedelta(days=day), NOW+timedelta(days=day+2)) for day in (4, 6, 8))
    requests = ({'binding_ref': original['case']['payload']['replay_ref']},)
    before = path.read_bytes()
    report = inspect_football_readiness(path, requests, config, test_blocks=blocks,
        as_of=NOW+timedelta(days=11), source_transport=SOURCE_TRANSPORT)
    assert report['source_transport'] == SOURCE_TRANSPORT
    assert report['source_complete_events'] == 1
    assert report['minimum_test_events'] == 200
    assert report['test_events'] == 0
    assert report['empirical_qualification'] == 'not_evaluated'
    assert report['events'][0]['source_processing']['receipt_count'] > 0
    assert path.read_bytes() == before


def test_new_physical_dataset_resolver_reconstructs_full_stream_case(tmp_path, monkeypatch):
    from context_models.dataset import resolve_case
    from context_models.football_training import build_joint_training_case
    from context_models.training_contracts import validate_resolved_case
    from model_artifacts import put_artifact
    path, original, config = source_case(tmp_path, monkeypatch, event_id=12000)
    payload = original['case']['payload']
    actual = build_joint_training_case(path, binding_ref=payload['replay_ref'], outcome_ref=payload['outcome_ref'],
        identity_ref=payload['event_identity_hash'], config=config, as_of=NOW+timedelta(hours=6), source_transport=SOURCE_TRANSPORT)
    ref = put_artifact(path, kind=actual['case']['kind'], payload=actual['case']['payload'], created_at=NOW+timedelta(hours=6))
    item = {'case_ref': ref, 'observation_refs': sorted(row['digest'] for row in actual['observations'])}
    from context_models.contracts import canonical_timestamp
    with _reader(path) as con:
        resolved = resolve_case(con, item, config=config,
            plan={'created_at': canonical_timestamp(NOW+timedelta(hours=6))}, latest=canonical_timestamp(NOW+timedelta(hours=7)))
    assert resolved['case'] == actual['case']
    assert {row['digest'] for row in resolved['observations']} == set(item['observation_refs'])
    assert validate_resolved_case(resolved, config=config) == resolved


def test_expanded_full_retention_is_rejected_before_materializing_the_pool(native_case, monkeypatch):
    import context_models.football_source_stream as stream
    path, case, _ = native_case
    ref = case['case']['payload']['replay_ref']
    monkeypatch.setattr(stream, 'MAX_EXPANDED_SOURCE_BYTES', 1)
    with _reader(path) as con:
        binding, original, _ = _load_publication(con, ref, latest=(NOW+timedelta(hours=6)).isoformat())
        base = joint_base(original, binding['payload'])
        with pytest.raises(ReplayUnavailable, match='expanded_byte_bound'):
            streamed_joint_sources(con, original.to_dict(), binding['payload'], base, feature_version=FEATURE_VERSION, retain_full=True)
        # Streaming feature processing itself need not retain the huge tuple.
        assert streamed_joint_sources(con, original.to_dict(), binding['payload'], base, feature_version=FEATURE_VERSION)['observations']


@pytest.mark.parametrize('change', ['repeated-clock', 'empty-withdrawal', 'team-correction'])
def test_load_projection_preserves_recovery_ties_and_withdrawals(tmp_path, monkeypatch, change):
    from context_models.contracts import OBSERVATION_FIELDS, canonical_timestamp
    from context_observations import append_observation_batch
    from context_sources.football import _empty_collection, _detail_event, normalize_football_context
    path, original_case, _ = source_case(tmp_path, monkeypatch, event_id=13000)
    ref = original_case['case']['payload']['replay_ref']
    historical = [row for row in original_case['observations'] if row['kind'] == 'appearance']
    native_key = max(historical, key=lambda row: row['payload']['scheduled_start'])['event_key']
    clock = NOW-timedelta(minutes=1)
    records = []
    if change == 'repeated-clock':
        for row in historical:
            if row['event_key'] == native_key:
                copied = {key: deepcopy(row[key]) for key in OBSERVATION_FIELDS}
                copied['valid_from'] = canonical_timestamp(clock)
                records.append(copied)
    elif change == 'empty-withdrawal':
        event = deepcopy(original_case['case']['payload']['event'])
        sample = next(row for row in historical if row['event_key'] == native_key)
        event.update(event_key=native_key, scheduled_start=sample['payload']['scheduled_start'], schedule_revision=sample['schedule_revision'], status='completed')
        records = [_empty_collection(event, 'api-football:team:1', 'appearance', observed_at=clock)]
    else:
        raw = deepcopy(next(row for row in original_case['observations'] if row['kind'] == 'base_fixture' and row['event_key'] == native_key)['payload']['detail'])
        raw['teams']['home']['id'] = 3
        raw['players'][0]['team']['id'] = 3
        raw['lineups'][0]['team']['id'] = 3
        records = list(normalize_football_context(_detail_event(raw), injuries=[], lineups=[], appearances=[raw], observed_at=clock))
    append_observation_batch(path, tuple((record, clock) for record in records))
    with _reader(path) as con:
        binding, original, _ = _load_publication(con, ref, latest=(NOW+timedelta(hours=6)).isoformat())
        base = joint_base(original, binding['payload'])
        result = streamed_joint_sources(con, original.to_dict(), binding['payload'], base,
                                        feature_version=PLAYER_LOAD_FEATURE_VERSION, retain_full=True)
        assert result['audit']['expanded_observation_bytes'] == len(__import__('model_artifacts').canonical_bytes(result['observations']))
        compact = joint_features(binding['payload']['native_event'], result['feature_observations'], base, cutoff=NOW, version=PLAYER_LOAD_FEATURE_VERSION)
        full = joint_features(binding['payload']['native_event'], result['observations'], base, cutoff=NOW, version=PLAYER_LOAD_FEATURE_VERSION)
        assert compact == full


def test_stream_training_and_physical_evaluation_roundtrip_cannot_activate_small_cohort(joint_cohort):
    from context_models.football_readiness import prepare_football_context
    from context_models.dataset import _reader
    from context_models.evaluator import verify_evaluation
    path, cases, config, built = joint_cohort
    blocks = tuple((NOW+timedelta(days=day), NOW+timedelta(days=day+2)) for day in (4, 6, 8))
    result = prepare_football_context(path, tuple({'binding_ref': case['case']['payload']['replay_ref']} for case in cases),
        config, test_blocks=blocks, code_revision='a'*40, created_at=built+timedelta(hours=1),
        source_transport=SOURCE_TRANSPORT, evaluate=True)
    assert result['status'] == 'evaluated_not_activated'
    assert result['fit_status'] == 'fitted'
    assert result['readiness']['test_events'] == 3
    assert result['approval_count'] == 0 and result['activated'] is False
    with _reader(path) as con:
        report = verify_evaluation(con, result['evaluation_ref'])
        assert report['kind'] == 'context-evaluation-v1'
        assert con.execute("SELECT count(*) FROM artifacts WHERE kind='context-approval-v1'").fetchone()[0] == 0
        assert con.execute('SELECT count(*) FROM active_manifest').fetchone()[0] == 0


@pytest.mark.parametrize('revision', ['unrelated-later-schema', 'invalid-older-supported'])
def test_weather_projection_matches_schema_filter_and_validates_old_supported_rows(tmp_path, monkeypatch, revision):
    from context_models.contracts import digest
    from context_observations import append_observation_batch
    from context_sources.openweather import forecast_payload, normalize_forecast
    from model_artifacts import canonical_bytes
    path, case, _ = source_case(tmp_path, monkeypatch, event_id=14000)
    event = case['case']['payload']['event']
    from datetime import datetime
    payload = forecast_payload(event, city='Test', country='CH', latitude=47., longitude=8.,
        point={'dt': datetime.fromisoformat(event['scheduled_start']).timestamp(), 'main': {'temp': 17.}, 'wind': {'speed': 2.}})
    earlier, later = NOW-timedelta(minutes=10), NOW-timedelta(minutes=5)
    good = normalize_forecast(payload, observed_at=earlier)
    second = normalize_forecast(payload, observed_at=later)
    if revision == 'unrelated-later-schema':
        second['source_schema'] = 'unrelated-weather-v1'
    else:
        good['source_revision'] = 'f'*64
    append_observation_batch(path, ((good, earlier), (second, later)))
    with _reader(path) as con:
        binding, original, _ = _load_publication(con, case['case']['payload']['replay_ref'], latest=(NOW+timedelta(hours=6)).isoformat())
        base = joint_base(original, binding['payload'])
        if revision == 'invalid-older-supported':
            with pytest.raises(ContextContractError, match='city forecast source'):
                streamed_joint_sources(con, original.to_dict(), binding['payload'], base, feature_version=FEATURE_VERSION)
        else:
            result = streamed_joint_sources(con, original.to_dict(), binding['payload'], base, feature_version=FEATURE_VERSION, retain_full=True)
            compact = joint_features(event, result['feature_observations'], base, cutoff=NOW)
            full = joint_features(event, result['observations'], base, cutoff=NOW)
            assert canonical_bytes(compact) == canonical_bytes(full)
            assert compact['values']['weather.temperature_c'] == 17.


def test_older_invalid_native_roster_revision_is_not_hidden_by_a_later_good_row(tmp_path, monkeypatch):
    from context_models.contracts import OBSERVATION_FIELDS, canonical_timestamp
    from context_observations import append_observation_batch
    path, case, _ = source_case(tmp_path, monkeypatch, event_id=15000)
    row = next(row for row in case['observations'] if row['kind'] == 'appearance')
    earlier, later = NOW-timedelta(minutes=10), NOW-timedelta(minutes=5)
    bad, good = ({key: deepcopy(row[key]) for key in OBSERVATION_FIELDS} for _ in range(2))
    bad.update(valid_from=canonical_timestamp(earlier), source_revision='f'*64)
    good['valid_from'] = canonical_timestamp(later)
    append_observation_batch(path, ((bad, earlier), (good, later)))
    with pytest.raises(ContextContractError, match='source validity/receipt binding mismatch'):
        _resolve(path, case['case']['payload']['replay_ref'])
