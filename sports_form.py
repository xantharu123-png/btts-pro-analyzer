"""Readonly, typed result tiles. Never infer match history from explanation text."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from html import escape


@dataclass(frozen=True)
class FormResult:
    outcome: str
    score: str = ''
    opponent: str = ''
    date: str = ''
    competition: str = ''
    venue: str = ''
    rank: int | None = None


@dataclass(frozen=True)
class TeamForm:
    team: str
    scope: str
    results: tuple[FormResult, ...]


def football_forms(basis, home, away):
    """Only accept the optional projection already validated by the card loader."""
    raw = basis.get('customer_recent_results', {})
    if not isinstance(raw, Mapping) or raw.get('schema') != 'football-recent-results-v1':
        return ()
    forms = []
    for side, team in (('home', home), ('away', away)):
        rows = raw.get(side)
        if not isinstance(rows, (list, tuple)) or not rows:
            continue
        results = tuple(FormResult(
            'S' if r['scored'] > r['conceded'] else 'N' if r['scored'] < r['conceded'] else 'U',
            f'{r["scored"]}:{r["conceded"]}', r['opponent'], r['played_at'],
            r['competition'], 'Heim' if r['venue'] == 'home' else 'Auswärts',
        ) for r in rows[:10])
        forms.append(TeamForm(team, 'Letzte Spiele · alle Spielorte', results))
    return tuple(forms)


def manual_football_forms(candidate, recent, *, model_clock):
    from football_customer_facts import validated_football_recent_results
    raw = validated_football_recent_results(recent, identity={
        'fixture_id': candidate.fixture_id, 'home_id': candidate.home_team_id,
        'away_id': candidate.away_team_id, 'scheduled_start': candidate.kickoff,
        'model_scope': candidate.model_scope, 'input_cutoff_at': model_clock,
    })
    return football_forms({'customer_recent_results': raw}, candidate.home_team, candidate.away_team)


def tennis_forms(context, records):
    """Aggregate-only legacy records cannot become invented ordered tiles."""
    raw = context.get('match_statistics', {})
    if not isinstance(raw, Mapping) or raw.get('schema') != 'tennis-customer-results-v2':
        return ()
    allowed = {name for name, _value, _scope in records}
    surface = {'Hard': 'Hartplatz', 'Clay': 'Sand', 'Grass': 'Rasen', 'Carpet': 'Teppich'}.get(raw.get('surface'), '')
    forms = []
    for entry in raw.get('players', {}).values():
        if not isinstance(entry, Mapping) or entry.get('player') not in allowed:
            continue
        rows = entry.get('surface_results', ())
        # The record validator has checked identity, cutoff, counts and rows.
        # Also reject an internally contradictory result/sets pair.
        if any(r['won'] != (int(r['score'].split(':')[0]) > int(r['score'].split(':')[1])) for r in rows):
            continue
        results = tuple(FormResult('S' if r['won'] else 'N', r['score'], r['opponent'],
            r['date'], 'Turnierdatum' if r['date_kind'] == 'tournament_date' else 'Ergebnisdatum',
            rank=r.get('opponent_rank')) for r in rows[:10])
        forms.append(TeamForm(entry['player'], surface, results))
    return tuple(forms)


def team_forms(signal, customer):
    """Existing same-call, hash-bound team facts; not public fallback prose."""
    if not customer['recent']:
        return ()
    sport = str(signal.sport).casefold().replace('-', '').replace('_', '').replace(' ', '')
    esports = sport in ('esport', 'esports')
    container = signal.context_evidence if esports else signal.team_sport_snapshot
    if not isinstance(container, Mapping):
        return ()
    parent = container if esports else container.get('team_sport_forecast', {})
    raw = container.get('recent_results' if esports else 'customer_recent_results', {})
    if not isinstance(parent, Mapping) or not isinstance(raw, Mapping):
        return ()
    typed = not esports and raw.get('schema') == 'team-recent-results-v2'
    if typed:
        from team_customer_facts import validate_team_recent_results
        from team_sport_forecasts import TeamSportForecast
        try:
            raw = validate_team_recent_results(raw, TeamSportForecast.from_dict(parent),
                competition=container.get('competition'),
                input_cutoff_at=container.get('input_cutoff_at'))
        except (TypeError, ValueError, KeyError):
            return ()
    if (raw.get('schema') != ('esports-recent-results-v1' if esports else
                             'team-recent-results-v2' if typed else 'team-recent-results-v1')
            or raw.get('source_input_hash') != parent.get('source_input_hash' if esports else 'model_input_hash')
            or not raw.get('source_input_hash')
            or raw.get('provider_event_id') != str(signal.provider_event_id)
            or raw.get('competitor_a') != signal.competitor_a
            or raw.get('competitor_b') != signal.competitor_b
            or not esports and raw.get('modeled_at') != parent.get('modeled_at')):
        return ()
    forms = []
    for side, team in (('a', signal.competitor_a), ('b', signal.competitor_b)):
        rows = raw.get(side + '_results')
        if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= 10:
            continue
        outcomes = rows if esports else [r.get('won') if isinstance(r, Mapping) else None for r in rows]
        if any(type(won) is not bool for won in outcomes):
            continue
        def display_name(name, team_id):
            if not typed:
                return name
            from sports_identity_media import participant_display_name
            return participant_display_name(parent['sport'], name, team_id=team_id,
                fixture_source=parent['provider'], competition=container.get('competition'))
        results = tuple(FormResult('S' if won else 'N',
            '' if esports else str(row.get('score') or ''),
            '' if esports else display_name(str(row.get('opponent') or ''), row.get('opponent_id')),
            '' if esports else str(row.get('start') or ''),
        ) for row, won in zip(rows, outcomes))
        scope = 'Serien · erfasste Reihenfolge' if esports else 'Endergebnisse inkl. Verlängerung'
        if sport in ('eishockey', 'icehockey'):
            scope += ' / Penaltyschießen'
        forms.append(TeamForm(display_name(team, parent.get('home_id' if side == 'a' else 'away_id')),
                              scope, results))
    return tuple(forms)


def _date_label(value):
    if not value:
        return ''
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%d.%m.%Y')
    except (ValueError, TypeError):
        return value


def _result_html(result):
    name = {'S': 'Sieg', 'U': 'Remis', 'N': 'Niederlage'}[result.outcome]
    fields = [f'{name} · {result.score}' if result.score else name]
    fields += [x for x in (result.opponent, _date_label(result.date), result.competition, result.venue) if x]
    if result.rank is not None:
        fields.append(f'Damaliger Weltrang: {result.rank}')
    body = ''.join(f'<span>{escape(str(field))}</span>' for field in fields)
    label = name + (f' {result.score}' if result.score else '') + (f' gegen {result.opponent}' if result.opponent else '')
    return (f'<details class="form-result form-{result.outcome.lower()}">'
        f'<summary aria-label="{escape(label, quote=True)}"><b>{result.outcome}</b>'
        f'<span>{escape(result.score) if result.score else "–"}</span></summary>'
        f'<div class="form-result-detail">{body}</div></details>')


def _opponent_line(result):
    name = result.opponent or 'Gegner offen'
    mark = next((letter for letter in name if letter.isalnum()), '?').upper()
    metadata = ' · '.join(x for x in (_date_label(result.date), result.competition,
        result.venue, f'Weltrang {result.rank}' if result.rank is not None else '') if x)
    return ('<li><details class="form-opponent-row"><summary>'
        f'<span class="form-opponent-mark" aria-hidden="true">{escape(mark)}</span>'
        f'<strong>{escape(name)}</strong><b>{escape(result.score or "–")}</b>'
        f'<span class="form-outcome form-outcome-{result.outcome.lower()}">{result.outcome}</span>'
        '</summary>' + (f'<p>{escape(metadata)}</p>' if metadata else '') + '</details></li>')


def _has_result_details(result):
    """A win/loss flag alone is a real result, not a known opponent/score row."""
    return any((result.opponent, result.score, result.date, result.competition,
                result.venue)) or result.rank is not None


def _window_html(forms, count):
    teams = []
    for form in forms:
        rows = form.results[:count]
        wins, draws, losses = (sum(r.outcome == mark for r in rows) for mark in ('S', 'U', 'N'))
        record = f'{wins}S · {draws}U · {losses}N' if any(r.outcome == 'U' for r in form.results) or 'Spielorte' in form.scope else f'{wins}S · {losses}N'
        known_rows = tuple(r for r in rows if _has_result_details(r))
        preview = ''.join(_opponent_line(r) for r in known_rows[:3])
        remainder = ''.join(_opponent_line(r) for r in known_rows[3:])
        more_label = ('Alle ' + str(len(rows)) + ' Spiele' if len(known_rows) == len(rows)
                      else str(len(known_rows) - 3) + ' weitere Spieldetails')
        more = ('<details class="form-opponents"><summary>' + more_label + '</summary>'
            f'<ol>{remainder}</ol></details>') if remainder else ''
        opponents = ('<div class="form-opponent-preview"><h5>Gegner & Ergebnisse</h5>'
                     f'<ol>{preview}</ol></div>{more}') if known_rows else ''
        missing = len(rows) - len(known_rows)
        coverage = ''
        if missing:
            note = ('Nur Serienbilanz verfügbar' if 'Serien' in form.scope else 'Nur Bilanz verfügbar') if not known_rows else (
                f'{missing} Ergebnis' + ('se' if missing != 1 else '') + ' ohne Spieldetails')
            coverage = f'<small class="form-coverage">{escape(note)}</small>'
        teams.append(f'<section class="form-team"><div class="form-team-heading"><strong>{escape(form.team)}</strong>'
            f'<span>{record} · {len(rows)} Spiele</span></div><small>{escape(form.scope)}</small>'
            f'<div class="form-results">{"".join(_result_html(r) for r in rows)}</div>'
            f'{opponents}{coverage}</section>')
    return f'<div class="form-window form-window-{count}">{"".join(teams)}</div>'


def render_form_html(forms, *, instance_key=''):
    if not forms:
        return ''
    suffix = sha256((instance_key + repr(forms)).encode()).hexdigest()[:16]
    group = 'form-' + suffix
    # Ten is enabled only when every displayed side has ten actual results.
    can_ten = all(len(form.results) >= 10 for form in forms)
    ten = (f'<input id="{group}-10" type="radio" name="{group}" value="10">'
        f'<label for="{group}-10">10 Spiele</label>') if can_ten else '<span class="form-ten-unavailable" title="Weniger als zehn Ergebnisse erfasst">10 Spiele</span>'
    chronology = 'Erfasste Reihenfolge' if any('erfasste Reihenfolge' in form.scope for form in forms) else 'Neueste zuerst'
    return (f'<section class="sports-form" aria-label="Letzte Ergebnisse">'
        f'<div class="form-heading"><h4>Aktuelle Form</h4><span>{chronology}</span><div class="form-toggle" role="group" aria-label="Anzahl Spiele">'
        # Do not supply a controlled `checked` prop through React Markdown:
        # React would restore it after the native label click. The initial
        # five-game view is CSS's default; both radios are genuine native
        # uncontrolled inputs once the user chooses a window.
        f'<input id="{group}-5" type="radio" name="{group}" value="5" aria-label="5 Spiele (Standardansicht)">'
        f'<label for="{group}-5">5 Spiele</label>{ten}</div></div>'
        f'{_window_html(forms, 5)}{_window_html(forms, 10) if can_ten else ""}</section>')
