"""Read-only Streamlit page renderer for the RisikoBet consumer surface."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from html import escape
import json
import math
from pathlib import Path
from typing import Mapping, Optional

import streamlit as st
from date_context import format_zurich_time
from tip_display_order import display_order_control, ordered_event_rows
from context_links import ContextReference
from team_sport_forecasts import TeamSportForecast
from betting_math import odds_below_publication_floor
from riskobet_candidates import (
    FOOTBALL_GOAL_HISTORY_SCHEMA,
    FOOTBALL_GOAL_HISTORY_LABELS,
    football_goal_history_source,
)

from riskobet_domain import (
    ContextState,
    EventModelSnapshot,
    EvidenceStage,
    FactorEvidence,
    FactorRole,
    RiskCandidate,
)
from riskobet_store import DEFAULT_DB_PATH, DEFAULT_LATEST_PATH, RiskBetStore
from riskobet_prices import load_shared_price_overlays
from riskobet_surface import (
    SPORT_FILTERS,
    RiskBetCard,
    RiskBetPriceOverlay,
    build_riskobet_card,
    compose_riskobet_catalog,
    compact_riskobet_tennis_form,
    customer_riskobet_note,
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
    optional = {"context_ref", "team_sport_forecast", "customer_recent_results"} & data.keys()
    _exact_keys(data, _SNAPSHOT_KEYS | optional, "snapshot")
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
            context_ref=ContextReference.from_dict(data["context_ref"]) if "context_ref" in data else None,
            team_sport_forecast=(
                TeamSportForecast.from_dict(data["team_sport_forecast"])
                if "team_sport_forecast" in data else None
            ),
            customer_recent_results=data.get('customer_recent_results'),
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


def upcoming_riskobet_candidates(
    view: RiskBetView,
    *,
    now: Optional[datetime] = None,
) -> tuple[RiskCandidate, ...]:
    """Project upcoming suggestions without mutating the published history.

    The exact snapshot-bound start is authoritative for this read-only view.
    A schedule change needs its own published revision; a clock comparison
    must not silently rewrite an old forecast or imply a finished result.
    """
    current = datetime.now(timezone.utc) if now is None else now
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise RiskBetViewError("upcoming comparison clock must be timezone-aware")
    current = current.astimezone(timezone.utc)
    return tuple(candidate for candidate in view.candidates if candidate.starts_at > current)


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
    *,
    price: Optional[RiskBetPriceOverlay] = None,
    snapshot: Optional[EventModelSnapshot] = None,
    now: Optional[datetime] = None,
) -> RiskBetCard:
    overlay = price
    # Private comparison text has no provider/book/time proof and cannot
    # publish a tip or overwrite the exact shared observation.
    del quote
    return build_riskobet_card(candidate, overlay, snapshot=snapshot, now=now)


def _customer_factor_detail(factor: FactorEvidence) -> str:
    """Project sporting observations without changing their frozen evidence."""
    if (factor.factor_key.startswith('football_highlight_context_checks_')
            or factor.factor_key.startswith('football_goal_history_')
            or factor.factor_key in {'tennis_calibrated_match_model', 'esports_subgraph_elo'}
            or factor.factor_key.startswith('football_fixture_id:')):
        return ''
    raw = factor.summary
    # These old/current templates describe implementation, not an extra
    # sporting observation. Expected goals/margins and other real facts stay.
    if raw.startswith((
        'Aus den Punktedifferenzen geschätzte Streuung:',
        'Kalibriertes Sieger-Modell', 'Siegermodell:',
        'Subgraph-Elo ', 'Spielstärke-Abstand:',
        'Das geglättete Log5-Modell', 'Forschungsmodell ohne ',
        'Berechnet:', 'Modellstand:', 'Sicherheitswert:', 'Evidenzprüfung',
    )) or factor.factor_key.startswith('prematch_model_') and 'Stärkedifferenz:' in raw:
        return ''
    if factor.factor_key == 'esports_recent_form':
        raw = raw.removesuffix(' Im Elo berücksichtigt.')
    summary = customer_riskobet_note(raw)
    # A technical fallback is not a substitute for a sporting fact.
    if summary == 'Technischer Prüfstatus ist noch nicht nutzerverständlich aufbereitet.':
        return ''
    return summary


def _factor_detail_rows(snapshot: EventModelSnapshot) -> tuple[str, ...]:
    visible_factors = tuple(
        (factor, _customer_factor_detail(factor))
        for factor in snapshot.factors
        if factor.role is not FactorRole.DISPLAY_ONLY
        and factor.factor_key != "esports_recent_form"
    )
    visible_factors = tuple((factor, summary) for factor, summary in visible_factors if summary)
    rows = []
    for factor, summary in visible_factors:
        observed = format_zurich_time(factor.observed_at)
        # Streamlit write escapes text. Deliberately omit internal factor keys,
        # provider identifiers and numeric implementation roles.
        rows.append(f"{summary} · Stand: {observed}")
    return tuple(rows)


def _render_factor_details(snapshot: EventModelSnapshot) -> None:
    for detail in _factor_detail_rows(snapshot):
        st.write(detail)


def _football_goal_history_html(candidate: RiskCandidate, snapshot: EventModelSnapshot) -> str:
    """Render only structured, snapshot-owned observed counts, never prose guesses."""
    if (snapshot.sport != 'football' or candidate.sport != 'football'
            or candidate.snapshot_id != snapshot.snapshot_id
            or candidate.event_key != snapshot.event_key
            or candidate.event_label != snapshot.event_label
            or candidate.starts_at != snapshot.starts_at):
        return ''
    factors = tuple(f for f in snapshot.factors if f.factor_key.startswith('football_goal_history_'))
    if not factors:
        return ''
    def unique_object(pairs):
        parsed = dict(pairs)
        if len(parsed) != len(pairs):
            raise ValueError('duplicate goal-history field')
        return parsed

    source = football_goal_history_source(event_key=snapshot.event_key, starts_at=snapshot.starts_at,
        modeled_at=snapshot.modeled_at, input_cutoff_at=snapshot.input_cutoff_at,
        input_hash=snapshot.input_hash)
    windows = {}
    for factor in factors:
        if (factor.role is not FactorRole.DISPLAY_ONLY or factor.sample_size != 0
                or factor.coverage is not None or factor.source != source
                or factor.observed_at > snapshot.input_cutoff_at
                or factor.imported_at != snapshot.modeled_at
                or factor.fresh_until != snapshot.starts_at):
            return ''
        try:
            raw = json.loads(factor.summary, object_pairs_hook=unique_object)
        except (ValueError, TypeError):
            return ''
        if (not isinstance(raw, dict) or set(raw) != {'schema', 'window', 'teams', 'samples', 'rows'}
                or raw['schema'] != FOOTBALL_GOAL_HISTORY_SCHEMA
                or type(raw['window']) is not int or raw['window'] not in (5, 10)
                or factor.factor_key != 'football_goal_history_'+str(raw['window'])):
            return ''
        window, teams, samples, rows = raw['window'], raw['teams'], raw['samples'], raw['rows']
        if (not isinstance(teams, list) or len(teams) != 2
                or any(not isinstance(team, str) or not team.strip() or len(team) > 200 for team in teams)
                or teams[0].casefold() == teams[1].casefold()
                or snapshot.event_label != f'{teams[0]} vs {teams[1]}'
                or not isinstance(samples, list) or len(samples) != 2
                or any(type(n) is not int or not 1 <= n <= window for n in samples)
                or window == 10 and samples != [10, 10]
                or not isinstance(rows, list) or len(rows) != 8):
            return ''
        for label, row in zip(FOOTBALL_GOAL_HISTORY_LABELS, rows):
            if (not isinstance(row, list) or len(row) != 3 or row[0] != label
                    or any(type(hits) is not int or not 0 <= hits <= sample
                           for hits, sample in zip(row[1:], samples))):
                return ''
        if any(rows[index+4][side] > rows[index][side] for index in range(4) for side in (1, 2)):
            return ''
        windows[window] = raw
    if 5 not in windows or len(windows) != len(factors):
        return ''
    if 10 in windows and (windows[10]['teams'] != windows[5]['teams']
            or windows[5]['samples'] != [5, 5]
            or any(not 0 <= ten[side]-five[side] <= 5
                   for five, ten in zip(windows[5]['rows'], windows[10]['rows']) for side in (1, 2))):
        return ''
    group = 'riskobet-goals-' + snapshot.snapshot_id
    ten_control = (f'<input id="{group}-10" type="radio" name="{group}" value="10">'
        f'<label for="{group}-10">10 Spiele</label>') if 10 in windows else (
        '<span class="form-ten-unavailable" title="Weniger als zehn Ergebnisse erfasst">10 Spiele</span>')
    tables = []
    for window, raw in sorted(windows.items()):
        headings = ''.join(f'<th scope="col">{escape(team)}</th>' for team in raw['teams'])
        body = ''
        for label, home, away in raw['rows']:
            display = ('Sieg + ' + label[1:] if label.startswith('W') else label + ' Tore').replace('-', '–')
            body += (f'<tr><th scope="row">{display}</th><td>{home}/{raw["samples"][0]}</td>'
                     f'<td>{away}/{raw["samples"][1]}</td></tr>')
        tables.append(f'<div class="form-window form-window-{window}"><section class="form-goal-markets">'
            f'<table><thead><tr><th scope="col">Gesamttore</th>{headings}</tr></thead>'
            f'<tbody>{body}</tbody></table></section></div>')
    return ('<section class="sports-form" aria-label="Historische Multigoal-Treffer">'
        '<div class="form-heading"><h4>Multigoal &amp; Sieg-Kombis</h4>'
        '<div class="form-toggle" role="group" aria-label="Anzahl Spiele">'
        f'<input id="{group}-5" type="radio" name="{group}" value="5" aria-label="5 Spiele (Standardansicht)">'
        f'<label for="{group}-5">5 Spiele</label>{ten_control}</div></div>'
        '<small>Historische Treffer / erfasste Spiele · Sieg des jeweiligen Teams · keine Modellchance</small>'
        + ''.join(tables) + '</section>')


def _render_quote_comparison(candidate: RiskCandidate) -> None:
    suffix = _widget_suffix(candidate)
    quote_key = f"riskobet-quote-{suffix}"
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
    if odds_below_publication_floor(quote):
        st.info('Unter 1,20 · nicht als Vorschlag anzeigen.')
        return
    if candidate.model_probability is None:
        st.info('Modellchance noch offen.')
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
    *,
    show_goal_history: bool = True,
) -> None:
    suffix = _widget_suffix(candidate)
    detail_key = f"riskobet-detail-{suffix}"
    with st.container(key=f"riskobet_actions_{suffix}"):
        if show_goal_history:
            history_html = _football_goal_history_html(candidate, snapshot)
            if history_html:
                st.markdown(history_html, unsafe_allow_html=True)
        recent_form = next(
            (
                _customer_factor_detail(factor)
                for factor in snapshot.factors
                if factor.factor_key == "esports_recent_form"
                and factor.role is FactorRole.MODEL
            ),
            None,
        )
        if recent_form:
            st.caption(recent_form)
        surface_factor = next(
            (
                factor
                for factor in snapshot.factors
                if factor.factor_key == "tennis_surface_evidence"
                and factor.role is FactorRole.DISPLAY_ONLY
            ),
            None,
        )
        details = list(_factor_detail_rows(snapshot))
        shown_records, shown_surfaces, shown_copy = set(), set(), set()
        record_factors = ([surface_factor] if surface_factor else []) + [
            factor for factor in snapshot.factors
            if factor.role is FactorRole.DISPLAY_ONLY and factor.factor_key.startswith('customer_recent_')
        ]
        for factor in record_factors:
            surface, records = compact_riskobet_tennis_form(factor.summary)
            if surface:
                if surface not in shown_surfaces:
                    st.caption('Belag: ' + surface)
                    shown_surfaces.add(surface)
                for player, record in records:
                    if (player, record) not in shown_records:
                        st.caption(player + ': ' + record, unsafe_allow_html=False)
                        shown_records.add((player, record))
            else:
                detail = _customer_factor_detail(factor)
                if detail and detail not in shown_copy:
                    if factor is surface_factor:
                        details.append(detail)
                    else:
                        st.caption(detail)
                    shown_copy.add(detail)
        for factor in snapshot.factors:
            if (factor.role is FactorRole.DISPLAY_ONLY
                    and factor.factor_key == 'customer_counter_'+candidate.selection_key):
                detail = _customer_factor_detail(factor)
                if detail:
                    st.caption('Gegenargument: '+detail)
        visible_context = tuple(
            _customer_factor_detail(factor)
            for factor in snapshot.factors
            if factor.role is FactorRole.DISPLAY_ONLY
            and factor.factor_key.startswith(("tennis_workload_", "football_context_"))
        )
        details.extend(detail for detail in visible_context if detail)
        # Do not offer an empty analysis drawer after method-only factors were
        # removed. Real observations/results remain in the retained detail rows.
        if details:
            with st.expander("Analyse anzeigen", expanded=False, key=detail_key):
                for detail in dict.fromkeys(details):
                    st.write(detail)


def _ordered_riskobet_cards(catalog, candidate_by_id, sort_mode):
    return ordered_event_rows(catalog.cards, mode=sort_mode,
        event_key=lambda card: (card.sport_key, card.event_key),
        starts_at=lambda card: candidate_by_id[card.candidate_id].starts_at,
        probability=lambda card: card.model_probability)


def _render_ordered_scenarios(catalog, candidate_by_id, snapshots, sort_mode):
    cards = _ordered_riskobet_cards(catalog, candidate_by_id, sort_mode)
    if not cards:
        return
    # Page whole events after selection/coherence, never separate scenarios
    # across pages or let a later featured event jump the chosen time order.
    events = tuple(dict.fromkeys((card.sport_key, card.event_key) for card in cards))
    st.markdown("## Risiko-Szenarien")
    page_size = 20
    pages = (len(events) + page_size - 1) // page_size
    page = st.selectbox("Spiele – Seite", range(1, pages + 1), key=f"riskobet-page-{len(events)}") if pages > 1 else 1
    offset = (page - 1) * page_size
    visible_events = set(events[offset:offset + page_size])
    visible = tuple(card for card in cards if (card.sport_key, card.event_key) in visible_events)
    if pages > 1:
        st.caption(f"{offset + 1}–{min(offset + page_size, len(events))} von {len(events)} Spielen")
    featured = {card.candidate_id: i for i, card in enumerate(catalog.featured)}
    additional = {card.candidate_id: i for i, card in enumerate(catalog.additional)}
    shown_goal_events = set()
    with st.container(key="riskobet_featured_grid"):
        # Row-oriented columns keep DOM and mobile order identical.
        for row_start in range(0, len(visible), 2):
            columns = st.columns(2)
            for position, card in enumerate(visible[row_start:row_start+2]):
                candidate = candidate_by_id[card.candidate_id]
                is_featured = card.candidate_id in featured
                key = (f"riskobet_featured_card_{featured[card.candidate_id]}" if is_featured
                       else f"riskobet_additional_row_{additional[card.candidate_id]}")
                with columns[position], st.container(key=key):
                    renderer = render_riskobet_card_html if is_featured else render_riskobet_compact_row_html
                    st.markdown(renderer(card, show_price=False), unsafe_allow_html=True)
                    event = (card.sport_key, card.event_key)
                    _render_detail(candidate, snapshots[candidate.snapshot_id],
                        show_goal_history=event not in shown_goal_events)
                    shown_goal_events.add(event)


def render_riskobet(
    path: str | Path | None = None,
    *,
    now: Optional[datetime] = None,
) -> None:
    """Render the read-only RisikoBet page without any provider/model calls."""

    with st.container(key="riskobet_page"):
        try:
            current = now if now is not None else datetime.now(timezone.utc)
            if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
                raise RiskBetViewError('RisikoBet render clock must be timezone-aware')
            current = current.astimezone(timezone.utc)
            view = load_riskobet_view(path)
            upcoming = () if view is None else upcoming_riskobet_candidates(view, now=current)
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
        sort_mode = display_order_control(st, key='riskobet_order')
        # Reuse only already stored, exactly bound prices. No provider call.
        overlays = load_shared_price_overlays(upcoming, view.snapshots.values(), now=current) if upcoming else {}
        cards = tuple(
            _display_card(candidate, _stored_manual_quote(candidate),
                price=overlays.get(candidate.candidate_id),
                snapshot=view.snapshots[candidate.snapshot_id], now=current)
            for candidate in upcoming
        )
        catalog = compose_riskobet_catalog(
            cards,
            sport_filter=sport_filter,
            max_featured=3,
        )
        event_count = len(
            {(card.sport_key, card.event_key) for card in catalog.cards}
        )
        completed = format_zurich_time(view.completed_at)
        with st.container(key="riskobet_summary"):
            if view.status == "PARTIAL":
                st.caption('Einzelne Sportarten: Aktualisierung offen.')
            if catalog.cards:
                scenario_label = (
                    "Szenario" if len(catalog.cards) == 1 else "Szenarien"
                )
                event_label = "Spiel" if event_count == 1 else "Spielen"
                st.caption(
                    f"{len(catalog.cards)} {scenario_label} aus {event_count} "
                    f"{event_label} · Stand: {completed}"
                )
        candidate_by_id = {
            candidate.candidate_id: candidate for candidate in upcoming
        }
        _render_ordered_scenarios(catalog, candidate_by_id, view.snapshots, sort_mode)
        from tip_publication import record_riskobet_catalog
        record_riskobet_catalog(catalog, candidate_by_id, view.snapshots,
            as_of=current, source_run_id=view.run_id)
        if not catalog.cards:
            st.info('Aktuell kein passendes Risiko-Szenario.')


__all__ = [
    "RiskBetView",
    "RiskBetViewError",
    "load_riskobet_view",
    "upcoming_riskobet_candidates",
    "render_riskobet",
]
