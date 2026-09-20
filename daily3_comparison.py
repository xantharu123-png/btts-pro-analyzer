"""Quote-free football comparison evidence, not a claim of betting value.

Retain exact-bound model variants and league observations. Shortlisting uses
the recent-form change against the same match's season-strength model, not an
unconditioned league frequency. Neither comparison is proof of betting value
or applied injury/weather effects. Ordinary forecasts remain unchanged.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from collections.abc import Mapping

SCHEMA = 'league-market-comparison-v1'
MIN_BASELINE_SAMPLES = 200
MIN_FORM_CHANGE = .02  # Presentation relevance, not empirical significance.


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def build_market_comparisons(fixture, history, probabilities, validation, *, prediction_version, as_of):
    """Use only the same already-loaded, completed league history; no I/O.

    Do not recalculate any model. Counts and the already computed three model
    variants are presentation evidence only. Conflicting duplicate outcomes
    are not allowed to support a comparison.
    """
    from challenge_engine import MARKET_BY_KEY, _fixture_datetime, _fixture_market_outcome, _credible_validation
    league = _mapping(fixture.get('league')).get('id')
    kickoff = _fixture_datetime(fixture)
    if type(league) is not int or kickoff is None:
        return {}
    cutoff = min(kickoff, as_of)
    observations = []
    for row in history:
        if not isinstance(row, dict) or _mapping(row.get('league')).get('id') != league:
            continue
        played = _fixture_datetime(row)
        status = _mapping(_mapping(row.get('fixture')).get('status')).get('short')
        # Existing historical adapters may omit status, but never accept a
        # known ongoing, postponed or extra-time score as a 90-minute result.
        if played is None or played >= cutoff or status not in (None, 'FT'):
            continue
        teams = _mapping(row.get('teams'))
        home, away = _mapping(teams.get('home')).get('id'), _mapping(teams.get('away')).get('id')
        # Historical CSV adapters use stable negative IDs for other teams.
        if any(type(n) is not int or n == 0 for n in (home, away)) or home == away:
            continue
        observations.append(((played.date(), home, away), played, row))
    results = {}
    for key, variants in probabilities.items():
        spec = MARKET_BY_KEY.get(key)
        if spec is None or not isinstance(variants, (tuple, list)) or len(variants) != 3:
            continue
        if any(not _number(p) or not 0 < p < 1 for p in variants):
            continue
        outcomes, dates, conflicts = {}, {}, set()
        for event, played, row in observations:
            outcome = _fixture_market_outcome(spec, row)
            if outcome is None:
                continue
            if event in outcomes and outcomes[event] != outcome:
                conflicts.add(event)
            outcomes[event] = outcome
            dates[event] = max(played, dates.get(event, played))
        if conflicts or len(outcomes) < MIN_BASELINE_SAMPLES:
            continue
        metric = validation.get(key)
        results[key] = {
            'schema': SCHEMA, 'fixture_id': fixture['fixture']['id'], 'league_id': league,
            'home_id': fixture['teams']['home']['id'], 'away_id': fixture['teams']['away']['id'],
            'market_key': key, 'scheduled_start': kickoff.isoformat(),
            'prediction_version': prediction_version,
            'validation_prediction_version': metric.prediction_version if metric else None,
            'model_skill_supported': _credible_validation(metric),
            'samples': len(outcomes), 'successes': sum(outcomes.values()),
            'latest_kickoff': max(dates.values()).isoformat(),
            'probabilities': [round(p, 6) for p in variants],
        }
    return results


def _clock(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo and parsed.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def baseline_upper(successes, samples):
    """Upper endpoint of the two-sided 95% Wilson interval (binomial baseline)."""
    if type(samples) is not int or type(successes) is not int or not 0 <= successes <= samples or samples <= 0:
        raise ValueError('Invalid baseline counts')
    z = 1.959963984540054
    p, z2 = successes / samples, z*z
    return (p + z2/(2*samples) + z*math.sqrt(p*(1-p)/samples + z2/(4*samples*samples))) / (1+z2/samples)


def validated_comparison(raw, *, identity, model_version=None):
    """Only exact event/market/model evidence; no legacy/fabricated fallback."""
    if not isinstance(raw, Mapping) or raw.get('schema') != SCHEMA:
        return None
    for field in ('fixture_id', 'market_key', 'home_id', 'away_id', 'scheduled_start'):
        if raw.get(field) != identity.get(field) or type(raw.get(field)) is not type(identity.get(field)):
            return None
    if identity.get('model_scope') != 'same_competition':
        return None
    version = raw.get('prediction_version')
    if not isinstance(version, str) or not version or (model_version is not None and version != model_version):
        return None
    if raw.get('validation_prediction_version') != version or raw.get('model_skill_supported') is not True:
        return None
    if type(raw.get('league_id')) is not int or raw['league_id'] <= 0:
        return None
    n, k = raw.get('samples'), raw.get('successes')
    if type(n) is not int or type(k) is not int or not MIN_BASELINE_SAMPLES <= n <= 100000 or not 0 <= k <= n:
        return None
    latest = _clock(raw.get('latest_kickoff'))
    cutoff = _clock(identity.get('input_cutoff_at'))
    modeled = _clock(identity.get('modeled_at'))
    if not latest or not cutoff or not modeled or not latest < cutoff <= modeled:
        return None
    probabilities = raw.get('probabilities')
    if not isinstance(probabilities, (list, tuple)) or len(probabilities) != 3:
        return None
    if any(not _number(p) or not 0 < p < 1 for p in probabilities):
        return None
    if probabilities[0] != identity.get('probability'):
        return None
    fields = ('schema', 'fixture_id', 'home_id', 'away_id', 'league_id', 'market_key',
              'scheduled_start', 'prediction_version', 'validation_prediction_version',
              'model_skill_supported', 'samples', 'successes', 'latest_kickoff')
    return {**{key: raw[key] for key in fields}, 'probabilities': list(probabilities)}


@dataclass(frozen=True)
class Comparison:
    margin: float
    lowest_model_probability: float
    baseline_probability: float
    samples: int
    match_reference_probability: float | None = None
    active_probability: float | None = None

    @property
    def summary(self):
        if self.match_reference_probability is not None:
            baseline = f'{self.match_reference_probability:.1%}'.replace('.', ',')
            change = f'{100 * (self.active_probability - self.match_reference_probability):.1f}'.replace('.', ',')
            return f'Formsignal: +{change} Prozentpunkte zum Grundmodell ({baseline}).'
        model = f'{self.lowest_model_probability:.1%}'.replace('.', ',')
        baseline = f'{self.baseline_probability:.1%}'.replace('.', ',')
        return f'Saison/Form mindestens {model}; Ligavergleich {baseline} aus {self.samples} Spielen.'


def football_form_comparison(signal, *, now, minimum_probability=0.0):
    """Shared prominence evidence; Daily3 alone adds its probability floor."""
    # This adapter only consumes an actual saved comparison. Missing sport-
    # specific baselines must not be replaced with an invented 50% prior.
    from forecast_analysis import read_football_analysis
    if str(signal.sport or '').casefold() not in ('fußball', 'fussball', 'football'):
        return None
    evidence = read_football_analysis(vars(signal), now=now)
    if not evidence:
        return None
    if not isinstance(signal.model_version, str) or not signal.model_version:
        return None
    raw = validated_comparison(evidence['basis'].get('market_comparison'),
                               identity=evidence['identity'], model_version=signal.model_version)
    if raw is None:
        return None
    active, season, form = raw['probabilities']
    floor = min(active, season, form)
    # Same event, opponents, venue and market. The season variant already
    # incorporates the team's underlying strength: an obvious favourite score
    # cannot qualify merely by exceeding an unrelated league-wide frequency.
    # This is an ablation of recent form, NOT proof of betting value/causality.
    margin = round(min(active, form) - season, 12)
    # Explicit presentation relevance threshold, not a learned effect size or
    # a confidence bound. Never fill slots with round-off/tiny positive deltas.
    if floor < minimum_probability or margin < MIN_FORM_CHANGE - 1e-12:
        return None
    return Comparison(margin, floor, raw['successes']/raw['samples'], raw['samples'], season, active)


def daily3_comparison(signal, *, now, minimum_probability):
    return football_form_comparison(signal, now=now, minimum_probability=minimum_probability)
