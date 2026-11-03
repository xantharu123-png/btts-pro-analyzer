"""Doublebet: up to three single bets a day at odds around 2.00, the most probable by the model.

Owner decision 03.11.2026 (docs/audits/2026-11-03-doublebet.md). Every candidate needs an
admitted current quote whose median lies in the band DOUBLEBET_ODDS_MIN..DOUBLEBET_ODDS_MAX;
the bookmaker then says roughly 50 % to all of them, and the ranking inside the band comes
from the model alone. Among the candidates that can be played as a day sequence (planning
allowance, before Zurich midnight, no overlapping events) the sequence of at most three legs
with the highest sum of model probabilities is chosen. Form (football) and surface (ATP)
comparisons remain supporting information, no longer a requirement. Haircut, release flags,
target profit and account money are not ranking inputs. Each choice carries its own
reservation minimum and the admitted offer as display information only (audit 2026-10-16, K4).
Published choices are chronological planning, not guaranteed match durations or cash credits.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from statistics import median
from zoneinfo import ZoneInfo

from betting_math import MINIMUM_RECOMMENDED_DECIMAL_ODDS
from challenge_engine import MARKET_BY_KEY
from daily3_identity import event_guard, events_overlap
from daily3_comparison import Comparison, daily3_comparison
from daily3_schedule import fits_daily3_window, planned_ready_at
from forecast_analysis import (DAILY_MODEL_HIGHLIGHT_MAX_AGE, build_forecast_analysis,
    football_context_highlight_reason, forecast_highlight_reason, read_football_analysis)
from forecast_selection import select_consumer_forecasts
from forecast_price_checks import has_current_price_check
from quote_publication import publication_quote
from selection_coherence import consumer_event_identity

POLICY_VERSION = 'doublebet-odds-around-2-most-probable-v14'
# Owner decision 03.11.2026: "um 2,00" is an admitted median quote from 1.80 to 2.20.
DOUBLEBET_ODDS_MIN = 1.80
DOUBLEBET_ODDS_MAX = 2.20
MAX_LEGS = 3
_TZ = ZoneInfo('Europe/Zurich')
_SPORTS = {'fussball': 'football', 'fußball': 'football', 'football': 'football',
           'tennis': 'tennis', 'basketball': 'basketball', 'eishockey': 'hockey',
           'hockey': 'hockey', 'ice hockey': 'hockey', 'e-sport': 'esports', 'esports': 'esports'}


@dataclass(frozen=True)
class Daily3Choice:
    signal: object
    event_id: str
    sport: str
    basis: str
    caution: str
    sampled_at: datetime
    start: datetime
    family: str
    comparison: Comparison | None
    # Reservation/display facts, never selection inputs (see module docstring).
    minimum_odds: float | None = None
    offer_odds: float | None = None
    offer_median_odds: float | None = None

    @property
    def price_blocked(self) -> bool:
        """No real-money reservation without a credible minimum met by the admitted offer.

        Since 23.10.2026 (owner decision) only the 1.20 floor blocks: an offer
        below 1.20 withholds the reservation; no observed offer does not.
        """
        from market_consensus import floor_only_pricing
        if floor_only_pricing():
            return self.offer_odds is not None and self.offer_odds < MINIMUM_RECOMMENDED_DECIMAL_ODDS
        return self.minimum_odds is None or self.offer_odds is None or self.offer_odds < self.minimum_odds

    def snapshot(self):
        s = self.signal
        return dict(event_id=self.event_id, event_guard=event_guard(s), sport=self.sport, event_label=s.event_label or s.label,
            market_key=s.market_key, market=s.market, selection=s.selection, scheduled_start=self.start.isoformat(),
            signal_key=s.key, model_probability=s.probability, modeled_at=self.sampled_at.isoformat(),
            model_version=s.model_version or f'Policy: {s.policy_version}',
            analysis_basis=(self.basis + ' ' + (self.comparison.summary if self.comparison else '')).strip(),
            analysis_caution=self.caution, policy_version=POLICY_VERSION)


def _clock(value):
    try:
        instant = datetime.fromisoformat(value)
        return instant.astimezone(timezone.utc) if instant.tzinfo and instant.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


RESERVATION_MINIMUM_FLAG = 'BETBOY_DAILY3_RESERVATION_MINIMUM'


def reservation_minimum_enforced() -> bool:
    """Whether a real-money reservation must meet the choice's own minimum odds.

    Audit 2026-10-16 K4 recommended the gate; the owner decided on 2026-10-20
    that it is active by default, superseding the 2026-10-17 rule of a bare
    1.20 floor. ``BETBOY_DAILY3_RESERVATION_MINIMUM=0`` switches it off (the
    minimum and the admitted offer are then shown as information only).
    """
    import os
    return os.environ.get(RESERVATION_MINIMUM_FLAG, '1').strip() != '0'


def reservation_minimum_odds(signal):
    """Stricter of the 1.20 floor and the forecast's own risk-adjusted minimum.

    The forecast minimum is the price at which the cautious model probability
    (model minus haircut) reaches the 3 % risk-adjusted ROI target. An unknown
    minimum stays unknown; it is never replaced by the floor (fail-closed).
    """
    from market_consensus import floor_only_pricing
    if floor_only_pricing():
        # Owner decision 23.10.2026: the model's own minimum no longer gates a
        # reservation anywhere; only the 1.20 floor does.
        return float(MINIMUM_RECOMMENDED_DECIMAL_ODDS)
    minimum = getattr(signal, 'minimum_odds', None)
    if (isinstance(minimum, bool) or not isinstance(minimum, (int, float))
            or not math.isfinite(minimum) or minimum <= 1.0):
        return None
    return round(max(float(MINIMUM_RECOMMENDED_DECIMAL_ODDS), float(minimum)), 2)


def admitted_offer_odds(signal, *, now):
    """Best current exact real offer behind the publication proof, or None."""
    quote = publication_quote(getattr(signal, 'reference_quote', None), candidate=signal, now=now)
    return None if quote is None else max(point.odds for point in quote.points)


def admitted_median_odds(signal, *, now):
    """Median of the admitted offers: what a typical book pays, as the 1.20 floor reads it."""
    quote = publication_quote(getattr(signal, 'reference_quote', None), candidate=signal, now=now)
    return None if quote is None else float(median(point.odds for point in quote.points))


def in_doublebet_band(odds):
    return odds is not None and DOUBLEBET_ODDS_MIN - 1e-9 <= odds <= DOUBLEBET_ODDS_MAX + 1e-9


def _explanation(signal, sport, now):
    analysis = build_forecast_analysis(signal, now=now)
    if forecast_highlight_reason(signal, now=now, analysis=analysis, check_context=False):
        return None
    if sport == 'football':
        evidence = read_football_analysis(vars(signal), now=now)
        context = evidence.get('context', {}) if evidence else {}
        # The daily automatic model uses the original daily observations, not
        # the 75-minute TOP-review window. Do not renew or invent their clocks;
        # actual vetoes, conflicts and missing observations remain exclusions.
        kwargs = ({'max_age': DAILY_MODEL_HIGHLIGHT_MAX_AGE}
                  if signal.source == 'automated_wettfinder_forecast' else {})
        if football_context_highlight_reason(context, now=now, **kwargs):
            return None
    basis = ' '.join(part for part in (analysis.basis, analysis.samples, analysis.data_age) if part)
    return basis, analysis.caution


def daily3_choices(signals, *, now, occupied_events=(), occupied_guards=(), used_slots=0, not_before=None):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Doublebet requires an aware server clock')
    if type(used_slots) is not int or used_slots < 0:
        raise ValueError('Invalid actual slot count')
    now = now.astimezone(timezone.utc)
    if not_before is not None and (not_before.tzinfo is None or not_before.utcoffset() is None):
        raise ValueError('Doublebet requires an aware planning clock')
    ready = max(now, not_before.astimezone(timezone.utc)) if not_before is not None else now
    today = now.astimezone(_TZ).date()
    occupied = set(occupied_events)
    guards = tuple(occupied_guards)
    slots = max(0, MAX_LEGS - used_slots)
    prepared = []
    for s in select_consumer_forecasts(signals, now=now):
        if not has_current_price_check(s, now=now):
            continue
        offer = admitted_offer_odds(s, now=now)
        if offer is None:
            continue
        offer_median = admitted_median_odds(s, now=now)
        if not in_doublebet_band(offer_median):
            continue
        sport = _SPORTS.get(str(s.sport or '').strip().casefold())
        start, sampled = _clock(s.scheduled_start), _clock(s.modeled_at)
        if not sport or not start or not sampled or not now < start or start.astimezone(_TZ).date() != today:
            continue
        if start < ready or not fits_daily3_window(start, sport, used_slots):
            continue
        event = consumer_event_identity(s)
        if event.startswith('unresolved:') or event in occupied or not all((s.key, s.market_key, s.market, s.selection)):
            continue
        if any(events_overlap(event_guard(s), guard) for guard in guards):
            continue
        explanation = _explanation(s, sport, now)
        if explanation is None or not 0 < s.probability < 1:
            continue
        # Supporting information only (owner 03.11.2026): no probability floor, no form bonus.
        comparison = daily3_comparison(s, now=now, minimum_probability=0.0, require_positive_change=False)
        spec = MARKET_BY_KEY.get(s.market_key) if sport == 'football' else None
        family = spec.kind if spec else s.market_key
        prepared.append(Daily3Choice(s, event, sport, *explanation, sampled, start, family, comparison,
                                     reservation_minimum_odds(s), offer, offer_median))
    return _best_sequence(prepared, slots)


def _follows(later, earlier):
    """A leg that starts after the earlier leg's planning allowance and does not overlap its event."""
    return (later.start >= planned_ready_at(earlier.start, earlier.sport)
            and not events_overlap(event_guard(later.signal), event_guard(earlier.signal)))


def _best_sequence(prepared, slots):
    """The day sequence of at most ``slots`` legs with the highest sum of model probabilities.

    Candidates are chained chronologically with their planning allowances; the
    probabilities are positive, so a longer feasible sequence always beats a
    shorter one. Ties go to the earlier first leg, then to stable keys.
    """
    if slots <= 0 or not prepared:
        return ()
    order = sorted(prepared, key=lambda c: (c.start, -c.signal.probability, c.event_id, c.signal.key))
    best: list[dict[int, tuple[float, tuple]]] = []
    for index, choice in enumerate(order):
        options = {1: (choice.signal.probability, (choice,))}
        for earlier_index in range(index):
            if not _follows(choice, order[earlier_index]):
                continue
            for length, (score, chain) in best[earlier_index].items():
                if length + 1 > slots:
                    continue
                candidate = (score + choice.signal.probability, chain + (choice,))
                current = options.get(length + 1)
                if current is None or candidate[0] > current[0] + 1e-12:
                    options[length + 1] = candidate
        best.append(options)
    winner = None
    for options in best:
        for score, chain in options.values():
            if winner is None or score > winner[0] + 1e-12 or (
                    abs(score - winner[0]) <= 1e-12 and _chain_order(chain) < _chain_order(winner[1])):
                winner = (score, chain)
    return tuple(winner[1]) if winner else ()


def _chain_order(chain):
    return tuple((c.start, c.event_id, c.signal.key) for c in chain)
