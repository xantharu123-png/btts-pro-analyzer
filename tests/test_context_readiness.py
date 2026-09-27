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
