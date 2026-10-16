"""Offline native-shaped HTTP fixtures, real bounded B1 and shared reservations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from importlib import import_module
from functools import partial
import json
from pathlib import Path
import sqlite3

import pytest
import requests

from context_observations import _SELECT, _decode_receipt
from context_models.dataset import _reader
from scanners.completed_history import CompletedHistoryStore

NOW = datetime(2026, 10, 16, 20, 4, tzinfo=timezone.utc)
SAMPLES = json.loads((Path(__file__).parent / "fixtures" / "nhl_boxscore_native_samples.json").read_text(encoding="utf-8"))


def capture_module():
    return import_module("context_sources.nhl_capture")


def body(number=119, *, completed=False, days=1, home=13, away=16):
    raw = deepcopy(SAMPLES["completed" if completed else "future"])
    raw.update(id=2026020000 + number, season=20262027, gameType=2,
               startTimeUTC=(NOW + timedelta(days=-days if completed else days)).isoformat())
    raw["homeTeam"]["id"], raw["awayTeam"]["id"] = home, away
    return raw


def event(raw, *, completed=False):
    return {"source": "NHL", "provider": "NHL", "competition": "NHL", "league": "NHL",
            "sport": "ice_hockey", "game_id": raw["id"], "provider_event_id": str(raw["id"]),
            "event_id": str(raw["id"]), "season": raw["season"], "game_type": raw["gameType"],
            "home_team_id": str(raw["homeTeam"]["id"]), "away_team_id": str(raw["awayTeam"]["id"]),
            "home_team": "FLA", "away_team": "CHI", "start_time": raw["startTimeUTC"],
            "status": "completed" if completed else "upcoming",
            "source_observed_at": (NOW - timedelta(seconds=10)).isoformat(),
            **({"result_observed_at": (NOW - timedelta(seconds=10)).isoformat(),
                "home_score": raw["homeTeam"]["score"], "away_score": raw["awayTeam"]["score"],
                "last_period_type": raw["gameOutcome"]["lastPeriodType"]} if completed else {})}


class Response:
    def __init__(self, url, payload, *, status=200, final_url=None, chunks=None):
        self.url, self.status_code, self.history = final_url or url, status, []
        self.chunks = chunks if chunks is not None else [json.dumps(payload).encode()]

    def iter_content(self, chunk_size):
        yield from self.chunks

    def close(self):
        pass


def setup_capture(tmp_path, monkeypatch, bodies, *, clock=None, response=None):
    clock = clock or (lambda: NOW)
    store = CompletedHistoryStore(tmp_path / "sports_completed_history.db", clock=clock)
    calls = []

    def get(url, **kwargs):
        identifier = int(url.split("/")[-2])
        calls.append(identifier)
        assert kwargs == {"timeout": 10, "allow_redirects": False, "stream": True}
        if response:
            return response(url, bodies[identifier])
        return Response(url, bodies[identifier])

    monkeypatch.setattr(requests, "get", get)
    return tmp_path / "context.db", store, calls


def collect(path, store, events, history=(), **kwargs):
    return capture_module().collect_nhl_context(path=path, history_store=store,
        events=events, completed_rows=history, clock=kwargs.pop("clock", store.clock), **kwargs)


def rows(path):
    if not path.exists():
        return []
    with _reader(path) as connection:
        return [_decode_receipt(row) for row in connection.execute(_SELECT).fetchall()]


def test_native_candidates_are_persisted_once_with_actual_receipts_and_unchanged_history(tmp_path, monkeypatch):
    future, past = body(), body(118, completed=True)
    path, store, calls = setup_capture(tmp_path, monkeypatch, {r["id"]: r for r in (future, past)})
    events, history = [event(future)] * 2, [event(past, completed=True)] * 2
    before = deepcopy((events, history))
    report = collect(path, store, events, history)
    assert calls == [2026020119, 2026020118]
    assert report["eligible_games"] == report["requested"] == report["stored_receipts"] == 2
    assert report["stored_new_payload_bytes"] > 0 and report["reused"] == 0
    assert len(rows(path)) == 2 and (events, history) == before
    assert all(row["complete"] is False for row in rows(path))
    assert collect(path, store, events, history)["reused"] == 2
    assert len(calls) == 2


@pytest.mark.parametrize("mutation", [
    {"source": "API-Hockey"}, {"competition": "SHL"}, {"source_contract": "api-hockey-v1"},
    {"home_team_id": True}, {"provider_event_id": "https://secret"}, {"game_id": True},
    {"season": 20242025}, {"game_type": 1}, {"status": "live"},
    {"start_time": NOW.isoformat()}, {"source_observed_at": (NOW + timedelta(seconds=1)).isoformat()},
])
def test_ineligible_events_make_no_http_or_context_db(tmp_path, monkeypatch, mutation):
    raw = body()
    path, store, calls = setup_capture(tmp_path, monkeypatch, {raw["id"]: raw})
    report = collect(path, store, [dict(event(raw), **mutation)])
    assert not calls and not path.exists() and report["eligible_games"] == 0


def test_history_is_two_latest_completed_native_games_per_team_within_actual_decision(tmp_path, monkeypatch):
    future = body()
    pasts = [body(100+i, completed=True, days=i) for i in (1, 2, 3, 15)]
    history = [event(r, completed=True) for r in pasts]
    history += [dict(event(body(110, completed=True), completed=True), status="live"),
                dict(event(body(111, completed=True), completed=True), start_time=(NOW+timedelta(hours=1)).isoformat()),
                dict(event(body(112, completed=True), completed=True), result_observed_at=(NOW+timedelta(seconds=1)).isoformat()),
                dict(event(body(113, completed=True), completed=True), source="API-Hockey")]
    path, store, calls = setup_capture(tmp_path, monkeypatch, {r["id"]: r for r in [future, *pasts]})
    report = collect(path, store, [event(future)], history)
    assert set(calls) == {2026020119, 2026020101, 2026020102}
    assert report["stored_receipts"] == 3


@pytest.mark.parametrize("bad_response,code", [
    (lambda url, raw: Response(url, raw, status=302), "http_status"),
    (lambda url, raw: Response(url, raw, final_url="https://evil.invalid/secret"), "http_url"),
    (lambda url, raw: Response(url, raw, chunks=[b"x" * (256*1024+1)]), "body_limit"),
    (lambda url, raw: Response(url, raw, chunks=[b"not json"]), "invalid_body"),
    (lambda url, raw: Response(url, dict(raw, id=2026020120)), "invalid_body"),
    (lambda url, raw: Response(url, dict(raw, homeTeam={"id": 999})), "invalid_body"),
])
def test_http_boundary_rejects_unsafe_or_unbound_bodies_and_consumes_failure_budget(tmp_path, monkeypatch, bad_response, code):
    raw = body()
    path, store, calls = setup_capture(tmp_path, monkeypatch, {raw["id"]: raw}, response=bad_response)
    report = collect(path, store, [event(raw)])
    assert report["requested"] == 1 and report["errors"] == [code]
    assert not path.exists() and report["stored_receipts"] == 0
    assert collect(path, store, [event(raw)])["deferred_request_budget"] == 1
    assert len(calls) == 1
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT requests FROM history_budget WHERE provider='NHL-context'").fetchone() == (1,)


def test_receipt_clock_is_read_after_body_and_missing_stats_remain_unknown(tmp_path, monkeypatch):
    raw = body(118, completed=True)
    raw.pop("playerByGameStats")
    future = body()
    time = [NOW]

    def response(url, payload):
        result = Response(url, payload)
        def chunks(chunk_size):
            yield json.dumps(payload).encode()
            time[0] = NOW + timedelta(seconds=5)
        result.iter_content = chunks
        return result

    path, store, calls = setup_capture(tmp_path, monkeypatch, {r["id"]: r for r in (future, raw)},
                                       clock=lambda: time[0], response=response)
    report = collect(path, store, [event(future)], [event(raw, completed=True)])
    assert report["observed_at"] == [(NOW+timedelta(seconds=5)).isoformat()]
    assert all(row["observed_at"] == "2026-10-16T20:04:05.000000Z" for row in rows(path))
    stored = next(r for r in rows(path) if r["payload"]["status"] == "completed")
    assert all(t["players"] is None for t in stored["payload"]["data"]["teams"].values())


def test_batch_byte_budget_is_atomic(tmp_path, monkeypatch):
    future, past = body(), body(118, completed=True)
    path, store, calls = setup_capture(tmp_path, monkeypatch, {r["id"]: r for r in (future, past)})
    report = collect(path, store, [event(future)], [event(past, completed=True)], max_new_payload_bytes=5000)
    assert report["requested"] == report["deferred_storage_budget"] == 2
    assert report["stored_receipts"] == report["stored_new_payload_bytes"] == 0
    assert rows(path) == []


def test_shared_utc_daily_limit_stops_33rd_request_in_second_store_instance(tmp_path, monkeypatch):
    bodies = [body(i) for i in range(1, 34)]
    path, store, calls = setup_capture(tmp_path, monkeypatch, {r["id"]: r for r in bodies})
    first = collect(path, store, [event(r) for r in bodies[:31]])
    second_store = CompletedHistoryStore(store.path, clock=store.clock)
    second = collect(path, second_store, [event(r) for r in bodies[31:]])
    assert first["requested"] == 31 and second["requested"] == second["deferred_request_budget"] == 1
    assert len(calls) == 32 and 2026020033 not in calls


@pytest.mark.parametrize("change", ["schedule", "teams", "score", "phase", "ttl"])
def test_changed_native_revision_and_24h_boundary_refresh_cached_body(tmp_path, monkeypatch, change):
    future, past = body(), body(118, completed=True)
    time = [NOW]
    bodies = {r["id"]: r for r in (future, past)}
    path, store, calls = setup_capture(tmp_path, monkeypatch, bodies, clock=lambda: time[0])
    collect(path, store, [event(future)], [event(past, completed=True)])
    time[0] = NOW + timedelta(hours=1 if change != "ttl" else 24)
    if change == "schedule":
        future["startTimeUTC"] = (NOW + timedelta(days=2)).isoformat()
    elif change == "teams":
        future["homeTeam"]["id"] = 1
    elif change == "score":
        past["homeTeam"]["score"] = 5
    elif change == "phase":
        past["gameOutcome"]["lastPeriodType"] = "OT"
        past["periodDescriptor"].update(number=4, periodType="OT")
    report = collect(path, store, [event(future)], [event(past, completed=True)])
    if change == "ttl":
        # The target has started at the boundary: no source scope, no writes.
        assert report["requested"] == 0 and len(calls) == 2
        future["startTimeUTC"] = (NOW + timedelta(days=3)).isoformat()
        collect(path, store, [event(future)], [event(past, completed=True)])
        assert len(calls) == 4
    else:
        assert report["requested"] == report["reused"] == 1
        assert len(rows(path)) == 3


def test_unseen_games_precede_cached_rechecks_and_shared_limit_resets_next_utc_day(tmp_path, monkeypatch):
    time = [NOW]
    old, new = body(1, days=4), body(2, days=4)
    path, store, calls = setup_capture(tmp_path, monkeypatch, {r["id"]: r for r in (old, new)}, clock=lambda: time[0])
    collect(path, store, [event(old)])
    # 30 more actual reservations leave just one remaining slot today.
    for i in range(30):
        assert store.reserve("NHL-context", str(2026021000+i), ttl=timedelta(0), daily_limit=32)
    old["startTimeUTC"] = (NOW+timedelta(days=5)).isoformat()
    time[0] += timedelta(hours=1)
    report = collect(path, store, [event(old), event(new)])
    assert calls == [2026020001, 2026020002] and report["deferred_request_budget"] == 1
    time[0] += timedelta(days=1)
    report = collect(path, CompletedHistoryStore(store.path, clock=lambda: time[0]), [event(old)])
    assert report["requested"] == 1 and len(calls) == 3


def test_completed_loader_callback_receives_exact_scope_and_never_replaces_baseline_rows():
    from scanners.hockey_scanner import completed_hockey_loader
    from types import SimpleNamespace
    baseline, events, received = [{"legacy": "unchanged"}], ({"native": "scope"},), []
    scanner = SimpleNamespace(history_coverage={"status": "complete"},
        get_completed_games=lambda *args, **kwargs: baseline)

    def collector(**kwargs):
        received.append(kwargs)
        return [{"bad": "replacement"}]

    loader = completed_hockey_loader(scanner, NOW.date(), collector=collector)
    assert loader(as_of=NOW, events=events) is baseline
    assert received[0]["events"] is events and received[0]["completed_rows"] is baseline
    def fail(**kwargs):
        raise RuntimeError("https://secret.invalid?token=private")
    loader = completed_hockey_loader(scanner, NOW.date(), collector=fail)
    assert loader(as_of=NOW, events=events) is baseline
    assert loader.coverage == {"status": "complete"}


def test_real_default_source_wiring_collects_native_http_into_admin_report_only(tmp_path, monkeypatch):
    import config_loader
    import scanners.completed_history as completed
    import runtime_paths
    from wettfinder_automation import _riskobet_default_sources, _default_ice_hockey_risk_source

    current = body(days=2)
    current["startTimeUTC"] = (NOW+timedelta(hours=1)).isoformat()
    past = body(118, completed=True)
    path, store, calls = setup_capture(tmp_path, monkeypatch, {r["id"]: r for r in (current, past)})
    # Real history owner and real B1 store, private path selection only.
    monkeypatch.setattr(completed, "CompletedHistoryStore", partial(CompletedHistoryStore, store.path, clock=lambda: NOW))
    monkeypatch.setattr(config_loader, "load_app_config", lambda: config_loader.AppConfig())
    store.record("NHL", "seed", [dict(event(past, completed=True), home_score=3, away_score=2, winner_side="home")])
    # Stored at NOW would be causal, but emulate a real earlier result receipt.
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE history_result_revisions SET observed_at=?", ((NOW-timedelta(seconds=10)).isoformat(),))
    requests_seen = []
    def http(url, **kwargs):
        requests_seen.append(url)
        if "/gamecenter/" in url:
            assert kwargs == {"timeout": 10, "allow_redirects": False, "stream": True}
            return Response(url, current if str(current["id"]) in url else past)
        assert "/schedule/" in url
        return type("ScheduleResponse", (), {"status_code": 200, "url": url,
            "json": lambda self: {"gameWeek": [{"games": [current]}]}})()
    monkeypatch.setattr(requests, "get", http)
    # Isolated direct default calls perform no new boxscore collection.
    baseline = _default_ice_hockey_risk_source(NOW.date(), NOW)
    assert not path.exists() and not any("gamecenter" in u for u in requests_seen)
    report = {}
    sources, due = _riskobet_default_sources({}, now=NOW, target_date=NOW.date(), research_due=True,
        nhl_capture_path=path, nhl_capture_report=report, clock=lambda: NOW)
    batch = sources["ice_hockey"]()
    assert report["requested"] == report["stored_receipts"] == 2, report
    assert len(rows(path)) == 2 and due["ice_hockey"] is True
    assert batch.snapshots == baseline.snapshots
    assert "native_boxscore" not in json.dumps([s.to_dict() for s in batch.snapshots])
    before = len(requests_seen)
    sources, due = _riskobet_default_sources({}, now=NOW, target_date=NOW.date(), research_due=False,
        nhl_capture_path=path, nhl_capture_report=report, clock=lambda: NOW)
    assert "ice_hockey" not in sources and len(requests_seen) == before
    assert report["status"] == "not_due"


def test_production_owner_publishes_actual_capture_report_not_raw_source_bodies(tmp_path, monkeypatch):
    import config_loader
    import runtime_paths
    import scanners.completed_history as completed
    import wettfinder_automation as worker
    import context_sources.nhl_capture as capture
    from riskobet_automation import run_riskobet
    from test_wettfinder_automation import _football_snapshot

    raw = body()
    raw["startTimeUTC"] = (NOW+timedelta(hours=1)).isoformat()
    path, store, _ = setup_capture(tmp_path, monkeypatch, {raw["id"]: raw})
    monkeypatch.setattr(completed, "CompletedHistoryStore", partial(CompletedHistoryStore, store.path, clock=lambda: NOW))
    monkeypatch.setattr(config_loader, "load_app_config", lambda: config_loader.AppConfig())
    monkeypatch.setattr(runtime_paths, "CONTEXT_MODEL_DB_PATH", path)
    monkeypatch.setattr(capture, "_now", lambda: NOW)
    state = tmp_path / "wettfinder.json"
    monkeypatch.setattr(worker, "STATE_PATH", state)
    monkeypatch.setattr(worker, "TENNIS_DB", tmp_path / "tennis.db")
    monkeypatch.setattr(worker, "ESPORTS_DB", tmp_path / "esports.db")
    def http(url, **kwargs):
        if "/gamecenter/" in url:
            return Response(url, raw)
        assert "/schedule/" in url
        return type("ScheduleResponse", (), {"status_code": 200, "url": url,
            "json": lambda self: {"gameWeek": [{"games": [raw]}]}})()
    monkeypatch.setattr(requests, "get", http)
    def run_hockey(**kwargs):
        return run_riskobet(ice_hockey_source=kwargs["ice_hockey_source"], now=NOW,
                           db_path=tmp_path/"risk.db", latest_path=tmp_path/"risk.json")
    document = worker.run_wettfinder(now=NOW, state_path=state, config=config_loader.AppConfig(),
        football_scanner=lambda _day: _football_snapshot(NOW),
        football_context_refresher=lambda *_args: {},
        football_quote_loader=lambda *_args: ({}, []), tennis_quote_loader=lambda *_args: ({}, []),
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [],
        tennis_model_refresher=lambda **_kwargs: {}, riskobet_enabled=True,
        riskobet_runner=run_hockey, riskobet_settlement_runner=lambda **_kwargs: {},
        riskobet_db_path=tmp_path/"risk.db", riskobet_latest_path=tmp_path/"risk.json",
        evidence_db_path=tmp_path/"evidence.db", evidence_settlement_runner=lambda **_kwargs: {},
        esports_settlement_runner=lambda *_args, **_kwargs: {})
    assert document["nhl_context_capture"]["stored_receipts"] == 1, document["nhl_context_capture"]
    assert document["nhl_context_capture"]["observed_at"] == [NOW.isoformat()]
    assert json.loads(state.read_text(encoding="utf-8"))["nhl_context_capture"] == document["nhl_context_capture"]
    assert "playerByGameStats" not in json.dumps(document)
    assert len(rows(path)) == 1


def test_daily_closure_sanitizes_unexpected_capture_failures_and_keeps_report_shape(tmp_path):
    report = {}
    collector = capture_module().daily_nhl_collector(path=tmp_path/"context.db", report=report,
                                                    clock=lambda: NOW.replace(tzinfo=None))
    collector(events=[], completed_rows=[])
    assert report["status"] == "failed" and report["errors"] == ["capture_failed"]
    assert report["requested"] == report["stored_receipts"] == 0


def test_default_reservations_follow_explicit_context_db_root_not_import_default(tmp_path, monkeypatch):
    raw = body()
    context_path = tmp_path/"override"/"context.db"
    implicit_path = tmp_path/"implicit-runtime"/"sports_completed_history.db"
    # Real class, real B1: redirect only the unsafe import-default destination
    # into this test's directory, so a RED cannot pollute inherited runtime.
    monkeypatch.setattr(CompletedHistoryStore.__init__, "__defaults__", (implicit_path,))
    monkeypatch.setattr(capture_module(), "CompletedHistoryStore", CompletedHistoryStore)
    monkeypatch.setattr(requests, "get", lambda url, **_kwargs: Response(url, raw))
    report = capture_module().collect_nhl_context(path=context_path, events=[event(raw)],
                                                 completed_rows=[], clock=lambda: NOW)
    assert report["stored_receipts"] == 1
    assert not implicit_path.exists()
    sibling = context_path.parent/"sports_completed_history.db"
    with sqlite3.connect(sibling) as connection:
        assert connection.execute("SELECT requests FROM history_budget WHERE provider='NHL-context'").fetchone() == (1,)


def test_24h_cache_boundary_keeps_one_payload_and_new_receipt_is_not_backdated(tmp_path, monkeypatch):
    raw = body(days=4)
    time = [NOW]
    path, store, calls = setup_capture(tmp_path, monkeypatch, {raw["id"]: raw}, clock=lambda: time[0])
    first = collect(path, store, [event(raw)])
    time[0] += timedelta(hours=24, microseconds=-1)
    cached = collect(path, store, [event(raw)])
    assert cached["reused"] == 1 and cached["requested"] == 0 and cached["observed_at"] == []
    time[0] += timedelta(microseconds=1)
    fresh = collect(path, store, [event(raw)])
    assert fresh["requested"] == fresh["stored_receipts"] == 1 and len(calls) == 2
    assert fresh["stored_new_payload_bytes"] < first["stored_new_payload_bytes"]
    with _reader(path) as connection:
        assert connection.execute("SELECT count(*) FROM context_contents").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM context_observations").fetchone() == (2,)
    assert sorted(r["observed_at"] for r in rows(path)) == ["2026-10-16T20:04:00.000000Z", "2026-10-17T20:04:00.000000Z"]


def test_failed_http_keeps_30minute_cooldown_and_consumes_each_retry_without_secret_text(tmp_path, monkeypatch):
    raw = body()
    time = [NOW]
    def failed(url, payload):
        raise requests.RequestException("https://secret.invalid?key=private")
    path, store, calls = setup_capture(tmp_path, monkeypatch, {raw["id"]: raw},
                                       clock=lambda: time[0], response=failed)
    assert collect(path, store, [event(raw)])["errors"] == ["http_failed"]
    time[0] += timedelta(minutes=30, microseconds=-1)
    assert collect(path, store, [event(raw)])["requested"] == 0
    time[0] += timedelta(microseconds=1)
    report = collect(path, store, [event(raw)])
    assert report["requested"] == 1 and len(calls) == 2
    assert "private" not in json.dumps(report) and not path.exists()
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT requests FROM history_budget WHERE provider='NHL-context'").fetchone() == (2,)


def test_no_eligible_scope_does_not_create_any_db_and_import_or_cache_read_does_not_request(tmp_path, monkeypatch):
    from importlib import reload
    calls = []
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: calls.append(args))
    module = reload(capture_module())
    path = tmp_path/"context.db"
    report = module.collect_nhl_context(path=path, events=[], completed_rows=[], clock=lambda: NOW)
    assert report["requested"] == 0 and calls == []
    assert not path.exists() and not (tmp_path/"sports_completed_history.db").exists()


def test_oversized_storage_budget_configuration_is_rejected_before_any_request(tmp_path, monkeypatch):
    raw = body()
    path, store, calls = setup_capture(tmp_path, monkeypatch, {raw["id"]: raw})
    with pytest.raises(ValueError):
        collect(path, store, [event(raw)], max_new_payload_bytes=1024*1024+1)
    assert calls == [] and not path.exists()


def test_genuine_native_correction_is_retained_without_rewriting_owner_or_reusing_old_revision(tmp_path, monkeypatch):
    raw = body(days=4)
    time = [NOW]
    bodies = {raw["id"]: raw}
    path, store, calls = setup_capture(tmp_path, monkeypatch, bodies, clock=lambda: time[0])
    owner = [event(raw)]
    history = [event(body(118, completed=True, days=15), completed=True)]
    before = deepcopy((owner, history))
    collect(path, store, owner, history)
    corrected = body(119, completed=True)
    bodies[raw["id"]] = corrected
    # A previously matching cache expires normally; only then can the HTTP
    # source reveal a revision that the owner has not received yet.
    time[0] += timedelta(hours=24)
    report = collect(path, store, owner, history)
    assert report["stored_receipts"] == 1 and report["errors"] == ["owner_revision_mismatch"], json.dumps(report)
    assert len(rows(path)) == 2 and (owner, history) == before
    assert {r["payload"]["event"]["status"] for r in rows(path)} == {"scheduled", "completed"}
    time[0] += timedelta(hours=1)
    report = collect(path, store, owner, history)
    assert report["requested"] == 1 and report["reused"] == 0 and len(calls) == 3
    assert len(rows(path)) == 3
    with _reader(path) as connection:
        assert connection.execute("SELECT count(*) FROM context_contents").fetchone() == (2,)


@pytest.mark.parametrize("mutation", [
    {"result_observed_at": (NOW-timedelta(days=2)).isoformat()},
    {"home_score": None}, {"home_score": 2},
])
def test_completed_pool_requires_genuine_result_receipt_and_final_score(tmp_path, monkeypatch, mutation):
    future, past = body(), body(118, completed=True)
    path, store, calls = setup_capture(tmp_path, monkeypatch, {r["id"]: r for r in (future, past)})
    collect(path, store, [event(future)], [dict(event(past, completed=True), **mutation)])
    assert calls == [2026020119]


def test_default_utc_request_budget_survives_local_midnight_and_resets_at_utc_midnight(tmp_path, monkeypatch):
    local = timezone(timedelta(hours=2))
    time = [datetime(2026, 10, 16, 23, 30, tzinfo=local)]
    bodies = {raw["id"]: raw for raw in (body(i, days=4) for i in range(1, 34))}
    calls = []
    def http(url, **kwargs):
        identifier = int(url.split("/")[-2])
        calls.append(identifier)
        return Response(url, bodies[identifier])
    monkeypatch.setattr(requests, "get", http)
    path = tmp_path/"explicit-context"/"context.db"
    def collect_default(ids):
        return capture_module().collect_nhl_context(path=path, events=[event(bodies[i]) for i in ids],
            completed_rows=[], clock=lambda: time[0])

    first = collect_default(range(2026020001, 2026020033))
    assert first["requested"] == first["stored_receipts"] == 32
    assert first["decision_at"] == "2026-10-16T21:30:00+00:00"
    time[0] += timedelta(hours=1)  # Local midnight, still October 16 in UTC.
    same_utc_day = collect_default([2026020033])
    assert same_utc_day["decision_at"] == "2026-10-16T22:30:00+00:00"
    assert same_utc_day["requested"] == 0 and same_utc_day["deferred_request_budget"] == 1
    assert len(calls) == 32
    time[0] += timedelta(hours=2)  # Actual next UTC date permits a new request.
    next_utc_day = collect_default([2026020033])
    assert next_utc_day["requested"] == next_utc_day["stored_receipts"] == 1
    assert next_utc_day["decision_at"] == "2026-10-17T00:30:00+00:00"
    assert len(calls) == 33
    with sqlite3.connect(path.parent/"sports_completed_history.db") as connection:
        assert connection.execute("SELECT day,requests FROM history_budget WHERE provider='NHL-context' ORDER BY day").fetchall() == [
            ("2026-10-16", 32), ("2026-10-17", 1)]
        assert connection.execute("SELECT attempted_at,success_at FROM history_requests WHERE cache_key='NHL-context:2026020033'").fetchone() == (
            "2026-10-17T00:30:00+00:00", "2026-10-17T00:30:00+00:00")
    assert len(rows(path)) == 33


def test_default_store_clock_keeps_advancing_between_requests_in_one_collection(tmp_path, monkeypatch):
    local = timezone(timedelta(hours=2))
    time = [datetime(2026, 10, 17, 1, 59, tzinfo=local)]
    bodies = [body(i, days=4) for i in (1, 2)]
    calls = []
    def http(url, **kwargs):
        calls.append(url)
        raw = bodies[len(calls)-1]
        # Completion of the first actual body advances the live clock into
        # the next UTC day; the second reservation must use this new instant.
        response = Response(url, raw)
        def chunks(chunk_size):
            yield json.dumps(raw).encode()
            time[0] += timedelta(minutes=2)
        response.iter_content = chunks
        return response
    monkeypatch.setattr(requests, "get", http)
    path = tmp_path/"context.db"
    report = capture_module().collect_nhl_context(path=path, events=[event(raw) for raw in bodies],
        completed_rows=[], clock=lambda: time[0])
    assert report["requested"] == report["stored_receipts"] == 2
    assert report["decision_at"] == "2026-10-16T23:59:00+00:00"
    assert report["observed_at"] == ["2026-10-17T00:01:00+00:00", "2026-10-17T00:03:00+00:00"]
    with sqlite3.connect(path.parent/"sports_completed_history.db") as connection:
        assert connection.execute("SELECT day,requests FROM history_budget WHERE provider='NHL-context' ORDER BY day").fetchall() == [
            ("2026-10-16", 1), ("2026-10-17", 1)]
        assert connection.execute("SELECT attempted_at FROM history_requests WHERE cache_key='NHL-context:2026020002'").fetchone() == (
            "2026-10-17T00:01:00+00:00",)
