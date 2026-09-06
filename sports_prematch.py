"""Causal, sport-specific research models for the three result-feed sports.

These are research estimates, never independently calibrated betting signals.
Training uses observed completed results, and the optional prequential report
uses only results actually observed before each evaluated kickoff. Importing
an old archive today therefore does not manufacture a historical backtest.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
from typing import Iterable, Mapping, Optional
import unicodedata

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, ndtr
from scipy.stats import skellam


MODEL_VERSION = "sports-prematch-research-v1"
MIN_TRAINING_GAMES = 40
MIN_TEAM_GAMES = 8
MIN_OVERTIME_GAMES = 8
MAX_HISTORY_GAMES = 1200
MAX_TEAMS = 64
MAX_EVALUATION_GAMES = 24
RIDGE_PSEUDO_GAMES = 5.0

_SCOPES = {
    "basketball": "including_overtime",
    "ice_hockey": "including_overtime_shootout",
    "cricket": "match_winner",
}
_MARKETS = {
    "basketball": "match_winner_including_ot",
    "ice_hockey": "match_winner_including_ot",
    "cricket": "match_winner",
}


@dataclass(frozen=True)
class PrequentialEvaluation:
    count: int = 0
    brier_score: Optional[float] = None
    baseline_brier_score: Optional[float] = None
    log_loss: Optional[float] = None
    method: str = "results-observed-before-evaluated-kickoff"


@dataclass(frozen=True)
class PrematchPrediction:
    sport: str
    p_home: Optional[float]
    p_away: Optional[float]
    training_games: int
    home_games: int
    away_games: int
    evaluation: PrequentialEvaluation
    factors: tuple[str, ...]
    missing: tuple[str, ...]
    limitations: tuple[str, ...]
    input_hash: str
    latest_result_observed_at: Optional[datetime]
    market_contract: str
    model_version: str = MODEL_VERSION
    evidence_stage: str = "RESEARCH"
    risk_probability: Optional[float] = None
    p_home_regulation: Optional[float] = None
    p_draw_regulation: Optional[float] = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if self.latest_result_observed_at is not None:
            payload["latest_result_observed_at"] = self.latest_result_observed_at.isoformat()
        return payload


@dataclass(frozen=True)
class _Match:
    event_id: str
    start: datetime
    observed: datetime
    home: str
    away: str
    winner_home: int
    home_score: Optional[int]
    away_score: Optional[int]
    neutral: bool
    extra_time: bool


@dataclass(frozen=True)
class _Identity:
    provider: str
    competition: str
    variant: str
    event_id: str
    start: datetime
    home: str
    away: str
    neutral: bool


@dataclass(frozen=True)
class _Fit:
    sport: str
    teams: tuple[str, ...]
    coefficients: tuple[float, ...]
    residual_scale: Optional[float] = None
    overtime_home_rate: Optional[float] = None
    overtime_games: int = 0


def _text(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def _time(value: object) -> Optional[datetime]:
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None
    return result.astimezone(timezone.utc) if result.tzinfo is not None else None


def _team(row: Mapping, side: str) -> str:
    cricket_side = "team1" if side == "home" else "team2"
    team_id = _text(row.get(f"{side}_team_id") or row.get(f"{cricket_side}_id"))
    if team_id:
        return "id:" + team_id
    name = _text(row.get(f"{side}_team") or row.get(cricket_side))
    return "name:" + name if name else ""


def _competition(row: Mapping) -> str:
    return _text(row.get("competition_id") or row.get("league_id")) or _text(
        row.get("competition") or row.get("league") or row.get("tournament")
    )


def _variant(sport: str, row: Mapping) -> str:
    if sport == "cricket":
        value = _text(row.get("format") or row.get("match_format"))
        return {"t20i": "t20", "twenty20": "t20", "one day": "odi"}.get(value, value)
    if sport == "ice_hockey":
        return _text(row.get("game_type"))
    return "including_overtime"


def _score(value: object) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0 or value != int(value):
        return None
    return int(value)


def _identity(sport: str, event: Mapping, as_of: datetime) -> tuple[Optional[_Identity], tuple[str, ...]]:
    missing = []
    provider = _text(event.get("provider") or event.get("source"))
    competition = _competition(event)
    event_id = _text(event.get("provider_event_id") or event.get("event_id")
                     or event.get("game_id") or event.get("match_id") or event.get("id"))
    start = _time(event.get("starts_at") or event.get("start_time") or event.get("scheduled_at"))
    home, away = _team(event, "home"), _team(event, "away")
    variant = _variant(sport, event)
    if not provider or not competition or not event_id or not home or not away or home == away:
        missing.append("Eindeutige Anbieter-, Wettbewerbs-, Event- und Teamidentität erforderlich.")
    if start is None or start <= as_of:
        missing.append("Ein bestätigter zukünftiger Anstoß mit Zeitzone ist erforderlich.")
    status = _text(event.get("status"))
    if status not in {"upcoming", "scheduled", "not_started", "not started", "ns", "fut", "pre"}:
        missing.append("Das Event ist nicht als bevorstehend bestätigt.")
    if sport == "cricket" and variant not in {"t20", "odi"}:
        missing.append("Test- und unbekannte Cricket-Formate benötigen ein eigenes Remis-/Formatmodell.")
    if sport == "ice_hockey" and variant not in {"1", "2", "3"}:
        missing.append("NHL-Spieltyp (Vorbereitung, reguläre Saison oder Playoffs) fehlt.")
    if missing:
        return None, tuple(missing)
    return _Identity(provider, competition, variant, event_id, start, home, away,
                     event.get("neutral_site") is True), ()


def _normalise_history(sport: str, identity: _Identity, history: Iterable[Mapping], as_of: datetime) -> tuple[_Match, ...]:
    # First select the latest known revision, then validate its result. An
    # invalid later revision must not resurrect an earlier completed score.
    revisions: dict[str, tuple[datetime, list[Mapping]]] = {}
    cutoff = min(as_of, identity.start)
    for row in history:
        if not isinstance(row, Mapping):
            continue
        provider = _text(row.get("provider") or row.get("source"))
        observed = _time(row.get("result_observed_at") or row.get("observed_at"))
        event_id = _text(row.get("provider_event_id") or row.get("event_id") or row.get("id"))
        if (
            provider != identity.provider
            or observed is None or observed >= cutoff or not event_id
            or event_id == identity.event_id
        ):
            continue
        previous = revisions.get(event_id)
        if previous is None or observed > previous[0]:
            revisions[event_id] = (observed, [row])
        elif observed == previous[0]:
            previous[1].append(row)
    result: list[_Match] = []
    for event_id, (observed, rows) in revisions.items():
        candidates = []
        for row in rows:
            # Scope belongs to the selected revision. Filtering it earlier
            # would silently reuse a stale score after a provider correction.
            if (
                _competition(row) != identity.competition
                or _variant(sport, row) != identity.variant
                or (_text(row.get("sport")) and _text(row.get("sport")) != sport)
                or _text(row.get("status")) not in {"completed", "final", "finished", "closed", "ended"}
            ):
                candidates.append(None)
                continue
            start = _time(row.get("start_time") or row.get("starts_at"))
            completed = _time(row.get("completed_at")) if row.get("completed_at") else None
            home, away = _team(row, "home"), _team(row, "away")
            winner = _text(row.get("winner_side"))
            home_score = _score(row.get("home_score_final", row.get("home_score")))
            away_score = _score(row.get("away_score_final", row.get("away_score")))
            invalid = (
                start is None or start >= observed or not home or not away or home == away
                or winner not in {"home", "away"}
                or _text(row.get("result_scope")) != _SCOPES[sport]
                or (row.get("completed_at") is not None and (
                    completed is None or not start <= completed <= observed
                ))
            )
            extra_time = False
            if sport in {"basketball", "ice_hockey"}:
                invalid = invalid or (
                    home_score is None or away_score is None or home_score == away_score
                    or (home_score is not None and away_score is not None and
                        (home_score > away_score) != (winner == "home"))
                )
            if sport == "ice_hockey":
                period = _text(row.get("last_period_type"))
                if period not in {"reg", "ot", "so"}:
                    invalid = True
                elif period != "reg" and home_score is not None and away_score is not None:
                    # NHL final OT/SO scores add exactly one winning goal to
                    # a regulation tie; never model that award as a 60m goal.
                    extra_time = True
                    if abs(home_score - away_score) != 1:
                        invalid = True
                    elif winner == "home":
                        home_score -= 1
                    else:
                        away_score -= 1
                    if home_score != away_score:
                        invalid = True
            if invalid:
                candidates.append(None)
            else:
                candidates.append(_Match(event_id, start, observed, home, away,
                    int(winner == "home"), home_score, away_score,
                    row.get("neutral_site") is True, extra_time))
        unique = set(candidates)
        if len(unique) == 1 and None not in unique:
            result.append(unique.pop())
    # Different IDs for the identical scheduled matchup are ambiguous aliases,
    # not independent observations. Keep only one if their payloads agree.
    natural: dict[tuple, list[_Match]] = {}
    for match in result:
        natural.setdefault((match.start, match.home, match.away), []).append(match)
    deduped = []
    for matches in natural.values():
        content = {(m.winner_home, m.home_score, m.away_score, m.neutral, m.extra_time) for m in matches}
        if len(content) == 1:
            deduped.append(min(matches, key=lambda m: (m.observed, m.event_id)))
    return tuple(sorted(deduped, key=lambda m: (m.start, m.event_id))[-MAX_HISTORY_GAMES:])


def _connected(matches: tuple[_Match, ...], home: str, away: str) -> bool:
    neighbours: dict[str, set[str]] = {}
    for match in matches:
        neighbours.setdefault(match.home, set()).add(match.away)
        neighbours.setdefault(match.away, set()).add(match.home)
    seen, todo = set(), [home]
    while todo:
        team = todo.pop()
        if team in seen:
            continue
        seen.add(team)
        todo.extend(neighbours.get(team, set()) - seen)
    return away in seen


@lru_cache(maxsize=64)
def _fit(sport: str, matches: tuple[_Match, ...]) -> Optional[_Fit]:
    teams = tuple(sorted({team for m in matches for team in (m.home, m.away)}))
    if len(matches) < MIN_TRAINING_GAMES or len(teams) > MAX_TEAMS:
        return None
    positions = {team: i for i, team in enumerate(teams)}
    n, t = len(matches), len(teams)
    if sport in {"basketball", "cricket"}:
        width = t + int(sport == "basketball")
        x = np.zeros((n, width))
        for i, match in enumerate(matches):
            x[i, positions[match.home]] = 1.0
            x[i, positions[match.away]] = -1.0
            if sport == "basketball":
                x[i, -1] = float(not match.neutral)
        if sport == "basketball":
            y = np.array([m.home_score - m.away_score for m in matches], dtype=float)
            penalty = np.eye(width) * RIDGE_PSEUDO_GAMES
            penalty[-1, -1] = 1e-8
            gram = x.T @ x
            try:
                coefficients = np.linalg.solve(gram + penalty, x.T @ y)
                effective_parameters = float(np.trace(np.linalg.solve(gram + penalty, gram)))
            except np.linalg.LinAlgError:
                return None
            residuals = y - x @ coefficients
            variance_prior = max(float(np.var(y, ddof=1)), 1.0)
            variance = (float(residuals @ residuals) + RIDGE_PSEUDO_GAMES * variance_prior) / (
                max(1.0, n - effective_parameters) + RIDGE_PSEUDO_GAMES
            )
            return _Fit(sport, teams, tuple(coefficients), math.sqrt(variance))
        y = np.array([m.winner_home for m in matches], dtype=float)
        def objective(coefficients):
            eta = x @ coefficients
            loss = np.logaddexp(0.0, eta).sum() - y @ eta
            loss += 0.5 * RIDGE_PSEUDO_GAMES * (coefficients @ coefficients)
            gradient = x.T @ (expit(eta) - y) + RIDGE_PSEUDO_GAMES * coefficients
            return loss, gradient
        fitted = minimize(objective, np.zeros(width), jac=True, method="L-BFGS-B",
                          options={"maxiter": 80, "ftol": 1e-10})
        return _Fit(sport, teams, tuple(fitted.x)) if fitted.success else None
    # Poisson attack/defence model over regulation goals, with a fitted home
    # designation effect and regularised team strengths.
    x = np.zeros((2 * n, 2 * t + 2))
    y = np.zeros(2 * n)
    for i, match in enumerate(matches):
        for offset, scoring, conceding, goals, home_sign in (
            (0, match.home, match.away, match.home_score, 0.5),
            (1, match.away, match.home, match.away_score, -0.5),
        ):
            j = 2 * i + offset
            x[j, positions[scoring]] = 1.0
            x[j, t + positions[conceding]] = 1.0
            x[j, -2] = 1.0
            x[j, -1] = home_sign if not match.neutral else 0.0
            y[j] = goals
    penalty = np.full(2 * t + 2, RIDGE_PSEUDO_GAMES)
    penalty[-2:] = 0.0
    initial = np.zeros(2 * t + 2)
    initial[-2] = math.log(max(float(y.mean()), 0.01))
    def objective(coefficients):
        eta = x @ coefficients
        mu = np.exp(eta)
        loss = float((mu - y * eta).sum() + 0.5 * (penalty * coefficients) @ coefficients)
        gradient = x.T @ (mu - y) + penalty * coefficients
        return loss, gradient
    fitted = minimize(objective, initial, jac=True, method="L-BFGS-B",
        bounds=[(-4.0, 4.0)] * (2 * t) + [(-5.0, 5.0), (-3.0, 3.0)],
        options={"maxiter": 100, "ftol": 1e-9})
    if not fitted.success or not np.isfinite(fitted.x).all():
        return None
    overtime = [m for m in matches if m.extra_time and not m.neutral]
    rate = ((sum(m.winner_home for m in overtime) + 0.5) / (len(overtime) + 1.0)
            if len(overtime) >= MIN_OVERTIME_GAMES else None)
    return _Fit(sport, teams, tuple(fitted.x), overtime_home_rate=rate, overtime_games=len(overtime))


def _predict(fitted: _Fit, home: str, away: str, neutral: bool) -> Optional[tuple[float, dict[str, float]]]:
    if home not in fitted.teams or away not in fitted.teams:
        return None
    h, a = fitted.teams.index(home), fitted.teams.index(away)
    coefficients = fitted.coefficients
    if fitted.sport == "basketball":
        margin = coefficients[h] - coefficients[a] + (0.0 if neutral else coefficients[-1])
        probability = float(ndtr(margin / fitted.residual_scale))
        return probability, {"expected_margin": margin, "residual_scale": fitted.residual_scale}
    if fitted.sport == "cricket":
        difference = coefficients[h] - coefficients[a]
        return float(expit(difference)), {"strength_difference": difference}
    if fitted.overtime_home_rate is None or neutral:
        return None
    t = len(fitted.teams)
    home_effect = 0.0 if neutral else coefficients[-1] / 2.0
    lambda_home = math.exp(coefficients[-2] + coefficients[h] + coefficients[t + a] + home_effect)
    lambda_away = math.exp(coefficients[-2] + coefficients[a] + coefficients[t + h] - home_effect)
    p_home_regulation = float(skellam.sf(0, lambda_home, lambda_away))
    p_draw_regulation = float(skellam.pmf(0, lambda_home, lambda_away))
    probability = p_home_regulation + p_draw_regulation * fitted.overtime_home_rate
    return probability, {"expected_home_goals": lambda_home, "expected_away_goals": lambda_away,
        "p_home_regulation": p_home_regulation, "p_draw_regulation": p_draw_regulation,
        "overtime_home_rate": fitted.overtime_home_rate}


def _enough_for_event(matches: tuple[_Match, ...], home: str, away: str) -> bool:
    counts = Counter(team for m in matches for team in (m.home, m.away))
    return (len(matches) >= MIN_TRAINING_GAMES and counts[home] >= MIN_TEAM_GAMES
            and counts[away] >= MIN_TEAM_GAMES and _connected(matches, home, away))


@lru_cache(maxsize=16)
def _evaluate(sport: str, matches: tuple[_Match, ...]) -> PrequentialEvaluation:
    points: list[tuple[_Match, tuple[_Match, ...]]] = []
    for target in matches:
        prior = tuple(m for m in matches if m.observed < target.start and m.start < target.start)
        if _enough_for_event(prior, target.home, target.away):
            points.append((target, prior))
    # A fixed bounded suffix is descriptive evidence, never parameter tuning
    # or a model-release gate. Every point still has a strictly prior fit.
    losses, baselines, log_losses = [], [], []
    for target, prior in points[-MAX_EVALUATION_GAMES:]:
        fitted = _fit(sport, prior)
        prediction = _predict(fitted, target.home, target.away, target.neutral) if fitted else None
        if prediction is None:
            continue
        p = min(1.0 - 1e-12, max(1e-12, prediction[0]))
        y = target.winner_home
        baseline = (sum(m.winner_home for m in prior) + 0.5) / (len(prior) + 1.0)
        losses.append((p - y) ** 2)
        baselines.append((baseline - y) ** 2)
        log_losses.append(-math.log(p if y else 1.0 - p))
    if not losses:
        return PrequentialEvaluation()
    return PrequentialEvaluation(len(losses), float(np.mean(losses)),
                                float(np.mean(baselines)), float(np.mean(log_losses)))


def predict_prematch(
    sport: str,
    event: Mapping[str, object],
    history: Iterable[Mapping[str, object]],
    as_of: datetime,
) -> PrematchPrediction:
    """Estimate a research-only full-match winner from strictly known results.

    ``as_of`` is the actual model decision time, not an old event-cache time.
    Repeated events from the same source/competition share bounded cached fits.
    No quote, injury, weather or fabricated historical observation enters here.
    """
    if sport not in _SCOPES:
        raise ValueError("supported sports: basketball, ice_hockey, cricket")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if not isinstance(event, Mapping):
        raise ValueError("event must be a mapping")
    as_of = as_of.astimezone(timezone.utc)
    identity, identity_missing = _identity(sport, event, as_of)
    matches = _normalise_history(sport, identity, history, as_of) if identity else ()
    counts = Counter(team for m in matches for team in (m.home, m.away))
    home_games = counts[identity.home] if identity else 0
    away_games = counts[identity.away] if identity else 0
    missing = list(identity_missing)
    if identity and len(matches) < MIN_TRAINING_GAMES:
        missing.append(f"Nur {len(matches)} passende abgeschlossene Spiele; mindestens {MIN_TRAINING_GAMES} benötigt.")
    if identity and (home_games < MIN_TEAM_GAMES or away_games < MIN_TEAM_GAMES):
        missing.append(f"Teamhistorie {home_games}/{away_games}; mindestens {MIN_TEAM_GAMES} pro Team benötigt.")
    if identity and not missing and not _connected(matches, identity.home, identity.away):
        missing.append("Die Gegnerhistorien sind nicht über gemeinsame Wettbewerbsgegner verbunden.")
    fitted = _fit(sport, matches) if not missing else None
    if not missing and fitted is None:
        missing.append("Das begrenzte sportspezifische Modell konnte nicht stabil angepasst werden.")
    prediction = _predict(fitted, identity.home, identity.away, identity.neutral) if fitted else None
    if fitted and prediction is None:
        missing.append("Für den vollständigen NHL-Siegermarkt fehlen passende Verlängerungs-/Shootout-Beobachtungen.")
    probability, values = prediction if prediction else (None, {})
    if probability is not None and (not math.isfinite(probability) or not 0.0 < probability < 1.0):
        probability = None
        missing.append("Keine endliche, nicht-degenerierte Modellwahrscheinlichkeit verfügbar.")
    evaluation = _evaluate(sport, matches) if fitted else PrequentialEvaluation()
    factors = []
    if probability is not None:
        if sport == "basketball":
            factors.append(f"Gegnerbereinigte erwartete Punktedifferenz Heim–Gast: {values['expected_margin']:.2f}; einschließlich Overtime.")
            factors.append(f"Aus den Punktedifferenzen geschätzte Streuung: {values['residual_scale']:.2f} Punkte.")
        elif sport == "ice_hockey":
            factors.append(f"Erwartete Tore in regulärer Spielzeit: {values['expected_home_goals']:.2f}/{values['expected_away_goals']:.2f}.")
            factors.append(f"Verlängerung/Shootout separat aus {fitted.overtime_games} passenden Spielen berücksichtigt.")
        else:
            factors.append(f"Gegnerbereinigte {identity.variant.upper()}-Stärkedifferenz: {values['strength_difference']:.3f}; ausschließlich explizite Matchsieger.")
    limitations = [
        "Forschungsmodell ohne unabhängigen Kalibrierungs- oder Wettwertnachweis.",
        "Akute Ausfälle, Aufstellungen, Wetter und weitere Matchup-Faktoren verändern diese Zahl nicht.",
        "Kein statistisch belegter individueller Wahrscheinlichkeits-Unterwert verfügbar.",
    ]
    if evaluation.count == 0:
        limitations.append("Keine aus rechtzeitig beobachteten Ergebnissen rekonstruierbare Vorab-Testfolge verfügbar.")
    canonical = {
        "version": MODEL_VERSION, "sport": sport,
        "identity": {**asdict(identity), "start": identity.start.isoformat()} if identity else None,
        "matches": [{**asdict(m), "start": m.start.isoformat(), "observed": m.observed.isoformat()} for m in matches],
    }
    input_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return PrematchPrediction(
        sport, probability, 1.0 - probability if probability is not None else None,
        len(matches), home_games, away_games, evaluation, tuple(factors), tuple(missing),
        tuple(limitations), input_hash, max((m.observed for m in matches), default=None),
        _MARKETS[sport], p_home_regulation=values.get("p_home_regulation"),
        p_draw_regulation=values.get("p_draw_regulation"),
    )


__all__ = ["MODEL_VERSION", "PrematchPrediction", "PrequentialEvaluation", "predict_prematch"]
