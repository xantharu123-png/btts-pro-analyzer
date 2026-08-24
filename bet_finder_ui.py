"""Shared, customer-facing rendering for one concrete model tip."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Callable, Iterable, Optional, TypeVar

import streamlit as st

from account_identity import storage_scope
from betting_math import EXTREME_SHORT_ODDS_CUTOFF
from market_consensus import (
    MarketConsensus,
    reference_price_status,
)
from multi_sport_recommendations import (
    PriceDecision,
    RecommendationCandidate,
    evaluate_candidate_price,
    format_probability_percent,
)
from tip_store import TipStore


LOGGER = logging.getLogger(__name__)
_ForecastRow = TypeVar("_ForecastRow")


def merge_consumer_forecast_catalog(
    *groups: Optional[Iterable[_ForecastRow]],
) -> list[_ForecastRow]:
    """Merge display catalogs without dropping distinct markets per fixture."""

    merged: list[_ForecastRow] = []
    seen: set[str] = set()
    for group in groups:
        for row in group or ():
            identity = _consumer_token(
                getattr(row, "candidate_id", None)
                or getattr(row, "key", None)
                or id(row)
            )
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(row)
    return merged


def _consumer_token(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


def _consumer_market_utility_tier(row: object) -> int:
    """Return a small, price-independent presentation tier.

    Combined result/goal decisions are more informative than a repeated team
    safety line.  This is deliberately presentation-only: no tier changes a
    model probability, price decision, ticket, or eligibility gate.
    """

    market_key = _consumer_token(getattr(row, "market_key", None))
    market = _consumer_token(getattr(row, "market", None))
    selection = _consumer_token(getattr(row, "selection", None))
    combined = "_".join(part for part in (market_key, market, selection) if part)
    if market_key.startswith("result_total_") or (
        "resultat" in market and ("gesamttore" in market or "tore" in market)
    ):
        return 0
    if (
        market_key.startswith(
            ("home_under_", "home_over_", "away_under_", "away_over_")
        )
        or "team_1_gesamttore" in market
        or "team_2_gesamttore" in market
        or "teamtore" in market
        or "team_total" in combined
    ):
        return 2
    if (
        market_key.startswith(("dc_", "mixed_"))
        or "doppelte_chance" in market
        or "gemischte_chance" in market
        or ("tore" in selection and "oder" in selection)
    ):
        return 3
    return 1


def _consumer_market_is_basis(row: object) -> bool:
    """Mirror broad consumer basis markets without importing the model layer."""

    market_key = _consumer_token(getattr(row, "market_key", None))
    market = _consumer_token(getattr(row, "market", None))
    selection = _consumer_token(getattr(row, "selection", None))
    basic_prefixes = ("dc_", "mixed_", "home_range_", "away_range_")
    basic_keys = {
        "total_over_0_5",
        "total_under_4_5",
        "home_over_0_5",
        "away_over_0_5",
        "home_under_1_5",
        "away_under_1_5",
        "home_under_2_5",
        "away_under_2_5",
        "corners_over_5_5",
        "corners_under_11_5",
        "home_corners_over_2_5",
        "away_corners_over_2_5",
        "home_corners_under_5_5",
        "away_corners_under_5_5",
        "yellow_over_1_5",
        "yellow_under_4_5",
        "home_yellow_over_0_5",
        "away_yellow_over_0_5",
        "home_yellow_under_2_5",
        "away_yellow_under_2_5",
    }
    if market_key.startswith(basic_prefixes) or market_key in basic_keys:
        return True
    if "doppelte_chance" in market or "gemischte_chance" in market:
        return True
    if selection in {"1_3_tore", "2_4_tore"}:
        return True
    is_team_total = (
        "team_1_gesamttore" in market
        or "team_2_gesamttore" in market
        or "teamtore" in market
        or "team_total" in market
    )
    return is_team_total and selection in {
        "uber_0_5",
        "unter_1_5",
        "unter_2_5",
    }


def _consumer_context_complete(row: object) -> bool:
    for attribute in ("context_complete", "release_context_complete"):
        value = getattr(row, attribute, None)
        if value is True:
            return True
    context = getattr(row, "context", None)
    return bool(
        isinstance(context, dict)
        and context.get("release_context_complete") is True
    )


def _consumer_fixture_identity(row: object) -> str:
    fixture_id = getattr(row, "fixture_id", None)
    if fixture_id is not None and not isinstance(fixture_id, bool):
        token = _consumer_token(fixture_id)
        if token:
            return f"fixture:{token}"
    event = _consumer_token(getattr(row, "event_label", None))
    if event:
        return f"event:{event}"
    teams = _consumer_token(
        "|".join(
            str(value or "")
            for value in (
                getattr(row, "home_team", None),
                getattr(row, "away_team", None),
            )
        )
    )
    if teams:
        return f"teams:{teams}"
    row_identity = (
        getattr(row, "candidate_id", None)
        or getattr(row, "key", None)
        or id(row)
    )
    return f"row:{_consumer_token(row_identity)}"


def _consumer_market_identity(row: object) -> str:
    market_key = _consumer_token(getattr(row, "market_key", None))
    market = _consumer_token(getattr(row, "market", None))
    keyed_families = (
        ("result_total_", "result_total"),
        ("result_", "result"),
        ("dc_", "double_chance"),
        ("btts_", "btts"),
        ("total_", "total"),
        ("home_corners_", "team_corners"),
        ("away_corners_", "team_corners"),
        ("corners_", "corner_total"),
        ("home_yellow_", "team_yellow"),
        ("away_yellow_", "team_yellow"),
        ("yellow_", "yellow_total"),
        ("home_", "team_total"),
        ("away_", "team_total"),
        ("mixed_", "mixed"),
    )
    for prefix, family in keyed_families:
        if market_key.startswith(prefix):
            return f"family:{family}"
    labeled_families = (
        ("resultat", "result_total"),
        ("beide_teams", "btts"),
        ("doppelte_chance", "double_chance"),
        ("team_1_gesamttore", "team_total"),
        ("team_2_gesamttore", "team_total"),
        ("teamtore", "team_total"),
        ("endergebnis", "result"),
        ("gesamttore", "total"),
    )
    for token, family in labeled_families:
        if token in market:
            return f"family:{family}"
    if market_key or market:
        return f"market:{market_key or market}"
    row_identity = (
        getattr(row, "candidate_id", None)
        or getattr(row, "key", None)
        or id(row)
    )
    return f"row:{_consumer_token(row_identity)}"


def partition_consumer_featured_forecasts(
    rows: Iterable[_ForecastRow],
    *,
    max_featured: int = 3,
) -> tuple[list[_ForecastRow], list[_ForecastRow]]:
    """Choose diverse main cards and keep every other forecast secondary.

    Ordering is stable inside each utility/context tier.  A fully checked row
    is preferred to an incomplete row of comparable usefulness.  At most one
    row per fixture and repeated market decision occupies a main-card slot.
    Broad basis markets never occupy such a slot; every row remains in the
    returned primary or secondary catalog.
    """

    if (
        isinstance(max_featured, bool)
        or not isinstance(max_featured, int)
        or max_featured < 1
    ):
        raise ValueError("max_featured must be a positive integer")
    ranked = sorted(
        enumerate(rows),
        key=lambda item: (
            _consumer_market_utility_tier(item[1]),
            0 if _consumer_context_complete(item[1]) else 1,
            item[0],
        ),
    )
    featured: list[_ForecastRow] = []
    secondary: list[_ForecastRow] = []
    used_fixtures: set[str] = set()
    used_markets: set[str] = set()
    for _index, row in ranked:
        if _consumer_market_is_basis(row):
            secondary.append(row)
            continue
        fixture_identity = _consumer_fixture_identity(row)
        market_identity = _consumer_market_identity(row)
        can_feature = (
            len(featured) < max_featured
            and fixture_identity not in used_fixtures
            and market_identity not in used_markets
        )
        if can_feature:
            featured.append(row)
            used_fixtures.add(fixture_identity)
            used_markets.add(market_identity)
        else:
            secondary.append(row)
    return featured, secondary


def partition_consumer_forecasts(
    rows: Iterable[_ForecastRow],
    *,
    quote_for: Callable[[_ForecastRow], Optional[MarketConsensus | dict]],
    now=None,
) -> tuple[list[_ForecastRow], list[_ForecastRow]]:
    """Keep every forecast, but relegate confirmed extreme-short prices.

    Missing, thin, stale, or merely below-value quotes stay in the primary
    model order. Only a fresh TOO_LOW market whose best observed price is
    below the existing public usefulness floor moves to the secondary group.
    """

    primary: list[_ForecastRow] = []
    extreme_short: list[_ForecastRow] = []
    for row in rows:
        raw_quote = quote_for(row)
        quote = (
            raw_quote
            if isinstance(raw_quote, MarketConsensus)
            else MarketConsensus.from_dict(raw_quote)
        )
        minimum_odds = getattr(row, "minimum_odds", None)
        is_extreme_short = False
        if quote is not None and minimum_odds is not None:
            status = reference_price_status(quote, minimum_odds, now=now)
            is_extreme_short = (
                status.code == "TOO_LOW"
                and quote.best_odds < EXTREME_SHORT_ODDS_CUTOFF
            )
        (extreme_short if is_extreme_short else primary).append(row)
    return primary, extreme_short


def _decimal_input(value: str):
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return text


def _save_tip(
    decision: PriceDecision,
    *,
    source: str,
) -> Optional[str]:
    try:
        store = TipStore(scope_id=storage_scope(st.session_state))
        if decision.status == "BET":
            store.save_decision(decision, source=source)
            return "Unter Meine Tipps gespeichert."
        if decision.quoted_odds is not None:
            candidate = decision.candidate
            store.archive_candidate(
                sport=candidate.sport,
                event_key=candidate.event_key,
                market=candidate.market,
                selection=candidate.selection or "keine Auswahl",
            )
    except (OSError, ValueError):
        LOGGER.exception("Consumer tip could not be persisted")
        return "Tipp konnte nicht gespeichert werden. Bitte später erneut versuchen."
    return None


def _render_stake_recommendation(decision: PriceDecision) -> None:
    if decision.status != "BET" or decision.stake_fraction <= 0:
        return
    st.caption(
        f"Einsatzvorschlag: {decision.stake_amount:.2f} € "
        f"({decision.stake_fraction * 100:.2f} % des Wettguthabens)"
    )


def _render_reference_price(
    candidate: RecommendationCandidate,
    quote: Optional[MarketConsensus],
    *,
    bankroll: float,
) -> Optional[PriceDecision]:
    status = reference_price_status(quote, candidate.minimum_odds)
    decision = None
    if quote is not None and status.usable_odds is not None:
        decision = evaluate_candidate_price(
            candidate,
            status.usable_odds,
            bankroll=bankroll,
            quote_confirmed=True,
        )

    if status.code == "PLAYABLE" and quote is not None:
        if decision is not None and decision.status == "BET":
            st.success(
                f"SPIELBARER TIPP: {candidate.selection} | aktuelle "
                f"Vergleichsquote {quote.conservative_odds:.2f} | spielbar ab "
                f"{candidate.minimum_odds:.2f}"
            )
        else:
            st.info(
                f"PASSENDE QUOTE: {candidate.selection} | die aktuelle "
                f"Vergleichsquote {quote.conservative_odds:.2f} erreicht die "
                f"Value-Grenze von {candidate.minimum_odds:.2f}. Das Modell "
                "sammelt noch Praxisergebnisse; daher kein Einsatzvorschlag."
            )
    elif status.code == "BORDERLINE" and quote is not None:
        st.info(
            f"PREIS NOCH OFFEN: {candidate.selection}. Nur einzelne Anbieter "
            f"erreichen die Value-Grenze {candidate.minimum_odds:.2f}; der Preis ist deshalb "
            "noch nicht zuverlässig bestätigt. Die Prognose bleibt unverändert."
        )
    elif status.code == "TOO_LOW" and quote is not None:
        st.info(
            f"QUOTE ZU NIEDRIG: {candidate.selection}. Die aktuell beobachtete "
            f"Bestquote {quote.best_odds:.2f} liegt unter der benötigten "
            f"Value-Grenze {candidate.minimum_odds:.2f}. Die Prognose bleibt "
            "unverändert; nur der angebotene Preis ist zu niedrig. Die "
            "Value-Grenze ist keine erwartete Buchmacherquote."
        )
    else:
        reason = {
            "THIN": "Es liegen noch zu wenige Vergleichsquoten vor.",
            "STALE": "Die Vergleichsquote ist nicht mehr aktuell.",
            "UNAVAILABLE": "Aktuell liegt keine exakt passende Vergleichsquote vor.",
            "INVALID_MINIMUM": "Die Value-Grenze konnte nicht sicher berechnet werden.",
        }.get(status.code, "Der Wettpreis kann noch nicht sicher bewertet werden.")
        st.info(
            f"PREIS NOCH OFFEN: {candidate.selection}. {reason} Das ist keine "
            "Aussage darüber, ob der mögliche "
            "Spielausgang richtig oder falsch ist."
        )

    if decision is not None and decision.status == "BET":
        _render_stake_recommendation(decision)
    return decision


def _render_manual_check(
    candidate: RecommendationCandidate,
    *,
    key: str,
    bankroll_key: str,
    price_source: str,
    save_source: Optional[str],
) -> Optional[PriceDecision]:
    odds_widget_key = f"bet_odds_{key}"
    manual_bankroll_key = f"{bankroll_key}_{key}"
    with st.expander("Eigene Buchmacherquote prüfen", expanded=False):
        st.caption(
            "Optional: Nur nötig, wenn die tatsächlich angebotene Quote mit "
            "der automatischen Marktübersicht verglichen werden soll."
        )
        with st.form(f"bet_price_{key}", border=False):
            price_column, bankroll_column = st.columns(2)
            with price_column:
                raw_odds = st.text_input(
                    f"{price_source} für {candidate.selection}",
                    placeholder="z. B. 1,95",
                    key=odds_widget_key,
                )
            with bankroll_column:
                bankroll = st.number_input(
                    "Aktuelles Wettguthaben",
                    min_value=1.0,
                    value=100.0,
                    step=10.0,
                    key=manual_bankroll_key,
                )
            confirmed = st.checkbox(
                f"Auswahl stimmt exakt: {candidate.selection} / {candidate.market}",
                value=False,
                key=f"bet_confirmed_{key}",
            )
            submitted = st.form_submit_button(
                "Eigene Quote prüfen",
                type="primary",
                use_container_width=True,
            )

        decision_state_key = f"bet_decision_{key}"
        if submitted:
            decision = evaluate_candidate_price(
                candidate,
                _decimal_input(raw_odds),
                bankroll=bankroll,
                quote_confirmed=confirmed,
            )
            st.session_state[decision_state_key] = decision
            if (
                save_source
                and confirmed
                and decision.status != "PRICE_REQUIRED"
            ):
                message = _save_tip(
                    decision,
                    source=f"{save_source} / eigene Quote",
                )
                if message:
                    st.toast(message)
        else:
            decision = st.session_state.get(decision_state_key)
            if not isinstance(decision, PriceDecision):
                return None

        if decision.status == "PRICE_REQUIRED":
            st.info(
                f"Quote und exakte Auswahl bestätigen. Value-Grenze "
                f"{candidate.minimum_odds:.2f}."
            )
        elif decision.status == "BET":
            st.success(
                f"PREIS BESTANDEN: {candidate.selection} @ "
                f"{decision.quoted_odds:.2f}"
            )
        elif decision.status in {"SHADOW", "RESEARCH"}:
            st.info(
                f"PREIS PASST: {candidate.selection} @ "
                f"{decision.quoted_odds:.2f}. Diese Auswahl wird noch "
                "geprüft; deshalb gibt es keinen Einsatzvorschlag."
            )
        else:
            st.info(
                f"MODELL-AUSWAHL BLEIBT: {candidate.selection}. Die angebotene "
                f"Quote erreicht die Value-Grenze {candidate.minimum_odds:.2f} "
                "noch nicht und reicht daher nicht für eine "
                "spielbare Preisbewertung."
            )
        if decision.status == "BET":
            _render_stake_recommendation(decision)
        return decision


def render_price_decision(
    candidate: RecommendationCandidate,
    *,
    key: str,
    bankroll_key: str = "shared_bet_finder_bankroll",
    price_source: str = "Dezimalquote",
    save_source: Optional[str] = None,
    live_price: bool = False,
    reference_quote: Optional[MarketConsensus | dict] = None,
    allow_manual_check: bool = False,
) -> Optional[PriceDecision]:
    """Render one model selection while keeping forecast and price separate."""
    del live_price  # Kept for call-site compatibility.
    selection = candidate.selection or "keine Auswahl"
    st.subheader(f"{candidate.market}: {selection}")
    st.caption(candidate.event_label)

    if candidate.forecast_available:
        metrics = st.columns(3)
        metrics[0].metric(
            "Modellwahrscheinlichkeit",
            format_probability_percent(candidate.model_probability),
        )
        metrics[1].metric(
            "Vorsichtige Prognose",
            format_probability_percent(candidate.risk_adjusted_probability),
        )
        metrics[2].metric(
            "Value-Grenze",
            (
                f"{candidate.minimum_odds:.2f}"
                if candidate.minimum_odds is not None
                else "k. A."
            ),
            help=(
                "Preis, ab dem die vorsichtige Modellrechnung den Zielwert "
                "erreicht; keine erwartete oder übliche Buchmacherquote."
            ),
        )

    if candidate.blockers:
        if candidate.forecast_available:
            st.warning(
                "PROGNOSE VORHANDEN, ABER NICHT ALS TIPP FREIGEGEBEN."
            )
        else:
            st.error("KEINE BELASTBARE PROGNOSE.")
        return None

    quote = (
        reference_quote
        if isinstance(reference_quote, MarketConsensus)
        else MarketConsensus.from_dict(reference_quote)
    )
    bankroll = float(st.session_state.get(bankroll_key, 100.0) or 100.0)
    automatic_decision = _render_reference_price(
        candidate,
        quote,
        bankroll=bankroll,
    )

    if (
        automatic_decision is not None
        and automatic_decision.status == "BET"
        and save_source
    ):
        if st.button(
            "Tipp merken",
            key=f"save_reference_{key}",
            use_container_width=True,
        ):
            message = _save_tip(
                automatic_decision,
                source=f"{save_source} / {quote.source}",
            )
            if message:
                st.toast(message)

    manual_decision = None
    if allow_manual_check:
        manual_decision = _render_manual_check(
            candidate,
            key=key,
            bankroll_key=bankroll_key,
            price_source=price_source,
            save_source=save_source,
        )

    return manual_decision or automatic_decision


__all__ = ["render_price_decision"]
