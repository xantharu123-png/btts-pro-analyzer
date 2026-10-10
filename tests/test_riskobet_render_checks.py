"""The render clock and manual display price cannot create or erase check proof."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

import riskobet_ui as ui
from riskobet_domain import ContextState, FactorEvidence, FactorRole
from riskobet_surface import RiskBetPriceOverlay, build_riskobet_card, compose_riskobet_catalog
from test_riskobet_ui import MODELED, START, RecordingStreamlit, _bundle


NOW = MODELED + timedelta(minutes=10)


def football_bundle(*, state=ContextState.FRESH, expired=None, missing=None):
    snapshot, candidate = _bundle("render-check")
    facts = tuple(FactorEvidence(
        factor_key=f"football_context_0_{section}", summary=f"{section}: checked",
        source="api-football-context", observed_at=MODELED, imported_at=MODELED,
        fresh_until=(NOW - timedelta(seconds=1) if section == expired
                     else MODELED + timedelta(minutes=75)), role=FactorRole.DISPLAY_ONLY,
    ) for section in ("h2h", "injuries", "weather", "lineups") if section != missing)
    # An unrelated customer-display observation is not a qualification check.
    old_display = FactorEvidence(factor_key="customer_recent_home", summary="Last results",
        source="customer-results", observed_at=MODELED - timedelta(days=2),
        imported_at=MODELED, fresh_until=MODELED, role=FactorRole.DISPLAY_ONLY)
    snapshot = replace(snapshot, input_cutoff_at=MODELED,
        factors=(*(f for f in snapshot.factors if f.role is FactorRole.MODEL), *facts, old_display))
    return snapshot, replace(candidate, snapshot_id=snapshot.snapshot_id, context_state=state)


def current_price(candidate):
    return RiskBetPriceOverlay(candidate_id=candidate.candidate_id, status="AVAILABLE",
        observed_odds=2.2, observed_at=MODELED.isoformat(), fetched_at=NOW.isoformat(),
        checked_at=NOW.isoformat(), price_check_current=True)


@pytest.mark.parametrize("section", ["h2h", "injuries", "weather"])
def test_stored_fresh_context_expires_at_render_without_changing_candidate(section):
    snapshot, candidate = football_bundle(expired=section)
    before = deepcopy(candidate.to_dict()), deepcopy(snapshot.to_dict())
    card = build_riskobet_card(candidate, current_price(candidate), snapshot=snapshot, now=NOW)
    catalog = compose_riskobet_catalog([card])
    assert catalog.featured == () and catalog.additional == (card,)
    assert (candidate.to_dict(), snapshot.to_dict()) == before
    assert card.model_probability == candidate.model_probability


def test_unrelated_expired_display_fact_does_not_cancel_current_checks():
    snapshot, candidate = football_bundle()
    card = build_riskobet_card(candidate, current_price(candidate), snapshot=snapshot, now=NOW)
    assert compose_riskobet_catalog([card]).featured == (card,)


@pytest.mark.parametrize("change", ["unknown_snapshot", "foreign_event", "future_model",
                                    "future_check", "missing_weather"])
def test_context_requires_exact_current_snapshot_proof(change):
    snapshot, candidate = football_bundle(missing="weather" if change == "missing_weather" else None)
    if change == "unknown_snapshot":
        snapshot = None
    elif change == "foreign_event":
        snapshot = replace(snapshot, event_key="other-event")
    elif change == "future_model":
        future = NOW + timedelta(minutes=1)
        snapshot = replace(snapshot, modeled_at=future)
        candidate = replace(candidate, snapshot_id=snapshot.snapshot_id)
    elif change == "future_check":
        future = NOW + timedelta(minutes=1)
        factors = tuple(replace(factor, observed_at=future, imported_at=future)
            if factor.factor_key.startswith("football_context_") else factor
            for factor in snapshot.factors)
        snapshot = replace(snapshot, modeled_at=future, input_cutoff_at=future, factors=factors)
        candidate = replace(candidate, snapshot_id=snapshot.snapshot_id)
    card = build_riskobet_card(candidate, current_price(candidate), snapshot=snapshot, now=NOW)
    assert compose_riskobet_catalog([card]).featured == ()


def fake_render(monkeypatch, *, manual=None, expired=None):
    snapshot, candidate = football_bundle(expired=expired)
    price = current_price(candidate)
    view = ui.RiskBetView(run_id="fake-run", status="COMPLETE", started_at=MODELED,
        completed_at=MODELED, candidates=(candidate,), cards=(),
        snapshots={snapshot.snapshot_id: snapshot})
    recorder = RecordingStreamlit()
    calls = {}
    monkeypatch.setattr(ui, "st", recorder)
    monkeypatch.setattr(ui, "load_riskobet_view", lambda _path: view)
    monkeypatch.setattr(ui, "_stored_manual_quote", lambda _candidate: manual)

    def overlay_loader(candidates, snapshots, *, now=None):
        calls["price_now"] = now
        return {candidate.candidate_id: price}

    monkeypatch.setattr(ui, "load_shared_price_overlays", overlay_loader)
    monkeypatch.setattr(ui, "_render_featured", lambda cards, *_: calls.update(featured=cards))
    monkeypatch.setattr(ui, "_render_additional", lambda cards, *_: calls.update(additional=cards))
    import tip_publication
    monkeypatch.setattr(tip_publication, "record_riskobet_catalog",
        lambda *args, **kwargs: calls.update(publication=kwargs))
    ui.render_riskobet(now=NOW)
    return candidate, price, calls


@pytest.mark.parametrize("manual", [None, 1.8, 3.2])
def test_manual_display_quote_preserves_actual_provider_coverage(monkeypatch, manual):
    candidate, overlay, calls = fake_render(monkeypatch, manual=manual)
    assert len(calls["featured"]) == 1
    card = calls["featured"][0]
    assert card.price_check_current is True
    assert card.observed_odds == (overlay.observed_odds if manual is None else manual)
    assert card.price_observed_at == (overlay.observed_at if manual is None else None)
    assert card.model_probability == candidate.model_probability
    assert overlay.checked_at == NOW.isoformat()


def test_one_render_clock_reaches_price_and_context_and_publication(monkeypatch):
    _, _, calls = fake_render(monkeypatch, expired="weather")
    assert calls["price_now"] == NOW
    assert calls["publication"]["as_of"] == NOW
    assert calls["featured"] == () and len(calls["additional"]) == 1


def typed_context():
    from test_highlight_context_checks import row
    context = deepcopy(row()["context"])
    for check in context.values():
        if isinstance(check, dict) and "checked_at" in check:
            check["checked_at"] = MODELED.isoformat()
    context["checked_at"] = MODELED.isoformat()
    return context


def published_bundle(context, *, offsets=None, missing_first=False, cutoff_delta=None):
    from riskobet_candidates import football_risk_bundle, select_football_risk_sources
    from test_riskobet_candidates import football_pool, MODELED_AT
    pool = football_pool(context=context)
    # Keep the public fixture's immutable event/model clock contract.
    context = deepcopy(context)
    observation_time = MODELED_AT if cutoff_delta is None else MODELED_AT + cutoff_delta - timedelta(minutes=5)
    for check in context.values():
        if isinstance(check, dict) and "checked_at" in check:
            check["checked_at"] = observation_time.isoformat()
    context["checked_at"] = observation_time.isoformat()
    for axis, offset in (offsets or {}).items():
        context[axis]["checked_at"] = (MODELED_AT + offset).isoformat()
    for item in pool:
        item.context = context
    selected = select_football_risk_sources(pool)
    if missing_first:
        selected[0].context = {}
    return football_risk_bundle(selected,
        modeled_at=MODELED_AT, source_pool=pool,
        input_cutoff_at=None if cutoff_delta is None else MODELED_AT + cutoff_delta), MODELED_AT


def test_new_pending_lineup_has_typed_bound_checks_and_can_be_top():
    result, current = published_bundle(typed_context())
    candidate = result.candidates[0]
    assert candidate.context_state is ContextState.PARTIAL
    receipts = [factor for factor in result.snapshot.factors
                if factor.factor_key.startswith("football_highlight_context_checks_")]
    assert receipts and all(factor.coverage == 1.0 for factor in receipts)
    assert all(factor.observed_at == current for factor in receipts)
    card = build_riskobet_card(candidate, current_price(candidate),
        snapshot=result.snapshot, now=current)
    assert compose_riskobet_catalog([card]).featured == (card,)
    assert all(ui._customer_factor_detail(factor) == "" for factor in receipts)


@pytest.mark.parametrize("change", ["missing", "unavailable", "blocked", "old", "future",
                                    "veto", "conflicting"])
def test_new_partial_receipt_never_converts_missing_or_adverse_check_into_top(change):
    context = typed_context()
    if change == "missing":
        context.pop("weather")
    elif change == "unavailable":
        context["injuries"]["availability"] = "not_covered"
    elif change == "blocked":
        context["lineups"]["status"] = "blocked"
    elif change == "veto":
        context["weather"]["veto_applied"] = True
    elif change == "conflicting":
        context["conflicting"] = True
    result, current = published_bundle(context)
    if change in {"old", "future"}:
        # The written proof expires honestly; never reset it at render time.
        current += timedelta(minutes=76) if change == "old" else -timedelta(seconds=1)
    candidate = result.candidates[0]
    card = build_riskobet_card(candidate, current_price(candidate),
        snapshot=result.snapshot, now=current)
    assert compose_riskobet_catalog([card]).featured == ()


def test_legacy_partial_summary_cannot_be_interpreted_as_successful_typed_checks():
    snapshot, candidate = football_bundle(state=ContextState.PARTIAL)
    card = build_riskobet_card(candidate, current_price(candidate), snapshot=snapshot, now=NOW)
    assert compose_riskobet_catalog([card]).featured == ()


def test_receipt_keeps_oldest_actual_axis_clock_and_expires_at_original_deadline():
    result, current = published_bundle(typed_context(), offsets={"weather": -timedelta(minutes=30)})
    receipts = [factor for factor in result.snapshot.factors
                if factor.factor_key.startswith("football_highlight_context_checks_")]
    assert receipts and all(f.observed_at == current-timedelta(minutes=30) for f in receipts)
    assert all(f.fresh_until == current+timedelta(minutes=45) for f in receipts)
    candidate = result.candidates[0]
    card = build_riskobet_card(candidate, current_price(candidate),
        snapshot=result.snapshot, now=current+timedelta(minutes=45))
    assert compose_riskobet_catalog([card]).featured == (card,)
    expired = build_riskobet_card(candidate, current_price(candidate),
        snapshot=result.snapshot, now=current+timedelta(minutes=45, seconds=1))
    assert compose_riskobet_catalog([expired]).featured == ()


@pytest.mark.parametrize("offset", [timedelta(minutes=-76), timedelta(seconds=1)])
def test_receipt_writer_cannot_refresh_an_old_or_future_actual_check(offset):
    result, _ = published_bundle(typed_context(), offsets={"weather": offset})
    assert not any(f.factor_key.startswith("football_highlight_context_checks_")
                   and f.coverage == 1.0 for f in result.snapshot.factors)


def test_receipt_schema_changes_input_hash_not_model_numbers(monkeypatch):
    import riskobet_candidates as adapter
    first, _ = published_bundle(typed_context())
    monkeypatch.setattr(adapter, "FOOTBALL_HIGHLIGHT_CHECK_SCHEMA", "future-check-schema")
    next_revision, _ = published_bundle(typed_context())
    assert first.snapshot.input_hash != next_revision.snapshot.input_hash
    assert first.snapshot.snapshot_id != next_revision.snapshot.snapshot_id
    assert [(c.model_probability, c.selection_key, c.market_key) for c in first.candidates] == [
        (c.model_probability, c.selection_key, c.market_key) for c in next_revision.candidates]


def test_explicit_blocked_lineup_cannot_disappear_without_a_clock():
    from forecast_analysis import football_context_highlight_reason
    context = typed_context()
    context["lineups"] = {"status": "blocked"}
    assert football_context_highlight_reason(context, now=NOW)


def test_other_selected_markets_context_cannot_certify_an_unchecked_direction_anchor():
    result, current = published_bundle(typed_context(), missing_first=True)
    cards = tuple(build_riskobet_card(candidate, current_price(candidate),
        snapshot=result.snapshot, now=current) for candidate in result.candidates)
    assert cards and not any(card.context_check_current for card in cards)
    assert compose_riskobet_catalog(cards).featured == ()


def test_new_fresh_flag_with_incomplete_typed_facts_cannot_use_legacy_fallback():
    context = typed_context()
    context["release_context_complete"] = True
    context["lineups"]["status"] = "passed"
    context["weather"].pop("availability")
    result, current = published_bundle(context)
    candidate = result.candidates[0]
    assert candidate.context_state is ContextState.FRESH
    card = build_riskobet_card(candidate, current_price(candidate),
        snapshot=result.snapshot, now=current)
    assert compose_riskobet_catalog([card]).featured == ()


def test_missing_context_with_earlier_input_cutoff_keeps_catalog_without_fake_check():
    result, current = published_bundle(typed_context(), missing_first=True,
        cutoff_delta=-timedelta(minutes=5))
    negative = [f for f in result.snapshot.factors if f.factor_key.startswith(
        "football_highlight_context_checks_") and f.coverage == 0.0]
    assert negative and all(f.observed_at <= result.snapshot.input_cutoff_at for f in negative)
    cards = tuple(build_riskobet_card(candidate, current_price(candidate),
        snapshot=result.snapshot, now=current) for candidate in result.candidates)
    catalog = compose_riskobet_catalog(cards)
    assert catalog.featured == () and catalog.additional


def test_existing_tennis_workload_check_clock_expires_but_unrelated_display_does_not():
    snapshot, candidate = _bundle("tennis-current-workload", sport="tennis")
    relevant = FactorEvidence(factor_key="tennis_workload_a_0", summary="Last match workload",
        source="tennis-shadow-observed-results", observed_at=MODELED-timedelta(minutes=5),
        imported_at=MODELED, fresh_until=NOW-timedelta(seconds=1), role=FactorRole.DISPLAY_ONLY)
    snapshot = replace(snapshot, factors=(*snapshot.factors, relevant))
    candidate = replace(candidate, snapshot_id=snapshot.snapshot_id)
    card = build_riskobet_card(candidate, current_price(candidate), snapshot=snapshot, now=NOW)
    assert compose_riskobet_catalog([card]).featured == ()
    unrelated = replace(relevant, factor_key="customer_recent_a", source="customer-results")
    snapshot = replace(snapshot, factors=(*snapshot.factors[:-1], unrelated))
    candidate = replace(candidate, snapshot_id=snapshot.snapshot_id)
    card = build_riskobet_card(candidate, current_price(candidate), snapshot=snapshot, now=NOW)
    assert compose_riskobet_catalog([card]).featured == (card,)
