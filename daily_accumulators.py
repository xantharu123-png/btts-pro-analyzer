"""Daily multi-event model selections. No API, persistence, prices in the score or stakes."""
from collections import Counter
from datetime import date, datetime, timezone
from itertools import chain
import logging
from math import isfinite, prod
from zoneinfo import ZoneInfo

from daily3_identity import event_guard
from daily_accumulator_prices import point_fetch
from forecast_analysis import build_forecast_analysis, forecast_highlight_reason
from forecast_selection import select_consumer_forecasts
from market_consensus import (
    FLOOR_BASIS_MODEL, MarketConsensus, ODDS_API_REFERENCE_SOURCE, REFERENCE_FETCH_MAX_AGE,
    REFERENCE_QUOTE_MAX_AGE, REFERENCE_SOURCE, quote_matches_candidate,
    quote_below_publication_floor, wettfinder_reference_price_status,
)
from tip_publication import compact_signal_row

_ZURICH = ZoneInfo("Europe/Zurich")
_BOOK_PREFIX = {REFERENCE_SOURCE: "api-football:", ODDS_API_REFERENCE_SOURCE: "odds-api:"}
_FLOOR = 1.20
_NODE_LIMIT = 75_000
_SPORTS = {"fussball":"football", "football":"football", "tennis":"tennis",
           "e-sport":"esports", "esports":"esports", "basketball":"basketball",
           "eishockey":"ice_hockey", "ice_hockey":"ice_hockey", "cricket":"cricket"}


def _clock(value):
    try:
        t = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        return t.astimezone(timezone.utc) if t.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _name(text):
    return ' '.join(str(text or '').casefold().split())


def offer_is_current(offer, *, as_of):
    """Recheck both original clocks; neither publication time nor page views renew one."""
    now = _clock(as_of)
    observed, fetched = _clock(offer.get('observed_at')), _clock(offer.get('fetched_at'))
    odds = offer.get('odds')
    return (now is not None and observed is not None and fetched is not None
            and observed <= fetched <= now and now-observed <= REFERENCE_QUOTE_MAX_AGE
            and now-fetched <= REFERENCE_FETCH_MAX_AGE and type(odds) in (int,float)
            and isfinite(odds) and odds >= _FLOOR)


def _exact_quote(signal):
    quote = MarketConsensus.from_dict(signal.reference_quote)
    if quote is None or not quote_matches_candidate(quote, signal) or not _clock(quote.scheduled_start):
        return None
    # API-Football's odds endpoint binds by fixture ID; when names ARE delivered
    # they must not contradict the model's participants either.
    if quote.source == REFERENCE_SOURCE and (
            (quote.event_home and _name(quote.event_home) != _name(signal.home_team))
            or (quote.event_away and _name(quote.event_away) != _name(signal.away_team))):
        return None
    return quote


def _offers(quote, now):
    prefix = _BOOK_PREFIX.get(quote.source) if quote is not None else None
    bundle_at = _clock(quote.fetched_at) if prefix else None
    if bundle_at is None or bundle_at > now:
        return {}
    offers = {}
    for point in quote.points:
        book = str(point.bookmaker_id or '')
        offer = dict(odds=point.odds, observed_at=point.observed_at, fetched_at=point_fetch(quote, point))
        if book.startswith(prefix) and book[len(prefix):].strip() and offer_is_current(offer, as_of=now):
            offers[book] = offer
    return offers


def eligible_combo_legs(signals, *, as_of, target_day, public=False):
    """Already published coherent models for today's not-yet-started games.

    A stale/missing offer may still yield an internal research leg; never a
    freshly quoted leg. Caller binds original forecast IDs before archival.
    """
    now = _clock(as_of)
    day = date.fromisoformat(target_day) if isinstance(target_day, str) else target_day
    if not now or day != now.astimezone(_ZURICH).date():
        return []
    from ev_signal_sources import ModelSignal
    inputs, analyses = [], {}
    for s in signals:
        if not isinstance(s, ModelSignal):
            continue
        start, modeled, cutoff = _clock(s.scheduled_start), _clock(s.modeled_at), _clock(s.input_cutoff_at)
        if (start and start > now and start.astimezone(_ZURICH).date() == day
                and modeled and cutoff and cutoff <= modeled <= now and s.model_version
                and s.event_label and s.key and s.market_key and s.selection):
            try:
                analyses[id(s)] = build_forecast_analysis(s, now=now)
            except (TypeError, ValueError, AttributeError, KeyError, ArithmeticError):
                continue
            inputs.append(s)
    legs = []
    for s in select_consumer_forecasts(inputs, now=now):
        try:
            leg = _eligible_leg(s, now, analyses[id(s)], public=public)
        except (TypeError, ValueError, AttributeError, KeyError, ArithmeticError):
            continue
        if leg is not None:
            legs.append(leg)
    return sorted(legs, key=_rank)


def _eligible_leg(s, now, analysis, *, public):
    if forecast_highlight_reason(s, now=now, analysis=analysis):
        return None
    row = compact_signal_row(s, featured_role="catalogue")
    native, sport = row.get('event_key'), _SPORTS.get(_name(s.sport))
    if not native or not sport:
        return None
    names = [s.home_team or s.competitor_a, s.away_team or s.competitor_b]
    ids = [s.home_team_id or s.competitor_a_id, s.away_team_id or s.competitor_b_id]
    if not all(names) or _name(names[0]) == _name(names[1]) or (any(ids) and (not all(ids) or ids[0] == ids[1])):
        return None
    name_keys = [f"{sport}:name:{_name(n)}" for n in names]
    participants = ([f"{sport}:id:{s.fixture_source or sport}:{i}" for i in ids]
                    if all(ids) else name_keys.copy())
    if sport == 'tennis':
        # Only exclusion tokens, never a positive join for a quote, model or
        # outcome. Two homonymous players may conservatively lose a slot.
        from tennis.data_loader import normalize_player_name
        from market_consensus import _tennis_identity_name
        for name in names:
            for kind, token in (('roster', normalize_player_name(name)), ('words', _tennis_identity_name(name))):
                if token:
                    name_keys.append(f"tennis:{kind}:{token}")
    quote = _exact_quote(s)
    if quote_below_publication_floor(quote, candidate=s, now=now):
        return None
    price_status = wettfinder_reference_price_status(quote, None, candidate=s, now=now)
    # A below-floor price or derived range is excluded. Without any price the
    # model-only arm can still be measured; no eligibility for the priced arm.
    if price_status.code == "BELOW_FLOOR" and (public or price_status.market_basis != FLOOR_BASIS_MODEL):
        return None
    return dict(event_key=native, aliases=event_guard(s)['aliases'], sport=sport,
                participants=participants, participant_names=name_keys, market_key=s.market_key,
                evidence_selection=row.get("selection_key") or row.get("selected_competitor") or row["selection"],
                selection=s.selection, event_label=s.event_label, probability=s.probability,
                starts_at=_clock(s.scheduled_start).isoformat(), signal_key=s.key,
                reason=analysis.basis, fixture_id=s.fixture_id, model_version=s.model_version,
                offers=_offers(quote, now))


def _rank(leg):
    return (-leg['probability'], leg['event_key'], leg['market_key'], leg['selection'], leg['signal_key'])


def _events(leg):
    return {leg['event_key'], *leg.get('aliases', ())}


def _same_side(left, right):
    return (all(left[k] == right[k] for k in ('event_key', 'market_key', 'selection', 'participants'))
            and left.get('evidence_selection') == right.get('evidence_selection'))


def _ticket(legs, books, reference_probability):
    return dict(size=len(legs), legs=sorted(legs, key=lambda leg:(leg['starts_at'],_rank(leg))),
                bookmaker_id=min(books) if books else None, reference_probability=reference_probability,
                price_status='confirmed' if books else 'unconfirmed')


def _public_family(leg):
    market = leg["market_key"]
    if leg["sport"] != "football":
        return "result" if market == "H2H" else "other"
    from challenge_engine import MARKET_BY_KEY

    spec = MARKET_BY_KEY.get(market)
    kind = spec.kind if spec is not None else None
    if kind in {"total", "team_total", "team_range", "total_range", "btts"} or market == "MIXED_BTTS_OR_OVER_2_5":
        return "goals"
    if kind in {"result", "double_chance"}:
        return "result"
    if kind in {"result_total", "mixed_or"}:
        return "result_and_goals"
    if kind in {"corner_total", "team_corners"}:
        return "corners"
    if kind in {"yellow_total", "team_yellow"}:
        return "cards"
    return "other"


def _best(pool, size, prior, confirmed, joint_score=None, *, diversify=False):
    # Public slips reserve all earlier fixtures. The research comparators keep
    # their original overlap policy so the historical baseline does not change.
    reserved = {event for s in prior for old in s["legs"] for event in _events(old)} if diversify else set()
    ranked = []
    for leg in pool:
        events = _events(leg)
        if events & reserved:
            continue
        hits = [] if diversify else [(i,old) for i,s in enumerate(prior) for old in s['legs'] if events & _events(old)]
        if len(hits) > 1 or any(not _same_side(old, leg) for _,old in hits):
            continue
        people = set(chain(leg['participants'], leg.get('participant_names', ())))
        books = frozenset(leg['offers'])
        if not confirmed or books:
            ranked.append((leg, events, people, {i for i,_ in hits}, books,
                           _public_family(leg) if diversify else None))
    family_cap = max(2, size // 2)
    if diversify and sum(min(n, family_cap) for n in Counter(r[-1] for r in ranked).values()) < size:
        return None
    used_families = Counter()
    best, score, nodes = None, -1., 0

    class Limit(Exception):
        pass

    def diverse_upper(start, remaining, p):
        # Best suffix under family caps alone. Ignoring event/person conflicts
        # is optimistic, so this cannot prune a better feasible solution.
        quotas = used_families.copy()
        for i in range(start, len(ranked)):
            leg, *_, family = ranked[i]
            if quotas[family] < family_cap:
                p *= leg["probability"]
                quotas[family] += 1
                remaining -= 1
                if not remaining:
                    return p
        return 0.

    def visit(start, picked, p, used, people, overlaps, books):
        nonlocal best, score, nodes
        remaining = size-len(picked)
        if not remaining:
            if joint_score is None:
                if p > score:
                    best, score = _ticket(picked, books, p), p
                return
            slip = _ticket(picked, books, p)
            calibrated = joint_score(slip)
            if type(calibrated) in (float, int) and 0 < calibrated < 1 and calibrated > score:
                best, score = dict(slip, calibrated_probability=calibrated), calibrated
            return
        for i in range(start, len(ranked)-remaining+1):
            leg, events, participants, shared, offered, family = ranked[i]
            if diversify and used_families[family] >= family_cap:
                continue
            nodes += 1
            if nodes > _NODE_LIMIT:
                raise Limit
            # Full-precision optimistic product, with the identical sequence
            # of multiplications as a completed path (not a log-score).
            # A product bound is not an upper bound for a calibrated model.
            if joint_score is None:
                upper = (diverse_upper(i, remaining, p) if diversify else
                         prod((ranked[j][0]['probability'] for j in range(i,i+remaining)), start=p))
                if upper <= max(score, 0.):
                    break
            if used & events or people & participants or overlaps & shared:
                continue
            common = offered if books is None else books & offered
            if confirmed and not common:
                continue
            if diversify:
                used_families[family] += 1
            visit(i+1, picked+[leg], p*leg['probability'], used|events, people|participants,
                  overlaps|shared, common)
            if diversify:
                used_families[family] -= 1

    try:
        visit(0, [], 1., set(), set(), set(), None)
    except Limit:
        logging.getLogger(__name__).info("Accumulator size %d omitted: optimality search limit", size)
        return None  # No unproven incumbent as an optimum.
    return best


def _select(legs, frozen, confirmed, joint_score=None, *, diversify=False):
    pool = sorted(legs, key=_rank)
    prior = list(frozen)
    result = []
    for size in (3,4,5,6):
        if any(s['size'] == size for s in prior):
            continue
        slip = _best(pool,size,prior,confirmed,joint_score,diversify=diversify)
        if slip is not None:
            prior.append(slip)
            result.append(slip)
    return result


def select_combo_set(legs, *, frozen=()):
    """Sports-only prospective arm. Even absent prices do not change its ranks."""
    return _select(legs, frozen, False)


def select_public_combo_set(legs, *, frozen=()):
    """Only new public slips diversify; already published plays and odds never change."""
    return _select(legs, frozen, False, diversify=True)


def select_confirmed_combo_set(legs, *, frozen=()):
    """Matched reference arm: search ALL potential sets with a shared fresh book."""
    return _select(legs, frozen, True)


def select_calibrated_combo_set(legs, *, frozen=(), score):
    """Proven maximum of the approved whole-slip model, not the reference product.

    The score must use only the sport/model inputs, never the bookmaker/odds.
    No comparable score or an exhausted budget leaves the size unpublished.
    """
    if not callable(score):
        return []
    return _select(legs, frozen, True, score)
