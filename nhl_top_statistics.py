"""Coverage gate and paired NHL market scoring for the frozen TOP study."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import fsum
from zoneinfo import ZoneInfo

from model_loss_statistics import paired_advantage_statistics


_ZURICH = ZoneInfo("Europe/Zurich")
_LIMITS = {"tier_60": (200, 30), "tier_70": (50, 15)}


@dataclass(frozen=True)
class _Game:
    source: Mapping
    event_id: str
    start: datetime
    zurich_day: date
    p_model: float
    p_market: float

    @property
    def tier_70(self):
        # Match the Wettfinder display threshold; score the original p instead.
        return round(self.p_model * 100, 1) >= 70.0


def _prepare(games):
    prepared, seen = [], set()
    for row in games:
        if not isinstance(row, Mapping):
            raise ValueError("NHL game must carry prevalidated evidence")
        event_id, start = row.get("event_id"), row.get("start")
        model, market = row.get("p_model"), row.get("p_market")
        if (not isinstance(event_id, str) or not event_id.strip() or event_id in seen
                or not isinstance(start, datetime) or start.utcoffset() is None
                or type(model) not in (int, float) or not .60 <= model <= 1
                or type(market) not in (int, float) or not 0 < market < 1):
            raise ValueError("invalid or duplicate NHL game")
        day = start.astimezone(_ZURICH).date()
        prepared.append(_Game(row, event_id, start.astimezone(timezone.utc), day, model, market))
        seen.add(event_id)
    return sorted(prepared, key=lambda game: (game.start, game.event_id))


def _counts(games):
    def count(group):
        return {"games": len(group), "zurich_days": len({game.zurich_day for game in group})}

    return {"tier_60": count(games), "tier_70": count([game for game in games if game.tier_70])}


def _sufficient(counts):
    return all(counts[tier]["games"] >= n and counts[tier]["zurich_days"] >= days
               for tier, (n, days) in _LIMITS.items())


def nhl_top_coverage(games):
    """Count qualifying pairs without opening outcomes at any sample size."""
    return _counts(_prepare(games))


def _score(settled):
    model = [(game.p_model - outcome) ** 2 for game, outcome in settled]
    market = [(game.p_market - outcome) ** 2 for game, outcome in settled]
    advantage, error, lower, p_value = paired_advantage_statistics(
        [b - a for a, b in zip(model, market)]
    )
    return dict(
        model_brier=fsum(model) / len(model),
        market_brier=fsum(market) / len(market),
        brier_advantage=advantage,
        paired_hac_standard_error=error,
        paired_one_sided_95pct_lower_bound=lower,
        paired_one_sided_p_value=p_value,
    )


def evaluate_nhl_top(games, load_outcome):
    """Apply both pre-registration coverage gates before emitting any scores.

    The caller owns the outcome-opening date and exact native game, market and
    outcome binding. An unresolved or conflicting outcome is supplied as None.
    """
    pairs = _prepare(games)
    coverage = _counts(pairs)
    result = dict(status="insufficient_coverage", coverage=coverage, settled=None, scores=None)
    if not _sufficient(coverage):
        return result

    settled = []
    for game in pairs:
        outcome = load_outcome(game.source)
        if outcome is None:
            continue
        if type(outcome) is not int or outcome not in (0, 1):
            raise ValueError("NHL outcome must be 0, 1, or None")
        settled.append((game, outcome))

    counts = _counts([game for game, _ in settled])
    result.update(status="insufficient_settled", settled=counts)
    if not _sufficient(counts):
        return result

    scores = {
        "tier_60": _score(settled),
        "tier_70": _score([(game, y) for game, y in settled if game.tier_70]),
    }
    passed = all(item["paired_one_sided_95pct_lower_bound"] > 0 for item in scores.values())
    return dict(result, status="passed" if passed else "not_passed", scores=scores)
