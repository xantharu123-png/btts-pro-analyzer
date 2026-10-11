"""Experimental OFFLINE football comparison, never a live forecast replacement.

Reuse the regularised attack/defence Poisson design in sports_prematch._fit,
without its NHL overtime model. Scope is API-Football-shaped positive IDs and
explicit FT regulation scores; CSV pseudo-IDs/unknown status are not promoted
to native evidence. Source receipt truth is NOT independently certified here.
Already-loaded results are the only inputs. No I/O, prices or release decision.
The penalty/bounds are inherited numerical choices, not proven optimal values.
History is bounded to the last 730 days. The fitted home coefficient describes
the provider's home designation, not an independently certified physical venue.
Missing result-receipt clocks permit only a current retrospective comparison;
they do NOT support prospective validation or causal recent-form residuals.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Iterable, Mapping
import math

import numpy as np
from scipy.optimize import minimize

VERSION = "football-opponent-adjusted-poisson-comparison-v1"
MAX_MATCHES, MAX_TEAMS, MIN_MATCHES, MIN_TEAM_MATCHES = 1200, 64, 40, 8
MAX_FORM_MATCHES = 6
TEAM_PENALTY = 5.0
HISTORY_DAYS = 730


class ComparisonUnavailable(ValueError):
    """A bounded, valid comparison is unavailable; never a coin-flip fallback."""


@dataclass(frozen=True)
class Match:
    fixture_id: int
    played_at: datetime
    home_id: int
    away_id: int
    home_goals: int
    away_goals: int
    home_effect_known: bool
    observed_at: datetime | None


@dataclass(frozen=True)
class StrengthFit:
    league_id: int
    teams: tuple[int, ...]
    matches: tuple[Match, ...]
    coefficients: tuple[float, ...]
    objective: float
    iterations: int


@dataclass(frozen=True)
class FormResidual:
    team_id: int
    fixture_id: int
    played_at: datetime
    prior_fixture_ids: tuple[int, ...]
    expected_scored: float
    expected_conceded: float
    scored: int
    conceded: int
    standardized_goal_balance: float


@dataclass(frozen=True)
class GoalStrengthComparison:
    version: str
    role: str
    empirically_qualified: bool
    fixture_id: int
    league_id: int
    home_id: int
    away_id: int
    cutoff: datetime
    starts_at: datetime
    fit: StrengthFit
    receipt_clock_matches: int
    expected_home_goals: float
    expected_away_goals: float
    p_home: float
    p_draw: float
    p_away: float
    score_law: tuple[tuple[int, int, float], ...]
    form_residuals: tuple[FormResidual, ...]


@dataclass(frozen=True)
class WinnerQualityPoint:
    fixture_id: int
    starts_at: datetime
    prior_fixture_ids: tuple[int, ...]
    outcome: str
    experimental_probabilities: tuple[float, float, float]
    legacy_probabilities: tuple[float, float, float]


@dataclass(frozen=True)
class WinnerQualityComparison:
    version: str
    role: str
    empirically_qualified: bool
    league_id: int
    cutoff: datetime
    attempted_targets: int
    receipt_clock_matches: int
    points: tuple[WinnerQualityPoint, ...]
    excluded: tuple[tuple[int, str], ...]
    experimental_brier: float | None
    legacy_brier: float | None
    experimental_log_loss: float | None
    legacy_log_loss: float | None


def _clock(value, label):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if type(value) is str else value
        if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ComparisonUnavailable(label + " requires an actual aware clock") from exc


def _integer(value, label, *, minimum=1):
    if type(value) is not int or value < minimum:
        raise ComparisonUnavailable(label + " requires an actual integer")
    return value


def _object(row, key):
    value = row.get(key)
    if not isinstance(value, Mapping):
        raise ComparisonUnavailable(key + " must be a source object")
    return value


def _identity(row):
    try:
        if not isinstance(row, Mapping):
            raise ComparisonUnavailable("fixture must be a mapping")
        event, league, teams = (_object(row, field) for field in ("fixture", "league", "teams"))
        result = (_integer(event["id"], "fixture ID"), _integer(league["id"], "league ID"),
                  _integer(teams["home"]["id"], "home ID"), _integer(teams["away"]["id"], "away ID"),
                  _clock(event["date"], "fixture start"))
        if result[2] == result[3]:
            raise ComparisonUnavailable("fixture teams must differ")
        return result
    except (KeyError, TypeError) as exc:
        raise ComparisonUnavailable("incomplete native fixture identity") from exc


def _home_effect_known(row):
    for flag in ("challenge_neutral_venue", "challenge_venue_unknown"):
        if flag in row and type(row[flag]) is not bool:
            raise ComparisonUnavailable("venue flags must be actual booleans")
    return not (row.get("challenge_neutral_venue") is True or row.get("challenge_venue_unknown") is True)


def _bounded_rows(history):
    raw = []
    for row in history:
        if len(raw) >= MAX_MATCHES:
            raise ComparisonUnavailable("history exceeds 1200 source matches; no silent suffix")
        raw.append(row)
    return tuple(raw)


def _matches(history, league_id, cutoff, target_id):
    raw = _bounded_rows(history)
    native, aliases = {}, {}
    for row in raw:
        if not isinstance(row, Mapping):
            raise ComparisonUnavailable("history fixtures must be mappings")
        if _object(row, "league").get("id") != league_id:
            continue
        if row.get("challenge_source") not in (None, "api-football", "api-football-ft-tail"):
            raise ComparisonUnavailable("comparison supports API-Football-shaped history only")
        event_id, _, home, away, start = _identity(row)
        if event_id == target_id or start >= cutoff or start < cutoff-timedelta(days=HISTORY_DAYS):
            continue
        if _object(row["fixture"], "status").get("short") != "FT":
            continue  # AET/PEN are NOT regulation results; no guessed subtraction.
        observed = _clock(row["result_observed_at"], "result observation") if row.get("result_observed_at") is not None else None
        if observed is not None and observed > cutoff:
            continue
        if observed is not None and observed <= start:
            raise ComparisonUnavailable("completed result was observed before the match")
        try:
            goals = tuple(_integer(_object(row, "goals")[side], "regulation goals", minimum=0) for side in ("home", "away"))
            if any(goal > 100 for goal in goals):
                raise ComparisonUnavailable("regulation score exceeds the bounded comparison domain")
            fulltime = _object(row, "score").get("fulltime") if "score" in row else None
            if fulltime is not None:
                if not isinstance(fulltime, Mapping):
                    raise ComparisonUnavailable("fulltime score must be an object")
                for i, side in enumerate(("home", "away")):
                    if fulltime.get(side) is not None and _integer(fulltime[side], "fulltime goals", minimum=0) != goals[i]:
                        raise ComparisonUnavailable("conflicting regulation goal fields")
        except (KeyError, TypeError, AttributeError) as exc:
            raise ComparisonUnavailable("completed regulation score is missing") from exc
        match = Match(event_id, start, home, away, *goals, _home_effect_known(row), observed)
        if event_id in native:
            previous = native[event_id]
            if replace(previous, observed_at=None) != replace(match, observed_at=None):
                raise ComparisonUnavailable("conflicting native fixture identity/result")
            clocks = [clock for clock in (previous.observed_at, observed) if clock is not None]
            match = replace(match, observed_at=min(clocks) if clocks else None)
        native[event_id] = match
    for event_id, match in sorted(native.items()):
        start, home, away = match.played_at, match.home_id, match.away_id
        goals = (match.home_goals, match.away_goals)
        key = (start, home, away)
        content = (goals, match.home_effect_known)
        if key in aliases and aliases[key][0] != content:
            raise ComparisonUnavailable("conflicting scheduled fixture aliases")
        if key not in aliases or event_id < aliases[key][1].fixture_id:
            aliases[key] = (content, match)
    accepted = tuple(sorted((item[1] for item in aliases.values()), key=lambda match: (match.played_at, match.fixture_id)))
    if len({team for match in accepted for team in (match.home_id, match.away_id)}) > MAX_TEAMS:
        raise ComparisonUnavailable("history exceeds 64 teams")
    return accepted


def _enough(matches, home, away):
    counts = Counter(team for row in matches for team in (row.home_id, row.away_id))
    if min(counts[home], counts[away]) < MIN_TEAM_MATCHES:
        raise ComparisonUnavailable("both teams need at least eight completed matches")
    if len(matches) < MIN_MATCHES:
        raise ComparisonUnavailable("comparison needs at least 40 completed matches")
    neighbours = {}
    for row in matches:
        neighbours.setdefault(row.home_id, set()).add(row.away_id)
        neighbours.setdefault(row.away_id, set()).add(row.home_id)
    seen, todo = set(), [home]
    while todo:
        team = todo.pop()
        if team not in seen:
            seen.add(team); todo.extend(neighbours.get(team, set()) - seen)
    if away not in seen:
        raise ComparisonUnavailable("target histories are not connected through observed opponents")


@lru_cache(maxsize=32)
def _fit(league_id, matches):
    """Exact existing joint-Poisson mechanics; no hockey/OT assumptions."""
    teams = tuple(sorted({team for row in matches for team in (row.home_id, row.away_id)}))
    positions, t = {team: i for i, team in enumerate(teams)}, len(teams)
    x, y = np.zeros((2*len(matches), 2*t+2)), np.zeros(2*len(matches))
    for i, row in enumerate(matches):
        for offset, scored, conceded, goals, sign in ((0, row.home_id, row.away_id, row.home_goals, .5),
                                                    (1, row.away_id, row.home_id, row.away_goals, -.5)):
            j = 2*i+offset
            x[j, positions[scored]], x[j, t+positions[conceded]] = 1., 1.
            x[j, -2], x[j, -1], y[j] = 1., sign if row.home_effect_known else 0., goals
    penalty = np.full(2*t+2, TEAM_PENALTY); penalty[-2:] = 0.
    initial = np.zeros(2*t+2); initial[-2] = math.log(max(float(y.mean()), .01))
    def objective(coef):
        eta = x @ coef; mu = np.exp(eta)
        loss = float((mu-y*eta).sum()+.5*(penalty*coef) @ coef)
        return loss, x.T @ (mu-y)+penalty*coef
    fitted = minimize(objective, initial, jac=True, method="L-BFGS-B",
        bounds=[(-4., 4.)]*(2*t)+[(-5., 5.), (-3., 3.)], options={"maxiter": 100, "ftol": 1e-9})
    if not fitted.success or not np.isfinite(fitted.x).all():
        raise ComparisonUnavailable("regularised goal-strength fit did not converge")
    return StrengthFit(league_id, teams, matches, tuple(float(v) for v in fitted.x), float(fitted.fun), int(fitted.nit))


def _rates(fit, home, away, home_effect_known):
    h, a, t, coef = fit.teams.index(home), fit.teams.index(away), len(fit.teams), fit.coefficients
    venue = coef[-1]/2 if home_effect_known else 0.
    rates = (math.exp(coef[-2]+coef[h]+coef[t+a]+venue), math.exp(coef[-2]+coef[a]+coef[t+h]-venue))
    if any(not math.isfinite(rate) or not 0 < rate <= 8 for rate in rates):
        raise ComparisonUnavailable("goal rates exceed the existing finite score-law contract")
    return rates


def _form(matches, league_id, home, away):
    result = []
    for team in (home, away):
        recent = [row for row in matches if team in (row.home_id, row.away_id)][-MAX_FORM_MATCHES:]
        for row in recent:
            if row.observed_at is None:
                continue
            prior = tuple(previous for previous in matches if previous.played_at < row.played_at
                          and previous.observed_at is not None and previous.observed_at < row.played_at)
            try:
                _enough(prior, row.home_id, row.away_id)
                rates = _rates(_fit(league_id, prior), row.home_id, row.away_id, row.home_effect_known)
            except ComparisonUnavailable:
                continue
            expected, goals = (rates, (row.home_goals, row.away_goals)) if team == row.home_id else (rates[::-1], (row.away_goals, row.home_goals))
            residual = ((goals[0]-goals[1])-(expected[0]-expected[1]))/math.sqrt(sum(expected))
            result.append(FormResidual(team, row.fixture_id, row.played_at, tuple(m.fixture_id for m in prior),
                *expected, *goals, residual))
    return tuple(result)


def compare_football_goal_strength(fixture: Mapping, history: Iterable[Mapping], cutoff: datetime,
                                   *, include_form=False) -> GoalStrengthComparison:
    """One detached offline comparison from loaded fixtures, never activation.

    Historical form is OPTIONAL and uses only individually clocked receipts
    observed before each historical kickoff. It is descriptive, not a learned
    probability adjustment or an independent statistical-significance claim.
    """
    from challenge_engine import score_matrix
    cutoff = _clock(cutoff, "comparison cutoff")
    event_id, league_id, home, away, start = _identity(fixture)
    if cutoff >= start or _object(fixture["fixture"], "status").get("short") not in {"NS", "TBD"}:
        raise ComparisonUnavailable("comparison needs a scheduled prematch target")
    if type(include_form) is not bool:
        raise ComparisonUnavailable("form option must be an actual boolean")
    matches = _matches(history, league_id, cutoff, event_id)
    _enough(matches, home, away)
    fitted = _fit(league_id, matches)
    rates = _rates(fitted, home, away, _home_effect_known(fixture))
    law = score_matrix(*rates)  # Existing normalized 90-minute Poisson buckets.
    p = tuple(sum(mass for (h, a), mass in law.items() if predicate(h, a))
              for predicate in (lambda h, a: h > a, lambda h, a: h == a, lambda h, a: h < a))
    return GoalStrengthComparison(VERSION, "experimental-offline", False, event_id, league_id, home, away,
        cutoff, start, fitted, sum(row.observed_at is not None for row in matches), *rates, *p,
        tuple((h, a, mass) for (h, a), mass in law.items()), _form(matches, league_id, home, away) if include_form else ())


def compare_retrospective_winner_quality(history: Iterable[Mapping], league_id: int, cutoff: datetime,
                                         *, max_targets=50) -> WinnerQualityComparison:
    """Bounded, paired raw-law comparison, NOT a prospective quality release.

    Compare the last <=50 finished targets using the same strictly earlier
    match inventory for both formulas. Preserve original raw xG fields for the
    legacy formula. No saved calibration map (which could know later labels),
    outcome tuning, prices or activation is used. Missing receipt clocks mean
    event-time reconstruction only; this is not a live prediction replay.
    Brier is the sum over the three mutually exclusive outcomes, not divided
    by three. An actual outcome assigned zero probability has infinite log
    loss; it remains paired, never excluded on the basis of that outcome.
    Every attempted target is either paired or explicitly excluded.
    """
    from challenge_engine import _fixture_model, score_matrix
    cutoff, league_id = _clock(cutoff, "evaluation cutoff"), _integer(league_id, "league ID")
    if type(max_targets) is not int or not 1 <= max_targets <= 50:
        raise ComparisonUnavailable("rolling comparison is bounded to 1..50 targets")
    # Retain raw model inputs; the fitted Match projection intentionally omits xG.
    rows = _bounded_rows(history)
    matches = _matches(rows, league_id, cutoff, 0)
    # Select the exact same eligible receipt used by Match deduplication. A
    # later identical-score receipt may carry later xG: do not feed that later
    # auxiliary revision to the historical legacy baseline by dict overwrite.
    accepted = {match.fixture_id: match for match in matches}
    by_id = {}
    for row in rows:
        if _object(row, "league").get("id") != league_id:
            continue
        event_id = row["fixture"]["id"]
        match = accepted.get(event_id)
        if match is None:
            continue
        observed = _clock(row["result_observed_at"], "result observation") if row.get("result_observed_at") is not None else None
        if observed == match.observed_at:
            if event_id in by_id and by_id[event_id].get("challenge_stats") != row.get("challenge_stats"):
                raise ComparisonUnavailable("conflicting raw legacy input revision")
            by_id[event_id] = row
    points, excluded = [], []
    targets = matches[-max_targets:]
    for target in targets:
        prior = tuple(row for row in matches if target.played_at-timedelta(days=HISTORY_DAYS) <= row.played_at < target.played_at
                      and (row.observed_at is None or row.observed_at < target.played_at))
        try:
            _enough(prior, target.home_id, target.away_id)
            fitted = _fit(league_id, prior)
            rates = _rates(fitted, target.home_id, target.away_id, target.home_effect_known)
            experimental = score_matrix(*rates)
            future_target = deepcopy(by_id[target.fixture_id])
            future_target["fixture"]["status"] = {"short": "NS"}
            future_target["goals"] = {"home": None, "away": None}
            original_prefix = [by_id[row.fixture_id] for row in prior]
            legacy = _fixture_model(future_target, original_prefix)
            if legacy is None:
                raise ComparisonUnavailable("legacy raw goal model unavailable on identical prefix")
            try:
                legacy_law = score_matrix(*legacy["active_lambdas"])
            except ValueError as exc:
                raise ComparisonUnavailable("legacy goal rates exceed the existing finite score-law contract") from exc
        except ComparisonUnavailable as exc:
            excluded.append((target.fixture_id, str(exc)))
            continue
        def probabilities(law):
            return tuple(sum(p for (h, a), p in law.items() if predicate(h, a))
                         for predicate in (lambda h, a: h > a, lambda h, a: h == a, lambda h, a: h < a))
        outcome = "home" if target.home_goals > target.away_goals else "away" if target.home_goals < target.away_goals else "draw"
        points.append(WinnerQualityPoint(target.fixture_id, target.played_at, tuple(row.fixture_id for row in prior),
            outcome, probabilities(experimental), probabilities(legacy_law)))
    def losses(field):
        if not points:
            return None, None
        brier, log_loss = [], []
        for point in points:
            values = getattr(point, field)
            index = ("home", "draw", "away").index(point.outcome)
            brier.append(sum((value-int(i == index))**2 for i, value in enumerate(values)))
            log_loss.append(-math.log(values[index]) if values[index] > 0 else math.inf)
        return math.fsum(brier)/len(points), math.fsum(log_loss)/len(points)
    new_brier, new_logloss = losses("experimental_probabilities")
    old_brier, old_logloss = losses("legacy_probabilities")
    return WinnerQualityComparison(VERSION, "retrospective-offline-not-prospective-validation", False,
        league_id, cutoff, len(targets), sum(row.observed_at is not None for row in matches), tuple(points),
        tuple(excluded), new_brier, old_brier, new_logloss, old_logloss)
