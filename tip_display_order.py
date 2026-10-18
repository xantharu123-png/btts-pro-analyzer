"""Read-only order after model/coherence selection; never a ranking model."""
from collections import OrderedDict
from datetime import datetime, timezone
from numbers import Real
import math

START_TIME = 'Startzeit'
PROBABILITY = 'Wahrscheinlichkeit'
ORDER_OPTIONS = (START_TIME, PROBABILITY)


def display_order_control(st, *, key, probability_available=True):
    # Model-backed surfaces have one presentation policy. In particular, an
    # old probability widget/session value cannot override actual start order.
    if probability_available:
        return START_TIME
    options = (START_TIME,)
    help_text = 'Nächste Spiele zuerst.'
    value = st.selectbox('Reihenfolge', options, index=0, key=key, help=help_text)
    return value if value in options else START_TIME


def _clock(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _chance(value):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not 0 <= value <= 1:
        return -1.
    return float(value)


def recommendation_probability(candidate):
    """RecommendationCandidate stores percent, unlike the fraction cards."""
    value = candidate.model_probability
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not 0 <= value <= 100:
        return None
    return float(value) / 100


def ordered_event_rows(rows, *, mode=START_TIME, event_key, starts_at, probability):
    """Keep every event adjacent, using original identities and actual clocks.

    Already selected objects are returned unchanged. Games default to actual
    start time; unknown starts follow known ones. Existing within-game chance
    priority is retained, with stable ties. Explicit probability mode remains
    available to internal callers, but no model-backed UI selects it.
    Quotes, quality badges and displayed team names are deliberately unused.
    """
    if mode not in ORDER_OPTIONS:
        raise ValueError('unknown display order')
    groups = OrderedDict()
    unbound = object()
    for index, row in enumerate(rows):
        identity = event_key(row)
        # Absence of an identity is not evidence that unrelated events are
        # one game. Keep these rows separate without inventing a source ID.
        groups.setdefault(identity if identity is not None else (unbound, index), []).append(row)
    last = datetime.max.replace(tzinfo=timezone.utc)
    def start(group):
        return min((_clock(starts_at(row)) or last for row in group), default=last)
    def chance(group):
        return max((_chance(probability(row)) for row in group), default=-1.)
    grouped = sorted(groups.values(), key=(lambda group: start(group)) if mode == START_TIME
                     else (lambda group: (-chance(group), start(group))))
    return tuple(row for group in grouped
                 for row in sorted(group, key=lambda item: (-_chance(probability(item)),
                                                           _clock(starts_at(item)) or last)))
