"""Actual Streamlit flows: no synthetic ledger doubles or source-text tests."""
from streamlit.testing.v1 import AppTest

from test_money_payout_confirmation import _challenge, _daily, _rows
from test_daily3_store import DAY, SCOPE


def _daily_render(path):
    import streamlit as st
    from daily3_store import Daily3Store
    from daily3_ui import _saved_bet
    from test_daily3_store import NOW, DAY, SCOPE
    store = Daily3Store(path, key=b'k'*32, clock=lambda: NOW)
    if st.session_state.get('_daily3_notice'):
        level, notice = st.session_state.pop('_daily3_notice')
        getattr(st, level)(notice)
    bet = next(iter(store.history(SCOPE)[DAY]['bets'].values()))
    _saved_bet(st, store, SCOPE, DAY, bet)


def _challenge_render(path, correction=False):
    from challenge_store import ChallengeLedger
    from challenge_15k import _render_pending_ticket_actions, _render_history
    ledger = ChallengeLedger(path)
    if correction:
        _render_history(ledger)
    else:
        _render_pending_ticket_actions(ledger, key_prefix='guard')


def _field(app, kind, prefix):
    return next(item for item in getattr(app, kind) if str(item.key).startswith(prefix))


def _button(app, label):
    return next(item for item in app.button if item.label == label)


def test_daily_second_step_only_for_higher_credit_and_bound_to_amount(tmp_path):
    store, bet = _daily(tmp_path)
    app = AppTest.from_function(_daily_render, args=(str(store.path),)).run(timeout=30)
    assert not app.exception
    assert not any(str(item.key).startswith('adjusted-confirm:') for item in app.checkbox)
    _field(app, 'text_input', 'returned:').set_value('240.00')
    _field(app, 'text_input', 'settled-ref:').set_value('Bookmaker voucher 123')
    _field(app, 'checkbox', 'settled-confirm:').check()
    before = _rows(store.path, 'daily3_events')
    _button(app, 'Abrechnung bestätigen').click().run()
    assert not app.exception
    assert _rows(store.path, 'daily3_events') == before
    assert _field(app, 'checkbox', 'adjusted-confirm:').value is False
    _field(app, 'checkbox', 'adjusted-confirm:').check()
    _field(app, 'text_input', 'adjusted-reason:').set_value('Documented bookmaker promotion')
    # A stale approval for 240 CHF must not also approve a new 241 CHF entry.
    _field(app, 'text_input', 'returned:').set_value('241.00')
    _button(app, 'Abrechnung bestätigen').click().run()
    assert not app.exception
    assert _rows(store.path, 'daily3_events') == before
    assert _field(app, 'checkbox', 'adjusted-confirm:').value is False
    _field(app, 'checkbox', 'adjusted-confirm:').check()
    _field(app, 'text_input', 'adjusted-reason:').set_value('Corrected promotion voucher 123')
    _button(app, 'Abrechnung bestätigen').click().run()
    assert not app.exception
    assert store.history(SCOPE)[DAY]['bets'][bet]['returned_cents'] == 24100


def test_challenge_high_odds_second_step_bound_to_actual_credit(tmp_path):
    ledger, ticket = _challenge(tmp_path)
    app = AppTest.from_function(_challenge_render, args=(ledger.db_path,)).run(timeout=30)
    assert not app.exception
    app.selectbox[0].select('Gewonnen').run()
    assert not any(str(item.key).startswith('guard_adjustment_confirmed:') for item in app.checkbox)
    _field(app, 'number_input', 'guard_settlement_odds').set_value(24.0).run()
    _field(app, 'number_input', 'guard_settlement_payout').set_value(845.28).run()
    assert not app.exception
    _field(app, 'checkbox', 'guard_settlement_confirmed').check().run()
    assert _button(app, 'Ergebnis verbuchen').disabled
    _field(app, 'checkbox', 'guard_adjustment_confirmed:').check().run()
    _field(app, 'text_input', 'guard_adjustment_reason:').set_value('Documented bookmaker promotion').run()
    assert not _button(app, 'Ergebnis verbuchen').disabled
    _field(app, 'number_input', 'guard_settlement_payout').set_value(846.00).run()
    assert _field(app, 'checkbox', 'guard_adjustment_confirmed:').value is False
    assert _button(app, 'Ergebnis verbuchen').disabled
    _field(app, 'checkbox', 'guard_adjustment_confirmed:').check().run()
    _field(app, 'text_input', 'guard_adjustment_reason:').set_value('Corrected promotion voucher 123').run()
    _button(app, 'Ergebnis verbuchen').click().run()
    assert not app.exception
    assert ledger.get_ticket(ticket)['payout'] == 846.00
    assert ledger.settlement_events(ticket)[-1]['source'] == 'MANUAL_CONFIRMED_ADJUSTMENT'


def test_challenge_correction_has_separate_amount_bound_confirmation(tmp_path):
    ledger, ticket = _challenge(tmp_path)
    ledger.settle_ticket(ticket, 'WON', actual_payout=105.66)
    app = AppTest.from_function(_challenge_render, args=(ledger.db_path, True)).run(timeout=30)
    assert not app.exception
    _field(app, 'selectbox', 'challenge_correction_action').select('Abrechnung korrigieren').run()
    _field(app, 'selectbox', 'challenge_correction_result').select('Gewonnen').run()
    assert not any(str(item.key).startswith('challenge_correction_adjustment_confirmed:') for item in app.checkbox)
    _field(app, 'number_input', 'challenge_correction_odds').set_value(24.0).run()
    _field(app, 'number_input', 'challenge_correction_payout').set_value(845.28).run()
    _field(app, 'text_input', 'challenge_correction_reason').set_value('Corrected bookmaker result').run()
    _field(app, 'checkbox', 'challenge_correction_confirmed').check().run()
    assert _button(app, 'Korrektur verbuchen').disabled
    _field(app, 'checkbox', 'challenge_correction_adjustment_confirmed:').check().run()
    _field(app, 'text_input', 'challenge_correction_adjustment_reason:').set_value('Bonus confirmed on voucher 123').run()
    _button(app, 'Korrektur verbuchen').click().run()
    assert not app.exception
    assert ledger.get_ticket(ticket)['payout'] == 845.28
    assert ledger.settlement_events(ticket)[-1]['source'] == 'MANUAL_CORRECTION_ADJUSTMENT'
