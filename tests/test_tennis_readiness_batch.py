"""Readiness consumes the same causal batch feature owner, never a future index."""
from datetime import timedelta

from context_models.readiness import audit_tennis_readiness
from test_tennis_live_training import packet
from test_tennis_live_worker import NOW
from test_tennis_training_batch import revision


def test_readiness_does_not_promote_future_player_membership(tmp_path):
    db, _, _, _, at = packet(tmp_path)
    baseline = audit_tennis_readiness(db, as_of=at, sample_limit=1)
    revision(db, '9000', NOW-timedelta(hours=2), (7001, 7002))
    revision(db, '9000', NOW+timedelta(hours=2), (100, 7002))
    actual = audit_tennis_readiness(db, as_of=at, sample_limit=1)
    assert actual['sample'] == baseline['sample']


def test_inventory_only_does_not_start_batch_discovery(tmp_path, monkeypatch):
    from context_models import tennis_training as impl
    db, _, _, _, at = packet(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('inventory-only started feature discovery')
    monkeypatch.setattr(impl, 'iter_live_tennis_features', forbidden, raising=False)
    result = audit_tennis_readiness(db, as_of=at, inventory_only=True)
    assert result['sample'] == [] and result['matching_final_events'] == 7


def test_readiness_two_cutoff_batch_excludes_early_key_and_keeps_all_later_revisions(tmp_path):
    """Actual readiness must apply each cutoff after shared discovery sees both."""
    db, originals, _, _, at = packet(tmp_path)
    baseline = audit_tennis_readiness(db, as_of=at, all_features=True, event_count=2)
    revision(db, '9000', NOW-timedelta(hours=2), (7001, 7002))
    revision(db, '9000', NOW+timedelta(hours=2), (100, 110))
    report = audit_tennis_readiness(db, as_of=at, all_features=True, event_count=2)
    assert [row['original_ref'] for row in report['sample']] == originals[:2]
    assert [row['cutoff'] for row in report['sample']] == [
        '2026-09-09T12:00:00.000000Z', '2026-09-10T12:00:00.000000Z']
    assert [row['references'] for row in baseline['sample']] == [7, 7]
    assert [row['references'] for row in report['sample']] == [7, 13]
    assert report['sample'][0] == baseline['sample'][0]
