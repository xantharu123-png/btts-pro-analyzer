"""Shared, source-complete roster exposure coordinates, not player quality.

Individual baseline-relative columns remain intact. Separate losses and gains
avoid cancelling an absent player's minutes against a replacement's minutes.
Neither their size nor sign assigns a probability effect: coefficients still
need chronological fitting and an independent held-out test.
"""
from math import fsum
import re

from context_models.contracts import validate_feature_vector

PLAYER_COLUMN = re.compile(
    r'(home|away)\.((?:venue|form)_(?:attack|defense))\.(goals|xg)\.'
    r'api-football:player:[1-9][0-9]*'
)
POOL_SUFFIXES = ('loss_exposure_v1', 'gain_exposure_v1')
POOL_COLUMN = re.compile(
    r'roster\.(home|away)\.((?:venue|form)_(?:attack|defense))\.(goals|xg)\.'
    r'(loss_exposure_v1|gain_exposure_v1)'
)


def pooled_roster_features(roster):
    """Return fixed columns with exact lineage; missing is never healthy/zero.

    Values inherit the baseline's outer, pair and metric weights and 1/90
    scaling. Thus these are weighted minute-exposure changes, not literal
    injury counts, goal contributions, measured fatigue or player ratings.
    """
    roster = validate_feature_vector(roster)
    groups = {}
    for key in roster['values']:
        match = PLAYER_COLUMN.fullmatch(key)
        if match is not None:
            groups.setdefault(match.groups(), []).append(key)
    result = {'values': {}, 'states': {}, 'refs': {}}
    for side in ('home', 'away'):
        for component in ('venue_attack', 'venue_defense', 'form_attack', 'form_defense'):
            for metric in ('goals', 'xg'):
                keys = sorted(groups.get((side, component, metric), []))
                complete = bool(keys) and all(
                    roster['states'][key] == 'available' and roster['refs'][key]
                    for key in keys
                )
                inapplicable = bool(keys) and all(
                    roster['states'][key] == 'not_applicable' for key in keys
                )
                refs = sorted({ref for key in keys for ref in roster['refs'][key]}) if complete else []
                values = [roster['values'][key] for key in keys] if complete else []
                for suffix, sign in zip(POOL_SUFFIXES, (-1., 1.)):
                    name = f'roster.{side}.{component}.{metric}.{suffix}'
                    result['values'][name] = fsum(max(0., sign*value) for value in values) if complete else None
                    result['states'][name] = 'available' if complete else 'not_applicable' if inapplicable else 'missing'
                    result['refs'][name] = list(refs)
    return result
