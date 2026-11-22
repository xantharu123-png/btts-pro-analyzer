from datetime import datetime, timedelta, timezone

import pytest

from daily_accumulator_surface import customer_cards, quote_status


NOW = datetime(2030, 1, 7, 12, tzinfo=timezone.utc)


def test_rendered_archived_combo_keeps_home_away_and_match_goals_distinct(monkeypatch):
    from streamlit.testing.v1 import AppTest

    slip = dict(example(), arm='daily-picks')
    for leg, key, names in zip(slip['legs'], ('HOME_UNDER_2_5', 'AWAY_UNDER_2_5', 'TOTAL_UNDER_2_5'),
                               (('FC Augsburg', 'FSV Mainz 05'), ('SC Freiburg', 'Werder Bremen'),
                                ('Köln', 'Stuttgart'))):
        leg.update(sport='football', market_key=key, selection='Unter 2.5',
                   event_label=' vs '.join(names),
                   participant_names=['football:name:' + n.casefold() for n in names])
    monkeypatch.setattr('daily_accumulator_receipts.load_daily_picks', lambda *a, **k: [slip])
    app = AppTest.from_string("""
import streamlit as st
from daily_accumulator_surface import render_daily_accumulators
render_daily_accumulators(st, as_of='2030-01-07T12:00:00+00:00')
""").run()
    assert not app.exception
    assert {row.value.splitlines()[1] for row in app.text} == {
        'FC Augsburg: Unter 2,5 Tore', 'Werder Bremen: Unter 2,5 Tore',
        'Gesamttore im Spiel: Unter 2,5'}


@pytest.mark.parametrize(('sport', 'key', 'expected'), [
    ('football', 'AWAY_OVER_0_5', 'Auswärtsteam: Über 0,5 Tore'),
    ('ice_hockey', 'AWAY_OVER_0_5', 'Über 0.5'),
])
def test_no_team_is_inferred_from_reversed_event_names_or_another_sport(sport, key, expected):
    from daily_accumulator_surface import _selection_label

    assert _selection_label(dict(sport=sport, market_key=key, selection='Über 0.5',
                                 event_label='Mainz vs Augsburg',
                                 participant_names=['football:name:augsburg', 'football:name:mainz'])) == expected


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


def test_real_daily_selection_visible_without_review_file_or_common_price():
    slip = dict(example(), arm='daily-picks', price_status='unconfirmed', bookmaker_id=None)
    for leg in slip['legs']:
        leg['offers'] = {}
    card, = customer_cards([slip], None, as_of=NOW, chance=lambda *a, **k: None)
    assert card['chance'] == pytest.approx(.343)
    assert card['estimated'] and not card['started'] and not card['price_observed']


def test_research_original_never_turns_into_a_customer_recommendation():
    assert not customer_cards([dict(example(), arm='model-observation')], as_of=NOW)


def test_already_started_kept_as_original_not_a_new_suggestion_or_live_chance():
    slip = dict(example(), arm='daily-picks')
    card, = customer_cards([slip], None, as_of=NOW + timedelta(hours=1), chance=None)
    assert card['started'] and card['chance'] == pytest.approx(.343) and not card['price_observed']
    assert customer_cards([dict(slip, captured_at=(NOW+timedelta(hours=1)).isoformat())],
                          None, as_of=NOW + timedelta(hours=2), chance=None) == []


@pytest.mark.parametrize('probability', [True, float('nan'), 1.2, 0, '0.7'])
def test_model_estimate_never_substitutes_a_price_or_a_bad_leg(probability):
    slip = dict(example(), arm='daily-picks')
    slip['legs'][0]['probability'] = probability
    assert customer_cards([slip], None, as_of=NOW, chance=None) == []


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
