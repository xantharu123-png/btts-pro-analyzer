"""Free-plan The Odds API transport; one shared ledger, no stored API keys.

Sports/events discovery is credit-free. Paid-in-credits requests reserve their
worst-case market/region cost before HTTP, across all processes and consumers.
The free plan never upgrades itself: 500/month less 25 reserve, max 16/day.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
from pathlib import Path
import re
import threading
from typing import Mapping

import requests

from api_budget import (
    APIBudgetGovernor, APIBudgetPriority, APIBudgetUnavailable, DEFAULT_DB_PATH,
)

BASE_URL = "https://api.the-odds-api.com/v4"
MONTH_PROVIDER = "the-odds-api:month"
DAY_PROVIDER = "the-odds-api:day"
_CLIENTS = {}
_CLIENT_LOCK = threading.Lock()


def _tokens(value):
    if not isinstance(value, str):
        raise APIBudgetUnavailable("Invalid quota parameters")
    tokens = set(value.split(","))
    if not tokens or any(not re.fullmatch(r"[a-zA-Z0-9_]+", part) for part in tokens):
        raise APIBudgetUnavailable("Invalid quota parameters")
    return tokens


def request_cost(path, params):
    if path == "sports" or re.fullmatch(r"sports/[a-z0-9_]+/events", path):
        return 0
    if not re.fullmatch(r"sports/[a-z0-9_]+/(?:events/[a-zA-Z0-9_-]+/)?odds", path):
        raise APIBudgetUnavailable("Unreviewed Odds API endpoint")
    markets = _tokens(params.get("markets", "h2h"))
    if "bookmakers" in params:
        regions = math.ceil(len(_tokens(params["bookmakers"])) / 10)
    else:
        region_keys = _tokens(params.get("regions", ""))
        if not region_keys <= {"eu", "uk", "us", "us2", "au"}:
            raise APIBudgetUnavailable("Unreviewed Odds API region")
        regions = len(region_keys)
    return len(markets) * regions


def _header_count(headers, name):
    if not isinstance(headers, Mapping):
        return None
    raw = next((v for k, v in headers.items() if str(k).casefold() == name), None)
    text = str(raw)
    return int(text) if re.fullmatch(r"[0-9]{1,9}", text) else None


class OddsAPIClient:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.month = APIBudgetGovernor(
            db_path, daily_limit=500, critical_floor=1,
            recommendation_reserve=10, background_reserve=25, quota_period="month",
        )
        self.day = APIBudgetGovernor(
            db_path, daily_limit=20, critical_floor=1,
            recommendation_reserve=3, background_reserve=4,
        )

    def get(self, path, *, api_key, params=None, timeout=20, now=None, get=None):
        key = str(api_key or "").strip()
        if not key or any(c.isspace() for c in key):
            raise APIBudgetUnavailable("The Odds API key is missing or invalid")
        query = dict(params or {})
        if any(str(k).casefold() == "apikey" for k in query):
            raise APIBudgetUnavailable("API key must not be overridden")
        endpoint = str(path).strip("/")
        cost = request_cost(endpoint, query)
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        reservations = []
        try:
            if cost:
                for governor, provider in ((self.day, DAY_PROVIDER), (self.month, MONTH_PROVIDER)):
                    reservation = governor.reserve(
                        api_key=key, endpoint=endpoint, provider=provider, cost=cost,
                        priority=APIBudgetPriority.BACKGROUND, now=current,
                    )
                    reservations.append((governor, reservation))
        except Exception:
            for governor, reservation in reservations:
                governor.complete(reservation, error="quota reservation refused", now=current)
            raise
        try:
            response = (get or requests.get)(
                f"{BASE_URL}/{endpoint}", params={**query, "apiKey": key},
                timeout=timeout, allow_redirects=False,
            )
        except Exception as exc:
            for governor, reservation in reservations:
                governor.complete(reservation, error=type(exc).__name__, now=current)
            # Request exceptions can contain the URL and therefore the key.
            raise APIBudgetUnavailable(f"Odds API transport failed: {type(exc).__name__}") from None
        headers = getattr(response, "headers", {})
        remaining = _header_count(headers, "x-requests-remaining")
        used = _header_count(headers, "x-requests-used")
        status = getattr(response, "status_code", None)
        if not isinstance(status, int) or isinstance(status, bool):
            status = None
        limits = [500]
        if remaining is not None:
            limits.append(remaining)
        if used is not None:
            limits.append(max(0, 500 - used))
        if status in {401, 403}:
            limits.append(0)
        for governor, reservation in reservations:
            governor.complete(reservation, http_status=status, now=current)
        if len(limits) > 1:
            self.month.reconcile_usage(
                api_key=key, used=500 - min(limits), daily_limit=500,
                provider=MONTH_PROVIDER, now=current,
            )
        return response


def odds_api_get(path, *, api_key, params=None, timeout=20):
    ledger = Path(os.environ.get("BETBOY_API_BUDGET_DB") or DEFAULT_DB_PATH)
    identity = str(ledger.resolve())
    with _CLIENT_LOCK:
        client = _CLIENTS.get(identity)
        if client is None:
            client = _CLIENTS[identity] = OddsAPIClient(ledger)
    return client.get(path, api_key=api_key, params=params, timeout=timeout)
