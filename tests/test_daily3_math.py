from dataclasses import replace
from decimal import Decimal

import pytest

from daily3_math import (Daily3Bet, Daily3Error, MAX_CENTS, balance, decimal_odds,
                         format_chf, has_unfinished_bets, parse_chf, reserve_allowed)


def test_agreed_fifty_to_one_twenty_to_zero_is_minus_fifty_net():
    first = Daily3Bet('event1', 5000, 'settled', 12000)
    assert balance([first]).realised_cents == 7000
    assert balance([first]).available_cents == 12000
    reserved = reserve_allowed([first], event_id='event2', stake_cents=12000)
    assert reserved.available_cents == 0 and reserved.worst_net_cents == -5000
    second = Daily3Bet('event2', 12000, 'settled', 0)
    assert balance([first, second]).available_cents == 0
    assert balance([first, second]).realised_cents == -5000


def test_only_confirmed_return_is_reusable_and_reservation_is_not_double_charged():
    reserved = Daily3Bet('event1', 2000, 'reserved')
    opened = replace(reserved, status='open')
    assert balance([reserved]).available_cents == balance([opened]).available_cents == 3000
    assert balance([opened]).realised_cents == 0
    lost = replace(opened, status='settled', returned_cents=0)
    assert reserve_allowed([lost], event_id='event2', stake_cents=3000).available_cents == 0
    with pytest.raises(Daily3Error):
        reserve_allowed([lost], event_id='event2', stake_cents=3001)


@pytest.mark.parametrize('bad', [True, False, 0, -1, 0.5, 100.0, Decimal('100'), float('nan'), float('inf'), MAX_CENTS+1])
def test_no_invalid_or_fractional_cent_stake(bad):
    with pytest.raises(Daily3Error):
        reserve_allowed([], event_id='event1', stake_cents=bad)


@pytest.mark.parametrize(('text', 'expected'), [('50', 5000), ('20,50', 2050), ('0.01', 1), (' 0 ', 0)])
def test_exact_chf_input(text, expected):
    assert parse_chf(text) == expected


@pytest.mark.parametrize('text', ['NaN', 'Infinity', '0.001', '1e3', '-1', True, 50, '', '00', '1,234'])
def test_bad_chf_input(text):
    with pytest.raises(Daily3Error):
        parse_chf(text)


@pytest.mark.parametrize('price', ['1.0001', '1,12', '1.95', '20', '1000'])
def test_low_or_high_valid_quote_has_no_budget_or_model_gate(price):
    assert Decimal(decimal_odds(price)) > 1
    assert reserve_allowed([], event_id='event1', stake_cents=5000).available_cents == 0


@pytest.mark.parametrize('price', ['1', '0', '-2', 'NaN', 'Infinity', True, 1.9])
def test_invalid_price_is_format_error_not_forecast_filter(price):
    with pytest.raises(Daily3Error):
        decimal_odds(price)


def test_void_is_not_profit_or_a_fourth_slot():
    bets = [Daily3Bet(str(i), 1000, 'settled', 1000) for i in range(3)]
    assert balance(bets).realised_cents == 0 and balance(bets).available_cents == 5000
    with pytest.raises(Daily3Error, match='Wettslots'):
        reserve_allowed(bets, event_id='fourth', stake_cents=1)


def test_cancelled_reservation_releases_slot_but_open_reservation_does_not_expire():
    pending = Daily3Bet('event1', 5000, 'reserved')
    assert has_unfinished_bets([pending])
    with pytest.raises(Daily3Error):
        reserve_allowed([pending], event_id='event2', stake_cents=1)
    cancelled = replace(pending, status='cancelled')
    assert not has_unfinished_bets([cancelled])
    assert reserve_allowed([cancelled], event_id='event2', stake_cents=5000).available_cents == 0


def test_same_event_cannot_get_opposing_or_duplicate_stake():
    bet = Daily3Bet('canonical_event', 1000, 'reserved')
    with pytest.raises(Daily3Error, match='Spiel'):
        reserve_allowed([bet], event_id='canonical_event', stake_cents=1000)


def test_partial_returns_and_late_corrections_keep_real_losses_visible():
    first = Daily3Bet('event1', 5000, 'settled', 12000)
    second = Daily3Bet('event2', 12000, 'open')
    corrected = replace(first, returned_cents=2500)
    assert balance([corrected, second]).available_cents == -9500
    assert balance([corrected, second]).worst_net_cents == -14500
    with pytest.raises(Daily3Error):
        reserve_allowed([corrected, second], event_id='event3', stake_cents=1)
    assert format_chf(-9500) == '−CHF 95.00'


def test_pending_correction_and_voluntary_close_stop_new_reservations():
    reviewed = Daily3Bet('event1', 1000, 'settled', 1000, under_review=True)
    assert has_unfinished_bets([reviewed])
    with pytest.raises(Daily3Error):
        reserve_allowed([reviewed], event_id='event2', stake_cents=1)
    with pytest.raises(Daily3Error):
        reserve_allowed([], event_id='event1', stake_cents=1, closed=True)


def test_combined_money_overflow_is_not_silently_truncated():
    with pytest.raises(Daily3Error):
        balance([Daily3Bet('event1', 1, 'settled', MAX_CENTS)])
