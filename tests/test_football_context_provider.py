"""Bounded new-source collection, not live model activation or fitted evidence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
import requests

import challenge_15k
from api_budget import APIBudgetPriority
from challenge_15k import ChallengeDataProvider
from context_models.contracts import ContextContractError, canonical_timestamp


SAMPLE = Path(__file__).parent / "fixtures/context/football/api-football-20260909.json"
NOW = datetime(2026, 9, 9, 9, tzinfo=timezone.utc)


def sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def current():
    detail = sample()["calls"][0]["samples"][1]
    return {"event_key": "api-football:football:1575469", "sport": "football", "competition": "94",
            "format": "90min", "home_id": "api-football:team:215", "away_id": "api-football:team:211",
            "scheduled_start": canonical_timestamp(detail["fixture"]["date"]),
            "schedule_revision": "source-test-v1", "status": "scheduled"}


def payload(rows):
    return {"errors": [], "results": len(rows), "paging": {"current": 1, "total": 1}, "response": deepcopy(rows)}


class Response:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return deepcopy(self.data)


def provider(monkeypatch, *, details=None, injuries=None):
    owner = ChallengeDataProvider("test-key-never-persisted", None)
    calls = []
    values = {"fixtures": payload(sample()["calls"][0]["samples"]) if details is None else details,
              "injuries": payload([]) if injuries is None else injuries}

    def fetch(url, **kwargs):
        calls.append((url.rsplit("/", 1)[-1], kwargs))
        data = values[calls[-1][0]]
        if isinstance(data, requests.RequestException):
            raise data
        return Response(data)

    monkeypatch.setattr(owner, "_rate_limit", lambda: None)
    monkeypatch.setattr(challenge_15k, "api_football_get", fetch)
    return owner, calls


def test_provider_uses_two_budgeted_calls_and_separate_actual_receipt_clocks(monkeypatch):
    owner, calls = provider(monkeypatch)
    clocks = iter([NOW, NOW + timedelta(seconds=2)])
    monkeypatch.setattr(owner, "_context_received_at", lambda: next(clocks))
    batch = owner.football_context_batch((current(),), historical_fixture_ids=(1570343,))
    assert len(calls) == 2
    assert calls[0][1]["params"] == {"ids": "1570343-1575469"}
    assert calls[1][1]["params"] == {"ids": "1575469"}
    assert all(call[1]["priority"] == APIBudgetPriority.BACKGROUND for call in calls)
    assert all(call[1]["allow_redirects"] is False and call[1]["timeout"] == 20 for call in calls)
    appearances = [r for r in batch["observations"] if r["record"]["kind"] == "appearance"]
    availability = [r for r in batch["observations"] if r["record"]["kind"] == "availability"]
    assert len(appearances) == 46 and len(availability) == 2
    assert {r["observed_at"] for r in appearances} == {canonical_timestamp(NOW)}
    assert {r["observed_at"] for r in availability} == {canonical_timestamp(NOW + timedelta(seconds=2))}
    assert all(r["record"]["complete"] is False for r in availability)
    assert all(r["record"]["published_at"] is None for r in batch["observations"])
    assert "test-key" not in json.dumps(batch)


@pytest.mark.parametrize("ids", [(True,), (-1,), (0,), ("1570343",), tuple(range(1, 22))])
def test_invalid_or_oversized_batch_fails_before_network(monkeypatch, ids):
    owner, calls = provider(monkeypatch)
    with pytest.raises(ContextContractError):
        owner.football_context_batch((current(),), historical_fixture_ids=ids)
    assert calls == []


def test_empty_request_does_not_fetch_or_invent_checks(monkeypatch):
    owner, calls = provider(monkeypatch)
    batch = owner.football_context_batch(())
    assert batch["observations"] == [] and batch["receipts"] == [] and calls == []


@pytest.mark.parametrize("bad", [requests.HTTPError("source unavailable"), ValueError("bad JSON"),
    {"errors": {"plan": "unavailable"}, "response": []}, payload([]) | {"paging": {"current": 1, "total": 2}},
    payload([]) | {"results": True}, payload([]) | {"response": [1]},
    payload([]) | {"results": 2}, payload([]) | {"paging": None}])
def test_unavailable_detail_call_never_retries_or_creates_old_history(monkeypatch, bad):
    owner, calls = provider(monkeypatch, details=bad)
    batch = owner.football_context_batch((current(),), historical_fixture_ids=(1570343,))
    assert len(calls) == 2
    assert not any(r["record"]["kind"] in {"appearance", "confirmed_lineup"} for r in batch["observations"])
    assert batch["receipts"][0]["status"] == "unavailable"
    assert batch["native_details"] == []


def test_failed_injury_source_does_not_turn_into_fresh_empty_list(monkeypatch):
    owner, calls = provider(monkeypatch, injuries=requests.HTTPError("not received"))
    batch = owner.football_context_batch((current(),), historical_fixture_ids=(1570343,))
    assert len(calls) == 2
    assert len([r for r in batch["observations"] if r["record"]["kind"] == "appearance"]) == 46
    assert not any(r["record"]["kind"] == "availability" for r in batch["observations"])
    assert batch["receipts"][1]["status"] == "unavailable"


@pytest.mark.parametrize("mutate", ["foreign", "duplicate", "wrong-team", "wrong-schedule"])
def test_invalid_native_binding_cannot_create_source_receipts(monkeypatch, mutate):
    details = deepcopy(sample()["calls"][0]["samples"])
    if mutate == "foreign":
        details[0]["fixture"]["id"] = 999
    elif mutate == "duplicate":
        details.append(deepcopy(details[0]))
    elif mutate == "wrong-team":
        details[1]["teams"]["home"]["id"] = 999
    else:
        details[1]["fixture"]["date"] = "2026-09-10T19:45:00+00:00"
    owner, calls = provider(monkeypatch, details=payload(details))
    batch = owner.football_context_batch((current(),), historical_fixture_ids=(1570343,))
    assert len(calls) == 2
    assert batch["receipts"][0]["status"] == "unavailable"
    assert batch["native_details"] == []
    assert not any(r["record"]["kind"] == "appearance" for r in batch["observations"])


def test_nonrequested_injuries_invalidate_source_not_a_healthy_claim(monkeypatch):
    owner, calls = provider(monkeypatch, injuries=payload(sample()["calls"][1]["samples"]))
    batch = owner.football_context_batch((current(),), historical_fixture_ids=(1570343,))
    assert len(calls) == 2
    assert not any(r["record"]["kind"] == "availability" for r in batch["observations"])
    assert batch["receipts"][1]["status"] == "unavailable"


def test_provider_does_not_accept_a_caller_supplied_historical_receipt(monkeypatch):
    owner, calls = provider(monkeypatch)
    with pytest.raises(TypeError):
        owner.football_context_batch((current(),), observed_at=NOW - timedelta(days=30))
    assert calls == []


@pytest.mark.parametrize("status", [200, 206, 302, 307, 503])
def test_actual_http_status_must_be_full_200_even_with_a_valid_body(monkeypatch, status):
    owner, calls = provider(monkeypatch)
    actual_calls = []
    def fetch(url, **kwargs):
        endpoint = url.rsplit("/", 1)[-1]
        actual_calls.append((endpoint, kwargs))
        response = requests.Response()
        response.status_code = status if endpoint == "fixtures" else 200
        response.url = url
        response._content = json.dumps(payload(sample()["calls"][0]["samples"] if endpoint == "fixtures" else [])).encode("utf-8")
        return response
    monkeypatch.setattr(challenge_15k, "api_football_get", fetch)
    batch = owner.football_context_batch((current(),), historical_fixture_ids=(1570343,))
    assert len(actual_calls) == 2
    assert batch["receipts"][0]["status"] == ("completed" if status == 200 else "unavailable")
    assert len([row for row in batch["observations"] if row["record"]["kind"] == "appearance"]) == (46 if status == 200 else 0)
    if status != 200:
        assert batch["native_details"] == []
