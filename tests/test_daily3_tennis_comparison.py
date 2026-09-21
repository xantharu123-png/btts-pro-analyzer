"""Synthetic calculation/transport proofs, not empirical tennis qualification."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from context_models.contracts import canonical_timestamp, digest
from context_models.tennis_live import CODE_PATHS, ORIGIN_KIND
from daily3_tennis_comparison import build_tennis_comparison, tennis_surface_comparison
from daily3_selection import daily3_choices
from test_daily3_selection import NOW, tennis
from tennis.elo import SurfaceElo
from tennis.model_state import ModelState
from tennis.predict import GateResult, predict_match
from tennis.serve_model import ServeReturnModel


def source():
    elo = SurfaceElo()
    elo.overall._table.update({'spieler a': [1690., 60], 'spieler b': [1500., 60]})
    elo.by_surface['Hard']._table.update({'spieler a': [1900., 30], 'spieler b': [1500., 30]})
    state = ModelState(elo, ServeReturnModel(), 1., 0., 800,
        (NOW-timedelta(hours=1)).timestamp(), NOW.date().isoformat(), 0., tour_scope='ATP',
        stats_through_kind='result_date', artifact_hash='a'*64,
        training_cutoff=(NOW-timedelta(hours=2)).isoformat())
    captured = []
    prediction = predict_match(state, 'Spieler A', 'Spieler B', 'Hard', as_of=NOW,
        original_capture=captured.append)
    # Synthetic gate verdict; tests do not establish real qualification.
    prediction.gates = [GateResult(name, True, 'synthetic') for name in
        ('Belag', 'Erfahrung', 'Aufschlag-Daten', 'Spieler-Zuordnung')]
    event = dict(event_key='espn:tennis:ATP:match:123', sport='tennis',
        competition='espn:ATP:tournament:189-2026', format='singles', status='scheduled',
        home_id='espn:tennis:ATP:player:1', away_id='espn:tennis:ATP:player:2',
        tour='ATP', surface=None, indoor=None, scheduled_start=canonical_timestamp(NOW+timedelta(hours=2)))
    event['schedule_revision'] = digest({'event_key': event['event_key'], 'scheduled_start': event['scheduled_start']})
    origin = dict(schema=1, kind=ORIGIN_KIND, event=event, cutoff=canonical_timestamp(NOW),
        state_hash=state.artifact_hash, native_receipt='b'*64,
        native_observed_at=canonical_timestamp(NOW-timedelta(seconds=1)), competition_revision='c'*64,
        native_state_identity='unresolved', code_hashes={name: 'd'*64 for name in CODE_PATHS}, **captured[0])
    return state, origin, prediction


def signal():
    state, origin, prediction = source()
    context = deepcopy(prediction.context_evidence)
    context['daily3_comparison'] = build_tennis_comparison(state, origin, prediction)
    from context_models.tennis_live import SIDECAR_KIND, MARKETS
    context['context_model'] = {'schema':1, 'kind':SIDECAR_KIND, 'event': origin['event'], 'cutoff': origin['cutoff'],
        'markets':MARKETS, 'original_artifact_hash':'e'*64,
        'reference':{'schema':1, 'kind':'context-consumer-reference-v1', 'key':'f'*64, 'payload_digest':'1'*64}}
    return replace(tennis(), probability=origin['values']['p_a_cal'], fixture_source='ESPN',
        provider_event_id='123', competitor_a_id='1', competitor_b_id='2', context_evidence=context)


def test_real_surface_ablation_and_shortlisting_leave_original_state_and_forecast_unchanged():
    state, origin, prediction = source()
    before = deepcopy((state.elo.to_payload(), origin, vars(prediction)))
    comparison = build_tennis_comparison(state, origin, prediction)
    assert comparison['probabilities_a'][0] == origin['values']['p_a_cal']
    assert comparison['probabilities_a'][2] > comparison['probabilities_a'][1]+.02
    assert before == (state.elo.to_payload(), origin, vars(prediction))
    s = signal()
    choices = daily3_choices([s], now=NOW)
    assert len(choices) == 1 and choices[0].signal is s
    assert choices[0].comparison.summary.startswith('Belagsignal:')


@pytest.mark.parametrize('field,value', [
    ('event_key', 'espn:tennis:ATP:match:124'), ('player_a', 'Fremder Spieler'),
    ('tour', 'WTA'), ('market_key', 'over_2_5_sets'), ('model_hash', 'b'*64),
    ('model_gates_passed', False), ('surface', 'Clay'), ('overall_matches', [True, 60]),
    ('surface_matches', [7, 60]), ('probabilities_a', [.9, .75, float('nan')]),
    ('probabilities_a', [.9, .75, True]), ('scheduled_start', 'bad'),
    ('modeled_at', (NOW+timedelta(seconds=1)).isoformat()),
])
def test_wrong_or_insufficient_comparisons_are_not_admitted(field, value):
    s = signal()
    s.context_evidence['daily3_comparison'][field] = value
    assert daily3_choices([s], now=NOW) == ()


def test_context_adjustment_or_stale_revision_cannot_borrow_original_ablation():
    s = signal()
    assert daily3_choices([replace(s, probability=s.probability+.001)], now=NOW) == ()
    assert daily3_choices([replace(s, modeled_at=(NOW-timedelta(hours=4)).isoformat())], now=NOW) == ()
    assert daily3_choices([replace(s, market_key='over_2_5_sets')], now=NOW) == ()


def test_only_selected_side_can_get_positive_surface_change():
    s = signal()
    reverse = replace(s, selected_competitor=s.competitor_b, probability=1-s.probability)
    assert tennis_surface_comparison(reverse, now=NOW, minimum_probability=0) is None
    raw = s.context_evidence['daily3_comparison']
    raw['probabilities_a'] = [1-p for p in raw['probabilities_a']]
    reverse = replace(s, selected_competitor=s.competitor_b, probability=s.probability)
    assert tennis_surface_comparison(reverse, now=NOW, minimum_probability=.70) is not None


def test_price_does_not_supply_model_evidence_or_change_its_order():
    s = signal()
    changed = replace(s, minimum_odds=999, evidence_stage='RELEASED')
    assert daily3_choices([s], now=NOW)[0].comparison == daily3_choices([changed], now=NOW)[0].comparison
    del s.context_evidence['daily3_comparison']
    assert daily3_choices([s], now=NOW) == ()


@pytest.mark.parametrize('change', ['gate', 'wta', 'legacy', 'few_surface', 'few_overall', 'few_calibration'])
def test_producer_does_not_grant_missing_qualification(change):
    state, origin, prediction = source()
    if change == 'gate':
        prediction.gates.append(GateResult('Freigabe', False, 'synthetic'))
    elif change == 'wta':
        state.tour_scope = 'WTA'
    elif change == 'legacy':
        state.tour_scope = 'legacy-combined'
    elif change == 'few_surface':
        state.elo.by_surface['Hard']._table['spieler a'][1] = 7
    elif change == 'few_overall':
        state.elo.overall._table['spieler a'][1] = 1
    else:
        state.cal_samples = 199
    assert build_tennis_comparison(state, origin, prediction) is None


def test_general_comparison_keeps_real_serve_mixture_and_calibration():
    from test_tennis_predict import _synthetic_state
    state, origin, _ = source()
    served = _synthetic_state()
    state.serve = served.serve
    state.elo = served.elo
    state.elo.overall._table['hero h'][0] = 1650.
    state.elo.overall._table['grinder g'][0] = 1500.
    state.serve_weight = .3
    captures = []
    prediction = predict_match(state, 'Hero H.', 'Grinder G.', 'Hard', as_of=NOW, original_capture=captures.append)
    assert all(g.passed for g in prediction.gates)
    origin.update(captures[0])
    comparison = build_tennis_comparison(state, origin, prediction)
    expected = []
    predict_match(state, 'Hero H.', 'Grinder G.', None, as_of=NOW, original_capture=expected.append)
    assert comparison['probabilities_a'][1] == expected[0]['values']['p_a_cal']
    elo_only = state.calibrate_match(state.elo.win_probability('hero h', 'grinder g', None), 'hero h', 'grinder g', tour='ATP')
    assert comparison['probabilities_a'][1] != pytest.approx(elo_only)


def test_incomplete_context_binding_cannot_claim_qualified_surface_comparison():
    s = signal()
    del s.context_evidence['context_model']['reference']
    assert daily3_choices([s], now=NOW) == ()


def test_real_worker_persists_comparison_with_its_actual_native_original(monkeypatch, tmp_path):
    import json
    from test_tennis_live_worker import NOW as clock, configure, competition, run_batch
    from test_tennis_predict import _synthetic_state
    from tennis.state_codec import encode_state
    from model_artifacts import put_artifact, load_manifest, publish_slots
    raw = competition()
    raw['competitors'][0]['athlete']['displayName'] = 'Hero H.'
    raw['competitors'][1]['athlete']['displayName'] = 'Grinder G.'
    db, predictions, _, _ = configure(monkeypatch, tmp_path, comp=raw)
    state = _synthetic_state()
    state.tour_scope, state.cal_samples = 'ATP', 800
    state.built_at = (clock-timedelta(hours=2)).timestamp()
    state.training_cutoff = (clock-timedelta(hours=3)).isoformat()
    state.stats_through = (clock-timedelta(days=1)).date().isoformat()
    state.elo.overall._table['hero h'][0] = 1650.
    state.elo.overall._table['grinder g'][0] = 1500.
    ref = put_artifact(db, kind='tennis-tour-state', payload={'schema':1,
        'training_cutoff':state.training_cutoff, 'state':encode_state(state, tour='ATP')},
        created_at=clock-timedelta(hours=1))
    head, _ = load_manifest(db)
    publish_slots(db, {'tennis:ATP':ref}, expected_manifest=head, published_at=clock-timedelta(minutes=30))
    result, rows = run_batch(db, predictions)
    assert result['stored'] == 1 and not result['errors']
    context = json.loads(rows[0]['context_json'])
    comparison = context['daily3_comparison']
    assert comparison['model_hash'] == ref
    assert comparison['event_key'] == context['context_model']['event']['event_key']
    assert comparison['modeled_at'] == context['context_model']['cutoff']
    assert round(comparison['probabilities_a'][0], 4) == rows[0]['p_cal']
    # Continue through the real immutable-context reader and application signal
    # adapter. The displayed model uses full precision, not rounded p_cal.
    from ev_signal_sources import tennis_model_signals
    signals = tennis_model_signals(predictions, today=clock.date().isoformat(), now=clock)
    assert len(signals) == 1
    assert signals[0].probability == comparison['probabilities_a'][0]
    assert signals[0].context_evidence['daily3_comparison'] == comparison
    selected = tennis_surface_comparison(signals[0], now=clock, minimum_probability=0)
    expected = min(comparison['probabilities_a'][0], comparison['probabilities_a'][2])-comparison['probabilities_a'][1]
    assert (selected is not None) == (expected >= .02)
