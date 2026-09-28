"""Short selected-market facts from immutable football card evidence only.

No history fetch, new model, prose parsing or ranking. Saved form sample sizes
are not win/draw/loss records; league-market benchmarks are not team form.
"""
from dataclasses import dataclass

from challenge_engine import MARKET_BY_KEY
from forecast_analysis import _contract, _decimal, _percent, _rate_copy, read_football_analysis


@dataclass(frozen=True)
class FootballCustomerAnalysis:
    summary: str
    counterargument: str
    facts: tuple[tuple[str, str], ...] = ()
    details: tuple[str, ...] = ()


def football_customer_analysis(signal, *, now):
    """Return selected-market summary/counter, fact pairs and plain details.

    ``None`` means that no exact-bound supported rate can be presented. The
    rendering caller owns HTML escaping. Context cautions stay with the shared
    context formatter; this helper never treats missing history as zero losses.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('customer evidence requires an aware clock')
    if str(signal.sport or '').casefold().replace('ß', 'ss') not in ('fussball', 'football'):
        return None
    evidence = read_football_analysis(vars(signal), now=now)
    spec = MARKET_BY_KEY.get(signal.market_key)
    if evidence is None or spec is None:
        return None
    basis = evidence['basis']
    home, away = signal.home_team, signal.away_team
    rates = _rate_copy(spec, basis, home, away)
    if not rates:
        return None
    contract, counter = _contract(spec, home, away)
    summary = f'{rates}; {contract}: {_percent(signal.probability)} im Modell.'
    caution = f'Gegenargument – {counter}: {_percent(1-signal.probability)} im Modell.'
    left, right = basis.get('expected_home_goals'), basis.get('expected_away_goals')
    # Describe the actual opposing model feature, not just the event complement.
    # Side orientation is essential for X2/1X and weaker outright winners.
    opposing_side = {'RESULT_HOME': 'away', 'RESULT_AWAY': 'home',
                     'DC_1X': 'away', 'DC_X2': 'home'}.get(spec.key)
    if opposing_side and left is not None and right is not None:
        other, own, opponent = (left, right, home) if opposing_side == 'home' else (right, left, away)
        if other > own:
            caution = (f'{opponent} hat die höhere Torprognose '
                       f'({_decimal(other)} gegenüber {_decimal(own)}); {caution}')
        else:
            caution = f'{opponent} bleibt mit {_decimal(other)} erwarteten Toren im Modell berücksichtigt; {caution}'
    elif spec.key == 'RESULT_DRAW' and left is not None and right is not None and left != right:
        stronger, expected = (home, left) if left > right else (away, right)
        caution = f'Die Torprognosen sind nicht gleich; {stronger} liegt mit {_decimal(expected)} höher. {caution}'
    elif spec.key == 'BTTS_YES' and left is not None and right is not None:
        lower, expected = (home, left) if left <= right else (away, right)
        caution = f'{lower} hat die niedrigere Torprognose ({_decimal(expected)}); ein torloses Team genügt zum Scheitern. {caution}'
    facts = []
    form = basis.get('form_samples')
    if form:
        facts.append(('Formbasis', f'{form[0]} / {form[1]} erfasste Spiele'))
    details = ('Sieg-/Remis-/Niederlagenbilanz nicht hinterlegt; Gegner der letzten Spiele sind in diesem Kartenstand nicht gespeichert.',)
    return FootballCustomerAnalysis(summary, caution, tuple(facts), details)
