"""Customer-visible regressions from the Claude source recheck."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from test_forecast_compact import InitialText
from test_publication_odds_floor import priced
from test_daily3_selection import NOW, football
from wettfinder_surface import build_wettfinder_card, render_editorial_card_html


def test_editorial_offer_source_and_time_are_visible_without_hover():
    # Removing visible quote provenance must fail even if its title survives.
    signal = priced(football(), (1.80,) * 3)
    card = build_wettfinder_card(signal, signal.reference_quote, now=NOW)
    before = deepcopy(card)

    markup = render_editorial_card_html(card)
    visible = InitialText(markup).visible

    assert 'Book <1>' in visible
    assert '01.01.2030 08:00' in visible  # 07:00 UTC is 08:00 in Zurich.
    assert '<1>' not in markup and '&lt;1&gt;' in markup
    assert card == before


def test_editorial_missing_offer_does_not_invent_provenance():
    card = build_wettfinder_card(football(), now=NOW)
    visible = InitialText(render_editorial_card_html(card)).visible
    assert 'Book ' not in visible and 'Stand:' not in visible


class _UtcHostDateTime(datetime):
    """Simulate the UTC VPS independently of the developer machine's zone."""

    def astimezone(self, tz=None):
        return super().astimezone(timezone.utc if tz is None else tz)

    @classmethod
    def now(cls, tz=None):
        return cls(2030, 1, 1, 23, 30, tzinfo=timezone.utc).astimezone(tz)


@pytest.mark.parametrize('value,want', [
    ('2030-01-01T23:30:00+00:00', '02.01.2030 00:30'),
    ('2030-07-01T22:30:00Z', '02.07.2030 00:30'),
    ('2030-07-02T01:30:00+03:00', '02.07.2030 00:30'),
    ('2030-01-01T23:30:00', 'n/a'),
    ('not-a-timestamp', 'n/a'),
    (None, 'n/a'),
])
def test_saved_tip_clock_is_zurich_not_the_server_zone(monkeypatch, value, want):
    import my_tips
    monkeypatch.setattr(my_tips, 'datetime', _UtcHostDateTime)
    assert my_tips._format_time(value) == want


@pytest.mark.parametrize('value,want', [
    ('2030-01-01T23:30:12+00:00', '02.01.2030 00:30:12'),
    ('2030-07-01T22:30:12Z', '02.07.2030 00:30:12'),
    ('2030-01-01T23:30:12', 'n/a'),
    ('not-a-timestamp', 'n/a'),
])
def test_scan_clock_is_zurich_not_the_server_zone(monkeypatch, value, want):
    import app
    monkeypatch.setattr(app, 'datetime', _UtcHostDateTime)
    assert app._format_snapshot_time(value) == want


def test_relative_publication_clock_uses_the_zurich_day_on_a_utc_server(monkeypatch):
    import app
    monkeypatch.setattr(app, 'datetime', _UtcHostDateTime)
    stamp = _UtcHostDateTime(2030, 1, 1, 22, 30, tzinfo=timezone.utc)
    assert app._format_stand(stamp) == 'gestern 23:30'


def test_filtered_primary_uses_next_statistical_market_not_largest_percentage(monkeypatch):
    # A 92% low-price selection must not silently promote a broad 91% cover
    # ahead of a 62% market with stronger same-revision statistical support.
    import app
    from test_wettfinder_statistical_leads import card, signal
    from test_workflow_integrity import _RecordingStreamlit
    from wettfinder_surface import compose_wettfinder_catalog, group_wettfinder_games
    removed = card(signal(1, 'RESULT_HOME', .92, .12, price=1.12))
    broad = card(signal(1, 'TOTAL_UNDER_4_5', .91, .01))
    supported = card(signal(1, 'HOME_UNDER_2_5', .62, .08))
    other = card(signal(2, 'RESULT_HOME', .75, .05))
    cards = (broad, other, removed, supported)
    before = deepcopy(cards)
    catalog = compose_wettfinder_catalog(cards)
    group = next(g for g in group_wettfinder_games(catalog) if g.lead.key == removed.key)
    assert catalog.event_leads[0].key == removed.key
    assert getattr(group, 'visible_lead', None) is supported

    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_games(catalog, {c.key: (None, c) for c in cards}, sport_filter='Alle')
    html = [text for text, _, _ in recording.markdown_calls if 'data-key=' in text]
    assert [next(c.key for c in cards if f'data-key="{c.key}"' in text) for text in html] == [
        other.key, supported.key, broad.key]
    assert cards == before


def test_fallback_never_reopens_opposite_direction_when_primary_has_no_offer():
    from dataclasses import replace
    from test_wettfinder_statistical_leads import card, signal
    from wettfinder_surface import compose_wettfinder_catalog, group_wettfinder_games
    primary = card(replace(signal(1, 'RESULT_HOME', .60, .12), reference_quote=None))
    opposite = card(signal(1, 'RESULT_AWAY', .40, .30))
    supported = card(signal(1, 'HOME_UNDER_2_5', .80, .08, price=1.20))
    broad = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01, price=8.0))
    catalog = compose_wettfinder_catalog((opposite, broad, supported, primary))
    group, = group_wettfinder_games(catalog)
    assert {item.key for item in group.cards} == {supported.key, broad.key}
    assert group.lead is primary
    assert getattr(group, 'visible_lead', None) is supported


def test_unranked_remainder_is_neutral_instead_of_inventing_a_primary(monkeypatch):
    import app
    from dataclasses import replace
    from test_wettfinder_statistical_leads import card, signal
    from test_workflow_integrity import _RecordingStreamlit
    from wettfinder_surface import compose_wettfinder_catalog, group_wettfinder_games
    removed = card(signal(1, 'RESULT_HOME', .92, .12, price=1.12))
    remainder = replace(card(signal(1, 'TOTAL_UNDER_4_5', .91, .01)), selection_rank=None)
    catalog = compose_wettfinder_catalog((removed, remainder))
    group, = group_wettfinder_games(catalog)
    assert getattr(group, 'visible_lead', None) is None
    recording = _RecordingStreamlit()
    monkeypatch.setattr(app, 'st', recording)
    app._render_wettfinder_games(catalog, {c.key: (None, c) for c in (removed, remainder)}, sport_filter='Alle')
    html = '\n'.join(text for text, _, _ in recording.markdown_calls)
    market_html = next(text for text, _, _ in recording.markdown_calls if 'data-key=' in text)
    assert html.count('class="se-match"') == 1
    assert 'class="se-card-top se-card-top-market"' in market_html
    assert 'class="se-match"' not in market_html


@pytest.mark.parametrize('changes', [
    {'model_version': 'foreign-model'}, {'fixture_source': 'foreign-provider'},
    {'home_team_id': 999}, {'input_cutoff_at': '2029-12-31T01:00:00Z'},
    {'modeled_at': None}, {'scheduled_start': '2030-01-01T12:00:00Z'},
])
def test_fallback_cannot_promote_foreign_or_missing_statistical_revision(changes):
    from dataclasses import replace
    from test_wettfinder_statistical_leads import card, signal
    from wettfinder_surface import WettfinderCatalog, group_wettfinder_games
    removed = card(signal(1, 'RESULT_HOME', .92, .12, price=1.12))
    foreign = replace(card(signal(1, 'HOME_UNDER_2_5', .80, .50)), **changes)
    supported = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    # The original catalog anchor is already fixed. A remaining foreign row
    # must not define a new revision merely because its market sorts first.
    catalog = WettfinderCatalog((), (foreign, supported), (), (removed,))
    group = next(g for g in group_wettfinder_games(catalog) if g.lead is removed)
    assert getattr(group, 'visible_lead', None) is supported


@pytest.mark.parametrize('anchor_change', [
    {'modeled_at': None}, {'input_cutoff_at': None}, {'scheduled_start': None},
    {'home_team_id': None}, {'model_version': ''}, {'policy_version': ''},
])
def test_unknown_original_cohort_cannot_authorize_a_fallback(anchor_change):
    from dataclasses import replace
    from forecast_selection import select_event_leads
    from test_wettfinder_statistical_leads import card, signal
    anchor = replace(card(signal(1, 'RESULT_HOME', .92, .12, price=1.12)), **anchor_change)
    offered = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    assert select_event_leads([offered], revision_anchors=[anchor]) == []


def test_empty_original_cohort_is_not_treated_as_unanchored_legacy_selection():
    from forecast_selection import select_event_leads
    from test_wettfinder_statistical_leads import card, signal
    offered = card(signal(1, 'TOTAL_UNDER_4_5', .90, .01))
    assert select_event_leads([offered], revision_anchors=[]) == []


def test_live_selection_does_not_claim_independent_model_confirmation(monkeypatch):
    import app
    from test_workflow_integrity import _RecordingStreamlit
    class LiveUI(_RecordingStreamlit):
        def selectbox(self, label, options, *, index=0, format_func=str, **kwargs):
            options = tuple(options)
            self.messages.extend(('option', format_func(option)) for option in options)
            return options[index]
        def dataframe(self, *_args, **_kwargs):
            pass
    ui = LiveUI(session_state={'live_football_snapshot': {
        'version': app.LIVE_SNAPSHOT_VERSION, 'scanned_at': '2030-01-01T23:30:00Z',
        'analyses': [{'fixture_id': 100, 'home_team': 'Alpha', 'away_team': 'Beta',
            'minute': 60, 'score': '1:0', 'btts_prob': 70., 'live_data_quality': 'MEDIUM',
            'model_calibrated': True, 'scheduled_start': '2030-01-01T22:30:00Z'}],
    }})
    monkeypatch.setattr(app, 'st', ui)
    monkeypatch.setattr('bet_finder_ui.st', ui)
    monkeypatch.setattr(app, 'datetime', _UtcHostDateTime)
    # The candidate builder, filters and selection renderer remain real.
    app._render_live_football(None, 'BTTS')
    options = [text for kind, text in ui.messages if kind == 'option' and 'Alpha vs Beta' in text]
    assert len(options) == 1 and options[0].startswith('Berechnet | ')
    assert 'geprüft' not in options[0]


def test_riskobet_customer_clocks_and_game_counts_use_zurich_german(monkeypatch):
    import riskobet_ui as ui
    from test_riskobet_ui import (
        MODELED, RecordingStreamlit, _all_text, _bundle, _checked_price_overlays, _view,
    )
    view = _view(_bundle('clock'))
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, 'st', fake)
    monkeypatch.setattr(ui, 'load_riskobet_view', lambda _path=None: view)
    monkeypatch.setattr(ui, 'load_shared_price_overlays', _checked_price_overlays)
    monkeypatch.setattr('tip_publication.record_riskobet_catalog', lambda *_a, **_kw: None)
    ui.render_riskobet(now=MODELED)
    text = _all_text(fake)
    assert '1 Szenario aus 1 Spiel · Stand: 02.01.2030 17:00' in text
    assert 'UTC' not in text and 'Event' not in text
    assert 'Stand: 02.01.2030 16:00' in text  # Original factor observation, not publication time.


def test_old_saved_source_identity_never_leaks_into_customer_caption(monkeypatch, tmp_path):
    import my_tips
    from account_identity import ACCOUNT_SCOPE_SESSION_KEY
    from test_tip_store import _decision
    from test_workflow_integrity import _RecordingStreamlit, _RecordingContext
    from tip_store import TipStore
    scope = 'a' * 32
    store = TipStore(tmp_path / 'tips.db', scope_id=scope)
    stored = store.save_decision(_decision(), source='api-football:42 @ 2030-01-01T07:00:00Z')
    class TipUI(_RecordingStreamlit):
        def columns(self, count, **_kwargs):
            return tuple(TipColumn(self, 'column') for _ in range(count))
    class TipColumn(_RecordingContext):
        def metric(self, *_args, **_kwargs):
            pass
        def button(self, *_args, **_kwargs):
            return False
    fake = TipUI(session_state={ACCOUNT_SCOPE_SESSION_KEY: scope})
    monkeypatch.setattr(my_tips, 'st', fake)
    monkeypatch.setattr(my_tips, 'TipStore', lambda **_kw: store)
    my_tips.render_saved_tips()
    captions = '\n'.join(str(value) for kind, value in fake.messages if kind == 'caption')
    assert 'Wettfinder' in captions
    assert 'api-football:42' not in captions and '2030-01-01T07:00:00Z' not in captions
    assert store.list_tips()[0].source == stored.source  # Presentation only; no evidence rewrite.
