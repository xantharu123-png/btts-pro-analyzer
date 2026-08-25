"""Stable browser-local account identity for persistent user records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

ACCOUNT_SCOPE_SESSION_KEY = "_betboy_account_scope"
_BROWSER_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_COMPONENT_DIR = Path(__file__).resolve().parent / "account_identity_component"
_identity_component = components.declare_component(
    "betboy_account_identity",
    path=str(_COMPONENT_DIR),
)


class AccountScopeUnavailable(ValueError):
    """Raised when durable account storage has not been established yet."""


def normalize_browser_id(value: Any) -> str | None:
    """Accept only the random 128-bit identifier produced by the component."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if _BROWSER_ID_RE.fullmatch(normalized) else None


def ensure_account_scope(st_module: Any) -> str | None:
    """Load the durable browser identity before account-backed UI is rendered."""
    current = normalize_browser_id(
        st_module.session_state.get(ACCOUNT_SCOPE_SESSION_KEY)
    )
    try:
        browser_id = normalize_browser_id(
            _identity_component(
                protocolVersion=2,
                default=current,
                key="betboy_account_identity",
            )
        )
    except Exception:
        # A blocked component or unavailable Web Storage must never create an
        # unrelated account namespace. An identity already confirmed during
        # this Streamlit session remains valid; otherwise callers fail closed.
        browser_id = None
    if browser_id is not None:
        st_module.session_state[ACCOUNT_SCOPE_SESSION_KEY] = browser_id
        return browser_id
    if current is not None:
        return current

    # On the first render the component responds asynchronously and triggers a
    # rerun. Account-backed UI remains unavailable until that response arrives.
    return None


def storage_scope(session_state: Any) -> str:
    """Return the validated durable account scope or fail closed.

    A random Streamlit session ID is suitable for transient scan jobs, but not
    for bankrolls, saved tips, or any other account-backed mutation: a browser
    restart would make those records appear lost under a different namespace.
    """
    try:
        account_scope = normalize_browser_id(
            session_state.get(ACCOUNT_SCOPE_SESSION_KEY)
        )
    except AttributeError:
        account_scope = None
    if account_scope is not None:
        return account_scope
    raise AccountScopeUnavailable(
        "Die dauerhafte Browser-ID ist noch nicht verfügbar."
    )


def account_scope_ready(session_state: Any) -> bool:
    """Return whether account-backed reads and writes are safe to expose."""
    try:
        return normalize_browser_id(
            session_state.get(ACCOUNT_SCOPE_SESSION_KEY)
        ) is not None
    except AttributeError:
        return False


__all__ = [
    "AccountScopeUnavailable",
    "ACCOUNT_SCOPE_SESSION_KEY",
    "account_scope_ready",
    "ensure_account_scope",
    "normalize_browser_id",
    "storage_scope",
]
