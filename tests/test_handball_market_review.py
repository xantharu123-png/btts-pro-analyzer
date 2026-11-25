from copy import deepcopy
from datetime import datetime, timedelta, timezone
from math import log

import pytest


DECIDED = datetime(2026, 11, 25, 7, tzinfo=timezone.utc)
KICKOFF = DECIDED + timedelta(hours=10)


def _review(rows):
    from handball_market_review import review_handball_market

    return review_handball_market(iter(rows))


def _forecast(**changes):
    return {
        'fixture': [39, 2026, 1, 2, KICKOFF.isoformat()],
        'p': {'home': .5, 'draw': .2, 'away': .3},
        'decided_at': DECIDED.isoformat(),
        'price_source_at': (DECIDED - timedelta(minutes=5)).isoformat(),
        'price_observed_at': (DECIDED + timedelta(minutes=10)).isoformat(),
        'odds': {'Book A': [2., 4., 4.], 'Book B': [4., 2., 4.]},
        'result': 'draw',
        **changes,
    }


def test_report_pairs_one_result_and_averages_no_vig_books_without_mutating_evidence():
    row = _forecast()
    before = deepcopy(row)
    result = _review([row])
    # Book A implies (1/2, 1/4, 1/4), B (1/4, 1/2, 1/4); average (3/8, 3/8, 1/4).
    assert result['paired'] == 1
    assert result['model_brier'] == pytest.approx(.98)
    assert result['market_brier'] == pytest.approx(.59375)
    assert result['model_log_loss'] == pytest.approx(-log(.20))
    assert result['market_log_loss'] == pytest.approx(-log(.375))
    assert result['first_paired_kickoff'] == result['last_paired_kickoff'] == KICKOFF.isoformat()
    assert result['exclusions'] == {}
    assert row == before


def test_margin_is_removed_per_book_before_averaging():
    # A is 125% overround -> (2/5, 2/5, 1/5); B is 100% -> (1/4, 1/2, 1/4).
    result = _review([_forecast(odds={'Book A': [2., 2., 4.], 'Book B': [4., 2., 4.]})])
    assert result['market_brier'] == pytest.approx(.45875)
    assert result['market_log_loss'] == pytest.approx(-log(.45))


@pytest.mark.parametrize(('field', 'value', 'reason'), [
    ('odds', {}, 'missing_price'),
    ('odds', {'Book A': [2., 4.]}, 'invalid_market'),
    ('odds', {'Book A': [2., 4., 4.], 'BOOK A': [4., 2., 4.]}, 'invalid_market'),
    ('odds', {'Book A': [2., True, 4.]}, 'invalid_market'),
    ('odds', {'Book A': [2., 10**400, 4.]}, 'invalid_market'),
    ('p', {'home': .5, 'draw': .03, 'away': .3}, 'invalid_model'),
    ('p', {'home': .5, 'draw': float('nan'), 'away': .5}, 'invalid_model'),
    ('result', 'postponed', 'invalid_result'),
    ('fixture', [39, 2026, 1, 1, KICKOFF.isoformat()], 'invalid_fixture'),
    ('price_source_at', None, 'missing_clock'),
    ('price_source_at', '2026-11-25T07:01:00', 'invalid_clock'),
    ('price_source_at', (DECIDED + timedelta(minutes=15)).isoformat(), 'unmatched_clock'),
    ('price_observed_at', (DECIDED - timedelta(seconds=1)).isoformat(), 'unmatched_clock'),
    ('price_observed_at', KICKOFF.isoformat(), 'unmatched_clock'),
    ('price_source_at', (DECIDED + timedelta(minutes=10) - timedelta(hours=36)).isoformat(), 'stale_price'),
    ('price_source_at', (DECIDED - timedelta(hours=1, seconds=1)).isoformat(), 'asynchronous'),
    ('price_observed_at', (DECIDED + timedelta(hours=1, seconds=1)).isoformat(), 'asynchronous'),
])
def test_rejected_observations_do_not_score(field, value, reason):
    result = _review([_forecast(**{field: value})])
    assert result['paired'] == 0
    assert result['exclusions'] == {reason: 1}
    assert all(result[key] is None for key in (
        'model_brier', 'market_brier', 'model_log_loss', 'market_log_loss',
        'first_paired_kickoff', 'last_paired_kickoff',
    ))


def test_both_one_hour_boundaries_are_inclusive_at_observation():
    old = (DECIDED - timedelta(hours=1)).isoformat()
    observed = (DECIDED + timedelta(hours=1)).isoformat()
    assert _review([_forecast(price_source_at=old, price_observed_at=observed)])['paired'] == 1


def test_rescheduled_forecast_requires_price_from_confirmed_new_fixture():
    confirmed = (DECIDED - timedelta(minutes=1)).isoformat()
    stale = _forecast(revision_confirmed_at=confirmed)
    refreshed = _forecast(revision_confirmed_at=confirmed, price_source_at=confirmed)
    rejected = _review([stale])
    assert rejected['paired'] == 0
    assert rejected['exclusions'] == {'unmatched_revision_clock': 1}
    assert _review([refreshed])['paired'] == 1


@pytest.mark.parametrize('confirmed', [None, '2026-11-25T07:00:00',
                                       (DECIDED + timedelta(seconds=1)).isoformat()])
def test_present_invalid_reschedule_clock_does_not_fall_back_to_legacy(confirmed):
    source = (DECIDED + timedelta(minutes=2)).isoformat()
    result = _review([_forecast(revision_confirmed_at=confirmed, price_source_at=source)])
    assert result['paired'] == 0
    assert result['exclusions'] == {'unmatched_revision_clock': 1}


def test_report_sorts_kickoff_by_instant_and_ignores_not_yet_settled_rows():
    earlier = (KICKOFF - timedelta(minutes=15)).astimezone(timezone(timedelta(hours=2)))
    upcoming = _forecast()
    del upcoming['result']
    result = _review([_forecast(), upcoming, _forecast(fixture=[39, 2026, 3, 4, earlier.isoformat()])])
    assert result['paired'] == 2
    assert result['exclusions'] == {}
    assert result['first_paired_kickoff'] == earlier.astimezone(timezone.utc).isoformat()
    assert result['last_paired_kickoff'] == KICKOFF.isoformat()


def test_impossible_model_outcome_does_not_emit_infinite_json_loss():
    result = _review([_forecast(p={'home': .5, 'draw': 0., 'away': .5})])
    assert result['paired'] == 1
    assert result['model_brier'] == 1.5
    assert result['model_log_loss'] == pytest.approx(-log(1e-15))
