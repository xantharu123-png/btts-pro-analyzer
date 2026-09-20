"""User policy: observed odds below 1.20 do not become new suggestions."""
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from daily3_math import Daily3Error
from daily3_selection import daily3_choices
from market_consensus import ODDS_API_REFERENCE_SOURCE, exact_market_target, wettfinder_consensus, quote_below_publication_floor
from test_daily3_selection import NOW, football, tennis
from test_daily3_store import DAY, SCOPE, command, ident, snapshot, store
from test_wettfinder_surface import _quote
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog, render_top_card_html


def priced(signal, odds=(1.12, 1.12, 1.12)):
    bet_name, value_name = exact_market_target(signal.market_key)
    quote = replace(_quote(signal, odds), bet_name=bet_name, value_name=value_name)
    quote = wettfinder_consensus(quote, now=NOW)
    return replace(signal, reference_quote=quote.to_dict(), minimum_odds=2.0)


def visible(signals):
    cards = [build_wettfinder_card(s, s.reference_quote, now=NOW) for s in signals]
    result = compose_wettfinder_catalog(cards)
    return result.featured + result.additional


@pytest.mark.parametrize('price,allowed', [(1.01, False), (1.12, False), (1.1999, False), (1.19999999, False), (1.20, True), (1.21, True)])
def test_floor_applies_to_wettfinder_and_daily3_without_changing_model(price, allowed):
    signal = priced(football(), (price,)*3)
    before = dict(vars(signal))
    assert bool(visible([signal])) is allowed
    assert bool(daily3_choices([signal], now=NOW)) is allowed
    assert vars(signal) == before
    if not allowed:
        assert 'MODELL-AUSWAHL' not in render_top_card_html(build_wettfinder_card(signal, signal.reference_quote, now=NOW))


def test_current_single_book_quote_also_counts_but_best_offer_at_floor_remains_allowed():
    low = priced(football(), (1.12,))
    assert not visible([low])
    assert not daily3_choices([low], now=NOW)
    higher = priced(football(), (1.10, 1.12, 1.20))
    assert visible([higher])
    assert daily3_choices([higher], now=NOW)


@pytest.mark.parametrize('price,allowed', [(1.12, False), (1.20, True)])
def test_same_floor_for_exact_tennis_offer(price, allowed):
    signal = tennis()
    quote = _quote(signal, (price,)*3)
    quote = replace(quote, source=ODDS_API_REFERENCE_SOURCE, provider_event_id='tennis-price-event',
        bet_name='h2h', value_name=signal.selected_competitor,
        event_home=signal.competitor_a, event_away=signal.competitor_b,
        points=tuple(replace(p, bookmaker_id=f'odds-api:{i}') for i, p in enumerate(quote.points)))
    signal = replace(signal, reference_quote=quote.to_dict())
    assert bool(visible([signal])) is allowed


def test_actual_automatic_renderer_uses_floor_with_precomputed_quote_evaluation(monkeypatch):
    import app
    from test_workflow_integrity import _RecordingStreamlit, _patch_automatic_snapshot, _automatic_status
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    low = priced(football(1))
    allowed = priced(football(2), (1.2,)*3)
    recorder, catalogs = _RecordingStreamlit(), []
    monkeypatch.setattr(app, 'st', recorder)
    monkeypatch.setattr(app, 'datetime', Clock)
    _patch_automatic_snapshot(monkeypatch, status=_automatic_status(NOW), forecasts=[low, allowed])
    monkeypatch.setattr(app, '_render_wettfinder_games', lambda result, *a, **kw: catalogs.append(result))
    app._render_automated_daily_selection()
    assert [c.key for c in catalogs[0].featured + catalogs[0].additional] == [allowed.key]


@pytest.mark.parametrize('change', ['missing', 'stale_fetch', 'stale_offers', 'foreign_event', 'foreign_market', 'unknown_provider', 'invalid_summary'])
def test_unknown_stale_or_foreign_quote_is_not_misrepresented_as_below_floor(change):
    signal = priced(football())
    raw = {**signal.reference_quote, 'points': [dict(p) for p in signal.reference_quote['points']]}
    raw.pop('executable_quote', None)
    if change == 'missing':
        raw = None
    elif change == 'stale_fetch':
        raw['fetched_at'] = (NOW-timedelta(hours=2)).isoformat()
    elif change == 'stale_offers':
        raw['quoted_at'] = (NOW-timedelta(hours=2)).isoformat()
        for point in raw['points']:
            point['observed_at'] = raw['quoted_at']
    elif change == 'foreign_event':
        raw['fixture_id'] = 999
    elif change == 'foreign_market':
        raw['market_key'] = 'RESULT_AWAY'
    elif change == 'unknown_provider':
        for point in raw['points']:
            point['bookmaker_id'] = None
    else:
        raw['best_odds'] = 1.01
        assert not quote_below_publication_floor(raw, candidate=signal, now=NOW)
        with pytest.raises(ValueError, match='reference quote'):
            replace(signal, reference_quote=raw)
        return
    signal = replace(signal, reference_quote=raw)
    assert visible([signal])
    assert daily3_choices([signal], now=NOW)


def test_filter_cannot_switch_to_opposing_outcome_or_limit_pool_before_replacement():
    home = priced(football(probability=.8))
    away = priced(football(key='RESULT_AWAY', probability=.2), (6.0,)*3)
    assert not visible([home, away])
    alternatives = [priced(football(i, 'DC_1X'), (1.3,)*3) for i in range(2, 5)]
    assert len(daily3_choices([home, *alternatives], now=NOW)) == 3
    assert home.key not in {c.key for c in visible([home, *alternatives])}


@pytest.mark.parametrize('problem', ['stale', 'unidentified'])
def test_stale_or_unidentified_high_offer_cannot_rescue_current_low_prices(problem):
    signal = priced(football(), (1.12, 1.12, 1.30))
    raw = {**signal.reference_quote, 'points': [dict(p) for p in signal.reference_quote['points']]}
    raw.pop('executable_quote', None)
    if problem == 'stale':
        raw['points'][-1]['observed_at'] = (NOW-timedelta(hours=2)).isoformat()
    else:
        raw['points'][-1]['bookmaker_id'] = None
    signal = replace(signal, reference_quote=raw)
    assert not visible([signal])
    assert not daily3_choices([signal], now=NOW)


@pytest.mark.parametrize('price', ['1.12', '1.199999999999'])
def test_new_daily3_reservation_below_floor_cannot_debit_budget(store, price):
    command(store, 'start')
    before = store.history(SCOPE)
    with pytest.raises(Daily3Error, match='1,20'):
        command(store, 'reserve', bet_id=ident(), stake_cents=1000, odds=price, snapshot=snapshot())
    assert store.history(SCOPE) == before


def test_exact_floor_can_be_reserved(store):
    command(store, 'start')
    bet = ident()
    command(store, 'reserve', bet_id=bet, stake_cents=1000, odds='1.2', snapshot=snapshot())
    assert store.history(SCOPE)[DAY]['bets'][bet]['odds'] == '1.2'


def test_old_low_price_contract_remains_readable_idempotent_and_settleable(store, monkeypatch):
    # Write a genuine pre-policy history, then restore the current threshold.
    command(store, 'start')
    bet, action = ident(), ident()
    args = dict(bet_id=bet, stake_cents=1000, odds='1.12', snapshot=snapshot())
    with monkeypatch.context() as old:
        old.setattr('daily3_store.MINIMUM_RECOMMENDED_DECIMAL_ODDS', 1.01)
        command(store, 'reserve', action_id=action, **args)
    command(store, 'reserve', action_id=action, **args)
    assert store.history(SCOPE)[DAY]['bets'][bet]['odds'] == '1.12'
    command(store, 'place', bet_id=bet, revision=1, reference='Previously agreed bookmaker contract')
    command(store, 'settle', bet_id=bet, revision=2, returned_cents=1120, reference='Actual return')
    assert store.history(SCOPE)[DAY]['bets'][bet]['returned_cents'] == 1120
