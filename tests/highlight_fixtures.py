"""Explicit synthetic positive context receipts for presentation-flow tests.

These are not production data. Tests of absent or stale coverage must omit or
replace the individual checks rather than relying on a blanket release flag.
"""


def football_checks(now):
    stamp = now.isoformat()
    return {
        'checked_at': stamp,
        'h2h': {'status': 'neutral', 'availability': 'available',
                'matches': 0, 'checked_at': stamp},
        'weather': {'status': 'passed', 'availability': 'available',
                    'veto_applied': False, 'checked_at': stamp},
        'injuries': {'status': 'observed', 'availability': 'available',
                     'coverage_available': True, 'home_missing': 0,
                     'away_missing': 0, 'checked_at': stamp},
        # Morning cards do not require a confirmed starting lineup.
        'lineups': {'status': 'pending', 'checked_at': stamp},
        'release_context_complete': False,
    }
