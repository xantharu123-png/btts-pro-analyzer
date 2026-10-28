"""Public proposals require exact real offers; model inventories remain intact."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import importlib
import json
import sqlite3

import pytest

from daily3_selection import daily3_choices
from test_daily3_selection import NOW, football
from test_publication_odds_floor import priced, visible


# Under the floor an expired, slightly future or unidentified quote leaves the tip unpriced and visible.
@pytest.mark.parametrize("problem", ["missing", "foreign_event", "foreign_market",
                                     *(pytest.param(name, marks=pytest.mark.price_policy("gate")) for name in ("expired", "future", "unidentified"))])
def test_public_consumers_withhold_unproved_offers_without_erasing_model(problem):
    signal = priced(football(), (1.50,) * 3)
    quote = deepcopy(signal.reference_quote)
    quote.pop("executable_quote", None)
    if problem == "missing":
        quote = None
    elif problem == "foreign_event":
        quote["fixture_id"] = 999
    elif problem == "foreign_market":
        quote["market_key"] = "RESULT_AWAY"
    elif problem == "expired":
        quote["fetched_at"] = (NOW - timedelta(days=2)).isoformat()
    else:
        if problem == "future":
            quote["fetched_at"] = quote["quoted_at"] = (NOW + timedelta(seconds=1)).isoformat()
        for point in quote["points"]:
            if problem == "future":
                point["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
            else:
                point["bookmaker_id"] = None
    signal = replace(signal, reference_quote=quote)
    before = deepcopy(vars(signal))
    assert visible([signal]) == ()
    assert daily3_choices([signal], now=NOW) == ()
    assert vars(signal) == before


@pytest.mark.price_policy("gate")
def test_public_floor_uses_one_exact_offer_and_keeps_last_known_clock():
    module = importlib.import_module("quote_publication")
    signal = priced(football(), (1.10, 1.12, 1.20))
    quote = deepcopy(signal.reference_quote)
    quote.pop("executable_quote", None)
    old = (NOW - timedelta(hours=3)).isoformat()
    quote["fetched_at"] = old
    quote["quoted_at"] = old
    for point in quote["points"]:
        point["observed_at"] = old
    admitted = module.publication_quote(quote, candidate=signal, now=NOW)
    assert admitted is not None
    assert max(point.odds for point in admitted.points) == 1.20
    assert admitted.fetched_at == old
    assert admitted.points[-1].observed_at == old


def test_unpriced_primary_does_not_promote_opposing_priced_outcome():
    primary = football(probability=.8)
    opposing = priced(football(key="RESULT_AWAY", probability=.2), (5.0,) * 3)
    assert visible([primary, opposing]) == ()
    assert daily3_choices([primary, opposing], now=NOW) == ()


def test_manual_football_filters_unknown_and_known_low_only_after_coherence():
    from alternative_markets_tab_extended import _filter_manual_market_rows
    from manual_search_filters import SearchFilters
    from wettfinder_surface import wettfinder_quote_binding_candidate
    from types import SimpleNamespace
    signal = priced(football(), (1.50,) * 3)
    row = SimpleNamespace(**wettfinder_quote_binding_candidate(signal))  # carries the probability since 25.10.2026
    result, total = _filter_manual_market_rows([row], {}, search_filters=SearchFilters(), now=NOW)
    assert result == [] and total == 0
    result, total = _filter_manual_market_rows([row], {signal.candidate_id: signal.reference_quote},
        search_filters=SearchFilters(), now=NOW)
    assert result == [row] and total == 1


def test_unpriced_live_is_analysis_only_without_a_tip_save_action(monkeypatch):
    import bet_finder_ui as ui
    from test_bet_finder_ui import _candidate
    shown = []
    for method in ("subheader", "write", "caption", "info"):
        monkeypatch.setattr(ui.st, method, lambda value, **_kw: shown.append(str(value)))
    monkeypatch.setattr(ui, "render_tip_bookmark", lambda *_a, **_kw: pytest.fail("unpriced public tip action"))
    ui.render_model_selection(_candidate(), save_source="Live", analysis_only=True)
    assert "Analyse" in " ".join(shown)
    assert "65.0 %" in " ".join(shown)


def test_riskobet_sidecar_is_read_without_a_normal_model_row(tmp_path):
    from riskobet_prices import load_shared_price_overlays
    from riskobet_surface import build_riskobet_card, compose_riskobet_catalog
    from test_shared_quote_observations import risk_price_fixture
    from test_wettfinder_surface import NOW as RISK_NOW
    row, candidate = risk_price_fixture(1.50)
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps({"model_candidates": [], "riskobet_price_observations": [row]}), encoding="utf-8")
    overlays = load_shared_price_overlays([candidate], now=RISK_NOW, path=path)
    assert candidate.candidate_id in overlays
    card = build_riskobet_card(candidate, overlays[candidate.candidate_id], now=RISK_NOW)
    assert len(compose_riskobet_catalog([card]).cards) == 1
    assert not compose_riskobet_catalog([build_riskobet_card(candidate, now=RISK_NOW)]).cards


def test_new_low_saved_bet_is_rejected_but_legacy_retry_remains_readable(tmp_path):
    from test_tip_store import _decision
    from tip_store import TipStore
    store = TipStore(tmp_path / "tips.db")
    normal = _decision(2.0)
    low = replace(normal, quoted_odds=1.12)
    with pytest.raises(ValueError, match="1,20"):
        store.save_decision(low, source="Test")
    saved = store.save_decision(normal, source="Test")
    with sqlite3.connect(store.db_path) as connection:
        connection.execute("UPDATE saved_tips SET quoted_odds=1.12 WHERE id=?", (saved.id,))
    before = store.list_tips()
    retried = store.save_decision(low, source="Test")
    assert retried.quoted_odds == 1.12
    assert store.list_tips() == before
    store.settle(retried.id, "WON")
    assert store.list_tips(active=False)[0].quoted_odds == 1.12


def test_legacy_prematch_reuses_only_same_native_event_market_and_start():
    module = importlib.import_module("quote_publication")
    helper = getattr(module, "native_football_publication_offer", None)
    assert callable(helper), "legacy prematch must pass a real exact cached offer"
    signal = priced(football(key="BTTS_YES"), (1.50,) * 3)
    args = dict(fixture_id=signal.fixture_id, scheduled_start=signal.scheduled_start,
                market_key="BTTS_YES", selection="Ja", home_team=signal.home_team,
                away_team=signal.away_team, now=NOW)
    quote, binding = helper([signal], **args)
    assert quote.best_odds == 1.50 and binding["fixture_id"] == 1
    assert helper([signal], **(args | {"fixture_id": 2})) == (None, None)
    assert helper([signal], **(args | {"market_key": "BTTS_NO", "selection": "Nein"})) == (None, None)
    assert helper([signal], **(args | {"scheduled_start": (NOW+timedelta(hours=4)).isoformat()})) == (None, None)


@pytest.mark.parametrize("problem", ["stale_high", "future_high"])
def test_admission_never_disagrees_with_the_displayed_native_point(problem):
    module = importlib.import_module("quote_publication")
    from wettfinder_surface import build_wettfinder_card
    signal = priced(football(), (1.12, 1.12, 1.30))
    quote = deepcopy(signal.reference_quote)
    quote.pop("executable_quote", None)
    quote["points"][-1]["observed_at"] = (
        NOW-timedelta(hours=3) if problem == "stale_high" else NOW+timedelta(seconds=1)).isoformat()
    if problem == "future_high":
        quote["quoted_at"] = quote["points"][-1]["observed_at"]
    signal = replace(signal, reference_quote=quote)
    assert module.publication_quote(quote, candidate=signal, now=NOW) is None
    assert build_wettfinder_card(signal, quote, now=NOW).quote_floor_excluded


def test_riskobet_sidecar_low_offer_precedes_older_model_quote_and_is_bounded(tmp_path):
    from riskobet_prices import load_shared_price_overlays
    from test_shared_quote_observations import risk_price_fixture
    from test_wettfinder_surface import NOW as RISK_NOW
    high, candidate = risk_price_fixture(1.50)
    low, _ = risk_price_fixture(1.12)
    path = tmp_path / "wettfinder_latest.json"
    path.write_text(json.dumps({"model_candidates": [high], "riskobet_price_observations": [low]}), encoding="utf-8")
    overlays = load_shared_price_overlays([candidate], now=RISK_NOW, path=path)
    assert overlays[candidate.candidate_id].observed_odds == 1.12
    assert not overlays[candidate.candidate_id].publication_eligible
    from riskobet_prices import bounded_riskobet_price_observations
    assert bounded_riskobet_price_observations([low]*3001, now=RISK_NOW) == []


def test_display_cannot_present_a_future_high_offer_when_current_offer_passes(monkeypatch):
    from wettfinder_surface import build_wettfinder_card
    signal = priced(football(), (1.25, 1.25, 1.50))
    quote = deepcopy(signal.reference_quote)
    quote.pop("executable_quote", None)
    quote['points'][-1]['observed_at'] = quote['quoted_at'] = (NOW+timedelta(seconds=1)).isoformat()
    signal = replace(signal, reference_quote=quote)
    card = build_wettfinder_card(signal, quote, now=NOW)
    assert not card.quote_floor_excluded
    assert card.observed_odds == 1.25
    assert max(point.odds for point in card.reference_quote.points) == 1.25


def test_generic_price_renderer_keeps_unknown_quote_outside_public_tip_markup(monkeypatch):
    import bet_finder_ui as ui
    from test_bet_finder_ui import _candidate
    messages = []
    monkeypatch.setattr(ui.st, 'caption', lambda value: messages.append(value))
    monkeypatch.setattr(ui.st, 'subheader', lambda *_a: pytest.fail('unpriced public tip header'))
    assert ui.render_price_decision(_candidate(), key='unknown-public') is None
    assert messages


def test_riskobet_display_uses_the_same_clock_checked_offer_as_admission():
    from riskobet_prices import shared_price_overlays
    from test_shared_quote_observations import risk_price_fixture
    from test_wettfinder_surface import NOW as RISK_NOW
    row, candidate = risk_price_fixture(1.50)
    quote = deepcopy(row['reference_quote'])
    quote.pop('executable_quote', None)
    quote['best_odds'] = quote['points'][-1]['odds'] = 2.0
    quote['points'][-1]['observed_at'] = quote['quoted_at'] = (RISK_NOW+timedelta(seconds=1)).isoformat()
    overlay = shared_price_overlays([candidate], [dict(row, reference_quote=quote)], now=RISK_NOW)[candidate.candidate_id]
    assert overlay.publication_eligible
    assert overlay.observed_odds == 1.50
    assert overlay.observed_at == RISK_NOW.isoformat()


def test_price_details_do_not_reintroduce_a_discarded_future_offer(monkeypatch):
    import bet_finder_ui as ui
    from test_bet_finder_ui import _candidate
    from types import SimpleNamespace
    signal = priced(football(), (1.25, 1.25, 1.50))
    quote = deepcopy(signal.reference_quote)
    quote.pop('executable_quote', None)
    quote['points'][-1]['observed_at'] = quote['quoted_at'] = (NOW+timedelta(seconds=1)).isoformat()
    shown = []
    class Clock(ui.datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(ui, 'datetime', Clock)
    monkeypatch.setattr(ui, 'st', SimpleNamespace(session_state={}, subheader=lambda *_a: None,
        write=lambda *_a: None, caption=lambda *_a: None))
    monkeypatch.setattr(ui, '_render_reference_price', lambda candidate, evaluation: shown.append(evaluation.quote))
    evaluation = ui.evaluate_reference_price(_candidate(), quote, bankroll=100,
        reference_binding_candidate=signal, now=NOW)
    ui.render_price_decision(_candidate(), key='current-proof-only', reference_quote=quote,
        reference_binding_candidate=signal, presentation='fixture_first',
        precomputed_reference_evaluation=evaluation)
    assert len(shown) == 1
    assert max(point.odds for point in shown[0].points) == 1.25


def test_filtered_price_subset_does_not_erase_precomputed_candidate_mismatch(monkeypatch):
    import bet_finder_ui as ui
    from test_bet_finder_ui import _candidate
    from types import SimpleNamespace
    signal = priced(football(), (1.25, 1.25, 1.50))
    quote = deepcopy(signal.reference_quote)
    quote.pop('executable_quote', None)
    quote['points'][-1]['observed_at'] = quote['quoted_at'] = (NOW+timedelta(seconds=1)).isoformat()
    evaluation = ui.evaluate_reference_price(_candidate(), quote, bankroll=100,
        reference_binding_candidate=signal, now=NOW)
    monkeypatch.setattr(ui, 'st', SimpleNamespace(session_state={}, caption=lambda *_a: None))
    with pytest.raises(ValueError, match='candidate'):
        ui.render_price_decision(replace(_candidate(), event_key='different-model'), key='foreign-precomputed',
            reference_quote=quote, reference_binding_candidate=signal, presentation='compact',
            precomputed_reference_evaluation=evaluation)
