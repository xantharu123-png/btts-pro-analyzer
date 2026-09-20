"""Read-only reuse of exact existing odds; no extra request or model write."""
from datetime import datetime, timezone
import json
from pathlib import Path

from market_consensus import (
    MarketConsensus, observed_consensus, quote_below_publication_floor,
    quote_matches_candidate, wettfinder_consensus,
)
from riskobet_domain import stable_event_key
from riskobet_surface import RiskBetPriceOverlay


def football_market(candidate):
    if candidate.sport != 'football':
        return None
    market, side = candidate.market_key, candidate.selection_key
    if candidate.settlement_contract != f'riskobet-settlement-v1:football:{market}:{side}':
        return None
    if market == 'result_90_minutes' and side in ('home', 'away'):
        return 'RESULT_' + side.upper()
    if market == 'draw_90_minutes' and side == 'draw':
        return 'RESULT_DRAW'
    if market == 'double_chance_90_minutes':
        return {'home_or_draw': 'DC_1X', 'away_or_draw': 'DC_X2'}.get(side)
    if side not in ('home', 'away'):
        return None
    for line in ('0_5', '1_5'):
        if market == f'underdog_team_over_{line}_90_minutes':
            return f'{side.upper()}_OVER_{line}'
    return None


def shared_price_overlays(candidates, rows, *, now=None):
    """Join by native event, kickoff and exact settlement market, not names."""
    now = now or datetime.now(timezone.utc)
    index = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        fixture = row.get('fixture_id')
        if type(fixture) is not int or fixture < 1:
            continue
        quote = MarketConsensus.from_dict(row.get('reference_quote'))
        if quote is None or not quote_matches_candidate(quote, row):
            continue
        event = stable_event_key('football', 'api-football', str(fixture))
        key = (event, row.get('market_key'))
        # A conflicting duplicate must not pick a convenient price.
        if key in index and index[key] != (row, quote):
            index[key] = None
        else:
            index[key] = (row, quote)
    overlays = {}
    for candidate in candidates:
        match = index.get((candidate.event_key, football_market(candidate)))
        if match is None:
            continue
        row, quote = match
        binding = {**row, 'scheduled_start': candidate.starts_at.isoformat()}
        display = observed_consensus(quote, candidate=binding, now=now)
        if display is None:
            continue
        fresh = wettfinder_consensus(quote, now=now)
        # Fetch age, too, matters: an old cached response is never current.
        fresh = fresh if fresh and fresh.is_wettfinder_fresh(now) else None
        price = max((fresh or display).points, key=lambda p: p.odds)
        overlays[candidate.candidate_id] = RiskBetPriceOverlay(
            candidate_id=candidate.candidate_id,
            status='AVAILABLE' if fresh else 'STALE',
            observed_odds=price.odds, bookmaker=price.bookmaker,
            observed_at=price.observed_at,
            below_floor=quote_below_publication_floor(quote, candidate=binding, now=now),
        )
    return overlays


def load_shared_price_overlays(candidates, *, now=None, path=None):
    source = Path(path) if path is not None else Path(__file__).resolve().parent / 'runtime_state' / 'wettfinder_latest.json'
    try:
        data = json.loads(source.read_text(encoding='utf-8'))
        rows = data.get('model_candidates', ())
        if not isinstance(rows, list):
            return {}
        return shared_price_overlays(candidates, rows, now=now)
    except (OSError, TypeError, ValueError, AttributeError):
        return {}
