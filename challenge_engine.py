"""Bookmaker-independent model and ticket logic for the 15K challenge.

The module deliberately separates event probabilities from market prices.
Bookmaker odds may constrain a final ticket and determine value, but they never
create, modify, or rank the underlying match candidates.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
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
DEFAULT_CHALLENGE_STAKE_FRACTION = 1.0
MIN_CHALLENGE_STAKE_FRACTION = 0.05
MAX_CHALLENGE_STAKE_FRACTION = 1.0
KELLY_REFERENCE_CAP = 0.25
CROSS_LEG_MODEL_FACTOR = 0.97

MIN_LEAGUE_MATCHES = 24
MIN_VENUE_MATCHES = 5
MIN_FORM_MATCHES = 5
MIN_H2H_MATCHES = 3
MIN_VALIDATION_MATCHES = 200
MIN_CALIBRATION_BINS = 3
MIN_CALIBRATION_BIN_SIZE = 20
MAX_EXPECTED_CALIBRATION_ERROR = 0.08
MAX_CALIBRATION_BIN_ERROR = 0.12
# z-Wert für die stichprobenadaptive Bin-Schwelle: ~98,8 % Konfidenz pro Bin,
# familienweise über 5 Bins ~6 % Falsch-Alarm bei perfekter Kalibrierung.
CALIBRATION_Z_SCORE = 2.5
# Kalibrierungsschicht: binierte, zur Identität geschrumpfte Isotonie-Karte
# pro Liga+Markt, gefittet ausschließlich auf Walk-forward-Prädiktionen.
CALIBRATION_MIN_SAMPLES = 100
CALIBRATION_REFIT_NEW_SAMPLES = 60
CALIBRATION_BIN_COUNT = 10
CALIBRATION_SHRINKAGE = 25.0
MIN_LEG_EXPECTED_ROI = 0.02

# Expected-Goals-Hybrid: Stärken werden aus Toren UND xG geschätzt.
# xG hat pro Spiel deutlich weniger Varianz als Tore; Inverse-Varianz-Logik
# (Var(Tore|lambda) = lambda vs. Var(xG-Fehler) ~ 0.6 * lambda) ergibt ~0.6.
XG_BLEND_WEIGHT = 0.6
XG_MIN_COVERAGE = 0.6
XG_MAX_MATCH_VALUE = 12.0


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
    calibration_bins: int = 0
    min_bin_size: int = 0
    max_calibration_error: Optional[float] = None
    max_error_bin_size: int = 0
    max_error_bin_mean_probability: Optional[float] = None
    raw_brier_score: Optional[float] = None


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
    if not isinstance(fixture, dict):
        return None
    fixture_data = fixture.get("fixture")
    if not isinstance(fixture_data, dict):
        return None
    return _parse_kickoff(fixture_data.get("date"))


def _fixture_score(fixture: dict[str, Any]) -> Optional[tuple[int, int]]:
    if not isinstance(fixture, dict) or not isinstance(fixture.get("goals"), dict):
        return None
    home = fixture["goals"].get("home")
    away = fixture["goals"].get("away")
    if isinstance(home, bool) or isinstance(away, bool):
        return None
    if not isinstance(home, int) or not isinstance(away, int) or home < 0 or away < 0:
        return None
    return home, away


def _is_completed_before(fixture: dict[str, Any], before: datetime) -> bool:
    score = _fixture_score(fixture)
    played_at = _fixture_datetime(fixture)
    return score is not None and played_at is not None and played_at < before


def _fixture_xg(fixture: dict[str, Any]) -> Optional[tuple[float, float]]:
    """Expected-Goals-Paar (Heim, Auswärts) aus challenge_stats, sonst None."""
    if not isinstance(fixture, dict):
        return None
    stats = fixture.get("challenge_stats")
    if not isinstance(stats, dict):
        return None
    home = _finite_nonnegative(stats.get("xg_home"))
    away = _finite_nonnegative(stats.get("xg_away"))
    if (
        home is None
        or away is None
        or home > XG_MAX_MATCH_VALUE
        or away > XG_MAX_MATCH_VALUE
    ):
        return None
    return home, away


def score_matrix(home_lambda: float, away_lambda: float, max_goals: int = 25) -> dict[tuple[int, int], float]:
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

    def marginal(rate: float) -> list[float]:
        values = [poisson(goals, rate) for goals in range(max_goals + 1)]
        tail = max(0.0, 1.0 - sum(values))
        if tail > 0.00001:
            raise ValueError("max_goals truncates too much probability mass")
        values[-1] += tail
        mass = sum(values)
        return [value / mass for value in values]

    home_probabilities = marginal(home_rate)
    away_probabilities = marginal(away_rate)
    matrix = {
        (home, away): home_probabilities[home] * away_probabilities[away]
        for home in range(max_goals + 1)
        for away in range(max_goals + 1)
    }
    mass = sum(matrix.values())
    if mass <= 0:
        raise ValueError("Score matrix has no probability mass")
    return {score: probability / mass for score, probability in matrix.items()}


def market_outcome(spec: MarketSpec, home_count: int, away_count: int) -> bool:
    """Settle a supported market on its two full-time count values."""
    if not isinstance(spec, MarketSpec):
        raise ValueError("spec must be a supported MarketSpec")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (home_count, away_count)
    ):
        raise ValueError("market counts must be non-negative integers")
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
) -> list[tuple[float, float, datetime, Optional[float], Optional[float]]]:
    """Letzte Spiele eines Teams: (Tore, Gegentore, Datum, xG, xGA)."""
    rows: list[tuple[float, float, datetime, Optional[float], Optional[float]]] = []
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
        xg_pair = _fixture_xg(fixture)
        if xg_pair is not None:
            xg_scored, xg_conceded = (
                xg_pair if actual_venue == "home" else (xg_pair[1], xg_pair[0])
            )
        else:
            xg_scored, xg_conceded = None, None
        rows.append(
            (float(scored), float(conceded), _fixture_datetime(fixture), xg_scored, xg_conceded)
        )
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


def _hybrid_strength(
    rows: list[tuple[float, float, datetime, Optional[float], Optional[float]]],
    *,
    scored: bool,
    prior_mean: float,
    prior_weight: float = 4.0,
) -> tuple[float, float]:
    """Geschrumpfte Team-Stärke aus Toren, mit xG geblendet (0.6/0.4).

    Gibt (Stärke, xG-Abdeckung) zurück. xG und Tore werden separat gegen
    denselben Liga-Prior geschrumpft und erst danach gewichtet gemischt;
    bei zu geringer xG-Abdeckung bleibt es beim reinen Tormodell.
    """
    goals_index = 0 if scored else 1
    xg_index = 3 if scored else 4
    base = _shrunk_mean((row[goals_index] for row in rows), prior_mean, prior_weight)
    xg_values = [row[xg_index] for row in rows if row[xg_index] is not None]
    coverage = len(xg_values) / len(rows) if rows else 0.0
    if rows and coverage >= XG_MIN_COVERAGE and xg_values:
        xg_part = _shrunk_mean(xg_values, prior_mean, prior_weight)
        return XG_BLEND_WEIGHT * xg_part + (1.0 - XG_BLEND_WEIGHT) * base, coverage
    return base, coverage


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

    home_scored, cov_hs = _hybrid_strength(home_venue, scored=True, prior_mean=league_home)
    home_conceded, cov_hc = _hybrid_strength(home_venue, scored=False, prior_mean=league_away)
    away_scored, cov_as = _hybrid_strength(away_venue, scored=True, prior_mean=league_away)
    away_conceded, cov_ac = _hybrid_strength(away_venue, scored=False, prior_mean=league_home)
    season_home = (home_scored + away_conceded) / 2.0
    season_away = (away_scored + home_conceded) / 2.0

    league_team_mean = (league_home + league_away) / 2.0
    form_home_attack, cov_fha = _hybrid_strength(
        home_form, scored=True, prior_mean=league_team_mean, prior_weight=3.0
    )
    form_away_defense, cov_fad = _hybrid_strength(
        away_form, scored=False, prior_mean=league_team_mean, prior_weight=3.0
    )
    form_away_attack, cov_faa = _hybrid_strength(
        away_form, scored=True, prior_mean=league_team_mean, prior_weight=3.0
    )
    form_home_defense, cov_fhd = _hybrid_strength(
        home_form, scored=False, prior_mean=league_team_mean, prior_weight=3.0
    )
    form_home = (form_home_attack + form_away_defense) / 2.0
    form_away = (form_away_attack + form_home_defense) / 2.0

    active_home = 0.75 * season_home + 0.25 * form_home
    active_away = 0.75 * season_away + 0.25 * form_away
    latest_observation = max(home_form[0][2], away_form[0][2])
    freshness_days = max(0.0, (kickoff - latest_observation).total_seconds() / 86_400.0)
    xg_coverage = min(
        cov_hs, cov_hc, cov_as, cov_ac, cov_fha, cov_fad, cov_faa, cov_fhd
    )
    return {
        "active_lambdas": (active_home, active_away),
        "season_lambdas": (season_home, season_away),
        "form_lambdas": (form_home, form_away),
        "venue_samples": (len(home_venue), len(away_venue)),
        "form_samples": (len(home_form), len(away_form)),
        "league_sample": league_sample,
        "freshness_days": freshness_days,
        "xg_coverage": xg_coverage,
    }


def _fixture_count_pair(
    fixture: dict[str, Any],
    family: str,
) -> Optional[tuple[int, int]]:
    if not isinstance(fixture, dict):
        return None
    stats = fixture.get("challenge_stats") or {}
    if not isinstance(stats, dict):
        return None
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
    if isinstance(max_count, bool) or not isinstance(max_count, int) or max_count < 1:
        raise ValueError("max_count must be a positive integer")
    parameters = (home_mean, away_mean, home_alpha, away_alpha)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in parameters
    ) or home_mean < 0 or away_mean < 0 or home_alpha <= 0 or away_alpha <= 0:
        raise ValueError("count distribution parameters are invalid")

    def marginal(mean: float, alpha: float) -> list[float]:
        values = [
            _negative_binomial_pmf(count, mean, alpha)
            for count in range(max_count)
        ]
        values.append(max(0.0, 1.0 - sum(values)))
        mass = sum(values)
        if mass <= 0:
            raise ValueError("Count distribution has no probability mass")
        return [value / mass for value in values]

    home_probabilities = marginal(home_mean, home_alpha)
    away_probabilities = marginal(away_mean, away_alpha)
    matrix = {
        (home, away): home_probabilities[home] * away_probabilities[away]
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
    calibration: Optional[dict[str, MarketCalibration]] = None,
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
    if calibration:
        for market_key, values in model["probabilities"].items():
            curve = calibration.get(market_key)
            if curve is not None:
                model["probabilities"][market_key] = tuple(curve(value) for value in values)
        model["calibrated_markets"] = len(
            [key for key in model["probabilities"] if key in calibration]
        )
    return model


def _calibration_diagnostics(
    predictions: list[float],
    outcomes: list[int],
) -> tuple[float, int, int, Optional[float], int, Optional[float]]:
    """ECE und Bin-Diagnostik auf besetzungsgleichen (Quantil-)Bins.

    Fixe 0.2-Raster passen nicht zum Vorhersagebereich des Modells: Liegen
    alle Wahrscheinlichkeiten z. B. zwischen 0.2 und 0.6, bleiben drei von
    fünf Rasterzellen leer und die Kalibrierung wirkt schlecht belegt, obwohl
    genug Daten vorliegen. Quantil-Bins (jeweils ~n/5 Beobachtungen) sind der
    übliche Schätzer und machen die Belegung konstruktionsbedingt gleich;
    identische Vorhersagewerte landen garantiert im selben Bin.
    """
    if not predictions or len(predictions) != len(outcomes):
        return 1.0, 0, 0, None, 0, None
    total = len(predictions)
    ordered_values = sorted(float(value) for value in predictions)
    edge_candidates = (
        ordered_values[min(total - 1, int(fraction * total))]
        for fraction in (0.2, 0.4, 0.6, 0.8)
    )
    edges = sorted(set(edge_candidates))

    bins: dict[int, list[int]] = {}
    for index, probability in enumerate(predictions):
        bin_index = bisect_right(edges, float(probability))
        bins.setdefault(bin_index, []).append(index)

    error = 0.0
    supported_sizes: list[int] = []
    supported_deviations: list[float] = []
    supported_means: list[float] = []
    for indices in bins.values():
        mean_probability = _mean(predictions[index] for index in indices)
        observed_rate = _mean(outcomes[index] for index in indices)
        deviation = abs(mean_probability - observed_rate)
        error += len(indices) / total * deviation
        if len(indices) >= MIN_CALIBRATION_BIN_SIZE:
            supported_sizes.append(len(indices))
            supported_deviations.append(deviation)
            supported_means.append(mean_probability)
    if not supported_deviations:
        return error, 0, 0, None, 0, None
    worst = max(range(len(supported_deviations)), key=lambda index: supported_deviations[index])
    return (
        error,
        len(supported_sizes),
        min(supported_sizes),
        supported_deviations[worst],
        supported_sizes[worst],
        supported_means[worst],
    )


def adaptive_bin_threshold(
    mean_probability: Optional[float],
    bin_size: int,
) -> float:
    """Stichprobenadaptive Bin-Schwelle: max(0.12, z * Binomial-SE).

    Eine starre Schwelle bestraft kleine Bins für reines Zufallsrauschen:
    bei n=56 liegt die 1σ-Streuung einer perfekt kalibrierten Vorhersage
    schon bei ±0.064. Die Schwelle steigt deshalb mit 1/sqrt(n), bleibt
    aber für große Stichproben beim inhaltlichen Standard 0.12.
    """
    if (
        mean_probability is None
        or not isinstance(mean_probability, (int, float))
        or not math.isfinite(float(mean_probability))
        or not isinstance(bin_size, int)
        or isinstance(bin_size, bool)
        or bin_size < 1
    ):
        return 1.0  # ohne Bin-Kontext kein Freispruch möglich
    probability = min(0.99, max(0.01, float(mean_probability)))
    standard_error = math.sqrt(probability * (1.0 - probability) / bin_size)
    return max(MAX_CALIBRATION_BIN_ERROR, CALIBRATION_Z_SCORE * standard_error)


@dataclass(frozen=True)
class MarketCalibration:
    """Monotone Kalibrierungskurve: rohe Modell-Wahrscheinlichkeit -> kalibriert.

    Stückweise linear zwischen den Stützstellen, außerhalb flach fortgesetzt.
    Die Kurve wird ausschließlich aus Walk-forward-Prädiktionen gefittet, also
    nur aus Information, die zum jeweiligen Vorhersagezeitpunkt vorlag.
    """

    points: tuple[tuple[float, float], ...]
    samples: int

    def __call__(self, probability: float) -> float:
        if not self.points:
            return probability
        value = min(1.0, max(0.0, float(probability)))
        xs = [point[0] for point in self.points]
        if value <= xs[0]:
            return self.points[0][1]
        if value >= xs[-1]:
            return self.points[-1][1]
        index = bisect_right(xs, value)
        x0, y0 = self.points[index - 1]
        x1, y1 = self.points[index]
        if x1 <= x0:
            return y1
        weight = (value - x0) / (x1 - x0)
        return y0 + weight * (y1 - y0)


def _pava(blocks: list[list[float]]) -> list[list[float]]:
    """Pool-Adjacent-Violators für monotone Niveaus (gewichtet).

    blocks: [sum_wx, sum_wy, sum_w] pro Bin; verschmilzt Verletzer zu Blöcken
    und liefert die Endblöcke mit ihren gewichteten Mittelpunkten.
    """
    merged = [block[:] for block in blocks]
    index = 0
    while index < len(merged) - 1:
        level_here = merged[index][1] / merged[index][2]
        level_next = merged[index + 1][1] / merged[index + 1][2]
        if level_here > level_next + 1e-12:
            merged[index][0] += merged[index + 1][0]
            merged[index][1] += merged[index + 1][1]
            merged[index][2] += merged[index + 1][2]
            del merged[index + 1]
            if index > 0:
                index -= 1
        else:
            index += 1
    return merged


def _fit_calibration_map(
    probabilities: list[float],
    outcomes: list[int],
) -> Optional[MarketCalibration]:
    """Binierte, isotonische Kalibrierungskarte mit Schrumpfung zur Identität.

    Gleich besetzte Bins über den rohen Wahrscheinlichkeiten; pro Bin wird die
    Trefferrate mit ``CALIBRATION_SHRINKAGE`` Pseudo-Beobachtungen Richtung der
    Vorhersage gezogen (kleine Bins => fast Identität), danach erzwingt PAVA
    Monotonie. Unter ``CALIBRATION_MIN_SAMPLES`` bleibt alles unkalibriert.
    """
    total = len(probabilities)
    if total < CALIBRATION_MIN_SAMPLES or total != len(outcomes):
        return None
    order = sorted(range(total), key=lambda index: probabilities[index])
    bin_count = min(CALIBRATION_BIN_COUNT, max(2, total // 40))
    blocks: list[list[float]] = []
    start = 0
    base, extra = divmod(total, bin_count)
    for bucket_index in range(bin_count):
        size = base + (1 if bucket_index < extra else 0)
        bucket = order[start : start + size]
        start += size
        if not bucket:
            continue
        mean_probability = _mean(probabilities[index] for index in bucket)
        observed_rate = _mean(outcomes[index] for index in bucket)
        count = len(bucket)
        shrunk_rate = (
            observed_rate * count + CALIBRATION_SHRINKAGE * mean_probability
        ) / (count + CALIBRATION_SHRINKAGE)
        blocks.append([mean_probability * count, shrunk_rate * count, float(count)])
    merged = _pava(blocks)
    points = tuple(
        (
            min(0.999, max(0.001, block[0] / block[2])),
            min(0.999, max(0.001, block[1] / block[2])),
        )
        for block in merged
    )
    # Stützstellen müssen streng aufsteigend sein (bisect-Interpolation).
    deduped: list[tuple[float, float]] = []
    for point in points:
        if deduped and point[0] <= deduped[-1][0] + 1e-9:
            deduped[-1] = point
        else:
            deduped.append(point)
    if len(deduped) < 2:
        return None
    return MarketCalibration(points=tuple(deduped), samples=total)


def _credible_validation(metric: Optional[ValidationMetrics]) -> bool:
    """Re-check the full validation contract instead of trusting one flag."""
    if metric is None or metric.passed is not True:
        return False
    count_values = (
        metric.observations,
        metric.calibration_bins,
        metric.min_bin_size,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in count_values
    ):
        return False
    numeric_values = (
        metric.brier_score,
        metric.baseline_brier_score,
        metric.relative_improvement,
        metric.expected_calibration_error,
        metric.max_calibration_error,
    )
    try:
        invalid_numeric = any(
            value is None
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in numeric_values
        )
    except (TypeError, ValueError):
        return False
    if invalid_numeric:
        return False
    if (
        not isinstance(metric.max_error_bin_size, int)
        or isinstance(metric.max_error_bin_size, bool)
        or metric.max_error_bin_size < 0
    ):
        return False
    bin_threshold = adaptive_bin_threshold(
        metric.max_error_bin_mean_probability,
        metric.max_error_bin_size,
    )
    return bool(
        metric.observations >= MIN_VALIDATION_MATCHES
        and 0.0 <= metric.brier_score <= 1.0
        and 0.0 < metric.baseline_brier_score <= 1.0
        and 0.02 <= metric.relative_improvement <= 1.0
        and 0.0 <= metric.expected_calibration_error <= MAX_EXPECTED_CALIBRATION_ERROR
        and MIN_CALIBRATION_BINS <= metric.calibration_bins <= 5
        and metric.min_bin_size >= MIN_CALIBRATION_BIN_SIZE
        and metric.min_bin_size <= metric.observations
        and metric.calibration_bins * metric.min_bin_size <= metric.observations
        and 0.0 <= metric.max_calibration_error <= bin_threshold
    )


def validate_league_markets(
    fixtures: Iterable[dict[str, Any]],
) -> dict[str, ValidationMetrics]:
    """Run an expanding-window, leakage-free market validation."""
    ordered = sorted(
        (fixture for fixture in fixtures if _fixture_datetime(fixture) and _fixture_score(fixture)),
        key=lambda item: _fixture_datetime(item),
    )
    records: dict[str, dict[str, list[float]]] = {
        spec.key: {"probabilities": [], "outcomes": [], "baselines": [], "raw": []}
        for spec in MARKET_SPECS
    }
    prior: list[dict[str, Any]] = []
    event_successes = {spec.key: 0 for spec in MARKET_SPECS}
    event_totals = {spec.key: 0 for spec in MARKET_SPECS}
    # Kalibrierungszustand pro Markt: Die Karte für Tag t wurde nur aus
    # Beobachtungen vor Tag t gefittet und wird periodisch nachgezogen.
    calibration_state: dict[str, dict[str, Any]] = {
        spec.key: {"map": None, "count": 0} for spec in MARKET_SPECS
    }

    grouped: dict[datetime, list[dict[str, Any]]] = {}
    for fixture in ordered:
        played_at = _fixture_datetime(fixture)
        if played_at is not None:
            day = played_at.replace(hour=0, minute=0, second=0, microsecond=0)
            grouped.setdefault(day, []).append(fixture)

    for day in sorted(grouped):
        day_fixtures = grouped[day]
        for fixture in day_fixtures:
            prediction = fixture_market_probabilities(fixture, prior)
            if prediction is None:
                continue
            for spec in MARKET_SPECS:
                probability_values = prediction["probabilities"].get(spec.key)
                outcome_value = _fixture_market_outcome(spec, fixture)
                if probability_values is None or outcome_value is None:
                    continue
                raw_probability = probability_values[0]
                curve = calibration_state[spec.key]["map"]
                probability = curve(raw_probability) if curve is not None else raw_probability
                outcome = int(outcome_value)
                baseline = (event_successes[spec.key] + 1.0) / (event_totals[spec.key] + 2.0)
                records[spec.key]["probabilities"].append(probability)
                records[spec.key]["outcomes"].append(outcome)
                records[spec.key]["baselines"].append(baseline)
                records[spec.key]["raw"].append(raw_probability)

        for fixture in day_fixtures:
            for spec in MARKET_SPECS:
                outcome_value = _fixture_market_outcome(spec, fixture)
                if outcome_value is None:
                    continue
                outcome = int(outcome_value)
                event_successes[spec.key] += outcome
                event_totals[spec.key] += 1
        prior.extend(day_fixtures)

        # Refit erst nach Tagesende: Die Karte ab morgen kennt heute.
        for spec in MARKET_SPECS:
            record = records[spec.key]
            state = calibration_state[spec.key]
            if len(record["raw"]) - state["count"] >= CALIBRATION_REFIT_NEW_SAMPLES:
                new_map = _fit_calibration_map(record["raw"], record["outcomes"])
                if new_map is not None:
                    state["map"] = new_map
                    state["count"] = len(record["raw"])

    metrics: dict[str, ValidationMetrics] = {}
    for spec in MARKET_SPECS:
        record = records[spec.key]
        probabilities = record["probabilities"]
        outcomes = [int(value) for value in record["outcomes"]]
        baselines = record["baselines"]
        raw_probabilities = record["raw"]
        observations = len(probabilities)
        if observations == 0:
            metrics[spec.key] = ValidationMetrics(0, None, None, None, None, False)
            continue
        brier = _mean((probability - outcome) ** 2 for probability, outcome in zip(probabilities, outcomes))
        raw_brier = _mean(
            (probability - outcome) ** 2 for probability, outcome in zip(raw_probabilities, outcomes)
        )
        baseline_brier = _mean((probability - outcome) ** 2 for probability, outcome in zip(baselines, outcomes))
        improvement = (baseline_brier - brier) / baseline_brier if baseline_brier > 0 else None
        (
            ece,
            calibration_bins,
            min_bin_size,
            max_calibration_error,
            max_error_bin_size,
            max_error_bin_mean,
        ) = _calibration_diagnostics(probabilities, outcomes)
        bin_threshold = adaptive_bin_threshold(max_error_bin_mean, max_error_bin_size)
        passed = (
            observations >= MIN_VALIDATION_MATCHES
            and improvement is not None
            and improvement >= 0.02
            and ece <= MAX_EXPECTED_CALIBRATION_ERROR
            and calibration_bins >= MIN_CALIBRATION_BINS
            and min_bin_size >= MIN_CALIBRATION_BIN_SIZE
            and max_calibration_error is not None
            and max_calibration_error <= bin_threshold
        )
        metrics[spec.key] = ValidationMetrics(
            observations=observations,
            brier_score=round(brier, 6),
            baseline_brier_score=round(baseline_brier, 6),
            relative_improvement=round(improvement, 6) if improvement is not None else None,
            expected_calibration_error=round(ece, 6),
            passed=passed,
            calibration_bins=calibration_bins,
            min_bin_size=min_bin_size,
            max_calibration_error=(
                round(max_calibration_error, 6)
                if max_calibration_error is not None else None
            ),
            max_error_bin_size=max_error_bin_size,
            max_error_bin_mean_probability=(
                round(max_error_bin_mean, 6)
                if max_error_bin_mean is not None else None
            ),
            raw_brier_score=round(raw_brier, 6),
        )
    return metrics


def fit_market_calibration(
    fixtures: Iterable[dict[str, Any]],
) -> dict[str, MarketCalibration]:
    """Finale Kalibrierungskarten pro Markt für neue Kandidaten.

    Nutzt denselben tagesgruppierten Walk-forward wie die Validierung, fittet
    die Karte aber auf allen gesammelten Prädiktionen — für ein künftiges
    Spiel ist das vollständig vergangenheitsbasiert (leakage-frei).
    """
    ordered = sorted(
        (fixture for fixture in fixtures if _fixture_datetime(fixture) and _fixture_score(fixture)),
        key=lambda item: _fixture_datetime(item),
    )
    raw_records: dict[str, dict[str, list[float]]] = {
        spec.key: {"probabilities": [], "outcomes": []} for spec in MARKET_SPECS
    }
    prior: list[dict[str, Any]] = []
    grouped: dict[datetime, list[dict[str, Any]]] = {}
    for fixture in ordered:
        played_at = _fixture_datetime(fixture)
        if played_at is not None:
            day = played_at.replace(hour=0, minute=0, second=0, microsecond=0)
            grouped.setdefault(day, []).append(fixture)

    for day in sorted(grouped):
        day_fixtures = grouped[day]
        for fixture in day_fixtures:
            prediction = fixture_market_probabilities(fixture, prior)
            if prediction is None:
                continue
            for spec in MARKET_SPECS:
                probability_values = prediction["probabilities"].get(spec.key)
                outcome_value = _fixture_market_outcome(spec, fixture)
                if probability_values is None or outcome_value is None:
                    continue
                raw_records[spec.key]["probabilities"].append(probability_values[0])
                raw_records[spec.key]["outcomes"].append(int(outcome_value))
        prior.extend(day_fixtures)

    maps: dict[str, MarketCalibration] = {}
    for spec in MARKET_SPECS:
        record = raw_records[spec.key]
        curve = _fit_calibration_map(record["probabilities"], record["outcomes"])
        if curve is not None:
            maps[spec.key] = curve
    return maps


def _fixture_identity(fixture: dict[str, Any]) -> Optional[dict[str, Any]]:
    fixture_data = fixture.get("fixture", {})
    teams = fixture.get("teams", {})
    league = fixture.get("league", {})
    fixture_id = fixture_data.get("id")
    league_id = league.get("id")
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in (fixture_id, league_id, home_id, away_id)
    ) or home_id == away_id:
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
    calibration: Optional[dict[str, MarketCalibration]] = None,
) -> list[ChallengeCandidate]:
    """Build price-independent candidates for one fixture."""
    identity = _fixture_identity(fixture)
    model = fixture_market_probabilities(fixture, league_history, calibration)
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
        metric = validation.get(spec.key)
        structural_haircut = 3.0 + spread_pp * 0.5 + sample_penalty + freshness_penalty
        calibration_haircut = (
            float(metric.max_calibration_error) * 100.0
            if metric and metric.max_calibration_error is not None
            and math.isfinite(float(metric.max_calibration_error))
            else 20.0
        )
        haircut_pp = min(20.0, max(structural_haircut, calibration_haircut))
        conservative = max(0.0, min(active, season, form) - haircut_pp / 100.0)
        validation_passed = _credible_validation(metric)

        sample_score = 35.0 * min(1.0, min(venue_samples) / 10.0)
        form_score = 15.0 * min(1.0, min(form_samples) / 6.0)
        agreement_score = 20.0 * max(0.0, 1.0 - spread_pp / 20.0)
        freshness_score = 10.0 * max(0.0, 1.0 - max(0.0, freshness_days - 7.0) / 28.0)
        validation_score = 20.0 if validation_passed else 0.0
        evidence = min(100.0, sample_score + form_score + agreement_score + freshness_score + validation_score)

        blocked: list[str] = []
        if not 0.58 <= active <= 0.92:
            blocked.append("Modellwahrscheinlichkeit außerhalb des Challenge-Korridors")
        if conservative < 0.55:
            blocked.append("Konservative Wahrscheinlichkeit unter 55 %")
        if spread_pp > 12.0:
            blocked.append("Saison- und Formmodell widersprechen sich")
        if not validation_passed:
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
        xg_coverage = float(model.get("xg_coverage", 0.0) or 0.0)
        if xg_coverage >= XG_MIN_COVERAGE:
            reasons.append(f"xG-Hybrid aktiv (Abdeckung {xg_coverage * 100:.0f} %)")
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
    # Sort by kickoff descending instead of trusting provider delivery order,
    # so "last 10" always means the ten most recent completed meetings.
    ordered = sorted(
        (fixture for fixture in fixtures if isinstance(fixture, dict)),
        key=lambda item: _fixture_datetime(item) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    scores: list[tuple[int, int]] = []
    for fixture in ordered:
        score = _fixture_score(fixture)
        if score is None:
            continue
        teams = fixture.get("teams")
        if not isinstance(teams, dict):
            continue
        home = teams.get("home")
        away = teams.get("away")
        if not isinstance(home, dict) or not isinstance(away, dict):
            continue
        historical_home = home.get("id")
        historical_away = away.get("id")
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
    if not isinstance(injuries, list) or any(not isinstance(entry, dict) for entry in injuries):
        return False, {"status": "unavailable"}, "Verletzungsdaten sind ungültig"

    summary: dict[int, dict[str, Any]] = {
        home_team_id: {"missing": set(), "questionable": set(), "names": []},
        away_team_id: {"missing": set(), "questionable": set(), "names": []},
    }
    for entry in injuries:
        team = entry.get("team")
        player = entry.get("player")
        if not isinstance(team, dict) or not isinstance(player, dict):
            return False, {"status": "unavailable"}, "Verletzungsdaten sind unvollständig"
        team_id = team.get("id")
        if team_id not in summary:
            continue
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
    if not isinstance(weather, dict) or weather.get("status") != "ok":
        return False, {"status": "unavailable"}, "Wetter zum Anpfiff konnte nicht verifiziert werden"
    temperature = _finite_number(weather.get("temperature_c"))
    wind = _finite_nonnegative(weather.get("wind_mps"))
    rain = _finite_nonnegative(weather.get("rain_3h_mm"))
    snow = _finite_nonnegative(weather.get("snow_3h_mm"))
    if temperature is None or wind is None or rain is None or snow is None:
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
    home_team_id: int,
    away_team_id: int,
) -> tuple[bool, dict[str, Any], Optional[str]]:
    minutes_to_kickoff = (kickoff - now).total_seconds() / 60.0
    confirmed_teams: set[int] = set()
    if isinstance(lineups, list):
        for item in lineups:
            if not isinstance(item, dict):
                continue
            team = item.get("team")
            starters = item.get("startXI")
            if not isinstance(team, dict) or not isinstance(starters, list):
                continue
            team_id = team.get("id")
            if team_id not in {home_team_id, away_team_id} or team_id in confirmed_teams:
                continue
            player_ids: list[int] = []
            for starter in starters:
                if not isinstance(starter, dict) or not isinstance(starter.get("player"), dict):
                    continue
                player_id = starter["player"].get("id")
                if isinstance(player_id, bool) or not isinstance(player_id, int) or player_id <= 0:
                    continue
                player_ids.append(player_id)
            if len(player_ids) == 11 and len(set(player_ids)) == 11:
                confirmed_teams.add(team_id)
    complete = confirmed_teams == {home_team_id, away_team_id}
    if not complete:
        reason = (
            "Aufstellungen fehlen kurz vor Anpfiff"
            if minutes_to_kickoff <= 60
            else "Aufstellungen sind noch nicht verifiziert"
        )
        return False, {"status": "required_missing", "required": True}, reason
    return True, {
        "status": "passed",
        "required": True,
        "teams": len(confirmed_teams),
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
    if kickoff <= now_utc:
        candidate.context = {"passed": False, "blocked_reasons": ["Spiel hat bereits begonnen"]}
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
    lineup_passed, lineup_summary, lineup_reason = _lineup_summary(
        lineups,
        kickoff,
        now_utc,
        candidate.home_team_id,
        candidate.away_team_id,
    )
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
    if (
        isinstance(max_candidates, bool)
        or not isinstance(max_candidates, int)
        or max_candidates < 1
    ):
        raise ValueError("max_candidates must be a positive integer")
    eligible = [candidate for candidate in candidates if candidate_is_credible(candidate)]
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


def candidate_is_credible(candidate: ChallengeCandidate) -> bool:
    """Validate the complete candidate contract again at selection time."""
    if not isinstance(candidate, ChallengeCandidate):
        return False
    if (
        not isinstance(candidate.blocked_reasons, list)
        or candidate.blocked_reasons
        or not isinstance(candidate.context, dict)
        or candidate.context.get("passed") is not True
    ):
        return False
    if not _credible_validation(candidate.validation):
        return False
    integer_values = (
        candidate.fixture_id,
        candidate.league_id,
        candidate.home_team_id,
        candidate.away_team_id,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in integer_values
    ):
        return False
    if candidate.home_team_id == candidate.away_team_id:
        return False
    if candidate.market_key not in MARKET_BY_KEY:
        return False
    numeric_values = (
        candidate.probability,
        candidate.conservative_probability,
        candidate.probability_haircut_pp,
        candidate.model_price,
        candidate.evidence_score,
        candidate.model_spread_pp,
        candidate.expected_home_goals,
        candidate.expected_away_goals,
    )
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in numeric_values
    ):
        return False
    if not (
        0.0 < candidate.conservative_probability <= candidate.probability <= 1.0
        and 0.0 <= candidate.probability_haircut_pp <= 20.0
        and 72.0 <= candidate.evidence_score <= 100.0
        and 0.0 <= candidate.model_spread_pp <= 12.0
        and 0.0 <= candidate.expected_home_goals <= 8.0
        and 0.0 <= candidate.expected_away_goals <= 8.0
    ):
        return False
    expected_price = 1.0 / candidate.conservative_probability
    if not math.isclose(candidate.model_price, expected_price, rel_tol=0.0, abs_tol=0.001):
        return False
    for samples, minimum in (
        (candidate.venue_samples, MIN_VENUE_MATCHES),
        (candidate.form_samples, MIN_FORM_MATCHES),
    ):
        if (
            not isinstance(samples, tuple)
            or len(samples) != 2
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < minimum
                for value in samples
            )
        ):
            return False
    return True


def _future_candidate(candidate: ChallengeCandidate, now: datetime) -> bool:
    kickoff = _parse_kickoff(candidate.kickoff)
    return kickoff is not None and kickoff > now


def _independent_fixture_set(candidates: Iterable[ChallengeCandidate]) -> bool:
    """Reject repeated fixtures or teams inside one accumulator."""
    items = tuple(candidates)
    if len({candidate.fixture_id for candidate in items}) != len(items):
        return False
    team_ids = [
        team_id
        for candidate in items
        for team_id in (candidate.home_team_id, candidate.away_team_id)
    ]
    return len(set(team_ids)) == len(team_ids)


def select_model_ticket(
    candidates: Iterable[ChallengeCandidate],
    odds_min: float = TARGET_ODDS_MIN,
    odds_max: float = TARGET_ODDS_MAX,
    *,
    now: Optional[datetime] = None,
) -> tuple[ChallengeCandidate, ...]:
    """Choose a quote-free preview using conservative model prices only."""
    try:
        odds_min = validate_decimal_odds(odds_min)
        odds_max = validate_decimal_odds(odds_max)
    except BettingMathError as exc:
        raise ValueError("Odds corridor must contain valid decimal odds") from exc
    if odds_min > odds_max:
        raise ValueError("Odds corridor minimum must not exceed its maximum")
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)
    board = [
        candidate for candidate in candidates
        if candidate_is_credible(candidate) and _future_candidate(candidate, now_utc)
    ]
    options: list[tuple[float, float, int, tuple[ChallengeCandidate, ...]]] = []
    for size in range(1, MAX_TICKET_LEGS + 1):
        for legs in combinations(board, size):
            if not _independent_fixture_set(legs):
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
    minimum_leg_roi: float = MIN_LEG_EXPECTED_ROI,
    now: Optional[datetime] = None,
) -> Optional[QuotedTicket]:
    """Return the strongest valid 1-3 leg ticket after manual price entry."""
    try:
        odds_min = validate_decimal_odds(odds_min)
        odds_max = validate_decimal_odds(odds_max)
    except BettingMathError as exc:
        raise ValueError("Odds corridor must contain valid decimal odds") from exc
    if odds_min > odds_max:
        raise ValueError("Odds corridor minimum must not exceed its maximum")
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)
    if (
        isinstance(minimum_ticket_roi, bool)
        or isinstance(minimum_leg_roi, bool)
        or not isinstance(minimum_ticket_roi, (int, float))
        or not isinstance(minimum_leg_roi, (int, float))
        or not math.isfinite(float(minimum_ticket_roi))
        or not math.isfinite(float(minimum_leg_roi))
        or minimum_ticket_roi < 0.0
        or minimum_leg_roi < 0.0
    ):
        raise ValueError("ROI thresholds must be finite and non-negative")
    priced: list[tuple[ChallengeCandidate, float, float]] = []
    for candidate in candidates:
        if not candidate_is_credible(candidate) or not _future_candidate(candidate, now_utc):
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
                kelly_cap=KELLY_REFERENCE_CAP,
            )
        except BettingMathError:
            continue
        if metrics.risk_adjusted_expected_roi < minimum_leg_roi * 100.0:
            continue
        priced.append((candidate, odds, metrics.risk_adjusted_expected_roi / 100.0))

    options: list[QuotedTicket] = []
    for size in range(1, MAX_TICKET_LEGS + 1):
        for entries in combinations(priced, size):
            candidates_in_ticket = tuple(entry[0] for entry in entries)
            if not _independent_fixture_set(candidates_in_ticket):
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
                kelly_cap=KELLY_REFERENCE_CAP,
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


def _stake_fraction(value: Any, label: str) -> float:
    fraction = _finite_nonnegative(value)
    if (
        fraction is None
        or fraction < MIN_CHALLENGE_STAKE_FRACTION
        or fraction > MAX_CHALLENGE_STAKE_FRACTION
    ):
        raise ValueError(f"{label} must be between 5% and 100%")
    return fraction


def ticket_stake(
    ticket: QuotedTicket,
    available_balance: float,
    challenge_fraction: float = DEFAULT_CHALLENGE_STAKE_FRACTION,
) -> float:
    """Return the configured challenge stake, rounded down to whole cents.

    ``ticket.stake_fraction`` remains the conservative quarter-Kelly reference.
    The challenge fraction is a separate, explicit risk decision because a
    roll-over challenge cannot mathematically operate under a hidden 2% cap.
    """
    balance = _finite_nonnegative(available_balance)
    if balance is None:
        raise ValueError("Available balance must be finite and non-negative")
    kelly_fraction = _finite_nonnegative(ticket.stake_fraction)
    if kelly_fraction is None or kelly_fraction > 1.0:
        raise ValueError("Ticket stake fraction must be finite and non-negative")
    fraction = _stake_fraction(challenge_fraction, "Challenge stake fraction")
    stake = min(balance, balance * fraction)
    return float(
        Decimal(str(stake)).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
    )


def kelly_reference_stake(ticket: QuotedTicket, available_balance: float) -> float:
    """Return quarter-Kelly as a comparison value, never as the challenge cap."""
    balance = _finite_nonnegative(available_balance)
    if balance is None:
        raise ValueError("Available balance must be finite and non-negative")
    fraction = _finite_nonnegative(ticket.stake_fraction)
    if fraction is None or fraction > KELLY_REFERENCE_CAP:
        raise ValueError("Ticket Kelly fraction is invalid")
    return float(
        Decimal(str(balance * fraction)).quantize(
            Decimal("0.01"),
            rounding=ROUND_FLOOR,
        )
    )


def consecutive_wins_to_target(
    current_balance: float,
    target_balance: float,
    decimal_odds: float,
    challenge_fraction: float,
) -> Optional[int]:
    """Return loss-free wins needed when the same bankroll fraction is rolled over."""
    current = _finite_nonnegative(current_balance)
    target = _finite_nonnegative(target_balance)
    if current is None or target is None:
        raise ValueError("Balances must be finite and non-negative")
    if current >= target:
        return 0
    if current <= 0.0:
        return None
    try:
        odds = validate_decimal_odds(decimal_odds)
    except BettingMathError as exc:
        raise ValueError("Decimal odds must be greater than 1") from exc
    fraction = _stake_fraction(challenge_fraction, "Challenge stake fraction")
    win_multiplier = 1.0 + fraction * (odds - 1.0)
    raw_steps = math.log(target / current) / math.log(win_multiplier)
    return max(1, math.ceil(raw_steps - 1e-12))


__all__ = [
    "ChallengeCandidate",
    "CROSS_LEG_MODEL_FACTOR",
    "DEFAULT_CHALLENGE_STAKE_FRACTION",
    "KELLY_REFERENCE_CAP",
    "MARKET_BY_KEY",
    "MARKET_SPECS",
    "MAX_CHALLENGE_STAKE_FRACTION",
    "MAX_TICKET_LEGS",
    "MIN_CHALLENGE_STAKE_FRACTION",
    "QuotedTicket",
    "TARGET_BALANCE",
    "TARGET_ODDS_MAX",
    "TARGET_ODDS_MIN",
    "ValidationMetrics",
    "apply_candidate_context",
    "build_fixture_candidates",
    "candidate_is_credible",
    "consecutive_wins_to_target",
    "fixture_market_probabilities",
    "market_outcome",
    "market_probability",
    "score_matrix",
    "select_model_ticket",
    "select_quoted_ticket",
    "select_shortlist",
    "kelly_reference_stake",
    "ticket_stake",
    "validate_league_markets",
]
