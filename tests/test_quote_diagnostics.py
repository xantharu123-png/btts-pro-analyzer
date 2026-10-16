"""Candidate-scoped quote receipt facts, never provider payloads or secrets."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
import requests

import market_consensus
from api_budget import APIBudgetExceeded


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)


def _football_candidate():
    return {"candidate_id": "42:BTTS_YES", "fixture_id": 42,
            "market_key": "BTTS_YES", "sport": "Fussball"}


def _football_payload():
    return {"errors": [], "response": [{
        "fixture": {"id": 42, "date": "2030-01-01T16:00:00+00:00"},
        "update": NOW.isoformat(), "bookmakers": [{
            "id": 1, "name": "Book A", "bets": [{
                "name": "Both Teams Score", "values": [
                    {"value": "Yes", "odd": "1.01"},
                    {"value": "No", "odd": "3.00"},
                ],
            }],
        }],
    }]}


def _tennis_candidate():
    return {"candidate_id": "tennis-A", "sport": "Tennis", "market_key": "H2H",
            "competitor_a": "Anna Lena", "competitor_b": "Bea",
            "selected_competitor": "Anna Lena",
            "scheduled_start": "2030-01-01T16:00:00+00:00"}


def _tennis_event():
    return {"id": "event-1", "home_team": "Bea", "away_team": "Anna Lena",
            "commence_time": "2030-01-01T16:00:00+00:00", "bookmakers": [{
                "key": "book-a", "title": "Book A", "last_update": NOW.isoformat(),
                "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Anna Lena", "price": 1.01},
                    {"name": "Bea", "price": 3.0},
                ]}],
            }]}


def test_football_diagnostic_preserves_received_short_single_book_quote():
    diagnostics = {"unrelated": {"reason_code": "KEEP"}}
    quotes = market_consensus.parse_fixture_consensus(
        _football_payload(), [_football_candidate()], fetched_at=NOW,
        diagnostics=diagnostics,
    )

    assert quotes["42:BTTS_YES"].best_odds == 1.01
    assert diagnostics["42:BTTS_YES"] == {
        "reason_code": "OBSERVED", "fetched_at": NOW.isoformat(),
        "provider_updated_at": NOW.isoformat(), "bookmaker_count": 1,
    }
    assert diagnostics["unrelated"] == {"reason_code": "KEEP"}


@pytest.mark.parametrize("case,reason", [
    ("empty", "FIXTURE_ABSENT"), ("wrong_fixture", "IDENTITY_MISMATCH"),
    ("market", "MARKET_ABSENT"), ("selection", "SELECTION_ABSENT"),
    ("invalid", "INVALID_QUOTE"), ("bad_clock", "BAD_CLOCK"),
    ("future_clock", "BAD_CLOCK"), ("stale_clock", "STALE_CLOCK"),
    ("unsupported", "UNSUPPORTED"), ("provider_error", "REQUEST_FAILED"),
    ("malformed", "UNKNOWN_NOT_RECEIVED"),
])
def test_football_diagnostic_reports_the_actual_missing_quote_gate(case, reason):
    payload, candidate = _football_payload(), _football_candidate()
    entry = payload["response"][0]
    if case == "empty":
        payload["response"] = []
    elif case == "wrong_fixture":
        entry["fixture"]["id"] = 43
    elif case == "market":
        entry["bookmakers"][0]["bets"][0]["name"] = "Match Winner"
    elif case == "selection":
        entry["bookmakers"][0]["bets"][0]["values"] = [{"value": "No", "odd": "3.0"}]
    elif case == "invalid":
        entry["bookmakers"][0]["bets"][0]["values"][0]["odd"] = "NaN"
    elif case == "bad_clock":
        entry["update"] = "provider-secret-invalid-clock"
    elif case == "future_clock":
        entry["update"] = (NOW + timedelta(minutes=2)).isoformat()
    elif case == "stale_clock":
        entry["update"] = (NOW - timedelta(minutes=46)).isoformat()
    elif case == "unsupported":
        candidate["market_key"] = "SYNTHETIC_UNKNOWN"
    elif case == "provider_error":
        payload["errors"] = {"secret-key": "secret-provider-error"}
    elif case == "malformed":
        payload = None
    diagnostics = {}

    assert market_consensus.parse_fixture_consensus(
        payload, [candidate], fetched_at=NOW, diagnostics=diagnostics,
    ) == {}
    assert diagnostics["42:BTTS_YES"]["reason_code"] == reason
    assert "secret" not in str(diagnostics)


def test_retained_football_observation_is_not_diagnosed_as_current():
    payload = _football_payload()
    payload["response"][0]["update"] = (NOW - timedelta(hours=3)).isoformat()
    diagnostics = {}

    quotes = market_consensus.parse_fixture_consensus(
        payload, [_football_candidate()], fetched_at=NOW,
        retain_observations=True, diagnostics=diagnostics,
    )

    assert quotes["42:BTTS_YES"].best_odds == 1.01
    assert diagnostics["42:BTTS_YES"]["reason_code"] == "STALE_CLOCK"
    assert diagnostics["42:BTTS_YES"]["provider_updated_at"] == "2030-01-01T07:00:00+00:00"


@pytest.mark.parametrize("case,reason", [
    ("observed", "OBSERVED"), ("empty", "UNKNOWN_NOT_RECEIVED"),
    ("identity", "IDENTITY_MISMATCH"), ("market", "MARKET_ABSENT"),
    ("selection", "SELECTION_ABSENT"), ("invalid", "INVALID_QUOTE"),
    ("bad_clock", "BAD_CLOCK"), ("stale_clock", "STALE_CLOCK"),
])
def test_tennis_parser_diagnostic_uses_received_event_facts(case, reason):
    event = _tennis_event()
    market = event["bookmakers"][0]["markets"][0]
    if case == "empty":
        event = None
    elif case == "identity":
        event["away_team"] = "Another Player"
    elif case == "market":
        market["key"] = "spreads"
    elif case == "selection":
        market["outcomes"] = [{"name": "Bea", "price": 3.0}]
    elif case == "invalid":
        market["outcomes"][0]["price"] = 1.0
    elif case == "bad_clock":
        event["bookmakers"][0]["last_update"] = "secret-bad-clock"
    elif case == "stale_clock":
        event["bookmakers"][0]["last_update"] = (NOW - timedelta(minutes=46)).isoformat()
    diagnostics = {}

    quotes = market_consensus.parse_h2h_event_consensus(
        event, [_tennis_candidate()], fetched_at=NOW, diagnostics=diagnostics,
    )

    assert diagnostics["tennis-A"]["reason_code"] == reason
    assert "secret" not in str(diagnostics)
    if case == "observed":
        assert quotes["tennis-A"].best_odds == 1.01
        assert diagnostics["tennis-A"]["bookmaker_count"] == 1
    else:
        assert quotes == {}


@pytest.mark.parametrize("case,reason", [
    ("observed", "OBSERVED"), ("empty", "FIXTURE_ABSENT"),
    ("error", "REQUEST_FAILED"), ("provider_error", "REQUEST_FAILED"),
])
def test_football_fetch_passes_candidate_diagnostics_without_changing_pair_return(monkeypatch, case, reason):
    class Response:
        def raise_for_status(self):
            if case == "error":
                raise requests.RequestException("https://provider.invalid/?key=secret")

        def json(self):
            if case == "empty":
                return {"errors": [], "response": []}
            if case == "provider_error":
                return {"errors": {"secret-key": "secret-provider-error"}}
            return _football_payload()

    monkeypatch.setattr(market_consensus, "api_football_get", lambda *args, **kwargs: Response())
    diagnostics = {}
    returned = market_consensus.fetch_football_consensus(
        "secret", [_football_candidate()], now=NOW, diagnostics=diagnostics,
    )

    assert isinstance(returned, tuple) and len(returned) == 2
    assert diagnostics["42:BTTS_YES"]["reason_code"] == reason
    assert "secret" not in str(diagnostics) + str(returned[1])
    if case == "observed":
        assert returned[0]["42:BTTS_YES"].best_odds == 1.01


@pytest.mark.parametrize("case,reason", [
    ("observed", "OBSERVED"), ("empty", "FIXTURE_ABSENT"),
    ("duplicate", "IDENTITY_MISMATCH"), ("error", "REQUEST_FAILED"),
    ("discovery_error", "REQUEST_FAILED"),
])
def test_tennis_fetch_diagnostics_reuse_existing_bounded_calls(monkeypatch, case, reason):
    calls = []

    def provider(path, _key, **_kwargs):
        calls.append(path)
        if path == "sports/":
            return [{"key": "tennis_atp_test", "active": True}], None
        if path.endswith("/events"):
            if case == "discovery_error":
                return None, "secret-error"
            return [_tennis_event()], None
        if case == "error":
            return None, "secret-error"
        if case == "empty":
            return [], None
        if case == "duplicate":
            return [_tennis_event(), deepcopy(_tennis_event())], None
        return [_tennis_event()], None

    monkeypatch.setattr(market_consensus, "_odds_api_json", provider)
    diagnostics = {}
    returned = market_consensus.fetch_tennis_h2h_consensus(
        "secret", [_tennis_candidate()], now=NOW, diagnostics=diagnostics,
    )

    assert isinstance(returned, tuple) and len(returned) == 2
    assert diagnostics["tennis-A"]["reason_code"] == reason
    assert "secret" not in str(diagnostics)
    assert len(calls) == (2 if case == "discovery_error" else 3)
    if case == "observed":
        assert returned[0]["tennis-A"].best_odds == 1.01


@pytest.mark.parametrize("fetch,candidate", [
    (market_consensus.fetch_football_consensus, _football_candidate()),
    (market_consensus.fetch_tennis_h2h_consensus, _tennis_candidate()),
])
def test_missing_credentials_never_claim_a_quote_was_fetched(fetch, candidate):
    diagnostics = {}

    quotes, errors = fetch("", [candidate], now=NOW, diagnostics=diagnostics)

    assert quotes == {} and errors
    assert diagnostics[candidate["candidate_id"]]["reason_code"] == "REQUEST_FAILED"
    assert diagnostics[candidate["candidate_id"]]["error_type"] == "MISSING_CREDENTIAL"
    assert "fetched_at" not in diagnostics[candidate["candidate_id"]]


@pytest.mark.parametrize("fetch,candidate,transport", [
    (market_consensus.fetch_football_consensus, _football_candidate(), "api_football_get"),
    (market_consensus.fetch_tennis_h2h_consensus, _tennis_candidate(), "odds_api_get"),
])
@pytest.mark.parametrize("failure,error_type,status", [
    ("budget", "BUDGET_EXHAUSTED", None),
    ("timeout", "TIMEOUT", None),
    ("http401", "HTTP_ERROR", 401),
    ("http403", "HTTP_ERROR", 403),
    ("http429", "HTTP_ERROR", 429),
])
def test_request_diagnostic_distinguishes_budget_http_and_timeout_without_messages(
    monkeypatch, fetch, candidate, transport, failure, error_type, status,
):
    def failed(*_args, **_kwargs):
        message = "https://provider.invalid/?apiKey=secret-provider-text"
        if failure == "budget":
            raise APIBudgetExceeded(message)
        if failure == "timeout":
            raise requests.Timeout(message)
        response = requests.Response()
        response.status_code = status
        response.url = message
        raise requests.HTTPError(message, response=response)

    monkeypatch.setattr(market_consensus, transport, failed)
    diagnostics = {}

    quotes, errors = fetch("secret", [candidate], now=NOW, diagnostics=diagnostics)

    assert quotes == {} and errors
    receipt = diagnostics[candidate["candidate_id"]]
    assert receipt["reason_code"] == "REQUEST_FAILED"
    assert receipt["error_type"] == error_type
    assert receipt.get("http_status") == status
    assert receipt["checked_at"] == NOW.isoformat()
    assert set(receipt) <= {"reason_code", "error_type", "http_status", "checked_at"}
    assert "secret" not in str(receipt) + str(errors)


def test_football_deadline_keeps_first_receipt_and_defers_unrequested_fixture(monkeypatch):
    first = _football_candidate()
    second = {**first, "candidate_id": "43:BTTS_YES", "fixture_id": 43}
    clock, requested = [100.0], []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            clock[0] = 102.0
            return _football_payload()

    def provider(*_args, **kwargs):
        requested.append(kwargs["params"]["fixture"])
        return Response()

    monkeypatch.setattr(market_consensus, "monotonic", lambda: clock[0], raising=False)
    monkeypatch.setattr(market_consensus, "api_football_get", provider)
    diagnostics = {}

    quotes, errors = market_consensus.fetch_football_consensus(
        "test", [first, second], now=NOW, deadline=101.0, diagnostics=diagnostics,
    )

    assert errors == [] and requested == [42]
    assert list(quotes) == ["42:BTTS_YES"]
    assert diagnostics["42:BTTS_YES"]["reason_code"] == "OBSERVED"
    assert diagnostics["43:BTTS_YES"] == {"reason_code": "DEFERRED"}
