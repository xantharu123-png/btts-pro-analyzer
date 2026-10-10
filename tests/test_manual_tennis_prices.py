"""An explicit manual scan gets real offers; later filters only read them."""
from copy import deepcopy
from datetime import datetime, timedelta
import json

import pytest

import market_consensus as markets
import tennis_tab as ui
from config_loader import AppConfig
from manual_search_filters import SearchFilters
from riskobet_prices import load_shared_price_overlays
from test_manual_tennis_filters import NOW, START, Recorder, _row
from test_market_consensus import _gea_zhang_quote_fixture


def _search(*args, **kwargs):
    worker = getattr(ui, '_run_tennis_search_worker', None)
    if worker is None:
        pytest.fail('Explicit manual tennis search must fetch actual H2H offers')
    return worker(*args, **kwargs)


def _provider(monkeypatch, events, *, failure=None):
    """Only the external HTTP seam is replaced; discovery and parsing run."""
    paths = []

    def transport(path, api_key, **kwargs):
        paths.append(path)
        assert api_key == 'dummy-key'
        if failure == 'exception':
            raise RuntimeError('https://provider.invalid?apiKey=dummy-key private failure')
        if failure == 'error':
            return None, 'https://provider.invalid?apiKey=dummy-key private failure'
        if path == 'sports/':
            return [{'key': 'tennis_atp_china_open', 'active': True}], None
        if path == 'sports/tennis_atp_china_open/events':
            return events, None
        assert path == 'sports/tennis_atp_china_open/odds'
        assert kwargs['params']['eventIds'].split(',') == sorted(e['id'] for e in events)
        assert kwargs['params']['markets'] == 'h2h'
        return ([] if failure == 'no_offer' else events), None

    monkeypatch.setattr(markets, '_odds_api_json', transport)
    return paths


def _predictions(monkeypatch, rows, *, end_date=None, freeze_clock=True):
    if freeze_clock:
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW if tz else NOW.replace(tzinfo=None)

        monkeypatch.setattr(ui, 'datetime', Clock)
        monkeypatch.setattr(markets, 'datetime', Clock)
    days = []
    monkeypatch.setattr(ui, '_run_daily_scan', lambda day=None: days.append(day) or 'model complete')

    def read(*, date_from, date_to, now):
        assert date_from == '2030-09-30'
        assert date_to == (end_date or '2030-09-30')
        assert now == NOW
        return rows

    monkeypatch.setattr(ui, '_load_current_predictions', read)
    return days


def test_explicit_search_prices_every_future_native_event_not_only_first_ten(monkeypatch):
    # Removing the fetch, truncating its candidates, or choosing the entry side
    # must lose these actual provider prices (including event number twelve).
    rows, events = [], []
    suffixes = ('Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta',
                'Eta', 'Theta', 'Iota', 'Kappa', 'Lambda', 'Mu')
    for index, suffix in enumerate(suffixes):
        row = {**_row(.25 if index == 0 else .75), 'id': index + 1,
               'provider_event_id': f'native-{index}',
               'player_a': f'Arthur {suffix}', 'player_b': f'Zhang {suffix}'}
        _, event = _gea_zhang_quote_fixture(NOW)
        event.update(id=f'odds-{index}', home_team=row['player_b'], away_team=row['player_a'])
        event['bookmakers'][0]['markets'][0]['outcomes'] = [
            {'name': row['player_b'], 'price': 2.70},
            {'name': row['player_a'], 'price': 1.52},
        ]
        rows.append(row)
        events.append(event)
    rows.extend([
        {**_row(), 'id': 90, 'scheduled_start_utc': NOW.isoformat()},
        {**_row(), 'id': 91, 'fixture_source': ''},
        {**_row(), 'id': 92, 'scheduled_start_utc': START.replace(tzinfo=None).isoformat()},
        {**_row(), 'id': 93, 'p_cal': float('nan')},
        {**_row(), 'id': 94, 'player_b': 'Arthur Gea'},
    ])
    original = deepcopy(rows)
    days = _predictions(monkeypatch, rows, end_date='2030-10-01')
    paths = _provider(monkeypatch, events)
    result = _search('2030-09-30', '2030-10-01', odds_api_key='dummy-key')

    observations = result['tennis_price_observations']
    assert len(observations) == 24
    assert {r['provider_event_id'] for r in observations} == {f'native-{i}' for i in range(12)}
    assert {r['selected_competitor']: r['reference_quote']['best_odds']
            for r in observations if r['provider_event_id'] == 'native-11'} == {
                'Arthur Mu': 1.52, 'Zhang Mu': 2.70}
    prices = ui._current_search_prices(rows[:12], now=NOW, price_observations=observations)
    assert prices[1].observed_odds == 2.70
    assert prices[12].observed_odds == 1.52
    assert all(r['fixture_source'] == 'ESPN' for r in observations)
    assert len({r['candidate_id'] for r in observations}) == 24
    assert result['price_check_errors'] == []
    assert days == ['2030-09-30', '2030-10-01']
    assert paths == ['sports/', 'sports/tennis_atp_china_open/events',
                     'sports/tennis_atp_china_open/odds']
    assert 'dummy-key' not in json.dumps(result)
    assert rows[:-2] == original[:-2]
    assert rows[-1] == original[-1]


def test_missing_key_leaves_prices_unknown_without_an_http_request(monkeypatch):
    _predictions(monkeypatch, [_row()])

    def forbidden(*_args, **_kwargs):
        raise AssertionError('A missing key cannot request odds')

    monkeypatch.setattr(markets, '_odds_api_json', forbidden)
    result = _search('2030-09-30', '2030-09-30', odds_api_key=None)
    assert result['tennis_price_observations'] == []
    assert result['price_check_errors'] == ['missing_api_key']


@pytest.mark.parametrize('failure,want_errors', [
    ('no_offer', []), ('error', ['provider_unavailable']),
    ('exception', ['provider_unavailable']),
])
def test_unoffered_or_failed_provider_never_turns_entry_odds_into_current_prices(
        monkeypatch, failure, want_errors):
    _predictions(monkeypatch, [_row()])
    _, event = _gea_zhang_quote_fixture(NOW)
    _provider(monkeypatch, [event], failure=failure)
    result = _search('2030-09-30', '2030-09-30', odds_api_key='dummy-key')
    assert result['tennis_price_observations'] == []
    assert result['price_check_errors'] == want_errors
    assert 'dummy-key' not in json.dumps(result)
    assert 'private failure' not in json.dumps(result)


def test_completion_drops_prices_that_expired_while_the_provider_request_ran(monkeypatch):
    # Validating at scan-start would incorrectly retain these now 25-hour-old
    # prices. The event itself remains future at completion.
    class Clock(datetime):
        current = NOW

        @classmethod
        def now(cls, tz=None):
            return cls.current if tz else cls.current.replace(tzinfo=None)

    monkeypatch.setattr(ui, 'datetime', Clock)
    monkeypatch.setattr(markets, 'datetime', Clock)
    start = (NOW + timedelta(days=2)).isoformat()
    _predictions(monkeypatch, [{**_row(), 'scheduled_start_utc': start}], freeze_clock=False)
    _, event = _gea_zhang_quote_fixture(NOW)
    event['commence_time'] = start

    def transport(path, _key, **_kwargs):
        if path == 'sports/':
            return [{'key': 'tennis_atp_china_open', 'active': True}], None
        if path.endswith('/odds'):
            Clock.current = NOW + timedelta(hours=25)
        return [event], None

    monkeypatch.setattr(markets, '_odds_api_json', transport)
    result = _search('2030-09-30', '2030-09-30', odds_api_key='dummy-key')
    assert result['tennis_price_observations'] == []


class Rerun(Exception):
    pass


class SearchRecorder(Recorder):
    def __init__(self):
        super().__init__()
        self.clicked = True

    def button(self, *_args, **_kwargs):
        clicked, self.clicked = self.clicked, False
        return clicked

    def rerun(self):
        raise Rerun()


def test_button_job_transfers_facts_then_quote_filters_rerender_without_fetch(
        monkeypatch, tmp_path):
    # Keeping the old stdout-only worker or dropping its result on job.done
    # must prevent the real 2.70 offer from reaching the rendered card.
    recorder = SearchRecorder()
    monkeypatch.setattr(ui, 'st', recorder)
    monkeypatch.setattr(ui, 'load_app_config', lambda *_args: AppConfig(odds_api_key='dummy-key'), raising=False)
    row = _row(.25)
    before = deepcopy(row)
    days = _predictions(monkeypatch, [row])
    _, event = _gea_zhang_quote_fixture(NOW)
    paths = _provider(monkeypatch, [event])
    cache = tmp_path / 'wettfinder.json'
    tomorrow = '2030-10-01'
    later_row = {**_row(.75), 'id': 2, 'match_date': tomorrow,
                 'provider_event_id': 'tomorrow-1',
                 'scheduled_start_utc': (START + timedelta(days=1)).isoformat()}
    later_candidate, later_event = _gea_zhang_quote_fixture(NOW)
    later_candidate.update(fixture_source='ESPN', provider_event_id='tomorrow-1',
                           scheduled_start=later_row['scheduled_start_utc'])
    later_event.update(id='tomorrow-odds', commence_time=later_row['scheduled_start_utc'])
    later_prices = markets._collect_tennis_event_prices(later_event, [later_candidate], now=NOW)
    cache.write_text(json.dumps({'tennis_price_observations': later_prices}), encoding='utf-8')
    original_cache = cache.read_bytes()
    monkeypatch.setattr(ui, 'load_shared_price_overlays',
        lambda candidates, *, now: load_shared_price_overlays(candidates, now=now, path=cache))
    job = {'state': 'idle'}
    monkeypatch.setattr(ui.scan_jobs, 'get_job', lambda *_args: job)

    def start(_key, worker, *, args, kwargs=None):
        job.update(state='done', result=worker(*args, **(kwargs or {})))

    def clear(_key):
        job.clear()
        job['state'] = 'idle'

    monkeypatch.setattr(ui.scan_jobs, 'start_job', start)
    monkeypatch.setattr(ui.scan_jobs, 'clear_job', clear)
    with pytest.raises(Rerun):
        ui.render_tennis_finder(NOW.date(), NOW.date())
    assert len(recorder.session_state.get('tennis_search_price_observations', [])) == 2
    assert 'dummy-key' not in json.dumps(recorder.session_state)
    assert job == {'state': 'idle'}

    for filters, should_show in ((SearchFilters(probability_min=.74, probability_max=.76,
                                   quote_min=2.60, quote_max=2.80), True),
                                 (SearchFilters(quote_max=2.60), False)):
        recorder.metrics.clear()
        ui.render_tennis_finder(NOW.date(), NOW.date(), search_filters=filters)
        assert (('Letzte Quote', '2.70') in recorder.metrics) is should_show
        if should_show:
            assert ('Modell', '75.0%') in recorder.metrics
            assert ('info', 'Modellfavorit: Zhang Zhizhen') in recorder.messages
    assert len(paths) == 3 and days == ['2030-09-30']
    assert row == before

    def later_read(*, date_from, date_to, now):
        assert (date_from, date_to, now) == (tomorrow, tomorrow, NOW)
        return [later_row]

    monkeypatch.setattr(ui, '_load_current_predictions', later_read)
    recorder.metrics.clear()
    ui.render_tennis_finder(tomorrow, tomorrow, search_filters=SearchFilters(quote_max=1.60))
    assert ('Letzte Quote', '1.52') in recorder.metrics
    assert len(paths) == 3 and days == ['2030-09-30']
    assert cache.read_bytes() == original_cache
