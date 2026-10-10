"""Defensive comparison shortlist, with the user's known-offer price floor.

v11 retains exact-bound model variants and at least 70% in all three. Compare
form (football) or surface (ATP) against the same match's general strength; a minimum
two-percentage-point change is a presentation rule, not an empirical guarantee.
Haircut, odds, RELEASED flags, target profit and account money are not ranking
inputs. After coherent model selection, known offers below 1.20 are hidden.
Unknown prices stay eligible after an actual check; offers above the floor do not change ranking.
Time admission leaves room for the remaining daily legs. Published choices are
chronological planning, not guaranteed match durations or future cash credits.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from challenge_engine import MARKET_BY_KEY
from daily3_identity import event_guard, events_overlap
from daily3_comparison import Comparison, daily3_comparison
from daily3_schedule import fits_daily3_window, planned_ready_at
from forecast_analysis import build_forecast_analysis, forecast_highlight_reason
from forecast_selection import select_consumer_forecasts
from forecast_price_checks import has_current_price_check
from market_consensus import quote_below_publication_floor
from selection_coherence import consumer_event_identity

POLICY_VERSION = 'daily3-defensive-day-sequence-checked-prices-v12'
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


def _explanation(signal, sport, now):
    analysis = build_forecast_analysis(signal, now=now)
    if forecast_highlight_reason(signal, now=now, analysis=analysis):
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
        if quote_below_publication_floor(s.reference_quote, candidate=s, now=now):
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
        comparison = daily3_comparison(s, now=now, minimum_probability=MIN_MODEL_PROBABILITY)
        if comparison is None:
            continue
        spec = MARKET_BY_KEY.get(s.market_key) if sport == 'football' else None
        family = spec.kind if spec else s.market_key
        prepared.append(Daily3Choice(s, event, sport, *explanation, sampled, start, family, comparison))
    unique = prepared
    selected, sport_count, family_count = [], Counter(), Counter()
    while unique and len(selected) < max(0, 3-used_slots):
        eligible = [c for c in unique if c.start >= ready and
                    fits_daily3_window(c.start, c.sport, used_slots+len(selected))]
        if not eligible:
            break
        # Relevance is an admission condition, not a reason to prefer higher
        # modeled loss risk. Diversity/form only break equal-risk ties.
        eligible.sort(key=lambda c: (-c.comparison.lowest_model_probability,
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
