"""Detached presentation facts from the same consumed inputs, never model inputs.

No provider requests, probability calculation, rank/quote rules or source reads.
Raw opponent IDs are not opponent strengths. Hockey model regulation scores
are not final scores; only a matched original raw result may supply the latter.
"""
from collections.abc import Mapping
from datetime import datetime, timezone
import math
import re
from types import MappingProxyType
import unicodedata


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


def _legacy_team_recent_facts(original):
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


_TEAM_RECENT_KEYS = frozenset(('schema', 'sport', 'provider', 'competition',
    'provider_event_id', 'starts_at', 'modeled_at', 'input_cutoff_at',
    'source_input_hash', 'competitor_a_id', 'competitor_b_id',
    'competitor_a', 'competitor_b', 'scope', 'a_results', 'b_results'))
_TEAM_RESULT_KEYS = frozenset(('event_id', 'start', 'result_observed_at',
    'team_identity', 'opponent_identity', 'won', 'opponent', 'opponent_id', 'score', 'scope'))
_FINAL_SCOPES = {'basketball': 'final_including_ot', 'ice_hockey': 'final_including_ot_so'}


def _label(value):
    return str(value).strip() if value is not None and not isinstance(value, bool) else ''


def _identity_token(team_id, name):
    value = _label(team_id) or _label(name)
    normalized = ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
    return ('id:' if _label(team_id) else 'name:') + normalized


def team_recent_facts(original):
    """Project only the actual normalized consumed inventory into typed facts.

    Legacy duck-typed helper inputs retain their old display-only contract;
    they cannot pass the v2 validator used by persisted snapshots.
    """
    from sports_prematch import OriginalPrematch, _text, _team, _competition, _variant, _SCOPES
    if not isinstance(original, OriginalPrematch):
        return _legacy_team_recent_facts(original)
    sport, identity = original.sport, original.identity
    if sport not in _FINAL_SCOPES or identity is None or not _hash(original.input_hash):
        return None
    event, modeled = original.raw_event, original.as_of
    if _clock(modeled) is None:
        return None
    scope = _FINAL_SCOPES[sport]
    result = dict(schema='team-recent-results-v2', sport=sport,
        provider=_label(event.get('provider') or event.get('source')),
        competition=_label(event.get('competition') or event.get('league') or event.get('tournament')) or sport,
        provider_event_id=_label(event.get('provider_event_id') or event.get('event_id') or
            event.get('game_id') or event.get('match_id') or event.get('id')),
        starts_at=identity.start.isoformat(), modeled_at=modeled.isoformat(),
        input_cutoff_at=modeled.isoformat(), source_input_hash=original.input_hash,
        competitor_a=_label(event.get('home_team', event.get('team1'))),
        competitor_b=_label(event.get('away_team', event.get('team2'))),
        competitor_a_id=_label(event.get('home_team_id', event.get('team1_id'))),
        competitor_b_id=_label(event.get('away_team_id', event.get('team2_id'))), scope=scope)
    matches = sorted(original.matches, key=lambda row: (row.start, row.event_id), reverse=True)
    for side, output in (('home', 'a_results'), ('away', 'b_results')):
        team, rows = getattr(identity, side), []
        for match in matches:
            if team not in {match.home, match.away}:
                continue
            is_home = team == match.home
            won = match.winner_home == (1 if is_home else 0)
            item = dict(event_id=match.event_id, start=match.start.isoformat(),
                result_observed_at=match.observed.isoformat(), team_identity=team,
                opponent_identity=match.away if is_home else match.home,
                won=won, opponent=None, opponent_id=None, score=None, scope=scope)
            raw_matches = [raw for raw in original.raw_history if isinstance(raw, Mapping)
                and _text(raw.get('provider') or raw.get('source')) == identity.provider
                and _competition(raw) == identity.competition and _variant(sport, raw) == identity.variant
                and (not _text(raw.get('sport')) or _text(raw.get('sport')) == sport)
                and _text(raw.get('provider_event_id') or raw.get('event_id') or raw.get('id')) == match.event_id
                and _clock(raw.get('start_time') or raw.get('starts_at')) == match.start
                and _clock(raw.get('result_observed_at') or raw.get('observed_at')) == match.observed
                and _team(raw, 'home') == match.home and _team(raw, 'away') == match.away
                and _text(raw.get('winner_side')) == ('home' if match.winner_home else 'away')
                and _text(raw.get('status')) in {'completed', 'final', 'finished', 'closed', 'ended'}
                and _text(raw.get('result_scope')) == _SCOPES[sport]]
            # Repeated identical accepted source rows are not ambiguous details.
            candidates = set()
            for raw in raw_matches:
                opposite = 'away' if is_home else 'home'
                name, native_id = raw.get(opposite+'_team'), raw.get(opposite+'_team_id')
                name = name.strip() if isinstance(name, str) and 0 < len(name.strip()) <= 100 else None
                native_id = _label(native_id) or None
                hs, aws = raw.get('home_score_final', raw.get('home_score')), raw.get('away_score_final', raw.get('away_score'))
                score = None
                if all(_number(v) and 0 <= v <= 1000 and v == int(v) for v in (hs, aws)):
                    h, a = int(hs), int(aws)
                    period = _text(raw.get('last_period_type'))
                    adjusted = (h-int(match.winner_home), a-int(not match.winner_home)) if sport == 'ice_hockey' and match.extra_time else (h, a)
                    if (h != a and (h > a) == bool(match.winner_home)
                            and adjusted == (match.home_score, match.away_score)
                            and (sport != 'ice_hockey' or period in ({'ot', 'so'} if match.extra_time else {'reg'}))):
                        score = f'{h}:{a}' if is_home else f'{a}:{h}'
                candidates.add((name, native_id, score))
            if len(candidates) == 1:
                item['opponent'], item['opponent_id'], item['score'] = candidates.pop()
            rows.append(item)
            if len(rows) == 10:
                break
        result[output] = rows
    return result


def validate_team_recent_results(payload, forecast, *, competition=None, input_cutoff_at=None):
    """Validate a closed same-call contract and return owned JSON values.

    The owning snapshot additionally binds this payload's digest. No probability
    is calculated and no external history is consulted at this boundary.
    """
    if not isinstance(payload, Mapping) or set(payload) != _TEAM_RECENT_KEYS:
        raise ValueError('invalid team recent-results schema')
    sport = _get(forecast, 'sport')
    if payload['schema'] != 'team-recent-results-v2' or sport not in _FINAL_SCOPES:
        raise ValueError('unsupported team recent-results contract')
    expected = dict(sport=sport, provider=_get(forecast, 'provider'),
        provider_event_id=_get(forecast, 'provider_event_id'),
        competitor_a_id=_get(forecast, 'home_id'), competitor_b_id=_get(forecast, 'away_id'),
        competitor_a=_get(forecast, 'home'), competitor_b=_get(forecast, 'away'),
        source_input_hash=_get(forecast, 'model_input_hash'), scope=_FINAL_SCOPES[sport])
    if any(payload[key] != value for key, value in expected.items()) or not _hash(payload['source_input_hash']):
        raise ValueError('recent results identity does not match forecast')
    for name in ('provider', 'competition', 'provider_event_id', 'competitor_a', 'competitor_b'):
        value = payload[name]
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise ValueError('invalid recent-results identity')
    if any(not isinstance(payload[name], str) or len(payload[name]) > 500 for name in ('competitor_a_id', 'competitor_b_id')):
        raise ValueError('invalid recent-results participant IDs')
    if competition is not None and payload['competition'] != competition:
        raise ValueError('recent results competition does not match snapshot')
    clocks = {key: _clock(payload[key]) for key in ('starts_at', 'modeled_at', 'input_cutoff_at')}
    start, modeled, cutoff = (clocks[key] for key in ('starts_at', 'modeled_at', 'input_cutoff_at'))
    if (any(value is None for value in clocks.values())
            or any(not isinstance(payload[key], str) for key in clocks)
            or start != _clock(_get(forecast, 'starts_at')) or modeled != _clock(_get(forecast, 'modeled_at'))
            or cutoff != _clock(input_cutoff_at if input_cutoff_at is not None else _get(forecast, 'modeled_at'))
            or not cutoff <= modeled < start):
        raise ValueError('recent results chronology does not match snapshot')
    expected_model_scope = 'including_overtime_shootout' if sport == 'ice_hockey' else 'including_overtime'
    if _get(forecast, 'model_scope') != expected_model_scope:
        raise ValueError('recent results scope does not match forecast')
    result = dict(payload)
    shared = {}
    for side, count_field in (('a', 'home_games'), ('b', 'away_games')):
        rows = payload[side+'_results']
        count = _get(forecast, count_field)
        if (not isinstance(rows, (list, tuple)) or len(rows) > 10
                or type(count) is not int or count < len(rows)):
            raise ValueError('invalid recent-results sample size')
        team = _identity_token(payload['competitor_'+side+'_id'], payload['competitor_'+side])
        previous, seen, copied = None, set(), []
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != _TEAM_RESULT_KEYS:
                raise ValueError('invalid closed recent-result row')
            event_id = row['event_id']
            played, observed = _clock(row['start']), _clock(row['result_observed_at'])
            if (not isinstance(event_id, str) or not 0 < len(event_id) <= 500
                    or event_id in seen or event_id == _label(payload['provider_event_id']).casefold()
                    or not isinstance(row['start'], str) or not isinstance(row['result_observed_at'], str)
                    or played is None or observed is None or not played < observed < cutoff
                    or previous is not None and played > previous
                    or type(row['won']) is not bool or row['team_identity'] != team
                    or row['scope'] != payload['scope']):
                raise ValueError('invalid recent-result identity/chronology')
            opponent = row['opponent_identity']
            if (not isinstance(opponent, str) or len(opponent) > 505
                    or not re.fullmatch(r'(?:id|name):\S(?:.*\S)?', opponent) or opponent == team):
                raise ValueError('invalid result opponent identity')
            name, native_id, score = row['opponent'], row['opponent_id'], row['score']
            if name is not None and (not isinstance(name, str) or not 0 < len(name.strip()) <= 100):
                raise ValueError('invalid result opponent label')
            if native_id is not None and (not isinstance(native_id, str) or not 0 < len(native_id.strip()) <= 500):
                raise ValueError('invalid result opponent ID')
            if native_id is not None and _identity_token(native_id, '') != opponent:
                raise ValueError('result opponent ID mismatch')
            if opponent.startswith('name:') and name is not None and _identity_token('', name) != opponent:
                raise ValueError('result opponent name mismatch')
            if score is not None:
                match = re.fullmatch(r'(0|[1-9][0-9]{0,3}):(0|[1-9][0-9]{0,3})', score) if isinstance(score, str) else None
                if match is None:
                    raise ValueError('invalid final score')
                own, other = map(int, match.groups())
                if max(own, other) > 1000 or own == other or (own > other) != row['won']:
                    raise ValueError('contradictory final score')
            latest = _clock(_get(forecast, 'latest_result_observed_at'))
            if latest is not None and observed > latest:
                raise ValueError('row was not consumed by forecast')
            other_row = shared.get(event_id)
            if other_row is not None and (row['team_identity'] != other_row['opponent_identity']
                    or opponent != other_row['team_identity'] or row['won'] == other_row['won']
                    or row['start'] != other_row['start'] or row['result_observed_at'] != other_row['result_observed_at']
                    or score is not None and other_row['score'] is not None and score != ':'.join(reversed(other_row['score'].split(':')))):
                raise ValueError('inconsistent shared result')
            shared[event_id] = row
            seen.add(event_id)
            previous = played
            copied.append(dict(row))
        result[side+'_results'] = copied
    return result


def freeze_team_recent_results(payload, forecast, **bindings):
    """Deeply own the validated bounded evidence for immutable domain use."""
    checked = validate_team_recent_results(payload, forecast, **bindings)
    return MappingProxyType({key: tuple(MappingProxyType(row) for row in value)
        if key in {'a_results', 'b_results'} else value for key, value in checked.items()})


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


def _hockey_goal_reason(factors, a, b, chosen):
    """Translate only the exact saved regulation-goal factor, never free prose."""
    if not isinstance(factors, (list, tuple)) or not factors:
        return ()
    factor = factors[0]
    match = re.fullmatch(
        r'Erwartete Tore in regulärer Spielzeit: ([0-9]+\.[0-9]{2})/([0-9]+\.[0-9]{2})\.',
        factor,
    ) if isinstance(factor, str) and len(factor) <= 220 else None
    if match is None:
        return ()
    home, away = (float(value) for value in match.groups())
    if not all(math.isfinite(value) and 0 <= value <= 30 for value in (home, away)):
        return ()
    selected, other = (home, away) if chosen == a else (away, home)
    opponent = b if chosen == a else a
    if selected == other:
        text = (f'{chosen} und {opponent} liegen in der Torprognose gleichauf: '
                f'je {_decimal(selected, 2)} erwartete Tore in regulärer Spielzeit.')
    else:
        relation = 'vor' if selected > other else 'hinter'
        text = (f'{chosen} liegt mit {_decimal(selected, 2)} erwarteten Toren in regulärer Spielzeit '
                f'{relation} {opponent} mit {_decimal(other, 2)} '
                f'– ein Unterschied von {_decimal(abs(selected-other), 2)} Toren.')
    return (text, 'Die Siegschätzung umfasst auch Verlängerung und Penaltyschießen.')


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
    display_a, display_b = a, b
    if sport in {'eishockey', 'icehockey'}:
        from sports_identity_media import participant_display_name
        display_a, display_b = (participant_display_name('ice_hockey', name,
            team_id=_get(signal, field), fixture_source=_get(signal, 'fixture_source'),
            competition=_get(signal, 'competition'))
            for name, field in ((a, 'competitor_a_id'), (b, 'competitor_b_id')))
    display_chosen = display_a if chosen == a else display_b
    counter = f'{display_b if chosen == a else display_a}: {_decimal((1-p)*100)} % modellierte Gegenchance.'
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
        if expected_sport == 'ice_hockey':
            reasons = _hockey_goal_reason(factors, display_a, display_b, display_chosen)
        elif isinstance(factors, (list, tuple)):
            reasons = tuple(value for value in factors[:2] if isinstance(value, str) and len(value) <= 220 and value.startswith(prefixes))
        facts = _mapping(recent_facts or snapshot.get('customer_recent_results'))
        if facts.get('schema') == 'team-recent-results-v2':
            try:
                validated = validate_team_recent_results(facts, forecast,
                    competition=snapshot.get('competition', _get(signal, 'competition')),
                    input_cutoff_at=snapshot.get('input_cutoff_at', forecast.get('modeled_at')))
            except (ValueError, TypeError, AttributeError):
                facts = {}
            else:
                recent = _recent_lines(validated, team=True)
                recent_counter = team_recent_counters(validated).get('home' if chosen == a else 'away')
                if recent_counter:
                    counter = recent_counter+' '+counter
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
