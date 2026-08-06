"""Compact Streamlit controls for browser-imported N1Bet prices."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence

import streamlit as st

from n1_import import (
    N1ImportError,
    N1ImportMatch,
    N1ImportSnapshot,
    N1WidgetBinding,
    apply_imported_widget_value,
    match_imported_quotes,
    parse_import_snapshot,
)
from n1_import_component import extension_archive, render_bridge


SNAPSHOT_STATE_KEY = "_n1_import_snapshot"
SNAPSHOT_TIME_STATE_KEY = "_n1_import_snapshot_time"
BRIDGE_STATUS_STATE_KEY = "_n1_import_bridge_status"


def _format_age(captured_at: datetime) -> str:
    seconds = max(
        0,
        int((datetime.now(timezone.utc) - captured_at.astimezone(timezone.utc)).total_seconds()),
    )
    if seconds < 60:
        return f"vor {seconds} Sek."
    return f"vor {seconds // 60} Min."


def _consume_bridge_response(response: object) -> None:
    if not isinstance(response, Mapping):
        return
    status = str(response.get("status") or "")
    st.session_state[BRIDGE_STATUS_STATE_KEY] = status
    if status != "OK" or not isinstance(response.get("snapshot"), Mapping):
        return
    try:
        snapshot = parse_import_snapshot(response["snapshot"])
    except N1ImportError as exc:
        st.session_state[BRIDGE_STATUS_STATE_KEY] = f"ERROR:{exc}"
        return
    st.session_state[SNAPSHOT_STATE_KEY] = snapshot
    st.session_state[SNAPSHOT_TIME_STATE_KEY] = snapshot.captured_at.isoformat()


def render_n1_import_sync(
    bindings: Sequence[N1WidgetBinding],
    *,
    key: str,
) -> dict[str, N1ImportMatch]:
    """Sync and apply exact imported prices before their widgets are created."""
    unique_bindings = {binding.target.key: binding for binding in bindings}
    if not unique_bindings:
        return {}

    nonce_key = f"_n1_import_sync_nonce_{key}"
    button_col, status_col = st.columns([1, 3])
    if button_col.button(
        "N1Bet sync",
        icon=":material/sync:",
        key=f"n1_import_sync_{key}",
        use_container_width=True,
    ):
        st.session_state[nonce_key] = int(st.session_state.get(nonce_key, 0)) + 1

    current_nonce = int(st.session_state.get(nonce_key, 0))
    ack_nonce_key = f"_n1_import_sync_ack_{key}"
    acknowledged_nonce = int(st.session_state.get(ack_nonce_key, 0))

    response = render_bridge(
        targets=[binding.target.to_component_dict() for binding in unique_bindings.values()],
        sync_nonce=current_nonce,
        force_sync=current_nonce > acknowledged_nonce,
        last_seen=str(st.session_state.get(SNAPSHOT_TIME_STATE_KEY, "")),
        key=f"n1_import_bridge_{key}",
    )
    _consume_bridge_response(response)
    if isinstance(response, Mapping) and str(response.get("status") or "") in {
        "OK",
        "EMPTY",
        "NO_EXTENSION",
    }:
        try:
            response_nonce = int(response.get("syncNonce", current_nonce))
        except (TypeError, ValueError, OverflowError):
            response_nonce = current_nonce
        st.session_state[ack_nonce_key] = max(acknowledged_nonce, response_nonce)

    snapshot = st.session_state.get(SNAPSHOT_STATE_KEY)
    if not isinstance(snapshot, N1ImportSnapshot):
        bridge_status = str(st.session_state.get(BRIDGE_STATUS_STATE_KEY, ""))
        if bridge_status == "NO_EXTENSION":
            status_col.caption("Importer nicht verbunden")
        elif bridge_status == "EMPTY":
            status_col.caption("Noch keine N1Bet-Seite erfasst")
        else:
            status_col.caption("Keine importierten N1Bet-Quoten")
        return {}

    matches = match_imported_quotes(
        [binding.target for binding in unique_bindings.values()],
        snapshot,
    )
    applied = 0
    for target_key, match in matches.items():
        binding = unique_bindings[target_key]
        if apply_imported_widget_value(st.session_state, binding, match):
            applied += 1
    status_col.caption(
        f"N1Bet {_format_age(snapshot.captured_at)} | "
        f"{len(snapshot.quotes)} Quoten | {len(matches)}/{len(unique_bindings)} passend"
    )
    if applied:
        st.session_state[f"_n1_import_last_applied_{key}"] = snapshot.captured_at.isoformat()
    return matches


def render_n1_importer_settings() -> None:
    st.subheader("N1Bet Importer")
    st.download_button(
        "Chrome-/Edge-Erweiterung herunterladen",
        data=extension_archive(),
        file_name="betboy-n1bet-importer.zip",
        mime="application/zip",
        icon=":material/download:",
        type="primary",
        use_container_width=True,
    )
    with st.expander("Einmalige Installation"):
        st.markdown(
            "1. ZIP entpacken.\n"
            "2. In `chrome://extensions` oder `edge://extensions` den Entwicklermodus aktivieren.\n"
            "3. `Entpackte Erweiterung laden` und den Ordner `betboy-n1bet-importer` waehlen."
        )
    st.caption(
        "Der Importer liest nur sichtbare Sportwetten-Quoten. "
        "Login, Passwort und Wettschein werden nicht gelesen; es wird keine Wette platziert."
    )
    snapshot = st.session_state.get(SNAPSHOT_STATE_KEY)
    if isinstance(snapshot, N1ImportSnapshot):
        st.success(
            f"Letzter Browser-Import: {_format_age(snapshot.captured_at)} | "
            f"{len(snapshot.quotes)} Quoten von {snapshot.page_count} Seite(n)"
        )


__all__ = ["render_n1_import_sync", "render_n1_importer_settings"]
