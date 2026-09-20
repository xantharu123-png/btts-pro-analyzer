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
    highlight_eligible: bool = False
    highlight_reason: str = "Modellgrundlagen nicht geprüft"
    analysis_data_age: str = ""
    compact_analysis: Optional[CompactAnalysis] = None
    # Separate from evidence qualification: coherence must still choose the
    # model's modal direction before any presentation-interest comparison.
    highlight_comparison: Optional[Comparison] = None
    quote_floor_excluded: bool = False


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
        return "Bestätigter Tipp", "positive"
    evidence_stage = str(signal.evidence_stage or "").strip().upper()
    if evidence_stage == "RELEASED":
        if signal.statistical_release_passed is True:
            return "Freigegeben", "positive"
        return "Freigabe ausstehend", "warning"
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
        highlight_eligible=not highlight_reason,
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
    if not card.highlight_eligible or card.quote_floor_excluded:
        return False
    if _token(card.sport) in {"fussball", "football"}:
        return card.highlight_comparison is not None
    return True


def _select_featured(
    cards: Iterable[WettfinderCard],
    *,
    max_featured: int,
) -> tuple[WettfinderCard, ...]:
    """Choose useful, sport-diverse cards without considering price data."""

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
    """Compose a coherent, price-neutral visible selection across all pages.

    Shared canonical coherence precedes every sport/section/page filter.
    Highlight qualification is retained from the common card-build clock;
    neutral descriptive rows stay visible in the additional section.
    """

    if (
        isinstance(max_featured, bool)
        or not isinstance(max_featured, int)
        or max_featured < 1
    ):
        raise ValueError("max_featured must be a positive integer")
    # Price may only remove a coherent proposal, never select its opposite.
    # Keep every input model unchanged, including the hidden low-price rows.
    original = [card for card in select_consumer_forecasts(cards) if not card.quote_floor_excluded]
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


def _status_badges(card: WettfinderCard, *, featured: bool) -> str:
    badges = []
    if featured and _can_feature(card):
        badges.append(
            '<span class="wf-badge wf-badge-top" '
            'aria-label="Aktuelle Modell-Auswahl">MODELL-AUSWAHL</span>'
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


def _analysis_markup(card: WettfinderCard, *, featured: bool = False) -> str:
    supporting_fact = (card.highlight_comparison.summary
                       if featured and _can_feature(card) and card.highlight_comparison else "")
    if card.compact_analysis is not None:
        return render_compact_analysis_html(card.compact_analysis, supporting_fact=supporting_fact)
    support = f'<p class="wf-analysis-support">{escape(supporting_fact)}</p>' if supporting_fact else ''
    samples = (
        f'<p class="wf-analysis-samples">{escape(card.analysis_samples)}</p>'
        if card.analysis_samples else ""
    )
    clocks = f'Berechnet: {format_model_clock(card.modeled_at)}'
    if card.analysis_data_age:
        clocks += ' · ' + card.analysis_data_age
    if card.highlight_reason:
        clocks += ' · Ohne Hervorhebung: ' + card.highlight_reason
    return (
        '<section class="wf-analysis">'
        '<h4>Warum diese Auswahl?</h4>'
        f'<p class="wf-analysis-basis">{escape(card.analysis_basis)}</p>'
        f'{support}'
        f'<p class="wf-analysis-caution">{escape(card.analysis_caution)}</p>'
        f"{samples}"
        f'<p class="wf-analysis-age">{escape(clocks)}</p>'
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


def _top_card_markup(card: WettfinderCard) -> str:
    price = format_decimal_odds(card.observed_odds)
    bookmaker_note = quote_display_note(card)
    metrics = "".join(
        (
            _metric("Sicherheitswert", format_probability(card.cautious_probability)),
            _metric("Risikopreis ab", format_decimal_odds(card.value_threshold)),
            _metric("Letzte Quote" if card.price_code == 'STALE' else "Quote" if card.price_code == 'OBSERVED' else "Aktuell", price, note=bookmaker_note),
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
        '<span>Modellwahrscheinlichkeit</span>'
        f'<strong>{escape(format_probability(card.model_probability))}</strong>'
        "</div>"
        f"{_analysis_markup(card, featured=True)}"
        f'<div class="wf-metric-grid">{metrics}</div>'
        '<p class="wf-uncertainty-note">Rechenwerte, keine gesicherte Mindestchance.</p>'
        '<details class="wf-fact wf-price-explain"><summary>Preisberechnung</summary>'
        '<div class="wf-fact-detail"><p>Sicherheitswert: Modell mit heuristischem '
        'Abschlag, keine statistisch bestätigte Mindestchance. Der Risikopreis '
        'ist eine Rechenschwelle, keine erwartete Buchmacherquote.</p></div></details>'
        f'<p class="wf-price-note wf-price-note-{escape(card.price_tone, quote=True)}" '
        f'data-price-code="{price_code}">{escape(price_note)}</p>'
        "</article>"
    )


def _compact_row_markup(card: WettfinderCard, *, grouped: bool = False, featured: bool = False) -> str:
    """Render one flat comparison row without duplicating full-card copy."""

    price = format_decimal_odds(card.observed_odds)
    bookmaker_note = quote_display_note(card)
    event = '' if grouped else (
        '<div class="wf-row-event"><span class="wf-row-meta">'
        f'{escape(card.sport)} · {escape(card.scheduled_start_label)}</span>'
        f'<strong>{escape(card.event_label)}</strong></div>'
    )
    group_attribute = ' data-grouped="true"' if grouped else ''
    # The prominent selection keeps its price caveat, even inside a game block.
    price_note = ''
    if featured:
        message = _PRICE_NOTES.get(card.price_code, 'Wettpreis separat prüfen.')
        if card.price_code == 'PLAYABLE' and not card.confirmed_tip:
            message = 'Die Quote erreicht den Value-Bereich; noch kein freigegebener Tipp.'
        price_note = (
            '<p class="wf-group-price-note">Sicherheitswert: heuristischer Abschlag, '
            'keine gesicherte Mindestchance. '
            f'{escape(message)}</p>'
        )
    return (
        f'<article class="wf-row"{group_attribute} data-key="{escape(card.key, quote=True)}" '
        f'data-price-code="{escape(card.price_code, quote=True)}" '
        f'aria-label="Modellprognose für {escape(card.event_label, quote=True)}">'
        f'{event}'
        '<div class="wf-row-pick">'
        f'<span class="wf-row-label">{escape(card.market)}</span>'
        f"<strong>{escape(card.selection)}</strong></div>"
        f'{_row_value("Modell", format_probability(card.model_probability))}'
        f'{_row_value("Sicherheitswert", format_probability(card.cautious_probability))}'
        f'{_row_value("Risikopreis ab", format_decimal_odds(card.value_threshold))}'
        f'{_row_value("Letzte Quote" if card.price_code == "STALE" else "Quote" if card.price_code == "OBSERVED" else "Aktuell", price, note=bookmaker_note)}'
        f"{_status_badges(card, featured=featured)}"
        f"{_analysis_markup(card, featured=featured)}"
        f'{price_note}'
        "</article>"
    )


def render_top_card_html(card: WettfinderCard) -> str:
    """Return escaped standalone markup for one top card."""

    return _top_card_markup(card)


def render_compact_row_html(card: WettfinderCard, *, grouped: bool = False, featured: bool = False) -> str:
    """Return escaped standalone markup for one flat additional row."""

    return _compact_row_markup(card, grouped=grouped, featured=featured)


__all__ = [
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
