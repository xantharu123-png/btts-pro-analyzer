"""Dixon-Coles (1997) goal model by time-weighted maximum likelihood (opt-in).

Alternative to the additive 12/6-match averages in
``challenge_engine._fixture_model`` (audit 2026-10-16, H1): multiplicative
attack/defence strengths, one home advantage, the low-score dependence
parameter ``rho`` and an exponential time decay are estimated jointly per
league from completed fixtures before a cutoff. Prices never enter. This module
imports nothing from ``challenge_engine`` (no import cycle); the engine opts in
through its ``goal_model`` switch, whose default behaviour is unchanged.

Model: ``log lambda_home = mu + attack[h] + defence[a] + home_advantage``,
``log lambda_away = mu + attack[a] + defence[h]`` (neutral venues drop the home
term); ``P(x, y) = tau(x, y) Poisson(x; lambda) Poisson(y; mu)`` with
``tau(0,0) = 1 - lambda*mu*rho``, ``tau(1,0) = 1 + mu*rho``,
``tau(0,1) = 1 + lambda*rho``, ``tau(1,1) = 1 - rho`` and ``tau = 1`` elsewhere.
Weights ``w = 0.5 ** (days_before_cutoff / half_life_days)``. A mild ridge
penalty shrinks strengths towards the league average; attack/defence are
centred after the fit (the intercept absorbs the shift, likelihood unchanged).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import math
from typing import Any, Iterable, Optional

import numpy as np
from scipy.optimize import minimize

DC_VERSION = "dixon-coles-mle-v1"
DEFAULT_HALF_LIFE_DAYS = 120.0
MAX_HISTORY_DAYS = 730
MIN_MATCHES = 40
MIN_TEAM_MATCHES = 4
MAX_TEAMS = 64
RHO_BOUNDS = (-0.25, 0.25)
STRENGTH_BOUNDS = (-3.0, 3.0)
RIDGE = 0.02
MAX_RATE = 8.0
_TAU_FLOOR = 1e-6


class DixonColesUnavailable(ValueError):
    """A bounded, converged fit is unavailable; callers must fail closed."""


@dataclass(frozen=True)
class DixonColesMatch:
    fixture_id: int
    played_at: datetime
    home_id: int
    away_id: int
    home_goals: int
    away_goals: int
    home_effect_known: bool = True


@dataclass(frozen=True)
class DixonColesFit:
    version: str
    league_id: Optional[int]
    cutoff: datetime
    half_life_days: float
    teams: tuple[int, ...]
    attack: tuple[float, ...]
    defence: tuple[float, ...]
    intercept: float
    home_advantage: float
    rho: float
    matches: int
    weight_sum: float
    log_likelihood: float
    converged: bool
    iterations: int
    # Venue-specific variant (hypothesis H4): separate away attack/defence;
    # ``attack``/``defence`` then hold the home-venue parameters.
    attack_away: Optional[tuple[float, ...]] = None
    defence_away: Optional[tuple[float, ...]] = None

    @property
    def venue_specific(self) -> bool:
        return self.attack_away is not None

    def _index(self, team_id: int) -> int:
        try:
            return self.teams.index(team_id)
        except ValueError as exc:
            raise DixonColesUnavailable("team has no fitted strength") from exc

    def rates(self, home_id: int, away_id: int, *, home_effect_known: bool = True) -> tuple[float, float]:
        home, away = self._index(home_id), self._index(away_id)
        venue = self.home_advantage if home_effect_known else 0.0
        attack_away = self.attack_away if self.attack_away is not None else self.attack
        defence_away = self.defence_away if self.defence_away is not None else self.defence
        rates = (
            math.exp(self.intercept + self.attack[home] + defence_away[away] + venue),
            math.exp(self.intercept + attack_away[away] + self.defence[home]),
        )
        if any(not math.isfinite(rate) or not 0.0 < rate <= MAX_RATE for rate in rates):
            raise DixonColesUnavailable("goal rates leave the finite score-law range")
        return rates

    def score_matrix(self, home_id: int, away_id: int, *, max_goals: int = 25,
                     home_effect_known: bool = True) -> dict[tuple[int, int], float]:
        home_rate, away_rate = self.rates(home_id, away_id, home_effect_known=home_effect_known)
        return dixon_coles_score_matrix(home_rate, away_rate, clamp_rho(self.rho, home_rate, away_rate),
                                        max_goals=max_goals)

    def summary(self) -> dict[str, Any]:
        return {
            "version": self.version, "league_id": self.league_id, "cutoff": self.cutoff.isoformat(),
            "half_life_days": self.half_life_days, "teams": len(self.teams), "matches": self.matches,
            "weight_sum": round(self.weight_sum, 3), "intercept": round(self.intercept, 6),
            "home_advantage": round(self.home_advantage, 6), "rho": round(self.rho, 6),
            "log_likelihood": round(self.log_likelihood, 4), "converged": self.converged,
            "iterations": self.iterations, "venue_specific": self.venue_specific,
        }


def decay_weights(days_before_cutoff: np.ndarray, half_life_days: float) -> np.ndarray:
    if not math.isfinite(half_life_days) or half_life_days <= 0.0:
        raise ValueError("half_life_days must be positive")
    return np.power(0.5, np.asarray(days_before_cutoff, dtype=float) / half_life_days)


def tau_correction(home_goals: int, away_goals: int, home_rate: float, away_rate: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1.0 - home_rate * away_rate * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + away_rate * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + home_rate * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def valid_rho_range(home_rate: float, away_rate: float, *, margin: float = 1e-6) -> tuple[float, float]:
    """Open interval of ``rho`` keeping every low-score correction factor positive.

    ``tau(1,0) = 1 + mu*rho`` and ``tau(0,1) = 1 + lambda*rho`` bound rho from
    below by ``-1/max(lambda, mu)``; ``tau(0,0) = 1 - lambda*mu*rho`` bounds it
    from above by ``1/(lambda*mu)``; ``tau(1,1) = 1 - rho`` needs ``rho < 1``.
    """
    top = max(float(home_rate), float(away_rate))
    product = float(home_rate) * float(away_rate)
    lower = (-1.0 / top + margin) if top > 0.0 else -1.0 + margin
    upper = min(1.0 - margin, (1.0 / product - margin) if product > 0.0 else 1.0 - margin)
    return max(lower, -1.0 + margin), upper


def clamp_rho(rho: float, home_rate: float, away_rate: float) -> float:
    """Fitted rho projected into the valid range for one fixture's rates."""
    lower, upper = valid_rho_range(home_rate, away_rate)
    return min(max(float(rho), lower), upper)


def _poisson_pmf(rate: float, max_goals: int) -> list[float]:
    if rate == 0.0:
        return [1.0] + [0.0] * max_goals
    return [math.exp(k * math.log(rate) - rate - math.lgamma(k + 1)) for k in range(max_goals + 1)]


def dixon_coles_score_matrix(home_rate: float, away_rate: float, rho: float, *,
                             max_goals: int = 25) -> dict[tuple[int, int], float]:
    """Normalised rho-corrected score law; ``rho == 0`` is independent Poisson."""
    for rate in (home_rate, away_rate):
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 0.0 <= rate <= MAX_RATE:
            raise ValueError("Goal rates must be finite and between 0 and 8")
    if not isinstance(max_goals, int) or max_goals < 5:
        raise ValueError("max_goals must be an integer of at least 5")
    home = _poisson_pmf(float(home_rate), max_goals)
    away = _poisson_pmf(float(away_rate), max_goals)
    matrix = {(h, a): home[h] * away[a] for h in range(max_goals + 1) for a in range(max_goals + 1)}
    if rho:
        for cell in ((0, 0), (1, 0), (0, 1), (1, 1)):
            factor = tau_correction(cell[0], cell[1], float(home_rate), float(away_rate), float(rho))
            if factor <= 0.0:
                raise ValueError("rho leaves the valid Dixon-Coles range for these rates")
            matrix[cell] *= factor
    mass = sum(matrix.values())
    if mass <= 0.0:
        raise ValueError("Score matrix has no probability mass")
    return {cell: probability / mass for cell, probability in matrix.items()}


def matches_from_fixtures(fixtures: Iterable[dict[str, Any]]) -> list[DixonColesMatch]:
    """API-Football-shaped completed fixtures to immutable match rows (no prices)."""
    rows: dict[int, DixonColesMatch] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        data, teams, goals = fixture.get("fixture") or {}, fixture.get("teams") or {}, fixture.get("goals") or {}
        fixture_id = data.get("id") if isinstance(data, dict) else None
        raw_date = data.get("date") if isinstance(data, dict) else None
        home = (teams.get("home") or {}).get("id") if isinstance(teams, dict) else None
        away = (teams.get("away") or {}).get("id") if isinstance(teams, dict) else None
        home_goals = goals.get("home") if isinstance(goals, dict) else None
        away_goals = goals.get("away") if isinstance(goals, dict) else None
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (fixture_id, home, away, home_goals, away_goals)):
            continue
        if home == away or home_goals < 0 or away_goals < 0 or not isinstance(raw_date, str):
            continue
        try:
            played = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError:
            continue
        if played.tzinfo is None:
            played = played.replace(tzinfo=timezone.utc)
        known = not (fixture.get("challenge_neutral_venue") is True or fixture.get("challenge_venue_unknown") is True)
        rows[fixture_id] = DixonColesMatch(fixture_id, played.astimezone(timezone.utc), home, away,
                                           home_goals, away_goals, known)
    return sorted(rows.values(), key=lambda row: (row.played_at, row.fixture_id))


def _design(matches: tuple[DixonColesMatch, ...], cutoff: datetime, half_life_days: float):
    teams = tuple(sorted({team for row in matches for team in (row.home_id, row.away_id)}))
    position = {team: index for index, team in enumerate(teams)}
    home = np.fromiter((position[row.home_id] for row in matches), dtype=int, count=len(matches))
    away = np.fromiter((position[row.away_id] for row in matches), dtype=int, count=len(matches))
    x = np.fromiter((row.home_goals for row in matches), dtype=float, count=len(matches))
    y = np.fromiter((row.away_goals for row in matches), dtype=float, count=len(matches))
    known = np.fromiter((1.0 if row.home_effect_known else 0.0 for row in matches), dtype=float, count=len(matches))
    days = np.fromiter(((cutoff - row.played_at).total_seconds() / 86400.0 for row in matches), dtype=float, count=len(matches))
    weights = decay_weights(np.maximum(days, 0.0), half_life_days)
    return teams, home, away, x, y, known, weights


def negative_log_likelihood(params: np.ndarray, home: np.ndarray, away: np.ndarray, x: np.ndarray, y: np.ndarray,
                            known: np.ndarray, weights: np.ndarray, team_count: int,
                            ridge: float = RIDGE, venue_specific: bool = False) -> tuple[float, np.ndarray]:
    """Weighted negative Dixon-Coles log-likelihood plus ridge, with its gradient.

    With ``venue_specific`` the parameter vector carries four strength blocks
    (home attack, home defence, away attack, away defence); the home advantage
    is then absorbed by the blocks and must be held at zero by the caller.
    """
    mu, home_advantage, rho = params[0], params[1], params[2]
    attack = params[3:3 + team_count]
    defence = params[3 + team_count:3 + 2 * team_count]
    if venue_specific:
        attack_away = params[3 + 2 * team_count:3 + 3 * team_count]
        defence_away = params[3 + 3 * team_count:3 + 4 * team_count]
    else:
        attack_away, defence_away = attack, defence
    eta_h = mu + attack[home] + defence_away[away] + home_advantage * known
    eta_a = mu + attack_away[away] + defence[home]
    lam, mum = np.exp(eta_h), np.exp(eta_a)
    tau = np.ones_like(lam)
    zero_zero = (x == 0) & (y == 0)
    one_zero = (x == 1) & (y == 0)
    zero_one = (x == 0) & (y == 1)
    one_one = (x == 1) & (y == 1)
    tau[zero_zero] = 1.0 - lam[zero_zero] * mum[zero_zero] * rho
    tau[one_zero] = 1.0 + mum[one_zero] * rho
    tau[zero_one] = 1.0 + lam[zero_one] * rho
    tau[one_one] = 1.0 - rho
    clipped = tau < _TAU_FLOOR
    tau = np.where(clipped, _TAU_FLOOR, tau)
    log_likelihood = float(np.sum(weights * (x * eta_h - lam + y * eta_a - mum + np.log(tau))))
    strengths = params[3:3 + (4 if venue_specific else 2) * team_count]
    penalty = ridge * float(strengths @ strengths)
    # Gradient with respect to the log-rates and rho.
    d_tau_d_lam = np.zeros_like(lam)
    d_tau_d_mu = np.zeros_like(lam)
    d_tau_d_rho = np.zeros_like(lam)
    d_tau_d_lam[zero_zero] = -mum[zero_zero] * rho
    d_tau_d_mu[zero_zero] = -lam[zero_zero] * rho
    d_tau_d_rho[zero_zero] = -lam[zero_zero] * mum[zero_zero]
    d_tau_d_mu[one_zero] = rho
    d_tau_d_rho[one_zero] = mum[one_zero]
    d_tau_d_lam[zero_one] = rho
    d_tau_d_rho[zero_one] = lam[zero_one]
    d_tau_d_rho[one_one] = -1.0
    live = np.where(clipped, 0.0, 1.0 / tau)
    g_eta_h = weights * (x - lam + lam * d_tau_d_lam * live)
    g_eta_a = weights * (y - mum + mum * d_tau_d_mu * live)
    g_rho = float(np.sum(weights * d_tau_d_rho * live))
    gradient = np.zeros_like(params)
    gradient[0] = float(np.sum(g_eta_h + g_eta_a))
    gradient[1] = float(np.sum(g_eta_h * known))
    gradient[2] = g_rho
    if venue_specific:
        gradient[3:3 + team_count] = np.bincount(home, weights=g_eta_h, minlength=team_count)
        gradient[3 + team_count:3 + 2 * team_count] = np.bincount(home, weights=g_eta_a, minlength=team_count)
        gradient[3 + 2 * team_count:3 + 3 * team_count] = np.bincount(away, weights=g_eta_a, minlength=team_count)
        gradient[3 + 3 * team_count:3 + 4 * team_count] = np.bincount(away, weights=g_eta_h, minlength=team_count)
    else:
        gradient[3:3 + team_count] = (np.bincount(home, weights=g_eta_h, minlength=team_count)
                                      + np.bincount(away, weights=g_eta_a, minlength=team_count))
        gradient[3 + team_count:3 + 2 * team_count] = (np.bincount(away, weights=g_eta_h, minlength=team_count)
                                                       + np.bincount(home, weights=g_eta_a, minlength=team_count))
    gradient[3:3 + len(strengths)] -= 2.0 * ridge * strengths
    return -(log_likelihood - penalty), -gradient


def fit_dixon_coles(matches: Iterable[DixonColesMatch], cutoff: datetime, *,
                    half_life_days: float = DEFAULT_HALF_LIFE_DAYS, league_id: Optional[int] = None,
                    initial: Optional[DixonColesFit] = None, max_history_days: int = MAX_HISTORY_DAYS,
                    ridge: float = RIDGE, level_prior: bool = False, venue_specific: bool = False) -> DixonColesFit:
    """Fit on completed matches strictly before ``cutoff`` (fail-closed on thin data).

    ``venue_specific=True`` (hypothesis H4) fits separate home- and away-venue
    attack/defence parameters per team; the league home advantage is then the
    difference of the venue block means after centring.

    ``level_prior=True`` keeps the time-weighted relative strengths but re-anchors
    the intercept so that the *unweighted* mean predicted goals over the whole
    history window equal the unweighted observed mean (moment matching; the
    weighted MLE alone follows recent scoring levels). Hypothesis H2 of the
    2026-10-20 plan: long-run level, recent relative strengths.
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff must be timezone-aware")
    cutoff = cutoff.astimezone(timezone.utc)
    horizon = cutoff - timedelta(days=max_history_days)
    usable = tuple(sorted((row for row in matches if horizon <= row.played_at < cutoff),
                          key=lambda row: (row.played_at, row.fixture_id)))
    if len(usable) < MIN_MATCHES:
        raise DixonColesUnavailable(f"fit needs at least {MIN_MATCHES} completed matches")
    teams, home, away, x, y, known, weights = _design(usable, cutoff, half_life_days)
    if len(teams) > MAX_TEAMS:
        raise DixonColesUnavailable("history exceeds the supported team count")
    counts = np.bincount(home, minlength=len(teams)) + np.bincount(away, minlength=len(teams))
    if int(counts.min()) < MIN_TEAM_MATCHES:
        raise DixonColesUnavailable("every fitted team needs enough completed matches")
    team_count = len(teams)
    blocks = 4 if venue_specific else 2
    params = np.zeros(3 + blocks * team_count)
    params[0] = math.log(max(float(np.average(np.concatenate((x, y)), weights=np.concatenate((weights, weights)))), 0.05))
    params[1] = 0.0 if venue_specific else 0.25
    params[2] = -0.05
    if initial is not None and initial.venue_specific == venue_specific:
        params[0], params[1], params[2] = initial.intercept, initial.home_advantage, initial.rho
        if venue_specific:
            params[1] = 0.0  # Absorbed by the venue blocks during the fit; re-derived afterwards.
        for index, team in enumerate(teams):
            if team in initial.teams:
                previous = initial.teams.index(team)
                params[3 + index] = initial.attack[previous]
                params[3 + team_count + index] = initial.defence[previous]
                if venue_specific:
                    params[3 + 2 * team_count + index] = initial.attack_away[previous]
                    params[3 + 3 * team_count + index] = initial.defence_away[previous]
    bounds = ([(-3.0, 3.0), (0.0, 0.0) if venue_specific else (-2.0, 2.0), RHO_BOUNDS]
              + [STRENGTH_BOUNDS] * (blocks * team_count))
    result = minimize(
        negative_log_likelihood, params, jac=True, method="L-BFGS-B", bounds=bounds,
        args=(home, away, x, y, known, weights, team_count, ridge, venue_specific),
        options={"maxiter": 400, "ftol": 1e-11, "gtol": 1e-7},
    )
    fitted = np.asarray(result.x, dtype=float)
    if not np.all(np.isfinite(fitted)):
        raise DixonColesUnavailable("fit produced non-finite parameters")
    attack = fitted[3:3 + team_count]
    defence = fitted[3 + team_count:3 + 2 * team_count]
    if venue_specific:
        attack_away = fitted[3 + 2 * team_count:3 + 3 * team_count]
        defence_away = fitted[3 + 3 * team_count:3 + 4 * team_count]
        means = [float(block.mean()) for block in (attack, defence, attack_away, defence_away)]
        attack, defence = attack - means[0], defence - means[1]
        attack_away, defence_away = attack_away - means[2], defence_away - means[3]
        # Away rates set the level; the home advantage is the home-venue surplus.
        intercept = float(fitted[0]) + means[2] + means[1]
        home_advantage = (means[0] + means[3]) - (means[2] + means[1])
    else:
        shift_attack, shift_defence = float(attack.mean()), float(defence.mean())
        attack, defence = attack - shift_attack, defence - shift_defence
        attack_away, defence_away = attack, defence
        intercept = float(fitted[0]) + shift_attack + shift_defence
        home_advantage = float(fitted[1])
    if level_prior:
        eta_h = intercept + attack[home] + defence_away[away] + home_advantage * known
        eta_a = intercept + attack_away[away] + defence[home]
        predicted = float(np.sum(np.exp(eta_h) + np.exp(eta_a)))
        observed = float(np.sum(x + y))
        if predicted > 0.0 and observed > 0.0:
            intercept += math.log(observed / predicted)
    return DixonColesFit(
        version=DC_VERSION + ("-venue" if venue_specific else "") + ("-level" if level_prior else ""),
        league_id=league_id, cutoff=cutoff, half_life_days=float(half_life_days),
        teams=teams, attack=tuple(float(v) for v in attack), defence=tuple(float(v) for v in defence),
        intercept=intercept, home_advantage=float(home_advantage), rho=float(fitted[2]),
        matches=len(usable), weight_sum=float(weights.sum()), log_likelihood=-float(result.fun),
        converged=bool(result.success), iterations=int(result.nit),
        attack_away=tuple(float(v) for v in attack_away) if venue_specific else None,
        defence_away=tuple(float(v) for v in defence_away) if venue_specific else None,
    )


def reweight_totals(target: dict[tuple[int, int], float], matrix: dict[tuple[int, int], float]) -> dict[tuple[int, int], float]:
    """Keep ``matrix``'s split within each total-goal line, adopt ``target``'s total-goal law.

    Coherent hybrid (hypothesis H3 in production form): one score matrix whose
    result structure comes from ``matrix`` (Dixon-Coles) and whose over/under
    distribution equals that of ``target`` (legacy). Cells of a total that has
    no mass in ``matrix`` take the target mass spread by the target's own split.
    """
    target_totals: dict[int, float] = {}
    matrix_totals: dict[int, float] = {}
    for (h, a), p in target.items():
        target_totals[h + a] = target_totals.get(h + a, 0.0) + p
    for (h, a), p in matrix.items():
        matrix_totals[h + a] = matrix_totals.get(h + a, 0.0) + p
    out: dict[tuple[int, int], float] = {}
    for cell, p in matrix.items():
        total = cell[0] + cell[1]
        base = matrix_totals.get(total, 0.0)
        if base > 0.0:
            out[cell] = p * target_totals.get(total, 0.0) / base
        else:
            out[cell] = target.get(cell, 0.0)
    mass = sum(out.values())
    if mass <= 0.0:
        raise ValueError("hybrid score matrix has no probability mass")
    return {cell: p / mass for cell, p in out.items()}


_LAST_FIT: dict[tuple[Optional[int], float, bool, bool], DixonColesFit] = {}


@lru_cache(maxsize=64)
def _cached_fit(league_id: Optional[int], cutoff_day: str, matches: tuple[DixonColesMatch, ...],
                half_life_days: float, level_prior: bool = False, venue_specific: bool = False) -> DixonColesFit:
    cutoff = datetime.fromisoformat(cutoff_day)
    key = (league_id, float(half_life_days), bool(level_prior), bool(venue_specific))
    fit = fit_dixon_coles(matches, cutoff, half_life_days=half_life_days, league_id=league_id,
                          initial=_LAST_FIT.get(key), level_prior=level_prior, venue_specific=venue_specific)
    if fit.converged:
        _LAST_FIT[key] = fit
    return fit


@lru_cache(maxsize=16)
def _cold_fit(league_id: Optional[int], cutoff_day: str, matches: tuple[DixonColesMatch, ...],
              half_life_days: float, level_prior: bool = False, venue_specific: bool = False) -> DixonColesFit:
    """Replayable fit without warm start: identical inputs give identical bytes."""
    cutoff = datetime.fromisoformat(cutoff_day)
    return fit_dixon_coles(matches, cutoff, half_life_days=half_life_days, league_id=league_id,
                           initial=None, level_prior=level_prior, venue_specific=venue_specific)


def last_fit(league_id: Optional[int], *, half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
             level_prior: bool = False, venue_specific: bool = False) -> Optional[DixonColesFit]:
    return _LAST_FIT.get((league_id, float(half_life_days), bool(level_prior), bool(venue_specific)))


def fit_for_fixture(fixture: dict[str, Any], league_history: Iterable[dict[str, Any]], *,
                    half_life_days: float = DEFAULT_HALF_LIFE_DAYS, level_prior: bool = False,
                    venue_specific: bool = False, cold_start: bool = False) -> DixonColesFit:
    """League fit at the fixture's kickoff day, cached per (league, day, history, options).

    ``cold_start`` ignores the warm-start history (ORIGINAL capture/replay).
    """
    data = fixture.get("fixture") if isinstance(fixture, dict) else None
    raw_date = data.get("date") if isinstance(data, dict) else None
    if not isinstance(raw_date, str):
        raise DixonColesUnavailable("fixture has no kickoff clock")
    kickoff = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    kickoff = kickoff.astimezone(timezone.utc)
    # The cutoff is the kickoff day start: identical fits for one match day and
    # no same-day result can enter (results are only completed fixtures anyway).
    cutoff = kickoff.replace(hour=0, minute=0, second=0, microsecond=0)
    league = fixture.get("league") if isinstance(fixture, dict) else None
    league_id = league.get("id") if isinstance(league, dict) and isinstance(league.get("id"), int) else None
    matches = tuple(row for row in matches_from_fixtures(league_history) if row.played_at < cutoff)
    fitter = _cold_fit if cold_start else _cached_fit
    return fitter(league_id, cutoff.isoformat(), matches, float(half_life_days), bool(level_prior),
                  bool(venue_specific))


__all__ = [
    "DC_VERSION", "DEFAULT_HALF_LIFE_DAYS", "DixonColesFit", "DixonColesMatch", "DixonColesUnavailable",
    "MIN_MATCHES", "MIN_TEAM_MATCHES", "RHO_BOUNDS", "clamp_rho", "decay_weights", "dixon_coles_score_matrix",
    "fit_dixon_coles", "fit_for_fixture", "last_fit", "matches_from_fixtures", "negative_log_likelihood",
    "reweight_totals", "tau_correction", "valid_rho_range",
]
