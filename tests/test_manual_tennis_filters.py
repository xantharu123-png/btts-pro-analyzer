"""Manual tennis filtering reads the visible revision and exact stored offers."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

import tennis_tab as ui
from manual_search_filters import SearchFilters
from market_consensus import parse_h2h_event_consensus
from riskobet_prices import load_shared_price_overlays
from tennis import shadow
from tennis.prediction_revisions import REVISION_SCHEMA, append_revision
from test_market_consensus import _gea_zhang_quote_fixture


NOW = datetime(2030, 9, 30, 8, tzinfo=timezone.utc)
START = NOW + timedelta(hours=1)


class Recorder:
    def __init__(self):
        self.session_state = {}
        self.messages = []
        self.metrics = []

    def button(self, *_args, **_kwargs):
        return False

    def container(self, **_kwargs):
        return nullcontext()

    def expander(self, *_args, **_kwargs):
        return nullcontext()

    def metric(self, label, value, **_kwargs):
        self.metrics.append((label, value))

    def __getattr__(self, kind):
        if kind in {'subheader', 'markdown', 'caption', 'info', 'warning', 'write', 'error'}:
            return lambda value, **_kwargs: self.messages.append((kind, value))
        raise AttributeError(kind)


def _row(probability=.25):
    return dict(id=1, created_utc=(NOW-timedelta(hours=2)).timestamp(),
        match_date=NOW.date().isoformat(), tour='ATP', tournament='China Open',
        provider_event_id='186197', fixture_source='ESPN', scheduled_start_utc=START.isoformat(),
        surface='Hard', best_of=3, player_a='Arthur Gea', player_b='Zhang Zhizhen',
        p_raw=probability, p_cal=probability, markets_json='{}', context_json='{}',
        gates_json=json.dumps({'Belag': {'passed': True, 'detail': 'Hard'}}),
        verdict='KEINE WETTE', recommended_side=None, recommended_edge=None,
        odds_a=1.01, odds_b=9.99, settled=0,
        model_version=shadow.TENNIS_MODEL_VERSION, policy_version=shadow.TENNIS_POLICY_VERSION)


def _quote(*, selected='Zhang Zhizhen', odds=1.52, observed=NOW):
    row, event = _gea_zhang_quote_fixture(observed, selected=selected)
    row.update(fixture_source='ESPN', provider_event_id='186197')
    name = 'Zhizhen Zhang' if selected == 'Zhang Zhizhen' else selected
    for outcome in event['bookmakers'][0]['markets'][0]['outcomes']:
        if outcome['name'] == name:
            outcome['price'] = odds
    quote = parse_h2h_event_consensus(event, [row], fetched_at=observed)[row['candidate_id']]
    return {**row, 'reference_quote': quote.to_dict(), 'quote_provider_event_id': quote.provider_event_id}


@pytest.fixture
def offline(tmp_path, monkeypatch):
    import requests

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Filtering must not fetch, scan or migrate storage')

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is not None else NOW.replace(tzinfo=None)

    monkeypatch.setattr(ui, 'datetime', Clock)
    monkeypatch.setattr(ui, 'st', Recorder())
    monkeypatch.setattr(ui.scan_jobs, 'get_job', lambda *_args: {'state': 'idle'})
    monkeypatch.setattr(ui.scan_jobs, 'start_job', forbidden)
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    monkeypatch.setattr(shadow, 'ensure_schema', forbidden)
    path = tmp_path / 'tennis.db'
    quote_path = tmp_path / 'wettfinder_latest.json'
    monkeypatch.setattr(ui, 'DB_PATH', path)
    calls = []

    def stored_quotes(candidates, *, now):
        calls.append(now)
        return load_shared_price_overlays(candidates, now=now, path=quote_path)

    # This is an I/O seam only: the real native identity/side/clock validator runs.
    monkeypatch.setattr(ui, 'load_shared_price_overlays', stored_quotes, raising=False)

    def prepare(row=None, quotes=(), revision=None, attempts=None):
        row = deepcopy(row or _row())
        with sqlite3.connect(path) as conn:
            columns = ','.join(f'{key} '+('INTEGER' if key in {'id', 'settled'} else 'REAL' if key in {'created_utc', 'p_raw', 'p_cal', 'odds_a', 'odds_b'} else 'TEXT') for key in row)
            conn.execute('CREATE TABLE predictions ('+columns+')')
            conn.execute('INSERT INTO predictions VALUES ('+','.join('?' for _ in row)+')', tuple(row.values()))
            if revision is not None:
                conn.executescript(REVISION_SCHEMA)
                append_revision(conn, row['id'], {**row, **revision})
        quote_path.write_text(json.dumps({'model_candidates': list(quotes),
            'price_check_attempts': attempts or {}}), encoding='utf-8')
        return path.read_bytes(), quote_path.read_bytes()

    return prepare, path, quote_path, calls


def _render(filters):
    ui.render_tennis_finder(NOW.date(), NOW.date(), search_filters=filters)
    return ui.st


def test_filter_probability_and_quote_refer_to_the_rendered_favorite_and_original_offer(offline):
    prepare, path, quote_path, calls = offline
    original_db, original_quotes = prepare(quotes=[_quote(observed=NOW-timedelta(minutes=7))])
    rendered = _render(SearchFilters(probability_min=.74, probability_max=.76, quote_min=1.50, quote_max=1.55))
    assert ('Modell', '75.0%') in rendered.metrics
    assert ('Letzte Quote', '1.52') in rendered.metrics
    assert ('info', 'Modellfavorit: Zhang Zhizhen') in rendered.messages
    assert any('09:53' in str(value) for kind, value in rendered.messages if kind == 'caption')
    assert calls == [NOW]
    assert path.read_bytes() == original_db and quote_path.read_bytes() == original_quotes


@pytest.mark.parametrize('filters', [
    SearchFilters(probability_min=.20, probability_max=.30),
    SearchFilters(quote_min=1.60), SearchFilters(quote_max=1.50),
    SearchFilters(market_kind='over_2_5_sets'),
])
def test_nonmatching_filters_hide_cards_without_changing_the_model(offline, filters):
    prepare, path, quote_path, _ = offline
    before = prepare(quotes=[_quote()])
    rendered = _render(filters)
    assert not rendered.metrics
    assert ('info', 'Keine Tennis-Auswahl passt zu deinen Filtern.') in rendered.messages
    assert (path.read_bytes(), quote_path.read_bytes()) == before


@pytest.mark.parametrize('change', [
    {'fixture_source': 'OTHER'}, {'provider_event_id': 'different'},
    {'scheduled_start': (START+timedelta(seconds=1)).isoformat()},
    {'scheduled_start': START.replace(tzinfo=None).isoformat()},
    {'competitor_a': 'Other Player'}, {'competitor_b': 'Other Player'},
    {'selected_competitor': 'Arthur Gea'},
])
def test_foreign_or_incomplete_native_offer_cannot_pass_an_active_quote_filter(offline, change):
    prepare, *_ = offline
    prepare(quotes=[{**_quote(), **change}])
    assert not _render(SearchFilters(quote_min=1.20)).metrics


def test_opposite_side_offer_and_entry_prices_are_not_used_for_the_selected_player(offline):
    prepare, *_ = offline
    prepare(quotes=[_quote(selected='Arthur Gea', odds=1.80)])
    assert not _render(SearchFilters(quote_min=1.20)).metrics


@pytest.mark.parametrize('observed', [NOW+timedelta(seconds=1), NOW-timedelta(hours=25)])
def test_future_and_expired_offers_do_not_supply_filter_prices(offline, observed):
    prepare, *_ = offline
    prepare(quotes=[_quote(observed=observed)])
    assert not _render(SearchFilters(quote_min=1.20)).metrics


def test_a_valid_no_quote_attempt_does_not_make_a_future_offer_current(offline):
    prepare, *_ = offline
    quote = {**_quote(observed=NOW+timedelta(seconds=1)),
        'key': 'native-B', 'modeled_at': (NOW-timedelta(hours=2)).isoformat()}
    prepare(quotes=[quote], attempts={'native-B': NOW.isoformat()})
    assert not _render(SearchFilters(quote_min=1.20)).metrics


def test_unknown_price_is_allowed_without_a_quote_range_but_is_never_invented(offline):
    prepare, *_ = offline
    prepare()
    rendered = _render(SearchFilters(probability_min=.70))
    assert ('Modell', '75.0%') in rendered.metrics
    assert all('Quote' not in label for label, _ in rendered.metrics)


def test_known_quote_below_floor_is_hidden_even_with_default_filters(offline):
    prepare, *_ = offline
    prepare(quotes=[_quote(odds=1.02)])
    assert not _render(SearchFilters()).metrics


def test_latest_revision_is_filtered_and_rendered_without_rewriting_the_entry(offline):
    prepare, path, quote_path, _ = offline
    original = _row(.80)
    before = prepare(original, quotes=[_quote()], revision={
        'created_utc': (NOW-timedelta(minutes=5)).timestamp(), 'p_raw': .25, 'p_cal': .25})
    rendered = _render(SearchFilters(probability_min=.74, probability_max=.76, quote_min=1.20))
    assert ('Modell', '75.0%') in rendered.metrics
    assert ('info', 'Modellfavorit: Zhang Zhizhen') in rendered.messages
    assert ('Letzte Quote', '1.52') in rendered.metrics
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT p_cal, odds_a, odds_b FROM predictions').fetchone() == (.80, 1.01, 9.99)
    assert (path.read_bytes(), quote_path.read_bytes()) == before


def test_latest_side_flip_cannot_keep_the_old_favorites_quote(offline):
    prepare, *_ = offline
    prepare(_row(.80), quotes=[_quote(selected='Arthur Gea')], revision={
        'created_utc': (NOW-timedelta(minutes=5)).timestamp(), 'p_raw': .25, 'p_cal': .25})
    assert not _render(SearchFilters(quote_min=1.20)).metrics


def test_filter_rerender_reuses_storage_without_scan_and_retains_current_same_side_offer(offline):
    prepare, path, quote_path, calls = offline
    before = prepare(quotes=[_quote(observed=NOW-timedelta(minutes=10))], revision={
        'created_utc': (NOW-timedelta(minutes=5)).timestamp(), 'p_raw': .24, 'p_cal': .24})
    first = _render(SearchFilters(probability_min=.75, quote_min=1.20))
    assert ('Modell', '76.0%') in first.metrics and ('Letzte Quote', '1.52') in first.metrics
    first.metrics.clear()
    second = _render(SearchFilters(quote_min=1.60))
    assert not second.metrics and calls == [NOW, NOW]
    assert (path.read_bytes(), quote_path.read_bytes()) == before


def test_manual_current_reader_hides_replaced_native_pair_without_rewriting_history(tmp_path, monkeypatch):
    from test_tennis_fixture_availability import correction
    from test_tennis_live_worker import NOW as native_now, configure, run_batch
    import requests

    context_path, predictions_path, _, _ = configure(monkeypatch, tmp_path)
    run_batch(context_path, predictions_path)
    monkeypatch.setattr(ui, 'DB_PATH', predictions_path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Reading native availability must not fetch or migrate storage')

    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    monkeypatch.setattr(shadow, 'ensure_schema', forbidden)
    before_clock = native_now + timedelta(seconds=3)
    rows = ui._load_current_predictions(now=before_clock)
    assert len(rows) == 1 and rows[0]['provider_event_id'] == '201'
    original_predictions = predictions_path.read_bytes()

    correction(context_path, 'replacement', clock=native_now + timedelta(seconds=10))
    corrected_context = context_path.read_bytes()
    assert ui._load_current_predictions(now=native_now + timedelta(seconds=11)) == []
    # A current-view exclusion never erases the original or its historical view.
    assert len(ui._load_current_predictions(now=before_clock)) == 1
    assert len(shadow.latest_predictions(predictions_path, pending_only=False,
                                       as_of=native_now + timedelta(seconds=11))) == 1
    assert predictions_path.read_bytes() == original_predictions
    assert context_path.read_bytes() == corrected_context
