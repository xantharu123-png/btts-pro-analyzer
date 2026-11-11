"""Heute und morgen, Schritt 2 (owner 10./11.11.2026): Doublebet and 15K preview tomorrow.

The preview is read-only. Reserving a Doublebet bet or placing a 15K ticket stays on the
match day, and tomorrow's selections are never recorded as tips, evidence, archive or shadow
before their own day (docs/audits/2026-11-11-morgen-vorschau-doublebet-15k.md).
"""
import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest
from streamlit.testing.v1 import AppTest

from daily3_selection import daily3_choices
from test_daily3_selection import NOW, _admitted_football

TODAY, TOMORROW = date(2030, 1, 1), date(2030, 1, 2)
# NOW is 07:00 UTC (08:00 in Zurich); 32 hours later is tomorrow 16:00 in Zurich.
TOMORROW_HOURS = 32


def _forbidden(name):
    def refuse(*_args, **_kwargs):
        raise AssertionError(f'{name} must not run for a preview')
    return refuse


# --- Doublebet selection -------------------------------------------------------------


def test_target_day_selects_a_tomorrow_row_that_the_match_day_does_not():
    tomorrow = _admitted_football(7, start_hours=TOMORROW_HOURS)
    assert daily3_choices([tomorrow], now=NOW) == ()
    choices = daily3_choices([tomorrow], now=NOW, target_day=TOMORROW)
    assert [choice.signal.key for choice in choices] == [tomorrow.key]


def test_preview_helper_plans_tomorrow_and_today_stays_unchanged():
    from daily3_selection import doublebet_preview_choices
    today = [_admitted_football(1, start_hours=3), _admitted_football(2, start_hours=6)]
    tomorrow = [_admitted_football(3, start_hours=TOMORROW_HOURS),
                _admitted_football(4, start_hours=TOMORROW_HOURS + 3)]
    mixed = today + tomorrow
    assert ([c.signal.key for c in daily3_choices(mixed, now=NOW)]
            == [c.signal.key for c in daily3_choices(today, now=NOW)] == ['1:RESULT_HOME', '2:RESULT_HOME'])
    preview = doublebet_preview_choices(mixed, now=NOW)
    assert [c.signal.key for c in preview] == ['3:RESULT_HOME', '4:RESULT_HOME']
    assert all(c.start.date() == TOMORROW for c in preview)


@pytest.mark.parametrize('day', [datetime(2030, 1, 2, tzinfo=timezone.utc), date(2029, 12, 31), date(2030, 1, 3), '2030-01-02'])
def test_target_day_outside_today_and_tomorrow_fails_closed(day):
    with pytest.raises(ValueError):
        daily3_choices([_admitted_football(7, start_hours=TOMORROW_HOURS)], now=NOW, target_day=day)


def test_listed_next_day_keeps_the_daily_model_lifetime_only_for_its_preview():
    from forecast_analysis import forecast_highlight_reason
    signal = _admitted_football(7, now=NOW - timedelta(hours=4), start_hours=TOMORROW_HOURS + 4)
    automatic = replace(signal, source='automated_wettfinder_forecast')
    # Default behavior unchanged: a tomorrow row is judged with the 150-minute window.
    assert forecast_highlight_reason(automatic, now=NOW, check_context=False) == 'Modellstand nicht aktuell belegt'
    assert forecast_highlight_reason(automatic, now=NOW, check_context=False, match_day=TOMORROW) == ''
    assert [c.signal.key for c in daily3_choices([automatic], now=NOW, target_day=TOMORROW)] == [automatic.key]
    # A manual (non-daily) model keeps its short window in the preview too.
    assert daily3_choices([signal], now=NOW, target_day=TOMORROW) == ()


# --- Doublebet page and rail ---------------------------------------------------------


def _render_doublebet_with_tomorrow(db_path):
    import streamlit as st
    from dataclasses import replace
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    from test_daily3_selection import NOW, football
    from test_publication_odds_floor import priced
    from daily3_ui import render_daily3
    from daily3_store import Daily3Store
    from test_morgen_vorschau import _forbidden
    st.session_state['_betboy_account_scope'] = 'a'*32
    pool = [football(1, start_hours=3), football(2, 'BTTS_YES', start_hours=32)]
    pool = [replace(priced(signal, (1.8,)*3), minimum_odds=1.5) for signal in pool]
    recorded = st.session_state.setdefault('recorded', [])

    def record(surface, rows, **_kwargs):
        recorded.append((surface, [row['candidate_id'] for row in rows]))
        return {'status': 'recorded'}

    with patch('tip_publication.record_selected_tips', record), \
         patch('tip_publication.record_signal_catalog', _forbidden('record_signal_catalog')), \
         patch('tip_publication.DEFAULT_HISTORY_DB', Path(db_path).with_suffix('.tips.db')):
        render_daily3(st, now=NOW,
            snapshot_loader=lambda **kw: SimpleNamespace(forecasts=pool, status=SimpleNamespace(generated_at=NOW)),
            store_factory=lambda: Daily3Store(db_path, key=b'q'*32, clock=lambda: NOW))


def test_doublebet_page_shows_tomorrow_read_only_and_records_only_today(tmp_path):
    app = AppTest.from_function(_render_doublebet_with_tomorrow, args=(str(tmp_path/'day.db'),)).run(timeout=30)
    assert not app.exception
    headings = [item.value for item in app.subheader]
    assert '1 Doublebet-Auswahl um Quote 2,00' in headings and 'Morgen (Vorschau)' in headings
    captions = ' '.join(item.value for item in app.caption)
    assert 'Vormerken erst am Spieltag' in captions and 'garantiert' not in captions.replace('nicht garantiert', '')
    cards = [item.value for item in app.markdown if 'data-key=' in item.value]
    assert any('Heimteam 1 vs ' in html for html in cards) and any('Heimteam 2 vs ' in html for html in cards)
    next(button for button in app.button if button.label == 'CHF 50 Tagesbudget bestätigen').click().run()
    assert not app.exception
    stake_keys = [str(item.key) for item in app.text_input if str(item.key).startswith('stake:')]
    assert len(stake_keys) == 1 and ':1:RESULT_HOME:' in stake_keys[0]
    assert [button.label for button in app.button].count('Einsatz vormerken') == 1
    recorded = app.session_state['recorded']
    assert recorded and all(surface == 'daily3_plan' and keys == ['1:RESULT_HOME'] for surface, keys in recorded)


def test_doublebet_preview_renderer_touches_no_store_form_or_recorder(monkeypatch):
    import daily3_store
    import daily3_ui
    import tip_publication
    from daily3_selection import doublebet_preview_choices
    from test_workflow_integrity import _RecordingStreamlit
    for module, name in ((tip_publication, 'record_selected_tips'), (tip_publication, 'record_signal_catalog'),
                         (daily3_store.Daily3Store, 'command'), (daily3_store.Daily3Store, '__init__')):
        monkeypatch.setattr(module, name, _forbidden(name))
    choices = doublebet_preview_choices([_admitted_football(5, start_hours=TOMORROW_HOURS)], now=NOW)
    assert len(choices) == 1
    ui = _RecordingStreamlit()  # No form, text_input or form_submit_button: any use raises.
    daily3_ui.render_doublebet_preview(ui, choices, now=NOW)
    messages = dict(ui.messages)
    assert messages['subheader'] == 'Morgen (Vorschau)'
    assert any('Heimteam 5 vs ' in value for value, _kwargs, _context in ui.markdown_calls)
    empty = _RecordingStreamlit()
    daily3_ui.render_doublebet_preview(empty, (), now=NOW)
    assert not empty.messages  # No fictional preview section without a choice.


def test_wettfinder_rail_lists_tomorrow_without_recording_it(monkeypatch):
    import app
    import tip_publication
    from daily3_selection import doublebet_preview_choices
    from test_workflow_integrity import _RecordingStreamlit
    pool = [_admitted_football(1, start_hours=3), _admitted_football(2, start_hours=TOMORROW_HOURS)]
    choices = daily3_choices(pool, now=NOW)
    preview = doublebet_preview_choices(pool, now=NOW)
    recorded = []
    monkeypatch.setattr(tip_publication, 'record_signal_catalog',
                        lambda surface, signals, **_kw: recorded.append((surface, [s.key for s in signals])))
    ui = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', ui)
    app._render_editorial_rail(choices, (), daily3_allowed=True, target_label='Heute', as_of=NOW,
                               source_run_id=NOW.isoformat(), preview_choices=preview)
    assert recorded == [('daily3_rail', ['1:RESULT_HOME'])]
    html = '\n'.join(value for value, _kwargs, _context in ui.markdown_calls)
    assert 'Morgen (Vorschau)' in html and 'Heimteam 2 vs ' in html
    # Without the entitlement there is no preview either.
    locked = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', locked)
    app._render_editorial_rail((), (), daily3_allowed=False, target_label='Heute', preview_choices=preview)
    assert 'Heimteam 2 vs ' not in '\n'.join(value for value, _kwargs, _context in locked.markdown_calls)


def test_wettfinder_page_feeds_the_rail_preview_from_the_same_forecasts():
    import inspect
    import app
    source = inspect.getsource(app._render_automated_daily_selection)
    assert 'doublebet_preview_choices(snapshot.forecasts, now=evaluation_now)' in source
    assert 'preview_choices=preview_choices' in source


# --- 15K -------------------------------------------------------------------------------

ARTIFACT_NOW = datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc)


def _next_day_candidate():
    from tests.test_wettfinder_automation import _football_snapshot
    original = _football_snapshot(ARTIFACT_NOW)['shortlist'][0]
    candidate = replace(original, candidate_id='fixture-2-btts', fixture_id=2,
                        kickoff='2030-01-02T15:00:00+00:00')
    candidate.context = dict(original.context)
    return candidate


def _artifact(tmp_path):
    import wettfinder_automation as automation
    from config_loader import AppConfig
    from test_challenge_15k import reference_quote_for
    from tests.test_wettfinder_next_day import _today_snapshot

    candidate = _next_day_candidate()
    quotes = {candidate.candidate_id: reference_quote_for(candidate, ARTIFACT_NOW)}

    def scan(day):
        if day == TOMORROW:
            from tests.test_wettfinder_automation import _football_snapshot
            snapshot = _football_snapshot(ARTIFACT_NOW)
            snapshot.update(shortlist=[], wettfinder_candidates=[candidate], discovery_candidates=[candidate],
                            context_fixture_statuses={'2': 'verified'},
                            fixture_kickoffs=['2030-01-02T15:00:00+00:00'])
            return snapshot
        return _today_snapshot()

    def refuse(*_args):
        raise AssertionError('no context refresh expected')

    artifact = tmp_path / 'wettfinder.json'
    document = automation.run_wettfinder(
        now=ARTIFACT_NOW, state_path=artifact, config=AppConfig(api_football_key='test'),
        football_scanner=scan, football_context_refresher=refuse,
        football_quote_loader=lambda rows: ({row['candidate_id']: quotes[row['candidate_id']]
                                             for row in rows if row.get('candidate_id') in quotes}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [], football_next_day=True,
    )
    assert document['next_day_search_date'] == '2030-01-02'
    return artifact, json.loads(artifact.read_text(encoding='utf-8'))


def _scope(day):
    from challenge_15k import MAX_SCAN_FIXTURES, _scope_signature
    from league_catalog import ALTERNATIVE_MARKET_LEAGUES
    return _scope_signature(list(ALTERNATIVE_MARKET_LEAGUES), day, MAX_SCAN_FIXTURES)


def test_next_day_15k_preview_is_rebuilt_from_the_artifact_without_a_ticket_pool(tmp_path):
    from wettfinder_automation import build_next_day_challenge_preview, build_scheduled_challenge_snapshot
    _artifact_path, document = _artifact(tmp_path)

    preview = build_next_day_challenge_preview(document, scope=_scope(TOMORROW))
    assert preview is not None and preview['search_date'] == '2030-01-02'
    assert [c.candidate_id for c in preview['challenge_model_candidates']] == ['fixture-2-btts']
    assert preview['shortlist'] == [] and preview['price_candidates'] == [] and preview['approved_candidates'] == 0
    assert 'fixture-2-btts' in preview['reference_quotes']
    # Only the validated next day of this artifact, only with the next day's scope.
    assert build_next_day_challenge_preview(document, scope=_scope(TODAY)) is None
    assert build_next_day_challenge_preview(document, scope=_scope(date(2030, 1, 3))) is None
    unmarked = {key: value for key, value in document.items() if key != 'next_day_search_date'}
    assert build_next_day_challenge_preview(unmarked, scope=_scope(TOMORROW)) is None
    # Today unchanged: the match-day snapshot never carries the next day's game.
    today = build_scheduled_challenge_snapshot(document, scope=_scope(TODAY))
    assert today is not None
    assert all(c.fixture_id != 2 for c in (*today['base_shortlist'], *today['challenge_model_candidates']))


class _FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        frozen = ARTIFACT_NOW + timedelta(minutes=30)
        return frozen if tz is None else frozen.astimezone(tz)


def _render_15k_morgen(artifact_path):
    import json
    from datetime import date
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    import streamlit as st
    import challenge_15k
    from test_morgen_vorschau import _FrozenClock, _forbidden
    st.session_state.setdefault('challenge_date_mode', 'Morgen')
    document = json.loads(Path(artifact_path).read_text(encoding='utf-8'))
    ledger = SimpleNamespace(pending_tickets=lambda: [], place_ticket=_forbidden('place_ticket'))
    with patch('challenge_15k.load_app_config', lambda _st: SimpleNamespace(api_football_key='k', weather_key='w')), \
         patch('challenge_15k._challenge_today', lambda now=None: date(2030, 1, 1)), \
         patch('challenge_15k.datetime', _FrozenClock), \
         patch('challenge_15k.read_shared_quote_rows', lambda *a, **k: []), \
         patch('wettfinder_automation.load_state', lambda *a, **k: document), \
         patch('challenge_15k.ChallengeDataProvider', _forbidden('provider scan')), \
         patch('challenge_15k.scan_jobs.start_job', _forbidden('provider scan')), \
         patch('challenge_15k._challenge_auto_recheck_fragment', _forbidden('auto recheck')), \
         patch('challenge_15k._scheduled_challenge_refresh_fragment', _forbidden('match-day refresh')), \
         patch('challenge_15k._load_scheduled_challenge_snapshot', _forbidden('match-day snapshot')):
        challenge_15k._render_analysis(ledger, {'current_balance': 100.0, 'stake_fraction': 0.05})


def test_15k_morgen_page_renders_tomorrow_cards_without_scan_or_ticket_form(tmp_path):
    artifact, _document = _artifact(tmp_path)
    app = AppTest.from_function(_render_15k_morgen, args=(str(artifact),)).run(timeout=60)
    assert not app.exception
    assert 'Morgen (Vorschau)' in [item.value for item in app.subheader]
    captions = ' '.join(item.value for item in app.caption)
    assert 'erst am Spieltag' in captions
    visible = ' '.join(item.value for item in app.markdown)
    assert 'FC Alpha' in visible and 'se-match' in visible
    assert not app.multiselect and not app.number_input
    assert not any('neu prüfen' in button.label for button in app.button)


def _render_15k_manual_morgen():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import patch
    import streamlit as st
    import challenge_15k
    from challenge_15k import (ALTERNATIVE_MARKET_LEAGUES, CHALLENGE_SNAPSHOT_VERSION, DEFAULT_CHALLENGE_LEAGUES,
                               MAX_SCAN_FIXTURES, _challenge_today, _scope_signature)
    from datetime import timedelta
    from test_challenge_15k import reference_quote_for, stress_safe_ticket_candidates
    from test_morgen_vorschau import _forbidden
    favorites = [league for league in DEFAULT_CHALLENGE_LEAGUES if league in ALTERNATIVE_MARKET_LEAGUES]
    st.session_state.setdefault('challenge_date_mode', 'Morgen')
    st.session_state.setdefault('challenge_league_scope_v2', f'Favoriten ({len(favorites)})')
    now = datetime.now(timezone.utc)
    candidates = stress_safe_ticket_candidates()
    st.session_state.setdefault('challenge_snapshot', {
        'version': CHALLENGE_SNAPSHOT_VERSION,
        'scope': _scope_signature(favorites, _challenge_today() + timedelta(days=1), MAX_SCAN_FIXTURES),
        'scanned_at': now.isoformat(), 'search_date': (_challenge_today() + timedelta(days=1)).isoformat(),
        'challenge_model_candidates': candidates,
        'reference_quotes': {c.candidate_id: reference_quote_for(c, now).to_dict() for c in candidates},
    })
    ledger = SimpleNamespace(pending_tickets=lambda: [], place_ticket=_forbidden('place_ticket'))
    with patch('challenge_15k.load_app_config', lambda _st: SimpleNamespace(api_football_key='', weather_key='')), \
         patch('challenge_15k.read_shared_quote_rows', lambda *a, **k: []):
        challenge_15k._render_analysis(ledger, {'current_balance': 100.0, 'stake_fraction': 0.05})


def test_15k_manual_morgen_result_shows_cards_but_tickets_only_on_the_match_day():
    app = AppTest.from_function(_render_15k_manual_morgen).run(timeout=60)
    assert not app.exception
    assert any('Beide Teams treffen' in item.value for item in app.markdown)
    assert not app.multiselect and not app.number_input
    assert 'erst am Spieltag' in ' '.join(item.value for item in app.caption)
