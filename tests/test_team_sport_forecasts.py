from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

import sports_prematch
from riskobet_candidates import adapt_research_matchwinner
from riskobet_automation import snapshot_from_dict
from test_sports_prematch import NOW, event, history


@pytest.mark.parametrize('sport', ['basketball', 'ice_hockey'])
@pytest.mark.parametrize('probability', [0.5, 0.07, 0.93, 0.43, 0.61])
def test_full_prediction_survives_risk_selection_once(monkeypatch, sport, probability):
    target = event(sport, source_observed_at=NOW.isoformat())
    rows = history(sport)
    original = sports_prematch.predict_prematch(sport, target, rows, NOW)
    prediction = replace(original, p_home=probability, p_away=1-probability)
    calls = []
    def predict(*args, **kwargs):
        calls.append((args, kwargs))
        return prediction
    monkeypatch.setattr(sports_prematch, 'predict_prematch', predict)
    result = adapt_research_matchwinner(sport, target, rows, modeled_at=NOW)
    assert len(calls) == 1
    payload = getattr(result.snapshot, 'team_sport_forecast', None)
    assert payload is not None
    assert getattr(payload, 'kind', None) == 'full_match_winner'
    assert payload.p_home == probability
    assert payload.p_away == 1-probability
    assert payload.missing == prediction.missing
    if probability in (.07, .93):
        assert result.candidates == ()
    assert snapshot_from_dict(result.snapshot.to_dict()) == result.snapshot
    from team_sport_forecasts import team_sport_forecast_rows
    projected = team_sport_forecast_rows(SimpleNamespace(snapshots=(result.snapshot,)), now=NOW, target_date=NOW.date())
    assert [row['probability'] for row in projected] == [probability, 1-probability]
    assert all(row['probability_haircut'] is None and row['minimum_odds'] is None for row in projected)
    assert all(row['evidence_stage'] == 'RESEARCH' and row['statistical_release_passed'] is False for row in projected)
    assert len(calls) == 1


def _snapshot(sport='basketball'):
    return adapt_research_matchwinner(sport, event(sport, source_observed_at=NOW.isoformat()), history(sport), modeled_at=NOW).snapshot


def test_actual_store_roundtrip_and_content_collision(tmp_path):
    from riskobet_domain import RiskRunSnapshot, RunStatus
    from riskobet_store import RiskBetStore, FrozenRevisionError
    snapshot = _snapshot()
    run = RiskRunSnapshot(started_at=NOW, completed_at=NOW, status=RunStatus.COMPLETE, snapshots=(snapshot,))
    store = RiskBetStore(tmp_path/'risk.db')
    store.append_run(run)
    loaded = store.load_run(run.run_id)
    assert snapshot_from_dict(loaded['snapshots'][0]) == snapshot
    changed = replace(snapshot, team_sport_forecast=replace(snapshot.team_sport_forecast, limitations=('Changed limitation',)))
    assert changed.snapshot_id != snapshot.snapshot_id
    collision = replace(snapshot, competition='Another competition')
    with pytest.raises(FrozenRevisionError):
        store.append_snapshot(collision, run.run_id)


def test_normal_artifact_reader_card_and_strict_isolation(tmp_path):
    from config_loader import AppConfig
    from riskobet_domain import RiskRunSnapshot, RunStatus
    from wettfinder_automation import run_wettfinder
    from ev_signal_sources import automated_wettfinder_forecasts, automated_wettfinder_signals
    from wettfinder_surface import build_wettfinder_card, wettfinder_recommendation_candidate
    snapshot = _snapshot()
    run = RiskRunSnapshot(started_at=NOW, completed_at=NOW, status=RunStatus.COMPLETE, snapshots=(snapshot,))
    path = tmp_path/'normal.json'
    document = run_wettfinder(now=NOW, state_path=path, config=AppConfig(),
        tennis_loader=lambda **kw: [], esports_loader=lambda **kw: [],
        riskobet_runner=lambda **kw: run)
    assert len(document['model_candidates']) == 2
    signals = automated_wettfinder_forecasts(path, now=NOW)
    assert len(signals) == 2
    assert document['candidates'] == document['challenge_release_candidates'] == []
    assert automated_wettfinder_signals(path, now=NOW) == []
    card = build_wettfinder_card(signals[0], now=NOW)
    assert card.cautious_probability is None
    assert card.value_threshold is None and not card.confirmed_tip and not card.highlight_eligible
    assert '84' in card.analysis_samples
    assert 'Verletzungen' in card.analysis_caution and 'Müdigkeit' in card.analysis_caution
    candidate = wettfinder_recommendation_candidate(signals[0])
    assert candidate.risk_adjusted_probability is None
    from bet_finder_ui import evaluate_reference_price
    from wettfinder_surface import wettfinder_quote_binding_candidate
    evaluation = evaluate_reference_price(candidate, None, bankroll=100,
        reference_binding_candidate=wettfinder_quote_binding_candidate(signals[0]), now=NOW)
    assert build_wettfinder_card(signals[0], now=NOW, price_evaluation=evaluation).cautious_probability is None
    with pytest.raises(ValueError):
        build_wettfinder_card(signals[0], now=NOW, release_overlay=object())
    for change in ({'source': 'persisted_model'}, {'evidence_stage': 'RELEASED'}, {'statistical_release_passed': True}, {'minimum_odds': 2.0}):
        with pytest.raises(ValueError):
            replace(signals[0], **change)
    with pytest.raises(ValueError):
        replace(signals[0], team_sport_snapshot=['bad'])


@pytest.mark.parametrize('change', [
    {'schema': 'future-v2'}, {'p_home': True}, {'p_away': None}, {'p_away': .2},
    {'p_home': float('nan')}, {'training_games': True}, {'home_games': 1000},
    {'market_contract': 'regulation_only'}, {'home': 'Team 8'},
    {'modeled_at': (NOW+timedelta(days=1)).isoformat()},
    {'latest_result_observed_at': (NOW+timedelta(minutes=1)).isoformat()},
])
def test_malformed_or_future_payload_fails_closed(change):
    snapshot = _snapshot()
    payload = snapshot.to_dict()
    payload['team_sport_forecast'].update(change)
    with pytest.raises(ValueError):
        snapshot_from_dict(payload)


def test_payload_immutability_legacy_and_misbinding():
    from team_sport_forecasts import TeamSportForecast
    snapshot = _snapshot()
    raw = snapshot.team_sport_forecast.to_dict()
    parsed = TeamSportForecast.from_dict(raw)
    raw['evaluation']['count'] = 0
    raw['factors'].clear()
    assert parsed.evaluation['count'] > 0 and parsed.factors
    with pytest.raises(TypeError):
        parsed.evaluation['count'] = 0
    for change in ({'event_key': 'wrong'}, {'modeled_at': NOW+timedelta(minutes=1)}, {'event_label': 'Wrong match'}):
        with pytest.raises(ValueError):
            replace(snapshot, **change)
    legacy = replace(snapshot, team_sport_forecast=None)
    assert 'team_sport_forecast' not in legacy.to_dict()
    assert snapshot_from_dict(legacy.to_dict()) == legacy
    cricket = adapt_research_matchwinner('cricket', event('cricket', source_observed_at=NOW.isoformat()), history('cricket'), modeled_at=NOW)
    assert 'team_sport_forecast' not in cricket.snapshot.to_dict()
    import hashlib
    from riskobet_domain import canonical_json
    # Baseline measured against the pre-bridge 534d27d adapter, not derived
    # from the code under test. Legacy payload bytes must not be enriched.
    assert hashlib.sha256(canonical_json(cricket.snapshot.to_dict()).encode()).hexdigest() == '203a82a16ad2ad705402da439f249f8d805c03b5d0e7ecfc901e20af94f0c2ab'


def test_same_day_older_model_stays_descriptive_and_expired_source_does_not(monkeypatch):
    from team_sport_forecasts import team_sport_forecast_rows, team_sport_source_coverage
    snapshot = _snapshot()
    monkeypatch.setattr(sports_prematch, 'predict_prematch', lambda *a, **kw: pytest.fail('second calculation'))
    run = SimpleNamespace(snapshots=(snapshot,))
    later = NOW+timedelta(hours=3)
    rows = team_sport_forecast_rows(run, now=later, target_date=NOW.date())
    assert len(rows) == 2
    assert all(row['modeled_at'] == NOW.isoformat() for row in rows)
    expired = replace(snapshot, factors=tuple(replace(f, fresh_until=NOW) for f in snapshot.factors))
    run = SimpleNamespace(snapshots=(expired,))
    assert team_sport_forecast_rows(run, now=later, target_date=NOW.date()) == []
    assert team_sport_source_coverage(run, [], now=later, target_date=NOW.date())['basketball']['coverage_reasons'] == ['source_evidence_expired']


def test_hockey_missing_ot_support_never_publishes_a_full_winner():
    from team_sport_forecasts import team_sport_forecast_rows
    sport = 'ice_hockey'
    rows = [r for r in history(sport) if r['last_period_type'] == 'REG']
    snapshot = adapt_research_matchwinner(sport, event(sport, source_observed_at=NOW.isoformat()), rows, modeled_at=NOW).snapshot
    assert snapshot.team_sport_forecast.p_home is None
    assert team_sport_forecast_rows(SimpleNamespace(snapshots=(snapshot,)), now=NOW, target_date=NOW.date()) == []


def test_actual_runner_reuses_original_snapshot_without_calls_and_survives_source_failure(tmp_path):
    from riskobet_automation import run_riskobet
    from team_sport_forecasts import team_sport_forecast_rows
    calls = []
    def source():
        calls.append('fetch_and_predict')
        return adapt_research_matchwinner('basketball', event(source_observed_at=NOW.isoformat()), history(), modeled_at=NOW)
    kwargs = dict(db_path=tmp_path/'risk.db', latest_path=tmp_path/'risk.json', basketball_source=source)
    first = run_riskobet(now=NOW, **kwargs)
    later = NOW+timedelta(hours=3)
    reused = run_riskobet(now=later, source_due={'basketball': False}, **kwargs)
    assert calls == ['fetch_and_predict']
    assert reused.snapshots == first.snapshots
    original = team_sport_forecast_rows(first, now=NOW, target_date=NOW.date())
    assert team_sport_forecast_rows(reused, now=later, target_date=NOW.date()) == original
    def failed():
        raise RuntimeError('offline fixture')
    kwargs['basketball_source'] = failed
    failed_run = run_riskobet(now=later, **kwargs)
    assert team_sport_forecast_rows(failed_run, now=later, target_date=NOW.date()) == original


@pytest.mark.parametrize('odds', [None, 1.01, 99.0, 'malformed'])
def test_optional_price_cannot_hide_research_or_make_it_released(tmp_path, monkeypatch, odds):
    import json
    from config_loader import AppConfig
    from riskobet_domain import RiskRunSnapshot, RunStatus
    from wettfinder_automation import run_wettfinder
    from ev_signal_sources import automated_wettfinder_snapshot
    from wettfinder_surface import build_wettfinder_card, wettfinder_recommendation_candidate, wettfinder_quote_binding_candidate
    from forecast_selection import select_consumer_forecasts
    from market_consensus import MarketConsensus, QuotePoint, ODDS_API_REFERENCE_SOURCE
    import forecast_evidence
    monkeypatch.setattr(forecast_evidence, '_now', lambda: NOW)
    snapshot = _snapshot()
    run = RiskRunSnapshot(started_at=NOW, completed_at=NOW, status=RunStatus.COMPLETE, snapshots=(snapshot,))
    path = tmp_path/'normal.json'
    document = run_wettfinder(now=NOW, state_path=path, config=AppConfig(),
        tennis_loader=lambda **kw: [], esports_loader=lambda **kw: [], riskobet_runner=lambda **kw: run,
        evidence_db_path=tmp_path/'evidence.db')
    before = automated_wettfinder_snapshot(path, now=NOW)
    assert document['forecast_evidence']['recorded'] == 2
    for row in document['model_candidates']:
        if odds == 'malformed':
            row['reference_quote'] = {'bad': 'payload'}
        elif odds is not None:
            points = tuple(QuotePoint(bookmaker=f'Book {i}', bookmaker_id=f'odds-api:{i}', odds=odds, observed_at=NOW.isoformat()) for i in range(3))
            quote = MarketConsensus(fixture_id=None, candidate_id=row['candidate_id'], market_key='H2H', bet_name='h2h',
                value_name=row['selection'], consensus_odds=odds, conservative_odds=odds, lowest_odds=odds, best_odds=odds,
                bookmaker_count=3, quoted_at=NOW.isoformat(), fetched_at=NOW.isoformat(), source=ODDS_API_REFERENCE_SOURCE,
                points=points, provider_event_id='price-provider-event', scheduled_start=row['scheduled_start'],
                event_home=row['competitor_a'], event_away=row['competitor_b'])
            assert MarketConsensus.from_dict(quote.to_dict()) is not None
            row['reference_quote'] = quote.to_dict()
    path.write_text(json.dumps(document), encoding='utf-8')
    after = automated_wettfinder_snapshot(path, now=NOW)
    assert len(after.forecasts) == 2 and after.signals == ()
    assert [s.key for s in select_consumer_forecasts(before.forecasts, now=NOW)] == [s.key for s in select_consumer_forecasts(after.forecasts, now=NOW)]
    assert len(select_consumer_forecasts(after.forecasts, now=NOW)) == 1
    for signal in after.forecasts:
        assert signal.reference_quote is None
        card = build_wettfinder_card(signal, now=NOW)
        assert not card.confirmed_tip and card.value_threshold is None
        assert card.model_probability == next(s.probability for s in before.forecasts if s.key == signal.key)
        assert wettfinder_recommendation_candidate(signal).risk_adjusted_probability is None


def test_normal_reader_rejects_wrong_day_and_missing_required_nullable_field(tmp_path):
    import json
    from config_loader import AppConfig
    from riskobet_domain import RiskRunSnapshot, RunStatus
    from wettfinder_automation import run_wettfinder
    from ev_signal_sources import automated_wettfinder_snapshot
    from team_sport_forecasts import team_sport_forecast_rows
    snapshot = _snapshot()
    run = RiskRunSnapshot(started_at=NOW, completed_at=NOW, status=RunStatus.COMPLETE, snapshots=(snapshot,))
    path = tmp_path/'normal.json'
    document = run_wettfinder(now=NOW, state_path=path, config=AppConfig(),
        tennis_loader=lambda **kw: [], esports_loader=lambda **kw: [], riskobet_runner=lambda **kw: run)
    assert document['sources']['basketball']['published_model_selection_count'] == 2
    next_start = snapshot.starts_at+timedelta(days=1)
    tomorrow = replace(snapshot, starts_at=next_start, team_sport_forecast=replace(snapshot.team_sport_forecast, starts_at=next_start))
    bad_rows = team_sport_forecast_rows(SimpleNamespace(snapshots=(tomorrow,)), now=NOW, target_date=next_start.date())
    tampered = dict(document, model_candidates=[dict(r, status='MODEL_SELECTION') for r in bad_rows])
    path.write_text(json.dumps(tampered), encoding='utf-8')
    assert automated_wettfinder_snapshot(path, now=NOW).status is None
    document['model_candidates'][0].pop('probability_haircut')
    path.write_text(json.dumps(document), encoding='utf-8')
    assert automated_wettfinder_snapshot(path, now=NOW).status is None
