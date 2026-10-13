"""Real SQLite command guards, including byte-faithful legacy replay.

These tests catch accepting a fresh oversized credit without a second explicit
confirmation, weakening signed event provenance, and mutating old money rows.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3

import pytest

from challenge_store import ChallengeLedger, SETTLEMENT_RULE_VERSION
from daily3_math import Daily3Error
from daily3_store import Daily3Store, _canonical
from test_daily3_store import DAY, NOW, SCOPE, command, placed


def _daily(tmp_path):
    store = Daily3Store(tmp_path/'daily.db', key=b'k'*32, clock=lambda: NOW)
    command(store, 'start')
    return store, placed(store)


def _challenge(tmp_path):
    ledger = ChallengeLedger(tmp_path/'challenge.db')
    ticket = ledger.record_manual_result('2026-09-12', 'Real booked ticket', 35.22, 3, 'LOST')
    ledger.reverse_settlement(ticket, reason='Actual result not yet final')
    return ledger, ticket


def _rows(path, table):
    with sqlite3.connect(path) as con:
        return con.execute('SELECT * FROM '+table+' ORDER BY 1').fetchall()


def _legacy_daily_credit(store, bet, *, action='b'*32):
    """Append the unchanged previously accepted v1 contract, test fixture only."""
    payload = dict(version=1, kind='settle', at=NOW.isoformat(), day=DAY,
                   args=dict(bet_id=bet, revision=2, returned_cents=84528, reference='Old real record'))
    raw = _canonical(payload)
    with store._connection() as con:
        days, actions, previous, _at = store._read(con, SCOPE)
        sequence = len(actions)+1
        mac = store._mac('event', [SCOPE, sequence, action, raw, previous])
        con.execute('INSERT INTO daily3_events VALUES (?,?,?,?,?,?)', (SCOPE, sequence, action, raw, previous, mac))
        con.execute('UPDATE daily3_heads SET sequence=?, tail=?, mac=? WHERE scope=?',
                    (sequence, mac, store._mac('head', [SCOPE, sequence, mac]), SCOPE))
    return payload


def _legacy_challenge_credit(ledger, ticket):
    """Construct a previously accepted signed 24.0-odds settlement, not a command."""
    at = datetime.now(timezone.utc).isoformat()
    with closing(ledger._connect()) as con:
        con.execute('BEGIN IMMEDIATE')
        balance = con.execute('SELECT current_balance_cents FROM challenge_settings').fetchone()[0]+84528
        con.execute('UPDATE challenge_tickets SET status=?, payout_cents=?, settled_at=?, settlement_odds=?, settlement_rule_version=?, settlement_note=? WHERE id=?',
                    ('WON', 84528, at, 24.0, SETTLEMENT_RULE_VERSION, 'Old real record', ticket))
        con.execute('UPDATE challenge_settings SET current_balance_cents=?, updated_at=?', (balance, at))
        ledger._record_transaction(con, created_at=at, kind='PAYOUT', amount_cents=84528,
                                   balance_after_cents=balance, ticket_id=ticket, note=f'Ticket #{ticket} settled WON')
        ledger._record_settlement_event(con, ticket_id=ticket, created_at=at, action='SETTLE',
            previous_status='PENDING', new_status='WON', previous_payout_cents=0,
            new_payout_cents=84528, settlement_odds=24.0, source='MANUAL_CONFIRMED', reason='Old real record')
        ledger._refresh_integrity_checkpoint(con)
        con.commit()


def test_daily_new_typo_credit_cannot_write_money(tmp_path):
    store, bet = _daily(tmp_path)
    before = _rows(store.path, 'daily3_events')
    with pytest.raises(Daily3Error, match='Zweitbestätigung'):
        command(store, 'settle', bet_id=bet, revision=2, returned_cents=24000, reference='Bookmaker')
    assert _rows(store.path, 'daily3_events') == before
    assert store.history(SCOPE)[DAY]['bets'][bet]['status'] == 'open'


@pytest.mark.parametrize('returned', [0, 1000, 2000, 2400, 2401])
def test_daily_normal_credit_and_one_cent_tolerance(tmp_path, returned):
    store, bet = _daily(tmp_path)
    command(store, 'settle', bet_id=bet, revision=2, returned_cents=returned, reference='Bookmaker')
    assert store.history(SCOPE)[DAY]['bets'][bet]['returned_cents'] == returned


@pytest.mark.parametrize('extra', [dict(adjustment_confirmed=False, adjustment_reason='Bonus credited'),
                                 dict(adjustment_confirmed=True, adjustment_reason=' '),
                                 dict(adjustment_confirmed=1, adjustment_reason='Bonus credited')])
def test_daily_second_flag_and_concrete_reason_are_both_required(tmp_path, extra):
    store, bet = _daily(tmp_path)
    before = _rows(store.path, 'daily3_events')
    with pytest.raises(Daily3Error):
        command(store, 'settle', bet_id=bet, revision=2, returned_cents=24000, reference='Bookmaker', **extra)
    assert _rows(store.path, 'daily3_events') == before


def test_daily_confirmed_adjustment_is_signed_replayable_and_idempotent(tmp_path):
    store, bet = _daily(tmp_path)
    args = dict(bet_id=bet, revision=2, returned_cents=24000, reference='Bookmaker #123',
                adjustment_confirmed=True, adjustment_reason='Bookmaker promotion credited separately')
    command(store, 'settle', action_id='c'*32, **args)
    before = _rows(store.path, 'daily3_events')
    command(store, 'settle', action_id='c'*32, **args)
    assert _rows(store.path, 'daily3_events') == before
    payload = json.loads(before[-1][3])
    assert payload['version'] == 2
    assert payload['args']['adjustment_confirmed'] is True
    assert payload['args']['adjustment_reason'] == 'Bookmaker promotion credited separately'
    reloaded = Daily3Store(store.path, key=b'k'*32, clock=lambda: NOW)
    assert reloaded.history(SCOPE)[DAY]['bets'][bet]['returned_cents'] == 24000
    with pytest.raises(Daily3Error):
        command(store, 'settle', action_id='c'*32, **dict(args, returned_cents=24001))


def test_daily_correction_guard_cannot_be_bypassed_by_old_reason_or_stale_revision(tmp_path):
    store, bet = _daily(tmp_path)
    command(store, 'settle', bet_id=bet, revision=2, returned_cents=2400, reference='First result')
    before = _rows(store.path, 'daily3_events')
    with pytest.raises(Daily3Error):
        command(store, 'correct', bet_id=bet, revision=3, returned_cents=24000, reference='New', reason='Typo correction')
    with pytest.raises(Daily3Error):
        command(store, 'correct', bet_id=bet, revision=2, returned_cents=24000, reference='New', reason='Correction',
                adjustment_confirmed=True, adjustment_reason='Promotion credit confirmed')
    assert _rows(store.path, 'daily3_events') == before
    command(store, 'correct', bet_id=bet, revision=3, returned_cents=24000, reference='New', reason='Correction',
            adjustment_confirmed=True, adjustment_reason='Promotion credit confirmed')
    assert store.history(SCOPE)[DAY]['bets'][bet]['returned_cents'] == 24000


def test_daily_legacy_excessive_credit_and_retry_remain_byte_faithful(tmp_path):
    store, bet = _daily(tmp_path)
    payload = _legacy_daily_credit(store, bet)
    before = _rows(store.path, 'daily3_events')
    assert store.history(SCOPE)[DAY]['bets'][bet]['returned_cents'] == 84528
    command(store, 'settle', action_id='b'*32, **payload['args'])
    assert _rows(store.path, 'daily3_events') == before


def test_daily_new_event_still_rejects_unknown_fields(tmp_path):
    store, bet = _daily(tmp_path)
    before = _rows(store.path, 'daily3_events')
    with pytest.raises(Daily3Error):
        command(store, 'settle', bet_id=bet, revision=2, returned_cents=24000, reference='New',
                adjustment_confirmed=True, adjustment_reason='Promotion credit confirmed', trusted=True)
    assert _rows(store.path, 'daily3_events') == before


@pytest.mark.parametrize('odds,payout', [(24.0, 845.28), (3.0, 845.28), (3.0001, 105.66)])
def test_challenge_new_higher_odds_or_credit_require_second_confirmation(tmp_path, odds, payout):
    ledger, ticket = _challenge(tmp_path)
    before = _rows(ledger.db_path, 'challenge_transactions')
    with pytest.raises(ValueError, match='second confirmation'):
        ledger.settle_ticket(ticket, 'WON', settlement_odds=odds, actual_payout=payout)
    assert _rows(ledger.db_path, 'challenge_transactions') == before
    assert ledger.get_ticket(ticket)['status'] == 'PENDING'


@pytest.mark.parametrize('status,odds,payout,want', [('WON', 3.0, 105.66, 105.66),
                                                  ('WON', 3.0, 105.67, 105.67),
                                                  ('WON', 2.0, 70.44, 70.44),
                                                  ('LOST', None, 0, 0), ('VOID', None, 35.22, 35.22)])
def test_challenge_normal_reduced_loss_void_one_cent_values(tmp_path, status, odds, payout, want):
    ledger, ticket = _challenge(tmp_path)
    result = ledger.settle_ticket(ticket, status, settlement_odds=odds, actual_payout=payout)
    assert result['payout'] == want
    assert ledger.verify_financial_ledger() == (True, None)


@pytest.mark.parametrize('confirm,reason', [(False, 'Bookmaker bonus credited'), (True, ''), (1, 'Bookmaker bonus credited')])
def test_challenge_second_flag_and_reason_required(tmp_path, confirm, reason):
    ledger, ticket = _challenge(tmp_path)
    before = _rows(ledger.db_path, 'challenge_transactions')
    with pytest.raises(ValueError):
        ledger.settle_ticket(ticket, 'WON', settlement_odds=24, actual_payout=845.28,
                             adjustment_confirmed=confirm, adjustment_reason=reason)
    assert _rows(ledger.db_path, 'challenge_transactions') == before


@pytest.mark.parametrize('odds', [3.0, 24.0])
def test_challenge_real_adjusted_credit_is_authenticated_not_hard_capped(tmp_path, odds):
    ledger, ticket = _challenge(tmp_path)
    prior = _rows(ledger.db_path, 'challenge_settlement_events')
    result = ledger.settle_ticket(ticket, 'WON', settlement_odds=odds, actual_payout=845.28,
        adjustment_confirmed=True, adjustment_reason='Bookmaker promotional bonus credited on voucher 123')
    assert result['payout'] == 845.28
    events = ledger.settlement_events(ticket)
    assert events[-1]['source'] == 'MANUAL_CONFIRMED_ADJUSTMENT'
    assert 'voucher 123' in events[-1]['reason']
    assert _rows(ledger.db_path, 'challenge_settlement_events')[:-1] == prior
    assert ledger.verify_financial_ledger() == (True, None)
    before = _rows(ledger.db_path, 'challenge_transactions')
    with pytest.raises(ValueError, match='already'):
        ledger.settle_ticket(ticket, 'WON', settlement_odds=odds, actual_payout=845.28,
            adjustment_confirmed=True, adjustment_reason='Bookmaker promotional bonus credited on voucher 123')
    assert _rows(ledger.db_path, 'challenge_transactions') == before


def test_challenge_correction_needs_its_own_second_confirmation(tmp_path):
    ledger, ticket = _challenge(tmp_path)
    ledger.settle_ticket(ticket, 'WON', settlement_odds=3, actual_payout=105.66)
    before = _rows(ledger.db_path, 'challenge_transactions')
    with pytest.raises(ValueError):
        ledger.correct_settlement(ticket, 'WON', settlement_odds=24, actual_payout=845.28, reason='Old correction reason')
    assert _rows(ledger.db_path, 'challenge_transactions') == before
    ledger.correct_settlement(ticket, 'WON', settlement_odds=24, actual_payout=845.28, reason='Correction',
        adjustment_confirmed=True, adjustment_reason='Bookmaker increased credit after documented bonus')
    assert ledger.settlement_events(ticket)[-1]['source'] == 'MANUAL_CORRECTION_ADJUSTMENT'
    assert ledger.verify_financial_ledger() == (True, None)


def test_challenge_legacy_high_odds_credit_stays_byte_faithful(tmp_path):
    ledger, ticket = _challenge(tmp_path)
    _legacy_challenge_credit(ledger, ticket)
    before_events = _rows(ledger.db_path, 'challenge_settlement_events')
    before_money = _rows(ledger.db_path, 'challenge_transactions')
    reloaded = ChallengeLedger(ledger.db_path)
    assert reloaded.verify_financial_ledger() == (True, None)
    assert reloaded.get_ticket(ticket)['payout'] == 845.28
    assert _rows(ledger.db_path, 'challenge_settlement_events') == before_events
    assert _rows(ledger.db_path, 'challenge_transactions') == before_money


@pytest.mark.parametrize('source', ['MANUAL_CONFIRMED_ADJUSTMENT', ' MANUAL_CONFIRMED_ADJUSTMENT '])
def test_challenge_caller_cannot_forge_confirmed_adjustment_provenance(tmp_path, source):
    ledger, ticket = _challenge(tmp_path)
    before = _rows(ledger.db_path, 'challenge_transactions')
    with pytest.raises(ValueError):
        ledger.settle_ticket(ticket, 'WON', actual_payout=105.66, source=source)
    assert _rows(ledger.db_path, 'challenge_transactions') == before
    assert ledger.verify_financial_ledger() == (True, None)


def test_challenge_confirmed_adjustment_is_authenticated_against_reason_tampering(tmp_path):
    ledger, ticket = _challenge(tmp_path)
    ledger.settle_ticket(ticket, 'WON', settlement_odds=24, actual_payout=845.28,
        adjustment_confirmed=True, adjustment_reason='Bookmaker promotional credit on voucher 123')
    with sqlite3.connect(ledger.db_path) as con:
        con.execute('DROP TRIGGER challenge_settlement_events_no_update')
        con.execute("UPDATE challenge_settlement_events SET reason='Forged reason' WHERE source='MANUAL_CONFIRMED_ADJUSTMENT'")
    assert ledger.verify_financial_ledger()[0] is False


def test_daily_confirmed_adjustment_is_authenticated_against_reason_tampering(tmp_path):
    store, bet = _daily(tmp_path)
    command(store, 'settle', bet_id=bet, revision=2, returned_cents=24000, reference='Voucher 123',
            adjustment_confirmed=True, adjustment_reason='Bookmaker promotional credit')
    with sqlite3.connect(store.path) as con:
        con.execute("UPDATE daily3_events SET payload=replace(payload, 'promotional', 'fabricated') WHERE sequence=4")
    with pytest.raises(Daily3Error):
        store.history(SCOPE)
