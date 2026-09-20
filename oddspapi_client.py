"""Read-only free-plan transport. Shared budgets, bounded bodies, no key logs."""
from datetime import datetime, timezone
import json
import re
import time

import requests

from api_budget import APIBudgetGovernor, APIBudgetPriority, APIBudgetUnavailable, APIBudgetExceeded, DEFAULT_DB_PATH

BASE_URL = 'https://api.oddspapi.io/v4/'
MONTH_PROVIDER = 'oddspapi:month'
DAY_PROVIDER = 'oddspapi:day'
MAX_RESPONSE_BYTES = 8_000_000


class OddsPapiClient:
    def __init__(self, api_key, *, db_path=DEFAULT_DB_PATH, get=requests.get, now=None):
        if not isinstance(api_key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,512}', api_key):
            raise APIBudgetUnavailable('Missing or invalid OddsPapi credential')
        self.key, self.get_http = api_key, get
        self.now = now
        self.authorized = False
        self.next_call = 0.0
        self.month = APIBudgetGovernor(db_path, daily_limit=250, critical_floor=1,
            recommendation_reserve=10, background_reserve=25, quota_period='month')
        self.day = APIBudgetGovernor(db_path, daily_limit=10, critical_floor=1,
            recommendation_reserve=2, background_reserve=3)

    def _clock(self):
        current = self.now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise APIBudgetUnavailable('An aware clock is required')
        return current.astimezone(timezone.utc)

    def _request(self, endpoint, params):
        delay = self.next_call - time.monotonic()
        if delay > 0:
            time.sleep(min(delay, 1.05))
        self.next_call = time.monotonic() + 1.05
        response = None
        started = time.monotonic()
        try:
            response = self.get_http(BASE_URL + endpoint,
                params={**params, 'apiKey': self.key}, timeout=(3, 8),
                allow_redirects=False, stream=True)
            if response.status_code != 200:
                raise APIBudgetUnavailable(f'OddsPapi HTTP {response.status_code}')
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=65536):
                if time.monotonic() - started > 15:
                    raise APIBudgetUnavailable('OddsPapi response exceeded time limit')
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise APIBudgetUnavailable('OddsPapi response exceeds size limit')
                chunks.append(chunk)
            return json.loads(b''.join(chunks))
        except APIBudgetUnavailable:
            raise
        except Exception as exc:
            raise APIBudgetUnavailable(f'OddsPapi transport: {type(exc).__name__}') from None
        finally:
            if response is not None:
                response.close()

    def authorize(self):
        """Account endpoint is free; never return its credential-bearing body."""
        self.authorized = False
        payload = self._request('account', {})
        if not isinstance(payload, dict) or not isinstance(payload.get('subscriptions'), list):
            raise APIBudgetUnavailable('OddsPapi account is invalid')
        matches = [s for s in payload['subscriptions'] if isinstance(s, dict)
                   and s.get('subscription_id') == payload.get('current_subscription_id')]
        if len(matches) != 1:
            raise APIBudgetUnavailable('OddsPapi subscription is ambiguous')
        sub = matches[0]
        limit, used = sub.get('request_limit'), sub.get('request_count')
        if (not payload.get('current_subscription_id') or sub.get('is_active') is not True
                or sub.get('auto_renew') is not False or type(sub.get('price')) is bool
                or sub.get('price') not in (None, 0)
                or type(limit) is not int or not 1 <= limit <= 250
                or type(used) is not int or not 0 <= used <= limit):
            raise APIBudgetUnavailable('An active free OddsPapi plan is required')
        self.month.reconcile_usage(api_key=self.key, provider=MONTH_PROVIDER,
            used=250 - (limit - used), daily_limit=250, now=self._clock())
        self.authorized = True
        return {'limit': limit, 'used': used, 'remaining': limit - used}

    def get(self, endpoint, params):
        allowed = {'fixtures': {'from', 'to', 'statusId', 'language'},
                   'odds-by-tournaments': {'tournamentIds', 'bookmaker', 'verbosity', 'language'}}
        if endpoint not in allowed or set(params) - allowed[endpoint]:
            raise APIBudgetUnavailable('Unreviewed OddsPapi request')
        if not self.authorized:
            raise APIBudgetUnavailable('OddsPapi free plan has not been checked')
        reservations = []
        try:
            for governor, provider in ((self.day, DAY_PROVIDER), (self.month, MONTH_PROVIDER)):
                reservation = governor.reserve(api_key=self.key, provider=provider,
                    endpoint=endpoint, priority=APIBudgetPriority.BACKGROUND, now=self._clock())
                reservations.append((governor, reservation))
            return self._request(endpoint, params)
        finally:
            # Count failed calls conservatively, too. Never persist URLs or bodies.
            for governor, reservation in reservations:
                governor.complete(reservation, now=self._clock())

    def ensure_refresh_budget(self, required_calls=3):
        if type(required_calls) is not int or required_calls < 1:
            raise APIBudgetUnavailable('Invalid refresh budget')
        for governor, provider in ((self.day, DAY_PROVIDER), (self.month, MONTH_PROVIDER)):
            state = governor.snapshot(api_key=self.key, provider=provider, now=self._clock())
            if state.remaining_estimate - required_calls < governor.background_reserve:
                raise APIBudgetExceeded('OddsPapi refresh budget exhausted')
