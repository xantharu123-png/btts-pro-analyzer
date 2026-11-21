from datetime import datetime, timedelta, timezone

import pytest

from daily_accumulator_surface import customer_cards, quote_status


NOW = datetime(2030, 1, 7, 12, tzinfo=timezone.utc)


def example():
    def leg(i):
        return dict(event_key=f'football:{i}', forecast_id=f'{i:064x}', event_label=f'Spiel {i}',
                    starts_at=(NOW + timedelta(hours=i)).isoformat(), market_key='HOME',
                    selection='Heimsieg', probability=.7, reason='Heimform', sport='Fußball',
                    model_version='v1', offers={'api:8': {
                        'odds': 1.2, 'observed_at': NOW.isoformat(), 'fetched_at': NOW.isoformat()}})
    return dict(day='2030-01-07', size=3, policy='daily-accumulators-v1', arm='candidate',
                legs=[leg(3), leg(1), leg(2)], price_status='confirmed', bookmaker_id='api:8',
                captured_at=NOW.isoformat(), reference_probability=.7 ** 3)


def test_uncalibrated_reference_is_never_a_customer_percentage():
    assert customer_cards([example()], {}, as_of=NOW, chance=lambda *a, **k: None) == []


def test_whole_slip_probability_and_event_order_not_price_or_average():
    card, = customer_cards([example()], {'valid': True}, as_of=NOW, chance=lambda *a, **k: .31)
    assert card['chance'] == .31
    assert [leg['event_label'] for leg in card['legs']] == ['Spiel 1', 'Spiel 2', 'Spiel 3']
    assert card['price_observed'] is True


def test_existing_slip_loses_price_confirmation_not_sports_chance():
    card, = customer_cards([example()], {}, as_of=NOW + timedelta(minutes=36), chance=lambda *a, **k: .31)
    assert card['chance'] == .31 and not card['price_observed']


@pytest.mark.parametrize('problem', ['started', 'wrong_day', 'wrong_arm', 'future_capture', 'duplicate'])
def test_not_public(problem):
    slip = example()
    if problem == 'started':
        slip['legs'][0]['starts_at'] = NOW.isoformat()
    elif problem == 'wrong_day':
        slip['day'] = '2029-01-01'
    elif problem == 'wrong_arm':
        slip['arm'] = 'reference'
    elif problem == 'future_capture':
        slip['captured_at'] = (NOW + timedelta(seconds=1)).isoformat()
    else:
        slip['legs'][1] = slip['legs'][0]
    assert customer_cards([slip], {}, as_of=NOW, chance=lambda *a, **k: .31) == []


@pytest.mark.parametrize('change', ['missing_book', 'under_floor', 'future_price', 'old_provider'])
def test_per_leg_price_requires_the_same_book_and_both_clocks(change):
    slip = example()
    offers = slip['legs'][1]['offers']
    if change == 'missing_book':
        offers['elsewhere'] = offers.pop('api:8')
    elif change == 'under_floor':
        offers['api:8']['odds'] = 1.19
    elif change == 'future_price':
        offers['api:8']['fetched_at'] = (NOW + timedelta(seconds=1)).isoformat()
    else:
        offers['api:8']['observed_at'] = (NOW - timedelta(minutes=46)).isoformat()
    assert not quote_status(slip, NOW)
