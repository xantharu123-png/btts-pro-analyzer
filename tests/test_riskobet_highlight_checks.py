"""Top scenarios need real context and price checks, after price-blind coherence."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json

import pytest

from riskobet_domain import ContextState, EvidenceStage
from riskobet_prices import load_shared_price_overlays, shared_price_overlays
from riskobet_surface import build_riskobet_card, compose_riskobet_catalog
from test_riskobet_tennis_prices import NOW, _fixture
from test_shared_quote_observations import risk_price_fixture
from test_riskobet_ui import _bundle


def checked_card(candidate, price=None, *, now=NOW):
    snapshot, _ = _bundle('context-proof', sport=candidate.sport)
    factor = replace(snapshot.factors[0], observed_at=now-timedelta(minutes=20),
        imported_at=now-timedelta(minutes=10), fresh_until=candidate.starts_at)
    snapshot = replace(snapshot, event_key=candidate.event_key, sport=candidate.sport,
        competition=candidate.competition, event_label=candidate.event_label,
        starts_at=candidate.starts_at, modeled_at=now-timedelta(minutes=10),
        input_cutoff_at=now-timedelta(minutes=10), factors=(factor,))
    if candidate.sport == 'football':
        from riskobet_domain import FactorEvidence, FactorRole
        factors = tuple(FactorEvidence(factor_key=f'football_context_0_{axis}',
            summary='Checked', source='api-football-context', observed_at=snapshot.modeled_at,
            imported_at=snapshot.modeled_at, fresh_until=candidate.starts_at,
            role=FactorRole.DISPLAY_ONLY) for axis in ('h2h', 'injuries', 'weather'))
        snapshot = replace(snapshot, factors=(factor, *factors))
    bound = replace(candidate, snapshot_id=snapshot.snapshot_id)
    return build_riskobet_card(bound, price, snapshot=snapshot, now=now)


def current_candidate():
    row, candidate = _fixture()
    return row, replace(candidate, context_state=ContextState.FRESH, missing_core_data=())


def catalog_for(row, candidate):
    overlays = shared_price_overlays([candidate], [row], now=NOW)
    card = checked_card(candidate, overlays.get(candidate.candidate_id))
    return card, compose_riskobet_catalog([card])


@pytest.mark.parametrize("state", [ContextState.PARTIAL, ContextState.STALE, ContextState.OPEN])
def test_unfinished_context_is_additional_not_top_even_with_exact_price(state):
    row, candidate = current_candidate()
    candidate = replace(candidate, context_state=state)
    card, catalog = catalog_for(row, candidate)
    assert catalog.featured == () and catalog.additional == (card,)
    assert card.model_probability == candidate.model_probability
    assert card.pros == candidate.pros and card.cons == candidate.cons


@pytest.mark.parametrize("change", [
    {"stage": EvidenceStage.RESEARCH}, {"missing_core_data": ("Aktuelle Spielerliste",)},
    {"stage": EvidenceStage.RESEARCH, "model_probability": None,
     "cautious_probability": None, "missing_core_data": ("Matchhistorie",)},
])
def test_research_or_missing_core_evidence_never_fills_top_slots(change):
    row, candidate = current_candidate()
    candidate = replace(candidate, **change)
    card, catalog = catalog_for(row, candidate)
    assert catalog.featured == () and catalog.additional == (card,)


def test_never_checked_unknown_price_stays_additional():
    _, candidate = current_candidate()
    card = checked_card(candidate)
    catalog = compose_riskobet_catalog([card])
    assert catalog.featured == () and catalog.additional == (card,)
    assert card.observed_odds is None


@pytest.mark.parametrize("age", [timedelta(), timedelta(hours=3), timedelta(hours=24)])
def test_real_exact_price_check_can_highlight_with_original_clocks(age):
    row, candidate = _fixture(age=age)
    candidate = replace(candidate, context_state=ContextState.FRESH, missing_core_data=())
    before_row, before_candidate = deepcopy(row), candidate.to_dict()
    card, catalog = catalog_for(row, candidate)
    assert catalog.featured == (card,) and catalog.additional == ()
    assert card.price_observed_at == (NOW - age).isoformat()
    assert row == before_row and candidate.to_dict() == before_candidate


@pytest.mark.parametrize("clock", ["fetched_at", "point"])
def test_future_price_clock_is_not_a_completed_check(clock):
    row, candidate = current_candidate()
    future = (NOW + timedelta(seconds=30)).isoformat()
    if clock == "fetched_at":
        row["reference_quote"]["fetched_at"] = future
    else:
        row["reference_quote"]["points"][0]["observed_at"] = future
        row["reference_quote"]["quoted_at"] = future
    card, catalog = catalog_for(row, candidate)
    assert catalog.featured == () and catalog.additional == (card,)


def test_price_check_older_than_24_hours_is_not_current():
    row, candidate = _fixture(age=timedelta(hours=24, seconds=1))
    candidate = replace(candidate, context_state=ContextState.FRESH, missing_core_data=())
    card, catalog = catalog_for(row, candidate)
    assert catalog.featured == () and catalog.additional == (card,)


def test_unchecked_anchor_cannot_be_replaced_by_checked_opposite_winner():
    row, first = current_candidate()
    second = replace(first, selection_key="away", selection_label=row["competitor_b"],
        settlement_contract="riskobet-settlement-v1:tennis:match_winner:away",
        model_probability=.64, cautious_probability=.54)
    other_row, _ = _fixture(selected=row["competitor_b"])
    overlay = shared_price_overlays([second], [other_row], now=NOW)[second.candidate_id]
    anchor = checked_card(first)
    opposite = checked_card(second, overlay)
    before = deepcopy(first.to_dict()), deepcopy(second.to_dict())
    catalog = compose_riskobet_catalog([anchor, opposite])
    # Filtering price coverage before coherence would feature the opposing side.
    assert catalog.featured == () and catalog.additional == (anchor,)
    assert (first.to_dict(), second.to_dict()) == before


def attempted_row():
    row, candidate = current_candidate()
    row.pop("reference_quote")
    row.update(key="tennis-gea-zhang-A", modeled_at=(NOW - timedelta(minutes=10)).isoformat())
    return row, candidate


def test_actual_exact_attempt_can_return_no_quote_without_removing_top_eligibility():
    row, candidate = attempted_row()
    attempts = {row["key"]: NOW.isoformat()}
    overlays = shared_price_overlays([candidate], [row], now=NOW, price_check_attempts=attempts)
    card = checked_card(candidate, overlays.get(candidate.candidate_id))
    assert compose_riskobet_catalog([card]).featured == (card,)
    assert card.observed_odds is None and card.price_code == "UNAVAILABLE"


@pytest.mark.parametrize("field,bad", [
    ("provider_event_id", "OTHER"), ("fixture_source", "OTHER"),
    ("scheduled_start", "2030-09-30T09:00:01+00:00"),
    ("competitor_a", "Other Player"), ("selected_competitor", "Zhang Zhizhen"),
    ("market_key", "TOTAL_OVER_2_5"), ("modeled_at", None), ("key", "OTHER"),
    ("provider_event_id", "x" * 241), ("fixture_source", "x" * 121),
    ("sport", "Basketball"),
])
def test_failed_price_attempt_never_crosses_native_event_start_or_selected_market(field, bad):
    row, candidate = attempted_row()
    attempts = {row["key"]: NOW.isoformat()}
    row[field] = bad
    overlays = shared_price_overlays([candidate], [row], now=NOW, price_check_attempts=attempts)
    card = checked_card(candidate, overlays.get(candidate.candidate_id))
    catalog = compose_riskobet_catalog([card])
    assert catalog.featured == () and catalog.additional == (card,)


@pytest.mark.parametrize("checked", [
    "2030-09-30T08:00:01+00:00", "2030-09-29T07:59:59+00:00",
    "2030-09-30T07:49:59+00:00", "2030-09-30T08:00:00", True, None,
])
def test_attempt_requires_original_current_aware_clock_after_the_bound_model(checked):
    row, candidate = attempted_row()
    overlays = shared_price_overlays([candidate], [row], now=NOW,
        price_check_attempts={row["key"]: checked})
    card = checked_card(candidate, overlays.get(candidate.candidate_id))
    assert compose_riskobet_catalog([card]).featured == ()


@pytest.mark.parametrize("change", [None,
    {"fixture_id": 999}, {"scheduled_start": "2030-01-01T15:00:01+00:00"},
    {"market_key": "DC_X2"}, {"home_team": "Other"}, {"source": "other"},
    {"sport": "Tennis"},
])
def test_football_missing_quote_attempt_requires_exact_native_fixture_start_and_market(change):
    row, candidate = risk_price_fixture(price=1.52)
    current = candidate.starts_at - timedelta(minutes=30)
    row.pop("reference_quote")
    row.update(key="football-price-check", modeled_at=(current - timedelta(minutes=10)).isoformat())
    candidate = replace(candidate, context_state=ContextState.FRESH, missing_core_data=(),
        event_label=f'{row["home_team"]} vs {row["away_team"]}')
    attempts = {row["key"]: current.isoformat()}
    if change:
        row.update(change)
    overlays = shared_price_overlays([candidate], [row], now=current, price_check_attempts=attempts)
    card = checked_card(candidate, overlays.get(candidate.candidate_id), now=current)
    assert bool(compose_riskobet_catalog([card]).featured) is (change is None)
    assert card.observed_odds is None


def test_duplicate_attempt_bindings_cannot_cherry_pick_a_favorable_clock():
    row, candidate = attempted_row()
    other = {**row, "modeled_at": (NOW + timedelta(seconds=1)).isoformat()}
    overlays = shared_price_overlays([candidate], [row, other], now=NOW,
        price_check_attempts={row["key"]: NOW.isoformat()})
    card = checked_card(candidate, overlays.get(candidate.candidate_id))
    assert compose_riskobet_catalog([card]).featured == ()


def test_saved_no_quote_attempt_loads_read_only_with_its_original_clock(tmp_path, monkeypatch):
    import requests

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Price-check reuse cannot fetch a provider')

    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    row, candidate = attempted_row()
    checked = (NOW - timedelta(minutes=1)).isoformat()
    path = tmp_path / 'wettfinder_latest.json'
    path.write_text(json.dumps({'model_candidates': [row],
        'price_check_attempts': {row['key']: checked}}), encoding='utf-8')
    before = path.read_bytes()
    overlay = load_shared_price_overlays([candidate], now=NOW, path=path)[candidate.candidate_id]
    card = checked_card(candidate, overlay)
    assert compose_riskobet_catalog([card]).featured == (card,)
    assert overlay.checked_at == checked and overlay.fetched_at is None
    assert path.read_bytes() == before and tuple(tmp_path.iterdir()) == (path,)
