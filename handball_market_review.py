"""Paired, contemporaneous 1X2 research on frozen Handball receipts."""

from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from math import isclose, log
from statistics import fmean

from betting_math import BettingMathError, proportional_no_vig_market
from scanners.api_handball import MAX_PRICE_AGE


_OUTCOMES = ('home', 'draw', 'away')
_MATCH_WINDOW = timedelta(hours=1)
_LOG_FLOOR = 1e-15


def _clock(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        time = datetime.fromisoformat(value)
        return time.astimezone(timezone.utc) if time.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _model_probability(values):
    if not isinstance(values, dict) or set(values) != set(_OUTCOMES):
        return None
    ordered = tuple(values[side] for side in _OUTCOMES)
    if (any(type(value) not in (float, int) or not 0 <= value <= 1 for value in ordered)
            or not isclose(sum(ordered), 1., rel_tol=0., abs_tol=1e-6)):
        return None
    return ordered


def _market_probability(books):
    if not isinstance(books, dict) or not books:
        return None
    shares = []
    names = set()
    for book, odds in books.items():
        if (not isinstance(book, str) or not 0 < len(book) <= 160 or book.strip() != book
                or not book.isprintable() or book.casefold() in names
                or not isinstance(odds, (list, tuple)) or len(odds) != 3):
            return None
        try:
            shares.append(proportional_no_vig_market(odds).no_vig_probabilities)
        except (BettingMathError, OverflowError):
            return None
        names.add(book.casefold())
    return tuple(fmean(side) for side in zip(*shares))


def _pair(row):
    """Return one score tuple or an exclusion; these are mutually exclusive."""
    result = row.get('result')
    if result not in _OUTCOMES:
        return 'invalid_result', None
    fixture = row.get('fixture')
    if (not isinstance(fixture, (list, tuple)) or len(fixture) != 5
            or any(type(value) is not int or not 0 < value < 2**63 for value in fixture[:4])
            or fixture[2] == fixture[3]):
        return 'invalid_fixture', None
    p_model = _model_probability(row.get('p'))
    if p_model is None:
        return 'invalid_model', None
    books = row.get('odds')
    if books is None or books == {}:
        return 'missing_price', None
    p_market = _market_probability(books)
    if p_market is None:
        return 'invalid_market', None
    clocks = (row.get('decided_at'), row.get('price_source_at'), row.get('price_observed_at'), fixture[4])
    if any(value is None for value in clocks):
        return 'missing_clock', None
    decided, source, observed, kickoff = (_clock(value) for value in clocks)
    if None in (decided, source, observed, kickoff):
        return 'invalid_clock', None
    if not (decided <= observed < kickoff and source <= observed):
        return 'unmatched_clock', None
    if 'revision_confirmed_at' in row:
        confirmed = _clock(row['revision_confirmed_at'])
        if confirmed is None or confirmed > decided or source < confirmed:
            return 'unmatched_revision_clock', None
    if observed - source >= MAX_PRICE_AGE:
        return 'stale_price', None
    if observed - decided > _MATCH_WINDOW or abs(source - decided) > _MATCH_WINDOW:
        return 'asynchronous', None
    outcome = _OUTCOMES.index(result)
    return None, (kickoff, *_losses(p_model, outcome), *_losses(p_market, outcome))


def _losses(probabilities, outcome):
    brier = sum((p - (index == outcome)) ** 2 for index, p in enumerate(probabilities))
    # A fixed floor keeps the proper-loss report serializable even for p=0.
    # It applies only inside the reported logarithm; neither input is changed.
    log_loss = -log(max(probabilities[outcome], _LOG_FLOOR))
    return brier, log_loss


def review_handball_market(forecasts: Iterable[dict]) -> dict:
    """Score exact regulation outcomes paired to saved first prematch markets.

    The caller supplies only the current revision per event; superseded
    forecasts and quote display receipts are not eligible inputs. An absent
    result means unsettled and does not enter either score or exclusions.
    """
    exclusions = Counter()
    pairs = []
    for row in forecasts:
        if not isinstance(row, dict):
            exclusions['invalid_forecast'] += 1
        elif 'result' in row:
            reason, pair = _pair(row)
            if pair is None:
                exclusions[reason] += 1
            else:
                pairs.append(pair)
    starts, brier_model, log_model, brier_market, log_market = zip(*pairs) if pairs else ((),) * 5
    return {
        'paired': len(pairs),
        'model_brier': fmean(brier_model) if pairs else None,
        'market_brier': fmean(brier_market) if pairs else None,
        'model_log_loss': fmean(log_model) if pairs else None,
        'market_log_loss': fmean(log_market) if pairs else None,
        'first_paired_kickoff': min(starts).isoformat() if pairs else None,
        'last_paired_kickoff': max(starts).isoformat() if pairs else None,
        'exclusions': dict(sorted(exclusions.items())),
    }
