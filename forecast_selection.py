"""One price-blind complete-pool presentation policy for both consumers.

Probability compares mutually exclusive directions only inside an exact event,
participant binding and model revision. It never ranks unrelated markets.
The returned objects are untouched; coherence is run exactly once before any
consumer's section, slot, occupancy or price filter.
"""
from datetime import datetime, timezone

from challenge_engine import MARKET_BY_KEY
from forecast_analysis import _clock, forecast_highlight_reason
from selection_coherence import _role_binding, consumer_event_identity, select_coherent_forecasts


def _family(row):
    key = str(row.market_key or '').upper()
    spec = MARKET_BY_KEY.get(key)
    return spec.kind if spec else key


def _stable_key(row):
    # Explicit role/market key beats input order, including probability ties.
    direction = {'RESULT_HOME': 0, 'RESULT_DRAW': 1, 'RESULT_AWAY': 2, 'BTTS_YES': 0, 'BTTS_NO': 1}
    return (direction.get(row.market_key, 0), str(row.market_key or ''),
            str(getattr(row, 'selected_competitor', '') or ''), str(row.key),
            str(getattr(row, 'model_version', '') or ''),
            str(getattr(row, 'policy_version', '') or ''),
            str(getattr(row, 'model_scope', '') or ''),
            str(_clock(getattr(row, 'input_cutoff_at', None)) or ''),
            str(_role_binding(row) or ''),
            str(_clock(getattr(row, 'scheduled_start', None)) or ''))


def select_consumer_forecasts(rows, *, now=None):
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError('consumer selection requires an aware clock')
    current = current.astimezone(timezone.utc)
    pool = list(rows)
    def eligible(row):
        retained = getattr(row, 'highlight_eligible', None)
        return retained if retained is not None else not forecast_highlight_reason(row, now=current)
    clocks = {id(row): _clock(getattr(row, 'modeled_at', None)) for row in pool}
    qualifications = {id(row): eligible(row) for row in pool}
    def preference(row):
        clock = clocks[id(row)]
        return (not qualifications[id(row)], -clock.timestamp() if clock else float('inf'),
                consumer_event_identity(row), _stable_key(row))
    ordered = sorted(pool, key=preference)
    directions = {}
    grouped = {}
    for row in ordered:
        family, clock, binding = _family(row), clocks[id(row)], _role_binding(row)
        event = consumer_event_identity(row)
        identity = (getattr(row, 'model_version', None), getattr(row, 'policy_version', None), getattr(row, 'model_scope', None))
        if (family not in {'result', 'btts', 'H2H'} or clock is None
                or not binding or binding[0] == 'invalid' or event.startswith('unresolved:')
                or not any(identity)):
            continue
        group = (event, binding, family, clock, _clock(getattr(row, 'input_cutoff_at', None)), identity)
        grouped[id(row)] = group
        previous = directions.get(group)
        probability = getattr(row, 'probability', getattr(row, 'model_probability', None))
        # Unsupported evidence cannot displace a supported direction merely
        # because it reports a larger number. Inside the same eligibility class
        # compare only these mutually exclusive, comparable model directions.
        score = (not qualifications[id(row)], -probability, _stable_key(row))
        if previous is None or score < previous[0]:
            directions[group] = (score, row)
    preferred = [row for row in ordered if id(row) not in grouped or directions[grouped[id(row)]][1] is row]
    # Presentation order is category-neutral. Separately preserve the model's
    # modal result direction as the event/revision scenario when available.
    # Otherwise two overlapping double-chance covers could erase that result
    # direction and misleadingly imply a draw-only recommendation. No result
    # probability is compared with a different market's probability here.
    anchors, seen_events = [], set()
    for row in preferred:
        event = consumer_event_identity(row)
        if event in seen_events:
            continue
        seen_events.add(event)
        identity = (getattr(row, 'model_version', None), getattr(row, 'policy_version', None), getattr(row, 'model_scope', None))
        group = (event, _role_binding(row), 'result', clocks[id(row)],
                 _clock(getattr(row, 'input_cutoff_at', None)), identity)
        modal = directions.get(group)
        anchor = modal[1] if modal and qualifications[id(modal[1])] == qualifications[id(row)] else row
        anchors.append(anchor)
    return select_coherent_forecasts(preferred, preferred=anchors)
