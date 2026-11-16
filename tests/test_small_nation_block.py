"""Owner 16.11.2026 „Beides“: no under-goal tips in senior national games against a small nation until the model
is repaired (docs/audits/2026-11-16-laenderspiele-kleinstaaten-ergebnis.md). Evidence is not touched."""
from types import SimpleNamespace

import pytest

from ev_signal_sources import SMALL_NATIONS, small_nation_under_blocked, without_small_nation_unders


def signal(home, away, key, scope='senior_national_pooled'):
    return SimpleNamespace(home_team=home, away_team=away, market_key=key, model_scope=scope)


@pytest.mark.parametrize('home,away,key,blocked', [
    # Favourite at home against a small nation: its own under, total under and combos with under.
    ('Finland', 'San Marino', 'HOME_UNDER_2_5', True),
    ('Finland', 'San Marino', 'HOME_UNDER_1_5', True),
    ('Finland', 'San Marino', 'TOTAL_UNDER_3_5', True),
    ('Finland', 'San Marino', 'RESULT_TOTAL_1X_UNDER_3_5', True),
    # Favourite away (Kazakhstan - Slovakia on 16.11.2026).
    ('Kazakhstan', 'Slovakia', 'AWAY_UNDER_2_5', True),
    ('Kazakhstan', 'Slovakia', 'TOTAL_UNDER_3_5', True),
    # The small nation's own goals, overs, ranges and results stay.
    ('Finland', 'San Marino', 'AWAY_UNDER_2_5', False),
    ('Kazakhstan', 'Slovakia', 'HOME_UNDER_1_5', False),
    ('Finland', 'San Marino', 'TOTAL_OVER_1_5', False),
    ('Finland', 'San Marino', 'HOME_RANGE_2_4', False),
    ('Finland', 'San Marino', 'MIXED_HOME_OR_OVER_2_5', False),
    ('Finland', 'San Marino', 'HOME_CORNERS_UNDER_5_5', False),
    # Two small nations, or none: the confirmed gap does not apply.
    ('Lithuania', 'Liechtenstein', 'TOTAL_UNDER_3_5', False),
    ('Spain', 'England', 'HOME_UNDER_2_5', False),
])
def test_only_under_goal_markets_against_exactly_one_small_nation_are_blocked(home, away, key, blocked):
    assert small_nation_under_blocked(signal(home, away, key)) is blocked


def test_club_games_and_missing_scope_are_never_blocked():
    assert not small_nation_under_blocked(signal('Finland', 'San Marino', 'HOME_UNDER_2_5', scope='same_competition'))
    assert not small_nation_under_blocked(signal('Finland', 'San Marino', 'HOME_UNDER_2_5', scope=None))
    assert not small_nation_under_blocked(SimpleNamespace())


def test_filter_keeps_order_and_every_other_row():
    rows = [signal('Finland', 'San Marino', 'TOTAL_OVER_1_5'), signal('Finland', 'San Marino', 'HOME_UNDER_2_5'),
            signal('Spain', 'England', 'HOME_UNDER_2_5'), signal('Kazakhstan', 'Slovakia', 'AWAY_UNDER_2_5')]
    assert without_small_nation_unders(rows) == [rows[0], rows[2]]


def test_small_nations_match_the_pre_registered_list():
    assert SMALL_NATIONS == {
        "San Marino", "Liechtenstein", "Gibraltar", "Andorra", "Malta", "Moldova", "Faroe Islands", "Luxembourg",
        "Kazakhstan", "Latvia", "Lithuania", "Estonia", "Armenia", "Azerbaijan", "Cyprus",
    }


def test_loader_applies_the_block_at_its_single_return():
    import inspect
    import ev_signal_sources
    source = inspect.getsource(ev_signal_sources.automated_wettfinder_forecasts)
    assert source.rstrip().endswith('return without_small_nation_unders(forecasts)')
