"""Short selected-market facts from immutable football card evidence only.

No history fetch, new model, prose parsing or ranking. Saved form sample sizes
are not win/draw/loss records; league-market benchmarks are not team form.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from forecast_analysis import _clock, _mapping

from challenge_engine import MARKET_BY_KEY
from forecast_analysis import _contract, _decimal, _percent, _rate_copy, read_football_analysis


@dataclass(frozen=True)
class FootballCustomerAnalysis:
    summary: str
    counterargument: str
    facts: tuple[tuple[str, str], ...] = ()
    details: tuple[str, ...] = ()
    fact_details: tuple[tuple[str, tuple[str, ...]], ...] = ()
    market_facts: tuple[tuple[str, str], ...] = ()


_RECENT_FIELDS = {'schema', 'fixture_id', 'home_id', 'away_id', 'scheduled_start',
                  'model_scope', 'as_of', 'home', 'away'}
_RESULT_FIELDS = {'fixture_id', 'played_at', 'opponent_id', 'opponent', 'venue',
                  'scored', 'conceded', 'competition'}


def build_football_recent_results(fixture, history, *, as_of, model_scope):
    """Project at most ten results per side from this model's loaded scope.

    No fetch and no new model fit. Negative CSV fixture IDs remain negative;
    raw score histories are not ranked-opponent evidence or native API receipts.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError('recent results require an aware clock')
    meta, teams = _mapping(fixture.get('fixture')), _mapping(fixture.get('teams'))
    start = _clock(meta.get('date'))
    ids = [_mapping(teams.get(side)).get('id') for side in ('home', 'away')]
    fixture_id = meta.get('id')
    if (start is None or type(fixture_id) is not int or fixture_id <= 0
            or any(type(i) is not int or i <= 0 for i in ids) or ids[0] == ids[1]):
        return None
    cutoff = min(as_of.astimezone(timezone.utc), start)
    minimum = cutoff - timedelta(days=730 if model_scope == 'senior_national_pooled' else 365)
    buckets = {i: {} for i in ids}
    conflicts = {i: set() for i in ids}
    versions, ambiguous = {}, set()
    for raw in history:
        if not isinstance(raw, dict):
            continue
        meta, pair, goals = (_mapping(raw.get(k)) for k in ('fixture', 'teams', 'goals'))
        played = _clock(meta.get('date'))
        key = meta.get('id')
        home, away = _mapping(pair.get('home')), _mapping(pair.get('away'))
        score = [goals.get(side) for side in ('home', 'away')]
        status = _mapping(meta.get('status')).get('short')
        # Inspect every loaded revision before the time-window filter. A later
        # reschedule outside that window must invalidate its old FT revision.
        if type(key) is int and key != 0:
            version = (played, home.get('id'), away.get('id'), status,
                       tuple((type(n).__name__, str(n)) for n in score),
                       raw.get('challenge_senior_national_team'))
            if key in versions and version != versions[key]:
                ambiguous.add(key)
            versions[key] = version
        if (type(key) is not int or key == 0 or key == fixture_id or played is None
                or not minimum <= played < cutoff or status != 'FT'
                or any(type(n) is not int or not 0 <= n <= 30 for n in score)
                or any(type(side.get('id')) is not int or side['id'] <= 0 for side in (home, away))
                or home['id'] == away['id']):
            continue
        if model_scope == 'senior_national_pooled' and raw.get('challenge_senior_national_team') is not True:
            continue
        for index, side in enumerate((home, away)):
            team = side['id']
            if team not in buckets:
                continue
            opponent = (away, home)[index]
            name = opponent.get('name')
            competition = _mapping(raw.get('league')).get('name', '')
            if (not isinstance(name, str) or not name.strip() or len(name) > 200
                    or not isinstance(competition, str) or len(competition) > 200):
                continue
            result = {'fixture_id': key, 'played_at': played.isoformat(),
                      'opponent_id': opponent['id'], 'opponent': name.strip(),
                      'venue': ('home', 'away')[index], 'scored': score[index],
                      'conceded': score[1-index], 'competition': competition}
            if key in buckets[team] and buckets[team][key] != result:
                conflicts[team].add(key)
            buckets[team][key] = result
    return {'schema': 'football-recent-results-v1', 'fixture_id': fixture_id,
            'home_id': ids[0], 'away_id': ids[1], 'scheduled_start': start.isoformat(),
            'model_scope': model_scope, 'as_of': cutoff.isoformat(),
            **{side: sorted((r for key, r in buckets[team].items() if key not in conflicts[team] | ambiguous),
                           key=lambda r: (r['played_at'], r['fixture_id']), reverse=True)[:10]
               for side, team in zip(('home', 'away'), ids)}}


def validated_football_recent_results(raw, *, identity):
    """Strict optional display data; never accept a wrong card or later history."""
    if type(raw) is not dict or set(raw) != _RECENT_FIELDS or raw['schema'] != 'football-recent-results-v1':
        return None
    for key in ('fixture_id', 'home_id', 'away_id'):
        if (type(raw[key]) is not int or type(identity.get(key)) is not int
                or raw[key] <= 0 or raw[key] != identity[key]):
            return None
    if any(raw[key] != identity.get(key) for key in ('model_scope', 'scheduled_start')):
        return None
    clock, cutoff = _clock(raw['as_of']), _clock(identity.get('input_cutoff_at'))
    if clock is None or cutoff is None or clock > cutoff:
        return None
    minimum = clock - timedelta(days=730 if raw['model_scope'] == 'senior_national_pooled' else 365)
    for side in ('home', 'away'):
        rows = raw[side]
        if type(rows) is not list or len(rows) > 10:
            return None
        seen, last = set(), clock
        for row in rows:
            if type(row) is not dict or set(row) != _RESULT_FIELDS:
                return None
            key, played = row['fixture_id'], _clock(row['played_at'])
            if (type(key) is not int or key == 0 or key == raw['fixture_id'] or key in seen
                    or played is None or not minimum <= played < clock or played > last
                    or type(row['opponent_id']) is not int or row['opponent_id'] <= 0
                    or row['opponent_id'] == raw[side+'_id'] or row['venue'] not in ('home', 'away')
                    or any(type(row[k]) is not int or not 0 <= row[k] <= 30 for k in ('scored', 'conceded'))
                    or not isinstance(row['opponent'], str) or not row['opponent'].strip() or len(row['opponent']) > 200
                    or not isinstance(row['competition'], str) or len(row['competition']) > 200):
                return None
            seen.add(key)
            last = played
    home_rows = {r['fixture_id']: r for r in raw['home']}
    away_rows = {r['fixture_id']: r for r in raw['away']}
    for key in home_rows.keys() & away_rows.keys():
        home, away = home_rows[key], away_rows[key]
        if (home['opponent_id'] != raw['away_id'] or away['opponent_id'] != raw['home_id']
                or home['venue'] == away['venue']
                or _clock(home['played_at']) != _clock(away['played_at'])
                or home['scored'] != away['conceded'] or home['conceded'] != away['scored']
                or home['competition'] != away['competition']):
            return None
    from copy import deepcopy
    return deepcopy(raw)


def validated_football_recent_map(raw, candidates, *, model_clock):
    """One bounded display projection per native event in a worker result."""
    result = {}
    clock = _clock(model_clock.isoformat() if isinstance(model_clock, datetime) else model_clock)
    if type(raw) is not dict or clock is None:
        return result
    for candidate in candidates:
        row = candidate if isinstance(candidate, dict) else vars(candidate)
        key = row.get('fixture_id')
        start = _clock(row.get('scheduled_start', row.get('kickoff')))
        if type(key) is not int or key <= 0 or start is None:
            continue
        recent = validated_football_recent_results(raw.get(str(key)), identity={
            'fixture_id': key, 'home_id': row.get('home_id', row.get('home_team_id')),
            'away_id': row.get('away_id', row.get('away_team_id')),
            'scheduled_start': start.isoformat(), 'model_scope': row.get('model_scope'),
            'input_cutoff_at': clock.isoformat()})
        if recent is not None:
            result[str(key)] = recent
    return result


def _record_copy(rows):
    wins = sum(r['scored'] > r['conceded'] for r in rows)
    draws = sum(r['scored'] == r['conceded'] for r in rows)
    return f'{wins}S · {draws}U · {len(rows)-wins-draws}N'


def recent_football_result_facts(recent, *, home, away):
    """Plain bounded display strings from an already validated projection."""
    facts, details = [], []
    labels = _form_labels(home, away)
    for side, team in (('home', home), ('away', away)):
        rows = recent[side]
        if not rows:
            continue
        label = (_record_copy(rows[:5]) + ' (5) / ' + _record_copy(rows) + ' (10)' if len(rows) == 10
                 else _record_copy(rows[:5]) + (' (5)' if len(rows) >= 5 else f' ({len(rows)} erfasst)'))
        facts.append((labels[side], label))
        details.extend(_team_result_details(rows, team))
    return tuple(facts), tuple(details)


def _team_result_details(rows, team):
    return tuple(f'{team} · {r["played_at"][:10]} · {r["opponent"]}: '
                 f'{r["scored"]}:{r["conceded"]} ({"Heim" if r["venue"] == "home" else "Gast"}; {r["competition"]})'
                 for r in rows)


def recent_football_goal_market_facts(recent, spec, *, home, away):
    """Observed goal-market counts, not fitted probabilities or selection rules.

    The caller supplies the exact-bound, validated recent-result projection.
    Team markets use goals scored for that team and goals conceded by the other
    team. Corners/cards must never receive facts inferred from football scores.
    """
    if spec.kind not in {'team_total', 'team_range', 'total', 'btts'}:
        return (), ()
    contract = _contract(spec, home, away)[0]
    if spec.kind in {'team_total', 'team_range'}:
        own_side = 'home' if spec.side.startswith('home') else 'away'
        opposing_side = 'away' if own_side == 'home' else 'home'
        own, opponent = (home, away) if own_side == 'home' else (away, home)
        contract = contract.rsplit(' für ', 1)[0]
        subjects = ((own_side, 'scored', f'{own} · {contract}'),
                    (opposing_side, 'conceded', f'{opponent} · Gegentore: {contract}'))
    else:
        subjects = (('home', 'total', f'{home}-Spiele · {contract}'),
                    ('away', 'total', f'{away}-Spiele · {contract}'))

    def matches(row, field):
        if spec.kind == 'btts':
            both = row['scored'] > 0 and row['conceded'] > 0
            return both if spec.side == 'yes' else not both
        goals = row['scored'] + row['conceded'] if field == 'total' else row[field]
        if spec.kind == 'team_range':
            return spec.low <= goals <= spec.high
        return goals > spec.threshold if spec.side.endswith('over') else goals < spec.threshold

    facts, details = [], []
    for side, field, label in subjects:
        rows = recent[side]
        if not rows:
            continue
        short = rows[:5]
        count = sum(matches(row, field) for row in short)
        value = f'{count}/{len(short)} zuletzt' if len(short) == 5 else f'{count}/{len(short)} erfasst'
        if len(rows) == 10:
            value += f' · {sum(matches(row, field) for row in rows)}/10'
        facts.append((label, value))
        team = home if side == 'home' else away
        details.append((label, (
            f'{team}: {count} von {len(short)} letzten erfassten Spielen erfüllen diese Torbedingung.',
            'Beobachtete Ergebnisse, keine zusätzliche Modellwahrscheinlichkeit.',
            *_team_result_details(rows, team),
        )))
    return tuple(facts), tuple(details)


def _form_labels(home, away):
    collides = home.strip().casefold() == away.strip().casefold()
    return {side: 'Form '+team+(f' ({venue})' if collides else '')
            for side, team, venue in (('home', home, 'Heim'), ('away', away, 'Gast'))}


def manual_football_customer_analysis(candidate, *, recent_results, model_clock, now):
    """Use the same exact-bound customer analysis for a manual search result."""
    from types import SimpleNamespace
    from forecast_analysis import project_football_analysis
    clock = _clock(model_clock.isoformat() if isinstance(model_clock, datetime) else model_clock)
    if clock is None:
        return None
    attributes = vars(candidate)
    if any(field not in attributes for field in ('home_team_id', 'away_team_id', 'kickoff')):
        return None
    row = {**attributes, 'sport': 'Fußball',
           'home_id': attributes['home_team_id'], 'away_id': attributes['away_team_id'],
           'scheduled_start': attributes['kickoff'], 'modeled_at': clock.isoformat(),
           'input_cutoff_at': clock.isoformat()}
    row['analysis_evidence'] = project_football_analysis(row,
        model_basis={**row, 'customer_recent_results': recent_results})
    return football_customer_analysis(SimpleNamespace(**row), now=now)


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
    recent = basis.get('customer_recent_results')
    details, fact_details, market_facts = [], [], ()
    if recent:
        result_facts, result_details = recent_football_result_facts(recent, home=home, away=away)
        if result_facts:
            facts = []  # Do not repeat the six-match form input beside actual records.
        facts.extend(result_facts)
        details.extend(result_details)
        labels = _form_labels(home, away)
        fact_details.extend((labels[side], _team_result_details(recent[side], team))
                            for side, team in (('home', home), ('away', away)) if recent[side])
        market_facts, market_details = recent_football_goal_market_facts(
            recent, spec, home=home, away=away)
        facts.extend(market_facts)
        fact_details.extend(market_details)
        if opposing_side:
            own_side = 'home' if opposing_side == 'away' else 'away'
            ours, theirs = recent[own_side][:5], recent[opposing_side][:5]
            if len(ours) == len(theirs) == 5:
                our_wins = sum(r['scored'] > r['conceded'] for r in ours)
                their_wins = sum(r['scored'] > r['conceded'] for r in theirs)
                if their_wins > our_wins:
                    other_team, own_team = (home, away) if opposing_side == 'home' else (away, home)
                    caution = f'{other_team} gewann {their_wins} der letzten 5 erfassten Spiele, {own_team} gewann {our_wins}. ' + caution
    if not details:
        details = ['Sieg-/Remis-/Niederlagenbilanz nicht hinterlegt; Gegner der letzten Spiele sind in diesem Kartenstand nicht gespeichert.']
    else:
        details.append('Erfasste Ergebnisse aus dem geladenen Modellumfang; keine vollständige teamübergreifende Gegnerstärke-Bewertung.')
    return FootballCustomerAnalysis(summary, caution, tuple(facts), tuple(details), tuple(fact_details), market_facts)
