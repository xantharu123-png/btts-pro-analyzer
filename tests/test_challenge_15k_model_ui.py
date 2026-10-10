"""Real Streamlit render checks for quote-free 15K model selections."""

from streamlit.testing.v1 import AppTest


def _render_model_candidates() -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from challenge_15k import _render_model_challenge
    from test_challenge_15k import stress_safe_ticket_candidates

    candidates = stress_safe_ticket_candidates()
    for candidate in candidates:
        candidate.context.update(
            release_context_complete=False,
            release_eligible=False,
            lineups={"status": "pending", "required": False},
        )
    _render_model_challenge(
        {
            "search_date": datetime.now(timezone.utc).date().isoformat(),
            "challenge_model_candidates": candidates,
            "reference_quotes": {
                candidates[0].candidate_id: {"best_odds": 1.05},
            },
        },
        SimpleNamespace(pending_tickets=lambda: []),
        {"current_balance": 100.0, "stake_fraction": 0.05},
    )


def test_15k_model_cards_render_without_quote_or_nested_expander():
    app = AppTest.from_function(_render_model_candidates).run(timeout=30)
    assert not app.exception
    assert [heading.value for heading in app.subheader] == ["15K-Modellauswahl"]
    assert len(app.multiselect) == 1
    assert not app.get("popover")
    visible = " ".join(item.value for item in app.markdown)
    captions = " ".join(item.value for item in app.caption)
    assert "Beide Teams treffen" in visible
    assert "Quote 1.05" not in visible + captions
    assert "Preisfreigabe" not in visible + captions
    assert "vorläufig" not in visible + captions
    assert 'class="se-match"' in visible
    assert 'class="se-card' in visible or 'se-card"' in visible
    assert 'Die Auswahl im Kurzcheck' in visible
    assert 'vorsichtige Rechnung' not in captions
    assert app.multiselect[0].placeholder == 'Auswahlen wählen'


def _render_editorial_models() -> None:
    from types import SimpleNamespace
    from challenge_15k import _render_model_challenge
    from test_challenge_15k_model_ui import editorial_snapshot
    _render_model_challenge(editorial_snapshot(), SimpleNamespace(pending_tickets=lambda: []),
                            {"current_balance": 100.0, "stake_fraction": 0.05})


def editorial_snapshot(candidates=None, *, now=None):
    from datetime import datetime, timedelta, timezone
    from football_customer_facts import build_football_recent_results
    from test_challenge_15k import stress_safe_ticket_candidates
    from wettfinder_automation import _football_candidate_record
    now = now or datetime.now(timezone.utc)
    candidates = stress_safe_ticket_candidates() if candidates is None else candidates
    records = {}
    for candidate in candidates:
        candidate.context['injuries'] = {"status": "observed", "availability": "available",
            "coverage_available": True, "checked_at": now.isoformat(),
            "home_missing": 2, "away_missing": 1, "home_names": ['Spieler A', 'Spieler B'],
            "away_names": ['Spieler C']}
        history = []
        for side, team_id in (('home', candidate.home_team_id), ('away', candidate.away_team_id)):
            for i in range(10):
                history.append({'fixture': {'id': 1000+candidate.fixture_id*100+(0 if side=='home' else 30)+i,
                    'date': (now-timedelta(days=i+1)).isoformat(), 'status': {'short': 'FT'}},
                    'teams': {'home': {'id': team_id}, 'away': {'id': 900+i, 'name': 'Gegner '+str(i+1)}},
                    'goals': {'home': 2, 'away': 1}, 'league': {'id': 39, 'name': 'Testliga'}})
        fixture = {'fixture': {'id': candidate.fixture_id, 'date': candidate.kickoff},
                   'teams': {'home': {'id': candidate.home_team_id}, 'away': {'id': candidate.away_team_id}}}
        recent = build_football_recent_results(fixture, history, as_of=now, model_scope=candidate.model_scope)
        records[candidate.candidate_id] = _football_candidate_record(candidate,
            context_checked_at=now, customer_recent_results=recent)
    return {'scanned_at': now.isoformat(), 'search_date': now.date().isoformat(),
            'challenge_model_candidates': candidates, 'challenge_display_records': records}


def test_15k_uses_same_form_scores_and_crests_as_wettfinder_without_internal_notes():
    app = AppTest.from_function(_render_editorial_models).run(timeout=30)
    assert not app.exception
    visible = ' '.join(item.value for item in app.markdown)
    assert 'se-shield-football' in visible and 'media.api-sports.io/football/teams/' in visible
    assert 'Aktuelle Form' in visible and '5 Spiele' in visible and '10 Spiele' in visible
    assert 'Gegner & Ergebnisse' in visible and 'Gegner 1' in visible and '2:1' in visible
    assert '2 Heim' in visible and '1 Gast' in visible and 'Spieler A' in visible
    for internal in ('Evidenzprüfung', 'heuristisch', 'vorsichtige Rechnung', 'Trainingsstichtag'):
        assert internal not in visible
    assert len(app.expander) == 2
    assert '1 Auswahl' in app.expander[0].label and '1 Auswahlen' not in app.expander[0].label


def test_15k_presentation_keeps_model_inputs_and_original_evidence_unchanged():
    from copy import deepcopy
    from datetime import datetime, timezone
    from challenge_15k import _challenge_card_signal
    from wettfinder_surface import build_wettfinder_card
    snapshot = editorial_snapshot()
    before = deepcopy(snapshot)
    candidate = snapshot['challenge_model_candidates'][0]
    signal = _challenge_card_signal(candidate, snapshot)
    card = build_wettfinder_card(signal, now=datetime.now(timezone.utc))
    assert card.model_probability == candidate.probability
    assert signal.model_version == candidate.prediction_version
    assert signal.modeled_at == snapshot['challenge_display_records'][candidate.candidate_id]['modeled_at']
    assert len(card.compact_analysis.forms[0].results) == 10
    assert snapshot == before


def test_15k_does_not_use_another_matches_saved_form():
    from challenge_15k import _challenge_card_signal
    from datetime import datetime, timezone
    from wettfinder_surface import build_wettfinder_card
    snapshot = editorial_snapshot()
    first, second = snapshot['challenge_model_candidates']
    snapshot['challenge_display_records'][first.candidate_id] = snapshot['challenge_display_records'][second.candidate_id]
    card = build_wettfinder_card(_challenge_card_signal(first, snapshot), now=datetime.now(timezone.utc))
    assert not card.compact_analysis.forms
    assert 'Gegner 1' not in card.analysis_basis


def test_15k_manual_snapshot_retains_bound_recent_form_without_saved_rows():
    from challenge_15k import _challenge_card_signal
    from datetime import datetime, timezone
    from wettfinder_surface import build_wettfinder_card
    snapshot = editorial_snapshot()
    candidate = snapshot['challenge_model_candidates'][0]
    record = snapshot.pop('challenge_display_records')[candidate.candidate_id]
    snapshot['football_recent_results'] = {
        str(candidate.fixture_id): record['analysis_evidence']['basis']['customer_recent_results']}
    signal = _challenge_card_signal(candidate, snapshot)
    card = build_wettfinder_card(signal, now=datetime.now(timezone.utc))
    assert len(card.compact_analysis.forms[0].results) == 10
    assert signal.modeled_at == snapshot['scanned_at']


def test_15k_rejects_saved_form_from_a_different_model_version():
    from challenge_15k import _challenge_card_signal
    from datetime import datetime, timezone
    from wettfinder_surface import build_wettfinder_card
    snapshot = editorial_snapshot()
    candidate = snapshot['challenge_model_candidates'][0]
    snapshot['challenge_display_records'][candidate.candidate_id]['model_version'] = 'other-model'
    card = build_wettfinder_card(_challenge_card_signal(candidate, snapshot), now=datetime.now(timezone.utc))
    assert not card.compact_analysis.forms


def test_15k_editorial_card_displays_existing_exact_quote_without_promoting_model():
    from challenge_15k import _challenge_card_signal
    from datetime import datetime, timezone
    from test_challenge_15k import reference_quote_for
    from wettfinder_surface import build_wettfinder_card, render_editorial_card_html
    snapshot = editorial_snapshot()
    candidate = snapshot['challenge_model_candidates'][0]
    now = datetime.now(timezone.utc)
    quote = reference_quote_for(candidate, now)
    card = build_wettfinder_card(_challenge_card_signal(candidate, snapshot), quote=quote, now=now)
    # Same executable offer chosen by the shared Wettfinder price display.
    assert card.observed_odds == 2.10
    assert '2.10' in render_editorial_card_html(card)
    assert card.model_probability == candidate.probability
    assert not card.confirmed_tip


def test_15k_preserves_saved_stale_context_instead_of_showing_fresh_absences():
    from challenge_15k import _challenge_card_signal
    from datetime import datetime, timezone
    from wettfinder_surface import build_wettfinder_card
    snapshot = editorial_snapshot()
    candidate = snapshot['challenge_model_candidates'][0]
    snapshot['challenge_display_records'][candidate.candidate_id]['context_stale'] = True
    signal = _challenge_card_signal(candidate, snapshot)
    assert signal.analysis_evidence['context']['stale'] is True
    card = build_wettfinder_card(signal, now=datetime.now(timezone.utc))
    injury = next(fact for fact in card.compact_analysis.facts if fact.label == 'Ausfälle')
    assert injury.value == 'veraltet'


def _15k_daily_age_card(*, automatic, bound=True):
    from datetime import datetime, timedelta, timezone
    from challenge_15k import _challenge_card_signal
    from test_challenge_15k import candidate
    from wettfinder_surface import build_wettfinder_card
    modeled_at = datetime(2026, 10, 9, 6, tzinfo=timezone.utc)
    item = candidate('1:BTTS', 1, .80, kickoff=modeled_at + timedelta(hours=8))
    snapshot = editorial_snapshot([item], now=modeled_at)
    # This test isolates daily MODEL age; current context has a separate clock.
    from highlight_fixtures import football_checks
    from copy import deepcopy
    record = snapshot['challenge_display_records'][item.candidate_id]
    record['context'] = football_checks(modeled_at + timedelta(hours=4))
    record['analysis_evidence']['context'] = deepcopy(record['context'])
    if automatic:
        snapshot['automatic_source'] = 'wettfinder_systemd_timer'
    if not bound:
        snapshot.pop('challenge_display_records')
    signal = _challenge_card_signal(item, snapshot)
    return signal, build_wettfinder_card(signal, now=modeled_at + timedelta(hours=4))


def test_15k_daily_model_uses_same_freshness_display_as_automatic_wettfinder():
    signal, card = _15k_daily_age_card(automatic=True)
    assert signal.source == 'automated_wettfinder_forecast'
    assert signal.modeled_at == '2026-10-09T06:00:00+00:00'
    assert card.highlight_reason == ''
    assert not card.confirmed_tip


def test_15k_manual_model_retains_existing_short_freshness_window():
    signal, card = _15k_daily_age_card(automatic=False)
    assert signal.source == 'challenge_15k_forecast'
    assert card.highlight_reason == 'Modellstand nicht aktuell belegt'


def test_15k_daily_marker_without_bound_original_does_not_extend_freshness():
    signal, card = _15k_daily_age_card(automatic=True, bound=False)
    assert signal.source == 'challenge_15k_forecast'
    assert card.highlight_reason == 'Modellstand nicht aktuell belegt'


def test_15k_asks_for_actual_odds_only_after_user_selects_models():
    app = AppTest.from_function(_render_model_candidates).run(timeout=30)
    assert not app.exception
    assert not app.number_input
    app.multiselect[0].set_value(["1:BTTS", "2:BTTS"]).run(timeout=30)
    assert not app.exception
    assert len(app.number_input) == 2
    assert any(item.value == "Tatsächliche Wette erfassen" for item in app.subheader)
    app.number_input[0].set_value(1.50).run(timeout=30)
    app.number_input[1].set_value(1.50).run(timeout=30)
    assert not app.exception
    assert any(item.label == "Tatsächliche Gesamtquote" for item in app.metric)
