"""Pure, price-neutral presentation data for the Wettfinder V2 surface.

This module deliberately owns no Streamlit state and does not evaluate a bet.
It turns loader-approved model rows and an already exact-bound consensus quote
into safe consumer-facing data, without letting price change model order or
probability.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import math
import re
from typing import Iterable, Mapping, Optional
import unicodedata
from zoneinfo import ZoneInfo

from bet_finder_ui import (
    ReferencePriceEvaluation,
    _consumer_market_identity,
    _consumer_market_is_basis,
    consumer_fixture_label,
)
from ev_signal_sources import ModelSignal
from market_consensus import (
    MarketConsensus,
    ReferencePriceStatus,
    quote_matches_candidate,
    wettfinder_consensus,
    wettfinder_reference_price_status,
)
from multi_sport_recommendations import RecommendationCandidate


_ALL_SPORT_FILTERS = {"", "alle", "all"}
_ZURICH_TZ = ZoneInfo("Europe/Zurich")


@dataclass(frozen=True)
class WettfinderCard:
    """One immutable, display-ready model forecast."""

    key: str
    sport: str
    scheduled_start_label: str
    event_label: str
    market: str
    selection: str
    model_probability: float
    cautious_probability: float
    value_threshold: Optional[float]
    observed_odds: Optional[float]
    bookmaker: Optional[str]
    price_code: str
    price_label: str
    price_tone: str
    evidence_label: str
    evidence_tone: str
    context_label: str
    detail: str
    confirmed_tip: bool
    reference_quote: Optional[MarketConsensus]
    manual_quote_key: str
    can_check_manual_quote: bool = True
    market_key: Optional[str] = None


@dataclass(frozen=True)
class WettfinderFixtureGroup:
    """Adjacent secondary rows for one sport-specific event identity."""

    fixture_identity: str
    label: str
    cards: tuple[WettfinderCard, ...]


@dataclass(frozen=True)
class WettfinderReleaseOverlay:
    """A strict decision bound to one persisted model and execution quote."""

    signal_key: str
    quote_candidate_id: str
    quote_market_key: str
    status: str
    quoted_odds: float
    quote_source: str
    bookmaker_id: str
    observed_at: str

    def __post_init__(self) -> None:
        if not all(
            str(value or "").strip()
            for value in (
                self.signal_key,
                self.quote_candidate_id,
                self.quote_market_key,
                self.status,
                self.quote_source,
                self.bookmaker_id,
                self.observed_at,
            )
        ):
            raise ValueError("release overlay identity is required")
        if (
            isinstance(self.quoted_odds, bool)
            or not isinstance(self.quoted_odds, (int, float))
            or not math.isfinite(float(self.quoted_odds))
            or float(self.quoted_odds) <= 1.0
        ):
            raise ValueError("release overlay odds are invalid")


@dataclass(frozen=True)
class WettfinderCatalog:
    """The unranked top cards plus every remaining card exactly once."""

    featured: tuple[WettfinderCard, ...]
    additional: tuple[WettfinderCard, ...]
    additional_groups: tuple[WettfinderFixtureGroup, ...]


def _token(value: object) -> str:
    normalized = unicodedata.normalize(
        "NFKD", str(value or "").casefold().replace("ß", "ss")
    )
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


def _clean_text(value: object, fallback: str = "–") -> str:
    text = str(value or "").strip()
    return text or fallback


def _consumer_context_label(value: object) -> str:
    """Keep the visible ``Kontext:`` prefix in one rendering layer only."""

    text = _clean_text(value, "Kontext ausstehend")
    while True:
        cleaned = re.sub(r"^kontext\s*:\s*", "", text, count=1, flags=re.I)
        if cleaned == text:
            break
        text = cleaned.strip()
    return text or "ausstehend"


def format_scheduled_start(value: object) -> str:
    """Format only valid ISO datetimes; malformed input never reaches HTML."""

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "–"
    if parsed.tzinfo is None:
        return "–"
    return parsed.astimezone(_ZURICH_TZ).strftime("%d.%m. %H:%M")


def format_probability(value: object) -> str:
    """Return a bounded display value without mutating the model probability."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "–"
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return "–"
    return f"{number * 100:.1f} %"


def format_decimal_odds(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "–"
    number = float(value)
    if not math.isfinite(number) or number <= 1.0:
        return "–"
    return f"{number:.2f}"


def _normalise_quote(quote: object) -> Optional[MarketConsensus]:
    if isinstance(quote, MarketConsensus):
        return quote
    if isinstance(quote, Mapping):
        return MarketConsensus.from_dict(quote)
    return None


def wettfinder_quote_binding_candidate(
    signal: ModelSignal,
) -> dict[str, object]:
    """Adapt retained loader identity to the existing quote-binding contract."""

    return {
        "candidate_id": signal.candidate_id or signal.key,
        "market_key": signal.market_key,
        "sport": signal.sport,
        "source": signal.source,
        "fixture_id": signal.fixture_id,
        "scheduled_start": signal.scheduled_start,
        "selection": signal.selection,
        "home_team": signal.home_team,
        "away_team": signal.away_team,
        "quote_provider_event_id": signal.quote_provider_event_id,
        "competitor_a": signal.competitor_a,
        "competitor_b": signal.competitor_b,
        "selected_competitor": signal.selected_competitor,
    }


def wettfinder_recommendation_candidate(
    signal: ModelSignal,
) -> RecommendationCandidate:
    """Build the complete immutable price candidate represented by a signal."""

    probability = signal.probability * 100.0
    haircut = signal.probability_haircut * 100.0
    normalized_sport = (
        str(signal.sport or "").strip().casefold().replace("ß", "ss")
    )
    return RecommendationCandidate(
        event_key=signal.key,
        sport=signal.sport or "Sport",
        event_label=signal.event_label or signal.label,
        market=signal.market or "Auswahl",
        selection=signal.selection or signal.label,
        line=None,
        model_probability=round(probability, 2),
        risk_adjusted_probability=round(probability - haircut, 2),
        probability_haircut=round(haircut, 2),
        fair_odds=round(100.0 / probability, 3),
        minimum_odds=signal.minimum_odds,
        model_name=signal.detail,
        expected_total=None,
        evidence=(
            signal.detail,
            (
                "Automatischer Marktvergleich liegt vor."
                if signal.reference_quote is not None
                else "Modellprognose und Wettpreis werden getrennt bewertet."
            ),
        ),
        blockers=(
            ()
            if signal.minimum_odds is not None
            else ("Keine belastbare Value-Grenze berechenbar.",)
        ),
        evidence_stage=signal.evidence_stage,
        release_pending=(
            normalized_sport == "fussball"
            and signal.statistical_release_passed is not True
        ),
    )


def _overlay_matches(
    overlay: Optional[WettfinderReleaseOverlay],
    signal: ModelSignal,
    quote: Optional[MarketConsensus],
    status: ReferencePriceStatus,
) -> bool:
    if overlay is None or quote is None or status.usable_odds is None:
        return False
    return bool(
        overlay.status == "BET"
        and overlay.signal_key == signal.key
        and overlay.quote_candidate_id == quote.candidate_id
        and overlay.quote_market_key.strip().upper()
        == quote.market_key.strip().upper()
        and overlay.quote_source == quote.source
        and overlay.bookmaker_id == status.bookmaker_id
        and overlay.observed_at == status.observed_at
        and math.isclose(
            float(overlay.quoted_odds),
            float(status.usable_odds),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
    )


def _price_copy(
    status: ReferencePriceStatus,
    quote: Optional[MarketConsensus],
    *,
    confirmed_tip: bool,
) -> tuple[str, str, Optional[float], Optional[str]]:
    """Present a status without ever relabelling an old price as current."""

    labels = {
        "TOO_LOW": ("Unter Value", "muted"),
        "BORDERLINE": ("Quote offen", "warning"),
        "THIN": ("Quote zu dünn", "warning"),
        "STALE": ("Veraltet", "muted"),
        "UNAVAILABLE": ("Quote fehlt", "muted"),
        "INVALID_MINIMUM": ("Quote offen", "warning"),
    }
    if status.code == "PLAYABLE":
        # A matching price is not a released tip. Reserve the green
        # consumer-facing "Spielbar" state for the exact, persisted release
        # overlay; SHADOW/RESEARCH rows remain visibly non-actionable.
        label, tone = (
            ("Spielbar", "positive")
            if confirmed_tip
            else ("Quote passend", "warning")
        )
        return label, tone, status.usable_odds, status.bookmaker
    label, tone = labels.get(status.code, ("Quote offen", "warning"))
    if status.code in {"TOO_LOW", "BORDERLINE"} and quote is not None:
        best = max(quote.points, key=lambda point: point.odds, default=None)
        return (
            label,
            tone,
            quote.best_odds,
            best.bookmaker if best is not None else None,
        )
    return label, tone, None, None


def _evidence_copy(signal: ModelSignal, confirmed_tip: bool) -> tuple[str, str]:
    if confirmed_tip:
        return "Bestätigter Tipp", "positive"
    evidence_stage = str(signal.evidence_stage or "").strip().upper()
    if evidence_stage == "RELEASED":
        if signal.statistical_release_passed is True:
            return "Freigegeben", "positive"
        return "Freigabe ausstehend", "warning"
    if evidence_stage == "SHADOW":
        return "Evidenzprüfung", "warning"
    if evidence_stage == "RESEARCH":
        return "Forschungsmodell", "muted"
    return "Modellprüfung", "muted"


def build_wettfinder_card(
    signal: ModelSignal,
    quote: object = None,
    *,
    now: Optional[datetime] = None,
    release_overlay: Optional[WettfinderReleaseOverlay] = None,
    price_evaluation: Optional[ReferencePriceEvaluation] = None,
) -> WettfinderCard:
    """Map one model signal and its exact-key quote to a display card.

    ``release_overlay`` is the identity- and execution-bound output of the
    strict price/decision path. It is optional because a normal model forecast
    remains visible before any release decision exists.
    """

    if price_evaluation is None:
        normalized_quote = _normalise_quote(quote)
        status = wettfinder_reference_price_status(
            normalized_quote,
            signal.minimum_odds,
            candidate=wettfinder_quote_binding_candidate(signal),
            now=now,
        )
        current_quote = wettfinder_consensus(normalized_quote, now=now)
    else:
        expected_candidate = wettfinder_recommendation_candidate(signal)
        if price_evaluation.candidate != expected_candidate:
            raise ValueError("price evaluation candidate mismatch")
        if now is not None:
            if now.tzinfo is None:
                raise ValueError("now must be timezone-aware")
            if now.astimezone(timezone.utc) != price_evaluation.evaluated_at:
                raise ValueError("price evaluation clock mismatch")
        status = price_evaluation.status
        current_quote = (
            None if status.code == "UNAVAILABLE" else price_evaluation.quote
        )
        if current_quote is not None and not quote_matches_candidate(
            current_quote,
            wettfinder_quote_binding_candidate(signal),
        ):
            raise ValueError("price evaluation quote mismatch")
        normalized_quote = current_quote
    released = signal.evidence_stage == "RELEASED"
    confirmed_tip = bool(
        released
        and signal.statistical_release_passed is True
        and status.code == "PLAYABLE"
        and _overlay_matches(release_overlay, signal, normalized_quote, status)
    )
    price_label, price_tone, observed_odds, bookmaker = _price_copy(
        status,
        current_quote,
        confirmed_tip=confirmed_tip,
    )
    evidence_label, evidence_tone = _evidence_copy(signal, confirmed_tip)
    model_probability = float(signal.probability)
    cautious_probability = model_probability - float(signal.probability_haircut)
    return WettfinderCard(
        key=signal.key,
        sport=_clean_text(signal.sport, "Modell"),
        scheduled_start_label=format_scheduled_start(signal.scheduled_start),
        event_label=_clean_text(signal.event_label or signal.label),
        market=_clean_text(signal.market, "Auswahl"),
        market_key=signal.market_key,
        selection=_clean_text(signal.selection or signal.label),
        model_probability=model_probability,
        cautious_probability=cautious_probability,
        value_threshold=signal.minimum_odds,
        observed_odds=observed_odds,
        bookmaker=bookmaker,
        price_code=status.code,
        price_label=price_label,
        price_tone=price_tone,
        evidence_label=evidence_label,
        evidence_tone=evidence_tone,
        context_label=_consumer_context_label(signal.context_summary),
        detail=_clean_text(signal.detail),
        confirmed_tip=confirmed_tip,
        reference_quote=current_quote,
        manual_quote_key=signal.key,
    )


def _fixture_identity(card: WettfinderCard) -> str:
    sport = _token(card.sport) or "modell"
    event = _token(card.event_label)
    if event:
        return f"{sport}:{event}"
    return f"{sport}:row_{_token(card.key) or 'unknown'}"


def _round_robin_by_sport(cards: Iterable[WettfinderCard]) -> list[WettfinderCard]:
    queues: OrderedDict[str, list[WettfinderCard]] = OrderedDict()
    for card in cards:
        queues.setdefault(_token(card.sport) or "modell", []).append(card)
    result: list[WettfinderCard] = []
    offsets = {sport: 0 for sport in queues}
    while True:
        appended = False
        for sport, queue in queues.items():
            offset = offsets[sport]
            if offset < len(queue):
                result.append(queue[offset])
                offsets[sport] = offset + 1
                appended = True
        if not appended:
            return result


def _select_featured(
    cards: Iterable[WettfinderCard],
    *,
    max_featured: int,
) -> tuple[WettfinderCard, ...]:
    """Choose useful, sport-diverse cards without considering price data."""

    selected: list[WettfinderCard] = []
    fixtures: set[str] = set()
    markets: set[str] = set()
    for card in cards:
        # Keep broad safety lines visible below the fold while useful diverse
        # markets exist; this is the established consumer-market contract.
        if _consumer_market_is_basis(card):
            continue
        fixture = _fixture_identity(card)
        market = f"{_token(card.sport)}:{_consumer_market_identity(card)}"
        if fixture in fixtures or market in markets:
            continue
        selected.append(card)
        fixtures.add(fixture)
        markets.add(market)
        if len(selected) == max_featured:
            break
    return tuple(selected)


def _group_additional(
    cards: Iterable[WettfinderCard],
) -> tuple[WettfinderFixtureGroup, ...]:
    groups: OrderedDict[str, list[WettfinderCard]] = OrderedDict()
    for card in cards:
        groups.setdefault(_fixture_identity(card), []).append(card)
    return tuple(
        WettfinderFixtureGroup(
            fixture_identity=identity,
            label=consumer_fixture_label(group_cards[0]),
            cards=tuple(group_cards),
        )
        for identity, group_cards in groups.items()
    )


def compose_wettfinder_catalog(
    cards: Iterable[WettfinderCard],
    *,
    sport_filter: str = "Alle",
    max_featured: int = 3,
) -> WettfinderCatalog:
    """Compose an unranked, complete, price-neutral visible catalog.

    With ``Alle`` the source order is round-robin by sport. Within each sport
    it remains the loader's original model order. Sport and event label form
    the fixture key, preventing equal event names in different sports from
    colliding.
    """

    if (
        isinstance(max_featured, bool)
        or not isinstance(max_featured, int)
        or max_featured < 1
    ):
        raise ValueError("max_featured must be a positive integer")
    original = tuple(cards)
    requested = _token(sport_filter)
    if requested in _ALL_SPORT_FILTERS:
        ordered = _round_robin_by_sport(original)
    else:
        ordered = [card for card in original if _token(card.sport) == requested]
    featured = _select_featured(ordered, max_featured=max_featured)
    featured_keys = {card.key for card in featured}
    remaining = [card for card in ordered if card.key not in featured_keys]
    groups = _group_additional(remaining)
    additional = tuple(card for group in groups for card in group.cards)
    return WettfinderCatalog(featured, additional, groups)


_PRICE_NOTES = {
    "PLAYABLE": "Die aktuelle Quote erreicht den Value-Bereich.",
    "TOO_LOW": "Aktuelle Quote unter Value. Die Prognose bleibt unverändert.",
    "BORDERLINE": "Preis nur bei einzelnen Anbietern im Value-Bereich.",
    "THIN": "Zu wenige Vergleichsanbieter für einen belastbaren Preis.",
    "STALE": "Vergleichsquote veraltet. Bitte den Preis neu prüfen.",
    "UNAVAILABLE": "Keine exakt passende Quote. Die Prognose bleibt unverändert.",
    "INVALID_MINIMUM": "Die Value-Grenze ist aktuell nicht belastbar.",
}


def _status_badges(card: WettfinderCard, *, featured: bool) -> str:
    badges = []
    if featured:
        badges.append(
            '<span class="wf-badge wf-badge-top" '
            'aria-label="Top-Auswahl">TOP</span>'
        )
    badges.extend(
        (
            '<span class="wf-badge wf-badge-evidence '
            f'wf-evidence-{escape(card.evidence_tone, quote=True)}">'
            f"{escape(card.evidence_label)}</span>",
            '<span class="wf-badge wf-badge-price '
            f'wf-price-{escape(card.price_tone, quote=True)}">'
            f"{escape(card.price_label)}</span>",
        )
    )
    return '<div class="wf-status-row">' + "".join(badges) + "</div>"


def _metric(label: str, value: str, *, note: Optional[str] = None) -> str:
    note_markup = (
        f'<span class="wf-metric-note">{escape(note)}</span>' if note else ""
    )
    return (
        '<div class="wf-metric"><span class="wf-metric-label">'
        f"{escape(label)}</span><strong>{escape(value)}</strong>"
        f"{note_markup}</div>"
    )


def _row_value(label: str, value: str, *, note: Optional[str] = None) -> str:
    note_markup = (
        f'<span class="wf-row-note">{escape(note)}</span>' if note else ""
    )
    return (
        '<div class="wf-row-value"><span class="wf-row-label">'
        f"{escape(label)}</span><strong>{escape(value)}</strong>"
        f"{note_markup}</div>"
    )


def _top_card_markup(card: WettfinderCard) -> str:
    price = format_decimal_odds(card.observed_odds)
    bookmaker_note = card.bookmaker if price != "–" else None
    metrics = "".join(
        (
            _metric("Modellwert", format_probability(card.model_probability)),
            _metric("Value ab", format_decimal_odds(card.value_threshold)),
            _metric("Aktuell", price, note=bookmaker_note),
        )
    )
    price_code = escape(card.price_code, quote=True)
    price_note = _PRICE_NOTES.get(
        card.price_code,
        "Wettpreis separat prüfen. Die Prognose bleibt unverändert.",
    )
    if card.price_code == "PLAYABLE" and not card.confirmed_tip:
        price_note = (
            "Die Quote erreicht den Value-Bereich; noch kein freigegebener Tipp."
        )
    event_label = escape(card.event_label)
    return (
        f'<article class="wf-top-card" data-key="{escape(card.key, quote=True)}" '
        f'aria-label="Modellprognose für {escape(card.event_label, quote=True)}">'
        f"{_status_badges(card, featured=True)}"
        '<p class="wf-meta">'
        f'<span class="wf-sport">{escape(card.sport)}</span>'
        '<span aria-hidden="true"> · </span>'
        f'<span class="wf-start">{escape(card.scheduled_start_label)}</span></p>'
        f'<h3 class="wf-event">{event_label}</h3>'
        f'<p class="wf-market">{escape(card.market)}</p>'
        f'<p class="wf-selection">{escape(card.selection)}</p>'
        '<div class="wf-primary-probability">'
        '<span>Vorsichtige Trefferchance</span>'
        f'<strong>{escape(format_probability(card.cautious_probability))}</strong>'
        "</div>"
        f'<div class="wf-metric-grid">{metrics}</div>'
        f'<p class="wf-price-note wf-price-note-{escape(card.price_tone, quote=True)}" '
        f'data-price-code="{price_code}">{escape(price_note)}</p>'
        '<p class="wf-context"><span>Kontext:</span> '
        f"{escape(card.context_label)}</p>"
        "</article>"
    )


def _compact_row_markup(card: WettfinderCard) -> str:
    """Render one flat comparison row without duplicating full-card copy."""

    price = format_decimal_odds(card.observed_odds)
    bookmaker_note = card.bookmaker if price != "–" else None
    return (
        f'<article class="wf-row" data-key="{escape(card.key, quote=True)}" '
        f'data-price-code="{escape(card.price_code, quote=True)}" '
        f'aria-label="Modellprognose für {escape(card.event_label, quote=True)}">'
        '<div class="wf-row-event">'
        '<span class="wf-row-meta">'
        f"{escape(card.sport)} · {escape(card.scheduled_start_label)}</span>"
        f"<strong>{escape(card.event_label)}</strong></div>"
        '<div class="wf-row-pick">'
        f'<span class="wf-row-label">{escape(card.market)}</span>'
        f"<strong>{escape(card.selection)}</strong></div>"
        f'{_row_value("Modell", format_probability(card.model_probability))}'
        f'{_row_value("Vorsichtig", format_probability(card.cautious_probability))}'
        f'{_row_value("Value ab", format_decimal_odds(card.value_threshold))}'
        f'{_row_value("Aktuell", price, note=bookmaker_note)}'
        f"{_status_badges(card, featured=False)}"
        "</article>"
    )


def render_top_card_html(card: WettfinderCard) -> str:
    """Return escaped standalone markup for one top card."""

    return _top_card_markup(card)


def render_compact_row_html(card: WettfinderCard) -> str:
    """Return escaped standalone markup for one flat additional row."""

    return _compact_row_markup(card)


__all__ = [
    "WettfinderCard",
    "WettfinderCatalog",
    "WettfinderFixtureGroup",
    "WettfinderReleaseOverlay",
    "build_wettfinder_card",
    "compose_wettfinder_catalog",
    "format_decimal_odds",
    "format_probability",
    "format_scheduled_start",
    "render_compact_row_html",
    "render_top_card_html",
    "wettfinder_quote_binding_candidate",
    "wettfinder_recommendation_candidate",
]
