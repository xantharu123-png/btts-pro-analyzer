"""Owning joint law in the existing training/evaluation/application pipeline.

No automatic activation: the existing held-out evaluator and approval registry
still own that decision. Unavailable factors are not replaced with zeros.
"""
from copy import deepcopy
from datetime import datetime
import re

import numpy as np

import challenge_engine as engine
from context_models.contracts import (
    ContextContractError, ContextIntegrityError, digest, event_in_population,
    validate_base_distribution, validate_effect_artifact,
    validate_event, validate_feature_vector,
)
from context_models.football_joint_effect import VERSION, _matrix, fit_joint_offset, joint_offset_delta, tilt_joint

BASE_VERSION = 'football-goals-captured-joint-v1'
COMPARISON_VERSION = 'football-goals-context-joint-v1'
FEATURE_VERSION = 'football-native-context-v1'
COVERAGE = {'version': FEATURE_VERSION + '.coverage', 'case': 'source-bound'}
LINK = 'log_joint_tilt'
TAIL_POLICY = 'calibrated-joint-goal-buckets-25plus-log-v1'


def cell_matrix(cells):
    if type(cells) is not list or not cells or len(cells) > 676:
        raise ContextContractError('joint cells require the bounded owning support')
    if any(type(cell) is not list or len(cell) != 3 for cell in cells):
        raise ContextContractError('joint cells need exact score and probability triples')
    coordinates = [(cell[0], cell[1]) for cell in cells]
    if (any(type(n) is not int for cell in coordinates for n in cell)
            or coordinates != sorted(set(coordinates))):
        raise ContextContractError('joint coordinates must be unique ordered integers')
    return _matrix({(h, a): p for h, a, p in cells})


def joint_params(cells):
    matrix = cell_matrix(cells)
    return {'home_lambda': sum(h*p for (h, a), p in matrix.items()),
            'away_lambda': sum(a*p for (h, a), p in matrix.items()), 'joint_cells': deepcopy(cells)}


def validate_joint_base(base):
    if base['version'] not in {BASE_VERSION, COMPARISON_VERSION}:
        raise ContextContractError('a joint cannot masquerade as a raw Poisson baseline')
    if base['params'] != joint_params(base['params']['joint_cells']):
        raise ContextIntegrityError('joint parameters differ from their effective means')
    matrix = cell_matrix(base['params']['joint_cells'])
    markets = {spec.key: engine.market_probability(matrix, spec) for spec in engine.GOAL_MARKET_SPECS}
    if base['markets'] != markets:
        raise ContextIntegrityError('joint markets differ from their shared goal distribution')


def feature_group(name):
    if re.fullmatch(r'roster\.(home|away)\.(venue|form)_(attack|defense)\.(goals|xg)\.api-football:player:[1-9][0-9]*', name):
        return 'roster'
    if name in {'weather.'+key for key in ('temperature_c', 'wind_mps', 'rain_3h_mm', 'snow_3h_mm',
                                          'receipt_age_hours', 'forecast_to_kickoff_hours')}:
        return 'weather'
    if name in {'schedule.gap_hours_'+side for side in ('home', 'away', 'delta')}:
        return 'schedule'
    raise ContextContractError('unknown source-bound football feature')


def joint_features(event, observations, base, *, cutoff):
    from context_models.football import football_features
    from context_models.football_city_weather import city_weather_features
    from context_sources.football import _detail_event
    from context_sources.outcomes import validate_football_base_input
    event, base = validate_event(event), validate_base_distribution(base)
    # Roster and city weather retain their own source/time validation.
    roster = football_features(event, observations, base, cutoff=cutoff)
    weather = city_weather_features(event, tuple(row for row in observations
        if row['event_key'] == event['event_key'] and row['kind'] == 'weather'), base, cutoff=cutoff)
    result = {**deepcopy(roster), 'version': FEATURE_VERSION, 'values': {}, 'states': {}, 'refs': {}, 'coverage': dict(COVERAGE)}
    for prefix, block in (('roster', roster), ('weather', weather)):
        for field in ('values', 'states', 'refs'):
            result[field].update({prefix+'.'+key: value for key, value in block[field].items()})
    # Schedule spacing is an observed scheduling proxy, NOT measured rest,
    # match duration or complete workload. No fabricated 90-minute end time.
    native = {}
    for row in observations:
        if row['kind'] != 'base_fixture' or row['observed_at'] > base['cutoff']:
            continue
        validate_football_base_input(row)
        native.setdefault(row['event_key'], []).append(row)
    candidates, conflicts = [], set()
    for revisions in native.values():
        latest = max(row['observed_at'] for row in revisions)
        selected = [row for row in revisions if row['observed_at'] == latest]
        events = [_detail_event(row['payload']['detail']) for row in selected]
        if any(ev != events[0] for ev in events):
            conflicts.update(ev[side] for ev in events for side in ('home_id', 'away_id'))
        elif events[0]['status'] == 'completed' and events[0]['scheduled_start'] < base['cutoff']:
            candidates.append((events[0], selected))
    used, gaps = {}, {}
    for side in ('home', 'away'):
        matches = [(ev, rows) for ev, rows in candidates if event[side+'_id'] in {ev['home_id'], ev['away_id']}]
        latest = max((ev['scheduled_start'] for ev, _ in matches), default=None)
        refs = sorted({row['digest'] for ev, rows in matches if ev['scheduled_start'] == latest for row in rows})
        gap = ((datetime.fromisoformat(event['scheduled_start'])-datetime.fromisoformat(latest)).total_seconds()/3600
               if latest is not None else None)
        state = 'conflicting' if event[side+'_id'] in conflicts else 'available' if gap is not None else 'missing'
        key = 'schedule.gap_hours_'+side
        result['values'][key] = gaps[side] = gap if state == 'available' else None
        result['states'][key] = state
        result['refs'][key] = used[side] = refs if state == 'available' else []
    key = 'schedule.gap_hours_delta'
    both = all(gaps[side] is not None for side in ('home', 'away'))
    result['values'][key] = gaps['home']-gaps['away'] if both else None
    result['states'][key] = 'available' if both else 'missing'
    result['refs'][key] = sorted(set(used['home']+used['away'])) if both else []
    return validate_feature_vector(result)


def effect_heads(fit):
    # Validate the coupled format before transporting two heads through A1.
    joint_offset_delta(fit, np.zeros((1, len(fit['scale']))))
    return {side: dict(link=LINK, scale=list(fit['scale']), coef=[pair[i] for pair in fit['coef']],
                      alpha=fit['alpha'], n_rows=fit['n_rows']) for i, side in enumerate(('home', 'away'))}


def fit_heads(cases, config, alpha):
    from context_models.training import _array
    matrices, x, outcomes = [], [], []
    for case in cases:
        payload = case['case']['payload']
        matrices.append(cell_matrix(payload['base']['params']['joint_cells']))
        x.append([payload['features']['values'][name] for name in config['feature_names']])
        outcome = next(row for row in case['observations'] if row['digest'] == payload['outcome_ref'])['payload']['result']
        # The live score matrix declares a pooled 25+ category, not exact 25.
        outcomes.append([min(outcome['goals_'+side], 25) for side in ('home', 'away')])
    return effect_heads(fit_joint_offset(tuple(matrices), _array(x), _array(outcomes), alpha=alpha))


def checked_joint_inputs(base, features, artifact, event):
    base, features = validate_base_distribution(base), validate_feature_vector(features)
    effect, event = validate_effect_artifact(artifact), validate_event(event)
    if (base['version'] != BASE_VERSION or base['family'] != 'football:goals:90min'
            or effect['model_variant'] != VERSION or features['version'] != FEATURE_VERSION
            or effect['feature_version'] != FEATURE_VERSION or features['coverage'] != COVERAGE
            or effect['coverage'] != COVERAGE or effect['preprocessing_artifacts']):
        raise ContextContractError('football joint effect law or feature coverage differs')
    if (base['event_key'] != event['event_key'] or features['event_key'] != event['event_key']
            or base['cutoff'] != features['cutoff'] or base['cutoff'] >= event['scheduled_start']
            or event['status'] != 'scheduled' or effect['training_end'] > base['cutoff']
            or not event_in_population(event, effect['population'])):
        raise ContextIntegrityError('joint effect event, time or population differs')
    reference = digest(dict(version='football-context-reference-v2', base_hash=digest(base), event_hash=digest(event), preprocessing=[]))
    if features['reference_hash'] != reference:
        raise ContextIntegrityError('joint features do not belong to this original')
    for name in effect['feature_names']:
        feature_group(name)
        if features['states'].get(name) != 'available' or not features['refs'].get(name):
            raise ContextContractError('consumed joint feature is unavailable')
    return base, features, effect, event


def apply_joint_effect(base, features, artifact, *, event):
    from context_models.football_effect import _numeric_array
    base, features, effect, event = checked_joint_inputs(base, features, artifact, event)
    heads = effect['heads']
    fit = dict(version=VERSION, scale=heads['home']['scale'],
        coef=[list(pair) for pair in zip(heads['home']['coef'], heads['away']['coef'])],
        alpha=heads['home']['alpha'], n_rows=heads['home']['n_rows'])
    x = _numeric_array([features['values'][name] for name in effect['feature_names']]).reshape(1, -1)
    delta = joint_offset_delta(fit, x)[0]
    matrix = tilt_joint(cell_matrix(base['params']['joint_cells']), *delta.tolist())
    cells = [[h, a, p] for (h, a), p in matrix.items()]
    return validate_base_distribution({**deepcopy(base), 'version': COMPARISON_VERSION,
        'model_hash': digest(dict(base=digest(base), features=digest(features), effect=digest(effect))),
        'params': joint_params(cells),
        'markets': {spec.key: engine.market_probability(matrix, spec) for spec in engine.GOAL_MARKET_SPECS}})
