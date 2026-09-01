from __future__ import annotations

import pytest

from riskobet_settlement import (
    SETTLEMENT_RULE_VERSION,
    BasketballMarket,
    BasketballResult,
    CricketDecisionMethod,
    CricketMarket,
    CricketOutcome,
    CricketResult,
    EsportsMarket,
    EsportsResult,
    EsportsTermination,
    EventStatus,
    FootballMarket,
    FootballResult,
    IceHockeyMarket,
    IceHockeyResult,
    Selection,
    SettlementInputError,
    SettlementStatus,
    Sport,
    TennisMarket,
    TennisResult,
    TennisTermination,
    settle_basketball,
    settle_cricket,
    settle_esports,
    settle_football,
    settle_ice_hockey,
    settle_market,
    settle_tennis,
)


def _status(result) -> SettlementStatus:
    assert result.rule_version == SETTLEMENT_RULE_VERSION
    return result.status


@pytest.mark.parametrize(
    "event_status",
    [
        EventStatus.SCHEDULED,
        EventStatus.LIVE,
        EventStatus.SUSPENDED,
        EventStatus.POSTPONED,
    ],
)
def test_non_terminal_state_is_unresolved_even_when_a_score_is_present(event_status):
    result = FootballResult(event_status, home_goals_90=4, away_goals_90=0)

    assert _status(
        settle_football(result, FootballMarket.RESULT_90_MINUTES, Selection.HOME)
    ) is SettlementStatus.UNRESOLVED


@pytest.mark.parametrize("event_status", [EventStatus.CANCELLED, EventStatus.ABANDONED])
def test_explicit_cancellation_or_abandonment_is_void(event_status):
    result = FootballResult(event_status, home_goals_90=4, away_goals_90=0)

    assert _status(
        settle_football(result, FootballMarket.RESULT_90_MINUTES, Selection.HOME)
    ) is SettlementStatus.VOID


def test_final_without_required_result_data_stays_unresolved():
    result = FootballResult(EventStatus.FINAL)

    assert _status(
        settle_football(result, FootballMarket.RESULT_90_MINUTES, Selection.HOME)
    ) is SettlementStatus.UNRESOLVED


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        (Selection.HOME, SettlementStatus.WIN),
        (Selection.AWAY, SettlementStatus.LOSS),
        (Selection.DRAW, SettlementStatus.LOSS),
    ],
)
def test_football_three_way_result(selection, expected):
    result = FootballResult(EventStatus.FINAL, home_goals_90=2, away_goals_90=1)

    assert _status(
        settle_football(result, FootballMarket.RESULT_90_MINUTES, selection)
    ) is expected


def test_football_draw_market_uses_regulation_and_ignores_extra_time_and_penalties():
    result = FootballResult(
        EventStatus.FINAL,
        home_goals_90=1,
        away_goals_90=1,
        home_goals_after_extra_time=2,
        away_goals_after_extra_time=1,
        winner_after_penalties=Selection.HOME,
    )

    assert _status(
        settle_football(result, FootballMarket.DRAW_90_MINUTES)
    ) is SettlementStatus.WIN
    assert _status(
        settle_football(result, FootballMarket.RESULT_90_MINUTES, Selection.HOME)
    ) is SettlementStatus.LOSS


@pytest.mark.parametrize(
    ("score", "selection", "expected"),
    [
        ((1, 1), Selection.HOME_OR_DRAW, SettlementStatus.WIN),
        ((0, 2), Selection.HOME_OR_DRAW, SettlementStatus.LOSS),
        ((0, 2), Selection.AWAY_OR_DRAW, SettlementStatus.WIN),
        ((1, 1), Selection.HOME_OR_AWAY, SettlementStatus.LOSS),
    ],
)
def test_football_double_chance(score, selection, expected):
    result = FootballResult(EventStatus.FINAL, *score)

    assert _status(
        settle_football(result, FootballMarket.DOUBLE_CHANCE_90_MINUTES, selection)
    ) is expected


@pytest.mark.parametrize(
    ("market", "goals", "expected"),
    [
        (FootballMarket.UNDERDOG_TEAM_OVER_0_5_90_MINUTES, 0, SettlementStatus.LOSS),
        (FootballMarket.UNDERDOG_TEAM_OVER_0_5_90_MINUTES, 1, SettlementStatus.WIN),
        (FootballMarket.UNDERDOG_TEAM_OVER_1_5_90_MINUTES, 1, SettlementStatus.LOSS),
        (FootballMarket.UNDERDOG_TEAM_OVER_1_5_90_MINUTES, 2, SettlementStatus.WIN),
    ],
)
def test_football_underdog_team_goal_boundaries(market, goals, expected):
    result = FootballResult(EventStatus.FINAL, home_goals_90=3, away_goals_90=goals)

    assert _status(settle_football(result, market, Selection.AWAY)) is expected


def test_tennis_match_winner_can_use_official_winner_without_set_score():
    result = TennisResult(EventStatus.FINAL, winner=Selection.AWAY)

    assert _status(
        settle_tennis(result, TennisMarket.MATCH_WINNER, Selection.AWAY)
    ) is SettlementStatus.WIN


@pytest.mark.parametrize(
    ("score", "market", "selection", "expected"),
    [
        ((2, 0), TennisMarket.AT_LEAST_ONE_SET, Selection.AWAY, SettlementStatus.LOSS),
        ((2, 1), TennisMarket.AT_LEAST_ONE_SET, Selection.AWAY, SettlementStatus.WIN),
        ((2, 1), TennisMarket.PLUS_1_5_SETS, Selection.AWAY, SettlementStatus.WIN),
        ((3, 1), TennisMarket.PLUS_1_5_SETS, Selection.AWAY, SettlementStatus.LOSS),
        ((2, 0), TennisMarket.OVER_2_5_SETS, Selection.OVER, SettlementStatus.LOSS),
        ((2, 1), TennisMarket.OVER_2_5_SETS, Selection.OVER, SettlementStatus.WIN),
    ],
)
def test_tennis_set_markets_use_the_completed_set_score(
    score, market, selection, expected
):
    result = TennisResult(EventStatus.FINAL, *score)

    assert _status(settle_tennis(result, market, selection)) is expected


@pytest.mark.parametrize(
    "termination",
    [TennisTermination.RETIREMENT, TennisTermination.WALKOVER],
)
@pytest.mark.parametrize("market", list(TennisMarket))
def test_tennis_retirement_and_walkover_void_every_supported_market(
    termination, market
):
    result = TennisResult(
        EventStatus.FINAL,
        home_sets=2,
        away_sets=0,
        winner=Selection.HOME,
        termination=termination,
    )
    selection = Selection.OVER if market is TennisMarket.OVER_2_5_SETS else Selection.HOME

    assert _status(settle_tennis(result, market, selection)) is SettlementStatus.VOID


def test_basketball_regulation_and_including_ot_are_distinct_contracts():
    result = BasketballResult(
        EventStatus.FINAL,
        home_points_regulation=90,
        away_points_regulation=90,
        home_points_final=101,
        away_points_final=105,
    )

    assert _status(
        settle_basketball(
            result, BasketballMarket.RESULT_REGULATION, Selection.DRAW
        )
    ) is SettlementStatus.WIN
    assert _status(
        settle_basketball(
            result,
            BasketballMarket.MATCH_WINNER_INCLUDING_OT,
            Selection.AWAY,
        )
    ) is SettlementStatus.WIN
    assert _status(
        settle_basketball(
            result, BasketballMarket.RESULT_REGULATION, Selection.AWAY
        )
    ) is SettlementStatus.LOSS


def test_basketball_final_tie_without_an_official_winner_stays_unresolved():
    result = BasketballResult(
        EventStatus.FINAL,
        home_points_final=100,
        away_points_final=100,
    )

    assert _status(
        settle_basketball(
            result,
            BasketballMarket.MATCH_WINNER_INCLUDING_OT,
            Selection.HOME,
        )
    ) is SettlementStatus.UNRESOLVED


def test_ice_hockey_regulation_draw_and_ot_winner_are_distinct():
    result = IceHockeyResult(
        EventStatus.FINAL,
        home_goals_60=2,
        away_goals_60=2,
        home_goals_final=2,
        away_goals_final=2,
        winner_including_ot=Selection.AWAY,
    )

    assert _status(
        settle_ice_hockey(result, IceHockeyMarket.DRAW_60_MINUTES)
    ) is SettlementStatus.WIN
    assert _status(
        settle_ice_hockey(
            result,
            IceHockeyMarket.MATCH_WINNER_INCLUDING_OT,
            Selection.AWAY,
        )
    ) is SettlementStatus.WIN


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        ((3, 2), SettlementStatus.WIN),
        ((4, 2), SettlementStatus.LOSS),
    ],
)
def test_ice_hockey_plus_1_5_puck_line_boundary(score, expected):
    result = IceHockeyResult(
        EventStatus.FINAL,
        home_goals_final=score[0],
        away_goals_final=score[1],
    )

    assert _status(
        settle_ice_hockey(
            result,
            IceHockeyMarket.PUCK_LINE_PLUS_1_5_INCLUDING_OT,
            Selection.AWAY,
        )
    ) is expected


@pytest.mark.parametrize(
    ("market", "goals", "expected"),
    [
        (IceHockeyMarket.TEAM_OVER_0_5_60_MINUTES, 0, SettlementStatus.LOSS),
        (IceHockeyMarket.TEAM_OVER_0_5_60_MINUTES, 1, SettlementStatus.WIN),
        (IceHockeyMarket.TEAM_OVER_1_5_60_MINUTES, 1, SettlementStatus.LOSS),
        (IceHockeyMarket.TEAM_OVER_1_5_60_MINUTES, 2, SettlementStatus.WIN),
    ],
)
def test_ice_hockey_team_goal_boundaries_are_60_minute_markets(
    market, goals, expected
):
    result = IceHockeyResult(
        EventStatus.FINAL,
        home_goals_60=4,
        away_goals_60=goals,
        home_goals_final=4,
        away_goals_final=goals + 3,
    )

    assert _status(
        settle_ice_hockey(result, market, Selection.AWAY)
    ) is expected


@pytest.mark.parametrize(
    ("outcome", "method", "selection", "expected"),
    [
        (
            CricketOutcome.HOME_WIN,
            CricketDecisionMethod.NORMAL,
            Selection.HOME,
            SettlementStatus.WIN,
        ),
        (
            CricketOutcome.HOME_WIN,
            CricketDecisionMethod.NORMAL,
            Selection.AWAY,
            SettlementStatus.LOSS,
        ),
        (
            CricketOutcome.AWAY_WIN,
            CricketDecisionMethod.DLS,
            Selection.AWAY,
            SettlementStatus.WIN,
        ),
        (
            CricketOutcome.HOME_WIN,
            CricketDecisionMethod.SUPER_OVER,
            Selection.HOME,
            SettlementStatus.WIN,
        ),
        (
            CricketOutcome.TIE,
            CricketDecisionMethod.NORMAL,
            Selection.HOME,
            SettlementStatus.VOID,
        ),
        (
            CricketOutcome.NO_RESULT,
            CricketDecisionMethod.NORMAL,
            Selection.AWAY,
            SettlementStatus.VOID,
        ),
    ],
)
def test_cricket_match_winner_defines_normal_dls_super_over_tie_and_no_result(
    outcome, method, selection, expected
):
    result = CricketResult(EventStatus.FINAL, outcome, method)

    assert _status(
        settle_cricket(result, CricketMarket.MATCH_WINNER, selection)
    ) is expected


def test_cricket_provider_gap_stays_unresolved():
    result = CricketResult(EventStatus.FINAL, outcome=None)

    assert _status(
        settle_cricket(result, CricketMarket.MATCH_WINNER, Selection.HOME)
    ) is SettlementStatus.UNRESOLVED


def test_esports_series_winner_and_at_least_one_map_settle_from_normal_series():
    result = EsportsResult(
        EventStatus.FINAL,
        home_maps=2,
        away_maps=1,
        winner=Selection.HOME,
    )

    assert _status(
        settle_esports(result, EsportsMarket.SERIES_WINNER, Selection.HOME)
    ) is SettlementStatus.WIN
    assert _status(
        settle_esports(result, EsportsMarket.AT_LEAST_ONE_MAP, Selection.AWAY)
    ) is SettlementStatus.WIN


def test_esports_zero_maps_loses_at_least_one_map():
    result = EsportsResult(EventStatus.FINAL, home_maps=2, away_maps=0)

    assert _status(
        settle_esports(result, EsportsMarket.AT_LEAST_ONE_MAP, Selection.AWAY)
    ) is SettlementStatus.LOSS


@pytest.mark.parametrize("market", list(EsportsMarket))
def test_esports_forfeit_voids_every_supported_market(market):
    result = EsportsResult(
        EventStatus.FINAL,
        home_maps=1,
        away_maps=0,
        winner=Selection.HOME,
        termination=EsportsTermination.FORFEIT,
    )

    assert _status(
        settle_esports(result, market, Selection.HOME)
    ) is SettlementStatus.VOID


def test_esports_cancellation_is_void_and_suspension_is_unresolved():
    cancelled = EsportsResult(EventStatus.CANCELLED)
    suspended = EsportsResult(EventStatus.SUSPENDED, home_maps=1, away_maps=0)

    assert _status(
        settle_esports(cancelled, EsportsMarket.SERIES_WINNER, Selection.HOME)
    ) is SettlementStatus.VOID
    assert _status(
        settle_esports(suspended, EsportsMarket.SERIES_WINNER, Selection.HOME)
    ) is SettlementStatus.UNRESOLVED


def test_generic_dispatch_accepts_serialized_enum_values():
    result = FootballResult("final", home_goals_90=1, away_goals_90=0)

    settlement = settle_market(
        sport="football",
        market="result_90_minutes",
        selection="home",
        result=result,
    )

    assert _status(settlement) is SettlementStatus.WIN


def test_generic_dispatch_rejects_result_from_the_wrong_sport():
    with pytest.raises(SettlementInputError, match="requires FootballResult"):
        settle_market(
            sport=Sport.FOOTBALL,
            market=FootballMarket.RESULT_90_MINUTES,
            selection=Selection.HOME,
            result=TennisResult(EventStatus.FINAL, 2, 0),
        )


@pytest.mark.parametrize(
    "bad_score",
    [-1, 1.5, True],
)
def test_malformed_scores_fail_closed_instead_of_being_coerced(bad_score):
    result = FootballResult(
        EventStatus.FINAL,
        home_goals_90=bad_score,
        away_goals_90=0,
    )

    with pytest.raises(SettlementInputError, match="non-negative integer"):
        settle_football(
            result,
            FootballMarket.RESULT_90_MINUTES,
            Selection.HOME,
        )


def test_conflicting_explicit_winner_and_score_is_rejected():
    result = TennisResult(
        EventStatus.FINAL,
        home_sets=2,
        away_sets=0,
        winner=Selection.AWAY,
    )

    with pytest.raises(SettlementInputError, match="conflicts"):
        settle_tennis(result, TennisMarket.MATCH_WINNER, Selection.HOME)


@pytest.mark.parametrize(
    ("result", "market", "settler"),
    [
        (
            TennisResult(
                EventStatus.FINAL,
                home_sets=1,
                away_sets=1,
                winner=Selection.HOME,
            ),
            TennisMarket.MATCH_WINNER,
            settle_tennis,
        ),
        (
            EsportsResult(
                EventStatus.FINAL,
                home_maps=1,
                away_maps=1,
                winner=Selection.HOME,
            ),
            EsportsMarket.SERIES_WINNER,
            settle_esports,
        ),
    ],
)
def test_tied_score_cannot_be_overridden_by_claimed_winner(
    result,
    market,
    settler,
):
    with pytest.raises(SettlementInputError, match="tied recorded score"):
        settler(result, market, Selection.HOME)


def test_market_selection_mismatch_is_rejected():
    result = FootballResult(EventStatus.FINAL, home_goals_90=1, away_goals_90=1)

    with pytest.raises(SettlementInputError, match="invalid"):
        settle_football(
            result,
            FootballMarket.DOUBLE_CHANCE_90_MINUTES,
            Selection.HOME,
        )
