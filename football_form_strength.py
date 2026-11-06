"""Form strength for the legacy goal rates (pre-registered test of 06.11.2026).

The raw legacy rates underestimated in-form teams. The pre-registered variant multiplies both
teams' rates by exp(KAPPA * (s_own - s_opponent)), where s is a team's mean goal difference per
match over its last WINDOW league matches before kickoff. Test on calibrated goal markets through
the unchanged walk-forward validation path, 16 634 games of 31 leagues before 01.09.2026:
Brier -0.00136 (SE 0.00017), log loss -0.00334 (SE 0.00039), better in 30 of 31 leagues
(docs/audits/2026-11-06-formstaerke-test.md).

This is an opt-in goal basis (``challenge_engine.GOAL_MODEL_FORM_STRENGTH``). Its prediction
version differs from the production one, so its candidates are never released; it exists for
measurement on new games until the owner decides. Pure computation, no I/O.
"""
from __future__ import annotations

import math
import numbers
from datetime import datetime
from typing import Any, Iterable, Optional

VERSION = "form-strength-v1-20261106"
KAPPA = 0.11
WINDOW = 10
MIN_GAMES = 5
# A goal difference per match beyond this bound is no real league form; such data fails closed.
MAX_ABS_FORM = 10.0
# The pre-registered test covered domestic league games only; UEFA club competitions fail closed.
EXCLUDED_LEAGUE_IDS = frozenset({2, 3, 848})
ANNOTATION_KEYS = frozenset({"version", "home_form", "away_form", "home_factor", "away_factor"})


def _finite(value: Any) -> bool:
    return (not isinstance(value, bool) and isinstance(value, numbers.Real)
            and math.isfinite(float(value)))


def team_form(history: Iterable[dict[str, Any]], team_id: int, league_id: Any, kickoff: datetime,
              *, fixture_datetime, fixture_score) -> Optional[float]:
    """Mean goal difference per match of the team's last WINDOW league matches before kickoff.

    Only completed regulation results of the same league count (``fixture_score``). Fewer than
    MIN_GAMES matches give no form (the caller applies no factor).
    """
    rows = []
    for item in history:
        if not isinstance(item, dict) or (item.get("league") or {}).get("id") != league_id:
            continue
        played = fixture_datetime(item)
        score = fixture_score(item)
        if played is None or score is None or played >= kickoff:
            continue
        teams = item.get("teams") or {}
        home = (teams.get("home") or {}).get("id")
        away = (teams.get("away") or {}).get("id")
        fixture_id = (item.get("fixture") or {}).get("id")
        if team_id == home:
            rows.append((played, str(fixture_id), score[0] - score[1]))
        elif team_id == away:
            rows.append((played, str(fixture_id), score[1] - score[0]))
    if len(rows) < MIN_GAMES:
        return None
    rows.sort()
    recent = rows[-WINDOW:]
    return sum(difference for _played, _id, difference in recent) / len(recent)


def _factors(home_form: float, away_form: float) -> tuple[float, float]:
    gap = home_form - away_form
    return math.exp(KAPPA * gap), math.exp(-KAPPA * gap)


def form_strength_annotation(home_form: Optional[float], away_form: Optional[float]) -> Optional[dict]:
    """Annotation of one fixture, or None when a form is missing (no factor) or invalid."""
    if home_form is None or away_form is None:
        return None
    if not (_finite(home_form) and _finite(away_form)) or max(abs(home_form), abs(away_form)) > MAX_ABS_FORM:
        return None
    home_factor, away_factor = _factors(float(home_form), float(away_form))
    return {"version": VERSION, "home_form": float(home_form), "away_form": float(away_form),
            "home_factor": home_factor, "away_factor": away_factor}


def form_strength_factors(annotation: Any) -> Optional[tuple[float, float]]:
    """Verified factors of an unchanged annotation; anything else is None (fail closed)."""
    if not isinstance(annotation, dict) or set(annotation) != ANNOTATION_KEYS:
        return None
    if annotation["version"] != VERSION:
        return None
    values = [annotation[key] for key in ("home_form", "away_form", "home_factor", "away_factor")]
    if not all(_finite(value) for value in values):
        return None
    home_form, away_form, home_factor, away_factor = (float(value) for value in values)
    if max(abs(home_form), abs(away_form)) > MAX_ABS_FORM:
        return None
    expected = _factors(home_form, away_form)
    if not (math.isclose(home_factor, expected[0], rel_tol=0, abs_tol=1e-12)
            and math.isclose(away_factor, expected[1], rel_tol=0, abs_tol=1e-12)):
        return None
    return home_factor, away_factor
