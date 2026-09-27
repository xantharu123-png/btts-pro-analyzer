"""Opt-in customer boundary for Streamlit; personal deployments stay unchanged.

Session cookies are checked against the portal on the server, never decoded in
JavaScript. Do not enable until the portal and reverse proxy are configured.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests

SESSION_COOKIE = "betboy_customer"
ACCESS_KEY = "_betboy_verified_customer"
PLAN_FEATURES = {
    "starter": frozenset({"automatic", "saved"}),
    "plus": frozenset({"automatic", "saved", "search", "riskobet"}),
    "pro": frozenset({"automatic", "saved", "search", "riskobet", "live", "daily3", "15k"}),
}
PAGE_FEATURES = {"Wettfinder": "automatic", "Meine Tipps": "saved", "RisikoBet": "riskobet", "Live": "live", "15K": "15k"}


class CustomerAccessDenied(ValueError):
    pass


def enabled() -> bool:
    return os.environ.get("BETBOY_CUSTOMER_ACCESS_REQUIRED") == "1"


def fetch_access(cookies) -> dict:
    token = os.environ.get("BETBOY_PORTAL_INTERNAL_TOKEN", "")
    endpoint = os.environ.get("BETBOY_PORTAL_INTERNAL_URL", "http://127.0.0.1:8010/internal/access/")
    address = urlsplit(endpoint)
    # No customer cookie can be sent to an arbitrary external URL by configuration.
    if not token or address.scheme != "http" or address.hostname not in {"127.0.0.1", "localhost", "::1"} or address.username or address.query or address.fragment or address.path != "/internal/access/":
        raise CustomerAccessDenied("Customer access is not configured.")
    cookie = cookies.get(SESSION_COOKIE, "")
    if not isinstance(cookie, str) or not re.fullmatch(r"[a-z0-9]{32}", cookie):
        raise CustomerAccessDenied("Login required.")
    try:
        # Ignore environment proxy settings: this is a loopback-only credential hop.
        with requests.Session() as client:
            client.trust_env = False
            response = client.get(
                endpoint, cookies={SESSION_COOKIE: cookie},
                headers={"X-BetBoy-Internal": token, "X-Forwarded-Proto": "https"},
                timeout=4, allow_redirects=False,
            )
        if response.status_code != 200:
            raise CustomerAccessDenied("An active subscription is required.")
        data = response.json()
        account = data.get("account_id")
        features = data.get("features")
        plan = data.get("plan")
        expires = datetime.fromisoformat(data.get("paid_until", ""))
        if (
            not isinstance(account, str) or not re.fullmatch(r"[a-f0-9]{32}", account)
            or plan not in PLAN_FEATURES or not isinstance(features, list)
            or not all(isinstance(feature, str) for feature in features)
            or frozenset(features) != PLAN_FEATURES[plan]
            or expires.tzinfo is None or expires <= datetime.now(timezone.utc)
        ):
            raise CustomerAccessDenied("Invalid entitlement.")
        return data
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        raise CustomerAccessDenied("Customer access could not be verified.") from exc


def bind_customer(st_module) -> bool:
    """Run before models or account data are read. Never migrate a browser ID."""
    if not enabled():
        return False
    try:
        access = fetch_access(st_module.context.cookies)
    except CustomerAccessDenied:
        st_module.session_state.clear()
        st_module.info("Bitte melde dich mit einem aktiven BetBoy-Abo an. / Please log in with an active BetBoy subscription.")
        st_module.link_button("Konto / Account", "/de/account/")
        st_module.stop()
        return False
    previous = st_module.session_state.get(ACCESS_KEY, {}).get("account_id")
    if previous != access["account_id"]:
        # Avoid leaking cached personal data after switching authenticated users.
        st_module.session_state.clear()
    st_module.session_state[ACCESS_KEY] = access
    st_module.session_state["_betboy_account_scope"] = access["account_id"]
    return True


def require_feature(st_module, feature: str) -> None:
    if not enabled():
        return
    try:
        access = fetch_access(st_module.context.cookies)
    except CustomerAccessDenied:
        st_module.session_state.clear()
        st_module.info("Bitte erneut einloggen. / Please log in again.")
        st_module.link_button("Konto / Account", "/de/account/")
        st_module.stop()
        return
    if feature not in access["features"]:
        st_module.info("Dieser Bereich ist in einem höheren Abo enthalten. / This feature requires a higher plan.")
        st_module.link_button("Abo / Subscription", "/de/account/")
        st_module.stop()


def assert_current_scope(cookies, scope: str, feature: str | None = None) -> None:
    if enabled():
        access = fetch_access(cookies)
        if access["account_id"] != scope:
            raise CustomerAccessDenied("Account ownership mismatch.")
        if feature and feature not in access["features"]:
            raise CustomerAccessDenied("Feature not included in the subscription.")
