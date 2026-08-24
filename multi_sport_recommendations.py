"""Bookmaker-independent live models with a separate market-price gate.

The module deliberately exposes only markets that can be settled from the
available provider payload. A model candidate is created before a bookmaker
quote is supplied. The quote is used only to decide whether the price offers
enough risk-adjusted edge and expected return.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any, Optional, Sequence

try:  # Managed-Automation-Runner hat kein scipy; der E-Sport-Pfad braucht es nicht
    from scipy.stats import nbinom
except ImportError:  # pragma: no cover - nur in Runner-Umgebungen ohne scipy
    nbinom = None

from betting_math import (
    DEFAULT_KELLY_CAP,
    DEFAULT_KELLY_FRACTION,
    MINIMUM_RECOMMENDED_DECIMAL_ODDS,
    MINIMUM_RISK_ADJUSTED_ROI_PERCENT,
    BettingMathError,
    ValueMetrics,
    evaluate_market_price,
    minimum_recommendation_odds,
)
from esports_elo import (
    ELO_UNCERTAINTY_MARGIN,
    expected_score,
    subgraph_ratings,
)


# Edge remains a useful diagnostic, but it is not a universal release
# threshold: the same probability-point gap has a different monetary value at
# different prices. Risk-adjusted expected return is the shared price gate.
MINIMUM_EXPECTED_ROI_PERCENT = MINIMUM_RISK_ADJUSTED_ROI_PERCENT
MAXIMUM_KELLY_FRACTION = DEFAULT_KELLY_CAP
# No honest model is 100% certain. Above this probability the dominant risk is
# wrong input data (clock, score), not the model — display and evidence must
# say so instead of printing a rounded "100.0 %".
HIGH_PROBABILITY_DISPLAY_CAP = 99.5
HIGH_PROBABILITY_EVIDENCE_THRESHOLD = 97.0
EVIDENCE_RESEARCH = "RESEARCH"
EVIDENCE_SHADOW = "SHADOW"
EVIDENCE_RELEASED = "RELEASED"
EVIDENCE_UNAVAILABLE = "UNAVAILABLE"
EVIDENCE_LABELS = {
    EVIDENCE_RESEARCH: "Forschung",
    EVIDENCE_SHADOW: "Unabhängige Shadow-Prüfung",
    EVIDENCE_RELEASED: "Echtgeld-freigegeben",
    EVIDENCE_UNAVAILABLE: "Kein belastbares Modell",
}
ESPORTS_MODEL_VERSION = "subgraph-elo-v3"
ESPORTS_MODEL_NAME = "Subgraph-ELO Series v3"
ESPORTS_HISTORY_WINDOW = 20


@dataclass(frozen=True)
class RecommendationCandidate:
    event_key: str
    sport: str
    event_label: str
    market: str
    selection: Optional[str]
    line: Optional[float]
    model_probability: Optional[float]
    risk_adjusted_probability: Optional[float]
    probability_haircut: Optional[float]
    fair_odds: Optional[float]
    minimum_odds: Optional[float]
    model_name: str
    expected_total: Optional[float]
    evidence: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    evidence_stage: str = EVIDENCE_RESEARCH
    # Normal Wettfinder forecasts remain visible while the additional paired
    # loss/FDR release evidence is collected. A matching price must not turn
    # such a forecast into a stake recommendation.
    release_pending: bool = False

    @property
    def forecast_available(self) -> bool:
        """Whether the price-independent model produced a concrete forecast."""
        return (
            self.model_probability is not None
            and self.selection is not None
            and 0.0 < self.model_probability < 100.0
        )

    @property
    def model_ready(self) -> bool:
        """Whether the forecast also passed every price-independent model gate."""
        return self.forecast_available and not self.blockers

    @property
    def evidence_label(self) -> str:
        return EVIDENCE_LABELS.get(self.evidence_stage, "Unbekannter Modellstand")


@dataclass(frozen=True)
class PriceDecision:
    status: str
    candidate: RecommendationCandidate
    quoted_odds: Optional[float]
    metrics: Optional[ValueMetrics]
    stake_fraction: float
    stake_amount: float
    reasons: tuple[str, ...]

    @property
    def actionable(self) -> bool:
        return self.status == "BET"

    @property
    def price_passed(self) -> bool:
        return self.status in {"BET", "SHADOW", "RESEARCH"}


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _whole_non_negative(value: Any) -> Optional[int]:
    number = _finite_number(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def _utc_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def esports_history_window(
    match: dict,
    *,
    now: Optional[datetime] = None,
) -> tuple[list[dict], list[dict]]:
    """Newest completed histories available at the prediction timestamp.

    Both pre-match and live ELO paths use this function so the displayed
    history counts and the shadow-log diagnostics describe the exact rows
    consumed by the model. Pre-match rows must additionally have completed
    before the scheduled series start.
    """
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    else:
        reference = reference.astimezone(timezone.utc)

    is_prematch = str(match.get("status") or "") == "upcoming"
    scheduled_start = _utc_datetime(match.get("begin_at")) if is_prematch else None

    def completed_history(rows: Any) -> list[dict]:
        if not isinstance(rows, list):
            return []
        verified: list[tuple[datetime, dict]] = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("won"), bool):
                continue
            played_at = _utc_datetime(row.get("begin_at"))
            completed_at = _utc_datetime(row.get("end_at"))
            if (
                played_at is None
                or completed_at is None
                or not played_at < completed_at < reference
                or (
                    scheduled_start is not None
                    and completed_at >= scheduled_start
                )
            ):
                continue
            verified.append((completed_at, row))
        verified.sort(key=lambda item: item[0], reverse=True)
        return [
            row
            for _completed_at, row in verified[:ESPORTS_HISTORY_WINDOW]
        ]

    return (
        completed_history(match.get("team1_history")),
        completed_history(match.get("team2_history")),
    )


def _event_key(item: dict, *fallback_parts: Any) -> str:
    value = item.get("game_id") or item.get("match_id") or item.get("id")
    if not isinstance(value, bool) and value is not None and str(value).strip():
        return str(value).strip()
    return ":".join(str(part).strip() for part in fallback_parts if str(part).strip())


def format_probability_percent(probability: Any) -> str:
    """Format a model probability without ever printing a rounded 100 %."""
    number = _finite_number(probability)
    if number is None:
        return "k. A."
    if number >= HIGH_PROBABILITY_DISPLAY_CAP:
        return f"> {HIGH_PROBABILITY_DISPLAY_CAP:.1f} %"
    return f"{number:.1f} %"


def format_fair_odds(fair_odds: Any) -> str:
    """Format model fair odds; cap the display when they round to 1.00."""
    number = _finite_number(fair_odds)
    if number is None:
        return "k. A."
    cap_odds = 100.0 / HIGH_PROBABILITY_DISPLAY_CAP
    if number <= cap_odds:
        return f"< {cap_odds:.3f}"
    return f"{number:.3f}"


def _minimum_market_odds(risk_adjusted_probability: float) -> Optional[float]:
    return minimum_recommendation_odds(
        risk_adjusted_probability,
        minimum_expected_roi_percent=MINIMUM_EXPECTED_ROI_PERCENT,
    )


def _candidate(
    *,
    event_key: str,
    sport: str,
    event_label: str,
    market: str,
    selection: str,
    line: Optional[float],
    model_probability: float,
    probability_haircut: float,
    model_name: str,
    expected_total: Optional[float],
    evidence: Sequence[str],
    evidence_stage: str = EVIDENCE_RESEARCH,
) -> RecommendationCandidate:
    probability = min(100.0, max(0.0, float(model_probability)))
    haircut = min(probability, max(0.0, float(probability_haircut)))
    adjusted = probability - haircut
    fair_odds = 100.0 / probability if probability > 0 else None
    minimum_odds = _minimum_market_odds(adjusted)
    evidence_notes = tuple(evidence)
    if probability >= HIGH_PROBABILITY_EVIDENCE_THRESHOLD:
        evidence_notes = evidence_notes + (
            "Sehr hohe Modellwahrscheinlichkeit: Das Risiko fehlerhafter "
            "Eingangsdaten (Uhr, Spielstand, Provider) übersteigt das "
            "verbleibende Modellrisiko.",
        )
    return RecommendationCandidate(
        event_key=event_key,
        sport=sport,
        event_label=event_label,
        market=market,
        selection=selection,
        line=line,
        model_probability=round(probability, 2),
        risk_adjusted_probability=round(adjusted, 2),
        probability_haircut=round(haircut, 2),
        fair_odds=round(fair_odds, 3) if fair_odds is not None else None,
        minimum_odds=minimum_odds,
        model_name=model_name,
        expected_total=(round(expected_total, 2) if expected_total is not None else None),
        evidence=evidence_notes,
        evidence_stage=evidence_stage,
        blockers=(
            ()
            if minimum_odds is not None
            else ("Die konservative Modellwahrscheinlichkeit ist für eine Preisfreigabe zu niedrig.",)
        ),
    )


def no_bet_candidate(
    sport: str,
    item: dict,
    blockers: Sequence[str],
    *,
    market: str = "Kein freigegebener Markt",
    model_name: str = "Kein belastbares Modell",
) -> RecommendationCandidate:
    home = item.get("home_team") or item.get("player1") or item.get("team1") or "Team 1"
    away = item.get("away_team") or item.get("player2") or item.get("team2") or "Team 2"
    return RecommendationCandidate(
        event_key=_event_key(item, home, away),
        sport=sport,
        event_label=f"{home} vs {away}",
        market=market,
        selection=None,
        line=None,
        model_probability=None,
        risk_adjusted_probability=None,
        probability_haircut=None,
        fair_odds=None,
        minimum_odds=None,
        model_name=model_name,
        expected_total=None,
        evidence=(),
        blockers=tuple(blockers),
        evidence_stage=EVIDENCE_UNAVAILABLE,
    )


def _half_line(value: Any) -> Optional[float]:
    line = _finite_number(value)
    if line is None or line <= 0:
        return None
    fraction = line - math.floor(line)
    if not math.isclose(fraction, 0.5, abs_tol=1e-9):
        return None
    return line


def _clock_minutes_remaining(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    text = value.strip().upper()
    iso_match = re.fullmatch(r"PT(?:(\d+)M)?([\d.]+)S", text)
    if iso_match:
        minutes = int(iso_match.group(1) or 0)
        seconds = _finite_number(iso_match.group(2))
        if seconds is None or not 0 <= seconds < 60:
            return None
        return minutes + seconds / 60.0
    plain_match = re.fullmatch(r"(\d+):(\d{2})", text)
    if not plain_match:
        return None
    seconds = int(plain_match.group(2))
    if seconds > 59:
        return None
    return int(plain_match.group(1)) + seconds / 60.0


def _gamma_poisson_total_probability(
    *,
    observed_count: int,
    observed_exposure: float,
    remaining_exposure: float,
    prior_rate: float,
    prior_exposure: float,
    line: float,
) -> tuple[float, float]:
    """Return P(final total > line) and the posterior expected final total."""
    shape = prior_rate * prior_exposure + observed_count
    rate = prior_exposure + observed_exposure
    if shape <= 0 or rate <= 0 or remaining_exposure < 0:
        raise ValueError("Invalid Gamma-Poisson state")
    expected_remaining = shape / rate * remaining_exposure
    expected_total = observed_count + expected_remaining
    required_future = math.floor(line - observed_count) + 1
    if required_future <= 0:
        return 1.0, expected_total
    if remaining_exposure <= 0:
        return 0.0, expected_total
    if nbinom is None:
        raise RuntimeError(
            "scipy fehlt in dieser Laufzeit — Basketball-Total-Modell nicht verfügbar"
        )
    success_probability = rate / (rate + remaining_exposure)
    over_probability = float(
        nbinom.sf(required_future - 1, shape, success_probability)
    )
    return min(1.0, max(0.0, over_probability)), expected_total


def basketball_total_candidate(game: dict, market_line: Any) -> RecommendationCandidate:
    if game.get("status") == "upcoming":
        return no_bet_candidate(
            "Basketball",
            game,
            [
                "Für Basketball ist noch kein leakage-frei walk-forward-validiertes "
                "Pre-Match-Modell freigegeben. Das vorhandene Totalmodell benötigt "
                "einen verifizierten Live-Spielstand und eine Spieluhr."
            ],
            market="Pre-Match",
            model_name="Pre-Match-Modell nicht freigegeben",
        )
    league = str(game.get("league") or "").strip()
    league_key = league.casefold()
    baselines = {
        # Neutral recent-season priors. Live pace receives increasing weight as
        # elapsed time grows; the explicit haircut covers remaining model risk.
        "nba": (231.4, 48, 12.0),
        "euroleague": (163.0, 40, 10.0),
    }
    baseline = baselines.get(league_key)
    home = str(game.get("home_team") or "HOME").strip() or "HOME"
    away = str(game.get("away_team") or "AWAY").strip() or "AWAY"
    label = f"{home} vs {away}"
    line = _half_line(market_line)
    blockers = []
    if baseline is None:
        blockers.append("Liga besitzt keinen freigegebenen Gesamtpunkte-Prior.")
    if line is None:
        blockers.append("Die angebotene Gesamtlinie muss eine positive x,5-Linie sein.")
    period = _whole_non_negative(game.get("period"))
    home_score = _whole_non_negative(game.get("home_score"))
    away_score = _whole_non_negative(game.get("away_score"))
    clock = _clock_minutes_remaining(game.get("game_clock"))
    if period is None or period < 1:
        blockers.append("Die laufende Periode fehlt oder ist unplausibel.")
    if home_score is None or away_score is None:
        blockers.append("Der verifizierte Spielstand fehlt.")
    if clock is None:
        blockers.append("Die verifizierte Spieluhr fehlt.")
    if line is not None and baseline is not None:
        lower_line, upper_line = (100.5, 350.5) if league_key == "nba" else (80.5, 260.5)
        if not lower_line <= line <= upper_line:
            blockers.append("Die Gesamtlinie liegt außerhalb des plausiblen Ligabereichs.")
    if line is not None and home_score is not None and away_score is not None:
        if line <= home_score + away_score:
            blockers.append("Die Gesamtlinie liegt nicht über dem bereits erzielten Punktestand.")
    if blockers:
        return no_bet_candidate(
            "Basketball",
            game,
            blockers,
            market="Gesamtpunkte reguläre Spielzeit",
            model_name="Gamma-Poisson Pace v1",
        )

    baseline_total, regulation_minutes, prior_exposure = baseline
    period_minutes = regulation_minutes / 4.0
    if period > 4 or clock > period_minutes:
        return no_bet_candidate(
            "Basketball",
            game,
            ["Verlängerung oder unplausible Uhr: Der Markt wird nicht bewertet."],
            market="Gesamtpunkte reguläre Spielzeit",
            model_name="Gamma-Poisson Pace v1",
        )
    elapsed = (period - 1) * period_minutes + (period_minutes - clock)
    remaining = regulation_minutes - elapsed
    if elapsed < period_minutes / 2.0 or remaining <= 0:
        return no_bet_candidate(
            "Basketball",
            game,
            ["Zu wenig reguläre Live-Spielzeit für eine Wettentscheidung."],
            market="Gesamtpunkte reguläre Spielzeit",
            model_name="Gamma-Poisson Pace v1",
        )

    observed = home_score + away_score
    over_probability, expected_total = _gamma_poisson_total_probability(
        observed_count=observed,
        observed_exposure=elapsed,
        remaining_exposure=remaining,
        prior_rate=baseline_total / regulation_minutes,
        prior_exposure=prior_exposure,
        line=line,
    )
    if over_probability >= 0.5:
        selection = f"Über {line:.1f} Gesamtpunkte"
        probability = over_probability * 100.0
    else:
        selection = f"Unter {line:.1f} Gesamtpunkte"
        probability = (1.0 - over_probability) * 100.0
    haircut = 8.0 + (2.0 if elapsed < regulation_minutes / 2.0 else 0.0)
    return _candidate(
        event_key=_event_key(game, home, away),
        sport="Basketball",
        event_label=label,
        market="Gesamtpunkte reguläre Spielzeit",
        selection=selection,
        line=line,
        model_probability=probability,
        probability_haircut=haircut,
        model_name="Gamma-Poisson Pace v1",
        expected_total=expected_total,
        evidence=(
            f"Live-Stand {home_score}:{away_score} nach {elapsed:.1f} von {regulation_minutes} Minuten.",
            f"Liga-Prior {baseline_total:.1f} Punkte; posteriorer Erwartungswert {expected_total:.1f}.",
            f"Robustheitsabschlag {haircut:.1f} Prozentpunkte für Pace-, Lineup- und Possession-Risiko.",
            "Lineup- und Verletzungsdaten stehen in diesem Live-Feed nicht zur "
            "Verfügung und wurden nicht spielerspezifisch modelliert.",
        ),
    )


def nhl_total_candidate(game: dict, market_line: Any) -> RecommendationCandidate:
    if game.get("status") == "upcoming":
        return no_bet_candidate(
            "Eishockey",
            game,
            [
                "Für NHL ist noch kein goalie- und lineup-sensitives, leakage-frei "
                "walk-forward-validiertes Pre-Match-Modell freigegeben. Das vorhandene "
                "Totalmodell benötigt einen verifizierten Live-Spielstand."
            ],
            market="Pre-Match",
            model_name="Pre-Match-Modell nicht freigegeben",
        )
    home = str(game.get("home_team") or "HOME").strip() or "HOME"
    away = str(game.get("away_team") or "AWAY").strip() or "AWAY"
    line = _half_line(market_line)
    blockers = []
    if line is None:
        blockers.append("Die angebotene Torlinie muss eine positive x,5-Linie sein.")
    period = _whole_non_negative(game.get("period"))
    home_score = _whole_non_negative(game.get("home_score"))
    away_score = _whole_non_negative(game.get("away_score"))
    clock = _clock_minutes_remaining(game.get("game_clock"))
    if period is None or period < 1:
        blockers.append("Die laufende Periode fehlt oder ist unplausibel.")
    if home_score is None or away_score is None:
        blockers.append("Der verifizierte Spielstand fehlt.")
    if clock is None:
        blockers.append("Die verifizierte Spieluhr fehlt.")
    if line is not None and not 0.5 <= line <= 15.5:
        blockers.append("Die Torlinie liegt außerhalb des plausiblen NHL-Bereichs.")
    if line is not None and home_score is not None and away_score is not None:
        if line <= home_score + away_score:
            blockers.append("Die Torlinie liegt nicht über dem bereits erzielten Spielstand.")
    if blockers:
        return no_bet_candidate(
            "Eishockey",
            game,
            blockers,
            market="Gesamttore reguläre Spielzeit",
            model_name="Gamma-Poisson Goals v1",
        )
    if period > 3 or clock > 20:
        return no_bet_candidate(
            "Eishockey",
            game,
            ["Verlängerung oder unplausible Uhr: Der Markt wird nicht bewertet."],
            market="Gesamttore reguläre Spielzeit",
            model_name="Gamma-Poisson Goals v1",
        )
    elapsed = (period - 1) * 20.0 + (20.0 - clock)
    remaining = 60.0 - elapsed
    if elapsed < 10.0 or remaining <= 0:
        return no_bet_candidate(
            "Eishockey",
            game,
            ["Zu wenig reguläre Live-Spielzeit für eine Wettentscheidung."],
            market="Gesamttore reguläre Spielzeit",
            model_name="Gamma-Poisson Goals v1",
        )

    observed = home_score + away_score
    baseline_total = 6.2
    over_probability, expected_total = _gamma_poisson_total_probability(
        observed_count=observed,
        observed_exposure=elapsed,
        remaining_exposure=remaining,
        prior_rate=baseline_total / 60.0,
        prior_exposure=120.0,
        line=line,
    )
    if over_probability >= 0.5:
        selection = f"Über {line:.1f} Tore"
        probability = over_probability * 100.0
    else:
        selection = f"Unter {line:.1f} Tore"
        probability = (1.0 - over_probability) * 100.0
    haircut = 10.0 + (3.0 if period == 3 and clock <= 3.0 else 0.0)
    return _candidate(
        event_key=_event_key(game, home, away),
        sport="Eishockey",
        event_label=f"{away} @ {home}",
        market="Gesamttore reguläre Spielzeit",
        selection=selection,
        line=line,
        model_probability=probability,
        probability_haircut=haircut,
        model_name="Gamma-Poisson Goals v1",
        expected_total=expected_total,
        evidence=(
            f"Live-Stand {away_score}:{home_score} nach {elapsed:.1f} von 60 Minuten.",
            f"Liga-Prior {baseline_total:.1f} Tore; posteriorer Erwartungswert {expected_total:.2f}.",
            f"Robustheitsabschlag {haircut:.1f} Prozentpunkte für Goalie-, Special-Team- und Empty-Net-Risiko.",
            "Starting-Goalie-, Lineup- und Verletzungsdaten stehen in diesem "
            "Live-Feed nicht zur Verfügung und wurden nicht einzeln modelliert.",
        ),
    )


def _series_win_probability(
    map_probability: float,
    selected_maps: int,
    opponent_maps: int,
    maps_to_win: int,
) -> float:
    """Exact binomial series probability under i.i.d. maps.

    Known limitation (audit E2): real series are negatively correlated —
    map veto gives the previous-map loser the next map/side pick, so a
    1:0 favourite is slightly LESS secure than i.i.d. says (roughly 2-4pp
    from 1:0 in a Bo3).  Pre-match (0:0) the inversion from the Elo
    series probability is exact and unaffected; the simplification only
    touches score-conditioned live states, which the shadow no longer
    logs.  The feed carries no veto data, so there is nothing to fit a
    correlated model to.
    """
    memo: dict[tuple[int, int], float] = {}

    def solve(selected_score: int, opponent_score: int) -> float:
        if selected_score >= maps_to_win:
            return 1.0
        if opponent_score >= maps_to_win:
            return 0.0
        key = (selected_score, opponent_score)
        if key not in memo:
            memo[key] = (
                map_probability * solve(selected_score + 1, opponent_score)
                + (1.0 - map_probability) * solve(selected_score, opponent_score + 1)
            )
        return memo[key]

    return solve(selected_maps, opponent_maps)


def _map_probability_from_series_probability(
    series_probability: float,
    maps_to_win: int,
) -> float:
    low = 0.0
    high = 1.0
    for _ in range(70):
        middle = (low + high) / 2.0
        value = _series_win_probability(middle, 0, 0, maps_to_win)
        if value < series_probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def esports_match_winner_candidate(
    match: dict,
    *,
    now: Optional[datetime] = None,
) -> RecommendationCandidate:
    team1 = str(match.get("team1") or "").strip()
    team2 = str(match.get("team2") or "").strip()
    stats1 = match.get("team1_stats")
    stats2 = match.get("team2_stats")
    blockers = []
    is_prematch = str(match.get("status") or "") == "upcoming"
    scheduled_start = _utc_datetime(match.get("begin_at")) if is_prematch else None
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    else:
        reference = reference.astimezone(timezone.utc)
    if is_prematch:
        if scheduled_start is None:
            blockers.append("Die verifizierte Pre-Match-Startzeit fehlt.")
        elif scheduled_start <= reference:
            blockers.append("Die Serie hat laut verifizierter Startzeit bereits begonnen.")
    if not team1 or not team2 or team1.casefold() == team2.casefold():
        blockers.append("Die Teams sind nicht eindeutig zugeordnet.")
    if (
        not is_prematch
        and (not isinstance(stats1, dict) or not isinstance(stats2, dict))
    ):
        blockers.append("Historische Teamdaten fehlen.")
        stats1 = {}
        stats2 = {}

    reported_matches1 = _whole_non_negative(stats1.get("matches"))
    reported_matches2 = _whole_non_negative(stats2.get("matches"))
    reported_wins1 = _whole_non_negative(stats1.get("wins"))
    reported_wins2 = _whole_non_negative(stats2.get("wins"))
    score1 = _whole_non_negative(match.get("team1_score"))
    score2 = _whole_non_negative(match.get("team2_score"))
    series_type = _whole_non_negative(match.get("series_type", 3))
    if not is_prematch:
        if None in (
            reported_matches1,
            reported_matches2,
            reported_wins1,
            reported_wins2,
        ):
            blockers.append("Gültige Sieg-/Matchzahlen fehlen.")
        elif (
            reported_wins1 > reported_matches1
            or reported_wins2 > reported_matches2
        ):
            blockers.append("Historische Sieg-/Matchzahlen widersprechen sich.")
    if score1 is None or score2 is None:
        blockers.append("Der verifizierte Serienstand fehlt.")
    elif is_prematch and (score1 != 0 or score2 != 0):
        blockers.append("Eine Pre-Match-Serie muss einen verifizierten Stand von 0:0 haben.")
    if series_type is None or series_type < 1 or series_type % 2 == 0:
        blockers.append("Das Best-of-Format fehlt oder ist unplausibel.")
    if not isinstance(match.get("team1_history"), list) or not isinstance(
        match.get("team2_history"), list
    ):
        blockers.append("Historische Matchlisten fehlen.")
    history1, history2 = esports_history_window(match, now=reference)
    matches1 = len(history1)
    matches2 = len(history2)
    wins1 = sum(1 for row in history1 if row["won"])
    wins2 = sum(1 for row in history2 if row["won"])
    if len(history1) < ESPORTS_HISTORY_WINDOW or len(history2) < ESPORTS_HISTORY_WINDOW:
        if is_prematch:
            blockers.append(
                "Mindestens 20 Matches je Team mit verifiziertem Abschlusszeitpunkt "
                "vor dem Prüfzeitpunkt und vor Serienbeginn sind erforderlich."
            )
        else:
            blockers.append(
                "Mindestens 20 Matches je Team mit verifiziertem Abschlusszeitpunkt "
                "vor dem Prüfzeitpunkt sind erforderlich."
            )
    team1_id = _whole_non_negative(match.get("team1_id"))
    team2_id = _whole_non_negative(match.get("team2_id"))
    if team1_id is None or team2_id is None or team1_id == team2_id:
        blockers.append("Team-IDs für die gegneradjustierte Stärkebewertung fehlen.")
    if blockers:
        return no_bet_candidate(
            "E-Sport",
            match,
            blockers,
            market="Match-Sieger",
            model_name=ESPORTS_MODEL_NAME,
        )

    maps_to_win = series_type // 2 + 1
    if score1 >= maps_to_win or score2 >= maps_to_win:
        return no_bet_candidate(
            "E-Sport",
            match,
            ["Die Serie ist bereits beendet oder der Serienstand ist unplausibel."],
            market="Match-Sieger",
            model_name=ESPORTS_MODEL_NAME,
        )

    elo1, elo2, subgraph_size = subgraph_ratings(
        history1, history2, team1_id, team2_id
    )
    team1_series_probability = expected_score(elo1, elo2)
    team1_map_probability = _map_probability_from_series_probability(
        team1_series_probability,
        maps_to_win,
    )
    team1_live_probability = _series_win_probability(
        team1_map_probability,
        score1,
        score2,
        maps_to_win,
    )

    if team1_live_probability >= 0.5:
        selection = team1
        point_probability = team1_live_probability
        fav_elo, opp_elo = elo1, elo2
        selected_score, opponent_score = score1, score2
    else:
        selection = team2
        point_probability = 1.0 - team1_live_probability
        fav_elo, opp_elo = elo2, elo1
        selected_score, opponent_score = score2, score1

    # Conservative line: the bounded subgraph carries estimation error,
    # priced as a flat ELO margin against the favourite.
    conservative_series_probability = expected_score(
        fav_elo - ELO_UNCERTAINTY_MARGIN,
        opp_elo,
    )
    conservative_map_probability = _map_probability_from_series_probability(
        conservative_series_probability,
        maps_to_win,
    )
    conservative_live_probability = _series_win_probability(
        conservative_map_probability,
        selected_score,
        opponent_score,
        maps_to_win,
    )
    # Five additional percentage points cover roster and map-veto effects
    # that public match histories do not identify.
    adjusted_probability = max(
        0.0,
        min(point_probability, conservative_live_probability) * 100.0 - 5.0,
    )
    probability_percent = point_probability * 100.0
    haircut = probability_percent - adjusted_probability
    series_evidence = (
        f"Pre-Match (Serie noch nicht gestartet), Best-of-{series_type}."
        if is_prematch
        else f"Serienstand {score1}:{score2}, Best-of-{series_type}."
    )
    return _candidate(
        event_key=_event_key(match, team1, team2),
        sport="E-Sport",
        event_label=f"{team1} vs {team2}",
        market="Match-Sieger",
        selection=selection,
        line=None,
        model_probability=probability_percent,
        probability_haircut=haircut,
        model_name=ESPORTS_MODEL_NAME,
        expected_total=None,
        evidence=(
            series_evidence,
            f"ELO {elo1:.0f} vs {elo2:.0f} aus {subgraph_size} Subgraph-Spielen (gegneradjustiert).",
            f"Historie: {team1} {wins1}/{matches1}, {team2} {wins2}/{matches2}.",
            f"Konservativ: 150 ELO-Punkte Unsicherheitsmarge plus 5,0 Prozentpunkte Modellabschlag.",
            "Rosterwechsel und Map-Veto stehen im Feed nicht verifiziert zur "
            "Verfügung und wurden nicht einzeln modelliert.",
        ),
        evidence_stage=EVIDENCE_SHADOW,
    )


def build_candidate(
    sport: str,
    item: dict,
    *,
    market_line: Any = None,
) -> RecommendationCandidate:
    if not isinstance(item, dict):
        return no_bet_candidate(sport, {}, ["Das Ereignisformat ist ungültig."])
    if sport == "Basketball":
        return basketball_total_candidate(item, market_line)
    if sport == "Eishockey":
        return nhl_total_candidate(item, market_line)
    if sport == "E-Sport":
        return esports_match_winner_candidate(item)
    if sport == "Tennis":
        return no_bet_candidate(
            sport,
            item,
            [
                "Dieser generische Ereignis-Scan ist nicht eindeutig mit dem "
                "persistierten Modellstate der separaten Tennis-Prematch-Pipeline "
                "verknüpft. Daher wird hier keine zweite oder erfundene "
                "Wahrscheinlichkeit erzeugt."
            ],
            market="Match-Sieger",
        )
    if sport == "Cricket":
        return no_bet_candidate(
            sport,
            item,
            [
                "Ein chronologisch validierter historischer Cricket-State mit "
                "Format-, Venue-, Batter-, Bowler-, Lineup- und Toss-Daten fehlt. "
                "Der Terminfeed allein reicht nicht für eine Prognose."
            ],
            market="Innings-Gesamtläufe",
        )
    return no_bet_candidate(sport, item, ["Sportart wird nicht unterstützt."])


def evaluate_candidate_price(
    candidate: RecommendationCandidate,
    quoted_odds: Any,
    *,
    bankroll: Any,
    quote_confirmed: bool = False,
) -> PriceDecision:
    if candidate.blockers:
        return PriceDecision(
            status="NO_BET",
            candidate=candidate,
            quoted_odds=None,
            metrics=None,
            stake_fraction=0.0,
            stake_amount=0.0,
            reasons=candidate.blockers,
        )
    balance = _finite_number(bankroll)
    if balance is None or balance <= 0:
        return PriceDecision(
            status="NO_BET",
            candidate=candidate,
            quoted_odds=None,
            metrics=None,
            stake_fraction=0.0,
            stake_amount=0.0,
            reasons=("Das Guthaben muss positiv und endlich sein.",),
        )
    if quoted_odds is None or (isinstance(quoted_odds, str) and not quoted_odds.strip()):
        return PriceDecision(
            status="PRICE_REQUIRED",
            candidate=candidate,
            quoted_odds=None,
            metrics=None,
            stake_fraction=0.0,
            stake_amount=0.0,
            reasons=("Aktuelle Dezimalquote eingeben.",),
        )
    if quote_confirmed is not True:
        return PriceDecision(
            status="PRICE_REQUIRED",
            candidate=candidate,
            quoted_odds=None,
            metrics=None,
            stake_fraction=0.0,
            stake_amount=0.0,
            reasons=("Marktlinie und Quote unmittelbar vor der Entscheidung bestätigen.",),
        )
    try:
        metrics = evaluate_market_price(
            candidate.model_probability,
            quoted_odds,
            probability_haircut=candidate.probability_haircut,
            kelly_fraction=DEFAULT_KELLY_FRACTION,
            kelly_cap=MAXIMUM_KELLY_FRACTION,
        )
    except BettingMathError as exc:
        return PriceDecision(
            status="NO_BET",
            candidate=candidate,
            quoted_odds=None,
            metrics=None,
            stake_fraction=0.0,
            stake_amount=0.0,
            reasons=(str(exc),),
        )

    reasons = []
    if (
        metrics.risk_adjusted_expected_roi + 1e-9
        < MINIMUM_EXPECTED_ROI_PERCENT
    ):
        reasons.append(
            f"Risiko-EV {metrics.risk_adjusted_expected_roi:.1f} % liegt unter {MINIMUM_EXPECTED_ROI_PERCENT:.1f} %."
        )
    effective_minimum = max(
        candidate.minimum_odds or math.inf,
        MINIMUM_RECOMMENDED_DECIMAL_ODDS,
    )
    if metrics.market_odds + 1e-9 < effective_minimum:
        reasons.append(
            f"Quote {metrics.market_odds:.2f} liegt unter der Value-Grenze "
            f"{effective_minimum:.2f}."
        )
    if metrics.kelly_fraction <= 0:
        reasons.append("Das risikoadjustierte Kelly-Ergebnis ist nicht positiv.")

    price_passed = not reasons
    released = candidate.evidence_stage == EVIDENCE_RELEASED
    shadow = candidate.evidence_stage == EVIDENCE_SHADOW
    status = (
        "BET"
        if price_passed and released
        else "SHADOW"
        if price_passed and shadow
        else "RESEARCH"
        if price_passed
        else "NO_BET"
    )
    stake_fraction = metrics.kelly_fraction if status == "BET" else 0.0
    return PriceDecision(
        status=status,
        candidate=candidate,
        quoted_odds=metrics.market_odds,
        metrics=metrics,
        stake_fraction=stake_fraction,
        stake_amount=round(balance * stake_fraction, 2),
        reasons=(
            (
                "Alle Modell-, Evidenz-, Preis-, Risiko-EV- und "
                "Einsatz-Gates bestanden.",
            )
            if status == "BET"
            else (
                "Modell- und Preisprüfung bestanden; die unabhängige "
                "Shadow-Evidenz reicht noch nicht für Echtgeld.",
            )
            if status == "SHADOW"
            else (
                "Der Preis wäre rechnerisch ausreichend, aber dieses Modell "
                "ist noch im Forschungsstadium.",
            )
            if price_passed
            else tuple(reasons)
        ),
    )
