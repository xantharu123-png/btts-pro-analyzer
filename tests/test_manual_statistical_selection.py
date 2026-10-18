"""The real manual producer and renderer share price-blind statistical choice."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import permutations

import pytest
from unittest.mock import MagicMock

import alternative_markets_tab_extended as market_tab
from bet_finder_ui import coherent_consumer_forecasts
from challenge_engine import MARKET_BY_KEY, MARKET_SPECS
from manual_search_filters import SearchFilters
from test_manual_football_filters import _quote, _render
from test_wettfinder_automation import _challenge_candidate


def candidate(key, probability, skill=.05, *, fixture=1, now=None):
    now = now or datetime.now(timezone.utc)
    base = _challenge_candidate(now + timedelta(hours=3))
    spec = MARKET_BY_KEY[key]
    return replace(base, candidate_id=f'{fixture}:{key}', fixture_id=fixture,
        home_team_id=fixture*10+1, away_team_id=fixture*10+2,
        market_key=key, market=spec.market, selection=spec.selection,
        probability=probability, conservative_probability=probability-.05,
        model_price=1. / (probability-.05),
        probability_haircut_pp=5., validation=replace(base.validation, relative_improvement=skill),
        context={'forecast_passed': True, 'passed': True, 'release_context_complete': True})


def test_manual_shared_helper_keeps_modal_result_before_overlapping_double_chances():
    now = datetime.now(timezone.utc)
    rows = [candidate(key, probability, now=now) for key, probability in (
        ('RESULT_HOME', .486390), ('RESULT_AWAY', .251021),
        ('DC_1X', .748979), ('DC_X2', .513610))]
    before = deepcopy(rows)
    for ordered in permutations(rows):
        selected = coherent_consumer_forecasts(ordered, model_clock=now.isoformat())
        assert {row.market_key for row in selected} == {'RESULT_HOME', 'DC_1X'}
        assert all(any(row is original for original in rows) for row in selected)
    assert rows == before


def test_manual_shared_helper_uses_statistical_skill_not_hardcoded_market_tier():
    now = datetime.now(timezone.utc)
    stronger = candidate('HOME_RANGE_1_3', .61, .20, now=now)
    weaker = candidate('TOTAL_UNDER_0_5', .91, .03, now=now)
    for rows in ((stronger, weaker), (weaker, stronger)):
        assert coherent_consumer_forecasts(rows, model_clock=now.isoformat()) == [stronger]


@pytest.mark.parametrize('key', [spec.key for spec in MARKET_SPECS])
def test_every_supported_real_candidate_can_reach_manual_shared_selection(key):
    now = datetime.now(timezone.utc)
    original = candidate(key, .70, now=now)
    assert coherent_consumer_forecasts([original], model_clock=now.isoformat()) == [original]


def test_real_manual_worker_retains_complete_model_pool_before_coherence(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [candidate(key, probability, now=now) for key, probability in (
        ('RESULT_HOME', .486390), ('RESULT_AWAY', .251021),
        ('DC_1X', .748979), ('DC_X2', .513610))]
    monkeypatch.setattr(market_tab, 'ChallengeDataProvider', lambda *_: object())
    monkeypatch.setattr(market_tab, 'scan_daily_challenge', lambda *_a, **_k: {
        'wettfinder_candidates': rows, 'scanned_at': now.isoformat()})
    monkeypatch.setattr(market_tab, 'fetch_football_consensus', lambda *_a, **_k: ({}, []))
    result = market_tab._run_market_scan_worker('fixture', None, [39], now.date(), now.date(),
        1200, {'league_ids': [39]})['challenge']
    assert {row.market_key for row in result['model_shortlist']} == {
        'RESULT_HOME', 'RESULT_AWAY', 'DC_1X', 'DC_X2'}


def test_real_manual_renderer_selects_lead_before_probability_order(monkeypatch):
    now = datetime.now(timezone.utc)
    home = candidate('RESULT_HOME', .60, .20, now=now)
    cover = candidate('TOTAL_UNDER_4_5', .90, .03, now=now)
    other = candidate('RESULT_HOME', .75, .10, fixture=2, now=now)
    rows = [cover, other, home]
    render, surface, snapshot = _render(monkeypatch, rows)
    surface.markdown = lambda text, **_: surface.messages.append(text)
    before = deepcopy(snapshot)
    # Equal kickoffs retain producer game order, not probability order. Keep
    # the legacy ID and the statistical lead ahead of its broader secondary.
    assert render(SearchFilters()) == ['1:RESULT_HOME', '1:TOTAL_UNDER_4_5', '2:RESULT_HOME']
    assert 'Weitere Märkte' in ' '.join(surface.messages)
    assert snapshot == before


def test_manual_price_filter_never_selects_opposite_or_promotes_cover(monkeypatch):
    now = datetime.now(timezone.utc)
    home = candidate('RESULT_HOME', .60, .20, now=now)
    away = candidate('RESULT_AWAY', .40, .25, now=now)
    cover = candidate('TOTAL_UNDER_4_5', .90, .03, now=now)
    render, surface, _ = _render(monkeypatch, [away, cover, home], quotes={
        home.candidate_id: _quote(home, 1.12, now),
        away.candidate_id: _quote(away, 3.0, now),
        cover.candidate_id: _quote(cover, 1.80, now)})
    surface.markdown = lambda text, **_: surface.messages.append(text)
    assert render(SearchFilters()) == ['1:TOTAL_UNDER_4_5']
    assert 'Weitere Märkte' in ' '.join(surface.messages)


def test_manual_goals_scope_contains_all_total_multigoal_ranges():
    wanted = {'TOTAL_RANGE_1_3', 'TOTAL_RANGE_1_4', 'TOTAL_RANGE_2_4'}
    assert wanted <= {spec.key for spec in MARKET_SPECS
                      if spec.kind in market_tab.FOOTBALL_MARKET_SCOPES['Tore']}


@pytest.mark.parametrize('clock', [None, 'not-a-clock', '2030-01-01T10:00:00'])
def test_missing_or_naive_manual_clock_never_manufactures_statistical_lead(clock):
    from bet_finder_ui import consumer_event_leads
    rows = [candidate('RESULT_HOME', .60, .20), candidate('TOTAL_UNDER_4_5', .90, .03)]
    before = deepcopy(rows)
    assert consumer_event_leads(rows, model_clock=clock) == []
    assert rows == before


def test_future_manual_clock_never_manufactures_statistical_lead():
    from bet_finder_ui import consumer_event_leads
    rows = [candidate('RESULT_HOME', .60, .20)]
    assert consumer_event_leads(rows, model_clock=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()) == []


@pytest.mark.parametrize('home_price,expected', [(None, []), (1.12, []), (1.80, ['1:RESULT_HOME'])])
def test_real_15k_model_renderer_never_promotes_a_priced_secondary(home_price, expected, monkeypatch):
    import challenge_15k
    import wettfinder_identity
    from market_consensus import serialize_consensus_map
    now = datetime.now(timezone.utc)
    home = candidate('RESULT_HOME', .60, .20, now=now)
    cover = candidate('TOTAL_UNDER_4_5', .90, .03, now=now)
    rows = [cover, home]
    quotes = {cover.candidate_id: _quote(cover, 1.80, now)}
    if home_price is not None:
        quotes[home.candidate_id] = _quote(home, home_price, now)
    snapshot = {'scanned_at': now.isoformat(), 'challenge_model_candidates': rows,
                'reference_quotes': serialize_consensus_map(quotes)}
    before = deepcopy(snapshot)
    ui = MagicMock()
    ui.multiselect.return_value = []
    monkeypatch.setattr(challenge_15k, 'st', ui)
    monkeypatch.setattr(challenge_15k, 'read_shared_quote_rows', lambda: [])
    monkeypatch.setattr(wettfinder_identity, 'rendered_identity_card', lambda card, signal: card)
    challenge_15k._render_model_challenge(snapshot, None, {})
    if expected:
        assert ui.multiselect.call_args.kwargs['options'] == expected
    else:
        ui.multiselect.assert_not_called()
    visible = ' '.join(str(call.args[0]) for call in ui.markdown.call_args_list)
    assert 'challenge-15k-1:TOTAL_UNDER_4_5' not in visible
    assert snapshot == before
