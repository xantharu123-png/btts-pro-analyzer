"""Real persisted source transport with synthetic clocks, not quality proof."""
from copy import deepcopy
from datetime import timedelta

import pytest

from context_models.tennis_v3 import tennis_features_v3
from context_models.tennis_v4 import tennis_features_v4
from context_sources.tennis_status import tennis_observations_as_of
from test_context_tennis_capture import NOW, competition, records, persist
from test_tennis_context_features import event, base


def append(db, at, *, started=False, raw=None, partial=False):
    raw = raw or competition(date=(NOW-timedelta(days=3)).isoformat())
    if started:
        raw = deepcopy(raw)
        raw['status'] = {'type': {'state': 'in', 'name': 'STATUS_IN_PROGRESS', 'completed': False}}
    values = records(raw, clock=at)
    return persist(db, values[:2] if partial else values, clock=at)


def calculate(db, *, at=NOW):
    history = tennis_observations_as_of(db, cutoff=at, tour='ATP')
    ev = event()
    return tennis_features_v4(ev, history, base(ev, cutoff=at), cutoff=at), history


def test_measured_sets_and_games_without_fabricated_end_or_duration(tmp_path):
    db = tmp_path/'v4.db'
    running = append(db, NOW-timedelta(hours=5), started=True)
    final = append(db, NOW-timedelta(hours=3))
    result, history = calculate(db)
    before = deepcopy(history)
    assert result['values']['bounded_sets_1d_a'] == 2
    assert result['values']['bounded_games_1d_a'] == 18
    assert result['values']['bounded_sets_complete_1d_a'] == 1
    assert result['values']['bounded_sets_1d_delta'] == 0
    assert set(result['refs']['bounded_sets_1d_a']) == set(running+final)
    assert result['values']['bounded_minutes_1d_a'] is None
    assert result['values']['bounded_minutes_complete_1d_a'] == 0
    assert result['values']['observed_recovery_exact_hours_a'] is None
    assert all(r['payload'].get('actual_end') is None for r in history)
    legacy = tennis_features_v3(event(), history, base(), cutoff=NOW)
    assert legacy['values']['observed_sets_1d_a'] is None
    assert history == before


@pytest.mark.parametrize('lower_hours,expected', [(23, 2), (24, 2), (25, None)])
def test_entire_interval_must_fit_in_window_not_just_final_receipt(tmp_path, lower_hours, expected):
    db = tmp_path/'v4.db'
    append(db, NOW-timedelta(hours=lower_hours), started=True)
    append(db, NOW-timedelta(hours=22))
    result, _ = calculate(db)
    assert result['values']['bounded_sets_1d_a'] == expected
    assert result['values']['bounded_sets_complete_1d_a'] == int(expected is not None)
    assert result['values']['bounded_sets_3d_a'] == 2


def test_scheduled_start_or_terminal_receipt_alone_is_not_a_running_lower_bound(tmp_path):
    db = tmp_path/'v4.db'
    append(db, NOW-timedelta(hours=3))
    result, _ = calculate(db)
    assert result['values']['bounded_sets_1d_a'] is None
    assert result['values']['bounded_sets_complete_1d_a'] == 0
    assert result['values']['bounded_recovery_minimum_hours_a'] == 9


def test_repeated_polling_keeps_first_proven_end_upper_bound(tmp_path):
    db = tmp_path/'v4.db'
    append(db, NOW-timedelta(hours=29), started=True)
    append(db, NOW-timedelta(hours=27))
    before, _ = calculate(db)
    append(db, NOW-timedelta(hours=2))
    result, history = calculate(db)
    # Old match stays outside today's load, despite a fresh result poll.
    assert result['values']['bounded_sets_1d_a'] is None
    assert result['values']['bounded_sets_3d_a'] == 2
    assert result['values']['bounded_recovery_minimum_hours_a'] == 33
    assert result['values']['bounded_recovery_minimum_hours_a'] == before['values']['bounded_recovery_minimum_hours_a']
    assert result['values']['observed_recovery_minimum_hours_a'] < before['values']['observed_recovery_minimum_hours_a']
    duplicate = tennis_features_v4(event(), history+history, base(), cutoff=NOW)
    assert duplicate == result


@pytest.mark.parametrize('change', ['cancelled', 'unknown', 'scheduled', 'participant', 'schedule', 'partial', 'score'])
def test_corrections_cannot_borrow_timing_from_invalidated_receipts(tmp_path, change):
    db = tmp_path/'v4.db'
    append(db, NOW-timedelta(hours=8), started=True)
    append(db, NOW-timedelta(hours=6))
    raw = competition()
    if change in {'cancelled', 'unknown', 'scheduled'}:
        state, code, completed = {'cancelled': ('post','STATUS_CANCELED',True),
            'unknown': ('bad','STATUS_UNKNOWN',False), 'scheduled': ('pre','STATUS_SCHEDULED',False)}[change]
        raw['status'] = {'type': dict(state=state, name=code, completed=completed)}
    elif change == 'participant':
        raw['competitors'][0]['id'] = '7'
    elif change == 'schedule':
        raw['date'] = '2026-09-09T01:00Z'
    elif change == 'score':
        raw['competitors'][0]['linescores'][0]['value'] = 7
    append(db, NOW-timedelta(hours=4), raw=raw, partial=change == 'partial')
    append(db, NOW-timedelta(hours=2))
    result, _ = calculate(db)
    assert result['values']['bounded_sets_1d_a'] is None
    assert result['values']['bounded_sets_complete_1d_a'] == 0


def test_later_running_receipt_starts_a_new_proof_interval(tmp_path):
    db = tmp_path/'v4.db'
    append(db, NOW-timedelta(hours=8), started=True)
    append(db, NOW-timedelta(hours=6))
    append(db, NOW-timedelta(hours=4), started=True)
    append(db, NOW-timedelta(hours=2))
    result, _ = calculate(db)
    assert result['values']['bounded_sets_1d_a'] == 2


def test_late_correction_not_consumed_by_earlier_cutoff(tmp_path):
    db = tmp_path/'v4.db'
    append(db, NOW-timedelta(hours=5), started=True)
    append(db, NOW-timedelta(hours=3))
    before, _ = calculate(db)
    append(db, NOW+timedelta(seconds=1), started=True)
    after, _ = calculate(db)
    assert before == after


def test_incomplete_other_known_match_prevents_complete_observed_load_claim(tmp_path):
    db = tmp_path/'v4.db'
    append(db, NOW-timedelta(hours=5), started=True)
    append(db, NOW-timedelta(hours=3))
    append(db, NOW-timedelta(hours=1), raw=competition(id='102'))
    result, _ = calculate(db)
    assert result['values']['bounded_sets_1d_a'] == 2
    assert result['values']['bounded_sets_complete_1d_a'] == 0


def test_future_schedule_is_not_missing_played_work_but_reopened_match_is(tmp_path):
    db = tmp_path/'v4.db'
    append(db, NOW-timedelta(hours=5), started=True)
    append(db, NOW-timedelta(hours=3))
    before, _ = calculate(db)
    future = competition(id='888', date=(NOW+timedelta(days=2)).isoformat(),
        status={'type':{'state':'pre', 'completed':False, 'name':'STATUS_SCHEDULED'}})
    append(db, NOW-timedelta(hours=1), raw=future)
    after, _ = calculate(db)
    assert after == before
    # Already-observed play must never be hidden by a later future schedule.
    future['id'] = '101'
    append(db, NOW-timedelta(minutes=30), raw=future)
    reopened, _ = calculate(db)
    assert reopened['values']['bounded_sets_1d_a'] is None


@pytest.mark.parametrize('tour', ['ATP', 'WTA'])
def test_bounded_load_replays_trains_and_changes_only_experimental_complementary_probabilities(tmp_path, tour):
    from datetime import datetime
    from context_models.tennis_live import original_base
    from context_models.tennis_training import build_live_training_case
    from context_models.training_cases import assemble_training_cases
    from context_models.training import fit_family
    from context_models.tennis_effect import apply_tennis_effect, tennis_context_result
    from context_models.training_contracts import validate_family_config
    from context_models.tennis_v4 import FEATURE_VERSION, COVERAGE_VERSION, TRAINING_VARIANT
    from model_artifacts import load_artifact
    from test_tennis_live_training import packet, live_config
    from test_context_tennis_outcome_capture import completed
    db, originals, outcomes, identity, built = packet(tmp_path, tour=tour)
    for index, ref in enumerate(originals):
        origin = load_artifact(db, ref)['payload']['origin']
        decision = datetime.fromisoformat(origin['cutoff'])
        for side in (0, 1):
            received = decision-timedelta(hours=(24 if (index+side) % 2 else 48))
            raw = completed(event_id=str(1000+index*10+side))
            raw['date'] = (received-timedelta(hours=4)).isoformat()
            raw['competitors'][0]['id'] = str(100+index*10+side)
            raw['competitors'][1]['id'] = str(5000+index*10+side)
            if (index+side) % 2:
                for pos, player in enumerate(raw['competitors']):
                    player['linescores'] = [{'value': 6 if (set_index % 2 == pos) else 4,
                                             'winner': set_index % 2 == pos} for set_index in range(5)]
            start = deepcopy(raw)
            start['status'] = {'type': {'state':'in', 'name':'STATUS_IN_PROGRESS', 'completed':False}}
            for at, competition_row in ((received+timedelta(minutes=1), start), (received+timedelta(minutes=2), raw)):
                persist(db, records(competition_row, clock=at, tour=tour,
                    slug='mens-singles' if tour == 'ATP' else 'womens-singles'), clock=at)
    config = live_config(tour)
    config.update(feature_version=FEATURE_VERSION, reference_version='tennis-context-reference-v4',
        model_variant=TRAINING_VARIANT, feature_names=['bounded_sets_3d_delta'],
        groups={'workload':['bounded_sets_3d_delta']})
    config['coverage']['version'] = COVERAGE_VERSION
    assert validate_family_config(config) == config
    cases = [build_live_training_case(db, original_ref=o, outcome_ref=r, identity_ref=identity,
        config=config, as_of=built) for o, r in zip(originals, outcomes)]
    train = tuple(cases[:4])
    assembly = assemble_training_cases(train, config)
    assert not assembly['excluded'] and assembly['canonical_events'] == 4
    fitted = fit_family(assembly['rows'], config, cases=train)
    assert fitted['status'] == 'fitted'
    final = cases[-1]['case']['payload']
    before = deepcopy(final)
    changed = apply_tennis_effect(final['base'], final['features'], fitted['artifact'], event=final['event'])
    assert changed['markets']['winner_a'] != final['base']['markets']['winner_a']
    assert changed['markets']['winner_a']+changed['markets']['winner_b'] == pytest.approx(1.)
    unapproved = tennis_context_result(final['base'], final['features'],
        {'kind':'context-effect-v1', 'payload':fitted['artifact']}, event=final['event'], effect_hash=fitted['effect_hash'])
    assert unapproved['role'] != 'applied' and unapproved['used_markets'] == final['base']['markets']
    assert final == before


def test_v3_config_cannot_consume_v4_workload_under_old_identity():
    from context_models.training_contracts import validate_family_config
    from context_models.contracts import ContextContractError
    from test_tennis_live_training import live_config
    config = live_config()
    config.update(feature_names=['bounded_sets_1d_delta'], groups={'workload':['bounded_sets_1d_delta']})
    with pytest.raises(ContextContractError):
        validate_family_config(config)


def test_empirical_report_binds_actual_v4_implementation():
    from context_models.evaluator import implementation_hashes
    import context_models.tennis_v4 as module
    import hashlib
    from pathlib import Path
    assert implementation_hashes()['context_models/tennis_v4.py'] == hashlib.sha256(
        Path(module.__file__).read_bytes()).hexdigest()


def test_legacy_workload_revisions_are_one_match_not_additional_play(tmp_path):
    from test_tennis_context_features import stored, native_row
    early = stored(tmp_path, [native_row(sets=(2, 1))], receipt=NOW-timedelta(minutes=30))
    later = stored(tmp_path, [native_row(sets=(3, 2))], receipt=NOW-timedelta(minutes=10))
    result = tennis_features_v4(event(), early+later, base(), cutoff=NOW)
    assert result['values']['bounded_sets_1d_a'] == 5
    assert result['values']['bounded_minutes_1d_a'] == 120
    assert result['values']['bounded_sets_complete_1d_a'] == 1
