"""Price-blind 1X2 baseline for the Handball-Bundesliga pilot only."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from math import erfc, sqrt

import numpy as np

MIN_LEAGUE_GAMES = 40
MIN_TEAM_GAMES = 8
_RIDGE = 6.0
_MIN_MARGIN_SD = 4.0


def predict_1x2(
    history: Iterable[tuple[int, int, int, int]], *, home_id: int, away_id: int,
) -> dict[str, float] | None:
    """Use completed, earlier regulation-time scores in a single league.

    Rows are (home ID, away ID, home goals, away goals). The caller owns
    fixture uniqueness, timestamps and the season/league and result checks.
    These fixed pilot choices do not imply calibration or a betting edge.
    """
    if (type(home_id) is not int or type(away_id) is not int
            or min(home_id, away_id) <= 0 or home_id == away_id):
        return None
    opponents: dict[int, set[int]] = defaultdict(set)
    scores: list[tuple[int, int, int, int]] = []
    for row in history:
        if not isinstance(row, tuple) or len(row) != 4 or any(type(v) is not int for v in row):
            return None
        home, away, home_goals, away_goals = row
        if min(home, away) <= 0 or home == away or min(home_goals, away_goals) < 0:
            return None
        scores.append(row)
        opponents[home].add(away)
        opponents[away].add(home)

    # A common strength scale requires a chain of actual opponents, not just
    # two teams with enough games in separate parts of the schedule.
    component = {home_id}
    pending = [home_id]
    while pending:
        for opponent in opponents.get(pending.pop(), ()):
            if opponent not in component:
                component.add(opponent)
                pending.append(opponent)
    if away_id not in component:
        return None
    games = [row for row in scores if row[0] in component]
    appearances = Counter(team for row in games for team in row[:2])
    if len(games) < MIN_LEAGUE_GAMES or min(appearances[home_id], appearances[away_id]) < MIN_TEAM_GAMES:
        return None

    # margin = home effect + strength(home) - strength(away) + residual
    # Shrink team strengths, but not the common home effect, toward zero.
    columns = {team: idx for idx, team in enumerate(sorted(component), start=1)}
    design = np.zeros((len(games), 1 + len(columns)))
    design[:, 0] = 1.0
    margins = np.zeros(len(games))
    for idx, (home, away, home_goals, away_goals) in enumerate(games):
        design[idx, columns[home]] = 1.0
        design[idx, columns[away]] = -1.0
        margins[idx] = home_goals - away_goals
    penalty = _RIDGE * np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ margins)
    residual = margins - design @ coefficients
    scale = max(_MIN_MARGIN_SD, sqrt(float(residual @ residual) / max(1, len(games) - len(columns))))
    mean = float(coefficients[0] + coefficients[columns[home_id]] - coefficients[columns[away_id]])

    # Round a continuous margin to whole goals. The smaller tail is used
    # directly so a strong favourite doesn't lose the underdog's tail to 1-CDF.
    root_two_sd = sqrt(2.0) * scale
    smaller_win = 0.5 * erfc((abs(mean) + 0.5) / root_two_sd)
    draw = 0.5 * erfc((abs(mean) - 0.5) / root_two_sd) - smaller_win
    larger_win = 1.0 - (draw + smaller_win)
    home_win, away_win = (larger_win, smaller_win) if mean >= 0 else (smaller_win, larger_win)
    return {"home": home_win, "draw": draw, "away": away_win}
