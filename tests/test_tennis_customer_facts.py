from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from tennis.customer_facts import build_match_statistics, customer_record_facts, format_customer_records
from test_daily3_selection import NOW, tennis


def result(number=1, **changes):
    return dict(settled=1, player_a="Spieler A", player_b="Spieler B", tour="ATP", surface="Clay",
        fixture_source="test", provider_event_id=str(number), termination="normal", best_of=3,
        player_a_sets=2, player_b_sets=0, scheduled_start_utc=(NOW-timedelta(days=number)).isoformat(),
        result_observed_at=(NOW-timedelta(days=number, hours=-2)).isoformat(), **changes)


def context(rows):
    data = deepcopy(tennis().context_evidence)
    data['match_statistics'] = build_match_statistics("Spieler A", "Spieler B", rows,
        surface="Clay", tour="ATP", as_of=NOW)
    return data


def changed_row(**changes):
    return {**result(), **changes}


def test_customer_copy_uses_observed_wins_not_elo_or_unbounded_streaks():
    rows = [result(i) for i in range(1, 11)]
    rows[3]['player_a_sets'], rows[3]['player_b_sets'] = 1, 2
    data = context(rows)
    facts = customer_record_facts(data, "Spieler A", "Spieler B", modeled_at=NOW)
    assert facts[0][:2] == ('Spieler A', '9/10 Siege')
    assert facts[1][:2] == ('Spieler B', '1/10 Siege')
    assert 'Sand · 10 erfasste Spiele · 22.12.2029–31.12.2029' == facts[0][2]
    text = ' '.join(format_customer_records(data, 'Spieler A', 'Spieler B', modeled_at=NOW))
    assert 'ungeschlagen' not in text and 'Elo' not in text


@pytest.mark.parametrize('changes', [
    {'result_observed_at': (NOW+timedelta(seconds=1)).isoformat()},
    {'scheduled_start_utc': (NOW-timedelta(days=91)).isoformat()},
    {'termination': 'retirement'}, {'termination': 'walkover'}, {'settled': 0},
    {'tour': 'WTA'}, {'tour': None}, {'player_a_sets': True}, {'player_a_sets': 1},
    {'player_b_sets': 2}, {'best_of': None}, {'player_a': 'Fremder A', 'player_b': 'Fremder B'},
])
def test_unusable_results_cannot_create_a_record(changes):
    assert not customer_record_facts(context([changed_row(**changes)]),
        'Spieler A', 'Spieler B', modeled_at=NOW)


def test_deduplication_conflicts_and_ten_match_cap():
    original = result()
    assert context([original, deepcopy(original), {**original, 'fixture_source': 'other'}])['match_statistics']['players']['a']['surface']['matches'] == 1
    assert not customer_record_facts(context([original, {**original, 'player_a_sets': 0, 'player_b_sets': 2}]),
        'Spieler A', 'Spieler B', modeled_at=NOW)
    assert context([result(i) for i in range(1, 25)])['match_statistics']['players']['a']['surface']['matches'] == 10


def test_two_sources_disagreeing_on_winner_do_not_produce_a_claim():
    original = result()
    disputed = {**original, 'fixture_source': 'other', 'player_a_sets': 0, 'player_b_sets': 2}
    for rows in ([original, disputed], [disputed, original]):
        assert not customer_record_facts(context(rows), 'Spieler A', 'Spieler B', modeled_at=NOW)


def test_missing_or_other_surface_is_not_a_surface_win():
    for surface in (None, 'Hard'):
        data = context([changed_row(surface=surface)])
        assert 'surface' not in data['match_statistics']['players']['a']
        assert 'Alle Beläge' in customer_record_facts(data, 'Spieler A', 'Spieler B', modeled_at=NOW)[0][2]


def test_snapshot_binding_and_malformed_counts_fail_closed():
    data = context([result()])
    for change in ('clock', 'players', 'surface', 'wins', 'count', 'date'):
        broken = deepcopy(data)
        raw = broken['match_statistics']
        if change == 'clock':
            raw['observed_at'] = (NOW+timedelta(seconds=1)).isoformat()
        elif change == 'players':
            raw['players']['a']['player'] = 'Fremder'
        elif change == 'surface':
            raw['surface'] = 'Hard'
        else:
            for entry in raw['players'].values():
                entry['surface'][{'wins': 'wins', 'count': 'matches', 'date': 'through'}[change]] = {'wins': 2, 'count': True, 'date': '2031-01-01'}[change]
        assert not customer_record_facts(broken, 'Spieler A', 'Spieler B', modeled_at=NOW)


def test_actual_forecast_and_daily3_share_customer_copy_without_changing_selection():
    from forecast_analysis import build_forecast_analysis
    from forecast_compact import build_compact_analysis, render_compact_analysis_html
    from daily3_selection import daily3_choices
    signal = replace(tennis(), context_evidence=context([result(i) for i in range(1, 6)]))
    original = deepcopy(vars(signal))
    before = daily3_choices([signal], now=NOW)
    analysis = build_forecast_analysis(signal, now=NOW)
    markup = render_compact_analysis_html(build_compact_analysis(signal, analysis, now=NOW))
    assert '5/5 Siege' in markup and '0/5 Siege' in markup and 'Sand' in markup
    assert 'Statistik &amp; Details' not in markup
    assert '5 erfasste Spiele' in markup  # Sporting sample scope remains on the form fact.
    for internal in ('Elo', 'Modellaufbau', 'Trainingsstichtag', 'Proxy', 'numerischer Vorteil'):
        assert internal not in markup
    assert vars(signal) == original
    assert daily3_choices([signal], now=NOW) == before


def test_prediction_freezes_statistics_without_changing_any_market():
    from test_tennis_predict import _synthetic_state
    from tennis.predict import predict_match
    state = _synthetic_state()
    row = changed_row(player_a='Hero H.', player_b='Grinder G.', surface='Hard')
    plain = predict_match(state, 'Hero H.', 'Grinder G.', 'Hard', as_of=NOW)
    with_history = predict_match(state, 'Hero H.', 'Grinder G.', 'Hard', as_of=NOW, workload_history=[row])
    from tennis.customer_facts import attach_customer_statistics
    attach_customer_statistics(with_history, [row], tour='ATP')
    assert with_history.market_summary() == plain.market_summary()
    assert with_history.p_a_cal == plain.p_a_cal
    assert customer_record_facts(with_history.context_evidence, 'Hero H.', 'Grinder G.', modeled_at=NOW)[0][1] == '1/1 Siege'


def test_riskobet_and_tennis_tab_use_the_same_frozen_record(tmp_path, monkeypatch):
    import json
    from test_riskobet_candidates import create_tennis_db, insert_tennis, MODELED_AT
    from riskobet_candidates import adapt_tennis_shadow
    from riskobet_domain import FactorRole
    from test_riskobet_ui import RecordingStreamlit
    import tennis_tab

    data = context([result(5)])
    path = tmp_path / 'tennis.db'
    create_tennis_db(path)
    insert_tennis(path, row_id=1, p_a=.35,
        markets='{"over_2_5_sets":0.45,"set_handicap_a_minus_1_5":0.12}', context=json.dumps(data))
    # The adapter fixture names are read from the actual stored row below.
    import sqlite3
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        row = dict(db.execute('SELECT * FROM predictions').fetchone())
        data['observed_at'] = data['match_statistics']['observed_at'] = (MODELED_AT-timedelta(minutes=5)).isoformat()
        for side in ('a', 'b'):
            name = row[f'player_{side}']
            data['players'][side]['player'] = data['match_statistics']['players'][side]['player'] = name
        db.execute('UPDATE predictions SET context_json=?, surface=?', (json.dumps(data), 'Clay'))
        row['context_json'] = json.dumps(data)
        row['surface'] = 'Clay'
    bundle = adapt_tennis_shadow(path, as_of=MODELED_AT)[0]
    factor = next(f for f in bundle.snapshot.factors if f.factor_key == 'tennis_surface_evidence')
    assert factor.role is FactorRole.DISPLAY_ONLY and '1/1 Siege' in factor.summary
    assert 'Elo' not in factor.summary
    fake = RecordingStreamlit()
    monkeypatch.setattr(tennis_tab, 'st', fake)
    # The blocked fixture stops after the customer fact without interactive controls.
    row['gates_json'] = '{}'
    tennis_tab._render_match_card(row)
    assert any('1/1 Siege' in str(item[1]) for item in fake.messages)


def test_regular_scan_persists_statistics_without_a_second_fetch(tmp_path, monkeypatch):
    import json
    from scripts import tennis_daily as daily
    from tennis import shadow
    from test_tennis_tour_readers import NOW as decision, _rated_state, _fixture
    state = _rated_state('ATP', winner='same a', artifact_hash='a'*64, through='2026-09-06')
    monkeypatch.setattr(daily, 'load_tour_state', lambda *_a, **_kw: state)
    monkeypatch.setattr(daily.requests, 'get', lambda *_a, **_kw: pytest.fail('no extra data requests'))
    history = [changed_row(player_a='Same A', player_b='Same B', surface='Hard',
        scheduled_start_utc=(decision-timedelta(days=2)).isoformat(),
        result_observed_at=(decision-timedelta(days=1)).isoformat())]
    db = tmp_path/'scan.db'
    result = daily.scan_fixtures('2026-09-08', [_fixture('ATP', 'atp-1')],
        decision_at=decision, db_path=db, surfaces={}, workload_history=history, append_observed_at=decision)
    assert result['status'] == 'complete' and result['stored'] == 1
    data = json.loads(shadow.latest_predictions(db, as_of=decision)[0]['context_json'])
    assert customer_record_facts(data, 'Same A', 'Same B', modeled_at=decision)[0][1] == '1/1 Siege'
