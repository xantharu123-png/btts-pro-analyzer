from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from challenge_engine import MARKET_BY_KEY
from daily3_identity import event_guard
from daily3_selection import MIN_MODEL_PROBABILITY, POLICY_VERSION, daily3_choices
from ev_signal_sources import ModelSignal, _automated_analysis_fields
from forecast_analysis import project_football_analysis
from highlight_fixtures import football_checks

NOW = datetime(2030, 1, 1, 7, tzinfo=timezone.utc)


def football(fixture=1, key='RESULT_HOME', probability=.75, *, now=NOW,
             baseline=.5, variants=None, comparison=True, start_hours=3):
    spec = MARKET_BY_KEY[key]
    row = dict(candidate_id=f'{fixture}:{key}', fixture_id=fixture,
        home_id=fixture*2, away_id=fixture*2+1, home_team=f'Heimteam {fixture}', away_team=f'Auswärtsteam {fixture}',
        market_key=key, probability=probability, model_scope='same_competition',
        scheduled_start=(now+timedelta(hours=start_hours)).isoformat(), modeled_at=now.isoformat(),
        input_cutoff_at=(now-timedelta(minutes=1)).isoformat(), context=football_checks(now))
    reference = dict(schema='league-market-comparison-v1', fixture_id=fixture,
        home_id=row['home_id'], away_id=row['away_id'], league_id=39, market_key=key,
        scheduled_start=row['scheduled_start'], prediction_version='test-model-v1',
        validation_prediction_version='test-model-v1', model_skill_supported=True,
        samples=400, successes=round(400*baseline), latest_kickoff=(now-timedelta(days=1)).isoformat(),
        # Synthetic positive same-match form signal, not live evidence. Tests
        # of absent/reversed signals supply their own explicit triplet.
        probabilities=list(variants or (probability, round(max(.001, probability-.03), 6),
                                         round(min(.999999, probability+.09), 6)))) if comparison else None
    evidence = project_football_analysis(row, model_basis={**row,
        'expected_home_goals': 1.8, 'expected_away_goals': .9, 'venue_samples': [12, 12],
        'form_samples': [6, 6], 'market_comparison': reference})
    return ModelSignal(key=row['candidate_id'], label=f'Heimteam {fixture} vs Auswärtsteam {fixture}',
        probability=probability, probability_haircut=.08, evidence_stage='SHADOW', policy_version='test-v1',
        detail='Interne Angaben nicht veröffentlichen', sport='Fußball', event_label=f'Heimteam {fixture} vs Auswärtsteam {fixture}',
        market=spec.market, selection=spec.selection, market_key=key, candidate_id=row['candidate_id'],
        fixture_id=fixture, home_team=row['home_team'], away_team=row['away_team'], home_team_id=row['home_id'],
        away_team_id=row['away_id'], scheduled_start=row['scheduled_start'], modeled_at=row['modeled_at'],
        input_cutoff_at=row['input_cutoff_at'], model_scope=row['model_scope'], analysis_evidence=evidence,
        model_version='test-model-v1', price_checked_at=now.isoformat())


def tennis(*, now=NOW, coverage=True):
    return ModelSignal(key='tennis1', label='Spieler A vs Spieler B', probability=.76, probability_haircut=.08,
        evidence_stage='SHADOW', policy_version='test-v1', detail='unused', scheduled_start=(now+timedelta(hours=2)).isoformat(),
        source='tennis_model', sport='Tennis', event_label='Spieler A vs Spieler B', market='Match Winner',
        selection='Sieg Spieler A', market_key='H2H', competitor_a='Spieler A', competitor_b='Spieler B', selected_competitor='Spieler A',
        fixture_source='api-tennis', provider_event_id='t1', competitor_a_id='a1', competitor_b_id='b1',
        modeled_at=now.isoformat(), input_cutoff_at=now.isoformat(), price_checked_at=now.isoformat(), context_evidence={
            'observed_at': now.isoformat(), 'players': {'a': {'player': 'Spieler A'}, 'b': {'player': 'Spieler B'}},
            'model_inputs': {'surface': 'Clay', 'surface_in_model': True, 'serve_in_model': True,
                **({'stats_through': now.date().isoformat(), 'stats_through_kind': 'result_date',
                    'model_built_at': now.isoformat(), 'training_cutoff': now.isoformat()} if coverage else {})}})


def _admitted(signal):
    """Explicit current price proof for tests of non-price selection policy."""
    if signal.sport == 'Fußball':
        from test_publication_odds_floor import priced
        return priced(signal, (1.8,)*3)
    from market_consensus import parse_h2h_event_consensus
    signal = replace(signal, candidate_id=signal.candidate_id or signal.key)
    event = dict(id=f'quote-{signal.key}', home_team=signal.competitor_a,
        away_team=signal.competitor_b, commence_time=signal.scheduled_start,
        bookmakers=[dict(key='test-book', title='Test Book', last_update=NOW.isoformat(),
            markets=[dict(key='h2h', outcomes=[dict(name=signal.selected_competitor, price=1.8)])])])
    quote = parse_h2h_event_consensus(event, [signal], fetched_at=NOW)[signal.candidate_id]
    return replace(signal, reference_quote=quote.to_dict())


def _admitted_football(*args, **kwargs):
    return _admitted(football(*args, **kwargs))


def test_no_opposing_selections_and_full_pool_diversity_before_cut():
    pool = [_admitted_football(i, 'HOME_OVER_0_5', .85) for i in range(1, 41)]
    pool += [_admitted_football(41, 'BTTS_YES', .85, start_hours=6), _admitted_football(42, 'TOTAL_OVER_2_5', .85, start_hours=9), _admitted_football(41, 'BTTS_NO', .15, start_hours=6)]
    choices = daily3_choices(pool, now=NOW)
    assert len(choices) == 3 and len({c.event_id for c in choices}) == 3
    assert len({c.family for c in choices}) == 3
    assert sum(c.signal.market_key == 'HOME_OVER_0_5' for c in choices) == 1


def test_prices_release_flags_and_pool_iteration_cannot_reorder_forecasts():
    assert daily3_choices([football()], now=NOW) == ()  # No positive price proof.
    pool = [_admitted_football(1), _admitted_football(2, 'BTTS_YES', start_hours=6), _admitted_football(3, 'HOME_UNDER_1_5', start_hours=9), _admitted(tennis())]
    changed = [replace(s, minimum_odds=999, evidence_stage='RELEASED', statistical_release_passed=True) for s in reversed(pool)]
    before = daily3_choices(pool, now=NOW)
    after = daily3_choices(changed, now=NOW)
    assert [c.signal.key for c in before] == [c.signal.key for c in after]
    assert [c.signal.probability for c in before] == [c.signal.probability for c in after]
    assert len(before) == 3


@pytest.mark.parametrize('key', ['HOME_OVER_0_5', 'AWAY_OVER_0_5', 'HOME_UNDER_1_5', 'AWAY_UNDER_1_5'])
def test_no_categorical_simple_market_ban(key):
    assert daily3_choices([_admitted_football(key=key)], now=NOW)[0].signal.market_key == key


def test_occupied_games_and_slots_are_never_offered_again():
    first = daily3_choices([_admitted_football(1)], now=NOW)[0]
    choices = daily3_choices([_admitted_football(1), _admitted_football(1, 'RESULT_AWAY'), _admitted_football(2), _admitted_football(3)], now=NOW,
                            occupied_events=[first.event_id], used_slots=2)
    assert len(choices) == 1 and choices[0].event_id != first.event_id
    assert daily3_choices([_admitted_football(2)], now=NOW, used_slots=3) == ()


def test_missing_stale_or_misbound_facts_are_not_relabelled_as_good_tips():
    base = _admitted_football()
    old = _admitted_football(now=NOW-timedelta(hours=3))
    changed = replace(base, probability=.9)
    for row in (replace(base, analysis_evidence=None), old, changed, replace(base, sport='Cricket')):
        assert daily3_choices([row], now=NOW) == ()


def test_daily_automatic_model_remains_visible_after_150_minutes_but_manual_stale_does_not():
    daily = _admitted_football(now=NOW-timedelta(hours=4), start_hours=8)
    # A daily model may remain usable, but its separate context checks must
    # have been refreshed; an old model clock must not renew those checks.
    daily = replace(daily, analysis_evidence={**daily.analysis_evidence,
                    'context': football_checks(NOW)})
    automatic = replace(daily, source='automated_wettfinder_forecast')
    assert daily3_choices([daily], now=NOW) == ()
    assert [choice.signal.key for choice in daily3_choices([automatic], now=NOW)] == [automatic.key]


def test_tennis_facts_require_both_players_and_same_model_time():
    from daily3_selection import _explanation
    s = _admitted(tennis())
    assert 'Sand' in _explanation(s, 'tennis', NOW)[0]
    assert _explanation(replace(s, competitor_a='Fremder Spieler'), 'tennis', NOW) is None
    assert _explanation(replace(s, modeled_at=(NOW-timedelta(minutes=1)).isoformat()), 'tennis', NOW) is None
    # A descriptive surface fact alone is not a measured comparison advantage.
    assert daily3_choices([s], now=NOW) == ()


def test_optional_persisted_model_fields_survive_shared_loader_projection():
    s = tennis()
    projected = _automated_analysis_fields(vars(s), now=NOW)
    for field in ('fixture_source', 'provider_event_id', 'competitor_a_id', 'competitor_b_id', 'context_evidence', 'model_version'):
        assert projected[field] == getattr(s, field)


def test_bare_high_probability_does_not_create_an_explanation_or_force_three():
    s = _admitted_football(probability=.99)
    assert daily3_choices([replace(s, analysis_evidence=None)], now=NOW) == ()
    assert len(daily3_choices([s], now=NOW)) == 1


def test_low_probability_modal_winner_is_not_a_defensive_daily3_choice():
    choices = daily3_choices([_admitted_football(1, 'RESULT_AWAY', .21), _admitted_football(1, 'RESULT_HOME', .46),
                             _admitted_football(1, 'RESULT_DRAW', .33)], now=NOW)
    assert choices == ()


@pytest.mark.parametrize('probability,eligible', [(.195, False), (.5, False), (.699999, False),
                                                (.7, False), (.729999, False), (.73, True), (.9, True)])
def test_defensive_threshold_is_price_free_and_does_not_erase_normal_forecasts(probability, eligible):
    from forecast_selection import select_consumer_forecasts
    signal = _admitted_football(probability=probability)
    assert bool(daily3_choices([signal], now=NOW)) is eligible
    assert select_consumer_forecasts([signal], now=NOW) == [signal]
    assert MIN_MODEL_PROBABILITY == .7


def test_same_kickoff_uses_defensive_variants_without_requiring_a_form_bonus():
    broad = [_admitted_football(1, 'AWAY_UNDER_2_5', .953, baseline=.50, variants=(.953,.95,.96)),
             _admitted_football(2, 'AWAY_UNDER_2_5', .91, baseline=.50, variants=(.91,.905,.925)),
             _admitted_football(3, 'HOME_OVER_0_5', .908, baseline=.50, variants=(.908,.905,.917))]
    alternatives = [_admitted_football(4, 'BTTS_YES', .74, baseline=.45, start_hours=6),
                    _admitted_football(5, 'TOTAL_OVER_2_5', .73, baseline=.43, start_hours=9),
                    _admitted_football(6, 'HOME_UNDER_1_5', .79, baseline=.54)]
    pool = broad + alternatives
    before = tuple(pool)
    for ordering in (pool, list(reversed(pool))):
        choices = daily3_choices(ordering, now=NOW)
        # All variants qualify; the old 2pp-only expectation was not a
        # defensiveness test. At the first kickoff the strongest conservative
        # model comparison wins, followed by the actual later day slots.
        assert [c.signal.key for c in choices] == [broad[0].key, alternatives[0].key, alternatives[1].key]
        assert all(c.snapshot()['policy_version'] == POLICY_VERSION for c in choices)
    assert tuple(pool) == before


def test_no_defensive_backfill_or_return_to_an_older_higher_probability():
    old = _admitted_football(probability=.95, now=NOW-timedelta(minutes=1))
    new = _admitted_football(probability=.60)
    assert daily3_choices([old, new, _admitted_football(2, probability=.69)], now=NOW) == ()


def test_defensive_profile_never_uses_an_unexplained_high_probability_or_haircut():
    unqualified = replace(_admitted_football(1, probability=.99), analysis_evidence=None)
    qualified = _admitted_football(2, probability=.75)
    rows = [unqualified, qualified, _admitted_football(3, probability=.74, start_hours=6)]
    baseline = daily3_choices(rows, now=NOW)
    changed = daily3_choices([replace(s, probability_haircut=.01, minimum_odds=999) for s in rows], now=NOW)
    assert [c.signal.key for c in baseline] == [qualified.key, '3:RESULT_HOME']
    assert [c.signal.key for c in changed] == [c.signal.key for c in baseline]
    assert '0/0 Ausfälle gemeldet' in baseline[0].caution
    assert 'Aufstellungen noch offen' in baseline[0].caution


def test_persisted_weak_identity_cannot_reappear_after_native_id_upgrade(monkeypatch):
    from daily3_comparison import Comparison
    monkeypatch.setattr('daily3_selection.daily3_comparison', lambda *_a, **_kw: Comparison(.1, .75, .5, 400))
    native = _admitted(tennis())
    weak = replace(native, fixture_source=None, provider_event_id=None, competitor_a_id=None, competitor_b_id=None)
    first = daily3_choices([weak], now=NOW)[0]
    assert first.event_id != daily3_choices([native], now=NOW)[0].event_id
    assert daily3_choices([native], now=NOW, occupied_guards=[first.snapshot()['event_guard']], used_slots=1) == ()


def test_distinct_source_ids_with_exact_same_event_alias_use_only_one_slot(monkeypatch):
    from daily3_comparison import Comparison
    monkeypatch.setattr('daily3_selection.daily3_comparison', lambda *_a, **_kw: Comparison(.1, .75, .5, 400))
    base = _admitted(tennis())
    second = _admitted(replace(base, key='tennis-second-source', fixture_source='different-fixture-source', provider_event_id='t2'))
    assert len(daily3_choices([base, second], now=NOW)) == 1
    # This is not a fuzzy same-opponent ban: a different complete kickoff is a
    # separate event when it also has a distinct native event ID.
    later = _admitted(replace(second, scheduled_start=(NOW+timedelta(hours=6)).isoformat()))
    assert len(daily3_choices([base, later], now=NOW)) == 2
    assert event_guard(base)['identity'] != event_guard(second)['identity']


@pytest.mark.parametrize('variants', [(.8, .8, .8), (.8, .805, .81), (.8, .79, .81)])
def test_validated_defensive_model_does_not_need_an_arbitrary_positive_form_bonus(variants):
    signal = _admitted_football(probability=.8, variants=variants)
    choices = daily3_choices([signal], now=NOW)
    assert [choice.signal.key for choice in choices] == [signal.key]
    assert choices[0].signal.probability == .8
    assert choices[0].comparison.lowest_model_probability == min(variants)
    assert '+-' not in choices[0].comparison.summary
    from daily3_comparison import football_form_comparison
    # The shared ordinary TOP policy is not broadened by the Daily3 repair.
    assert football_form_comparison(signal, now=NOW) is None


def test_daily_context_keeps_its_original_clock_without_expiring_after_75_minutes():
    signal = _admitted_football(now=NOW-timedelta(hours=4), start_hours=8)
    signal = replace(signal, source='automated_wettfinder_forecast')
    before = signal.analysis_evidence['context']['injuries']['checked_at']
    assert [choice.signal.key for choice in daily3_choices([signal], now=NOW)] == [signal.key]
    assert signal.analysis_evidence['context']['injuries']['checked_at'] == before


@pytest.mark.parametrize('age,eligible', [
    (timedelta(hours=24), True),
    (timedelta(hours=24, seconds=1), False),
])
def test_daily_context_and_model_expire_at_the_daily_lifetime(age, eligible):
    signal = _admitted_football(now=NOW-age, start_hours=age.total_seconds()/3600+3)
    signal = replace(signal, source='automated_wettfinder_forecast', price_checked_at=NOW.isoformat())
    assert bool(daily3_choices([signal], now=NOW)) is eligible


@pytest.mark.parametrize('clock', [None, 'invalid', (NOW+timedelta(seconds=1)).isoformat()])
def test_daily_lifetime_does_not_admit_missing_invalid_or_future_context_clocks(clock):
    from copy import deepcopy
    signal = _admitted_football(now=NOW-timedelta(hours=4), start_hours=8)
    evidence = deepcopy(signal.analysis_evidence)
    evidence['context']['injuries']['checked_at'] = clock
    signal = replace(signal, source='automated_wettfinder_forecast', analysis_evidence=evidence)
    assert daily3_choices([signal], now=NOW) == ()


@pytest.mark.parametrize('axis', ['injuries', 'weather', 'h2h', 'lineups'])
def test_original_adverse_context_is_not_ignored_by_daily_lifetime(axis):
    from copy import deepcopy
    signal = _admitted_football(now=NOW-timedelta(hours=4), start_hours=8)
    evidence = deepcopy(signal.analysis_evidence)
    evidence['context'][axis]['status'] = 'blocked'
    signal = replace(signal, source='automated_wettfinder_forecast', analysis_evidence=evidence)
    assert daily3_choices([signal], now=NOW) == ()


def test_defensive_daily_sequence_begins_with_earliest_qualified_match():
    first = _admitted_football(401, probability=.75, start_hours=3)
    second = _admitted_football(402, probability=.80, start_hours=6)
    third = _admitted_football(403, probability=.90, start_hours=9)
    assert [choice.signal.key for choice in daily3_choices([third, second, first], now=NOW)] == [
        '401:RESULT_HOME', '402:RESULT_HOME', '403:RESULT_HOME']


def test_choice_carries_reservation_minimum_and_admitted_offer_without_changing_selection():
    signal = _admitted_football()  # Offer 1.80 from the shared fixture, forecast minimum 2.00.
    choice, = daily3_choices([signal], now=NOW)
    assert choice.minimum_odds == 2.0 and choice.offer_odds == 1.8 and choice.price_blocked
    cheaper, = daily3_choices([replace(signal, minimum_odds=1.5)], now=NOW)
    assert cheaper.minimum_odds == 1.5 and not cheaper.price_blocked
    floored, = daily3_choices([replace(signal, minimum_odds=1.05)], now=NOW)
    assert floored.minimum_odds == 1.2 and not floored.price_blocked  # The 1.20 floor still applies.
    unknown, = daily3_choices([replace(signal, minimum_odds=None)], now=NOW)
    assert unknown.minimum_odds is None and unknown.price_blocked  # Fail-closed, never silently 1.20.
    assert {c.signal.key for c in (choice, cheaper, floored, unknown)} == {signal.key}
    assert 'minimum_odds' not in choice.snapshot() and 'offer_odds' not in choice.snapshot()
