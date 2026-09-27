"""Small, frozen result summaries for customers, never inferred from ratings.

Only already observed completed matches are used. The observed history is not
a complete career record, so copy always names the sample and its date range.
No network, model adjustment, database migration or extra history copies.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Mapping

from .data_loader import normalize_player_name
from .workload import _instant

SURFACE_NAMES = {"Hard": "Hartplatz", "Clay": "Sand", "Grass": "Rasen", "Carpet": "Teppich"}
WINDOW_DAYS = 90
MAX_MATCHES = 10


def attach_customer_statistics(prediction, history, *, tour):
    """Freeze presentation facts after prediction, outside the sealed model."""
    if (not history or _instant(getattr(prediction, "modeled_at", None)) is None
            or not isinstance(getattr(prediction, "context_evidence", None), dict)):
        return
    statistics = build_match_statistics(prediction.player_a, prediction.player_b, history,
        surface=prediction.surface, tour=tour, as_of=prediction.modeled_at)
    if any(item.get("recent") for item in statistics["players"].values()):
        prediction.context_evidence["match_statistics"] = statistics


def build_match_statistics(player_a, player_b, history, *, surface, tour, as_of):
    """Summarize up to ten results per player, all known before this forecast."""
    cutoff = _instant(as_of)
    if cutoff is None:
        raise ValueError("statistics cutoff must be aware")
    names = (normalize_player_name(player_a), normalize_player_name(player_b))
    events, conflicts = {}, set()
    for row in history:
        if not isinstance(row, Mapping) or row.get("settled") != 1:
            continue
        if row.get("tour") != tour or row.get("termination") != "normal":
            continue
        participants = tuple(normalize_player_name(str(row.get(f"player_{side}") or "")) for side in ("a", "b"))
        if not all(participants) or participants[0] == participants[1] or not set(names).intersection(participants):
            continue
        start, observed = _instant(row.get("scheduled_start_utc")), _instant(row.get("result_observed_at"))
        if start is None or observed is None or not cutoff - timedelta(days=WINDOW_DAYS) <= start < observed <= cutoff:
            continue
        a, b, best_of = row.get("player_a_sets"), row.get("player_b_sets"), row.get("best_of")
        if any(type(value) is not int for value in (a, b, best_of)) or best_of not in (3, 5):
            continue
        target = best_of // 2 + 1
        if max(a, b) != target or not 0 <= min(a, b) < target:
            continue
        identity = (row.get("fixture_source"), row.get("provider_event_id"))
        if not all(isinstance(value, str) and value.strip() for value in identity):
            continue
        record = (start, tuple(sorted(participants)), participants[0 if a > b else 1], row.get("surface"))
        if identity in events and events[identity] != record:
            conflicts.add(identity)
        events[identity] = record
    # Repeat model versions and exact duplicate events from different sources
    # count once; conflicting results for an event are not a usable statistic.
    matches, clashes = {}, set()
    for identity, record in events.items():
        if identity in conflicts:
            continue
        key = record[:2]
        if key in matches and matches[key] != record:
            clashes.add(key)
        matches[key] = record
    records = sorted((row for key, row in matches.items() if key not in clashes), reverse=True)
    players = {}
    for side, player, name in zip(("a", "b"), (player_a, player_b), names):
        own = [row for row in records if name in row[1]]
        groups = {}
        for label, subset in (("recent", own), ("surface", [r for r in own if r[3] == surface and surface in SURFACE_NAMES])):
            sample = subset[:MAX_MATCHES]
            if sample:
                groups[label] = {"matches": len(sample), "wins": sum(row[2] == name for row in sample),
                    "from": sample[-1][0].date().isoformat(), "through": sample[0][0].date().isoformat()}
        players[side] = {"player": player, **groups}
    return {"schema": "tennis-customer-results-v1", "observed_at": cutoff.isoformat(),
            "surface": surface, "tour": tour, "players": players}


def customer_record_facts(context, player_a, player_b, *, modeled_at):
    """Return (player, compact value, scoped description), or no claim at all."""
    if not isinstance(context, Mapping):
        return ()
    inputs, raw = context.get("model_inputs"), context.get("match_statistics")
    cutoff = _instant(modeled_at)
    if (not isinstance(inputs, Mapping) or not isinstance(raw, Mapping) or cutoff is None
            or _instant(context.get("observed_at")) != cutoff
            or raw.get("schema") != "tennis-customer-results-v1"
            or _instant(raw.get("observed_at")) != cutoff
            or raw.get("surface") != inputs.get("surface")
            or raw.get("tour") not in ("ATP", "WTA")
            or inputs.get("model_tour_scope") in ("ATP", "WTA")
            and raw.get("tour") != inputs["model_tour_scope"]):
        return ()
    players = raw.get("players")
    if not isinstance(players, Mapping) or not isinstance(context.get("players"), Mapping):
        return ()
    facts = []
    for side, player in (("a", player_a), ("b", player_b)):
        entry, original = players.get(side), context["players"].get(side)
        if (not isinstance(entry, Mapping) or not isinstance(original, Mapping)
                or entry.get("player") != player or original.get("player") != player):
            return ()
        group = "surface" if "surface" in entry else "recent"
        sample = entry.get(group)
        if not isinstance(sample, Mapping):
            continue
        count, wins = sample.get("matches"), sample.get("wins")
        if type(count) is not int or type(wins) is not int or not 0 <= wins <= count <= MAX_MATCHES or not count:
            continue
        try:
            first, last = date.fromisoformat(sample["from"]), date.fromisoformat(sample["through"])
        except (KeyError, TypeError, ValueError):
            continue
        if not cutoff.date() - timedelta(days=WINDOW_DAYS) <= first <= last <= cutoff.date():
            continue
        surface = raw.get("surface")
        if group == "surface" and (not isinstance(surface, str) or surface not in SURFACE_NAMES):
            continue
        label = SURFACE_NAMES[surface] if group == "surface" else "Alle Beläge"
        scope = f"{label} · {count} erfasste Spiele · {first:%d.%m.%Y}–{last:%d.%m.%Y}"
        value = f"{wins}/{count} Siege" + (" · alle Beläge" if group == "recent" else "")
        facts.append((player, value, scope))
    return tuple(facts)


def format_customer_records(context, player_a, player_b, *, modeled_at):
    return tuple(f"{player}: {value} ({scope})." for player, value, scope in
                 customer_record_facts(context, player_a, player_b, modeled_at=modeled_at))
