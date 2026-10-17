"""Market coverage changes do not pretend to be prediction model changes."""
from copy import deepcopy

from challenge_engine import CHALLENGE_MARKET_CATALOG_SIGNATURE, CHALLENGE_PREDICTION_VERSION
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from test_daily3_selection import NOW
from wettfinder_automation import _football_state_from_snapshot, football_due


def test_new_market_catalog_metadata_is_separate_from_unchanged_prediction_identity():
    state = _football_state_from_snapshot(
        {'scanned_at': NOW.isoformat(), 'fixtures_found': 0, 'errors': []},
        attempted_at=NOW, search_date=NOW.date(),
    )
    assert state['discovery_model_version'] == CHALLENGE_PREDICTION_VERSION
    assert state['discovery_market_catalog_signature'] == CHALLENGE_MARKET_CATALOG_SIGNATURE


def test_due_decision_recognizes_catalog_coverage_without_running_or_mutating_a_scan():
    state = dict(status='completed', search_date=NOW.date().isoformat(),
        last_attempt_at=NOW.isoformat(), discovery_league_ids=sorted(ALTERNATIVE_MARKET_LEAGUES),
        discovery_model_version=CHALLENGE_PREDICTION_VERSION)
    before = deepcopy(state)
    legacy = football_due(state, now=NOW)
    assert legacy.due and legacy.reason == 'market_catalog_changed'
    assert state == before
    state['discovery_market_catalog_signature'] = CHALLENGE_MARKET_CATALOG_SIGNATURE
    current = football_due(state, now=NOW)
    assert not current.due and current.reason == 'daily_discovery_current'


def test_previous_95_market_discovery_cannot_hide_the_new_range_coverage():
    state = dict(status='completed', search_date=NOW.date().isoformat(),
        last_attempt_at=NOW.isoformat(), discovery_league_ids=sorted(ALTERNATIVE_MARKET_LEAGUES),
        discovery_model_version=CHALLENGE_PREDICTION_VERSION,
        discovery_market_catalog_signature='football-market-catalog:95-bounded-multigoal-v1')
    before = deepcopy(state)
    decision = football_due(state, now=NOW)
    assert decision.due and decision.reason == 'market_catalog_changed'
    assert state == before
