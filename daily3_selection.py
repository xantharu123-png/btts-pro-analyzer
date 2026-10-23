"""Defensive comparison shortlist, with the user's known-offer price floor.

Retain exact-bound model variants and at least 70% in all three. Compare form
(football) or surface (ATP) against the same match's general strength; a positive
two-percentage-point change is not necessary for a defensive day selection.
Haircut, odds, RELEASED flags, target profit and account money are not ranking
inputs. After coherent model selection, a real exactly matched offer from 1.20
is required. Unknown prices remain background-only; admitted prices do not change ranking.
Each choice additionally carries its own risk-adjusted minimum odds and the admitted
offer. Both are reservation and display information only, never a selection input:
real money may only be reserved at or above that minimum (audit 2026-10-16, K4).
Time admission checks each actual leg, not imaginary future bets. Published choices are
chronological planning, not guaranteed match durations or future cash credits.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import math
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

POLICY_VERSION = 'daily3-defensive-day-sequence-checked-prices-v13'
# Deliberate shortlist threshold, not a learned/calibrated safety boundary.
MIN_MODEL_PROBABILITY = 0.70
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
    comparison: Comparison
    # Reservation/display facts, never selection inputs (see module docstring).
    minimum_odds: float | None = None
    offer_odds: float | None = None

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
            model_version=s.model_version or f'Policy: {s.policy_version}', analysis_basis=self.basis + ' ' + self.comparison.summary,
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
        raise ValueError('Daily3 requires an aware server clock')
    if type(used_slots) is not int or used_slots < 0:
        raise ValueError('Invalid actual slot count')
    now = now.astimezone(timezone.utc)
    if not_before is not None and (not_before.tzinfo is None or not_before.utcoffset() is None):
        raise ValueError('Daily3 requires an aware planning clock')
    ready = max(now, not_before.astimezone(timezone.utc)) if not_before is not None else now
    today = now.astimezone(_TZ).date()
    occupied = set(occupied_events)
    guards = tuple(occupied_guards)
    prepared = []
    for s in select_consumer_forecasts(signals, now=now):
        if not has_current_price_check(s, now=now):
            continue
        offer = admitted_offer_odds(s, now=now)
        if offer is None:
            continue
        sport = _SPORTS.get(str(s.sport or '').strip().casefold())
        start, sampled = _clock(s.scheduled_start), _clock(s.modeled_at)
        if not sport or not start or not sampled or not now < start or start.astimezone(_TZ).date() != today:
            continue
        event = consumer_event_identity(s)
        if event.startswith('unresolved:') or event in occupied or not all((s.key, s.market_key, s.market, s.selection)):
            continue
        if any(events_overlap(event_guard(s), guard) for guard in guards):
            continue
        explanation = _explanation(s, sport, now)
        if explanation is None or not MIN_MODEL_PROBABILITY <= s.probability < 1:
            continue
        comparison = daily3_comparison(s, now=now, minimum_probability=MIN_MODEL_PROBABILITY,
                                       require_positive_change=False)
        if comparison is None:
            continue
        spec = MARKET_BY_KEY.get(s.market_key) if sport == 'football' else None
        family = spec.kind if spec else s.market_key
        prepared.append(Daily3Choice(s, event, sport, *explanation, sampled, start, family, comparison,
                                     reservation_minimum_odds(s), offer))
    unique = prepared
    selected, sport_count, family_count = [], Counter(), Counter()
    while unique and len(selected) < max(0, 3-used_slots):
        eligible = [c for c in unique if c.start >= ready and
                    fits_daily3_window(c.start, c.sport, used_slots+len(selected))]
        if not eligible:
            break
        # Plan the earliest qualified game first rather than replacing the
        # entire day's sequence with a higher probability late-night game.
        # At the same kickoff, defensive strength precedes diversity/form.
        eligible.sort(key=lambda c: (c.start, -c.comparison.lowest_model_probability,
                                   sport_count[c.sport], family_count[(c.sport, c.family)],
                                   -c.comparison.margin,
                                   -c.sampled_at.timestamp(), c.start, c.event_id, c.signal.key))
        # The shared complete pool is already coherent. Defensive shortlisting
        # may only remove rows; it cannot re-anchor an opposing scenario.
        match = eligible[0]
        selected.append(match)
        ready = planned_ready_at(match.start, match.sport)
        sport_count[match.sport] += 1
        family_count[(match.sport, match.family)] += 1
        match_guard = event_guard(match.signal)
        unique = [c for c in unique if not events_overlap(event_guard(c.signal), match_guard)]
    return tuple(selected)
