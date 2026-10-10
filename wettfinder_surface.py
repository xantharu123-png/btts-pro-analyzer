"""Pure, price-neutral presentation data for the Wettfinder V2 surface.

This module deliberately owns no Streamlit state and does not evaluate a bet.
It turns loader-approved model rows and an already exact-bound consensus quote
into safe consumer-facing data. The user floor excludes known offers below
1.20 after coherence; price never changes model probability or ranks survivors.
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
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from bet_finder_ui import (
    ReferencePriceEvaluation,
    _consumer_market_identity,
    consumer_fixture_label,
)
from ev_signal_sources import ModelSignal
from daily3_comparison import Comparison, football_form_comparison
from forecast_analysis import build_forecast_analysis, forecast_highlight_reason, format_model_clock
from forecast_compact import CompactAnalysis, build_compact_analysis, render_compact_analysis_html
from forecast_selection import select_consumer_forecasts
from forecast_price_checks import has_current_price_check
from market_consensus import (
    MarketConsensus,
    ReferencePriceStatus,
    quote_matches_candidate,
    quote_below_publication_floor,
    observed_consensus,
    wettfinder_consensus,
    wettfinder_reference_price_status,
)
from multi_sport_recommendations import RecommendationCandidate
from selection_coherence import consumer_event_identity


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
    cautious_probability: Optional[float]
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
    analysis_basis: str = ""
    analysis_caution: str = ""
    analysis_samples: str = ""
    # Original event binding, never reconstructed from a formatted display date
    # or a bookmaker quote. Shared coherence runs before sections/pagination.
    fixture_id: Optional[int] = None
    fixture_source: Optional[str] = None
    provider_event_id: Optional[str] = None
    scheduled_start: Optional[str] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    competitor_a: Optional[str] = None
    competitor_b: Optional[str] = None
    selected_competitor: Optional[str] = None
    competitor_a_id: Optional[str] = None
    competitor_b_id: Optional[str] = None
    modeled_at: Optional[str] = None
    input_cutoff_at: Optional[str] = None
    model_version: Optional[str] = None
    policy_version: Optional[str] = None
    model_scope: Optional[str] = None
    # Model evidence/clocks qualify direction independently of TOP context admission.
    model_eligible: bool = False
    highlight_eligible: bool = False
    # Admission only after price-blind whole-pool direction selection.
    price_check_completed: bool = False
    highlight_reason: str = "Modellgrundlagen nicht geprüft"
    analysis_data_age: str = ""
    compact_analysis: Optional[CompactAnalysis] = None
    # Separate from evidence qualification: coherence must still choose the
    # model's modal direction before any presentation-interest comparison.
    highlight_comparison: Optional[Comparison] = None
    quote_floor_excluded: bool = False
    # Optional presentation-only raster assets. Attached after model/price
    # selection; the builder never resolves images or performs network calls.
    home_image: Optional[str] = None
    away_image: Optional[str] = None
    home_image_credit: Optional[str] = None
    away_image_credit: Optional[str] = None
    home_image_source: Optional[str] = None
    away_image_source: Optional[str] = None
    home_image_crop: Optional[tuple[float, float, float]] = None
    away_image_crop: Optional[tuple[float, float, float]] = None


@dataclass(frozen=True)
class WettfinderFixtureGroup:
    """Selections for one sport-specific event identity."""

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
    """Price-neutral primary cards and logically compatible additional cards.

    The complete model pool remains upstream, not a list of contradictory
    standalone user recommendations. Section and page boundaries cannot reset
    the event's selected scenario.
    """

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

    text = _clean_text(value, "ausstehend")
    while True:
        cleaned = re.sub(
            r"^kontext(?:\s*:\s*|\s+)",
            "",
            text,
            count=1,
            flags=re.I,
        )
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
    rounded = f"{number * 100:.1f}"
    if rounded == "100.0" and number < 1:
        return ">99.9 %"
    if rounded == "0.0" and number > 0:
        return "<0.1 %"
    return f"{rounded} %"


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
        "fixture_source": signal.fixture_source,
        "provider_event_id": signal.provider_event_id,
        "competition": signal.competition,
    }


def wettfinder_recommendation_candidate(
    signal: ModelSignal,
) -> RecommendationCandidate:
    """Build the complete immutable price candidate represented by a signal."""

    probability = signal.probability * 100.0
    haircut = signal.probability_haircut * 100.0 if signal.probability_haircut is not None else None
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
        risk_adjusted_probability=round(probability - haircut, 2) if haircut is not None else None,
        probability_haircut=round(haircut, 2) if haircut is not None else None,
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
        "OBSERVED": ("Quote abgerufen", "neutral"),
    }
    if status.code == "PLAYABLE":
        # Report only what the price check established; the user decides
        # whether to place a bet, independently of internal model status.
        return (
            "Quote im Value-Bereich", "neutral",
            status.usable_odds, status.bookmaker,
        )
    label, tone = labels.get(status.code, ("Quote offen", "warning"))
    if status.code in {"TOO_LOW", "BORDERLINE", "THIN", "STALE", "OBSERVED"} and quote is not None:
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
        return "Modell geprüft", "positive"
    evidence_stage = str(signal.evidence_stage or "").strip().upper()
    if evidence_stage == "RELEASED":
        if signal.statistical_release_passed is True:
            return "Modell geprüft", "positive"
        return "Modellprüfung offen", "warning"
    if evidence_stage == "SHADOW":
        return "Evidenzprüfung", "warning"
    if evidence_stage == "RESEARCH":
        return ("Modell noch nicht unabhängig bestätigt" if signal.source == 'team_sport_research' else "Forschungsmodell"), "muted"
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

    now = now or (price_evaluation.evaluated_at if price_evaluation else datetime.now(timezone.utc))
    if signal.probability_haircut is None and release_overlay is not None:
        raise ValueError('Research forecast cannot receive a release overlay')
    if price_evaluation is None:
        normalized_quote = _normalise_quote(quote)
        status = wettfinder_reference_price_status(
            normalized_quote,
            signal.minimum_odds,
            candidate=wettfinder_quote_binding_candidate(signal),
            now=now,
        )
        current_quote = wettfinder_consensus(normalized_quote, now=now) or observed_consensus(
            normalized_quote, candidate=wettfinder_quote_binding_candidate(signal), now=now)
        if status.code == 'UNAVAILABLE':
            current_quote = None
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
    cautious_probability = model_probability - float(signal.probability_haircut) if signal.probability_haircut is not None else None
    analysis = build_forecast_analysis(signal, now=now)
    highlight_reason = forecast_highlight_reason(signal, now=now, analysis=analysis)
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
        analysis_basis=analysis.basis,
        analysis_caution=analysis.caution,
        analysis_samples=analysis.samples,
        fixture_id=signal.fixture_id,
        fixture_source=signal.fixture_source,
        provider_event_id=signal.provider_event_id,
        scheduled_start=signal.scheduled_start,
        home_team=signal.home_team,
        away_team=signal.away_team,
        home_team_id=signal.home_team_id,
        away_team_id=signal.away_team_id,
        competitor_a=signal.competitor_a,
        competitor_b=signal.competitor_b,
        selected_competitor=signal.selected_competitor,
        competitor_a_id=signal.competitor_a_id,
        competitor_b_id=signal.competitor_b_id,
        modeled_at=signal.modeled_at,
        input_cutoff_at=signal.input_cutoff_at,
        model_version=signal.model_version,
        policy_version=signal.policy_version,
        model_scope=signal.model_scope,
        model_eligible=not forecast_highlight_reason(signal, now=now, analysis=analysis, check_context=False),
        highlight_eligible=not highlight_reason,
        price_check_completed=has_current_price_check(signal, now=now, quote=normalized_quote),
        highlight_reason=highlight_reason,
        analysis_data_age=analysis.data_age,
        compact_analysis=build_compact_analysis(signal, analysis, now=now),
        highlight_comparison=(football_form_comparison(signal, now=now)
                              if not highlight_reason else None),
        quote_floor_excluded=quote_below_publication_floor(
            normalized_quote, candidate=wettfinder_quote_binding_candidate(signal), now=now),
    )


def _fixture_identity(card: WettfinderCard) -> str:
    return consumer_event_identity(card)


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


def _can_feature(card: WettfinderCard) -> bool:
    if not card.highlight_eligible or not card.price_check_completed:
        return False
    if _token(card.sport) in {"fussball", "football"}:
        return card.highlight_comparison is not None
    return True


def _select_featured(
    cards: Iterable[WettfinderCard],
    *,
    max_featured: int,
) -> tuple[WettfinderCard, ...]:
    """Admit actually checked cards, then rank without considering price values."""

    # Rank football only after whole-pool directional coherence. Keep the
    # other sports' evidence rules and cross-sport rotation; no quote or
    # raw-probability ranking, and no quota filled with unsupported forecasts.
    queues: OrderedDict[str, list[WettfinderCard]] = OrderedDict()
    for card in cards:
        if _can_feature(card):
            queues.setdefault(_token(card.sport), []).append(card)
    for sport, queue in queues.items():
        if sport in {"fussball", "football"}:
            queue.sort(key=lambda card: (-card.highlight_comparison.margin, card.key))
    ranked = _round_robin_by_sport(card for queue in queues.values() for card in queue)
    selected: list[WettfinderCard] = []
    fixtures: set[str] = set()
    markets: set[str] = set()
    for card in ranked:
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
    """Compose coherent selections, then apply the known-offer minimum.

    Shared canonical coherence precedes every sport/section/page filter.
    Highlight qualification is retained from the common card-build clock;
    Unknown prices remain visible. The floor cannot select another direction.
    """

    if (
        isinstance(max_featured, bool)
        or not isinstance(max_featured, int)
        or max_featured < 1
    ):
        raise ValueError("max_featured must be a positive integer")
    original = [card for card in select_consumer_forecasts(cards)
                if not card.quote_floor_excluded]
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


def group_wettfinder_games(catalog: WettfinderCatalog) -> tuple[WettfinderFixtureGroup, ...]:
    """Move all displayed markets of a game into one block, including highlights.

    No new selection, ranking, price check or truncation. Coherence has already
    run on the complete pool. Highlighted games come first; each card stays the
    original object and appears once.
    """
    return _group_additional((*catalog.featured, *catalog.additional))


def wettfinder_game_label(group: WettfinderFixtureGroup) -> str:
    """Plain event facts, safely escaped for Streamlit's Markdown labels."""
    first = group.cards[0]
    noun = 'Auswahl' if len(group.cards) == 1 else 'Auswahlen'
    label = f'{group.label} · {first.sport} · {first.scheduled_start_label} · {len(group.cards)} {noun}'
    return re.sub(r'([\\`*_{}\[\]()<>!|~#])', r'\\\1', ' '.join(label.split()))


_PRICE_NOTES = {
    "PLAYABLE": "Quote im Value-Bereich.",
    "TOO_LOW": "Quote unter Value.",
    "BORDERLINE": "Value nur bei einzelnen Anbietern.",
    "THIN": "Wenige Vergleichsanbieter.",
    "STALE": "Letzter Quotenstand · beim Buchmacher prüfen.",
    "UNAVAILABLE": "Quote fehlt · eigene Quote prüfen.",
    "INVALID_MINIMUM": "Die Value-Grenze ist aktuell nicht belastbar.",
}


def _status_badges(card: WettfinderCard, *, featured: bool, show_price: bool = True) -> str:
    badges = []
    if featured and _can_feature(card):
        badges.append(
            '<span class="wf-badge wf-badge-top" '
            'aria-label="Aktuelle Modell-Auswahl">MODELL-AUSWAHL</span>'
        )
    if show_price:
        badges.append(
            '<span class="wf-badge wf-badge-price '
            f'wf-price-{escape(card.price_tone, quote=True)}">'
            f"{escape(card.price_label)}</span>"
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


def _analysis_markup(card: WettfinderCard, *, featured: bool = False) -> str:
    supporting_fact = (card.highlight_comparison.summary
                       if featured and _can_feature(card) and card.highlight_comparison else "")
    if card.compact_analysis is not None:
        return render_compact_analysis_html(card.compact_analysis, supporting_fact=supporting_fact, instance_key=card.key)
    support = f'<p class="wf-analysis-support">{escape(supporting_fact)}</p>' if supporting_fact else ''
    return (
        '<section class="wf-analysis">'
        '<h4>Warum diese Auswahl?</h4>'
        f'{support}'
        '<p>Für diese Auswahl liegen keine weiteren Spielstatistiken vor.</p>'
        '</section>'
    )


def quote_display_note(card: WettfinderCard) -> Optional[str]:
    if card.observed_odds is None:
        return None
    parts = [card.bookmaker] if card.bookmaker else []
    if card.reference_quote is not None:
        point = next((p for p in card.reference_quote.points
                      if p.bookmaker == card.bookmaker and abs(p.odds-card.observed_odds) < 0.000001), None)
        stamp = point.observed_at if point else card.reference_quote.quoted_at
        if stamp:
            parts.append(('Abgerufen: ' if card.price_code == 'OBSERVED' else 'Stand: ') + format_model_clock(stamp))
    return ' · '.join(parts) or None


def _top_card_markup(card: WettfinderCard, *, show_price: bool = True) -> str:
    metrics = ''
    price_details = ''
    if show_price:
        price = format_decimal_odds(card.observed_odds)
        bookmaker_note = quote_display_note(card)
        metrics += _metric("Risikopreis ab", format_decimal_odds(card.value_threshold))
        metrics += _metric(
            "Letzte Quote" if card.price_code == 'STALE' else
            "Quote" if card.price_code == 'OBSERVED' else "Aktuell",
            price, note=bookmaker_note,
        )
        price_note = _PRICE_NOTES.get(card.price_code, "Wettpreis separat prüfen. Die Prognose bleibt unverändert.")
        price_details = (
            f'<p class="wf-price-note wf-price-note-{escape(card.price_tone, quote=True)}" '
            f'data-price-code="{escape(card.price_code, quote=True)}">{escape(price_note)}</p>'
        )
    event_label = escape(card.event_label)
    return (
        f'<article class="wf-top-card" data-key="{escape(card.key, quote=True)}" '
        f'aria-label="Modellprognose für {escape(card.event_label, quote=True)}">'
        f"{_status_badges(card, featured=True, show_price=show_price)}"
        '<p class="wf-meta">'
        f'<span class="wf-sport">{escape(card.sport)}</span>'
        '<span aria-hidden="true"> · </span>'
        f'<span class="wf-start">{escape(card.scheduled_start_label)}</span></p>'
        f'<h3 class="wf-event">{event_label}</h3>'
        f'<p class="wf-market">{escape(card.market)}</p>'
        f'<p class="wf-selection">{escape(card.selection)}</p>'
        '<div class="wf-primary-probability">'
        '<span>Modellwahrscheinlichkeit</span>'
        f'<strong>{escape(format_probability(card.model_probability))}</strong>'
        "</div>"
        f"{_analysis_markup(card, featured=True)}"
        f'<div class="wf-metric-grid">{metrics}</div>'
        f'{price_details}'
        "</article>"
    )


def _compact_row_markup(card: WettfinderCard, *, grouped: bool = False, featured: bool = False, show_price: bool = True) -> str:
    """Render one flat comparison row without duplicating full-card copy."""

    event = '' if grouped else (
        '<div class="wf-row-event"><span class="wf-row-meta">'
        f'{escape(card.sport)} · {escape(card.scheduled_start_label)}</span>'
        f'<strong>{escape(card.event_label)}</strong></div>'
    )
    group_attribute = ' data-grouped="true"' if grouped else ''
    price_columns = ''
    if show_price:
        price = format_decimal_odds(card.observed_odds)
        bookmaker_note = quote_display_note(card)
        price_columns = (
            f'{_row_value("Risikopreis ab", format_decimal_odds(card.value_threshold))}'
            f'{_row_value("Letzte Quote" if card.price_code == "STALE" else "Quote" if card.price_code == "OBSERVED" else "Aktuell", price, note=bookmaker_note)}'
        )
    uncertainty_note = ''
    if featured and show_price:
        message = _PRICE_NOTES.get(card.price_code, 'Wettpreis separat prüfen.') if show_price else ''
        uncertainty_note = (
            f'<p class="wf-group-price-note">{escape(message)}</p>'
        )
    price_attribute = f' data-price-code="{escape(card.price_code, quote=True)}"' if show_price else ''
    return (
        f'<article class="wf-row"{group_attribute} data-key="{escape(card.key, quote=True)}"{price_attribute} '
        f'aria-label="Modellprognose für {escape(card.event_label, quote=True)}">'
        f'{event}'
        '<div class="wf-row-pick">'
        f'<span class="wf-row-label">{escape(card.market)}</span>'
        f"<strong>{escape(card.selection)}</strong></div>"
        f'{_row_value("Modell", format_probability(card.model_probability))}'
        f'{price_columns}'
        f"{_status_badges(card, featured=featured, show_price=show_price)}"
        f"{_analysis_markup(card, featured=featured)}"
        f'{uncertainty_note}'
        "</article>"
    )


def render_top_card_html(card: WettfinderCard, *, show_price: bool = True) -> str:
    """Return escaped standalone markup for one top card."""

    return _top_card_markup(card, show_price=show_price)


def render_compact_row_html(card: WettfinderCard, *, grouped: bool = False, featured: bool = False, show_price: bool = True) -> str:
    """Return escaped standalone markup for one flat additional row."""

    return _compact_row_markup(card, grouped=grouped, featured=featured, show_price=show_price)


def _safe_identity_image_uri(value: object) -> Optional[str]:
    """Only reviewed CDN paths; image bytes never pass through this server."""
    from sports_identity_media import safe_participant_image_url
    return safe_participant_image_url(value)


def _safe_identity_image_source(value: object) -> Optional[str]:
    """Only a canonical Wikimedia Commons file page may be an attribution link."""
    if not isinstance(value, str) or len(value) > 2048:
        return None
    if re.search(r'[\s<>"\'\\]', value) or re.search(r"%(?![0-9a-fA-F]{2})", value):
        return None
    try:
        source = urlsplit(value)
        path = unquote(source.path, encoding="utf-8", errors="strict")
    except (ValueError, UnicodeDecodeError):
        return None
    if (
        source.scheme != "https" or source.netloc != "commons.wikimedia.org"
        or not path.startswith("/wiki/File:") or path == "/wiki/File:"
        or source.query or source.fragment
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
    ):
        return None
    return value


def _safe_identity_crop_style(value: object) -> str:
    """A bounded numeric focal point/zoom, never caller-provided CSS markup."""
    if type(value) not in (tuple, list) or len(value) != 3:
        return ''
    if any(isinstance(number, bool) or not isinstance(number, (int, float)) for number in value):
        return ''
    try:
        x, y, scale = (float(number) for number in value)
    except (ValueError, OverflowError):
        return ''
    if not all(math.isfinite(number) for number in (x, y, scale)):
        return ''
    if not (0 <= x <= 100 and 0 <= y <= 100 and 1 <= scale <= 3):
        return ''
    # Formatting only converted floats prevents objects/strings from injecting
    # styles. Canonical zero avoids a redundant negative-zero percentage.
    focal_x, focal_y, zoom = (format(number or 0.0, '.6g') for number in (x, y, scale))
    return f'transform:scale({zoom});transform-origin:{focal_x}% {focal_y}%'


def render_match_header_html(card: WettfinderCard) -> str:
    """Keep the original shield, with verified portraits/crests or neutral initials."""
    first = card.home_team or card.competitor_a
    second = card.away_team or card.competitor_b
    if not first or not second:
        return f'<p class="se-event">{escape(card.event_label)}</p>'
    sport = _token(card.sport)
    image_kind = {'tennis': 'tennis', 'fussball': 'football', 'football': 'football',
                  'soccer': 'football', 'basketball': 'basketball', 'eishockey': 'ice_hockey',
                  'ice_hockey': 'ice_hockey', 'cricket': 'cricket',
                  'e_sport': 'esports', 'esport': 'esports', 'esports': 'esports'}.get(sport)

    def team(name, image_value, credit_value, source_value, crop_value):
        initials = ''.join(word[0] for word in name.split()[:2]).upper()
        image_uri = _safe_identity_image_uri(image_value) if image_kind else None
        if image_uri:
            from sports_identity_media import participant_image_url_matches_kind
            if not participant_image_url_matches_kind(image_kind, image_uri):
                image_uri = None
        attribution = ''
        if image_uri:
            crop_style = _safe_identity_crop_style(crop_value)
            image_style = f' style="{escape(crop_style, quote=True)}"' if crop_style else ''
            shield = (
                f'<span class="se-shield se-shield-image se-shield-{image_kind}" aria-hidden="true">'
                f'<span class="se-image-initials">{escape(initials)}</span>'
                f'<img src="{escape(image_uri, quote=True)}" alt="" decoding="async" loading="lazy" '
                f'referrerpolicy="no-referrer"{image_style}></span>'
            )
            source = _safe_identity_image_source(source_value)
            if source:
                credit = str(credit_value).strip() if credit_value is not None else ''
                credit = credit or "Wikimedia Commons"
                credit_label = '© Foto' if image_kind == 'tennis' else '© Logo'
                attribution = (
                    f'<a class="se-image-credit" href="{escape(source, quote=True)}" '
                    f'target="_blank" rel="noopener noreferrer" title="{escape(credit, quote=True)}" '
                    f'aria-label="Bildnachweis: {escape(credit, quote=True)}">{credit_label}</a>'
                )
        else:
            shield = f'<span class="se-shield" aria-hidden="true">{escape(initials)}</span>'
        return (f'<div class="se-team"><span class="se-identity">{shield}{attribution}</span>'
                f'<strong>{escape(name)}</strong></div>')
    return ('<div class="se-match">' + team(first, card.home_image, card.home_image_credit, card.home_image_source, card.home_image_crop)
        + f'<div class="se-match-time"><span>{escape(card.sport)}</span><b>VS</b>'
        + f'<span>{escape(card.scheduled_start_label)}</span></div>'
        + team(second, card.away_image, card.away_image_credit, card.away_image_source, card.away_image_crop) + '</div>')


def render_editorial_card_html(card: WettfinderCard, *, grouped=False, featured=False, supporting_fact='', show_form=True, include_match=False) -> str:
    """Sport-first customer facts; raw model notes stay on the card object."""
    has_match = not grouped or include_match
    head = render_match_header_html(card) if has_match else ''
    note = quote_display_note(card)
    quote_label = 'Letzte Quote' if card.price_code == 'STALE' else 'Quote'
    quote_note = f' title="{escape(note, quote=True)}"' if note else ''
    quote_html = f'<div class="se-number se-number-quote"{quote_note}><span>{quote_label}</span><strong>{escape(format_decimal_odds(card.observed_odds))}</strong></div>'
    if card.compact_analysis is not None:
        compact = card.compact_analysis
        if not supporting_fact and featured and _can_feature(card) and card.highlight_comparison is not None:
            supporting_fact = card.highlight_comparison.summary
        analysis_html = render_compact_analysis_html(compact,
            instance_key=card.key, show_form=show_form, show_summary=False)
        reason = '<p class="wf-analysis-short">' + escape(compact.summary) + '</p>'
        if supporting_fact:
            reason += '<p class="se-reason-support">' + escape(supporting_fact) + '</p>'
    else:
        analysis_html = _analysis_markup(card, featured=featured)
        reason = ''
    reason_html = ('<div class="se-reason"><h4>Die Auswahl im Kurzcheck</h4>' + reason + '</div>') if reason else ''
    secondary = grouped and not include_match
    if secondary:
        analysis_html = ('<details class="se-market-details"><summary>Analyse & Details</summary>'
                         + reason_html + analysis_html + '</details>')
        reason_html = ''
    return (
        f'<article class="wf-row se-card" data-key="{escape(card.key, quote=True)}"'
        + (' data-grouped="true"' if grouped else '')
        + f' aria-label="Modellprognose für {escape(card.event_label, quote=True)}">'
        + ('<div class="se-card-top">' + head if has_match else '<div class="se-card-top se-card-top-market">')
        + '<div class="se-pick-and-reason"><div class="se-pick"><div class="se-pick-label">'
        f'<span>{escape(card.market)}</span><strong>{escape(card.selection)}</strong></div>'
        f'<div class="se-number"><span aria-label="Modellchance">Modell</span><strong>{escape(format_probability(card.model_probability))}</strong></div>'
        f'{quote_html}</div>{reason_html}</div></div>{analysis_html}</article>'
    )


__all__ = [
    "render_editorial_card_html",
    "render_match_header_html",
    "WettfinderCard",
    "WettfinderCatalog",
    "WettfinderFixtureGroup",
    "WettfinderReleaseOverlay",
    "build_wettfinder_card",
    "compose_wettfinder_catalog",
    "group_wettfinder_games",
    "wettfinder_game_label",
    "format_decimal_odds",
    "format_probability",
    "format_scheduled_start",
    "render_compact_row_html",
    "render_top_card_html",
    "wettfinder_quote_binding_candidate",
    "wettfinder_recommendation_candidate",
]
