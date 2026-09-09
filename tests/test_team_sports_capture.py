from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from context_sources import team_sports_capture as capture
from scanners.basketball_scanner import BasketballScanner
from scanners import completed_history as history
from tests.test_completed_sports_history import nba_payload, nhl_payload, euro_payload, cricket_payload

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
SOURCES = ("ESPN", "EuroLeague", "NHL")


def native_reply(provider):
    return {"ESPN": nba_payload, "EuroLeague": euro_payload, "NHL": nhl_payload}[provider]()


def fake_existing_get(monkeypatch, payload, calls):
    def get(url, **kwargs):
        calls.append((url, deepcopy(kwargs)))
        query = urlencode(kwargs.get("params") or {})
        return SimpleNamespace(status_code=200, url=url + ("?" + query if query else ""),
                               history=[], json=lambda: deepcopy(payload))
    monkeypatch.setattr(history.requests, "get", get)


def run_schedule(scanner, provider):
    if provider == "ESPN":
        return scanner.get_upcoming_games("NBA", date(2026, 1, 1), date(2026, 1, 1))
    if provider == "EuroLeague":
        return scanner.get_upcoming_games("Euroleague", date(2026, 5, 24), date(2026, 5, 24))
    return scanner.get_upcoming_nhl_games(date(2026, 1, 1), date(2026, 1, 1))


def completed_arguments(scanner, provider):
    return {
        "ESPN": ("nba:2026-01-01", scanner.espn_nba_url, history.parse_espn_results,
                 {"dates": "20260101-20260131", "limit": 1000}),
        "EuroLeague": ("E2025", scanner.euroleague_games_base + "/competitions/E/seasons/E2025/games",
                       history.parse_euroleague_results, {"limit": 500}),
        "NHL": ("2026-01-01", scanner.nhl_schedule_base + "/2026-01-01", history.parse_nhl_results, None),
    }[provider]


@pytest.mark.parametrize("provider", SOURCES)
@pytest.mark.parametrize("phase", ["schedule", "history"])
def test_actual_existing_json_reads_capture_before_lossy_status_filters(tmp_path, monkeypatch, provider, phase):
    calls, clocks = [], []
    fake_existing_get(monkeypatch, native_reply(provider), calls)
    monkeypatch.setattr(capture, "_receipt_now", lambda: clocks.append(NOW) or NOW)
    scanner = BasketballScanner()
    path = tmp_path / "context_models.db"
    with capture.capture_team_sports_worker(path=path) as observed:
        if phase == "schedule":
            # These actually completed bodies are discarded by upcoming parsers.
            assert run_schedule(scanner, provider) == []
        else:
            key, url, parser, params = completed_arguments(scanner, provider)
            cache = history.CompletedHistoryStore(tmp_path / "legacy.db", clock=lambda: NOW)
            assert history.fetch_page(cache, provider, key, url, parser, params=params) == (True, None)
    assert len(calls) == 1 and clocks == [NOW]
    assert len(observed.report()["receipt_refs"]) == 1
    assert path.is_file()


@pytest.mark.parametrize("provider", SOURCES)
def test_inactive_capture_never_reads_new_clock_or_creates_context_state(tmp_path, monkeypatch, provider):
    calls = []
    fake_existing_get(monkeypatch, native_reply(provider), calls)
    monkeypatch.setattr(capture, "_receipt_now", lambda: pytest.fail("default path sampled an additional clock"))
    assert run_schedule(BasketballScanner(), provider) == []
    assert len(calls) == 1 and not list(tmp_path.iterdir())


def test_active_team_capture_does_not_interpret_or_retime_cricket(tmp_path, monkeypatch):
    calls = []
    fake_existing_get(monkeypatch, cricket_payload(), calls)
    monkeypatch.setattr(capture, "_receipt_now", lambda: pytest.fail("Cricket entered new capture"))
    scanner = SimpleNamespace(rapidapi_key="fixture-only-key", cricket_api_key=None,
        cricbuzz_base="https://cricbuzz-cricket.p.rapidapi.com", headers={}, last_error=None)
    cache = history.CompletedHistoryStore(tmp_path / "legacy.db", clock=lambda: NOW)
    with capture.capture_team_sports_worker(path=tmp_path / "context_models.db") as observed:
        rows = history.completed_cricket(scanner, date(2026, 1, 1), NOW.date(), store=cache)
    assert len(rows) == 1 and rows[0]["provider"] == "Cricbuzz"
    assert observed.report()["status"] == "no_receipts"
    assert not (tmp_path / "context_models.db").exists() and len(calls) == 1


@pytest.mark.parametrize("provider", SOURCES)
def test_warm_legacy_cache_remains_baseline_not_forged_new_b1_receipt(tmp_path, monkeypatch, provider):
    scanner = BasketballScanner()
    key, url, parser, params = completed_arguments(scanner, provider)
    cache = history.CompletedHistoryStore(tmp_path / "legacy.db", clock=lambda: NOW)
    assert cache.reserve(provider, key, ttl=timedelta(hours=12), daily_limit=48)
    cache.record(provider, key, parser(native_reply(provider)))
    before = cache.read([provider], date(2026, 1, 1), NOW.date(), as_of=NOW)
    assert len(before) == 1
    monkeypatch.setattr(history.requests, "get", lambda *a, **k: pytest.fail("warm cache triggered another fetch"))
    monkeypatch.setattr(capture, "_receipt_now", lambda: pytest.fail("cache row became a native receipt"))
    path = tmp_path / "context_models.db"
    with capture.capture_team_sports_worker(path=path) as observed:
        assert history.fetch_page(cache, provider, key, url, parser, params=params) == (False, None)
    assert observed.report()["status"] == "no_receipts"
    assert cache.read([provider], date(2026, 1, 1), NOW.date(), as_of=NOW) == before
    assert not path.exists()


@pytest.mark.parametrize("provider", SOURCES)
def test_actual_json_receipt_is_not_backdated_to_cache_clock_or_body_time(tmp_path, monkeypatch, provider):
    from context_sources.team_sports_status import team_sport_observations_as_of
    calls, order = [], []
    fake_existing_get(monkeypatch, native_reply(provider), calls)
    actual_get = history.requests.get

    def received(*args, **kwargs):
        reply = actual_get(*args, **kwargs)
        decode = reply.json
        reply.json = lambda: order.append("json") or decode()
        reply.headers = {"Date": "Thu, 01 Jan 2026 00:00:00 GMT"}
        return reply

    monkeypatch.setattr(history.requests, "get", received)
    actual = NOW + timedelta(seconds=9)
    monkeypatch.setattr(capture, "_receipt_now", lambda: order.append("receipt") or actual)
    cache = history.CompletedHistoryStore(tmp_path / "legacy.db", clock=lambda: NOW)
    key, url, parser, params = completed_arguments(BasketballScanner(), provider)

    def parse(payload):
        order.append("parser")
        return parser(payload)

    path = tmp_path / "context_models.db"
    with capture.capture_team_sports_worker(path=path):
        assert history.fetch_page(cache, provider, key, url, parse, params=params) == (True, None)
    assert order == ["json", "receipt", "parser"]
    assert team_sport_observations_as_of(path, cutoff=NOW) == ()
    assert len(team_sport_observations_as_of(path, cutoff=actual)) == 1
    assert cache.read([provider], date(2026, 1, 1), NOW.date(), as_of=NOW)[0]["result_observed_at"] == NOW.isoformat()


@pytest.mark.parametrize("provider", SOURCES)
@pytest.mark.parametrize("defect", ["redirect", "url", "query", "metadata", "invalid_url"])
def test_response_binding_failure_is_capture_partial_and_never_legacy_error(tmp_path, monkeypatch, provider, defect):
    calls = []
    fake_existing_get(monkeypatch, native_reply(provider), calls)
    get = history.requests.get

    def malformed(*args, **kwargs):
        response = get(*args, **kwargs)
        if defect == "redirect":
            response.history = [SimpleNamespace(status_code=302)]
        elif defect == "url":
            response.url = response.url.replace("https://", "https://unbound.example/")
        elif defect == "query":
            response.url += "&scope=wrong" if "?" in response.url else "?scope=wrong"
        elif defect == "invalid_url":
            response.url = "https://[broken"
        else:
            del response.history
        return response

    monkeypatch.setattr(history.requests, "get", malformed)
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    path = tmp_path / "context_models.db"
    scanner = BasketballScanner()
    with capture.capture_team_sports_worker(path=path) as observed:
        assert run_schedule(scanner, provider) == []
    assert observed.report()["status"] == "partial"
    assert observed.report()["receipt_refs"] == [] and not path.exists()
    assert not scanner.errors and len(calls) == 1


@pytest.mark.parametrize("code", [206, 302, 404, 500])
def test_non_200_never_decodes_or_forges_capture_and_budget_stays_single(tmp_path, monkeypatch, code):
    calls = []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(status_code=code, json=lambda: pytest.fail("old non-200 was decoded"))

    monkeypatch.setattr(history.requests, "get", get)
    monkeypatch.setattr(capture, "_receipt_now", lambda: pytest.fail("non-JSON observation was invented"))
    cache = history.CompletedHistoryStore(tmp_path / "legacy.db", clock=lambda: NOW)
    key, url, parser, params = completed_arguments(BasketballScanner(), "ESPN")
    path = tmp_path / "context_models.db"
    with capture.capture_team_sports_worker(path=path) as observed:
        assert history.fetch_page(cache, "ESPN", key, url, parser, params=params) == (True, f"HTTP {code}")
        assert history.fetch_page(cache, "ESPN", key, url, parser, params=params) == (False, f"HTTP {code}")
    assert len(calls) == 1 and observed.report()["status"] == "no_receipts" and not path.exists()


def test_receipt_drains_when_later_worker_fails_and_owner_resets(tmp_path, monkeypatch):
    from context_sources.team_sports_status import team_sport_observations_as_of
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    fake_existing_get(monkeypatch, native_reply("ESPN"), [])
    path = tmp_path / "context_models.db"
    with pytest.raises(RuntimeError, match="later worker"):
        with capture.capture_team_sports_worker(path=path) as observed:
            run_schedule(BasketballScanner(), "ESPN")
            raise RuntimeError("later worker")
    assert observed.report()["status"] == "captured"
    assert len(team_sport_observations_as_of(path, cutoff=NOW)) == 1
    monkeypatch.setattr(capture, "_receipt_now", lambda: pytest.fail("leaked capture owner"))
    assert run_schedule(BasketballScanner(), "ESPN") == []


def test_capture_storage_failure_is_not_swallowed_as_provider_error(tmp_path, monkeypatch):
    from context_models.contracts import ContextIntegrityError
    fake_existing_get(monkeypatch, native_reply("ESPN"), [])
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)

    def corrupted(*args, **kwargs):
        raise ContextIntegrityError("broken real context store")

    monkeypatch.setattr(capture, "append_observation", corrupted)
    scanner = BasketballScanner()
    with pytest.raises(ContextIntegrityError, match="broken real context store"):
        with capture.capture_team_sports_worker(path=tmp_path / "context_models.db"):
            assert run_schedule(scanner, "ESPN") == []
    assert not scanner.errors
    assert capture._CURRENT.get() is None


def test_nested_owner_is_rejected_without_resetting_outer_owner(tmp_path, monkeypatch):
    from context_models.contracts import ContextContractError
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    fake_existing_get(monkeypatch, native_reply("ESPN"), [])
    with capture.capture_team_sports_worker(path=tmp_path / "outer.db") as outer:
        with pytest.raises(ContextContractError, match="already has an owner"):
            with capture.capture_team_sports_worker(path=tmp_path / "inner.db"):
                pytest.fail("second owner was allowed")
        assert run_schedule(BasketballScanner(), "ESPN") == []
    assert len(outer.report()["receipt_refs"]) == 1 and not (tmp_path / "inner.db").exists()


@pytest.mark.parametrize("provider", SOURCES)
def test_legacy_parser_error_still_retains_actual_native_response(tmp_path, monkeypatch, provider):
    from context_sources.team_sports_status import team_sport_observations_as_of
    fake_existing_get(monkeypatch, native_reply(provider), [])
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    key, url, _, params = completed_arguments(BasketballScanner(), provider)
    cache = history.CompletedHistoryStore(tmp_path / "legacy.db", clock=lambda: NOW)

    def broken(_):
        raise ValueError("legacy parser failed")

    path = tmp_path / "context_models.db"
    with capture.capture_team_sports_worker(path=path):
        assert history.fetch_page(cache, provider, key, url, broken, params=params) == (True, "ValueError")
    assert len(team_sport_observations_as_of(path, cutoff=NOW)) == 1


def test_actual_sqlite_corrupt_existing_receipt_fails_after_legacy_response(tmp_path, monkeypatch):
    import sqlite3
    from context_models.contracts import ContextIntegrityError
    fake_existing_get(monkeypatch, native_reply("ESPN"), [])
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    path = tmp_path / "context_models.db"
    with capture.capture_team_sports_worker(path=path):
        run_schedule(BasketballScanner(), "ESPN")
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE context_contents SET payload=?", (b"{}",))
    with pytest.raises(ContextIntegrityError, match="collision"):
        with capture.capture_team_sports_worker(path=path):
            assert run_schedule(BasketballScanner(), "ESPN") == []
    assert capture._CURRENT.get() is None


@pytest.mark.parametrize("provider", SOURCES)
def test_known_ids_in_partial_response_survive_without_whole_scope_health_claim(tmp_path, monkeypatch, provider):
    payload = native_reply(provider)
    if provider == "ESPN":
        payload["events"].append({"id": None, "competitions": []})
    elif provider == "EuroLeague":
        payload["data"].append({"id": None, "played": False})
    else:
        payload["gameWeek"].append({"games": [{"id": None, "gameState": "PST"}]})
    fake_existing_get(monkeypatch, payload, [])
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)
    with capture.capture_team_sports_worker(path=tmp_path / "context_models.db") as observed:
        run_schedule(BasketballScanner(), provider)
    report = observed.report()
    assert report["status"] == "partial" and len(report["receipt_refs"]) == 1
    assert "native-event-id-unavailable" in report["issues"]


def test_thread_local_capture_owners_persist_only_their_actual_receipts(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from context_sources.team_sports_status import team_sport_observations_as_of
    barrier = Barrier(2)
    monkeypatch.setattr(capture, "_receipt_now", lambda: NOW)

    def worker(index):
        path = tmp_path / f"context-{index}.db"
        payload = native_reply("ESPN")
        payload["events"][0]["competitions"][0]["id"] = str(100 + index)
        key, url, _, params = completed_arguments(BasketballScanner(), "ESPN")
        response = SimpleNamespace(status_code=200, history=[], url=url + "?" + urlencode(params))
        with capture.capture_team_sports_worker(path=path) as observed:
            barrier.wait(timeout=10)
            capture.observe_completed_team_sports_response("ESPN", key, url, params, payload, response)
        rows = team_sport_observations_as_of(path, cutoff=NOW)
        return observed.report(), rows

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(worker, [0, 1]))
    assert first[0]["receipt_refs"] != second[0]["receipt_refs"]
    assert first[1][0]["event_key"] == "espn:basketball:100"
    assert second[1][0]["event_key"] == "espn:basketball:101"
    assert capture._CURRENT.get() is None
