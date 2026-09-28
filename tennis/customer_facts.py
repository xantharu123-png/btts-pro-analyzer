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
    if (_instant(getattr(prediction, "modeled_at", None)) is None
            or not isinstance(getattr(prediction, "context_evidence", None), dict)):
        return
    from .cached_results import cached_match_statistics
    cached = cached_match_statistics(prediction.player_a, prediction.player_b,
        surface=prediction.surface, tour=tour, as_of=prediction.modeled_at)
    if cached:
        prediction.context_evidence['match_statistics'] = cached
        return
    statistics = build_match_statistics(prediction.player_a, prediction.player_b, history,
        surface=prediction.surface, tour=tour, as_of=prediction.modeled_at)
    if any(item.get("recent") for item in statistics["players"].values()):
        prediction.context_evidence["match_statistics"] = statistics


def customer_statistics_context(context, player_a, player_b, *, modeled_at):
    """Optional old-card projection using only a cache predating that forecast."""
    if not isinstance(context, Mapping):
        return context
    raw, inputs = context.get('match_statistics'), context.get('model_inputs')
    if isinstance(raw, Mapping) and raw.get('schema') == 'tennis-customer-results-v2':
        return context
    cutoff = _instant(modeled_at)
    players = context.get('players')
    if (cutoff is None or _instant(context.get('observed_at')) != cutoff
            or not isinstance(inputs, Mapping) or not isinstance(players, Mapping)
            or any(not isinstance(players.get(side), Mapping) or players[side].get('player') != name
                   for side, name in (('a', player_a), ('b', player_b)))):
        return context
    from .cached_results import cached_match_statistics
    cached = cached_match_statistics(player_a, player_b, surface=inputs.get('surface'),
        tour=inputs.get('model_tour_scope') or (raw.get('tour') if isinstance(raw, Mapping) else None), as_of=cutoff)
    # Do not replace a fuller live-result sample with a smaller cached one.
    prior_counts = {}
    if isinstance(raw, Mapping):
        old_players = raw.get('players', {})
        if not isinstance(old_players, Mapping):
            return context
        for side in ('a', 'b'):
            entry = old_players.get(side, {})
            if not isinstance(entry, Mapping) or not isinstance(entry.get('surface', {}), Mapping):
                return context
            count = entry.get('surface', {}).get('matches', 0)
            if type(count) is not int or not 0 <= count <= MAX_MATCHES:
                return context
            prior_counts[side] = count
    if cached and all(len(cached['players'][side]['surface_results']) >= prior_counts.get(side, 0) for side in ('a', 'b')):
        return {**context, 'match_statistics': cached}
    return context


def _result_details(sample, *, cutoff):
    if not isinstance(sample, list) or not 1 <= len(sample) <= MAX_MATCHES:
        return ()
    details, previous = [], cutoff.date()
    for row in sample:
        if not isinstance(row, Mapping) or type(row.get('won')) is not bool:
            return ()
        try:
            day = date.fromisoformat(row['date'])
        except (KeyError, TypeError, ValueError):
            return ()
        if not cutoff.date()-timedelta(days=365) <= day <= previous:
            return ()
        opponent, score, rank = row.get('opponent'), row.get('score'), row.get('opponent_rank')
        if (not isinstance(opponent, str) or not 0 < len(opponent) <= 120
                or any(ord(c) < 32 for c in opponent) or not isinstance(score, str)
                or score not in {'2:0', '2:1', '3:0', '3:1', '3:2', '0:2', '1:2', '0:3', '1:3', '2:3'}
                or (rank is not None and (type(rank) is not int or not 1 <= rank <= 3000))
                or row.get('date_kind') not in ('tournament_date', 'result_date')):
            return ()
        label = 'Turnierdatum' if row['date_kind'] == 'tournament_date' else 'Ergebnisdatum'
        quality = f' · damaliger Rang {rank}' if rank is not None else ''
        details.append(f'{label} {day:%d.%m.%Y}: {"Sieg" if row["won"] else "Niederlage"} {score} gegen {opponent}{quality}')
        previous = day
    return tuple(details)


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
    context = customer_statistics_context(context, player_a, player_b, modeled_at=modeled_at)
    inputs, raw = context.get("model_inputs"), context.get("match_statistics")
    cutoff = _instant(modeled_at)
    if (not isinstance(inputs, Mapping) or not isinstance(raw, Mapping) or cutoff is None
            or _instant(context.get("observed_at")) != cutoff
            or raw.get("schema") not in ("tennis-customer-results-v1", "tennis-customer-results-v2")
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
        v2 = raw['schema'] == 'tennis-customer-results-v2'
        if not cutoff.date() - timedelta(days=365 if v2 else WINDOW_DAYS) <= first <= last <= cutoff.date():
            continue
        surface = raw.get("surface")
        if group == "surface" and (not isinstance(surface, str) or surface not in SURFACE_NAMES):
            continue
        label = SURFACE_NAMES[surface] if group == "surface" else "Alle Beläge"
        scope = f"{label} · {count} erfasste Spiele · {first:%d.%m.%Y}–{last:%d.%m.%Y}"
        value = f"{wins}/{count} Siege" + (" · alle Beläge" if group == "recent" else "")
        if v2:
            results = entry.get('surface_results')
            if (not _result_details(results, cutoff=cutoff) or len(results) != count
                    or sum(row['won'] for row in results) != wins
                    or results[-1]['date'] != sample['from'] or results[0]['date'] != sample['through']):
                continue
            windows = [f'{sum(row["won"] for row in results[:n])}/{n}' for n in (5, 10) if count >= n]
            value = ' · '.join(windows)+' Siege' if windows else f'{wins}/{count} Siege'
            scope = f'{label} · letzte {"5 / 10" if count >= 10 else str(count)} erfasste Spiele · {first:%d.%m.%Y}–{last:%d.%m.%Y}'
            if raw.get('coverage') == 'completed_knockout_rounds':
                scope += ' · K.-o.-Runden einschließlich Qualifikation'
        facts.append((player, value, scope))
    return tuple(facts)


def customer_record_details(context, player_a, player_b, *, modeled_at):
    context = customer_statistics_context(context, player_a, player_b, modeled_at=modeled_at)
    facts = customer_record_facts(context, player_a, player_b, modeled_at=modeled_at)
    raw = context.get('match_statistics') if isinstance(context, Mapping) else None
    if not isinstance(raw, Mapping) or raw.get('schema') != 'tennis-customer-results-v2' or not isinstance(raw.get('players'), Mapping):
        return {}
    allowed = {row[0] for row in facts}
    return {entry['player']: _result_details(entry.get('surface_results'), cutoff=_instant(modeled_at))
            for entry in raw['players'].values() if isinstance(entry, Mapping) and entry.get('player') in allowed}


def format_customer_records(context, player_a, player_b, *, modeled_at):
    return tuple(f"{player}: {value} ({scope})." for player, value, scope in
                 customer_record_facts(context, player_a, player_b, modeled_at=modeled_at))
