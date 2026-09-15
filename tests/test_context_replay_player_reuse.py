"""Synthetic chronological mechanics, not effect or empirical qualification."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from context_models.contracts import ContextIntegrityError, digest
from context_models.replay import _selected_native_rows, football_context_input_refs, replay_base_distribution
from context_training_helpers import NOW, envelope, football_inventory, football_recipe
from test_context_replay_identity_refresh import persist


@pytest.fixture(scope='module')
def inventory(tmp_path_factory):
    return football_inventory(tmp_path_factory.mktemp('native-roster-reuse'))


def recipe_for(history, decision=NOW):
    latest = _selected_native_rows(history, decision=decision.isoformat())
    payload = football_recipe(latest)['payload']
    payload.update(schema=2, context_refs=football_context_input_refs(history, decision_at=decision))
    return envelope('context-base-replay-recipe-v1', payload)


def run(event, history, identity, recipe):
    return replay_base_distribution('football', event, history, decision_at=NOW,
        reconstructed_at=NOW, recipe=recipe, identity_map=identity)['payload']['base']


def pool_with_summary(inventory, tmp_path, *, change=None):
    event, history, _, identity = deepcopy(inventory)
    full = next(row for row in history if row['event_key'] != event['event_key'])
    summary = deepcopy(full['payload']['detail'])
    summary.pop('players')
    summary.pop('lineups')
    if change == 'empty':
        summary['players'] = []
    elif change == 'result':
        summary['goals']['home'] += 1
    newer = persist(tmp_path, summary, NOW - timedelta(minutes=5))
    return event, history + newer, identity, full, newer[0]


def test_replay_reuses_real_old_player_clock_without_changing_latest_math_or_v1(inventory, tmp_path, monkeypatch):
    event, pool, identity, old, summary = pool_with_summary(inventory, tmp_path)
    original = deepcopy((event, pool, identity))
    latest = _selected_native_rows(pool, decision=NOW.isoformat())
    legacy = run(event, pool, identity, football_recipe(latest))
    from context_sources import football_native
    native_receipts = []
    original_provenance = football_native.football_native_provenance
    def observe(fixtures, receipts, **kwargs):
        native_receipts.extend(receipts)
        return original_provenance(fixtures, receipts, **kwargs)
    monkeypatch.setattr(football_native, 'football_native_provenance', observe)
    recipe = recipe_for(pool)
    upgraded = run(event, pool, identity, recipe)
    assert recipe['payload']['context_refs'] == [old['digest']]
    assert old['digest'] not in recipe['payload']['input_refs']
    assert summary['digest'] in recipe['payload']['input_refs']
    assert upgraded['params'] == legacy['params'] and upgraded['markets'] == legacy['markets']
    key = old['event_key']
    prior = next(row for row in legacy['history_refs'] if row['native_event_key'] == key)
    current = next(row for row in upgraded['history_refs'] if row['native_event_key'] == key)
    assert prior['roster_join'] == 'unresolved'
    assert current['roster_join'] == 'verified_native'
    # Inspect the owning provenance boundary, not a displayed approximation.
    assert [row for row in native_receipts if row['detail']['fixture']['id'] == old['payload']['detail']['fixture']['id']] == [
        {'detail': old['payload']['detail'], 'observed_at': old['observed_at']}]
    assert (event, pool, identity) == original


@pytest.mark.parametrize('change', ['empty', 'result'])
def test_explicit_withdrawal_or_native_result_correction_never_revives_old_players(inventory, tmp_path, change):
    event, pool, identity, old, _ = pool_with_summary(inventory, tmp_path, change=change)
    recipe = recipe_for(pool)
    assert recipe['payload']['context_refs'] == []
    base = run(event, pool, identity, recipe)
    assert next(row for row in base['history_refs'] if row['native_event_key'] == old['event_key'])['roster_join'] == 'unresolved'


@pytest.mark.parametrize('wrong', ['missing', 'unrelated', 'duplicate'])
def test_context_receipts_cannot_be_omitted_substituted_or_duplicated(inventory, tmp_path, wrong):
    event, pool, identity, old, _ = pool_with_summary(inventory, tmp_path)
    payload = recipe_for(pool)['payload']
    payload['context_refs'] = {'missing': [], 'unrelated': ['f'*64], 'duplicate': [old['digest']]*2}[wrong]
    with pytest.raises(ValueError):
        run(event, pool, identity, envelope('context-base-replay-recipe-v1', payload))


def test_simultaneous_older_detail_conflict_stops_reuse(inventory, tmp_path):
    event, pool, identity, old, _ = pool_with_summary(inventory, tmp_path)
    changed = deepcopy(old['payload']['detail'])
    changed['players'][0]['players'][0]['statistics'][0]['games']['minutes'] += 1
    collision = persist(tmp_path, changed, datetime.fromisoformat(old['observed_at']), name='collision')
    recipe = recipe_for(pool + collision)
    assert recipe['payload']['context_refs'] == []
    base = run(event, pool + collision, identity, recipe)
    assert next(row for row in base['history_refs'] if row['native_event_key'] == old['event_key'])['roster_join'] == 'unresolved'


def test_full_training_case_reuses_projected_players_after_summary_without_medical_receipt(tmp_path):
    from test_context_training_cases import football_case
    from context_models.football import football_features
    from context_models.training_cases import assemble_training_cases
    from context_models.training_contracts import validate_resolved_case
    resolved, config = football_case(tmp_path)
    payload = resolved['case']['payload']
    decision = datetime.fromisoformat(payload['base']['cutoff'])
    old = next(row for row in resolved['observations'] if row['kind'] == 'base_fixture'
        and row['event_key'] != payload['event']['event_key'])
    summary = deepcopy(old['payload']['detail'])
    summary.pop('players')
    summary.pop('lineups')
    added = persist(tmp_path, summary, decision - timedelta(minutes=5))
    resolved['observations'] += added
    history = tuple(row for row in resolved['observations'] if row['kind'] == 'base_fixture')
    recipe = recipe_for(history, decision)
    identity = resolved['artifacts'][payload['event_identity_hash']]
    rebuilt = replay_base_distribution('football', payload['event'], history, decision_at=decision,
        reconstructed_at=NOW, recipe=recipe, identity_map=identity)
    base = rebuilt['payload']['base']
    features = football_features(payload['event'], tuple(row for row in resolved['observations']
        if row['kind'] != 'match_outcome'), base, cutoff=decision)
    assert features['values'] == payload['features']['values']
    payload.update(base=base, features=features, replay_ref=rebuilt['digest'])
    resolved['artifacts'] = {row['digest']: row for row in (rebuilt, recipe, identity)}
    resolved['case'] = envelope('context-training-case-v1', payload)
    assert validate_resolved_case(resolved, config=config) == resolved
    assembled = assemble_training_cases((resolved,), config)
    assert assembled['canonical_events'] == 1 and len(assembled['rows']) == 2
    assert assembled['excluded'] == ()


@pytest.mark.parametrize('context', ['valid', 'missing', 'late'])
def test_d4_checks_schema_two_context_receipts_as_real_references(tmp_path, context):
    import sqlite3
    from context_observations import append_observation, observations_as_of
    from context_sources.football import _detail_event
    from context_sources.outcomes import normalize_football_base_input
    from context_runtime import verify_context_database
    from model_artifacts import ArtifactIntegrityError, put_artifact
    event, history, _, _ = football_inventory(tmp_path, count=1)
    path = tmp_path / 'synthetic-football-9000.db'
    old = next(row for row in history if row['event_key'] != event['event_key'])
    summary = deepcopy(old['payload']['detail'])
    summary.pop('players')
    received = NOW - timedelta(minutes=5)
    record = normalize_football_base_input(summary, observed_at=received)
    append_observation(path, record, observed_at=received)
    selected = observations_as_of(path, old['event_key'], cutoff=NOW,
        schedule_revision=_detail_event(summary)['schedule_revision'])
    pool = history + tuple(row for row in selected if row['kind'] == 'base_fixture'
        and row['digest'] != old['digest'])
    recipe = recipe_for(pool)
    if context == 'missing':
        recipe['payload']['context_refs'] = ['f'*64]
    elif context == 'late':
        late_clock = NOW + timedelta(seconds=1)
        late = normalize_football_base_input(old['payload']['detail'], observed_at=late_clock)
        late_ref = append_observation(path, late, observed_at=late_clock)
        recipe['payload']['context_refs'] = [late_ref]
    put_artifact(path, kind=recipe['kind'], payload=recipe['payload'], created_at=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA journal_mode=DELETE')
    before = path.read_bytes()
    if context == 'valid':
        report = verify_context_database(path)
        assert 'd1-original-replay-context-unavailable' in report['limitations']
        assert report['empirical_approval_verified'] is False
    else:
        with pytest.raises(ArtifactIntegrityError, match='context database verification failed') as rejected:
            verify_context_database(path)
        assert isinstance(rejected.value.__cause__, ContextIntegrityError)
    assert path.read_bytes() == before
