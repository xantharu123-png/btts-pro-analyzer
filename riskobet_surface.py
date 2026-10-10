"""Pure, price-neutral presentation helpers for the RisikoBet page.

The module deliberately owns no Streamlit state and performs no provider work.
It maps an immutable :class:`riskobet_domain.RiskCandidate` to escaped consumer
markup. Price observations never change model probabilities or ranking.
The user floor removes known offers below 1.20 after whole-event coherence.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import math
import re
from typing import TYPE_CHECKING, Iterable, Mapping, Optional
import unicodedata
from betting_math import odds_below_publication_floor
from zoneinfo import ZoneInfo

if TYPE_CHECKING:  # pragma: no cover - the runtime accepts the frozen contract.
    from riskobet_domain import RiskCandidate


SPORT_FILTERS = (
    "Alle",
    "Fußball",
    "Tennis",
    "Basketball",
    "Eishockey",
    "Cricket",
    "E-Sport",
)

_SPORT_LABELS = {
    "football": "Fußball",
    "tennis": "Tennis",
    "basketball": "Basketball",
    "ice_hockey": "Eishockey",
    "cricket": "Cricket",
    "esports": "E-Sport",
}
_FILTER_TO_SPORT = {
    label: key for key, label in _SPORT_LABELS.items()
}
_ZURICH_TZ = ZoneInfo("Europe/Zurich")
_SIMPLE_MARKET_KEYS = frozenset(
    {
        "underdog_team_over_0_5_90_minutes",
        "plus_1_5_sets",
        "at_least_one_map",
    }
)

_EVIDENCE_COPY = {
    # These are consumer labels, not the internal lifecycle enum names.  In
    # particular, SHADOW must never look like a quality seal: it still means
    # that the model has not earned its version-bound validation evidence.
    "RESEARCH": ("Frühe Analyse · noch nicht historisch geprüft", "muted"),
    "SHADOW": ("Im Test · noch nicht historisch bestätigt", "warning"),
    "VALIDATED": ("Historisch validiert", "positive"),
}
_CONTEXT_COPY = {
    "FRESH": ("Kontext frisch", "positive"),
    "PARTIAL": ("Kontext teilweise offen", "warning"),
    "STALE": ("Kontext veraltet", "warning"),
    "OPEN": ("Kontext offen", "muted"),
}
_PRICE_COPY = {
    "AVAILABLE": ("Quote beobachtet", "neutral"),
    "OBSERVED": ("Quote abgerufen", "neutral"),
    "PLAYABLE": ("Preis passend", "positive"),
    "TOO_LOW": ("Quote niedrig", "muted"),
    "BORDERLINE": ("Preis grenzwertig", "warning"),
    "THIN": ("Wenige Anbieter", "warning"),
    "STALE": ("Quote veraltet", "warning"),
    "UNAVAILABLE": ("Quote fehlt", "muted"),
    "OPEN": ("Preis offen", "muted"),
}
_INTERNAL_FACTOR_STATUS_COPY = {
    "passed": "geprüft",
    "neutral": "ohne klaren Einfluss",
    "observed": "vorhanden und geprüft",
    "partial": "nur teilweise verarbeitet",
    "blocked": "spricht gegen diese Auswahl",
    "required_missing": "noch nicht bestätigt",
    "unavailable": "nicht verfügbar",
    "open": "noch offen",
    "stale": "nicht mehr aktuell",
    "missing": "fehlt",
    "failed": "konnte nicht geprüft werden",
    "unknown": "Status unklar",
}
_INTERNAL_FACTOR_STATUS_RE = re.compile(
    r"^(?P<label>[^:\r\n]{1,120}?)\s*:\s*(?P<status>"
    + "|".join(
        re.escape(status)
        for status in sorted(
            _INTERNAL_FACTOR_STATUS_COPY,
            key=len,
            reverse=True,
        )
    )
    + r")\s*[.!]?\s*$",
    flags=re.IGNORECASE,
)
_INTERNAL_FACTOR_STATUS_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<status>"
    + "|".join(
        re.escape(status)
        for status in sorted(
            _INTERNAL_FACTOR_STATUS_COPY,
            key=len,
            reverse=True,
        )
    )
    + r")(?![A-Za-z0-9_])",
    flags=re.IGNORECASE,
)
_PUBLIC_DETAIL_REPLACEMENTS = (
    (re.compile(r'\bSubgraph-Elo\s+\d+(?:[.,]\d+)?\s*/\s*\d+(?:[.,]\d+)?', re.IGNORECASE),
     'Längerfristiger Spielstärkenvergleich'),
    (re.compile(r'Spielstärke-Abstand:\s*\d+(?:[.,]\d+)?\s+Elo-Punkte', re.IGNORECASE),
     'Längerfristiger Spielstärkenvergleich'),
    (re.compile(r"\bRESEARCH\s*:\s*", re.IGNORECASE),
     "Frühe Analyse · noch nicht historisch geprüft: "),
    (
        re.compile(r"\bSHADOW\s*:\s*", re.IGNORECASE),
        "Im Test · noch nicht historisch bestätigt: ",
    ),
    (re.compile(r"\bBeta\(2\s*,\s*2\)-Glättung\b", re.IGNORECASE),
     "vorsichtige Glättung kleiner Stichproben"),
    (re.compile(r"\bDas geglättete Log5-Modell\b", re.IGNORECASE),
     "Das vorsichtige Gegnervergleichsmodell"),
    (re.compile(r"\bLog5-Modell\b", re.IGNORECASE), "Gegnervergleichsmodell"),
    (re.compile(r"\bSubgraph-Elo\b", re.IGNORECASE),
     "Stärkevergleich im relevanten Teilnehmerfeld"),
    (re.compile(r"\bi\.i\.d\.-Mapannahme\b", re.IGNORECASE),
     "Annahme gleichbleibender Mapchancen"),
    (re.compile(r"\beingefrorenen Modellzustand\b", re.IGNORECASE),
     "vor Spielbeginn festgehaltenen Modellstand"),
)
_UNSAFE_TECHNICAL_DETAIL_RE = re.compile(
    r"(?:^|[^A-Za-z0-9])(?:[A-Za-z0-9]+_)*provider(?:_id)?(?:$|[^A-Za-z0-9])"
    r"|(?:^|[^A-Za-z0-9])(?:[A-Za-z0-9]+_)*factor_key(?:$|[^A-Za-z0-9])"
    r"|\b(?:walk[- ]?forward|gate|api-[a-z0-9_-]+)\b"
    r"|\b(?:source|provider)_(?:failed|partial|unavailable)\b"
    r"|(?<![\d.,])\b(?:HTTP\s*)?[45]\d{2}\b",
    flags=re.IGNORECASE,
)
_TECHNICAL_DETAIL_FALLBACK = (
    "Technischer Prüfstatus ist noch nicht nutzerverständlich aufbereitet."
)


@dataclass(frozen=True)
class RiskBetPriceOverlay:
    """One exact candidate-bound price observation.

    This structure intentionally has no model fields.  Repricing a candidate
    can therefore change only the price fragment rendered on its card.
    """

    candidate_id: str
    status: str = "UNAVAILABLE"
    observed_odds: Optional[float] = None
    bookmaker: Optional[str] = None
    observed_at: Optional[str] = None
    below_floor: bool = False
    fetched_at: Optional[str] = None
    checked_at: Optional[str] = None
    price_check_current: bool = False

    def __post_init__(self) -> None:
        candidate_id = str(self.candidate_id or "").strip()
        status = str(self.status or "").strip().upper()
        if not candidate_id:
            raise ValueError("price candidate identity is required")
        if status not in _PRICE_COPY:
            raise ValueError("unsupported RisikoBet price status")
        if not isinstance(self.below_floor, bool):
            raise ValueError('below_floor must be boolean')
        if not isinstance(self.price_check_current, bool):
            raise ValueError('price_check_current must be boolean')
        if self.observed_odds is not None:
            if (
                isinstance(self.observed_odds, bool)
                or not isinstance(self.observed_odds, (int, float))
                or not math.isfinite(float(self.observed_odds))
                or float(self.observed_odds) <= 1.0
            ):
                raise ValueError("observed odds must be a finite decimal quote")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "status", status)


@dataclass(frozen=True)
class RiskBetCard:
    """Immutable, display-ready RisikoBet scenario."""

    candidate_id: str
    event_key: str
    sport_key: str
    sport: str
    competition: str
    scheduled_start_label: str
    event_label: str
    market_key: str
    market: str
    selection: str
    model_probability: Optional[float]
    cautious_probability: Optional[float]
    evidence_code: str
    evidence_label: str
    evidence_tone: str
    context_code: str
    context_label: str
    context_tone: str
    pros: tuple[str, ...]
    cons: tuple[str, ...]
    missing_core_data: tuple[str, ...]
    price_code: str
    price_label: str
    price_tone: str
    observed_odds: Optional[float]
    bookmaker: Optional[str]
    price_observed_at: Optional[str]
    simple_market: bool
    quote_floor_excluded: bool = False
    # Preserve the frozen role/market contract. Display labels and prices must
    # never be used to infer whether two scenarios can win together.
    snapshot_id: str = ""
    selection_key: str = ""
    settlement_contract: Optional[str] = None
    price_check_current: bool = False
    context_check_current: bool = False


@dataclass(frozen=True)
class RiskBetCatalog:
    """At most three featured cards plus flat, compact additional rows."""

    featured: tuple[RiskBetCard, ...]
    additional: tuple[RiskBetCard, ...]

    @property
    def cards(self) -> tuple[RiskBetCard, ...]:
        return self.featured + self.additional


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().upper()


def _token(value: object) -> str:
    normalized = unicodedata.normalize(
        "NFKD", str(value or "").casefold().replace("ß", "ss")
    )
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


def _clean_text(value: object, fallback: str = "–") -> str:
    text = str(value or "").strip()
    return text or fallback


def format_riskobet_public_detail(value: object) -> str:
    """Translate raw model-status summaries into cautious consumer copy.

    Upstream context contracts intentionally persist stable machine values
    such as ``passed`` and ``required_missing``.  Those values remain intact
    in the immutable model snapshot, while every consumer surface uses this
    presentation-only translation.  The wording describes only what was
    observed; it never promotes the candidate's evidence stage.
    """

    raw_text = _clean_text(value, "")
    if not raw_text:
        return ""
    # Already published snapshots retain their immutable original text. Render
    # the known old surface template as sample sizes without internal ratings.
    if re.match(r"^(Hartplatz|Sand|Rasen|Teppich): ", raw_text):
        raw_text = re.sub(r"[\d.,]+ Elo \((\d+) Spiele\)", r"\1 erfasste Spiele", raw_text)
        raw_text = re.sub(r" · (Belag-Elo berücksichtigt|Gesamt-Elo verwendet)(?: · Daten bis .*\Z)?", "", raw_text)
        raw_text = raw_text.replace("keine Belagspiele", "keine erfassten Spiele")
    if _UNSAFE_TECHNICAL_DETAIL_RE.search(raw_text):
        return _TECHNICAL_DETAIL_FALLBACK
    text = raw_text
    for pattern, replacement in _PUBLIC_DETAIL_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    match = _INTERNAL_FACTOR_STATUS_RE.fullmatch(text)
    if match is not None:
        label = match.group("label").strip()
        status = match.group("status").casefold()
        text = f"{label}: {_INTERNAL_FACTOR_STATUS_COPY[status]}"
    else:
        text = _INTERNAL_FACTOR_STATUS_TOKEN_RE.sub(
            lambda item: _INTERNAL_FACTOR_STATUS_COPY[
                item.group("status").casefold()
            ],
            text,
        )
    return text


def format_riskobet_start(value: object) -> str:
    """Render only timezone-aware starts in the product's Zurich timezone."""

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return "–"
    if parsed.tzinfo is None:
        return "–"
    return parsed.astimezone(_ZURICH_TZ).strftime("%d.%m. %H:%M")


def format_riskobet_probability(value: object) -> str:
    """Show absent research probabilities honestly instead of inventing one."""

    if value is None:
        return "offen"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "offen"
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return "offen"
    if number >= 0.9995:
        return "> 99,5 %"
    return f"{number * 100:.1f} %"


def format_riskobet_odds(value: object) -> str:
    if value is None:
        return "–"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "–"
    number = float(value)
    if not math.isfinite(number) or number <= 1.0:
        return "–"
    return f"{number:.2f}"


def _normalise_price(
    candidate_id: str,
    price: object,
) -> RiskBetPriceOverlay:
    if price is None:
        return RiskBetPriceOverlay(candidate_id=candidate_id)
    if isinstance(price, RiskBetPriceOverlay):
        overlay = price
    elif isinstance(price, Mapping):
        overlay = RiskBetPriceOverlay(
            candidate_id=str(price.get("candidate_id") or ""),
            status=str(price.get("status") or "UNAVAILABLE"),
            observed_odds=price.get("observed_odds"),
            bookmaker=price.get("bookmaker"),
            observed_at=price.get("observed_at"),
            below_floor=price.get('below_floor') is True,
            fetched_at=price.get('fetched_at'),
            checked_at=price.get('checked_at'),
            price_check_current=price.get('price_check_current') is True,
        )
    else:
        raise TypeError("price must be a RiskBetPriceOverlay or mapping")
    if overlay.candidate_id != candidate_id:
        raise ValueError("price overlay candidate mismatch")
    return overlay


def _is_simple_market(market_key: object, selection: object) -> bool:
    normalized_key = _token(market_key)
    if normalized_key in _SIMPLE_MARKET_KEYS:
        return True
    token = _token(f"{normalized_key} {selection}")
    patterns = (
        "over_0_5",
        "one_plus_goal",
        "one_plus_set",
        "one_plus_map",
        "at_least_one_goal",
        "at_least_one_set",
        "at_least_one_map",
        "mindestens_ein_tor",
        "mindestens_einen_satz",
        "mindestens_eine_map",
        "1_tor",
        "1_satz",
        "1_map",
    )
    return any(pattern in token for pattern in patterns)


def _current_context_check(candidate, snapshot, now):
    """Read original bound facts; no inference from provider summary prose."""
    from riskobet_domain import EventModelSnapshot, FactorRole
    if not isinstance(snapshot, EventModelSnapshot):
        return False
    if any(getattr(candidate, field, None) != getattr(snapshot, field, None)
           for field in ('snapshot_id', 'event_key', 'sport', 'competition', 'event_label', 'starts_at')):
        return False
    if snapshot.modeled_at > now or snapshot.input_cutoff_at > now or snapshot.starts_at <= now:
        return False
    if snapshot.missing_core_data or _enum_value(candidate.context_state) not in {'FRESH', 'PARTIAL'}:
        return False
    def current(factor):
        return (factor.observed_at <= factor.imported_at <= now
                and factor.observed_at <= now <= factor.fresh_until)
    if candidate.sport == 'football':
        checks = {}
        receipts = {}
        for factor in snapshot.factors:
            match = re.fullmatch(r'football_context_(\d+)_(h2h|injuries|weather)', factor.factor_key)
            if (match and factor.source == 'api-football-context'
                    and factor.role is FactorRole.DISPLAY_ONLY):
                checks.setdefault(match[1], {})[match[2]] = factor
            match = re.fullmatch(r'football_highlight_context_checks_(\d+)', factor.factor_key)
            if match:
                receipts[match[1]] = factor
        if not checks or any(set(group) != {'h2h', 'injuries', 'weather'}
                             or not all(current(factor) for factor in group.values())
                             for group in checks.values()):
            return False
        # New receipts record the shared typed check contract. Legacy PARTIAL
        # summaries do not tell whether missing checks or only lineups caused it.
        if receipts:
            return (set(receipts) == set(checks) and all(
                factor.source == 'football-highlight-context-checks-v1'
                and factor.role is FactorRole.DISPLAY_ONLY
                and factor.coverage == 1.0 and current(factor)
                for factor in receipts.values()))
        return _enum_value(candidate.context_state) == 'FRESH'
    model_factors = tuple(factor for factor in snapshot.factors if factor.role is FactorRole.MODEL)
    # Retain the existing sport's canonical FRESH admission, but do not let
    # its actual workload facts survive their own original validity deadline.
    relevant_context = tuple(factor for factor in snapshot.factors
        if candidate.sport == 'tennis' and factor.factor_key.startswith('tennis_workload_')
        and factor.source == 'tennis-shadow-observed-results')
    return (_enum_value(candidate.context_state) == 'FRESH' and bool(model_factors)
            and all(current(factor) for factor in (*model_factors, *relevant_context)))


def build_riskobet_card(
    candidate: "RiskCandidate",
    price: object = None,
    *,
    snapshot: object = None,
    now: Optional[datetime] = None,
) -> RiskBetCard:
    """Map one frozen model candidate and one optional exact price overlay."""

    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError('RisikoBet presentation clock must be timezone-aware')
    current = current.astimezone(timezone.utc)
    candidate_id = _clean_text(getattr(candidate, "candidate_id", None), "")
    event_key = _clean_text(getattr(candidate, "event_key", None), "")
    sport_key = str(getattr(candidate, "sport", "") or "").strip()
    if not candidate_id or not event_key:
        raise ValueError("candidate and event identity are required")
    if sport_key not in _SPORT_LABELS:
        raise ValueError("unsupported RisikoBet sport")

    evidence_code = _enum_value(getattr(candidate, "stage", None))
    context_code = _enum_value(getattr(candidate, "context_state", None))
    if evidence_code not in _EVIDENCE_COPY:
        raise ValueError("unsupported RisikoBet evidence stage")
    if context_code not in _CONTEXT_COPY:
        raise ValueError("unsupported RisikoBet context state")
    evidence_label, evidence_tone = _EVIDENCE_COPY[evidence_code]
    context_label, context_tone = _CONTEXT_COPY[context_code]

    pros = tuple(
        text
        for text in (
            format_riskobet_public_detail(value)
            for value in getattr(candidate, "pros", ())
        )
        if text
    )
    cons = tuple(
        text
        for text in (
            format_riskobet_public_detail(value)
            for value in getattr(candidate, "cons", ())
        )
        if text
    )
    if not pros or not cons:
        raise ValueError("RisikoBet cards require at least one pro and contra")

    overlay = _normalise_price(candidate_id, price)
    price_label, price_tone = _PRICE_COPY[overlay.status]
    market_key = _clean_text(getattr(candidate, "market_key", None), "")
    selection = _clean_text(getattr(candidate, "selection_label", None))
    return RiskBetCard(
        candidate_id=candidate_id,
        event_key=event_key,
        sport_key=sport_key,
        sport=_SPORT_LABELS[sport_key],
        competition=_clean_text(getattr(candidate, "competition", None)),
        scheduled_start_label=format_riskobet_start(
            getattr(candidate, "starts_at", None)
        ),
        event_label=_clean_text(getattr(candidate, "event_label", None)),
        market_key=market_key,
        market=_clean_text(getattr(candidate, "market_label", None)),
        selection=selection,
        model_probability=getattr(candidate, "model_probability", None),
        cautious_probability=getattr(
            candidate, "cautious_probability", None
        ),
        evidence_code=evidence_code,
        evidence_label=evidence_label,
        evidence_tone=evidence_tone,
        context_code=context_code,
        context_label=context_label,
        context_tone=context_tone,
        pros=pros,
        cons=cons,
        missing_core_data=tuple(
            text
            for text in (
                format_riskobet_public_detail(value)
                for value in getattr(candidate, "missing_core_data", ())
            )
            if text
        ),
        price_code=overlay.status,
        price_label=price_label,
        price_tone=price_tone,
        observed_odds=overlay.observed_odds,
        bookmaker=(
            _clean_text(overlay.bookmaker, "") or None
            if overlay.bookmaker is not None
            else None
        ),
        price_observed_at=(
            _clean_text(overlay.observed_at, "") or None
            if overlay.observed_at is not None
            else None
        ),
        simple_market=_is_simple_market(market_key, selection),
        quote_floor_excluded=(overlay.below_floor or (
            overlay.status in {'AVAILABLE', 'PLAYABLE', 'TOO_LOW', 'BORDERLINE', 'THIN'}
            and odds_below_publication_floor(overlay.observed_odds))),
        snapshot_id=str(getattr(candidate, "snapshot_id", "") or ""),
        selection_key=str(getattr(candidate, "selection_key", "") or ""),
        settlement_contract=getattr(candidate, "settlement_contract", None),
        price_check_current=overlay.price_check_current,
        context_check_current=_current_context_check(candidate, snapshot, current),
    )


def _event_identity(card: RiskBetCard) -> tuple[str, str]:
    return card.sport_key, card.event_key


def _scenario_constraint(card: RiskBetCard):
    """Exact frozen settlement semantics, never probability/price inference."""
    expected = (
        f"riskobet-settlement-v1:{card.sport_key}:"
        f"{card.market_key}:{card.selection_key}"
    )
    if not card.snapshot_id or card.settlement_contract != expected:
        return None
    side = card.selection_key
    if card.sport_key == "football":
        from selection_coherence import _count_masks
        side_prefix = {"home": "HOME", "away": "AWAY"}.get(side)
        key = None
        if card.market_key == "result_90_minutes" and side_prefix:
            key = f"RESULT_{side_prefix}"
        elif card.market_key == "draw_90_minutes" and side == "draw":
            key = "RESULT_DRAW"
        elif card.market_key == "double_chance_90_minutes":
            key = {"home_or_draw": "DC_1X", "away_or_draw": "DC_X2", "home_or_away": "DC_12"}.get(side)
        elif side_prefix and card.market_key in {
            "underdog_team_over_0_5_90_minutes", "underdog_team_over_1_5_90_minutes"
        }:
            line = "0_5" if "over_0_5" in card.market_key else "1_5"
            key = f"{side_prefix}_OVER_{line}"
        return _count_masks().get((key, False)) if key else None
    if card.sport_key == "tennis":
        # Both supported match lengths are represented. With the event cap of
        # two this preserves every possible joint truth pattern for V1 markets;
        # it makes no claim about the probability or actual best-of format.
        scores = ((2, 0), (2, 1), (0, 2), (1, 2), (3, 0), (3, 1), (3, 2), (0, 3), (1, 3), (2, 3))
        mask = 0
        for index, (home, away) in enumerate(scores):
            selected, opponent = (home, away) if side == "home" else (away, home)
            if card.market_key == "over_2_5_sets" and side == "over":
                won = home + away > 2.5
            elif side in {"home", "away"} and card.market_key == "match_winner":
                won = selected > opponent
            elif side in {"home", "away"} and card.market_key == "at_least_one_set":
                won = selected >= 1
            elif side in {"home", "away"} and card.market_key == "plus_1_5_sets":
                won = selected + 1.5 > opponent
            else:
                return None
            if won:
                mask |= 1 << index
        return "sets", mask
    binary = {
        "basketball": {"match_winner_including_ot"},
        "ice_hockey": {"match_winner_including_ot"},
        "cricket": {"match_winner"},
        "esports": {"series_winner"},
    }
    if card.market_key in binary.get(card.sport_key, ()) and side in {"home", "away"}:
        return "winner", 1 if side == "home" else 2
    # An E-sport map is not independent of a series winner in Best-of-1.
    # The card contract does not retain an exact frozen series length, so do
    # not guess multi-map compatibility from its label or model probability.
    # Such a map may still be the primary; only unproven extras are withheld.
    return None


def _coherent_scenarios(cards: Iterable[RiskBetCard]) -> list[RiskBetCard]:
    """Anchor the first evidenced scenario before price/slot/page filters.

    Opposing results are alternatives, not independently playable selections.
    Keep the upstream risk order (including its underdog intent), intersect all
    accepted predicates and never combine different frozen event revisions.
    Unknown semantics may stay as one primary, not certified-compatible extras.
    """
    result = []
    states = {}
    for card in cards:
        event = _event_identity(card)
        constraint = _scenario_constraint(card)
        previous = states.get(event)
        if previous is None:
            states[event] = (card.snapshot_id, constraint)
            result.append(card)
            continue
        snapshot, accepted = previous
        if (not snapshot or snapshot != card.snapshot_id or accepted is None or constraint is None):
            continue
        domain, mask = constraint
        if domain != accepted[0]:
            continue
        intersection = accepted[1] & mask
        if not intersection:
            continue
        states[event] = (snapshot, (domain, intersection))
        result.append(card)
    return result


def _cap_scenarios_per_event(
    cards: Iterable[RiskBetCard],
) -> list[RiskBetCard]:
    result: list[RiskBetCard] = []
    counts: dict[tuple[str, str], int] = {}
    candidate_ids: set[str] = set()
    for card in cards:
        if card.candidate_id in candidate_ids:
            raise ValueError("duplicate RisikoBet candidate identity")
        candidate_ids.add(card.candidate_id)
        if card.quote_floor_excluded:
            continue
        event = _event_identity(card)
        count = counts.get(event, 0)
        if count >= 2:
            continue
        counts[event] = count + 1
        result.append(card)
    return result


def _round_robin_by_sport(cards: Iterable[RiskBetCard]) -> list[RiskBetCard]:
    queues: OrderedDict[str, list[RiskBetCard]] = OrderedDict(
        (sport_key, []) for sport_key in _SPORT_LABELS
    )
    for card in cards:
        queues[card.sport_key].append(card)
    result: list[RiskBetCard] = []
    offsets = {sport_key: 0 for sport_key in queues}
    while True:
        appended = False
        for sport_key, queue in queues.items():
            offset = offsets[sport_key]
            if offset < len(queue):
                result.append(queue[offset])
                offsets[sport_key] = offset + 1
                appended = True
        if not appended:
            return result


def _evidence_then_sport_order(
    cards: Iterable[RiskBetCard],
) -> list[RiskBetCard]:
    cards = list(cards)
    established = [
        card for card in cards if card.evidence_code != "RESEARCH"
    ]
    research = [card for card in cards if card.evidence_code == "RESEARCH"]
    return _round_robin_by_sport(established) + _round_robin_by_sport(research)


def _select_featured(
    ordered: Iterable[RiskBetCard],
    *,
    max_featured: int,
) -> tuple[RiskBetCard, ...]:
    """Highlight checked scenarios, only after whole-event price-blind coherence."""

    ordered = tuple(card for card in ordered
                    if card.context_check_current and not card.missing_core_data
                    and card.model_probability is not None
                    and card.evidence_code != 'RESEARCH'
                    and card.price_check_current)
    established = tuple(
        card for card in ordered if card.evidence_code != "RESEARCH"
    )
    research = tuple(card for card in ordered if card.evidence_code == "RESEARCH")
    selected: list[RiskBetCard] = []
    selected_ids: set[str] = set()
    featured_events: set[tuple[str, str]] = set()
    simple_selected = False

    def fill_from(cohort: tuple[RiskBetCard, ...]) -> None:
        nonlocal simple_selected

        # Use informative non-basis scenarios first and keep events diverse.
        for card in cohort:
            if len(selected) == max_featured:
                return
            event = _event_identity(card)
            if card.simple_market or event in featured_events:
                continue
            selected.append(card)
            selected_ids.add(card.candidate_id)
            featured_events.add(event)

        # A single simple 1+ scenario may be featured when a concrete pro
        # exists, but these broad safety lines can never dominate the top.
        if not simple_selected:
            for card in cohort:
                if len(selected) == max_featured:
                    return
                event = _event_identity(card)
                if (
                    not card.simple_market
                    or card.candidate_id in selected_ids
                    or event in featured_events
                    or not card.pros
                ):
                    continue
                selected.append(card)
                selected_ids.add(card.candidate_id)
                featured_events.add(event)
                simple_selected = True
                break

        # If only a few events exist, a second non-simple scenario from an
        # event is still useful and remains inside the hard event cap applied
        # before this selection step.
        for card in cohort:
            if len(selected) == max_featured:
                return
            if card.candidate_id in selected_ids or card.simple_market:
                continue
            selected.append(card)
            selected_ids.add(card.candidate_id)

    # Research and incomplete checks remain additional cards, never top-slot
    # filler. Price-check coverage cannot change the prior direction anchor.
    fill_from(established)
    if len(selected_ids) == len(established):
        fill_from(research)
    return tuple(selected)


def compose_riskobet_catalog(
    cards: Iterable[RiskBetCard],
    *,
    sport_filter: str = "Alle",
    max_featured: int = 3,
) -> RiskBetCatalog:
    """Build the model-ordered catalog, excluding known offers below 1.20.

    ``Alle`` is composed round-robin across the six fixed sports.  Within a
    sport, the upstream model order remains stable apart from the contractual
    rule that Research follows Shadow/Validated evidence.  A third scenario
    for the same event is never published.
    """

    if sport_filter not in SPORT_FILTERS:
        raise ValueError("sport_filter must be one of SPORT_FILTERS")
    if (
        isinstance(max_featured, bool)
        or not isinstance(max_featured, int)
        or not 1 <= max_featured <= 3
    ):
        raise ValueError("max_featured must be between one and three")

    # Evidence priority precedes the hard event cap. Otherwise two weaker
    # records can erase a later validated record before it is even considered.
    priority = {"VALIDATED": 0, "SHADOW": 1, "RESEARCH": 2}
    pool = tuple(cards)
    if len({card.candidate_id for card in pool}) != len(pool):
        raise ValueError("duplicate RisikoBet candidate identity")
    evidenced = sorted(pool, key=lambda card: priority[card.evidence_code])
    capped = list(_cap_scenarios_per_event(_coherent_scenarios(evidenced)))
    if sport_filter == "Alle":
        ordered = _evidence_then_sport_order(capped)
    else:
        sport_key = _FILTER_TO_SPORT[sport_filter]
        filtered = [card for card in capped if card.sport_key == sport_key]
        ordered = [
            card for card in filtered if card.evidence_code != "RESEARCH"
        ] + [card for card in filtered if card.evidence_code == "RESEARCH"]

    featured = _select_featured(ordered, max_featured=max_featured)
    featured_ids = {card.candidate_id for card in featured}
    additional = tuple(
        card for card in ordered if card.candidate_id not in featured_ids
    )
    return RiskBetCatalog(featured=featured, additional=additional)


def _badge(kind: str, tone: str, label: str) -> str:
    return (
        f'<span class="rb-badge rb-badge-{kind} rb-{kind}-{tone}">'
        f"{escape(label)}</span>"
    )


def customer_riskobet_note(value: object) -> str:
    """Keep concrete sport copy, not generic model/workload explanations."""
    text = _clean_text(value, '')
    generic = (
        'serve-simulation', 'satzsimulation', 'das satzmodell sieht',
        'das modell setzt ein regulär beendetes', 'grundmodell: spielstärke',
        'unvollständige historie belegt keine tatsächliche erholungsdauer',
        'jüngstes beobachtetes ergebnis seit',
        'keine zeitlich belegte vorherige matchbelastung verfügbar',
        'belastungsdaten decken nur zuvor beobachtete',
        'numerischer belastungseffekt', 'als numerischer effekt validiert',
    )
    isolated_sets = re.search(
        r':\s*zuletzt\s+(?:\d+|ein|zwei|drei|vier|fünf)\s+'
        r'(?:beobachtete\s+Sätze|Sätze\s+beobachtet)\.?\s*$', text,
        flags=re.IGNORECASE,
    )
    if isolated_sets or any(part in text.casefold() for part in generic):
        return ''
    public = format_riskobet_public_detail(text)
    return '' if public == _TECHNICAL_DETAIL_FALLBACK else public


def compact_riskobet_tennis_form(value: object) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Project only the exact frozen customer-record templates, never history.

    Tennis snapshots retain aggregate strings, not ordered result rows. The
    original date/scope remains in the factor; only explicit counts are copied.
    Player names are not split at dots or passed through status translations.
    """
    text = _clean_text(value, '')
    surface_names = 'Hartplatz|Sand|Rasen|Teppich|Alle Beläge'
    record_pattern = re.compile(
        r'(?P<player>[^:]{1,200}):\s*'
        r'(?P<counts>\d+/\d+(?:\s*·\s*\d+/\d+)*)\s+Siege'
        r'(?P<all_surfaces>\s*·\s*alle Beläge)?\s*'
        r'\((?P<surface>' + surface_names + r')\s*·\s*'
        r'(?:letzte (?:5 / 10|\d+) erfasste Spiele|\d+ erfasste Spiele)\s*·\s*'
        r'\d{2}\.\d{2}\.\d{4}–\d{2}\.\d{2}\.\d{4}'
        r'(?:\s*·\s*K\.-o\.-Runden einschließlich Qualifikation)?\)\.?'
    )
    records, surface, offset = [], '', 0
    while offset < len(text):
        match = record_pattern.match(text, offset)
        if not match:
            break
        pairs = [tuple(map(int, ratio.split('/'))) for ratio in re.split(r'\s*·\s*', match['counts'])]
        if (len(pairs) > 2 or any(not 0 <= wins <= count <= 10 or count == 0 for wins, count in pairs)
                or len({count for _, count in pairs}) != len(pairs)):
            return '', ()
        if surface and surface != match['surface']:
            return '', ()
        if match['all_surfaces'] and match['surface'] != 'Alle Beläge':
            return '', ()
        surface = match['surface']
        player = match['player'].strip()
        if not player or any(name == player for name, _ in records):
            return '', ()
        records.append((player, ' · '.join(f'{wins}/{count} Siege' for wins, count in pairs)))
        offset = match.end()
        while offset < len(text) and text[offset].isspace():
            offset += 1
    if offset == len(text) and 1 <= len(records) <= 2:
        return surface, tuple(records)
    # Older surface-only evidence has sample counts, not win records. Preserve
    # that distinction; do not turn an Elo/rating into a form or a victory count.
    legacy = re.fullmatch(r'(?P<surface>' + surface_names + r'):\s*(?P<body>.+)', text)
    if not legacy:
        return '', ()
    body = re.sub(r'[\d.,]+ Elo \((\d+) Spiele\)', r'\1 erfasste Spiele', legacy['body'])
    body = re.sub(r' · (?:Belag-Elo berücksichtigt|Gesamt-Elo verwendet)(?: · Daten bis .*\Z)?', '', body)
    samples = []
    for part in body.split(' · '):
        sample = re.fullmatch(r'(?P<player>.+?) (?P<count>\d+) erfasste Spiele', part)
        if not sample:
            return '', ()
        samples.append((sample['player'], sample['count'] + ' erfasste Spiele'))
    return (legacy['surface'], tuple(samples)) if 1 <= len(samples) <= 2 else ('', ())


def _reason_block(kind: str, title: str, values: Iterable[str]) -> str:
    values = tuple(text for value in values if (text := customer_riskobet_note(value)))
    if not values:
        return ''
    items = "".join(f"<li>{escape(value)}</li>" for value in values)
    return (
        f'<section class="rb-reason rb-reason-{kind}">'
        f"<h4>{escape(title)}</h4><ul>{items}</ul></section>"
    )


def _price_markup(card: RiskBetCard, *, compact: bool) -> str:
    odds = format_riskobet_odds(card.observed_odds)
    bookmaker = (
        f'<span class="rb-price-bookmaker">{escape(card.bookmaker)}</span>'
        if card.bookmaker and odds != "–"
        else ""
    )
    css_class = "rb-row-price" if compact else "rb-price"
    stamp = ('<span class="rb-price-bookmaker">' + ('Abgerufen: ' if card.price_code == 'OBSERVED' else 'Stand: ')
             + escape(format_riskobet_start(card.price_observed_at)) + '</span>') if card.price_observed_at else ''
    label = 'Letzte Quote' if card.price_code == 'STALE' else 'Quote'
    return (
        f'<div class="{css_class}" data-price-code="'
        f'{escape(card.price_code, quote=True)}">'
        f'<span class="rb-field-label">{label}</span>'
        f"{_badge('price', card.price_tone, card.price_label)}"
        f'<strong class="rb-price-odds">{escape(odds)}</strong>'
        f"{bookmaker}{stamp}</div>"
    )


def render_riskobet_card_html(card: RiskBetCard, *, show_price: bool = True) -> str:
    """Render sport facts; evidence and cautious estimates stay internal."""

    probability = format_riskobet_probability(card.model_probability)
    missing = ""
    missing_data = tuple(text for value in card.missing_core_data if (text := customer_riskobet_note(value)))
    if missing_data:
        missing_items = ", ".join(missing_data)
        missing = (
            '<p class="rb-missing"><span>Fehlende Kerndaten:</span> '
            f"{escape(missing_items)}</p>"
        )
    price_footer = (
        '<p class="rb-price-separation">Der Wettpreis verändert diese Prognose nicht.</p>'
        if show_price else ''
    )
    market_markup = f'<p class="rb-market">{escape(card.market)}</p>' if card.market != card.selection else ''
    return (
        f'<article class="rb-card rb-card-featured" data-key="'
        f'{escape(card.candidate_id, quote=True)}" '
        f'aria-label="Risiko-Szenario für {escape(card.event_label, quote=True)}">'
        '<div class="rb-status-row">'
        f"{_badge('sport', 'neutral', card.sport)}"
        f"{_badge('context', card.context_tone, card.context_label)}"
        "</div>"
        '<p class="rb-meta">'
        f'<span class="rb-competition">{escape(card.competition)}</span>'
        '<span aria-hidden="true"> · </span>'
        f'<time class="rb-start">{escape(card.scheduled_start_label)}</time></p>'
        f'<h3 class="rb-event">{escape(card.event_label)}</h3>'
        f'{market_markup}'
        f'<p class="rb-selection">{escape(card.selection)}</p>'
        '<div class="rb-probabilities">'
        '<div><span>Modellwahrscheinlichkeit</span>'
        f"<strong>{escape(probability)}</strong></div></div>"
        '<div class="rb-reasons">'
        f"{_reason_block('pro', 'Modellgrundlage', card.pros)}"
        f"{_reason_block('contra', 'Spricht dagegen', card.cons)}"
        "</div>"
        f"{missing}"
        f"{_price_markup(card, compact=False) if show_price else ''}"
        f"{price_footer}"
        "</article>"
    )


def render_riskobet_compact_row_html(card: RiskBetCard, *, show_price: bool = True) -> str:
    """Render a flat sport-first row without internal evidence or safety values."""

    probability = format_riskobet_probability(card.model_probability)
    pros = tuple(text for value in card.pros if (text := customer_riskobet_note(value)))
    cons = tuple(text for value in card.cons if (text := customer_riskobet_note(value)))
    reason_pro = ('<span class="rb-row-pro"><b>Grundlage:</b> '
                  + escape(pros[0]) + '</span>') if pros else ''
    reason_contra = ('<span class="rb-row-contra"><b>Contra:</b> '
                     + escape(cons[0]) + '</span>') if cons else ''
    market_markup = f'<span>{escape(card.market)}</span>' if card.market != card.selection else ''
    missing = ""
    missing_data = tuple(text for value in card.missing_core_data if (text := customer_riskobet_note(value)))
    if missing_data:
        missing = (
            '<span class="rb-row-missing">Fehlt: '
            f"{escape(', '.join(missing_data))}</span>"
        )
    return (
        f'<article class="rb-row" data-key="'
        f'{escape(card.candidate_id, quote=True)}" '
        f'aria-label="Risiko-Szenario für {escape(card.event_label, quote=True)}">'
        '<div class="rb-row-event">'
        '<span class="rb-row-meta">'
        f"{escape(card.sport)} · {escape(card.competition)} · "
        f"{escape(card.scheduled_start_label)}</span>"
        f"<strong>{escape(card.event_label)}</strong>"
        '<span class="rb-row-status">'
        f"{_badge('context', card.context_tone, card.context_label)}"
        "</span></div>"
        '<div class="rb-row-pick">'
        f'{market_markup}'
        f"<strong>{escape(card.selection)}</strong></div>"
        '<div class="rb-row-probabilities">'
        '<span>Modell <strong>'
        f"{escape(probability)}</strong></span></div>"
        '<div class="rb-row-reasons">'
        f'{reason_pro}{reason_contra}{missing}</div>'
        f"{_price_markup(card, compact=True) if show_price else ''}"
        "</article>"
    )


__all__ = [
    "SPORT_FILTERS",
    "RiskBetCard",
    "RiskBetCatalog",
    "RiskBetPriceOverlay",
    "build_riskobet_card",
    "customer_riskobet_note",
    "compact_riskobet_tennis_form",
    "compose_riskobet_catalog",
    "format_riskobet_odds",
    "format_riskobet_probability",
    "format_riskobet_public_detail",
    "format_riskobet_start",
    "render_riskobet_card_html",
    "render_riskobet_compact_row_html",
]
