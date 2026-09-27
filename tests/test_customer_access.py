from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from customer_access import (
    ACCESS_KEY, PLAN_FEATURES, CustomerAccessDenied, assert_current_scope,
    bind_customer, enabled, fetch_access, require_feature,
)


def payload(plan="starter", account="a" * 32):
    return {"account_id": account, "plan": plan, "features": list(PLAN_FEATURES[plan]),
            "paid_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("BETBOY_CUSTOMER_ACCESS_REQUIRED", "1")
    monkeypatch.setenv("BETBOY_PORTAL_INTERNAL_TOKEN", "test-only")
    monkeypatch.setenv("BETBOY_PORTAL_INTERNAL_URL", "http://127.0.0.1:8010/internal/access/")


def test_personal_deployment_unchanged(monkeypatch):
    monkeypatch.delenv("BETBOY_CUSTOMER_ACCESS_REQUIRED", raising=False)
    assert not enabled()
    assert bind_customer(None) is False
    require_feature(None, "15k")


def test_server_verifies_cookie_on_loopback(configured):
    response = SimpleNamespace(status_code=200, json=lambda: payload())
    with patch("customer_access.requests.Session") as cls:
        client = cls.return_value.__enter__.return_value
        client.get.return_value = response
        assert fetch_access({"betboy_customer": "s" * 32})["plan"] == "starter"
        assert client.trust_env is False
        assert client.get.call_args.kwargs["allow_redirects"] is False
        assert client.get.call_args.kwargs["cookies"] == {"betboy_customer": "s" * 32}


@pytest.mark.parametrize("url", ["https://evil.example/internal/access/", "http://localhost.evil.example/internal/access/", "http://user@localhost:8010/internal/access/", "http://127.0.0.1/else/"])
def test_cookie_never_sent_to_external_origin(configured, monkeypatch, url):
    monkeypatch.setenv("BETBOY_PORTAL_INTERNAL_URL", url)
    with patch("customer_access.requests.Session") as cls, pytest.raises(CustomerAccessDenied):
        fetch_access({"betboy_customer": "s" * 32})
    cls.assert_not_called()


@pytest.mark.parametrize("change", [
    {"account_id": "../../other"}, {"plan": "admin"}, {"features": ["automatic", "saved", "15k"]},
    {"paid_until": "2020-01-01T00:00:00+00:00"}, {"paid_until": "2040-01-01T00:00:00"},
    {"features": [True]},
])
def test_malformed_expired_or_elevated_access_rejected(configured, change):
    data = {**payload(), **change}
    with patch("customer_access.requests.Session") as cls:
        cls.return_value.__enter__.return_value.get.return_value = SimpleNamespace(status_code=200, json=lambda: data)
        with pytest.raises(CustomerAccessDenied):
            fetch_access({"betboy_customer": "s" * 32})


def test_new_customer_does_not_adopt_legacy_browser_account(configured):
    st = SimpleNamespace(context=SimpleNamespace(cookies={}), session_state={"_betboy_account_scope": "b" * 32, "old_tickets": ["private"]})
    with patch("customer_access.fetch_access", return_value=payload()):
        assert bind_customer(st)
    assert "old_tickets" not in st.session_state
    assert st.session_state["_betboy_account_scope"] == "a" * 32


def test_changing_user_clears_cached_personal_data(configured):
    st = SimpleNamespace(context=SimpleNamespace(cookies={}), session_state={ACCESS_KEY: payload(account="b" * 32), "tickets": ["private"]})
    with patch("customer_access.fetch_access", return_value=payload()):
        bind_customer(st)
    assert "tickets" not in st.session_state


def test_expired_session_cannot_read_old_scope(configured):
    with patch("customer_access.fetch_access", side_effect=CustomerAccessDenied), pytest.raises(CustomerAccessDenied):
        assert_current_scope({}, "a" * 32)


def test_account_scope_cannot_be_forged(configured):
    with patch("customer_access.fetch_access", return_value=payload()), pytest.raises(CustomerAccessDenied):
        assert_current_scope({}, "b" * 32)


def test_starter_cannot_use_pro_feature(configured):
    st = MagicMock()
    with patch("customer_access.fetch_access", return_value=payload()):
        require_feature(st, "daily3")
    st.stop.assert_called_once()


def test_pro_has_advertised_features(configured):
    st = MagicMock()
    with patch("customer_access.fetch_access", return_value=payload("pro")):
        for feature in PLAN_FEATURES["pro"]:
            require_feature(st, feature)
    st.stop.assert_not_called()


@pytest.mark.parametrize("access", [payload("starter"), payload("pro", account="b" * 32)])
def test_daily3_callback_cannot_write_after_downgrade_or_account_switch(configured, access):
    from daily3_ui import _submit
    st = SimpleNamespace(context=SimpleNamespace(cookies={}), session_state={})
    store = MagicMock()
    with patch("customer_access.fetch_access", return_value=access):
        _submit(st, store, "a" * 32, "x", "start", "2026-09-27", dict)
    store.command.assert_not_called()


def test_feature_catalog_matches_portal_without_importing_django():
    import runpy
    from pathlib import Path
    plans = runpy.run_path(str(Path(__file__).resolve().parents[1] / "portal/members/plans.py"))["PLANS"]
    assert {key: frozenset(value["features"]) for key, value in plans.items()} == PLAN_FEATURES
