"""Price-blind Daily3 presentation policy; not a calibrated safety ranking.

v1 prefers individually explainable, current model selections, diversifies
sport/market families and keeps one selection per unambiguous event. Only
mutually exclusive directions in the same event/model revision are compared
by probability. Haircut, minimum/observed odds, RELEASED flags and account
money are not ranking inputs. The ordinary full catalog is never modified.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo

from challenge_engine import MARKET_BY_KEY
from daily3_identity import event_guard, events_overlap
from forecast_analysis import build_forecast_analysis, read_football_analysis
from selection_coherence import consumer_event_identity, select_coherent_forecasts

POLICY_VERSION = 'daily3-evidence-diversity-v1'
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
    """Use existing exact-bound evidence, never make a claim from admin prose."""
    if sport == 'football':
        evidence = read_football_analysis(vars(signal), now=now)
        analysis = build_forecast_analysis(signal, now=now)
        if evidence and analysis.samples and 'konkrete Modellgrundlagen fehlen' not in analysis.basis:
            return analysis.basis+' '+analysis.samples, analysis.caution
    if sport == 'tennis':
        context = signal.context_evidence
        if not isinstance(context, dict):
            return None
        inputs, players = context.get('model_inputs'), context.get('players')
        # The existing tennis producer binds observations to both participant
        # names and the model cutoff. A bare surface label is not such evidence.
        if not isinstance(inputs, dict) or not isinstance(players, dict):
            return None
        if (_clock(context.get('observed_at')) != _clock(signal.modeled_at)
                or not all(isinstance(players.get(side), dict) and players[side].get('player') == name
                           for side, name in (('a', signal.competitor_a), ('b', signal.competitor_b)))):
            return None
        surfaces = {'Hard': 'Hartplatz', 'Clay': 'Sand', 'Grass': 'Rasen', 'Carpet': 'Teppich',
                    'hard': 'Hartplatz', 'clay': 'Sand', 'grass': 'Rasen', 'carpet': 'Teppich'}
        surface = surfaces.get(inputs.get('surface'))
        if inputs.get('surface_in_model') is True and surface:
            serve = ' und Aufschlagdaten' if inputs.get('serve_in_model') is True else ''
            basis = f'Das Modell berücksichtigt die Spielstärke auf {surface}{serve}. Daraus ergibt sich die Auswahl {signal.selection}.'
            caution = 'Eine Modellschätzung, keine sichere Wette. Verletzungen und Müdigkeit sind in diesem Beleg nicht als numerischer Vorteil nachgewiesen.'
            return basis, caution
    if sport == 'esports':
        evidence = signal.context_evidence
        if not isinstance(evidence, dict) or evidence.get('schema') != 'esports-card-basis-v1':
            return None
        if (evidence.get('provider_event_id') != signal.provider_event_id
                or _clock(evidence.get('modeled_at')) != _clock(signal.modeled_at)
                or evidence.get('competitor_a') != signal.competitor_a
                or evidence.get('competitor_b') != signal.competitor_b):
            return None
        left, right = evidence.get('elo_a'), evidence.get('elo_b')
        if not all(type(n) in (int, float) and math.isfinite(n) and 0 < n < 10000 for n in (left, right)):
            return None
        selected_a = signal.selected_competitor == signal.competitor_a
        if signal.selected_competitor not in (signal.competitor_a, signal.competitor_b):
            return None
        own, opponent = (left, right) if selected_a else (right, left)
        basis = f'Modellbasis für {signal.selected_competitor}: Elo {own:.0f}, Gegner {opponent:.0f}. Diese gespeicherten Spielstärken fließen in das Siegmodell ein.'
        caution = 'Kaderwechsel, Ersatzspieler und aktuelle Serienbelastung sind damit nicht als zusätzlicher Vorteil belegt.'
        return basis, caution
    # A sport is not banned. Until its shared producer supplies an individually
    # attributable explanation, its forecasts remain in the ordinary finder.
    return None


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
    for s in signals:
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
        if explanation is None:
            continue
        spec = MARKET_BY_KEY.get(s.market_key) if sport == 'football' else None
        family = spec.kind if spec else s.market_key
        prepared.append(Daily3Choice(s, event, sport, *explanation, sampled, start, family))
    # Newest observed model wins for an identical key; source iteration order
    # and a price refresh cannot change the selected model revision.
    prepared.sort(key=lambda c: (-c.sampled_at.timestamp(), c.start, c.event_id, c.signal.key))
    unique, seen = [], set()
    for choice in prepared:
        if choice.signal.key not in seen:
            seen.add(choice.signal.key)
            unique.append(choice)
    # Within one event/model revision, mutually exclusive outcomes ARE on the
    # same probability scale. Prefer that model's most likely direction instead
    # of accidentally choosing "AWAY" merely because its key sorts first. This
    # is not a cross-sport safety score or a probability floor for other markets.
    directions = {}
    for choice in unique:
        if choice.family in ('result', 'btts', 'H2H'):
            group = (choice.event_id, choice.family, choice.sampled_at, choice.signal.model_version,
                     choice.signal.policy_version, choice.signal.model_scope)
            previous = directions.get(group)
            if previous is None or choice.signal.probability > previous.signal.probability:
                directions[group] = choice
    preferred_directions = {id(c) for c in directions.values()}
    unique = [c for c in unique if c.family not in ('result', 'btts', 'H2H') or id(c) in preferred_directions]
    selected, sport_count, family_count = [], Counter(), Counter()
    while unique and len(selected) < max(0, 3-used_slots):
        unique.sort(key=lambda c: (sport_count[c.sport], family_count[(c.sport, c.family)],
                                   -c.sampled_at.timestamp(), c.start, c.event_id, c.signal.key))
        # Coherence checks the whole remaining pool, including weak event
        # aliases, BEFORE taking a single card. One event then consumes one slot.
        coherent = {id(s) for s in select_coherent_forecasts([c.signal for c in unique])}
        match = next((c for c in unique if id(c.signal) in coherent), None)
        if match is None:
            break
        selected.append(match)
        sport_count[match.sport] += 1
        family_count[(match.sport, match.family)] += 1
        match_guard = event_guard(match.signal)
        unique = [c for c in unique if not events_overlap(event_guard(c.signal), match_guard) and id(c.signal) in coherent]
    return tuple(selected)
