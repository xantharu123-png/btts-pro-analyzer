"""One price-blind complete-pool presentation policy for both consumers.

Probability compares mutually exclusive directions only inside an exact event,
participant binding and model revision. It never ranks unrelated markets.
The returned objects are untouched; coherence is run exactly once before any
consumer's section, slot, occupancy or price filter.
"""
from datetime import datetime, timezone
import math

from challenge_engine import MARKET_BY_KEY
from forecast_analysis import _clock, forecast_highlight_reason
from selection_coherence import _role_binding, consumer_event_identity, select_coherent_forecasts


def validated_selection_rank(value):
    """Optional canonical producer rank; invalid legacy metadata stays absent."""
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        return None
    if any(type(number) not in (int, float) for number in value):
        return None
    try:
        rank = tuple(float(number) for number in value)
    except OverflowError:
        return None
    return rank if all(math.isfinite(number) for number in rank) else None


def _model_probability(row):
    """Finite model probability of a row; anything else cannot lead a game."""
    value = getattr(row, 'probability', None)
    if value is None:
        value = getattr(row, 'model_probability', None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def select_event_leads(rows, *, revision_anchors=None, require_comparable=False):
    """Choose the most probable selection per already coherent canonical event pool.

    Owner decision 23.10.2026 (docs/audits/2026-10-23-hauptauswahl-wahrscheinlichkeit.md):
    the lead of a game is the shown selection with the highest model
    probability, compared only within the first/current row's participant and
    model revision. The producer's statistical rank (``selection_rank``) stays
    on the rows for the catalog order but no longer picks the lead. Quotes and
    display sorting are absent. A pool without a comparable revision keeps the
    canonical legacy preference (its first row) unless ``require_comparable``
    is set, in which case it gets no lead. Explicit revision anchors restrict a
    publication fallback to rows from that exact original cohort; an unknown
    binding admits no fallback.
    """
    grouped = {}
    for row in rows:
        grouped.setdefault(consumer_event_identity(row), []).append(row)
    anchors = {consumer_event_identity(row): row for row in revision_anchors or ()}
    anchored = revision_anchors is not None
    def revision(row):
        binding = _role_binding(row)
        clocks = tuple(_clock(getattr(row, field, None)) for field in (
            'scheduled_start', 'modeled_at', 'input_cutoff_at'))
        model, policy = getattr(row, 'model_version', None), getattr(row, 'policy_version', None)
        if (not binding or binding[0] == 'invalid' or any(clock is None for clock in clocks)
                or not isinstance(model, str) or not model.strip()
                or not isinstance(policy, str) or not policy.strip()):
            return None
        result = (binding, *clocks, model, policy,
                  getattr(row, 'model_scope', None), getattr(row, 'model_eligible', None))
        # Preserve the original unanchored producer contract. A publication
        # fallback additionally requires the original native source identity.
        return result + tuple(getattr(row, field, None) for field in (
            'fixture_id', 'fixture_source', 'provider_event_id')) if anchored else result
    leads = []
    for pool in grouped.values():
        first = anchors.get(consumer_event_identity(pool[0])) if anchored else pool[0]
        if first is None:
            continue
        current_revision = revision(first)
        comparable = [row for row in pool if current_revision is not None and revision(row) == current_revision
                      and _model_probability(row) is not None]
        if not comparable and (anchored or require_comparable):
            continue
        lead = min(comparable, key=lambda row: (
            -_model_probability(row), _stable_key(row)
        )) if comparable else first
        leads.append(lead)
    return leads


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
        retained = getattr(row, 'model_eligible', None)
        return retained if retained is not None else not forecast_highlight_reason(
            row, now=current, check_context=False)
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
