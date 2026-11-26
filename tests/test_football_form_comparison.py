from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from time import monotonic

import pytest


CAPTURED = datetime(2026, 11, 26, 9, tzinfo=timezone.utc)
RECORDED = CAPTURED + timedelta(minutes=2)
KICKOFF = CAPTURED + timedelta(hours=8)
FINAL = KICKOFF + timedelta(hours=2)


def pair(**overrides):
    return {
        'fixture_id': 101, 'league_id': 61, 'home_id': 12, 'away_id': 13,
        'kickoff': KICKOFF.isoformat(), 'captured_at': CAPTURED.isoformat(),
        'model_version': 'challenge-engine:legacy-form-strength-joint-calibration-v1',
        'model_scope': 'same_competition',
        'with_form': (0.6, 0.3, 0.1), 'without_form': (0.4, 0.3, 0.3),
        **overrides,
    }


def final(**overrides):
    return {
        'fixture': {'id': 101, 'date': KICKOFF.isoformat(), 'status': {'short': 'FT'}},
        'league': {'id': 61}, 'teams': {'home': {'id': 12}, 'away': {'id': 13}},
        'goals': {'home': 2, 'away': 1}, 'score': {'fulltime': {'home': 2, 'away': 1}},
        **overrides,
    }


def test_missing_sidecar_read_and_settlement_do_not_create_file(tmp_path):
    from football_form_comparison import league_report, settle_pairs

    path = tmp_path / 'form.db'
    assert settle_pairs(path, final(), observed_at=FINAL)['status'] == 'missing'
    assert league_report(path) == {'status': 'missing', 'stored': 0, 'settled': 0, 'open': 0, 'groups': []}
    assert not path.exists()


@pytest.mark.parametrize('change', [
    {'fixture_id': True}, {'away_id': 12}, {'league_id': 2**63},
    {'kickoff': '2026-11-26T17:00'}, {'captured_at': '2026-11-26T09:03:00+00:00'},
    {'kickoff': RECORDED.isoformat()}, {'with_form': (0.6, 0.3, 0.2)},
    {'without_form': (float('nan'), 0.4, 0.6)}, {'model_scope': 'senior_national_pooled'},
])
def test_malformed_or_nonprospective_pair_is_not_stored(tmp_path, change):
    from football_form_comparison import append_pairs, league_report

    path = tmp_path / 'form.db'
    assert append_pairs(path, [pair(**change)], recorded_at=RECORDED)['rejected'] == 1
    assert league_report(path)['stored'] == 0
    assert not path.exists()


def test_duplicate_and_conflicting_replay_preserve_first_probabilities(tmp_path):
    from football_form_comparison import append_pairs, league_report, settle_pairs

    path = tmp_path / 'form.db'
    assert append_pairs(path, [pair()], recorded_at=RECORDED)['inserted'] == 1
    assert append_pairs(path, [pair()], recorded_at=RECORDED + timedelta(minutes=2))['duplicates'] == 1
    assert append_pairs(path, [pair(with_form=(0.2, 0.3, 0.5))], recorded_at=RECORDED)['conflicts'] == 1
    assert append_pairs(path, [pair(home_id=13, away_id=12, model_version='different')], recorded_at=RECORDED)['conflicts'] == 1
    assert settle_pairs(path, final(), observed_at=FINAL)['settled'] == 1
    group, = league_report(path)['groups']
    assert group['markets']['X2']['with_form_expected'] == pytest.approx(0.4)


@pytest.mark.parametrize('change', [
    {'fixture': {'id': 102, 'date': KICKOFF.isoformat(), 'status': {'short': 'FT'}}},
    {'fixture': {'id': 101, 'date': (KICKOFF + timedelta(seconds=1)).isoformat(), 'status': {'short': 'FT'}}},
    {'teams': {'home': {'id': 13}, 'away': {'id': 12}}},
    {'league': {'id': 62}}, {'league': {}},
    {'fixture': {'id': 101, 'date': KICKOFF.isoformat(), 'status': {'short': 'AET'}}},
    {'fixture': {'id': 101, 'date': KICKOFF.isoformat(), 'status': {'short': 'PEN'}}},
    {'goals': {'home': 2, 'away': None}}, {'goals': {'home': True, 'away': 1}},
    {'score': {'fulltime': {'home': 1, 'away': 2}}},
    {'fixture': {'id': 101, 'date': KICKOFF.isoformat(), 'status': {'short': 'FT'},
                 'timestamp': int(KICKOFF.timestamp()) + 1}},
    {'score': {'fulltime': {'home': 2, 'away': 1}, 'extratime': {'home': 0, 'away': None}}},
    {'score': {'fulltime': {'home': 2, 'away': 1}, 'penalty': {'home': None, 'away': 5}}},
])
def test_unbound_or_nonregulation_final_leaves_pair_open(tmp_path, change):
    from football_form_comparison import append_pairs, league_report, settle_pairs

    path = tmp_path / 'form.db'
    append_pairs(path, [pair()], recorded_at=RECORDED)
    assert settle_pairs(path, final(**change), observed_at=FINAL)['settled'] == 0
    assert league_report(path)['open'] == 1


def test_result_is_first_verified_final_and_cannot_be_rewritten(tmp_path):
    from football_form_comparison import append_pairs, league_report, settle_pairs

    path = tmp_path / 'form.db'
    append_pairs(path, [pair()], recorded_at=RECORDED)
    assert settle_pairs(path, final(), observed_at=KICKOFF)['settled'] == 0
    # Fulltime may be omitted, but the native FT flag and integer goals may not.
    assert settle_pairs(path, final(score={}), observed_at=FINAL)['status'] == 'settled'
    assert settle_pairs(path, final(), observed_at=FINAL + timedelta(minutes=2))['status'] == 'unchanged'
    assert settle_pairs(path, final(goals={'home': 1, 'away': 2}, score={}), observed_at=FINAL)['status'] == 'conflict'
    assert league_report(path)['groups'][0]['markets']['1']['hits'] == 1


def test_grouped_expected_hits_and_brier_use_identical_settled_matches(tmp_path):
    from football_form_comparison import append_pairs, league_report, settle_pairs

    path = tmp_path / 'form.db'
    append_pairs(path, [pair(), pair(fixture_id=102), pair(fixture_id=103, league_id=62),
                        pair(fixture_id=104, model_version='previous'),
                        pair(fixture_id=105, model_scope='cross_competition_provisional_forecast')], recorded_at=RECORDED)
    settle_pairs(path, final(), observed_at=FINAL)
    report = league_report(path)
    assert (report['stored'], report['settled'], report['open']) == (5, 1, 4)
    assert len(report['groups']) == 4
    group, = [group for group in report['groups'] if group['settled']]
    assert (group['stored'], group['settled'], group['open']) == (2, 1, 1)
    assert group['brier_1x2'] == pytest.approx({'with_form': 0.26, 'without_form': 0.54})
    expected = {'1': (1, 0.6, 0.4), 'X': (0, 0.3, 0.3), '2': (0, 0.1, 0.3),
                '1X': (1, 0.9, 0.7), 'X2': (0, 0.4, 0.6), '12': (1, 0.7, 0.7)}
    for name, (hits, active, season) in expected.items():
        market = group['markets'][name]
        assert market == pytest.approx({'hits': hits, 'with_form_expected': active,
                                       'without_form_expected': season, 'with_form_brier': (hits - active)**2,
                                       'without_form_brier': (hits - season)**2})
    assert all(g['brier_1x2']['with_form'] is None for g in report['groups'] if not g['settled'])
    assert json.loads(json.dumps(report, allow_nan=False)) == report


def test_capacity_never_evicts_frozen_pairs(tmp_path, monkeypatch):
    import football_form_comparison as store

    monkeypatch.setattr(store, 'MAX_PAIRS', 2)
    path = tmp_path / 'form.db'
    first = store.append_pairs(path, [pair(), pair(fixture_id=102), pair(fixture_id=103)], recorded_at=RECORDED)
    assert (first['inserted'], first['capacity_skipped']) == (2, 1)
    assert store.append_pairs(path, [pair()], recorded_at=RECORDED)['duplicates'] == 1
    assert store.settle_pairs(path, final(), observed_at=FINAL)['settled'] == 1
    assert store.league_report(path)['stored'] == 2


def test_corrupt_stored_probability_cannot_be_reported_as_model_evidence(tmp_path):
    from football_form_comparison import append_pairs, league_report, settle_pairs

    path = tmp_path / 'form.db'
    append_pairs(path, [pair()], recorded_at=RECORDED)
    settle_pairs(path, final(), observed_at=FINAL)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute('UPDATE form_pairs SET with_home=20.0')
    with pytest.raises(ValueError, match='probabilities'):
        league_report(path)


def test_a_revised_kickoff_settles_only_its_own_stored_pair(tmp_path):
    from football_form_comparison import append_pairs, league_report, settle_pairs

    path = tmp_path / 'form.db'
    moved = (KICKOFF + timedelta(days=1)).astimezone(timezone(timedelta(hours=1)))
    append_pairs(path, [pair(), pair(kickoff=moved.isoformat(), with_form=(0.2, 0.1, 0.7))], recorded_at=RECORDED)
    result = final(fixture={'id': 101, 'date': moved.astimezone(timezone.utc).isoformat(), 'status': {'short': 'FT'}},
                   goals={'home': 1, 'away': 2}, score={'fulltime': {'home': 1, 'away': 2}})
    assert settle_pairs(path, result, observed_at=FINAL + timedelta(days=1))['settled'] == 1
    group, = league_report(path)['groups']
    assert (group['stored'], group['open']) == (2, 1)
    assert group['markets']['X2']['hits'] == 1
    assert group['markets']['X2']['with_form_expected'] == pytest.approx(0.8)


def test_native_agreeing_timestamp_and_absent_extra_period_scores_can_settle(tmp_path):
    from football_form_comparison import append_pairs, settle_pairs

    path = tmp_path / 'form.db'
    append_pairs(path, [pair()], recorded_at=RECORDED)
    result = final(fixture={'id': 101, 'date': KICKOFF.isoformat(), 'timestamp': int(KICKOFF.timestamp()),
                            'status': {'short': 'FT', 'elapsed': 90, 'extra': 7}},
                   score={'fulltime': {'home': 2, 'away': 1}, 'extratime': {'home': None, 'away': None},
                          'penalty': {'home': None, 'away': None}})
    assert settle_pairs(path, result, observed_at=FINAL)['settled'] == 1


def test_settlement_does_not_wait_on_a_busy_diagnostic_writer(tmp_path):
    from football_form_comparison import append_pairs, settle_pairs

    path = tmp_path / 'form.db'
    append_pairs(path, [pair()], recorded_at=RECORDED)
    with closing(sqlite3.connect(path)) as holder, holder:
        holder.execute('BEGIN IMMEDIATE')
        started = monotonic()
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            settle_pairs(path, final(), observed_at=FINAL)
        assert monotonic() - started < 1.0
    assert settle_pairs(path, final(), observed_at=FINAL)['settled'] == 1
