"""Recent form is optional display evidence, not a new risk ranking input."""
from copy import deepcopy
from datetime import timedelta

from test_riskobet_candidates import football_pool, MODELED_AT, KICKOFF
from riskobet_candidates import adapt_football_candidates
from football_customer_facts import build_football_recent_results


def recent_results():
    fixture = {'fixture': {'id': 77, 'date': KICKOFF.isoformat()},
               'teams': {'home': {'id': 100}, 'away': {'id': 200}}}
    history = [{'fixture': {'id': 1000+i, 'date': (MODELED_AT-timedelta(days=i+1)).isoformat(),
                           'status': {'short': 'FT'}},
                'teams': {'home': {'id': 100, 'name': 'Home Underdog'},
                          'away': {'id': 500+i, 'name': 'Real opponent '+str(i)}},
                'goals': {'home': 2, 'away': 1}, 'league': {'name': 'Test League'}}
               for i in range(10)]
    return build_football_recent_results(fixture, history, as_of=MODELED_AT, model_scope='same_competition')


def adapt(recent=None):
    return adapt_football_candidates(football_pool(), modeled_at=MODELED_AT,
        input_cutoff_at=MODELED_AT, recent_results_by_fixture={'77': recent} if recent else {})[0]


def test_riskobet_form_and_opponent_facts_are_bound_but_never_change_selection_math():
    base = adapt()
    with_form = adapt(recent_results())
    assert with_form.candidates != ()
    assert [(c.market_key, c.model_probability) for c in base.candidates] == [
        (c.market_key, c.model_probability) for c in with_form.candidates]
    factors = {f.factor_key: f for f in with_form.snapshot.factors}
    assert '5S · 0U · 0N (5)' in factors['customer_recent_home'].summary
    assert '10S · 0U · 0N (10)' in factors['customer_recent_home'].summary
    assert 'Real opponent' in factors['customer_recent_home'].summary
    assert with_form.snapshot.input_hash != base.snapshot.input_hash


def test_riskobet_cannot_import_a_wrong_team_or_later_result_into_the_saved_revision():
    for key, value in [('home_id', 999), ('as_of', (MODELED_AT+timedelta(minutes=1)).isoformat())]:
        altered = deepcopy(recent_results())
        altered[key] = value
        result = adapt(altered)
        assert not any(f.factor_key.startswith('customer_recent_') for f in result.snapshot.factors)
        assert result.snapshot.input_hash == adapt().snapshot.input_hash


def test_display_form_cannot_increase_the_evidence_ranking_sample_size():
    from riskobet_domain import FactorRole
    from riskobet_quality import evidence_order
    pool = football_pool()
    for candidate in pool:
        candidate.venue_samples = (5, 5)
    base = adapt_football_candidates(pool, modeled_at=MODELED_AT, input_cutoff_at=MODELED_AT)[0]
    updated = adapt_football_candidates(pool, modeled_at=MODELED_AT, input_cutoff_at=MODELED_AT,
        recent_results_by_fixture={'77': recent_results()})[0]
    assert all(f.role == FactorRole.DISPLAY_ONLY for f in updated.snapshot.factors
               if f.factor_key.startswith('customer_recent_'))
    for old, new in zip(base.candidates, updated.candidates):
        # The immutable snapshot/candidate revision ID changes, not its data-quality rank.
        assert evidence_order(old, base.snapshot)[:-1] == evidence_order(new, updated.snapshot)[:-1]


def test_display_form_does_not_weaken_riskobet_existing_distinct_name_contract():
    pool = football_pool()
    for candidate in pool:
        candidate.home_team = candidate.away_team = 'United'
    recent = recent_results()
    recent['away'] = [{'fixture_id': 2000, 'played_at': (MODELED_AT-timedelta(days=1)).isoformat(),
        'opponent_id': 800, 'opponent': 'Away opponent', 'venue': 'away',
        'scored': 0, 'conceded': 3, 'competition': 'Test League'}]
    assert adapt_football_candidates(pool, modeled_at=MODELED_AT, input_cutoff_at=MODELED_AT,
        recent_results_by_fixture={'77': recent}) == ()
