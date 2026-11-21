"""Receipt clock for one exact native offer; never advance a book to another page's receipt."""

from market_consensus import (
    ODDS_API_REFERENCE_SOURCE, REFERENCE_SOURCE, _parse_utc, native_partition_contract,
    validated_native_partitions,
)


def point_fetch(quote, point):
    """Return the proven receipt clock. The caller has already matched the fixture and market."""
    if point not in quote.points or not point.bookmaker_id:
        return None
    observed, aggregate = _parse_utc(point.observed_at), _parse_utc(quote.fetched_at)
    if observed is None or aggregate is None or observed > aggregate:
        return None
    if quote.source == ODDS_API_REFERENCE_SOURCE:
        # Each native H2H event is an entry of ONE received EU response;
        # the producer rejects duplicate event IDs before parsing it.
        if (quote.provider_event_id and quote.market_key == "H2H" and quote.bet_name == "h2h"
                and point.bookmaker_id.startswith("odds-api:")):
            return aggregate.isoformat()
        return None
    if quote.source != REFERENCE_SOURCE or not point.bookmaker_id.startswith("api-football:"):
        return None
    direct = _parse_utc(point.fetched_at)
    if point.fetched_at is not None and (direct is None or not observed <= direct <= aggregate):
        return None
    # Older snapshots can prove the clock via an exhaustive market partition.
    # In particular, 1X2 constituents do NOT prove a price for double chance.
    contract = native_partition_contract(quote)
    clocks = set()
    if contract is not None and contract[-1] is not None:
        matching = [part for part in quote.native_market_partitions
                    if isinstance(part, dict) and part.get("bookmaker_id") == point.bookmaker_id]
        clocks = {part["fetched_at"] for part in validated_native_partitions(matching, quote)}
    if direct is not None:
        clocks.add(direct.isoformat())
    return clocks.pop() if len(clocks) == 1 else None
