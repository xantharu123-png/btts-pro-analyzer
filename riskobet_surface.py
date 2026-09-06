"""Pure, price-neutral presentation helpers for the RisikoBet page.

The module deliberately owns no Streamlit state and performs no provider work.
It maps an immutable :class:`riskobet_domain.RiskCandidate` to escaped consumer
markup.  Price observations are a separate overlay and are never consulted by
filtering, scenario limits or featured-card composition.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from html import escape
import math
import re
from typing import TYPE_CHECKING, Iterable, Mapping, Optional
import unicodedata
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
    r"|\b(?:HTTP\s*)?[45]\d{2}\b",
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

    def __post_init__(self) -> None:
        candidate_id = str(self.candidate_id or "").strip()
        status = str(self.status or "").strip().upper()
        if not candidate_id:
            raise ValueError("price candidate identity is required")
        if status not in _PRICE_COPY:
            raise ValueError("unsupported RisikoBet price status")
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


def build_riskobet_card(
    candidate: "RiskCandidate",
    price: object = None,
) -> RiskBetCard:
    """Map one frozen model candidate and one optional exact price overlay."""

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
    )


def _event_identity(card: RiskBetCard) -> tuple[str, str]:
    return card.sport_key, card.event_key


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
    """Select useful scenarios without inspecting any price field."""

    ordered = tuple(ordered)
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

    # Evidenced scenarios always receive the first opportunity.  Research may
    # fill genuinely free top slots only after every evidenced scenario has
    # been placed; it never jumps above an evidenced additional row.
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
    """Build the visible catalog using model fields only.

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

    capped = _cap_scenarios_per_event(tuple(cards))
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


def _reason_block(kind: str, title: str, values: Iterable[str]) -> str:
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
    return (
        f'<div class="{css_class}" data-price-code="'
        f'{escape(card.price_code, quote=True)}">'
        '<span class="rb-field-label">Preis</span>'
        f"{_badge('price', card.price_tone, card.price_label)}"
        f'<strong class="rb-price-odds">{escape(odds)}</strong>'
        f"{bookmaker}</div>"
    )


def render_riskobet_card_html(card: RiskBetCard) -> str:
    """Render an escaped full card with all decision fields immediately visible."""

    probability = format_riskobet_probability(card.model_probability)
    cautious = format_riskobet_probability(card.cautious_probability)
    missing = ""
    if card.missing_core_data:
        missing_items = ", ".join(card.missing_core_data)
        missing = (
            '<p class="rb-missing"><span>Fehlende Kerndaten:</span> '
            f"{escape(missing_items)}</p>"
        )
    return (
        f'<article class="rb-card rb-card-featured" data-key="'
        f'{escape(card.candidate_id, quote=True)}" '
        f'aria-label="Risiko-Szenario für {escape(card.event_label, quote=True)}">'
        '<div class="rb-status-row">'
        f"{_badge('sport', 'neutral', card.sport)}"
        f"{_badge('evidence', card.evidence_tone, card.evidence_label)}"
        f"{_badge('context', card.context_tone, card.context_label)}"
        "</div>"
        '<p class="rb-meta">'
        f'<span class="rb-competition">{escape(card.competition)}</span>'
        '<span aria-hidden="true"> · </span>'
        f'<time class="rb-start">{escape(card.scheduled_start_label)}</time></p>'
        f'<h3 class="rb-event">{escape(card.event_label)}</h3>'
        f'<p class="rb-market">{escape(card.market)}</p>'
        f'<p class="rb-selection">{escape(card.selection)}</p>'
        '<div class="rb-probabilities">'
        '<div><span>Modellwahrscheinlichkeit</span>'
        f"<strong>{escape(probability)}</strong></div>"
        '<div><span>Sicherheitswert</span>'
        f"<strong>{escape(cautious)}</strong></div></div>"
        '<p class="rb-uncertainty-note">Heuristischer Abschlag, keine '
        'statistisch bestätigte Mindestchance.</p>'
        '<div class="rb-reasons">'
        f"{_reason_block('pro', 'Spricht dafür', card.pros)}"
        f"{_reason_block('contra', 'Spricht dagegen', card.cons)}"
        "</div>"
        f"{missing}"
        f"{_price_markup(card, compact=False)}"
        '<p class="rb-price-separation">Der Wettpreis verändert diese '
        "Prognose nicht.</p>"
        "</article>"
    )


def render_riskobet_compact_row_html(card: RiskBetCard) -> str:
    """Render one genuinely flat row while retaining every decision field."""

    probability = format_riskobet_probability(card.model_probability)
    cautious = format_riskobet_probability(card.cautious_probability)
    missing = ""
    if card.missing_core_data:
        missing = (
            '<span class="rb-row-missing">Fehlt: '
            f"{escape(', '.join(card.missing_core_data))}</span>"
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
        f"{_badge('evidence', card.evidence_tone, card.evidence_label)}"
        f"{_badge('context', card.context_tone, card.context_label)}"
        "</span></div>"
        '<div class="rb-row-pick">'
        f"<span>{escape(card.market)}</span>"
        f"<strong>{escape(card.selection)}</strong></div>"
        '<div class="rb-row-probabilities">'
        '<span>Modell <strong>'
        f"{escape(probability)}</strong></span>"
        '<span>Sicherheitswert <strong>'
        f"{escape(cautious)}</strong></span></div>"
        '<div class="rb-row-reasons">'
        '<span class="rb-row-pro"><b>Pro:</b> '
        f"{escape(card.pros[0])}</span>"
        '<span class="rb-row-contra"><b>Contra:</b> '
        f"{escape(card.cons[0])}</span>{missing}</div>"
        f"{_price_markup(card, compact=True)}"
        "</article>"
    )


__all__ = [
    "SPORT_FILTERS",
    "RiskBetCard",
    "RiskBetCatalog",
    "RiskBetPriceOverlay",
    "build_riskobet_card",
    "compose_riskobet_catalog",
    "format_riskobet_odds",
    "format_riskobet_probability",
    "format_riskobet_public_detail",
    "format_riskobet_start",
    "render_riskobet_card_html",
    "render_riskobet_compact_row_html",
]
