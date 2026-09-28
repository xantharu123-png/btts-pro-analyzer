"""Compact, factual explanation of the surface-Elo input to a tennis forecast."""

from __future__ import annotations

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
    evidence = {
        "surface": surface,
        "players": {
            "a": {"matches": count_a, "elo": round(table.rating(a), 1) if count_a else None},
            "b": {"matches": count_b, "elo": round(table.rating(b), 1) if count_b else None},
        },
        "surface_elo_applied": min(count_a, count_b) >= MIN_SURFACE_ELO_MATCHES,
        "stats_through": state.stats_through,
    }
    # Detached display evidence: use the same state and cutoff, never alter or
    # rerun prediction. The serve contribution is recovered from its mixture.
    from .workload import _instant
    cutoff = _instant(prediction.modeled_at)
    if cutoff is not None:
        p_elo = state.elo.win_probability(a, b, surface if inputs.get("surface_in_model") else None)
        matchup = {"p_elo_a": p_elo, "p_a_cal": prediction.p_a_cal}
        weight = state.serve_weight
        if inputs.get("serve_in_model") is True and 0 < weight <= 1:
            p_serve = (prediction.p_a_raw - (1-weight)*p_elo) / weight
            if 0 <= p_serve <= 1:
                hold_a, hold_b = state.serve.expected_hold_probabilities(
                    a, b, surface, as_of=cutoff, indoor=inputs.get("indoor"))
                matchup.update(p_serve_a=p_serve, hold_a=hold_a, hold_b=hold_b,
                               p_serve_rounding_error=.00005/weight)
        evidence["matchup"] = matchup
    return evidence


def format_surface_evidence(
    evidence: object, player_a: str, player_b: str,
) -> str | None:
    """Show the real surface sample, not internal ratings or an invented record."""

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
            parts.append(f"{name} {count} erfasste Spiele")
        elif rating is None:
            parts.append(f"{name} keine erfassten Spiele")
        else:
            return None
        counts.append(count)
    if applied != (min(counts) >= MIN_SURFACE_ELO_MATCHES):
        return None
    return f"{_SURFACE_NAMES[surface]}: {' · '.join(parts)}"


def tennis_choice_reason(context, player_a, player_b, selected, probability, *, modeled_at,
                         market_key="H2H"):
    """Explain winner direction, not a invented reason for another contract."""
    from .customer_facts import customer_record_facts, customer_statistics_context
    from .workload import _instant
    if (not isinstance(context, Mapping) or selected not in (player_a, player_b)
            or player_a == player_b or _instant(modeled_at) is None
            or _instant(context.get("observed_at")) != _instant(modeled_at)):
        return "", ""
    players = context.get("players")
    if not isinstance(players, Mapping) or any(
        not isinstance(players.get(side), Mapping) or players[side].get("player") != name
        for side, name in (("a", player_a), ("b", player_b))
    ):
        return "", ""
    context = customer_statistics_context(context, player_a, player_b, modeled_at=modeled_at)
    inputs, evidence = context.get("model_inputs"), context.get("surface_evidence")
    if (not isinstance(inputs, Mapping) or not isinstance(evidence, Mapping)
            or evidence.get("surface") != inputs.get("surface")
            or not format_surface_evidence(evidence, player_a, player_b)
            or market_key not in {"H2H", "Match Winner", "MatchWinner", "match_winner"}):
        return "", ""
    own, other = ("a", "b") if selected == player_a else ("b", "a")
    opponent = player_b if own == "a" else player_a
    matchup = evidence.get("matchup")
    long_probability, serve_probability = None, None
    if isinstance(matchup, Mapping):
        p_cal, p_elo, p_serve = (matchup.get(key) for key in ("p_a_cal", "p_elo_a", "p_serve_a"))
        valid = lambda value: type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
        if (not valid(p_cal) or not valid(p_elo) or not valid(probability)
                or not math.isclose(probability, p_cal if own == "a" else 1-p_cal, abs_tol=.00011)):
            return "", ""
        long_probability = p_elo if own == "a" else 1-p_elo
        error = matchup.get('p_serve_rounding_error', .0005)
        if (inputs.get("serve_in_model") is True and valid(p_serve)
                and type(error) in (int, float) and math.isfinite(error) and 0 <= error < .1
                and abs(p_serve-.5) > error+1e-10):
            serve_probability = p_serve if own == "a" else 1-p_serve
    elif evidence.get("surface_elo_applied") is True:
        # Legacy cards lack the mixture but retain the actual surface comparison.
        left, right = (evidence["players"][side]["elo"] for side in (own, other))
        long_probability = .5 if left == right else (.51 if left > right else .49)
    reason, counter = "", ""
    label = _SURFACE_NAMES[evidence["surface"]]
    if long_probability is not None and long_probability > .5:
        reason = f"{selected}: Die längerfristigen Ergebnisse sprechen für diese Auswahl"
        reason += f" auf {label}." if evidence.get("surface_elo_applied") else "."
    elif long_probability is not None and long_probability < .5:
        reason = f"{selected} ist hier die Außenseiter-Auswahl."
        counter = f"Die längerfristigen Ergebnisse sprechen eher für {opponent}."
    if serve_probability is not None and serve_probability > .5:
        reason += " Die Aufschlag- und Rückschlagdaten sprechen ebenfalls dafür." if reason and long_probability > .5 else " Die Aufschlag- und Rückschlagdaten sprechen für diese Auswahl."
    elif serve_probability is not None and serve_probability < .5:
        counter += f" Die Aufschlag- und Rückschlagdaten sprechen eher für {opponent}."
    records = customer_record_facts(context, player_a, player_b, modeled_at=modeled_at)
    raw_statistics = context.get('match_statistics')
    samples = raw_statistics.get('players', {}) if isinstance(raw_statistics, Mapping) else {}
    if len(records) == 2:
        entries = {}
        for side, entry in samples.items():
            if isinstance(entry, Mapping):
                entries[side] = entry.get("surface", entry.get("recent", {}))
        results = {side: samples[side].get('surface_results') for side in (own, other) if side in samples}
        if raw_statistics.get('schema') == 'tennis-customer-results-v2' and all(isinstance(results.get(side), list) and len(results[side]) >= 5 for side in (own, other)):
            comparisons = [(n, sum(row['won'] for row in results[other][:n]), sum(row['won'] for row in results[own][:n]))
                for n in (5, 10) if all(len(results[side]) >= n for side in (own, other))]
            better = next(((n, other_wins, own_wins) for n, other_wins, own_wins in comparisons if other_wins > own_wins), None)
            if better:
                n, other_wins, own_wins = better
                counter += f' In den letzten {n} erfassten Belagsspielen hat {opponent} mehr Siege ({other_wins}/{n} gegenüber {selected}: {own_wins}/{n}).'
            better_recent = False  # The precisely named window is already shown.
        else:
            better_recent = (own in entries and other in entries and
                entries[other]["wins"] / entries[other]["matches"] > entries[own]["wins"] / entries[own]["matches"])
        if better_recent:
            opponent_record = next(item for item in records if item[0] == opponent)
            counter += f" Zuletzt hat {opponent} die bessere erfasste Bilanz ({opponent_record[1]}); sie allein entscheidet diesen Vergleich nicht."
    return reason.strip(), counter.strip()
