"""Offline regressions for the 02 October scanner/mathematical audit."""
from datetime import datetime, timezone
from dataclasses import replace
from types import SimpleNamespace

import pytest
import requests

from scripts import tennis_daily as daily
from tennis import simulator as sim
from tennis.predict import predict_match
from tennis.state_codec import encode_state, decode_state
from test_tennis_predict import _synthetic_state


def test_midnight_scan_discovers_current_zurich_day():
    assert daily._default_scan_date(datetime(2026, 10, 1, 22, 5, tzinfo=timezone.utc)) == '2026-10-02'
    assert daily._default_scan_date(datetime(2026, 10, 25, 23, 5, tzinfo=timezone.utc)) == '2026-10-26'


def test_wta_slam_is_bo3_and_atp_qualifying_is_not_main_draw():
    assert daily.match_format('WTA', 'Wimbledon', 5, {}) == 3
    assert daily.match_format('ATP', 'Wimbledon', 5, {'qualifying': True}) == 3
    assert daily.match_format('ATP', 'Wimbledon Qualifying', 5, {}) == 3
    assert daily.match_format('ATP', 'Wimbledon', 5, {}) == 5
    with pytest.raises(ValueError):
        daily.match_format('WTA', 'Wimbledon', 5, {'best_of': 5})


def test_all_fixture_transports_failed_are_not_an_empty_day(monkeypatch):
    def unavailable(*args, **kwargs):
        raise requests.HTTPError('offline 503')
    monkeypatch.setattr(daily.requests, 'get', unavailable)
    with pytest.raises(daily.ProviderFetchError):
        daily.fetch_fixtures('2026-10-02')


def test_valid_empty_primary_is_a_success_without_another_provider(monkeypatch):
    monkeypatch.setattr(daily, 'fetch_fixtures_sofascore', lambda *a, **k: [])
    monkeypatch.setattr(daily, 'fetch_fixtures_espn', lambda *a, **k: pytest.fail('extra provider'))
    assert daily.fetch_fixtures('2026-10-02') == []


def test_failed_sources_make_daily_exit_nonzero_without_a_database(monkeypatch):
    monkeypatch.setattr(daily.requests, 'get', lambda *a, **k: (_ for _ in ()).throw(requests.HTTPError('offline 503')))
    monkeypatch.setattr(daily, 'auto_settle_completed', lambda: 0)
    monkeypatch.setattr(daily, 'tournament_surface_map', lambda *_: {})
    monkeypatch.setattr(daily.shadow, 'workload_history', lambda *_: [])
    monkeypatch.setattr(daily.shadow, 'summary', lambda: {})
    assert daily._run_daily(SimpleNamespace(date='2026-10-02', allow_legacy_model=False)) == 1


def test_espn_partial_response_keeps_valid_tour_and_reports_failure(monkeypatch):
    from test_context_tennis_capture import competition
    good = competition(status={'type': {'state': 'pre', 'name': 'STATUS_SCHEDULED', 'completed': False}})
    for index, player in enumerate(good['competitors']):
        player['athlete'] = {'displayName': ('Alpha', 'Beta')[index]}
    def events(tour, day):
        if tour == 'wta':
            raise daily.ProviderFetchError(['offline WTA unavailable'])
        return [{'id': '101', 'name': 'Test Open', 'groupings': [
            {'grouping': {'slug': 'mens-singles'}, 'competitions': [good]}]}]
    monkeypatch.setattr(daily, '_fetch_espn_events', events)
    monkeypatch.setattr('tennis.live_context.active_worker', lambda: None)
    with pytest.raises(daily.ProviderFetchError) as failure:
        daily.fetch_fixtures_espn('2026-10-02')
    assert len(failure.value.fixtures) == 1
    assert failure.value.fixtures[0]['tour'] == 'ATP'
    assert failure.value.issues == ['offline WTA unavailable']


def test_rejected_historical_result_is_visible_not_silently_skipped(monkeypatch):
    row = dict(id=9, match_date='2026-09-01', tour='WTA', fixture_source='ESPN',
        provider_event_id='9', player_a='Alpha', player_b='Beta')
    monkeypatch.setattr(daily.shadow, 'pending_predictions', lambda: [row])
    monkeypatch.setattr(daily, 'fetch_results_espn', lambda *a: [dict(
        provider_event_id='9', player_a='Alpha', player_b='Beta', winner='Alpha',
        winner_sets=2, loser_sets=0, termination='normal', result_observed_at='2026-09-01T17:00:00Z')])
    monkeypatch.setattr(daily.shadow, 'settle', lambda *a, **k: (_ for _ in ()).throw(ValueError('legacy Bo5 format')))
    with pytest.raises(daily.SettlementBatchError) as failure:
        daily.auto_settle_completed(today='2026-10-02')
    assert failure.value.issues[0]['prediction_id'] == 9
    assert failure.value.issues[0]['reason'] == 'settlement_rejected'


def test_failed_sofascore_results_cannot_be_a_successful_daily_scan(monkeypatch):
    row = dict(id=9, match_date='2026-09-01', tour='ATP', fixture_source='SofaScore',
        provider_event_id='9', player_a='Alpha', player_b='Beta')
    monkeypatch.setattr(daily.shadow, 'pending_predictions', lambda: [row])
    monkeypatch.setattr(daily.requests, 'get', lambda *a, **k: (_ for _ in ()).throw(requests.HTTPError('offline 503')))
    monkeypatch.setattr(daily, 'fetch_fixtures', lambda *a, **k: [])
    monkeypatch.setattr(daily, 'tournament_surface_map', lambda *_: {})
    monkeypatch.setattr(daily.shadow, 'workload_history', lambda *_: [])
    monkeypatch.setattr(daily.shadow, 'summary', lambda: {})
    with pytest.raises(daily.SettlementBatchError) as failure:
        daily.auto_settle_completed(today='2026-10-02')
    assert failure.value.issues[0]['reason'] == 'result_source_failed'
    assert daily._run_daily(SimpleNamespace(date='2026-10-02', allow_legacy_model=False)) == 1


def test_valid_empty_sofascore_results_are_not_a_failed_response(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {'events': []}
    monkeypatch.setattr(daily.requests, 'get', lambda *a, **k: Response())
    assert daily.fetch_results_sofascore('2026-10-02') == []


def test_scan_wta_slam_passes_bo3_to_predict_and_storage(monkeypatch):
    captured = []
    def predict(state, a, b, surface, best_of, **kwargs):
        captured.append((kwargs['tour'], best_of))
        return SimpleNamespace(context_evidence={})
    monkeypatch.setattr(daily, '_load_models', lambda *a, **k: ({'WTA': object()}, {}, []))
    monkeypatch.setattr(daily, 'predict_match', predict)
    monkeypatch.setattr('tennis.live_context.active_worker', lambda: None)
    monkeypatch.setattr('tennis.surface_evidence.build_surface_evidence', lambda *a: None)
    monkeypatch.setattr('tennis.customer_facts.attach_customer_statistics', lambda *a, **k: None)
    monkeypatch.setattr(daily.shadow, 'store_prediction', lambda *a, **k: 1)
    fixture = dict(tour='WTA', tournament='Wimbledon', player_a='Alpha', player_b='Beta',
        match_date='2026-10-03', scheduled_start_utc='2026-10-03T12:00:00Z')
    result = daily.scan_fixtures('2026-10-03', [fixture], decision_at=datetime(2026,10,2,tzinfo=timezone.utc),
        surfaces={'wimbledon': ('Grass', 5, 'Wimbledon', False)}, workload_history=[])
    assert captured == [('WTA', 3)] and result['stored'] == 1 and not result['errors']


def test_point_tiebreak_uses_serve_points_and_matches_reference():
    pa, pb = sim.hold_to_point_prob(.8), sim.hold_to_point_prob(.7)
    assert sim.serve_tiebreak_win_prob(pa, pb, a_serves_first=True) == pytest.approx(.5800890825346847)
    assert sim.serve_tiebreak_win_prob(pa, pb, a_serves_first=False) == pytest.approx(.5800890825346847)
    assert sim.serve_tiebreak_win_prob(pa, pb) + sim.serve_tiebreak_win_prob(pb, pa) == pytest.approx(1)


def test_bo5_deciding_tiebreak_is_ten_points_and_raw_winner_matches_dp():
    seven = sim._point_set_distribution_cached(.8, .7, 7)
    ten = sim._point_set_distribution_cached(.8, .7, 10)
    assert seven != ten
    dp = sim.simulate_match(.8, .7, 5, model_version=sim.POINT_MODEL_VERSION)
    assert dp.p_a_win == pytest.approx(sim.point_match_win_probability(.8, .7, 5), abs=1e-12)


@pytest.mark.parametrize('value', [True, 0, 1, float('nan'), float('inf')])
def test_new_point_model_never_clamps_invalid_inputs(value):
    with pytest.raises(ValueError):
        sim.simulate_match(value, .7, model_version=sim.POINT_MODEL_VERSION)


@pytest.mark.parametrize('bo', [3, 5])
@pytest.mark.parametrize('target', [.03, .2, .5, .82, .97])
def test_all_market_marginals_share_calibrated_winner(bo, target):
    market = sim.simulate_match(.8, .7, bo, model_version=sim.POINT_MODEL_VERSION, winner_probability=target)
    assert market.p_a_win == pytest.approx(target, abs=1e-12)
    assert sum(p for (a, b), p in market.correct_scores.items() if a > b) == pytest.approx(target, abs=1e-12)
    for values in (market.correct_scores, market.sets_played, market.games_total, market.games_diff):
        assert sum(values.values()) == pytest.approx(1, abs=1e-12)
    mirror = sim.simulate_match(.7, .8, bo, model_version=sim.POINT_MODEL_VERSION, winner_probability=1-target)
    assert market.expected_total_games == pytest.approx(mirror.expected_total_games, abs=1e-10)
    assert market.p_tiebreak_in_match == pytest.approx(mirror.p_tiebreak_in_match, abs=1e-10)
    assert market.handicap_a(-.5) == pytest.approx(1-mirror.handicap_a(.5), abs=1e-10)


def test_new_state_version_is_bound_and_legacy_codec_bytes_unchanged():
    legacy = replace(_synthetic_state(), tour_scope='ATP')
    old = encode_state(legacy, tour='ATP')
    assert old['schema'] == 1 and 'market_model_version' not in old
    assert encode_state(decode_state(old), tour='ATP') == old
    updated = replace(legacy, market_model_version=sim.POINT_MODEL_VERSION)
    new = encode_state(updated, tour='ATP')
    assert new['schema'] == 2 and new['market_model_version'] == sim.POINT_MODEL_VERSION
    assert decode_state(new).market_model_version == sim.POINT_MODEL_VERSION
    bad = {**new, 'market_model_version': 'made-up'}
    with pytest.raises(ValueError):
        decode_state(bad)


def test_regular_required_version_rebuilds_fresh_legacy_without_overwriting_artifacts(tmp_path):
    from test_tennis_tour_state import state, NOW
    from tennis.tour_state import refresh_tours, load_tour_state
    path = tmp_path/'models.db'
    clock = lambda: NOW
    first = refresh_tours(path=path, as_of=NOW,
        builder=lambda tour: state(tour, through='2027-01-01'), publication_clock=clock)
    calls = []
    def current(tour):
        calls.append(tour)
        return replace(state(tour, through='2027-01-01'), market_model_version=sim.POINT_MODEL_VERSION)
    second = refresh_tours(path=path, as_of=NOW, builder=current, publication_clock=clock,
        if_stale_days=7, required_market_version=sim.POINT_MODEL_VERSION)
    assert calls == ['ATP', 'WTA'] and second['status'] == 'complete'
    for tour in calls:
        assert first['tours'][tour]['artifact_hash'] != second['tours'][tour]['artifact_hash']
        assert load_tour_state(tour, path=path).market_model_version == sim.POINT_MODEL_VERSION


def test_new_predictor_publishes_coherent_winner_and_joint_markets():
    state = replace(_synthetic_state(), market_model_version=sim.POINT_MODEL_VERSION)
    prediction = predict_match(state, 'Hero H.', 'Grinder G.', 'Hard')
    assert prediction.markets.p_a_win == pytest.approx(prediction.p_a_cal, abs=1e-12)
    assert sum(p for (a, b), p in prediction.markets.correct_scores.items() if a > b) == pytest.approx(prediction.p_a_cal, abs=1e-12)
    assert prediction.context_evidence['model_inputs']['market_model_version'] == sim.POINT_MODEL_VERSION
