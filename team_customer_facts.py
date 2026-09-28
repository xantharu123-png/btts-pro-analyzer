"""Detached presentation facts from the same consumed inputs, never model inputs.

No provider requests, probability calculation, rank/quote rules or source reads.
Raw opponent IDs are not opponent strengths. Hockey model regulation scores
are not final scores; only a matched original raw result may supply the latter.
"""
from collections.abc import Mapping
from datetime import datetime, timezone
import math
import re


def _get(value, name, default=None):
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _clock(value):
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo is not None else None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None


def _decimal(value, digits=1):
    return f'{value:.{digits}f}'.replace('.', ',')


def esports_recent_facts(match, original):
    """Copy at most 10 real outcomes at this model call's consumed positions."""
    positions = _mapping(_mapping(original.get('consumed')).get('history_indices'))
    source_hash = original.get('inputs_hash')
    if not _hash(source_hash):
        return None
    result = {'schema': 'esports-recent-results-v1', 'provider_event_id': str(match.get('id')),
              'source_input_hash': source_hash, 'competitor_a': match.get('team1'),
              'competitor_b': match.get('team2')}
    for side, output in (('team1', 'a_results'), ('team2', 'b_results')):
        history, indices = match.get(side + '_history'), positions.get(side)
        if not isinstance(history, list) or not isinstance(indices, list) or len(indices) < 5:
            return None
        if len(indices) != len(set(str(index) for index in indices)):
            return None
        outcomes = []
        for index in indices[:10]:
            if type(index) is not int or not 0 <= index < len(history):
                return None
            won = _mapping(history[index]).get('won')
            if type(won) is not bool:
                return None
            outcomes.append(won)
        result[output] = outcomes
    return result


def team_recent_facts(original):
    """Build an optional sidecar after prediction without modifying originals.

Only normalized consumed matches are eligible. Final scores/names come from
the raw row with the identical event ID, kickoff and observed-result clock.
Missing or ambiguous raw rows retain outcome only, not invented final scores.
"""
    sport, identity = _get(original, 'sport'), _get(original, 'identity')
    source_hash, modeled = _get(original, 'input_hash'), _clock(_get(original, 'as_of'))
    if sport not in {'basketball', 'ice_hockey'} or identity is None or not _hash(source_hash) or modeled is None:
        return None
    event = _mapping(_get(original, 'raw_event'))
    result = {'schema': 'team-recent-results-v1', 'sport': sport,
        'provider_event_id': str(_get(identity, 'event_id')), 'modeled_at': modeled.isoformat(),
        'source_input_hash': source_hash, 'competitor_a': event.get('home_team'),
        'competitor_b': event.get('away_team')}
    matches = sorted(_get(original, 'matches', ()), key=lambda row: _get(row, 'start'), reverse=True)
    for side, output in (('home', 'a_results'), ('away', 'b_results')):
        team = _get(identity, side)
        rows = []
        for match in matches:
            if team not in {_get(match, 'home'), _get(match, 'away')}:
                continue
            is_home = team == _get(match, 'home')
            won = bool(_get(match, 'winner_home')) if is_home else not bool(_get(match, 'winner_home'))
            item = {'won': won, 'start': _get(match, 'start').isoformat(),
                    'opponent': None, 'score': None, 'scope': 'final_including_ot_so' if sport == 'ice_hockey' else 'final_including_ot'}
            raw_matches = [raw for raw in _get(original, 'raw_history', ()) if isinstance(raw, Mapping)
                and str(raw.get('provider_event_id', raw.get('event_id', ''))) == _get(match, 'event_id')
                and _clock(raw.get('start_time', raw.get('starts_at'))) == _get(match, 'start')
                and _clock(raw.get('result_observed_at')) == _get(match, 'observed')]
            if len(raw_matches) == 1:
                raw = raw_matches[0]
                opponent = raw.get('away_team' if is_home else 'home_team')
                if isinstance(opponent, str) and 0 < len(opponent.strip()) <= 100:
                    item['opponent'] = opponent.strip()
                hs = raw.get('home_score_final', raw.get('home_score'))
                aw = raw.get('away_score_final', raw.get('away_score'))
                if all(_number(v) and 0 <= v <= 1000 and v == int(v) for v in (hs, aw)):
                    item['score'] = f'{int(hs)}:{int(aw)}' if is_home else f'{int(aw)}:{int(hs)}'
            rows.append(item)
            if len(rows) == 10:
                break
        result[output] = rows
    return result


def _recent_lines(facts, *, team=False):
    result = []
    for name, field in ((facts.get('competitor_a'), 'a_results'), (facts.get('competitor_b'), 'b_results')):
        values = facts.get(field)
        if not isinstance(values, (tuple, list)) or not 1 <= len(values) <= 10:
            continue
        outcomes = [_mapping(value).get('won') if team else value for value in values]
        if any(type(won) is not bool for won in outcomes):
            continue
        windows = [f'{sum(outcomes[:n])}/{n} Siege' for n in (5, 10) if len(outcomes) >= n]
        if not windows:
            windows = [f'{sum(outcomes)}/{len(outcomes)} Siege (unvollständige Historie)']
        line = str(name) + ': ' + ' · '.join(windows)
        if team:
            details = []
            for row in values[:5]:
                label = 'S' if row['won'] else 'N'
                if row.get('score'):
                    label += ' ' + str(row['score'])
                if row.get('opponent'):
                    label += ' gegen ' + str(row['opponent'])
                details.append(label)
            line += '; zuletzt: ' + ', '.join(details)
            scopes = {row.get('scope') for row in values}
            if 'final_including_ot_so' in scopes:
                line += ' · Endstände inklusive Verlängerung/Penaltyschießen'
            elif 'final_including_ot' in scopes:
                line += ' · Endstände inklusive Overtime'
        result.append(line)
    return tuple(result)


def team_recent_counters(facts):
    """Selected-side counter from typed same-call last-five outcomes only."""
    result = {}
    first, second = facts.get('a_results'), facts.get('b_results')
    if not all(isinstance(rows, (list, tuple)) and len(rows) >= 5
               and all(isinstance(row, Mapping) and type(row.get('won')) is bool for row in rows[:5])
               for rows in (first, second)):
        return result
    a_wins, b_wins = sum(row['won'] for row in first[:5]), sum(row['won'] for row in second[:5])
    a, b = facts.get('competitor_a'), facts.get('competitor_b')
    if a_wins < b_wins:
        result['home'] = f'Bessere erfasste Kurzform bei {b}: {b_wins}/5 Siege gegenüber {a}: {a_wins}/5. Die Gegner dieser Spiele können unterschiedlich stark gewesen sein.'
    elif b_wins < a_wins:
        result['away'] = f'Bessere erfasste Kurzform bei {a}: {a_wins}/5 Siege gegenüber {b}: {b_wins}/5. Die Gegner dieser Spiele können unterschiedlich stark gewesen sein.'
    return result


def team_customer_explanation(signal, probability=None, *, recent_facts=None):
    """Return reasons/counterpoint/recent tuples for public card formatters."""
    empty = {'reasons': (), 'counterpoint': None, 'recent': ()}
    sport = str(_get(signal, 'sport', '')).casefold().replace('-', '').replace('_', '').replace(' ', '')
    if sport not in {'esport', 'esports', 'basketball', 'eishockey', 'icehockey'}:
        return empty
    a, b, chosen = (_get(signal, field) for field in ('competitor_a', 'competitor_b', 'selected_competitor'))
    p = probability if probability is not None else _get(signal, 'probability')
    if not all(isinstance(name, str) and name.strip() for name in (a, b, chosen)) or a == b or chosen not in (a, b):
        return empty
    if not _number(p) or not 0 <= p <= 1:
        return empty
    counter = f'{b if chosen == a else a}: {_decimal((1-p)*100)} % modellierte Gegenchance.'
    reasons, recent = (), ()
    if sport in {'esport', 'esports'}:
        context = _mapping(_get(signal, 'context_evidence'))
        if (context.get('schema') != 'esports-card-basis-v1'
                or context.get('provider_event_id') != str(_get(signal, 'provider_event_id'))
                or _clock(context.get('modeled_at')) is None
                or _clock(context.get('modeled_at')) != _clock(_get(signal, 'modeled_at'))
                or context.get('competitor_a') != a or context.get('competitor_b') != b):
            return {**empty, 'counterpoint': counter}
        elo_a, elo_b = context.get('elo_a'), context.get('elo_b')
        if all(_number(value) and 0 < value <= 10000 for value in (elo_a, elo_b)):
            advantage = (elo_a-elo_b) if chosen == a else (elo_b-elo_a)
            if advantage > 0:
                reasons = (f'{chosen}: Die längerfristigen Serienergebnisse sprechen im Spielstärkenvergleich für diese Auswahl.',)
            elif advantage < 0:
                counter = f'{chosen} ist im längerfristigen Serienvergleich schwächer; die längerfristigen Serienergebnisse sprechen eher für {b if chosen == a else a}; ' + counter
        facts = _mapping(context.get('recent_results'))
        if (facts.get('schema') == 'esports-recent-results-v1' and _hash(facts.get('source_input_hash'))
                and facts.get('source_input_hash') == context.get('source_input_hash')
                and facts.get('provider_event_id') == context['provider_event_id']
                and facts.get('competitor_a') == a and facts.get('competitor_b') == b
                and all(isinstance(facts.get(field), (list, tuple)) and 5 <= len(facts[field]) <= 10
                        and all(type(value) is bool for value in facts[field])
                        for field in ('a_results', 'b_results'))):
            recent = _recent_lines(facts)
            if recent:
                first, second = facts.get('a_results'), facts.get('b_results')
                if len(first) >= 5 and len(second) >= 5:
                    selected, opposite = (first, second) if chosen == a else (second, first)
                    wins, other_wins = sum(selected[:5]), sum(opposite[:5])
                    form = f'{chosen}: zuletzt {wins}/5 Siege; {b if chosen == a else a}: {other_wins}/5. Gegnerqualität daraus nicht ablesbar.'
                    if wins > other_wins:
                        reasons += (form,)
                    elif wins < other_wins:
                        counter = form + ' ' + counter
    else:
        snapshot = _mapping(_get(signal, 'team_sport_snapshot'))
        forecast = _mapping(snapshot.get('team_sport_forecast'))
        expected_sport = 'basketball' if sport == 'basketball' else 'ice_hockey'
        chosen_p = forecast.get('p_home' if chosen == a else 'p_away')
        if (forecast.get('sport') != expected_sport or forecast.get('model_version') != 'sports-prematch-research-v1'
                or forecast.get('provider_event_id') != str(_get(signal, 'provider_event_id'))
                or _clock(forecast.get('modeled_at')) is None
                or _clock(forecast.get('modeled_at')) != _clock(_get(signal, 'modeled_at'))
                or forecast.get('home') != a or forecast.get('away') != b
                or not _number(chosen_p) or not math.isclose(chosen_p, p, abs_tol=1e-12)
                or forecast.get('missing')):
            return {**empty, 'counterpoint': counter}
        prefixes = ('Gegnerbereinigte erwartete Punktedifferenz Heim–Gast:', 'Aus den Punktedifferenzen geschätzte Streuung:') if sport == 'basketball' else ('Erwartete Tore in regulärer Spielzeit:', 'Verlängerung/Shootout separat aus ')
        factors = forecast.get('factors', ())
        if isinstance(factors, (list, tuple)):
            reasons = tuple(value for value in factors[:2] if isinstance(value, str) and len(value) <= 220 and value.startswith(prefixes))
        facts = _mapping(recent_facts or snapshot.get('customer_recent_results'))
        if (facts.get('schema') == 'team-recent-results-v1' and facts.get('sport') == expected_sport
                and _hash(facts.get('source_input_hash')) and facts.get('source_input_hash') == forecast.get('model_input_hash')
                and facts.get('provider_event_id') == forecast.get('provider_event_id')
                and _clock(facts.get('modeled_at')) == _clock(forecast.get('modeled_at'))
                and facts.get('competitor_a') == a and facts.get('competitor_b') == b):
            recent = _recent_lines(facts, team=True)
            if recent:
                recent_counter = team_recent_counters(facts).get('home' if chosen == a else 'away')
                if recent_counter:
                    counter = recent_counter+' '+counter
        if not recent:
            recent = tuple(factor['summary'] for factor in snapshot.get('factors', ())
                if isinstance(factor, Mapping) and factor.get('factor_key') in {'customer_recent_a', 'customer_recent_b'}
                and factor.get('role') == 'DISPLAY_ONLY'
                and factor.get('source') == 'customer-results:'+str(forecast.get('model_input_hash'))
                and _clock(factor.get('observed_at')) == _clock(forecast.get('modeled_at'))
                and isinstance(factor.get('summary'), str) and len(factor['summary']) <= 600)
            recent_counter = next((factor['summary'] for factor in snapshot.get('factors', ())
                if isinstance(factor, Mapping) and factor.get('factor_key') == 'customer_counter_'+('home' if chosen == a else 'away')
                and factor.get('role') == 'DISPLAY_ONLY'
                and factor.get('source') == 'customer-results:'+str(forecast.get('model_input_hash'))
                and _clock(factor.get('observed_at')) == _clock(forecast.get('modeled_at'))
                and isinstance(factor.get('summary'), str) and len(factor['summary']) <= 600), None)
            if recent_counter:
                counter = recent_counter+' '+counter
    return {'reasons': reasons, 'counterpoint': counter, 'recent': recent}
