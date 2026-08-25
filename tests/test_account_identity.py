from account_identity import (
    AccountScopeUnavailable,
    ACCOUNT_SCOPE_SESSION_KEY,
    account_scope_ready,
    normalize_browser_id,
    storage_scope,
)
from pathlib import Path

import pytest


def test_browser_id_validation_is_strict():
    valid = "0123456789abcdef0123456789abcdef"
    assert normalize_browser_id(valid.upper()) == valid
    assert normalize_browser_id("short") is None
    assert normalize_browser_id("g" * 32) is None
    assert normalize_browser_id(None) is None
    assert normalize_browser_id(123) is None


def test_storage_scope_prefers_durable_browser_account():
    account_id = "fedcba9876543210fedcba9876543210"
    state = {
        ACCOUNT_SCOPE_SESSION_KEY: account_id,
        "_betboy_session_scope": "temporary-session",
    }

    assert storage_scope(state) == account_id


def test_storage_scope_rejects_short_lived_session_fallback():
    state = {"_betboy_session_scope": "temporary-session"}

    with pytest.raises(AccountScopeUnavailable, match="Browser-ID"):
        storage_scope(state)
    assert account_scope_ready(state) is False


def test_browser_component_accepts_current_streamlit_render_protocol():
    source = (
        Path(__file__).resolve().parents[1]
        / "account_identity_component"
        / "index.html"
    ).read_text(encoding="utf-8")

    assert "event.source !== window.parent" in source
    assert "event.origin !== PARENT_ORIGIN" in source
    assert "trustedParentOrigin" in source
    assert "parentUrl.origin === window.location.origin" in source
    assert "window.localStorage.getItem(STORAGE_KEY) === value" in source
    assert '}, "*")' not in source
    assert "postMessage({" in source
    assert "}, PARENT_ORIGIN);" in source
    assert "message.isStreamlitMessage ||" not in source
