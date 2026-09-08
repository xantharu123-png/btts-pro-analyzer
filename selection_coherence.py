"""Choose a logically coherent consumer view without changing model candidates.

This is presentation selection, not a probability, price, eligibility, or ticket
rule. The caller owns the price-neutral model ranking and supplies its preferred
primary rows. Apply this once to the complete pool, before pagination or splitting
cards into sections. Returned entries are the original objects in original order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from functools import lru_cache
import json
import math
import unicodedata
from typing import Any, TypeVar

from challenge_engine import MARKET_BY_KEY, MARKET_SPECS, market_outcome


_T = TypeVar("_T")
_GOAL_KINDS = frozenset({"result", "double_chance", "btts", "total", "team_total", "team_range", "result_total", "mixed_or"})
_DOMAINS = {**{kind: "goals" for kind in _GOAL_KINDS}, "corner_total": "corners", "team_corners": "corners", "yellow_total": "yellow", "team_yellow": "yellow"}


def _get(row: Any, name: str) -> Any:
    return row.get(name) if isinstance(row, Mapping) else getattr(row, name, None)


def _text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).strip().casefold().split())


def _sport(row: Any) -> str:
    name = _text(_get(row, "sport"))
    aliases = {"fußball": "football", "fussball": "football", "soccer": "football", "eishockey": "ice_hockey", "ice hockey": "ice_hockey", "e-sport": "esports", "e-sports": "esports", "esport": "esports"}
    if name:
        return aliases.get(name, name)
    # ChallengeCandidate is football-only and has no sport field.
    return "football" if _get(row, "fixture_id") is not None else "unknown"


def _native_id(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value) if value > 0 else ""
    if isinstance(value, str) and value.strip() and value.strip() != "0":
        return value.strip()
    return ""


def _pair(row: Any) -> tuple[str, str] | None:
    """Exact role-bound names; no fuzzy joins or parsing of display labels."""
    for a, b in (("home_team", "away_team"), ("competitor_a", "competitor_b")):
        pair = (_text(_get(row, a)), _text(_get(row, b)))
        if all(pair) and pair[0] != pair[1]:
            return pair
    return None


def _role_binding(row: Any) -> tuple[str, str, str] | None:
    """Stable participant IDs outrank mutable labels; partial IDs stay unknown."""
    for a, b in (("home_team_id", "away_team_id"), ("competitor_a_id", "competitor_b_id")):
        raw = (_get(row, a), _get(row, b))
        if any(value is not None for value in raw):
            ids = (_native_id(raw[0]), _native_id(raw[1]))
            if all(ids) and ids[0] != ids[1]:
                return "ids", *ids
            return "invalid", "", ""
    names = _pair(row)
    return ("names", *names) if names else None


def _kickoff(row: Any) -> str:
    for name in ("scheduled_start", "kickoff", "scheduled_start_utc"):
        value = _get(row, name)
        if not isinstance(value, (str, datetime)):
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
        except (ValueError, OverflowError):
            continue
    return ""


def consumer_event_identity(row: Any) -> str:
    """Identify an event, never a priced selection or a display date alone.

    Native IDs keep one event together across schedule revisions. Provider IDs
    are namespaced by the actual fixture source, not by an odds-provider ID.
    Legacy fallback requires the complete canonical UTC kickoff and participants
    (or the exact event label). Unidentifiable rows share a conservative bucket;
    they cannot be certified as compatible extra selections.
    """
    sport = _sport(row)
    fixture = _native_id(_get(row, "fixture_id"))
    if fixture:
        return json.dumps([sport, "fixture", fixture], ensure_ascii=False)
    provider = _text(_get(row, "fixture_source"))
    event = _native_id(_get(row, "provider_event_id"))
    if provider and event:
        return json.dumps([sport, "provider", provider, event], ensure_ascii=False)
    kickoff = _kickoff(row)
    binding = _role_binding(row)
    if kickoff and binding and binding[0] == "ids":
        return json.dumps([sport, "participant_ids", provider, sorted(binding[1:]), kickoff], ensure_ascii=False)
    pair = _pair(row)
    if kickoff and pair:
        return json.dumps([sport, "participants", sorted(pair), kickoff], ensure_ascii=False)
    label = _text(_get(row, "event_label"))
    if kickoff and label:
        return json.dumps([sport, "label", label, kickoff], ensure_ascii=False)
    return f"unresolved:{sport}"


def _identity_tier(row: Any) -> int:
    if _native_id(_get(row, "fixture_id")):
        return 3
    if _text(_get(row, "fixture_source")) and _native_id(_get(row, "provider_event_id")):
        return 2
    binding = _role_binding(row)
    if binding and binding[0] == "ids" and _kickoff(row):
        return 1
    return 0


def _exact_event_signatures(row: Any) -> tuple[tuple[Any, ...], ...]:
    """Recognize only exact ambiguity, never manufacture a native event join."""
    kickoff = _kickoff(row)
    if not kickoff:
        return ()
    sport = _sport(row)
    signatures: list[tuple[Any, ...]] = []
    pair = _pair(row)
    if pair:
        signatures.append((sport, kickoff, "names", *sorted(pair)))
    binding = _role_binding(row)
    if binding and binding[0] == "ids":
        signatures.append((sport, kickoff, "ids", _text(_get(row, "fixture_source")), *sorted(binding[1:])))
    label = _text(_get(row, "event_label"))
    if label:
        signatures.append((sport, kickoff, "label", label))
    return tuple(signatures)


@lru_cache(maxsize=1)
def _count_masks() -> dict[tuple[str, bool], tuple[str, int]]:
    """Exact finite witnesses for all configured count predicates.

    This grid is not a probability truncation. For each domain let B be greater
    than every configured individual/total boundary. Any count above B can be
    represented by B or B+1 while preserving home/away ordering, equality, and
    all boundary predicates. Values at or below the greatest boundary stay
    exact. Consequently every possible truth vector has a representative here,
    including arbitrarily high counts. Domains are logically separate; this
    makes no claim of statistical independence.
    """
    maxima: dict[str, float] = {}
    for spec in MARKET_SPECS:
        domain = _DOMAINS.get(spec.kind)
        if domain:
            boundaries = [float(v) for v in (spec.threshold, spec.low, spec.high) if v is not None]
            maxima[domain] = max([maxima.get(domain, 1.0), *boundaries])
    masks: dict[tuple[str, bool], tuple[str, int]] = {}
    for spec in MARKET_SPECS:
        domain = _DOMAINS.get(spec.kind)
        if domain is None:
            continue
        cap = math.floor(maxima[domain]) + 2
        counts = [(h, a) for h in range(cap + 1) for a in range(cap + 1)]
        for reverse in (False, True):
            mask = 0
            for index, (home, away) in enumerate(counts):
                won = market_outcome(spec, away, home) if reverse else market_outcome(spec, home, away)
                if won:
                    mask |= 1 << index
            masks[(spec.key, reverse)] = (domain, mask)
    return masks


def _constraint(row: Any) -> tuple[str, Any] | None:
    key = str(_get(row, "market_key") or "").strip().upper()
    pair = _pair(row)
    binding = _role_binding(row)
    if binding and binding[0] == "invalid":
        return None
    reverse = binding is not None and binding[1] > binding[2]
    if _sport(row) == "football" and key in MARKET_BY_KEY:
        return _count_masks().get((key, reverse))
    if key == "H2H" and pair:
        selected = _text(_get(row, "selected_competitor"))
        if selected in pair:
            if _sport(row) == "football":
                result = "RESULT_HOME" if selected == pair[0] else "RESULT_AWAY"
                return _count_masks()[(result, reverse)]
            winner = binding[1] if selected == pair[0] else binding[2]
            return "winner", frozenset({(binding[0], winner)})
    return None


def select_coherent_forecasts(rows: Iterable[_T], *, preferred: Iterable[_T] = ()) -> list[_T]:
    """Return an ordered, jointly satisfiable consumer subset of ``rows``.

    The first preferred row per event anchors that event. An external preferred
    row constrains the subset without being inserted. Other rows are admitted in
    original order only if the intersection of ALL accepted predicates remains
    nonempty. This catches contradictions that pairwise comparisons miss.
    Unknown semantics may be a primary, but compatibility with extras is never
    invented. An exact full-time/name alias with weaker identity than another
    row is withheld as an unproven standalone extra, even if it appeared first
    or was preferred. Distinct equal-tier native IDs are NEVER merged. This is
    presentation-only: no model/probability/evidence/price field is inspected.
    """
    pool = list(rows)
    anchors = list(preferred)
    # First occurrence by identity, never dataclass equality (which may include
    # prices). Anchor lookup must stay linear for the complete multi-sport pool.
    first_index: dict[int, int] = {}
    for index, row in enumerate(pool):
        first_index.setdefault(id(row), index)
    unique_rows = {id(row): row for row in (*pool, *anchors)}
    event_ids = {token: consumer_event_identity(row) for token, row in unique_rows.items()}
    aliases = {token: (_identity_tier(row), _exact_event_signatures(row)) for token, row in unique_rows.items()}
    strongest: dict[tuple[Any, ...], int] = {}
    for tier, signatures in aliases.values():
        for signature in signatures:
            strongest[signature] = max(strongest.get(signature, tier), tier)
    # Merely suppress the ambiguous weaker presentation row. There is no native
    # ID rewrite, fuzzy event merge, or ranking of different strong-ID events.
    withheld = {token for token, (tier, signatures) in aliases.items() if any(strongest[signature] > tier for signature in signatures)}
    accepted: set[int] = set()
    states: dict[str, dict[str, Any] | None] = {}
    seen: dict[str, set[tuple[str, Any]]] = {}
    bindings: dict[str, tuple[str, ...] | None] = {}

    def admit(row: _T) -> bool:
        if id(row) in withheld:
            return False
        event = event_ids[id(row)]
        raw_binding = _role_binding(row)
        binding = (raw_binding[0], *sorted(raw_binding[1:])) if raw_binding else None
        constraint = None if event.startswith("unresolved:") else _constraint(row)
        if event not in states:
            states[event] = None if constraint is None else {constraint[0]: constraint[1]}
            seen[event] = set() if constraint is None else {constraint}
            bindings[event] = binding
            return True
        state = states[event]
        if bindings[event] != binding or state is None or constraint is None or constraint in seen[event]:
            return False
        domain, mask = constraint
        intersection = state.get(domain, mask) & mask
        if not intersection:
            return False
        state[domain] = intersection
        seen[event].add(constraint)
        return True

    anchored: set[str] = set()
    for anchor in anchors:
        event = event_ids[id(anchor)]
        if id(anchor) in withheld or event in anchored:
            continue
        anchored.add(event)
        admit(anchor)
        index = first_index.get(id(anchor))
        if index is not None:
            accepted.add(index)
    for index, row in enumerate(pool):
        if index not in accepted and admit(row):
            accepted.add(index)
    return [row for index, row in enumerate(pool) if index in accepted]


__all__ = ["consumer_event_identity", "select_coherent_forecasts"]
