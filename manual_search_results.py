"""Projection of existing manual E-Sport snapshots; never fetches or stores data."""
from dataclasses import dataclass
from datetime import datetime, timezone

from esports_prices import attach_cached_esports_prices
from market_consensus import observed_consensus
from multi_sport_recommendations import esports_match_winner_candidate


@dataclass(frozen=True)
class ManualEsportsResult:
    item: dict
    candidate: object
    quote: object


def esports_search_results(items, filters, *, now=None):
    current = now or datetime.now(timezone.utc)
    candidates, bindings = [], []
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate = esports_match_winner_candidate(item, now=current)
        candidates.append((item, candidate))
        binding = {}
        if (candidate.forecast_available and item.get("status") == "upcoming"
                and str(item.get("source") or "").casefold() == "pandascore"
                and type(item.get("id")) is int and item["id"] > 0):
            binding = dict(candidate_id=candidate.event_key, source="esports_shadow",
                           sport="E-Sport", competition=item.get("game"),
                           fixture_source="pandascore", provider_event_id=str(item["id"]),
                           competitor_a=item.get("team1"), competitor_b=item.get("team2"),
                           selected_competitor=candidate.selection, market_key="H2H",
                           scheduled_start=item.get("begin_at"))
        bindings.append(binding)
    prices = attach_cached_esports_prices(bindings, now=current)
    results = []
    for (item, candidate), binding in zip(candidates, prices):
        quote = observed_consensus(binding.get("reference_quote"), candidate=binding, now=current)
        probability = candidate.model_probability / 100 if candidate.forecast_available else None
        if filters.matches(probability=probability,
                           quote=quote.best_odds if quote is not None else None,
                           market_kind="match_winner" if candidate.forecast_available else None):
            results.append(ManualEsportsResult(item, candidate, quote))
    return results
