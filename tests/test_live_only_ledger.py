"""Offline Live-only policy binding, first receipt and native settlement compatibility."""
from contextlib import closing
import sqlite3

import pytest

import live_tip_ledger as ledger
import live_tip_surface as surface
from test_live_comparison_ledger import observation
from test_live_tip_ledger import NOW, Provider, fixture, goal, record, settle


LIVE_MODEL = 'live-restspiel-xg-neutral-split-v1'
LIVE_POLICY = 'first-displayed-live-market-xg-neutral-split-regulation-v1'


def written(db):
    with closing(sqlite3.connect(db)) as connection:
        return connection.execute('SELECT fixture_id,market,side,model_version,policy_version,status '
                                  'FROM live_tips ORDER BY id').fetchall()


def test_visible_live_only_selection_uses_new_policy_but_old_display_keeps_first_receipt(tmp_path, monkeypatch):
    db = tmp_path / 'live.db'
    writer = ledger.record_displayed_live_tip
    monkeypatch.setattr(ledger, 'record_displayed_live_tip', lambda **kw: writer(db_path=db, now=NOW, **kw))
    candidate, row = observation()
    surface.record_visible_analysis(candidate, row, snapshot_at=NOW, age_seconds=0)
    row['model_version'] = LIVE_MODEL
    surface.record_visible_analysis(candidate, row, snapshot_at=NOW, age_seconds=0)
    row['fixture_id'] = 124
    surface.record_visible_analysis(candidate, row, snapshot_at=NOW, age_seconds=0)
    assert written(db) == [
        (123, 'ft_result', 'home', 'live-comparison-source', ledger.COMPARISON_POLICY_VERSION, 'open'),
        (124, 'ft_result', 'home', LIVE_MODEL, LIVE_POLICY, 'open'),
    ]


@pytest.mark.parametrize('market,side,version,policy', [
    ('ft_result', 'home', 'legacy-model', LIVE_POLICY),
    ('ft_result', 'home', LIVE_MODEL + ':forged', LIVE_POLICY),
    ('ft_result', 'home', ' ' + LIVE_MODEL, LIVE_POLICY),
    ('ft_result', 'home', ' ' + LIVE_MODEL, ledger.COMPARISON_POLICY_VERSION),
    ('ft_result', 'home', LIVE_MODEL, ledger.COMPARISON_POLICY_VERSION),
    ('ft_result', 'home', LIVE_MODEL, None),
    ('red_next', 'home', LIVE_MODEL, ledger.POLICY_VERSION),
    ('red_next', 'home', LIVE_MODEL, LIVE_POLICY),
    ('ft_total', 'under_0_5', LIVE_MODEL, LIVE_POLICY),
])
def test_policy_model_mismatch_or_unavailable_market_never_creates_a_receipt(tmp_path, market, side, version, policy):
    db = tmp_path / 'live.db'
    with pytest.raises(ValueError):
        record(db, market, side, model_version=version, policy_version=policy)
    assert not db.exists()


def test_live_only_version_does_not_use_legacy_surface_without_a_supported_comparison(tmp_path, monkeypatch):
    db = tmp_path / 'live.db'
    writer = ledger.record_displayed_live_tip
    monkeypatch.setattr(ledger, 'record_displayed_live_tip', lambda **kw: writer(db_path=db, now=NOW, **kw))
    candidate, row = observation()
    candidate.market, candidate.selection = 'Noch ein Tor', 'Mindestens 1 weiteres Tor'
    row['model_version'] = LIVE_MODEL
    row.pop('live_comparison')
    surface.record_visible_analysis(candidate, row, snapshot_at=NOW, age_seconds=0)
    assert not db.exists()


def test_old_and_live_only_comparison_receipts_settle_without_changing_provider_route(tmp_path):
    db = tmp_path / 'live.db'
    for fid, version, policy in ((123, 'old-model', ledger.COMPARISON_POLICY_VERSION),
                                 (124, LIVE_MODEL, LIVE_POLICY)):
        assert record(db, 'ft_result', 'draw', fixture_id=fid, model_version=version, policy_version=policy)
        assert record(db, 'next_scorer', 'away', fixture_id=fid + 2, model_version=version, policy_version=policy)
    finals = {fid: fixture(fulltime=(0, 0) if fid < 125 else (1, 1), fixture_id=fid) for fid in range(123, 127)}
    provider = Provider(finals, {'response': [goal(10, 15), goal(20, 90, 9)]})
    assert settle(db, provider)['settled'] == 4
    assert provider.calls == [
        ('fixtures', {'id': 123}), ('fixtures', {'id': 124}), ('fixtures', {'id': 125}),
        ('fixtures/events', {'fixture': 125}), ('fixtures', {'id': 126}), ('fixtures/events', {'fixture': 126}),
    ]
    counts = [(fid, policy, status) for fid, _, _, _, policy, status in written(db)]
    assert counts == [(123, ledger.COMPARISON_POLICY_VERSION, 'won'), (125, ledger.COMPARISON_POLICY_VERSION, 'won'),
                      (124, LIVE_POLICY, 'won'), (126, LIVE_POLICY, 'won')]
