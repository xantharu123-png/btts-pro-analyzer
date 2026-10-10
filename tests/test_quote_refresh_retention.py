"""An unsuccessful price refresh cannot erase a known exact price floor."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json

import pytest

from market_consensus import quote_below_publication_floor
from wettfinder_automation import _apply_reference_quotes, refresh_prices_only
from wettfinder_surface import wettfinder_quote_binding_candidate
from test_shared_quote_observations import _tennis_price_fixture
from test_wettfinder_surface import NOW, _quote, _signal


EXECUTION_FIELDS = (
    "reference_quote_source", "reference_quote_executable_odds",
    "reference_quote_bookmaker", "reference_quote_bookmaker_id",
    "reference_quote_observed_at",
)


def _fixture(sport, price=1.02):
    if sport == "tennis":
        _, row, quote = _tennis_price_fixture(price=price)
    else:
        signal = _signal()
        row = {**wettfinder_quote_binding_candidate(signal), "key": signal.key,
               "probability": signal.probability, "minimum_odds": signal.minimum_odds,
               "modeled_at": signal.modeled_at, "input_cutoff_at": signal.input_cutoff_at,
               "status": "MODEL_SELECTION"}
        quote = _quote(signal, (price,) * 3)
    row["reference_quote"] = quote.to_dict()
    row["reference_price_status"] = "PLAYABLE"
    for field in EXECUTION_FIELDS:
        row[field] = "previous execution metadata"
    return row, quote


@pytest.mark.parametrize("sport", ["football", "tennis"])
@pytest.mark.parametrize("age_minutes", [10, 90])
def test_failed_refresh_retains_exact_low_quote_without_clock_or_release_promotion(sport, age_minutes):
    previous, quote = _fixture(sport)
    before = deepcopy(previous)
    current, checked = deepcopy(previous), deepcopy(previous)
    now = NOW + timedelta(minutes=age_minutes)

    counts, playable = _apply_reference_quotes(
        [current], [checked], {}, now=now, previous_rows=[previous],
        price_evaluated_at=now,
    )

    assert current["reference_quote"] == quote.to_dict()
    assert current["reference_quote"]["fetched_at"] == NOW.isoformat()
    assert all(p["observed_at"] == NOW.isoformat() for p in current["reference_quote"]["points"])
    assert quote_below_publication_floor(current["reference_quote"], candidate=current, now=now)
    assert counts == {"UNAVAILABLE": 1} and playable == []
    assert current["reference_price_status"] == "UNAVAILABLE"
    assert "reference_price_evaluated_at" not in current
    assert all(field not in current for field in EXECUTION_FIELDS)
    assert all(field not in checked for field in EXECUTION_FIELDS)
    assert current["probability"] == previous["probability"]
    assert current["modeled_at"] == previous["modeled_at"]
    assert previous == before


@pytest.mark.parametrize("sport", ["football", "tennis"])
def test_failed_refresh_of_still_fresh_high_price_cannot_release_old_offer(sport):
    previous, quote = _fixture(sport, price=2.10)
    current, checked = deepcopy(previous), deepcopy(previous)
    counts, playable = _apply_reference_quotes(
        [current], [checked], {}, now=NOW + timedelta(minutes=10), previous_rows=[previous],
    )
    assert current["reference_quote"] == quote.to_dict()
    assert counts == {"UNAVAILABLE": 1} and playable == []
    assert all(field not in current for field in EXECUTION_FIELDS)


@pytest.mark.parametrize("sport", ["football", "tennis"])
def test_new_exact_quote_replaces_old_low_observation(sport):
    previous, _ = _fixture(sport)
    _, incoming = _fixture(sport, price=2.10)
    now = NOW + timedelta(minutes=10)
    incoming = replace(incoming, fetched_at=now.isoformat(), quoted_at=now.isoformat(),
                       points=tuple(replace(p, observed_at=now.isoformat()) for p in incoming.points))
    current, checked = deepcopy(previous), deepcopy(previous)
    counts, playable = _apply_reference_quotes(
        [current], [checked], {incoming.candidate_id: incoming}, now=now,
        previous_rows=[previous], price_evaluated_at=now,
    )
    assert current["reference_quote"]["best_odds"] == 2.10
    assert current["reference_quote"]["fetched_at"] == now.isoformat()
    assert not quote_below_publication_floor(current["reference_quote"], candidate=current, now=now)
    assert counts == {"PLAYABLE": 1} and len(playable) == 1
    assert current["reference_quote_executable_odds"] == 2.10


@pytest.mark.parametrize("sport", ["football", "tennis"])
def test_conflicting_previous_observations_do_not_choose_a_convenient_price(sport):
    low, _ = _fixture(sport)
    high, _ = _fixture(sport, price=2.10)
    current, checked = deepcopy(low), deepcopy(low)
    _apply_reference_quotes([current], [checked], {}, now=NOW, previous_rows=[low, high, low])
    assert "reference_quote" not in current
    assert current["reference_price_status"] == "UNAVAILABLE"


@pytest.mark.parametrize("sport", ["football", "tennis"])
def test_identical_previous_observations_are_not_a_conflict(sport):
    previous, quote = _fixture(sport)
    current, checked = deepcopy(previous), deepcopy(previous)
    _apply_reference_quotes([current], [checked], {}, now=NOW,
                            previous_rows=[previous, deepcopy(previous)])
    assert current["reference_quote"] == quote.to_dict()


@pytest.mark.parametrize("problem", ["other_candidate", "other_start", "other_side", "other_provider"])
def test_retention_rejects_changed_tennis_event_or_side(problem):
    previous, _ = _fixture("tennis")
    current = deepcopy(previous)
    if problem == "other_candidate":
        current["candidate_id"] += "-new-model-row"
    elif problem == "other_start":
        current["scheduled_start"] = (NOW + timedelta(days=1)).isoformat()
    elif problem == "other_side":
        current["selected_competitor"] = current["competitor_b"]
    else:
        current["quote_provider_event_id"] = "different-odds-event"
    _apply_reference_quotes([current], [deepcopy(current)], {}, now=NOW, previous_rows=[previous])
    assert "reference_quote" not in current


def test_foreign_incoming_quote_is_rejected_without_erasing_exact_known_low_price():
    previous, quote = _fixture("football")
    foreign = replace(quote, fixture_id=999999)
    current, checked = deepcopy(previous), deepcopy(previous)
    counts, playable = _apply_reference_quotes(
        [current], [checked], {quote.candidate_id: foreign}, now=NOW,
        previous_rows=[previous], price_evaluated_at=NOW,
    )
    assert current["reference_quote"] == quote.to_dict()
    assert quote_below_publication_floor(current["reference_quote"], candidate=current, now=NOW)
    assert current["reference_price_status"] == "UNAVAILABLE"
    assert counts == {"UNAVAILABLE": 1} and playable == []
    assert all(field not in current for field in EXECUTION_FIELDS)
    assert "reference_price_evaluated_at" not in current


@pytest.mark.parametrize("outcome", ["no_coverage", "provider_failure"])
def test_price_only_refresh_keeps_known_low_price_on_empty_or_failed_provider(tmp_path, outcome):
    previous, quote = _fixture("tennis")
    path = tmp_path / "tennis-prices.json"
    document = {"generated_at": NOW.isoformat(), "model_candidates": [previous],
                "candidates": [], "football": {"untouched": True}}
    path.write_text(json.dumps(document), encoding="utf-8")

    def loader(_rows):
        if outcome == "provider_failure":
            raise RuntimeError("do not publish provider secrets")
        return {}, []

    now = NOW + timedelta(minutes=10)
    summary = refresh_prices_only(state_path=path, now=now, quote_loader=loader, quote_sport="tennis")
    after = json.loads(path.read_text(encoding="utf-8"))
    current = after["model_candidates"][0]
    assert current["reference_quote"] == quote.to_dict()
    assert quote_below_publication_floor(current["reference_quote"], candidate=current, now=now)
    assert summary["quotes"] == 0
    assert summary["operational_errors"] == int(outcome == "provider_failure")
    assert current["reference_price_status"] == "UNAVAILABLE"
    assert all(field not in current for field in EXECUTION_FIELDS)
    assert after["generated_at"] == document["generated_at"]
    assert after["football"] == document["football"]
    assert after["candidates"] == []
    assert "do not publish provider secrets" not in path.read_text(encoding="utf-8")
