from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from test_sports_editorial import editorial_football, editorial_tennis, NOW
from wettfinder_identity import rendered_identity_card, with_identity_images
from wettfinder_surface import build_wettfinder_card


def recorder(monkeypatch):
    import sports_identity_media
    calls = []
    def image(kind, name, **kwargs):
        calls.append((kind, name, kwargs))
        return SimpleNamespace(image_url='image-' + name, source_url=None, credit=None)
    monkeypatch.setattr(sports_identity_media, 'participant_image', image)
    return calls


def test_pure_or_non_ui_render_never_loads_images(monkeypatch):
    calls = recorder(monkeypatch)
    signal = editorial_football()
    card = build_wettfinder_card(signal, now=NOW)
    assert with_identity_images(card, signal) is card
    assert rendered_identity_card(card, signal) is card
    assert calls == []


def test_images_are_disposable_presentation_fields_not_signal_or_money(monkeypatch):
    calls = recorder(monkeypatch)
    signal = replace(editorial_tennis(), competitor_a='Arthur Gea', competitor_b='Zhang Zhizhen')
    before = deepcopy(vars(signal))
    card = build_wettfinder_card(signal, now=NOW)
    decorated = with_identity_images(card, signal, enabled=True)
    assert [call[1] for call in calls] == ['Arthur Gea', 'Zhang Zhizhen']
    assert decorated.home_image == 'image-Arthur Gea'
    assert decorated.away_image == 'image-Zhang Zhizhen'
    assert card.home_image is None
    assert vars(signal) == before
    assert {key: value for key, value in vars(decorated).items() if '_image' not in key} == {
        key: value for key, value in vars(card).items() if '_image' not in key}


def test_native_football_namespace_inferred_only_from_bound_automatic_identity(monkeypatch):
    calls = recorder(monkeypatch)
    signal = replace(editorial_football(), source='automated_wettfinder_forecast')
    card = build_wettfinder_card(signal, now=NOW)
    with_identity_images(card, signal, enabled=True)
    assert [call[0] for call in calls] == ['football', 'football']
    assert [call[2]['fixture_source'] for call in calls] == ['api_football', 'api_football']
    assert [call[2]['team_id'] for call in calls] == [card.home_team_id, card.away_team_id]


@pytest.mark.parametrize('change', ['foreign', 'missing', 'misbound', 'wrong_producer'])
def test_unknown_or_foreign_namespace_never_inferred(monkeypatch, change):
    calls = recorder(monkeypatch)
    signal = replace(editorial_football(), source='automated_wettfinder_forecast')
    if change == 'foreign':
        signal = replace(signal, fixture_source='another_provider')
    elif change == 'missing':
        signal = replace(signal, analysis_evidence=None)
    elif change == 'wrong_producer':
        signal = replace(signal, source='unknown')
    else:
        evidence = deepcopy(signal.analysis_evidence)
        evidence['identity']['home_id'] = 999
        signal = replace(signal, analysis_evidence=evidence)
    card = build_wettfinder_card(signal, now=NOW)
    with_identity_images(card, signal, enabled=True)
    assert all(call[2]['fixture_source'] != 'api_football' for call in calls)


def test_missing_images_leave_card_unmodified(monkeypatch):
    import sports_identity_media
    monkeypatch.setattr(sports_identity_media, 'participant_image', lambda *_a, **_kw: None)
    signal = editorial_tennis()
    card = build_wettfinder_card(signal, now=NOW)
    assert with_identity_images(card, signal, enabled=True) is card


@pytest.mark.parametrize('sport, kind, provider, team_ids', [
    ('Basketball', 'basketball', 'ESPN', ('espn:basketball:team:2', 'espn:basketball:team:13')),
    ('Eishockey', 'ice_hockey', 'NHL', ('nhl:ice_hockey:team:10', 'nhl:ice_hockey:team:6')),
    ('Cricket', 'cricket', 'Cricbuzz', ('2', '4')),
    ('E-Sport', 'esports', 'pandascore', ('1669', '134536')),
])
def test_team_logos_use_existing_sport_provider_ids_without_mutating_card(monkeypatch, sport, kind, provider, team_ids):
    calls = recorder(monkeypatch)
    signal = SimpleNamespace(competition='NBA' if sport == 'Basketball' else None, context_evidence=None)
    card = replace(build_wettfinder_card(editorial_tennis(), now=NOW), sport=sport,
        fixture_source=provider, competitor_a_id=team_ids[0], competitor_b_id=team_ids[1])
    before = deepcopy(vars(card))
    decorated = with_identity_images(card, signal, enabled=True)
    assert [call[0] for call in calls] == [kind, kind]
    assert [call[2]['team_id'] for call in calls] == list(team_ids)
    assert all(call[2]['fixture_source'] == provider for call in calls)
    assert decorated.home_image is not None and decorated.away_image is not None
    assert vars(card) == before
    assert {k: v for k, v in vars(decorated).items() if '_image' not in k} == {
        k: v for k, v in before.items() if '_image' not in k}


def test_fallback_bridge_is_ui_only_static_and_has_no_fetch_or_storage(monkeypatch):
    import streamlit.components.v1 as components
    import streamlit.runtime.scriptrunner as runtime
    from wettfinder_identity import install_image_fallback
    calls = []
    monkeypatch.setattr(components, 'html', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(runtime, 'get_script_run_ctx', lambda **_kw: None)
    install_image_fallback()
    assert calls == []
    monkeypatch.setattr(runtime, 'get_script_run_ctx', lambda **_kw: object())
    install_image_fallback()
    script = calls[0][0][0]
    assert calls[0][1] == {'height': 0, 'scrolling': False}
    assert "attributeFilter:['src']" in script
    assert "doc.addEventListener('error', onImage, true)" in script
    assert "image.complete && image.naturalWidth > 0" in script
    assert "'.se-shield-image img'" in script
    assert "previous.version === 1" in script
    for forbidden in ('fetch(', 'XMLHttpRequest', 'localStorage', 'sessionStorage', 'cookie', 'https://'):
        assert forbidden not in script
