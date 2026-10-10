"""Read-only proof of a price-check attempt, separate from model qualification."""
from datetime import datetime, timedelta, timezone

from market_consensus import MarketConsensus, quote_matches_candidate


PRICE_CHECK_MAX_AGE = timedelta(hours=24)


def _clock(value):
    if not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value)
        return instant.astimezone(timezone.utc) if instant.tzinfo and instant.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def valid_price_check_time(checked_at, modeled_at, *, now):
    """Use original aware clocks; a check cannot precede its model revision."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("price check requires an aware server clock")
    current = now.astimezone(timezone.utc)
    checked, modeled = _clock(checked_at), _clock(modeled_at)
    return (checked is not None and modeled is not None
            and modeled <= checked <= current and current-checked <= PRICE_CHECK_MAX_AGE)


def has_current_price_check(signal, *, now, quote=None):
    """An exact attempt may return no quote; an exact saved quote also proves a check.

    This admission flag never changes probabilities, direction or price ranking.
    The persisted loader binds price_checked_at to the signal's exact original key.
    """
    if valid_price_check_time(getattr(signal, "price_checked_at", None), signal.modeled_at, now=now):
        return True
    raw = quote if quote is not None else getattr(signal, "reference_quote", None)
    parsed = raw if isinstance(raw, MarketConsensus) else MarketConsensus.from_dict(raw)
    candidate = {**vars(signal), "candidate_id": signal.candidate_id or signal.key}
    return (parsed is not None and quote_matches_candidate(parsed, candidate)
            and valid_price_check_time(parsed.fetched_at, signal.modeled_at, now=now))
