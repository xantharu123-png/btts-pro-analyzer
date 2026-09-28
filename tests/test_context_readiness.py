"""Diagnostic native inventory never turns repeated receipts into test games."""
from context_models.readiness import audit_tennis_readiness
from test_tennis_live_training import packet
import pytest


def test_readiness_counts_native_events_and_leaves_database_unchanged(tmp_path):
    db, _, _, _, at = packet(tmp_path)
    before = db.read_bytes()
    report = audit_tennis_readiness(db, as_of=at, sample_limit=2)
    assert report['original_publications'] == report['unique_original_events'] == 7
    assert report['matching_final_events'] == 7
    assert report['sample_limited'] and len(report['sample']) == 2
    assert report['qualified'] is False
    assert report['total_events_meet_test_count_floor_only'] is False
    assert all(row['measured']['bounded_sets_3d_delta'] is None for row in report['sample'])
    assert all(row['measured']['observed_recovery_minimum_hours_delta'] is not None for row in report['sample'])
    assert db.read_bytes() == before


@pytest.mark.parametrize('limit', [0, 101, True, 1.5])
def test_readiness_bounds_before_opening_or_creating_a_file(tmp_path, limit):
    db = tmp_path/'absent.db'
    with pytest.raises(ValueError):
        audit_tennis_readiness(db, as_of=None, sample_limit=limit)
    assert not db.exists()


def test_inventory_only_keeps_tours_separate_and_does_not_build_features(tmp_path, monkeypatch):
    db, _, _, _, at = packet(tmp_path)
    packet(tmp_path, tour='WTA')
    before = db.read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError('inventory must not build features or read test labels')
    monkeypatch.setattr('context_models.readiness.tennis_features_v4', forbidden)
    report = audit_tennis_readiness(db, as_of=at, inventory_only=True)
    assert report['tour_cohorts']['ATP']['matching_final_events'] == 7
    assert report['tour_cohorts']['WTA']['matching_final_events'] == 7
    assert not report['tour_cohorts']['WTA']['meets_test_count_floor_only']
    assert report['matching_final_events'] == 14
    assert sum(report['tour_cohorts']['ATP']['decision_days'].values()) == 7
    assert report['sample'] == [] and report['qualified'] is False
    assert db.read_bytes() == before


@pytest.mark.parametrize('value', [1, 0, None, 'yes'])
def test_inventory_flag_is_explicit_and_validated_before_opening(tmp_path, value):
    with pytest.raises(ValueError, match='boolean'):
        audit_tennis_readiness(tmp_path / 'absent.db', as_of=None, inventory_only=value)
    assert not (tmp_path / 'absent.db').exists()


def test_complete_feature_inventory_does_not_confuse_a_sample_with_coverage(tmp_path):
    db, _, _, _, at = packet(tmp_path)
    packet(tmp_path, tour='WTA')
    before = db.read_bytes()
    report = audit_tennis_readiness(db, as_of=at, sample_limit=2, all_features=True)
    assert len(report['sample']) == report['matching_final_events'] == 14
    assert report['sample_limited'] is False
    assert report['sample_policy'] == 'all-earliest-original-events-no-outcome-scoring'
    for tour in ('ATP', 'WTA'):
        cohort = report['feature_cohorts'][tour]
        assert cohort['evaluated_events'] == 7
        assert cohort['available']['bounded_sets_3d_delta'] == 0
        assert cohort['available']['observed_recovery_minimum_hours_delta'] == 7
        assert cohort['both_players_complete_sets_3d'] == 0
    assert report['qualified'] is False
    assert db.read_bytes() == before


@pytest.mark.parametrize('value', [1, 0, None, 'yes'])
def test_all_features_flag_is_validated_before_opening(tmp_path, value):
    with pytest.raises(ValueError, match='boolean'):
        audit_tennis_readiness(tmp_path / 'absent.db', as_of=None, all_features=value)
    assert not (tmp_path / 'absent.db').exists()


def test_inventory_only_and_all_features_cannot_silently_skip_the_requested_check(tmp_path):
    with pytest.raises(ValueError, match='mutually exclusive'):
        audit_tennis_readiness(tmp_path / 'absent.db', as_of=None, inventory_only=True, all_features=True)


def test_coarse_player_index_does_not_decode_every_repeated_source_body_in_python(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    db, _, _, _, at = packet(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('coarse index must use distinct small SQL projections')
    # Only the diagnostic's coarse index; physical/native validators remain real.
    monkeypatch.setattr('context_models.readiness.json', SimpleNamespace(loads=forbidden, dumps=json.dumps))
    report = audit_tennis_readiness(db, as_of=at, all_features=True)
    assert report['matching_final_events'] == len(report['sample']) == 7
    assert all(row['references'] > 0 for row in report['sample'])


def test_complete_inventory_can_run_in_disjoint_bounded_ranges_without_faking_full_coverage(tmp_path):
    db, _, _, _, at = packet(tmp_path)
    first = audit_tennis_readiness(db, as_of=at, all_features=True, event_offset=0, event_count=3)
    last = audit_tennis_readiness(db, as_of=at, all_features=True, event_offset=3, event_count=4)
    complete = audit_tennis_readiness(db, as_of=at, all_features=True)
    assert first['sample_limited'] and last['sample_limited']
    assert first['sample_policy'] == 'consecutive-range-earliest-original-time-order'
    assert first['feature_inventory_range'] == {'start': 0, 'stop': 3}
    assert last['feature_inventory_range'] == {'start': 3, 'stop': 7}
    assert {r['event_key'] for r in first['sample']}.isdisjoint(r['event_key'] for r in last['sample'])
    assert first['sample']+last['sample'] == complete['sample']
    for key in complete['feature_cohorts']['ATP']['available']:
        assert first['feature_cohorts']['ATP']['available'][key]+last['feature_cohorts']['ATP']['available'][key] == complete['feature_cohorts']['ATP']['available'][key]
    assert not any(report['qualified'] for report in (first, last, complete))


@pytest.mark.parametrize('offset,count', [(True, 3), (-1, 3), (0, True), (0, 0), (0, 101)])
def test_inventory_range_is_bounded_before_opening(tmp_path, offset, count):
    with pytest.raises(ValueError):
        audit_tennis_readiness(tmp_path/'absent.db', as_of=None, all_features=True,
                              event_offset=offset, event_count=count)
    assert not (tmp_path/'absent.db').exists()
