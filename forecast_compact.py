"""Short, typed card facts with optional native click/touch/keyboard details.

Presentation only: no new data requests, ranking, probabilities or money rules.
The full original explanation remains available without opening the whole card.
"""
from dataclasses import dataclass
from datetime import timedelta
from html import escape

from challenge_engine import MARKET_BY_KEY
from forecast_analysis import (
    _clock, _contract, _decimal, _mapping, _percent, _tennis_inputs,
    forecast_highlight_reason, format_model_clock, read_football_analysis,
)


@dataclass(frozen=True)
class Fact:
    label: str
    value: str
    details: tuple[str, ...] = ()
    warning: bool = False


@dataclass(frozen=True)
class CompactAnalysis:
    summary: str
    facts: tuple[Fact, ...]
    warnings: tuple[str, ...]
    explanation: tuple[str, ...]
    model_clock: str


def _names_line(injuries, side, bucket, count):
    names = injuries.get(side + '_' + bucket + '_names')
    # Legacy mixed lists are exact absences only if no doubtful player was
    # reported. Unknown doubtful count is NOT zero.
    if names is None and bucket == 'missing' and injuries.get(side + '_questionable') == 0:
        names = injuries.get(side + '_names')
    if count == 0:
        return 'keine gemeldet'
    if not names:
        return 'Namen nicht verfügbar'
    if len(names) > count:
        return 'Namen nicht eindeutig zugeordnet'
    suffix = ' (Liste unvollständig)' if len(names) < count else ''
    return ', '.join(names) + suffix


def _injury_details(injuries, home, away):
    lines = []
    for side, team in (('home', home), ('away', away)):
        missing = injuries[side + '_missing']
        lines.append(f'{team} · {missing} Ausfälle: {_names_line(injuries, side, "missing", missing)}')
        doubtful = injuries.get(side + '_questionable')
        if doubtful is not None:
            lines.append(f'{team} · {doubtful} fraglich: {_names_line(injuries, side, "questionable", doubtful)}')
        # Older mixed observations remain useful but must not be presented as
        # an exact list of ruled-out players when status separation is absent.
        if side + '_missing_names' not in injuries and doubtful != 0 and injuries.get(side + '_names'):
            lines.append(f'{team} · gemeldete Spieler, Status nicht einzeln zugeordnet: ' + ', '.join(injuries[side + '_names']))
    lines.append('Kaderstand: ' + format_model_clock(injuries['checked_at']))
    return tuple(lines)


def build_compact_analysis(signal, analysis, *, now):
    sport = str(signal.sport or '').strip().casefold().replace('ß', 'ss')
    facts, warnings = [], []
    summary = analysis.basis.split('. ', 1)[0].rstrip('.')
    football = sport in {'fussball', 'football'}
    evidence = read_football_analysis(vars(signal), now=now) if football else None
    spec = MARKET_BY_KEY.get(signal.market_key) if football else None
    home, away = signal.home_team or 'Heimteam', signal.away_team or 'Gastteam'
    context = _mapping(evidence.get('context')) if evidence else {}
    basis = _mapping(evidence.get('basis')) if evidence else {}
    if football:
        summary = 'Modellgrundlagen unvollständig'
        if spec and analysis.supported:
            count_market = spec.kind in {'corner_total', 'team_corners', 'yellow_total', 'team_yellow'}
            unit = basis.get('expected_unit') if count_market else 'Tore'
            heading = 'Torprognose' if unit == 'Tore' else f'{unit}-Prognose'
            left = basis.get('expected_market_home' if count_market else 'expected_home_goals')
            right = basis.get('expected_market_away' if count_market else 'expected_away_goals')
            if left is not None and right is not None:
                if spec.kind in {'team_total', 'team_range', 'team_corners', 'team_yellow'}:
                    is_home = spec.side.startswith('home')
                    summary = f'{heading} {home if is_home else away}: {_decimal(left if is_home else right)}'
                else:
                    summary = f'{heading}: {_decimal(left)} : {_decimal(right)} (Heim : Gast)'
                if spec.kind == 'result' and ((spec.side == 'home' and left < right) or (spec.side == 'away' and right < left)):
                    warnings.append('Außenseiter-Szenario')
            venue = basis.get('venue_samples')
            if venue:
                facts.append(Fact('Basis', f'{venue[0]} Heim · {venue[1]} Gast', (analysis.samples,)))
        counter = _contract(spec, home, away)[1] if spec else 'Auswahl tritt nicht ein'
        facts.insert(0, Fact('Gegenrisiko', _percent(1 - signal.probability),
                             (counter, 'Modellschätzung, keine gesicherte Wahrscheinlichkeit.')))
        def fresh(axis):
            clock = _clock(axis.get('checked_at'))
            return clock is not None and context.get('stale') is not True and timedelta(0) <= now - clock <= timedelta(minutes=75)
        injuries = _mapping(context.get('injuries'))
        if fresh(injuries):
            facts.append(Fact('Ausfälle', f'{injuries["home_missing"]} Heim · {injuries["away_missing"]} Gast',
                              _injury_details(injuries, home, away)))
            applied = _mapping(context.get('probability_integration')).get('applied')
            if applied is False:
                warnings.append('Ausfallwirkung nicht eingerechnet')
            elif applied is not True or injuries.get('impact_assessment_complete') is False:
                warnings.append('Ausfallwirkung nicht vollständig belegt')
        else:
            label = 'veraltet' if injuries else 'offen'
            facts.append(Fact('Ausfälle', label, ('Kein aktueller, verifizierter Kaderstand verfügbar.',), True))
        lineups = _mapping(context.get('lineups'))
        status = lineups.get('status') if fresh(lineups) else None
        lineup_label = {'passed': 'bestätigt', 'pending': 'offen', 'confirmation_due': 'offen',
                        'blocked': 'ungeklärt', 'unavailable': 'offen'}.get(status, 'offen')
        facts.append(Fact('Aufstellung', lineup_label,
                          ('Stand: ' + format_model_clock(lineups.get('checked_at')),
                           'Heim- und Gastaufstellung.' if status == 'passed' else 'Keine vollständig bestätigte Aufstellung.')))
        if signal.model_scope and signal.model_scope != 'same_competition':
            warnings.append('Ligavergleich nicht bestätigt')
    elif sport == 'tennis' and analysis.supported:
        inputs = _tennis_inputs(signal)
        surface = {'hard': 'Hartplatz', 'clay': 'Sand', 'grass': 'Rasen', 'carpet': 'Teppich'}.get(str(inputs.get('surface')).casefold())
        summary = f'Belag: {surface}' if surface else 'Belagspezifisches Modell'
        if inputs.get('serve_in_model') is True:
            summary += ' · Aufschlagdaten berücksichtigt'
        warnings.append('Verletzungs-/Müdigkeitseffekte nicht belegt')
    elif sport in {'e-sport', 'esports'} and analysis.supported:
        warnings.append('Kader-/Belastungseffekte nicht belegt')
    elif not analysis.supported:
        summary = 'Modellgrundlagen unvollständig'
        warnings.append('Keine vollständige Begründung verfügbar')
    else:
        warnings.append(analysis.caution)
    if not analysis.data_current:
        warnings.append('Datenstand nicht aktuell belegt')
    freshness = forecast_highlight_reason(signal, now=now, analysis=analysis)
    if freshness and freshness != 'Keine exakt zugeordneten Modellgrundlagen' and freshness not in warnings:
        warnings.append(freshness)
    explanation = tuple(part for part in (analysis.basis, analysis.caution, analysis.samples, analysis.data_age) if part)
    return CompactAnalysis(summary, tuple(facts), tuple(warnings), explanation, format_model_clock(signal.modeled_at))


def _fact_html(fact):
    summary = f'<span>{escape(fact.label)}</span> <strong>{escape(fact.value)}</strong>'
    tone = ' wf-fact-warning' if fact.warning else ''
    if not fact.details:
        return f'<span class="wf-fact{tone}">{summary}</span>'
    body = ''.join(f'<p>{escape(line)}</p>' for line in fact.details)
    return (f'<details class="wf-fact{tone}"><summary>{summary}</summary>'
            f'<div class="wf-fact-detail">{body}</div></details>')


def render_compact_analysis_html(compact):
    facts = ''.join(_fact_html(fact) for fact in compact.facts)
    warnings = ' · '.join(escape(text) for text in compact.warnings)
    warning_html = f'<p class="wf-analysis-alert">{warnings}</p>' if warnings else ''
    explanation = _fact_html(Fact('Berechnung & Daten', '', compact.explanation))
    return ('<section class="wf-analysis" aria-label="Kurzcheck">'
            f'<p class="wf-analysis-short">{escape(compact.summary)}</p>'
            f'<div class="wf-facts">{facts}</div>{warning_html}'
            f'<div class="wf-analysis-footer"><span>Berechnet: {escape(compact.model_clock)}</span>{explanation}</div>'
            '</section>')
