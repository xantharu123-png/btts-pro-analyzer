"""Bookmaker-independent model and ticket logic for the 15K challenge.

The module deliberately separates event probabilities from market prices.
Bookmaker odds may constrain a final ticket and determine value, but they never
create, modify, or rank the underlying match candidates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from itertools import combinations
import math
import re
import unicodedata
from typing import Any, Iterable, Optional

from betting_math import BettingMathError, evaluate_market_price, validate_decimal_odds


TARGET_BALANCE = 15_000.0
TARGET_ODDS_MIN = 2.0
TARGET_ODDS_MAX = 3.0
MAX_TICKET_LEGS = 3
MAX_STAKE_FRACTION = 0.02
CROSS_LEG_MODEL_FACTOR = 0.97

MIN_LEAGUE_MATCHES = 24
MIN_VENUE_MATCHES = 5
MIN_FORM_MATCHES = 5
MIN_H2H_MATCHES = 3
MIN_VALIDATION_MATCHES = 30


@dataclass(frozen=True)
class MarketSpec:
    key: str
    market: str
    selection: str
    kind: str
    side: Optional[str] = None
    threshold: Optional[float] = None
    low: Optional[int] = None
    high: Optional[int] = None


@dataclass(frozen=True)
class ValidationMetrics:
    observations: int
    brier_score: Optional[float]
    baseline_brier_score: Optional[float]
    relative_improvement: Optional[float]
    expected_calibration_error: Optional[float]
    passed: bool


@dataclass
class ChallengeCandidate:
    candidate_id: str
    fixture_id: int
    league_id: int
    league_name: str
    kickoff: str
    home_team_id: int
    away_team_id: int
    home_team: str
    away_team: str
    market_key: str
    market: str
    selection: str
    probability: float
    conservative_probability: float
    probability_haircut_pp: float
    model_price: float
    evidence_score: float
    model_spread_pp: float
    expected_home_goals: float
    expected_away_goals: float
    venue_samples: tuple[int, int]
    form_samples: tuple[int, int]
    validation: Optional[ValidationMetrics]
    expected_market_home: Optional[float] = None
    expected_market_away: Optional[float] = None
    expected_unit: Optional[str] = None
    reasons: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def base_eligible(self) -> bool:
        return not self.blocked_reasons

    @property
    def eligible(self) -> bool:
        return self.base_eligible and self.context.get("passed") is True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["base_eligible"] = self.base_eligible
        payload["eligible"] = self.eligible
        return payload


@dataclass(frozen=True)
class QuotedLeg:
    candidate: ChallengeCandidate
    odds: float
    expected_roi: float


@dataclass(frozen=True)
class QuotedTicket:
    legs: tuple[QuotedLeg, ...]
    total_odds: float
    joint_probability: float
    expected_roi: float
    stake_fraction: float
    model_dependency_factor: float

    @property
    def potential_multiplier(self) -> float:
        return self.total_odds


def market_specs() -> tuple[MarketSpec, ...]:
    """Return the N1Bet-compatible market subset the model can settle exactly."""
    specs: list[MarketSpec] = [
        MarketSpec("RESULT_HOME", "Endergebnis", "Heimsieg", "result", side="home"),
        MarketSpec("RESULT_DRAW", "Endergebnis", "Unentschieden", "result", side="draw"),
        MarketSpec("RESULT_AWAY", "Endergebnis", "Auswärtssieg", "result", side="away"),
        MarketSpec("DC_1X", "Doppelte Chance", "1X", "double_chance", side="1X"),
        MarketSpec("DC_X2", "Doppelte Chance", "X2", "double_chance", side="X2"),
        MarketSpec("DC_12", "Doppelte Chance", "12", "double_chance", side="12"),
        MarketSpec("BTTS_YES", "Beide Teams treffen", "Ja", "btts", side="yes"),
        MarketSpec("BTTS_NO", "Beide Teams treffen", "Nein", "btts", side="no"),
    ]

    for threshold in (0.5, 1.5, 2.5, 3.5, 4.5):
        token = str(threshold).replace(".", "_")
        specs.extend(
            (
                MarketSpec(
                    f"TOTAL_OVER_{token}",
                    "Gesamttore",
                    f"Über {threshold}",
                    "total",
                    side="over",
                    threshold=threshold,
                ),
                MarketSpec(
                    f"TOTAL_UNDER_{token}",
                    "Gesamttore",
                    f"Unter {threshold}",
                    "total",
                    side="under",
                    threshold=threshold,
                ),
            )
        )

    for team_side, market_label in (
        ("home", "Team 1 Gesamttore"),
        ("away", "Team 2 Gesamttore"),
    ):
        prefix = "HOME" if team_side == "home" else "AWAY"
        for threshold in (0.5, 1.5, 2.5):
            token = str(threshold).replace(".", "_")
            specs.extend(
                (
                    MarketSpec(
                        f"{prefix}_OVER_{token}",
                        market_label,
                        f"Über {threshold}",
                        "team_total",
                        side=f"{team_side}_over",
                        threshold=threshold,
                    ),
                    MarketSpec(
                        f"{prefix}_UNDER_{token}",
                        market_label,
                        f"Unter {threshold}",
                        "team_total",
                        side=f"{team_side}_under",
                        threshold=threshold,
                    ),
                )
            )
        specs.extend(
            (
                MarketSpec(
                    f"{prefix}_RANGE_1_3",
                    market_label,
                    "1-3 Tore",
                    "team_range",
                    side=team_side,
                    low=1,
                    high=3,
                ),
                MarketSpec(
                    f"{prefix}_RANGE_2_4",
                    market_label,
                    "2-4 Tore",
                    "team_range",
                    side=team_side,
                    low=2,
                    high=4,
                ),
            )
        )

    specs.extend(
        (
            MarketSpec(
                "RESULT_TOTAL_1X_UNDER_3_5",
                "Resultat & Gesamttore 3,5",
                "1X und Unter 3,5",
                "result_total",
                side="1X_under",
                threshold=3.5,
            ),
            MarketSpec(
                "RESULT_TOTAL_X2_UNDER_3_5",
                "Resultat & Gesamttore 3,5",
                "X2 und Unter 3,5",
                "result_total",
                side="X2_under",
                threshold=3.5,
            ),
            MarketSpec(
                "RESULT_TOTAL_12_OVER_1_5",
                "Resultat & Gesamttore 1,5",
                "12 und Über 1,5",
                "result_total",
                side="12_over",
                threshold=1.5,
            ),
            MarketSpec(
                "MIXED_BTTS_OR_OVER_2_5",
                "Gemischte Chance",
                "BTTS Ja oder Über 2,5 Tore",
                "mixed_or",
                side="btts_yes_or_over",
                threshold=2.5,
            ),
            MarketSpec(
                "MIXED_HOME_OR_OVER_2_5",
                "Gemischte Chance",
                "Team 1 gewinnt oder Über 2,5 Tore",
                "mixed_or",
                side="home_or_over",
                threshold=2.5,
            ),
            MarketSpec(
                "MIXED_AWAY_OR_OVER_2_5",
                "Gemischte Chance",
                "Team 2 gewinnt oder Über 2,5 Tore",
                "mixed_or",
                side="away_or_over",
                threshold=2.5,
            ),
        )
    )

    for threshold in (5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5):
        token = str(threshold).replace(".", "_")
        specs.extend(
            (
                MarketSpec(
                    f"CORNERS_OVER_{token}",
                    "Eckbälle: Gesamtzahl",
                    f"Über {threshold}",
                    "corner_total",
                    side="over",
                    threshold=threshold,
                ),
                MarketSpec(
                    f"CORNERS_UNDER_{token}",
                    "Eckbälle: Gesamtzahl",
                    f"Unter {threshold}",
                    "corner_total",
                    side="under",
                    threshold=threshold,
                ),
            )
        )
    for team_side, market_label in (
        ("home", "Eckbälle: Gesamtzahl Team 1"),
        ("away", "Eckbälle: Gesamtzahl Team 2"),
    ):
        prefix = "HOME_CORNERS" if team_side == "home" else "AWAY_CORNERS"
        for threshold in (2.5, 3.5, 4.5, 5.5):
            token = str(threshold).replace(".", "_")
            specs.extend(
                (
                    MarketSpec(
                        f"{prefix}_OVER_{token}",
                        market_label,
                        f"Über {threshold}",
                        "team_corners",
                        side=f"{team_side}_over",
                        threshold=threshold,
                    ),
                    MarketSpec(
                        f"{prefix}_UNDER_{token}",
                        market_label,
                        f"Unter {threshold}",
                        "team_corners",
                        side=f"{team_side}_under",
                        threshold=threshold,
                    ),
                )
            )

    for threshold in (1.5, 2.5, 3.5, 4.5):
        token = str(threshold).replace(".", "_")
        specs.extend(
            (
                MarketSpec(
                    f"YELLOW_OVER_{token}",
                    "Gesamtzahl Gelbe Karten",
                    f"Über {threshold}",
                    "yellow_total",
                    side="over",
                    threshold=threshold,
                ),
                MarketSpec(
                    f"YELLOW_UNDER_{token}",
                    "Gesamtzahl Gelbe Karten",
                    f"Unter {threshold}",
                    "yellow_total",
                    side="under",
                    threshold=threshold,
                ),
            )
        )
    for team_side, market_label in (
        ("home", "Gelbe Karten: Gesamtzahl Team 1"),
        ("away", "Gelbe Karten: Gesamtzahl Team 2"),
    ):
        prefix = "HOME_YELLOW" if team_side == "home" else "AWAY_YELLOW"
        for threshold in (0.5, 1.5, 2.5):
            token = str(threshold).replace(".", "_")
            specs.extend(
                (
                    MarketSpec(
                        f"{prefix}_OVER_{token}",
                        market_label,
                        f"Über {threshold}",
                        "team_yellow",
                        side=f"{team_side}_over",
                        threshold=threshold,
                    ),
                    MarketSpec(
                        f"{prefix}_UNDER_{token}",
                        market_label,
                        f"Unter {threshold}",
                        "team_yellow",
                        side=f"{team_side}_under",
                        threshold=threshold,
                    ),
                )
            )
    return tuple(specs)


MARKET_SPECS = market_specs()
MARKET_BY_KEY = {spec.key: spec for spec in MARKET_SPECS}
COUNT_MARKET_KINDS = {"corner_total", "team_corners", "yellow_total", "team_yellow"}
GOAL_MARKET_SPECS = tuple(spec for spec in MARKET_SPECS if spec.kind not in COUNT_MARKET_KINDS)
CORNER_MARKET_SPECS = tuple(
    spec for spec in MARKET_SPECS if spec.kind in {"corner_total", "team_corners"}
)
YELLOW_MARKET_SPECS = tuple(
    spec for spec in MARKET_SPECS if spec.kind in {"yellow_total", "team_yellow"}
)


def _finite_nonnegative(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric < 0:
        return None
    return numeric


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _parse_kickoff(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fixture_datetime(fixture: dict[str, Any]) -> Optional[datetime]:
    return _parse_kickoff(fixture.get("fixture", {}).get("date"))


def _fixture_score(fixture: dict[str, Any]) -> Optional[tuple[int, int]]:
    home = fixture.get("goals", {}).get("home")
    away = fixture.get("goals", {}).get("away")
    if isinstance(home, bool) or isinstance(away, bool):
        return None
    if not isinstance(home, int) or not isinstance(away, int) or home < 0 or away < 0:
        return None
    return home, away


def _is_completed_before(fixture: dict[str, Any], before: datetime) -> bool:
    score = _fixture_score(fixture)
    played_at = _fixture_datetime(fixture)
    return score is not None and played_at is not None and played_at < before


def score_matrix(home_lambda: float, away_lambda: float, max_goals: int = 12) -> dict[tuple[int, int], float]:
    """Return a normalized independent-Poisson score matrix."""
    home_rate = _finite_nonnegative(home_lambda)
    away_rate = _finite_nonnegative(away_lambda)
    if home_rate is None or away_rate is None or home_rate > 8 or away_rate > 8:
        raise ValueError("Goal rates must be finite and between 0 and 8")
    if not isinstance(max_goals, int) or max_goals < 5:
        raise ValueError("max_goals must be an integer of at least 5")

    def poisson(k: int, rate: float) -> float:
        if rate == 0:
            return 1.0 if k == 0 else 0.0
        return math.exp(k * math.log(rate) - rate - math.lgamma(k + 1))

    matrix = {
        (home, away): poisson(home, home_rate) * poisson(away, away_rate)
        for home in range(max_goals + 1)
        for away in range(max_goals + 1)
    }
    mass = sum(matrix.values())
    if mass <= 0:
        raise ValueError("Score matrix has no probability mass")
    return {score: probability / mass for score, probability in matrix.items()}


def market_outcome(spec: MarketSpec, home_count: int, away_count: int) -> bool:
    """Settle a supported market on its two full-time count values."""
    home_goals = home_count
    away_goals = away_count
    total = home_count + away_count
    if spec.kind == "result":
        return {
            "home": home_goals > away_goals,
            "draw": home_goals == away_goals,
            "away": home_goals < away_goals,
        }[str(spec.side)]
    if spec.kind == "double_chance":
        return {
            "1X": home_goals >= away_goals,
            "X2": home_goals <= away_goals,
            "12": home_goals != away_goals,
        }[str(spec.side)]
    if spec.kind == "btts":
        scored = home_goals > 0 and away_goals > 0
        return scored if spec.side == "yes" else not scored
    if spec.kind == "total":
        return total > float(spec.threshold) if spec.side == "over" else total < float(spec.threshold)
    if spec.kind == "team_total":
        goals = home_goals if str(spec.side).startswith("home") else away_goals
        return goals > float(spec.threshold) if str(spec.side).endswith("over") else goals < float(spec.threshold)
    if spec.kind == "team_range":
        goals = home_goals if spec.side == "home" else away_goals
        return int(spec.low) <= goals <= int(spec.high)
    if spec.kind == "result_total":
        under = total < float(spec.threshold)
        over = total > float(spec.threshold)
        return {
            "1X_under": home_goals >= away_goals and under,
            "X2_under": home_goals <= away_goals and under,
            "12_over": home_goals != away_goals and over,
        }[str(spec.side)]
    if spec.kind == "mixed_or":
        over = total > float(spec.threshold)
        return {
            "btts_yes_or_over": (home_goals > 0 and away_goals > 0) or over,
            "home_or_over": home_goals > away_goals or over,
            "away_or_over": home_goals < away_goals or over,
        }[str(spec.side)]
    if spec.kind in {"corner_total", "yellow_total"}:
        return total > float(spec.threshold) if spec.side == "over" else total < float(spec.threshold)
    if spec.kind in {"team_corners", "team_yellow"}:
        count = home_count if str(spec.side).startswith("home") else away_count
        return count > float(spec.threshold) if str(spec.side).endswith("over") else count < float(spec.threshold)
    raise ValueError(f"Unsupported market kind: {spec.kind}")


def market_probability(matrix: dict[tuple[int, int], float], spec: MarketSpec) -> float:
    return sum(
        probability
        for (home_goals, away_goals), probability in matrix.items()
        if market_outcome(spec, home_goals, away_goals)
    )


def _fixture_market_outcome(spec: MarketSpec, fixture: dict[str, Any]) -> Optional[bool]:
    if spec.kind not in COUNT_MARKET_KINDS:
        score = _fixture_score(fixture)
        return market_outcome(spec, *score) if score is not None else None
    stats = fixture.get("challenge_stats") or {}
    if spec.kind in {"corner_total", "team_corners"}:
        home_value = stats.get("corners_home")
        away_value = stats.get("corners_away")
    else:
        home_value = stats.get("yellow_cards_home")
        away_value = stats.get("yellow_cards_away")
    if (
        isinstance(home_value, bool)
        or isinstance(away_value, bool)
        or not isinstance(home_value, int)
        or not isinstance(away_value, int)
        or home_value < 0
        or away_value < 0
    ):
        return None
    return market_outcome(spec, home_value, away_value)


def _team_observations(
    fixtures: Iterable[dict[str, Any]],
    team_id: int,
    before: datetime,
    *,
    venue: Optional[str],
    limit: int,
) -> list[tuple[float, float, datetime]]:
    rows: list[tuple[float, float, datetime]] = []
    ordered = sorted(
        fixtures,
        key=lambda item: _fixture_datetime(item) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    for fixture in ordered:
        if not _is_completed_before(fixture, before):
            continue
        teams = fixture.get("teams", {})
        home_id = teams.get("home", {}).get("id")
        away_id = teams.get("away", {}).get("id")
        if team_id not in {home_id, away_id}:
            continue
        actual_venue = "home" if home_id == team_id else "away"
        if venue is not None and actual_venue != venue:
            continue
        home_goals, away_goals = _fixture_score(fixture) or (None, None)
        if home_goals is None:
            continue
        scored, conceded = (
            (home_goals, away_goals) if actual_venue == "home" else (away_goals, home_goals)
        )
        rows.append((float(scored), float(conceded), _fixture_datetime(fixture)))
        if len(rows) >= limit:
            break
    return rows


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        raise ValueError("At least one observation is required")
    return sum(values) / len(values)


def _shrunk_mean(values: Iterable[float], prior_mean: float, prior_weight: float = 4.0) -> float:
    sample = list(values)
    if not sample:
        return prior_mean
    return (sum(sample) + prior_weight * prior_mean) / (len(sample) + prior_weight)


def _league_goal_means(fixtures: Iterable[dict[str, Any]], before: datetime) -> Optional[tuple[float, float, int]]:
    scores = [
        _fixture_score(fixture)
        for fixture in fixtures
        if _is_completed_before(fixture, before)
    ]
    scores = [score for score in scores if score is not None]
    if len(scores) < MIN_LEAGUE_MATCHES:
        return None
    return (
        _mean(score[0] for score in scores),
        _mean(score[1] for score in scores),
        len(scores),
    )


def _fixture_model(
    fixture: dict[str, Any],
    league_history: Iterable[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    kickoff = _fixture_datetime(fixture)
    teams = fixture.get("teams", {})
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")
    if kickoff is None or not isinstance(home_id, int) or not isinstance(away_id, int):
        return None

    history = list(league_history)
    league_means = _league_goal_means(history, kickoff)
    if league_means is None:
        return None
    league_home, league_away, league_sample = league_means

    home_venue = _team_observations(history, home_id, kickoff, venue="home", limit=12)
    away_venue = _team_observations(history, away_id, kickoff, venue="away", limit=12)
    home_form = _team_observations(history, home_id, kickoff, venue=None, limit=6)
    away_form = _team_observations(history, away_id, kickoff, venue=None, limit=6)
    if min(len(home_venue), len(away_venue)) < MIN_VENUE_MATCHES:
        return None
    if min(len(home_form), len(away_form)) < MIN_FORM_MATCHES:
        return None

    home_scored = _shrunk_mean((row[0] for row in home_venue), league_home)
    home_conceded = _shrunk_mean((row[1] for row in home_venue), league_away)
    away_scored = _shrunk_mean((row[0] for row in away_venue), league_away)
    away_conceded = _shrunk_mean((row[1] for row in away_venue), league_home)
    season_home = (home_scored + away_conceded) / 2.0
    season_away = (away_scored + home_conceded) / 2.0

    league_team_mean = (league_home + league_away) / 2.0
    form_home = (
        _shrunk_mean((row[0] for row in home_form), league_team_mean, 3.0)
        + _shrunk_mean((row[1] for row in away_form), league_team_mean, 3.0)
    ) / 2.0
    form_away = (
        _shrunk_mean((row[0] for row in away_form), league_team_mean, 3.0)
        + _shrunk_mean((row[1] for row in home_form), league_team_mean, 3.0)
    ) / 2.0

    active_home = 0.75 * season_home + 0.25 * form_home
    active_away = 0.75 * season_away + 0.25 * form_away
    latest_observation = max(home_form[0][2], away_form[0][2])
    freshness_days = max(0.0, (kickoff - latest_observation).total_seconds() / 86_400.0)
    return {
        "active_lambdas": (active_home, active_away),
        "season_lambdas": (season_home, season_away),
        "form_lambdas": (form_home, form_away),
        "venue_samples": (len(home_venue), len(away_venue)),
        "form_samples": (len(home_form), len(away_form)),
        "league_sample": league_sample,
        "freshness_days": freshness_days,
    }


def _fixture_count_pair(
    fixture: dict[str, Any],
    family: str,
) -> Optional[tuple[int, int]]:
    stats = fixture.get("challenge_stats") or {}
    if family == "corners":
        home_value = stats.get("corners_home")
        away_value = stats.get("corners_away")
    elif family == "yellow":
        home_value = stats.get("yellow_cards_home")
        away_value = stats.get("yellow_cards_away")
    else:
        raise ValueError("Unknown count family")
    if (
        isinstance(home_value, bool)
        or isinstance(away_value, bool)
        or not isinstance(home_value, int)
        or not isinstance(away_value, int)
        or home_value < 0
        or away_value < 0
    ):
        return None
    return home_value, away_value


def _normalized_referee(value: Any) -> str:
    text = str(value or "").split(",", 1)[0]
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    return re.sub(r"\s+", " ", text)


def _team_count_observations(
    fixtures: Iterable[dict[str, Any]],
    team_id: int,
    before: datetime,
    *,
    family: str,
    venue: Optional[str],
    limit: int,
) -> list[tuple[float, float, datetime]]:
    rows: list[tuple[float, float, datetime]] = []
    ordered = sorted(
        fixtures,
        key=lambda item: _fixture_datetime(item) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    for fixture in ordered:
        if not _is_completed_before(fixture, before):
            continue
        counts = _fixture_count_pair(fixture, family)
        if counts is None:
            continue
        teams = fixture.get("teams", {})
        home_id = teams.get("home", {}).get("id")
        away_id = teams.get("away", {}).get("id")
        if team_id not in {home_id, away_id}:
            continue
        actual_venue = "home" if home_id == team_id else "away"
        if venue is not None and actual_venue != venue:
            continue
        own, opponent = counts if actual_venue == "home" else (counts[1], counts[0])
        rows.append((float(own), float(opponent), _fixture_datetime(fixture)))
        if len(rows) >= limit:
            break
    return rows


def _league_count_means(
    fixtures: Iterable[dict[str, Any]],
    before: datetime,
    family: str,
) -> Optional[tuple[float, float, int]]:
    pairs = [
        _fixture_count_pair(fixture, family)
        for fixture in fixtures
        if _is_completed_before(fixture, before)
    ]
    pairs = [pair for pair in pairs if pair is not None]
    if len(pairs) < MIN_LEAGUE_MATCHES:
        return None
    return _mean(pair[0] for pair in pairs), _mean(pair[1] for pair in pairs), len(pairs)


def _dispersion_alpha(values: Iterable[float]) -> float:
    sample = list(values)
    if len(sample) < 2:
        return 0.10
    mean = _mean(sample)
    if mean <= 0:
        return 0.10
    variance = sum((value - mean) ** 2 for value in sample) / (len(sample) - 1)
    alpha = (variance - mean) / (mean * mean)
    return max(0.03, min(1.5, alpha))


def _negative_binomial_pmf(k: int, mean: float, alpha: float) -> float:
    if k < 0 or mean < 0 or alpha <= 0:
        return 0.0
    if mean == 0:
        return 1.0 if k == 0 else 0.0
    size = 1.0 / alpha
    success = size / (size + mean)
    return math.exp(
        math.lgamma(k + size)
        - math.lgamma(k + 1)
        - math.lgamma(size)
        + size * math.log(success)
        + k * math.log1p(-success)
    )


def _count_matrix(
    home_mean: float,
    away_mean: float,
    home_alpha: float,
    away_alpha: float,
    max_count: int,
) -> dict[tuple[int, int], float]:
    matrix = {
        (home, away): (
            _negative_binomial_pmf(home, home_mean, home_alpha)
            * _negative_binomial_pmf(away, away_mean, away_alpha)
        )
        for home in range(max_count + 1)
        for away in range(max_count + 1)
    }
    mass = sum(matrix.values())
    if mass <= 0:
        raise ValueError("Count matrix has no probability mass")
    return {counts: probability / mass for counts, probability in matrix.items()}


def _fixture_count_model(
    fixture: dict[str, Any],
    league_history: Iterable[dict[str, Any]],
    family: str,
) -> Optional[dict[str, Any]]:
    kickoff = _fixture_datetime(fixture)
    teams = fixture.get("teams", {})
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")
    if kickoff is None or not isinstance(home_id, int) or not isinstance(away_id, int):
        return None
    history = list(league_history)
    league_means = _league_count_means(history, kickoff, family)
    if league_means is None:
        return None
    league_home, league_away, league_sample = league_means
    home_venue = _team_count_observations(
        history, home_id, kickoff, family=family, venue="home", limit=12
    )
    away_venue = _team_count_observations(
        history, away_id, kickoff, family=family, venue="away", limit=12
    )
    home_form = _team_count_observations(
        history, home_id, kickoff, family=family, venue=None, limit=6
    )
    away_form = _team_count_observations(
        history, away_id, kickoff, family=family, venue=None, limit=6
    )
    if min(len(home_venue), len(away_venue)) < MIN_VENUE_MATCHES:
        return None
    if min(len(home_form), len(away_form)) < MIN_FORM_MATCHES:
        return None

    season_home = (
        _shrunk_mean((row[0] for row in home_venue), league_home)
        + _shrunk_mean((row[1] for row in away_venue), league_home)
    ) / 2.0
    season_away = (
        _shrunk_mean((row[0] for row in away_venue), league_away)
        + _shrunk_mean((row[1] for row in home_venue), league_away)
    ) / 2.0
    league_team_mean = (league_home + league_away) / 2.0
    form_home = (
        _shrunk_mean((row[0] for row in home_form), league_team_mean, 3.0)
        + _shrunk_mean((row[1] for row in away_form), league_team_mean, 3.0)
    ) / 2.0
    form_away = (
        _shrunk_mean((row[0] for row in away_form), league_team_mean, 3.0)
        + _shrunk_mean((row[1] for row in home_form), league_team_mean, 3.0)
    ) / 2.0
    active_home = 0.75 * season_home + 0.25 * form_home
    active_away = 0.75 * season_away + 0.25 * form_away

    referee_sample = 0
    referee_mean = None
    if family == "yellow":
        referee = _normalized_referee(fixture.get("fixture", {}).get("referee"))
        if not referee:
            return None
        referee_totals = []
        for historical_fixture in history:
            if not _is_completed_before(historical_fixture, kickoff):
                continue
            if _normalized_referee(historical_fixture.get("fixture", {}).get("referee")) != referee:
                continue
            counts = _fixture_count_pair(historical_fixture, "yellow")
            if counts is not None:
                referee_totals.append(float(sum(counts)))
        if len(referee_totals) < 5:
            return None
        referee_sample = len(referee_totals)
        referee_mean = _shrunk_mean(referee_totals, league_home + league_away, 5.0)

        def apply_referee(home_value: float, away_value: float) -> tuple[float, float]:
            team_total = home_value + away_value
            if team_total <= 0:
                return referee_mean / 2.0, referee_mean / 2.0
            adjusted_total = 0.75 * team_total + 0.25 * referee_mean
            home_share = home_value / team_total
            return adjusted_total * home_share, adjusted_total * (1.0 - home_share)

        season_home, season_away = apply_referee(season_home, season_away)
        form_home, form_away = apply_referee(form_home, form_away)
        active_home, active_away = apply_referee(active_home, active_away)

    home_alpha = _dispersion_alpha(
        [row[0] for row in home_venue] + [row[1] for row in away_venue]
    )
    away_alpha = _dispersion_alpha(
        [row[0] for row in away_venue] + [row[1] for row in home_venue]
    )
    max_count = 25 if family == "corners" else 12
    return {
        "active_counts": (active_home, active_away),
        "season_counts": (season_home, season_away),
        "form_counts": (form_home, form_away),
        "active_matrix": _count_matrix(active_home, active_away, home_alpha, away_alpha, max_count),
        "season_matrix": _count_matrix(season_home, season_away, home_alpha, away_alpha, max_count),
        "form_matrix": _count_matrix(form_home, form_away, home_alpha, away_alpha, max_count),
        "venue_samples": (len(home_venue), len(away_venue)),
        "form_samples": (len(home_form), len(away_form)),
        "league_sample": league_sample,
        "dispersion": (home_alpha, away_alpha),
        "referee_sample": referee_sample,
        "referee_mean": referee_mean,
    }


def fixture_market_probabilities(
    fixture: dict[str, Any],
    league_history: Iterable[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    history = list(league_history)
    model = _fixture_model(fixture, history)
    if model is None:
        return None
    active_matrix = score_matrix(*model["active_lambdas"])
    season_matrix = score_matrix(*model["season_lambdas"])
    form_matrix = score_matrix(*model["form_lambdas"])
    model["probabilities"] = {
        spec.key: (
            market_probability(active_matrix, spec),
            market_probability(season_matrix, spec),
            market_probability(form_matrix, spec),
        )
        for spec in GOAL_MARKET_SPECS
    }
    model["count_models"] = {}
    for family, specs in (
        ("corners", CORNER_MARKET_SPECS),
        ("yellow", YELLOW_MARKET_SPECS),
    ):
        count_model = _fixture_count_model(fixture, history, family)
        if count_model is None:
            continue
        model["count_models"][family] = count_model
        for spec in specs:
            model["probabilities"][spec.key] = (
                market_probability(count_model["active_matrix"], spec),
                market_probability(count_model["season_matrix"], spec),
                market_probability(count_model["form_matrix"], spec),
            )
    return model


def _expected_calibration_error(predictions: list[float], outcomes: list[int]) -> float:
    if not predictions:
        return 1.0
    total = len(predictions)
    error = 0.0
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        upper = lower + 0.2
        indices = [
            index
            for index, probability in enumerate(predictions)
            if lower <= probability < upper or (upper == 1.0 and probability == 1.0)
        ]
        if not indices:
            continue
        mean_probability = _mean(predictions[index] for index in indices)
        observed_rate = _mean(outcomes[index] for index in indices)
        error += len(indices) / total * abs(mean_probability - observed_rate)
    return error


def validate_league_markets(
    fixtures: Iterable[dict[str, Any]],
) -> dict[str, ValidationMetrics]:
    """Run an expanding-window, leakage-free market validation."""
    ordered = sorted(
        (fixture for fixture in fixtures if _fixture_datetime(fixture) and _fixture_score(fixture)),
        key=lambda item: _fixture_datetime(item),
    )
    records: dict[str, dict[str, list[float]]] = {
        spec.key: {"probabilities": [], "outcomes": [], "baselines": []}
        for spec in MARKET_SPECS
    }
    prior: list[dict[str, Any]] = []
    event_successes = {spec.key: 0 for spec in MARKET_SPECS}
    event_totals = {spec.key: 0 for spec in MARKET_SPECS}

    for fixture in ordered:
        prediction = fixture_market_probabilities(fixture, prior)
        score = _fixture_score(fixture)
        if score is None:
            continue
        if prediction is not None:
            for spec in MARKET_SPECS:
                probability_values = prediction["probabilities"].get(spec.key)
                outcome_value = _fixture_market_outcome(spec, fixture)
                if probability_values is None or outcome_value is None:
                    continue
                probability = probability_values[0]
                outcome = int(outcome_value)
                baseline = (event_successes[spec.key] + 1.0) / (event_totals[spec.key] + 2.0)
                records[spec.key]["probabilities"].append(probability)
                records[spec.key]["outcomes"].append(outcome)
                records[spec.key]["baselines"].append(baseline)

        for spec in MARKET_SPECS:
            outcome_value = _fixture_market_outcome(spec, fixture)
            if outcome_value is None:
                continue
            outcome = int(outcome_value)
            event_successes[spec.key] += outcome
            event_totals[spec.key] += 1
        prior.append(fixture)

    metrics: dict[str, ValidationMetrics] = {}
    for spec in MARKET_SPECS:
        record = records[spec.key]
        probabilities = record["probabilities"]
        outcomes = [int(value) for value in record["outcomes"]]
        baselines = record["baselines"]
        observations = len(probabilities)
        if observations == 0:
            metrics[spec.key] = ValidationMetrics(0, None, None, None, None, False)
            continue
        brier = _mean((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes))
        baseline_brier = _mean((probability - outcome) ** 2 for probability, outcome in zip(baselines, outcomes))
        improvement = (baseline_brier - brier) / baseline_brier if baseline_brier > 0 else None
        ece = _expected_calibration_error(probabilities, outcomes)
        passed = (
            observations >= MIN_VALIDATION_MATCHES
            and improvement is not None
            and improvement >= 0.02
            and ece <= 0.12
        )
        metrics[spec.key] = ValidationMetrics(
            observations=observations,
            brier_score=round(brier, 6),
            baseline_brier_score=round(baseline_brier, 6),
            relative_improvement=round(improvement, 6) if improvement is not None else None,
            expected_calibration_error=round(ece, 6),
            passed=passed,
        )
    return metrics


def _fixture_identity(fixture: dict[str, Any]) -> Optional[dict[str, Any]]:
    fixture_data = fixture.get("fixture", {})
    teams = fixture.get("teams", {})
    league = fixture.get("league", {})
    fixture_id = fixture_data.get("id")
    league_id = league.get("id")
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")
    if not all(isinstance(value, int) for value in (fixture_id, league_id, home_id, away_id)):
        return None
    kickoff = _fixture_datetime(fixture)
    if kickoff is None:
        return None
    return {
        "fixture_id": fixture_id,
        "league_id": league_id,
        "league_name": str(league.get("name") or f"Liga {league_id}"),
        "kickoff": kickoff.isoformat(),
        "home_team_id": home_id,
        "away_team_id": away_id,
        "home_team": str(teams.get("home", {}).get("name") or "Heimteam"),
        "away_team": str(teams.get("away", {}).get("name") or "Auswärtsteam"),
    }


def build_fixture_candidates(
    fixture: dict[str, Any],
    league_history: Iterable[dict[str, Any]],
    validation: dict[str, ValidationMetrics],
) -> list[ChallengeCandidate]:
    """Build price-independent candidates for one fixture."""
    identity = _fixture_identity(fixture)
    model = fixture_market_probabilities(fixture, league_history)
    if identity is None or model is None:
        return []

    freshness_days = float(model["freshness_days"])
    active_home, active_away = model["active_lambdas"]
    candidates: list[ChallengeCandidate] = []
    for spec in MARKET_SPECS:
        probability_values = model["probabilities"].get(spec.key)
        if probability_values is None:
            continue
        active, season, form = probability_values
        referee_sample = 0
        if spec.kind in {"corner_total", "team_corners"}:
            count_model = model["count_models"]["corners"]
            venue_samples = count_model["venue_samples"]
            form_samples = count_model["form_samples"]
            expected_market_home, expected_market_away = count_model["active_counts"]
            expected_unit = "Ecken"
        elif spec.kind in {"yellow_total", "team_yellow"}:
            count_model = model["count_models"]["yellow"]
            venue_samples = count_model["venue_samples"]
            form_samples = count_model["form_samples"]
            expected_market_home, expected_market_away = count_model["active_counts"]
            expected_unit = "Gelbe Karten"
            referee_sample = int(count_model.get("referee_sample", 0))
        else:
            venue_samples = model["venue_samples"]
            form_samples = model["form_samples"]
            expected_market_home = None
            expected_market_away = None
            expected_unit = None
        spread_pp = (max(active, season, form) - min(active, season, form)) * 100.0
        sample_penalty = max(0.0, 8 - min(venue_samples)) * 0.5
        freshness_penalty = max(0.0, freshness_days - 14.0) * 0.12
        haircut_pp = min(15.0, 3.0 + spread_pp * 0.5 + sample_penalty + freshness_penalty)
        conservative = max(0.0, min(active, season, form) - haircut_pp / 100.0)
        metric = validation.get(spec.key)

        sample_score = 35.0 * min(1.0, min(venue_samples) / 10.0)
        form_score = 15.0 * min(1.0, min(form_samples) / 6.0)
        agreement_score = 20.0 * max(0.0, 1.0 - spread_pp / 20.0)
        freshness_score = 10.0 * max(0.0, 1.0 - max(0.0, freshness_days - 7.0) / 28.0)
        validation_score = 20.0 if metric and metric.passed else 0.0
        evidence = min(100.0, sample_score + form_score + agreement_score + freshness_score + validation_score)

        blocked: list[str] = []
        if not 0.58 <= active <= 0.92:
            blocked.append("Modellwahrscheinlichkeit außerhalb des Challenge-Korridors")
        if conservative < 0.55:
            blocked.append("Konservative Wahrscheinlichkeit unter 55 %")
        if spread_pp > 12.0:
            blocked.append("Saison- und Formmodell widersprechen sich")
        if metric is None or not metric.passed:
            blocked.append("Markt hat das Walk-forward-Gate nicht bestanden")
        if evidence < 72.0:
            blocked.append("Evidenzscore unter 72")
        if freshness_days > 35.0:
            blocked.append("Letzte Formbeobachtung ist zu alt")

        model_price = 1.0 / conservative if conservative > 0 else math.inf
        candidate_id = f"{identity['fixture_id']}:{spec.key}"
        reasons = [
            f"Konservativ {conservative * 100:.1f} % nach {haircut_pp:.1f} PP Abschlag",
            f"Venue-Stichprobe {venue_samples[0]}/{venue_samples[1]}",
            f"Saison/Form-Spanne {spread_pp:.1f} PP",
        ]
        if expected_unit and expected_market_home is not None and expected_market_away is not None:
            reasons.append(
                f"Erwartete {expected_unit} {expected_market_home:.1f}/{expected_market_away:.1f}"
            )
        if referee_sample:
            reasons.append(f"Schiedsrichter-Stichprobe {referee_sample}")
        candidates.append(
            ChallengeCandidate(
                candidate_id=candidate_id,
                **identity,
                market_key=spec.key,
                market=spec.market,
                selection=spec.selection,
                probability=round(active, 6),
                conservative_probability=round(conservative, 6),
                probability_haircut_pp=round(haircut_pp, 2),
                model_price=round(model_price, 4) if math.isfinite(model_price) else math.inf,
                evidence_score=round(evidence, 1),
                model_spread_pp=round(spread_pp, 2),
                expected_home_goals=round(active_home, 3),
                expected_away_goals=round(active_away, 3),
                venue_samples=venue_samples,
                form_samples=form_samples,
                validation=metric,
                expected_market_home=(
                    round(expected_market_home, 3)
                    if expected_market_home is not None else None
                ),
                expected_market_away=(
                    round(expected_market_away, 3)
                    if expected_market_away is not None else None
                ),
                expected_unit=expected_unit,
                reasons=reasons,
                blocked_reasons=blocked,
            )
        )
    return candidates


def _h2h_scores(
    fixtures: Iterable[dict[str, Any]],
    current_home_team_id: int,
    current_away_team_id: int,
) -> list[tuple[int, int]]:
    scores: list[tuple[int, int]] = []
    for fixture in fixtures:
        score = _fixture_score(fixture)
        if score is None:
            continue
        teams = fixture.get("teams", {})
        historical_home = teams.get("home", {}).get("id")
        historical_away = teams.get("away", {}).get("id")
        if {historical_home, historical_away} != {current_home_team_id, current_away_team_id}:
            continue
        if historical_home == current_home_team_id:
            scores.append(score)
        else:
            scores.append((score[1], score[0]))
    return scores[:10]


def _injury_summary(
    injuries: Optional[list[dict[str, Any]]],
    home_team_id: int,
    away_team_id: int,
    coverage_available: bool,
) -> tuple[bool, dict[str, Any], Optional[str]]:
    if not coverage_available:
        return False, {"status": "unavailable"}, "Verletzungsdaten werden für diese Liga nicht abgedeckt"
    if injuries is None:
        return False, {"status": "unavailable"}, "Verletzungsdaten konnten nicht verifiziert werden"

    summary: dict[int, dict[str, Any]] = {
        home_team_id: {"missing": set(), "questionable": set(), "names": []},
        away_team_id: {"missing": set(), "questionable": set(), "names": []},
    }
    for entry in injuries:
        team_id = entry.get("team", {}).get("id")
        if team_id not in summary:
            continue
        player = entry.get("player", {})
        player_id = player.get("id") or player.get("name")
        if player_id is None:
            continue
        injury_type = str(player.get("type") or "").casefold()
        bucket = "questionable" if "question" in injury_type else "missing"
        summary[team_id][bucket].add(player_id)
        name = str(player.get("name") or player_id)
        if name not in summary[team_id]["names"]:
            summary[team_id]["names"].append(name)

    home_weight = len(summary[home_team_id]["missing"]) + 0.5 * len(summary[home_team_id]["questionable"])
    away_weight = len(summary[away_team_id]["missing"]) + 0.5 * len(summary[away_team_id]["questionable"])
    passed = max(home_weight, away_weight) <= 5 and abs(home_weight - away_weight) <= 3
    public_summary = {
        "status": "passed" if passed else "blocked",
        "home_missing": len(summary[home_team_id]["missing"]),
        "home_questionable": len(summary[home_team_id]["questionable"]),
        "away_missing": len(summary[away_team_id]["missing"]),
        "away_questionable": len(summary[away_team_id]["questionable"]),
        "home_names": summary[home_team_id]["names"][:8],
        "away_names": summary[away_team_id]["names"][:8],
    }
    reason = None if passed else "Ausfalllage ist zu groß oder zu einseitig"
    return passed, public_summary, reason


def _weather_summary(weather: Optional[dict[str, Any]]) -> tuple[bool, dict[str, Any], Optional[str]]:
    if not weather or weather.get("status") != "ok":
        return False, {"status": "unavailable"}, "Wetter zum Anpfiff konnte nicht verifiziert werden"
    temperature = _finite_number(weather.get("temperature_c"))
    wind = _finite_nonnegative(weather.get("wind_mps"))
    rain = _finite_nonnegative(weather.get("rain_3h_mm")) or 0.0
    snow = _finite_nonnegative(weather.get("snow_3h_mm")) or 0.0
    if temperature is None or wind is None:
        return False, {"status": "unavailable"}, "Wetterdaten sind unvollständig"
    adverse = temperature < 0.0 or temperature > 35.0 or wind >= 12.0 or rain >= 6.0 or snow >= 2.0
    summary = {
        "status": "blocked" if adverse else "passed",
        "temperature_c": round(temperature, 1),
        "wind_mps": round(wind, 1),
        "rain_3h_mm": round(rain, 1),
        "snow_3h_mm": round(snow, 1),
        "description": weather.get("description") or "n/a",
    }
    return (not adverse), summary, ("Wetter erhöht die Modellunsicherheit" if adverse else None)


def _lineup_summary(
    lineups: Optional[list[dict[str, Any]]],
    kickoff: datetime,
    now: datetime,
) -> tuple[bool, dict[str, Any], Optional[str]]:
    minutes_to_kickoff = (kickoff - now).total_seconds() / 60.0
    required = -5 <= minutes_to_kickoff <= 60
    complete = bool(
        lineups
        and len(lineups) >= 2
        and all(len(item.get("startXI") or []) >= 11 for item in lineups[:2])
    )
    if required and not complete:
        return False, {"status": "required_missing", "required": True}, "Aufstellungen fehlen kurz vor Anpfiff"
    return True, {
        "status": "passed" if complete else "not_due",
        "required": required,
        "teams": len(lineups or []),
    }, None


def apply_candidate_context(
    candidate: ChallengeCandidate,
    *,
    h2h_fixtures: Optional[list[dict[str, Any]]],
    injuries: Optional[list[dict[str, Any]]],
    injury_coverage: bool,
    weather: Optional[dict[str, Any]],
    lineups: Optional[list[dict[str, Any]]],
    now: Optional[datetime] = None,
) -> ChallengeCandidate:
    """Attach non-price context as veto gates without altering probability."""
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)
    kickoff = _parse_kickoff(candidate.kickoff)
    if kickoff is None:
        candidate.context = {"passed": False, "blocked_reasons": ["Anstoßzeit ist ungültig"]}
        return candidate

    blocked: list[str] = []
    spec = MARKET_BY_KEY[candidate.market_key]
    scores = _h2h_scores(
        h2h_fixtures or [],
        candidate.home_team_id,
        candidate.away_team_id,
    )
    descriptive_h2h = spec.kind in COUNT_MARKET_KINDS
    count_outcomes = [
        _fixture_market_outcome(spec, fixture)
        for fixture in (h2h_fixtures or [])
        if _fixture_market_outcome(spec, fixture) is not None
    ]
    if descriptive_h2h and len(count_outcomes) < MIN_H2H_MATCHES:
        hits = None
        h2h_rate = None
        h2h_passed = len(scores) >= MIN_H2H_MATCHES
    else:
        outcomes = (
            [bool(value) for value in count_outcomes]
            if descriptive_h2h
            else [market_outcome(spec, *score) for score in scores]
        )
        hits = sum(int(value) for value in outcomes)
        h2h_rate = (hits + 1.0) / (len(outcomes) + 2.0) if outcomes else None
        h2h_passed = (
            len(outcomes) >= MIN_H2H_MATCHES
            and h2h_rate is not None
            and h2h_rate + 0.20 >= candidate.conservative_probability
        )
    if not h2h_passed:
        blocked.append(
            "H2H-Stichprobe fehlt" if len(scores) < MIN_H2H_MATCHES else "H2H widerspricht der Auswahl deutlich"
        )

    injuries_passed, injuries_summary, injuries_reason = _injury_summary(
        injuries,
        candidate.home_team_id,
        candidate.away_team_id,
        injury_coverage,
    )
    if injuries_reason:
        blocked.append(injuries_reason)
    weather_passed, weather_summary, weather_reason = _weather_summary(weather)
    if weather_reason:
        blocked.append(weather_reason)
    lineup_passed, lineup_summary, lineup_reason = _lineup_summary(lineups, kickoff, now_utc)
    if lineup_reason:
        blocked.append(lineup_reason)

    candidate.context = {
        "passed": h2h_passed and injuries_passed and weather_passed and lineup_passed,
        "h2h": {
            "status": "passed" if h2h_passed else "blocked",
            "matches": len(scores),
            "hits": hits,
            "smoothed_hit_rate": round(h2h_rate, 4) if h2h_rate is not None else None,
            "descriptive_only": descriptive_h2h and h2h_rate is None,
        },
        "injuries": injuries_summary,
        "weather": weather_summary,
        "lineups": lineup_summary,
        "blocked_reasons": blocked,
    }
    return candidate


def select_shortlist(
    candidates: Iterable[ChallengeCandidate],
    max_candidates: int = 6,
) -> list[ChallengeCandidate]:
    """Select a small price-independent board for the later quote check."""
    eligible = [candidate for candidate in candidates if candidate.eligible]
    eligible.sort(
        key=lambda candidate: (
            candidate.conservative_probability,
            candidate.evidence_score,
            candidate.validation.relative_improvement if candidate.validation and candidate.validation.relative_improvement is not None else -1.0,
        ),
        reverse=True,
    )
    selected: list[ChallengeCandidate] = []
    per_fixture: dict[int, int] = {}
    for candidate in eligible:
        if per_fixture.get(candidate.fixture_id, 0) >= 2:
            continue
        selected.append(candidate)
        per_fixture[candidate.fixture_id] = per_fixture.get(candidate.fixture_id, 0) + 1
        if len(selected) >= max_candidates:
            break
    return selected


def select_model_ticket(
    candidates: Iterable[ChallengeCandidate],
    odds_min: float = TARGET_ODDS_MIN,
    odds_max: float = TARGET_ODDS_MAX,
) -> tuple[ChallengeCandidate, ...]:
    """Choose a quote-free preview using conservative model prices only."""
    board = [candidate for candidate in candidates if candidate.eligible]
    options: list[tuple[float, float, int, tuple[ChallengeCandidate, ...]]] = []
    for size in range(1, MAX_TICKET_LEGS + 1):
        for legs in combinations(board, size):
            if len({leg.fixture_id for leg in legs}) != size:
                continue
            dependency_factor = CROSS_LEG_MODEL_FACTOR ** max(0, size - 1)
            model_total = math.prod(leg.model_price for leg in legs) / dependency_factor
            if not odds_min <= model_total <= odds_max:
                continue
            joint = (
                math.prod(leg.conservative_probability for leg in legs)
                * dependency_factor
            )
            average_evidence = _mean(leg.evidence_score for leg in legs)
            options.append((joint, average_evidence, -size, legs))
    if not options:
        return ()
    return max(options, key=lambda item: item[:3])[3]


def select_quoted_ticket(
    candidates: Iterable[ChallengeCandidate],
    odds_by_candidate: dict[str, float],
    *,
    odds_min: float = TARGET_ODDS_MIN,
    odds_max: float = TARGET_ODDS_MAX,
    minimum_ticket_roi: float = 0.03,
) -> Optional[QuotedTicket]:
    """Return the strongest valid 1-3 leg ticket after manual price entry."""
    priced: list[tuple[ChallengeCandidate, float, float]] = []
    for candidate in candidates:
        if not candidate.eligible:
            continue
        raw_odds = odds_by_candidate.get(candidate.candidate_id)
        if raw_odds in (None, 0, 0.0):
            continue
        try:
            odds = validate_decimal_odds(raw_odds)
            metrics = evaluate_market_price(
                candidate.conservative_probability * 100.0,
                odds,
                probability_haircut=0.0,
                kelly_fraction=0.25,
                kelly_cap=MAX_STAKE_FRACTION,
            )
        except BettingMathError:
            continue
        if metrics.risk_adjusted_expected_roi < 0:
            continue
        priced.append((candidate, odds, metrics.risk_adjusted_expected_roi / 100.0))

    options: list[QuotedTicket] = []
    for size in range(1, MAX_TICKET_LEGS + 1):
        for entries in combinations(priced, size):
            candidates_in_ticket = tuple(entry[0] for entry in entries)
            if len({candidate.fixture_id for candidate in candidates_in_ticket}) != size:
                continue
            total_odds = math.prod(entry[1] for entry in entries)
            if not odds_min <= total_odds <= odds_max:
                continue
            dependency_factor = CROSS_LEG_MODEL_FACTOR ** max(0, size - 1)
            joint_probability = (
                math.prod(
                    candidate.conservative_probability for candidate in candidates_in_ticket
                )
                * dependency_factor
            )
            expected_roi = joint_probability * total_odds - 1.0
            if expected_roi < minimum_ticket_roi:
                continue
            metrics = evaluate_market_price(
                joint_probability * 100.0,
                total_odds,
                probability_haircut=0.0,
                kelly_fraction=0.25,
                kelly_cap=MAX_STAKE_FRACTION,
            )
            legs = tuple(
                QuotedLeg(candidate=entry[0], odds=entry[1], expected_roi=entry[2])
                for entry in entries
            )
            options.append(
                QuotedTicket(
                    legs=legs,
                    total_odds=round(total_odds, 4),
                    joint_probability=round(joint_probability, 6),
                    expected_roi=round(expected_roi, 6),
                    stake_fraction=round(metrics.kelly_fraction, 6),
                    model_dependency_factor=round(dependency_factor, 6),
                )
            )
    if not options:
        return None
    return max(
        options,
        key=lambda ticket: (
            ticket.joint_probability,
            ticket.expected_roi,
            -len(ticket.legs),
        ),
    )


def ticket_stake(ticket: QuotedTicket, available_balance: float) -> float:
    balance = _finite_nonnegative(available_balance)
    if balance is None:
        raise ValueError("Available balance must be finite and non-negative")
    return round(min(balance, balance * min(ticket.stake_fraction, MAX_STAKE_FRACTION)), 2)


__all__ = [
    "ChallengeCandidate",
    "CROSS_LEG_MODEL_FACTOR",
    "MARKET_BY_KEY",
    "MARKET_SPECS",
    "MAX_STAKE_FRACTION",
    "MAX_TICKET_LEGS",
    "QuotedTicket",
    "TARGET_BALANCE",
    "TARGET_ODDS_MAX",
    "TARGET_ODDS_MIN",
    "ValidationMetrics",
    "apply_candidate_context",
    "build_fixture_candidates",
    "fixture_market_probabilities",
    "market_outcome",
    "market_probability",
    "score_matrix",
    "select_model_ticket",
    "select_quoted_ticket",
    "select_shortlist",
    "ticket_stake",
    "validate_league_markets",
]
