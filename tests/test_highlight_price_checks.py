"""Price-check admission is downstream of model direction, never a price ranking."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from betting_math import BETTING_POLICY_VERSION
from challenge_engine import MARKET_BY_KEY
from daily3_selection import daily3_choices
from ev_signal_sources import ModelSignal, automated_wettfinder_forecasts
from forecast_analysis import forecast_highlight_reason, project_football_analysis
from forecast_selection import select_consumer_forecasts
from market_consensus import MarketConsensus, QuotePoint, REFERENCE_SOURCE, exact_market_target
from wettfinder_surface import build_wettfinder_card, compose_wettfinder_catalog


NOW = datetime(2030, 1, 1, 7, tzinfo=timezone.utc)


def _signal(market_key="DC_1X", probability=.75, *, modeled_at=NOW):
    spec = MARKET_BY_KEY[market_key]
    row = dict(key=f"81:{market_key}", candidate_id=f"81:{market_key}", fixture_id=81,
        home_id=11, away_id=12, home_team="Alpha", away_team="Beta", market_key=market_key,
        probability=probability, scheduled_start=(NOW+timedelta(hours=3)).isoformat(),
        modeled_at=modeled_at.isoformat(), input_cutoff_at=modeled_at.isoformat(), model_scope="same_competition",
        context={"checked_at": NOW.isoformat(),
            "h2h": {"status": "neutral", "availability": "available", "matches": 0, "checked_at": NOW.isoformat()},
            "weather": {"status": "passed", "availability": "available", "veto_applied": False, "checked_at": NOW.isoformat()},
            "injuries": {"status": "observed", "availability": "available", "coverage_available": True,
                "home_missing": 0, "away_missing": 0, "impact_assessment_complete": True, "checked_at": NOW.isoformat()},
            "lineups": {"status": "pending", "checked_at": NOW.isoformat()}})
    comparison = dict(schema="league-market-comparison-v1", fixture_id=81, home_id=11, away_id=12,
        league_id=39, market_key=market_key, scheduled_start=row["scheduled_start"], prediction_version="test-model-v1",
        validation_prediction_version="test-model-v1", model_skill_supported=True, samples=400, successes=200,
        latest_kickoff=(NOW-timedelta(days=1)).isoformat(), probabilities=[probability, probability-.05, min(.99, probability+.05)])
    evidence = project_football_analysis(row, model_basis={**row, "expected_home_goals": 1.8,
        "expected_away_goals": .9, "venue_samples": [12, 12], "form_samples": [6, 6], "market_comparison": comparison})
    return ModelSignal(key=row["key"], candidate_id=row["candidate_id"], fixture_id=81, label="Alpha vs Beta",
        probability=probability, probability_haircut=.08, evidence_stage="SHADOW", policy_version=BETTING_POLICY_VERSION,
        detail="Synthetic model", source="automated_wettfinder_forecast", sport="Fußball", event_label="Alpha vs Beta",
        market=spec.market, selection=spec.selection, market_key=market_key, home_team="Alpha", away_team="Beta",
        home_team_id=11, away_team_id=12, scheduled_start=row["scheduled_start"], modeled_at=row["modeled_at"],
        input_cutoff_at=row["input_cutoff_at"], model_scope=row["model_scope"], model_version="test-model-v1",
        minimum_odds=1.8, analysis_evidence=evidence)


def _with_attempt(signal, stamp):
    return replace(signal, price_checked_at=stamp)


def _quote(signal, *, fetched_at=NOW, odds=1.9):
    bet_name, value_name = exact_market_target(signal.market_key)
    return MarketConsensus(fixture_id=81, candidate_id=signal.candidate_id, market_key=signal.market_key,
        bet_name=bet_name, value_name=value_name, consensus_odds=odds, conservative_odds=odds,
        lowest_odds=odds, best_odds=odds, bookmaker_count=3, quoted_at=fetched_at.isoformat(),
        fetched_at=fetched_at.isoformat(), source=REFERENCE_SOURCE,
        points=tuple(QuotePoint(f"Book {n}", odds, f"api-football:{n}", fetched_at.isoformat()) for n in range(3)),
        scheduled_start=signal.scheduled_start, event_home="Alpha", event_away="Beta")


def test_never_price_checked_model_stays_visible_but_is_not_featured_or_daily3():
    # Break caught: model eligibility alone qualifies a row for a highlighted placement.
    signal = _signal()
    assert not forecast_highlight_reason(signal, now=NOW)
    card = build_wettfinder_card(signal, now=NOW)
    catalog = compose_wettfinder_catalog([card])
    assert catalog.featured == ()
    assert [item.key for item in catalog.additional] == ["81:DC_1X"]
    assert daily3_choices([signal], now=NOW) == ()
    assert card.model_probability == .75 and card.price_code == "UNAVAILABLE"


@pytest.mark.parametrize("stamp", [None, "invalid", True, "2030-01-01T07:00:00",
    "2030-01-01T07:00:01+00:00", "2030-01-01T06:59:59+00:00"])
def test_invalid_future_or_pre_model_attempt_never_qualifies(stamp):
    # Break caught: a check timestamp is accepted without typing, awareness or revision bounds.
    signal = _with_attempt(_signal(), stamp)
    card = build_wettfinder_card(signal, now=NOW)
    assert compose_wettfinder_catalog([card]).featured == ()
    assert daily3_choices([signal], now=NOW) == ()


def test_actual_unavailable_price_result_can_still_feature_without_inventing_odds():
    # Break caught: no quote is mistaken for no attempt, or UNAVAILABLE is promoted to a playable quote.
    signal = _with_attempt(_signal(), NOW.isoformat())
    card = build_wettfinder_card(signal, now=NOW)
    assert [item.key for item in compose_wettfinder_catalog([card]).featured] == ["81:DC_1X"]
    assert [item.signal.key for item in daily3_choices([signal], now=NOW)] == ["81:DC_1X"]
    assert getattr(card, "price_check_completed", False) is True
    assert card.observed_odds is None and card.reference_quote is None and card.price_code == "UNAVAILABLE"


@pytest.mark.parametrize(("age", "accepted"), [(24, True), (24.0001, False)])
def test_attempt_age_uses_the_original_check_clock(age, accepted):
    # Break caught: an old attempt is refreshed by card building or an inclusive 24h boundary is lost.
    model = _signal(modeled_at=NOW-timedelta(hours=25))
    signal = _with_attempt(model, (NOW-timedelta(hours=age)).isoformat())
    card = build_wettfinder_card(signal, now=NOW)
    assert getattr(card, "price_check_completed", False) is accepted


@pytest.mark.parametrize("bad", ["candidate", "fixture", "market", "future", "before_model", "old"])
def test_foreign_or_invalid_original_quote_cannot_substitute_for_a_price_attempt(bad):
    # Break caught: any present quote substitutes for an exact, current check.
    signal = _signal()
    quote = _quote(signal)
    if bad in {"candidate", "fixture", "market"}:
        quote = replace(quote, **{"candidate": {"candidate_id": "other"}, "fixture": {"fixture_id": 82},
            "market": {"market_key": "RESULT_AWAY"}}[bad])
    else:
        stamp = NOW + timedelta(seconds=1) if bad == "future" else NOW - timedelta(seconds=1 if bad == "before_model" else 90000)
        quote = _quote(signal, fetched_at=stamp)
    signal = replace(signal, reference_quote=quote.to_dict())
    card = build_wettfinder_card(signal, quote, now=NOW)
    assert compose_wettfinder_catalog([card]).featured == ()
    assert daily3_choices([signal], now=NOW) == ()
    assert [item.key for item in compose_wettfinder_catalog([card]).additional] == ["81:DC_1X"]


def test_exact_existing_quote_is_an_actual_check_without_an_attempt_map():
    # Break caught: historical exact quotes require a newly invented attempt timestamp.
    signal = _signal()
    quote = _quote(signal)
    signal = replace(signal, reference_quote=quote.to_dict())
    card = build_wettfinder_card(signal, quote, now=NOW)
    assert [item.key for item in compose_wettfinder_catalog([card]).featured] == ["81:DC_1X"]
    assert [item.signal.key for item in daily3_choices([signal], now=NOW)] == ["81:DC_1X"]


@pytest.mark.parametrize(("attempt_key", "stamp", "expected"), [
    ("81:DC_1X", "2030-01-01T07:00:00+00:00", "2030-01-01T07:00:00+00:00"),
    ("other", "2030-01-01T07:00:00+00:00", None),
    ("81:DC_1X", "2030-01-01T07:00:01+00:00", None),
    ("81:DC_1X", "2030-01-01T06:59:59+00:00", None),
    ("81:DC_1X", "2030-01-01T07:00:00", None),
])
def test_loader_projects_only_the_exact_valid_attempt_and_preserves_original_time(tmp_path, attempt_key, stamp, expected):
    # Break caught: loader uses another key, trusts a row-level claimed check, or renews original times.
    from test_ev_signal_sources import _automatic_document
    signal = _signal()
    row = {**{key: value for key, value in vars(signal).items() if value is not None},
        "event": signal.event_label, "home_id": 11, "away_id": 12,
        "price_checked_at": "2030-01-01T07:00:00+00:00"}
    document = _automatic_document([row])
    document["price_check_attempts"] = {attempt_key: stamp}
    before = deepcopy(document)
    loaded = automated_wettfinder_forecasts(tmp_path / "offline.json", now=NOW, _loaded=(document, NOW, []))
    assert len(loaded) == 1
    assert getattr(loaded[0], "price_checked_at", None) == expected
    assert document == before


def test_price_admission_cannot_switch_the_models_modal_direction_to_checked_opposition():
    # Break caught: price eligibility runs before coherent direction selection.
    home = _signal("RESULT_HOME", .75)
    away = _with_attempt(_signal("RESULT_AWAY", .72), NOW.isoformat())
    assert [item.key for item in select_consumer_forecasts([away, home], now=NOW)] == ["81:RESULT_HOME"]
    catalog = compose_wettfinder_catalog([build_wettfinder_card(s, now=NOW) for s in [away, home]])
    assert catalog.featured == ()
    assert [item.key for item in catalog.additional] == ["81:RESULT_HOME"]
    assert daily3_choices([away, home], now=NOW) == ()


def test_known_below_floor_price_remains_excluded_after_an_actual_check():
    # Break caught: successful admission bypasses the existing known-offer 1.20 floor.
    signal = _signal()
    quote = _quote(signal, odds=1.1)
    signal = replace(signal, reference_quote=quote.to_dict())
    catalog = compose_wettfinder_catalog([build_wettfinder_card(signal, quote, now=NOW)])
    assert not catalog.featured and not catalog.additional
    assert daily3_choices([signal], now=NOW) == ()
