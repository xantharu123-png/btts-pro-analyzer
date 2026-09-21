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
