from dataclasses import replace
from datetime import datetime, timezone

import pytest

import challenge_engine as engine
from forecast_analysis import project_football_analysis, read_football_analysis
from forecast_selection import select_event_leads
from test_football_form_comparison_capture import _match
from test_wettfinder_statistical_leads import card, signal


def test_wettfinder_candidates_keep_the_already_calculated_outcomes_without_exporting_to_ticket():
    match, history = _match()
    pairs = []
    candidates = engine.build_fixture_candidates(
        match, history, {}, goal_model=engine.PRODUCTION_GOAL_MODEL,
        candidate_profile=engine.CANDIDATE_PROFILE_WETTFINDER, form_comparison_capture=pairs.append,
    )
    pair, = pairs
    double_chances = [c for c in candidates if c.market_key.startswith('DC_')]
    assert len(double_chances) == 3
    for candidate in double_chances:
        assert getattr(candidate, 'result_probabilities', None) == pair['with_form']
        assert 'result_probabilities' not in candidate.to_dict()
    assert all(getattr(c, 'result_probabilities', None) is None
               for c in candidates if not c.market_key.startswith('DC_'))


def _evidence_case():
    instant = '2030-01-01T10:00:00+00:00'
    return dict(candidate_id='1:DC_X2', fixture_id=1, home_team='Heim', away_team='Gast',
                market_key='DC_X2', probability=.593201, model_scope='same_competition',
                home_id=10, away_id=20, scheduled_start='2030-01-01T15:00:00+00:00',
                modeled_at=instant, input_cutoff_at=instant, model_version='known-law')


def test_distribution_is_bound_to_the_exact_candidate_and_its_model_version():
    row = _evidence_case()
    vector = [.406799, .2775, .315701]
    row['analysis_evidence'] = project_football_analysis(row, model_basis=dict(row, result_probabilities=vector))
    assert read_football_analysis(row)['basis'].get('result_probabilities') == vector
    persisted_wrong_model = dict(row, model_version='other-law')
    assert 'result_probabilities' not in read_football_analysis(persisted_wrong_model)['basis']
    assert read_football_analysis(dict(row, home_id=20, away_id=10)) is None
    assert read_football_analysis(row, now=datetime(2029, 1, 1, tzinfo=timezone.utc)) is None


def test_projection_cannot_relabel_same_law_and_marginal_from_a_different_model_clock():
    row = _evidence_case()
    prior = dict(row, modeled_at='2030-01-01T09:45:00+00:00', input_cutoff_at='2030-01-01T09:45:00+00:00',
                 result_probabilities=[.406799, .6 - .406799, .4],
                 expected_home_goals=1.5, expected_away_goals=1.1)
    # Same fixture, model version, and exact X2 probability; not the same revision.
    row['analysis_evidence'] = project_football_analysis(row, model_basis=prior)
    assert read_football_analysis(row)['basis'] == {'expected_home_goals': 1.5, 'expected_away_goals': 1.1}


@pytest.mark.parametrize('vector', [[.41, .28, .32], [.32, .28, .40], [True, 0, 0], [.41, .59], None])
def test_unusable_distribution_does_not_invalidate_legacy_analysis_or_get_a_model_pin(vector):
    row = _evidence_case()
    row['analysis_evidence'] = project_football_analysis(
        row, model_basis=dict(row, expected_home_goals=1.5, expected_away_goals=1.1, result_probabilities=vector),
    )
    assert read_football_analysis(row)['basis'] == {'expected_home_goals': 1.5, 'expected_away_goals': 1.1}


@pytest.mark.parametrize(('key', 'p', 'excluded'), [('DC_1X', .54, 2), ('DC_X2', .54, 0), ('DC_12', .54, 1)])
def test_a_cover_that_excludes_the_unique_most_likely_outcome_cannot_become_the_primary(key, p, excluded):
    weak = card(signal(1, key, p, .14))
    acceptable = card(signal(1, 'TOTAL_UNDER_4_5', .52, .10))
    chances = [.31, .31, .31]
    chances[(excluded + 1) % 3] = .23
    chances[excluded] = .46
    contradicted = replace(weak, result_probabilities=tuple(chances))
    assert select_event_leads([contradicted, acceptable], require_comparable=True) == [acceptable]
    assert select_event_leads([contradicted], require_comparable=True) == []
    # A tie does not supply a unique conflicting outcome; the broad cover remains rankable.
    chances = [.2, .2, .2]
    chances[excluded] = chances[(excluded + 1) % 3] = .4
    tied = replace(weak, model_probability=.6, result_probabilities=tuple(chances))
    assert select_event_leads([tied], require_comparable=True) == [tied]
