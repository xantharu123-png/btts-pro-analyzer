"""Presentation regressions using already-validated, explicitly synthetic facts."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import re

import pytest

from forecast_analysis import project_football_analysis
from sports_form import TeamForm, FormResult, render_form_html
from test_daily3_selection import NOW, football, tennis
from wettfinder_surface import build_wettfinder_card, render_editorial_card_html


def editorial_football(*, now=NOW, count=10, fixture=1, key='RESULT_HOME', long=False, start_hours=3):
    from football_customer_facts import build_football_recent_results
    signal = football(fixture, key, now=now, start_hours=start_hours)
    home = 'Nordstadt Fußballverein mit einem außergewöhnlich langen Vereinsnamen' if long else 'FC Nordstadt'
    away = 'Athletik Südpark'
    if fixture != 1:
        home += ' ' + str(fixture)
        away += ' ' + str(fixture)
    row = {**vars(signal), 'home_id': signal.home_team_id, 'away_id': signal.away_team_id,
        'home_team': home, 'away_team': away}
    history = []
    scores = ((2, 1), (1, 1), (0, 1), (3, 0), (2, 2), (1, 0), (0, 2), (2, 0), (1, 2), (3, 1))
    for side, team_id, name in (('home', signal.home_team_id, home), ('away', signal.away_team_id, away)):
        for index, score in enumerate(scores[:count]):
            opponent = {'id': 1000+index, 'name': f'Gegner {index+1}'}
            own = {'id': team_id, 'name': name}
            own_home = index % 2 == 0
            history.append({'fixture': {'id': 10000+fixture*100+(0 if side == 'home' else 30)+index,
                'date': (now-timedelta(days=index*4+2)).isoformat(), 'status': {'short': 'FT'}},
                'teams': {'home': own if own_home else opponent, 'away': opponent if own_home else own},
                'goals': {'home': score[0 if own_home else 1], 'away': score[1 if own_home else 0]},
                'league': {'id': 99, 'name': 'Lokale Testliga'}})
    fixture_data = {'fixture': {'id': fixture, 'date': signal.scheduled_start},
        'teams': {'home': {'id': signal.home_team_id}, 'away': {'id': signal.away_team_id}}}
    recent = build_football_recent_results(fixture_data, history,
        as_of=now-timedelta(minutes=1), model_scope=signal.model_scope)
    basis = {**signal.analysis_evidence['basis'], **row, 'customer_recent_results': recent}
    evidence = project_football_analysis(row, model_basis=basis)
    return replace(signal, home_team=home, away_team=away, event_label=f'{home} vs {away}',
        label=f'{home} vs {away}', analysis_evidence=evidence)


def editorial_tennis(*, now=NOW, count=10):
    signal = tennis(now=now)
    context = deepcopy(signal.context_evidence)
    raw = {'schema': 'tennis-customer-results-v2', 'surface': 'Clay', 'tour': 'ATP',
        'observed_at': now.isoformat(), 'players': {}}
    for side, name in (('a', signal.competitor_a), ('b', signal.competitor_b)):
        results = [{'won': (i+int(side == 'b')) % 3 != 0, 'score': '2:0' if (i+int(side == 'b')) % 3 != 0 else '1:2',
            'date': (now-timedelta(days=i*3+1)).date().isoformat(), 'date_kind': 'result_date',
            'opponent': f'Tennisspieler {i+1}', 'opponent_rank': 20+i*4} for i in range(count)]
        raw['players'][side] = {'player': name, 'surface': {'matches': count,
            'wins': sum(row['won'] for row in results), 'from': results[-1]['date'], 'through': results[0]['date']},
            'surface_results': results}
    context['match_statistics'] = raw
    return replace(signal, context_evidence=context)


def test_editorial_preserves_model_and_original_facts_but_renders_real_tiles():
    signal = editorial_football()
    before = deepcopy(vars(signal))
    card = build_wettfinder_card(signal, now=NOW)
    assert card.model_probability == signal.probability
    assert len(card.compact_analysis.forms) == 2
    assert any(f.label == 'Form FC Nordstadt' for f in card.compact_analysis.facts)
    results = card.compact_analysis.forms[0].results
    assert [r.outcome for r in results[:3]] == ['S', 'U', 'N']
    assert [r.score for r in results[:3]] == ['2:1', '1:1', '0:1']
    assert results[1].venue == 'Auswärts'  # Own-team score orientation.
    html = render_editorial_card_html(card)
    assert 'form-window-5' in html and 'form-window-10' in html
    assert 'Gegner & Ergebnisse' in html and 'Neueste zuerst' in html
    assert 'Letzte Spiele · alle Spielorte' in html
    assert 'form-u' in html and 'Gegner 1' in html
    assert html.count('Modellchance') == 1
    assert vars(signal) == before


def test_reference_layout_keeps_match_and_pick_together_and_opponents_visible():
    card = build_wettfinder_card(editorial_football(), now=NOW)
    html = render_editorial_card_html(card, grouped=True, include_match=True)
    top = html.split('class="se-card-top"', 1)[1].split('aria-label="Kurzcheck"', 1)[0]
    assert 'class="se-match"' in top and 'class="se-pick"' in top
    assert html.count('class="wf-analysis-short"') == 1
    preview = html.split('class="form-opponent-preview"', 1)[1].split('class="form-opponents"', 1)[0]
    assert all(f'Gegner {index}' in preview for index in (1, 2, 3))
    assert 'Gegner 4' not in preview
    assert 'Alle 5 Spiele' in html and 'Alle 10 Spiele' in html


def test_second_market_stays_visible_without_repeating_the_whole_match():
    card = build_wettfinder_card(editorial_football(key='TOTAL_OVER_2_5'), now=NOW)
    html = render_editorial_card_html(card, grouped=True, show_form=False)
    headline, details = html.split('<details class="se-market-details">', 1)
    assert card.selection in headline and 'Modellchance' in headline and 'Quote' in headline
    assert 'class="se-match"' not in html and 'class="sports-form"' not in html
    assert 'class="wf-analysis-short"' in details and 'Gegenrisiko' in details
    assert 'Statistik &amp; Details' not in details


@pytest.mark.parametrize('signal_factory', [editorial_football, editorial_tennis])
@pytest.mark.parametrize('stage', ['RELEASED', 'SHADOW', 'RESEARCH'])
@pytest.mark.parametrize('renderer', ['editorial', 'top', 'compact'])
def test_customer_renderers_keep_sport_facts_and_do_not_export_internal_model_notes(signal_factory, stage, renderer):
    from wettfinder_surface import render_top_card_html, render_compact_row_html
    signal = replace(signal_factory(), evidence_stage=stage)
    before_signal = deepcopy(vars(signal))
    card = build_wettfinder_card(signal, now=NOW)
    before_card = deepcopy(card)
    sentinel = 'Interner Prüfbeleg · Trainingsstichtag · Erfasste Turniere bis 25.09.2026'
    compact = replace(card.compact_analysis, explanation=card.compact_analysis.explanation + (sentinel,))
    card = replace(card, compact_analysis=compact)
    render = {'editorial': render_editorial_card_html,
              'top': render_top_card_html, 'compact': render_compact_row_html}[renderer]
    markup = render(card)
    for text in ('Sicherheitswert', 'heuristisch', 'Mindestchance', 'Evidenzprüfung',
                 'Berechnet:', 'Statistik &amp; Details', sentinel):
        assert text not in markup
    assert card.selection in markup
    assert 'sports-form' in markup and 'Gegner & Ergebnisse' in markup
    assert card.compact_analysis.forms[0].results[0].opponent in markup
    if signal_factory is editorial_football:
        assert 'Gegenargument' in markup
    assert sentinel in card.compact_analysis.explanation
    assert card == replace(before_card, compact_analysis=compact)
    assert vars(signal) == before_signal


def test_legacy_card_without_typed_sport_facts_never_exports_raw_method_notes():
    from wettfinder_surface import render_top_card_html, render_compact_row_html
    card = replace(build_wettfinder_card(editorial_tennis(), now=NOW), compact_analysis=None,
        analysis_basis='Interner Modellaufbau und Trainingsstichtag',
        analysis_caution='Interne Effektprüfung', analysis_data_age='Turnierstart-Proxy',
        analysis_samples='Interne Stichprobe')
    before = deepcopy(card)
    for render in (render_editorial_card_html, render_top_card_html, render_compact_row_html):
        html = render(card)
        assert 'keine weiteren Spielstatistiken' in html
        for value in (card.analysis_basis, card.analysis_caution, card.analysis_data_age, card.analysis_samples):
            assert value not in html
    assert card == before


@pytest.mark.parametrize('status_none', [True, False])
def test_empty_day_keeps_sports_and_both_picture_panels_without_fake_tips(monkeypatch, status_none):
    import app
    from types import SimpleNamespace
    from test_workflow_integrity import _RecordingStreamlit, _automatic_status
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    monkeypatch.setattr(app, 'automated_wettfinder_snapshot', lambda **_: SimpleNamespace(
        status=None if status_none else _automatic_status(NOW), forecasts=()))
    app._render_automated_daily_selection()
    assert 'editorial_auto_layout' in recording.containers
    assert 'wettfinder_v2_sports' in recording.containers
    images = [path for kind, path in recording.event_log if kind == 'image']
    assert len(images) == 2 and images[0].endswith('stadium-cover.png') and images[1].endswith('tennis-cover.png')
    html = '\n'.join(value for value, _kwargs, _context in recording.markdown_calls)
    assert 'se-rail-choice' not in html and 'data-key=' not in html


def test_picture_rail_does_not_reintroduce_a_tennis_quote_below_the_known_floor(monkeypatch):
    import app
    from datetime import datetime
    from types import SimpleNamespace
    from market_consensus import ODDS_API_REFERENCE_SOURCE
    from test_wettfinder_surface import _quote
    from test_workflow_integrity import _RecordingStreamlit, _automatic_status
    recording = _RecordingStreamlit()
    signal = editorial_tennis()
    # Bind the imported quote helper to this test's 07:00 model clock; its
    # default is 12:00 and would correctly be rejected as a future offer.
    quote = _quote(signal, (1.1,) * 3, fetched_at=NOW)
    quote = replace(quote, source=ODDS_API_REFERENCE_SOURCE, provider_event_id='tennis-price-event',
        bet_name='h2h', value_name=signal.selected_competitor,
        event_home=signal.competitor_a, event_away=signal.competitor_b,
        points=tuple(replace(point, bookmaker_id=f'odds-api:{index}') for index, point in enumerate(quote.points)))
    signal = replace(signal, reference_quote=quote.to_dict())
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(app, 'st', recording)
    monkeypatch.setattr(app, 'datetime', Clock)
    monkeypatch.setattr(app, 'automated_wettfinder_snapshot', lambda **_: SimpleNamespace(
        status=_automatic_status(NOW), forecasts=(signal,)))
    app._render_automated_daily_selection()
    html = '\n'.join(value for value, _kwargs, _context in recording.markdown_calls)
    assert signal.event_label not in html


@pytest.mark.parametrize('count', [1, 3, 5, 9])
def test_short_history_never_claims_or_enables_ten_games(count):
    card = build_wettfinder_card(editorial_football(count=count), now=NOW)
    html = render_editorial_card_html(card)
    assert 'value="10"' not in html and 'form-window-10' not in html
    assert f'{min(5,count)} Spiele' in html
    assert len(card.compact_analysis.forms[0].results) == count


def test_misbound_history_cannot_create_form_tiles():
    signal = editorial_football()
    evidence = deepcopy(signal.analysis_evidence)
    evidence['basis']['customer_recent_results']['home_id'] = 998
    card = build_wettfinder_card(replace(signal, analysis_evidence=evidence), now=NOW)
    assert not card.compact_analysis.forms


def test_tennis_tiles_use_sets_surface_and_real_opponents_not_draws():
    card = build_wettfinder_card(editorial_tennis(), now=NOW)
    assert len(card.compact_analysis.forms) == 2
    html = render_editorial_card_html(card)
    assert 'Sand' in html and 'Tennisspieler 1' in html and 'Weltrang 20' in html
    assert 'form-u' not in html and 'value="10"' in html
    assert '1:2' in html and 'Ergebnisdatum' in html


def test_conflicting_tennis_winner_and_sets_do_not_become_a_result_tile():
    signal = editorial_tennis()
    data = deepcopy(signal.context_evidence)
    data['match_statistics']['players']['a']['surface_results'][0]['score'] = '2:0'
    card = build_wettfinder_card(replace(signal, context_evidence=data), now=NOW)
    assert [form.team for form in card.compact_analysis.forms] == [signal.competitor_b]


def test_markup_escapes_names_and_controls_have_separate_card_ids():
    form = TeamForm('<script>bad()</script>', 'Hartplatz', tuple(
        FormResult('S', '2:0', 'A < B', '2026-09-01', 'Test') for _ in range(10)))
    one = render_form_html((form,), instance_key='first')
    two = render_form_html((form,), instance_key='second')
    assert '<script>' not in one and '&lt;script&gt;' in one and 'A &lt; B' in one
    assert re.search(r'name="([^"]+)"', one)[1] != re.search(r'name="([^"]+)"', two)[1]
    assert '<summary aria-label="Sieg 2:0 gegen A &lt; B">' in one
    assert 'onclick' not in one
    # React Markdown must not turn the native radio into a locked controlled
    # input. Five games are the stylesheet's initial view.
    assert ' checked' not in one and '5 Spiele (Standardansicht)' in one


def test_shared_area_destinations_and_callback_are_synchronized(monkeypatch):
    import app
    from test_workflow_integrity import _RecordingStreamlit
    recording = _RecordingStreamlit(session_state={'workspace': 'RisikoBet'})
    callbacks = []
    def selectbox(label, options, **kw):
        callbacks.append((label, options, kw))
        return recording.session_state[kw['key']]
    recording.selectbox = selectbox
    monkeypatch.setattr(app, 'st', recording)
    app._render_editorial_header('RisikoBet')
    label, options, kwargs = callbacks[0]
    assert len(callbacks) == 1
    assert tuple(options) == app.AREA_OPTIONS and label == 'Bereich'
    recording.session_state[kwargs['key']] = '15K'
    kwargs['on_change']()
    assert recording.session_state['workspace'] == '15K'
    assert recording.session_state['settings_open'] is False


def test_identical_game_form_is_shown_once_without_dropping_any_market(monkeypatch):
    import app
    from test_workflow_integrity import _RecordingStreamlit
    from wettfinder_surface import group_wettfinder_games, WettfinderCatalog
    signals = [editorial_football(), editorial_football(key='TOTAL_OVER_2_5')]
    cards = tuple(build_wettfinder_card(signal, now=NOW) for signal in signals)
    group = group_wettfinder_games(WettfinderCatalog(cards, (), ()))[0]
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_game(group, {c.key: (s, c) for s,c in zip(signals,cards)}, {c.key for c in cards})
    html = '\n'.join(call[0] for call in recording.markdown_calls)
    assert html.count('class="sports-form"') == 1
    assert html.count('class="wf-row se-card"') == 2
    assert all(f'data-key="{c.key}"' in html for c in cards)


def test_theme_embeds_font_locally_and_retains_accessible_controls():
    from editorial_theme import editorial_css
    css = editorial_css()
    assert 'data:font/ttf;base64,' in css
    assert 'url(https:' not in css
    assert ':focus-visible' in css and 'env(safe-area-inset-bottom' in css
    assert '.form-toggle label' in css and '44px' in css
    assert '.st-key-riskobet_summary p {color:var(--bb-ink) !important;}' in css
    assert '[data-testid="stElementContainer"]:has(iframe[height="0"])' in css
    assert ':has(>iframe[height="0"])' not in css


def test_new_daily3_rail_respects_existing_plan_entitlements(monkeypatch):
    import app, customer_access
    from test_workflow_integrity import _RecordingStreamlit
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    monkeypatch.setattr(customer_access, 'enabled', lambda: True)
    assert not app._daily3_rail_allowed()
    recording.session_state[customer_access.ACCESS_KEY] = {'features': ['wettfinder']}
    assert not app._daily3_rail_allowed()
    recording.session_state[customer_access.ACCESS_KEY]['features'].append('daily3')
    assert app._daily3_rail_allowed()


def test_shared_navigation_is_reachable_when_plan_guard_stops_page(monkeypatch):
    import app
    from test_workflow_integrity import _RecordingStreamlit
    recording = _RecordingStreamlit(session_state={'workspace': 'RisikoBet'})
    recording.set_page_config = lambda **_kw: None
    monkeypatch.setattr(app, 'st', recording)
    monkeypatch.setattr(app, '_apply_app_styles', lambda: None)
    monkeypatch.setattr(app, 'bind_customer', lambda _st: True)
    monkeypatch.setattr(app, '_session_scope_id', lambda: 'test-scope')
    monkeypatch.setattr(app, 'get_analyzer', lambda *_args: None)
    monkeypatch.setattr(app, '_render_sidebar', lambda _analyzer: 'RisikoBet')
    def higher_plan_required(_st, _feature):
        raise RuntimeError('page stopped by plan guard')
    monkeypatch.setattr(app, 'require_feature', higher_plan_required)
    with pytest.raises(RuntimeError, match='page stopped by plan guard'):
        app.main()
    assert recording.selectboxes == [('Bereich', app.AREA_OPTIONS, 0, 'bb_area_navigation')]
    assert recording.segmented_controls == []


def test_navigation_callback_syncs_flat_area_and_route_before_next_render(monkeypatch):
    import app
    from test_workflow_integrity import _RecordingStreamlit
    recording = _RecordingStreamlit(session_state={'workspace': 'RisikoBet'})
    callbacks = {}
    def selectbox(_label, _options, **kwargs):
        callbacks[kwargs['key']] = kwargs['on_change']
    recording.selectbox = selectbox
    monkeypatch.setattr(app, 'st', recording)
    app._render_editorial_header('RisikoBet')
    assert list(callbacks) == ['bb_area_navigation']
    for area, workspace in (('3 a day', 'Wettfinder'), ('15K', '15K')):
        recording.session_state['bb_area_navigation'] = area
        callbacks['bb_area_navigation']()
        assert recording.session_state['workspace'] == workspace
        assert recording.session_state['bb_area_navigation'] == area
        assert recording.session_state['wettfinder_mode_v2'] == '3 a day'


@pytest.mark.parametrize('sport', ['Basketball', 'Eishockey'])
def test_team_sport_tiles_keep_final_score_scope_and_source_binding(sport):
    from types import SimpleNamespace
    from sports_form import team_forms
    from team_customer_facts import team_customer_explanation
    token = 'basketball' if sport == 'Basketball' else 'ice_hockey'
    forecast = {'sport': token, 'model_version': 'sports-prematch-research-v1',
        'provider_event_id': '1', 'modeled_at': NOW.isoformat(), 'home': 'Alpha', 'away': 'Beta',
        'p_home': .7, 'p_away': .3, 'model_input_hash': 'a'*64, 'missing': [], 'factors': []}
    facts = {'schema': 'team-recent-results-v1', 'sport': token, 'provider_event_id': '1',
        'modeled_at': NOW.isoformat(), 'source_input_hash': 'a'*64, 'competitor_a': 'Alpha', 'competitor_b': 'Beta',
        'a_results': [{'won': True, 'score': '100:90', 'opponent': 'Gamma'}]*10,
        'b_results': [{'won': False, 'score': '90:100', 'opponent': 'Gamma'}]*10}
    signal = SimpleNamespace(sport=sport, probability=.7, competitor_a='Alpha', competitor_b='Beta',
        selected_competitor='Alpha', provider_event_id='1', modeled_at=NOW.isoformat(),
        team_sport_snapshot={'team_sport_forecast': forecast, 'customer_recent_results': facts})
    forms = team_forms(signal, team_customer_explanation(signal))
    assert len(forms) == 2 and forms[0].results[0].score == '100:90'
    assert 'inkl. Verlängerung' in forms[0].scope
    if sport == 'Eishockey':
        assert 'Penaltyschießen' in forms[0].scope
    facts['source_input_hash'] = 'b'*64
    assert team_forms(signal, team_customer_explanation(signal)) == ()


def test_esports_never_invents_opponents_scores_or_time_order():
    from test_team_customer_facts import TeamCustomerFactsTests
    from team_customer_facts import team_customer_explanation
    from sports_form import team_forms
    signal = TeamCustomerFactsTests().esports_signal()
    signal.context_evidence.update(source_input_hash='a'*64, recent_results={
        'schema': 'esports-recent-results-v1', 'provider_event_id': '55', 'source_input_hash': 'a'*64,
        'competitor_a': 'Alpha', 'competitor_b': 'Beta', 'a_results': [True]*10, 'b_results': [False]*10})
    forms = team_forms(signal, team_customer_explanation(signal))
    before = deepcopy(forms)
    html = render_form_html(forms)
    assert 'Erfasste Reihenfolge' in html and 'Neueste zuerst' not in html
    # Two teams in both the 5-/10-game windows: one honest scope note per
    # team/window, never an invented opponent row for every win/loss flag.
    assert html.count('Nur Serienbilanz verfügbar') == 4
    assert 'form-opponent-preview' not in html and 'form-opponents' not in html
    assert 'Gegner nicht hinterlegt' not in html
    assert 'Keine weiteren Einzelspieldaten' not in html
    assert 'Gegner und Einzelresultat nicht hinterlegt' not in html
    assert html.count('class="form-result form-s"') == 15
    assert html.count('class="form-result form-n"') == 15
    assert '10S · 0N · 10 Spiele' in html and '0S · 10N · 10 Spiele' in html
    assert forms == before
    assert all(not r.opponent and not r.score and not r.date for f in forms for r in f.results)


def test_outcome_only_non_series_form_has_one_neutral_coverage_note():
    forms = (TeamForm('Alpha', 'Hartplatz', tuple(FormResult('S') for _ in range(5))),)
    before = deepcopy(forms)
    html = render_form_html(forms)
    assert html.count('Nur Bilanz verfügbar') == 1
    assert 'Nur Serienbilanz' not in html and 'form-opponent-row' not in html
    assert html.count('class="form-result form-s"') == 5
    assert '5S · 0N · 5 Spiele' in html
    assert forms == before


def test_mixed_form_keeps_real_details_without_empty_opponent_rows():
    results = (
        FormResult('S', '2:0', 'Gegner A', '2026-09-29'),
        FormResult('N'),
        FormResult('S', '1:0', 'Gegner B'),
        FormResult('N', date='2026-09-27'),
        FormResult('S', '3:1'),
    )
    forms = (TeamForm('Alpha', 'Serien · erfasste Reihenfolge', results),)
    before = deepcopy(forms)
    html = render_form_html(forms)
    assert html.count('class="form-opponent-row"') == 4
    assert html.count('1 Ergebnis ohne Spieldetails') == 1
    assert 'Nur Serienbilanz verfügbar' not in html
    assert 'Gegner A' in html and 'Gegner B' in html
    assert '27.09.2026' in html and '3:1' in html
    assert html.count('Gegner offen') == 2
    assert '1 weitere Spieldetails' in html and 'Alle 5 Spiele' not in html
    assert '3S · 2N · 5 Spiele' in html
    assert html.count('class="form-result form-s"') == 3
    assert html.count('class="form-result form-n"') == 2
    assert forms == before


def test_partial_form_window_counts_its_own_missing_details():
    results = tuple(FormResult('S', '2:0', f'Gegner {i}') if i in (0, 7)
                    else FormResult('N') for i in range(10))
    html = render_form_html((TeamForm('Alpha', 'Serien · erfasste Reihenfolge', results),))
    five, ten = html.split('class="form-window form-window-10"', 1)
    assert '4 Ergebnisse ohne Spieldetails' in five
    assert '8 Ergebnisse ohne Spieldetails' in ten
    assert five.count('class="form-opponent-row"') == 1
    assert ten.count('class="form-opponent-row"') == 2
    assert 'Gegner 7' not in five and 'Gegner 7' in ten


def test_rank_or_location_only_remains_a_real_observation_not_an_empty_row():
    forms = (TeamForm('Alpha', 'Hartplatz', (
        FormResult('S', rank=12), FormResult('N', venue='Auswärts'), FormResult('S'),
    )),)
    html = render_form_html(forms)
    assert html.count('class="form-opponent-row"') == 2
    assert 'Weltrang 12' in html and 'Auswärts' in html
    assert html.count('1 Ergebnis ohne Spieldetails') == 1
    assert '2S · 1N · 3 Spiele' in html
