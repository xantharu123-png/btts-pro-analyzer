"""Defensive, price-blind model shortlist, not a certified safety ranking.

v2 requires at least 70% model probability on top of the existing exact-bound
evidence and freshness checks. Higher model probability precedes diversity;
diversity only breaks ties. This is a product preference, NOT an empirical
lower confidence bound or proof of lower actual loss risk across models.
Haircut, minimum/observed odds, RELEASED flags, target profit and account money
are not ranking inputs. The ordinary full catalog is never modified.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from challenge_engine import MARKET_BY_KEY
from daily3_identity import event_guard, events_overlap
from forecast_analysis import build_forecast_analysis, forecast_highlight_reason
from forecast_selection import select_consumer_forecasts
from selection_coherence import consumer_event_identity

POLICY_VERSION = 'daily3-defensive-model-v2'
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

    def snapshot(self):
        s = self.signal
        return dict(event_id=self.event_id, event_guard=event_guard(s), sport=self.sport, event_label=s.event_label or s.label,
            market_key=s.market_key, market=s.market, selection=s.selection, scheduled_start=self.start.isoformat(),
            signal_key=s.key, model_probability=s.probability, modeled_at=self.sampled_at.isoformat(),
            model_version=s.model_version or f'Policy: {s.policy_version}', analysis_basis=self.basis,
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


def daily3_choices(signals, *, now, occupied_events=(), occupied_guards=(), used_slots=0):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Daily3 requires an aware server clock')
    if type(used_slots) is not int or used_slots < 0:
        raise ValueError('Invalid actual slot count')
    now = now.astimezone(timezone.utc)
    today = now.astimezone(_TZ).date()
    occupied = set(occupied_events)
    guards = tuple(occupied_guards)
    prepared = []
    for s in select_consumer_forecasts(signals, now=now):
        sport = _SPORTS.get(str(s.sport or '').strip().casefold())
        start, sampled = _clock(s.scheduled_start), _clock(s.modeled_at)
        if not sport or not start or not sampled or not now < start or start.astimezone(_TZ).date() != today:
            continue
        if not timedelta(0) <= now-sampled <= timedelta(hours=2, minutes=30):
            continue
        event = consumer_event_identity(s)
        if event.startswith('unresolved:') or event in occupied or not all((s.key, s.market_key, s.market, s.selection)):
            continue
        if any(events_overlap(event_guard(s), guard) for guard in guards):
            continue
        explanation = _explanation(s, sport, now)
        if explanation is None or not MIN_MODEL_PROBABILITY <= s.probability < 1:
            continue
        spec = MARKET_BY_KEY.get(s.market_key) if sport == 'football' else None
        family = spec.kind if spec else s.market_key
        prepared.append(Daily3Choice(s, event, sport, *explanation, sampled, start, family))
    unique = prepared
    selected, sport_count, family_count = [], Counter(), Counter()
    while unique and len(selected) < max(0, 3-used_slots):
        unique.sort(key=lambda c: (-c.signal.probability,
                                   sport_count[c.sport], family_count[(c.sport, c.family)],
                                   -c.sampled_at.timestamp(), c.start, c.event_id, c.signal.key))
        # The shared complete pool is already coherent. Defensive shortlisting
        # may only remove rows; it cannot re-anchor an opposing scenario.
        match = unique[0]
        selected.append(match)
        sport_count[match.sport] += 1
        family_count[(match.sport, match.family)] += 1
        match_guard = event_guard(match.signal)
        unique = [c for c in unique if not events_overlap(event_guard(c.signal), match_guard)]
    return tuple(selected)
