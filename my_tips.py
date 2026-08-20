"""One records workspace for finder decisions, challenge tickets and tennis."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from account_identity import storage_scope
from tip_store import SavedTip, TipStore


RESULT_LABELS = {
    "WON": "Gewonnen",
    "LOST": "Verloren",
    "VOID": "Ungültig",
}


def _format_time(value: str | None) -> str:
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return str(value)


def _settle(store: TipStore, tip: SavedTip, result: str) -> None:
    try:
        store.settle(tip.id, result)
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.rerun()


def _archive(store: TipStore, tip: SavedTip) -> None:
    try:
        store.archive(tip.id)
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.rerun()


def render_saved_tips() -> None:
    store = TipStore(scope_id=storage_scope(st.session_state))
    active = store.list_tips(active=True)
    st.subheader("Aktive Tipps")
    if not active:
        st.info("Noch keine preisgeprüften Tipps gespeichert.")
    for tip in active:
        with st.container(border=True):
            st.markdown(f"**{tip.event_label}**")
            st.caption(
                f"{tip.sport} · {tip.market}: {tip.selection} · "
                f"{tip.source} · {_format_time(tip.updated_at)}"
            )
            metrics = st.columns(4)
            metrics[0].metric("Modell", f"{tip.model_probability:.1f} %")
            metrics[1].metric("Konservativ", f"{tip.risk_adjusted_probability:.1f} %")
            metrics[2].metric("Mindestquote", f"{tip.minimum_odds:.2f}")
            metrics[3].metric("Quote", f"{tip.quoted_odds:.2f}")
            actions = st.columns(4)
            if actions[0].button(
                "Gewonnen",
                icon=":material/check_circle:",
                key=f"tip_won_{tip.id}",
                use_container_width=True,
            ):
                _settle(store, tip, "WON")
            if actions[1].button(
                "Verloren",
                icon=":material/cancel:",
                key=f"tip_lost_{tip.id}",
                use_container_width=True,
            ):
                _settle(store, tip, "LOST")
            if actions[2].button(
                "Ungültig",
                icon=":material/remove_circle:",
                key=f"tip_void_{tip.id}",
                use_container_width=True,
            ):
                _settle(store, tip, "VOID")
            if actions[3].button(
                "Entfernen",
                icon=":material/delete:",
                key=f"tip_archive_{tip.id}",
                use_container_width=True,
            ):
                _archive(store, tip)

    history = store.list_tips(active=False)
    st.subheader("Verlauf")
    if not history:
        st.caption("Noch keine abgeschlossenen Tipps.")
        return
    frame = pd.DataFrame(
        [
            {
                "Datum": _format_time(tip.settled_at),
                "Sport": tip.sport,
                "Spiel": tip.event_label,
                "Tipp": f"{tip.market}: {tip.selection}",
                "Quote": tip.quoted_odds,
                "Ergebnis": RESULT_LABELS.get(tip.result, tip.result),
            }
            for tip in history
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_my_tips() -> None:
    area = st.selectbox(
        "Bereich",
        ["Wettfinder", "15K Challenge"],
        key="my_tips_area",
    )
    if area == "Wettfinder":
        render_saved_tips()
    elif area == "15K Challenge":
        from challenge_15k import render_challenge_history

        render_challenge_history()


__all__ = ["render_my_tips", "render_saved_tips"]
