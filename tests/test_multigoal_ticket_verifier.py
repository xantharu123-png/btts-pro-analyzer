"""Standalone ticket-definition validation, without creating any backup."""
import hashlib
import json
import sqlite3

import pytest

from challenge_engine import MarketSpec, market_outcome
from scripts import backup_runtime_databases as verifier


NEW_DEFINITIONS = {
    'TOTAL_RANGE_1_3': ('total_range', None, None, 1, 3),
    'TOTAL_RANGE_1_4': ('total_range', None, None, 1, 4),
    'TOTAL_RANGE_2_4': ('total_range', None, None, 2, 4),
    'HOME_RANGE_1_4': ('team_range', 'home', None, 1, 4),
    'AWAY_RANGE_1_4': ('team_range', 'away', None, 1, 4),
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def verify_leg(key, definition):
    """Exercise the real definition verifier against a private memory-only DB.

    This is the definition layer, not a claim of full-ledger authentication.
    Each test computes an internally consistent v3 definition hash so semantic
    rejection cannot accidentally pass merely because its hash was stale.
    """
    kind, side, threshold, low, high = definition
    leg = dict(market_key=key, market_kind=kind, market_side=side,
               market_threshold=threshold, market_low=low, market_high=high,
               settlement_rule_version=2)
    evidence = [{'source': 'synthetic-unit-fixture'}]
    payload = dict(analysis_date='2026-10-17', legs=[leg], quote_evidence=evidence,
        reference_total_odds=1.8, played_total_odds=1.8, joint_probability=.7,
        expected_roi=.26, definition_version=3, stake_cents=100,
        created_at='2026-10-17T10:00:00+00:00', quote_verified_at='2026-10-17T10:00:00+00:00',
        analysis_timezone='Europe/Zurich', entry_source='MODEL',
        model_contract_signature='challenge-engine:hac-fdr-executable-frechet-v11')
    digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
    with sqlite3.connect(':memory:') as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('''CREATE TABLE challenge_tickets (
            id INTEGER, stake_cents INTEGER, payout_cents INTEGER,
            settlement_rule_version INTEGER, definition_version INTEGER,
            legs_json TEXT, quote_evidence_json TEXT, quote_evidence_hash TEXT,
            entry_source TEXT, model_contract_signature TEXT,
            ticket_definition_hash TEXT, created_at TEXT, analysis_timezone TEXT,
            total_odds REAL, played_odds REAL, analysis_date TEXT,
            joint_probability REAL, expected_roi REAL, quote_verified_at TEXT)''')
        connection.execute('INSERT INTO challenge_tickets VALUES (' + ','.join(['?'] * 19) + ')', (
            1, 100, 0, 2, 3, canonical([leg]), canonical(evidence),
            hashlib.sha256(canonical(evidence).encode()).hexdigest(), 'MODEL',
            payload['model_contract_signature'], digest, payload['created_at'],
            'Europe/Zurich', 1.8, 1.8, '2026-10-17', .7, .26, payload['quote_verified_at']))
        verifier._verify_ticket_definitions(connection)


@pytest.mark.parametrize('key,definition', NEW_DEFINITIONS.items())
def test_standalone_verifier_accepts_exact_new_multigoal_ticket_definition(key, definition):
    verify_leg(key, definition)


@pytest.mark.parametrize('key,home,away,want', [
    ('TOTAL_RANGE_1_3', 0, 0, False), ('TOTAL_RANGE_1_3', 1, 0, True),
    ('TOTAL_RANGE_1_3', 1, 2, True), ('TOTAL_RANGE_1_3', 1, 3, False),
    ('TOTAL_RANGE_1_4', 0, 0, False), ('TOTAL_RANGE_1_4', 0, 1, True),
    ('TOTAL_RANGE_1_4', 2, 2, True), ('TOTAL_RANGE_1_4', 2, 3, False),
    ('TOTAL_RANGE_2_4', 0, 1, False), ('TOTAL_RANGE_2_4', 1, 1, True),
    ('TOTAL_RANGE_2_4', 4, 0, True), ('TOTAL_RANGE_2_4', 5, 0, False),
    ('HOME_RANGE_1_4', 0, 2, False), ('HOME_RANGE_1_4', 1, 0, True),
    ('HOME_RANGE_1_4', 4, 5, True), ('HOME_RANGE_1_4', 5, 4, False),
    ('AWAY_RANGE_1_4', 2, 0, False), ('AWAY_RANGE_1_4', 0, 1, True),
    ('AWAY_RANGE_1_4', 5, 4, True), ('AWAY_RANGE_1_4', 4, 5, False),
])
def test_standalone_contract_fields_have_inclusive_total_and_role_bound_semantics(key, home, away, want):
    fields = verifier.CHALLENGE_MARKET_DEFINITIONS.get(key)
    assert fields is not None, f'missing standalone settlement contract for {key}'
    spec = MarketSpec(key, 'Synthetic', 'Synthetic', *fields)
    assert market_outcome(spec, home, away) is want


@pytest.mark.parametrize('key,definition', [
    ('TOTAL_RANGE_1_3', ('total_range', None, None, 0, 3)),
    ('TOTAL_RANGE_1_4', ('total_range', None, None, 1, 5)),
    ('TOTAL_RANGE_2_4', ('total_range', None, None, 1, 4)),
    ('HOME_RANGE_1_4', ('team_range', 'away', None, 1, 4)),
    ('AWAY_RANGE_1_4', ('team_range', 'home', None, 1, 4)),
    ('TOTAL_RANGE_0_99', ('total_range', None, None, 0, 99)),
])
def test_standalone_verifier_rejects_changed_bounds_side_and_unknown_contract(key, definition):
    with pytest.raises(RuntimeError, match='market definition is invalid'):
        verify_leg(key, definition)


def test_original_ninety_standalone_definitions_remain_byte_identical():
    old = {key: value for key, value in verifier.CHALLENGE_MARKET_DEFINITIONS.items()
           if key not in NEW_DEFINITIONS}
    assert len(old) == 90
    # Captured from the standalone verifier before adding the five definitions.
    assert hashlib.sha256(canonical(old).encode()).hexdigest() == (
        '34ce6ea1952d6c5fae8a6d3c43808a713e94c2cc4dff0a8f7474e0842062c739')
