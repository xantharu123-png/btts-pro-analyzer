"""A price-only artifact refresh reaches existing sessions before admission."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib
import json

import pytest

from test_daily3_selection import NOW, football
from test_publication_odds_floor import priced


def receipt(price, *, fetched=NOW, identity='shared-native'):
    signal = priced(football(key='BTTS_YES'), (price,)*3)
    row = dict(vars(signal), candidate_id=identity, key=identity, source='football_challenge')
    quote = deepcopy(signal.reference_quote)
    quote.pop('executable_quote', None)
    quote['candidate_id'] = identity
    quote['fetched_at'] = quote['quoted_at'] = fetched.isoformat()
    for point in quote['points']:
        point['observed_at'] = fetched.isoformat()
    row['reference_quote'] = quote
    return row


@pytest.mark.parametrize('shared_price,expected', [(1.01, 1.01), (2.0, 2.0)])
def test_latest_exact_receipt_is_chosen_before_floor_across_consumer_ids(shared_price, expected):
    module = importlib.import_module('quote_publication')
    merge = getattr(module, 'latest_reference_quotes', None)
    assert callable(merge), 'renderers need the latest exact native quote, not cached positive admission'
    consumer = priced(football(key='BTTS_YES'), (1.50,)*3)
    source = receipt(shared_price, fetched=NOW+timedelta(minutes=5))
    before = deepcopy(source), deepcopy(vars(consumer))
    result = merge([consumer], {consumer.candidate_id: consumer.reference_quote},
        shared_rows=[source], now=NOW+timedelta(minutes=10))
    assert result[consumer.candidate_id].best_odds == expected
    assert result[consumer.candidate_id].candidate_id == consumer.candidate_id
    assert (source, vars(consumer)) == before


def test_btts_cached_offer_does_not_cherry_pick_old_positive_before_latest_low():
    from quote_publication import native_football_publication_offer
    old = receipt(1.50, identity='manual-old')
    latest = receipt(1.01, fetched=NOW+timedelta(minutes=5))
    result = native_football_publication_offer([old, latest], fixture_id=1,
        scheduled_start=old['scheduled_start'], market_key='BTTS_YES', selection='Ja',
        home_team=old['home_team'], away_team=old['away_team'], now=NOW+timedelta(minutes=10))
    assert result == (None, None)


def test_manual_football_existing_session_adopts_new_low_quote_without_a_scan(monkeypatch, tmp_path):
    import quote_publication as publication
    from manual_search_filters import SearchFilters
    from test_manual_football_filters import _quote, _render
    from test_manual_selection_coherence import _row
    row = _row('BTTS_YES', complete=True, probability=.75)
    now = datetime.now(timezone.utc)
    old = _quote(row, 1.50, now-timedelta(minutes=10))
    path = tmp_path/'wettfinder_latest.json'
    path.write_text(json.dumps({'model_candidates': []}), encoding='utf-8')
    monkeypatch.setattr(publication, 'DEFAULT_QUOTE_STATE_PATH', path, raising=False)
    render, _, snapshot = _render(monkeypatch, [row], quotes={row.candidate_id: old})
    assert render(SearchFilters()) == [row.candidate_id]
    before = deepcopy(snapshot)
    native = dict(vars(row), candidate_id='native-shared', source='football_challenge', sport='Fußball',
                  scheduled_start=row.kickoff)
    quote = replace(_quote(row, 1.01, now), candidate_id='native-shared')
    native['reference_quote'] = quote.to_dict()
    path.write_text(json.dumps({'model_candidates': [native]}), encoding='utf-8')
    artifact = path.read_bytes()
    assert render(SearchFilters()) == []
    assert snapshot == before and path.read_bytes() == artifact


def test_tennis_explicit_session_offer_yields_to_newer_shared_low_quote(monkeypatch, tmp_path):
    import quote_publication as publication
    import tennis_tab
    from test_manual_tennis_filters import NOW as TENNIS_NOW, _row, _quote
    old = _quote(odds=1.50, observed=TENNIS_NOW-timedelta(minutes=10))
    latest = _quote(odds=1.01, observed=TENNIS_NOW)
    path = tmp_path/'wettfinder_latest.json'
    path.write_text(json.dumps({'tennis_price_observations': []}), encoding='utf-8')
    monkeypatch.setattr(publication, 'DEFAULT_QUOTE_STATE_PATH', path, raising=False)
    assert tennis_tab._current_search_prices([_row()], now=TENNIS_NOW, price_observations=[old])[1].observed_odds == 1.50
    path.write_text(json.dumps({'tennis_price_observations': [latest]}), encoding='utf-8')
    assert tennis_tab._current_search_prices([_row()], now=TENNIS_NOW, price_observations=[old]) == {}


@pytest.mark.parametrize('change', ['older', 'foreign_start', 'foreign_market', 'foreign_participant', 'failed_attempt'])
def test_newer_manual_offer_is_not_replaced_by_old_foreign_or_failed_shared_evidence(change):
    from quote_publication import latest_reference_quotes
    consumer = priced(football(key='BTTS_YES'), (2.0,)*3)
    source = receipt(1.01, fetched=NOW-timedelta(minutes=5) if change == 'older' else NOW+timedelta(minutes=5))
    if change == 'foreign_start':
        source['scheduled_start'] = (NOW+timedelta(hours=5)).isoformat()
    elif change == 'foreign_market':
        source['market_key'] = 'BTTS_NO'
        source['selection'] = 'Nein'
    elif change == 'foreign_participant':
        source['home_team'] = 'Different home participant'
    elif change == 'failed_attempt':
        source['reference_quote'] = None
        source['price_checked_at'] = (NOW+timedelta(minutes=5)).isoformat()
    result = latest_reference_quotes([consumer], {consumer.candidate_id: consumer.reference_quote},
        shared_rows=[source], now=NOW+timedelta(minutes=10))
    assert result[consumer.candidate_id].best_odds == 2.0
    assert result[consumer.candidate_id].fetched_at == NOW.isoformat()


def test_identical_same_clock_native_copies_ignore_only_consumer_id_but_conflicts_withhold():
    from quote_publication import latest_reference_quotes
    consumer = priced(football(key='BTTS_YES'), (1.50,)*3)
    # Model fixture metadata and the quote receipt native fields are identical.
    identical = receipt(1.50)
    assert latest_reference_quotes([consumer], {consumer.candidate_id: consumer.reference_quote},
        shared_rows=[identical], now=NOW)[consumer.candidate_id].best_odds == 1.50
    conflict = receipt(1.01)
    assert latest_reference_quotes([consumer], {consumer.candidate_id: consumer.reference_quote},
        shared_rows=[conflict], now=NOW) == {}


def test_same_model_15k_adopts_price_only_refresh_without_replacing_manual_state():
    import challenge_15k
    from market_consensus import serialize_consensus_map, deserialize_consensus_map
    from test_challenge_15k import candidate
    from test_manual_football_filters import _quote
    model = candidate('1:BTTS_YES', 1, .75, kickoff=NOW+timedelta(hours=4))
    old = _quote(model, 1.50, NOW)
    new = _quote(model, 1.01, NOW+timedelta(minutes=5))
    scope = {'date': NOW.date().isoformat(), 'league_ids': [39]}
    current = dict(scope=scope, scanned_at=NOW.isoformat(), challenge_model_candidates=[model],
        reference_quotes=serialize_consensus_map({model.candidate_id: old}), manual_state={'keep': True})
    scheduled = dict(current, challenge_model_candidates=[deepcopy(model)],
        reference_quotes=serialize_consensus_map({model.candidate_id: new}), manual_state={'replace': False})
    before = deepcopy(current), deepcopy(scheduled)
    preferred = challenge_15k._prefer_scheduled_snapshot(current, scheduled, scope=scope,
        now=NOW+timedelta(minutes=10))
    assert deserialize_consensus_map(preferred['reference_quotes'])[model.candidate_id].best_odds == 1.01
    assert preferred['challenge_model_candidates'] is current['challenge_model_candidates']
    assert preferred['manual_state'] == {'keep': True} and preferred['scanned_at'] == current['scanned_at']
    assert (current, scheduled) == before
    assert challenge_15k._prefer_scheduled_snapshot(preferred, scheduled, scope=scope,
        now=NOW+timedelta(minutes=10)) is preferred


@pytest.mark.parametrize('change', ['model', 'model_clock', 'scope'])
def test_15k_quote_adoption_cannot_replace_a_different_model_revision_or_scope(change):
    import challenge_15k
    from market_consensus import serialize_consensus_map
    from test_challenge_15k import candidate
    from test_manual_football_filters import _quote
    model = candidate('1:BTTS_YES', 1, .75, kickoff=NOW+timedelta(hours=4))
    scope = {'date': NOW.date().isoformat(), 'league_ids': [39]}
    current = dict(scope=scope, scanned_at=NOW.isoformat(), challenge_model_candidates=[model],
        reference_quotes=serialize_consensus_map({model.candidate_id: _quote(model, 2.0, NOW)}))
    scheduled = dict(current, challenge_model_candidates=[deepcopy(model)],
        reference_quotes=serialize_consensus_map({model.candidate_id: _quote(model, 1.01, NOW+timedelta(minutes=5))}))
    if change == 'model':
        scheduled['challenge_model_candidates'][0].probability = .5
    elif change == 'model_clock':
        scheduled['scanned_at'] = (NOW-timedelta(minutes=1)).isoformat()
    else:
        scheduled['scope'] = dict(scope, league_ids=[140])
    assert challenge_15k._prefer_scheduled_snapshot(current, scheduled, scope=scope,
        now=NOW+timedelta(minutes=10)) is current


def test_15k_same_clock_quote_conflict_stays_withheld_across_rerenders_until_newer_receipt():
    import challenge_15k
    from market_consensus import serialize_consensus_map, deserialize_consensus_map
    from test_challenge_15k import candidate
    from test_manual_football_filters import _quote
    model = candidate('1:BTTS_YES', 1, .75, kickoff=NOW+timedelta(hours=4))
    scope = {'date': NOW.date().isoformat(), 'league_ids': [39]}
    current = dict(scope=scope, scanned_at=NOW.isoformat(), challenge_model_candidates=[model],
        reference_quotes=serialize_consensus_map({model.candidate_id: _quote(model, 1.01, NOW)}))
    scheduled = dict(current, challenge_model_candidates=[deepcopy(model)],
        reference_quotes=serialize_consensus_map({model.candidate_id: _quote(model, 2.0, NOW)}))
    first = challenge_15k._prefer_scheduled_snapshot(current, scheduled, scope=scope, now=NOW)
    assert not deserialize_consensus_map(first['reference_quotes'])
    again = challenge_15k._prefer_scheduled_snapshot(first, scheduled, scope=scope, now=NOW)
    assert not deserialize_consensus_map(again['reference_quotes'])
    later = dict(scheduled, reference_quotes=serialize_consensus_map({model.candidate_id:
        _quote(model, 2.0, NOW+timedelta(minutes=1))}))
    recovered = challenge_15k._prefer_scheduled_snapshot(again, later, scope=scope, now=NOW+timedelta(minutes=1))
    assert deserialize_consensus_map(recovered['reference_quotes'])[model.candidate_id].best_odds == 2.0


@pytest.mark.parametrize('grows_after_stat', [False, True])
def test_shared_receipt_read_is_byte_bounded_before_json_allocation(monkeypatch, tmp_path, grows_after_stat):
    import quote_publication as publication
    from pathlib import Path
    from types import SimpleNamespace
    path = tmp_path/'wettfinder_latest.json'
    path.write_text(json.dumps({'model_candidates': [receipt(1.50)]}), encoding='utf-8')
    original = path.read_bytes()
    monkeypatch.setattr(publication, 'MAX_QUOTE_STATE_BYTES', 20, raising=False)
    if grows_after_stat:
        stat = Path.stat
        monkeypatch.setattr(Path, 'stat', lambda self, *a, **kw:
            SimpleNamespace(st_size=1) if self == path else stat(self, *a, **kw))
    assert publication.read_shared_quote_rows(path) == []
    assert path.read_bytes() == original


@pytest.mark.parametrize('renderer', ['_render_model_challenge', '_render_price_check'])
@pytest.mark.parametrize('same_clock_conflict', [False, True])
def test_newer_manual_15k_model_uses_new_exact_price_from_older_daily_model(monkeypatch, tmp_path, renderer, same_clock_conflict):
    import challenge_15k as ui
    import quote_publication as publication
    from market_consensus import serialize_consensus_map
    from test_challenge_15k import candidate
    from test_manual_football_filters import _quote
    from types import SimpleNamespace
    model = candidate('manual-15k', 1, .75, kickoff=NOW+timedelta(hours=4))
    old = _quote(model, 1.50, NOW)
    fresh = replace(_quote(model, 2.0 if same_clock_conflict else 1.01, NOW+timedelta(minutes=5)),
                    candidate_id='older-daily-model')
    native = dict(vars(model), candidate_id='older-daily-model', source='football_challenge',
        sport='Fußball', scheduled_start=model.kickoff, modeled_at=(NOW-timedelta(hours=2)).isoformat(),
        probability=.40, reference_quote=fresh.to_dict())
    path = tmp_path/'wettfinder_latest.json'
    path.write_text(json.dumps({'generated_at': (NOW-timedelta(hours=1)).isoformat(),
        'model_candidates': [native]}, default=str), encoding='utf-8')
    monkeypatch.setattr(publication, 'DEFAULT_QUOTE_STATE_PATH', path)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW+timedelta(minutes=10)
    monkeypatch.setattr(ui, 'datetime', Clock)
    messages = []
    monkeypatch.setattr(ui, 'st', SimpleNamespace(info=lambda value: messages.append(value),
        caption=lambda *_a: None, subheader=lambda *_a: pytest.fail('old price leaked a public 15K tip')))
    snapshot = dict(scanned_at=NOW.isoformat(), challenge_model_candidates=[model],
        forecast_shortlist=[model], shortlist=[model], price_candidates=[],
        reference_quotes=serialize_consensus_map({} if same_clock_conflict else {model.candidate_id: old}),
        manual_state={'keep': 'newer manual model'})
    if same_clock_conflict:
        snapshot['reference_quote_conflicts'] = {model.candidate_id: (NOW+timedelta(minutes=5)).isoformat()}
    before = deepcopy(snapshot), path.read_bytes()
    getattr(ui, renderer)(snapshot, SimpleNamespace(pending_tickets=lambda: []),
                          {'current_balance': 100.0, 'stake_fraction': .05})
    assert messages
    assert (snapshot, path.read_bytes()) == before
