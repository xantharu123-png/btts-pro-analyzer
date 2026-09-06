"""Read-only Streamlit page renderer for the RisikoBet consumer surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Mapping, Optional

import streamlit as st

from riskobet_domain import (
    ContextState,
    EventModelSnapshot,
    EvidenceStage,
    FactorEvidence,
    FactorRole,
    RiskCandidate,
)
from riskobet_store import DEFAULT_DB_PATH, DEFAULT_LATEST_PATH, RiskBetStore
from riskobet_surface import (
    SPORT_FILTERS,
    RiskBetCard,
    RiskBetPriceOverlay,
    build_riskobet_card,
    compose_riskobet_catalog,
    format_riskobet_public_detail,
    render_riskobet_card_html,
    render_riskobet_compact_row_html,
)


_RUN_STATUSES = frozenset({"COMPLETE", "PARTIAL", "FAILED"})
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "started_at",
        "completed_at",
        "status",
        "snapshots",
        "candidates",
        "errors",
    }
)
_SNAPSHOT_KEYS = frozenset(
    {
        "snapshot_id",
        "event_key",
        "sport",
        "competition",
        "event_label",
        "starts_at",
        "modeled_at",
        "input_cutoff_at",
        "model_version",
        "input_hash",
        "factors",
        "missing_core_data",
    }
)
_FACTOR_KEYS = frozenset(
    {
        "factor_key",
        "summary",
        "source",
        "observed_at",
        "imported_at",
        "fresh_until",
        "coverage",
        "sample_size",
        "role",
    }
)
_CANDIDATE_KEYS = frozenset(
    {
        "candidate_id",
        "snapshot_id",
        "event_key",
        "sport",
        "competition",
        "event_label",
        "starts_at",
        "market_key",
        "market_label",
        "selection_key",
        "selection_label",
        "model_probability",
        "cautious_probability",
        "stage",
        "context_state",
        "policy_version",
        "pros",
        "cons",
        "missing_core_data",
        "settlement_contract",
        "featured",
        "stage_history",
        "settlements",
    }
)


class RiskBetViewError(ValueError):
    """The published consumer document is incomplete or inconsistent."""


@dataclass(frozen=True)
class RiskBetView:
    run_id: str
    status: str
    started_at: datetime
    completed_at: datetime
    candidates: tuple[RiskCandidate, ...]
    cards: tuple[RiskBetCard, ...]
    snapshots: Mapping[str, EventModelSnapshot]


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RiskBetViewError(f"{label} must be an object")
    return value


def _exact_keys(
    payload: Mapping[str, object],
    expected: frozenset[str],
    label: str,
) -> None:
    if set(payload) != expected:
        raise RiskBetViewError(f"{label} does not match schema version 1")


def _sequence(value: object, label: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes, Mapping)):
        raise RiskBetViewError(f"{label} must be a sequence")
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise RiskBetViewError(f"{label} must be a sequence") from exc


def _datetime(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise RiskBetViewError(f"{label} must be an ISO datetime")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RiskBetViewError(f"{label} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RiskBetViewError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _factor(payload: object) -> FactorEvidence:
    data = _mapping(payload, "factor")
    _exact_keys(data, _FACTOR_KEYS, "factor")
    try:
        return FactorEvidence(
            factor_key=data["factor_key"],
            summary=data["summary"],
            source=data["source"],
            observed_at=_datetime(data["observed_at"], "observed_at"),
            imported_at=_datetime(data["imported_at"], "imported_at"),
            fresh_until=_datetime(data["fresh_until"], "fresh_until"),
            coverage=data["coverage"],
            sample_size=data["sample_size"],
            role=FactorRole(data["role"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RiskBetViewError("factor failed domain validation") from exc


def _snapshot(payload: object) -> EventModelSnapshot:
    data = _mapping(payload, "snapshot")
    _exact_keys(data, _SNAPSHOT_KEYS, "snapshot")
    try:
        snapshot = EventModelSnapshot(
            event_key=data["event_key"],
            sport=data["sport"],
            competition=data["competition"],
            event_label=data["event_label"],
            starts_at=_datetime(data["starts_at"], "starts_at"),
            modeled_at=_datetime(data["modeled_at"], "modeled_at"),
            input_cutoff_at=_datetime(
                data["input_cutoff_at"], "input_cutoff_at"
            ),
            model_version=data["model_version"],
            input_hash=data["input_hash"],
            factors=tuple(_factor(item) for item in _sequence(data["factors"], "factors")),
            missing_core_data=tuple(
                _sequence(data["missing_core_data"], "missing_core_data")
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, RiskBetViewError):
            raise
        raise RiskBetViewError("snapshot failed domain validation") from exc
    if data["snapshot_id"] != snapshot.snapshot_id:
        raise RiskBetViewError("snapshot identity mismatch")
    return snapshot


def _candidate(payload: object) -> RiskCandidate:
    data = _mapping(payload, "candidate")
    _exact_keys(data, _CANDIDATE_KEYS, "candidate")
    # Consumer augmentations are not interpreted by the page, but their basic
    # shape remains schema checked so corrupt content cannot be half-rendered.
    if not isinstance(data["featured"], bool):
        raise RiskBetViewError("candidate featured flag is invalid")
    _sequence(data["stage_history"], "stage_history")
    _sequence(data["settlements"], "settlements")
    try:
        candidate = RiskCandidate(
            snapshot_id=data["snapshot_id"],
            event_key=data["event_key"],
            sport=data["sport"],
            competition=data["competition"],
            event_label=data["event_label"],
            starts_at=_datetime(data["starts_at"], "starts_at"),
            market_key=data["market_key"],
            market_label=data["market_label"],
            selection_key=data["selection_key"],
            selection_label=data["selection_label"],
            model_probability=data["model_probability"],
            cautious_probability=data["cautious_probability"],
            stage=EvidenceStage(data["stage"]),
            context_state=ContextState(data["context_state"]),
            policy_version=data["policy_version"],
            pros=tuple(_sequence(data["pros"], "pros")),
            cons=tuple(_sequence(data["cons"], "cons")),
            missing_core_data=tuple(
                _sequence(data["missing_core_data"], "missing_core_data")
            ),
            settlement_contract=data["settlement_contract"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, RiskBetViewError):
            raise
        raise RiskBetViewError("candidate failed domain validation") from exc
    if data["candidate_id"] != candidate.candidate_id:
        raise RiskBetViewError("candidate identity mismatch")
    return candidate


def _read_latest(path: str | Path | None) -> Optional[dict[str, object]]:
    # RiskBetStore.read_latest only depends on ``latest_path``.  Constructing a
    # read-only instance without __init__ avoids creating/opening SQLite merely
    # because a user visits the page.
    reader = object.__new__(RiskBetStore)
    reader.latest_path = Path(path) if path is not None else DEFAULT_LATEST_PATH
    payload = reader.read_latest()
    if payload is not None or path is not None:
        return payload
    # The SQLite database is the backed-up source of truth; latest JSON is a
    # derived, atomically replaceable consumer cache.  A restore may therefore
    # legitimately contain only the checkpointed database.  Recover through
    # the strict immutable read-only path without creating, migrating or
    # journaling anything from a page visit.
    return RiskBetStore.recover_latest_from_database(DEFAULT_DB_PATH)


def load_riskobet_view(path: str | Path | None = None) -> Optional[RiskBetView]:
    """Strictly hydrate the last atomically published read-only view."""

    payload = _read_latest(path)
    if payload is None:
        return None
    data = _mapping(payload, "RisikoBet payload")
    _exact_keys(data, _TOP_LEVEL_KEYS, "RisikoBet payload")
    if data["schema_version"] != 1:
        raise RiskBetViewError("unsupported RisikoBet schema")
    status = str(data["status"] or "").strip().upper()
    if status not in _RUN_STATUSES:
        raise RiskBetViewError("invalid RisikoBet run status")
    errors = _sequence(data["errors"], "errors")
    if any(not isinstance(item, str) or not item.strip() for item in errors):
        raise RiskBetViewError("invalid RisikoBet error summary")

    snapshots = tuple(
        _snapshot(item) for item in _sequence(data["snapshots"], "snapshots")
    )
    if len({item.snapshot_id for item in snapshots}) != len(snapshots):
        raise RiskBetViewError("duplicate snapshot identity")
    snapshot_by_id = {item.snapshot_id: item for item in snapshots}
    candidates = tuple(
        _candidate(item)
        for item in _sequence(data["candidates"], "candidates")
    )
    if len({item.candidate_id for item in candidates}) != len(candidates):
        raise RiskBetViewError("duplicate candidate identity")
    for candidate in candidates:
        snapshot = snapshot_by_id.get(candidate.snapshot_id)
        if snapshot is None:
            raise RiskBetViewError("candidate references an unknown snapshot")
        if (
            candidate.event_key != snapshot.event_key
            or candidate.sport != snapshot.sport
            or candidate.competition != snapshot.competition
            or candidate.event_label != snapshot.event_label
            or candidate.starts_at != snapshot.starts_at
        ):
            raise RiskBetViewError("candidate differs from its snapshot")

    try:
        cards = tuple(build_riskobet_card(item) for item in candidates)
    except (TypeError, ValueError) as exc:
        raise RiskBetViewError("candidate presentation is invalid") from exc
    return RiskBetView(
        run_id=str(data["run_id"] or "").strip(),
        status=status,
        started_at=_datetime(data["started_at"], "started_at"),
        completed_at=_datetime(data["completed_at"], "completed_at"),
        candidates=candidates,
        cards=cards,
        snapshots=snapshot_by_id,
    )


def _widget_suffix(candidate: RiskCandidate) -> str:
    return f"{candidate.candidate_id}-{candidate.snapshot_id}"


def _decimal_quote(value: object) -> Optional[float]:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        quote = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(quote) or quote <= 1.0:
        return None
    return quote


def _stored_manual_quote(candidate: RiskCandidate) -> Optional[float]:
    state = getattr(st, "session_state", {})
    key = f"riskobet-quote-{_widget_suffix(candidate)}"
    try:
        value = state.get(key)
    except AttributeError:
        value = None
    return _decimal_quote(value)


def _display_card(
    candidate: RiskCandidate,
    quote: Optional[float],
) -> RiskBetCard:
    overlay = (
        None
        if quote is None
        else RiskBetPriceOverlay(
            candidate_id=candidate.candidate_id,
            status="AVAILABLE",
            observed_odds=quote,
            bookmaker="Eigene Buchmacherquote",
        )
    )
    return build_riskobet_card(candidate, overlay)


def _render_factor_details(snapshot: EventModelSnapshot) -> None:
    st.caption("Grundlage dieser Analyse")
    visible_factors = tuple(
        factor
        for factor in snapshot.factors
        if factor.role is not FactorRole.DISPLAY_ONLY
    )
    if not visible_factors:
        st.caption("Keine zusätzlichen Kontextfaktoren hinterlegt.")
        return
    for factor in visible_factors:
        observed = factor.observed_at.astimezone(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        )
        # Streamlit write escapes text. Deliberately omit internal factor keys,
        # provider identifiers and numeric implementation roles.
        summary = format_riskobet_public_detail(factor.summary)
        st.write(f"{summary} · Stand: {observed}")


def _render_quote_comparison(candidate: RiskCandidate) -> None:
    suffix = _widget_suffix(candidate)
    quote_key = f"riskobet-quote-{suffix}"
    st.caption(
        "Optional: Die eigene Quote wird nur mit der Modellwahrscheinlichkeit "
        "verglichen. Sie verändert weder Auswahl noch Reihenfolge."
    )
    value = st.text_input(
        "Eigene Dezimalquote",
        placeholder="z. B. 3,20",
        key=quote_key,
    )
    quote = _decimal_quote(value)
    if value not in (None, "") and quote is None:
        st.info("Bitte eine gültige Dezimalquote größer als 1,00 eingeben.")
        return
    if quote is None:
        return
    if candidate.model_probability is None:
        st.info(
            "Der Vergleich ist ohne berechenbare Modellwahrscheinlichkeit "
            "ehrlich nicht möglich."
        )
        return
    implied = 1.0 / quote
    difference = candidate.model_probability - implied
    direction = "über" if difference >= 0 else "unter"
    st.info(
        f"Implizite Quotechance: {implied * 100:.1f} %. "
        f"Das Modell liegt {abs(difference) * 100:.1f} Prozentpunkte "
        f"{direction} dieser Chance."
    )


def _render_detail(
    candidate: RiskCandidate,
    snapshot: EventModelSnapshot,
) -> None:
    suffix = _widget_suffix(candidate)
    detail_key = f"riskobet-detail-{suffix}"
    with st.container(key=f"riskobet_actions_{suffix}"):
        st.caption("Modellstand: " + snapshot.modeled_at.astimezone(timezone.utc).strftime("%d.%m. %H:%M UTC"))
        visible_context = tuple(
            format_riskobet_public_detail(factor.summary)
            for factor in snapshot.factors
            if factor.role is FactorRole.DISPLAY_ONLY
            and factor.factor_key.startswith(("tennis_workload_", "football_context_"))
        )
        if visible_context:
            st.caption("Beobachteter Kontext – kein berechneter Zu-/Abschlag: " + " · ".join(visible_context[:4]))
        with st.expander(
            "Analyse anzeigen", expanded=False, key=detail_key
        ):
            _render_factor_details(snapshot)
        with st.container(key=f"riskobet_price_action_{suffix}"):
            with st.popover("Eigene Quote prüfen"):
                _render_quote_comparison(candidate)


def _render_featured(
    cards: tuple[RiskBetCard, ...],
    candidate_by_id: Mapping[str, RiskCandidate],
    snapshots: Mapping[str, EventModelSnapshot],
) -> None:
    if not cards:
        return
    st.markdown("## Szenarien nach Datenqualität")
    st.caption("Evidenz, Kontext und Modellunsicherheit bestimmen die Reihenfolge; nicht die Quote oder allein der Spielbeginn.")
    with st.container(key="riskobet_featured_grid"):
        # Build rows, not two persistent columns.  When CSS stacks the row at
        # tablet/mobile widths, DOM and visual order therefore remain the
        # quotenfreie model order (0, 1, 2) instead of becoming 0, 2, 1.
        for row_start in range(0, len(cards), 2):
            columns = st.columns(2)
            for offset, base_card in enumerate(cards[row_start : row_start + 2]):
                index = row_start + offset
                candidate = candidate_by_id[base_card.candidate_id]
                display_card = _display_card(
                    candidate, _stored_manual_quote(candidate)
                )
                with columns[offset]:
                    with st.container(key=f"riskobet_featured_card_{index}"):
                        st.markdown(
                            render_riskobet_card_html(display_card),
                            unsafe_allow_html=True,
                        )
                        _render_detail(
                            candidate,
                            snapshots[candidate.snapshot_id],
                        )


def _render_additional(
    cards: tuple[RiskBetCard, ...],
    candidate_by_id: Mapping[str, RiskCandidate],
    snapshots: Mapping[str, EventModelSnapshot],
) -> None:
    if not cards:
        return
    st.markdown("## Weitere Szenarien")
    page_size = 20
    pages = (len(cards) + page_size - 1) // page_size
    page = st.selectbox("Weitere Szenarien – Seite", range(1, pages + 1), key=f"riskobet-page-{len(cards)}") if pages > 1 else 1
    offset = (page - 1) * page_size
    visible_cards = cards[offset:offset + page_size]
    st.caption(f"{offset + 1}–{offset + len(visible_cards)} von {len(cards)} weiteren Szenarien")
    with st.container(key="riskobet_additional"):
        for index, base_card in enumerate(visible_cards, start=offset):
            candidate = candidate_by_id[base_card.candidate_id]
            display_card = _display_card(
                candidate, _stored_manual_quote(candidate)
            )
            with st.container(key=f"riskobet_additional_row_{index}"):
                st.markdown(
                    render_riskobet_compact_row_html(display_card),
                    unsafe_allow_html=True,
                )
                _render_detail(candidate, snapshots[candidate.snapshot_id])


def render_riskobet(path: str | Path | None = None) -> None:
    """Render the read-only RisikoBet page without any provider/model calls."""

    with st.container(key="riskobet_page"):
        try:
            view = load_riskobet_view(path)
        except (OSError, TypeError, ValueError):
            st.error(
                "RisikoBet-Daten können aktuell nicht sicher angezeigt "
                "werden. Bitte später erneut versuchen."
            )
            return
        if view is None:
            st.info("Aktuell liegen noch keine RisikoBet-Szenarien vor.")
            return
        if view.status == "FAILED":
            st.error(
                "Die letzte RisikoBet-Analyse konnte nicht bereitgestellt "
                "werden. Bitte später erneut versuchen."
            )
            return
        with st.container(key="riskobet_filters"):
            sport_filter = st.segmented_control(
                "Sport",
                SPORT_FILTERS,
                default="Alle",
                key="riskobet-sport-filter",
            )
        if sport_filter not in SPORT_FILTERS:
            sport_filter = "Alle"
        catalog = compose_riskobet_catalog(
            view.cards,
            sport_filter=sport_filter,
            max_featured=3,
        )
        event_count = len(
            {(card.sport_key, card.event_key) for card in catalog.cards}
        )
        completed = view.completed_at.astimezone(timezone.utc).strftime(
            "%d.%m.%Y %H:%M UTC"
        )
        with st.container(key="riskobet_summary"):
            if view.status == "PARTIAL":
                st.warning(
                    "Einige Sportarten wurden nicht vollständig aktualisiert. "
                    "Sichtbar sind nur bereits verarbeitete Daten; bitte den "
                    "jeweiligen Evidenzstand beachten."
                )
            if catalog.cards:
                scenario_label = (
                    "Szenario" if len(catalog.cards) == 1 else "Szenarien"
                )
                event_label = "Event" if event_count == 1 else "Events"
                st.caption(
                    f"{len(catalog.cards)} {scenario_label} aus {event_count} "
                    f"{event_label} · Stand: {completed}"
                )
        if not catalog.cards:
            st.info("Für diesen Sport sind aktuell keine Szenarien verfügbar.")
            return
        candidate_by_id = {
            candidate.candidate_id: candidate for candidate in view.candidates
        }
        _render_featured(catalog.featured, candidate_by_id, view.snapshots)
        _render_additional(catalog.additional, candidate_by_id, view.snapshots)


__all__ = [
    "RiskBetView",
    "RiskBetViewError",
    "load_riskobet_view",
    "render_riskobet",
]
