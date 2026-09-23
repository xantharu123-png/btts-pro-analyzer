"""Compact, factual explanation of the surface-Elo input to a tennis forecast."""

from __future__ import annotations

from datetime import date
import math
from typing import Mapping

from .data_loader import resolve_player_name_key


MIN_SURFACE_ELO_MATCHES = 8  # Mirrors the frozen tennis.elo SurfaceElo default.


_SURFACE_NAMES = {
    "Hard": "Hartplatz",
    "Clay": "Sand",
    "Grass": "Rasen",
    "Carpet": "Teppich",
}


def build_surface_evidence(state: object, prediction: object) -> dict | None:
    """Freeze the model's actual surface table after, not inside, prediction."""

    context = getattr(prediction, "context_evidence", None)
    inputs = context.get("model_inputs") if isinstance(context, dict) else None
    surface = inputs.get("surface") if isinstance(inputs, dict) else None
    if not isinstance(surface, str) or surface not in _SURFACE_NAMES:
        return None
    known = state.elo.known_players()
    a = resolve_player_name_key(prediction.player_a, known)
    b = resolve_player_name_key(prediction.player_b, known)
    if a not in known or b not in known:
        return None
    table = state.elo.by_surface[surface]
    count_a, count_b = table.matches(a), table.matches(b)
    return {
        "surface": surface,
        "players": {
            "a": {"matches": count_a, "elo": round(table.rating(a), 1) if count_a else None},
            "b": {"matches": count_b, "elo": round(table.rating(b), 1) if count_b else None},
        },
        "surface_elo_applied": min(count_a, count_b) >= MIN_SURFACE_ELO_MATCHES,
        "stats_through": state.stats_through,
    }


def format_surface_evidence(
    evidence: object, player_a: str, player_b: str,
) -> str | None:
    """Describe frozen model inputs, never infer a win rate from Elo."""

    if not isinstance(evidence, Mapping):
        return None
    surface = evidence.get("surface")
    players = evidence.get("players")
    applied = evidence.get("surface_elo_applied")
    if not isinstance(surface, str) or surface not in _SURFACE_NAMES or not isinstance(players, Mapping):
        return None
    if not isinstance(applied, bool):
        return None
    parts = []
    counts = []
    for side, name in (("a", player_a), ("b", player_b)):
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 120
            or any(ord(character) < 32 for character in name)
        ):
            return None
        item = players.get(side)
        if not isinstance(item, Mapping):
            return None
        count = item.get("matches")
        rating = item.get("elo")
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 100_000:
            return None
        if count:
            if (
                isinstance(rating, bool)
                or not isinstance(rating, (int, float))
                or not math.isfinite(rating)
            ):
                return None
            parts.append(f"{name} {rating:,.0f} Elo ({count} Spiele)".replace(",", "."))
        elif rating is None:
            parts.append(f"{name} keine Belagspiele")
        else:
            return None
        counts.append(count)
    if applied != (min(counts) >= MIN_SURFACE_ELO_MATCHES):
        return None
    use = "Belag-Elo berücksichtigt" if applied else "Gesamt-Elo verwendet"
    through = evidence.get("stats_through")
    date_note = ""
    if isinstance(through, str):
        try:
            date_note = f" · Daten bis {date.fromisoformat(through):%d.%m.%Y}"
        except ValueError:
            pass
    return f"{_SURFACE_NAMES[surface]}: {' · '.join(parts)} · {use}{date_note}"
