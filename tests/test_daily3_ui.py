from streamlit.testing.v1 import AppTest


def _render(db_path, missing_identity=False, price_state=None):
    import streamlit as st
    from dataclasses import replace
    from datetime import timedelta
    from types import SimpleNamespace
    from test_daily3_selection import NOW, football
    from daily3_ui import render_daily3
    from daily3_store import Daily3Store
    from market_consensus import MarketConsensus, QuotePoint, REFERENCE_SOURCE
    from wettfinder_surface import build_wettfinder_card
    st.set_page_config(layout='wide')
    if not missing_identity:
        st.session_state['_betboy_account_scope'] = 'a'*32
    def loader(**kwargs):
        st.session_state['snapshot_loads'] = st.session_state.get('snapshot_loads', 0)+1
        probability = .7 if st.session_state.get('changed_model') else .65
        signal = football(probability=probability)
        if price_state in ('too_low', 'stale'):
            observed_at = NOW - timedelta(hours=2) if price_state == 'stale' else NOW
            points = tuple(
                QuotePoint(
                    bookmaker=f'Book {index}', odds=1.12,
                    bookmaker_id=f'api-football:{index}',
                    observed_at=observed_at.isoformat(),
                )
                for index in range(1, 4)
            )
            quote = MarketConsensus(
                fixture_id=signal.fixture_id,
                candidate_id=signal.candidate_id,
                market_key=signal.market_key,
                bet_name='Match Winner', value_name='Home',
                consensus_odds=1.12, conservative_odds=1.12,
                lowest_odds=1.12, best_odds=1.12,
                bookmaker_count=3, quoted_at=observed_at.isoformat(),
                fetched_at=observed_at.isoformat(), source=REFERENCE_SOURCE,
                points=points, scheduled_start=signal.scheduled_start,
                event_home=signal.home_team, event_away=signal.away_team,
            )
            signal = replace(signal, minimum_odds=2.00, reference_quote=quote.to_dict())
        elif price_state == 'missing':
            signal = replace(signal, minimum_odds=2.00, reference_quote=None)
        card = build_wettfinder_card(signal, signal.reference_quote, now=NOW)
        st.session_state['fixture_price_code'] = card.price_code
        return SimpleNamespace(forecasts=(signal,))
    render_daily3(st, now=NOW, snapshot_loader=loader,
                  store_factory=lambda: Daily3Store(db_path, key=b'q'*32, clock=lambda: NOW))


def _button(app, label):
    return next(b for b in app.button if b.label == label)


def _field(app, kind, prefix):
    return next(item for item in getattr(app, kind) if str(item.key).startswith(prefix))


def test_real_user_flow_start_reserve_place_settle_is_flat_and_persistent(tmp_path):
    app = AppTest.from_function(_render, args=(str(tmp_path/'daily3.db'),)).run(timeout=30)
    assert not app.exception
    assert app.header[0].value == '3 a day keeps the job away'
    assert app.session_state['snapshot_loads'] == 1
    assert not any('Analyse' in e.label for e in app.expander)
    _button(app, 'CHF 50 Tagesbudget bestätigen').click().run()
    assert not app.exception
    assert _field(app, 'text_input', 'stake:').value == ''
    assert _field(app, 'text_input', 'odds:').value == ''
    _field(app, 'text_input', 'stake:').set_value('20,00')
    _field(app, 'text_input', 'odds:').set_value('1,12')
    _field(app, 'checkbox', 'exact:').check()
    _button(app, 'Einsatz vormerken').click().run()
    assert not app.exception and not app.error
    assert any(m.label == 'Verfügbar' and m.value == 'CHF 30.00' for m in app.metric)
    _field(app, 'text_input', 'ref:').set_value('Echter Buchmacherbeleg')
    _field(app, 'checkbox', 'placed:').check()
    _button(app, 'Als platziert bestätigen').click().run()
    assert not app.exception and not app.error
    _field(app, 'text_input', 'returned:').set_value('22,40')
    _field(app, 'text_input', 'settled-ref:').set_value('Abrechnung nach Gebühren')
    _field(app, 'checkbox', 'settled-confirm:').check()
    _button(app, 'Abrechnung bestätigen').click().run()
    assert not app.exception and not app.error
    assert any(m.label == 'Verfügbar' and m.value == 'CHF 52.40' for m in app.metric)
    app.run()
    assert any(m.label == 'Netto abgerechnet' and m.value == 'CHF 2.40' for m in app.metric)


def test_too_low_current_quote_warns_without_hiding_selection_or_money_flow(tmp_path):
    app = AppTest.from_function(
        _render, args=(str(tmp_path/'daily3.db'), False, 'too_low')
    ).run(timeout=30)
    assert not app.exception
    assert app.session_state['fixture_price_code'] == 'TOO_LOW'
    assert any(
        'Quote' in warning.value
        and ('unter' in warning.value.lower() or 'niedrig' in warning.value.lower())
        for warning in app.warning
    )
    assert any('Heimteam 1' in item.value for item in app.subheader)
    _button(app, 'CHF 50 Tagesbudget bestätigen').click().run()
    assert not app.exception
    assert any(button.label == 'Einsatz vormerken' for button in app.button)


def test_missing_or_stale_quote_status_does_not_change_model_selection(tmp_path):
    for price_state, expected_code, expected_label in (
        ('missing', 'UNAVAILABLE', 'Quote fehlt'),
        ('stale', 'STALE', 'Veraltet'),
    ):
        app = AppTest.from_function(
            _render, args=(str(tmp_path/f'{price_state}.db'), False, price_state)
        ).run(timeout=30)
        assert not app.exception
        assert app.session_state['fixture_price_code'] == expected_code
        assert any(expected_label in item.value for item in app.info)
        assert any('Heimteam 1' in item.value for item in app.subheader)


def test_changed_analysis_invalidates_only_unsubmitted_confirmation(tmp_path):
    app = AppTest.from_function(_render, args=(str(tmp_path/'daily3.db'),)).run(timeout=30)
    _button(app, 'CHF 50 Tagesbudget bestätigen').click().run()
    _field(app, 'text_input', 'stake:').set_value('20')
    _field(app, 'text_input', 'odds:').set_value('1.5')
    _field(app, 'checkbox', 'exact:').check()
    app.session_state['changed_model'] = True
    _button(app, 'Einsatz vormerken').click().run()
    assert not app.exception
    assert any('Analyse hat sich' in item.value for item in app.error)
    assert any(m.label == 'Verfügbar' and m.value == 'CHF 50.00' for m in app.metric)


def test_rerender_with_new_analysis_clears_unsubmitted_confirmation_and_stake(tmp_path):
    app = AppTest.from_function(_render, args=(str(tmp_path/'daily3.db'),)).run(timeout=30)
    _button(app, 'CHF 50 Tagesbudget bestätigen').click().run()
    original_key = _field(app, 'text_input', 'stake:').key
    _field(app, 'text_input', 'stake:').set_value('20')
    _field(app, 'text_input', 'odds:').set_value('1.12')
    _field(app, 'checkbox', 'exact:').check()
    app.session_state['changed_model'] = True
    app.run()
    assert not app.exception
    assert _field(app, 'text_input', 'stake:').key != original_key
    assert _field(app, 'text_input', 'stake:').value == ''
    assert _field(app, 'text_input', 'odds:').value == ''
    assert _field(app, 'checkbox', 'exact:').value is False


def test_no_scope_means_no_anonymous_money_account_but_visible_models(tmp_path):
    db = tmp_path/'daily3.db'
    app = AppTest.from_function(_render, args=(str(db), True)).run(timeout=30)
    assert not app.exception and not db.exists()
    assert any('Heimteam 1' in item.value for item in app.subheader)
    assert not any(button.label == 'CHF 50 Tagesbudget bestätigen' for button in app.button)


def test_day_close_does_not_hide_pending_real_bet_or_refill(tmp_path):
    app = AppTest.from_function(_render, args=(str(tmp_path/'daily3.db'),)).run(timeout=30)
    _button(app, 'CHF 50 Tagesbudget bestätigen').click().run()
    _field(app, 'text_input', 'stake:').set_value('50')
    _field(app, 'text_input', 'odds:').set_value('2')
    _field(app, 'checkbox', 'exact:').check()
    _button(app, 'Einsatz vormerken').click().run()
    _button(app, 'Für heute beenden').click().run()
    assert not app.exception
    assert any(button.label == 'Als platziert bestätigen' for button in app.button)
    assert not any(button.label == 'CHF 50 Tagesbudget bestätigen' for button in app.button)
    assert any(m.label == 'Verfügbar' and m.value == 'CHF 0.00' for m in app.metric)
