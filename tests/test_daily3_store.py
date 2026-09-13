from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
import uuid

import pytest

from daily3_math import Daily3Error
from daily3_store import Daily3Store, Daily3IntegrityError, day_balance

SCOPE = 'a'*32
DAY = '2026-09-13'
NOW = datetime(2026, 9, 13, 10, tzinfo=timezone.utc)


def ident():
    return uuid.uuid4().hex


def snapshot(event='football:fixture:1', now=NOW):
    return dict(event_id=event, event_guard={'identity': event, 'aliases': []}, sport='football', event_label='Home vs Away', market_key='RESULT_HOME',
        market='Endergebnis', selection='Heimsieg', scheduled_start=(now+timedelta(hours=5)).isoformat(),
        signal_key=event+'-home', model_probability=.6, modeled_at=now.isoformat(), model_version='test-model',
        analysis_basis='Das Modell erwartet 2,0 zu 0,9 Tore.', analysis_caution='Ein früher Rückstand bleibt möglich.',
        policy_version='daily3-evidence-diversity-v1')


@pytest.fixture
def store(tmp_path):
    return Daily3Store(tmp_path/'daily3.db', key=b'k'*32, clock=lambda: NOW)


def command(store, kind, day=DAY, scope=SCOPE, action_id=None, **args):
    return store.command(scope, action_id=action_id or ident(), kind=kind, day=day, **args)


def reserve(store, amount=2000, event='football:fixture:1', **kwargs):
    bet_id = ident()
    command(store, 'reserve', bet_id=bet_id, stake_cents=amount, odds='1.12', snapshot=snapshot(event), **kwargs)
    return bet_id


def placed(store, amount=2000, event='football:fixture:1'):
    bet_id = reserve(store, amount, event)
    command(store, 'place', bet_id=bet_id, revision=1, reference='Buchmacher / Beleg 123')
    return bet_id


def test_complete_real_stake_fifty_one_twenty_zero_flow(store):
    command(store, 'start')
    first = placed(store, 5000)
    assert day_balance(store.history(SCOPE)[DAY]).available_cents == 0
    command(store, 'settle', bet_id=first, revision=2, returned_cents=12000, reference='Tatsächlich gutgeschrieben 120 CHF')
    second = placed(store, 12000, 'football:fixture:2')
    command(store, 'settle', bet_id=second, revision=2, returned_cents=0, reference='Verloren / abgerechnet')
    state = day_balance(store.history(SCOPE)[DAY])
    assert (state.realised_cents, state.available_cents, state.placed_count) == (-5000, 0, 2)
    with pytest.raises(Daily3Error):
        reserve(store, 1, 'football:fixture:3')


def test_two_independent_connections_cannot_spend_same_budget_twice(store):
    command(store, 'start')
    def attempt(index):
        other = Daily3Store(store.path, key=b'k'*32, clock=lambda: NOW)
        try:
            reserve(other, 3000, f'football:fixture:{index}')
            return True
        except Daily3Error:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, (1, 2))) == [False, True]
    assert day_balance(store.history(SCOPE)[DAY]).available_cents == 2000


def test_duplicate_actions_do_not_reissue_daily_budget_or_returns(store):
    action = ident()
    command(store, 'start', action_id=action)
    command(store, 'start', action_id=action)
    with pytest.raises(Daily3Error):
        command(store, 'start')
    bet = placed(store)
    action = ident()
    args = dict(bet_id=bet, revision=2, returned_cents=5000, reference='Beleg')
    command(store, 'settle', action_id=action, **args)
    command(store, 'settle', action_id=action, **args)
    assert day_balance(store.history(SCOPE)[DAY]).available_cents == 8000
    with pytest.raises(Daily3Error):
        command(store, 'settle', action_id=action, **dict(args, returned_cents=6000))


def test_stale_tab_cannot_correct_newer_result(store):
    command(store, 'start')
    bet = placed(store)
    command(store, 'settle', bet_id=bet, revision=2, returned_cents=1000, reference='Teilrückzahlung')
    with pytest.raises(Daily3Error, match='veraltet'):
        command(store, 'correct', bet_id=bet, revision=2, returned_cents=5000, reference='alt', reason='alt')
    assert day_balance(store.history(SCOPE)[DAY]).realised_cents == -1000


def test_reservation_not_released_by_restart_time_or_voluntary_close(store):
    command(store, 'start')
    bet = reserve(store, 5000)
    command(store, 'close')
    reloaded = Daily3Store(store.path, key=b'k'*32, clock=lambda: NOW+timedelta(days=1))
    with pytest.raises(Daily3Error):
        command(reloaded, 'start', day='2026-09-14')
    with pytest.raises(Daily3Error):
        command(reloaded, 'cancel', bet_id=bet, revision=1, not_placed=False)
    command(reloaded, 'cancel', bet_id=bet, revision=1, not_placed=True)
    command(reloaded, 'start', day='2026-09-14')
    history = reloaded.history(SCOPE)
    assert history[DAY]['closed'] and day_balance(history['2026-09-14']).available_cents == 5000


def test_no_fourth_bet_even_after_void_and_no_event_opposites(store):
    command(store, 'start')
    first = placed(store, 1000)
    with pytest.raises(Daily3Error, match='Spiel'):
        reserve(store, 1000)
    for index in range(3):
        bet = first if index == 0 else placed(store, 1000, f'football:fixture:{index+1}')
        command(store, 'settle', bet_id=bet, revision=2, returned_cents=1000, reference='Void')
    with pytest.raises(Daily3Error, match='Wettslots'):
        reserve(store, 1, 'football:fixture:4')


def test_correction_retains_negative_balance_and_old_evidence(store):
    command(store, 'start')
    first = placed(store, 5000)
    command(store, 'settle', bet_id=first, revision=2, returned_cents=12000, reference='Erste Abrechnung')
    placed(store, 12000, 'football:fixture:2')
    command(store, 'review', bet_id=first, revision=3, reason='Buchmacher prüft erneut')
    with pytest.raises(Daily3Error):
        reserve(store, 1, 'football:fixture:3')
    command(store, 'correct', bet_id=first, revision=4, returned_cents=2500, reference='Neuer Beleg', reason='Teil-Void korrigiert')
    assert day_balance(store.history(SCOPE)[DAY]).available_cents == -9500
    with sqlite3.connect(store.path) as con:
        raw = '\n'.join(row[0] for row in con.execute('SELECT payload FROM daily3_events'))
    assert 'Erste Abrechnung' in raw and 'Neuer Beleg' in raw


def test_actual_outside_limit_bet_is_recorded_not_disguised_as_approved(store):
    command(store, 'start')
    command(store, 'external', bet_id=ident(), stake_cents=8000, odds='1.12', snapshot=snapshot(),
            reference='Bereits extern platziert', reason='Nicht vorgemerkt')
    state = day_balance(store.history(SCOPE)[DAY])
    assert state.available_cents == -3000 and state.worst_net_cents == -8000
    with pytest.raises(Daily3Error):
        reserve(store, 1, 'football:fixture:3')


@pytest.mark.parametrize('start', ['2026-03-28T23:30:00+00:00', '2026-10-24T22:30:00+00:00'])
def test_zurich_day_uses_server_time_through_dst(store, start):
    instant = datetime.fromisoformat(start)
    store.clock = lambda: instant
    day = '2026-03-29' if '03-' in start else '2026-10-25'
    command(store, 'start', day=day)
    store.clock = lambda: instant+timedelta(hours=3)
    with pytest.raises(Daily3Error):
        command(store, 'start', day=day)
    assert len(store.history(SCOPE)) == 1


def test_immutable_forecast_and_odds_are_not_overwritten_by_caller_or_refresh(store):
    command(store, 'start')
    snap = snapshot()
    bet = ident()
    command(store, 'reserve', bet_id=bet, stake_cents=1000, odds='1.12', snapshot=snap)
    snap['model_probability'] = .99
    history = store.history(SCOPE)
    history[DAY]['bets'][bet]['odds'] = '9'
    assert store.history(SCOPE)[DAY]['bets'][bet]['snapshot']['model_probability'] == .6
    assert store.history(SCOPE)[DAY]['bets'][bet]['odds'] == '1.12'


@pytest.mark.parametrize('attack', ['payload', 'truncate', 'half_sequence', 'drop_head', 'swap_scope'])
def test_changed_or_truncated_history_is_rejected(store, attack):
    command(store, 'start')
    reserve(store)
    with sqlite3.connect(store.path) as con:
        if attack == 'payload':
            con.execute("UPDATE daily3_events SET payload=replace(payload, '2000', '200') WHERE sequence=2")
        elif attack == 'truncate':
            old = con.execute('SELECT mac FROM daily3_events WHERE sequence=1').fetchone()[0]
            con.execute('DELETE FROM daily3_events WHERE sequence=2')
            con.execute('UPDATE daily3_heads SET sequence=1, tail=?', (old,))
        elif attack == 'half_sequence':
            con.execute('UPDATE daily3_heads SET sequence=2.5')
        elif attack == 'drop_head':
            con.execute('DELETE FROM daily3_heads')
        else:
            con.execute('UPDATE daily3_events SET scope=?', ('b'*32,))
            con.execute('UPDATE daily3_heads SET scope=?', ('b'*32,))
    target = 'b'*32 if attack == 'swap_scope' else SCOPE
    with pytest.raises(Daily3IntegrityError):
        store.history(target)


def test_consistent_backup_restores_open_liabilities_and_rejects_wrong_key(store, tmp_path):
    command(store, 'start')
    placed(store, 3000)
    destination = tmp_path/'restored.db'
    store.backup(destination)
    restored = Daily3Store(destination, key=b'k'*32, clock=lambda: NOW)
    assert restored.history(SCOPE) == store.history(SCOPE)
    assert day_balance(restored.history(SCOPE)[DAY]).available_cents == 2000
    with pytest.raises(Daily3IntegrityError):
        Daily3Store(destination, key=b'z'*32).history(SCOPE)


@pytest.mark.parametrize('scope', ['', 'anonymous', 'a'*31, 'A'*32, None])
def test_missing_scope_never_creates_an_anonymous_account(store, scope):
    with pytest.raises(Daily3Error):
        command(store, 'start', scope=scope)


def test_scopes_are_separate_and_clock_rollback_cannot_reopen_budget(store):
    command(store, 'start')
    assert store.history('b'*32) == {}
    command(store, 'start', scope='b'*32)
    store.clock = lambda: NOW-timedelta(seconds=1)
    with pytest.raises(Daily3Error, match='Serverzeit'):
        reserve(store)


def test_native_event_upgrade_cannot_bypass_transactional_slot_guard(store):
    from dataclasses import replace
    from test_daily3_selection import tennis
    from daily3_selection import daily3_choices
    command(store, 'start')
    native = tennis(now=NOW)
    weak = replace(native, fixture_source=None, provider_event_id=None, competitor_a_id=None, competitor_b_id=None)
    first = daily3_choices([weak], now=NOW)[0].snapshot()
    upgraded = daily3_choices([native], now=NOW)[0].snapshot()
    command(store, 'reserve', bet_id=ident(), stake_cents=1000, odds='1.12', snapshot=first)
    with pytest.raises(Daily3Error, match='Spielzuordnung'):
        command(store, 'reserve', bet_id=ident(), stake_cents=1000, odds='1.12', snapshot=upgraded)
    assert day_balance(store.history(SCOPE)[DAY]).used_slots == 1


def test_late_external_prior_day_liability_blocks_an_already_started_new_day(store):
    command(store, 'start')
    tomorrow = NOW+timedelta(days=1)
    store.clock = lambda: tomorrow
    command(store, 'start', day='2026-09-14')
    external = dict(snapshot(), model_probability=None, modeled_at=None, model_version=None,
                    policy_version='external-bookmaker-record-v1')
    bet = ident()
    command(store, 'external', bet_id=bet, stake_cents=1000, odds='1.12', snapshot=external,
            reference='Alter tatsächlich platzierter Beleg', reason='Verspäteter Nachtrag')
    today_bet = dict(bet_id=ident(), stake_cents=1000, odds='1.12', snapshot=snapshot('new-event', now=tomorrow))
    with pytest.raises(Daily3Error, match='Vortags'):
        command(store, 'reserve', day='2026-09-14', **today_bet)
    command(store, 'settle', bet_id=bet, revision=1, returned_cents=0, reference='Tatsächlich abgerechnet')
    command(store, 'reserve', day='2026-09-14', **today_bet)
    assert store.history(SCOPE)[DAY]['bets'][bet]['snapshot']['model_probability'] is None
    assert day_balance(store.history(SCOPE)['2026-09-14']).available_cents == 4000
