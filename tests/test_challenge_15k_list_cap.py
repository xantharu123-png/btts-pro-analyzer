"""Owner decisions 03.11.2026: the 15K page shows at most five games, one ticket per day, and per
game the most probable market that can be a ticket leg (fresh quote at or above 1.25)."""
import inspect
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import challenge_15k
import ev_signal_sources
import wettfinder_automation
from challenge_engine import MARKET_BY_KEY, MAX_TICKET_LEGS, MIN_CHALLENGE_LEG_ODDS
from market_consensus import MarketConsensus, QuotePoint, REFERENCE_SOURCE, exact_market_target
from tests.test_challenge_15k import candidate

NOW = datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc)
KICKOFF = NOW + timedelta(hours=5)


def _quote(item, odds):
    bet_name, value_name = exact_market_target(item.market_key) or ("", "")
    return MarketConsensus(
        fixture_id=item.fixture_id, candidate_id=item.candidate_id, market_key=item.market_key,
        bet_name=bet_name, value_name=value_name, consensus_odds=odds, conservative_odds=odds,
        lowest_odds=odds, best_odds=odds, bookmaker_count=4, quoted_at=NOW.isoformat(),
        fetched_at=NOW.isoformat(), source=REFERENCE_SOURCE,
        points=tuple(QuotePoint(bookmaker=f"Book {index}", odds=odds, bookmaker_id=f"api-football:{index}",
                                observed_at=NOW.isoformat()) for index in range(1, 5)),
        scheduled_start=item.kickoff, event_home=item.home_team, event_away=item.away_team,
    )


def _market(candidate_id, fixture_id, probability, market_key):
    spec = MARKET_BY_KEY[market_key]
    return replace(candidate(candidate_id, fixture_id, probability, kickoff=KICKOFF),
                   market_key=market_key, market=spec.market, selection=spec.selection)


def test_caps_are_five_and_internal_bounds_unchanged():
    assert challenge_15k.CHALLENGE_PAGE_MAX_GAMES == 5
    assert ev_signal_sources.MAX_AUTOMATED_CHALLENGE_RELEASE_CANDIDATES == 5
    assert challenge_15k.MAX_PUBLIC_FORECASTS == 15
    assert MAX_TICKET_LEGS == 3 and MIN_CHALLENGE_LEG_ODDS == 1.25


@pytest.mark.price_policy("floor")
def test_leg_odds_follow_the_ticket_floor():
    item = _market("1:HOME_UNDER_2_5", 1, 0.69, "HOME_UNDER_2_5")
    leg = lambda odds: challenge_15k.challenge_leg_odds(  # noqa: E731
        _quote(item, odds), candidate=item, now=NOW)
    assert leg(1.91) == pytest.approx(1.91)
    assert leg(1.25) == pytest.approx(1.25)
    assert leg(1.22) is None
    assert challenge_15k.challenge_leg_odds(None, candidate=item, now=NOW) is None


@pytest.mark.price_policy("floor")
def test_page_shows_per_game_the_most_probable_leg_capable_market():
    # 03.11.2026: the most probable market of a game had odds of 1.0x and hid the game although
    # another market of the same game was playable as a ticket leg.
    pool = [
        _market("1:HOME_OVER_0_5", 1, 0.86, "HOME_OVER_0_5"),      # 1.05: below the 1.20 floor
        _market("1:HOME_UNDER_2_5", 1, 0.69, "HOME_UNDER_2_5"),    # 1.91: the leg to show
        _market("2:HOME_UNDER_2_5", 2, 0.90, "HOME_UNDER_2_5"),    # 1.03 only: game stays off the page
        _market("3:AWAY_OVER_0_5", 3, 0.76, "AWAY_OVER_0_5"),      # 1.22: above the floor, below the leg floor
        _market("3:AWAY_UNDER_2_5", 3, 0.70, "AWAY_UNDER_2_5"),    # 1.30: the leg to show
        *(_market(f"{index}:BTTS_YES", index, probability, "BTTS_YES")
          for index, probability in ((4, 0.80), (5, 0.79), (6, 0.78), (7, 0.60))),  # 1.50 each
    ]
    odds = {"1:HOME_OVER_0_5": 1.05, "1:HOME_UNDER_2_5": 1.91, "2:HOME_UNDER_2_5": 1.03,
            "3:AWAY_OVER_0_5": 1.22, "3:AWAY_UNDER_2_5": 1.30}
    quotes = {item.candidate_id: _quote(item, odds.get(item.candidate_id, 1.50)) for item in pool}

    chosen = challenge_15k._challenge_page_selections(pool, quotes, now=NOW)

    assert [item.candidate_id for item in chosen] == [
        "4:BTTS_YES", "5:BTTS_YES", "6:BTTS_YES", "3:AWAY_UNDER_2_5", "1:HOME_UNDER_2_5"]
    assert len({item.fixture_id for item in chosen}) == 5
    started = [replace(item, kickoff=(NOW - timedelta(hours=1)).isoformat()) for item in pool]
    assert challenge_15k._challenge_page_selections(
        started, {item.candidate_id: _quote(item, 1.50) for item in started}, now=NOW) == []


@pytest.mark.price_policy("floor")
def test_ticket_pool_rows_need_a_leg_capable_offer():
    item = _market("1:HOME_UNDER_2_5", 1, 0.69, "HOME_UNDER_2_5")
    row = {"source": "football_challenge", "fixture_id": 1, "candidate_id": item.candidate_id,
           "market_key": item.market_key, "scheduled_start": KICKOFF, "minimum_odds": item.minimum_odds,
           "home_team": item.home_team, "away_team": item.away_team}
    assert wettfinder_automation._challenge_leg_capable({**row, "reference_quote": _quote(item, 1.91).to_dict()}, now=NOW)
    assert not wettfinder_automation._challenge_leg_capable({**row, "reference_quote": _quote(item, 1.22).to_dict()}, now=NOW)
    assert not wettfinder_automation._challenge_leg_capable(row, now=NOW)
    for source in (wettfinder_automation.run_wettfinder, wettfinder_automation._republish_floor_candidates):
        text = inspect.getsource(source)
        assert "_challenge_leg_capable(" in text
        assert "[:MAX_AUTOMATED_CHALLENGE_RELEASE_CANDIDATES]" in text


def test_render_uses_the_page_selection():
    render = inspect.getsource(challenge_15k._render_model_challenge)
    assert "_challenge_page_selections(pool, quotes, now=now)" in render
    assert "leads" not in render and "_challenge_display_selections" not in render
    assert "[:CHALLENGE_PAGE_MAX_GAMES]" in inspect.getsource(challenge_15k._challenge_page_selections)
