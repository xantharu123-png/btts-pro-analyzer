"""UEFA league strength for the cross-competition (home-league transfer) football model.

Plan 2026-11-05, step 1. In a Champions/Europa/Conference League game without enough UEFA history
the live model takes each team's goals from its own domestic league and plays them against each
other one to one. A Premier League side and a Kazakh side then look alike. This table corrects the
goal rates with a league factor estimated from the UEFA games themselves.

Fit (``scripts/uefa_league_strength_fit.py``): offset Poisson regression over the live goal rates
of 751 UEFA games (07/2025 to 04.11.2026), ridge prior tau 0.3, half-life 365 days:
    lambda_home' = lambda_home * exp(HOME_OFFSET + s[home league] - s[away league])
    lambda_away' = lambda_away * exp(AWAY_OFFSET + s[away league] - s[home league])
Walk-forward test on 551 games (each matchday fitted only on earlier games): goal log-likelihood
+0.136 per game (SE 0.033), 1X2 log loss 1.031 -> 0.939, no calibration band worse.

A league without an estimate gets no factor; that game stays without a validated transfer model.
Pure arithmetic, no I/O.
"""
from __future__ import annotations

import math
from typing import Any, Optional

VERSION = "uefa-league-strength-v1-20261104"
HOME_OFFSET = 0.066
AWAY_OFFSET = -0.085
STRENGTHS: dict[int, float] = {
    39: 0.614,  # England / Premier League, 127 team games
    140: 0.394,  # Spain / La Liga, 114 team games
    78: 0.357,  # Germany / Bundesliga, 96 team games
    61: 0.324,  # France / Ligue 1, 94 team games
    94: 0.307,  # Portugal / Primeira Liga, 75 team games
    135: 0.294,  # Italy / Serie A, 85 team games
    144: 0.248,  # Belgium / Jupiler Pro League, 61 team games
    119: 0.183,  # Denmark / Superliga, 52 team games
    203: 0.127,  # Turkey / Süper Lig, 53 team games
    197: 0.113,  # Greece / Super League 1, 66 team games
    103: 0.092,  # Norway / Eliteserien, 56 team games
    271: 0.047,  # Hungary / NB I, 32 team games
    218: 0.044,  # Austria / Bundesliga, 45 team games
    88: 0.036,  # Netherlands / Eredivisie, 71 team games
    419: 0.002,  # Azerbaijan / Premyer Liqa, 26 team games
    318: -0.049,  # Cyprus / 1. Division, 29 team games
    333: -0.065,  # Ukraine / Premier League, 17 team games
    106: -0.070,  # Poland / Ekstraklasa, 32 team games
    345: -0.074,  # Czech-Republic / Czech Liga, 45 team games
    207: -0.106,  # Switzerland / Super League, 41 team games
    383: -0.129,  # Israel / Ligat Ha'al, 32 team games
    172: -0.158,  # Bulgaria / First League, 33 team games
    286: -0.172,  # Serbia / Super Liga, 28 team games
    210: -0.183,  # Croatia / HNL, 30 team games
    179: -0.198,  # Scotland / Premiership, 47 team games
    283: -0.209,  # Romania / Liga I, 22 team games
    244: -0.254,  # Finland / Veikkausliiga, 18 team games
    113: -0.290,  # Sweden / Allsvenskan, 26 team games
    164: -0.377,  # Iceland / Úrvalsdeild, 13 team games
    332: -0.418,  # Slovakia / Super Liga, 16 team games
    389: -0.430,  # Kazakhstan / Premier League, 20 team games
}
ANNOTATION_KEYS = frozenset({"version", "home_league_id", "away_league_id", "home_factor", "away_factor"})


def _league_id(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _factors(home_league_id: int, away_league_id: int) -> Optional[tuple[float, float]]:
    home, away = STRENGTHS.get(home_league_id), STRENGTHS.get(away_league_id)
    if home is None or away is None:
        return None
    gap = home - away
    return math.exp(HOME_OFFSET + gap), math.exp(AWAY_OFFSET - gap)


def league_strength_annotation(home_league_id: Any, away_league_id: Any) -> Optional[dict[str, Any]]:
    """Fixture annotation for two domestic source leagues, or None if one has no estimate."""
    home, away = _league_id(home_league_id), _league_id(away_league_id)
    if home is None or away is None:
        return None
    factors = _factors(home, away)
    if factors is None:
        return None
    return {"version": VERSION, "home_league_id": home, "away_league_id": away,
            "home_factor": factors[0], "away_factor": factors[1]}


def league_strength_factors(annotation: Any) -> Optional[tuple[float, float]]:
    """Verified (home, away) rate factors of an annotation; None for anything not built here."""
    if not isinstance(annotation, dict) or set(annotation) != ANNOTATION_KEYS:
        return None
    if annotation["version"] != VERSION:
        return None
    home, away = _league_id(annotation["home_league_id"]), _league_id(annotation["away_league_id"])
    if home is None or away is None:
        return None
    factors = _factors(home, away)
    if factors is None:
        return None
    for stated, expected in zip((annotation["home_factor"], annotation["away_factor"]), factors):
        if (isinstance(stated, bool) or not isinstance(stated, (int, float)) or not math.isfinite(stated)
                or not math.isclose(float(stated), expected, rel_tol=0.0, abs_tol=1e-12)):
            return None
    return factors
