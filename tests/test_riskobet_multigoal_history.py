"""Multigoal history is exact, optional display evidence, never a new tip."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json

import pytest

import riskobet_candidates as adapters
import riskobet_ui as ui
from riskobet_domain import FactorEvidence, FactorRole, canonical_input_hash
from riskobet_quality import evidence_order
from riskobet_surface import build_riskobet_card, compose_riskobet_catalog
from tip_display_order import START_TIME
from test_riskobet_candidates import MODELED_AT, KICKOFF, football_pool
from test_riskobet_football_recent_results import recent_results
from test_riskobet_ui import RecordingStreamlit, _checked_price_overlays


SCHEMA = 'football-goal-history-v1'
LABELS = ('1-3', '1-4', '2-3', '2-4', 'W1-3', 'W1-4', 'W2-3', 'W2-4')


def history(*, away_count=10):
    raw = recent_results()
    # Home totals: 3,0,2,4,4, then five wins with three goals.
    for row, scores in zip(raw['home'], ((2, 1), (0, 0), (1, 1), (3, 1), (0, 4))):
        row['scored'], row['conceded'] = scores
    raw['away'] = [dict(row, fixture_id=2000+i, opponent_id=800+i,
        opponent='Away opponent '+str(i), scored=0, conceded=2, venue='away')
        for i, row in enumerate(raw['home'][:away_count])]
    return raw


def adapt(raw=None):
    return adapters.adapt_football_candidates(football_pool(), modeled_at=MODELED_AT,
        input_cutoff_at=MODELED_AT, recent_results_by_fixture={'77': raw} if raw else {})[0]


def goal_factors(snapshot):
    return tuple(f for f in snapshot.factors if f.factor_key.startswith('football_goal_history_'))


def display_bundle(*, ten=True):
    bundle = adapt()
    snapshot = bundle.snapshot
    source = SCHEMA + ':' + canonical_input_hash({
        'event_key': snapshot.event_key, 'starts_at': snapshot.starts_at.isoformat(),
        'modeled_at': snapshot.modeled_at.isoformat(),
        'input_cutoff_at': snapshot.input_cutoff_at.isoformat(),
        'input_hash': snapshot.input_hash,
    })
    factors = []
    for window in ((5, 10) if ten else (5,)):
        payload = {'schema': SCHEMA, 'window': window,
            'teams': ['Home Underdog', 'Away Favourite'], 'samples': [window, window],
            'rows': [[label, 2 if not label.startswith('W') else 1, 0] for label in LABELS]}
        factors.append(FactorEvidence(factor_key='football_goal_history_'+str(window),
            summary=json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
            source=source, observed_at=MODELED_AT, imported_at=MODELED_AT,
            fresh_until=KICKOFF, sample_size=0, role=FactorRole.DISPLAY_ONLY))
    snapshot = replace(snapshot, factors=(*snapshot.factors, *factors))
    return snapshot, bundle.candidates


def rendered(monkeypatch, snapshot, candidate):
    recorder = RecordingStreamlit()
    monkeypatch.setattr(ui, 'st', recorder)
    ui._render_detail(candidate, snapshot)
    return recorder, ''.join(value for value, _kwargs, _context in recorder.markdown_calls)


def test_exact_joint_history_is_display_only_and_cannot_change_selection_or_rank():
    baseline, updated = adapt(), adapt(history())
    factors = goal_factors(updated.snapshot)
    assert len(factors) == 2
    five, ten = [json.loads(f.summary) for f in factors]
    assert five == {'schema': SCHEMA, 'window': 5,
        'teams': ['Home Underdog', 'Away Favourite'], 'samples': [5, 5],
        'rows': [['1-3', 2, 5], ['1-4', 4, 5], ['2-3', 2, 5], ['2-4', 4, 5],
                 ['W1-3', 1, 0], ['W1-4', 2, 0], ['W2-3', 1, 0], ['W2-4', 2, 0]]}
    assert ten['samples'] == [10, 10]
    assert ten['rows'][0] == ['1-3', 7, 10]
    assert ten['rows'][4] == ['W1-3', 6, 0]
    assert all(f.role is FactorRole.DISPLAY_ONLY and f.sample_size == 0
               and f.source.startswith(SCHEMA+':') and len(f.summary) <= 600 for f in factors)
    for old, new in zip(baseline.candidates, updated.candidates):
        assert (old.market_key, old.selection_key, old.model_probability,
                old.cautious_probability, old.stage, old.context_state, old.pros, old.cons) == (
                new.market_key, new.selection_key, new.model_probability,
                new.cautious_probability, new.stage, new.context_state, new.pros, new.cons)
        assert evidence_order(old, baseline.snapshot)[:-1] == evidence_order(new, updated.snapshot)[:-1]


def test_short_actual_history_keeps_denominator_and_never_invents_ten_games():
    factors = goal_factors(adapt(history(away_count=3)).snapshot)
    assert len(factors) == 1
    five = json.loads(factors[0].summary)
    assert five['samples'] == [5, 3]
    assert five['rows'][0] == ['1-3', 2, 3]


def test_bridge_version_changes_only_revisions_with_structured_history(monkeypatch):
    baseline, enriched = adapt(), adapt(history())
    monkeypatch.setattr(adapters, 'FOOTBALL_GOAL_HISTORY_SCHEMA', 'future-goal-history-v2', raising=False)
    assert adapt().snapshot.input_hash == baseline.snapshot.input_hash
    assert adapt(history()).snapshot.input_hash != enriched.snapshot.input_hash


def test_wrong_identity_or_future_history_cannot_supply_structured_counts():
    for key, value in [('home_id', 999), ('as_of', (MODELED_AT+timedelta(seconds=1)).isoformat())]:
        raw = history()
        raw[key] = value
        updated = adapt(raw)
        assert not goal_factors(updated.snapshot)
        assert updated.snapshot.input_hash == adapt().snapshot.input_hash


def test_saved_counts_render_as_one_compact_escaped_historical_table_with_window_controls(monkeypatch):
    snapshot, candidates = display_bundle()
    recorder, html = rendered(monkeypatch, snapshot, candidates[0])
    assert 'Multigoal &amp; Sieg-Kombis' in html
    assert 'Historische Treffer' in html and 'keine Modellchance' in html
    assert 'Home Underdog' in html and 'Away Favourite' in html
    assert 'Sieg + 1–3' in html and '1–3 Tore' in html
    assert '2/5' in html and '2/10' in html
    assert html.count('value="5"') == 1 and html.count('value="10"') == 1
    assert 'form-window-5' in html and 'form-window-10' in html
    assert not any('"schema"' in str(value) for _kind, value, _context in recorder.messages)
    assert all(ui._customer_factor_detail(factor) == '' for factor in goal_factors(snapshot))
    # Filtering cannot depend on DISPLAY_ONLY alone: malformed model factors also stay private.
    assert ui._customer_factor_detail(replace(goal_factors(snapshot)[0], role=FactorRole.MODEL)) == ''


@pytest.mark.parametrize('change', ['unknown_field', 'schema', 'window', 'label', 'negative',
    'excess_hits', 'boolean', 'missing_row', 'sample', 'team', 'source', 'sample_size',
    'role', 'coverage', 'import_clock', 'fresh_clock', 'owner', 'sport'])
def test_untrusted_or_foreign_counts_are_suppressed_not_guessed(monkeypatch, change):
    snapshot, candidates = display_bundle(ten=False)
    factor = goal_factors(snapshot)[0]
    payload = json.loads(factor.summary)
    if change == 'unknown_field': payload['probability'] = 0.9
    elif change == 'schema': payload['schema'] = 'future-v9'
    elif change == 'window': payload['window'] = 10
    elif change == 'label': payload['rows'][0][0] = 'under_3'
    elif change == 'negative': payload['rows'][0][1] = -1
    elif change == 'excess_hits': payload['rows'][0][1] = 6
    elif change == 'boolean': payload['rows'][0][1] = True
    elif change == 'missing_row': payload['rows'].pop()
    elif change == 'sample': payload['samples'][0] = 0
    elif change == 'team': payload['teams'][0] = 'Foreign Team'
    elif change == 'source': factor = replace(factor, source=SCHEMA+':'+('f'*64))
    elif change == 'sample_size': factor = replace(factor, sample_size=10)
    elif change == 'role': factor = replace(factor, role=FactorRole.MODEL)
    elif change == 'coverage': factor = replace(factor, coverage=1)
    elif change == 'import_clock': factor = replace(factor, observed_at=MODELED_AT-timedelta(minutes=1),
        imported_at=MODELED_AT-timedelta(minutes=1))
    elif change == 'fresh_clock': factor = replace(factor, fresh_until=KICKOFF+timedelta(hours=1))
    factor = replace(factor, summary=json.dumps(payload, separators=(',', ':')))
    snapshot = replace(snapshot, factors=(*[f for f in snapshot.factors if not f.factor_key.startswith('football_goal_history_')], factor))
    if change == 'owner': snapshot = replace(snapshot, event_key='foreign-event')
    if change == 'sport': snapshot = replace(snapshot, sport='basketball')
    recorder, html = rendered(monkeypatch, snapshot, candidates[0])
    assert 'form-goal-markets' not in html
    assert ui._customer_factor_detail(factor) == ''
    assert not any('"schema"' in str(value) for _kind, value, _context in recorder.messages)


def test_old_prose_only_snapshots_stay_immutable_without_invented_counts(monkeypatch):
    snapshot, candidates = display_bundle()
    snapshot = replace(snapshot, factors=tuple(f for f in snapshot.factors
        if not f.factor_key.startswith('football_goal_history_')))
    before = deepcopy(snapshot.to_dict())
    _recorder, html = rendered(monkeypatch, snapshot, candidates[0])
    assert 'form-goal-markets' not in html and snapshot.to_dict() == before


def test_same_event_two_scenarios_show_history_once_per_visible_event(monkeypatch):
    snapshot, candidates = display_bundle()
    assert len(candidates) == 2
    recorder = RecordingStreamlit()
    monkeypatch.setattr(ui, 'st', recorder)
    overlays = _checked_price_overlays(candidates, [snapshot], now=MODELED_AT)
    cards = [build_riskobet_card(c, overlays[c.candidate_id], snapshot=snapshot, now=MODELED_AT)
             for c in candidates]
    catalog = compose_riskobet_catalog(cards)
    ui._render_ordered_scenarios(catalog, {c.candidate_id: c for c in candidates},
        {snapshot.snapshot_id: snapshot}, START_TIME)
    assert sum('class="sports-form"' in html for html, _kwargs, _context in recorder.markdown_calls) == 1


def test_actual_adapter_snapshot_roundtrip_displays_exact_counts_without_mutation(monkeypatch):
    bundle = adapt(history())
    before = deepcopy(bundle.snapshot.to_dict())
    hydrated = ui._snapshot(before)
    _recorder, html = rendered(monkeypatch, hydrated, bundle.candidates[0])
    assert '2/5' in html and '7/10' in html and '6/10' in html
    assert hydrated.to_dict() == before == bundle.snapshot.to_dict()


def test_table_escapes_structured_team_names_and_does_not_parse_prose(monkeypatch):
    snapshot, candidates = display_bundle(ten=False)
    factor = goal_factors(snapshot)[0]
    payload = json.loads(factor.summary)
    payload['teams'][0] = '<b>Home & Town</b>'
    factor = replace(factor, summary=json.dumps(payload, separators=(',', ':')))
    snapshot = replace(snapshot, event_label=payload['teams'][0]+' vs '+payload['teams'][1],
        factors=(factor,))
    candidate = replace(candidates[0], event_label=snapshot.event_label)
    _recorder, html = rendered(monkeypatch, snapshot, candidate)
    assert '&lt;b&gt;Home &amp; Town&lt;/b&gt;' in html and '<b>Home & Town</b>' not in html


@pytest.mark.parametrize('summary', ['{invalid', '[]', 'null',
    '{"schema":"foreign","schema":"football-goal-history-v1","window":5,"teams":["Home Underdog","Away Favourite"],"samples":[5,5],"rows":[["1-3",2,0],["1-4",2,0],["2-3",2,0],["2-4",2,0],["W1-3",1,0],["W1-4",1,0],["W2-3",1,0],["W2-4",1,0]]}'])
def test_invalid_or_ambiguous_json_cannot_render_a_partial_table(monkeypatch, summary):
    snapshot, candidates = display_bundle(ten=False)
    factor = replace(goal_factors(snapshot)[0], summary=summary)
    snapshot = replace(snapshot, factors=(factor,))
    _recorder, html = rendered(monkeypatch, snapshot, candidates[0])
    assert 'form-goal-markets' not in html
