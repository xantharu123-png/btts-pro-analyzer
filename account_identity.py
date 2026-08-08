"""Stable browser-local account identity for persistent user records."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import streamlit.components.v1 as components

import scan_jobs


ACCOUNT_SCOPE_SESSION_KEY = "_betboy_account_scope"
_BROWSER_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_COMPONENT_DIR = Path(__file__).resolve().parent / "account_identity_component"
_identity_component = components.declare_component(
    "betboy_account_identity",
    path=str(_COMPONENT_DIR),
)


def normalize_browser_id(value: Any) -> str | None:
    """Accept only the random 128-bit identifier produced by the component."""
    normalized = str(value or "").strip().lower()
    return normalized if _BROWSER_ID_RE.fullmatch(normalized) else None


def ensure_account_scope(st_module: Any) -> str | None:
    """Load the durable browser identity before account-backed UI is rendered."""
    current = normalize_browser_id(
        st_module.session_state.get(ACCOUNT_SCOPE_SESSION_KEY)
    )
    browser_id = normalize_browser_id(
        _identity_component(
            protocolVersion=1,
            default=current,
            key="betboy_account_identity",
        )
    )
    if browser_id is not None:
        st_module.session_state[ACCOUNT_SCOPE_SESSION_KEY] = browser_id
        return browser_id
    if current is not None:
        return current

    # On the first render the component responds asynchronously and triggers a
    # rerun. The regular session scope remains the short-lived fallback until
    # that response arrives, so the page never gets stuck on an empty first run.
    return None


def storage_scope(session_state: Any) -> str:
    """Return durable account scope, with a test/legacy session fallback."""
    try:
        account_scope = normalize_browser_id(
            session_state.get(ACCOUNT_SCOPE_SESSION_KEY)
        )
    except AttributeError:
        account_scope = None
    if account_scope is not None:
        return account_scope
    return scan_jobs.session_scope(session_state)


__all__ = [
    "ACCOUNT_SCOPE_SESSION_KEY",
    "ensure_account_scope",
    "normalize_browser_id",
    "storage_scope",
]
