"""Pure, price-neutral presentation data for the Wettfinder V2 surface.

This module deliberately owns no Streamlit state and does not evaluate a bet.
It turns loader-approved model rows and an already exact-bound consensus quote
into safe consumer-facing data, without letting price change model order or
probability.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from html import escape
import math
import re
from typing import Iterable, Mapping, Optional
import unicodedata
from zoneinfo import ZoneInfo

from bet_finder_ui import (
    _consumer_market_identity,
    _consumer_market_is_basis,
    consumer_fixture_label,
)
from ev_signal_sources import ModelSignal
from market_consensus import (
    MarketConsensus,
    ReferencePriceStatus,
    wettfinder_consensus,
    wettfinder_reference_price_status,
)


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


def _signal_quote_candidate(signal: ModelSignal) -> dict[str, object]:
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
) -> tuple[str, str, Optional[float], Optional[str]]:
    """Present a status without ever relabelling an old price as current."""

    labels = {
        "PLAYABLE": ("Spielbar", "positive"),
        "TOO_LOW": ("Unter Value", "muted"),
        "BORDERLINE": ("Quote offen", "warning"),
        "THIN": ("Quote zu dünn", "warning"),
        "STALE": ("Veraltet", "muted"),
        "UNAVAILABLE": ("Quote fehlt", "muted"),
        "INVALID_MINIMUM": ("Quote offen", "warning"),
    }
    label, tone = labels.get(status.code, ("Quote offen", "warning"))
    if status.code == "PLAYABLE":
        return label, tone, status.usable_odds, status.bookmaker
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
    if signal.evidence_stage == "RELEASED":
        if signal.statistical_release_passed is True:
            return "Freigegeben", "positive"
        return "Freigabe ausstehend", "warning"
    if signal.context_complete is True:
        return "Vollständig geprüft", "neutral"
    if signal.context_complete is False:
        return "Teilprüfung", "warning"
    return "Prüfung ausstehend", "muted"


def build_wettfinder_card(
    signal: ModelSignal,
    quote: object = None,
    *,
    now: Optional[datetime] = None,
    release_overlay: Optional[WettfinderReleaseOverlay] = None,
) -> WettfinderCard:
    """Map one model signal and its exact-key quote to a display card.

    ``release_overlay`` is the identity- and execution-bound output of the
    strict price/decision path. It is optional because a normal model forecast
    remains visible before any release decision exists.
    """

    normalized_quote = _normalise_quote(quote)
    status = wettfinder_reference_price_status(
        normalized_quote,
        signal.minimum_odds,
        candidate=_signal_quote_candidate(signal),
        now=now,
    )
    current_quote = wettfinder_consensus(normalized_quote, now=now)
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
        context_label=_clean_text(signal.context_summary, "Kontext ausstehend"),
        detail=_clean_text(signal.detail),
        confirmed_tip=confirmed_tip,
        reference_quote=normalized_quote,
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


def _display_pair(label: str, value: str) -> str:
    return (
        '<div class="wf-field"><span class="wf-label">'
        f"{escape(label)}</span><strong>{escape(value)}</strong></div>"
    )


def _card_markup(card: WettfinderCard, *, compact: bool) -> str:
    tag = "div" if compact else "article"
    classes = "wf-row" if compact else "wf-top-card"
    price = format_decimal_odds(card.observed_odds)
    bookmaker = card.bookmaker or "–"
    fields = "".join(
        (
            _display_pair("Sport / Start", f"{card.sport} · {card.scheduled_start_label}"),
            _display_pair("Begegnung", card.event_label),
            _display_pair("Markt", card.market),
            _display_pair("Auswahl", card.selection),
            _display_pair("Vorsichtig", format_probability(card.cautious_probability)),
            _display_pair("Modell", format_probability(card.model_probability)),
            _display_pair("Value ab", format_decimal_odds(card.value_threshold)),
            _display_pair("Quote", price),
            _display_pair("Buchmacher", bookmaker),
            _display_pair("Kontext", card.context_label),
            _display_pair("Modellhinweis", card.detail),
        )
    )
    return (
        f'<{tag} class="{classes}" data-key="{escape(card.key, quote=True)}">'
        f'<div class="wf-status wf-evidence-{escape(card.evidence_tone)}">'
        f"{escape(card.evidence_label)}</div>"
        f'<div class="wf-status wf-price-{escape(card.price_tone)}">'
        f"{escape(card.price_label)}</div>{fields}</{tag}>"
    )


def render_top_card_html(card: WettfinderCard) -> str:
    """Return escaped standalone markup for one top card."""

    return _card_markup(card, compact=False)


def render_compact_row_html(card: WettfinderCard) -> str:
    """Return escaped standalone markup for one flat additional row."""

    return _card_markup(card, compact=True)


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
]
