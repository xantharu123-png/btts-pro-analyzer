"""Readonly, typed result tiles. Never infer match history from explanation text."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from html import escape
import re


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


def football_goal_history_rows(forms, count):
    """Observed joint hits in already validated football history, not a forecast."""
    if count not in (5, 10) or type(count) is not int or len(forms) != 2:
        return ()
    scores = []
    for form in forms:
        if form.scope != 'Letzte Spiele · alle Spielorte' or not 1 <= len(form.results) <= 10:
            return ()
        side = []
        for row in form.results[:count]:
            if not isinstance(row.score, str) or not re.fullmatch(r'[0-9]{1,2}:[0-9]{1,2}', row.score):
                return ()
            left, right = map(int, row.score.split(':'))
            outcome = 'S' if left > right else 'U' if left == right else 'N'
            if max(left, right) > 30 or row.outcome != outcome:
                return ()
            side.append((left, right))
        scores.append(side)
    ranges = ((1, 3), (1, 4), (2, 3), (2, 4))
    rows = []
    for winner in (False, True):
        for low, high in ranges:
            label = f'Sieg + {low}–{high}' if winner else f'{low}–{high} Tore'
            counts = tuple(f'{sum(low <= left + right <= high and (not winner or left > right) for left, right in side)}/{len(side)}'
                           for side in scores)
            rows.append((label, *counts))
    return tuple(rows)


def _goal_history_html(forms, count):
    rows = football_goal_history_rows(forms, count)
    if not rows:
        return ''
    headings = ''.join(f'<th scope="col">{escape(form.team)}</th>' for form in forms)
    body = ''.join(f'<tr><th scope="row">{escape(label)}</th><td>{left}</td><td>{right}</td></tr>'
                   for label, left, right in rows)
    return ('<section class="form-goal-markets" aria-label="Historische Multigoal-Treffer">'
            '<h5>Multigoal &amp; Sieg-Kombis</h5><small>Gesamttore · Treffer / Spiele</small>'
            '<table><thead><tr><th scope="col">Letzte Spiele</th>' + headings
            + '</tr></thead><tbody>' + body + '</tbody></table></section>')


def _window_html(forms, count, *, include_goal_ranges=False):
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
    ranges = _goal_history_html(forms, count) if include_goal_ranges else ''
    return f'<div class="form-window form-window-{count}">{"".join(teams)}{ranges}</div>'


GOAL_HISTORY_NOTE = 'Historische Treffer / erfasste Spiele · Sieg des jeweiligen Teams · keine Modellchance'
_SURFACES = ('Hartplatz', 'Sand', 'Rasen', 'Teppich')
_OUTCOME_NAMES = {'S': 'Sieg', 'U': 'Remis', 'N': 'Niederlage'}


def render_goal_history_html(forms, *, instance_key=''):
    """The football goal-range table in the RisikoBet detail layout (owner 17.11.2026).

    Same markup as the RisikoBet page: heading with the 5/10 switch, the note, one table per window. Observed
    counts from already validated results only; ten is offered only when both sides have ten results.
    """
    windows = {5: football_goal_history_rows(forms, 5)}
    if not windows[5]:
        return ''
    if all(len(form.results) >= 10 for form in forms):
        ten_rows = football_goal_history_rows(forms, 10)
        if ten_rows:
            windows[10] = ten_rows
    group = 'goals-' + sha256((instance_key + repr(forms)).encode()).hexdigest()[:16]
    ten = (f'<input id="{group}-10" type="radio" name="{group}" value="10">'
           f'<label for="{group}-10">10 Spiele</label>') if 10 in windows else (
        '<span class="form-ten-unavailable" title="Weniger als zehn Ergebnisse erfasst">10 Spiele</span>')
    headings = ''.join(f'<th scope="col">{escape(form.team)}</th>' for form in forms)
    tables = ''
    for window, rows in sorted(windows.items()):
        body = ''.join(f'<tr><th scope="row">{escape(label)}</th><td>{left}</td><td>{right}</td></tr>'
                       for label, left, right in rows)
        tables += (f'<div class="form-window form-window-{window}"><section class="form-goal-markets">'
                   f'<table><thead><tr><th scope="col">Gesamttore</th>{headings}</tr></thead>'
                   f'<tbody>{body}</tbody></table></section></div>')
    return ('<section class="sports-form" aria-label="Historische Multigoal-Treffer">'
            '<div class="form-heading"><h4>Multigoal &amp; Sieg-Kombis</h4>'
            '<div class="form-toggle" role="group" aria-label="Anzahl Spiele">'
            # No controlled `checked` prop (see render_form_html): five games is the CSS default.
            f'<input id="{group}-5" type="radio" name="{group}" value="5" aria-label="5 Spiele (Standardansicht)">'
            f'<label for="{group}-5">5 Spiele</label>{ten}</div></div>'
            f'<small>{GOAL_HISTORY_NOTE}</small>{tables}</section>')


def form_text_lines(forms):
    """Recent results as plain lines like the RisikoBet detail, never tiles (owner 17.11.2026).

    With draws (football): „Team: 3S · 1U · 1N (5) / 6S · 2U · 2N (10); Gegner (10): A 2:0; B 1:1“; opponents
    follow only when every listed result names one with its score. Without draws (tennis): only the record,
    „Spieler: 4/5 Siege · 6/10 Siege“, as on the RisikoBet tennis card; single results belong in the drawer.
    """
    lines = []
    scopes = {form.scope for form in forms if form.results}
    if len(scopes) == 1 and next(iter(scopes)) in _SURFACES:
        lines.append('Belag: ' + next(iter(scopes)))
    for form in forms:
        results = form.results[:10]
        if not results:
            continue
        with_draws = 'Spielorte' in form.scope or any(r.outcome == 'U' for r in form.results)

        def record(rows):
            wins = sum(r.outcome == 'S' for r in rows)
            if not with_draws:
                return f'{wins}/{len(rows)} Siege'
            draws = sum(r.outcome == 'U' for r in rows)
            return f'{wins}S · {draws}U · {len(rows) - wins - draws}N'

        if with_draws:
            label = (f'{record(results[:5])} (5) / {record(results)} (10)' if len(results) == 10
                     else record(results[:5]) + (' (5)' if len(results) >= 5 else f' ({len(results)} erfasst)'))
        else:
            label = (f'{record(results[:5])} · {record(results)}' if len(results) == 10
                     else record(results[:5]))
        text = f'{form.team}: {label}'
        for count in (10, 5, 1) if with_draws else ():
            rows = results[:count]
            if not all(r.opponent and r.score for r in rows):
                continue
            expanded = text + f'; Gegner ({len(rows)}): ' + '; '.join(f'{r.opponent} {r.score}' for r in rows)
            if len(expanded) <= 600:
                text = expanded
                break
        lines.append(text)
    return tuple(lines)


def form_detail_lines(forms):
    """Every known result as one plain line for the analysis drawer (what a tile showed on click)."""
    lines = []
    for form in forms:
        known = [r for r in form.results[:10] if _has_result_details(r)]
        if not known:
            continue
        if form.scope:
            lines.append(f'{form.team}: {form.scope}')
        for r in known:
            head = ' · '.join(x for x in (form.team, _date_label(r.date), r.opponent) if x)
            facts = [_OUTCOME_NAMES[r.outcome], r.venue, r.competition]
            if r.rank is not None:
                facts.append(f'Damaliger Weltrang: {r.rank}')
            lines.append(f'{head}: {r.score or "–"} ({"; ".join(x for x in facts if x)})')
    return tuple(lines)


def render_form_html(forms, *, instance_key='', include_goal_ranges=False):
    if not forms:
        return ''
    suffix = sha256((instance_key + repr(forms) + ('|goal-history' if include_goal_ranges else '')).encode()).hexdigest()[:16]
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
        f'{_window_html(forms, 5, include_goal_ranges=include_goal_ranges)}'
        f'{_window_html(forms, 10, include_goal_ranges=include_goal_ranges) if can_ten else ""}</section>')
