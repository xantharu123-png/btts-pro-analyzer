"""Pure, provider-independent settlement rules for RisikoBet shadow markets.

The module deliberately consumes canonical result records rather than provider
payloads.  Provider adapters are responsible for translating their payloads to
these records and must never infer a terminal state from elapsed time.  Every
supported market therefore returns one of ``WIN``, ``LOSS``, ``VOID`` or
``UNRESOLVED`` and carries the versioned rule that produced the decision.

V1 policy choices which are otherwise bookmaker-specific are explicit here:

* football markets use the score after regulation time;
* tennis retirement and walkover void every supported market;
* basketball and ice-hockey regulation markets exclude overtime;
* ice-hockey puck line includes overtime, while team-goal markets use 60 min;
* cricket ties and no-results void match-winner selections, while an official
  DLS or Super-Over winner settles normally;
* an e-sport forfeit or cancellation voids every supported market.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias, TypeVar


SETTLEMENT_RULE_VERSION = "riskobet-settlement-v1"


class SettlementInputError(ValueError):
    """Raised for a malformed or unsupported settlement contract."""


class SettlementStatus(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    VOID = "VOID"
    UNRESOLVED = "UNRESOLVED"


class Sport(str, Enum):
    FOOTBALL = "football"
    TENNIS = "tennis"
    BASKETBALL = "basketball"
    ICE_HOCKEY = "ice_hockey"
    CRICKET = "cricket"
    ESPORTS = "esports"


class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    SUSPENDED = "suspended"
    POSTPONED = "postponed"
    FINAL = "final"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"


class Selection(str, Enum):
    HOME = "home"
    AWAY = "away"
    DRAW = "draw"
    HOME_OR_DRAW = "home_or_draw"
    AWAY_OR_DRAW = "away_or_draw"
    HOME_OR_AWAY = "home_or_away"
    OVER = "over"


class FootballMarket(str, Enum):
    RESULT_90_MINUTES = "result_90_minutes"
    DRAW_90_MINUTES = "draw_90_minutes"
    DOUBLE_CHANCE_90_MINUTES = "double_chance_90_minutes"
    UNDERDOG_TEAM_OVER_0_5_90_MINUTES = "underdog_team_over_0_5_90_minutes"
    UNDERDOG_TEAM_OVER_1_5_90_MINUTES = "underdog_team_over_1_5_90_minutes"


class TennisMarket(str, Enum):
    MATCH_WINNER = "match_winner"
    AT_LEAST_ONE_SET = "at_least_one_set"
    PLUS_1_5_SETS = "plus_1_5_sets"
    OVER_2_5_SETS = "over_2_5_sets"


class BasketballMarket(str, Enum):
    MATCH_WINNER_INCLUDING_OT = "match_winner_including_ot"
    RESULT_REGULATION = "result_regulation"


class IceHockeyMarket(str, Enum):
    MATCH_WINNER_INCLUDING_OT = "match_winner_including_ot"
    RESULT_60_MINUTES = "result_60_minutes"
    DRAW_60_MINUTES = "draw_60_minutes"
    PUCK_LINE_PLUS_1_5_INCLUDING_OT = "puck_line_plus_1_5_including_ot"
    TEAM_OVER_0_5_60_MINUTES = "team_over_0_5_60_minutes"
    TEAM_OVER_1_5_60_MINUTES = "team_over_1_5_60_minutes"


class CricketMarket(str, Enum):
    MATCH_WINNER = "match_winner"


class EsportsMarket(str, Enum):
    SERIES_WINNER = "series_winner"
    AT_LEAST_ONE_MAP = "at_least_one_map"


class TennisTermination(str, Enum):
    NORMAL = "normal"
    RETIREMENT = "retirement"
    WALKOVER = "walkover"


class CricketOutcome(str, Enum):
    HOME_WIN = "home_win"
    AWAY_WIN = "away_win"
    TIE = "tie"
    NO_RESULT = "no_result"


class CricketDecisionMethod(str, Enum):
    NORMAL = "normal"
    DLS = "dls"
    SUPER_OVER = "super_over"


class EsportsTermination(str, Enum):
    NORMAL = "normal"
    FORFEIT = "forfeit"


@dataclass(frozen=True)
class SettlementResult:
    status: SettlementStatus
    reason: str
    rule_version: str = SETTLEMENT_RULE_VERSION


@dataclass(frozen=True)
class FootballResult:
    status: EventStatus | str
    home_goals_90: int | None = None
    away_goals_90: int | None = None
    home_goals_after_extra_time: int | None = None
    away_goals_after_extra_time: int | None = None
    winner_after_penalties: Selection | str | None = None


@dataclass(frozen=True)
class TennisResult:
    status: EventStatus | str
    home_sets: int | None = None
    away_sets: int | None = None
    winner: Selection | str | None = None
    termination: TennisTermination | str = TennisTermination.NORMAL


@dataclass(frozen=True)
class BasketballResult:
    status: EventStatus | str
    home_points_regulation: int | None = None
    away_points_regulation: int | None = None
    home_points_final: int | None = None
    away_points_final: int | None = None


@dataclass(frozen=True)
class IceHockeyResult:
    status: EventStatus | str
    home_goals_60: int | None = None
    away_goals_60: int | None = None
    home_goals_final: int | None = None
    away_goals_final: int | None = None
    winner_including_ot: Selection | str | None = None


@dataclass(frozen=True)
class CricketResult:
    status: EventStatus | str
    outcome: CricketOutcome | str | None = None
    decision_method: CricketDecisionMethod | str = CricketDecisionMethod.NORMAL


@dataclass(frozen=True)
class EsportsResult:
    status: EventStatus | str
    home_maps: int | None = None
    away_maps: int | None = None
    winner: Selection | str | None = None
    termination: EsportsTermination | str = EsportsTermination.NORMAL


CanonicalResult: TypeAlias = (
    FootballResult
    | TennisResult
    | BasketballResult
    | IceHockeyResult
    | CricketResult
    | EsportsResult
)


@dataclass(frozen=True)
class ParsedSettlementContract:
    """Canonical, sport-bound interpretation of a frozen contract string."""

    rule_version: str
    sport: Sport
    market: Enum
    selection: Selection


_MARKETS_BY_SPORT: dict[Sport, type[Enum]] = {
    Sport.FOOTBALL: FootballMarket,
    Sport.TENNIS: TennisMarket,
    Sport.BASKETBALL: BasketballMarket,
    Sport.ICE_HOCKEY: IceHockeyMarket,
    Sport.CRICKET: CricketMarket,
    Sport.ESPORTS: EsportsMarket,
}

_SELECTIONS_BY_MARKET: dict[Enum, frozenset[Selection]] = {
    FootballMarket.RESULT_90_MINUTES: frozenset(
        {Selection.HOME, Selection.AWAY, Selection.DRAW}
    ),
    FootballMarket.DRAW_90_MINUTES: frozenset({Selection.DRAW}),
    FootballMarket.DOUBLE_CHANCE_90_MINUTES: frozenset(
        {Selection.HOME_OR_DRAW, Selection.AWAY_OR_DRAW, Selection.HOME_OR_AWAY}
    ),
    FootballMarket.UNDERDOG_TEAM_OVER_0_5_90_MINUTES: frozenset(
        {Selection.HOME, Selection.AWAY}
    ),
    FootballMarket.UNDERDOG_TEAM_OVER_1_5_90_MINUTES: frozenset(
        {Selection.HOME, Selection.AWAY}
    ),
    TennisMarket.MATCH_WINNER: frozenset({Selection.HOME, Selection.AWAY}),
    TennisMarket.AT_LEAST_ONE_SET: frozenset({Selection.HOME, Selection.AWAY}),
    TennisMarket.PLUS_1_5_SETS: frozenset({Selection.HOME, Selection.AWAY}),
    TennisMarket.OVER_2_5_SETS: frozenset({Selection.OVER}),
    BasketballMarket.MATCH_WINNER_INCLUDING_OT: frozenset(
        {Selection.HOME, Selection.AWAY}
    ),
    BasketballMarket.RESULT_REGULATION: frozenset(
        {Selection.HOME, Selection.AWAY, Selection.DRAW}
    ),
    IceHockeyMarket.MATCH_WINNER_INCLUDING_OT: frozenset(
        {Selection.HOME, Selection.AWAY}
    ),
    IceHockeyMarket.RESULT_60_MINUTES: frozenset(
        {Selection.HOME, Selection.AWAY, Selection.DRAW}
    ),
    IceHockeyMarket.DRAW_60_MINUTES: frozenset({Selection.DRAW}),
    IceHockeyMarket.PUCK_LINE_PLUS_1_5_INCLUDING_OT: frozenset(
        {Selection.HOME, Selection.AWAY}
    ),
    IceHockeyMarket.TEAM_OVER_0_5_60_MINUTES: frozenset(
        {Selection.HOME, Selection.AWAY}
    ),
    IceHockeyMarket.TEAM_OVER_1_5_60_MINUTES: frozenset(
        {Selection.HOME, Selection.AWAY}
    ),
    CricketMarket.MATCH_WINNER: frozenset({Selection.HOME, Selection.AWAY}),
    EsportsMarket.SERIES_WINNER: frozenset({Selection.HOME, Selection.AWAY}),
    EsportsMarket.AT_LEAST_ONE_MAP: frozenset({Selection.HOME, Selection.AWAY}),
}


def parse_settlement_contract(
    value: str,
    *,
    candidate: object | None = None,
) -> ParsedSettlementContract:
    """Parse and optionally bind a contract to its frozen candidate payload."""

    if type(value) is not str or not value or value != value.strip() or len(value) > 240:
        raise SettlementInputError("settlement contract must be canonical text")
    parts = value.split(":")
    if len(parts) != 4 or any(not part for part in parts):
        raise SettlementInputError("settlement contract must contain four fields")
    rule_version, sport_value, market_value, selection_value = parts
    if rule_version != SETTLEMENT_RULE_VERSION:
        raise SettlementInputError("unsupported settlement rule version")
    sport = _enum(sport_value, Sport, "settlement sport")
    market = _enum(
        market_value,
        _MARKETS_BY_SPORT[sport],
        f"{sport.value} settlement market",
    )
    selection = _enum(selection_value, Selection, "settlement selection")
    if selection not in _SELECTIONS_BY_MARKET[market]:
        raise SettlementInputError(
            f"Selection {selection.value!r} is invalid for {market.value}"
        )
    if candidate is not None:
        if not isinstance(candidate, dict):
            try:
                candidate = dict(candidate)  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise SettlementInputError("candidate payload must be a mapping") from exc
        if candidate.get("settlement_contract") != value:
            raise SettlementInputError("candidate settlement contract mismatch")
        if candidate.get("sport") != sport.value:
            raise SettlementInputError("candidate sport differs from settlement contract")
        if candidate.get("market_key") != market.value:
            raise SettlementInputError("candidate market differs from settlement contract")
        if candidate.get("selection_key") != selection.value:
            raise SettlementInputError("candidate selection differs from settlement contract")
    return ParsedSettlementContract(rule_version, sport, market, selection)


EnumT = TypeVar("EnumT", bound=Enum)


def _enum(value: EnumT | str, enum_type: type[EnumT], field: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise SettlementInputError(f"Unsupported {field}: {value!r}") from exc


def _optional_enum(
    value: EnumT | str | None,
    enum_type: type[EnumT],
    field: str,
) -> EnumT | None:
    if value is None:
        return None
    return _enum(value, enum_type, field)


def _score(value: int | None, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SettlementInputError(f"{field} must be a non-negative integer")
    return value


def _score_pair(
    home: int | None,
    away: int | None,
    *,
    home_field: str,
    away_field: str,
) -> tuple[int, int] | None:
    clean_home = _score(home, home_field)
    clean_away = _score(away, away_field)
    if clean_home is None or clean_away is None:
        return None
    return clean_home, clean_away


def _lifecycle(status: EventStatus | str) -> SettlementResult | None:
    clean_status = _enum(status, EventStatus, "event status")
    if clean_status in {EventStatus.CANCELLED, EventStatus.ABANDONED}:
        return SettlementResult(SettlementStatus.VOID, f"event_{clean_status.value}")
    if clean_status is not EventStatus.FINAL:
        return SettlementResult(
            SettlementStatus.UNRESOLVED,
            f"event_{clean_status.value}",
        )
    return None


def _unresolved(reason: str) -> SettlementResult:
    return SettlementResult(SettlementStatus.UNRESOLVED, reason)


def _settled(won: bool, reason: str) -> SettlementResult:
    return SettlementResult(
        SettlementStatus.WIN if won else SettlementStatus.LOSS,
        reason,
    )


def _require_selection(
    value: Selection | str | None,
    allowed: set[Selection],
    market: Enum,
) -> Selection:
    if value is None:
        raise SettlementInputError(f"{market.value} requires a selection")
    selection = _enum(value, Selection, "selection")
    if selection not in allowed:
        raise SettlementInputError(
            f"Selection {selection.value!r} is invalid for {market.value}"
        )
    return selection


def _side_score(selection: Selection, home: int, away: int) -> tuple[int, int]:
    if selection is Selection.HOME:
        return home, away
    if selection is Selection.AWAY:
        return away, home
    raise SettlementInputError("A team/player selection must be home or away")


def _score_winner(home: int, away: int) -> Selection | None:
    if home > away:
        return Selection.HOME
    if away > home:
        return Selection.AWAY
    return None


def _validated_winner(
    explicit: Selection | str | None,
    scores: tuple[int, int] | None,
    *,
    field: str,
    allow_tied_explicit: bool = False,
) -> Selection | None:
    clean = _optional_enum(explicit, Selection, field)
    if clean not in {None, Selection.HOME, Selection.AWAY}:
        raise SettlementInputError(f"{field} must be home or away")
    derived = _score_winner(*scores) if scores is not None else None
    if (
        scores is not None
        and derived is None
        and clean is not None
        and not allow_tied_explicit
    ):
        raise SettlementInputError(f"{field} conflicts with the tied recorded score")
    if clean is not None and derived is not None and clean is not derived:
        raise SettlementInputError(f"{field} conflicts with the recorded score")
    return clean or derived


def settle_football(
    result: FootballResult,
    market: FootballMarket | str,
    selection: Selection | str | None = None,
) -> SettlementResult:
    """Settle supported football markets strictly from the 90-minute score."""

    clean_market = _enum(market, FootballMarket, "football market")
    gate = _lifecycle(result.status)
    if gate is not None:
        return gate
    scores = _score_pair(
        result.home_goals_90,
        result.away_goals_90,
        home_field="home_goals_90",
        away_field="away_goals_90",
    )
    if scores is None:
        return _unresolved("football_regulation_score_missing")
    home, away = scores

    if clean_market is FootballMarket.RESULT_90_MINUTES:
        choice = _require_selection(
            selection,
            {Selection.HOME, Selection.AWAY, Selection.DRAW},
            clean_market,
        )
        winner = _score_winner(home, away) or Selection.DRAW
        return _settled(choice is winner, "football_result_90_minutes")

    if clean_market is FootballMarket.DRAW_90_MINUTES:
        if selection is not None and _enum(selection, Selection, "selection") is not Selection.DRAW:
            raise SettlementInputError("draw_90_minutes only accepts draw")
        return _settled(home == away, "football_draw_90_minutes")

    if clean_market is FootballMarket.DOUBLE_CHANCE_90_MINUTES:
        choice = _require_selection(
            selection,
            {
                Selection.HOME_OR_DRAW,
                Selection.AWAY_OR_DRAW,
                Selection.HOME_OR_AWAY,
            },
            clean_market,
        )
        winner = _score_winner(home, away) or Selection.DRAW
        covered = {
            Selection.HOME_OR_DRAW: {Selection.HOME, Selection.DRAW},
            Selection.AWAY_OR_DRAW: {Selection.AWAY, Selection.DRAW},
            Selection.HOME_OR_AWAY: {Selection.HOME, Selection.AWAY},
        }
        return _settled(winner in covered[choice], "football_double_chance_90_minutes")

    choice = _require_selection(
        selection,
        {Selection.HOME, Selection.AWAY},
        clean_market,
    )
    team_goals, _ = _side_score(choice, home, away)
    line = (
        0.5
        if clean_market is FootballMarket.UNDERDOG_TEAM_OVER_0_5_90_MINUTES
        else 1.5
    )
    return _settled(team_goals > line, f"football_team_over_{line:.1f}_90_minutes")


def settle_tennis(
    result: TennisResult,
    market: TennisMarket | str,
    selection: Selection | str | None = None,
) -> SettlementResult:
    """Settle tennis markets under the V1 all-markets retirement void rule."""

    clean_market = _enum(market, TennisMarket, "tennis market")
    gate = _lifecycle(result.status)
    if gate is not None:
        return gate
    termination = _enum(result.termination, TennisTermination, "tennis termination")
    if termination in {TennisTermination.RETIREMENT, TennisTermination.WALKOVER}:
        return SettlementResult(
            SettlementStatus.VOID,
            f"tennis_{termination.value}_void",
        )
    scores = _score_pair(
        result.home_sets,
        result.away_sets,
        home_field="home_sets",
        away_field="away_sets",
    )
    winner = _validated_winner(result.winner, scores, field="tennis winner")

    if clean_market is TennisMarket.MATCH_WINNER:
        choice = _require_selection(
            selection, {Selection.HOME, Selection.AWAY}, clean_market
        )
        if winner is None:
            return _unresolved("tennis_winner_missing")
        return _settled(choice is winner, "tennis_match_winner")

    if clean_market is TennisMarket.OVER_2_5_SETS:
        if selection is not None and _enum(selection, Selection, "selection") is not Selection.OVER:
            raise SettlementInputError("over_2_5_sets only accepts over")
        if scores is None:
            return _unresolved("tennis_set_score_missing")
        return _settled(sum(scores) > 2.5, "tennis_over_2_5_sets")

    choice = _require_selection(
        selection, {Selection.HOME, Selection.AWAY}, clean_market
    )
    if scores is None:
        return _unresolved("tennis_set_score_missing")
    selected_sets, opponent_sets = _side_score(choice, *scores)
    if clean_market is TennisMarket.AT_LEAST_ONE_SET:
        return _settled(selected_sets >= 1, "tennis_at_least_one_set")
    return _settled(
        selected_sets + 1.5 > opponent_sets,
        "tennis_plus_1_5_sets",
    )


def settle_basketball(
    result: BasketballResult,
    market: BasketballMarket | str,
    selection: Selection | str | None,
) -> SettlementResult:
    """Settle basketball winner markets with an explicit time scope."""

    clean_market = _enum(market, BasketballMarket, "basketball market")
    gate = _lifecycle(result.status)
    if gate is not None:
        return gate
    if clean_market is BasketballMarket.MATCH_WINNER_INCLUDING_OT:
        choice = _require_selection(
            selection, {Selection.HOME, Selection.AWAY}, clean_market
        )
        scores = _score_pair(
            result.home_points_final,
            result.away_points_final,
            home_field="home_points_final",
            away_field="away_points_final",
        )
        if scores is None or _score_winner(*scores) is None:
            return _unresolved("basketball_final_winner_missing")
        return _settled(choice is _score_winner(*scores), "basketball_winner_including_ot")

    choice = _require_selection(
        selection,
        {Selection.HOME, Selection.AWAY, Selection.DRAW},
        clean_market,
    )
    scores = _score_pair(
        result.home_points_regulation,
        result.away_points_regulation,
        home_field="home_points_regulation",
        away_field="away_points_regulation",
    )
    if scores is None:
        return _unresolved("basketball_regulation_score_missing")
    outcome = _score_winner(*scores) or Selection.DRAW
    return _settled(choice is outcome, "basketball_result_regulation")


def settle_ice_hockey(
    result: IceHockeyResult,
    market: IceHockeyMarket | str,
    selection: Selection | str | None = None,
) -> SettlementResult:
    """Settle ice-hockey markets with explicit 60-minute/including-OT scope."""

    clean_market = _enum(market, IceHockeyMarket, "ice-hockey market")
    gate = _lifecycle(result.status)
    if gate is not None:
        return gate

    if clean_market is IceHockeyMarket.MATCH_WINNER_INCLUDING_OT:
        choice = _require_selection(
            selection, {Selection.HOME, Selection.AWAY}, clean_market
        )
        final_scores = _score_pair(
            result.home_goals_final,
            result.away_goals_final,
            home_field="home_goals_final",
            away_field="away_goals_final",
        )
        winner = _validated_winner(
            result.winner_including_ot,
            final_scores,
            field="ice-hockey winner_including_ot",
            allow_tied_explicit=True,
        )
        if winner is None:
            return _unresolved("ice_hockey_final_winner_missing")
        return _settled(choice is winner, "ice_hockey_winner_including_ot")

    if clean_market is IceHockeyMarket.PUCK_LINE_PLUS_1_5_INCLUDING_OT:
        choice = _require_selection(
            selection, {Selection.HOME, Selection.AWAY}, clean_market
        )
        scores = _score_pair(
            result.home_goals_final,
            result.away_goals_final,
            home_field="home_goals_final",
            away_field="away_goals_final",
        )
        if scores is None:
            return _unresolved("ice_hockey_final_score_missing")
        selected, opponent = _side_score(choice, *scores)
        return _settled(
            selected + 1.5 > opponent,
            "ice_hockey_puck_line_plus_1_5_including_ot",
        )

    regulation_scores = _score_pair(
        result.home_goals_60,
        result.away_goals_60,
        home_field="home_goals_60",
        away_field="away_goals_60",
    )
    if regulation_scores is None:
        return _unresolved("ice_hockey_60_minute_score_missing")
    home, away = regulation_scores

    if clean_market is IceHockeyMarket.RESULT_60_MINUTES:
        choice = _require_selection(
            selection,
            {Selection.HOME, Selection.AWAY, Selection.DRAW},
            clean_market,
        )
        outcome = _score_winner(home, away) or Selection.DRAW
        return _settled(choice is outcome, "ice_hockey_result_60_minutes")

    if clean_market is IceHockeyMarket.DRAW_60_MINUTES:
        if selection is not None and _enum(selection, Selection, "selection") is not Selection.DRAW:
            raise SettlementInputError("draw_60_minutes only accepts draw")
        return _settled(home == away, "ice_hockey_draw_60_minutes")

    choice = _require_selection(
        selection, {Selection.HOME, Selection.AWAY}, clean_market
    )
    team_goals, _ = _side_score(choice, home, away)
    line = (
        0.5
        if clean_market is IceHockeyMarket.TEAM_OVER_0_5_60_MINUTES
        else 1.5
    )
    return _settled(
        team_goals > line,
        f"ice_hockey_team_over_{line:.1f}_60_minutes",
    )


def settle_cricket(
    result: CricketResult,
    market: CricketMarket | str,
    selection: Selection | str | None,
) -> SettlementResult:
    """Settle cricket match winner including explicit DLS/Super-Over policy."""

    clean_market = _enum(market, CricketMarket, "cricket market")
    choice = _require_selection(
        selection, {Selection.HOME, Selection.AWAY}, clean_market
    )
    gate = _lifecycle(result.status)
    if gate is not None:
        return gate
    outcome = _optional_enum(result.outcome, CricketOutcome, "cricket outcome")
    method = _enum(
        result.decision_method,
        CricketDecisionMethod,
        "cricket decision method",
    )
    if outcome is None:
        return _unresolved("cricket_outcome_missing")
    if outcome in {CricketOutcome.TIE, CricketOutcome.NO_RESULT}:
        return SettlementResult(
            SettlementStatus.VOID,
            f"cricket_{outcome.value}_void",
        )
    winner = (
        Selection.HOME if outcome is CricketOutcome.HOME_WIN else Selection.AWAY
    )
    return _settled(choice is winner, f"cricket_match_winner_{method.value}")


def settle_esports(
    result: EsportsResult,
    market: EsportsMarket | str,
    selection: Selection | str | None,
) -> SettlementResult:
    """Settle e-sport series markets; cancellation and forfeit are V1 voids."""

    clean_market = _enum(market, EsportsMarket, "e-sport market")
    choice = _require_selection(
        selection, {Selection.HOME, Selection.AWAY}, clean_market
    )
    gate = _lifecycle(result.status)
    if gate is not None:
        return gate
    termination = _enum(
        result.termination,
        EsportsTermination,
        "e-sport termination",
    )
    if termination is EsportsTermination.FORFEIT:
        return SettlementResult(SettlementStatus.VOID, "esports_forfeit_void")
    scores = _score_pair(
        result.home_maps,
        result.away_maps,
        home_field="home_maps",
        away_field="away_maps",
    )
    if clean_market is EsportsMarket.SERIES_WINNER:
        winner = _validated_winner(result.winner, scores, field="e-sport winner")
        if winner is None:
            return _unresolved("esports_series_winner_missing")
        return _settled(choice is winner, "esports_series_winner")
    if scores is None:
        return _unresolved("esports_map_score_missing")
    selected_maps, _ = _side_score(choice, *scores)
    return _settled(selected_maps >= 1, "esports_at_least_one_map")


def settle_market(
    *,
    sport: Sport | str,
    market: str | Enum,
    selection: Selection | str | None,
    result: CanonicalResult,
) -> SettlementResult:
    """Dispatch one canonical result to its sport-specific pure rule set."""

    clean_sport = _enum(sport, Sport, "sport")
    contracts: dict[Sport, tuple[type[object], object]] = {
        Sport.FOOTBALL: (FootballResult, settle_football),
        Sport.TENNIS: (TennisResult, settle_tennis),
        Sport.BASKETBALL: (BasketballResult, settle_basketball),
        Sport.ICE_HOCKEY: (IceHockeyResult, settle_ice_hockey),
        Sport.CRICKET: (CricketResult, settle_cricket),
        Sport.ESPORTS: (EsportsResult, settle_esports),
    }
    expected_type, handler = contracts[clean_sport]
    if not isinstance(result, expected_type):
        raise SettlementInputError(
            f"{clean_sport.value} requires {expected_type.__name__}"
        )
    return handler(result, market, selection)  # type: ignore[operator]


__all__ = [
    "SETTLEMENT_RULE_VERSION",
    "BasketballMarket",
    "BasketballResult",
    "CanonicalResult",
    "CricketDecisionMethod",
    "CricketMarket",
    "CricketOutcome",
    "CricketResult",
    "EsportsMarket",
    "EsportsResult",
    "EsportsTermination",
    "EventStatus",
    "FootballMarket",
    "FootballResult",
    "IceHockeyMarket",
    "IceHockeyResult",
    "ParsedSettlementContract",
    "Selection",
    "SettlementInputError",
    "SettlementResult",
    "SettlementStatus",
    "Sport",
    "TennisMarket",
    "TennisResult",
    "TennisTermination",
    "parse_settlement_contract",
    "settle_basketball",
    "settle_cricket",
    "settle_esports",
    "settle_football",
    "settle_ice_hockey",
    "settle_market",
    "settle_tennis",
]
