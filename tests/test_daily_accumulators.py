from collections import Counter
from dataclasses import replace
from datetime import timedelta
from itertools import combinations

import pytest

from test_daily3_selection import NOW, football
from test_publication_odds_floor import priced


def model(i, p=.75, odds=1.20):
    s = replace(football(i, probability=p), source="automated_wettfinder_forecast")
    return priced(s, (odds,) * 3)


def pool(*signals):
    from daily_accumulators import eligible_combo_legs
    return eligible_combo_legs(signals, as_of=NOW, target_day=NOW.date())


def test_inclusive_per_leg_floor_not_replaced_by_a_total_or_a_higher_book():
    rows = pool(model(1, odds=1.19999999), model(2), model(3, odds=9))
    assert [r['fixture_id'] for r in rows] == [2, 3]
    assert rows[0]['offers']['api-football:1']['odds'] == 1.20
    assert rows[0]['probability'] == rows[1]['probability'] == .75


@pytest.mark.parametrize('delta,field', [(46,'observed_at'), (36,'fetched_at'), (-1,'observed_at'), (-1,'fetched_at')])
def test_stale_or_future_offer_does_not_become_an_executable_price(delta,field):
    signal = model(1)
    from copy import deepcopy
    quote = deepcopy(signal.reference_quote)
    stamp = (NOW-timedelta(minutes=delta)).isoformat()
    if field == 'fetched_at':
        quote[field] = stamp
    else:
        for point in quote['points']:
            point[field] = stamp
        quote['quoted_at'] = stamp
        quote.pop('executable_quote', None)
    legs = pool(replace(signal, reference_quote=quote))
    assert len(legs) == 1 and legs[0]['offers'] == {}


def test_wrong_fixture_market_and_names_do_not_certify_a_price():
    s = model(1)
    for quote in (model(2).reference_quote, dict(s.reference_quote, value_name="Away"),
                  dict(s.reference_quote, event_home='Another team')):
        assert pool(replace(s, reference_quote=quote))[0]['offers'] == {}
    assert not pool(replace(s, analysis_evidence=None))
    assert not pool(replace(s, scheduled_start=NOW.isoformat()))


def test_four_non_nested_tickets_no_padding_and_reordered_data_stable():
    from daily_accumulators import select_combo_set
    legs = pool(*(model(i, .80 - i / 1000) for i in range(1, 19)))
    tickets = select_combo_set(legs)
    assert [s['size'] for s in tickets] == [3, 4, 5, 6]
    assert [[leg['fixture_id'] for leg in s['legs']] for s in tickets[:2]] == [[1, 2, 3], [1, 4, 5, 6]]
    assert select_combo_set(reversed(legs)) == tickets
    assert select_combo_set(legs, frozen=tickets[:1]) == tickets[1:]
    sets = [{leg['event_key'] for leg in s['legs']} for s in tickets]
    assert all(len(a & b) <= 1 for a,b in combinations(sets, 2))
    assert max(Counter(event for group in sets for event in group).values()) <= 2
    assert not select_combo_set(legs[:2])


def test_competing_sides_not_reused_even_when_they_become_more_probable():
    from daily_accumulators import select_combo_set
    legs = pool(*(model(i, .80 - i / 1000) for i in range(1, 10)))
    frozen = select_combo_set(legs)[0]
    opposite = dict(legs[0], selection="Auswärtssieg", market_key="RESULT_AWAY", signal_key="changed", probability=.99)
    assert all(leg['signal_key'] != 'changed' for t in select_combo_set([opposite,*legs[1:]], frozen=[frozen]) for leg in t['legs'])


def test_shared_participant_requires_search_beyond_greedy_highest_leg():
    from daily_accumulators import select_combo_set
    legs = pool(*(model(i,p) for i,p in enumerate([.90,.89,.88,.80,.60], 1)))
    # The first leg conflicts with each of the next two, but the latter coexist.
    legs[1]['participants'][0] = legs[0]['participants'][0]
    legs[2]['participants'][0] = legs[0]['participants'][1]
    t = select_combo_set(legs)[0]
    assert {leg['fixture_id'] for leg in t['legs']} == {2,3,4}
    assert t['reference_probability'] == pytest.approx(.89*.88*.80)


def test_separate_reference_search_never_mixes_books_and_finds_alternative():
    from daily_accumulators import select_combo_set, select_confirmed_combo_set
    legs = pool(*(model(i, .81-i/100) for i in range(1,5)))
    legs[0]['offers'] = {'odds-api:1': legs[0]['offers']['api-football:1']}
    model_slip = select_combo_set(legs)[0]
    assert model_slip['price_status'] == 'unconfirmed' and model_slip['bookmaker_id'] is None
    t = select_confirmed_combo_set(legs)[0]
    assert [leg['fixture_id'] for leg in t['legs']] == [2,3,4]
    assert (t['price_status'], t['bookmaker_id']) == ('confirmed', 'api-football:1')
    assert not select_confirmed_combo_set(legs[:3])


def test_tennis_native_event_hash_is_not_the_sport_name():
    from test_daily3_selection import tennis, _admitted
    s = _admitted(replace(tennis(), fixture_source="espn", model_version="tennis-v1"))
    legs = pool(s)
    assert len(legs) == 1 and legs[0]['sport'] == 'tennis'
    assert legs[0]['evidence_selection'] == 'Spieler A' != legs[0]['selection']
    assert legs[0]['offers']['odds-api:test-book']['odds'] == 1.8


def test_missing_price_cannot_create_a_confirmed_offer_or_hide_a_sporting_observation():
    from daily_accumulators import select_combo_set, select_confirmed_combo_set
    unpriced = [replace(model(i), reference_quote=None) for i in range(1,4)]
    legs = pool(*unpriced)
    assert select_combo_set(legs)[0]['price_status'] == 'unconfirmed'
    assert not select_confirmed_combo_set(legs)


def test_same_provider_participant_under_two_names_cannot_appear_twice():
    from daily_accumulators import select_combo_set
    legs = pool(*(model(i, .80 - i / 100) for i in range(1, 5)))
    legs[1]['participants'][1] = legs[0]['participants'][0]
    t = select_combo_set(legs)[0]
    assert {leg['fixture_id'] for leg in t['legs']} == {1,3,4}


def test_frozen_fixture_alias_with_changed_native_id_cannot_escape_overlap():
    from daily_accumulators import select_combo_set
    legs = pool(*(model(i, .80 - i / 100) for i in range(1, 8)))
    frozen = select_combo_set(legs)[0]
    renamed = dict(legs[0], event_key='football:999', probability=.99)
    assert not any(leg['event_key'] == 'football:999' for t in
                   select_combo_set([renamed,*legs[1:]], frozen=[frozen]) for leg in t['legs'])


def test_only_point_with_native_book_id_and_real_provider_clock_can_confirm():
    from copy import deepcopy
    signal = model(1)
    for field, value in [('bookmaker_id', 'other-feed:8'), ('bookmaker_id', None), ('observed_at', None)]:
        q = deepcopy(signal.reference_quote)
        q.pop('executable_quote', None)
        q['points'][0][field] = value
        assert set(pool(replace(signal, reference_quote=q))[0]['offers']) == {'api-football:2','api-football:3'}


def test_candidate_pool_includes_future_games_beyond_twenty_but_not_next_zurich_day():
    from daily_accumulators import eligible_combo_legs, select_combo_set
    signals = [model(i, .51 if i < 24 else .81) for i in range(1,27)]
    tomorrow = replace(model(27), scheduled_start=(NOW+timedelta(hours=16)).isoformat())
    legs = eligible_combo_legs([*signals,tomorrow],as_of=NOW,target_day=NOW.date())
    assert len(legs) == 26
    assert {leg['fixture_id'] for leg in select_combo_set(legs)[0]['legs']} == {24,25,26}


def test_broken_individual_candidate_does_not_remove_an_unrelated_fixture():
    assert [leg['fixture_id'] for leg in pool(None, model(3), {'invalid': True})] == [3]


def test_frozen_home_pick_cannot_be_reused_with_reversed_team_roles():
    from daily_accumulators import select_combo_set
    legs = pool(*(model(i, .80 - i / 100) for i in range(1, 8)))
    frozen = select_combo_set(legs)[0]
    flipped = dict(legs[0], participants=legs[0]['participants'][::-1], probability=.99)
    assert not any(leg['event_key'] == flipped['event_key'] for t in
                   select_combo_set([flipped,*legs[1:]], frozen=[frozen]) for leg in t['legs'])


def test_tennis_without_player_ids_rejects_same_player_spelled_two_ways():
    from daily_accumulators import select_combo_set
    from test_daily3_selection import tennis
    def match(i, a, b):
        base = tennis()
        context = dict(base.context_evidence, players={'a':{'player':a},'b':{'player':b}})
        return replace(base, key='tennis'+str(i), fixture_source='espn', provider_event_id=str(i),
                       model_version='tennis-v1', competitor_a=a, competitor_b=b, competitor_a_id=None,
                       competitor_b_id=None, selected_competitor=a, selection='Sieg '+a, event_label=a+' vs '+b,
                       context_evidence=context)
    legs = pool(match(1,'Roger Federer','Andy Murray'),match(2,'Federer R.','Rafael Nadal'),model(3))
    assert len(legs) == 3 and not select_combo_set(legs)
